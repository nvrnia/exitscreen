"""The panel adapter - the only module that imports IT8951.

Everything else in the package is pure Pillow and runs anywhere. Keeping the
hardware behind this one module is what lets the whole layout be developed and
previewed on a laptop where the driver cannot even be installed.

Import is deliberately deferred into __init__ rather than at module scope, so
this file can be imported on a machine without the driver (to read VCOM, or for
a --dry-run) without exploding.
"""

from __future__ import annotations

import time

from PIL import Image

# Printed on the panel's ribbon cable. A wrong value degrades the display, so it
# is a constant here rather than something a caller can forget to pass.
VCOM = -1.81

# Full 16-grey refresh. Affordable on every push because the guard in run.py
# means we only push when the image actually changed - see BACKLOG.md.
DEFAULT_MODE = "GC16"


class Panel:
    """A connected e-paper panel."""

    def __init__(self, vcom: float = VCOM, rotate=None, spi_hz: int | None = None):
        from IT8951 import constants
        from IT8951.display import AutoEPDDisplay

        self._constants = constants
        kwargs = {"vcom": vcom, "rotate": rotate}
        if spi_hz is not None:
            kwargs["spi_hz"] = spi_hz
        self._display = AutoEPDDisplay(**kwargs)

    @property
    def size(self) -> tuple[int, int]:
        return self._display.width, self._display.height

    def clear(self) -> float:
        """White the panel. Returns seconds taken."""
        started = time.time()
        self._display.clear()
        return time.time() - started

    def show(self, img: Image.Image, mode: str = DEFAULT_MODE) -> float:
        """Paste an image and draw it. Returns seconds taken.

        The image is expected to already match the panel size and be mode 'L' -
        eink.reduce() produces exactly that. Anything else is coerced here rather
        than silently drawn wrong.
        """
        if img.mode != "L":
            img = img.convert("L")
        if img.size != self.size:
            img = img.resize(self.size, Image.LANCZOS)

        waveform = getattr(self._constants.DisplayModes, mode)
        self._display.frame_buf.paste(img, (0, 0))

        started = time.time()
        self._display.draw_full(waveform)
        return time.time() - started
