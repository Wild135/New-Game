"""Loads and validates the JSON balance files in ``config/``.

All game numbers live in those files so the economy can be tuned without
touching code.  ``GameConfig`` checks the data on load and raises a clear
``ConfigError`` if something is wrong (missing ids, negative costs, ...).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from game.paths import resource_path


class ConfigError(ValueError):
    """Raised when a configuration file contains invalid data."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing config file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path.name}: {exc}") from exc


def _index(items: list[dict], what: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in items:
        if "id" not in item:
            raise ConfigError(f"A {what} entry has no 'id': {item}")
        if item["id"] in result:
            raise ConfigError(f"Duplicate {what} id '{item['id']}'")
        result[item["id"]] = item
    return result


def _positive(value: Any, label: str, allow_zero: bool = False) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{label} must be a number, got {value!r}")
    if value < 0 or (value == 0 and not allow_zero):
        raise ConfigError(f"{label} must be {'>= 0' if allow_zero else '> 0'}, got {value}")


class GameConfig:
    """All configuration in one object."""

    def __init__(self, config_dir: Path | None = None, overrides: dict[str, dict] | None = None):
        self.dir = Path(config_dir) if config_dir else resource_path("config")
        raw: dict[str, dict] = {}
        for name in ("economy", "floors", "rockets", "planets", "managers", "research",
                     "missions", "achievements", "prestige", "shop"):
            raw[name] = _load_json(self.dir / f"{name}.json")
        if overrides:
            for name, data in overrides.items():
                raw[name] = data
        self.raw = raw
        self.economy: dict[str, Any] = raw["economy"]
        self.floor_list: list[dict] = raw["floors"]["floors"]
        self.floors = _index(self.floor_list, "floor")
        self.components: dict[str, dict] = raw["floors"]["components"]
        self.rocket_list: list[dict] = raw["rockets"]["rockets"]
        self.rockets = _index(self.rocket_list, "rocket")
        self.planet_list: list[dict] = raw["planets"]["planets"]
        self.planets = _index(self.planet_list, "planet")
        self.manager_list: list[dict] = raw["managers"]["managers"]
        self.managers = _index(self.manager_list, "manager")
        self.surnames: list[str] = raw["managers"].get("surnames", ["Smith"])
        self.research_list: list[dict] = raw["research"]["research"]
        self.research = _index(self.research_list, "research")
        self.research_categories: list[str] = raw["research"]["categories"]
        self.main_missions: list[dict] = raw["missions"]["main"]
        self.daily_pool: list[dict] = raw["missions"]["daily_pool"]
        self.achievement_list: list[dict] = raw["achievements"]["achievements"]
        self.achievements = _index(self.achievement_list, "achievement")
        self.prestige: dict[str, Any] = raw["prestige"]
        self.legacy_upgrades = _index(self.prestige["upgrades"], "legacy upgrade")
        self.boosts = _index(raw["shop"]["boosts"], "boost")
        self.cosmetic_list: list[dict] = raw["shop"]["cosmetics"]
        self.cosmetics = _index(self.cosmetic_list, "cosmetic")
        self.workforce_list: list[dict] = raw["shop"]["workforce"]
        self.workforce = _index(self.workforce_list, "workforce upgrade")
        self.milestones: list[list[float]] = sorted(self.economy["milestones"])
        self.support_milestones: list[list[float]] = sorted(self.economy["support_milestones"])
        self.validate()

    # ------------------------------------------------------------------
    def validate(self) -> None:
        econ = self.economy
        for key in ("tick_seconds", "storage_seconds", "launch_interval", "offline_cap_hours",
                    "manual_tap_seconds", "manual_max_seconds"):
            _positive(econ.get(key), f"economy.{key}")
        if not 0 <= econ.get("offline_efficiency", 0) <= 1:
            raise ConfigError("economy.offline_efficiency must be between 0 and 1")
        for floor in self.floor_list:
            label = f"floor '{floor['id']}'"
            if floor.get("kind") not in ("producer", "transport", "assembly", "launch", "support"):
                raise ConfigError(f"{label} has unknown kind {floor.get('kind')!r}")
            _positive(floor.get("base_cost"), f"{label}.base_cost")
            _positive(floor.get("unlock_cost", 0), f"{label}.unlock_cost", allow_zero=True)
            growth = floor.get("cost_growth")
            _positive(growth, f"{label}.cost_growth")
            if growth < 1:
                raise ConfigError(f"{label}.cost_growth must be >= 1")
            if floor["kind"] == "support":
                _positive(floor.get("per_level"), f"{label}.per_level")
            else:
                _positive(floor.get("base_rate"), f"{label}.base_rate")
            if floor["kind"] == "producer":
                comp = floor.get("component")
                if comp != "special" and comp not in self.components:
                    raise ConfigError(f"{label} produces unknown component {comp!r}")
        for kind in ("launch", "assembly", "transport"):
            if not any(f["kind"] == kind for f in self.floor_list):
                raise ConfigError(f"floors.json needs a '{kind}' floor")
        for rocket in self.rocket_list:
            label = f"rocket '{rocket['id']}'"
            if not rocket.get("recipe"):
                raise ConfigError(f"{label} has an empty recipe")
            for comp, amount in rocket["recipe"].items():
                if comp != "special" and comp not in self.components:
                    raise ConfigError(f"{label} needs unknown component {comp!r}")
                _positive(amount, f"{label}.recipe.{comp}")
            _positive(rocket.get("value"), f"{label}.value")
            _positive(rocket.get("unlock_cost", 0), f"{label}.unlock_cost", allow_zero=True)
            if rocket.get("planet") and rocket["planet"] not in self.planets:
                raise ConfigError(f"{label} references unknown planet {rocket['planet']!r}")
            if rocket.get("research") and rocket["research"] not in self.research:
                raise ConfigError(f"{label} references unknown research {rocket['research']!r}")
            if "special" in rocket["recipe"] and not rocket.get("planet"):
                raise ConfigError(f"{label} uses a special resource but has no planet")
        if self.rocket_list[0].get("unlock_cost", 0) != 0:
            raise ConfigError("The first rocket must be free (unlock_cost 0)")
        if self.planet_list[0].get("unlock_cost", 0) != 0:
            raise ConfigError("The first planet must be free (unlock_cost 0)")
        for planet in self.planet_list:
            label = f"planet '{planet['id']}'"
            _positive(planet.get("value_mult"), f"{label}.value_mult")
            _positive(planet.get("cost_mult"), f"{label}.cost_mult")
            special = planet.get("special")
            if special and special not in self.components:
                raise ConfigError(f"{label} special resource {special!r} is not a component")
        for manager in self.manager_list:
            label = f"manager '{manager['id']}'"
            if manager.get("rarity") not in ("common", "rare", "epic", "legendary"):
                raise ConfigError(f"{label} has unknown rarity")
            if manager.get("slot") not in ("producer", "transport", "assembly", "launch", "any"):
                raise ConfigError(f"{label} has unknown slot")
            active = manager.get("active", {})
            _positive(active.get("duration"), f"{label}.active.duration")
            _positive(active.get("cooldown"), f"{label}.active.cooldown")
        for research in self.research_list:
            label = f"research '{research['id']}'"
            _positive(research.get("cost"), f"{label}.cost")
            if research.get("category") not in self.research_categories:
                raise ConfigError(f"{label} has unknown category")
            for req in research.get("requires", []):
                if req not in self.research:
                    raise ConfigError(f"{label} requires unknown research {req!r}")
        for mission in self.main_missions:
            _positive(mission.get("target"), f"mission '{mission['id']}'.target")
        for ach in self.achievement_list:
            if len(ach["tiers"]) != len(ach["rewards"]):
                raise ConfigError(f"achievement '{ach['id']}' tiers/rewards length mismatch")
            if ach["tiers"] != sorted(ach["tiers"]):
                raise ConfigError(f"achievement '{ach['id']}' tiers must be ascending")

    # ------------------------------------------------------------------
    def component_for(self, comp: str, planet_id: str) -> str | None:
        """Resolve the 'special' placeholder to the planet's special resource."""
        if comp == "special":
            return self.planets[planet_id].get("special")
        return comp

    def floor_available_on(self, floor_id: str, planet_id: str) -> bool:
        """The Planetary Refinery only exists on planets with a special resource."""
        if floor_id == "special":
            return bool(self.planets[planet_id].get("special"))
        return True
