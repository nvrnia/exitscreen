"""Push a PNG to the e-paper panel. Pi only.

    python tools/first_light.py out/frame_grey16.png
    python tools/first_light.py out/frame_grey16.png --clear-only
    python tools/first_light.py out/frame_grey16.png --mode DU

Deliberately standalone: it imports nothing from the exitscreen package, only
Pillow and the driver. If this works, the hardware and driver are good, and any
later failure is our code. If it fails, our code was never involved.

VCOM is the panel's calibration voltage and is printed on the ribbon cable.
A wrong value degrades the display, so it is required rather than defaulted
silently - the value for this panel is -1.81.
"""

from __future__ import annotations

import argparse
import sys
import time

from PIL import Image

VCOM = -1.81


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", nargs="?", help="PNG to display")
    ap.add_argument("--vcom", type=float, default=VCOM)
    ap.add_argument("--mode", default="GC16",
                    help="GC16 (full, 16 grey) or DU (fast, 1-bit)")
    ap.add_argument("--clear-only", action="store_true",
                    help="white the panel and stop")
    ap.add_argument("--no-clear", action="store_true",
                    help="skip the clear before drawing")
    ap.add_argument("--rotate", default=None,
                    help="None, CW, CCW or flip, if the image lands sideways")
    args = ap.parse_args()

    from IT8951 import constants
    from IT8951.display import AutoEPDDisplay

    print(f"initialising panel at VCOM {args.vcom} ...")
    started = time.time()
    display = AutoEPDDisplay(vcom=args.vcom, rotate=args.rotate)
    print(f"  ready in {time.time() - started:.1f}s")
    print(f"  panel reports {display.width} x {display.height}")

    if not args.no_clear or args.clear_only:
        print("clearing to white ...")
        started = time.time()
        display.clear()
        print(f"  cleared in {time.time() - started:.1f}s")

    if args.clear_only:
        return

    if not args.image:
        sys.exit("no image given (use --clear-only to just white the panel)")

    img = Image.open(args.image)
    print(f"loaded {args.image}: {img.size} {img.mode}")

    if img.mode != "L":
        img = img.convert("L")
        print("  converted to L")

    if img.size != (display.width, display.height):
        print(f"  WARNING: image is {img.size}, panel is "
              f"{(display.width, display.height)}")
        print("  pasting at (0, 0) without scaling - expect it cropped or inset")

    try:
        mode = getattr(constants.DisplayModes, args.mode)
    except AttributeError:
        sys.exit(f"unknown mode {args.mode!r}. Available: "
                 f"{[m for m in dir(constants.DisplayModes) if not m.startswith('_')]}")

    display.frame_buf.paste(img, (0, 0))

    print(f"drawing with {args.mode} ...")
    started = time.time()
    display.draw_full(mode)
    elapsed = time.time() - started
    print(f"  drawn in {elapsed:.1f}s")
    print("\ndone - look at the panel.")


if __name__ == "__main__":
    main()
