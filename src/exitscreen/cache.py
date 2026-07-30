"""Tiny on-disk cache shared by the data blocks.

Two jobs, both about never showing a broken screen:
  - survive an outage: keep the last good answer when a feed goes down
  - be a good citizen: skip the network entirely if the last answer is fresh

Deliberately plain JSON files. Anything cached here is disposable - deleting
the cache directory is always safe.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"


def _path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


def save(name: str, payload: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _path(name).with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"saved_at": time.time(), "payload": payload}),
        encoding="utf-8",
    )
    # Replace atomically so a crash mid-write cannot leave a truncated cache
    # that then fails to parse on the next boot.
    tmp.replace(_path(name))


def load(name: str, max_age: float | None = None) -> Any | None:
    """Return the cached payload, or None if absent, unreadable or too old."""
    path = _path(name)
    if not path.exists():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if max_age is not None and time.time() - blob.get("saved_at", 0) > max_age:
        return None
    return blob.get("payload")


def age(name: str) -> float | None:
    """Seconds since this entry was written, or None if there isn't one."""
    path = _path(name)
    if not path.exists():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return time.time() - blob.get("saved_at", 0)
