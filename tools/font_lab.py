"""Render the layout under each candidate typeface, so the choice is made by
looking rather than by reading adjectives.

    py tools/font_lab.py           sample data, identical across all candidates
    py tools/font_lab.py --live    real metro and weather

Writes one full frame per candidate, plus out/font_compare.png - the decision
rows stacked, which is where the differences actually show.

Sizes are held constant across candidates on purpose. Each face has a different
x-height so the "fairest" comparison would tune sizes per font, but that hides
which face reads best at a given size - and a given size is what the panel has.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from exitscreen import eink, frame, theme  # noqa: E402

OUT = ROOT / "out"

PLEX_SANS = "IBMPlexSans[wdth,wght].ttf"
INSTRUMENT_SANS = "InstrumentSans[wdth,wght].ttf"
ARCHIVO = "Archivo[wdth,wght].ttf"
LITERATA = "Literata[opsz,wght].ttf"
BRICOLAGE = "BricolageGrotesque[opsz,wdth,wght].ttf"

# (key, label, text face, numeral face or None to match)
# Five deliberately different directions rather than five shades of grotesque.
CANDIDATES = [
    ("1", "Literata main + Archivo supporting", LITERATA, ARCHIVO),
    ("2", "Literata main + Bricolage Grotesque supporting", LITERATA, BRICOLAGE),
    ("3", "Literata main + IBM Plex Sans supporting", LITERATA, PLEX_SANS),
    ("4", "Literata main + Instrument Sans supporting", LITERATA, INSTRUMENT_SANS),
]


def resolve(name: str) -> str:
    """Find a bundled font file from a loose name, e.g. 'literata' or 'plexsans'."""
    needle = name.lower().replace(" ", "").replace("-", "")
    for path in sorted(theme.FONT_DIR.glob("*.ttf")):
        low = path.name.lower()
        if "italic" in low or "weathericons" in low:
            continue
        if needle in low.replace("-", "").replace(" ", ""):
            return path.name
    raise SystemExit(f"no bundled font matches {name!r}")


def render(main_face, sub_face, data):
    fonts = theme.Fonts(main_face=main_face, sub_face=sub_face)
    return eink.reduce(frame.build_frame(data, fonts=fonts), "grey16")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="use real metro and weather")
    ap.add_argument(
        "faces",
        nargs="*",
        help="loose font names to compare, e.g. literata bricolage. "
             "Use main+sub to pair a main face with a supporting one. "
             "Defaults to the shortlist.",
    )
    args = ap.parse_args()

    global CANDIDATES
    if args.faces:
        CANDIDATES = []
        for i, spec in enumerate(args.faces, start=1):
            if "+" in spec:
                main, sub = spec.split("+", 1)
                CANDIDATES.append(
                    (str(i), f"{main} main + {sub} supporting",
                     resolve(main), resolve(sub))
                )
            else:
                CANDIDATES.append((str(i), spec, resolve(spec), None))

    if args.live:
        sys.path.insert(0, str(ROOT / "tools"))
        from preview import build_data

        data = build_data(live=True)
    else:
        data = frame.sample_data()

    OUT.mkdir(parents=True, exist_ok=True)

    # Stack the decision rows, which is where a typeface either works or does not.
    band_h = theme.FOOTER_TOP - theme.DECISION_TOP
    label_h = 34
    sheet = Image.new(
        "L", (theme.WIDTH, (band_h + label_h) * len(CANDIDATES)), theme.PAPER
    )
    sd = ImageDraw.Draw(sheet)
    label_font = theme.load(PLEX_SANS, 19, weight=500)

    for i, (key, label, face, numeral_face) in enumerate(CANDIDATES):
        img = render(face, numeral_face, data)
        path = OUT / f"font_{key}.png"
        img.save(path)
        print(f"  {key}  {label}")
        print(f"     -> {path}")

        y = i * (band_h + label_h)
        sd.text((theme.CONTENT_LEFT, y + 8), f"{key} · {label}",
                font=label_font, fill=theme.MUTED)
        sheet.paste(
            img.crop((0, theme.DECISION_TOP, theme.WIDTH, theme.FOOTER_TOP)),
            (0, y + label_h),
        )
        sd.line(
            [(theme.CONTENT_LEFT, y + label_h - 4),
             (theme.CONTENT_RIGHT, y + label_h - 4)],
            fill=theme.DIVIDER, width=1,
        )

    compare = OUT / "font_compare.png"
    sheet.save(compare)
    print(f"\ncomparison sheet -> {compare}")


if __name__ == "__main__":
    main()
