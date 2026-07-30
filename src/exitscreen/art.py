"""The daily art panel: a fallback chain in front of museum.py.

This module owns the *policy* - what to show when the ideal is unavailable -
while museum.py owns fetching. daily() walks today's artwork, then yesterday's
cached one, then a grey placeholder, so a front-door panel is never blank.

placeholder() is deliberately plain. It is the floor of that chain, not a
decorative fallback: if it is on the wall, something is wrong, and it should look
like a gap rather than like a choice.
"""

from __future__ import annotations

from datetime import date, timedelta

from PIL import Image, ImageDraw

from . import theme as T

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

    Extra keyword arguments are accepted and ignored so callers need not care
    which placeholder is in use.
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
