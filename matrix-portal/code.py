# code.py — Main entry point for Matrix Portal M4 (64x64 RGB LED Matrix)
# Adafruit Matrix Portal M4 — CircuitPython 8+
#
# Copy the contents of matrix-portal/ to your CIRCUITPY drive.
# Required CircuitPython libraries (install from the library bundle):
#   adafruit_matrixportal, adafruit_esp32spi, adafruit_requests,
#   adafruit_display_text, adafruit_imageload, adafruit_datetime,
#   adafruit_bitmap_font (optional, for nicer fonts)

import board
import displayio
import rgbmatrix
import framebufferio
import gc
import os
import rtc
import time

# ── Display init ───────────────────────────────────────────────────────────────
displayio.release_displays()

matrix = rgbmatrix.RGBMatrix(
    width=64, height=64, bit_depth=4,
    rgb_pins=[
        board.MTX_R1, board.MTX_G1, board.MTX_B1,
        board.MTX_R2, board.MTX_G2, board.MTX_B2,
    ],
    addr_pins=[
        board.MTX_ADDRA, board.MTX_ADDRB,
        board.MTX_ADDRC, board.MTX_ADDRD,
    ],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE,
    tile=1, serpentine=True,
)
display = framebufferio.FramebufferDisplay(matrix, auto_refresh=True)


def set_display_brightness(pct):
    """Set panel brightness from a 0-100 percentage.

    Some CircuitPython versions don't expose a settable brightness on an
    rgbmatrix-backed FramebufferDisplay, so guard the assignment - a missing
    feature should dim nothing, not crash the boot or the poll loop.
    """
    try:
        display.brightness = max(0.05, min(1.0, int(pct) / 100.0))
    except (AttributeError, NotImplementedError, ValueError) as e:
        print(f"Brightness not adjustable on this display: {e}")

# ── Config from settings.toml ─────────────────────────────────────────────────
WIFI_SSID       = os.getenv("CIRCUITPY_WIFI_SSID", "")
WIFI_PASSWORD   = os.getenv("CIRCUITPY_WIFI_PASSWORD", "")
DEFAULT_MODE    = os.getenv("DEFAULT_MODE", "clock")
BRIGHTNESS      = int(os.getenv("BRIGHTNESS", "50"))
COMPANION_URL   = os.getenv("COMPANION_URL", "")
TZ_OFFSET       = int(os.getenv("TIMEZONE_OFFSET", "0"))
MODE_SCHEDULE   = os.getenv("MODE_SCHEDULE", "")
SCRNSAVER_TYPE  = os.getenv("SCREENSAVER_TYPE", "both")

SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN", "")

OWM_API_KEY    = os.getenv("OPENWEATHER_API_KEY", "")
WEATHER_LOC    = os.getenv("WEATHER_LOCATION", "New York,US")
WEATHER_UNITS  = os.getenv("WEATHER_UNITS", "imperial")

ESPN_LEAGUE    = os.getenv("ESPN_LEAGUE", "NBA")
ESPN_TEAM      = os.getenv("ESPN_TEAM", "LAL")

set_display_brightness(BRIGHTNESS)

# ── Splash screen ─────────────────────────────────────────────────────────────
from utils.display_helper import make_text_label, center_label, COLORS

splash = displayio.Group()
line1 = make_text_label("Matrix", color=COLORS["cyan"], y=22, scale=2)
center_label(line1, y=22)
line2 = make_text_label("Portal", color=COLORS["white"], y=40, scale=2)
center_label(line2, y=40)
splash.append(line1)
splash.append(line2)
display.root_group = splash
gc.collect()

# ── Network ───────────────────────────────────────────────────────────────────
from utils.network_helper import NetworkHelper
network = NetworkHelper(WIFI_SSID, WIFI_PASSWORD, timezone_offset=TZ_OFFSET)

print("Connecting to WiFi…")
line2.text = "WiFi…  "
center_label(line2, y=40)

connected = network.connect()
if connected:
    print("Syncing time…")
    line2.text = "Time…  "
    center_label(line2, y=40)
    network.sync_time()
else:
    print("WiFi failed — clock and offline modes only")
    line2.text = "No WiFi"
    center_label(line2, y=40)
    time.sleep(2)

gc.collect()
print(f"Free RAM after network init: {gc.mem_free()} bytes")

# ── Mode schedule parser ───────────────────────────────────────────────────────
def parse_schedule(schedule_str):
    """Parse "HH:MM=mode,HH:MM=mode" into sorted list of (hour, min, mode)."""
    entries = []
    if not schedule_str:
        return entries
    for part in schedule_str.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        time_str, mode = part.split("=", 1)
        time_str = time_str.strip()
        mode = mode.strip()
        if ":" in time_str:
            try:
                h, m = time_str.split(":")
                entries.append((int(h), int(m), mode))
            except ValueError:
                pass
    return sorted(entries, key=lambda e: e[0] * 60 + e[1])


def scheduled_mode(schedule, current_hour, current_min):
    """Return the mode that should be active at the given time."""
    if not schedule:
        return None
    current_minutes = current_hour * 60 + current_min
    best = None
    for h, m, mode in schedule:
        entry_minutes = h * 60 + m
        if entry_minutes <= current_minutes:
            best = mode
    if best is None:
        # Wrap: use the last entry of the previous day
        best = schedule[-1][2]
    return best


SCHEDULE = parse_schedule(MODE_SCHEDULE)

# ── Mode initialisation (lazy — only construct the active mode) ───────────────
from modes.clock_mode import ClockMode

_mode_instances = {}
_mode_constructors = {}

def _register_modes():
    global _mode_constructors
    _mode_constructors["clock"] = lambda: ClockMode(display)

    from modes.music_mode import MusicMode
    _mode_constructors["music"] = lambda: MusicMode(
        display, network,
        companion_url=COMPANION_URL,
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        refresh_token=SPOTIFY_REFRESH_TOKEN,
    )

    from modes.weather_mode import WeatherMode
    _mode_constructors["weather"] = lambda: WeatherMode(
        display, network,
        companion_url=COMPANION_URL,
        api_key=OWM_API_KEY,
        location=WEATHER_LOC,
        units=WEATHER_UNITS,
    )

    from modes.sports_mode import SportsMode
    _mode_constructors["sports"] = lambda: SportsMode(
        display, network,
        companion_url=COMPANION_URL,
        league=ESPN_LEAGUE,
        team=ESPN_TEAM,
    )

    from modes.screensaver_mode import ScreensaverMode
    _mode_constructors["screensaver"] = lambda: ScreensaverMode(
        display, screensaver_type=SCRNSAVER_TYPE
    )


def get_mode(name):
    """Return (or lazily construct) a mode instance by name."""
    if name not in _mode_constructors:
        name = "clock"
    if name not in _mode_instances:
        print(f"Constructing mode: {name}")
        gc.collect()
        _mode_instances[name] = _mode_constructors[name]()
        gc.collect()
    return _mode_instances[name]


print("Registering modes…")
_register_modes()
gc.collect()
print(f"Free RAM after mode registration: {gc.mem_free()} bytes")

# ── Main loop ─────────────────────────────────────────────────────────────────
current_mode_name = DEFAULT_MODE
current_mode = None

# Track state for companion polling
last_companion_poll = 0
COMPANION_POLL_INTERVAL = 10  # seconds
manual_override = False
manual_override_until = 0

# Time-sync refresh (every 6 hours)
last_time_sync = time.monotonic()
TIME_SYNC_INTERVAL = 6 * 3600

def switch_mode(name, manual=False):
    global current_mode_name, current_mode, manual_override, manual_override_until
    if name not in _mode_constructors:
        print(f"Unknown mode: {name}")
        return
    if name == current_mode_name and current_mode is not None:
        return
    print(f"Switching to mode: {name}")
    if current_mode is not None:
        try:
            current_mode.on_exit()
        except Exception as e:
            print(f"on_exit error: {e}")
    gc.collect()
    current_mode_name = name
    current_mode = get_mode(name)
    current_mode.on_enter()
    if manual:
        manual_override = True
        manual_override_until = time.monotonic() + 3600  # hold manual for 1 hour


# Initial mode
switch_mode(current_mode_name)
print(f"Started — mode: {current_mode_name}  RAM: {gc.mem_free()} bytes")

while True:
    try:
        now = time.monotonic()
        t = rtc.RTC().datetime

        # ── Periodic time sync ────────────────────────────────────────────────
        if connected and (now - last_time_sync) >= TIME_SYNC_INTERVAL:
            last_time_sync = now
            network.sync_time()

        # ── Manual override expiry ────────────────────────────────────────────
        if manual_override and now >= manual_override_until:
            manual_override = False

        # ── Companion polling (mode commands + brightness) ────────────────────
        if COMPANION_URL and (now - last_companion_poll) >= COMPANION_POLL_INTERVAL:
            last_companion_poll = now
            try:
                status = network.get_json(f"{COMPANION_URL}/api/matrix/status")
                if status:
                    new_brightness = status.get("brightness")
                    if new_brightness is not None:
                        set_display_brightness(new_brightness)

                    new_mode = status.get("mode")
                    if new_mode and new_mode != current_mode_name:
                        switch_mode(new_mode, manual=status.get("manual", False))
            except Exception as e:
                print(f"Companion poll error: {e}")

        # ── Schedule-based mode switching (if no manual override) ─────────────
        if not manual_override and SCHEDULE:
            sched_mode = scheduled_mode(SCHEDULE, t.tm_hour, t.tm_min)
            if sched_mode and sched_mode != current_mode_name:
                switch_mode(sched_mode)

        # ── Update current mode ───────────────────────────────────────────────
        if current_mode:
            current_mode.update()

        gc.collect()

    except MemoryError as e:
        print(f"MemoryError: {e} — switching to clock to recover")
        _mode_instances.clear()
        gc.collect()
        current_mode_name = ""
        current_mode = None
        switch_mode("clock")
        time.sleep(2)

    except Exception as e:
        print(f"Main loop error: {e}")
        time.sleep(0.5)
