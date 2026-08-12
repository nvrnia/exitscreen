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

# (frame radius, content padding). The padding has to grow with the radius or the
# corner curve eats into the margin diagonally and the date looks crowded again -
# measured at ~17px of clearance, which is what 36/24 gives.
PAIRS = [(36, 24), (48, 27), (60, 30), (72, 34)]

ZOOM = 3
CROP = (0, 0, 150, 130)  # the top-left corner, where both curves meet


def render(frame_radius: int, pad: int, art=None) -> Image.Image:
    """Render at a radius and padding, restoring the theme afterwards.

    Padding ripples through CONTENT_LEFT/RIGHT, the art box and the columns, so
    all of those are recomputed and put back.
    """
    saved = {name: getattr(theme, name) for name in (
        "FRAME_RADIUS", "FRAME_PAD", "CONTENT_LEFT", "CONTENT_RIGHT", "MARGIN_X",
        "ART_LEFT", "ART_RIGHT", "ART_W", "COL_EDGES")}
    try:
        theme.FRAME_RADIUS = frame_radius
        theme.FRAME_PAD = pad
        theme.CONTENT_LEFT = theme.FRAME_LEFT + pad
        theme.CONTENT_RIGHT = theme.FRAME_RIGHT - pad
        theme.MARGIN_X = theme.CONTENT_LEFT
        theme.ART_LEFT = theme.CONTENT_LEFT
        theme.ART_RIGHT = theme.CONTENT_RIGHT
        theme.ART_W = theme.ART_RIGHT - theme.ART_LEFT
        theme.COL_EDGES = theme._col_edges()
        return eink.reduce(
            frame.build_frame(frame.sample_data(), art=art), "grey16"
        )
    finally:
        for name, value in saved.items():
            setattr(theme, name, value)


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

    for i, (radius, pad) in enumerate(PAIRS):
        crop = render(radius, pad).crop(CROP).resize((w, h), Image.NEAREST)
        sheet.paste(crop, (i * w, 0))
        label = f"radius {radius} / pad {pad}"
        d.text((i * w + 8, h + 8), label, font=label_font, fill=theme.BLACK)
        print(f"  {label}")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "corners.png"
    sheet.save(path)
    return path


def frames() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    art = real_art()
    print("  using today's artwork" if art is not None else "  using placeholder")
    for radius, pad in PAIRS:
        path = OUT / f"corner_r{radius}.png"
        render(radius, pad, art=art).save(path)
        print(f"  radius {radius:>2}  pad {pad}  ->  {path.name}")
    return OUT


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", action="store_true", help="whole frames instead")
    args = ap.parse_args()
    print("wrote", frames() if args.frames else corners())


if __name__ == "__main__":
    main()
