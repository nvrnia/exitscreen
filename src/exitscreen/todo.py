"""Open tasks from one TickTick list.

Verified against the live API on 2026-07-27:
  - `GET /open/v1/project/{id}/data` returns {project, tasks, columns}.
  - **Completed tasks are absent from the response entirely.** Ticking a task off
    in the app removes it from this payload, so there is no completion filter to
    get backwards. The status check below is defensive only.
  - `status` is 0 on open tasks.
  - `sortOrder` is a large negative integer, ascending in the user's own order,
    and the API does **not** return tasks sorted by it. Without an explicit sort
    the list appears shuffled on the panel.
  - Useful fields present: title, status, sortOrder, dueDate, startDate,
    isAllDay, priority, tags, projectId, id.
  - `tags` is **absent entirely** on a task with no tags, so it needs a default.
  - The access token lasts ~180 days and **no refresh_token is issued**, so
    re-running tools/ticktick_auth.py is the recovery path when it expires.

There is no "all tasks" endpoint in this API - you must name a project. That is
why the design uses a single dedicated list.

**dueDate timezones, verified 2026-07-30.** The offset is honest UTC, not local
wall time wearing a +0000 badge. An all-day task due 27 July came back as
`2026-07-26T22:00:00.000+0000`, and 22:00 UTC is midnight Amsterdam on the 27th
in summer - which is only true if the offset means what it says. A cosmetic
offset would have given `2026-07-27T00:00:00.000+0000` instead.

The consequence is a trap: that value's *naive* date is 26 July, the wrong day.
Always convert to Europe/Amsterdam before reading a date or an hour off it. The
separate `timeZone` field is the user's own zone and is not needed for this.
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
MIN_POLL = 900  # 15 minutes; TickTick has no webhooks so we poll
MAX_STALE = 24 * 3600  # a day-old task list still beats an empty column

OPEN_STATUS = 0

TZ = ZoneInfo("Europe/Amsterdam")

# How long the journey takes, front door to being there: "Dentist #40m".
#
# The leading # is required. Without it "Buy 2m of rope" would claim a two-minute
# journey, and a wrong leave time looks exactly as authoritative as a right one.
TRAVEL_TAG = re.compile(r"#(\d{1,3})\s*m\b", re.IGNORECASE)

# The same shape as a real TickTick tag, for when the app lifts "#40m" out of the
# title and into `tags` instead of leaving it in the text. Which of the two
# happens is unverified, so both are accepted - it costs one branch.
TRAVEL_TAG_ONLY = re.compile(r"^(\d{1,3})\s*m$", re.IGNORECASE)


def _parse_due(task: dict) -> datetime | None:
    """The task's clock time in Amsterdam, or None if it has none.

    All-day tasks return None: "buy bread today" has no time to leave for. See
    the module docstring for why the conversion is not optional.
    """
    if task.get("isAllDay"):
        return None

    raw = task.get("dueDate") or task.get("startDate")
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return None


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

    The appointment time is always shown when there is one - it is free, it sits
    beside the title, and it lets you sanity-check the leave time next to it.

    The leave-by line only appears while it is still achievable. A stale
    "leave by 08:20" at 11:00 is worse than nothing: it is noise that teaches you
    to ignore the live ones. Once it passes, the task keeps its time and loses
    its deadline.
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
    """Return (tasks to show, total open count).

    The total drives the "+N more" line, so it counts every open task rather
    than only the ones that fit.

    `now` is a parameter rather than read inside, mirroring metro.parse() - it
    makes the leave-by boundary testable instead of only observable at 18:25.
    """
    now = now or datetime.now(TZ)
    raw_tasks = payload.get("tasks") or []

    open_tasks = [
        t
        for t in raw_tasks
        if t.get("status", OPEN_STATUS) == OPEN_STATUS and (t.get("title") or "").strip()
    ]

    # Respect the order the user arranged in the app - least surprising for them,
    # and the API's own ordering is not it.
    open_tasks.sort(key=lambda t: t.get("sortOrder", 0))

    tasks = []
    for t in open_tasks:
        due = _parse_due(t)
        travel_min = _travel_minutes(t)
        at, note = _labels(due, travel_min, now)
        # Strip the tag so the panel reads "Dentist", not "Dentist #40m".
        # Collapse whitespace too, or a mid-title tag leaves a double space.
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

    An expired token looks like any other failure here: we fall back to the last
    good list rather than blanking the column, which buys time to notice and
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
