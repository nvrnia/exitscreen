"""Render every weather icon state at once, through the real frame code.

    py tools/icon_sheet.py            all nine states -> out/icon_sheet.png
    py tools/icon_sheet.py --browse   dump the font's whole glyph catalogue

Useful because the weather only ever shows you one icon at a time. This drives
the same build_frame() path the panel uses, so what you see here is what the
display would do - not an approximation.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from exitscreen import eink, frame, icons, theme  # noqa: E402
from exitscreen.models import Departure, FrameData, Task, Weather  # noqa: E402

OUT = ROOT / "out"

# A plausible rain forecast, for the cases that should show the bar chart. The
# weather column has two layouts, not one - bars when rain is expected today and
# an icon alone when it is not - so the sheet has to cover both or it is only
# testing half of what the panel does.
WET = [10, 25, 60, 85, 45, 20, 10, 5]

# One representative WMO code per icon, plus the states that change the layout
# rather than just the glyph.
CASES = [
    (0, False, None, "clear"),
    (2, False, None, "partly"),
    (3, False, None, "cloud"),
    (45, False, None, "fog"),
    (63, True, WET, "rain + bars"),
    (75, False, WET, "snow + bars"),
    (81, True, WET, "showers + bars"),
    (95, True, WET, "storm + bars"),
    (0, True, None, "umbrella, no bars"),
]

COLS = 3


def sheet() -> Path:
    """Crop the weather column out of a real frame, once per icon state.

    The crop is the decision row - DECISION_TOP..FOOTER_TOP - which is where the
    three columns live in the four-band layout.
    """
    x0, x1 = theme.COL_EDGES[1], theme.COL_EDGES[2]
    top, bottom = theme.DECISION_TOP, theme.FOOTER_TOP
    w, h = x1 - x0, bottom - top
    rows = (len(CASES) + COLS - 1) // COLS

    label_font = theme.load(theme.SUB_FACE, 16, weight=500)
    canvas = Image.new("L", (w * COLS, (h + 26) * rows), theme.PAPER)
    d = ImageDraw.Draw(canvas)

    for i, (code, umbrella, rain, label) in enumerate(CASES):
        data = FrameData(
            fetched_at=datetime(2026, 7, 30, 8, 4),
            departures=[
                Departure(datetime(2026, 7, 30, 8, 14), "E", "the far terminus")
            ],
            weather=Weather(
                temp_c=7.4,
                temp_max_c=11.2,
                wmo=code,
                wind_kmh=18,
                gust_kmh=34,
                beaufort=3,
                umbrella=umbrella,
                rain_hours=rain or [],
                first_rain_at="15:00" if rain else None,
            ),
            todos=[Task("sample")],
        )
        img = eink.reduce(frame.build_frame(data), "grey16")
        col = img.crop((x0, top, x1, bottom))

        cx, cy = (i % COLS) * w, (i // COLS) * (h + 26)
        canvas.paste(col, (cx, cy))
        d.text(
            (cx + 12, cy + h + 4),
            f"wmo {code}{'  +umbrella' if umbrella else ''}  ->  {label}",
            font=label_font,
            fill=theme.MUTED,
        )
        print(f"  wmo {code:>3}  umbrella={str(umbrella):<5}  "
              f"bars={str(bool(rain)):<5}  {label}")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "icon_sheet.png"
    canvas.save(path)
    return path


def browse(size: int = 48, per_row: int = 16) -> Path:
    """Every glyph in the bundled font, so you can pick different ones.

    Weather Icons puts its glyphs in the Private Use Area. This walks that
    range and draws whatever exists, with its codepoint underneath.
    """
    font = theme.load(icons.WEATHER_FONT, size)
    label_font = theme.load(theme.SUB_FACE, 11, weight=400)

    found = []
    for cp in range(0xF000, 0xF0FF + 1):
        bbox = font.getbbox(chr(cp))
        if bbox and (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0:
            found.append(cp)

    cell_w, cell_h = size + 26, size + 34
    rows = (len(found) + per_row - 1) // per_row
    canvas = Image.new("L", (cell_w * per_row, cell_h * rows), theme.PAPER)
    d = ImageDraw.Draw(canvas)

    for i, cp in enumerate(found):
        cx = (i % per_row) * cell_w + cell_w // 2
        cy = (i // per_row) * cell_h + size // 2 + 8
        d.text((cx, cy), chr(cp), font=font, fill=theme.BLACK, anchor="mm")
        d.text((cx, cy + size // 2 + 12), f"{cp:04x}", font=label_font,
               fill=theme.MUTED, anchor="mm")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "icon_catalogue.png"
    canvas.save(path)
    print(f"  {len(found)} glyphs in U+F000..U+F0FF")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--browse", action="store_true",
                    help="dump the font's glyph catalogue instead")
    args = ap.parse_args()

    path = browse() if args.browse else sheet()
    print("wrote", path)


if __name__ == "__main__":
    main()
