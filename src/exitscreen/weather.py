"""Current conditions and the "what do I take with me" decision, via Open-Meteo.

Verified against the live API on 2026-07-26:
  - No key, no signup. HTTPS works properly here (unlike OVapi).
  - Units already come back metric for a European location: degC, km/h,
    degrees. No need to force them with extra parameters.
  - timezone=auto resolves to Europe/Amsterdam, so the hourly time grid is in
    local time and lines up with current.time.
  - hourly returns 7 days (168 entries); we only look a few hours ahead.

The decisions are the point of this block. The panel answers "what do I take
with me", so an upcoming soaking matters more than a currently dry sky.
"""

from __future__ import annotations

import requests

from . import cache, settings
from .models import Weather

URL = "https://api.open-meteo.com/v1/forecast"

# Your coordinates, from the gitignored settings file. Open-Meteo needs no key.
LAT = settings.get("weather", "latitude")
LON = settings.get("weather", "longitude")

PARAMS = {
    "latitude": LAT,
    "longitude": LON,
    "current": (
        "temperature_2m,weather_code,wind_speed_10m,wind_direction_10m,"
        "wind_gusts_10m"
    ),
    "hourly": "precipitation_probability,temperature_2m",
    "timezone": "auto",
}

# How far ahead to look. Eight hours rather than six so that rain in the
# mid-afternoon is already visible at breakfast - a six-hour window read at
# 08:00 ends at 14:00 and would miss a 15:00 shower entirely.
LOOKAHEAD_HOURS = 8

UMBRELLA_THRESHOLD = 40  # percent - a call to action
RAIN_BARS_THRESHOLD = 25  # percent - merely worth showing the shape of

# WMO codes from 51 up are drizzle/rain/snow/showers/thunder - actively wet.
WET_FROM_CODE = 51

# Beaufort 6 is officially described as "umbrellas are hard to use", which makes
# it the natural point to stop advising an umbrella and start advising a coat.
# Gusts are judged separately: a gusty day can ruin an umbrella even when the
# sustained wind is unremarkable.
WIND_NOTABLE_BEAUFORT = 6
GUST_NOTABLE_KMH = 50

CACHE_KEY = "weather"
MIN_POLL = 900  # 15 minutes
MAX_STALE = 6 * 3600

# Upper bound in km/h for forces 1..11; anything above is force 12. Verified
# against published tables rather than recalled - sources differ by +/-1 at the
# 117/118 boundary, which is immaterial at the wind speeds seen here.
_BEAUFORT_UPPER = (5, 11, 19, 28, 38, 49, 61, 74, 88, 102, 117)


def beaufort(kmh: float | None) -> int:
    """Wind force on the Beaufort scale, from a speed in km/h."""
    if kmh is None or kmh < 1:
        return 0
    for force, upper in enumerate(_BEAUFORT_UPPER, start=1):
        if kmh <= upper:
            return force
    return 12


def _hour_window(payload: dict) -> tuple[list[int], list[str]]:
    """The next LOOKAHEAD_HOURS of precipitation probability, with their times.

    Aligns to the current hour using current.time, which the API returns on the
    same local grid as the hourly array.
    """
    current = payload.get("current") or {}
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    probs = hourly.get("precipitation_probability") or []
    if not times or not probs:
        return [], []

    now_hour = (current.get("time") or "")[:13]
    start = 0
    for i, t in enumerate(times):
        if t[:13] >= now_hour:
            start = i
            break

    end = start + LOOKAHEAD_HOURS
    window = [p if p is not None else 0 for p in probs[start:end]]
    return window, times[start:end]


def _today_max_temp(payload: dict) -> float | None:
    """Today's high, from the hourly temperatures we already fetch."""
    current = payload.get("current") or {}
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    today = (current.get("time") or "")[:10]
    if not today or not times or not temps:
        return None

    values = [
        t for stamp, t in zip(times, temps) if stamp[:10] == today and t is not None
    ]
    return max(values) if values else None


def parse(payload: dict) -> Weather | None:
    current = payload.get("current")
    if not current:
        return None

    window, stamps = _hour_window(payload)
    peak = max(window) if window else 0
    code = int(current.get("weather_code") or 0)

    # Bars only appear when there is rain worth showing. An empty list is the
    # signal for the renderer to draw the icon alone - the absence is the
    # message on a dry day.
    rain_hours = window if peak >= RAIN_BARS_THRESHOLD else []

    first_rain_at = None
    for index, (prob, stamp) in enumerate(zip(window, stamps)):
        if prob >= RAIN_BARS_THRESHOLD:
            # Index 0 is the hour we are already in, so a time would read as
            # stale advice ("Rain 15:00" at 15:13, while it is raining).
            first_rain_at = "now" if index == 0 else stamp[11:16]
            break

    wind_kmh = float(current.get("wind_speed_10m") or 0)
    gust = current.get("wind_gusts_10m")

    return Weather(
        temp_c=current.get("temperature_2m"),
        temp_max_c=_today_max_temp(payload),
        wmo=code,
        wind_kmh=wind_kmh,
        gust_kmh=float(gust) if gust is not None else None,
        # Beaufort describes sustained wind. Feeding gusts in here would report
        # a force the day does not actually have; gusts are shown separately.
        beaufort=beaufort(wind_kmh),
        blustery=(
            beaufort(wind_kmh) >= WIND_NOTABLE_BEAUFORT
            or float(gust or 0) >= GUST_NOTABLE_KMH
        ),
        umbrella=code >= WET_FROM_CODE or peak >= UMBRELLA_THRESHOLD,
        rain_hours=rain_hours,
        first_rain_at=first_rain_at,
    )


def fetch(timeout: float = 15) -> dict:
    r = requests.get(URL, params=PARAMS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_weather() -> Weather | None:
    """Current weather, cached. Returns None only if there is nothing usable."""
    fresh = cache.load(CACHE_KEY, max_age=MIN_POLL)
    if fresh is not None:
        return parse(fresh)

    try:
        payload = fetch()
        cache.save(CACHE_KEY, payload)
        return parse(payload)
    except Exception:
        stale = cache.load(CACHE_KEY, max_age=MAX_STALE)
        return parse(stale) if stale is not None else None
