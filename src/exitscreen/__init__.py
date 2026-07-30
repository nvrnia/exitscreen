"""exitscreen - an e-ink "what to know before I leave" display for the front door.

Panel: Waveshare 9.7" e-Paper HAT, ED097TC2 / IT8951, 1200x825, mono with
16 grey levels, VCOM -1.81.

The renderer is pure Pillow: build_frame() returns a mode-"L" PIL Image and
imports nothing platform-specific. Pushing that image to the panel lives in a
separate adapter that only ever runs on the Pi, so layout work happens on the
laptop without the hardware attached.
"""
