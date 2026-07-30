"""AI-generated art: a REJECTED approach, kept as the record of the experiment.

    py tools/art_lab.py                 generate the candidate style strings
    py tools/art_lab.py --seed 42       reproducible
    py tools/art_lab.py --in-frame      also composite each into a real frame

**This is not the live art pipeline.** The panel takes its daily artwork from the
Cleveland Museum of Art - see src/exitscreen/museum.py and tools/art_veto.py.
Real paintings won on the grounds that they are prettier and more honest: an oil
actually has the tone and brushwork that a prompt only asks for.

The experiment is worth keeping because it succeeded on its own terms.
Pollinations needs no key, accepts the exact 1136x450 aspect ratio rather than
forcing a crop out of a square, and takes a seed, so a promising result is
reproducible - which the push guard would have required. If Cleveland ever goes
away, this is a working fallback rather than a fresh start.

Everything is converted to the panel's 16 greys before you see it - judging a
full-colour render would be judging something the display cannot show.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from exitscreen import eink, frame, theme as T  # noqa: E402

OUT = ROOT / "out" / "art"
ENDPOINT = "https://image.pollinations.ai/prompt/"

# The art box is 1136x450 - a 2.52:1 letterbox. Image models are trained mostly
# on squares, so an extreme ratio may itself degrade the result. Requesting the
# exact target avoids a crop; whether that is better than cropping a squarer
# image is one of the things this tool exists to find out.
WIDTH, HEIGHT = 1136, 448  # multiple of 8, matching the box within 2px

# Constant across every day, so the series reads as one hand. Straight from the
# ART BIBLE: delicate linework, cross-hatch shading, unpeopled, NL-adjacent,
# calm rather than whimsical, no text.
STYLES = {
    "A_etching": (
        "delicate pen-and-ink cross-hatch etching, fine-line engraving, "
        "black ink on white paper, no colour, airy linework with cross-hatch "
        "shading for shadow, calm and sincere, unpeopled"
    ),
    "B_engraving": (
        "antique copperplate engraving, dense parallel hatching and cross-hatch "
        "shading, fine burin lines, monochrome black and white, no people, "
        "quiet and restrained"
    ),
    "C_woodcut": (
        "fine woodcut print, carved line shading, high contrast black and white, "
        "unpeopled landscape, calm, no text"
    ),
}

# The variable half - what makes today's art today's.
SCENE = (
    "a low brick canal bridge over still water, flat wide Dutch sky, "
    "reeds in the foreground, overcast morning"
)

NEGATIVE = "no people, no text, no lettering, no signature, no colour, no frame"


def generate(prompt: str, seed: int | None, timeout: int = 120) -> Image.Image:
    url = ENDPOINT + urllib.parse.quote(prompt)
    params = {"width": WIDTH, "height": HEIGHT, "model": "flux", "nologo": "true"}
    if seed is not None:
        params["seed"] = seed
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    from io import BytesIO

    return Image.open(BytesIO(response.content))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scene", default=SCENE)
    ap.add_argument("--in-frame", action="store_true",
                    help="also composite each result into a real frame")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    results = []

    for key, style in STYLES.items():
        prompt = f"{style}. {args.scene}. {NEGATIVE}"
        print(f"\n{key}")
        print(f"  {prompt[:110]}...")
        try:
            raw = generate(prompt, args.seed)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc.__class__.__name__}: {exc}")
            continue

        raw.convert("RGB").save(OUT / f"{key}_raw.png")

        # What the panel would actually show.
        panel = eink.reduce(raw.convert("L"), "grey16")
        panel.save(OUT / f"{key}_grey16.png")
        results.append((key, panel))
        print(f"  ok  {raw.size} {raw.mode} -> {OUT / f'{key}_grey16.png'}")

        if args.in_frame:
            data = frame.sample_data()
            composed = eink.reduce(frame.build_frame(data, art=panel), "grey16")
            composed.save(OUT / f"{key}_frame.png")

    if not results:
        sys.exit("\nnothing generated")

    # Stack them for comparison, since the differences are in the shading.
    pad, label_h = 12, 30
    sheet = Image.new(
        "L", (WIDTH, (HEIGHT + label_h + pad) * len(results)), T.PAPER
    )
    d = ImageDraw.Draw(sheet)
    caption = T.load("WorkSans[wght].ttf", 19, weight=500)
    for i, (key, panel) in enumerate(results):
        y = i * (HEIGHT + label_h + pad)
        d.text((4, y + 4), key.replace("_", " · "), font=caption, fill=T.MUTED)
        sheet.paste(panel, (0, y + label_h))
    sheet.save(OUT / "compare.png")
    print(f"\ncomparison -> {OUT / 'compare.png'}")


if __name__ == "__main__":
    main()
