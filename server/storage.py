from __future__ import annotations

import json
import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
REPORTS_DIR = DATA_DIR / "migration_reports"

DEFAULT_SETTINGS = {
    "retention_days": 30,
    "max_file_size_mb": 1024,
    "allowed_extensions": [".stl", ".json"],
    "upload_access_mode": "open_lan",
    "upload_shared_password": "",
}

DEFAULT_ADMINS = {"admins": []}
DEFAULT_SESSIONS = {"sessions": []}
DEFAULT_UPLOADERS = {"uploaders": []}
DEFAULT_UPLOADS = {"batches": [], "files": []}
DEFAULT_GROUPS = {"groups": {}}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=path.parent) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
    Path(tmp.name).replace(path)


@dataclass
class DataStore:
    data_dir: Path = DATA_DIR

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self.files_dir = self.data_dir / "files"
        self.reports_dir = self.data_dir / "migration_reports"
        self.admins_path = self.data_dir / "admins.json"
        self.sessions_path = self.data_dir / "sessions.json"
        self.uploaders_path = self.data_dir / "uploaders.json"
        self.uploads_path = self.data_dir / "uploads.json"
        self.settings_path = self.data_dir / "settings.json"
        self.groups_path = self.data_dir / "groups.json"

    def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_file(self.admins_path, DEFAULT_ADMINS)
        self._ensure_file(self.sessions_path, DEFAULT_SESSIONS)
        self._ensure_file(self.uploaders_path, DEFAULT_UPLOADERS)
        self._ensure_file(self.uploads_path, DEFAULT_UPLOADS)
        self._ensure_file(self.settings_path, DEFAULT_SETTINGS)
        self._ensure_file(self.groups_path, DEFAULT_GROUPS)

    def _ensure_file(self, path: Path, default_payload: dict[str, Any]) -> None:
        if not path.exists():
            atomic_write_json(path, deepcopy(default_payload))

    def _read_json(self, path: Path, default_payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if not path.exists():
                atomic_write_json(path, deepcopy(default_payload))
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        with self._lock:
            atomic_write_json(path, payload)

    def read_admins(self) -> dict[str, Any]:
        return self._read_json(self.admins_path, DEFAULT_ADMINS)

    def write_admins(self, payload: dict[str, Any]) -> None:
        self._write_json(self.admins_path, payload)

    def read_sessions(self) -> dict[str, Any]:
        return self._read_json(self.sessions_path, DEFAULT_SESSIONS)

    def write_sessions(self, payload: dict[str, Any]) -> None:
        self._write_json(self.sessions_path, payload)

    def read_uploaders(self) -> dict[str, Any]:
        return self._read_json(self.uploaders_path, DEFAULT_UPLOADERS)

    def write_uploaders(self, payload: dict[str, Any]) -> None:
        self._write_json(self.uploaders_path, payload)

    def read_uploads(self) -> dict[str, Any]:
        return self._read_json(self.uploads_path, DEFAULT_UPLOADS)

    def write_uploads(self, payload: dict[str, Any]) -> None:
        self._write_json(self.uploads_path, payload)

    def read_settings(self) -> dict[str, Any]:
        data = self._read_json(self.settings_path, DEFAULT_SETTINGS)
        for key, value in DEFAULT_SETTINGS.items():
            data.setdefault(key, value)
        return data

    def write_settings(self, payload: dict[str, Any]) -> None:
        for key, value in DEFAULT_SETTINGS.items():
            payload.setdefault(key, value)
        self._write_json(self.settings_path, payload)

    def read_groups(self) -> dict[str, Any]:
        return self._read_json(self.groups_path, DEFAULT_GROUPS)

    def write_groups(self, payload: dict[str, Any]) -> None:
        self._write_json(self.groups_path, payload)

    def update(self, reader: Callable[[], dict[str, Any]], writer: Callable[[dict[str, Any]], None], mutator: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            data = reader()
            mutated = mutator(data)
            writer(mutated)
            return mutated
