"""Read and update the untracked .env file.

Deliberately stdlib-only rather than pulling in python-dotenv: this reads a
handful of KEY=value lines and the project has no other use for a dependency.

Values written back preserve the file's comments and ordering, so .env stays
readable and hand-editable after a script has touched it.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load() -> dict[str, str]:
    """All values from .env, with real environment variables taking precedence.

    The env-var override matters on the Pi, where systemd or cron may supply
    secrets directly rather than via a file.
    """
    values: dict[str, str] = {}

    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

    for key in list(values) + [
        "TICKTICK_CLIENT_ID",
        "TICKTICK_CLIENT_SECRET",
        "TICKTICK_REDIRECT_URI",
        "TICKTICK_ACCESS_TOKEN",
        "TICKTICK_PROJECT_ID",
    ]:
        if os.environ.get(key):
            values[key] = os.environ[key]

    return values


def get(key: str, default: str = "") -> str:
    return load().get(key, default) or default


def require(key: str) -> str:
    """Fetch a value, or fail with a message that says how to fix it."""
    value = get(key)
    if not value:
        raise SystemExit(
            f"{key} is not set.\n"
            f"Add it to {ENV_PATH} (copy .env.example if it is missing)."
        )
    return value


def update(**pairs: str) -> None:
    """Write values into .env, replacing existing keys and keeping comments."""
    lines = (
        ENV_PATH.read_text(encoding="utf-8").splitlines()
        if ENV_PATH.exists()
        else []
    )

    remaining = dict(pairs)
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)

    for key, value in remaining.items():
        out.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
