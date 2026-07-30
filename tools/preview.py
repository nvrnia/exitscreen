"""Render the frame on the laptop, with no panel attached.

    py tools/preview.py              render, save all modes, open a viewer
    py tools/preview.py --mode bw    start the viewer on the dithered version
    py tools/preview.py --no-show    just write the PNGs (for a headless run)

In the viewer: 1/2/3 switch reduction mode, R re-renders (edit theme.py and
press R to see the change), S saves the current view, Q quits.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

# The package lives in src/, which is not on the path unless it is installed.
# Deriving this from __file__ rather than the working directory means the
# script runs from anywhere.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image  # noqa: E402

from exitscreen import eink, frame  # noqa: E402

OUT = ROOT / "out"


def build_data(live: bool = False):
    """Sample data, with any block that is actually built swapped in for real."""
    data = frame.sample_data()
    if not live:
        return data

    data.day = date.today()
    # Data freshness, not render time - the push guard depends on this.
    data.fetched_at = datetime.now()
    from exitscreen import metro, weather

    departures = metro.get_departures(limit=2)
    data.departures = departures
    print(
        f"  metro:   {len(departures)} live departures"
        if departures
        else "  metro:   no data (renders as a dash)"
    )

    conditions = weather.get_weather()
    data.weather = conditions
    if conditions:
        umbrella = " + umbrella" if conditions.umbrella else ""
        print(
            f"  weather: {round(conditions.temp_c)}C, wmo {conditions.wmo}, "
            f"wind {round(conditions.wind_kmh)}km/h{umbrella}"
        )
    else:
        print("  weather: no data (renders as a dash)")

    from exitscreen import todo

    tasks, total = todo.get_todos(limit=4)
    data.todos = tasks
    data.todo_total = total
    if tasks:
        extra = f" (+{total - len(tasks)} more)" if total > len(tasks) else ""
        print(f"  todo:    {len(tasks)} of {total} open{extra}")
        for t in tasks:
            print(f"           {t.title!r}" + (f"  ->  {t.note}" if t.note else ""))
    else:
        print("  todo:    no open tasks (renders as 'nothing to do')")

    return data


def render(mode: str, live: bool = False) -> Image.Image:
    return eink.reduce(frame.build_frame(build_data(live)), mode)


def save_all(live: bool = False) -> dict[str, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    base = frame.build_frame(build_data(live))
    paths = {}
    for mode in eink.MODES:
        img = eink.reduce(base, mode)
        path = OUT / f"frame_{mode}.png"
        img.save(path)
        paths[mode] = path
        print(f"  {mode:<8} {eink.levels_used(img):>3} greys  ->  {path}")
    return paths


def show(start_mode: str, live: bool = False) -> None:
    try:
        import tkinter as tk

        from PIL import ImageTk
    except ImportError as e:
        print(f"\nNo Tk viewer available ({e}). PNGs are in {OUT}.")
        return

    state = {"mode": start_mode, "photo": None}

    root = tk.Tk()
    root.title("exitscreen preview")
    root.configure(bg="#333")

    # Fit 1200x825 inside the screen, leaving room for the caption bar.
    scale = min(1.0, (root.winfo_screenwidth() - 120) / 1200,
                (root.winfo_screenheight() - 220) / 825)
    view = (int(1200 * scale), int(825 * scale))

    label = tk.Label(root, bg="#333", bd=0)
    label.pack(padx=12, pady=(12, 4))
    status = tk.Label(root, bg="#333", fg="#ddd", font=("Consolas", 10))
    status.pack(pady=(0, 10))

    def draw():
        img = render(state["mode"], live)
        state["photo"] = ImageTk.PhotoImage(
            img.resize(view, Image.LANCZOS) if scale < 1.0 else img
        )
        label.configure(image=state["photo"])
        status.configure(
            text=f"  {state['mode']}   {eink.levels_used(img)} greys   "
                 f"1200x825 at {int(scale * 100)}%      "
                 f"[1/2/3] mode   [R] re-render   [S] save   [Q] quit  "
        )

    def on_key(event):
        key = event.keysym.lower()
        if key in ("q", "escape"):
            root.destroy()
        elif key == "r":
            draw()
        elif key == "s":
            OUT.mkdir(parents=True, exist_ok=True)
            path = OUT / f"frame_{state['mode']}.png"
            render(state["mode"], live).save(path)
            print("saved", path)
        elif key in ("1", "2", "3"):
            state["mode"] = eink.MODES[int(key) - 1]
            draw()

    root.bind("<Key>", on_key)
    draw()
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=eink.MODES, default="grey16")
    ap.add_argument("--no-show", action="store_true", help="write PNGs only")
    ap.add_argument("--live", action="store_true", help="use real data where built")
    args = ap.parse_args()

    print("rendering 1200x825:")
    save_all(args.live)

    if not args.no_show:
        show(args.mode, args.live)


if __name__ == "__main__":
    main()
