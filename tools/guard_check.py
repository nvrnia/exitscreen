"""Why did the panel refresh? Diff the frame's inputs between two runs.

    py tools/guard_check.py           snapshot now, and diff against last time
    py tools/guard_check.py --reset   forget the previous snapshot

Run it twice a few minutes apart. It reports the frame digest and, when the
digest changes, **exactly which field changed** - so a refresh is either
explained by real data moving or exposed as non-determinism.

This exists because the push guard has been wrong twice. The first time the
footer stamp came from now() instead of cache age, so every run differed and the
panel refreshed every five minutes forever. Guessing from the outside cost far
more than measuring would have.

Touches no hardware and never pushes. Safe to run on the Pi beside cron.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from exitscreen import eink, frame  # noqa: E402

SNAPSHOT = ROOT / "cache" / "guard_snapshot.json"


def snapshot() -> dict:
    """Every input the frame draws, flattened to comparable scalars."""
    import run  # the production gather, so this measures what cron measures

    data = run.gather()
    art_image, data.artwork = run.gather_art()
    img = eink.reduce(frame.build_frame(data, art=art_image), run.REDUCTION)

    fields = {
        "digest": eink.frame_digest(img),
        "day": str(data.day),
        "footer_stamp": data.fetched_at.strftime("%H:%M") if data.fetched_at else None,
        "artwork": data.artwork.label if data.artwork else None,
        "todo_total": data.todo_total,
    }

    for i, d in enumerate(data.departures):
        fields[f"metro_{i}"] = f"{d.clock} {d.line} -> {d.destination}"
    for i, t in enumerate(data.todos):
        fields[f"todo_{i}"] = f"{t.title} | at={t.at} | note={t.note}"

    w = data.weather
    if w:
        fields["weather"] = (
            f"{round(w.temp_c) if w.temp_c is not None else None}C "
            f"wmo={w.wmo} max={round(w.temp_max_c) if w.temp_max_c else None} "
            f"umbrella={w.umbrella} bft={w.beaufort} blustery={w.blustery} "
            f"rain={w.rain_hours} first={w.first_rain_at}"
        )

    return fields


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true", help="forget the last snapshot")
    args = ap.parse_args()

    if args.reset:
        SNAPSHOT.unlink(missing_ok=True)
        print("snapshot cleared")
        return

    now = snapshot()
    previous = None
    if SNAPSHOT.exists():
        try:
            previous = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(now, indent=1), encoding="utf-8")

    print(f"\ndigest {now['digest']}")

    if previous is None:
        print("no previous snapshot - run again in a few minutes to compare")
        return

    if previous["digest"] == now["digest"]:
        print(f"UNCHANGED since last run - the guard would skip. Good.")
        return

    print(f"CHANGED from {previous['digest']}\n")
    keys = sorted(set(previous) | set(now))
    changed = [k for k in keys if k != "digest" and previous.get(k) != now.get(k)]

    if not changed:
        print("  *** NOTHING in the inputs changed, but the pixels did. ***")
        print("  That is real non-determinism - a font, a rounding, or drawing")
        print("  order. Not explainable by the data.")
        return

    for k in changed:
        print(f"  {k}")
        print(f"      was: {previous.get(k)}")
        print(f"      now: {now.get(k)}")

    print("\nVerdict: the refresh IS explained by the data above changing."
          if changed else "")


if __name__ == "__main__":
    main()
