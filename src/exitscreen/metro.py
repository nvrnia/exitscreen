"""Next metro departures from the home stop, via OVapi.

All of the following was verified against the live API on 2026-07-25 and is
recorded in exitscreen-spec.md; the short version:

  - http, not https. The certificate on v0.ovapi.nl does not match the
    hostname. The data is public and unauthenticated, so plain http is the
    honest fix - never disable certificate verification instead.
  - <stop code> is a TimingPointCode (one platform), not a StopAreaCode. The
    stopareacode endpoint returns an empty object for it.
  - That platform is already the direction we ride (northbound: D to
    the interchange, E to the far terminus), so there is no direction
    filter here. The platform is the filter. <stop code>-OPPOSITE is the other way.
  - Times are naive local Amsterdam, with no offset in the string.
  - Departures that have already left are still present in the feed.

This module answers "which metro can I catch", not "which metro is next". The
difference is the walk to the platform - see WALK_TO_PLATFORM_MIN.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import cache
from .models import Departure

TPC = "<stop code>"  # the home stop, northbound
URL = "http://v0.ovapi.nl/tpc/{tpc}"
TZ = ZoneInfo("Europe/Amsterdam")

# OVapi is a free, community-run server. The spec asks for ~10 minutes; this
# is enforced here rather than left to the caller or to cron.
MIN_POLL = 600
CACHE_KEY = "metro"

# Beyond this the cached data is too stale to be worth showing at all.
MAX_STALE = 3600

# Where the last get_departures() answer came from. Set on every call and read by
# run.py for the log.
#
# This exists because on 22 August the log said "2 departures" right up until it
# said "0 departures", and there was no way to tell whether those 2 came from a
# live fetch or from an hour-old cache being served while the wifi was down. The
# whole outage had to be reasoned about backwards from staleness constants.
# One word in the log would have answered it immediately.
#
#   fresh        fetched from OVapi just now, and it carried departures
#   cached       recent enough that we deliberately did not call out (MIN_POLL)
#   empty        a well-formed 200 that listed no departures at all. Normal at
#                3am, suspicious at 21:10. Deliberately NOT cached
#   stale        the fetch FAILED; serving old data rather than nothing
#   unreachable  the fetch failed and the cache is past MAX_STALE
LAST_SOURCE = "unknown"

# Front door to standing on the platform with the doors open - the walk plus the
# stairs. Departures closer than this are filtered out entirely.
#
# Without this the feed's own "has it left yet" test is the only filter, so at
# 10:50 the hero clock showed 10:52: a train you cannot reach. That put an
# uncatchable departure in the largest element on the panel and demoted the real
# answer to the small grey line underneath, which is exactly backwards.
#
# Consequence worth knowing: the hero jumps a whole interval as the threshold is
# crossed. At 10:46 it reads 10:52; a minute later that train is out of reach and
# it reads 10:57. Abrupt, but true.
WALK_TO_PLATFORM_MIN = 6


# Destinations as OVapi gives them are too long to show twice in one column.
# "CS" is how Dutch signage abbreviates Centraal Station, so it reads naturally.
SHORTEN = {
    "the interchange": "the terminus",
    "the far terminus": "Den Haag CS",
    "the city Slinge": "Slinge",
}


def short_destination(name: str) -> str:
    """A platform-sign style abbreviation, or the name unchanged."""
    return SHORTEN.get(name, name)


def _parse_time(value: str | None) -> datetime | None:
    """OVapi timestamps carry no offset, so attach Amsterdam explicitly.

    Relying on the Pi's system timezone would be fragile: it has no RTC and
    boots with the wrong clock until NTP catches up.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=TZ)
    except ValueError:
        return None


def parse(
    payload: dict,
    now: datetime | None = None,
    limit: int = 2,
    walk_min: int | None = None,
) -> list[Departure]:
    """Turn a raw OVapi response into *reachable* departures, soonest first.

    Reachable, not merely upcoming: anything leaving sooner than the walk to the
    platform is dropped. See WALK_TO_PLATFORM_MIN.
    """
    now = now or datetime.now(TZ)
    reach = (WALK_TO_PLATFORM_MIN if walk_min is None else walk_min) * 60

    stop = payload.get(TPC) or {}
    passes = stop.get("Passes") or {}

    upcoming = []
    for p in passes.values():
        # Prefer the real-time estimate; fall back to the timetable.
        when = _parse_time(p.get("ExpectedDepartureTime")) or _parse_time(
            p.get("TargetDepartureTime")
        )
        if when is None:
            continue

        seconds = (when - now).total_seconds()
        # Covers both cases in one test: already left (the feed still lists
        # these) and leaving too soon to walk to.
        if seconds < reach:
            continue

        upcoming.append(
            (
                when,
                Departure(
                    when=when,
                    line=str(p.get("LinePublicNumber") or "?"),
                    destination=p.get("DestinationName50") or "?",
                    minutes=int(seconds // 60),
                ),
            )
        )

    # Key order in Passes is not guaranteed chronological, so sort explicitly.
    upcoming.sort(key=lambda pair: pair[0])
    return [d for _, d in upcoming[:limit]]


def carries_departures(payload: dict) -> bool:
    """Is this a structurally sound answer about our stop?

    fetch() only raises on a network error or a non-200. OVapi is a free
    community server, and a 200 carrying an empty or wrong-shaped body sails
    straight through - so without this we would treat junk as a good answer,
    save it over a working cache, and serve it for the next MIN_POLL.

    Deliberately checks the *shape*, not the count. An empty Passes is possible
    at 3am and is handled separately - see get_departures().
    """
    stop = payload.get(TPC)
    return isinstance(stop, dict) and isinstance(stop.get("Passes"), dict)


def has_any_passes(payload: dict) -> bool:
    """Does it list any departures at all, reachable or not?"""
    return bool((payload.get(TPC) or {}).get("Passes"))


def fetch(tpc: str = TPC, timeout: float = 15) -> dict:
    """Raw GET. Raises on network or HTTP failure."""
    r = requests.get(URL.format(tpc=tpc), timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_departures(limit: int = 2, force: bool = False) -> list[Departure] | None:
    """Reachable departures, using the cache to stay polite and stay alive.

    **None and [] mean different things**, and the difference is the point:

        [...]  the feed answered; these are the trains you can catch
        []     the feed answered and there is genuinely nothing reachable
        None   we could not get data at all - unreachable, and the cache has
               aged past MAX_STALE

    They used to be conflated, so a dead OVapi rendered the same dash as a quiet
    platform. On a door screen that reads as "no trains tonight" when it actually
    means "I have no idea", which is the more dangerous of the two.
    """
    global LAST_SOURCE

    recent = None if force else cache.load(CACHE_KEY, max_age=MIN_POLL)
    if recent is not None:
        LAST_SOURCE = "cached"
        return parse(recent, limit=limit)

    try:
        payload = fetch()
        if not carries_departures(payload):
            # A 200 with the wrong shape is a failure, not an answer. Raising
            # here drops into the cache fallback below rather than caching junk.
            raise ValueError(f"response has no {TPC}/Passes")

        if has_any_passes(payload):
            cache.save(CACHE_KEY, payload)
            LAST_SOURCE = "fresh"
            return parse(payload, limit=limit)

        # Well-formed but carrying nothing. Legitimate at 3am, a glitch at 21:10,
        # and we cannot tell which from the response alone. So: never cache it -
        # that would poison a good answer for MIN_POLL and turn one bad response
        # into ten minutes of empty column - and prefer the last real data.
        #
        # Falling back is safe at 3am *because* parse() filters against the clock:
        # every cached train has long gone, so it yields [] by itself. At 21:10 it
        # shows the trains that are really running. The same branch is right in
        # both cases without having to know which one we are in.
        stale = cache.load(CACHE_KEY, max_age=MAX_STALE)
        if stale is not None:
            LAST_SOURCE = "empty, using last known"
            return parse(stale, limit=limit)

        LAST_SOURCE = "empty"
        return parse(payload, limit=limit)
    except Exception:
        # Network down, API down, garbage response - fall back to whatever we
        # last saw, as long as it is not hopelessly stale. Minutes are
        # recomputed against now, so a cached payload still counts down.
        stale = cache.load(CACHE_KEY, max_age=MAX_STALE)
        if stale is not None:
            LAST_SOURCE = "stale"
            return parse(stale, limit=limit)
        LAST_SOURCE = "unreachable"
        return None  # not "no trains" - "no idea". See the docstring.
