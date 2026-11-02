"""Collects bonuses from many sources into one simple object.

A ``Modifiers`` object holds two kinds of values:

* multipliers (``mult``) - start at 1.0 and are multiplied together
* additions (``add``) - start at 0.0 and are summed

Stat names used throughout the game:

  production, transport, assembly, launch_capacity, launch_interval, value,
  storage, rp_gain, cost, planet_cost, manager_bonus (add),
  offline_efficiency (add), offline_cap_hours (add), start_credits (add),
  ``all`` (production + transport + assembly + launch capacity),
  ``logistics`` (transport + assembly), ``producer:<component>``.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Modifiers:
    mults: dict[str, float] = field(default_factory=dict)
    adds: dict[str, float] = field(default_factory=dict)

    def mul(self, stat: str, value: float) -> None:
        self.mults[stat] = self.mults.get(stat, 1.0) * value

    def add(self, stat: str, value: float) -> None:
        self.adds[stat] = self.adds.get(stat, 0.0) + value

    def m(self, stat: str) -> float:
        return self.mults.get(stat, 1.0)

    def a(self, stat: str) -> float:
        return self.adds.get(stat, 0.0)

    def apply_effect(self, effect: dict, scale: float = 1.0) -> None:
        """Apply a config effect like {"stat": "value", "mult": 1.2}."""
        stat = effect["stat"]
        if "mult" in effect:
            self.mul(stat, effect["mult"] ** scale if scale != 1 else effect["mult"])
        if "add" in effect:
            self.add(stat, effect["add"] * scale)

    def merged(self, other: "Modifiers") -> "Modifiers":
        result = Modifiers(dict(self.mults), dict(self.adds))
        for stat, value in other.mults.items():
            result.mul(stat, value)
        for stat, value in other.adds.items():
            result.add(stat, value)
        return result

    # Helpers that combine the umbrella stats ---------------------------
    def kind_mult(self, kind: str, component_key: str | None = None) -> float:
        if kind == "producer":
            value = self.m("production") * self.m("all")
            if component_key:
                value *= self.m(f"producer:{component_key}")
            return value
        if kind == "transport":
            return self.m("transport") * self.m("all") * self.m("logistics")
        if kind == "assembly":
            return self.m("assembly") * self.m("all") * self.m("logistics")
        if kind == "launch":
            return self.m("launch_capacity") * self.m("all")
        return 1.0
