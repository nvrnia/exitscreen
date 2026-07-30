"""Measure the real gaps in a rendered frame, instead of eyeballing them.

    py tools/spacing_audit.py           sample data
    py tools/spacing_audit.py --live    real data

Scans the rendered image for bands of ink and reports the whitespace between
them, per region. Eyeballing a screenshot at 100% zoom is how spacing drifts;
this puts numbers on it, so "too close together" becomes checkable.

Ink is any pixel darker than INK_THRESHOLD, which ignores the art box's light
grey fill but catches all text and rules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from exitscreen import eink, frame, theme as T  # noqa: E402

INK_THRESHOLD = 200
MIN_BAND = 1  # 1px hairline rules matter here


def ink_bands(img, box):
    """Vertical bands containing ink within box=(x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    px = img.load()

    rows = []
    for y in range(y0, y1):
        has_ink = False
        for x in range(x0, x1):
            if px[x, y] < INK_THRESHOLD:
                has_ink = True
                break
        rows.append(has_ink)

    bands = []
    start = None
    for i, has_ink in enumerate(rows):
        if has_ink and start is None:
            start = i
        elif not has_ink and start is not None:
            if i - start >= MIN_BAND:
                bands.append((y0 + start, y0 + i - 1))
            start = None
    if start is not None and len(rows) - start >= MIN_BAND:
        bands.append((y0 + start, y1 - 1))
    return bands


def report(img, name, box, labels=None):
    bands = ink_bands(img, box)
    print(f"\n{name}  (x {box[0]}..{box[2]})")
    if not bands:
        print("   no ink")
        return

    for i, (top, bottom) in enumerate(bands):
        tag = ""
        if labels and i < len(labels):
            tag = f"  {labels[i]}"
        print(f"   band {i + 1}: y {top}..{bottom}  ({bottom - top + 1}px tall){tag}")
        if i + 1 < len(bands):
            gap = bands[i + 1][0] - bottom - 1
            flag = ""
            if gap < 8:
                flag = "   <-- tight"
            elif gap > 40:
                flag = "   <-- loose"
            print(f"        gap {gap}px{flag}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    if args.live:
        sys.path.insert(0, str(ROOT / "tools"))
        from preview import build_data

        data = build_data(live=True)
    else:
        data = frame.sample_data()

    img = eink.reduce(frame.build_frame(data), "grey16")

    print("=" * 62)
    print("SPACING AUDIT — gaps are whitespace between bands of ink")
    print("=" * 62)

    # Bands down the whole panel, measured across the full content width.
    # A narrow strip down the left edge of the content: catches the bands
    # without merging the three columns into one, which a full-width scan does.
    report(img, "left edge, top to bottom",
           (T.CONTENT_LEFT, T.FRAME_TOP + 2, T.CONTENT_LEFT + 260, T.FRAME_BOTTOM))

    row = (T.DECISION_TOP + 2, T.FOOTER_TOP - 2)
    for index, name in enumerate(["METRO column", "WEATHER column", "TODO column"]):
        left, right = T.column(index)
        report(img, name, (left, row[0], right, row[1]))

    print("\n" + "=" * 62)
    print("horizontal margins")
    print("=" * 62)
    px = img.load()

    def first_ink_x(y0, y1):
        # start inside the frame border, or every answer is the frame
        for x in range(T.FRAME_LEFT + 4, T.WIDTH):
            for y in range(y0, y1):
                if px[x, y] < INK_THRESHOLD:
                    return x
        return None

    for label, (y0, y1) in [
        ("date", (T.TOPBAR_TOP + 8, T.TOPBAR_TOP + T.TOPBAR_H)),
        ("METRO label", (T.LABEL_BASE - 20, T.LABEL_BASE + 4)),
        ("clock", (T.HERO_BASE - 56, T.HERO_BASE + 6)),
        ("nameplate", (T.FOOTER_BASE - 18, T.FOOTER_BASE + 6)),
    ]:
        x = first_ink_x(y0, y1)
        note = "" if x == T.CONTENT_LEFT else f"   <-- expected {T.CONTENT_LEFT}"
        print(f"   {label:<14} first ink at x={x}{note}")


if __name__ == "__main__":
    main()
