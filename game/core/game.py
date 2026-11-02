"""The Game object: owns all game state and every gameplay system.

This class is the single entry point the user interface talks to.  It has no
pygame code, so it can be unit-tested and reused if the game is ever ported to
another engine (for example for mobile).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from game.core.config import GameConfig
from game.core.numformat import clamp_big, format_money
from game.economy.formulas import bulk_cost, max_affordable, upgrade_cost
from game.economy.modifiers import Modifiers
from game.factories.factory import Factory, FactoryStats, LaunchResult
from game.managers.manager_system import ManagerSystem
from game.missions.mission_system import MissionSystem
from game.prestige.prestige_system import PrestigeSystem
from game.research.research_system import ResearchSystem
from game.shop.shop_system import ShopSystem

STAT_KEYS = ["rockets_launched", "total_earned", "upgrades_bought", "managers_hired",
             "research_done", "planets_unlocked", "prestiges", "floors_unlocked",
             "rockets_unlocked", "abilities_used", "taps", "components_made",
             "seconds_played", "rp_earned", "gems_earned", "best_income"]

DEFAULT_SETTINGS = {"master_volume": 0.8, "music_volume": 0.5, "sfx_volume": 0.8, "muted": False,
                    "launch_animations": True, "scientific": False, "show_fps": False,
                    "buy_amount": "1"}


@dataclass
class GameEvent:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class OfflineReport:
    seconds_away: float = 0.0
    seconds_counted: float = 0.0
    rockets: float = 0.0
    money: float = 0.0
    rp: float = 0.0
    capped: bool = False

    def merge(self, other: "OfflineReport") -> "OfflineReport":
        return OfflineReport(self.seconds_away + other.seconds_away,
                             self.seconds_counted + other.seconds_counted,
                             self.rockets + other.rockets, clamp_big(self.money + other.money),
                             self.rp + other.rp, self.capped or other.capped)

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict) -> "OfflineReport":
        return cls(**{k: data[k] for k in cls().__dict__ if k in data})


class Game:
    def __init__(self, config: GameConfig | None = None, now: float | None = None):
        self.config = config or GameConfig()
        econ = self.config.economy
        self.credits: float = float(econ["starting_credits"])
        self.gems: float = float(econ["starting_gems"])
        self.rp: float = 0.0
        self.run_earned: float = 0.0
        self.stats: dict[str, float] = {k: 0.0 for k in STAT_KEYS}
        self.stats["planets_unlocked"] = 1
        self.stats["rockets_unlocked"] = 1
        self.factories: dict[str, Factory] = {}
        first_planet = self.config.planet_list[0]["id"]
        self.factories[first_planet] = Factory(self.config, first_planet)
        self.current_planet = first_planet
        self.unlocked_rockets: set[str] = {self.config.rocket_list[0]["id"]}
        self.settings: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.tutorial: dict[str, Any] = {"step": 0, "done": False}
        self.pending_offline: OfflineReport | None = None
        now = time.time() if now is None else now
        self.created_at = now
        self.last_seen = now          # never moves backwards (clock-change protection)
        self.events: list[GameEvent] = []
        self.managers = ManagerSystem(self)
        self.research = ResearchSystem(self)
        self.prestige = PrestigeSystem(self)
        self.missions = MissionSystem(self)
        self.shop = ShopSystem(self)
        self.global_mods_cached = Modifiers()
        self.stats_cache: dict[str, FactoryStats] = {}
        self._accumulator = 0.0
        self._mission_timer = 0.0
        self.missions.refresh_daily(now)
        self.refresh_stats()

    # ------------------------------------------------------------------ events
    def emit(self, kind: str, **data: Any) -> None:
        self.events.append(GameEvent(kind, data))

    def toast(self, text: str) -> None:
        self.emit("toast", text=text)

    def drain_events(self) -> list[GameEvent]:
        events, self.events = self.events, []
        return events

    # ------------------------------------------------------------------ currency
    def earn(self, amount: float) -> None:
        amount = max(0.0, amount)
        self.credits = clamp_big(self.credits + amount)
        self.run_earned = clamp_big(self.run_earned + amount)
        self.stats["total_earned"] = clamp_big(self.stats["total_earned"] + amount)

    def spend_credits(self, amount: float) -> bool:
        if amount < 0 or amount > self.credits or math.isinf(amount):
            return False
        self.credits -= amount
        return True

    def spend_gems(self, amount: float) -> bool:
        if amount < 0 or amount > self.gems:
            return False
        self.gems -= amount
        return True

    def grant_reward(self, reward: dict, source: str = "") -> dict:
        """Pay out a reward dict like {"gems": 5, "rp": 10, "credits_minutes": 5}."""
        given: dict[str, float] = {}
        if reward.get("gems"):
            self.gems += reward["gems"]
            self.stats["gems_earned"] += reward["gems"]
            given["gems"] = reward["gems"]
        if reward.get("rp"):
            self.rp += reward["rp"]
            self.stats["rp_earned"] += reward["rp"]
            given["rp"] = reward["rp"]
        credits = float(reward.get("credits", 0))
        if reward.get("credits_minutes"):
            income = max(self.total_income(), 2.0)
            credits += income * 60 * reward["credits_minutes"]
        if credits:
            self.earn(credits)
            given["credits"] = credits
        self.emit("reward", source=source, given=given)
        return given

    # ------------------------------------------------------------------ modifiers
    def global_modifiers(self, include_temporary: bool = True) -> Modifiers:
        mods = self.research.modifiers().merged(self.prestige.modifiers())
        if include_temporary:
            mods = mods.merged(self.shop.modifiers())
        return mods

    def cost_mult(self) -> float:
        return max(0.2, self.global_mods_cached.m("cost"))

    def best_planet_cost_mult(self) -> float:
        return max(self.config.planets[p]["cost_mult"] for p in self.factories)

    def factory_stats(self, planet_id: str, include_temporary: bool = True,
                      global_mods: Modifiers | None = None) -> FactoryStats:
        factory = self.factories[planet_id]
        gmods = global_mods if global_mods is not None else self.global_modifiers(include_temporary)
        floor_mods, manager_factory_mods = self.managers.floor_and_factory_mods(
            planet_id, include_active=include_temporary)
        mods = gmods.merged(factory.factory_modifiers()).merged(manager_factory_mods)
        return factory.compute_stats(mods, floor_mods)

    def refresh_stats(self) -> None:
        self.global_mods_cached = self.global_modifiers(True)
        for pid in self.factories:
            self.stats_cache[pid] = self.factory_stats(pid, global_mods=self.global_mods_cached)

    def total_income(self) -> float:
        return sum(s.income_per_second for s in self.stats_cache.values())

    def total_auto_income(self) -> float:
        """Income per second from fully automated lines (used by offline and time warp)."""
        gmods = self.global_modifiers(False)
        total = 0.0
        for pid in self.factories:
            total += self.factory_stats(pid, include_temporary=False, global_mods=gmods).auto_income_per_second
        return total

    # ------------------------------------------------------------------ simulation
    def update(self, real_dt: float) -> None:
        """Advance the game by real elapsed time using a fixed timestep."""
        tick = self.config.economy["tick_seconds"]
        real_dt = max(0.0, min(real_dt, 1.0))  # big gaps are handled as offline time
        self._accumulator += real_dt
        steps = 0
        while self._accumulator >= tick and steps < 20:
            self._accumulator -= tick
            self.step(tick)
            steps += 1
        if steps >= 20:
            self._accumulator = 0.0

    def step(self, dt: float) -> None:
        self.stats["seconds_played"] += dt
        self.managers.tick(dt)
        self.shop.tick(dt)
        self.refresh_stats()
        for pid, factory in self.factories.items():
            stats = self.stats_cache[pid]
            made_before = factory.components_made
            for launch in factory.step(dt, stats):
                self._apply_launch(launch)
            self.stats["components_made"] += factory.components_made - made_before
        income = self.total_income()
        if income > self.stats["best_income"]:
            self.stats["best_income"] = income
        self._mission_timer += dt
        if self._mission_timer >= 0.5:
            self._mission_timer = 0.0
            self.missions.check_notifications()

    def _apply_launch(self, launch: LaunchResult, silent: bool = False) -> None:
        self.earn(launch.revenue)
        self.rp += launch.rp
        self.stats["rp_earned"] += launch.rp
        self.stats["rockets_launched"] += launch.count
        if not silent:
            self.emit("launch", planet=launch.planet_id, rocket=launch.rocket_id,
                      count=launch.count, revenue=launch.revenue, rp=launch.rp)

    # ------------------------------------------------------------------ player actions
    @property
    def factory(self) -> Factory:
        return self.factories[self.current_planet]

    def tap_floor(self, floor_id: str, planet_id: str | None = None) -> bool:
        factory = self.factories[planet_id or self.current_planet]
        econ = self.config.economy
        if self.config.floors[floor_id]["kind"] == "launch":
            return self.manual_launch(planet_id)
        ok = factory.tap(floor_id, econ["manual_tap_seconds"], econ["manual_max_seconds"])
        if ok:
            self.stats["taps"] += 1
            self.emit("tap", floor=floor_id)
        return ok

    def manual_launch(self, planet_id: str | None = None) -> bool:
        factory = self.factories[planet_id or self.current_planet]
        pad = factory.floors[factory._first_of_kind("launch")]
        if pad.manager_uid:
            return False
        if factory.ready < 1:
            self.toast("No rocket is ready yet")
            return False
        if factory.request_launch(self.config.economy["manual_launch_countdown"]):
            self.stats["taps"] += 1
            self.emit("countdown", planet=factory.planet_id)
            return True
        return False

    def max_level(self) -> int:
        return int(self.config.economy["max_floor_level"])

    def upgrade_quote(self, floor_id: str, amount: str, planet_id: str | None = None
                      ) -> tuple[int, float]:
        """How many levels ``amount`` ('1', '10', '25', 'max') buys and the total cost."""
        factory = self.factories[planet_id or self.current_planet]
        floor = factory.floors[floor_id]
        fdef = self.config.floors[floor_id]
        if floor.level <= 0:
            return 0, 0.0
        base = fdef["base_cost"] * self.config.planets[factory.planet_id]["cost_mult"] * self.cost_mult()
        remaining = self.max_level() - floor.level
        if remaining <= 0:
            return 0, 0.0
        if amount == "max":
            count = max_affordable(base, fdef["cost_growth"], floor.level, self.credits, remaining)
            count = max(count, 1)
        else:
            count = min(int(amount), remaining)
        return count, bulk_cost(base, fdef["cost_growth"], floor.level, count)

    def upgrade_floor(self, floor_id: str, amount: str = "1", planet_id: str | None = None) -> int:
        factory = self.factories[planet_id or self.current_planet]
        floor = factory.floors[floor_id]
        if floor.level <= 0:
            self.toast("Unlock this floor first")
            return 0
        count, cost = self.upgrade_quote(floor_id, amount, factory.planet_id)
        if count <= 0:
            self.toast("Already at max level")
            return 0
        if not self.spend_credits(cost):
            self.toast("Not enough credits")
            return 0
        old_level = floor.level
        floor.level += count
        self.stats["upgrades_bought"] += count
        milestone = None
        for req, mult in self.config.milestones:
            if old_level < req <= floor.level:
                milestone = (req, mult)
        self.emit("upgrade", floor=floor_id, levels=count, level=floor.level, milestone=milestone)
        self.refresh_stats()
        return count

    def unlock_floor(self, floor_id: str, planet_id: str | None = None) -> bool:
        factory = self.factories[planet_id or self.current_planet]
        floor = factory.floors.get(floor_id)
        if floor is None or floor.level > 0:
            return False
        cost = factory.unlock_cost(floor_id, self.cost_mult())
        if not self.spend_credits(cost):
            self.toast("Not enough credits")
            return False
        floor.level = 1
        self.stats["floors_unlocked"] += 1
        self.emit("floor_unlocked", floor=floor_id, planet=factory.planet_id)
        self.refresh_stats()
        return True

    def workforce_cost(self, workforce_id: str, planet_id: str | None = None) -> float:
        factory = self.factories[planet_id or self.current_planet]
        wdef = self.config.workforce[workforce_id]
        level = factory.workforce.get(workforce_id, 0)
        return upgrade_cost(wdef["base_cost"] * self.config.planets[factory.planet_id]["cost_mult"]
                            * self.cost_mult(), wdef["cost_growth"], level + 1)

    def buy_workforce(self, workforce_id: str, planet_id: str | None = None) -> bool:
        factory = self.factories[planet_id or self.current_planet]
        wdef = self.config.workforce[workforce_id]
        if factory.workforce[workforce_id] >= wdef["max_level"]:
            self.toast("Already at max level")
            return False
        if not self.spend_credits(self.workforce_cost(workforce_id, factory.planet_id)):
            self.toast("Not enough credits")
            return False
        factory.workforce[workforce_id] += 1
        self.stats["upgrades_bought"] += 1
        self.emit("workforce", id=workforce_id)
        self.refresh_stats()
        return True

    # rockets -----------------------------------------------------------
    def rocket_requirements(self, rocket_id: str) -> str:
        """Empty string if the rocket may be purchased, else what is missing."""
        rocket = self.config.rockets[rocket_id]
        if rocket.get("planet") and rocket["planet"] not in self.factories:
            return f"Unlock {self.config.planets[rocket['planet']]['name']} first"
        if rocket.get("research") and rocket["research"] not in self.research.done:
            return f"Research {self.config.research[rocket['research']]['name']}"
        return ""

    def unlock_rocket(self, rocket_id: str) -> bool:
        if rocket_id in self.unlocked_rockets:
            return False
        missing = self.rocket_requirements(rocket_id)
        if missing:
            self.toast(missing)
            return False
        if not self.spend_credits(self.config.rockets[rocket_id]["unlock_cost"]):
            self.toast("Not enough credits")
            return False
        self.unlocked_rockets.add(rocket_id)
        self.stats["rockets_unlocked"] = len(self.unlocked_rockets)
        self.emit("rocket_unlocked", rocket=rocket_id)
        return True

    def select_rocket(self, rocket_id: str, planet_id: str | None = None) -> bool:
        factory = self.factories[planet_id or self.current_planet]
        if rocket_id not in self.unlocked_rockets:
            self.toast("Unlock this rocket first")
            return False
        ok, reason = factory.can_build(rocket_id)
        if not ok:
            self.toast(reason)
            return False
        if factory.rocket_id == rocket_id:
            return True
        stats = self.stats_cache.get(factory.planet_id) or self.factory_stats(factory.planet_id)
        leftover = factory.launch_all_ready(stats)
        if leftover:
            self._apply_launch(leftover)
        factory.rocket_id = rocket_id
        factory.countdown = -1.0
        self.emit("rocket_selected", rocket=rocket_id, planet=factory.planet_id)
        self.refresh_stats()
        return True

    # planets -----------------------------------------------------------
    def planet_unlock_cost(self, planet_id: str) -> float:
        return self.config.planets[planet_id]["unlock_cost"] * self.global_mods_cached.m("planet_cost")

    def next_locked_planet(self) -> str | None:
        for planet in self.config.planet_list:
            if planet["id"] not in self.factories:
                return planet["id"]
        return None

    def unlock_planet(self, planet_id: str) -> bool:
        if planet_id in self.factories:
            return False
        if planet_id != self.next_locked_planet():
            self.toast("Unlock the previous planet first")
            return False
        if not self.spend_credits(self.planet_unlock_cost(planet_id)):
            self.toast("Not enough credits")
            return False
        self.factories[planet_id] = Factory(self.config, planet_id)
        self.stats["planets_unlocked"] = len(self.factories)
        self.emit("planet_unlocked", planet=planet_id)
        self.refresh_stats()
        return True

    def switch_planet(self, planet_id: str) -> bool:
        if planet_id not in self.factories:
            return False
        self.current_planet = planet_id
        self.emit("planet_switched", planet=planet_id)
        return True

    # queries -----------------------------------------------------------
    def max_floor_level(self, floor_id: str | None = None) -> int:
        best = 0
        for factory in self.factories.values():
            for fid, floor in factory.floors.items():
                if floor_id is None or fid == floor_id:
                    best = max(best, floor.level)
        return best

    def feature_unlocked(self, feature: str) -> tuple[bool, str]:
        s = self.stats
        if feature == "research":
            return (s["managers_hired"] >= 1 or self.research.done != set(),
                    "Hire your first manager to unlock Research")
        if feature == "planets":
            return (len(self.factories) > 1 or s["total_earned"] >= 1_000_000,
                    "Earn $1M in total to unlock Planets")
        if feature == "prestige":
            return (s["prestiges"] > 0 or s["total_earned"] >= 1e9,
                    "Earn $1B in total to unlock Space Legacy")
        return True, ""

    # ------------------------------------------------------------------ offline
    def offline_cap_seconds(self) -> float:
        hours = self.config.economy["offline_cap_hours"] + self.global_mods_cached.a("offline_cap_hours")
        return hours * 3600

    def offline_efficiency(self) -> float:
        econ = self.config.economy
        return min(econ["max_offline_efficiency"],
                   econ["offline_efficiency"] + self.global_mods_cached.a("offline_efficiency"))

    def apply_offline(self, now: float) -> OfflineReport | None:
        """Award progress for the time since ``last_seen``.  Safe against clock changes."""
        from game.economy.offline import compute_offline
        elapsed = now - self.last_seen
        if elapsed <= 0:
            # Clock moved backwards (or no time passed): award nothing.  We keep
            # last_seen so the player cannot gain by moving the clock back and forth.
            return None
        self.last_seen = now
        self.missions.refresh_daily(now)
        if elapsed < 30:
            # Short gaps (alt-tab, brief lag) simply run the normal simulation.
            remaining = elapsed
            tick = self.config.economy["tick_seconds"]
            while remaining > 0:
                step = min(tick * 5, remaining)
                self.step(step)
                remaining -= step
            return None
        report = compute_offline(self, elapsed)
        if report.money <= 0 and report.rp <= 0:
            return None
        self.pending_offline = report if self.pending_offline is None else self.pending_offline.merge(report)
        return self.pending_offline

    def collect_offline(self, multiplier: float = 1.0) -> OfflineReport | None:
        report = self.pending_offline
        if report is None:
            return None
        self.pending_offline = None   # cleared first so it can never be collected twice
        self.earn(report.money * multiplier)
        self.rp += report.rp
        self.stats["rp_earned"] += report.rp
        self.stats["rockets_launched"] += report.rockets
        self.emit("offline_collected", money=report.money * multiplier)
        return report

    def touch(self, now: float) -> None:
        """Record that the player is active right now (called by the app/autosave)."""
        if now > self.last_seen:
            self.last_seen = now

    # ------------------------------------------------------------------ prestige reset
    def reset_run(self) -> None:
        first_planet = self.config.planet_list[0]["id"]
        self.managers.unassign_all()
        self.factories = {first_planet: Factory(self.config, first_planet)}
        self.current_planet = first_planet
        self.unlocked_rockets = {self.config.rocket_list[0]["id"]}
        self.credits = float(self.prestige.start_credits())
        self.run_earned = 0.0
        self.shop.boosts = []
        self.pending_offline = None
        self.refresh_stats()

    # ------------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        return {
            "version": self.config.economy["save_version"],
            "credits": self.credits, "gems": self.gems, "rp": self.rp,
            "run_earned": self.run_earned, "stats": dict(self.stats),
            "factories": {pid: f.to_dict() for pid, f in self.factories.items()},
            "current_planet": self.current_planet,
            "unlocked_rockets": sorted(self.unlocked_rockets),
            "settings": dict(self.settings), "tutorial": dict(self.tutorial),
            "created_at": self.created_at, "last_seen": self.last_seen,
            "pending_offline": self.pending_offline.to_dict() if self.pending_offline else None,
            "managers": self.managers.to_dict(), "research": self.research.to_dict(),
            "prestige": self.prestige.to_dict(), "missions": self.missions.to_dict(),
            "shop": self.shop.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict, config: GameConfig | None = None) -> "Game":
        game = cls(config, now=float(data.get("last_seen", time.time())))
        cfg = game.config

        def num(key: str, default: float = 0.0) -> float:
            try:
                value = float(data.get(key, default))
            except (TypeError, ValueError):
                return default
            return max(0.0, clamp_big(value)) if value == value else default

        game.credits, game.gems, game.rp = num("credits"), num("gems"), num("rp")
        game.run_earned = num("run_earned")
        for key, value in data.get("stats", {}).items():
            if key in game.stats:
                game.stats[key] = max(0.0, float(value))
        factories = {}
        for pid, fdata in data.get("factories", {}).items():
            if pid in cfg.planets:
                factories[pid] = Factory.from_dict(cfg, fdata)
        first = cfg.planet_list[0]["id"]
        if first not in factories:
            factories[first] = Factory(cfg, first)
        game.factories = factories
        game.current_planet = data.get("current_planet", first)
        if game.current_planet not in game.factories:
            game.current_planet = first
        game.unlocked_rockets = {r for r in data.get("unlocked_rockets", []) if r in cfg.rockets}
        game.unlocked_rockets.add(cfg.rocket_list[0]["id"])
        game.settings.update({k: v for k, v in data.get("settings", {}).items() if k in DEFAULT_SETTINGS})
        game.tutorial.update(data.get("tutorial", {}))
        game.created_at = float(data.get("created_at", game.created_at))
        game.last_seen = float(data.get("last_seen", game.last_seen))
        if data.get("pending_offline"):
            game.pending_offline = OfflineReport.from_dict(data["pending_offline"])
        game.managers.load(data.get("managers", {}))
        game.research.load(data.get("research", {}))
        game.prestige.load(data.get("prestige", {}))
        game.missions.load(data.get("missions", {}))
        game.shop.load(data.get("shop", {}))
        # Repair references between managers and floors.
        for factory in game.factories.values():
            for floor in factory.floors.values():
                inst = game.managers.get(floor.manager_uid)
                if inst is None or inst.planet != factory.planet_id or inst.floor != floor.id:
                    floor.manager_uid = None
        for inst in game.managers.instances:
            factory = game.factories.get(inst.planet) if inst.planet else None
            if factory is None or inst.floor not in factory.floors or \
                    factory.floors[inst.floor].manager_uid != inst.uid:
                inst.planet = inst.floor = None
        for factory in game.factories.values():
            ok, _ = factory.can_build(factory.rocket_id)
            if not ok or factory.rocket_id not in game.unlocked_rockets:
                factory.rocket_id = cfg.rocket_list[0]["id"]
        game.stats["planets_unlocked"] = len(game.factories)
        game.stats["rockets_unlocked"] = len(game.unlocked_rockets)
        game.refresh_stats()
        game.events.clear()
        return game

    def describe_money(self, value: float) -> str:
        return format_money(value, self.settings.get("scientific", False))
