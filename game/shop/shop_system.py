"""Simulated gem shop: cosmetics and optional convenience boosts.

There are NO real-money purchases in this version.  Gems are only earned by
playing (missions, achievements, daily rewards and gifts).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.economy.modifiers import Modifiers

if TYPE_CHECKING:  # pragma: no cover
    from game.core.game import Game

SLOTS = ["paint", "decal", "exhaust", "effect", "theme", "hat"]


class ShopSystem:
    def __init__(self, game: "Game"):
        self.game = game
        self.cfg = game.config
        self.owned: set[str] = {c["id"] for c in self.cfg.cosmetic_list
                                if c["cost"] == 0 and not c.get("requires_legacy")}
        self.equipped: dict[str, str] = {}
        for cos in self.cfg.cosmetic_list:
            if cos["id"] in self.owned and cos["slot"] not in self.equipped:
                self.equipped[cos["slot"]] = cos["id"]
        self.boosts: list[dict] = []  # [{id, stat, mult, remaining}]

    # cosmetics --------------------------------------------------------
    def is_owned(self, cos_id: str) -> bool:
        cos = self.cfg.cosmetics[cos_id]
        if cos.get("requires_legacy"):
            return self.game.prestige.levels.get(cos["requires_legacy"], 0) > 0
        return cos_id in self.owned

    def buy_cosmetic(self, cos_id: str) -> bool:
        cos = self.cfg.cosmetics[cos_id]
        if self.is_owned(cos_id):
            return self.equip(cos_id)
        if cos.get("requires_legacy"):
            self.game.toast("Unlock this with a Legacy upgrade")
            return False
        if not self.game.spend_gems(cos["cost"]):
            self.game.toast("Not enough gems")
            return False
        self.owned.add(cos_id)
        self.equip(cos_id)
        self.game.emit("purchase", id=cos_id)
        return True

    def equip(self, cos_id: str) -> bool:
        if not self.is_owned(cos_id):
            return False
        self.equipped[self.cfg.cosmetics[cos_id]["slot"]] = cos_id
        return True

    def equipped_item(self, slot: str) -> dict:
        cos_id = self.equipped.get(slot)
        if cos_id and cos_id in self.cfg.cosmetics:
            return self.cfg.cosmetics[cos_id]
        return next(c for c in self.cfg.cosmetic_list if c["slot"] == slot)

    # boosts -------------------------------------------------------------
    def buy_boost(self, boost_id: str) -> bool:
        boost = self.cfg.boosts[boost_id]
        if self.game.gems < boost["cost"]:
            self.game.toast("Not enough gems")
            return False
        if "warp_hours" in boost:
            income = self.game.total_auto_income()
            if income <= 0:
                self.game.toast("Automate a full production line first")
                return False
            self.game.spend_gems(boost["cost"])
            amount = income * boost["warp_hours"] * 3600
            self.game.earn(amount)
            self.game.emit("time_warp", amount=amount)
            return True
        self.game.spend_gems(boost["cost"])
        if "rp" in boost:
            self.game.rp += boost["rp"]
            self.game.emit("purchase", id=boost_id)
            return True
        effect = boost["effect"]
        for active in self.boosts:
            if active["id"] == boost_id:
                active["remaining"] += effect["duration"]   # stacking extends time
                break
        else:
            self.boosts.append({"id": boost_id, "stat": effect["stat"], "mult": effect["mult"],
                                "remaining": float(effect["duration"])})
        self.game.emit("purchase", id=boost_id)
        return True

    def tick(self, dt: float) -> None:
        for boost in self.boosts:
            boost["remaining"] -= dt
        self.boosts = [b for b in self.boosts if b["remaining"] > 0]

    def modifiers(self) -> Modifiers:
        mods = Modifiers()
        for boost in self.boosts:
            mods.mul(boost["stat"], boost["mult"])
        return mods

    def to_dict(self) -> dict:
        return {"owned": sorted(self.owned), "equipped": dict(self.equipped), "boosts": self.boosts}

    def load(self, data: dict) -> None:
        self.owned |= {c for c in data.get("owned", []) if c in self.cfg.cosmetics}
        for slot, cos_id in data.get("equipped", {}).items():
            if cos_id in self.cfg.cosmetics:
                self.equipped[slot] = cos_id
        self.boosts = [b for b in data.get("boosts", [])
                       if isinstance(b, dict) and b.get("id") in self.cfg.boosts
                       and float(b.get("remaining", 0)) > 0]
