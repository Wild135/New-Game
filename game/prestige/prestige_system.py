"""Space Legacy: reset a run to earn Legacy Stars and permanent bonuses."""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.economy.formulas import legacy_stars_for, upgrade_cost
from game.economy.modifiers import Modifiers

if TYPE_CHECKING:  # pragma: no cover
    from game.core.game import Game

RESETS = ["Credits", "Factory floors and workforce", "Unlocked planets (back to Earth)",
          "Unlocked rockets", "Manager assignments (managers are kept)", "Active boosts"]
KEEPS = ["Gems", "Research Points and completed research", "Hired managers and their levels",
         "Achievements and statistics", "Cosmetics", "Legacy Stars and Legacy upgrades",
         "Mission progress"]


class PrestigeSystem:
    def __init__(self, game: "Game"):
        self.game = game
        self.cfg = game.config
        self.pcfg = game.config.prestige
        self.stars = 0               # unspent stars
        self.total_stars = 0         # all stars ever earned
        self.levels: dict[str, int] = {uid: 0 for uid in game.config.legacy_upgrades}

    def estimated_stars(self) -> int:
        p = self.pcfg
        return legacy_stars_for(self.game.run_earned, p["divisor"], p["scale"], p["exponent"])

    def can_prestige(self) -> tuple[bool, str]:
        stars = self.estimated_stars()
        if stars < self.pcfg["min_stars"]:
            need = self.pcfg["divisor"] * (self.pcfg["min_stars"] / self.pcfg["scale"]) ** (1 / self.pcfg["exponent"])
            from game.core.numformat import format_money
            return False, f"Earn {format_money(need)} this run to earn your first star"
        return True, ""

    def star_multiplier(self, stars: int | None = None) -> float:
        stars = self.stars if stars is None else stars
        return 1 + self.pcfg["star_bonus"] * stars

    def upgrade_cost(self, upgrade_id: str) -> float:
        u = self.cfg.legacy_upgrades[upgrade_id]
        return float(round(upgrade_cost(u["base_cost"], u["cost_growth"], self.levels[upgrade_id] + 1)))

    def buy_upgrade(self, upgrade_id: str) -> bool:
        u = self.cfg.legacy_upgrades[upgrade_id]
        if self.levels[upgrade_id] >= u["max_level"]:
            self.game.toast("Already at max level")
            return False
        cost = self.upgrade_cost(upgrade_id)
        if self.stars < cost:
            self.game.toast("Not enough Legacy Stars")
            return False
        self.stars -= int(cost)
        self.levels[upgrade_id] += 1
        self.game.emit("legacy_upgrade", id=upgrade_id)
        return True

    def modifiers(self) -> Modifiers:
        mods = Modifiers()
        mods.mul("all", self.star_multiplier())
        for uid, level in self.levels.items():
            if level <= 0:
                continue
            for eff in self.cfg.legacy_upgrades[uid]["effects"]:
                if "mult_per_level" in eff:
                    mods.mul(eff["stat"], max(0.2, 1 + eff["mult_per_level"] * level))
                if "add_per_level" in eff:
                    mods.add(eff["stat"], eff["add_per_level"] * level)
        return mods

    def start_credits(self) -> float:
        level = self.levels.get("head_start", 0)
        base = self.cfg.economy["starting_credits"]
        return base if level <= 0 else max(base, 1000 * 10 ** (level - 1))

    def prestige(self) -> int:
        ok, reason = self.can_prestige()
        if not ok:
            self.game.toast(reason)
            return 0
        earned = self.estimated_stars()
        self.stars += earned
        self.total_stars += earned
        self.game.reset_run()
        self.game.stats["prestiges"] += 1
        self.game.emit("prestige", stars=earned)
        return earned

    def to_dict(self) -> dict:
        return {"stars": self.stars, "total_stars": self.total_stars, "levels": dict(self.levels)}

    def load(self, data: dict) -> None:
        self.stars = max(0, int(data.get("stars", 0)))
        self.total_stars = max(self.stars, int(data.get("total_stars", 0)))
        for uid, level in data.get("levels", {}).items():
            if uid in self.levels:
                self.levels[uid] = max(0, min(int(level), self.cfg.legacy_upgrades[uid]["max_level"]))
