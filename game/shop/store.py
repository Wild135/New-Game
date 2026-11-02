"""Real-money store (in-app purchases).

How it works:

* Products live in ``config/store.json``.
* The UI calls ``Store.purchase(product_id)``.  The store asks a
  ``PurchaseProvider`` to take the payment.  When the provider reports success
  (with a unique transaction id) the store grants the items **once**.
* ``TestProvider`` simulates a successful payment WITHOUT charging anything.
  It is used while ``test_mode`` is true (the default for this Windows build).

Taking real money needs a payment platform, and the platform decides which one
is allowed:
  - iOS:     Apple StoreKit (required by Apple for digital goods)
  - Android: Google Play Billing (required by Google for digital goods)
  - Windows: Steamworks microtransactions, or a web payment provider
To go live you write a provider class with the same ``begin`` method that talks
to that platform (and ideally verifies receipts on a server), then set
``test_mode`` to false.  See docs/MONETIZATION.md.
"""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Callable

from game.economy.modifiers import Modifiers

if TYPE_CHECKING:  # pragma: no cover
    from game.core.game import Game

Callback = Callable[[bool, str, str], None]   # (success, transaction_id, error message)


class PurchaseProvider:
    """Interface every payment provider implements."""
    name = "base"

    def begin(self, product: dict, callback: Callback) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class TestProvider(PurchaseProvider):
    """Pretends the payment succeeded. Charges nothing. For development and the demo build."""
    name = "test"
    __test__ = False   # tell pytest this is not a test class

    def __init__(self, fail: bool = False):
        self.fail = fail

    def begin(self, product: dict, callback: Callback) -> None:
        if self.fail:
            callback(False, "", "Payment declined (test)")
        else:
            callback(True, f"test-{uuid.uuid4().hex[:12]}", "")


class Store:
    def __init__(self, game: "Game", provider: PurchaseProvider | None = None):
        self.game = game
        cfg = game.config.raw.get("store", {"enabled": False, "products": [], "perks": {}})
        self.enabled: bool = bool(cfg.get("enabled", False))
        self.test_mode: bool = bool(cfg.get("test_mode", True))
        self.products: list[dict] = cfg.get("products", [])
        self.by_id = {p["id"]: p for p in self.products}
        self.perk_defs: dict[str, list[dict]] = cfg.get("perks", {})
        self.provider: PurchaseProvider = provider or TestProvider()
        self.owned: set[str] = set()           # one-time products already bought
        self.perks: set[str] = set()
        self.transactions: set[str] = set()    # processed transaction ids (no double grants)
        self.history: list[dict] = []
        self.pending: str | None = None

    # ------------------------------------------------------------------
    def available(self, product_id: str) -> bool:
        product = self.by_id.get(product_id)
        if product is None or not self.enabled:
            return False
        return not (product.get("one_time") and product_id in self.owned)

    def purchase(self, product_id: str) -> bool:
        """Start a purchase. Returns True if it completed successfully right away."""
        if not self.available(product_id):
            self.game.toast("This item is not available")
            return False
        if self.pending:
            return False
        self.pending = product_id
        result = {"ok": False}

        def done(success: bool, transaction_id: str, error: str) -> None:
            result["ok"] = self.complete(product_id, success, transaction_id, error)
        self.provider.begin(self.by_id[product_id], done)
        return result["ok"]

    def complete(self, product_id: str, success: bool, transaction_id: str, error: str = "") -> bool:
        self.pending = None
        if not success:
            self.game.toast(error or "Purchase cancelled")
            return False
        if not transaction_id or transaction_id in self.transactions:
            return False                      # duplicate callback: never grant twice
        if not self.available(product_id):
            return False
        self.transactions.add(transaction_id)
        product = self.by_id[product_id]
        if product.get("one_time"):
            self.owned.add(product_id)
        self.history.append({"product": product_id, "transaction": transaction_id, "time": time.time(),
                             "test": self.test_mode})
        self.grant(product["grant"], product["name"])
        self.game.emit("store_purchase", product=product_id)
        return True

    def grant(self, grant: dict, source: str) -> None:
        game = self.game
        if grant.get("gems"):
            game.grant_reward({"gems": grant["gems"]}, source=source)
        if grant.get("manager"):
            inst = game.managers.grant(grant["manager"])
            if inst:
                game.toast(f"{game.managers.display_name(inst)} joined your team!")
        if grant.get("warp_hours"):
            income = max(game.total_auto_income(), game.total_income(), 5.0)
            game.earn(income * grant["warp_hours"] * 3600)
        for cos_id in grant.get("cosmetics", []):
            if cos_id in game.config.cosmetics:
                game.shop.owned.add(cos_id)
                game.shop.equip(cos_id)
        if grant.get("perk"):
            self.perks.add(grant["perk"])
            game.refresh_stats()

    def modifiers(self) -> Modifiers:
        mods = Modifiers()
        for perk in self.perks:
            for effect in self.perk_defs.get(perk, []):
                mods.apply_effect(effect)
        return mods

    def price_text(self, product: dict) -> str:
        return f"${product['price']:.2f}"

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"owned": sorted(self.owned), "perks": sorted(self.perks),
                "transactions": sorted(self.transactions), "history": self.history[-200:]}

    def load(self, data: dict) -> None:
        self.owned = {p for p in data.get("owned", []) if p in self.by_id}
        self.perks = {p for p in data.get("perks", []) if p in self.perk_defs}
        self.transactions = set(data.get("transactions", []))
        self.history = list(data.get("history", []))
