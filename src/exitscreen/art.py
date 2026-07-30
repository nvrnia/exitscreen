"""The daily art panel.

Block 4 (AI-generated cross-hatch art) is deferred, so this module only provides
stand-ins. placeholder() is a quiet grey box that stays out of the way while the
layout is being worked on; procedural_scene() is a drawn cross-hatch scene, kept
for when it is useful to judge the layout against real tonal weight.

When the art block lands, add fetch_daily() here and keep one of these as the
offline fallback for a failed generation.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

from PIL import Image, ImageDraw

from . import theme as T

# How far up from the bottom the drawn scene fades out, if softening is used.
QUIET_ZONE = 0.86

BOX_FILL = 221  # grey, snapped to a panel level (13 x 17)
BOX_LABEL = "INSERT ART HERE"


def daily(width: int, height: int, day: date | None = None):
    """(image, Artwork|None) for today, with a fallback chain that cannot fail.

        today's artwork  ->  yesterday's cached one  ->  the grey placeholder

    The panel is by a front door; it must always show something. A museum having
    a bad night, or the wifi dropping, costs you a different picture - never a
    blank rectangle.
    """
    from . import museum

    day = day or date.today()

    try:
        image, artwork = museum.daily((width, height), day=day)
        if image is not None:
            return image, artwork
    except Exception:
        pass  # any failure falls through to the cached day below

    # Yesterday's is already on disk and needs no network at all.
    try:
        image, artwork = museum.daily((width, height), day=day - timedelta(days=1))
        if image is not None:
            return image, artwork
    except Exception:
        pass

    return placeholder(width, height), None


def placeholder(width: int, height: int, **_ignored) -> Image.Image:
    """A quiet grey box with a centred label.

    Deliberately unobtrusive: while the layout is being tuned, a detailed scene
    competes for attention with the thing actually being judged. Extra keyword
    arguments are accepted and ignored so callers can pass scene options
    (seed, weight) without caring which placeholder is in use.
    """
    art = Image.new("L", (width, height), BOX_FILL)
    d = ImageDraw.Draw(art)

    font = T.load(T.SUB_FACE, 22, weight=400)
    tracking = 4.0
    label_width = T.tracked_width(d, BOX_LABEL, font, tracking)
    T.draw_tracked(
        d,
        (width / 2 - label_width / 2, height / 2 - 14),
        BOX_LABEL,
        font,
        tracking,
        T.MUTED,
    )
    return art


def procedural_scene(
    width: int,
    height: int,
    seed: int = 3,
    weight: float = 1.0,
    soften: bool = False,
) -> Image.Image:
    """A procedural canal-and-bridge scene in the house cross-hatch style.

    weight scales the tonal density: ~0.7 for a bright clear day, ~1.4 for a grey
    wet one, mirroring how the real daily art is meant to flex.

    soften applies a vignette-to-white edge treatment. It defaults to off because
    the art sits inside a hairline box: a scene dissolving into white just inside
    a crisp border reads as a mistake rather than a choice. Kept for the day the
    art goes full-bleed, where the fade is the point.
    """
    rng = random.Random(seed)
    art = Image.new("L", (width, height), 255)
    d = ImageDraw.Draw(art)

    horizon = int(height * 0.62)

    # sky: long sparse strokes, thickening toward the top
    for y in range(0, horizon, 6):
        density = 1.0 - (y / horizon)
        if rng.random() < (0.25 + density * 0.5) * weight:
            x = rng.randint(-100, width)
            length = rng.randint(200, 700)
            grey = int(150 + rng.random() * 70 - (weight - 1) * 40)
            d.line(
                [(x, y), (x + length, y - rng.randint(0, 6))],
                fill=max(0, min(255, grey)),
                width=1,
            )

    # water: horizontal ripples, darker with depth
    for y in range(horizon, height, 5):
        depth = (y - horizon) / max(1, height - horizon)
        for _ in range(rng.randint(2, 5)):
            x = rng.randint(-50, width)
            length = rng.randint(60, 320)
            grey = int(170 - depth * 90 + rng.random() * 40 - (weight - 1) * 35)
            d.line([(x, y), (x + length, y)], fill=max(0, min(255, grey)), width=1)

    # bridge: deck with an arch springing up beneath it
    bx0, bx1 = int(width * 0.18), int(width * 0.72)
    deck = int(horizon - height * 0.13)
    arch_h = int(height * 0.20)
    d.line([(bx0, deck), (bx1, deck)], fill=40, width=3)
    d.arc([bx0, deck, bx1, deck + arch_h * 2], start=180, end=360, fill=40, width=3)

    # cross-hatch the spandrel: the solid mass between deck and arch
    for x in range(bx0, bx1, 7):
        t = (x - bx0) / max(1, bx1 - bx0)
        drop = max(0.0, arch_h * math.sin(math.pi * t) * 0.55)
        if drop > 4:
            d.line([(x, deck + 2), (x, deck + drop)], fill=120, width=1)
    for x in range(bx0, bx1, 13):
        t = (x - bx0) / max(1, bx1 - bx0)
        drop = max(0.0, arch_h * math.sin(math.pi * t) * 0.5)
        if drop > 6:
            d.line([(x, deck + 2), (x + 10, deck + drop)], fill=140, width=1)

    # parapet hatching above the deck
    for x in range(bx0, bx1, 6):
        d.line([(x, deck - 2), (x - 8, deck - 22)], fill=110, width=1)

    # abutments
    for px in (bx0, bx1):
        d.line([(px, deck), (px, horizon + 26)], fill=60, width=4)

    # reeds in the near corner for foreground depth
    for _ in range(14):
        x = rng.randint(int(width * 0.75), width - 20)
        base = rng.randint(horizon + 20, height - 30)
        h = rng.randint(40, 110)
        d.line([(x, base), (x + rng.randint(-8, 8), base - h)], fill=70, width=2)

    return _soften_edges(art) if soften else art


def _soften_edges(art: Image.Image) -> Image.Image:
    """Vignette the scene out to white, and quiet the bottom of the frame."""
    width, height = art.size
    mask = Image.new("L", (width, height), 0)
    m = ImageDraw.Draw(mask)

    cx, cy = width / 2, height * 0.45
    maxd = math.hypot(cx, cy)
    step = 2
    for y in range(0, height, step):
        for x in range(0, width, 8):
            dist = math.hypot(x - cx, y - cy) / maxd
            fade = max(0.0, min(1.0, (dist - 0.55) / 0.45))
            m.rectangle([x, y, x + 8, y + step], fill=int(fade * 255))

    quiet_from = int(height * QUIET_ZONE)
    for y in range(quiet_from, height):
        t = (y - quiet_from) / max(1, height - quiet_from)
        m.rectangle([0, y, width, y], fill=int(max(0, min(255, t * 255))))

    return Image.composite(Image.new("L", (width, height), 255), art, mask)
