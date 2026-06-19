# Matrix Portal M4 Setup Guide

> **Branch:** `claude/port-matrix-portal-LFL6w`
> **Hardware:** [Adafruit Matrix Portal M4 — ID:4745](https://www.adafruit.com/product/4745)
> **Display:** 64×64 HUB75 RGB LED Matrix Panel

---

## What's in this port

| Feature | Status | Notes |
|---|---|---|
| Album art display | ✅ | Requires companion for JPEG→BMP conversion |
| Scrolling artist / track | ✅ | |
| Weather (current + 3-day) | ✅ | Direct OWM API or via companion |
| Sports scores | ✅ | Direct ESPN API (no key needed) |
| Clock | ✅ | NTP-synced |
| Pipes screensaver | ✅ | |
| DVD logo screensaver | ✅ | Rainbow color on bounce |
| Mode schedule | ✅ | `settings.toml` |
| Web control panel | ✅ | Served by desktop companion |
| Spotify OAuth | ✅ | Handled by desktop companion |

---

## Hardware needed

- Adafruit Matrix Portal M4 (ID:4745)
- 64×64 HUB75 RGB LED matrix panel (P3 pitch works great indoors)
- 5V 4A+ power supply (matrix requires its own power — **not** USB)
- USB-C cable (for programming / serial)

---

## Part 1 — Install CircuitPython

1. Download the latest **CircuitPython 8.x** UF2 for Matrix Portal M4 from  
   [circuitpython.org/board/adafruit_matrixportal_m4](https://circuitpython.org/board/adafruit_matrixportal_m4)

2. Hold the **RESET** button, then double-tap it quickly — the board mounts as `MATRIXBOOT`.

3. Drag the `.uf2` file onto `MATRIXBOOT`. The board reboots and mounts as `CIRCUITPY`.

---

## Part 2 — Install CircuitPython libraries

Download the **CircuitPython 8.x library bundle** from  
[circuitpython.org/libraries](https://circuitpython.org/libraries)

### Easiest: use `circup` (recommended)

`circup` installs exactly the right library versions for your board with one
command — far less error-prone than copying folders from the bundle by hand:

```bash
pip3 install circup
# With the board plugged in (mounted as CIRCUITPY):
circup install adafruit_display_text adafruit_imageload adafruit_esp32spi \
               adafruit_requests adafruit_datetime
```

To update everything later: `circup update`.

### Manual alternative

If you'd rather not use `circup`, copy these from the
[CircuitPython 8.x library bundle](https://circuitpython.org/libraries) into
`CIRCUITPY/lib/`:

```
adafruit_display_text/
adafruit_imageload/
adafruit_esp32spi/
adafruit_requests.mpy
adafruit_datetime.mpy
```

---

## Part 3 — Copy project files

Copy the contents of `matrix-portal/` from this repo onto your `CIRCUITPY` drive:

```
CIRCUITPY/
├── boot.py
├── code.py
├── settings.toml          ← fill in your values
├── modes/
│   ├── clock_mode.py
│   ├── music_mode.py
│   ├── weather_mode.py
│   ├── sports_mode.py
│   └── screensaver_mode.py
└── utils/
    ├── display_helper.py
    ├── network_helper.py
    └── storage_helper.py
```

---

## Part 4 — Configure `settings.toml`

Open `CIRCUITPY/settings.toml` and fill in your values:

```toml
CIRCUITPY_WIFI_SSID = "YourNetwork"
CIRCUITPY_WIFI_PASSWORD = "YourPassword"

# Get these from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = "abc123..."
SPOTIFY_CLIENT_SECRET = "def456..."
SPOTIFY_REFRESH_TOKEN = ""        # filled in after running companion --auth

OPENWEATHER_API_KEY = ""          # https://openweathermap.org/api (free tier)
WEATHER_LOCATION = "Chicago,US"
WEATHER_UNITS = "imperial"        # or "metric"

ESPN_LEAGUE = "NBA"               # NFL, NBA, MLB, NHL
ESPN_TEAM = "CHI"                 # team abbreviation

BRIGHTNESS = 50
DEFAULT_MODE = "music"            # music, weather, sports, clock, screensaver

# Your desktop companion's local IP + port (see Part 5)
COMPANION_URL = "http://192.168.1.100:5001"

TIMEZONE_OFFSET = -6              # hours from UTC (-5=EST, -6=CST, -7=MST, -8=PST)
SCREENSAVER_TYPE = "both"         # pipes, dvd, or both

# Optional mode schedule — comment out to disable
# MODE_SCHEDULE = "07:00=clock,09:00=music,22:30=screensaver"

# Optional night dimming — bright by day, dim after 10pm
# BRIGHTNESS_SCHEDULE = "07:00=60,22:00=15"

ENABLE_WATCHDOG = 1               # auto-reboot if the firmware hangs (1=on, 0=off)
```

### Notes on the newer options

- **`BRIGHTNESS_SCHEDULE`** — `HH:MM=PERCENT` pairs. The panel dims/brightens at
  each boundary; you can still nudge brightness with the DOWN button or the web
  UI in between, and it sticks until the next scheduled change.
- **`ENABLE_WATCHDOG`** — a hardware watchdog reboots the board if it ever wedges
  (e.g. a stuck network stack). Recommended for an always-on display.

---

## Part 5 — Run the desktop companion

The companion runs on your Mac/PC/Linux machine and handles:
- Spotify OAuth (full browser-based flow)
- Resizing + converting album art to 64×64 BMP for the Matrix Portal
- Web control panel at `http://localhost:5001`
- Proxying weather and sports data (optional)

### Install companion dependencies

```bash
cd companion
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### First-time Spotify auth

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Create an app, add `http://127.0.0.1:8888/callback` as a Redirect URI
3. Copy your Client ID and Client Secret into `companion/companion_config.json`  
   (the file is created automatically on first run — run the server once, then edit it)
4. Run:
   ```bash
   python companion.py --auth
   ```
   Follow the prompts, paste the redirect URL. A token is saved to `.spotify_token.json`.

### Run the companion

```bash
python companion.py
# or specify a port:
python companion.py --port 5001
```

Find your machine's local IP (`ifconfig` / `ipconfig`) and set `COMPANION_URL` in `settings.toml`.

### Keep the companion running (auto-start on login/boot)

So you don't have to start it by hand every time:

```bash
cd companion
bash services/install_service.sh
```

This installs a **launchd agent** on macOS or a **systemd user service** on Linux
that starts the companion automatically and restarts it if it crashes. (On Linux,
`loginctl enable-linger $USER` keeps it running even when you're logged out.)

### Optional: find the companion by name instead of IP (mDNS)

If you `pip install zeroconf` in the companion's venv, it advertises itself as
`matrixportal-companion.local`. You can then set:

```toml
COMPANION_URL = "http://matrixportal-companion.local:5001"
```

and never worry about your computer's IP changing. (mDNS resolution is reliable
on the S3 board's native WiFi; on the M4's ESP32 co-processor it can be hit or
miss — if music art stops working, fall back to the numeric IP.)

Open **http://localhost:5001** in your browser for the web control panel.

---

## Part 6 — Power on

1. Connect the matrix panel to the Matrix Portal (the HUB75 connector goes directly on the back).
2. Connect the **external 5V power supply** to the matrix panel's power connector — **not** through the Matrix Portal's USB.
3. Connect USB-C to your computer or a USB charger for the Matrix Portal's logic power.
4. The Matrix Portal boots, connects to WiFi, syncs the clock, and starts the default mode.

---

## Modes

| Mode | Description |
|---|---|
| `music` | Album art + scrolling artist/track. Requires companion + Spotify. |
| `weather` | Current conditions + 3-day forecast. Requires OWM API key. |
| `sports` | Live scores for your team. No API key needed. |
| `clock` | Digital clock + date. Works fully offline. |
| `screensaver` | Pipes and/or DVD logo. Works fully offline. |

Switch modes from the web control panel at `http://<companion-ip>:5001/`.

The **music** screen also shows a now-playing progress bar along the bottom and
keeps the scrolling artist/track readable with a dim band behind the text.

---

## On-device controls (buttons)

No phone needed — the two buttons on the Matrix Portal work standalone:

| Button | Action |
|---|---|
| **UP** | Cycle to the next mode (music → weather → sports → clock → screensaver) |
| **DOWN** | Step brightness (10 → 25 → 50 → 75 → 100 → 10 %) |

> Holding **UP** while plugging in USB still drops to file-editing mode (the drive
> becomes writable from your computer) — that's handled by `boot.py` before the
> firmware starts, so it doesn't conflict with the in-app button actions.

---

## Reliability (always-on display)

This build is meant to run unattended on a wall:

- **Watchdog** — if the firmware ever hangs, the board auto-reboots (toggle with
  `ENABLE_WATCHDOG`).
- **WiFi auto-reconnect** — if your network blips, it reconnects on its own
  instead of silently going dark.
- **Last-good caching** — the most recent album art, weather, and scores are
  saved to flash, so after a reboot or power cut the panel shows real content
  immediately instead of placeholders while it reconnects.
- **Robust time sync** — falls back to a second time source if the primary is
  down, so the clock stays correct.

---

## Offline operation

If you don't want to use the companion (or have no computer running), the Matrix Portal can:
- Show the **clock** without any network (after initial NTP sync)
- Show **screensavers** without any network
- Show **weather** and **sports** directly (no companion needed — set API keys in `settings.toml`)
- Show **music** text-only (no album art — requires Spotify credentials in `settings.toml`)

Set `COMPANION_URL = ""` to run fully standalone.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Display is dim or flickering | Check the external 5V power supply — needs at least 4A for a 64×64 panel |
| WiFi won't connect | Verify SSID/password in `settings.toml`; 2.4GHz only |
| `MemoryError` | The device recovers automatically and switches to clock mode. File a GitHub issue if persistent. |
| Album art not showing | Confirm companion is running and `COMPANION_URL` is correct; check companion logs |
| Time is wrong | Check `TIMEZONE_OFFSET` in `settings.toml` |
| Serial output | Connect via USB and open a serial terminal at 115200 baud |

For serial output on Mac/Linux:
```bash
screen /dev/tty.usbmodem* 115200
# or
ls /dev/tty.usbmodem* && cat /dev/tty.usbmodem*
```

---

## Memory tips

The SAMD51 has 512KB RAM. If you hit `MemoryError`:
- Set `DEFAULT_MODE = "clock"` and switch modes manually via the web UI
- Reduce `bit_depth` from `4` to `3` in `code.py` (slightly less color depth)
- Disable modes you don't use by commenting out their constructors in `code.py`

---

## Differences from the Raspberry Pi version

| Pi Version | Matrix Portal Version |
|---|---|
| Full Python (CPython) | CircuitPython 8 |
| `rpi-rgb-led-matrix` | `rgbmatrix` (built-in to CircuitPython) |
| Flask web server on device | Flask companion on desktop |
| Full Spotify OAuth on device | OAuth on companion, token stored in `settings.toml` |
| `spotipy` library | Direct Spotify API calls |
| `pyowm` library | Direct OpenWeatherMap API calls |
| `espn-api` library | Direct ESPN API calls |
| Threading | Single-threaded with cooperative updates |
| LED simulator (dev mode) | Use REPL / serial output for debugging |
