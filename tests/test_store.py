"""Real-money store (test provider), gem spends and exclusive cosmetics."""
import math

from game.core.game import Game
from game.shop.store import TestProvider
from tests.conftest import automate_earth


def test_gem_pack_grants_gems(game):
    gems = game.gems
    assert game.store.purchase("gems_small")
    assert game.gems == gems + 80
    assert game.store.purchase("gems_small")        # consumable: can buy again
    assert game.gems == gems + 160


def test_one_time_products(game):
    assert game.store.purchase("starter_pack")
    assert "starter_pack" in game.store.owned
    assert any(m.def_id == "kai" for m in game.managers.instances)
    assert not game.store.purchase("starter_pack")  # only once


def test_failed_payment_grants_nothing(game):
    game.store.provider = TestProvider(fail=True)
    gems = game.gems
    assert not game.store.purchase("gems_large")
    assert game.gems == gems
    assert game.store.pending is None


def test_duplicate_transaction_is_ignored(game):
    gems = game.gems
    assert game.store.complete("gems_small", True, "txn-1")
    assert not game.store.complete("gems_small", True, "txn-1")
    assert game.gems == gems + 80


def test_golden_investor_perk(game):
    base_value = game.factory_stats("earth").value_per_rocket
    cap = game.offline_cap_seconds()
    assert game.store.purchase("golden_investor")
    game.refresh_stats()
    assert math.isclose(game.factory_stats("earth").value_per_rocket / base_value, 1.5)
    assert game.offline_cap_seconds() == cap + 4 * 3600
    game.earn(1e13)
    game.prestige.prestige()                         # perks survive Space Legacy
    assert "golden_investor" in game.store.perks


def test_exclusive_cosmetics(game):
    game.gems = 10_000
    assert not game.shop.buy_cosmetic("paint_galaxy")
    assert game.store.purchase("galaxy_bundle")
    assert game.shop.is_owned("paint_galaxy")
    assert game.shop.equipped["paint"] == "paint_galaxy"


def test_store_state_saved(game):
    game.store.purchase("golden_investor")
    game.store.purchase("starter_pack")
    loaded = Game.from_dict(game.to_dict(), game.config)
    assert loaded.store.owned == {"golden_investor", "starter_pack"}
    assert "golden_investor" in loaded.store.perks
    assert not loaded.store.purchase("starter_pack")


def test_collect_offline_doubled(game):
    automate_earth(game)
    report = game.apply_offline(game.last_seen + 3600)
    credits, gems = game.credits, game.gems = game.credits, 100
    game.collect_offline_doubled()
    assert math.isclose(game.credits - credits, report.money * 2)
    assert game.gems == 100 - game.offline_double_cost()


def test_collect_doubled_needs_gems(game):
    automate_earth(game)
    game.apply_offline(game.last_seen + 3600)
    game.gems = 0
    assert game.collect_offline_doubled() is None
    assert game.pending_offline is not None          # still collectable normally


def test_ability_reset_boost(game):
    automate_earth(game)
    inst = game.managers.instances[0]
    game.gems = 100
    assert not game.shop.buy_boost("ability_reset")   # nothing on cooldown: no charge
    assert game.gems == 100
    game.managers.activate(inst.uid)
    assert game.shop.buy_boost("ability_reset")
    assert inst.cooldown == 0 and game.gems == 85
