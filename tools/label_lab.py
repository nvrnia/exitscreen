"""Compare treatments for the panel's furniture - the letterspaced caps.

    py tools/label_lab.py            sample data
    py tools/label_lab.py --live     real data

The column headings, the date and the nameplate all share one treatment. Small,
light, grey caps in a condensed serif look weedy next to a 76px black numeral;
this tool renders alternatives so the fix is chosen by looking.

Writes one full frame per variant plus out/label_compare.png, which crops the
top bar, the row labels and the footer - the three places furniture appears.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from exitscreen import eink, frame, theme as T  # noqa: E402

OUT = ROOT / "out"

# Everything is held constant except the one variable being judged, so a change
# in the render can only be caused by that variable. Changing weight, tracking
# and size together made it impossible to tell which had overshot.
BASE = {
    "FURNITURE_INK": 0,
    "TOPBAR_TRACKING": 7.0,
    "LABEL_TRACKING": 7.0,
    "NAMEPLATE_TRACKING": 6.0,
    "TOPBAR_SIZE": 24,
    "LABEL_SIZE": 22,
    "NAMEPLATE_SIZE": 21,
}

DEFAULT_WEIGHTS = [700, 725, 750, 775]

# The three strips where furniture appears, as (label, y0, y1).
STRIPS = [
    ("top bar", 18, 58),
    ("column headings", 540, 580),
    ("footer", 766, 806),
]


def render(overrides, data):
    saved = {k: getattr(T, k) for k in overrides}
    try:
        for key, value in overrides.items():
            setattr(T, key, value)
        return eink.reduce(frame.build_frame(data), "grey16")
    finally:
        for key, value in saved.items():
            setattr(T, key, value)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--weights", nargs="*", type=int, default=DEFAULT_WEIGHTS,
                    help="Literata weight values to ladder (axis runs 200-900)")
    ap.add_argument("--tracking", type=float, default=None,
                    help="override tracking for every variant")
    args = ap.parse_args()

    variants = []
    for w in args.weights:
        overrides = dict(BASE, FURNITURE_WEIGHT=w)
        note = f"weight {w}"
        if args.tracking is not None:
            overrides.update(TOPBAR_TRACKING=args.tracking,
                             LABEL_TRACKING=args.tracking,
                             NAMEPLATE_TRACKING=args.tracking)
            note += f", tracking {args.tracking}"
        variants.append((str(w), note, overrides))

    if args.live:
        sys.path.insert(0, str(ROOT / "tools"))
        from preview import build_data

        data = build_data(live=True)
    else:
        data = frame.sample_data()

    OUT.mkdir(parents=True, exist_ok=True)

    strip_h = sum(y1 - y0 for _, y0, y1 in STRIPS)
    block_h = strip_h + 34
    sheet = Image.new("L", (T.WIDTH, block_h * len(variants)), T.PAPER)
    sd = ImageDraw.Draw(sheet)
    caption = T.load("WorkSans[wght].ttf", 18, weight=500)

    for i, (key, description, overrides) in enumerate(variants):
        img = render(overrides, data)
        img.save(OUT / f"label_{key}.png")
        print(f"  {key}  {description}")

        top = i * block_h
        sd.text((T.CONTENT_LEFT, top + 7), f"{key} · {description}",
                font=caption, fill=T.MUTED)
        sd.line([(T.CONTENT_LEFT, top + 30), (T.CONTENT_RIGHT, top + 30)],
                fill=T.DIVIDER, width=1)

        y = top + 34
        for _, y0, y1 in STRIPS:
            sheet.paste(img.crop((0, y0, T.WIDTH, y1)), (0, y))
            y += y1 - y0

    path = OUT / "label_compare.png"
    sheet.save(path)
    print(f"\ncomparison -> {path}")


if __name__ == "__main__":
    main()
