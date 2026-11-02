"""Production chain simulation tests."""
import math

from game.economy.modifiers import Modifiers
from game.factories.factory import Factory
from tests.conftest import automate_earth


def stats_for(factory):
    return factory.compute_stats(Modifiers())


def test_initial_floors(config):
    f = Factory(config, "earth")
    assert f.floors["parts"].level == 1
    assert f.floors["engines"].level == 0
    assert "special" not in f.floors        # Earth has no special resource
    assert "special" in Factory(config, "moon").floors


def test_manual_floors_do_nothing_without_taps(config):
    f = Factory(config, "earth")
    s = stats_for(f)
    for _ in range(100):
        f.step(0.1, s)
    assert f.floors["parts"].storage == 0
    assert f.ready == 0


def test_tapping_produces_parts(config):
    f = Factory(config, "earth")
    s = stats_for(f)
    assert f.tap("parts", 8, 40)
    for _ in range(100):
        f.step(0.1, s)
    assert math.isclose(f.floors["parts"].storage, 8.0, rel_tol=1e-6)  # 1 part/s for 8 seconds


def test_full_chain_makes_and_launches_rockets(game):
    automate_earth(game)
    for _ in range(600):                       # one minute
        game.step(0.1)
    assert game.stats["rockets_launched"] > 0
    assert game.credits > 0


def test_bottleneck_is_slowest_stage(config):
    f = Factory(config, "earth")
    f.floors["parts"].level = 50
    f.floors["assembly"].level = 50
    f.floors["launchpad"].level = 50
    f.floors["transport"].level = 5
    s = stats_for(f)
    assert s.bottleneck == "transport"
    assert math.isclose(s.rocket_rate, s.stage_rockets["transport"])
    f.floors["transport"].level = 200
    s = stats_for(f)
    assert s.bottleneck != "transport"


def test_simulated_throughput_matches_bottleneck(config):
    """Over a long run, launched rockets/s converges to the steady-state rate."""
    f = Factory(config, "earth")
    for fid in ("parts", "transport", "assembly", "launchpad"):
        f.floors[fid].manager_uid = f"m_{fid}"
    f.floors["parts"].level = 30
    f.floors["transport"].level = 12
    f.floors["assembly"].level = 30
    f.floors["launchpad"].level = 30
    s = stats_for(f)
    launched = 0.0
    for _ in range(int(600 / 0.1)):
        for launch in f.step(0.1, s):
            launched += launch.count
    expected = s.rocket_rate * 600
    assert launched > 0
    assert abs(launched - expected) / expected < 0.08


def test_no_negative_inventory(config):
    f = Factory(config, "earth")
    for fid in f.floors:
        if f.floors[fid].level > 0:
            f.floors[fid].manager_uid = "x"
    f.floors["transport"].level = 300
    f.floors["assembly"].level = 300
    s = stats_for(f)
    for _ in range(2000):
        f.step(0.1, s)
        assert all(v >= -1e-9 for v in f.buffer.values())
        assert all(fl.storage >= -1e-9 for fl in f.floors.values())
        assert f.ready >= 0


def test_frame_rate_independence(config):
    """Different step sizes give (nearly) the same production."""
    results = []
    for dt in (0.05, 0.1, 0.5):
        f = Factory(config, "earth")
        for fid in ("parts", "transport", "assembly", "launchpad"):
            f.floors[fid].manager_uid = "x"
            f.floors[fid].level = 20
        s = stats_for(f)
        total = 0.0
        steps = int(300 / dt)
        for _ in range(steps):
            for launch in f.step(dt, s):
                total += launch.revenue
        results.append(total)
    assert max(results) / min(results) < 1.06


def test_storage_capacity_is_respected(config):
    f = Factory(config, "earth")
    f.floors["parts"].manager_uid = "x"
    s = stats_for(f)
    for _ in range(5000):
        f.step(0.1, s)
    assert f.floors["parts"].storage <= s.storage_cap["parts"] + 1e-6


def test_can_build_rules(config):
    f = Factory(config, "earth")
    assert f.can_build("mini")[0]
    ok, reason = f.can_build("explorer")
    assert not ok and "Engine" in reason
    f.floors["engines"].level = 1
    assert f.can_build("explorer")[0]
    assert not f.can_build("lunar_explorer")[0]   # Moon only


def test_special_resource_resolves_per_planet(config):
    moon = Factory(config, "moon")
    recipe = moon.resolved_recipe("lunar_explorer")
    assert "helium3" in recipe and "special" not in recipe


def test_manual_launch_requires_rocket(config):
    f = Factory(config, "earth")
    assert not f.request_launch(3)
    f.ready = 2
    assert f.request_launch(3)
    s = stats_for(f)
    launches = []
    for _ in range(40):
        launches += f.step(0.1, s)
    assert len(launches) == 1 and launches[0].count == 1


def test_factory_roundtrip(config):
    f = Factory(config, "earth")
    f.floors["parts"].level = 33
    f.floors["parts"].storage = 12.5
    f.ready = 3
    f.workforce["hiring"] = 2
    g = Factory.from_dict(config, f.to_dict())
    assert g.floors["parts"].level == 33
    assert g.floors["parts"].storage == 12.5
    assert g.ready == 3 and g.workforce["hiring"] == 2
