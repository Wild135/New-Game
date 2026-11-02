"""File locations.

* ``resource_path`` finds bundled files (config, fonts) both when running from
  source and from a PyInstaller-built .exe.
* ``user_data_dir`` is where saves live.  On Windows this is
  ``%APPDATA%\\RocketEmpire`` so we never write into the install folder.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "RocketEmpire"


def project_root() -> Path:
    # PyInstaller unpacks bundled data into sys._MEIPASS.
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir)
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return project_root().joinpath(*parts)


def user_data_dir() -> Path:
    override = os.environ.get("ROCKET_EMPIRE_DATA_DIR")
    if override:
        path = Path(override)
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
