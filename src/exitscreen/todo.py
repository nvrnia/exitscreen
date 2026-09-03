"""Today's tasks from one TickTick list.

Today's, not all open ones. A task due next month is not something you need to
know on the way out of the door.

Two things about this API that will catch you out, both verified live. The full
set is in BACKLOG.md.

**dueDate's offset is honest UTC**, not local wall time wearing a +0000 badge.
An all-day task due 27 July comes back as 2026-07-26T22:00:00.000+0000, and
22:00 UTC is midnight Amsterdam on the 27th in summer. So that value's naive
date is the 26th, the wrong day. Always convert to Europe/Amsterdam before
reading a date or an hour off it.

**The API does not sort by sortOrder**, which is a large negative integer in the
user's own order. Without an explicit sort the list looks shuffled on the panel.

There is also no "all tasks" endpoint, you have to name a project, which is why
this is built around a single dedicated list.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from . import cache, config
from .models import Task

API = "https://api.ticktick.com/open/v1"

CACHE_KEY = "todo"
MIN_POLL = 900  # TickTick has no webhooks, so we poll
MAX_STALE = 24 * 3600  # a day-old list still beats an empty column

OPEN_STATUS = 0

TZ = ZoneInfo("Europe/Amsterdam")

# How long the journey takes, front door to being there: "Dentist #40m".
#
# The leading # is required. Without it "Buy 2m of rope" claims a two minute
# journey, and a wrong leave time looks exactly as authoritative as a right one.
TRAVEL_TAG = re.compile(r"#(\d{1,3})\s*m\b", re.IGNORECASE)

# For when the app lifts "#40m" out of the title and into `tags` instead. Which
# of the two happens is unverified, so both are accepted.
TRAVEL_TAG_ONLY = re.compile(r"^(\d{1,3})\s*m$", re.IGNORECASE)


def _due(task: dict) -> datetime | None:
    """When the task is due, in Amsterdam. All-day tasks land at local midnight.

    The conversion is not optional. See the module docstring: reading the date
    without converting first is off by one.
    """
    raw = task.get("dueDate") or task.get("startDate")
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return None


def _clock_time(task: dict) -> datetime | None:
    """The due moment, but only when it is a real time of day.

    All-day tasks return None. "Buy bread today" has no time to leave for, so it
    gets no inline time and no leave-by line.
    """
    return None if task.get("isAllDay") else _due(task)


def _travel_minutes(task: dict) -> int | None:
    """Door-to-door minutes from a #40m tag, in the title or in `tags`."""
    match = TRAVEL_TAG.search(task.get("title") or "")
    if match:
        return int(match.group(1))

    for tag in task.get("tags") or []:
        match = TRAVEL_TAG_ONLY.match(str(tag).strip())
        if match:
            return int(match.group(1))

    return None


def _labels(
    due: datetime | None, travel_min: int | None, now: datetime
) -> tuple[str | None, str | None]:
    """(inline time, second-line note) for one task.

    The appointment time always shows when there is one. It is free, it sits
    beside the title, and it lets you sanity-check the leave time next to it.

    The leave-by line only appears while it is still achievable. A stale "leave
    by 08:20" sitting there at 11:00 is noise that teaches you to ignore the live
    ones.
    """
    if due is None:
        return None, None

    at = f"{due:%H:%M}"

    if travel_min is not None:
        leave_at = due - timedelta(minutes=travel_min)
        if leave_at > now:
            return at, f"leave by {leave_at:%H:%M}"

    return at, None


def parse(
    payload: dict, limit: int = 4, now: datetime | None = None
) -> tuple[list[Task], int]:
    """Return (today's tasks to show, how many there are in total).

    Only tasks dated today. The panel answers "what do I need before I walk out",
    so a task due next month is noise on the door. The list used to show
    everything open, including a lunch a month away. Deliberate consequences:
    undated tasks never appear, and neither do overdue ones.

    The total drives the "+N more" line, so it counts every task due today rather
    than only the ones that fit.

    `now` is a parameter rather than read inside, same as metro.parse(), so the
    date boundary and the leave-by boundary are testable instead of only
    observable at midnight and at 18:25.
    """
    now = now or datetime.now(TZ)
    today = now.date()
    raw_tasks = payload.get("tasks") or []

    open_tasks = [
        t
        for t in raw_tasks
        if t.get("status", OPEN_STATUS) == OPEN_STATUS and (t.get("title") or "").strip()
    ]

    # The order arranged in the app, which the API does not give us.
    open_tasks.sort(key=lambda t: t.get("sortOrder", 0))

    tasks = []
    for t in open_tasks:
        when = _due(t)
        if when is None or when.date() != today:
            continue

        due = _clock_time(t)
        travel_min = _travel_minutes(t)
        at, note = _labels(due, travel_min, now)
        # Strip the tag so it reads "Dentist", not "Dentist #40m", and collapse
        # whitespace or a mid-title tag leaves a double space.
        title = re.sub(r"\s+", " ", TRAVEL_TAG.sub("", t["title"])).strip()
        tasks.append(
            Task(
                title=title or t["title"].strip(),
                at=at,
                note=note,
                due=due,
                travel_min=travel_min,
            )
        )

    return tasks[:limit], len(tasks)


def fetch(timeout: float = 20) -> dict:
    """Raw GET of the configured project's data. Raises on failure."""
    token = config.require("TICKTICK_ACCESS_TOKEN")
    project_id = config.require("TICKTICK_PROJECT_ID")

    response = requests.get(
        f"{API}/project/{project_id}/data",
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def get_todos(limit: int = 4) -> tuple[list[str], int]:
    """Tasks to display, cached. Empty only when there is nothing usable.

    An expired token looks like any other failure here, so we fall back to the
    last good list rather than blanking the column. That buys time to notice and
    re-authorise without the panel going wrong in the meantime.
    """
    fresh = cache.load(CACHE_KEY, max_age=MIN_POLL)
    if fresh is not None:
        return parse(fresh, limit=limit)

    try:
        payload = fetch()
        cache.save(CACHE_KEY, payload)
        return parse(payload, limit=limit)
    except Exception:
        stale = cache.load(CACHE_KEY, max_age=MAX_STALE)
        if stale is not None:
            return parse(stale, limit=limit)
        return [], 0
