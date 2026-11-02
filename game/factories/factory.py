"""The production chain of one planet's rocket factory.

Raw Materials -> Producer floors -> Transport -> Assembly -> Launchpad -> Revenue

The simulation moves real quantities between stages every fixed tick, so a
slow stage really does slow everything after it (a bottleneck).  Nothing in
this file knows about graphics - it is pure game logic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from game.core.numformat import clamp_big
from game.economy.formulas import leveled_output, milestone_multiplier, upgrade_cost
from game.economy.modifiers import Modifiers

if TYPE_CHECKING:  # pragma: no cover
    from game.core.config import GameConfig

STAGE_LABELS = {"producer": "Production", "transport": "Transport", "assembly": "Assembly",
                "launch": "Launchpad"}


@dataclass
class FloorState:
    id: str
    level: int = 0                 # 0 means the floor is still locked
    storage: float = 0.0           # finished components waiting (producers only)
    manual_time: float = 0.0       # seconds of work left from player taps
    manager_uid: str | None = None
    flow: float = 0.0              # smoothed measured throughput (for display)

    def to_dict(self) -> dict:
        return {"id": self.id, "level": self.level, "storage": self.storage,
                "manual_time": self.manual_time, "manager_uid": self.manager_uid}

    @classmethod
    def from_dict(cls, data: dict) -> "FloorState":
        return cls(id=str(data["id"]), level=max(0, int(data.get("level", 0))),
                   storage=max(0.0, float(data.get("storage", 0.0))),
                   manual_time=max(0.0, float(data.get("manual_time", 0.0))),
                   manager_uid=data.get("manager_uid"))


@dataclass
class FactoryStats:
    """Rates calculated from levels and bonuses. Recomputed every tick."""
    rate: dict[str, float] = field(default_factory=dict)
    storage_cap: dict[str, float] = field(default_factory=dict)
    buffer_cap: dict[str, float] = field(default_factory=dict)
    automated: dict[str, bool] = field(default_factory=dict)
    recipe: dict[str, float] = field(default_factory=dict)
    recipe_total: float = 1.0
    producer_of: dict[str, str] = field(default_factory=dict)   # component -> floor id
    interval: float = 6.0
    capacity: float = 1.0
    value_per_rocket: float = 0.0
    rp_per_rocket: float = 0.0           # RP for a single-rocket launch
    queue_cap: float = 5.0
    # Rockets per second each stage could support, and the slowest one.
    stage_rockets: dict[str, float] = field(default_factory=dict)
    rocket_rate: float = 0.0
    bottleneck: str | None = None
    auto_rocket_rate: float = 0.0
    auto_bottleneck: str | None = None

    @property
    def income_per_second(self) -> float:
        return self.rocket_rate * self.value_per_rocket

    @property
    def auto_income_per_second(self) -> float:
        return self.auto_rocket_rate * self.value_per_rocket


@dataclass
class LaunchResult:
    planet_id: str
    rocket_id: str
    count: float
    revenue: float
    rp: float


class Factory:
    """One planet's factory: floor levels, inventories and the simulation."""

    def __init__(self, config: "GameConfig", planet_id: str):
        self.config = config
        self.planet_id = planet_id
        self.floors: dict[str, FloorState] = {}
        for fdef in config.floor_list:
            if not config.floor_available_on(fdef["id"], planet_id):
                continue
            starting_level = 1 if fdef.get("unlock_cost", 0) == 0 else 0
            self.floors[fdef["id"]] = FloorState(fdef["id"], level=starting_level)
        self.buffer: dict[str, float] = {}      # assembly input storage per component
        self.ready: float = 0.0                 # finished rockets waiting at the pad
        self.pad_timer: float = 0.0
        self.countdown: float = -1.0            # manual launch countdown (-1 = idle)
        self.rocket_id: str = config.rocket_list[0]["id"]
        self.workforce: dict[str, int] = {w["id"]: 0 for w in config.workforce_list}
        self.rockets_built: float = 0.0
        self.components_made: float = 0.0
        self.assembly_progress: float = 0.0     # 0..1 progress of the next rocket (visual)

    # ------------------------------------------------------------------
    # Helpers
    def floor_def(self, floor_id: str) -> dict:
        return self.config.floors[floor_id]

    def unlocked(self, floor_id: str) -> bool:
        floor = self.floors.get(floor_id)
        return bool(floor and floor.level > 0)

    def ordered_floor_ids(self) -> list[str]:
        return [f["id"] for f in self.config.floor_list if f["id"] in self.floors]

    def component_of(self, floor_id: str) -> str | None:
        fdef = self.floor_def(floor_id)
        if fdef["kind"] != "producer":
            return None
        return self.config.component_for(fdef["component"], self.planet_id)

    def resolved_recipe(self, rocket_id: str | None = None) -> dict[str, float]:
        rocket = self.config.rockets[rocket_id or self.rocket_id]
        recipe: dict[str, float] = {}
        for comp, amount in rocket["recipe"].items():
            real = self.config.component_for(comp, self.planet_id)
            if real is None:
                continue
            recipe[real] = recipe.get(real, 0.0) + float(amount)
        return recipe

    def can_build(self, rocket_id: str) -> tuple[bool, str]:
        rocket = self.config.rockets[rocket_id]
        if rocket.get("planet") and rocket["planet"] != self.planet_id:
            planet_name = self.config.planets[rocket["planet"]]["name"]
            return False, f"Only built on {planet_name}"
        producers = {self.component_of(fid): fid for fid in self.floors
                     if self.floor_def(fid)["kind"] == "producer"}
        for comp in self.resolved_recipe(rocket_id):
            fid = producers.get(comp)
            if fid is None:
                return False, f"Needs {self.config.components[comp]['name']}"
            if not self.unlocked(fid):
                return False, f"Unlock {self.floor_def(fid)['name']}"
        return True, ""

    def upgrade_cost(self, floor_id: str, cost_mult: float = 1.0) -> float:
        fdef = self.floor_def(floor_id)
        planet = self.config.planets[self.planet_id]
        level = max(1, self.floors[floor_id].level)
        return upgrade_cost(fdef["base_cost"] * planet["cost_mult"] * cost_mult,
                            fdef["cost_growth"], level)

    def unlock_cost(self, floor_id: str, cost_mult: float = 1.0) -> float:
        fdef = self.floor_def(floor_id)
        return fdef.get("unlock_cost", 0) * self.config.planets[self.planet_id]["cost_mult"] * cost_mult

    def worker_count(self, floor_id: str) -> int:
        """Simulated employees on a floor (only a few are drawn on screen)."""
        level = self.floors[floor_id].level
        if level <= 0:
            return 0
        return 1 + level // 10 + self.workforce.get("hiring", 0)

    def support_multiplier(self, floor_id: str) -> float:
        fdef = self.floor_def(floor_id)
        level = self.floors[floor_id].level
        if level <= 0:
            return 1.0
        return 1.0 + fdef["per_level"] * level * milestone_multiplier(level, self.config.support_milestones)

    # ------------------------------------------------------------------
    def factory_modifiers(self) -> Modifiers:
        """Bonuses that come from inside this factory (planet, workforce, support floors, rocket)."""
        mods = Modifiers()
        planet = self.config.planets[self.planet_id]
        for stat, value in planet.get("modifiers", {}).items():
            mods.mul(stat, value)
        for wdef in self.config.workforce_list:
            level = self.workforce.get(wdef["id"], 0)
            if level:
                mods.mul(wdef["stat"], 1.0 + wdef["per_level"] * level)
        for fid, floor in self.floors.items():
            fdef = self.floor_def(fid)
            if fdef["kind"] == "support" and floor.level > 0:
                mods.mul(fdef["effect"], self.support_multiplier(fid))
        bonus = self.config.rockets[self.rocket_id].get("bonus")
        if bonus:
            mods.apply_effect(bonus)
        return mods

    def compute_stats(self, mods: Modifiers, floor_mods: dict[str, Modifiers] | None = None,
                      ) -> FactoryStats:
        """Calculate every rate for the current levels and bonuses.

        ``mods`` must already include global and factory bonuses.
        ``floor_mods`` holds per-floor manager bonuses (stat 'rate' and 'storage').
        """
        cfg = self.config
        econ = cfg.economy
        floor_mods = floor_mods or {}
        stats = FactoryStats()
        stats.recipe = self.resolved_recipe()
        stats.recipe_total = sum(stats.recipe.values()) or 1.0
        storage_mult = mods.m("storage")
        planet = cfg.planets[self.planet_id]
        for fid, floor in self.floors.items():
            fdef = cfg.floors[fid]
            kind = fdef["kind"]
            stats.automated[fid] = floor.manager_uid is not None
            if kind == "support" or floor.level <= 0:
                stats.rate[fid] = 0.0
                continue
            fm = floor_mods.get(fid)
            local = fm.m("rate") if fm else 1.0
            key = fdef.get("component")
            mult = mods.kind_mult(kind, key)
            if kind == "producer":
                real = self.component_of(fid)
                if real and real != key:
                    mult *= mods.m(f"producer:{real}")
                stats.producer_of[real] = fid
            base = leveled_output(fdef["base_rate"], floor.level, cfg.milestones)
            rate = clamp_big(base * mult * local)
            stats.rate[fid] = rate
            if kind == "producer":
                local_storage = fm.m("storage") if fm else 1.0
                stats.storage_cap[fid] = max(econ["min_storage"], rate * econ["storage_seconds"]) \
                    * storage_mult * local_storage
        # Launchpad
        pad_id = self._first_of_kind("launch")
        stats.capacity = max(1.0, math.floor(stats.rate.get(pad_id, 1.0)))
        interval = econ["launch_interval"] * mods.m("launch_interval")
        stats.interval = max(econ["min_launch_interval"], interval)
        stats.queue_cap = stats.capacity * 3 + 2
        # Assembly input buffer: enough for several rockets or a few seconds of work.
        asm_rate = stats.rate.get(self._first_of_kind("assembly"), 0.0)
        rockets_buffer = max(econ["assembly_buffer_rockets"],
                             asm_rate / stats.recipe_total * econ["storage_seconds"] * 0.5)
        for comp, amount in stats.recipe.items():
            stats.buffer_cap[comp] = amount * rockets_buffer * storage_mult
        rocket = cfg.rockets[self.rocket_id]
        stats.value_per_rocket = clamp_big(rocket["value"] * planet["value_mult"] * mods.m("value"))
        stats.rp_per_rocket = rocket.get("rp", 0.0) * mods.m("rp_gain")
        self._compute_throughput(stats)
        return stats

    def _first_of_kind(self, kind: str) -> str:
        for fid in self.floors:
            if self.config.floors[fid]["kind"] == kind:
                return fid
        raise KeyError(kind)

    def _compute_throughput(self, stats: FactoryStats) -> None:
        """Steady-state rockets/second each stage allows; the minimum is the bottleneck."""
        total = stats.recipe_total
        stage: dict[str, float] = {}
        for comp, amount in stats.recipe.items():
            fid = stats.producer_of.get(comp)
            stage[fid or f"missing:{comp}"] = (stats.rate.get(fid, 0.0) / amount) if fid else 0.0
        transport_id = self._first_of_kind("transport")
        assembly_id = self._first_of_kind("assembly")
        pad_id = self._first_of_kind("launch")
        stage[transport_id] = stats.rate.get(transport_id, 0.0) / total
        stage[assembly_id] = stats.rate.get(assembly_id, 0.0) / total
        stage[pad_id] = stats.capacity / stats.interval
        stats.stage_rockets = stage
        best = min(stage, key=lambda k: stage[k])
        stats.rocket_rate = stage[best]
        stats.bottleneck = best
        auto = {k: (v if stats.automated.get(k, False) else 0.0) for k, v in stage.items()}
        best_auto = min(auto, key=lambda k: auto[k])
        stats.auto_rocket_rate = auto[best_auto]
        stats.auto_bottleneck = best_auto

    # ------------------------------------------------------------------
    def tap(self, floor_id: str, tap_seconds: float, max_seconds: float) -> bool:
        """Player taps a floor that has no manager: it works for a few seconds."""
        floor = self.floors.get(floor_id)
        if not floor or floor.level <= 0 or floor.manager_uid:
            return False
        floor.manual_time = min(max_seconds, floor.manual_time + tap_seconds)
        return True

    def request_launch(self, countdown: float) -> bool:
        """Manual launch: start the countdown if a rocket is ready."""
        if self.ready < 1 or self.countdown > 0:
            return False
        self.countdown = countdown
        return True

    def _active_fraction(self, floor: FloorState, dt: float) -> float:
        if floor.manager_uid is not None:
            return 1.0
        if floor.manual_time <= 0:
            return 0.0
        used = min(floor.manual_time, dt)
        floor.manual_time -= used
        return used / dt

    def step(self, dt: float, stats: FactoryStats) -> list[LaunchResult]:
        """Advance the production chain by ``dt`` seconds."""
        if dt <= 0:
            return []
        launches: list[LaunchResult] = []
        recipe = stats.recipe
        # 1) Producers make components into their own storage.
        for fid, floor in self.floors.items():
            fdef = self.config.floors[fid]
            if fdef["kind"] != "producer" or floor.level <= 0:
                continue
            frac = self._active_fraction(floor, dt)
            cap = stats.storage_cap.get(fid, 0.0)
            made = 0.0
            if frac > 0 and floor.storage < cap:
                made = min(stats.rate[fid] * dt * frac, cap - floor.storage)
                floor.storage += made
                self.components_made += made
            floor.flow += (made / dt - floor.flow) * min(1.0, dt * 2)
        # 2) Transport moves components into the assembly buffer.
        transport = self.floors[self._first_of_kind("transport")]
        frac = self._active_fraction(transport, dt)
        moved_total = 0.0
        if frac > 0:
            budget = stats.rate[transport.id] * dt * frac
            moved_total = self._transport(budget, stats)
        transport.flow += (moved_total / dt - transport.flow) * min(1.0, dt * 2)
        # 3) Assembly turns buffered components into rockets.
        assembly = self.floors[self._first_of_kind("assembly")]
        frac = self._active_fraction(assembly, dt)
        built = 0.0
        if frac > 0 and recipe:
            work = stats.rate[assembly.id] * dt * frac / stats.recipe_total
            limit = min(self.buffer.get(c, 0.0) / a for c, a in recipe.items())
            room = max(0.0, stats.queue_cap - self.ready)
            built = max(0.0, min(work, limit, room))
            if built > 0:
                for comp, amount in recipe.items():
                    self.buffer[comp] = max(0.0, self.buffer.get(comp, 0.0) - built * amount)
                self.ready += built
                self.rockets_built += built
        self.assembly_progress = self.ready % 1.0 if self.ready < 1 else 1.0
        assembly.flow += (built * stats.recipe_total / dt - assembly.flow) * min(1.0, dt * 2)
        # 4) Launchpad.
        pad = self.floors[self._first_of_kind("launch")]
        if pad.manager_uid is not None:
            self.countdown = -1.0
            self.pad_timer += dt
            while self.pad_timer >= stats.interval and self.ready >= 1:
                self.pad_timer -= stats.interval
                launches.append(self._launch(stats))
            if self.ready < 1:
                self.pad_timer = min(self.pad_timer, stats.interval)
        elif self.countdown > 0:
            self.countdown -= dt
            if self.countdown <= 0:
                self.countdown = -1.0
                if self.ready >= 1:
                    launches.append(self._launch(stats))
        return launches

    def _transport(self, budget: float, stats: FactoryStats) -> float:
        """Share the transport budget between components in recipe proportions."""
        recipe = stats.recipe
        moved_total = 0.0
        pending = dict(recipe)
        for _ in range(3):  # a few passes so unused share goes to other components
            if budget <= 1e-12 or not pending:
                break
            weight_sum = sum(pending.values())
            used = 0.0
            for comp in list(pending):
                share = budget * pending[comp] / weight_sum
                fid = stats.producer_of.get(comp)
                if fid is None:
                    pending.pop(comp)
                    continue
                source = self.floors[fid]
                space = stats.buffer_cap.get(comp, 0.0) - self.buffer.get(comp, 0.0)
                amount = max(0.0, min(share, source.storage, space))
                if amount > 0:
                    source.storage -= amount
                    self.buffer[comp] = self.buffer.get(comp, 0.0) + amount
                    used += amount
                if amount < share - 1e-12:
                    pending.pop(comp)  # this component is satisfied or empty
            budget -= used
            moved_total += used
        return moved_total

    @staticmethod
    def rp_for_launch(count: float, stats: FactoryStats) -> float:
        """Research Points grow with the logarithm of the batch size, so RP stays
        meaningful instead of exploding with production."""
        if count < 1:
            return 0.0
        return stats.rp_per_rocket * (1.0 + math.log10(count))

    def _launch(self, stats: FactoryStats) -> LaunchResult:
        count = min(math.floor(self.ready), stats.capacity)
        self.ready -= count
        return LaunchResult(self.planet_id, self.rocket_id, count,
                            clamp_big(count * stats.value_per_rocket),
                            self.rp_for_launch(count, stats))

    def launch_all_ready(self, stats: FactoryStats) -> LaunchResult | None:
        """Sell every waiting rocket immediately (used when switching rocket type)."""
        if self.ready < 1:
            self.ready = 0.0
            return None
        count = math.floor(self.ready)
        self.ready = 0.0
        return LaunchResult(self.planet_id, self.rocket_id, count,
                            clamp_big(count * stats.value_per_rocket), self.rp_for_launch(count, stats))

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"planet_id": self.planet_id,
                "floors": [f.to_dict() for f in self.floors.values()],
                "buffer": dict(self.buffer), "ready": self.ready, "pad_timer": self.pad_timer,
                "rocket_id": self.rocket_id, "workforce": dict(self.workforce),
                "rockets_built": self.rockets_built, "components_made": self.components_made}

    @classmethod
    def from_dict(cls, config: "GameConfig", data: dict) -> "Factory":
        factory = cls(config, data["planet_id"])
        for fdata in data.get("floors", []):
            if fdata.get("id") in factory.floors:
                factory.floors[fdata["id"]] = FloorState.from_dict(fdata)
        # Floors from a newer config that the save does not know keep defaults.
        factory.buffer = {k: max(0.0, float(v)) for k, v in data.get("buffer", {}).items()
                          if k in config.components}
        factory.ready = max(0.0, float(data.get("ready", 0.0)))
        factory.pad_timer = max(0.0, float(data.get("pad_timer", 0.0)))
        rocket_id = data.get("rocket_id")
        if rocket_id in config.rockets:
            factory.rocket_id = rocket_id
        for wid, level in data.get("workforce", {}).items():
            if wid in factory.workforce:
                factory.workforce[wid] = max(0, int(level))
        factory.rockets_built = float(data.get("rockets_built", 0.0))
        factory.components_made = float(data.get("components_made", 0.0))
        return factory
