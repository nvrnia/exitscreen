# exitscreen

A what-to-know-before-I-leave display for the front door, in the city.

An e-ink panel showing the next metro I can actually catch, today's weather, the
shared to-do list, and a painting. It refreshes every five minutes but only
redraws when something has genuinely changed, so most of the day it sits there
costing nothing — e-ink holds its image with the power off.

![the panel](docs/panel.png)

## Hardware

| | |
|---|---|
| Panel | Waveshare 9.7" e-Paper HAT — ED097TC2 via IT8951, 1200×825, 16 grey levels |
| Computer | Raspberry Pi 3 Model A+ (512MB), headless, on wifi |
| Wiring | Jumper wires rather than stacked, so the HAT sits behind the frame |
| VCOM | **−1.81** — printed on the panel's own ribbon. Using the wrong value degrades the display |

## What's on it

- **Metro** — next two northbound departures from the home stop, live from
  OVapi. Only trains that are still *reachable*: anything closer than the walk to
  the platform is filtered out, because a departure you can't make is worse than
  no departure at all.
- **Weather** — the city, from Open-Meteo. Temperature and today's high, an
  umbrella verdict, and a bar chart of the next eight hours' rain chance that only
  appears when rain is actually expected.
- **To do** — the shared TickTick list. A task with a clock time and a `#40m`
  door-to-door tag gets a second line: `leave by 18:25`.
- **Art** — a public-domain painting a day from the Cleveland Museum of Art,
  greyscaled and cropped to the box. Deterministic by date, so it never changes
  mid-day.

## Running it

```bash
py tools/preview.py            # sample data, no network, opens a viewer
py tools/preview.py --live     # real data
py tools/preview.py --no-show  # just write PNGs to out/
python run.py --dry-run        # the production path, no hardware touched
python run.py                  # render and push to the panel
```

On the Pi, cron runs `run.py` every five minutes from 07:00 to 22:00, with a
clear-and-redraw at 06:59 and an `@reboot` entry that waits for NTP first — the
Pi has no clock of its own and boots believing it is some time in the past.

### Setup

Copy `.env.example` to `.env` and fill in the TickTick credentials, then run
`py tools/ticktick_auth.py`. `.env` is gitignored and never leaves the machine
it's on; it has to be copied to the Pi separately.

## Layout

```
src/exitscreen/
  frame.py     composes the whole 1200x825 image. Pure: data in, image out
  theme.py     every tunable number — geometry, greys, fonts. The tuning surface
  metro.py     OVapi
  weather.py   Open-Meteo
  todo.py      TickTick
  museum.py    Cleveland, and the deterministic daily pick
  art.py       the fallback chain in front of museum.py
  icons.py     weather glyphs from a bundled font; arrows drawn by hand
  eink.py      256 greys down to the panel's 16, and the frame hash
  display.py   the only file that imports the IT8951 driver
tools/         previewers, typography labs, a spacing auditor, art veto
deploy/        crontab and a one-command Pi rebuild script
```

`BACKLOG.md` is the working memory — what's left, what was tried, and what was
verified against a live API on which date. Read it before changing anything.

## Things worth knowing before you touch it

- **`frame.py` never learns the current time.** Everything time-dependent is
  decided in the data modules and handed over as a finished string. That's what
  keeps rendering deterministic.
- **The push guard depends on that determinism.** `run.py` hashes the reduced
  frame and skips the panel when the pixels match. The footer's "updated HH:MM"
  comes from cache age, not from `now()` — an earlier version used `now()` and
  refreshed the panel every five minutes forever.
- **OVapi is plain `http://`** because its TLS certificate doesn't match its
  hostname. Never "fix" that by disabling certificate verification.
- **Pillow's text layout is forced to `BASIC`** so the laptop and the Pi shape
  text identically — the Pi has libraqm and Windows doesn't, and without this the
  preview quietly stops predicting the panel.
- **Everything is placed on a baseline grid**, not by per-element offsets. It's
  the only way different type sizes align optically.

## Credits

Fonts are Literata and Work Sans (SIL Open Font License, bundled with their
licences in `assets/fonts/`). Weather glyphs are Erik Flowers' Weather Icons.
Artwork is CC0 from the Cleveland Museum of Art's open access collection. The
IT8951 driver is [GregDMeyer/IT8951](https://github.com/GregDMeyer/IT8951).
