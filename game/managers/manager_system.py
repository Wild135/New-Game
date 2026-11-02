"""Managers: hire them, assign them to floors (which automates the floor),
level them up and trigger their active abilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from game.economy.modifiers import Modifiers

if TYPE_CHECKING:  # pragma: no cover
    from game.core.game import Game

SLOT_KINDS = {
    "producer": ("producer",),
    "transport": ("transport",),
    "assembly": ("assembly",),
    "launch": ("launch",),
    "any": ("producer", "transport", "assembly", "launch"),
}
RARITY_ORDER = ["common", "rare", "epic", "legendary"]


@dataclass
class ManagerInstance:
    uid: str
    def_id: str
    surname: str
    level: int = 1
    planet: str | None = None
    floor: str | None = None
    cooldown: float = 0.0      # seconds until the ability can be used again
    active: float = 0.0        # seconds the ability is still running

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict) -> "ManagerInstance":
        return cls(uid=str(data["uid"]), def_id=str(data["def_id"]),
                   surname=str(data.get("surname", "")), level=max(1, int(data.get("level", 1))),
                   planet=data.get("planet"), floor=data.get("floor"),
                   cooldown=max(0.0, float(data.get("cooldown", 0.0))),
                   active=max(0.0, float(data.get("active", 0.0))))


class ManagerSystem:
    def __init__(self, game: "Game"):
        self.game = game
        self.cfg = game.config
        self.instances: list[ManagerInstance] = []
        self.next_uid = 1

    # ------------------------------------------------------------------
    def definition(self, inst: ManagerInstance) -> dict:
        return self.cfg.managers[inst.def_id]

    def get(self, uid: str | None) -> ManagerInstance | None:
        for inst in self.instances:
            if inst.uid == uid:
                return inst
        return None

    def display_name(self, inst: ManagerInstance) -> str:
        return f"{self.cfg.managers[inst.def_id]['name']} {inst.surname}".strip()

    def hired_count(self, def_id: str | None = None, rarity: str | None = None) -> int:
        count = 0
        for inst in self.instances:
            mdef = self.cfg.managers[inst.def_id]
            if def_id and inst.def_id != def_id:
                continue
            if rarity and mdef["rarity"] != rarity:
                continue
            count += 1
        return count

    def hire_cost(self, def_id: str) -> tuple[float, str]:
        """Returns (cost, currency) where currency is 'credits' or 'gems'."""
        econ = self.cfg.economy
        mdef = self.cfg.managers[def_id]
        rarity = mdef["rarity"]
        if rarity in ("common", "rare"):
            count = self.hired_count(rarity=rarity)
            scale = self.game.best_planet_cost_mult()
            cost = econ["manager_hire_base"][rarity] * econ["manager_hire_growth"][rarity] ** count * scale
            return cost, "credits"
        count = self.hired_count(def_id=def_id)
        return float(round(econ["manager_gem_cost"][rarity] * econ["manager_gem_growth"] ** count)), "gems"

    def can_hire(self, def_id: str) -> tuple[bool, str]:
        mdef = self.cfg.managers[def_id]
        if mdef.get("unique") and self.hired_count(def_id=def_id) > 0:
            return False, "Already hired"
        cost, currency = self.hire_cost(def_id)
        balance = self.game.credits if currency == "credits" else self.game.gems
        if balance < cost:
            return False, "Not enough " + ("credits" if currency == "credits" else "gems")
        return True, ""

    def hire(self, def_id: str) -> ManagerInstance | None:
        ok, reason = self.can_hire(def_id)
        if not ok:
            self.game.toast(reason)
            return None
        cost, currency = self.hire_cost(def_id)
        if currency == "credits":
            if not self.game.spend_credits(cost):
                return None
        elif not self.game.spend_gems(cost):
            return None
        surnames = self.cfg.surnames
        surname = surnames[(self.next_uid * 7 + len(def_id)) % len(surnames)]
        inst = ManagerInstance(uid=f"m{self.next_uid}", def_id=def_id, surname=surname)
        self.next_uid += 1
        self.instances.append(inst)
        self.game.stats["managers_hired"] += 1
        self.game.emit("manager_hired", uid=inst.uid)
        return inst

    def fits(self, inst_or_def: ManagerInstance | str, floor_kind: str) -> bool:
        def_id = inst_or_def if isinstance(inst_or_def, str) else inst_or_def.def_id
        slot = self.cfg.managers[def_id]["slot"]
        return floor_kind in SLOT_KINDS[slot]

    def assign(self, uid: str, planet_id: str, floor_id: str) -> bool:
        inst = self.get(uid)
        factory = self.game.factories.get(planet_id)
        if inst is None or factory is None or floor_id not in factory.floors:
            return False
        floor = factory.floors[floor_id]
        kind = self.cfg.floors[floor_id]["kind"]
        if floor.level <= 0 or not self.fits(inst, kind):
            self.game.toast("This manager can't run that floor")
            return False
        self.unassign(uid)
        if floor.manager_uid:
            self.unassign(floor.manager_uid)
        inst.planet, inst.floor = planet_id, floor_id
        floor.manager_uid = uid
        floor.manual_time = 0.0
        self.game.emit("manager_assigned", uid=uid, planet=planet_id, floor=floor_id)
        return True

    def unassign(self, uid: str) -> None:
        inst = self.get(uid)
        if inst is None or inst.planet is None:
            return
        factory = self.game.factories.get(inst.planet)
        if factory and inst.floor in factory.floors and factory.floors[inst.floor].manager_uid == uid:
            factory.floors[inst.floor].manager_uid = None
        inst.planet = inst.floor = None
        inst.active = 0.0

    def unassign_all(self) -> None:
        for inst in self.instances:
            inst.planet = inst.floor = None
            inst.active = 0.0

    def upgrade_cost(self, inst: ManagerInstance) -> float:
        econ = self.cfg.economy
        rarity = self.cfg.managers[inst.def_id]["rarity"]
        return econ["manager_level_cost"][rarity] * econ["manager_level_growth"] ** (inst.level - 1) \
            * self.game.best_planet_cost_mult()

    def upgrade(self, uid: str) -> bool:
        inst = self.get(uid)
        if inst is None:
            return False
        if inst.level >= self.cfg.economy["manager_max_level"]:
            self.game.toast("Manager is at max level")
            return False
        if not self.game.spend_credits(self.upgrade_cost(inst)):
            self.game.toast("Not enough credits")
            return False
        inst.level += 1
        self.game.emit("manager_upgraded", uid=uid)
        return True

    def activate(self, uid: str) -> bool:
        inst = self.get(uid)
        if inst is None or inst.planet is None:
            self.game.toast("Assign the manager to a floor first")
            return False
        if inst.cooldown > 0:
            return False
        ability = self.cfg.managers[inst.def_id]["active"]
        inst.active = ability["duration"]
        inst.cooldown = ability["cooldown"]
        self.game.stats["abilities_used"] += 1
        self.game.emit("ability", uid=uid, name=ability["name"])
        return True

    def tick(self, dt: float) -> None:
        for inst in self.instances:
            if inst.cooldown > 0:
                inst.cooldown = max(0.0, inst.cooldown - dt)
            if inst.active > 0:
                inst.active = max(0.0, inst.active - dt)

    # ------------------------------------------------------------------
    def passive_strength(self, inst: ManagerInstance) -> float:
        econ = self.cfg.economy
        bonus = self.game.global_mods_cached.a("manager_bonus")
        return (1 + econ["manager_level_bonus"] * (inst.level - 1)) * (1 + bonus)

    @staticmethod
    def scale_mult(mult: float, strength: float) -> float:
        if mult >= 1:
            return 1 + (mult - 1) * strength
        return max(0.3, 1 - (1 - mult) * strength)

    def floor_and_factory_mods(self, planet_id: str, include_active: bool = True
                               ) -> tuple[dict[str, Modifiers], Modifiers]:
        floor_mods: dict[str, Modifiers] = {}
        factory_mods = Modifiers()
        for inst in self.instances:
            if inst.planet != planet_id or inst.floor is None:
                continue
            mdef = self.cfg.managers[inst.def_id]
            strength = self.passive_strength(inst)
            fm = floor_mods.setdefault(inst.floor, Modifiers())
            for eff in mdef["passive"]:
                value = self.scale_mult(eff["mult"], strength)
                if eff.get("scope") == "factory":
                    factory_mods.mul(eff["stat"], value)
                else:
                    fm.mul(eff["stat"], value)
            if include_active and inst.active > 0:
                ability = mdef["active"]
                if ability.get("scope") == "factory":
                    factory_mods.mul(ability["stat"], ability["mult"])
                else:
                    fm.mul(ability["stat"], ability["mult"])
        return floor_mods, factory_mods

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"instances": [i.to_dict() for i in self.instances], "next_uid": self.next_uid}

    def load(self, data: dict) -> None:
        self.instances = []
        for idata in data.get("instances", []):
            try:
                inst = ManagerInstance.from_dict(idata)
            except (KeyError, ValueError, TypeError):
                continue
            if inst.def_id in self.cfg.managers:
                self.instances.append(inst)
        self.next_uid = max([int(data.get("next_uid", 1))] +
                            [int(i.uid[1:]) + 1 for i in self.instances if i.uid[1:].isdigit()])
