"""Which metro and bus get me to class on time.

Answers one question: given today's class, which bus from the interchange
reaches the university stop in time, and which metro from the home stop makes that bus.

Three inputs, deliberately separate:
  assets/uni_schedule.json  the weekly class times, hand-edited
  assets/timetable.json         the timetable, generated from GTFS
  live metro departures     passed in, so this module needs no network

The bus timetable is scheduled rather than live: OVapi's live endpoints cannot
reach these stops (see BACKLOG), and you plan a departure against the schedule
anyway - delays matter at the stop, not at your front door.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "assets"
SCHEDULE = ASSETS / "uni_schedule.json"
TIMETABLE = ASSETS / "timetable.json"

# Measured from the GTFS feed across 2,728 real journeys: median 7.0 minutes,
# range 6.5-7.0. Consistent enough to treat as fixed.
METRO_RIDE_MIN = 7

# Metro platform at the interchange to the bus at perron AA. NOT measured -
# an estimate, and the one number here most worth correcting from experience.
TRANSFER_MIN = 6

# Standing time at the stop before the bus leaves, on top of that walk. This is a
# preference rather than a measurement, so it lives in uni_schedule.json as
# bus_buffer_min; this is only the fallback if the file omits it. The point is to
# arrive with the bus not yet there, rather than jogging onto it.
DEFAULT_BUS_BUFFER_MIN = 8

# How close a live departure must be to the deadline before it is worth naming.
# Metros run every 3-4 minutes, so anything inside this is "the one you want";
# beyond it we show the deadline instead of an arbitrary early train.
NAMEABLE_WINDOW_MIN = 20

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass
class Commute:
    """One planned journey. Times are strings because the frame only draws them."""

    class_start: str            # "14:00"
    arrive_by: str              # "11:45" - class minus the early margin
    bus_departs: str            # "11:03" from the interchange
    bus_arrives: str            # "11:32" at the university stop
    metro_deadline: str         # last moment a metro can leave the home stop
    metro_departs: str | None    # a real departure at/before that, when known
    metro_line: str | None
    wait_at_cs: int = 0          # minutes standing at the interchange
    missed: bool = False         # the deadline has passed - this bus is gone


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _clock(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def class_start_for(day: date, schedule: dict | None = None) -> str | None:
    """Today's class start, or None on a free day."""
    schedule = schedule if schedule is not None else _load(SCHEDULE)
    if not schedule:
        return None
    return (schedule.get("weekly") or {}).get(DAYS[day.weekday()])


def runs_on(day: date, timetable: dict | None = None) -> list[tuple[str, str]]:
    """(departs the interchange, arrives the university stop) for every bus that day."""
    timetable = timetable if timetable is not None else _load(TIMETABLE)
    if not timetable:
        return []
    stamp = day.strftime("%Y%m%d")
    for block in timetable.get("timetables", []):
        if stamp in block.get("dates", ()):
            return [tuple(r) for r in block["runs"]]
    return []


def expired(day: date, timetable: dict | None = None) -> bool:
    """Has the generated timetable run out? It only covers one term."""
    timetable = timetable if timetable is not None else _load(TIMETABLE)
    if not timetable:
        return True
    return day.strftime("%Y%m%d") > str(timetable.get("valid_to", ""))


def plan(day: date, now: datetime | None, departures, schedule=None, timetable=None):
    """The journey for today, or None when there is nothing to plan.

    `departures` is the live metro list from metro.get_departures() - a list, or
    None when the feed is unreachable. Only used to pick which metro to name.
    """
    now = now or datetime.now()
    schedule = schedule if schedule is not None else _load(SCHEDULE)
    start = class_start_for(day, schedule)
    if not start:
        return None                      # free day: the column stays as it was

    # A FLOOR, not a target. Buses are ~30 minutes apart, so treating it as an
    # exact deadline threw away a bus arriving 29 minutes before class - one
    # minute short of a 30-minute rule - and took one an hour early instead.
    early = (schedule or {}).get("arrive_at_least_min",
                                 (schedule or {}).get("arrive_early_min", 20))
    arrive_by = _mins(start) - early

    # The latest bus that still clears the floor. Latest, not earliest: no point
    # going an hour early just because a 06:33 bus also arrives before class.
    options = [r for r in runs_on(day, timetable) if _mins(r[1]) <= arrive_by]
    if not options:
        return None
    bus_dep, bus_arr = max(options, key=lambda r: _mins(r[1]))

    # Work backwards to the last moment a metro can leave the home stop:
    # bus departure, minus standing-around slack, minus the platform-to-platform
    # walk, minus the ride itself.
    buffer_min = (schedule or {}).get("bus_buffer_min", DEFAULT_BUS_BUFFER_MIN)
    latest_metro = _mins(bus_dep) - buffer_min - TRANSFER_MIN - METRO_RIDE_MIN

    # Name a real departure only when one sits close to the deadline. The feed
    # reaches ~85 minutes ahead, so for a class this afternoon there simply is no
    # live metro to point at - and picking the earliest that technically
    # qualifies gave "catch the 08:08" for a bus at 11:31. Outside that window
    # the deadline itself is the useful thing to show.
    metro_departs = metro_line = None
    for d in (departures or []):
        at = _mins(d.clock)
        if latest_metro - NAMEABLE_WINDOW_MIN <= at <= latest_metro:
            metro_departs, metro_line = d.clock, d.line   # keep the last, i.e. latest

    missed = _mins(f"{now:%H:%M}") > latest_metro

    wait = 0
    if metro_departs:
        wait = _mins(bus_dep) - (_mins(metro_departs) + METRO_RIDE_MIN + TRANSFER_MIN)

    return Commute(
        class_start=start,
        arrive_by=_clock(arrive_by),
        bus_departs=bus_dep,
        bus_arrives=bus_arr,
        metro_departs=metro_departs,
        metro_deadline=_clock(latest_metro),
        metro_line=metro_line,
        wait_at_cs=max(0, wait),
        missed=missed,
    )
