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
    fresh = None if force else cache.load(CACHE_KEY, max_age=MIN_POLL)
    if fresh is not None:
        return parse(fresh, limit=limit)

    try:
        payload = fetch()
        cache.save(CACHE_KEY, payload)
        return parse(payload, limit=limit)
    except Exception:
        # Network down, API down, garbage response - fall back to whatever we
        # last saw, as long as it is not hopelessly stale. Minutes are
        # recomputed against now, so a cached payload still counts down.
        stale = cache.load(CACHE_KEY, max_age=MAX_STALE)
        if stale is not None:
            return parse(stale, limit=limit)
        return None  # not "no trains" - "no idea". See the docstring.
