"""Build a hand-approved collection of Dutch landscape etchings from the Met.

    py tools/curate_art.py --search          gather candidates, write contact sheets
    py tools/curate_art.py --keep 3,7,12     approve by index
    py tools/curate_art.py --list            show what has been approved

Why curated rather than searched at runtime:

The Met's *images* are excellent - public domain, no API key, reliable. Its
*search* is not: "landscape etching" returns a desk, a photograph and a Mexican
calavera print, and its own Drawings and Prints department reports one landscape.
Searching live would eventually put a mahogany secretary on the wall at 7am.

So the search is used once, as a rough net, and a person picks from the catch.
The approved object IDs are committed to the repo. After that the daily job needs
no search at all: pick by date, fetch that image, done. Deterministic, which the
push guard depends on, and immune to the search getting worse.

Small figures are NOT auto-rejected. The art bible asks for unpeopled scenes, but
Dutch landscape etching almost always carries a little staffage - a figure on a
path, a boat. Judge those by eye rather than by tag.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
from PIL import Image, ImageDraw, ImageOps  # noqa: E402

from exitscreen import theme as T  # noqa: E402

BASE = "https://collectionapi.metmuseum.org/public/collection/v1"

COLLECTION = ROOT / "assets" / "art_collection.json"
CANDIDATES = ROOT / "out" / "art" / "candidates.json"
SHEETS = ROOT / "out" / "art"

# The Met caps at 80 requests/second; nowhere near that is needed.
WORKERS = 8

# The known cast, plus subject nets. Noise is expected and fine - it gets
# filtered by a human, not by a clever query.
QUERIES = [
    "Anthonie Waterloo", "Jacob van Ruisdael", "Allart van Everdingen",
    "Jan van de Velde", "Herman Saftleven", "Roelant Roghman",
    "Esaias van de Velde", "Claes Jansz. Visscher", "Rembrandt landscape",
    "Dutch landscape etching", "windmill etching", "canal landscape print",
    "river landscape etching", "farmhouse etching trees",
]

WANTED_MEDIUM = ("etching", "engraving", "drypoint")

# Tags that suggest the subject is a place rather than a person or a story.
GOOD_TAGS = {
    "landscapes", "trees", "rivers", "boats", "houses", "windmills", "bridges",
    "canals", "farms", "villages", "mountains", "ruins", "roads", "clouds",
    "cottages", "forests", "water", "ships", "castles", "fields",
}


def search(query: str) -> list[int]:
    try:
        r = requests.get(f"{BASE}/search",
                         params={"q": query, "hasImages": "true"}, timeout=30)
        return (r.json().get("objectIDs") or [])[:40]
    except Exception:
        return []


def fetch_object(oid: int) -> dict | None:
    try:
        o = requests.get(f"{BASE}/objects/{oid}", timeout=30).json()
    except Exception:
        return None

    if not (o.get("isPublicDomain") and o.get("primaryImageSmall")):
        return None

    medium = (o.get("medium") or "").lower()
    if not any(w in medium for w in WANTED_MEDIUM):
        return None

    tags = {(t.get("term") or "").lower() for t in (o.get("tags") or [])}
    return {
        "id": o["objectID"],
        "title": o.get("title") or "?",
        "artist": o.get("artistDisplayName") or "unknown",
        "date": o.get("objectDate") or "?",
        "medium": (o.get("medium") or "")[:60],
        "image": o["primaryImageSmall"],
        "image_full": o.get("primaryImage") or o["primaryImageSmall"],
        "tags": sorted(tags),
        "landscape_tag": bool(tags & GOOD_TAGS),
    }


def do_search():
    print("gathering candidate ids ...")
    ids: set[int] = set()
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for found in ex.map(search, QUERIES):
            ids.update(found)
    print(f"  {len(ids)} unique ids across {len(QUERIES)} queries")

    print("fetching details (public domain + etching/engraving only) ...")
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        objects = [o for o in ex.map(fetch_object, sorted(ids)) if o]
    print(f"  {len(objects)} are public-domain prints with images")

    # Subject-tagged ones first, so the likely keepers are at the top of sheet 1.
    objects.sort(key=lambda o: (not o["landscape_tag"], o["artist"], o["title"]))

    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES.write_text(json.dumps(objects, indent=1), encoding="utf-8")
    print(f"  written to {CANDIDATES}")

    build_sheets(objects)


def build_sheets(objects, cols=4, rows=4, cell=(280, 210)):
    """Contact sheets, numbered, so approval is 'keep 3,7,12'."""
    label_font = T.load("WorkSans[wght].ttf", 15, weight=500)
    small_font = T.load("WorkSans[wght].ttf", 13, weight=400)
    per_sheet = cols * rows
    pad, caption_h = 10, 44

    def thumb(o):
        try:
            r = requests.get(o["image"], timeout=45)
            return ImageOps.grayscale(Image.open(BytesIO(r.content)))
        except Exception:
            return None

    for sheet_no in range((len(objects) + per_sheet - 1) // per_sheet):
        batch = objects[sheet_no * per_sheet:(sheet_no + 1) * per_sheet]
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            images = list(ex.map(thumb, batch))

        sheet = Image.new(
            "L",
            (cols * (cell[0] + pad) + pad,
             rows * (cell[1] + caption_h + pad) + pad),
            T.PAPER,
        )
        d = ImageDraw.Draw(sheet)

        for i, (o, im) in enumerate(zip(batch, images)):
            index = sheet_no * per_sheet + i
            cx = pad + (i % cols) * (cell[0] + pad)
            cy = pad + (i // cols) * (cell[1] + caption_h + pad)

            if im is not None:
                t = im.copy()
                t.thumbnail(cell, Image.LANCZOS)
                sheet.paste(t, (cx + (cell[0] - t.width) // 2,
                                cy + (cell[1] - t.height) // 2))
            d.rectangle([cx, cy, cx + cell[0], cy + cell[1]],
                        outline=T.DIVIDER, width=1)

            mark = "*" if o["landscape_tag"] else " "
            d.text((cx, cy + cell[1] + 6), f"[{index}]{mark} {o['title'][:30]}",
                   font=label_font, fill=T.BLACK)
            d.text((cx, cy + cell[1] + 24),
                   f"{o['artist'][:26]} · {o['date'][:14]}",
                   font=small_font, fill=T.MUTED)

        path = SHEETS / f"contact_{sheet_no + 1}.png"
        sheet.save(path)
        print(f"  sheet {sheet_no + 1}: {path}")


def do_keep(spec: str):
    objects = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    wanted = []
    for part in spec.replace(" ", "").split(","):
        if "-" in part:
            a, b = part.split("-")
            wanted.extend(range(int(a), int(b) + 1))
        elif part:
            wanted.append(int(part))

    approved = [objects[i] for i in wanted if 0 <= i < len(objects)]
    existing = []
    if COLLECTION.exists():
        existing = json.loads(COLLECTION.read_text(encoding="utf-8"))

    seen = {o["id"] for o in existing}
    added = [o for o in approved if o["id"] not in seen]
    combined = existing + added

    COLLECTION.parent.mkdir(parents=True, exist_ok=True)
    COLLECTION.write_text(json.dumps(combined, indent=1), encoding="utf-8")
    print(f"added {len(added)}, collection now {len(combined)} works")
    for o in added:
        print(f"   {o['title'][:44]} — {o['artist'][:26]}")


def do_list():
    if not COLLECTION.exists():
        sys.exit("no collection yet - run --search then --keep")
    objects = json.loads(COLLECTION.read_text(encoding="utf-8"))
    print(f"{len(objects)} approved works\n")
    for o in objects:
        print(f"  [{o['id']}] {o['title'][:46]}")
        print(f"        {o['artist'][:34]} · {o['date'][:18]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--keep", help="indices to approve, e.g. 3,7,12 or 0-5")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.search:
        do_search()
    elif args.keep:
        do_keep(args.keep)
    elif args.list:
        do_list()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
