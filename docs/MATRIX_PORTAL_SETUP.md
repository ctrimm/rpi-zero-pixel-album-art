# Matrix Portal Setup Guide (S3 and M4)

> **Hardware:** [Adafruit Matrix Portal S3 — ID:5778](https://www.adafruit.com/product/5778) *or*
> [Matrix Portal M4 — ID:4745](https://www.adafruit.com/product/4745), plus a 64×64 HUB75 RGB LED panel.

The same firmware runs on both boards and detects which one it's on.

**Which one do I have?** Look at the back of the board, or plug it in and check the
drive name / `boot_out.txt` on `CIRCUITPY`. If you bought it from Adafruit in the last
couple of years it's most likely the **S3** (a single ESP32-S3 chip with a little
metal-can WiFi module). The older **M4** has two chips: an ATSAMD51 plus an ESP32
WiFi co-processor.

| | Matrix Portal S3 | Matrix Portal M4 |
|---|---|---|
| Main chip | ESP32-S3 (WiFi built in) | SAMD51 + ESP32 WiFi co-processor |
| RAM | 512 KB + 2 MB PSRAM | 192 KB |
| Album art without companion | ✅ decoded on the board | ❌ text only |
| Colour depth | 6 bits | 4 bits (RAM) |
| Live scores without companion | ✅ | ✅ (small ESPN team feed) |

---

## What's in this port

| Feature | Notes |
|---|---|
| Album art + scrolling artist/track + progress bar | Companion (both boards) or standalone on the S3 |
| Automatic mode switching | Album art when music starts, clock when it stops. A mode you pick by hand stays until music starts again — same rules as the Pi version |
| Weather (current + 3-day) | Direct OpenWeatherMap or via the companion |
| Weather on the 8s | Classic Weather Channel-style local forecast at :08, :18, … :58 (~46 s), then back to what was showing |
| Sports scores | Live / final / upcoming, team colours and records (ESPN, no key) |
| Clock | Digital or analog, 12h or 24h, NTP-synced |
| Screensavers | Pipes and DVD logo |
| Brightness | Real dimming (software), night schedule, 0 = panel off |
| Web dashboard + admin panel | Served by the companion — same UI as the Pi version |
| Test pattern / clear | From the dashboard |
| Watchdog, WiFi auto-reconnect, last-good caching | For an always-on display |

---

## Part 1 — Install CircuitPython

1. Download the latest stable **CircuitPython 9.x (or newer)** `.uf2` for your board:
   - S3: [circuitpython.org/board/adafruit_matrixportal_s3](https://circuitpython.org/board/adafruit_matrixportal_s3/)
   - M4: [circuitpython.org/board/matrixportal_m4](https://circuitpython.org/board/matrixportal_m4/)
2. Double-tap the **RESET** button — the board mounts as a drive ending in `BOOT`.
3. Drag the `.uf2` onto that drive. The board reboots and mounts as `CIRCUITPY`.

## Part 2 — Install libraries

Easiest with [`circup`](https://github.com/adafruit/circup), which picks versions
matching your CircuitPython:

```bash
pip3 install circup
# With the board plugged in:
circup install adafruit_display_text adafruit_imageload adafruit_requests
circup install adafruit_esp32spi        # M4 only
```

Or copy those folders/files from the matching
[library bundle](https://circuitpython.org/libraries) into `CIRCUITPY/lib/`.

## Part 3 — Copy the firmware

Copy everything in `matrix-portal/` to the `CIRCUITPY` drive:

```
CIRCUITPY/
├── boot.py
├── code.py
├── settings.toml          ← fill in your values (Part 4)
├── modes/
└── utils/
```

> `boot.py` makes the drive writable *by the firmware* (for the last-good cache), so it
> becomes read-only on your computer. To edit files again, **hold the UP button while
> plugging in USB**.

## Part 4 — Configure `settings.toml`

Fill in WiFi and pick **one** way to get Spotify data:

- **With the companion (recommended):** set `COMPANION_URL` (Part 5). The companion
  handles Spotify, weather and sports; you only need WiFi on the board.
- **Standalone:** leave `COMPANION_URL` empty and set `SPOTIFY_CLIENT_ID`,
  `SPOTIFY_CLIENT_SECRET` and `SPOTIFY_REFRESH_TOKEN` (run `python companion.py --auth`
  once on any computer — it prints the refresh token), plus `OPENWEATHER_API_KEY` for weather.

The file is commented; the useful extras:

| Setting | Default | |
|---|---|---|
| `WEATHER_ON_8S` | `0` | local forecast at :08, :18, … :58. With the companion, its admin panel (*Weather*) controls this |
| `SHOW_TRACK_INFO` | `1` | song + artist over the album art (long names scroll); `0` = art only. With the companion, its admin panel (*Now playing*) controls this |
| `CLOCK_STYLE` | `digital` | or `analog` |
| `TIME_FORMAT` | `12h` | or `24h` |
| `AUTO_SWITCH` | `1` | album art when music starts, `FALLBACK_MODE` when it stops |
| `FALLBACK_MODE` | `clock` | any mode |
| `BRIGHTNESS_SCHEDULE` | — | e.g. `"07:00=60,22:00=15,01:00=0"` (0 = off) |
| `MODE_SCHEDULE` | — | e.g. `"07:00=clock,22:00=screensaver"` |
| `COMPANION_POLL_INTERVAL` | `3` | seconds |

Keep comments on their own lines in `settings.toml`.

## Part 5 — Run the companion

The companion runs on any always-on computer on your network — **a Raspberry Pi works
great**, as does a Mac/PC/Linux box. It reuses the Pi app's code in `src/`.

```bash
cd companion
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python companion.py               # first run creates companion_config.json
```

1. Open **http://localhost:5001/admin** (login `admin` / `admin` — change it under
   *Security*) and enter your Spotify **Client ID** and **secret** (from
   [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard), with
   redirect URI `http://127.0.0.1:8888/callback`), weather key, team, etc.
2. Sign in to Spotify once:
   ```bash
   python companion.py --auth
   ```
   On a machine without a browser (e.g. a headless Pi) it prints a URL: open it on
   your phone, sign in, and paste the `127.0.0.1:8888/...` address you land on back
   into the terminal. The running companion connects within a minute.
3. Set `COMPANION_URL = "http://<companion-ip>:5001"` on the board.

Auto-start on boot/login: `bash services/install_service.sh` (launchd on macOS,
systemd user service on Linux; run `loginctl enable-linger $USER` on a Pi).

Optional: `pip install zeroconf` advertises `http://matrixportal-companion.local:5001`
so you don't need a fixed IP (reliable on the S3; hit-or-miss on the M4).

**Dashboard:** `http://<companion-ip>:5001/` — mode buttons, brightness, now playing,
test pattern. **Admin:** `/admin`.

## Part 6 — Power on

1. Plug the panel's HUB75 connector into the board and screw down the power terminals.
2. Power the **panel** from a 5V 4A+ supply (not USB).
3. Power the board via USB-C. It connects to WiFi, syncs the clock and starts.

---

## Buttons

| Button | Action |
|---|---|
| **UP** | Next mode (music → weather → sports → clock → screensaver) — counts as picking by hand |
| **DOWN** | Brightness: off → 10 → 25 → 50 → 75 → 100 % |

Changes made with the buttons stick: the companion only overrides them when you change
something in the web UI.

## How brightness works

CircuitPython's LED matrix driver can only switch the panel on or off (any brightness
above 0 is full brightness). So the firmware dims in software: every colour on screen is
scaled to the brightness level, including album art. Very low levels lose some colour
detail, especially on the M4's 4-bit colour.

## Reliability

- **Watchdog** reboots the board if the firmware hangs (`ENABLE_WATCHDOG`).
- **WiFi auto-reconnect** every 30 s if the link drops.
- **Last-good cache**: album art, track, weather and scores are saved to flash so a
  reboot shows real content immediately. To protect the flash (it has no wear
  levelling), files are only written when their content changes and at most once every
  15 minutes each.
- **Time sync** from two sources, refreshed every 6 hours.

## Troubleshooting

| Problem | Fix |
|---|---|
| Only half the panel lights / image repeats | Use this firmware (it drives all 5 address lines). |
| Panel dim or flickery | Power supply: 5V, 4A+ for 64×64 |
| "No WiFi" | Check SSID/password; 2.4 GHz only |
| "Not set up" on the music screen | Set `COMPANION_URL` or the `SPOTIFY_*` settings |
| No album art (M4, no companion) | Expected — the M4 can't decode JPEGs. Use the companion |
| Dashboard says "Board offline" | Check `COMPANION_URL` on the board and that both are on the same network |
| Wrong time | `TIMEZONE_OFFSET` |
| `MemoryError` on the M4 | It recovers to the clock automatically. Use the companion for weather/sports, or lower `BIT_DEPTH` |

Serial console (prints what the board is doing): `screen /dev/tty.usbmodem* 115200`
(Mac/Linux) or the Mu editor / [code.circuitpython.org](https://code.circuitpython.org).

## Differences from the Raspberry Pi version

| Pi | Matrix Portal |
|---|---|
| Python on Linux | CircuitPython on a microcontroller |
| Web UI on the Pi | Web UI on the companion |
| Spotify login on the Pi | Login on the companion (or a refresh token in `settings.toml`) |
| Hardware brightness | Software dimming |
