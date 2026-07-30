"""Every bundled typeface, side by side, on the strings this display uses.

    py tools/font_specimen.py       -> out/font_specimen.png

The font_lab tool renders whole layouts, which is right for judging a shortlist
but poor for comparing many faces - the differences drown in the surrounding
furniture. This strips it to what actually matters: the clock, the temperature,
a line of prose, and the small caps label.

Faces are discovered from assets/fonts rather than listed, so anything dropped
in that folder shows up here on the next run.

Digit behaviour is measured and printed per row, because Pillow here has no
libraqm and therefore cannot switch on OpenType tabular figures. A face whose
digits are already fixed-width is the only way to stop the clock changing width.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from exitscreen import theme  # noqa: E402

OUT = ROOT / "out"
LABEL_FACE = "IBMPlexSans[wdth,wght].ttf"

PROSE = "Call landlord about the boiler"
ROW_H = 122
HEADER_H = 48

# Skipped: italics (we never set them), and the icon font, which has no letters.
SKIP_TOKENS = ("italic", "weathericons")

# Pretty names and grouping. Anything unrecognised still renders, under "other".
KNOWN = {
    "Fraunces": ("Fraunces", "display serif"),
    "YoungSerif": ("Young Serif", "display serif"),
    "Gloock": ("Gloock", "display serif"),
    "InstrumentSerif": ("Instrument Serif", "display serif"),
    "Newsreader": ("Newsreader", "book serif"),
    "Literata": ("Literata", "book serif"),
    "CrimsonPro": ("Crimson Pro", "book serif"),
    "EBGaramond": ("EB Garamond", "book serif"),
    "Piazzolla": ("Piazzolla", "book serif"),
    "LibreBaskerville": ("Libre Baskerville", "book serif"),
    "SpecialElite": ("Special Elite", "typewriter"),
    "CutiveMono": ("Cutive Mono", "typewriter"),
    "CourierPrime": ("Courier Prime", "typewriter"),
    "JetBrainsMono": ("JetBrains Mono", "mono"),
    "DMMono": ("DM Mono", "mono"),
    "SpaceGrotesk": ("Space Grotesk", "sans"),
    "BricolageGrotesque": ("Bricolage Grotesque", "sans"),
    "DMSans": ("DM Sans", "sans"),
    "InstrumentSans": ("Instrument Sans", "sans"),
    "Archivo": ("Archivo", "sans"),
    "IBMPlexSans": ("IBM Plex Sans", "sans"),
    "Inter": ("Inter", "sans"),
    "AtkinsonHyperlegibleNext": ("Atkinson Hyperlegible", "sans"),
}

CATEGORY_ORDER = ["display serif", "book serif", "typewriter", "mono", "sans", "other"]


def discover():
    """All usable text faces in assets/fonts, grouped and ordered."""
    found = []
    seen_families = set()

    for path in sorted(theme.FONT_DIR.glob("*.ttf")):
        low = path.name.lower()
        if any(token in low for token in SKIP_TOKENS):
            continue

        stem = path.stem.split("[")[0].split("-")[0]
        if stem in seen_families:
            continue  # e.g. CourierPrime-Regular and -Bold are one family here
        seen_families.add(stem)

        name, category = KNOWN.get(stem, (stem, "other"))
        found.append((name, path.name, category))

    return sorted(found, key=lambda row: (CATEGORY_ORDER.index(row[2]), row[0]))


def digit_report(draw, filename) -> str:
    """Whether the clock will hold its width, and by how much it will not."""
    big = theme.load(filename, 60, weight=700)
    widths = [draw.textlength(str(n), font=big) for n in range(10)]
    times = [draw.textlength(t, font=big) for t in ("08:14", "08:21", "11:11", "00:00")]
    jitter = max(times) - min(times)
    if len(set(widths)) == 1:
        return "fixed-width digits · clock never shifts"
    if jitter <= 8:
        return f"near-fixed digits · clock shifts {jitter:.0f}px"
    return f"proportional digits · clock shifts {jitter:.0f}px"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    faces = discover()

    sheet = Image.new(
        "L", (theme.WIDTH, HEADER_H + ROW_H * len(faces)), theme.PAPER
    )
    d = ImageDraw.Draw(sheet)

    name_font = theme.load(LABEL_FACE, 21, weight=600)
    note_font = theme.load(LABEL_FACE, 16, weight=400)
    cat_font = theme.load(LABEL_FACE, 15, weight=500)

    d.text(
        (32, 14),
        f"All {len(faces)} bundled typefaces, on the strings this panel draws",
        font=name_font,
        fill=theme.BLACK,
    )

    last_cat = None
    for i, (name, filename, category) in enumerate(faces):
        y = HEADER_H + i * ROW_H

        new_group = category != last_cat
        d.line(
            [(32, y), (theme.WIDTH - 32, y)],
            fill=theme.BLACK if new_group else theme.DIVIDER,
            width=1,
        )
        if new_group:
            text = category.upper()
            d.text(
                (theme.WIDTH - 32 - d.textlength(text, font=cat_font), y + 6),
                text, font=cat_font, fill=theme.MUTED,
            )
            last_cat = category

        d.text((32, y + 8), name, font=name_font, fill=theme.BLACK)
        d.text((32, y + 33), digit_report(d, filename), font=note_font, fill=theme.MUTED)

        d.text((32, y + 54), "08:14", font=theme.load(filename, 60, weight=700),
               fill=theme.BLACK)
        d.text((250, y + 62), "20°", font=theme.load(filename, 44, weight=600),
               fill=theme.BLACK)
        d.text((390, y + 40), PROSE, font=theme.load(filename, 23, weight=400),
               fill=theme.BLACK)
        d.text((390, y + 72), "then 08:21", font=theme.load(filename, 25, weight=400),
               fill=theme.MUTED)
        theme.draw_tracked(d, (560, y + 76), "METRO",
                           theme.load(filename, 20, weight=500), 2.4, theme.MUTED)
        d.text((700, y + 74), "D  the interchange",
               font=theme.load(filename, 21, weight=400), fill=theme.MUTED)

    path = OUT / "font_specimen.png"
    sheet.save(path)
    print(f"{len(faces)} faces -> {path}")
    for name, filename, category in faces:
        print(f"   {category:<14} {name:<24} {filename}")


if __name__ == "__main__":
    main()
