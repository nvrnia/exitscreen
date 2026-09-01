"""Compose the whole 1200x825 frame.

build_frame() is pure: data in, PIL image out. It imports nothing
platform-specific, so it runs identically on the laptop and on the Pi. The panel
driver never appears here - that is the other half, in eink.py / display.py.

Four bands inside a hairline frame: top bar, boxed art, decision row, footer.

Every piece of text is placed on a **baseline** from theme.py's grid, using
anchor="ls" (left, baseline). Nothing here computes its own vertical position, so
the three columns line up with each other and with the bands above and below.
"""

from __future__ import annotations

from datetime import date, datetime

from PIL import Image, ImageDraw

from . import art as art_module
from . import icons
from . import theme as T
from .models import Departure, FrameData, Task, Weather

MISSING = "–"  # en dash, shown when a feed is down

# Column headings, in one place so they stay consistent
LABEL_METRO = "METRO"
LABEL_COMMUTE = "TO UNI"
LABEL_WEATHER = "WEATHER"
LABEL_TODO = "TO DO"



# --- helpers -------------------------------------------------------------


def _fit(draw, text: str, font, max_width: float) -> str:
    """Truncate with an ellipsis so long text cannot run past its column."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    while text and draw.textlength(text + ellipsis, font=font) > max_width:
        text = text[:-1]
    return text.rstrip() + ellipsis


def _fit_tracked(draw, text: str, font, tracking: float, max_width: float) -> str:
    """_fit, but for text that will be drawn letter-spaced.

    _fit measures with textlength(), which knows nothing about tracking. The
    caption is drawn with draw_tracked_right() at 1.2px per character, so over a
    long artist-and-title that is ~70px of width nobody accounted for - which is
    exactly how the caption ended up printed over the date.
    """
    if T.tracked_width(draw, text, font, tracking) <= max_width:
        return text
    ellipsis = "…"
    while text and T.tracked_width(draw, text + ellipsis, font, tracking) > max_width:
        text = text[:-1]
    return text.rstrip() + ellipsis


def _text(d, x, baseline, string, font, fill=T.BLACK):
    """Draw a single line on a baseline."""
    d.text((x, baseline), string, font=font, fill=fill, anchor="ls")


def _outline(d, box, radius: int, fill=T.DIVIDER):
    """A hairline rectangle, rounded when the theme asks for it."""
    if radius > 0:
        d.rounded_rectangle(box, radius=radius, outline=fill, width=1)
    else:
        d.rectangle(box, outline=fill, width=1)


def _corner_mask(width: int, height: int, radius: int) -> Image.Image | None:
    """A paste mask that rounds an image's corners. None means leave it square.

    Anti-aliased, so the curve does not read as a staircase once the frame is
    quantised to 16 greys.
    """
    if radius <= 0:
        return None
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, width - 1, height - 1], radius=radius, fill=255
    )
    return mask


def _supports_dash() -> bool:
    """%-d is glibc-only; Windows needs the manual form."""
    try:
        date(2026, 7, 5).strftime("%-d")
        return True
    except ValueError:
        return False


def _date_label(day: date) -> str:
    if _supports_dash():
        return f"{day:%a %-d %B}".upper()
    return f"{day:%a} {day.day} {day:%B}".upper()


# --- bands ---------------------------------------------------------------


def _draw_topbar(d, f, data):
    """Date, top-left, flush with the art box and nameplate below it.

    Deliberately no clock - see the refresh decisions in BACKLOG.md.
    """
    T.draw_tracked(
        d,
        (T.MARGIN_X, T.TOPBAR_BASE),
        _date_label(data.day),
        f.topbar,
        T.TOPBAR_TRACKING,
        T.FURNITURE_INK,
    )


def _draw_caption_topbar(d, f, data):
    """Artist and title, right-aligned in the top bar's empty half.

    Costs no space and never covers the artwork. Truncated against the date's
    right edge so a long title can never collide with it.
    """
    if not data.artwork:
        return
    date_width = T.tracked_width(d, _date_label(data.day), f.topbar,
                                 T.TOPBAR_TRACKING)
    available = T.CONTENT_RIGHT - (T.MARGIN_X + date_width + 40)
    text = _fit_tracked(d, data.artwork.label.upper(), f.caption,
                        T.CAPTION_TRACKING, available)
    T.draw_tracked_right(d, T.CONTENT_RIGHT, T.TOPBAR_BASE, text, f.caption,
                         T.CAPTION_TRACKING, T.MUTED)


def _draw_metro(d, f, data, x=None, right=None):
    if x is None:
        x, right = T.column(0)

    T.draw_tracked(d, (x, T.LABEL_BASE), LABEL_METRO, f.label, T.LABEL_TRACKING, T.FURNITURE_INK)

    if not data.departures:
        _text(d, x, T.HERO_BASE, MISSING, f.big)
        # "no departures" and "feed unavailable" are different facts. The first
        # says stay in; the second says check your phone. Showing the former when
        # we mean the latter is the more dangerous mistake on a door.
        _text(d, x, T.METRO_LINE_2,
              "feed unavailable" if data.metro_unavailable else "no departures",
              f.meta, T.MUTED)
        return

    from . import metro as metro_module

    first = data.departures[0]
    _text(d, x, T.HERO_BASE, first.clock, f.big)

    def route(baseline, departure, start_x, prefix=""):
        """line + arrow + destination on one line, optionally time-prefixed."""
        cursor = start_x
        if prefix:
            _text(d, cursor, baseline, prefix, f.meta, T.MUTED)
            cursor += d.textlength(prefix, font=f.meta)
        _text(d, cursor, baseline, departure.line, f.meta, T.MUTED)
        cursor += d.textlength(departure.line, font=f.meta)
        icons.arrow(d, cursor + 9, baseline - 6, length=13, bearing=90)
        cursor += 29
        name = metro_module.short_destination(departure.destination)
        _text(d, cursor, baseline, _fit(d, name, f.meta, right - cursor), f.meta,
              T.MUTED)

    # The first departure's route sits BESIDE the big time rather than under it.
    # Both share the hero baseline, which is what makes a 70px numeral and a 21px
    # line look deliberately set rather than accidentally adjacent - and it frees
    # a whole line lower down for the commute.
    route(T.HERO_BASE, first, x + d.textlength(first.clock, font=f.big) + 18)

    # Both departures carry their own destination: D and E alternate here and go
    # to different cities, so a bare "then 15:31" cannot be acted on.
    if len(data.departures) > 1:
        route(T.METRO_LINE_1, data.departures[1], x,
              prefix=f"{data.departures[1].clock}   ")

    # The commute takes the line the second departure used to occupy.
    if data.commute is not None:
        c = data.commute
        metro_at = c.metro_departs or c.metro_deadline
        _text(d, x, T.METRO_LINE_2,
              _fit(d, f"metro {metro_at} · bus {c.bus_departs}", f.meta, right - x),
              f.meta, T.MUTED)


def _draw_weather(d, f, data, x=None, right=None):
    if x is None:
        x, right = T.column(1)
    w = data.weather

    T.draw_tracked(d, (x, T.LABEL_BASE), LABEL_WEATHER, f.label, T.LABEL_TRACKING, T.FURNITURE_INK)

    if w is None:
        _text(d, x, T.HERO_BASE, MISSING, f.temp)
        return

    if w.temp_c is None:
        _text(d, x, T.HERO_BASE, MISSING, f.temp)
        cursor = x + d.textlength(MISSING, font=f.temp)
    else:
        digits = f"{round(w.temp_c)}"
        _text(d, x, T.HERO_BASE, digits, f.temp)
        cursor = x + d.textlength(digits, font=f.temp)
        # Raise the degree sign to the digits' cap line rather than their baseline.
        cap = d.textbbox((0, 0), "0", font=f.temp, anchor="ls")[1]
        deg_cap = d.textbbox((0, 0), "°", font=f.degree, anchor="ls")[1]
        _text(d, cursor + 2, T.HERO_BASE + (cap - deg_cap), "°", f.degree)
        cursor += 2 + d.textlength("°", font=f.degree)

    if w.temp_max_c is not None:
        # Drawn, not typed: not every typeface carries a right-arrow glyph, and a
        # missing one renders as an empty box. Same reasoning as the icons - and
        # it frees the typeface choice from glyph coverage.
        icons.arrow(d, cursor + 14, T.HERO_BASE - 7, length=14, bearing=90)
        _text(d, cursor + 36, T.HERO_BASE, f"{round(w.temp_max_c)}°", f.small, T.MUTED)

    # Fixed position and size in both states - see WEATHER_ICON_* in theme.py.
    icons.draw_weather(
        d,
        right - T.WEATHER_ICON_SIZE,
        T.WEATHER_ICON_TOP,
        T.WEATHER_ICON_SIZE,
        w.wmo,
        w.umbrella,
    )

    if w.show_bars:
        _draw_rain_bars(d, x, T.BARS_TOP, w.rain_hours)
        if w.first_rain_at:
            # An umbrella is useless in a blow, so the advice changes rather than
            # stubbornly recommending one.
            advice = "take a coat" if w.blustery else "take umbrella"
            _text(
                d,
                x,
                T.WEATHER_LINE_1,
                _fit(d, f"Rain {w.first_rain_at} — {advice}", f.small, right - x),
                f.small,
                T.MUTED,
            )
    if w.blustery:
        gust = f" · gusts {round(w.gust_kmh)}" if w.gust_kmh else ""
        _text(
            d,
            x,
            T.WEATHER_LINE_2,
            _fit(d, f"wind {w.beaufort}{gust}", f.small, right - x),
            f.small,
            T.MUTED,
        )


def _draw_rain_bars(d, x, y, hours, bar_w=13, gap=5):
    """Precipitation probability as a small bar chart. 100% fills the height."""
    for i, prob in enumerate(hours):
        prob = max(0, min(100, prob or 0))
        h = max(2, round(T.BARS_H * prob / 100))
        bx = x + i * (bar_w + gap)
        # Faint bars read as noise on e-ink, so low values stay grey.
        fill = T.BLACK if prob >= 40 else T.MUTED
        d.rectangle([bx, y + T.BARS_H - h, bx + bar_w, y + T.BARS_H], fill=fill)


def _draw_todo(img, d, f, data, x=None, right=None):
    if x is None:
        x, right = T.column(2)

    T.draw_tracked(d, (x, T.LABEL_BASE), LABEL_TODO, f.label, T.LABEL_TRACKING, T.FURNITURE_INK)

    if not data.todos:
        _text(d, x, T.TODO_FIRST_BASE, "nothing to do", f.todo, T.MUTED)
        return

    # A drawn circle instead of an em-dash: no dependence on a face's dash width,
    # and it reads as an unticked box without the hard edges of one.
    radius = 10  # sized to hold a check mark rather than read as a bullet
    stroke = 2.5  # fractional, via supersampling in icons.bullet
    gap = radius * 2 + 14

    # Reserve the overflow row when the list might not fit whole. Notes are the
    # new reason it might: they are what makes the renderer drop a task the
    # fetcher had already handed over, which data.overflow cannot know about.
    may_truncate = data.overflow or any(t.note for t in data.todos)
    limit = T.TODO_OVERFLOW_BASE - (T.TODO_STEP if may_truncate else 0)

    drawn = 0
    baseline = T.TODO_FIRST_BASE
    for task in data.todos:
        # Look ahead at the note as well as the task. Testing the task alone
        # would let a "leave by" line be orphaned below the fold - or worse,
        # drawn over "+N more".
        note = task.note
        needed = baseline + (T.TODO_NOTE_OFFSET if note else 0)
        if needed > limit:
            break

        # Sit the circle on the text's optical centre, not its baseline.
        icons.bullet(img, x + radius, baseline - 8, radius, T.BLACK, stroke)

        # The inline time is reserved *before* the title is fitted. Appending it
        # and truncating the whole string would cut the time off the end - the one
        # part that has to survive.
        suffix = f"{T.TODO_TIME_SEP}{task.at}" if task.at else ""
        suffix_w = d.textlength(suffix, font=f.todo) if suffix else 0

        title = _fit(d, task.title, f.todo, right - x - gap - suffix_w)
        _text(d, x + gap, baseline, title, f.todo)
        if suffix:
            # Grey, so the title stays the thing you read first.
            _text(d, x + gap + d.textlength(title, font=f.todo), baseline,
                  suffix, f.todo, T.MUTED)

        if note:
            # Indented to the title, not to the circle: the note belongs to the
            # task's text, and hanging it under the circle would read as a
            # second, unticked item.
            note_base = baseline + T.TODO_NOTE_OFFSET
            _text(d, x + gap, note_base,
                  _fit(d, note, f.todo_note, right - x - gap), f.todo_note, T.MUTED)
            baseline = note_base + T.TODO_STEP_AFTER_NOTE
        else:
            baseline += T.TODO_STEP
        drawn += 1

    # Counted from what was actually drawn, not from what was fetched. Those
    # differ whenever a note pushes a task off the bottom, and "+1 more" under a
    # list that silently swallowed two is a quiet lie.
    remaining = (data.todo_total or len(data.todos)) - drawn
    if remaining > 0:
        _text(d, x, min(baseline, T.TODO_OVERFLOW_BASE),
              f"+{remaining} more", f.small, T.MUTED)


def _draw_footer(d, f, data):
    """Nameplate bottom-left, data freshness bottom-right."""
    # The nameplate is a heading like METRO and TODAY, so it takes the main face;
    # the freshness stamp is metadata and stays with the supporting one.
    T.draw_tracked(
        d,
        (T.MARGIN_X, T.FOOTER_BASE),
        "our exit screen",
        f.nameplate,
        T.NAMEPLATE_TRACKING,
        T.NAMEPLATE_INK,
    )

    if data.fetched_at is not None:
        T.draw_tracked_right(
            d,
            T.CONTENT_RIGHT,
            T.FOOTER_BASE,
            f"updated {data.fetched_at:%H:%M}",
            f.stamp,
            0.8,
            T.MUTED,
        )


# --- frame ---------------------------------------------------------------


def build_frame(
    data: FrameData | None = None,
    art: Image.Image | None = None,
    fonts: T.Fonts | None = None,
) -> Image.Image:
    """Return the composed frame as a mode-'L' image, ready for eink.py."""
    data = data or FrameData()
    f = fonts or T.Fonts()

    img = Image.new("L", (T.WIDTH, T.HEIGHT), T.PAPER)
    d = ImageDraw.Draw(img)

    # art, filling its box. Masked to the same radius as its border, or the
    # painting's square corners would poke out past a rounded one.
    if art is None:
        art = art_module.placeholder(T.ART_W, T.ART_H)
    if art.mode != "L":
        art = art.convert("L")
    if art.size != (T.ART_W, T.ART_H):
        art = art.resize((T.ART_W, T.ART_H), Image.LANCZOS)
    img.paste(art, (T.ART_LEFT, T.ART_TOP), _corner_mask(T.ART_W, T.ART_H,
                                                         T.ART_RADIUS))

    # the plate, and a crisp border around the art drawn over it
    _outline(d, [T.FRAME_LEFT, T.FRAME_TOP, T.FRAME_RIGHT, T.FRAME_BOTTOM],
             T.FRAME_RADIUS)
    _outline(d, [T.ART_LEFT - 1, T.ART_TOP - 1, T.ART_RIGHT, T.ART_BOTTOM],
             T.ART_RADIUS)

    _draw_topbar(d, f, data)
    _draw_caption_topbar(d, f, data)

    edges = T.columns(False)

    # rules above the decision row and above the footer
    for y in (T.DECISION_TOP, T.FOOTER_TOP):
        d.line([(T.CONTENT_LEFT, y), (T.CONTENT_RIGHT, y)], fill=T.DIVIDER, width=1)

    # Column dividers, inset from the rules so they do not form hard corners.
    # Driven by `edges`, not COL_EDGES, or a four-column day would draw its
    # dividers in the three-column positions.
    for x in edges[1:-1]:
        d.line(
            [(x, T.DECISION_TOP + 16), (x, T.FOOTER_TOP - 16)],
            fill=T.DIVIDER,
            width=1,
        )

    _draw_metro(d, f, data)
    _draw_weather(d, f, data)
    _draw_todo(img, d, f, data)
    _draw_footer(d, f, data)

    return img


def sample_data() -> FrameData:
    """Representative data for layout work with no network."""
    return FrameData(
        day=date(2026, 7, 26),
        fetched_at=datetime(2026, 7, 26, 8, 4),
        departures=[
            Departure(datetime(2026, 7, 26, 8, 14), "D", "the interchange"),
            Departure(datetime(2026, 7, 26, 8, 21), "E", "the far terminus"),
        ],
        weather=Weather(
            temp_c=20.4,
            temp_max_c=23.1,
            wmo=61,
            wind_kmh=44,
            gust_kmh=61,
            beaufort=6,
            blustery=True,
            umbrella=True,
            rain_hours=[5, 10, 25, 80, 55, 15, 8, 4],
            first_rain_at="15:00",
        ),
        # One timed-and-tagged task, one timed-but-untagged, two plain - so the
        # preview exercises every note state without a live TickTick connection.
        todos=[
            Task("Dentist", at="19:00", note="leave by 18:25"),
            Task("Pick up parcel"),
            Task("Ring Mum", at="20:30"),
            Task("Call landlord about the boiler"),
        ],
        todo_total=6,
    )
