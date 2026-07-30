"""Veto an artwork so it never appears again.

    py tools/art_veto.py                    what is on the panel today
    py tools/art_veto.py --next 12          contact sheet of the works coming up
    py tools/art_veto.py --today            veto today's, pick a replacement
    py tools/art_veto.py 1234 5678          veto by Cleveland object id
    py tools/art_veto.py --list             everything vetoed so far
    py tools/art_veto.py --undo 1234        change your mind

The blacklist lives in assets/, not cache/, so a veto survives reflashing the
SD card. Given that has already happened once, that distinction matters.

Vetoing today's work also clears the day's cached image, so the next run picks
a replacement instead of serving the rejected one from disk.

`--next` is the point of the whole tool: selection is deterministic, so the next
N days can be rendered now and the duds killed before they ever reach the wall.
Reviewing only today's pick means every bad one gets a day on the door first.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from exitscreen import eink, frame, museum, theme  # noqa: E402

# A quarter of the real art box, so a dozen fit on screen at once. Same 2.52:1
# ratio and the same crop, so the composition is what the panel would show.
THUMB = (theme.ART_W // 4, theme.ART_H // 4)
SHEET_COLS = 3
# Three caption lines at 13/11/11px plus breathing room. 46 was too short and the
# third line bled into the thumbnail of the row beneath.
CAPTION_H = 56


def load() -> list[int]:
    if not museum.BLACKLIST.exists():
        return []
    try:
        return [int(i) for i in json.loads(
            museum.BLACKLIST.read_text(encoding="utf-8"))]
    except (ValueError, OSError):
        return []


def save(ids: list[int]) -> None:
    museum.BLACKLIST.parent.mkdir(parents=True, exist_ok=True)
    museum.BLACKLIST.write_text(json.dumps(sorted(set(ids)), indent=1),
                                encoding="utf-8")


def describe(work: dict | None) -> str:
    if not work:
        return "nothing selected"
    artist = work["artist"] or "unknown"
    return f"[{work['id']}] {artist} — {work['title']} ({work['date']})"


def clear_cached_day(day: date) -> None:
    """Drop the day's cached image so a replacement is fetched next run."""
    from exitscreen import cache

    for path in museum.ART_CACHE.glob(f"{day.isoformat()}_*.png"):
        try:
            path.unlink()
        except OSError:
            pass
    cache.save(f"artwork_{day.isoformat()}", None)


def upcoming_sheet(days: int, start: date | None = None) -> Path:
    """Render the next `days` picks as one contact sheet. Network, one call each.

    Reduced to the panel's 16 greys before you see it, and passed through the
    same museum.fetch_image() the panel uses - a full-colour thumbnail would be
    judging something the display cannot show.
    """
    start = start or date.today()
    index = museum.get_index()  # fetched once, not per day

    rows = (days + SHEET_COLS - 1) // SHEET_COLS
    cell_w, cell_h = THUMB[0], THUMB[1] + CAPTION_H
    canvas = Image.new("L", (cell_w * SHEET_COLS, cell_h * rows), theme.PAPER)
    d = ImageDraw.Draw(canvas)
    title_font = theme.load(theme.SUB_FACE, 13, weight=500)
    meta_font = theme.load(theme.SUB_FACE, 11, weight=400)

    for i in range(days):
        day = start + timedelta(days=i)
        work = museum.pick_for(day, index=index)
        cx, cy = (i % SHEET_COLS) * cell_w, (i // SHEET_COLS) * cell_h

        if not work:
            d.text((cx + 8, cy + 8), "nothing selected", font=title_font,
                   fill=theme.MUTED)
            continue

        try:
            thumb = eink.reduce(museum.fetch_image(work, THUMB), "grey16")
            canvas.paste(thumb, (cx, cy))
            score = f"{museum.contrast_score(thumb):.0f}"
        except Exception as exc:  # noqa: BLE001 - one dead image must not stop the sheet
            d.rectangle([cx, cy, cx + THUMB[0] - 1, cy + THUMB[1] - 1],
                        outline=theme.DIVIDER)
            d.text((cx + 8, cy + 8), f"fetch failed: {exc.__class__.__name__}",
                   font=meta_font, fill=theme.MUTED)
            score = "?"

        # Date, id and contrast on the first line; artist and title get a line
        # each to themselves, measured to the cell rather than cut at a character
        # count that a wide title overruns.
        room = THUMB[0] - 12
        ty = cy + THUMB[1] + 6
        d.text((cx + 6, ty), f"{day:%a %d %b}   [{work['id']}]   c{score}",
               font=title_font, fill=theme.BLACK)
        d.text((cx + 6, ty + 17),
               frame._fit(d, work["artist"] or "unknown", meta_font, room),
               font=meta_font, fill=theme.MUTED)
        d.text((cx + 6, ty + 31), frame._fit(d, work["title"], meta_font, room),
               font=meta_font, fill=theme.MUTED)

        flat = score != "?" and float(score) < theme.ART_FLAT_THRESHOLD
        print(f"  {day:%Y-%m-%d}  [{work['id']:>7}]  contrast {score:>3}"
              f"{'  <-- flat, will be stretched' if flat else ''}"
              f"  {work['artist'] or 'unknown'} - {work['title'][:44]}")

    OUT = ROOT / "out" / "art"
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "upcoming.png"
    canvas.save(path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", type=int, help="Cleveland object ids")
    ap.add_argument("--today", action="store_true", help="veto today's artwork")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--undo", type=int, metavar="ID")
    ap.add_argument("--next", type=int, metavar="N", default=None,
                    help="contact sheet of the next N days' picks")
    args = ap.parse_args()

    blacklist = load()

    if args.next is not None:
        if args.next < 1:
            sys.exit("--next needs a positive number of days")
        print(f"next {args.next} days, {len(blacklist)} already vetoed:\n")
        path = upcoming_sheet(args.next)
        print(f"\nwrote {path}")
        print("veto any of them with:  py tools/art_veto.py <id> <id> ...")
        return

    if args.list:
        if not blacklist:
            print("nothing vetoed")
            return
        index = {w["id"]: w for w in museum.get_index()}
        print(f"{len(blacklist)} vetoed:")
        for oid in blacklist:
            print(f"  {describe(index.get(oid)) if oid in index else f'[{oid}]'}")
        return

    if args.undo is not None:
        if args.undo not in blacklist:
            sys.exit(f"{args.undo} is not vetoed")
        blacklist.remove(args.undo)
        save(blacklist)
        print(f"un-vetoed {args.undo}")
        return

    ids = list(args.ids)
    today = date.today()

    if args.today:
        work = museum.pick_for(today)
        if not work:
            sys.exit("no artwork selected for today")
        ids.append(work["id"])
        print(f"vetoing today's: {describe(work)}")

    if not ids:
        # Default: just report, so the id is to hand before deciding.
        work = museum.pick_for(today)
        print(f"today ({today}): {describe(work)}")
        print(f"\nveto it with:  py tools/art_veto.py --today")
        print(f"{len(load())} vetoed so far, "
              f"{len(museum.get_index())} works in the collection")
        return

    save(blacklist + ids)
    clear_cached_day(today)

    replacement = museum.pick_for(today)
    print(f"blacklist now {len(load())} works")
    print(f"today is now: {describe(replacement)}")
    print("\nrun `python run.py --force` on the Pi to swap it now,")
    print("or leave it and the next scheduled run will pick it up.")


if __name__ == "__main__":
    main()
