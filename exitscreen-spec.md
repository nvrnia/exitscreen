# exitscreen — build spec for Claude Code

A DIY e-ink "what to know before I leave" display for the front door.
This file is the single source of truth. It grows as we research each block.
Status tags: ✅ decided · 🔶 in progress · ⬜ not started · ⚠️ needs live verification

---

## The device

- **Board:** Raspberry Pi 3 Model A+ (quad-core, 512 MB RAM), running Raspberry Pi OS Lite 32-bit, headless.
  - hostname `exitscreen-pi`, user `exitscreen`, reachable at `exitscreen-pi.local` over SSH.
- **Display:** Waveshare 9.7" e-Paper HAT, panel **ED097TC2**, controller **IT8951**, **1200 × 825**, mono with 16 grey levels.
  - Connected over **SPI** via jumper wires (not stacked). DIP switch set to SPI.
  - **VCOM = -1.81** (must be passed to the driver; wrong value degrades the panel).
- Plugged in permanently by the door. Landscape orientation.

## Driver / rendering approach ✅ decided (method) 🔶 (not yet built)

- Hardware verified working with Waveshare's C demo (`sudo ./epd -1.81 0` → grey bars).
- **For the actual project, use Python** with the **GregDMeyer/IT8951** library (MIT, community standard).
  - It has a **virtual-display mode** → develop/layout on a laptop with no hardware attached. Use this for all layout work.
- Rendering model: build ONE full 1200×825 image (Pillow), then push it to the panel. Don't draw block-by-block on the hardware.
- **Ghosting:** Waveshare recommends a full refresh every ~24h to clear it. Plan a full white clear + redraw once a day (e.g. 2am).
- **No RTC on the Pi:** clock is wrong until network time syncs after boot. Don't trust local time immediately on boot; wait for NTP.

---

## Layout ✅ decided

Landscape **1200 × 825**, minimal black & white, "cute daily print by the door" vibe.
Hero-art layout:

- **Top (majority of the screen):** large daily AI-generated art, **full-bleed, no border**. Cozy-but-clean **cross-hatch** B&W style, driven by the day's data.
- **Below the art, centered:** a dated caption like **"25 July"** (written month, no weekday, letter-spaced so it reads like a signed print caption — comfortable size, not tiny).
- **A horizontal divider line**, then a **slim bottom info strip** split by **two vertical dividers** into three columns:
  1. **METRO (left):** big bold next departure e.g. `4'`, smaller second time e.g. `12'`, line/destination underneath e.g. `E → Den Haag`.
  2. **WEATHER (middle):** icon + number e.g. `☂ 7°`, wind under it e.g. `↑18`. The icon does the "bring this" work.
  3. **TODO (right):** checkboxes from one TickTick list.

Keep the strip thin so the art gets maximum room, but the metro number stays large/glanceable.

---

## Block 1 — METRO 🔶 in progress

**Location:** user boards at **the home stop** (the city, underground metro station, lines **D** and **E**).
Typical destinations: **the interchange** and **the far terminus** (both served by line E; D also runs through here).

### Data source ✅ decided: OVapi (`v0.ovapi.nl`)
- Free, community-run public API fed by NDOV Loket. Covers all Dutch operators incl. **the operator** (the city).
- **No API key, no OAuth** — just HTTP GET a URL and parse JSON. (Big win vs TickTick's OAuth.)
- Two endpoint styles:
  - `https://v0.ovapi.nl/tpc/<TPC>` — a single **TimingPointCode** = one platform/quay (one direction).
  - `https://v0.ovapi.nl/stopareacode/<code>` — groups all platforms of a station together (both directions).
- Response contains a `Passes` object: each pass has line number, destination, and **TargetDepartureTime** / **ExpectedDepartureTime** (real-time). Compute "minutes from now" = ExpectedDepartureTime − now.

### ✅ VERIFIED LIVE (2026-07-25, against the real API)

- **Use `http://`, not `https://`.** The TLS certificate on `v0.ovapi.nl` does not
  match the hostname, so any verifying HTTP client refuses the connection. Plain
  HTTP returns 200. Acceptable here: public departure data, no auth, no secrets.
  Do **not** work around this by disabling certificate verification.
- **The stop code is `<stop code>`, and it is a TimingPointCode — not a StopAreaCode.**
  `tpc/<stop code>` returns a full payload; `stopareacode/<stop code>` returns an empty
  object. The drgl.nl lead was correct, but only via the `tpc/` endpoint.
- **`<stop code>` is already the direction we ride.** It is the northbound platform:
  every pass is `LineDirection 2`, line **D → the interchange** and line
  **E → the far terminus**, alternating roughly every 7–8 minutes.
  No direction filtering is needed — the platform *is* the filter.
- The opposite platform is **`<stop code>-OPPOSITE`** (D → De Akkers, E → Slinge). Not used.
- Confirmed field names on a live pass:
  `LinePublicNumber`, `DestinationName50`, `TargetDepartureTime`,
  `ExpectedDepartureTime`, `TransportType` (`"METRO"`), `LineDirection`.
- Real-time delays are genuinely present (observed scheduled `23:07:00` vs
  expected `23:08:15`), so `ExpectedDepartureTime` is the field to use.
- **Timestamps are naive local Amsterdam time** — no timezone suffix, no UTC
  offset. Parse them as `Europe/Amsterdam` explicitly rather than trusting the
  Pi's system timezone.
- **Past departures are included in the response.** The feed held a train that
  had already left 1.9 minutes earlier, so upcoming-only filtering is required.

### Implementation notes
- Poll the single TPC `<stop code>`; no direction filter needed (see above).
- Drop passes whose `ExpectedDepartureTime` is in the past, then sort — the
  `Passes` object's key order should not be trusted as chronological.
- Show the next ~2 departures.
- **Etiquette:** OVapi is a free non-commercial server — **poll gently, ~every 10 minutes**, not more. Cache the last good response.
- Handle "no departures" (night) and API-down gracefully (show last good data or a dash).

---

## Block 2 — WEATHER ✅ decided

**Location:** the city, approx **lat 0.00, lon 0.00** (fine-tune to the apartment if wanted).

### Data source ✅ decided: Open-Meteo (`api.open-meteo.com`)
- Free, **no API key, no signup, no meaningful rate limits** (10k calls/day free tier — we use a handful).
- Blends national weather models incl. **KNMI** (Dutch met office) → accurate over the city.
- One GET returns everything, clean JSON, arrays index-aligned with their `time` array.

### Endpoint (one call covers the whole block)
```
https://api.open-meteo.com/v1/forecast?latitude=0.00&longitude=0.00&current=temperature_2m,weather_code,wind_speed_10m,wind_direction_10m&hourly=precipitation_probability,temperature_2m&timezone=auto
```
- `current.temperature_2m` → the big number, e.g. `7°`
- `current.wind_speed_10m` (km/h) + `current.wind_direction_10m` → wind, e.g. `↑18`
- `current.weather_code` → **WMO code** → maps to a B&W icon (0 = clear, 1–3 = cloud, 45/48 = fog, 51–67 = rain/drizzle, 71–77 = snow, 80–82 = showers, 95+ = thunder).
- `hourly.precipitation_probability` → look **ahead a few hours** for the "bring an umbrella" decision (not just the current instant).

### Implementation notes
- Poll every ~15–30 min; cache last good response; on failure show last good data.
- `timezone=auto` so the hourly `time` array is in local the city time (helps the "rain at 4pm" logic).
- Units default to metric/°C/km-h for a European location — confirm in the response; can force with `&wind_speed_unit=kmh&temperature_unit=celsius`.
- The **"bring this"** rules (Logic epic) consume this data: high upcoming precip prob → umbrella icon; low temp → jacket; high wind → wind icon. Design the icon set as part of the art/render style (cross-hatch B&W to match).

## Block 3 — TODO (TickTick) ✅ decided

Show tasks from **one dedicated TickTick list** (e.g. "Exitscreen" or "Errands"). One-list design is deliberate — it sidesteps the API's biggest limitation (see quirks).

### Data source: TickTick Open API (official)
- REST API at `api.ticktick.com`, **OAuth2**. Register app at **developer.ticktick.com/manage**.
- Scope needed: **`tasks:read`** only (we never write).

### One-time setup (do interactively, then cache)
1. Register app → get **Client ID** + **Client Secret**. Store as env vars on the Pi (never commit the secret).
2. Set a **redirect URI** — a dummy like `http://127.0.0.1:8080` is fine (doesn't need to be a live site).
3. OAuth2 flow (run once):
   - Send user to `https://ticktick.com/oauth/authorize?scope=tasks:read&client_id=...&state=...&redirect_uri=...&response_type=code`
   - User grants access → redirected to `redirect_uri?code=...`
   - Exchange the code: POST (form-urlencoded) to `https://ticktick.com/oauth/token` with client_id, client_secret, code, grant_type=authorization_code, redirect_uri → returns an **access_token**.
4. **Cache the access token** on the Pi. From then on it just reads.

### Pulling the list (runtime)
- All requests: header `Authorization: Bearer {access_token}`.
- **No global "all tasks" or "due today" endpoint.** You must: list projects → find the one you want → fetch that project's tasks.
  - `GET https://api.ticktick.com/open/v1/project` → list of projects (find your list's **projectId** once, then hard-code it).
  - `GET https://api.ticktick.com/open/v1/project/{projectId}/data` → that project's tasks.
- Show the open (incomplete) task titles, a few of them, as checkboxes.

### Quirks / notes
- **No webhooks** → **poll** on a timer (same cron pattern as the other blocks). ~15–30 min is plenty.
- Community reference (structure only, not required): `lazeroffmichael/ticktick-py`.
- Token may expire / need refresh — check whether the token response includes a refresh_token and handle re-auth gracefully (fall back to last good list if auth fails).
- ⚠️ VERIFY: exact field names in the project/task JSON on a live response before writing the parser.

## Block 4 — DAILY ART 🔶 in progress (identity defined, pipeline TBD)

The soul of the display: one AI-generated B&W illustration per day, driven by the day's data.

### ART BIBLE (visual identity — keep every day consistent as one series)
- **Technique:** delicate **linework with cross-hatch shading** (etching / fine-line engraving feel). Outlines delicate; shadow/depth built from hatching, not solid black fills. Calm and sincere, **not** whimsical/cartoony.
- **Subject:** quiet, **unpeopled** scenes of **place and nature**. One clear focal subject (a bridge, a window, a tree, water, sky) grounded in a **modest amount of setting/detail** — not stark-empty, not busy.
- **Setting flavor:** loosely **NL-adjacent** — canals, low bridges, rooftops, flat wide skies, water — but **not touristy/landmark the city**. Just gently Dutch-feeling. Generic cozy/nature scenes are fine too.
- **Tone:** **varies with the day's mood.** Clear day → light, airy, lots of white. Grey/rainy day → darker, denser hatching, atmospheric. The *technique stays constant*; the *tonal weight flexes*.
- **No people. No text baked into the image** (the date caption is added separately by the render layer).

### ART BIBLE — craft details
- **Line density:** medium, **leaning airy** — balanced linework that keeps enough white space to read cleanly on e-ink. Not sparse, not heavily inked.
- **Edge treatment:** **soft / vignette fade** — the scene dissolves toward the edges rather than a hard rectangular cut-off (looks better full-bleed on the panel).
- **Consistency rule:** **same recognizable "hand"/style every day**, but subject & composition vary freely. Always reads as one series; the scene is a daily surprise.
- **Caption harmony:** leave **calm quiet space near the bottom** of the art so the separately-rendered "25 July" caption sits in breathing room, not crashing into dense linework.

### DAILY DRIVER (what makes today's art today's)
- **Weather-led**, blended with season/time-of-year and general day feel.
- **Literalness: between literal and suggestive.** A rainy day reads wetter/moodier and *may* show rain, but don't force a 1:1 "weather icon as a scene." Aim for mood-match over literal depiction.

### PIPELINE 🔶 (model chosen, prompt/convert TBD)

**Image model — DECISION PARKED for later** (art block deferred; everything else can be built without it).
When picking up: the ART BIBLE below is fully defined, only the model/pipeline is open.
- **Free routes a Pi can actually use** (the ChatGPT app's free images are NOT API-usable):
  - **Cloudflare Workers AI — recommended free option.** Ongoing free tier (~10k "neurons"/day, resets daily, no credit card), and it **hosts FLUX Schnell** (the open version of the model below). Stable because there's a real account behind it. One image/day is trivial against the quota. Sign up at dash.cloudflare.com → Workers AI API token.
  - **Pollinations.ai** — no key, no signup at all (`image.pollinations.ai/prompt/<prompt>`). Dead simple, but no uptime guarantee / rate limits shift. Fine for hobby use (missed day = reuse yesterday's).
- **Paid route (~$1/mo)** if free tiers annoy: FLUX via Black Forest Labs API / fal.ai / Replicate. Best stylized-illustration quality among API models; Midjourney ruled out (no real API).
- ⚠️ **~70% on which model nails cross-hatch specifically.** Prompt-test the actual style string on whichever provider before committing.

**Prompt builder:**
- Constant **style string** (from the ART BIBLE above) + variable **day data** (weather, season, maybe a scene noun).
- Keep the style string fixed so the series stays coherent; vary only subject/mood.
- Example shape: `"{fixed style: delicate pen-and-ink cross-hatch etching, unpeopled quiet NL-adjacent scene, soft vignette edges, airy, calm}" + "{today: a low canal bridge under heavy grey rain, moody, dense shading}"`.

**B&W conversion for the panel:**
- Generated image → greyscale → map to the panel's **16 grey levels** (or 1-bit with dithering — test both).
- Cross-hatch line art survives this reduction well (a key reason it was chosen).
- Pillow for conversion; likely Floyd–Steinberg dithering. **Test on real hardware** — fine lines can muddy at 1200×825 mono.
- Target the full-bleed art region of the layout; leave the bottom "quiet space" for the caption.

**Scheduling:** regenerate once each morning; cache the day's image; on API failure reuse yesterday's or a stored fallback.

---

## Cross-cutting / later
- **Render pipeline:** compose all four blocks into one 1200×825 Pillow image → dither/convert → push via IT8951.
- **Scheduling:** cron on the Pi. Frequent-ish refresh for metro/weather; daily full-clear at ~2am; daily art regen in the morning.
- **Error handling:** WiFi down, any API down → show last good data, never a broken screen.
- **Frame:** 3D printed, in progress (separate track).
