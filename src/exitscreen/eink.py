"""Reduce a rendered frame to what the panel can physically display.

A mode-'L' image has 256 grey levels; the ED097TC2 has 16. Anything we don't
reduce ourselves gets reduced by the driver, silently and with no say in how.
Doing it here means the laptop preview shows the real output, and lets us
compare the two candidate reductions:

  grey16  - 16 levels, no dithering. Smooth for tonal art, and the natural
            partner to the IT8951's GC16 full-quality waveform.
  bw      - 1 bit with Floyd-Steinberg dithering. Crisper thin lines, at the
            cost of texture in flat areas; pairs with the faster DU/A2 modes.

The spec calls for testing both on real hardware, so both stay available.
Neither function imports IT8951, so this module runs fine on the laptop.
"""

from __future__ import annotations

import hashlib

from PIL import Image

LEVELS = 16
STEP = 255 / (LEVELS - 1)  # 17.0

# Nearest-of-16 lookup, applied per pixel.
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

    The runner renders every 5 minutes but the metro feed is only polled every
    10, so roughly half of all renders produce a byte-identical frame. Comparing
    this digest against the last pushed one means the panel only flashes when
    something actually changed - no wasted 1-3 second refresh, and a delayed
    train still appears sooner than a fixed 10-minute cycle would allow.

    Digest the *reduced* image, not the source: two frames that differ only in
    tones the panel cannot show are the same frame as far as the panel cares.

    This must be computed on a frame whose "updated" stamp came from the data's
    fetch time rather than from now(). A stamp rendered from the clock changes
    every render, so the digest would never match and the guard would do nothing.
    """
    if img.mode != "L":
        img = img.convert("L")
    return hashlib.sha256(img.tobytes()).hexdigest()[:16]
