# exitscreen

An e-ink screen by our front door that tells us what we need to know before
walking out. Next metro we can actually catch, whether to take a coat, what's on
the shared to-do list, and a painting.

![the panel](docs/panel.png)

It refreshes every five minutes but only redraws when something's actually
changed. E-ink holds its image with the power off, so most of the time it just
sits there costing nothing.

Built for our flat in the city, so a lot of it is hardcoded to us — one metro
stop, one city, two people. That's on purpose.

## What's on it

**Metro** — the next two northbound trains from the home stop, live from OVapi.
Only ones we can actually reach: it's a six minute walk to the platform, so
anything sooner than that gets skipped. A train you'll miss is worse than no
train at all.

**Weather** — the city, from Open-Meteo. Temperature and today's high, whether
to take an umbrella, and a little bar chart of the next eight hours' rain chance
that only shows up when rain is actually coming.

**To do** — our shared TickTick list. If a task has a time on it and a `#40m`
tag saying how long it takes to get there, it gets a second line: `leave by
18:25`. That tag is door-to-door minutes, and we know that number better than any
API does.

**Art** — a public domain painting a day from the Cleveland Museum of Art,
greyscaled and cropped to fit. Same painting all day, picked by date. If one
looks bad on the panel, `py tools/art_veto.py --today` kills it for good.

## Running it

```bash
py tools/preview.py            # sample data, no network, opens a viewer
py tools/preview.py --live     # real data
python run.py --dry-run        # the real thing, without touching the panel
python run.py                  # render and push to the panel
```

On the Pi, cron runs `run.py` every five minutes from 07:00 to 22:00, with a
clear-and-redraw at 06:59. There's also an `@reboot` entry that waits for NTP
first — the Pi has no clock of its own and boots thinking it's some time in the
past, which made it filter out every departure as "already gone".

To set up: copy `.env.example` to `.env`, fill in the TickTick bits, run
`py tools/ticktick_auth.py`. `.env` is gitignored, so it has to be copied to the
Pi separately.

## The hardware

A Waveshare 9.7" e-Paper HAT — ED097TC2 driven by an IT8951, 1200×825, sixteen
greys — on a Raspberry Pi 3 A+. Connected with jumper wires rather than stacked,
so the board sits flat behind the frame.

**VCOM is −1.81**, printed on the panel's own ribbon cable. Yours will be
different, and using the wrong value degrades the display.

## Where things are

```
src/exitscreen/
  frame.py     builds the whole 1200x825 image. Pure: data in, image out
  theme.py     every number worth changing — geometry, greys, fonts
  metro.py     OVapi
  weather.py   Open-Meteo
  todo.py      TickTick
  museum.py    Cleveland, and picking the day's painting
  art.py       what to show when the painting can't be fetched
  icons.py     weather glyphs from a bundled font; arrows drawn by hand
  eink.py      256 greys down to 16, and the frame hash
  display.py   the only file that imports the panel driver
tools/         previewers, a spacing auditor, art veto, typography labs
deploy/        crontab and a one-command Pi rebuild script
```

`BACKLOG.md` is the running notes — what's left, what was tried, what broke.

## Three things that'll bite you

**Rendering has to be deterministic.** `run.py` hashes the image and skips the
panel if nothing changed, so anything time-dependent has to be decided in the
data modules and handed to `frame.py` as a finished string. `frame.py` never
learns what time it is. An early version put `now()` in the footer, which made
every frame differ and refreshed the panel every five minutes forever.

**OVapi is plain `http://`** because its TLS certificate doesn't match its
hostname. Don't "fix" that by turning off certificate verification.

**Pillow's text layout is pinned to `BASIC`** so the laptop and the Pi shape text
identically. The Pi has libraqm and Windows doesn't, and without this the preview
quietly stops predicting what the panel will do.

## Credits

Fonts are Literata and Work Sans, weather glyphs are Erik Flowers' Weather Icons,
all OFL and bundled with their licences. Paintings are CC0 from the Cleveland
Museum of Art. Panel driver is [GregDMeyer/IT8951](https://github.com/GregDMeyer/IT8951).
