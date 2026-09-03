"""Next metro departures from the home stop, via OVapi.

Verified against the live API on 2026-07-25:

  - http, not https. The certificate on v0.ovapi.nl does not match the hostname.
    The data is public and unauthenticated, so plain http is the honest fix.
    Never turn off certificate verification instead.
  - The stop code is a TimingPointCode, one platform, not a StopAreaCode. The
    stopareacode endpoint returns an empty object for it.
  - That platform is already the direction we ride, so there is no direction
    filter here. The platform is the filter.
  - Times are naive local Amsterdam, no offset in the string.
  - Trains that have already left are still in the feed.

This answers "which metro can I catch", not "which metro is next". The
difference is the walk, see WALK_TO_PLATFORM_MIN.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import cache, settings
from .models import Departure

# Your platform and your walk are personal, so they live in the gitignored
# settings file rather than in a public repo.
TPC = settings.get("metro", "tpc")
URL = "http://v0.ovapi.nl/tpc/{tpc}"
TZ = ZoneInfo("Europe/Amsterdam")

# OVapi is a free community server, so poll gently. Enforced here rather than
# left to the caller or to cron.
MIN_POLL = 600
CACHE_KEY = "metro"

# Past this, cached data is too old to be worth showing at all.
MAX_STALE = 3600

# Where the last answer came from. run.py logs it.
#
# On 22 August the log read "2 departures" right up until it read "0", with no
# way to tell whether those 2 were live or an hour old with the wifi down. One
# word would have answered it.
#
#   fresh        just fetched, and it had departures
#   cached       recent enough that we deliberately did not call out
#   empty        a well-formed 200 listing nothing. Normal at 3am, suspicious at
#                21:10. Never cached
#   stale        the fetch failed; serving old data rather than nothing
#   unreachable  the fetch failed and the cache is past MAX_STALE
LAST_SOURCE = "unknown"

# Front door to standing on the platform, walk plus stairs. Anything sooner is
# dropped. Without it, a train two minutes away landed in the biggest element on
# the panel while the one you could actually make sat in the small grey line
# underneath. The hero jumps a whole interval as the threshold is crossed, which
# is abrupt but true.
WALK_TO_PLATFORM_MIN = settings.get("metro", "walk_to_platform_min", 6)

# The feed's destination names are too long for this column. The first
# departure's route is drawn beside the 70px time, which leaves about 180px, so
# a long name truncated mid-word. Which names need shortening depends on your
# platform, so it comes from settings.
SHORTEN = settings.get("metro", "shorten", {})


def short_destination(name: str) -> str:
    """A platform-sign style abbreviation, or the name unchanged."""
    return SHORTEN.get(name, name)


def _parse_time(value: str | None) -> datetime | None:
    """OVapi timestamps carry no offset, so attach Amsterdam explicitly.

    Trusting the Pi's system timezone would be fragile: it has no clock of its
    own and boots wrong until NTP catches up.
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
    """Turn a raw OVapi response into reachable departures, soonest first.

    Reachable, not just upcoming: anything leaving sooner than the walk to the
    platform is dropped.
    """
    now = now or datetime.now(TZ)
    reach = (WALK_TO_PLATFORM_MIN if walk_min is None else walk_min) * 60

    stop = payload.get(TPC) or {}
    passes = stop.get("Passes") or {}

    upcoming = []
    for p in passes.values():
        when = _parse_time(p.get("ExpectedDepartureTime")) or _parse_time(
            p.get("TargetDepartureTime")
        )
        if when is None:
            continue

        seconds = (when - now).total_seconds()
        # Covers both cases at once: already left, which the feed still lists,
        # and leaving too soon to walk to.
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

    # Key order in Passes is not guaranteed chronological.
    upcoming.sort(key=lambda pair: pair[0])
    return [d for _, d in upcoming[:limit]]


def carries_departures(payload: dict) -> bool:
    """Is this a structurally sound answer about our stop?

    fetch() only raises on a network error or a non-200, and a 200 carrying an
    empty or wrong-shaped body sails straight through. Without this we would
    treat junk as a good answer, save it over a working cache, and serve it for
    the next MIN_POLL.

    Checks the shape, not the count. An empty Passes is possible at 3am and is
    handled separately in get_departures().
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

    None and [] mean different things, and the difference is the point:

        [...]  the feed answered; these are the trains you can catch
        []     the feed answered and there is genuinely nothing reachable
        None   we could not get data at all, and the cache has aged out

    They used to be the same, so a dead OVapi drew the same dash as a quiet
    platform. On a door screen that reads as "no trains tonight" when it means
    "I have no idea", which is the more dangerous of the two.
    """
    global LAST_SOURCE

    recent = None if force else cache.load(CACHE_KEY, max_age=MIN_POLL)
    if recent is not None:
        LAST_SOURCE = "cached"
        return parse(recent, limit=limit)

    try:
        payload = fetch()
        if not carries_departures(payload):
            # Raising here drops into the cache fallback rather than caching junk.
            raise ValueError(f"response has no {TPC}/Passes")

        if has_any_passes(payload):
            try:
                cache.save(CACHE_KEY, payload)
            except Exception:
                # A failed cache write must not throw away a good fetch.
                pass
            LAST_SOURCE = "fresh"
            return parse(payload, limit=limit)

        # Well formed but carrying nothing. Legitimate at 3am, a glitch at 21:10,
        # and the response alone cannot tell us which. So never cache it, and
        # prefer the last real data.
        #
        # Falling back is safe at 3am because parse() filters against the clock:
        # every cached train has long gone, so it yields [] by itself. The same
        # branch is right in both cases without knowing which one we are in.
        stale = cache.load(CACHE_KEY, max_age=MAX_STALE)
        if stale is not None:
            LAST_SOURCE = "empty, using last known"
            return parse(stale, limit=limit)

        LAST_SOURCE = "empty"
        return parse(payload, limit=limit)
    except Exception:
        # Fall back to whatever we last saw, as long as it is not hopelessly
        # old. Minutes are recomputed against now, so a cached payload still
        # counts down.
        stale = cache.load(CACHE_KEY, max_age=MAX_STALE)
        if stale is not None:
            LAST_SOURCE = "stale"
            return parse(stale, limit=limit)
        LAST_SOURCE = "unreachable"
        return None  # not "no trains", "no idea". See the docstring.
