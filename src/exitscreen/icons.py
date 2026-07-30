"""Icons for the decision row.

Weather comes from the bundled **Weather Icons** font (SIL OFL 1.1,
erikflowers/weather-icons). Its glyphs live in the Private Use Area, so we map
codepoints explicitly rather than typing characters.

Bundling a font here is safe in a way that relying on a *general* typeface is
not: the risk with an arbitrary font is that it lacks the glyph and silently
renders an empty box. This font is shipped with the project and its glyphs are
verified, so that failure mode does not exist.

The arrow and checkbox stay hand-drawn - the wind arrow has to rotate to an
arbitrary bearing, which a fixed glyph cannot do.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .theme import BLACK, MUTED, load

WEATHER_FONT = "weathericons-regular-webfont.ttf"

# Codepoints parsed from the project's own weather-icons.css.
GLYPHS = {
    "clear": 0xF00D,  # wi-day-sunny
    "partly": 0xF002,  # wi-day-cloudy
    "cloud": 0xF013,  # wi-cloudy
    "fog": 0xF014,  # wi-fog
    "rain": 0xF019,  # wi-rain
    "snow": 0xF01B,  # wi-snow
    "showers": 0xF01A,  # wi-showers
    "storm": 0xF01E,  # wi-thunderstorm
    "umbrella": 0xF084,  # wi-umbrella
}

# WMO codes as Open-Meteo documents them.
_WMO = [
    ({0}, "clear"),
    ({1, 2}, "partly"),
    ({3}, "cloud"),
    ({45, 48}, "fog"),
    ({51, 53, 55, 56, 57, 61, 63, 65, 66, 67}, "rain"),
    ({71, 73, 75, 77, 85, 86}, "snow"),
    ({80, 81, 82}, "showers"),
    ({95, 96, 99}, "storm"),
]


def weather_name(code: int, umbrella_weather: bool = False) -> str:
    """Which icon a WMO code should use.

    umbrella_weather wins outright: the panel answers "what do I take with
    me", so an upcoming soaking outranks a currently dry sky.
    """
    if umbrella_weather:
        return "umbrella"
    for codes, name in _WMO:
        if code in codes:
            return name
    return "cloud"


def draw_weather(d, x, y, size, code, umbrella_weather=False, fill=BLACK):
    """Draw the weather icon centred in a size x size box at (x, y)."""
    name = weather_name(code, umbrella_weather)
    font = load(WEATHER_FONT, size)
    d.text(
        (x + size / 2, y + size / 2),
        chr(GLYPHS[name]),
        font=font,
        fill=fill,
        anchor="mm",
    )


# --- hand-drawn marks ----------------------------------------------------


def arrow(d, x, y, length=18, bearing=90, fill=MUTED, w=2):
    """Arrow of `length` pointing along `bearing` degrees (0 = up, 90 = right).

    The head is a filled triangle rather than two strokes. Pillow does not join
    line ends, so at width 2 the shaft and both head strokes each ended in their
    own square cap and visibly failed to meet at the tip - the head looked
    detached from the body. A polygon has no join to get wrong.
    """
    a = math.radians(bearing - 90)
    dx, dy = math.cos(a), math.sin(a)
    tip_x, tip_y = x + dx * length, y + dy * length

    head = max(7.0, length * 0.55)
    # Stop the shaft inside the head so no square cap pokes out of the sides.
    d.line(
        [(x, y), (tip_x - dx * head * 0.8, tip_y - dy * head * 0.8)],
        fill=fill,
        width=w,
    )

    px, py = -dy, dx  # perpendicular to the shaft
    half = head * 0.36
    d.polygon(
        [
            (tip_x, tip_y),
            (tip_x - dx * head + px * half, tip_y - dy * head + py * half),
            (tip_x - dx * head - px * half, tip_y - dy * head - py * half),
        ],
        fill=fill,
    )


def checkbox(d, x, y, size=18, fill=BLACK, w=2):
    d.rectangle([x, y, x + size, y + size], outline=fill, width=w)


def bullet(img, cx, cy, r=10, fill=BLACK, w=2.5, ss=4):
    """An open circle, used as the task-list bullet.

    Drawn rather than typed for the same reason as the other symbols, and because
    an outlined circle reads as an unticked box without the hard edges of one.

    Rendered at ss times the size and downsampled, because Pillow strokes only at
    integer widths - so a step from 3 to 2 is a 33% change, far more than the
    small adjustment wanted. Supersampling gives fractional weights like 2.5, and
    the antialiasing it produces is free on a 16-grey panel.

    Takes the image rather than a draw handle, since it composites a tile.
    """
    pad = 3
    side = int((r + w + pad) * 2)
    big = side * ss

    tile = Image.new("L", (big, big), 0)
    td = ImageDraw.Draw(tile)
    centre = big / 2
    rr = r * ss
    td.ellipse(
        [centre - rr, centre - rr, centre + rr, centre + rr],
        outline=255,
        width=max(1, round(w * ss)),
    )

    mask = tile.resize((side, side), Image.LANCZOS)
    ink = Image.new("L", (side, side), fill)
    img.paste(ink, (int(cx - side / 2), int(cy - side / 2)), mask)
