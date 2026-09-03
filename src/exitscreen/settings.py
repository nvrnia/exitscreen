"""Where you live and when you travel: the values that are yours, not the code's.

Everything here is personal - a home metro stop, a weekly class timetable, the
minutes a particular walk takes. None of it belongs in a public repository: a
timetable plus a station is a published statement of when a specific person
leaves a specific building, and no reader of the code needs it.

So it lives in assets/settings.json, which is gitignored, exactly as .env
already holds the TickTick token. assets/settings.example.json is committed as
the template. This is the same split the project already uses, not a new one.

Fails closed and loudly: a missing or malformed settings file raises with an
instruction rather than quietly falling back to someone else's commute.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).resolve().parents[2] / "assets"
SETTINGS = ASSETS / "settings.json"
EXAMPLE = ASSETS / "settings.example.json"


class SettingsError(RuntimeError):
    """Settings are missing or unusable. The message says how to fix it."""


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    """The whole settings file, read once per process."""
    if not SETTINGS.exists():
        raise SettingsError(
            f"{SETTINGS} not found.\n"
            f"Copy {EXAMPLE.name} to {SETTINGS.name} and fill in your own stop, "
            f"coordinates and timetable. It is gitignored on purpose."
        )
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SettingsError(f"{SETTINGS} could not be read: {exc}") from exc
    if not isinstance(data, dict):
        raise SettingsError(f"{SETTINGS} should contain a JSON object")
    return data


def section(name: str) -> dict[str, Any]:
    """One top-level block, e.g. "metro". Missing blocks are an error, not {}.

    Returning an empty dict would let a caller silently use its own defaults and
    render a plausible-looking frame for the wrong city.
    """
    data = load()
    if name not in data or not isinstance(data[name], dict):
        raise SettingsError(
            f'{SETTINGS.name} has no "{name}" section. '
            f"Compare it against {EXAMPLE.name}."
        )
    return data[name]


def get(name: str, key: str, default: Any = None) -> Any:
    """One value, with a default for genuinely optional tuning knobs."""
    return section(name).get(key, default)
