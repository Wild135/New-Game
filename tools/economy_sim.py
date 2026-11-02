"""Automated economy simulation.

A bot plays the real game logic (no graphics) with different strategies and
reports when key milestones happen and how much money it has at checkpoints.

Usage:
    python tools/economy_sim.py                # 1 hour, both strategies
    python tools/economy_sim.py --hours 168    # one week
    python tools/economy_sim.py --offline      # test offline progression
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.core.game import Game  # noqa: E402
from game.core.numformat import format_duration, format_money  # noqa: E402

CHECKPOINTS = [300, 1800, 3600, 6 * 3600, 86400, 3 * 86400, 7 * 86400]


class Bot:
    def __init__(self, game: Game, strategy: str, prestige: bool = True):
        self.game = game
        self.strategy = strategy
        self.allow_prestige = prestige
        self.firsts: dict[str, float] = {}

    def mark(self, key: str, now: float) -> None:
        self.firsts.setdefault(key, now)

    def act(self, now: float) -> None:
        g = self.game
        for pid, factory in g.factories.items():
            for fid, floor in factory.floors.items():
                if floor.level > 0 and floor.manager_uid is None and g.config.floors[fid]["kind"] in (
                        "producer", "transport", "assembly"):
                    g.tap_floor(fid, pid)
            if factory.ready >= 1:
                pad = factory.floors["launchpad"]
                if pad.manager_uid is None:
                    g.manual_launch(pid)
        g.missions.claim_main()
        for ach in g.config.achievement_list:
            g.missions.claim_achievement(ach["id"])
        for i in range(len(g.missions.daily)):
            g.missions.claim_daily(i)
        # Research: cheapest available
        options = [r for r in g.config.research_list if g.research.state(r["id"]) == "available"]
        options.sort(key=lambda r: r["cost"])
        for r in options:
            if g.rp >= r["cost"]:
                g.research.research(r["id"])
                self.mark("first_research", now)
        self.hire_managers(now)
        self.buy_stuff(now)
        if self.allow_prestige:
            stars = g.prestige.estimated_stars()
            if stars >= max(10, g.prestige.total_stars * 1.0) and g.prestige.can_prestige()[0]:
                g.prestige.prestige()
                self.mark("first_prestige", now)
                # spend stars
                for _ in range(50):
                    best = min(g.config.legacy_upgrades, key=lambda u: g.prestige.upgrade_cost(u))
                    if not g.prestige.buy_upgrade("legacy_production"):
                        break
                    del best

    def hire_managers(self, now: float) -> None:
        g = self.game
        for pid, factory in g.factories.items():
            for fid in factory.ordered_floor_ids():
                floor = factory.floors[fid]
                kind = g.config.floors[fid]["kind"]
                if floor.level <= 0 or floor.manager_uid or kind == "support":
                    continue
                # reuse a free manager first
                free = [m for m in g.managers.instances if m.planet is None and g.managers.fits(m, kind)]
                if free:
                    g.managers.assign(free[0].uid, pid, fid)
                    continue
                candidates = [m["id"] for m in g.config.manager_list if m["rarity"] == "common"
                              and g.managers.fits(m["id"], kind)]
                candidates.sort(key=lambda d: g.managers.hire_cost(d)[0])
                for def_id in candidates:
                    cost, cur = g.managers.hire_cost(def_id)
                    if cur == "credits" and g.credits >= cost:
                        inst = g.managers.hire(def_id)
                        if inst:
                            g.managers.assign(inst.uid, pid, fid)
                            self.mark("first_manager", now)
                        break
                for def_id in [m["id"] for m in g.config.manager_list if m["rarity"] in ("epic", "legendary")]:
                    if g.managers.can_hire(def_id)[0] and g.managers.fits(def_id, kind):
                        inst = g.managers.hire(def_id)
                        if inst:
                            g.managers.assign(inst.uid, pid, fid)
        if all(f.manager_uid for fid, f in g.factory.floors.items()
               if f.level > 0 and g.config.floors[fid]["kind"] != "support"):
            self.mark("full_automation", now)
        for inst in g.managers.instances:
            if inst.planet and inst.cooldown <= 0:
                g.managers.activate(inst.uid)

    def buy_stuff(self, now: float) -> None:
        g = self.game
        # planets
        nxt = g.next_locked_planet()
        if nxt and g.credits >= g.planet_unlock_cost(nxt):
            g.unlock_planet(nxt)
            self.mark(f"planet_{nxt}", now)
        for pid in list(g.factories):
            factory = g.factories[pid]
            # rockets: unlock & select the most valuable buildable rocket
            for rocket in g.config.rocket_list:
                rid = rocket["id"]
                if rid not in g.unlocked_rockets and not g.rocket_requirements(rid) \
                        and g.credits >= rocket["unlock_cost"] * 1.2:
                    if g.unlock_rocket(rid):
                        self.mark(f"rocket_{rid}", now)
            best = None
            for rid in g.unlocked_rockets:
                ok, _ = factory.can_build(rid)
                if ok:
                    val = g.config.rockets[rid]["value"]
                    if best is None or val > g.config.rockets[best]["value"]:
                        best = rid
            if best and best != factory.rocket_id:
                g.select_rocket(best, pid)
            # unlock floors needed for next rocket
            for fid in factory.ordered_floor_ids():
                floor = factory.floors[fid]
                if floor.level == 0:
                    cost = factory.unlock_cost(fid, g.cost_mult())
                    if g.credits >= cost * 1.5:
                        if g.unlock_floor(fid, pid):
                            self.mark("first_floor_unlock", now)
            # workforce
            for wid in factory.workforce:
                cost = g.workforce_cost(wid, pid)
                if g.credits >= cost * 4:
                    g.buy_workforce(wid, pid)
            # upgrades
            for _ in range(60):
                stats = g.stats_cache[pid]
                if self.strategy == "bottleneck":
                    target = stats.bottleneck
                    if target is None or target.startswith("missing"):
                        break
                else:  # cheapest
                    ids = [f for f in factory.ordered_floor_ids() if factory.floors[f].level > 0
                           and g.config.floors[f]["kind"] != "support"]
                    target = min(ids, key=lambda f: g.upgrade_quote(f, "1", pid)[1])
                count, cost = g.upgrade_quote(target, "1", pid)
                if count <= 0 or cost > g.credits:
                    break
                g.upgrade_floor(target, "1", pid)
                self.mark("first_upgrade", now)
            # support floors occasionally
            for fid in factory.ordered_floor_ids():
                if g.config.floors[fid]["kind"] == "support" and factory.floors[fid].level > 0:
                    count, cost = g.upgrade_quote(fid, "1", pid)
                    if count and cost < g.credits * 0.1:
                        g.upgrade_floor(fid, "1", pid)


def run(strategy: str, hours: float, prestige: bool, verbose: bool = True) -> dict:
    game = Game(now=0.0)
    bot = Bot(game, strategy, prestige)
    total = hours * 3600
    now = 0.0
    checkpoints = [c for c in CHECKPOINTS if c <= total] + ([total] if total not in CHECKPOINTS else [])
    results = {}
    next_cp = 0
    started = time.time()
    while now < total:
        # Fine steps early (manual tapping matters), coarse steps later.
        dt = 0.1 if now < 1800 else (0.5 if now < 6 * 3600 else 2.0)
        act_every = 1.0 if now < 1800 else (5.0 if now < 6 * 3600 else 20.0)
        n = int(act_every / dt)
        bot.act(now)
        for _ in range(n):
            game.step(dt)
        game.drain_events()
        now += act_every
        if game.stats["rockets_launched"] >= 1:
            bot.mark("first_launch", now)
        while next_cp < len(checkpoints) and now >= checkpoints[next_cp]:
            cp = checkpoints[next_cp]
            results[cp] = (game.credits, game.total_income(), game.stats["total_earned"],
                           len(game.factories), game.prestige.total_stars, game.rp)
            next_cp += 1
    if verbose:
        print(f"\n=== Strategy: {strategy}  ({hours}h simulated in {time.time() - started:.1f}s) ===")
        for key, value in sorted(bot.firsts.items(), key=lambda kv: kv[1]):
            print(f"  {key:<28} at {format_duration(value)}")
        for cp, (credits, income, earned, planets, stars, rp) in results.items():
            print(f"  @{format_duration(cp):>9}: credits {format_money(credits):>10}  income "
                  f"{format_money(income):>10}/s  earned {format_money(earned):>10}  planets {planets}"
                  f"  stars {stars}  rp {rp:.0f}")
        print("  floors:", {f: fl.level for f, fl in game.factory.floors.items()},
              "rocket:", game.factory.rocket_id)
    return {"firsts": bot.firsts, "results": results, "game": game}


def offline_test() -> None:
    print("\n=== Offline progression test ===")
    out = run("bottleneck", 0.5, prestige=False, verbose=False)
    game = out["game"]
    game.last_seen = 1800
    for hours in (1, 4, 8, 24):
        g2 = Game.from_dict(game.to_dict(), game.config)
        report = g2.apply_offline(1800 + hours * 3600)
        if report:
            print(f"  away {hours:>2}h -> counted {format_duration(report.seconds_counted)} "
                  f"rockets {report.rockets:.0f} money {format_money(report.money)} capped={report.capped}")
        else:
            print(f"  away {hours}h -> nothing (no automated line)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--strategy", choices=["bottleneck", "cheapest", "both"], default="both")
    parser.add_argument("--no-prestige", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    strategies = ["bottleneck", "cheapest"] if args.strategy == "both" else [args.strategy]
    for strat in strategies:
        run(strat, args.hours, not args.no_prestige)
    if args.offline:
        offline_test()
