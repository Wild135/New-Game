"""Gameplay system tests: upgrades, managers, research, rockets, planets, prestige, missions, shop."""
import math

import pytest

from game.core.game import Game
from tests.conftest import automate_earth


def test_cannot_spend_more_than_available(game):
    game.credits = 3
    assert game.upgrade_floor("parts") == 0
    assert game.credits == 3
    assert not game.spend_credits(5)
    assert not game.spend_credits(-1)
    assert not game.spend_credits(float("inf"))


def test_upgrade_costs_money_and_raises_level(game):
    game.credits = 100
    count, cost = game.upgrade_quote("parts", "1")
    assert count == 1
    assert game.upgrade_floor("parts") == 1
    assert game.factory.floors["parts"].level == 2
    assert math.isclose(game.credits, 100 - cost)
    assert game.stats["upgrades_bought"] == 1


def test_bulk_and_max_upgrades(rich_game):
    g = rich_game
    assert g.upgrade_floor("parts", "10") == 10
    assert g.factory.floors["parts"].level == 11
    g.credits = 1000
    count, cost = g.upgrade_quote("parts", "max")
    assert cost <= 1000
    assert g.upgrade_floor("parts", "max") == count
    assert g.credits >= 0


def test_max_level_cap(rich_game):
    g = rich_game
    g.factory.floors["parts"].level = g.max_level()
    assert g.upgrade_floor("parts") == 0


def test_milestone_event(rich_game):
    g = rich_game
    g.factory.floors["parts"].level = 9
    g.upgrade_floor("parts")
    events = [e for e in g.drain_events() if e.kind == "upgrade"]
    assert events and events[0].data["milestone"] == (10, 2)


def test_unlock_floor(rich_game):
    g = rich_game
    assert g.unlock_floor("engines")
    assert g.factory.floors["engines"].level == 1
    assert not g.unlock_floor("engines")      # already unlocked


def test_manager_hire_assign_and_automation(game):
    game.credits = 1000
    inst = game.managers.hire("alex")
    assert inst is not None and game.stats["managers_hired"] == 1
    assert not game.managers.assign(inst.uid, "earth", "transport")  # wrong slot
    assert game.managers.assign(inst.uid, "earth", "parts")
    assert game.factory.floors["parts"].manager_uid == inst.uid
    for _ in range(50):
        game.step(0.1)
    assert game.factory.floors["parts"].storage > 0  # works without taps


def test_manager_bonus_affects_rate(game):
    before = game.factory_stats("earth").rate["parts"]
    game.credits = 1000
    inst = game.managers.hire("alex")
    game.managers.assign(inst.uid, "earth", "parts")
    after = game.factory_stats("earth").rate["parts"]
    assert math.isclose(after / before, 1.2, rel_tol=1e-6)
    game.credits = 1e9
    game.managers.upgrade(inst.uid)
    upgraded = game.factory_stats("earth").rate["parts"]
    assert upgraded > after


def test_manager_ability_and_cooldown(game):
    game.credits = 1000
    inst = game.managers.hire("alex")
    assert not game.managers.activate(inst.uid)   # not assigned
    game.managers.assign(inst.uid, "earth", "parts")
    base = game.factory_stats("earth").rate["parts"]
    assert game.managers.activate(inst.uid)
    assert math.isclose(game.factory_stats("earth").rate["parts"] / base, 2.0, rel_tol=1e-6)
    assert not game.managers.activate(inst.uid)   # cooldown
    game.managers.tick(31)
    assert math.isclose(game.factory_stats("earth").rate["parts"], base, rel_tol=1e-6)
    game.managers.tick(300)
    assert game.managers.activate(inst.uid)


def test_replacing_manager(game):
    game.credits = 1e6
    a = game.managers.hire("alex")
    b = game.managers.hire("kai")
    game.managers.assign(a.uid, "earth", "parts")
    game.managers.assign(b.uid, "earth", "parts")
    assert game.factory.floors["parts"].manager_uid == b.uid
    assert a.planet is None


def test_unique_and_gem_managers(rich_game):
    g = rich_game
    cost, currency = g.managers.hire_cost("nova")
    assert currency == "gems"
    gems = g.gems
    assert g.managers.hire("nova") is not None
    assert g.gems == gems - cost
    assert g.managers.hire("nova") is None       # unique


def test_research(rich_game):
    g = rich_game
    assert g.research.state("engine_mfg") == "locked"
    assert not g.research.research("engine_mfg")
    base = g.factory_stats("earth").rate["parts"]
    assert g.research.research("precision_lathes")
    assert not g.research.research("precision_lathes")   # only once
    g.refresh_stats()
    assert math.isclose(g.factory_stats("earth").rate["parts"] / base, 1.25, rel_tol=1e-6)
    assert g.research.state("engine_mfg") == "available"


def test_research_requires_rp(game):
    game.rp = 1
    assert not game.research.research("precision_lathes")
    assert game.rp == 1


def test_rockets_unlock_and_select(rich_game):
    g = rich_game
    assert not g.select_rocket("explorer")            # locked
    assert g.unlock_rocket("explorer")
    assert not g.select_rocket("explorer")            # needs engine floor
    g.unlock_floor("engines")
    assert g.select_rocket("explorer")
    assert g.factory.rocket_id == "explorer"
    assert g.rocket_requirements("lunar_explorer")    # needs the Moon
    assert not g.unlock_rocket("lunar_explorer")


def test_rocket_value_increases_revenue(rich_game):
    g = rich_game
    mini = g.factory_stats("earth").value_per_rocket
    g.unlock_rocket("explorer")
    g.unlock_floor("engines")
    g.select_rocket("explorer")
    assert g.factory_stats("earth").value_per_rocket > mini


def test_planets_unlock_switch_and_keep_progress(rich_game):
    g = rich_game
    g.factory.floors["parts"].level = 42
    assert not g.unlock_planet("mars")                # must go in order
    assert g.unlock_planet("moon")
    assert g.switch_planet("moon")
    assert g.factory.planet_id == "moon"
    assert g.factory.floors["parts"].level == 1
    g.switch_planet("earth")
    assert g.factory.floors["parts"].level == 42
    moon_stats = g.factory_stats("moon")
    earth_stats = g.factory_stats("earth")
    assert moon_stats.interval < earth_stats.interval   # Moon: low gravity


def test_all_factories_run_in_parallel(rich_game):
    g = rich_game
    g.unlock_planet("moon")
    automate_earth(g)
    for def_id, fid in (("alex", "parts"), ("sam", "transport"), ("riley", "assembly"), ("jordan", "launchpad")):
        g.credits += 1e9
        inst = g.managers.hire(def_id)
        g.managers.assign(inst.uid, "moon", fid)
    for _ in range(600):
        g.step(0.1)
    assert g.factories["moon"].rockets_built > 0
    assert g.factories["earth"].rockets_built > 0


def test_prestige(rich_game):
    g = rich_game
    assert not g.prestige.can_prestige()[0]
    g.earn(1e12)
    stars = g.prestige.estimated_stars()
    assert stars >= 1
    g.research.research("precision_lathes")
    g.unlock_planet("moon")
    gems = g.gems
    inst = g.managers.hire("alex")
    g.managers.assign(inst.uid, "earth", "parts")
    assert g.prestige.prestige() == stars
    assert g.prestige.stars == stars
    assert list(g.factories) == ["earth"]
    assert g.factory.floors["parts"].level == 1
    assert g.gems == gems                                 # kept
    assert "precision_lathes" in g.research.done          # kept
    assert g.managers.get(inst.uid) is not None           # kept but unassigned
    assert g.managers.get(inst.uid).planet is None
    assert g.run_earned == 0
    # unspent stars boost production
    assert g.factory_stats("earth").rate["parts"] > 1.0


def test_legacy_upgrades(rich_game):
    g = rich_game
    g.prestige.stars = 100
    cost = g.prestige.upgrade_cost("legacy_production")
    assert g.prestige.buy_upgrade("legacy_production")
    assert g.prestige.stars == 100 - cost
    g.prestige.stars = 0
    assert not g.prestige.buy_upgrade("legacy_production")


def test_main_mission_claim_once(game):
    m = game.missions
    assert not m.claim_main()
    game.stats["rockets_launched"] = 1
    gems = game.gems
    assert m.claim_main()
    assert game.gems == gems + 5
    assert m.main_index == 1
    assert not m.claim_main()  # next mission not complete


def test_achievements_claim_once(game):
    m = game.missions
    game.stats["rockets_launched"] = 150
    gems = game.gems
    assert m.claim_achievement("launch")
    assert m.claim_achievement("launch")
    assert not m.claim_achievement("launch")
    assert game.gems == gems + 5 + 10


def test_daily_missions_and_login(game):
    m = game.missions
    now = 1_700_000_000.0
    m.refresh_daily(now)
    assert len(m.daily) == 3
    entry = m.daily[0]
    ddef = m.daily_def(entry)
    game.stats[ddef["stat"]] += entry["target"]
    assert m.claim_daily(0)
    assert not m.claim_daily(0)
    assert m.can_claim_login(now)
    assert m.claim_login(now) is not None
    assert not m.can_claim_login(now)          # once per day
    assert not m.can_claim_login(now - 86400)  # clock moved back: still no
    assert m.can_claim_login(now + 86400)


def test_free_gift(game):
    now = 1_700_000_000.0
    m = game.missions
    assert m.claim_gift(now)
    assert not m.claim_gift(now + 10)
    assert m.claim_gift(now + 4 * 3600 + 1)


def test_shop_cosmetics_and_boosts(rich_game):
    g = rich_game
    gems = g.gems
    assert g.shop.buy_cosmetic("paint_ocean")
    assert g.shop.equipped["paint"] == "paint_ocean"
    assert g.gems == gems - 15
    assert g.shop.buy_cosmetic("paint_ocean")  # re-equip, no charge
    assert g.gems == gems - 15
    assert not g.shop.buy_cosmetic("theme_legacy")
    base = g.factory_stats("earth").value_per_rocket
    assert g.shop.buy_boost("turbo2")
    g.refresh_stats()
    assert math.isclose(g.stats_cache["earth"].value_per_rocket / base, 2.0)
    g.shop.tick(1801)
    assert not g.shop.boosts


def test_time_warp_requires_automation(rich_game):
    g = rich_game
    assert not g.shop.buy_boost("warp1")
    automate_earth(g)
    credits = g.credits
    assert g.shop.buy_boost("warp1")
    assert g.credits > credits


def test_workforce(rich_game):
    g = rich_game
    before = g.factory_stats("earth").rate["parts"]
    assert g.buy_workforce("hiring")
    assert g.factory_stats("earth").rate["parts"] > before


def test_rapid_clicking_never_goes_negative(game):
    game.credits = 50
    for _ in range(200):
        game.upgrade_floor("parts")
        game.upgrade_floor("transport", "max")
        game.managers.hire("alex")
    assert game.credits >= 0


def test_very_large_money(rich_game):
    g = rich_game
    g.credits = 1e299
    g.earn(1e299)
    assert g.credits <= 1e300 and not math.isinf(g.credits)
    assert g.upgrade_floor("parts", "max") > 0


@pytest.mark.parametrize("seconds", [60.0])
def test_game_update_handles_large_real_dt(game, seconds):
    game.update(seconds)  # clamps internally, must not hang or crash
    assert game.stats["seconds_played"] <= 2.1


def test_features_unlock_gradually(game):
    assert not game.feature_unlocked("research")[0]
    assert not game.feature_unlocked("planets")[0]
    game.stats["managers_hired"] = 1
    assert game.feature_unlocked("research")[0]


def test_new_game_defaults(config):
    g = Game(config)
    assert g.credits == config.economy["starting_credits"]
    assert g.current_planet == "earth"
