"""Compare corner radii, since this is a decision for the eye not the spec.

    py tools/corner_lab.py            zoomed top-left corners, side by side
    py tools/corner_lab.py --frames   whole frames at each radius

Writes to out/corners.png. Pick a pair, put them in theme.py as FRAME_RADIUS
and ART_RADIUS, and press R in the preview viewer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from exitscreen import eink, frame, theme  # noqa: E402

OUT = ROOT / "out"

# (frame radius, art radius). 0/0 is what it looked like before.
PAIRS = [(0, 0), (10, 7), (18, 12), (26, 18), (36, 24)]

ZOOM = 3
CROP = (0, 0, 150, 130)  # the top-left corner, where both curves meet


def render(frame_radius: int, art_radius: int, art=None) -> Image.Image:
    frame_before, art_before = theme.FRAME_RADIUS, theme.ART_RADIUS
    theme.FRAME_RADIUS, theme.ART_RADIUS = frame_radius, art_radius
    try:
        return eink.reduce(
            frame.build_frame(frame.sample_data(), art=art), "grey16"
        )
    finally:
        theme.FRAME_RADIUS, theme.ART_RADIUS = frame_before, art_before


def real_art():
    """Today's painting, so the masked corners are judged on a real image."""
    from exitscreen import art as art_module

    image, _ = art_module.daily(theme.ART_W, theme.ART_H)
    return image


def corners() -> Path:
    label_font = theme.load(theme.SUB_FACE, 13, weight=500)
    w = (CROP[2] - CROP[0]) * ZOOM
    h = (CROP[3] - CROP[1]) * ZOOM

    sheet = Image.new("L", (w * len(PAIRS), h + 30), theme.PAPER)
    d = ImageDraw.Draw(sheet)

    for i, (fr, ar) in enumerate(PAIRS):
        crop = render(fr, ar).crop(CROP).resize((w, h), Image.NEAREST)
        sheet.paste(crop, (i * w, 0))
        label = "square (before)" if fr == 0 else f"frame {fr} / art {ar}"
        d.text((i * w + 8, h + 8), label, font=label_font, fill=theme.BLACK)
        print(f"  frame {fr:>2} / art {ar:>2}   {label}")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "corners.png"
    sheet.save(path)
    return path


def frames() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    art = real_art()
    print("  using today's artwork" if art is not None else "  using placeholder")
    for fr, ar in PAIRS:
        path = OUT / f"corner_{fr}_{ar}.png"
        render(fr, ar, art=art).save(path)
        print(f"  wrote {path.name}")
    return OUT


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", action="store_true", help="whole frames instead")
    args = ap.parse_args()
    print("wrote", frames() if args.frames else corners())


if __name__ == "__main__":
    main()
