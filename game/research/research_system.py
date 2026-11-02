"""Technology research tree paid with Research Points (RP)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.economy.modifiers import Modifiers

if TYPE_CHECKING:  # pragma: no cover
    from game.core.game import Game


class ResearchSystem:
    def __init__(self, game: "Game"):
        self.game = game
        self.cfg = game.config
        self.done: set[str] = set()

    def state(self, research_id: str) -> str:
        """'done', 'available' (requirements met) or 'locked'."""
        if research_id in self.done:
            return "done"
        node = self.cfg.research[research_id]
        if all(req in self.done for req in node.get("requires", [])):
            return "available"
        return "locked"

    def can_research(self, research_id: str) -> tuple[bool, str]:
        state = self.state(research_id)
        if state == "done":
            return False, "Already researched"
        if state == "locked":
            names = [self.cfg.research[r]["name"] for r in self.cfg.research[research_id]["requires"]
                     if r not in self.done]
            return False, "Requires " + ", ".join(names)
        if self.game.rp < self.cfg.research[research_id]["cost"]:
            return False, "Not enough Research Points"
        return True, ""

    def research(self, research_id: str) -> bool:
        ok, reason = self.can_research(research_id)
        if not ok:
            self.game.toast(reason)
            return False
        self.game.rp -= self.cfg.research[research_id]["cost"]
        self.done.add(research_id)
        self.game.stats["research_done"] += 1
        self.game.emit("research", id=research_id)
        return True

    def modifiers(self) -> Modifiers:
        mods = Modifiers()
        for rid in self.done:
            for effect in self.cfg.research[rid].get("effects", []):
                mods.apply_effect(effect)
        return mods

    def to_dict(self) -> dict:
        return {"done": sorted(self.done)}

    def load(self, data: dict) -> None:
        self.done = {r for r in data.get("done", []) if r in self.cfg.research}
