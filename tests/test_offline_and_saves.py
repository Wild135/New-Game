"""Offline earnings, save/load, corruption recovery and migrations."""
import json
import math

import pytest

from game.core.game import Game
from game.saves.save_manager import SaveError, SaveManager, migrate
from tests.conftest import automate_earth


def test_offline_requires_automation(game):
    assert game.apply_offline(game.last_seen + 3600) is None
    assert game.pending_offline is None


def test_offline_earnings_and_cap(game):
    automate_earth(game)
    game.refresh_stats()
    start = game.last_seen
    report = game.apply_offline(start + 3600)
    assert report is not None and report.money > 0
    one_hour = report.money
    game.collect_offline()
    report = game.apply_offline(game.last_seen + 24 * 3600)
    assert report.capped
    assert math.isclose(report.seconds_counted, game.offline_cap_seconds())
    assert math.isclose(report.money, one_hour * 8, rel_tol=0.02)


def test_offline_matches_steady_state(game):
    automate_earth(game)
    game.refresh_stats()
    stats = game.factory_stats("earth", include_temporary=False)
    report = game.apply_offline(game.last_seen + 7200)
    expected = stats.auto_income_per_second * 7200 * game.offline_efficiency()
    assert math.isclose(report.money, expected, rel_tol=1e-6)


def test_offline_collect_only_once(game):
    automate_earth(game)
    game.apply_offline(game.last_seen + 3600)
    credits = game.credits
    first = game.collect_offline()
    assert first is not None
    assert game.credits > credits
    after = game.credits
    assert game.collect_offline() is None
    assert game.credits == after


def test_clock_moved_backwards(game):
    automate_earth(game)
    last = game.last_seen
    assert game.apply_offline(last - 5000) is None
    assert game.last_seen == last          # never moves backwards
    assert game.pending_offline is None


def test_research_raises_offline_cap(rich_game):
    g = rich_game
    cap = g.offline_cap_seconds()
    g.research.research("offline_prod")
    g.research.research("extended_shifts")
    g.refresh_stats()
    assert g.offline_cap_seconds() == cap + 4 * 3600


def test_pending_offline_survives_save(game, tmp_path):
    automate_earth(game)
    game.apply_offline(game.last_seen + 3600)
    data = game.to_dict()
    loaded = Game.from_dict(json.loads(json.dumps(data)), game.config)
    assert loaded.pending_offline is not None
    assert math.isclose(loaded.pending_offline.money, game.pending_offline.money)


def test_save_roundtrip(rich_game, tmp_path):
    g = rich_game
    automate_earth(g)
    g.upgrade_floor("parts", "10")
    g.research.research("precision_lathes")
    g.unlock_planet("moon")
    g.shop.buy_cosmetic("paint_gold")
    g.settings["music_volume"] = 0.3
    g.tutorial["done"] = True
    sm = SaveManager(tmp_path)
    sm.save(g.to_dict())
    loaded = Game.from_dict(sm.load(), g.config)
    assert loaded.credits == pytest.approx(g.credits)
    assert loaded.factory.floors["parts"].level == g.factory.floors["parts"].level
    assert "moon" in loaded.factories
    assert "precision_lathes" in loaded.research.done
    assert loaded.shop.equipped["paint"] == "paint_gold"
    assert loaded.settings["music_volume"] == 0.3
    assert loaded.tutorial["done"]
    assert len(loaded.managers.instances) == 4
    assert loaded.factory.floors["parts"].manager_uid is not None


def test_missing_save_returns_none(tmp_path):
    assert SaveManager(tmp_path).load() is None


def test_corrupted_save_falls_back_to_backup(game, tmp_path):
    sm = SaveManager(tmp_path)
    game.credits = 111
    sm.save(game.to_dict())
    game.credits = 222
    sm.save(game.to_dict())          # first save becomes backup 1
    sm.path.write_text("{ this is not json", encoding="utf-8")
    data = sm.load()
    assert data is not None and data["credits"] == 111
    assert "damaged" in sm.last_error


def test_tampered_checksum_is_rejected(game, tmp_path):
    sm = SaveManager(tmp_path)
    sm.save(game.to_dict())
    payload = json.loads(sm.path.read_text())
    payload["data"]["credits"] = 1e30
    sm.path.write_text(json.dumps(payload))
    assert sm.load() is None


def test_broken_save_does_not_replace_good_backup(game, tmp_path):
    sm = SaveManager(tmp_path)
    game.credits = 5
    sm.save(game.to_dict())
    sm.save(game.to_dict())
    sm.path.write_text("garbage")
    game.credits = 9
    sm.save(game.to_dict())          # broken main is NOT rotated into backups
    assert json.loads(sm.backup_path(1).read_text())["data"]["credits"] == 5


def test_atomic_write_leaves_no_temp_files(game, tmp_path):
    sm = SaveManager(tmp_path)
    for _ in range(5):
        sm.save(game.to_dict())
    assert not list(tmp_path.glob(".save-*"))
    assert sm.backup_path(3).exists()


def test_migration_from_version_0():
    data = migrate({"version": 0, "money": 50})
    assert data["version"] == 1 and data["credits"] == 50
    with pytest.raises(SaveError):
        migrate({"version": 999})


def test_load_tolerates_bad_values(config):
    data = Game(config).to_dict()
    data["credits"] = "lots"
    data["gems"] = -5
    data["factories"]["earth"]["rocket_id"] = "does_not_exist"
    data["managers"]["instances"].append({"uid": "m99", "def_id": "ghost"})
    data["current_planet"] = "pluto"
    g = Game.from_dict(data, config)
    assert g.credits == 0 and g.gems == 0
    assert g.factory.rocket_id == "mini"
    assert g.current_planet == "earth"
    assert not g.managers.instances
