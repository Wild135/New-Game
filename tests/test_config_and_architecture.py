"""Configuration validation and architecture rules."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from game.core.config import ConfigError, GameConfig

ROOT = Path(__file__).resolve().parent.parent


def load_raw(name):
    return json.loads((ROOT / "config" / f"{name}.json").read_text())


def test_default_config_is_valid(config):
    assert config.floors["parts"]["kind"] == "producer"
    assert len(config.rocket_list) == 10
    assert len(config.planet_list) == 9


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d["floors"].__setitem__(0, {**d["floors"][0], "base_cost": -5}), "base_cost"),
    (lambda d: d["floors"].__setitem__(0, {**d["floors"][0], "kind": "teleporter"}), "unknown kind"),
    (lambda d: d["floors"].append(dict(d["floors"][0])), "Duplicate"),
    (lambda d: d["floors"].__setitem__(3, {**d["floors"][3], "cost_growth": 0.9}), "cost_growth"),
])
def test_invalid_floor_config(mutate, message):
    data = copy.deepcopy(load_raw("floors"))
    mutate(data)
    with pytest.raises(ConfigError, match=message):
        GameConfig(overrides={"floors": data})


def test_invalid_rocket_reference():
    data = copy.deepcopy(load_raw("rockets"))
    data["rockets"][1]["recipe"] = {"unobtainium": 3}
    with pytest.raises(ConfigError, match="unknown component"):
        GameConfig(overrides={"rockets": data})


def test_invalid_research_requirement():
    data = copy.deepcopy(load_raw("research"))
    data["research"][0]["requires"] = ["time_travel"]
    with pytest.raises(ConfigError, match="unknown research"):
        GameConfig(overrides={"research": data})


def test_missing_config_dir(tmp_path):
    with pytest.raises(ConfigError, match="Missing config file"):
        GameConfig(config_dir=tmp_path)


def test_bad_json(tmp_path):
    for f in (ROOT / "config").glob("*.json"):
        (tmp_path / f.name).write_text(f.read_text())
    (tmp_path / "economy.json").write_text("{oops")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        GameConfig(config_dir=tmp_path)


def test_game_logic_does_not_import_pygame():
    """Gameplay logic must stay independent from the graphics engine (mobile port)."""
    code = ("import sys; import game.core.game, game.economy.offline, game.saves.save_manager; "
            "print('pygame' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
