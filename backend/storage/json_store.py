from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from filelock import FileLock

from backend.storage.schema import HearthDoc

logger = logging.getLogger(__name__)


class JsonStore:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._path = data_dir / "hearth.json"
        self._bak = data_dir / "hearth.json.bak"
        self._lock_path = data_dir / "hearth.json.lock"
        self._lock = FileLock(str(self._lock_path))

    def _ensure_dir(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _default_doc(self) -> dict:
        return HearthDoc().model_dump()

    def _ensure_defaults(self, doc: dict) -> dict:
        """Fill in any top-level keys that are missing from an older document."""
        defaults = self._default_doc()
        for key, value in defaults.items():
            if key not in doc:
                doc[key] = value
        return doc

    def read(self) -> dict:
        self._ensure_dir()
        if not self._path.exists():
            return self._default_doc()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return self._ensure_defaults(raw)
        except (json.JSONDecodeError, OSError):
            logger.warning("hearth.json unreadable; attempting recovery from .bak")
            if self._bak.exists():
                try:
                    raw = json.loads(self._bak.read_text(encoding="utf-8"))
                    return self._ensure_defaults(raw)
                except (json.JSONDecodeError, OSError):
                    logger.error("Backup also unreadable; starting fresh")
            return self._default_doc()

    def write(self, data: dict) -> None:
        self._ensure_dir()
        with self._lock:
            tmp = self._path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            if self._path.exists():
                shutil.copy2(self._path, self._bak)
            os.replace(tmp, self._path)

    def mutate(self, fn: Callable[[dict], None]) -> None:
        with self._lock:
            data = self.read()
            fn(data)
            # write acquires lock again; release here to avoid deadlock by calling internal method
            tmp = self._path.with_suffix(".json.tmp")
            self._ensure_dir()
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            if self._path.exists():
                shutil.copy2(self._path, self._bak)
            os.replace(tmp, self._path)
