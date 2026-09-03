# exitscreen log

What I've built, what broke, and why some things ended up the way they did.
Mostly written for future me, who will not remember any of this.

The rule I keep coming back to: if something cost me an afternoon to work out,
it goes in here, so it only costs an afternoon once.

---

## Where it's at

On the wall and running since 27 July 2026. Renders every 5 minutes and only
pushes when the image actually changed.

| column | state |
|---|---|
| metro | live. Only departures I can reach, 6 minute walk filter. Says "feed unavailable" when it can't reach OVapi |
| weather | live. Temperature, umbrella rule, rain bars when rain is coming |
| to do | live. Today's tasks only, with leave-by times on `#40m` tagged ones |
| commute | live. On a class day, which metro catches which bus |
| art | live. A Cleveland Museum painting a day, with a veto list |
| panel | Pi 3A+, 48px rounded corners, wired with jumper leads |

Cron clears at 05:59, renders every 5 minutes from 06:00 to 21:55, does a last
render at 22:00, and has an `@reboot` entry that waits for NTP. Moved an hour
earlier when I started needing to leave around 07:00.

Signal at the Pi is about -70 dBm, which is only fair. Everything below makes it
fail honestly and recover on its own, but none of it makes the link stronger. If
`journalctl -t wifi-watchdog` shows the watchdog firing a lot, the answer is a
repeater or a powerline adapter, not more code.

Seeing it without the hardware:

```
py tools/preview.py --live        real data, opens the viewer
py tools/preview.py               sample data, no network
py tools/preview.py --no-show     just write PNGs to out/
```

Viewer keys: `1`/`2`/`3` reduction mode, `R` re-render, `S` save, `Q` quit. The
Tk viewer has still never actually been opened, only headless rendering. If it
errors, the PNGs in `out/` still work.

---

## What's left

**Worth doing**

- Time the walk properly, door to platform, and set the real number. Right now
  `WALK_TO_PLATFORM_MIN` is 6 and that's a guess. It's one constant.
- `weather.py` and `todo.py` still cache a well-formed but junk 200 the way
  metro used to, and neither logs where its data came from. Same three line fix
  that metro got.
- Dither the art region to 16 levels instead of posterising. Banding is a
  quantisation artefact, so tuning contrast only treats the symptom. Art box
  only, text and rules have to stay hard-edged. Probably the real fix.
- Once a leave-by time falls inside the feed's ~85 minute reach, name the actual
  train: "leave 18:22, D at 18:27". Clearly buildable now.
- Move `exitscreen.log` and `cache/` to a tmpfs RAM disk so nothing is being
  written during normal running, and a power cut can't corrupt the card.
- Rerun `tools/build_bus_timetable.py`. The current timetable expires
  2026-12-09 and `commute.py` warns when it does.

**Small**

- Tune `UMBRELLA_THRESHOLD` (40%) and `LOOKAHEAD_HOURS` (6). Both guesses.
- Tune the to-do display limit, currently 4.
- Check what the metro feed does late at night or during engineering works. The
  no-departures path is written but never tested.
- Confirm a leave-by line by eye on a genuinely timed task. The timezone
  reasoning is sound but only all-day tasks existed to test against.
- Diarise the TickTick token expiry, roughly late January 2027.
- Check the ED097TC2 datasheet for its own rated update count rather than
  trusting figures for comparable panels.
- Confirm the Tk viewer actually opens.

**Physical**

- 3D printed frame, separate track, already going.
- Cable management and a permanent mount by the door.
- Decide whether the Pi is visible or hidden.

**One real design question, found by `icon_sheet.py`**

The umbrella override swallows the weather glyph. WMO 63 (rain), 81 (showers)
and 95 (storm) all render the same umbrella, so a thunderstorm looks like
drizzle. And `wmo 0 + umbrella` loses the sun on a clear day with rain later.
Decide whether the umbrella replaces the glyph, sits beside it, or only
overrides on codes that aren't already obvious.

---

## The log

### 2026-08-23  Why the wifi never recovered on its own

The obvious question, and worth writing down: why didn't it just reconnect? It
sat unreachable from about 20:09 to at least 06:59, eleven hours, and only came
back when I pulled the power.

Because nothing knew it was disconnected. It isn't a clean drop. The Broadcom
radio stays nominally associated while passing no traffic, so NetworkManager
sees "connected, signal fine" and has no reason to retry. It isn't refusing to
reconnect, it doesn't believe anything is wrong. Power saving makes this much
more likely, which is why turning it off mattered, but a marginal signal can get
there on its own. About 85% confident in the mechanism, certain about the
symptom.

Two things made it worse. Nothing runs between 22:00 and 06:00, so even a
midnight recovery wouldn't have drawn a frame until morning. And nothing ever
checked whether the network worked at all: `run.py` notices its feeds failed and
just shrugs.

Fixed with `deploy/wifi_watchdog.sh`. It pings the router every 5 minutes from
root's crontab, around the clock. On failure it bounces `wlan0`; after 6
failures in a row, about 30 minutes, it reboots, which is what I was doing by
hand. The failure count lives in `/run`, which is tmpfs, so no SD card writes.

It pings the gateway rather than the internet on purpose. A router that answers
while the uplink is down means a broken uplink, and bouncing our own wifi can't
fix that. Pointless reconnects are their own risk.

Tested with stubbed `ping`, `nmcli` and `reboot`: it counts failures, clears on
recovery, reboots at the threshold, and treats a missing default route as a
failure.

Still to install. It needs root's crontab, not the exitscreen user's:

```
sudo cp deploy/wifi_watchdog.sh /usr/local/bin/ && sudo chmod +x /usr/local/bin/wifi_watchdog.sh
sudo crontab -e     # */5 * * * * /usr/local/bin/wifi_watchdog.sh
```

### 2026-08-23  Where "0 departures" came from when there were departures

Two separate holes, either of which could cause it, and the log couldn't tell
them apart because it recorded the count but never the source.

**A bad response looked exactly like a good one.** `fetch()` only raises on a
network error or a non-200. OVapi is a free community server, and a 200 carrying
an empty or wrong-shaped body sailed straight through, got treated as a real
answer, saved over a working cache, and served for the next `MIN_POLL`. One
glitched response became ten minutes of empty column.

`carries_departures()` now checks the shape. A 200 without `{TPC}/Passes` is a
failure, not an answer, and drops into the cache fallback instead of overwriting
it. A well-formed response listing nothing is never cached and falls back to the
last known data. That one branch is right in both situations, because `parse()`
filters against the clock: at 21:10 the cached trains are still upcoming and get
shown, at 3am they've all gone so it yields `[]` on its own. No need to guess
which case we're in. Tested against five malformed payloads: empty Passes,
missing Passes key, empty object, wrong stop code, Passes as a list. None of
them can poison the cache.

**The log hid where the data came from.** `metro : 2 departures` looked identical
whether it was a live fetch or hour-old cache being served with the wifi down. I
had to reason about the whole 22 August outage backwards from staleness
constants. `metro.LAST_SOURCE` now records it and `run.py` logs it: `fresh`,
`cached`, `empty`, `empty, using last known`, `stale`, `unreachable`. So
`2 departures (stale)` now says outright that the network is down.

### 2026-08-23  The blank frame was the ghost-clear, not a crash

The panel sat all day showing yesterday's art with an empty metro and weather
column. Nothing had crashed. The log says exactly what happened:

```
2026-08-23 06:59:02  metro   : 0 departures
2026-08-23 06:59:02  weather : no data
2026-08-23 06:59:05  cleared in 0.7s
```

The daily ghost-clear ran while both feeds were dead. The blank-frame guard had
an explicit `--clear` exemption, so it whited the panel, drew an empty frame,
and that frame stayed up all day.

The reasoning behind the exemption was just wrong. It was: "`--clear` has already
whited the panel, so it has to draw something or the display is left blank." But
the guard runs before the panel is even opened. Declining there means it never
gets cleared in the first place, and the previous good frame simply stays.

The guard now applies to `--clear` too. Checked across five paths: dead feeds
with no flag, with `--force`, and with `--clear` all touch nothing; live feeds
still clear and push normally. A ghost-clear is cosmetic maintenance. Skipping it
on a day the feeds are down costs nothing. Blanking the door does.

Also found in the same log, and this is the underlying cause of the whole week:
the wifi link is weak, not broken. 5GHz was measuring -77 dBm at 12 Mbit/s
against 2.4GHz at -70 dBm and 28.8. Moved to the 2.4GHz network, since 5GHz has
worse range and wall penetration and this fetches a few KB every five minutes.
The trade was backwards.

-70 dBm is still only fair though. Both bands scan at about 48-50 from where the
Pi sits, so the real problem is distance from the router, not the band. If it
keeps dropping, no configuration will fix it.

And the thing that had been bugging me: at 21:10 metro went to `0 departures`
and stayed there while weather kept working. `get_departures()` returned `[]`
both when the feed was unreachable and when there genuinely were no trains, so a
dead OVapi rendered the same dash as a quiet platform. It read as "no trains
tonight" when it meant "no idea". It now returns `None` for unreachable and keeps
`[]` for genuinely nothing. `FrameData.metro_unavailable` carries the difference,
the column says "feed unavailable", and the blank-frame guard keys off the flag
rather than guessing from emptiness.

**Why the feeds went blank at different times.** Each one serves its last good
data until its own limit runs out, so a single network failure blanks them
staggered:

| feed | serves stale for | went blank |
|---|---|---|
| metro | 1 hour | 21:10 |
| weather | 6 hours | about 02:10, unseen, window shut at 22:00 |
| to-do | 24 hours | never got there |

Working back from metro blanking at 21:10, the wifi died at about 20:10. That
staggering isn't a bug, it's the different `MAX_STALE` values doing what they
were written to do. Leaving them. An OVapi payload only reaches about 85 minutes
ahead, so a metro window longer than an hour would have no future departures left
to show anyway.

The persistent journal works properly now. `systemd-tmpfiles --create` was the
missing step, `mkdir` alone isn't enough. The next death will finally have a
`journalctl -b -1` to read.

### 2026-08-23  Bug sweep: races and collisions

A pass looking for races, shared state, and things that only misbehave under
load. Three real bugs.

**Two writers shared one cache temp file.** `cache.save()` wrote to `{name}.tmp`,
the same name for every process, then renamed it. Two writers on the same key
would interleave into that one file and both rename it. Demonstrated with 40
concurrent write pairs: on Windows it raises `PermissionError`, on Linux it
doesn't raise at all and produces spliced JSON, which `load()` then quietly
discards as "no cache". `run.py` takes a lock, but any tool I run by hand, like
`preview.py --live`, can land on top of the cron job and both write the metro
cache. Fixed with `tempfile.mkstemp()` in the cache directory so each writer gets
its own file and the rename stays atomic. Re-tested: 40/40 clean, nothing
spliced, no leftover temp files.

**A failed cache write threw away a good fetch.** `cache.save()` sat inside
`get_departures()`'s `try`, so a write failure fell through to the `except` and
served stale data while holding fresh data in hand. The save is wrapped on its
own now. A cache problem costs you the cache, not the answer.

**The art blacklist was re-read once per candidate.** `pick_for()` called
`blacklisted_ids()` inside a list comprehension, so the JSON file was opened and
parsed 120 times per render, and the loop could see the blacklist change halfway
through. Hoisted out, one read. Selection verified unchanged: seven consecutive
days still give seven different works.

Checked and clean: no cache key collisions across the seven keys in use;
`build_frame()` doesn't mutate the data passed to it; five renders of identical
data give one digest; `metro.LAST_SOURCE` tracks fresh to stale to fresh without
leaking a wrong answer forward; corrupt, truncated and empty cache files all read
as absent rather than crashing; every tool runs.

One thing I noticed and left: `theme.Fonts()` is constructed on every
`build_frame()`, loading about 14 variable-font instances per render. Works fine,
but it's the obvious thing to cache if a render ever feels slow on the Pi.

### 2026-08-21  It was wifi power saving, and never the hardware

The panel kept freezing and the Pi kept going unreachable. I diagnosed it wrong
three times, dead SD card, loose SD card, failing power supply, before actually
gathering evidence instead of inferring it.

Raspberry Pi OS turns on wifi power management for `wlan0` by default. The radio
drops its association and never re-associates. Straight from the driver:

```
brcmfmac: brcmf_cfg80211_set_power_mgmt: power save enabled
```

**The Pi never crashed.** It stayed up, cron kept firing every five minutes, and
every fetch failed. The blank-frame guard then correctly held the last good
frame, so the visible symptom was a frozen screen, which looks exactly like a
dead machine. 40 `no live data` lines in the log, on the five minute cadence, are
what proved it was alive the whole time.

The fix is a NetworkManager drop-in rather than `nmcli` on the connection. The
connection is named `netplan-wlan0-...`, which means netplan generates it and can
regenerate it on boot, wiping a per-connection setting. A global drop-in can't be
overwritten that way:

```
/etc/NetworkManager/conf.d/wifi-powersave-off.conf
[connection]
wifi.powersave = 2
```

Verified across a reboot. `dmesg` now shows the pair, driver enables it at boot
and NetworkManager disables it three seconds later, and
`/usr/sbin/iw wlan0 get power_save` reports `Power save: off`.

**What the crash history actually showed**, once `tools/pi_doctor.py` existed to
reconstruct it: three outages in three weeks across 14,890 log entries, and every
single one was me. Deliberate shutdowns and debugging reboots. There was never a
spontaneous crash.

How the three wrong diagnoses happened, so it doesn't happen again:

- **The green LED means SD card activity, not "booted".** An idle, running Pi has
  a dark green LED. I read "red on, no green" as a boot failure twice. It's
  perfectly normal for a healthy idle machine.
- **`EXT4 orphan cleanup` was self-inflicted.** It means the last shutdown was
  unclean, which it was, because I kept pulling the power to test the card.
- **`get_throttled=0x0` got treated as inconclusive** and I still suspected the
  official 5.1V/2.5A supply. It was fine the whole time.
- **The answer was in `exitscreen.log` from day one.** A line every five minutes
  means every gap is an outage. Reconstructing that took one script and would
  have ruled out the hardware immediately, instead of three wrong turns reasoning
  from LEDs.

The rule: on a Pi that seems dead, read the log and `dmesg` before touching the
hardware. `tools/pi_doctor.py` does all of it in one run now.

### 2026-07-31  Today's tasks only

The column was showing every open task. With a real list that meant a lunch dated
29 August sitting on the front door under a heading that means "before you walk
out". `parse()` now keeps only tasks whose due date, converted to Amsterdam, is
today.

`_due()` gets the due moment for any task including all-day ones. `_clock_time()`
is the narrower one that returns None for all-day, and still drives the inline
time and the leave-by line.

The off-by-one is handled and tested. An all-day task due 31 July arrives as
`2026-07-30T22:00:00+0000`, so the date has to be read after converting to
Amsterdam. Reading it naively hides today's tasks and shows yesterday's.

`todo_total` counts today's tasks, so "+N more" can't promise tasks that aren't
on today's list.

Consequences I picked on purpose, not oversights:

- **Undated tasks never appear.** Jot "buy bread" with no date and the door stays
  quiet about it. Chosen deliberately over including undated ones.
- **Overdue tasks never appear** either. Dated before today means gone.
- A task dated today whose time has passed, due 00:30 and seen at 09:00, does
  show. It's due today, which is the rule. "Overdue" means an earlier date.

### 2026-07-30  Leave-by times on timed tasks

The one thing on the panel that changes behaviour rather than just informing you.
A task with a clock time gets a second line: "leave by 18:25".

What made it possible was that TickTick already sends `dueDate`, `isAllDay` and
`tags`, and `parse()` was throwing all of it away. No new API and no new habit,
just set a due time in the app like normal.

`Task` replaces bare title strings, with `at` for the inline time and `note` for
the second line, both decided as finished display strings in `todo.py` so
`frame.py` still needs no idea what "now" is.

Journey time comes from a `#40m` tag meaning front door to actually being there.
Read from the title and from `tags`, since I never confirmed which one TickTick
puts it in, and accepting both costs one branch.

**The leading `#` is required.** Without it, "Buy 2m of rope" claims a two minute
journey, and a wrong leave time looks exactly as authoritative as a right one.
Tested.

The leave line disappears once it's passed. A stale "leave by 08:20" sitting
there at 11:00 is noise that teaches you to ignore the live ones. Timed but
untagged gets an inline time only, no second line.

Push guard verified: the digest changes exactly once per timed task per day, at
the deadline. Renders minutes apart are byte-identical otherwise.

Two design corrections, both found by rendering it rather than thinking about it:

1. A bare "19:00" on its own row halved the visible list for nothing. It's a fact
   TickTick handed us, not a deadline we worked out. Bare times went inline after
   the title. Only the computed leave-by earns a row.
2. `data.overflow` counted `todo_total - len(todos)` from what was fetched, but
   the renderer can draw fewer, so "+N more" undercounted. Now counted from what
   was actually drawn. Latent before; notes made it common.

The spacing is deliberately uneven: `TODO_NOTE_OFFSET` inside a pair against
`TODO_STEP_AFTER_NOTE` between pairs. The asymmetry is the mechanism, proximity
groups the note with its task. At an even 33px it read as an unrelated extra
task. A noted task takes 58px against a plain 33, so one note and no overflow row
means all four tasks visible, one note with overflow means three, two notes means
two. That degradation is the right way round.

Wording is still unlocked: "leave by 18:25" vs "leave 18:25" vs an arrow.

### 2026-07-30  Only show metros I can actually catch

The column was answering "which metro is next", not "which metro can I catch". At
10:50 the 70px hero clock showed 10:52, a train a 3-5 minute walk away and
therefore unreachable, while the one I could actually make was demoted to the
small grey line underneath. The biggest element on the panel was wrong and the
right answer was in the small print.

`WALK_TO_PLATFORM_MIN = 6` in `metro.py`, front door to standing on the platform,
walk plus stairs. Departures closer than that get dropped entirely. `parse()`
takes a `walk_min` override so the boundary is testable.

Verified by sweeping the cutoff against the live feed: the window slides
correctly and still finds departures at a 45 minute cutoff.

It filters silently. No "leave now" cue, no "+6 min walk" caption. The value is
in the times being trustworthy, not in the panel explaining itself.

Worked through, with a timetable of 15:53, 15:57, 16:01, 16:05, 16:09, 16:13 and
a 6 minute cutoff:

| render time | skipped as unreachable | hero | then |
|---|---|---|---|
| 15:50 | 15:53 (3m) | 15:57 | 16:01 |
| 15:55 | 15:57 (2m) | 16:01 | 16:05 |
| 16:00 | 16:01 (1m), 16:05 (5m) | 16:09 | 16:13 |

That's all it does. At 15:50 the 15:53 train is 3 minutes off, the walk is 6, so
it isn't shown. The hero jumping a whole interval as the threshold is crossed is
intended: at 10:46 it reads 10:52, a minute later that train is out of reach and
it reads 10:57.

**A limitation I'm leaving in.** The filter is correct at the instant it renders,
but the frame then sits on the glass for five minutes. A frame rendered at 15:50
shows 15:57 as its hero; read at 15:54 that train is 3 minutes away and no longer
catchable. Closing it would mean filtering on walk plus refresh interval, 6 + 5 =
11 minutes, which costs a whole departure from view. At 15:50 you'd be shown
16:01 even though 15:57 is still makeable. Not worth the trade. Revisit only if
it actually makes me miss a train.

### 2026-07-30  Tools sweep and dead code

Every script in `tools/` checked against the current package API, statically (a
script walked each file's AST and verified every `theme.X` and model field it
references actually exists) and then by running it. The static half is the useful
one, since it covers the tools that need network or hardware.

`icon_sheet.py` had been broken since the four-band redesign. It referenced
`theme.STRIP_FACE`, `theme.STRIP_TOP` and `Weather(wind_bearing=...)`, none of
which survived. Repaired to crop `DECISION_TOP..FOOTER_TOP`, and improved while I
was in there: the cases now cover both weather layouts, bars when rain is
expected and icon alone when not, since testing one was testing half the column.

Deleted, all provably unreferenced:

- `tools/curate_art.py`, which built a hand-approved collection from the Met, a
  source I'd already rejected, and wrote a file nothing read and which it had
  never actually produced. Superseded by `museum.py` plus `art_veto.py`. Findings
  kept in `museum.py`'s docstring.
- `art.py`'s `procedural_scene()`, defined and never called. Took `_soften_edges()`
  and `QUIET_ZONE` with it. `placeholder()` stays, it's live.
- The plaque caption: `_draw_caption_plaque()`, its dispatch, four `PLAQUE_*`
  constants, two loaded fonts, and `CAPTION_STYLE`, a switch with one value.
- `theme.py`'s `GREY_STEPS`, `DECISION_H` and `draw_tracked_centred()`.
- An unused `Artwork` re-export in `frame.py`, and five leftover font constants
  in `font_lab.py`.
- A UTF-8 BOM in `art.py`, the only one in the repo, left by a PowerShell
  `Set-Content -Encoding utf8`. Python tolerated it, AST tooling did not.

Also retired the pre-redesign word "strip" from `icons.py`, `metro.py` and
`weather.py`. The layout has been four bands for a while.

Checked and deliberately not changed: there are zero repeated 4+ line blocks in
the codebase, so I didn't invent any shared helpers. The `sys.path` bootstrap in
11 tools is 3 lines of standard idiom, and extracting it needs a module that
itself requires the path to be set.

Verified by rendering `frame.sample_data()` before and after: identical digest,
so nothing visible changed.

### 2026-07-28  A cold unplug killed the SD card

Unplugged without shutting down, replugged hours later: red LED on, green LED
never lit, nothing on the network. Reflashing the same card fixed it completely.

The misleading part, written down so the next diagnosis is faster: the card read
perfectly from Windows. Partition table intact, every boot file present and the
right size, `config.txt` and `cmdline.txt` clean. On that basis I decided the
card was healthy and went looking at power supplies and jumper wiring. Wrong.

**A readable card is not a bootable card.** Windows can only see the FAT32 boot
partition. The ext4 root is invisible to it, and the Pi's bootloader is far less
tolerant of FAT damage than Windows' driver is. "Green LED never lights" does not
rule out the card.

Next time, reflash early. It's free, it's both the test and the likely fix, and
it takes twenty minutes with `deploy/setup_pi.sh`.

Fixed as a result: `setup_pi.sh` aborted silently at the cron step on a fresh
machine, because `set -euo pipefail` treated "no crontab yet" as fatal.

### 2026-07-27  First light

Everything worked first try. Measured, not estimated:

- panel reports exactly 1200 x 825, no rotation needed
- controller init 2.3s, clear 0.7s, `GC16` full draw 1.5s. I'd estimated 1-3s for
  the draw, so it's at the fast end
- from cron: fetch and render about 1s, push 0.7s

Raspbian 13 (trixie) things that bit, or nearly did:

- **PEP 668** refuses a system-wide `pip install`. A venv at `~/venv` created with
  `--system-site-packages` so it can see apt's prebuilt Pillow, requests and GPIO
  rather than rebuilding them on a 512MB board.
- **Do not `pip install ./[rpi]`** despite the driver's README saying so.
  `python3-rpi-lgpio` is preinstalled and provides the `RPi.GPIO` module name as a
  drop-in; the extra fetches the legacy library from PyPI and shadows it. Install
  plain `pip install --no-build-isolation ./IT8951`.
- `--no-build-isolation` makes the build use apt's Cython instead of downloading
  and compiling one. armhf often has no prebuilt wheel.
- Debian calls Pillow `python3-pil`, not `python3-pillow`.
- SPI was already on and the `exitscreen` user was already in the `gpio` and `spi`
  groups, so no sudo is needed to drive the panel.
- The Pi's Pillow has libraqm, the Windows laptop's doesn't. `theme.load()` forces
  `ImageFont.Layout.BASIC` on both, or the preview stops predicting the panel.

VCOM is -1.81 on my panel. It's printed on the ribbon cable and yours will be
different.

### 2026-07-26  Layout redesign

Replaced the hero-art layout with four bands: top bar, boxed art, a three column
decision row, footer. Geometry in `theme.py`, arrangement in `frame.py`.

**Absolute times, never relative.** `4'` starts lying the moment it's drawn, since
the panel refreshes every few minutes and "in 4 minutes" can be long gone. `08:14`
stays correct, and it's what makes push-on-change possible at all.

**Literata for the furniture, Work Sans for the data hung on it.** Serif for the
date, column labels, clock, temperature and nameplate. Sans for everything else.
Chosen by rendering 23 faces in the real layout rather than by adjectives.
Literata was commissioned for e-reader screens, which is an unusually good fit
here. All-serif was tried first and was too heavy.

Atkinson Hyperlegible rendered an arrow as tofu, which is why every arrow is now
drawn as a vector. Typeface choice is no longer limited by glyph coverage.

Three findings worth not rediscovering:

- **Beaufort km/h upper bounds**, verified: 1:5, 2:11, 3:19, 4:28, 5:38, 6:49,
  7:61, 8:74, 9:88, 10:102, 11:117. Now the table in `weather.py`. Force 6 is
  officially "umbrellas are hard to use", which is a ready-made threshold.
- **Tabular figures aren't available** without libraqm. `features=['tnum']` raises
  `KeyError`. The trap is that `layout_engine=RAQM` is silently accepted and falls
  back to basic layout with only a warning, so it looks like it worked. This is
  why `theme.load()` pins `Layout.BASIC` on both machines.
- Digit widths were measured instead. The impact is modest on a left-aligned
  column, but the big numeral breathes by up to 64px across a day. Mono isn't
  required.

### 2026-07-26  Picking the APIs

Checked rather than inherited from the spec.

**OVapi stays for metro.** It's the standard source for Dutch realtime departures
across operators. The alternatives are worse here: NDOV Loket is the raw upstream
feed and needs materially more work, and the NS API is trains only, no metro. The
known warts, plain HTTP because of the broken certificate, community server, poll
gently, are the cost of the category.

**Open-Meteo stays for weather.** One keyless request returns temperature, wind,
gusts and a full day hourly outlook. It already blends KNMI, so I get Dutch met
office data without KNMI's own registration and rawer feed. Met.no is comparable
but no better for this.

**Buienradar is a maybe.** Free, keyless, 2 hour rain forecast at 5 minute
resolution off the rain radar, which Open-Meteo can't match. For a screen read in
the act of leaving, "rain starting in 20 minutes" might be the most valuable line
on it. If I build it: verify the current hostname first, and record the
attribution, since the terms are non-commercial use with attribution required.
It can't replace the hourly outlook, since 2 hours ahead won't tell you about
15:00 at breakfast. An addition, not a substitution.

---

## Things I learned the hard way

**OVapi**

- `v0.ovapi.nl` has a broken TLS certificate, hostname mismatch. Use `http://`.
  Never "fix" this by turning off certificate verification.
- Timestamps are naive local Amsterdam time. Parsed as `Europe/Amsterdam`
  explicitly rather than trusting the Pi's clock.
- The feed includes trains that have already departed. Filtered out.
- Windows has no system tz database, so `tzdata` is in requirements.
- The feed reaches much further than I assumed: 17 departures, about 85 minutes
  ahead, measured 2026-07-30. An earlier note here said 20 minutes and was wrong.
  It matters, because it makes "leave by 18:22, catch the D at 18:27" genuinely
  buildable for anything inside the next hour and a half.
- The stop code is a TimingPointCode, not a StopAreaCode. `stopareacode/` returns
  an empty object for it. It also turned out to already be our direction, so no
  direction filter is needed at all.

**TickTick**

- **Completed tasks are absent from the response entirely.** Ticking one off in
  the app removes it from the payload, so there's no completion filter to get
  backwards. The `status == 0` check is defensive only.
- **`sortOrder` is negative and the API doesn't sort by it.** Tasks came back in
  the wrong order. Without an explicit ascending sort the list looks shuffled.
- The token lasts about 180 days and **no refresh token is issued**. Re-running
  `tools/ticktick_auth.py` is the recovery path.
- Credentials go to the token endpoint as form fields. The HTTP Basic fallback
  wasn't needed.
- The redirect URI has to be registered on the app first, or authorising fails
  with `At least one redirect_uri must be registered with the client`.
- `tags` is absent entirely on a task with no tags, so it needs a default.
- **`dueDate`'s offset is honest UTC**, not local wall time wearing a `+0000`
  badge. An all-day task due 27 July came back as `2026-07-26T22:00:00.000+0000`,
  and 22:00 UTC is midnight Amsterdam on the 27th in summer, which is only true
  if the offset means what it says. A cosmetic offset would have read
  `2026-07-27T00:00:00.000+0000`. The trap: that value's naive date is 26 July,
  the wrong day. Always convert to `Europe/Amsterdam` before reading a date or an
  hour off it. The separate `timeZone` field is the user's own zone and isn't
  needed.

**Open-Meteo**

- `timezone=auto` resolves correctly and the hourly grid aligns with
  `current.time`, so the lookahead window indexes cleanly.
- `wind_direction_10m` is the direction wind comes *from*, meteorological
  convention. The arrow is flipped 180 degrees to point where it's blowing to.
- HTTPS works properly here, unlike OVapi.

**The bus timetable**

OVapi can't reach these stops at all. `stopareacode/`, `tpc/` with an alphabetic
code, and `line/` detail all return empty objects, and `tpc/` only accepts
numeric codes. So `tools/build_bus_timetable.py` extracts the route from the
national GTFS feed into a 4KB asset. No real loss: you plan a departure against
the schedule, and delays matter at the stop, not at your front door.

Two numbers came out of the GTFS rather than guesswork. The metro ride is 7
minutes, the median of 2,728 real journeys, range 6.5 to 7.0. The bus takes about
30 minutes and runs every 30.

---

## Refresh cadence, settled

**Panel wear isn't a constraint.** Rated endurance is 1 million updates
(pessimistic, OED Technologies), 10 million (E Ink Corporation for Pearl), or
about 90 million from Visionect's 50,000 hour figure. A real teardown found a
screen still readable after 4.5 years and 3-4M updates. At 5 minutes over a 15
hour day that's 180/day, about 65,700/year. Even on the pessimistic rating,
about 15 years.

The real cost is the 1-3 second black flash per full refresh.

**The frame is not static between polls, and I got this wrong twice.** This
section used to claim nothing changes between OVapi polls, so with absolute times
the frame would be byte-identical between them. Wrong, and worth knowing why.

The cause is the timetable. Trains run every 3-4 minutes at my stop, and
`metro.parse()` recomputes against `now` on every run rather than against the
fetch. So the displayed pair rolls over as trains pass, between polls rather than
at them. Measured on the live feed by stepping `now` minute by minute across an
hour: a change roughly every 4 minutes, against a 5 minute cron cadence.

This has always been true. It's a property of living next to a frequent metro line
and showing the next two departures, not of any code I wrote recently.

It's also not the walk filter. The same sweep with the filter off gave 14 changes
an hour against 15 with it, which is noise. The filter shifts when a train leaves
the list, not how often. The two got written up together once and that was
confusing.

So, plainly: the push guard works correctly, but it will almost never skip during
service hours, because something genuinely changes nearly every run. The panel
flashes about every 5 minutes.

The earlier "168 pushes, 0 skips" was therefore not only the footer stamp bug.
That bug was real and worth fixing, the stamp came from `now()` and made every
frame differ, but fixing it didn't make the panel sit still, and saying so implied
it would.

Accepted. Fresh metro times are the whole point of the screen, and the flash is a
fair price on something you walk past.

---

## Tried and dropped

**DU partial refresh of the bottom band.** Proposed to kill the flashing, then
withdrawn on inspection. DU is a 2-level waveform, black and white only, no
intermediate greys. The decision row is built on greys: `MUTED` for every metro
destination, the `then` time, todo notes, weather advice, `+N more` and the inline
times; `DIVIDER` for the rules and column separators. Under DU those snap to black
or vanish. The hierarchy that `spacing_audit.py` and the baseline grid exist to
protect only lives in the 16 greys `GC16` gives.

The plumbing wasn't the obstacle. `AutoEPDDisplay.draw_partial()` already exists
in the GregDMeyer library, so it would have been cheap to build. Cheap and wrong
is worse than expensive and wrong.

If the flash ever does get annoying, try `GL16` or `GLD16` instead, 16-grey
waveforms with a gentler flash meant for text on white. That's a one line change
to `DEFAULT_MODE` in `display.py`, with no partial-region logic and no ghosting
schedule. I haven't verified those modes exist in the installed driver, since it
only installs on the Pi. Check first:

```
~/venv/bin/python -c "from IT8951 import constants; print([m for m in dir(constants.DisplayModes) if not m.startswith('_')])"
```

One useful side finding: "dark staining" in areas of static imagery is a real
ageing mechanism. Because every push is a full refresh, every pixel gets
exercised every time, so the never-changing nameplate isn't at risk.

**Three art sources.** Cleveland won: open API, no key, and real filters rather
than free text, `type=Painting&cc0=1&has_image=1`. The response carries image
dimensions, so works that wouldn't survive the crop get ranked out before
anything downloads.

The Met was rejected. Images are fine and keyless, but the search is unusable.
"landscape etching" returned a desk, a photograph and a calavera print, and its
own Drawings and Prints department reported one landscape. 340 candidates yielded
3 usable works.

Art Institute of Chicago was rejected too. Excellent search, but the IIIF image
endpoint returns 403 even with their documented identifying header.

AI generation (Pollinations) worked on its own terms: no key, native 1136x450,
seeded and therefore reproducible. Kept in `tools/art_lab.py` as a documented
fallback, not the live path. Real paintings won because they're prettier and more
honest. An oil actually has the tone and brushwork a prompt only asks for.

**Folding the bus into the metro column.** Tried and dropped. It pushed out the
second departure, which I still want.

**A wall-label style caption** inside the art's bottom corner. Built, compared,
lost. It covers part of the painting and needs an opaque background to stay
readable over a busy sky.

**A live clock.** Still rejected. A clock up to 10 minutes wrong is worse than no
clock, so there's a muted `updated HH:MM` bottom right instead.

---

## Decisions I'm not reopening

**Layout**

- Art gets 45%. This is a dashboard with art, not art with data underneath. A
  deliberate reversal of the original plan.
- Absolute metro times, never relative.
- No clock, just the updated stamp.
- Date top left, `OUR EXIT SCREEN` bottom left, updated stamp bottom right.
- Wind is conditional: hidden when calm, gusts when notable. No direction arrow,
  since the walk is to an underground platform.
- Weather is adaptive: bars plus icon when rain is expected, icon alone when not.
  The emptiness on a dry day is itself the signal.
- All three columns are labelled. The weather column originally had no heading,
  which made its temperature look higher than the metro clock despite sharing a
  baseline. A missing element reading as a misalignment.
- Symbols are drawn, never typed.

**Refresh**

- Render every 5 minutes during the day, push only when the image changes.
- **The daily art must be cached, not refetched per render.** The guard compares
  rendered pixels, so art that changed between renders would break it entirely.
- Whole-screen `GC16` every push.
- Daily clear at 05:59, and the first render after it bypasses the push guard.
- **The updated stamp renders the data's fetch time, not `now()`.** Otherwise
  every render differs, the hash never matches, and the push guard does nothing.

**Architecture**

- The renderer stays pure. `frame.py` never imports IT8951, so layout work happens
  on the laptop.
- Weather icons come from a bundled icon font, not hand-drawn vectors. This
  reverses an earlier call: the original worry, that a missing glyph renders an
  empty box, applies to general-purpose typefaces you don't control. This font
  ships with the project and every glyph used has been rendered and checked. The
  wind arrow stays hand-drawn, because it has to rotate to an arbitrary bearing.
- Every column degrades on its own. A dead feed costs one column, not the screen.
- grey16 is the default reduction.
- Secrets live in env vars and untracked files, never in git.

---

## Still only answerable on the hardware

- grey16 vs 1-bit. Decided on the laptop, never actually settled on glass.
- Whether the hairline rules survive e-ink contrast at all.
- Whether the large numerals read from a few steps back.
- Whether the solid weather icons clash with the finer art above them.
- How intrusive the `GC16` flash really is in the hallway.
