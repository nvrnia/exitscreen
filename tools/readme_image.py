"""Render the README's hero image from sample data.

    py tools/readme_image.py        -> docs/panel.png

Deliberately NOT a photo of the real panel. A screenshot of the live screen
shows real departures, real destinations and a real to-do list, which between
them narrow down where the author lives. Sample data says the same thing about
the design without saying anything about the person.

The artwork is fetched for real, because it is public domain and it is the
part of the layout a still image most needs to show.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from exitscreen import art, eink, frame, theme  # noqa: E402
from exitscreen.models import Departure  # noqa: E402

OUT = ROOT / "docs" / "panel.png"


def main() -> None:
    data = frame.sample_data()

    # Shorter than the defaults so the destination beside the hero time does not
    # ellipsise. The layout tools want the long ones - they are testing the
    # truncation. A hero image is not the place to demonstrate it.
    data.departures = [
        Departure(data.departures[0].when, "D", "the centre"),
        Departure(data.departures[1].when, "E", "the far terminus"),
    ]

    image, artwork = art.daily(theme.ART_W, theme.ART_H)
    if artwork:
        data.artwork = artwork
        print(f"  artwork: {artwork.label}")
    else:
        print("  no artwork available - rendering the placeholder block")

    img = eink.reduce(frame.build_frame(data, art=image), "grey16")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"  wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
