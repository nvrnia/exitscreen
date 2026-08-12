"""Geometry, greys and fonts for the 1200x825 panel.

Everything tunable about the layout lives here, so frame.py stays about
arrangement and this stays about measurements.

The vertical layout is a **baseline grid**, not a set of per-element offsets.
Text is positioned by where its baseline sits, which is the only way to get
different sizes to line up optically - anchoring by the top of the em box makes
a 76px number and a 56px number look misaligned even when their boxes agree.
Change a constant here and everything holding that line moves together.
"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageFont

# --- panel ---------------------------------------------------------------

WIDTH, HEIGHT = 1200, 825

# The IT8951 drives 16 grey levels - multiples of 17. Every grey below is snapped
# to one of them, so the preview cannot promise a tone the panel would quantise
# away.
PAPER = 255  # background
BLACK = 0  # primary text, the big numerals
MUTED = 102  # secondary text
DIVIDER = 153  # hairline rules

# --- frame ---------------------------------------------------------------
# A hairline border around the whole panel, like a printed plate.

FRAME_INSET = 14
# A rounded corner eats the margin *diagonally*, so the corner text needs to come
# in on both axes. Widening this alone hit diminishing returns - measured at a
# 48px radius, padding 27 -> 34 only moved the clearance 14.2 -> 17.3px, because
# the date's distance from the *top* edge was the binding constraint. Pulling the
# top bar and footer baselines inward as well got it to ~21px for a third of the
# horizontal cost. See TOPBAR_BASE and FOOTER_BASE.
FRAME_PAD = 30

FRAME_LEFT = FRAME_INSET  # 14
FRAME_TOP = FRAME_INSET  # 14
FRAME_RIGHT = WIDTH - FRAME_INSET  # 1186
FRAME_BOTTOM = HEIGHT - FRAME_INSET  # 811

CONTENT_LEFT = FRAME_LEFT + FRAME_PAD  # 38
CONTENT_RIGHT = FRAME_RIGHT - FRAME_PAD  # 1162
MARGIN_X = CONTENT_LEFT

# Rounded to match the physical bezel. Square corners inside a rounded surround
# read as a mistake rather than a choice. 0 goes back to sharp.
#
# The art box stays square on purpose: rounding it clipped a visible bite out of
# each corner of the painting, and a crisp rectangle reads like a print in a
# mount rather than a widget.
FRAME_RADIUS = 48
ART_RADIUS = 0

# --- vertical bands ------------------------------------------------------
# Stacked inside the frame with deliberate gaps between them:
#
#   14   top bar band      44 tall, baseline at 44
#   58   gap               10
#   68   art box          450 tall  (~55% of the panel)
#  518   gap               12
#  530   rule + decision row       229 tall
#  759   rule + footer band         52 tall, baseline at 792
#  811   frame bottom
#
# 44 + 10 + 450 + 12 + 229 + 52 = 797 = 811 - 14
#
# The art gave up 20px to the decision row: at 209px the row could not hold a
# 76px clock plus two lines under it without the descenders colliding.

TOPBAR_TOP = 14
TOPBAR_H = 50
# Baseline 56, not 50: the rounded corner cuts across this band diagonally, and
# the date sitting only 19px below the frame edge was what made the corner look
# crowded. 6px down buys ~5px of diagonal clearance - far more per pixel than
# widening FRAME_PAD does. The date is all caps and digits, so it has no
# descenders to collide with the art box.
TOPBAR_BASE = 56

# 74, not 68: follows the date down, so the top bar keeps roughly even gaps above
# and below it rather than pinning the date against the art.
ART_TOP = 74
ART_BOTTOM = 518
ART_H = ART_BOTTOM - ART_TOP  # 450
ART_LEFT = CONTENT_LEFT
ART_RIGHT = CONTENT_RIGHT
ART_W = ART_RIGHT - ART_LEFT  # 1136

DECISION_TOP = 530  # the rule sits on this line
FOOTER_TOP = 759  # and on this one

# 786, not 792: same reasoning as TOPBAR_BASE, at the other two corners. The
# nameplate and the freshness stamp both sit in a rounded corner's path.
FOOTER_BASE = 786

# --- baselines inside the decision row -----------------------------------
# The two lines that matter for cross-column alignment are shared: the column
# labels, and the "hero" line the clock and temperature both sit on. Below those,
# each column keeps its own rhythm - forcing one grid on all three was what
# crushed the spacing, because the weather column has a 30px bar chart where the
# others have a line of text.
#
# Gaps are measured optically (cap-top to previous descender), not by dividing
# the space evenly, which is why the numbers are not round.

# Offset chosen so the metro column - the one with a consistent three elements -
# sits optically centred between the two rules, rather than hugging the top.
# Measured: 16px above / 39px below before, ~28/~27 after.
ROW_TOP = DECISION_TOP + 27  # 557

LABEL_BASE = ROW_TOP + 16  # 573  METRO / WEATHER / TO DO
HERO_BASE = ROW_TOP + 90  # 647  the clock and the temperature share this

# metro: two lines of supporting text
METRO_LINE_1 = ROW_TOP + 131  # 688  "then 14:41"
METRO_LINE_2 = ROW_TOP + 169  # 726  "D -> the interchange"

# weather: bar chart, then two lines. Bars must clear the temperature's
# descenders, which is why the first text line sits lower than metro's.
# The weather icon sits in the same place at the same size whether or not it is
# raining. It used to grow and move left on a dry day to fill the space the bars
# vacated, but a glanceable display wants continuity more than it wants tidy
# space-filling - the eye should always find the icon in the same corner.
WEATHER_ICON_SIZE = 40
WEATHER_ICON_TOP = ROW_TOP + 45  # 602, optically centred on the hero line

BARS_TOP = ROW_TOP + 104  # 661
# 22, not 26: the bars are bottom-aligned, so a full-height bar reached to
# within 13px of the advice line beneath - against 23-26px everywhere else on
# the panel. Four pixels of chart resolution buys an even gap.
BARS_H = 22
WEATHER_LINE_1 = ROW_TOP + 160  # 717  "Rain now - take umbrella"
WEATHER_LINE_2 = ROW_TOP + 186  # 743  "wind 6 - gusts 61"

# todo: an even rhythm of its own, four tasks plus an overflow line
TODO_FIRST_BASE = ROW_TOP + 54  # 611
TODO_STEP = 33
# Cap for "+N more"; it normally follows the last task instead of
# sitting at a fixed line, which left it stranded on a short list.
TODO_OVERFLOW_BASE = ROW_TOP + 186  # 743

# A leave-by deadline gets its own line under the task. The bare appointment time
# does not - it goes inline after the title, since spending a whole row on a time
# TickTick already gave us halved the visible list for nothing.
#
# The asymmetry is the mechanism: 26px inside a task-and-note pair against 38px
# between pairs, so proximity groups the note with its task. At an even 33px it
# read as an unrelated extra task. 22 was too tight - spacing_audit measured only
# 6px of white, and the note's ascenders came up level with the line above.
TODO_NOTE_OFFSET = 26  # task baseline -> its own note's baseline
TODO_STEP_AFTER_NOTE = 38  # note baseline -> the next task's baseline

# Between the title and its inline time. Wide and unpunctuated: a comma or dash
# would read as part of the task's own text.
TODO_TIME_SEP = "   "

# Between stamp (19) and small (21): it has to recede under a 23px task line
# without becoming the fine print.
TODO_NOTE_SIZE = 20

# --- artwork caption -----------------------------------------------------
# Artist and title, right-aligned in the top bar's otherwise empty half. Costs no
# space and never covers the art.
#
# The rejected alternative was a "plaque": a small white wall-label inside the
# art's bottom-left corner. It was rendered and compared, and it lost because it
# covers a corner of the painting and needs an opaque background to stay legible
# over a busy sky. Its code is gone; it is in git history if it is ever wanted.
CAPTION_SIZE = 17
CAPTION_TRACKING = 1.2

# Landscapes usually carry their horizon above centre, so the crop is biased
# upward rather than taking the middle band.
ART_CROP_CENTRING = (0.5, 0.45)

# Paintings rarely use the full tonal range - an oil might span greys 60-190,
# and reducing that to 16 levels wastes most of them, which is why unprocessed
# paintings look flat and muddy on the panel. Stretching the histogram first
# gives the 16 levels something to work with.
#
# The cutoff ignores that percentage at each end, so one bright highlight or a
# single black shadow cannot anchor the whole stretch.
ART_AUTOCONTRAST_CUTOFF = 2

# Applied after the stretch. 1.0 is off. Left off by default: on a work that
# already has range it blows highlights to white and shadows to black, and it was
# what made an enhanced Vuillard read as texture rather than as a painting.
ART_CONTRAST_BOOST = 1.0

# Only works flatter than this get touched at all, measured as the standard
# deviation of their greys. A blanket stretch vandalises paintings that are dark
# or pale *on purpose* - Church's "Twilight in the Wilderness" would become
# afternoon. Below ~45 a work is genuinely muddy rather than deliberately quiet.
ART_FLAT_THRESHOLD = 45

# --- columns -------------------------------------------------------------
# Three columns in a 1.1 / 1 / 1.2 ratio. Todo gets the most room because it
# holds wrapping text; weather the least.
#
# Note the outer columns carry NO inner padding: the first column's text starts
# flush at CONTENT_LEFT so METRO lines up with the date above it and the
# nameplate below it, and the last column ends flush at CONTENT_RIGHT. Padding
# applies only where two columns meet.

# Derived rather than hardcoded, so changing FRAME_PAD (which the corner radius
# forces) reflows the columns instead of needing them recalculated by hand.
COL_RATIOS = (1.1, 1.0, 1.2)


def _col_edges() -> tuple[int, ...]:
    span = CONTENT_RIGHT - CONTENT_LEFT
    scale = span / sum(COL_RATIOS)
    edges = [CONTENT_LEFT]
    for ratio in COL_RATIOS[:-1]:
        edges.append(round(edges[-1] + ratio * scale))
    edges.append(CONTENT_RIGHT)
    return tuple(edges)


COL_EDGES = _col_edges()
COL_GUTTER = 22


def column(index: int) -> tuple[int, int]:
    """Left and right x for one decision column's content."""
    left = COL_EDGES[index] + (0 if index == 0 else COL_GUTTER)
    right = COL_EDGES[index + 1] - (0 if index == len(COL_EDGES) - 2 else COL_GUTTER)
    return left, right


# --- fonts ---------------------------------------------------------------

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

# Two faces, split by role rather than by category:
#   MAIN - headings and headline numbers. The panel's own structure.
#   SUB  - the details hung off that structure.
#
# Literata is a book serif commissioned for e-reader screens, which makes it an
# unusually good fit for e-ink, and it gives the printed-plate feel the art bible
# asks for. Setting everything in it was too much serif, so supporting text drops
# to a sans for contrast and hierarchy.
MAIN_FACE = "Literata[opsz,wght].ttf"

# Work Sans is a *humanist* sans - drawn from calligraphic skeletons, the same
# tradition a book serif comes from - so it shares Literata's bone structure and
# reads as a relative rather than a stranger.
#
# Two earlier attempts and why they were rejected:
#   Bricolage Grotesque - its own designed-in quirks, so two characterful faces
#     competed instead of one supporting the other.
#   Source Sans 3 - meshed well but measured the narrowest of eleven candidates
#     (266px on a sample task line, vs 306px here), which read as cramped.
#
# Neutrality is the point for this role. A generic sans would be wrong as the
# panel's primary voice, but supporting text is meant to recede.
SUB_FACE = "WorkSans[wght].ttf"


def _apply_axes(font: ImageFont.FreeTypeFont, **wanted: float) -> None:
    """Set variable-font axes by name, ignoring axes this font lacks.

    Pillow's set_variation_by_axes() wants one value per axis in the font's own
    order, which differs between families (Inter is opsz/wght, Plex is
    wght/wdth). Resolving by name keeps call sites from caring.
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
    # BASIC layout is forced rather than left to Pillow's default. The Pi has
    # libraqm installed (via python3-pil's dependencies) and the Windows laptop
    # does not, so the default would give the two machines different text
    # shaping - and the preview would quietly stop predicting the panel.
    # Latin-only content loses nothing by skipping HarfBuzz.
    font = ImageFont.truetype(
        str(FONT_DIR / filename), size, layout_engine=ImageFont.Layout.BASIC
    )
    if axes:
        _apply_axes(font, **axes)
    return font


# --- furniture styling ---------------------------------------------------
# The letterspaced caps that label the panel: the date, the three column
# headings, and the nameplate. They share one treatment so they read as a set.
#
# These are the knobs for "the titles look lacklustre": weight and ink give them
# presence, tracking gives narrow serif caps the width they otherwise lack.

# Literata's weight axis runs to 900, so there is more headroom than the usual
# 700 "bold". Tracking is the other half of the fix: the caps are narrow by
# construction and cannot be widened, but letterspacing gives the *word* the
# width it lacks - the trick engraved plates and title pages use.
#
# Optical size is deliberately left at its default text cut rather than pushed
# toward display: the display cut has finer details, which is the opposite of
# what a low-contrast e-ink panel wants at 22px.
# The two "hero" numbers. They share HERO_BASE, so if the sizes differ the
# smaller one starts lower and leaves a wider gap under its heading - which is
# why the weather column's label gap measured 31px against metro's 20px.
# One size for both, so the clock and the temperature are true peers.
# The degree sign is drawn separately at DEGREE_SCALE and raised to sit with the
# digits' cap line - at full size it dominates a two-character number, which is
# what made an equal-sized temperature look oversized on the first attempt.
HERO_SIZE = 70
DEGREE_SCALE = 0.55

FURNITURE_WEIGHT = 750
FURNITURE_INK = BLACK

TOPBAR_SIZE = 24
TOPBAR_TRACKING = 7.0

LABEL_SIZE = 22
LABEL_TRACKING = 7.0

# The nameplate is not a heading like METRO - it is a signature. It takes the
# supporting face, weight and grey, matching the freshness stamp opposite it so
# the two ends of the footer balance.
NAMEPLATE_SIZE = 19
NAMEPLATE_TRACKING = 1.6
NAMEPLATE_WEIGHT = 400
NAMEPLATE_INK = MUTED


class Fonts:
    """The loaded faces for one frame, by role.

    Built once per render. Variable-font instances carry their axis settings, so
    a Regular and a Bold from the same file must be separate objects.
    """

    def __init__(self, main_face: str | None = None, sub_face: str | None = None):
        m = main_face or MAIN_FACE
        s = sub_face or SUB_FACE

        # main - the panel's structure: its headings and headline numbers
        self.big = load(m, HERO_SIZE, weight=700)  # 15:28
        self.temp = load(m, HERO_SIZE, weight=700)  # 21
        self.degree = load(m, round(HERO_SIZE * DEGREE_SCALE), weight=700)
        self.topbar = load(m, TOPBAR_SIZE, weight=FURNITURE_WEIGHT)
        self.label = load(m, LABEL_SIZE, weight=FURNITURE_WEIGHT)
        self.nameplate = load(s, NAMEPLATE_SIZE, weight=NAMEPLATE_WEIGHT)

        # supporting - the details
        self.then = load(s, 25, weight=400)  # then 14:38
        self.meta = load(s, 21, weight=400)  # E -> the interchange
        self.small = load(s, 21, weight=400)  # trend, wind, rain line, +N more
        self.todo = load(s, 23, weight=400)  # task titles
        self.todo_note = load(s, TODO_NOTE_SIZE, weight=400)  # leave by 18:25
        self.stamp = load(s, 19, weight=400)  # updated 14:27

        # artwork caption, in the top bar
        self.caption = load(s, CAPTION_SIZE, weight=400)


# --- text helpers --------------------------------------------------------
# Letter-spacing for the top bar, column labels and nameplate. Pillow has no
# tracking parameter, so characters are advanced manually - which also drops
# kerning, exactly what spaced-out small caps want.
#
# All of these take a BASELINE y, matching the grid above.


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
