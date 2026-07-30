"""The daily art panel: a fallback chain in front of museum.py.

This module owns the *policy* - what to show when the ideal is unavailable -
while museum.py owns fetching. daily() walks today's artwork, then yesterday's
cached one, then a grey placeholder, so a front-door panel is never blank.
"""

from __future__ import annotations

from datetime import date, timedelta

from PIL import Image, ImageDraw

from . import theme as T

BOX_FILL = 221  # grey, snapped to a panel level (13 x 17)
BOX_LABEL = "INSERT ART HERE"


def daily(width: int, height: int, day: date | None = None):
    """(image, Artwork|None), falling back until something is showable.

    today's artwork -> yesterday's cached one -> the grey placeholder. The panel
    is by a front door and must always show something: a museum having a bad
    night costs you a different picture, never a blank rectangle.
    """
    from . import museum

    day = day or date.today()

    for attempt in (day, day - timedelta(days=1)):
        try:
            image, artwork = museum.daily((width, height), day=attempt)
            if image is not None:
                return image, artwork
        except Exception:
            continue  # yesterday's is already on disk and needs no network

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
