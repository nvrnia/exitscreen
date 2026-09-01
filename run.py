"""Fetch, render, and push to the panel. The production entry point.

    python run.py                 fetch, render, push only if changed
    python run.py --force         push even if the image is identical
    python run.py --clear         white the panel first, then render and push
    python run.py --dry-run       fetch and render, write a PNG, touch no hardware
    python run.py --wait-for-clock  block until NTP has set the time

Run from cron every 5 minutes. The guard means the panel only refreshes when the
image actually differs, so a 5-minute cadence costs nothing on the days when
nothing changes - see BACKLOG.md for the endurance figures behind that.

Every data source is wrapped: one dead feed costs its column, never the screen.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from exitscreen import cache, eink, frame  # noqa: E402
from exitscreen.models import FrameData  # noqa: E402

DIGEST_KEY = "last_pushed_digest"
OUT = ROOT / "out"

REDUCTION = "grey16"


def log(message: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}", flush=True)


def wait_for_clock(timeout: int = 180) -> bool:
    """Block until the system clock has been set by NTP.

    This Pi has no RTC, so at boot it believes it is some time in the past. A
    frame rendered then would show wrong departure times and, worse, would filter
    out every departure as 'already gone'. Only matters for the @reboot run.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            out = subprocess.run(
                ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return True  # no timedatectl - not a systemd box, do not block forever
        if out == "yes":
            return True
        time.sleep(5)
    return False


def single_instance():
    """Refuse to run twice at once, returning the lock or None.

    Two processes driving the panel over SPI at the same time gives
    "lgpio.error: 'GPIO busy'" and a failed render - seen in the log when a
    manual run collided with the 5-minute cron job. A slow feed can cause the
    same overlap unattended, so this is not only a hand-operation problem.

    The lock lives in the temp dir, which is tmpfs on the Pi, so this costs no
    SD card writes. The returned handle must stay referenced for the lifetime of
    the run - closing it releases the lock.
    """
    try:
        import fcntl
    except ImportError:
        # Windows: previews and --dry-run only, no hardware to collide over.
        return True

    handle = open(Path(tempfile.gettempdir()) / "exitscreen.lock", "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def freshest_fetch() -> datetime:
    """When the newest feed data actually arrived - NOT when we rendered.

    This is load-bearing. The footer draws this as "updated HH:MM", so if it came
    from now() the stamp would advance every run, the digest would always differ,
    and the push guard would refresh the panel every five minutes forever. Using
    the cache ages means the stamp only moves when data genuinely does, which for
    metro is every 10 minutes - and when metro refetches, the times on screen have
    usually changed anyway.
    """
    ages = [age for age in (cache.age(key) for key in ("metro", "weather", "todo"))
            if age is not None]
    if not ages:
        return datetime.now()
    return datetime.now() - timedelta(seconds=min(ages))


def gather() -> FrameData:
    """Collect every block, tolerating individual failures."""
    data = FrameData(day=date.today())
    all_departures: list = []

    try:
        from exitscreen import metro

        # Ask for more than the two we display: commute.py needs to find the
        # departure nearest its deadline, which can be an hour out. Same single
        # fetch either way - the limit only slices an already-parsed payload.
        departures = metro.get_departures(limit=20)
        # None means unreachable; [] means the feed answered with nothing.
        data.metro_unavailable = departures is None
        all_departures = departures or []
        data.departures = all_departures[:2]
        # The source matters as much as the count: "2 departures (stale)" says
        # the network is down and you are looking at old data, which "2
        # departures" alone hides completely.
        log("metro   : feed unavailable" if departures is None
            else f"metro   : {len(data.departures)} departures ({metro.LAST_SOURCE})")
    except Exception as exc:  # noqa: BLE001 - a dead feed must not stop the frame
        log(f"metro   : FAILED ({exc.__class__.__name__}: {exc})")

    try:
        from exitscreen import weather

        data.weather = weather.get_weather()
        w = data.weather
        log(f"weather : {round(w.temp_c)}C wmo {w.wmo}" if w else "weather : no data")
    except Exception as exc:  # noqa: BLE001
        log(f"weather : FAILED ({exc.__class__.__name__}: {exc})")

    try:
        from exitscreen import todo

        data.todos, data.todo_total = todo.get_todos(limit=4)
        timed = [f"{t.title} ({t.note})" for t in data.todos if t.note]
        log(f"todo    : {len(data.todos)} of {data.todo_total}"
            + (f" | {', '.join(timed)}" if timed else ""))
    except Exception as exc:  # noqa: BLE001
        log(f"todo    : FAILED ({exc.__class__.__name__}: {exc})")

    try:
        from exitscreen import commute

        data.commute = commute.plan(data.day, datetime.now(), all_departures)
        if data.commute:
            c = data.commute
            log(f"commute : class {c.class_start} | metro "
                + (f"{c.metro_departs}" if c.metro_departs else f"by {c.metro_deadline}")
                + f" | bus {c.bus_departs} -> the university stop {c.bus_arrives}")
        elif commute.expired(data.day):
            log("commute : bus timetable has EXPIRED - rerun "
                "tools/build_bus_timetable.py")
    except Exception as exc:  # noqa: BLE001
        log(f"commute : FAILED ({exc.__class__.__name__}: {exc})")

    # Set last: the caches have now been written, so this reflects this run's
    # data rather than the previous one's.
    data.fetched_at = freshest_fetch()
    return data


def gather_art():
    """(image, Artwork|None). Never raises - art.daily() has its own fallbacks."""
    from exitscreen import art, theme

    try:
        image, artwork = art.daily(theme.ART_W, theme.ART_H)
        log(f"art     : {artwork.label[:52]}" if artwork else "art     : placeholder")
        return image, artwork
    except Exception as exc:  # noqa: BLE001
        log(f"art     : FAILED ({exc.__class__.__name__}: {exc})")
        return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="push even when the image has not changed")
    ap.add_argument("--clear", action="store_true",
                    help="white the panel first; implies --force")
    ap.add_argument("--dry-run", action="store_true",
                    help="render to out/ and touch no hardware")
    ap.add_argument("--wait-for-clock", action="store_true",
                    help="block until NTP has set the time (for @reboot)")
    args = ap.parse_args()

    if args.wait_for_clock:
        log("waiting for NTP ...")
        log("clock synced" if wait_for_clock() else "clock NOT synced - continuing")

    # Held for the whole run; see single_instance().
    lock = single_instance()
    if lock is None:
        log("another run is already going - skipping this one")
        return 0

    data = gather()
    art_image, data.artwork = gather_art()
    img = eink.reduce(frame.build_frame(data, art=art_image), REDUCTION)
    digest = eink.frame_digest(img)

    if args.dry_run:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / "frame_grey16.png"
        img.save(path)
        log(f"dry run : {digest} -> {path}")
        return 0

    # Never replace a good frame with an empty one.
    #
    # If metro AND weather both came back with nothing, every feed failed - the
    # caches have a staleness limit and stop serving old data past it. In
    # practice that means the wifi is down: @reboot runs with --force, so without
    # this guard it would push a blank frame over a perfectly good one, and that
    # blank would sit on the door until the next successful run. A stale frame is
    # far better than an empty one.
    #
    # This applies to --clear too, and that is the whole point. The 06:59
    # ghost-clear once ran with both feeds dead: it whited the panel and drew an
    # empty frame, which then sat on the door all day. The clear used to be
    # exempt on the reasoning that it had already blanked the display so it had
    # to draw *something* - but this check happens before the panel is even
    # opened, so declining here means it is never cleared in the first place and
    # yesterday's good frame stays up. A ghost-clear is cosmetic maintenance;
    # skipping it for a day costs nothing.
    if data.weather is None and (data.metro_unavailable or not data.departures):
        log("no live data - every feed failed. Panel left as it was")
        return 0

    # A clear leaves the panel white, so the frame must be redrawn even if it is
    # identical to what was there before - otherwise the guard would skip it and
    # leave the display blank.
    force = args.force or args.clear
    previous = cache.load(DIGEST_KEY)

    if digest == previous and not force:
        log(f"no change ({digest}) - panel left alone")
        return 0

    try:
        from exitscreen.display import Panel

        panel = Panel()
    except Exception as exc:  # noqa: BLE001
        log(f"PANEL INIT FAILED ({exc.__class__.__name__}: {exc})")
        return 1

    if args.clear:
        log(f"cleared in {panel.clear():.1f}s")

    elapsed = panel.show(img)
    cache.save(DIGEST_KEY, digest)
    log(f"pushed {digest} in {elapsed:.1f}s"
        + ("" if previous is None else f" (was {previous})"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
