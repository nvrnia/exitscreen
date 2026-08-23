"""The daily artwork, from the Cleveland Museum of Art's open collection.

Cleveland was chosen after testing three sources:

  - **The Met** - images are fine and need no key, but the search is unusable.
    "landscape etching" returned a desk, a photograph and a calavera print; its
    own Drawings and Prints department reported one landscape. 340 candidates
    yielded three usable works.
  - **Art Institute of Chicago** - excellent search, but the IIIF image endpoint
    returns 403 even with their documented identifying header.
  - **Cleveland** - open API, no key, and real filters rather than free text.
    The response carries image dimensions, so works that would not survive the
    crop are ranked out before anything is downloaded.

Selection is deterministic for a given date. That is not a nicety: run.py
compares rendered pixels to decide whether to refresh the panel, so art that
changed between renders would defeat the guard and flash the display every five
minutes.
"""

from __future__ import annotations

import random
from datetime import date
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageEnhance, ImageOps, ImageStat

from . import cache
from . import theme
from .models import Artwork

API = "https://openaccess-api.clevelandart.org/api/artworks/"
FIELDS = "id,title,creation_date,technique,department,images,creators"

# Cleveland catalogues Japanese screens and Chinese handscrolls as "Painting"
# too. Department is the clean separator: these three are oil on canvas, the
# Asian art departments are scrolls, screens and album leaves.
DEPARTMENTS = (
    "European Painting and Sculpture",
    "American Painting and Sculpture",
    "Modern European Painting and Sculpture",
)

# Belt and braces - a scroll catalogued under a Western department still goes.
EXCLUDE_TECHNIQUE = ("scroll", "screen", "album", "fan", "tapestry", "miniature")

# Several subject terms rather than one, for variety. The user asked for wildly
# varied, and a single query returns a single flavour of landscape.
QUERIES = (
    "landscape", "river", "coast", "mountains", "winter", "trees", "sea",
    "valley", "forest", "storm", "harbor", "meadow", "sunset", "snow",
)

# The art box is 2.52:1 and paintings are not. Below 1.2 the crop takes a sliver
# rather than a band; above 3.5 is a panorama that would be arbitrarily sliced.
MIN_RATIO, MAX_RATIO = 1.2, 3.5

INDEX_KEY = "museum_index"
INDEX_MAX_AGE = 7 * 24 * 3600  # the collection does not change quickly

# Fixed, so the rotation order is stable across restarts. Changing it reshuffles.
SHUFFLE_SEED = 20260728

BLACKLIST = Path(__file__).resolve().parents[2] / "assets" / "art_blacklist.json"
ART_CACHE = Path(__file__).resolve().parents[2] / "cache" / "art"


def _clean_artist(creators) -> str:
    """'Georges Michel (French, 1763-1843)' -> 'Georges Michel'."""
    if not creators:
        return ""
    name = (creators[0] or {}).get("description") or ""
    return name.split("(")[0].strip()


def _usable(record: dict) -> dict | None:
    web = (record.get("images") or {}).get("web") or {}
    width, height = int(web.get("width") or 0), int(web.get("height") or 0)
    if not (height and web.get("url")):
        return None

    if record.get("department") not in DEPARTMENTS:
        return None

    technique = (record.get("technique") or "").lower()
    if any(word in technique for word in EXCLUDE_TECHNIQUE):
        return None

    ratio = width / height
    if not (MIN_RATIO <= ratio <= MAX_RATIO):
        return None

    return {
        "id": record["id"],
        "title": record.get("title") or "Untitled",
        "artist": _clean_artist(record.get("creators")),
        "date": record.get("creation_date") or "",
        "url": web["url"],
        "ratio": round(ratio, 3),
    }


def build_index(timeout: float = 60) -> list[dict]:
    """Query Cleveland across several subjects and keep what fits. Network."""
    found: dict[int, dict] = {}
    for query in QUERIES:
        try:
            response = requests.get(
                API,
                params={"q": query, "type": "Painting", "has_image": 1, "cc0": 1,
                        "limit": 100, "fields": FIELDS},
                timeout=timeout,
            )
            response.raise_for_status()
        except Exception:
            continue  # one bad query must not lose the whole index
        for record in response.json().get("data", []):
            work = _usable(record)
            if work:
                found[work["id"]] = work
    return sorted(found.values(), key=lambda w: w["id"])


def get_index(force: bool = False) -> list[dict]:
    """The work index, rebuilt at most weekly."""
    if not force:
        cached = cache.load(INDEX_KEY, max_age=INDEX_MAX_AGE)
        if cached:
            return cached

    index = build_index()
    if index:
        cache.save(INDEX_KEY, index)
        return index

    # Network failed - a stale index is far better than no art.
    return cache.load(INDEX_KEY) or []


def blacklisted_ids() -> set[int]:
    """Vetoed works. Lives in assets/ rather than cache/ so it survives a
    reflash - the cache directory does not."""
    import json

    if not BLACKLIST.exists():
        return set()
    try:
        return {int(i) for i in json.loads(BLACKLIST.read_text(encoding="utf-8"))}
    except (ValueError, OSError):
        return set()


def pick_for(day: date, index: list[dict] | None = None) -> dict | None:
    """The work for a given date.

    A fixed-seed shuffle indexed by day number gives a full cycle before any
    repeat, deterministically, without needing to remember what has been shown.
    A "seen" state file would be one more thing to lose or corrupt.
    """
    # Read once, not once per work: this was re-opening and re-parsing the JSON
    # for all ~120 candidates on every render, and left the loop able to see the
    # blacklist change halfway through.
    vetoed = blacklisted_ids()
    works = [w for w in (index if index is not None else get_index())
             if w["id"] not in vetoed]
    if not works:
        return None

    order = list(works)
    random.Random(SHUFFLE_SEED).shuffle(order)
    return order[day.toordinal() % len(order)]


def fetch_image(work: dict, size: tuple[int, int], timeout: float = 90) -> Image.Image:
    """Download, greyscale, and crop to fill. Raises on failure.

    Greyscale happens before the resize: on a 424MB Pi, holding a full-colour
    painting and its resized copy at once is worth avoiding. Cleveland's `web`
    image is ~900px, which is plenty for a 1136px-wide box and far cheaper than
    the full-resolution file.
    """
    response = requests.get(work["url"], timeout=timeout)
    response.raise_for_status()
    grey = ImageOps.grayscale(Image.open(BytesIO(response.content)))
    cropped = ImageOps.fit(grey, size, method=Image.LANCZOS,
                           centering=theme.ART_CROP_CENTRING)
    return enhance(cropped)


def enhance(image: Image.Image) -> Image.Image:
    """Stretch a muddy work's tonal range. Leave everything else alone.

    Most paintings use only the middle of the range, so quantising to 16 greys
    throws away most of the levels - which is why they look flat on the panel.
    Stretching first gives the levels something to work with.

    But this is deliberately *conditional*. A blanket stretch would override the
    painter on any work that is dark or pale on purpose, and would crush the
    works that least need it, since the boost still fires on an image that
    already spans 0-255.

    Measured on the cropped band rather than the whole painting, so the decision
    is about what is actually being shown.
    """
    if contrast_score(image) >= theme.ART_FLAT_THRESHOLD:
        return image  # already has range - the painter's choice stands

    stretched = ImageOps.autocontrast(image, cutoff=theme.ART_AUTOCONTRAST_CUTOFF)
    if theme.ART_CONTRAST_BOOST != 1.0:
        stretched = ImageEnhance.Contrast(stretched).enhance(
            theme.ART_CONTRAST_BOOST)
    return stretched


def contrast_score(image: Image.Image) -> float:
    """Standard deviation of the greys - a rough measure of how flat an image is.

    Used to reject works that stay muddy even after enhancement, rather than
    guessing from metadata which says nothing about tone.
    """
    return ImageStat.Stat(image).stddev[0]


def _cache_path(day: date, size: tuple[int, int]) -> Path:
    return ART_CACHE / f"{day.isoformat()}_{size[0]}x{size[1]}.png"


def daily(size: tuple[int, int], day: date | None = None):
    """(image, Artwork) for the day, or (None, None) if nothing is available.

    Today's image is cached to disk and reused for every render that day. This
    is what makes a daily artwork compatible with a five-minute render cadence:
    the pixels must be identical or the push guard refreshes the panel every run.
    """
    day = day or date.today()
    path = _cache_path(day, size)

    meta = cache.load(f"artwork_{day.isoformat()}")
    if path.exists() and meta:
        return Image.open(path).convert("L"), Artwork(**meta)

    work = pick_for(day)
    if not work:
        return None, None

    try:
        image = fetch_image(work, size)
    except Exception:
        return None, None

    ART_CACHE.mkdir(parents=True, exist_ok=True)
    image.save(path)
    meta = {"title": work["title"], "artist": work["artist"], "date": work["date"]}
    cache.save(f"artwork_{day.isoformat()}", meta)

    # Keep a week; the fallback only ever reaches back one day.
    for old in sorted(ART_CACHE.glob("*.png"))[:-7]:
        try:
            old.unlink()
        except OSError:
            pass

    return image, Artwork(**meta)
