"""Three structural layout prototypes, rendered from the same live data.

    py tools/layout_lab.py --live
    py tools/layout_lab.py            sample data

Writes out/layout_A.png .. layout_C.png.

Nothing here touches frame.py - the layout currently running on the panel is
untouched. These are throwaway sketches whose only job is to let a structure be
judged before any of it is built for real. They reuse the real theme, fonts and
icons so the comparison is fair, but the placement numbers are local and rough.

  A  current      art across the top, three columns beneath
  B  side by side art down the left, the three blocks stacked on the right
  C  board first  slim art band, a real departure list, weather + todo paired
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402

from exitscreen import art as art_module  # noqa: E402
from exitscreen import eink, frame, icons  # noqa: E402
from exitscreen import theme as T  # noqa: E402
from exitscreen import metro as metro_module  # noqa: E402

OUT = ROOT / "out"


# --- shared furniture ----------------------------------------------------


def new_canvas(f, data):
    img = Image.new("L", (T.WIDTH, T.HEIGHT), T.PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([T.FRAME_LEFT, T.FRAME_TOP, T.FRAME_RIGHT, T.FRAME_BOTTOM],
                outline=T.DIVIDER, width=1)
    T.draw_tracked(d, (T.MARGIN_X, T.TOPBAR_BASE), frame._date_label(data.day),
                   f.topbar, T.TOPBAR_TRACKING, T.FURNITURE_INK)
    return img, d


def footer(d, f, data):
    d.line([(T.CONTENT_LEFT, T.FOOTER_TOP), (T.CONTENT_RIGHT, T.FOOTER_TOP)],
           fill=T.DIVIDER, width=1)
    T.draw_tracked(d, (T.MARGIN_X, T.FOOTER_BASE), "our exit screen",
                   f.nameplate, T.NAMEPLATE_TRACKING, T.NAMEPLATE_INK)
    if data.fetched_at:
        T.draw_tracked_right(d, T.CONTENT_RIGHT, T.FOOTER_BASE,
                             f"updated {data.fetched_at:%H:%M}", f.stamp, 0.8,
                             T.NAMEPLATE_INK)


def art_box(img, d, box):
    x0, y0, x1, y1 = box
    art = art_module.placeholder(x1 - x0, y1 - y0)
    img.paste(art, (x0, y0))
    d.rectangle([x0 - 1, y0 - 1, x1, y1], outline=T.DIVIDER, width=1)


def label(d, f, x, baseline, text):
    T.draw_tracked(d, (x, baseline), text, f.label, T.LABEL_TRACKING, T.FURNITURE_INK)


def line(d, x, baseline, text, font, fill=T.MUTED):
    d.text((x, baseline), text, font=font, fill=fill, anchor="ls")


def route(d, f, x, right, baseline, departure, prefix=""):
    cursor = x
    if prefix:
        line(d, cursor, baseline, prefix, f.meta)
        cursor += d.textlength(prefix, font=f.meta)
    line(d, cursor, baseline, departure.line, f.meta)
    cursor += d.textlength(departure.line, font=f.meta)
    icons.arrow(d, cursor + 9, baseline - 6, length=13, bearing=90)
    cursor += 29
    name = metro_module.short_destination(departure.destination)
    line(d, cursor, baseline, frame._fit(d, name, f.meta, right - cursor), f.meta)


def weather_block(img, d, f, w, x, right, label_base, hero_base, bars_top, line_1):
    if w is None:
        line(d, x, hero_base, "–", f.temp, T.BLACK)
        return
    digits = f"{round(w.temp_c)}" if w.temp_c is not None else "–"
    line(d, x, hero_base, digits, f.temp, T.BLACK)
    cursor = x + d.textlength(digits, font=f.temp)
    cap = d.textbbox((0, 0), "0", font=f.temp, anchor="ls")[1]
    deg_cap = d.textbbox((0, 0), "°", font=f.degree, anchor="ls")[1]
    line(d, cursor + 2, hero_base + (cap - deg_cap), "°", f.degree, T.BLACK)
    cursor += 2 + d.textlength("°", font=f.degree)
    if w.temp_max_c is not None:
        icons.arrow(d, cursor + 14, hero_base - 7, length=14, bearing=90)
        line(d, cursor + 36, hero_base, f"{round(w.temp_max_c)}°", f.small)

    if w.show_bars:
        icons.draw_weather(d, right - 32, hero_base - 36, 32, w.wmo, w.umbrella)
        for i, prob in enumerate(w.rain_hours):
            prob = max(0, min(100, prob or 0))
            h = max(2, round(T.BARS_H * prob / 100))
            bx = x + i * 18
            d.rectangle([bx, bars_top + T.BARS_H - h, bx + 13, bars_top + T.BARS_H],
                        fill=T.BLACK if prob >= 40 else T.MUTED)
        if w.first_rain_at:
            advice = "take a coat" if w.blustery else "take umbrella"
            line(d, x, line_1,
                 frame._fit(d, f"Rain {w.first_rain_at} — {advice}", f.small, right - x),
                 f.small)
    else:
        icons.draw_weather(d, x + 2, bars_top - 6, 58, w.wmo, w.umbrella)


def todo_block(img, d, f, data, x, right, first_base, step, limit_base):
    if not data.todos:
        line(d, x, first_base, "nothing to do", f.todo)
        return
    radius, stroke = 10, 2.5
    gap = radius * 2 + 14
    baseline = first_base
    for task in data.todos:
        if baseline > limit_base:
            break
        icons.bullet(img, x + radius, baseline - 8, radius, T.BLACK, stroke)
        # This lab compares band geometry, not task timing, so titles only.
        line(d, x + gap, baseline, frame._fit(d, task.title, f.todo, right - x - gap),
             f.todo, T.BLACK)
        baseline += step
    if data.overflow:
        line(d, x, min(baseline, limit_base + step), f"+{data.overflow} more", f.small)


# --- A: current ----------------------------------------------------------


def layout_a(data, f):
    return frame.build_frame(data, fonts=f)


# --- B: art down the left, blocks stacked right --------------------------


def layout_b(data, f):
    img, d = new_canvas(f, data)
    split = 706
    art_box(img, d, (T.CONTENT_LEFT, 68, split, 752))

    x, right = split + 30, T.CONTENT_RIGHT
    d.line([(split + 1, 68), (split + 1, 752)], fill=T.PAPER, width=0)

    # metro
    label(d, f, x, 104, "METRO")
    if data.departures:
        line(d, x, 178, data.departures[0].clock, f.big, T.BLACK)
        route(d, f, x, right, 214, data.departures[0])
        if len(data.departures) > 1:
            route(d, f, x, right, 246, data.departures[1],
                  prefix=f"{data.departures[1].clock}   ")
    else:
        line(d, x, 178, "–", f.big, T.BLACK)

    d.line([(x, 286), (right, 286)], fill=T.DIVIDER, width=1)

    # weather
    label(d, f, x, 330, "WEATHER")
    weather_block(img, d, f, data.weather, x, right,
                  label_base=330, hero_base=404, bars_top=424, line_1=482)

    d.line([(x, 522), (right, 522)], fill=T.DIVIDER, width=1)

    # todo
    label(d, f, x, 566, "TO DO")
    todo_block(img, d, f, data, x, right, first_base=606, step=33, limit_base=705)

    footer(d, f, data)
    return img


# --- C: slim art, a real departure list ----------------------------------


def layout_c(data, f):
    img, d = new_canvas(f, data)
    art_box(img, d, (T.CONTENT_LEFT, 68, T.CONTENT_RIGHT, 322))
    d.line([(T.CONTENT_LEFT, 344), (T.CONTENT_RIGHT, 344)], fill=T.DIVIDER, width=1)

    split = 620
    d.line([(split, 360), (split, 743)], fill=T.DIVIDER, width=1)

    # metro, with more departures than the current layout can show
    x, right = T.CONTENT_LEFT, split - 24
    label(d, f, x, 388, "METRO")
    if data.departures:
        line(d, x, 470, data.departures[0].clock, f.big, T.BLACK)
        route(d, f, x, right, 508, data.departures[0])
        base = 556
        for dep in data.departures[1:4]:
            line(d, x, base, dep.clock, f.then)
            route(d, f, x + 92, right, base, dep)
            base += 38
    else:
        line(d, x, 470, "–", f.big, T.BLACK)

    # weather and todo share the right half
    x2, right2 = split + 26, T.CONTENT_RIGHT
    label(d, f, x2, 388, "WEATHER")
    weather_block(img, d, f, data.weather, x2, right2,
                  label_base=388, hero_base=462, bars_top=482, line_1=540)

    d.line([(x2, 580), (right2, 580)], fill=T.DIVIDER, width=1)
    label(d, f, x2, 622, "TO DO")
    todo_block(img, d, f, data, x2, right2, first_base=662, step=33, limit_base=728)

    footer(d, f, data)
    return img


LAYOUTS = [
    ("A", "current — art across the top, three columns beneath", layout_a),
    ("B", "side by side — art down the left, blocks stacked right", layout_b),
    ("C", "board first — slim art, four departures listed", layout_c),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    if args.live:
        sys.path.insert(0, str(ROOT / "tools"))
        from preview import build_data

        data = build_data(live=True)
        # C shows more departures than the other two, so fetch enough for it
        try:
            from exitscreen import metro

            data.departures = metro.get_departures(limit=4)
        except Exception:
            pass
    else:
        data = frame.sample_data()

    OUT.mkdir(parents=True, exist_ok=True)
    f = T.Fonts()
    for key, description, fn in LAYOUTS:
        img = eink.reduce(fn(data, f), "grey16")
        path = OUT / f"layout_{key}.png"
        img.save(path)
        print(f"  {key}  {description}\n     -> {path}")


if __name__ == "__main__":
    main()
