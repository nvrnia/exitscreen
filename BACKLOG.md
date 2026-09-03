# exitscreen — backlog

Working plan. `exitscreen-spec.md` says *what* we're building and why;
this file tracks *what's left and in what order*.

**Keep this updated as we go** — tick items off, move things between sprints,
add anything discovered mid-build. It's the memory between sessions.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · ⚠️ needs live verification
Size: **S** ≈ one sitting · **M** ≈ a session · **L** ≈ multiple sessions

---

## Where we are now

*Last updated: 2026-08-23 — a week of wifi debugging, all deployed.*

> ✅ **On the wall and running.** First light 2026-07-27. Renders every 5 minutes
> from 06:00 to 22:00 and pushes only when the image changes.

| column | state |
|---|---|
| METRO | ✅ reachable departures only (6-min walk filter); says "feed unavailable" when it cannot reach OVapi |
| WEATHER | ✅ the city conditions, umbrella rule, adaptive rain bars |
| TODO | ✅ **today's tasks only**, with leave-by times on `#40m`-tagged ones |
| ART | ✅ a Cleveland Museum painting a day, with veto |
| PANEL | ✅ Pi 3A+ at <your Pi's IP>, rounded 48px corners |

**Schedule:** clear at 05:59, renders `*/5` 06:00–21:55, final render 22:00,
`@reboot` waits for NTP. Moved an hour earlier for a ~07:00 departure.

**The wifi week (22–23 Aug), in one line:** the Pi's wifi kept dying silently -
the radio stayed nominally associated while passing nothing, so nothing ever
triggered a reconnect. Diagnosed wrongly three times (SD card twice, power supply
once) before `dmesg` and the log settled it. Now on 2.4GHz with power saving off
and a watchdog that bounces the interface when the router stops answering.

⚠️ **Signal is still only −70 dBm.** Everything above makes it fail *honestly* and
recover *automatically*; none of it makes the link stronger. If
`journalctl -t wifi-watchdog` shows it firing often, the answer is a repeater or
a powerline adapter, not more code.

**Deployed and installed on the Pi as of 2026-08-23:** all code, the 06:00
crontab (clean - see the installer bug below), the wifi watchdog in root's cron,
logrotate, and a persistent journal.

---|---|
| METRO | ✅ live — reachable the home stop departures only, 6-min walk filter |
| WEATHER | ✅ live — the city conditions, umbrella rule, adaptive rain bars |
| TODO | ✅ live — "our to do" list, with leave-by times on timed tasks |
| ART | ✅ live — a Cleveland Museum painting a day, with veto |
| PANEL | ✅ live — Pi 3A+ on `exitscreen-pi.local`, cron every 5 min |

See it:

```
py tools/preview.py --live        # fetches real data, opens the viewer
py tools/preview.py               # sample data, no network
py tools/preview.py --no-show     # just write PNGs to out/
```

Viewer keys: `1`/`2`/`3` reduction mode · `R` re-render · `S` save · `Q` quit.
⚠️ The Tk viewer has still never actually been run — only headless rendering is
verified. If it errors, the PNGs in `out/` still work.

**Now judged on real glass.** The panel is no longer the untested assumption; the
open questions are the umbrella icon override and art contrast, both below.

---

## Fiddling with the icons — quick reference

Everything icon-related lives in **`src/exitscreen/icons.py`**, and that file is
**unaffected by the redesign** — the codepoints and WMO mapping carry over intact.
Only the *placement* numbers quoted below move, since the weather column is being
rebuilt.

- **`GLYPHS`** — maps names to codepoints in the Weather Icons font.
  584 glyphs are available; we use 9. To browse the rest, look at
  `css/weather-icons.css` in the erikflowers/weather-icons repo — each
  `.wi-NAME:before { content: "\fXXX" }` is a usable codepoint.
- **`_WMO`** — which WMO codes map to which icon name. Reorder or resplit freely.
- **`weather_name()`** — the umbrella override lives here (umbrella wins over
  the actual sky, deliberately).
- **`draw_weather()`** — draws centred in a box. Glyphs render *wider* than their
  nominal box, so changing the size may need the surrounding spacing rechecked.
- **Size and position** are `WEATHER_ICON_SIZE` / `WEATHER_ICON_TOP` in `theme.py`;
  the column's arrangement is `frame.py` → `_draw_weather()`.

Tools:

```
py tools/icon_sheet.py            all 9 states at once -> out/icon_sheet.png
py tools/icon_sheet.py --browse   all 256 glyphs + codepoints -> out/icon_catalogue.png
py tools/preview.py --live        the full frame; press R to re-render
py tools/font_specimen.py         all 23 bundled faces, side by side
py tools/font_lab.py --live       typography candidates in the real layout
py tools/font_lab.py --live literata+archivo newsreader   any loose names work
```

`font_specimen.py` **discovers** fonts from `assets/fonts`, so anything dropped
in that folder appears on the next run. `font_lab.py` takes loose names and
`main+sub` pairings.

`icon_sheet.py` drives the real `build_frame()` path, so it shows what the
panel would actually do rather than an approximation. `--browse` is how you
find a different glyph: read the codepoint off the sheet, paste it into
`GLYPHS`. The font has far more than weather — moon phases, thermometers,
sunrise/sunset, a Beaufort wind scale (`f0b7`–`f0c2`).

Minor: a few cells in the catalogue render as empty boxes — those are unused
slots in the font, not bugs.

---

## EPIC 0 — Foundations ✅ done

- [x] Project skeleton, `src/` layout, `.gitignore`, requirements
- [x] Fonts bundled with OFL licenses; variable-weight support verified
- [x] `theme.py` — geometry, greys, font roles (the single tuning surface)
- [x] `icons.py` — WMO code mapping; weather from a bundled icon font,
      arrow + checkbox hand-drawn
- [x] `art.py` — the grey placeholder, and the fallback chain around it
- [x] `frame.py` — `build_frame(data) → image`, pure, no platform imports
- [x] `eink.py` — 256→16 grey reduction, plus 1-bit modes for comparison
- [x] `tools/preview.py` — headless render + Tk viewer
- [x] Decided grey16 over 1-bit dithering (dithering shredded hairlines and muted text)

**Left over from this epic:**
- [ ] **S** Confirm the Tk viewer actually opens — only ever run headless

~~Decide caption case~~ and ~~lock the EB Garamond + Inter pairing~~ — **both
superseded by Epic 2.5.** The redesign deletes the letterspaced caption, which was
the only reason a serif was in the project at all. Typography is reopened and gets
chosen from rendered candidates in `font_lab.py`.

---

## EPIC 1 — Metro (OVapi) 🔶 mostly done

- [x] ⚠️ Found the working code: **`<your TPC>`**, and it is a **TimingPointCode**,
      not a StopAreaCode (`stopareacode/` returns an empty object for it)
- [x] ⚠️ Dumped a live response; all spec field names confirmed
- [x] Decided single TPC. It turned out `<your TPC>` **is already our direction**
      (northbound: D→the interchange, E→the far terminus), so no direction
      filter is needed at all. `<the opposite platform>` is the opposite platform
- [x] `metro.py` — fetch, filter, sort, next N as `Departure` objects
- [x] Minutes from `ExpectedDepartureTime`; real-time delays confirmed present
- [x] Disk cache + 10-minute minimum poll interval, enforced in the module
- [x] Falls back to cached data on failure, then to `–`
- [x] Live departures rendering on a real frame

**Discovered along the way — recorded in the spec:**
- `v0.ovapi.nl` has a **broken TLS certificate** (hostname mismatch). Use `http://`.
  Never "fix" this by disabling certificate verification
- Timestamps are **naive local Amsterdam time**; parsed as `Europe/Amsterdam`
  explicitly rather than trusting the Pi's clock
- The feed **includes trains that have already departed** — filtered out
- Windows has no system tz database → added `tzdata` to requirements
- ⚠️ **The feed reaches much further than assumed: 17 departures, ~85 minutes
  ahead** (measured 2026-07-30). An earlier note here said ~20 minutes and that
  was wrong. It matters because it makes "leave by 18:22 → catch the D at 18:27"
  genuinely buildable for anything inside the next hour and a half

**Walk-time filter — added 2026-07-30.**

The column answered "which metro is next", not "which metro can I catch". At
10:50 the 70px hero clock showed `10:52` — a train that is a 3–5 minute walk
away, so unreachable — while the one you could actually make was demoted to the
small grey line beneath it. The panel's largest element was wrong and the right
answer was in the small print.

- [x] `WALK_TO_PLATFORM_MIN = 6` in `metro.py` — front door to standing on the
      platform, walk plus stairs. Departures closer than this are dropped
      entirely; `parse()` takes a `walk_min` override so the boundary is testable
- [x] Verified by sweeping the cutoff against the live feed: the window slides
      correctly and still finds departures at a 45-minute cutoff
- [x] Chosen to filter **silently** — no "leave now" cue, no "+6 min walk"
      caption. The value is in the times being trustworthy, not in self-explanation
- [ ] **S** Tune the 6 after a week of real use. Time the walk properly, door to
      platform, and set the real number — it is one constant
- Known and intended: the hero **jumps a whole interval** as the threshold is
  crossed. At 10:46 it reads 10:52; a minute later that train is out of reach and
  it reads 10:57

**The rule, worked through.** Timetable 15:53, 15:57, 16:01, 16:05, 16:09, 16:13
with a 6-minute cutoff:

| render time | skipped as unreachable | HERO | then |
|---|---|---|---|
| 15:50 | 15:53 (3m) | 15:57 | 16:01 |
| 15:55 | 15:57 (2m) | 16:01 | 16:05 |
| 16:00 | 16:01 (1m), 16:05 (5m) | 16:09 | 16:13 |

That is all it does: at 15:50 the 15:53 train is 3 minutes off, the walk is 6, so
it is not shown. Confirmed as the intended behaviour 2026-07-30.

**Known limitation, deliberately left.** The filter is correct at the *instant* it
renders, but the frame then sits on the glass for five minutes. A frame rendered at
15:50 shows 15:57 as its hero; read at 15:54 that train is 3 minutes away and no
longer catchable. Closing it would mean filtering on walk + refresh interval
(6 + 5 = 11 min), which costs a whole departure from view — at 15:50 you would be
shown 16:01 despite 15:57 still being makeable. Judged not worth the trade;
revisit only if it actually causes a missed train.

**Still open:**
- [ ] **S** ⚠️ Check what the feed does late at night / during engineering works
      (does `Passes` go empty?) — the no-departures path is written but untested
- [ ] **S** Consider shortening `the terminus` → `Centraal` if the column gets tight
- [ ] **S** Verify the numbers against the actual platform sign in person

~~Decide how to render an imminent train (`0'` vs `now`)~~ — **moot.** Absolute
times never go stale.

**Done when:** the column shows real the home stop departures I can verify
against the platform sign.

---

## EPIC 2 — Weather (Open-Meteo) ✅ built

- [x] `weather.py` — current temp / WMO code / wind speed + direction
- [x] ⚠️ Units confirmed already metric (`°C`, `km/h`, `°`) — no need to force them
- [x] Umbrella rule: raining now (WMO ≥ 51) **or** ≥40% precipitation
      probability within the next 6 hours
- [x] Wind direction feeds the bearing-aware arrow
- [x] Cache + 15 min minimum poll + falls back to stale, then to `–`
- [x] Live weather rendering on a real frame

**Notes:**
- `timezone=auto` resolves to `Europe/Amsterdam`; the hourly grid aligns with
  `current.time`, so the lookahead window indexes cleanly
- `wind_direction_10m` is the direction wind comes **from** (meteorological
  convention). The arrow is flipped 180° to point where it's blowing **to**
- HTTPS works properly here, unlike OVapi

**Icons — replaced with a bundled font:**
- [x] Swapped the hand-drawn weather vectors for the **Weather Icons** font
      (SIL OFL 1.1, verified; attribution in `assets/fonts/OFL-weathericons.txt`)
- [x] Codepoints parsed from the project's own CSS, not guessed — listed in `icons.py`
- [x] All nine states rendered through the real frame code and eyeballed
- [x] Spacing fixed: several glyphs draw wider than their nominal box
- Wind arrow and checkbox stay hand-drawn — the arrow must rotate to an
  arbitrary bearing, which a fixed glyph cannot do

**Still open:**
- [ ] **S** Tune `UMBRELLA_THRESHOLD` (40%) and `LOOKAHEAD_HOURS` (6) after
      living with it — these are guesses, not measurements
- [ ] **S** ⚠️ Check how the icons hold up on real e-ink; they are heavier and
      more solid than the delicate cross-hatch art above them

**Done when:** I look at the screen, see the umbrella, take an umbrella, and it rains.

---

## EPIC 2.5 — Dashboard layout redesign ✅ built

Replaced the hero-art layout with four bands: top bar, boxed art, a three-column
decision row, footer. Geometry lives in `theme.py`, arrangement in `frame.py`.

**Why absolute times:** `4'` starts lying the moment it is drawn — the panel
refreshes every few minutes, so "in 4 minutes" can be long gone. `08:14` stays
correct, and it is what makes push-on-change possible at all.

**Typography: Literata (main) + Work Sans (supporting).** The rule is *serif is
the panel's furniture, sans is the data hung on it* — serif for the date, column
labels, clock, temperature and nameplate; sans for everything hung off them.
Chosen by rendering 23 faces in the real layout, not by adjectives.

- Literata was commissioned for e-reader screens, an unusually good fit for e-ink
- All-serif was tried first and rejected as too heavy
- **Bricolage Grotesque was the first supporting pick and was dropped** — two
  characterful faces competed instead of one supporting the other. Source Sans 3
  meshed but measured narrowest of eleven candidates and read as cramped
- Atkinson Hyperlegible rendered `→` as tofu, which is why **all arrows are drawn
  as vectors**. Typeface choice is no longer limited by glyph coverage

**Three findings worth not rediscovering:**
- ⚠️ **Beaufort km/h upper bounds verified:** `1:5 · 2:11 · 3:19 · 4:28 · 5:38 ·
  6:49 · 7:61 · 8:74 · 9:88 · 10:102 · 11:117`. Now the table in `weather.py`.
  Force 6 is officially *"umbrellas are hard to use"* — a ready-made threshold
- ⚠️ **Tabular figures are unavailable** without libraqm; `features=['tnum']`
  raises `KeyError`. The trap: `layout_engine=RAQM` is silently *accepted* and
  falls back to basic layout with only a warning, so it looks like it worked.
  This is why `theme.load()` pins `Layout.BASIC` on both machines
- Digit widths were measured instead. Impact is modest on a left-aligned column,
  but the big numeral breathes by up to 64px across a day. Mono is not required

**Rejected here, later reversed:** this section used to list *"`LEAVE BY` with
walk-time arithmetic"* as deliberately out of scope. It shipped on 2026-07-30 —
see the leave-by section under EPIC 3. A live clock is still rejected.

---

## EPIC 3 — Todo (TickTick) ✅ built

- [x] App registered at developer.ticktick.com/manage
- [x] Secrets in `.env` (gitignored); `.env.example` committed as the record of
      which values are needed
- [x] `config.py` — stdlib-only `.env` reader/writer, real env vars take precedence
      (matters on the Pi, where cron or systemd may supply values directly)
- [x] `tools/ticktick_auth.py` — two-step OAuth2, `tasks:read` only
- [x] Access token written to `.env`
- [x] Project id saved: **"our to do"** `<your TickTick project id>`
- [x] ⚠️ Live task JSON dumped and field names confirmed
- [x] `todo.py` — fetch, sort, titles + total for the "+N more" line
- [x] Falls back to a stale list on failure, then to "nothing to do"
- [x] All three columns now rendering real data

**Verified live — recorded so it is not rediscovered:**
- **Completed tasks are absent from the response entirely.** Ticking one off in
  the app removes it from the payload, so there is no completion filter to get
  backwards. The `status == 0` check is defensive only
- **`sortOrder` is negative and the API does not sort by it.** Tasks came back in
  the wrong order; without an explicit ascending sort the list looks shuffled
- The token lasts **~180 days** and **no refresh_token is issued** — re-running
  `tools/ticktick_auth.py` is the recovery path
- Credentials go to the token endpoint as **form fields** (the HTTP Basic
  fallback was not needed)
- The redirect URI **must be registered on the app first**, or authorising fails
  with `At least one redirect_uri must be registered with the client`
- Endpoint shape: `GET /open/v1/project/{id}/data` → `{project, tasks, columns}`
- **`tags` is absent entirely** on a task with no tags — it needs a default
- ⚠️ **`dueDate`'s offset is honest UTC**, not local wall time wearing a `+0000`
  badge (verified 2026-07-30). An all-day task due 27 July came back as
  `2026-07-26T22:00:00.000+0000`, and 22:00 UTC *is* midnight Amsterdam on the
  27th in summer — only true if the offset means what it says. A cosmetic offset
  would have read `2026-07-27T00:00:00.000+0000`.
  **The trap:** that value's naive date is 26 July, the wrong day. Always convert
  to `Europe/Amsterdam` before reading a date or an hour off it. The separate
  `timeZone` field is the user's own zone and is not needed

### Today only — built 2026-07-31

The column was showing **every** open task. With a real list that meant a lunch
dated 29 August sat on the front door under a heading that means "before you walk
out". `parse()` now keeps only tasks whose due date, converted to Amsterdam, is
today.

- [x] `_due()` gets the due moment for **any** task, all-day included; `_clock_time()`
      is the narrower one that returns None for all-day, and still drives the
      inline time and the leave-by line
- [x] ⚠️ The off-by-one is handled and tested: an all-day task due 31 July arrives
      as `2026-07-30T22:00:00+0000`, so the date must be read **after** converting
      to Amsterdam. Reading it naively hides today's tasks and shows yesterday's
- [x] `todo_total` counts today's tasks, so "+N more" cannot promise tasks that
      are not on today's list

**Chosen consequences, not oversights:**
- **Undated tasks never appear.** Jot "buy bread" with no date and the door stays
  quiet about it. This was picked deliberately over including undated ones
- **Overdue tasks never appear** either — dated before today means gone
- A task dated *today* but whose time has passed (due 00:30, seen at 09:00) **is**
  shown. It is due today, which is the rule; "overdue" means an earlier date

**Done when:** the column shows only what actually matters before leaving.
Currently that is nothing, and it correctly renders "nothing to do".

---

### Leave-by times on timed tasks — built 2026-07-30

The one feature on the panel that changes behaviour rather than just informing.
A task with a clock time gets a second line: **"leave by 18:25"**.

The enabling fact was that TickTick *already* sends `dueDate` / `isAllDay` /
`tags` and `parse()` was throwing all of it away. No new API, no new habit — set
a due time in the app as normal.

- [x] `Task` model replaces bare title strings, with `at` (inline time) and
      `note` (the second line) as finished display strings decided in `todo.py`,
      so `frame.py` still needs no notion of "now"
- [x] Journey time comes from a **`#40m` tag** meaning *front door to being
      there*. Read from the title **and** from `tags`, since it is unverified
      which one TickTick puts it in — accepting both costs one branch
- [x] ⚠️ **The leading `#` is required.** Without it "Buy 2m of rope" claims a
      two-minute journey, and a wrong leave time looks exactly as authoritative
      as a right one. Tested
- [x] The leave line **disappears once it has passed** — a stale "leave by 08:20"
      at 11:00 is noise that teaches you to ignore the live ones
- [x] Timed but untagged → **inline time only**, no second line
- [x] Push guard verified: the digest changes **exactly once per timed task per
      day**, at the deadline. Renders minutes apart are byte-identical otherwise

**Two design corrections worth keeping, both found by rendering it:**
1. A bare "19:00" on its own row halved the visible list for no gain — it is a
   fact TickTick handed us, not a deadline we computed. Bare times went **inline**
   after the title; only the computed leave-by earns a row
2. `data.overflow` counted `todo_total - len(todos)` from what was *fetched*, but
   the renderer can draw fewer, so "+N more" undercounted. Now counted from what
   was actually **drawn**. Latent before; notes made it common

**Geometry:** `TODO_NOTE_OFFSET = 22` inside a pair against
`TODO_STEP_AFTER_NOTE = 36` between pairs. The asymmetry *is* the mechanism —
proximity groups the note with its task; at an even 33px it read as an unrelated
extra task. Measured cost: a noted task takes 58px against a plain 33. One note
and no overflow row → all four tasks visible; one note with overflow → three;
two notes → two. That degradation is the right way round.

**Still open:**
- [ ] **M** Once a leave time falls inside the feed's ~85-minute reach, name the
      actual train: "leave 18:22 → D 18:27". Now clearly buildable — the 20-minute
      horizon that argued against it was a mis-measurement
- [ ] **S** Confirm by eye on a *timed* task, not just an all-day one. The
      timezone reasoning is sound but only all-day tasks existed to test against
- [ ] **S** Wording is unlocked: "leave by 18:25" vs "leave 18:25" vs "→ 18:25"
- [ ] **S** Decide whether to merge our two separate lists too.
      The API has no "all tasks" endpoint, so that means two calls and a merge
- [ ] **S** Tune the display limit (currently 4) once real tasks accumulate
- [ ] **S** Diarise the token expiry — roughly late January 2027

**Done when:** ticking a task in the phone app clears it from the door within a
poll cycle.

---

## EPIC 4 — First light on the panel ⬜ 🔴 biggest risk

Everything so far is theory until pixels hit glass. **Can be pulled forward
at any time** — it doesn't depend on the data blocks.

- [x] Installed GregDMeyer/IT8951 on the Pi — **but NOT with the `[rpi]` extra**,
      see the trixie notes below
- [x] Deployed by `scp` of `src/ tools/ assets/ run.py .env` to `~/exitscreen`
- [x] `display.py` — the only module that imports IT8951. VCOM **-1.81**
- [ ] **L** ⚠️ Push a real frame and judge it in person:
      - does grey16 hold up, or does 1-bit actually look better on glass?
      - do the hairline rules survive?
      - is the 78px metro number readable from a few steps back?
      - is the caption tracking right at real size?
- [ ] **S** Tune `theme.py` against what we see, not what the monitor showed
- [ ] **S** Confirm landscape orientation / rotation is right
- [ ] **S** Judge how intrusive the `GC16` black flash actually is in the hallway
- [ ] **S** Test whether `DU` renders correctly on this controller — the mode
      docs warn some reduced modes render a white background as grey

**Post-first-light optimisation to evaluate (deliberately deferred):**
Only the metro column changes often, so flashing the whole 1200×825 panel to
update one corner is wasteful. Region-based partial `DU` refresh of just that
column would cost 200–600ms with **no black flash**, needing a full `GC16` pass
every 5–10 partials to clear accumulated ghosting (≈ hourly at our rate). Our
metro text is pure black on white, which is exactly what `DU` is good at.

Deferred because it rests on two things we cannot check without hardware: how bad
the flash really is, and whether `DU` behaves on this controller. Adding it later
touches only the push step, not the renderer.

### First light — what actually happened, 2026-07-27

Everything worked first try. Measured, not estimated:
- panel reports exactly **1200 x 825** — no rotation needed
- controller init **2.3s**, clear **0.7s**, `GC16` full draw **1.5s**
  (I had estimated 1–3s for the draw; it is at the fast end)
- from cron: fetch + render ~1s, push **0.7s**

**Raspbian 13 (trixie) specifics — these bit, or nearly did:**
- **PEP 668**: system-wide `pip install` is refused. Solution is a venv at
  `~/venv` created with `--system-site-packages`, so it can see apt's prebuilt
  Pillow / requests / GPIO rather than rebuilding them on a 512MB board
- **Do NOT `pip install ./[rpi]`**, despite the driver's README saying so.
  `python3-rpi-lgpio` is preinstalled and provides the `RPi.GPIO` module name as
  a drop-in; the extra would fetch the legacy library from PyPI and shadow it.
  Install plain `pip install --no-build-isolation ./IT8951`
- `--no-build-isolation` makes the build use apt's Cython instead of downloading
  and compiling one — armhf often has no prebuilt wheel
- Debian calls Pillow **`python3-pil`**, not `python3-pillow`
- SPI was already enabled (`/dev/spidev0.0` present) and the `exitscreen` user is
  already in the `gpio` and `spi` groups, so **no sudo is needed** to drive the panel
- Pi Pillow has **libraqm**, the Windows laptop does not. `theme.load()` now forces
  `ImageFont.Layout.BASIC` on both, or the preview would stop predicting the panel

**Done when:** ~~a frame with fake data is hanging by the door looking correct.~~
✅ real data, on the wall.

---

## EPIC 5 — Make it live ⬜

Turning a script into an appliance.

- [x] `run.py` — fetch all blocks → build frame → push. Each block wrapped so one
      failure costs its column, not the screen. Flags: `--force`, `--clear`,
      `--dry-run`, `--wait-for-clock`
- [x] On-disk cache layer shared by all data blocks — `cache.py` exists
- [x] Scheduling — cron installed, recorded in `deploy/crontab`:
      - render every **5 min, 07:00–22:00**; asleep overnight
      - **push only when the rendered image differs** (content hash)
      - daily white clear at **06:59**, one minute before the window opens
      - the **07:00 render must bypass the push guard** — the panel has just been
        cleared, so a hash matching last night would leave it blank all day
      - art regen each morning
- [ ] **S** ⚠️ No RTC on this Pi — don't trust the clock until NTP syncs after boot.
      Wait for time sync before the first render
- [x] Survives reboot — `@reboot` with `--wait-for-clock`, which polls
      `timedatectl` until NTP sets the time. Without it the Pi boots believing it
      is in the past, every departure looks "already gone" and gets filtered out,
      and the metro column renders empty
- [ ] **S** Log rotation — `~/exitscreen.log` grows unbounded at ~180 runs/day
- [ ] **M** ⚠️ **Make the SD card survive a power cut.** See the incident below.
      Move `~/exitscreen.log` and the `cache/` directory to a tmpfs RAM disk so
      nothing is being written during normal operation. The log is diagnostic
      only and losing it on reboot costs nothing

**Root cause of "0 departures when there were departures" — 2026-08-23.**

Two separate holes, both able to produce it, and the log could not distinguish
them because it recorded the *count* but never the *source*.

**Hole 1: a bad API response was indistinguishable from a good one.** `fetch()`
only raises on a network error or a non-200. OVapi is a free community server,
and a 200 carrying an empty or wrong-shaped body sailed straight through - so it
was treated as a good answer, **saved over a working cache**, and served for the
next `MIN_POLL`. One glitched response became ten minutes of empty column.

- [x] `carries_departures()` checks the response *shape*. A 200 without
      `{TPC}/Passes` is now a failure, not an answer, and drops into the cache
      fallback instead of overwriting it
- [x] A well-formed response listing nothing is **never cached**, and falls back
      to the last known data. That single branch is right in both situations
      *because* `parse()` filters against the clock: at 21:10 the cached trains
      are still upcoming and get shown; at 3am they have all gone, so it yields
      `[]` by itself. No need to guess which case we are in
- [x] Tested against five malformed payloads - empty Passes, missing Passes key,
      empty object, wrong stop code, Passes as a list. None can poison the cache

**Hole 2: the log hid where the data came from.** `metro : 2 departures` looked
identical whether it was a live fetch or hour-old cached data being served with
the wifi down. The whole 22 August outage had to be reasoned about backwards from
staleness constants.

- [x] `metro.LAST_SOURCE` records it and `run.py` logs it:
      `fresh` · `cached` · `empty` · `empty, using last known` · `stale` ·
      `unreachable`. So `2 departures (stale)` now says outright that the network
      is down and you are looking at old data

- [ ] **S** weather.py and todo.py have the same blind spot - a 200 with a junk
      body would be cached the same way, and neither logs its source. Lower stakes
      (weather holds 6 hours, to-do 24) but the same fix applies

---

### Why the wifi never recovered on its own — 2026-08-23

The obvious question, asked and worth writing down: **why did it not just
reconnect?** It sat unreachable from ~20:09 to at least 06:59 - eleven hours -
and only came back when the power was pulled.

**Because nothing knew it was disconnected.** The failure is not a clean drop.
The Broadcom radio (`brcmfmac`) stays *nominally associated* while passing no
traffic, so NetworkManager sees "connected, signal fine" and has no reason to
retry. It is not refusing to reconnect; it does not believe anything is wrong.
Power saving makes this far more likely, which is why disabling it mattered -
but a marginal signal can produce the same state on its own. ~85% confident in
the specific mechanism; certain about the symptom.

Two gaps made it worse:
- **Nothing runs between 22:00 and 06:00**, so even a midnight recovery would
  not have drawn a frame until 06:59
- **Nothing ever checked whether the network worked.** `run.py` notices its feeds
  failed and simply shrugs

- [x] `deploy/wifi_watchdog.sh` — pings the **router** every 5 minutes from
      root's crontab, 24/7. On failure it bounces `wlan0`; after 6 consecutive
      failures (~30 min) it reboots, which is what pulling the power was doing by
      hand. Failure count lives in `/run` (tmpfs), so no SD card writes
- Pings the gateway rather than the internet on purpose: a router that answers
  while the uplink is down is a broken uplink, and bouncing our own wifi cannot
  fix that. Pointless reconnects are their own risk
- Tested with stubbed `ping`/`nmcli`/`reboot`: counts failures, clears on
  recovery, reboots at the threshold, and treats a missing default route as a
  failure

- [ ] **S** Install it. Needs **root's** crontab, not the exitscreen user's:
      `sudo cp deploy/wifi_watchdog.sh /usr/local/bin/ && sudo chmod +x ...`
      then `sudo crontab -e` and add `*/5 * * * * /usr/local/bin/wifi_watchdog.sh`

---

### Deep bug sweep 2026-08-23 — concurrency and collisions

Beyond the metro work, a pass looking for races, shared state and things that
only misbehave under load. Three real bugs.

**1. Two writers shared one cache temp file.** `cache.save()` wrote to
`{name}.tmp` - the same name for every process - then renamed it. Two writers on
the same key would interleave into that one file and both rename it.

- Demonstrated with 40 concurrent write pairs: on Windows it raises
  `PermissionError`; **on Linux it does not raise at all** and produces spliced
  JSON, which `load()` then silently discards as "no cache"
- `run.py` takes a lock, but any tool run by hand - `preview.py --live` - can
  land on top of the cron job, and both write the metro cache
- [x] Fixed with `tempfile.mkstemp()` in the cache directory, so each writer gets
      its own file and the rename stays atomic. Re-tested: **40/40 clean, nothing
      spliced, no leftover temp files**

**2. A failed cache write threw away a good fetch.** `cache.save()` sits inside
`get_departures()`'s `try`, so a write failure fell through to the `except` and
served *stale* data while holding *fresh* data in hand.

- [x] The save is now wrapped on its own. A cache problem costs you the cache,
      not the answer

**3. The art blacklist was re-read once per candidate.** `pick_for()` called
`blacklisted_ids()` inside a list comprehension, so the JSON file was opened and
parsed **120 times per render** - and the loop could see the blacklist change
halfway through.

- [x] Hoisted out. One read. Selection verified unchanged: seven consecutive days
      still give seven distinct works

**Checked and clean:** no cache key collisions across the seven keys in use;
`build_frame()` does not mutate the data passed to it; five renders of identical
data give one digest; `metro.LAST_SOURCE` correctly tracks fresh → stale → fresh
without leaking a wrong answer forward; corrupt, truncated and empty cache files
all read as absent rather than crashing; all 13 tools run.

- [ ] **S** `weather.py` and `todo.py` still cache a well-formed-but-junk 200 the
      way metro used to, and neither reports its source. Same three-line fix
- [ ] **S** `theme.Fonts()` is constructed on every `build_frame()`, loading ~14
      variable-font instances per render. Works fine, but it is the obvious thing
      to cache if a render ever feels slow on the Pi

---

### Incident 2026-08-23 — the blank frame was the ghost-clear, not a crash

The panel sat all day showing yesterday's art with an empty METRO and WEATHER.
Nothing had crashed. The log says exactly what happened:

```
2026-08-23 06:59:02  metro   : 0 departures
2026-08-23 06:59:02  weather : no data
2026-08-23 06:59:05  cleared in 0.7s
```

The daily ghost-clear ran while both feeds were dead. The blank-frame guard had
an explicit `--clear` exemption, so it whited the panel and drew an empty frame,
and that frame stayed up all day.

**The reasoning behind the exemption was wrong.** It was: "`--clear` has already
whited the panel, so it must draw *something* or the display is left blank."
But the guard runs **before the panel is even opened** - declining there means it
is never cleared in the first place, and the previous good frame simply stays.

- [x] Guard now applies to `--clear` too. Verified across five paths: dead feeds
      with no flag, with `--force`, and with `--clear` all touch nothing; live
      feeds still clear and push normally
- A ghost-clear is cosmetic maintenance. Skipping it on a day the feeds are down
  costs nothing; blanking the door does not

**Also found, and this is the underlying cause of the whole week.** The wifi link
is weak, not broken:

```
5GHz  <my 5GHz network>   signal -77 dBm   tx 12.0 Mbit/s
2.4GHz <my network>     signal -70 dBm   tx 28.8 Mbit/s
```

- [x] Moved to the 2.4GHz SSID. 5GHz has worse range and wall penetration, and
      this fetches a few KB every five minutes - the trade was backwards
- ⚠️ **-70 dBm is still only "fair".** Both bands scan at ~48-50 from the Pi's
      position, so the real problem is distance from the router, not the band. If
      it keeps dropping, no configuration will fix it - that is a repeater, a
      powerline adapter, or moving the router
- [x] Wifi power saving stays disabled and survived a reboot; that fix was real
      but was never the whole story

**Still open, spotted in the same log.** At 21:10 metro went to `0 departures`
and stayed there while weather kept working:

- [x] **Fixed 2026-08-23.** `get_departures()` returned `[]` both when the feed
      was unreachable and when there genuinely were no trains, so a dead OVapi
      rendered the same dash as a quiet platform - reading as "no trains tonight"
      when it meant "no idea". It now returns **`None`** for unreachable and keeps
      `[]` for genuinely nothing. `FrameData.metro_unavailable` carries the
      distinction, the column says **"feed unavailable"**, and the blank-frame
      guard keys off the flag rather than inferring from emptiness

**The timing of 22 August, explained by the three staleness windows.** Each feed
serves its last good data until its own limit expires, so one network failure
blanks them at different times:

| feed | serves stale for | went blank |
|---|---|---|
| metro | 1 hour | 21:10 |
| weather | 6 hours | ~02:10, unseen - window closed at 22:00 |
| to-do | 24 hours | never got there |

Working back from metro blanking at 21:10, **the wifi died at about 20:10**. The
staggered failure was not a bug; it is the different `MAX_STALE` values doing
exactly what they were written to do. Left as they are: an OVapi payload only
reaches ~85 minutes ahead, so a metro window longer than an hour would have no
future departures left to show anyway.
- [ ] **S** Persistent journal is now genuinely working (`systemd-tmpfiles
      --create` was the missing step; `mkdir` alone is not enough). The next
      death will finally have a `journalctl -b -1` to read

---

### Incident 2026-08-21 — SOLVED: wifi power saving. Never the hardware

The panel kept freezing and the Pi kept becoming unreachable. Diagnosed wrong
three times - dead SD card, loose SD card, failing power supply - before the
evidence was actually gathered rather than inferred.

**The cause.** Raspberry Pi OS enables wifi power management on `wlan0` by
default. The radio drops its association and never re-associates. Confirmed
directly from the driver:

```
brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
```

**The Pi never crashed.** It stayed up, cron kept firing every five minutes, and
every fetch failed. `run.py`'s blank-frame guard then correctly held the last
good frame - so the visible symptom was a frozen screen, which looks exactly like
a dead machine. 40 `no live data` lines in the log, on the five-minute cadence,
are what proved it was alive the whole time.

**The fix**, as a NetworkManager drop-in rather than `nmcli` on the connection.
The connection is named `netplan-wlan0-...`, meaning netplan generates it and can
regenerate it on boot, wiping a per-connection setting. A global drop-in cannot
be overwritten that way:

```
/etc/NetworkManager/conf.d/wifi-powersave-off.conf
[connection]
wifi.powersave = 2
```

- [x] Verified across a reboot. `dmesg` now shows the pair - driver enables it at
      boot, NetworkManager disables it three seconds later - and
      `/usr/sbin/iw wlan0 get power_save` reports `Power save: off`

**What the crash history actually showed** (`tools/pi_doctor.py`): three outages
in three weeks across 14,890 log entries, and **every one of them was us** -
deliberate shutdowns and debugging reboots. There was never a spontaneous crash.

**How three diagnoses went wrong, so it does not happen again:**
- **The green LED means SD card activity, not "booted".** An idle, running Pi has
  a dark green LED. "Red on, no green" was read as a boot failure twice; it is
  perfectly normal for a healthy idle machine
- **`EXT4 orphan cleanup` was self-inflicted.** It means the last shutdown was
  unclean - which it was, because we kept pulling the power to test the card
- **`get_throttled=0x0` was treated as inconclusive** and the official 5.1V/2.5A
  supply was still suspected. It was fine all along
- ⚠️ **The answer was in `exitscreen.log` from day one.** A line every five
  minutes means every gap is an outage. Reconstructing that took one script and
  would have ruled out the hardware immediately, instead of three wrong turns
  reasoning from LEDs

**Rule:** on a Pi that seems dead, read the log and `dmesg` before touching the
hardware. `tools/pi_doctor.py` now does all of it in one run.

- [ ] **S** If it still drops occasionally: the Pi is on the **5GHz** SSID
      (`<my 5GHz network>`). 5GHz has shorter range and worse wall penetration, and
      this fetches a few KB every five minutes - the 2.4GHz band would suit it
      better

---

### Incident 2026-07-28 — cold unplug killed the SD card

Unplugged without shutting down, replugged hours later: red LED on, green LED
never lit, nothing on the network. Reflashing the **same** card fixed it
completely.

**The misleading part**, recorded so the next diagnosis is faster: the card read
*perfectly* from Windows — partition table intact, every boot file present and
correct size, `config.txt` and `cmdline.txt` clean. On that basis I concluded the
card was healthy and sent us looking at power supplies and jumper wiring. Wrong.

**A readable card is not a bootable card.** Windows can only see the FAT32 boot
partition; the ext4 root is invisible to it, and the Pi's bootloader is far less
tolerant of FAT damage than Windows' driver is. "Green LED never lights" does
*not* rule out the card.

**Next time, reflash early.** It is free, it is both the test and the likely fix,
and it takes twenty minutes with `deploy/setup_pi.sh`.

Also fixed as a result: `setup_pi.sh` aborted silently at the cron step on a
fresh machine, because `set -euo pipefail` treated "no crontab yet" as fatal.
- [ ] **S** Survive WiFi dropping: last good data, never a broken screen
- [ ] **S** Log somewhere I can read over SSH when it misbehaves

### Refresh cadence — researched, settled, don't reopen

**Panel wear is not a constraint.** Rated endurance: **1 million** updates
(pessimistic, OED Technologies), **10 million** (E Ink Corporation for Pearl), or
~**90 million** from Visionect's 50,000-hour figure. A real teardown found a
screen still readable after 4.5 years and ~3–4M updates.

At 5 min over a 15-hour day = **180/day ≈ 65,700/year**. Even on the pessimistic
1M rating that's **~15 years**.

The real cost is the **1–3 second black flash** per full refresh.

#### ⚠️ Correction 2026-07-30 — the frame is NOT static between polls

This section used to claim that *"nothing changes between OVapi polls (10 min), so
with absolute times the frame is byte-identical between polls."* **That was
wrong**, and it is worth knowing why, because it produced a wrong prediction twice.

**The cause is the timetable.** Trains run every 3–4 minutes at the home stop,
and `metro.parse()` recomputes against `now` on every run rather than against the
fetch. So the displayed pair rolls over as trains pass — *between* polls, not at
them. Measured on the live feed by stepping `now` minute-by-minute across an hour:
**a change roughly every 4 minutes**, against a 5-minute cron cadence.

This has always been true. It is a property of living next to a frequent metro
line and showing the next two departures, not of any code written recently.

> **Not the walk filter.** The same sweep with the filter disabled gave 14 changes
> per hour against 15 with it — noise. The filter shifts *when* a train leaves the
> list, not how often. It is a display rule and has no bearing on refresh
> frequency; the two were written up together once and that was confusing.

**What this means, stated plainly:** the push guard works correctly, but it will
**almost never skip during service hours**, because something genuinely changes
nearly every run. The panel flashes about every 5 minutes, 07:00–22:00.

The earlier `168 pushes / 0 skips` was therefore not *solely* the footer-stamp
bug. That bug was real and worth fixing — the stamp came from `now()` and made
every frame differ — but fixing it did not make the panel sit still, and saying so
implied it would.

Accepted as-is 2026-07-30: fresh metro times are the whole point of the screen,
and the flash is a fair price on something you walk past.

#### Rejected: DU partial refresh of the bottom band

Proposed to kill the flashing, then **withdrawn on inspection**. Recorded so it is
not re-proposed.

**DU is a 2-level waveform — black and white only, no intermediate greys.** The
decision row is built on greys: `MUTED` (102) for every metro destination, the
`then` time, todo notes, weather advice, `+N more` and the inline appointment
times; `DIVIDER` (153) for the rules and column separators. Under DU those snap to
black or vanish. The hierarchy that `spacing_audit.py` and the baseline grid exist
to protect only lives in the 16 greys `GC16` provides.

Note the plumbing is *not* the obstacle — `AutoEPDDisplay.draw_partial()` already
exists in the GregDMeyer library, so it would have been cheap to build. Cheap and
wrong is worse than expensive and wrong.

**If the flash ever does become annoying, try `GL16` / `GLD16` instead** — 16-grey
waveforms with a gentler flash, intended for text on white. That is a one-line
change to `DEFAULT_MODE` in `display.py`, with no partial-region logic and no
ghosting schedule. ⚠️ Unverified that those modes exist in the installed driver
(~85% confident; it only installs on the Pi). Check first with:

```
~/venv/bin/python -c "from IT8951 import constants; print([m for m in dir(constants.DisplayModes) if not m.startswith('_')])"
```

One useful side finding: "dark staining" in areas of **static** imagery is a real
ageing mechanism. Because every push is a full refresh, every pixel is exercised
every time — so the never-changing nameplate isn't at risk.

Sources: [Visionect lifespan](https://www.visionect.com/blog/epaper-lifespan/) ·
[e-ink degradation](https://e-ink-reader.ru/eink_degradation_en.php) ·
[refresh modes](https://www.geniatech.com/solution/e-paper-refresh-technology/)

- [ ] **S** ⚠️ Still worth checking the ED097TC2 datasheet for its own rated
      update count, rather than relying on figures for comparable panels

**Done when:** it's been up a week without me touching it.

---

## EPIC 6 — Daily art ✅ built (museum, not AI)

**The plan changed course.** This epic was written around AI generation; the
artwork now comes from the **Cleveland Museum of Art's** open collection. Real
paintings won on the grounds that they are prettier and more honest — an oil
actually has the tone and brushwork a prompt only asks for.

- [x] `museum.py` — Cleveland client, filtered index cached weekly
- [x] Deterministic selection: fixed-seed shuffle indexed by day ordinal, so a
      full cycle passes before any repeat **with no "seen" state file** to lose or
      corrupt. ~120 works ≈ 4 months
- [x] Greyscale before resize (a 424MB Pi should not hold a full-colour painting
      and its copy), crop to fill at `ART_CROP_CENTRING = (0.5, 0.45)` because
      landscapes carry their horizon above centre
- [x] Today's image cached to `cache/art/` — **load-bearing, not an optimisation.**
      The push guard compares pixels, so art that changed between renders would
      flash the panel every five minutes
- [x] Fallback chain: today's → yesterday's cached → `art.placeholder()`
- [x] Caption: artist · title, right-aligned in the otherwise-empty top bar
- [x] `tools/art_veto.py` — blacklist in `assets/` so a veto survives a reflash,
      plus `--next N`, a contact sheet of upcoming picks

**Three sources tested. Recorded so none gets retried:**
- **Cleveland** ✅ — open API, no key, and *real filters* rather than free text:
  `type=Painting&cc0=1&has_image=1`. The response carries image dimensions, so
  works that would not survive the crop are ranked out before anything downloads
- **The Met** ❌ — images fine and keyless, but the search is unusable.
  "landscape etching" returned a desk, a photograph and a calavera print; its own
  Drawings and Prints department reported one landscape. **340 candidates yielded
  3 usable works**
- **Art Institute of Chicago** ❌ — excellent search, but the IIIF image endpoint
  returns **403** even with their documented identifying header
- **AI (Pollinations)** — worked on its own terms: no key, native 1136×450, seeded
  and therefore reproducible. Kept in `tools/art_lab.py` as a documented fallback,
  not the live path

**Contrast — the one open thread.** The first painting on real glass was rejected
as too flat. Paintings often use only the middle of the tonal range, so quantising
to 16 greys wastes most of the levels.
- [x] Conditional stretch: only works measuring below `ART_FLAT_THRESHOLD = 45`
      (std dev of greys) get touched. A blanket stretch would vandalise paintings
      that are dark or pale *on purpose* — Church's "Twilight in the Wilderness"
      would become afternoon
- [ ] **M** ⚠️ **Untried and probably the real fix: dither the art region** to the
      same 16 levels instead of posterising. Banding is a quantisation artefact,
      so contrast tuning treats the symptom. Text and rules must stay hard-edged,
      so this is the art box only
- [ ] **S** The 45 threshold is calibrated on very few points. Revisit as vetoes
      accumulate — the `--next` sheet prints each work's score

---

## API review — both choices re-verified 2026-07-26

Checked rather than inherited from the spec.

**Metro — OVapi stays.** Confirmed as the standard source for Dutch realtime
departures across all operators including the operator. The alternatives are worse here:
NDOV Loket is the raw upstream feed and needs materially more work; the NS API is
trains only, no metro. The known warts (plain HTTP because of the broken
certificate, community server, poll gently) are the cost of the category.

**Weather — Open-Meteo stays as primary.** One keyless request returns
temperature, wind, gusts *and* a full-day hourly outlook. It already blends KNMI,
so we get Dutch met office data without KNMI's own registration and rawer feed.
Met.no is comparable but no better for this.

### Optional follow-on: Buienradar rain nowcast ⬜

Free, keyless, **2-hour rain forecast at 5-minute resolution** off Dutch rain
radar — granularity Open-Meteo can't match. For a screen read *in the act of
leaving*, "rain starting in 20 minutes" might be the most valuable line on it.

- [ ] ⚠️ **S** Verify the current hostname before writing any parser
      (`gadgets.` vs `gpsgadget.buienradar.nl`) — same discipline as the metro code
- [ ] **S** Record the attribution: terms are **non-commercial use with
      attribution required**. Fine for a hallway, but it must be credited
- Cannot replace the hourly outlook: 2 hours ahead won't tell you about 15:00
  at breakfast. This is an addition, not a substitution

Sources: [Buienradar raintext](https://github.com/thijse/Buienradar/blob/master/README.md) ·
[OVapi / NDOV](https://publicapi.dev/transport-for-the-netherlands-api)

---

## Tools — full sweep 2026-07-30

Every script in `tools/` was checked against the current package API, statically
(a script walked each file's AST and verified every `theme.X` / model field it
references actually exists) and then by running it. **All 13 pass.** The static
check is the useful half — it covers the tools that need network or hardware.

| Tool | State |
|---|---|
| `preview.py` | ✅ the main one. `--live` now prints each task's leave-by note |
| `spacing_audit.py` | ✅ measures ink bands and flags tight gaps. Caught the to-do note at 6px |
| `guard_check.py` | ✅ **new** — run twice, and it names which frame input changed |
| `icon_sheet.py` | ✅ **repaired** — see below |
| `art_veto.py` | ✅ **extended** with `--next N`, a contact sheet of upcoming picks |
| `font_lab.py`, `font_specimen.py`, `label_lab.py`, `layout_lab.py` | ✅ typography/layout labs, all run |
| `art_lab.py` | ✅ runs; docstring now marks AI generation as the **rejected** path |
| `find_pi.py`, `first_light.py`, `ticktick_auth.py` | ✅ not runnable headlessly (network scan / hardware / interactive OAuth) |
| `curate_art.py` | 🗑 **deleted** — see below |

**`icon_sheet.py` had been broken since the four-band redesign** — it referenced
`theme.STRIP_FACE`, `theme.STRIP_TOP` and `Weather(wind_bearing=…)`, none of which
survived. Repaired to crop `DECISION_TOP..FOOTER_TOP`, and improved while open: the
cases now cover **both** weather layouts (bars when rain is expected, icon alone
when not), since testing only one was testing half the column.

It immediately earned its keep by exposing a real design question:
- [ ] **S** ⚠️ **The umbrella override swallows the weather glyph.** wmo 63 (rain),
      81 (showers) and 95 (storm) all render an identical umbrella, so a
      thunderstorm is indistinguishable from drizzle — and `wmo 0 + umbrella`
      loses the sun entirely on a clear day with rain later. Decide whether the
      umbrella should replace the glyph, sit beside it, or only override on
      non-obvious codes

### Dead-code sweep — 2026-07-30

Removed, all provably unreferenced across the whole repo:

- **`tools/curate_art.py`** — built a hand-approved collection from **the Met**,
  which was rejected as a source, and wrote `assets/art_collection.json`, which
  nothing read and which it had never actually produced. Superseded by `museum.py`
  (automatic) plus `art_veto.py` (veto). Findings kept in `museum.py`'s docstring
- **`art.py`: `procedural_scene()`** — defined, never called; took `_soften_edges()`
  and `QUIET_ZONE` with it. `placeholder()` stays, it is live
- **The plaque caption** — `_draw_caption_plaque()`, its dispatch, four `PLAQUE_*`
  constants, two loaded fonts, and `CAPTION_STYLE` (a switch with one value)
- **`theme.py`: `GREY_STEPS`, `DECISION_H`, `draw_tracked_centred()`** — dead
- **`frame.py`** — an unused `Artwork` re-export; five leftover font constants in
  `font_lab.py`
- **A UTF-8 BOM in `art.py`**, the only one in the repo, left by a PowerShell
  `Set-Content -Encoding utf8`. Python tolerated it; AST tooling did not

Also retired the pre-redesign word **"strip"** from `icons.py`, `metro.py` and
`weather.py` — the layout has been four bands for a while.

Checked and deliberately *not* changed: there are **zero repeated 4+ line blocks**
in the codebase, so no shared helpers were invented. The `sys.path` bootstrap in 11
tools is 3 lines of standard idiom, and extracting it needs a module that itself
requires the path to be set.

Verified by rendering `frame.sample_data()` before and after: **identical digest
`94f8cfc90d2c81d7`**, so nothing visible changed.

---

## EPIC 7 — Physical ⬜

- [ ] **L** 3D printed frame (separate track, already in progress)
- [ ] **S** Cable management / permanent mount by the door
- [ ] **S** Decide whether the Pi is visible or hidden

---

## Suggested order

1. ~~**Metro**~~ ✅ done
2. ~~**Weather**~~ ✅ done
3. ~~**Layout redesign (Epic 2.5)**~~ ✅ done
4. **First light** ← the honest next step. Everything laptop-side is finished
5. **TickTick** — the only remaining work that does not need hardware
6. **Make it live** — cron, wiring the push guard into a runner, resilience
7. **Art** — the treat, once it's already useful

**First light is now the bottleneck, not a nice-to-have.** Across this build I
flagged five separate judgements as unanswerable from a laptop:

- grey16 vs 1-bit dithering
- whether the grey-153 hairline rules survive e-ink contrast
- whether the 76px numerals read from a few steps back
- whether Literata's finer serifs hold up where a bold sans would
- how intrusive the `GC16` flash actually is, and whether `DU` is usable

Plus roughly five small vertical-spacing nudges, all judged on a backlit monitor
at 100% zoom against a 9.7" 150-DPI panel with no backlight. Some of those are
wrong and there is no way to know which from here. Further tuning before first
light is guessing dressed up as progress.

---

## Open questions

**Only answerable on the hardware:**
- grey16 vs 1-bit — decided on the laptop, **not yet settled on glass**
- Whether the hairline rules (grey 153) survive e-ink contrast at all
- Are the large numerals readable from a few steps back
- Do the solid Weather Icons clash with the delicate cross-hatch art above
- How intrusive the `GC16` flash is, and whether `DU` works well enough to
  justify partial refresh of the metro column

**Answerable now:**
- Which typeface — from rendered candidates, not adjectives
- Whether tabular figures are really unavailable, and whether the jitter matters
- How many todos actually fit before the column looks cramped
- Where the repo lives on the Pi and how code gets there

## Locked decisions

**Layout (2026-07-26 redesign):**
- **Art gets 45%** — this is a dashboard with art, not art with data underneath.
  A deliberate reversal of the spec's "art gets maximum room"
- **Absolute metro times** (`08:14`), never relative. They don't go stale between
  refreshes, and they're what makes push-on-change work
- **No clock.** A muted `updated HH:MM` bottom-right instead — a clock up to 10
  minutes wrong is worse than no clock
- Date top-left · `OUR EXIT SCREEN` bottom-left · updated stamp bottom-right
- **No `LEAVE BY`** and no walk-time arithmetic
- Wind is **conditional** — hidden when calm, Beaufort + gusts when notable.
  No direction arrow; the walk is to an underground platform
- Weather is **adaptive** — bars + small icon when rain is expected, enlarged icon
  alone when not. The emptiness on a dry day is itself the signal

**Typography — settled after twelve candidates:**
- **Literata main + Work Sans supporting.** Serif is the panel's furniture
  (headings, clock, temperature, nameplate); sans is the data hung on it. Two
  constants in `theme.py` — `MAIN_FACE` and `SUB_FACE`
- Work Sans is **humanist** — drawn from calligraphic skeletons, the same
  tradition as a book serif — so it shares Literata's bone structure. Grotesques
  share nothing with it, which is why they never quite meshed
- Rejected, with reasons: **Bricolage Grotesque** (its own quirks competed with
  the serif instead of supporting it); **Source Sans 3** (meshed, but measured
  narrowest of eleven at 266px vs Work Sans's 306px — read as cramped)
- All three columns are labelled **METRO / WEATHER / TO DO**. The weather column
  originally had no heading, which made its temperature look higher than the
  metro clock despite sharing a baseline — a missing element reading as a
  misalignment
- **Symbols are drawn, never typed.** Arrows and icons are vectors, because a
  face missing a glyph renders an empty box — and because it frees the typeface
  choice from glyph coverage

**Refresh:**
- Render every 5 min 07:00–22:00; **push only when the image changes**
- ⚠️ **The daily art must be cached, not refetched per render.** The guard compares
  rendered pixels, so art that changed between renders would break it entirely.
  Done: `museum.daily()` writes `cache/art/` and reuses it all day
- Whole-screen `GC16` every push. Partial refresh was considered and rejected —
  see the DU note under EPIC 5
- Daily clear at **06:59**; the 07:00 render bypasses the push guard
- **The updated stamp must render the data's fetch time, not `now()`** — otherwise
  every render differs, the hash never matches, and the push guard does nothing

**Architecture:**
- Renderer stays pure — `frame.py` never imports IT8951, so layout work
  happens on the laptop
- **Weather icons come from a bundled icon font**, not hand-drawn vectors.
  (This reverses an earlier call. The original worry — a missing glyph renders
  an empty box — applies to *general-purpose* typefaces you don't control. This
  font ships with the project and every glyph we use has been rendered and
  checked.) The wind arrow stays hand-drawn: it must rotate to an arbitrary
  bearing, which a fixed glyph cannot do
- Every column degrades independently; a dead feed costs one column, not the screen
- grey16 is the default reduction (pending hardware confirmation)
- Secrets live in env vars / untracked files, never in git

## Resolved, kept for reference

- **Stoparea vs single TPC** → single TPC `<your TPC>`, which turned out to
  already be the direction we ride, so no direction filter is needed
