"""Geometry, greys and fonts for the 1200x825 panel.

Everything tunable about the layout lives here so frame.py can stay about
arrangement.

Vertical positions are baselines, not top edges. It is the only way to get
different sizes to line up by eye: anchor a 76px number and a 56px number by
their em boxes and they look wrong even when the boxes agree. Move a constant
here and everything sitting on that line moves with it.
"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageFont

# --- panel ---------------------------------------------------------------

WIDTH, HEIGHT = 1200, 825

# The IT8951 gives 16 greys, all multiples of 17. Everything below snaps to one,
# so the preview cannot promise a tone the panel would quantise away.
PAPER = 255
BLACK = 0
MUTED = 102
DIVIDER = 153

# --- frame ---------------------------------------------------------------

FRAME_INSET = 14
# A rounded corner eats the margin diagonally, so corner text has to come in on
# both axes. Widening this alone stops paying: at radius 48, padding 27 -> 34
# only bought 14.2 -> 17.3px, because the date's distance from the top edge was
# what actually bound. Pulling TOPBAR_BASE and FOOTER_BASE in got about 21px for
# a third of the horizontal cost.
FRAME_PAD = 30

FRAME_LEFT = FRAME_INSET  # 14
FRAME_TOP = FRAME_INSET  # 14
FRAME_RIGHT = WIDTH - FRAME_INSET  # 1186
FRAME_BOTTOM = HEIGHT - FRAME_INSET  # 811

CONTENT_LEFT = FRAME_LEFT + FRAME_PAD  # 38
CONTENT_RIGHT = FRAME_RIGHT - FRAME_PAD  # 1162
MARGIN_X = CONTENT_LEFT

# Rounded to match the bezel. 0 goes back to sharp. The art box stays square:
# rounding it bit a visible chunk out of each corner of the painting.
FRAME_RADIUS = 48
ART_RADIUS = 0

# --- vertical bands ------------------------------------------------------
#   14   top bar     44 tall, baseline 44
#   58   gap         10
#   68   art        450 tall
#  518   gap         12
#  530   rule + decision row  229
#  759   rule + footer         52
#  811   frame bottom
#
# The art gave up 20px to the decision row. At 209 the row could not hold a 76px
# clock plus two lines under it without descenders colliding.

TOPBAR_TOP = 14
TOPBAR_H = 50
# 56 not 50. The rounded corner cuts this band diagonally, and the date sitting
# 19px below the frame edge was what made the corner look crowded. All caps and
# digits, so no descenders to hit the art box.
TOPBAR_BASE = 56

# 74 not 68, so the date is not pinned against the art.
ART_TOP = 74
ART_BOTTOM = 518
ART_H = ART_BOTTOM - ART_TOP  # 450
ART_LEFT = CONTENT_LEFT
ART_RIGHT = CONTENT_RIGHT
ART_W = ART_RIGHT - ART_LEFT  # 1136

DECISION_TOP = 530  # the rule sits on this line
FOOTER_TOP = 759  # and on this one

# Same reasoning as TOPBAR_BASE, at the other two corners.
FOOTER_BASE = 786

# --- baselines inside the decision row -----------------------------------
# Only two lines are shared across columns: the labels, and the hero line the
# clock and temperature both sit on. Below those each column keeps its own
# rhythm. Forcing one grid on all three is what crushed the spacing, because
# weather has a bar chart where the others have text.
#
# Gaps are measured by eye, cap-top to the previous descender, which is why the
# numbers are not round.

# Puts the metro column optically between the two rules instead of hugging the
# top. Was 16 above and 39 below, now about 28 and 27.
ROW_TOP = DECISION_TOP + 27  # 557

LABEL_BASE = ROW_TOP + 16  # 573
HERO_BASE = ROW_TOP + 90  # 647  clock and temperature share this

METRO_LINE_1 = ROW_TOP + 131  # 688
METRO_LINE_2 = ROW_TOP + 169  # 726

# Sits where metro's hero and first line are, so the columns still share a beat.
COMMUTE_LINE_1 = ROW_TOP + 62
COMMUTE_LINE_2 = ROW_TOP + 100
COMMUTE_TIME_X = 62  # both times align in a column

# The icon keeps its size and place wet or dry. It used to grow and shift left
# on a dry day to fill the space the bars left, but the eye should always find
# it in the same corner.
WEATHER_ICON_SIZE = 40
WEATHER_ICON_TOP = ROW_TOP + 45  # 602

BARS_TOP = ROW_TOP + 104  # 661
# 22 not 26. Bars are bottom-aligned, so a full-height one came within 13px of
# the text below, against 23-26 everywhere else. Four pixels of chart for an
# even gap.
BARS_H = 22
WEATHER_LINE_1 = ROW_TOP + 160  # 717
WEATHER_LINE_2 = ROW_TOP + 186  # 743
# Lines are drawn one after another from WEATHER_LINE_1, not at fixed slots. A
# dry but windy day used to leave a hole where the rain line would have been.
WEATHER_LINE_STEP = WEATHER_LINE_2 - WEATHER_LINE_1  # 26

TODO_FIRST_BASE = ROW_TOP + 54  # 611
TODO_STEP = 33
# Ceiling for "+N more". It normally follows the last task, which stops it being
# stranded halfway down a short list.
TODO_OVERFLOW_BASE = ROW_TOP + 186  # 743

# A leave-by deadline gets its own line; a bare appointment time goes inline
# after the title, because spending a whole row on a time TickTick already gave
# us halved the visible list for nothing.
#
# The uneven spacing is the point: 26px inside a task-and-note pair against 38
# between pairs, so the note reads as belonging to its task. At a flat 33 it
# looked like another task. 22 was too tight, only 6px of white.
TODO_NOTE_OFFSET = 26
TODO_STEP_AFTER_NOTE = 38

# Wide and unpunctuated. A comma or dash would read as part of the task.
TODO_TIME_SEP = "   "

# Between stamp (19) and small (21): has to recede under a 23px task line
# without turning into fine print.
TODO_NOTE_SIZE = 20

# --- artwork caption -----------------------------------------------------
# Artist and title, right-aligned in the empty half of the top bar. Costs no
# space and never covers the painting.
#
# The alternative was a small wall label inside the art's bottom corner. It was
# built and compared, and it lost: it covers part of the painting and needs an
# opaque background to stay readable over a busy sky.
CAPTION_SIZE = 17
CAPTION_TRACKING = 1.2

# Landscapes usually put the horizon above centre, so bias the crop upward.
ART_CROP_CENTRING = (0.5, 0.45)

# Paintings rarely use the full range. An oil might span greys 60-190, and
# squeezing that into 16 levels wastes most of them, which is why an untouched
# painting looks muddy here. Stretching first gives the 16 levels something to
# work with. The cutoff ignores that percentage at each end so one highlight
# cannot anchor the whole stretch.
ART_AUTOCONTRAST_CUTOFF = 2

# Applied after the stretch, 1.0 is off. Off by default: on a work that already
# has range it blows highlights white and shadows black.
ART_CONTRAST_BOOST = 1.0

# Only works flatter than this get touched, measured as the standard deviation
# of their greys. A blanket stretch wrecks paintings that are dark or pale on
# purpose. Below about 45 a work is genuinely muddy rather than quiet.
ART_FLAT_THRESHOLD = 45

# --- columns -------------------------------------------------------------
# Three columns, 1.1 / 1 / 1.2. Todo gets the most because it holds wrapping
# text, weather the least.
#
# The outer columns carry no inner padding, so METRO lines up with the date
# above and the nameplate below, and the last column ends flush right. Padding
# only applies where two columns meet.
#
# Derived rather than hardcoded, so changing FRAME_PAD reflows the columns.
COL_RATIOS = (1.1, 1.0, 1.2)

# On a class day the commute gets its own narrow column and METRO keeps both
# departures. Folding the bus into METRO was tried and dropped: it pushed out
# the second departure, which is still wanted.
COL_RATIOS_WITH_BUS = (1.05, 0.62, 0.95, 1.08)

COL_GUTTER = 22


def _col_edges(ratios=None) -> tuple[int, ...]:
    ratios = ratios or COL_RATIOS
    span = CONTENT_RIGHT - CONTENT_LEFT
    scale = span / sum(ratios)
    edges = [CONTENT_LEFT]
    for ratio in ratios[:-1]:
        edges.append(round(edges[-1] + ratio * scale))
    edges.append(CONTENT_RIGHT)
    return tuple(edges)


COL_EDGES = _col_edges()


def columns(with_bus: bool) -> tuple[int, ...]:
    """Column edges for the layout actually being drawn."""
    return _col_edges(COL_RATIOS_WITH_BUS if with_bus else COL_RATIOS)


def column_at(edges: tuple[int, ...], index: int) -> tuple[int, int]:
    """Left and right x for one column of a given edge set."""
    left = edges[index] + (0 if index == 0 else COL_GUTTER)
    right = edges[index + 1] - (0 if index == len(edges) - 2 else COL_GUTTER)
    return left, right


def column(index: int) -> tuple[int, int]:
    """Left and right x for one decision column's content."""
    left = COL_EDGES[index] + (0 if index == 0 else COL_GUTTER)
    right = COL_EDGES[index + 1] - (0 if index == len(COL_EDGES) - 2 else COL_GUTTER)
    return left, right


# --- fonts ---------------------------------------------------------------

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

# Two faces, split by role: MAIN for headings and headline numbers, SUB for the
# details hung off them.
#
# Literata is a book serif drawn for e-reader screens, so it suits e-ink and
# gives the printed-plate feel. Setting everything in it was too much serif.
MAIN_FACE = "Literata[opsz,wght].ttf"

# Work Sans is humanist, drawn from the same calligraphic bones as a book serif,
# so it reads as a relative of Literata rather than a stranger.
#
# Two that were tried and dropped: Bricolage Grotesque had too many quirks of
# its own, so two characterful faces competed. Source Sans 3 meshed well but
# measured narrowest of eleven candidates, 266px on a sample task line against
# 306 here, which read as cramped.
SUB_FACE = "WorkSans[wght].ttf"


def _apply_axes(font: ImageFont.FreeTypeFont, **wanted: float) -> None:
    """Set variable-font axes by name, ignoring any this font lacks.

    Pillow wants one value per axis in the font's own order, which differs
    between families. Resolving by name keeps call sites out of it.
    """
    try:
        axes = font.get_variation_axes()
    except OSError:
        return  # static font, nothing to set

    values = []
    for axis in axes:
        name = axis["name"]
        if isinstance(name, bytes):
            name = name.decode()
        key = name.lower().replace(" ", "")
        value = wanted.get(key, axis["default"])
        values.append(max(axis["minimum"], min(axis["maximum"], value)))
    font.set_variation_by_axes(values)


def load(filename: str, size: int, **axes: float) -> ImageFont.FreeTypeFont:
    """Load a bundled font at a size, optionally setting variable axes.

    Axis names are lowercased with spaces removed: weight, opticalsize, width.
    """
    # BASIC layout is forced, not left to Pillow. The Pi has libraqm and the
    # Windows laptop does not, so the default shapes text differently on each
    # and the preview stops predicting the panel. Latin-only text loses nothing.
    font = ImageFont.truetype(
        str(FONT_DIR / filename), size, layout_engine=ImageFont.Layout.BASIC
    )
    if axes:
        _apply_axes(font, **axes)
    return font


# --- furniture styling ---------------------------------------------------
# The letterspaced caps that label the panel: date, column headings, nameplate.
# One treatment so they read as a set. Weight gives them presence, tracking
# gives narrow serif caps the width they cannot get otherwise.
#
# Optical size stays on the text cut rather than display. The display cut has
# finer detail, the opposite of what a low-contrast panel wants at 22px.

# Both hero numbers take one size, so the clock and the temperature are peers.
# At different sizes the smaller starts lower and leaves a wider gap under its
# heading: weather measured 31px against metro's 20.
#
# The degree sign is drawn separately and raised to the digits' cap line. At
# full size it swamps a two-character number.
HERO_SIZE = 70
DEGREE_SCALE = 0.55

FURNITURE_WEIGHT = 750
FURNITURE_INK = BLACK

TOPBAR_SIZE = 24
TOPBAR_TRACKING = 7.0

LABEL_SIZE = 22
LABEL_TRACKING = 7.0

# The nameplate is a signature, not a heading like METRO. It takes the
# supporting face and grey, matching the stamp opposite so the footer balances.
NAMEPLATE_SIZE = 19
NAMEPLATE_TRACKING = 1.6
NAMEPLATE_WEIGHT = 400
NAMEPLATE_INK = MUTED


class Fonts:
    """The loaded faces for one frame, by role.

    Built once per render. Variable-font instances carry their axis settings, so
    a Regular and a Bold from the same file have to be separate objects.
    """

    def __init__(self, main_face: str | None = None, sub_face: str | None = None):
        m = main_face or MAIN_FACE
        s = sub_face or SUB_FACE

        self.big = load(m, HERO_SIZE, weight=700)  # 15:28
        self.temp = load(m, HERO_SIZE, weight=700)  # 21
        self.degree = load(m, round(HERO_SIZE * DEGREE_SCALE), weight=700)
        self.topbar = load(m, TOPBAR_SIZE, weight=FURNITURE_WEIGHT)
        self.label = load(m, LABEL_SIZE, weight=FURNITURE_WEIGHT)
        self.nameplate = load(s, NAMEPLATE_SIZE, weight=NAMEPLATE_WEIGHT)

        self.then = load(s, 25, weight=400)  # then 14:38
        self.meta = load(s, 21, weight=400)  # E -> the interchange
        self.small = load(s, 21, weight=400)  # trend, wind, rain, +N more
        self.todo = load(s, 23, weight=400)  # task titles
        self.todo_note = load(s, TODO_NOTE_SIZE, weight=400)  # leave by 18:25
        self.stamp = load(s, 19, weight=400)  # updated 14:27

        self.caption = load(s, CAPTION_SIZE, weight=400)


# --- text helpers --------------------------------------------------------
# Pillow has no tracking parameter, so characters are advanced by hand. That
# also drops kerning, which is what spaced-out caps want anyway. All of these
# take a baseline y.


def tracked_width(draw, text: str, font, tracking: float) -> float:
    """Width of text drawn with per-character tracking."""
    if not text:
        return 0.0
    return sum(draw.textlength(c, font=font) for c in text) + tracking * (len(text) - 1)


def draw_tracked(draw, xy, text: str, font, tracking: float, fill=BLACK) -> None:
    """Draw letter-spaced text. xy is (left, baseline)."""
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill, anchor="ls")
        x += draw.textlength(char, font=font) + tracking


def draw_tracked_right(draw, right_x, baseline, text, font, tracking, fill=BLACK):
    """Right-aligned letter-spaced text, for the footer's freshness stamp."""
    width = tracked_width(draw, text, font, tracking)
    draw_tracked(draw, (right_x - width, baseline), text, font, tracking, fill)
