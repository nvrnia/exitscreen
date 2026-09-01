"""The shapes passed between the data blocks and the renderer.

Kept in their own module so metro.py / weather.py / todo.py and frame.py can all
share them without importing each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class Departure:
    when: datetime  # absolute departure time - what actually gets displayed
    line: str
    destination: str
    minutes: int = 0  # kept for logging and any future "in N min" use

    @property
    def clock(self) -> str:
        return self.when.strftime("%H:%M")


@dataclass
class Weather:
    temp_c: float | None
    wmo: int
    wind_kmh: float
    temp_max_c: float | None = None  # today's high, for the "-> 23 deg" trend
    gust_kmh: float | None = None
    beaufort: int = 0
    umbrella: bool = False
    # Wind worth mentioning at all - either sustained force or gusts. Decided in
    # weather.py so the thresholds live with the rest of the weather rules.
    blustery: bool = False
    # Next few hours of precipitation probability, for the bar chart. Empty when
    # no rain is expected today - which is itself the signal to hide the bars.
    rain_hours: list[int] = field(default_factory=list)
    first_rain_at: str | None = None  # "15:00"

    @property
    def show_bars(self) -> bool:
        return bool(self.rain_hours)


@dataclass
class Task:
    """One to-do line, with two optional pieces of timing hung off it.

    The two are deliberately separate, because they are worth different amounts
    of space:

      `at`   the appointment time, drawn *inline* after the title. It is a fact
             TickTick handed us, so it is cheap and costs no vertical space.
      `note` a leave-by deadline, drawn on its own second line. It is the only
             thing here we worked out, and the only thing that changes what you
             do, so it earns a row of its own.

    Spending a row on a bare time was the first attempt, and it halved how many
    tasks fit for no gain.

    Both are finished display strings rather than raw timing, decided in todo.py.
    That keeps frame.py from needing any notion of "now" - which it deliberately
    does not have - and follows the same split as Weather.umbrella and
    Weather.first_rain_at above.
    """

    title: str  # any "#40m" travel tag already stripped
    at: str | None = None  # "19:00", inline after the title
    note: str | None = None  # "leave by 18:25", its own line beneath
    due: datetime | None = None  # tz-aware; None means no clock time
    travel_min: int | None = None  # door-to-door minutes, from the tag

    @property
    def leave_at(self) -> datetime | None:
        """When to walk out of the front door, or None if unknowable."""
        if self.due is None or self.travel_min is None:
            return None
        return self.due - timedelta(minutes=self.travel_min)


@dataclass
class Artwork:
    """The daily artwork's label. Kept separate from the image itself so
    frame.py never has to know where either came from."""

    title: str
    artist: str = ""
    date: str = ""

    @property
    def label(self) -> str:
        """One line: artist first, since that is what you recognise."""
        parts = [p for p in (self.artist, self.title) if p and p != "?"]
        return " · ".join(parts)


@dataclass
class FrameData:
    """Everything the frame needs. Any field may be absent - a dead feed should
    cost you one column, never the whole screen."""

    day: date = field(default_factory=date.today)
    # When the data was fetched, NOT when the frame was rendered. The footer
    # stamp shows this so an unchanged frame hashes identically and the push
    # guard can skip it. Rendering now() here would defeat the whole mechanism.
    fetched_at: datetime | None = None
    departures: list[Departure] = field(default_factory=list)
    # True when the metro feed could not be reached at all, as opposed to
    # answering with nothing. The column says so rather than showing a dash that
    # reads as "no trains".
    metro_unavailable: bool = False
    # Today's journey to class, or None on a free day / outside term. Built in
    # commute.py so frame.py stays a renderer.
    commute: object | None = None
    weather: Weather | None = None
    todos: list[Task] = field(default_factory=list)
    todo_total: int = 0  # for "+N more"; 0 means "same as len(todos)"
    artwork: Artwork | None = None

    @property
    def overflow(self) -> int:
        return max(0, self.todo_total - len(self.todos))
