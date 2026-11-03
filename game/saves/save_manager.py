"""Reliable JSON saves.

* Atomic writes: data goes to a temporary file, is flushed to disk, then
  renamed over the real save.  A crash mid-write can't corrupt the save.
* A checksum detects damaged files.
* The previous saves are kept as backups (save.bak1.json ... save.bak3.json).
  If the main save is broken we load the newest valid backup instead.
* Saves carry a version number; ``migrate`` upgrades old formats.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from game.paths import user_data_dir

CURRENT_VERSION = 1
BACKUP_COUNT = 3


class SaveError(Exception):
    pass


def _checksum(payload: dict) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def migrate(data: dict) -> dict:
    """Upgrade old save formats to the current version, step by step."""
    version = int(data.get("version", 0))
    if version > CURRENT_VERSION:
        raise SaveError(f"Save is from a newer game version ({version})")
    if version < 1:
        # Version 0 (pre-release) stored money as "money" instead of "credits".
        if "money" in data and "credits" not in data:
            data["credits"] = data.pop("money")
        data["version"] = 1
    # Future: if version < 2: ... data["version"] = 2
    return data


class SaveManager:
    def __init__(self, directory: Path | None = None, filename: str = "save.json"):
        self.directory = Path(directory) if directory else user_data_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / filename
        self.last_error: str | None = None
        self.loaded_from: Path | None = None

    def backup_path(self, index: int) -> Path:
        return self.directory / f"{self.path.stem}.bak{index}{self.path.suffix}"

    # ------------------------------------------------------------------
    def save(self, data: dict) -> None:
        payload = {"format": "rocket_empire_save", "checksum": _checksum(data), "data": data}
        text = json.dumps(payload, separators=(",", ":"))
        # Validate before touching the existing files.
        if self._decode(text) is None:
            raise SaveError("Refusing to write an invalid save")
        self._rotate_backups()
        fd, tmp_name = tempfile.mkstemp(prefix=".save-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _rotate_backups(self) -> None:
        if not self.path.exists() or self._read_file(self.path) is None:
            return  # never let a broken save push out a good backup
        for index in range(BACKUP_COUNT, 1, -1):
            older = self.backup_path(index - 1)
            if older.exists():
                os.replace(older, self.backup_path(index))
        shutil.copy2(self.path, self.backup_path(1))

    # ------------------------------------------------------------------
    @staticmethod
    def _decode(text: str) -> dict | None:
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("format") != "rocket_empire_save":
            return None
        data = payload.get("data")
        if not isinstance(data, dict) or payload.get("checksum") != _checksum(data):
            return None
        return data

    def _read_file(self, path: Path) -> dict | None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        return self._decode(text)

    def load(self) -> dict[str, Any] | None:
        """Return the newest valid save data, or None if there is no save at all."""
        self.last_error = None
        candidates = [self.path] + [self.backup_path(i) for i in range(1, BACKUP_COUNT + 1)]
        any_exists = False
        for candidate in candidates:
            if not candidate.exists():
                continue
            any_exists = True
            data = self._read_file(candidate)
            if data is None:
                self.last_error = f"{candidate.name} is damaged"
                continue
            try:
                data = migrate(data)
            except SaveError as exc:
                self.last_error = str(exc)
                continue
            self.loaded_from = candidate
            if candidate != self.path:
                self.last_error = f"Main save was damaged - restored {candidate.name}"
            return data
        if any_exists and self.last_error is None:
            self.last_error = "No valid save found"
        return None

    def delete_all(self) -> None:
        for candidate in [self.path] + [self.backup_path(i) for i in range(1, BACKUP_COUNT + 1)]:
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass
