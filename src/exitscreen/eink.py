"""Reduce a rendered frame to what the panel can physically display.

A mode-'L' image has 256 grey levels, the ED097TC2 has 16. Anything we do not
reduce ourselves gets reduced by the driver, silently and with no say in how.
Doing it here means the laptop preview shows the real output, and lets us
compare the two candidates:

  grey16  16 levels, no dithering. Smooth for tonal art, and the natural partner
          to the IT8951's GC16 waveform.
  bw      1 bit with Floyd-Steinberg dithering. Crisper thin lines, at the cost
          of texture in flat areas. Pairs with the faster DU and A2 modes.

Both stay available so they can be compared on real glass. Nothing here imports
IT8951, so it runs fine on the laptop.
"""

from __future__ import annotations

import hashlib

from PIL import Image

LEVELS = 16
STEP = 255 / (LEVELS - 1)  # 17.0

_GREY16_LUT = [round(round(v / STEP) * STEP) for v in range(256)]

MODES = ("grey16", "bw", "bw-flat")


def to_grey16(img: Image.Image) -> Image.Image:
    """Snap to the panel's 16 grey levels. Returns mode 'L'."""
    if img.mode != "L":
        img = img.convert("L")
    return img.point(_GREY16_LUT)


def to_bilevel(img: Image.Image, dither: bool = True) -> Image.Image:
    """Reduce to pure black and white. Returns mode '1'."""
    if img.mode != "L":
        img = img.convert("L")
    method = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    return img.convert("1", dither=method)


def reduce(img: Image.Image, mode: str = "grey16") -> Image.Image:
    """Apply one of MODES. Returns mode 'L' so callers can treat results alike."""
    if mode == "grey16":
        return to_grey16(img)
    if mode == "bw":
        return to_bilevel(img, dither=True).convert("L")
    if mode == "bw-flat":
        return to_bilevel(img, dither=False).convert("L")
    raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")


def levels_used(img: Image.Image) -> int:
    """How many distinct greys survive. A sanity check that reduction worked."""
    if img.mode != "L":
        img = img.convert("L")
    return sum(1 for count in img.histogram() if count)


def frame_digest(img: Image.Image) -> str:
    """A stable fingerprint of the reduced frame, for the push guard.

    Comparing this against the last pushed digest means the panel only flashes
    when something actually changed, and a delayed train still shows up sooner
    than a fixed cycle would allow.

    Two things it is easy to get wrong:

    Digest the reduced image, not the source. Two frames that differ only in
    tones the panel cannot show are the same frame as far as the panel cares.

    The frame's "updated" stamp has to come from the data's fetch time, not from
    now(). A stamp read off the clock changes every render, so the digest would
    never match and the guard would do nothing.

    It rarely gets to skip during service hours, because trains run every 3-4
    minutes and parse() recomputes against now, so the displayed pair rolls over
    about as often as we render. Still worth having: it is what stops a static
    frame being redrawn, which is most of the night and any quiet stretch.
    """
    if img.mode != "L":
        img = img.convert("L")
    return hashlib.sha256(img.tobytes()).hexdigest()[:16]
