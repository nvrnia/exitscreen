"""Tiny on-disk cache shared by the data blocks.

Two jobs, both about never showing a broken screen:
  - survive an outage: keep the last good answer when a feed goes down
  - be a good citizen: skip the network entirely if the last answer is fresh

Deliberately plain JSON files. Anything cached here is disposable - deleting
the cache directory is always safe.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"


def _path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


def save(name: str, payload: Any) -> None:
    """Write atomically, via a temp file unique to this writer.

    The temp name used to be just "{name}.tmp", shared by every process. Two
    writers hitting the same key would interleave into one file and then both
    rename it: on Windows that raises, and on Linux it silently produces spliced
    JSON that load() later discards as "no cache". run.py takes a lock, but any
    tool run by hand - preview.py --live, say - can land on top of the cron job.

    mkstemp gives each writer its own file in the same directory, so the rename
    stays atomic and nobody can be halfway through the file being renamed.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    blob = json.dumps({"saved_at": time.time(), "payload": payload})

    fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, prefix=f".{name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(blob)
        # Atomic: a reader sees either the old file or the new one, never a
        # half-written one, and a crash mid-write cannot truncate the real cache.
        os.replace(tmp, _path(name))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


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
