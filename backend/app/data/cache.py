"""Small JSON cache keyed by a string.

File-backed for now (data/cache/, gitignored). After step 1.1 the `data_cache` table can take
over behind the same get/set interface, so fetchers don't change.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Protocol

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "cache"


class Cache(Protocol):
    def get(self, key: str, max_age_s: float | None = None) -> Any | None: ...

    def set(self, key: str, value: Any) -> None: ...


class FileCache:
    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.root / digest[:2] / f"{digest}.json"

    def get(self, key: str, max_age_s: float | None = None) -> Any | None:
        """Return the cached value, or None if missing, unreadable or older than max_age_s."""
        path = self._path(key)
        try:
            if max_age_s is not None and time.time() - path.stat().st_mtime > max_age_s:
                return None
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def set(self, key: str, value: Any) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file, then rename, so a crash never leaves a half-written entry.
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(value, f)
        os.replace(tmp, path)
