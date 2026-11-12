# code.py — Main entry point for Adafruit Matrix Portal S3 / M4 (64x64 RGB LED Matrix)
# CircuitPython 9+
#
# Works on both boards and detects which one it's running on:
#   - Matrix Portal S3 (ESP32-S3, native WiFi, jpegio + bitmaptools available)
#   - Matrix Portal M4 (SAMD51 + ESP32 WiFi co-processor over SPI)
#
# Copy the contents of matrix-portal/ to your CIRCUITPY drive.
# Required libraries (from the matching CircuitPython library bundle):
#   adafruit_display_text, adafruit_imageload, adafruit_requests
#   (+ adafruit_esp32spi on the M4)

import board
import displayio
import rgbmatrix
import framebufferio
import gc
import os
import rtc
import time

from utils.network_helper import NetworkHelper, BOARD_NAME
from utils.display_helper import (
    make_text_label, center_label, make_palette, make_bitmap, dimmer, COLORS,
)
from utils.now_playing import NowPlaying
from utils import storage_helper

IS_S3 = BOARD_NAME == "S3"

# ── Config from settings.toml ─────────────────────────────────────────────────
def _setting(name, default):
    value = os.getenv(name)
    return default if value is None else value


def _int_setting(name, default):
    try:
        return int(_setting(name, default))
    except (TypeError, ValueError):
        print(f"Bad {name} in settings.toml - using {default}")
        return default


WIFI_SSID       = _setting("CIRCUITPY_WIFI_SSID", "")
WIFI_PASSWORD   = _setting("CIRCUITPY_WIFI_PASSWORD", "")
DEFAULT_MODE    = _setting("DEFAULT_MODE", "clock")
BRIGHTNESS      = _int_setting("BRIGHTNESS", 50)
COMPANION_URL   = _setting("COMPANION_URL", "").rstrip("/")
TZ_OFFSET       = _int_setting("TIMEZONE_OFFSET", 0)
MODE_SCHEDULE   = _setting("MODE_SCHEDULE", "")
SCRNSAVER_TYPE  = _setting("SCREENSAVER_TYPE", "both")

SPOTIFY_CLIENT_ID     = _setting("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = _setting("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REFRESH_TOKEN = _setting("SPOTIFY_REFRESH_TOKEN", "")

OWM_API_KEY    = _setting("OPENWEATHER_API_KEY", "")
WEATHER_LOC    = _setting("WEATHER_LOCATION", "New York,US")
WEATHER_UNITS  = _setting("WEATHER_UNITS", "imperial")

ESPN_LEAGUE    = _setting("ESPN_LEAGUE", "NBA")
ESPN_TEAM      = _setting("ESPN_TEAM", "LAL")

CLOCK_STYLE    = _setting("CLOCK_STYLE", "digital")
TIME_FORMAT    = _setting("TIME_FORMAT", "12h")
AUTO_SWITCH    = _int_setting("AUTO_SWITCH", 1)
FALLBACK_MODE  = _setting("FALLBACK_MODE", "clock")
COMPANION_POLL = max(1, _int_setting("COMPANION_POLL_INTERVAL", 3))
BIT_DEPTH      = _int_setting("BIT_DEPTH", 6 if IS_S3 else 4)

BRIGHTNESS_SCHEDULE = _setting("BRIGHTNESS_SCHEDULE", "")
ENABLE_WATCHDOG     = _int_setting("ENABLE_WATCHDOG", 1)

VALID_MODES = ("music", "weather", "sports", "clock", "screensaver")

# ── Display init ───────────────────────────────────────────────────────────────
displayio.release_displays()

# A 64x64 panel needs 5 address lines (A-E): 2 x 2^5 = 64 rows. With only A-D
# CircuitPython computes a 32-row panel and refuses to start.
matrix = rgbmatrix.RGBMatrix(
    width=64, height=64, bit_depth=max(1, min(6, BIT_DEPTH)),
    rgb_pins=[
        board.MTX_R1, board.MTX_G1, board.MTX_B1,
        board.MTX_R2, board.MTX_G2, board.MTX_B2,
    ],
    addr_pins=[
        board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC,
        board.MTX_ADDRD, board.MTX_ADDRE,
    ],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE,
    tile=1, serpentine=True,
)
display = framebufferio.FramebufferDisplay(matrix, auto_refresh=True)

current_brightness = max(0, min(100, BRIGHTNESS))


def set_brightness(pct):
    """0 turns the panel off; 1-100 dims in software (rgbmatrix itself can
    only switch the panel on or off)."""
    global current_brightness
    pct = max(0, min(100, int(pct)))
    current_brightness = pct
    try:
        display.brightness = 0.0 if pct == 0 else 1.0
    except (AttributeError, NotImplementedError, ValueError) as e:
        print(f"Can't switch display on/off: {e}")
    if pct:
        dimmer.set_level(pct)


set_brightness(current_brightness)

# ── Splash screen ─────────────────────────────────────────────────────────────
splash = displayio.Group()
line1 = make_text_label("Matrix", color=COLORS["cyan"], y=22, scale=2)
center_label(line1, y=22)
line2 = make_text_label("Portal", color=COLORS["white"], y=40, scale=2)
center_label(line2, y=40)
splash.append(line1)
splash.append(line2)
display.root_group = splash
gc.collect()


def splash_status(text):
    line2.text = text
    center_label(line2, y=40)


# ── Network ───────────────────────────────────────────────────────────────────
network = NetworkHelper(WIFI_SSID, WIFI_PASSWORD, timezone_offset=TZ_OFFSET)

print(f"Matrix Portal {BOARD_NAME} — connecting to WiFi…")
splash_status("WiFi")

connected = network.connect()
if connected:
    print("Syncing time…")
    splash_status("Time")
    network.sync_time()
else:
    print("WiFi failed — clock and offline modes only")
    splash_status("No WiFi")
    time.sleep(2)

gc.collect()
print(f"Free RAM after network init: {gc.mem_free()} bytes")

now_playing = NowPlaying(
    network, companion_url=COMPANION_URL, client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET, refresh_token=SPOTIFY_REFRESH_TOKEN,
)


# ── Schedules ─────────────────────────────────────────────────────────────────
def _parse_schedule(schedule_str, convert):
    """Parse "HH:MM=value,HH:MM=value" into sorted (minutes, value) pairs."""
    entries = []
    for part in (schedule_str or "").split(","):
        if "=" not in part:
            continue
        time_str, value = part.split("=", 1)
        try:
            h, m = time_str.strip().split(":")
            entries.append((int(h) * 60 + int(m), convert(value.strip())))
        except ValueError:
            pass
    return sorted(entries, key=lambda e: e[0])


def _scheduled(schedule, t):
    """Value of the schedule entry in effect at struct_time t (wraps past midnight)."""
    if not schedule:
        return None
    now_min = t.tm_hour * 60 + t.tm_min
    best = schedule[-1][1]
    for minutes, value in schedule:
        if minutes <= now_min:
            best = value
    return best


SCHEDULE = _parse_schedule(MODE_SCHEDULE, str)
BRIGHT_SCHEDULE = _parse_schedule(BRIGHTNESS_SCHEDULE, int)


def validate_settings():
    """Return a list of human-readable config problems (empty == all good)."""
    warnings = []
    if not WIFI_SSID:
        warnings.append("No WiFi SSID")
    if DEFAULT_MODE not in VALID_MODES:
        warnings.append("Bad DEFAULT_MODE")
    if DEFAULT_MODE == "music" and not now_playing.available:
        warnings.append("Music: no Spotify")
    if DEFAULT_MODE == "weather" and not OWM_API_KEY and not COMPANION_URL:
        warnings.append("No weather key")
    return warnings


_setting_warnings = validate_settings()
if _setting_warnings:
    print("Settings warnings:", _setting_warnings)
    line1.text = "Check"
    center_label(line1, y=22)
    for _w in _setting_warnings:
        splash_status(_w[:10])
        time.sleep(1.5)

# ── Modes (constructed lazily — only the active one is in RAM) ────────────────
from modes.clock_mode import ClockMode

_mode_instances = {}
_mode_constructors = {
    "clock": lambda: ClockMode(display, style=CLOCK_STYLE, time_format=TIME_FORMAT),
}


def _register_modes():
    from modes.music_mode import MusicMode
    _mode_constructors["music"] = lambda: MusicMode(
        display, network, now_playing, companion_url=COMPANION_URL)

    from modes.weather_mode import WeatherMode
    _mode_constructors["weather"] = lambda: WeatherMode(
        display, network, companion_url=COMPANION_URL, api_key=OWM_API_KEY,
        location=WEATHER_LOC, units=WEATHER_UNITS)

    from modes.sports_mode import SportsMode
    _mode_constructors["sports"] = lambda: SportsMode(
        display, network, companion_url=COMPANION_URL, league=ESPN_LEAGUE,
        team=ESPN_TEAM, tz_offset=TZ_OFFSET)

    from modes.screensaver_mode import ScreensaverMode
    _mode_constructors["screensaver"] = lambda: ScreensaverMode(
        display, screensaver_type=SCRNSAVER_TYPE)


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

# ── Hardware watchdog ─────────────────────────────────────────────────────────
# Auto-reboot if the firmware hangs (e.g. a wedged network stack). The network
# helper feeds it during requests so legitimate I/O isn't cut short.
_watchdog = None
if ENABLE_WATCHDOG:
    try:
        import microcontroller
        from watchdog import WatchDogMode
        microcontroller.watchdog.timeout = 16  # seconds (SAMD51 max ~16.4)
        microcontroller.watchdog.mode = WatchDogMode.RESET
        _watchdog = microcontroller.watchdog
        print("Watchdog enabled (16s)")
    except Exception as e:
        print(f"Watchdog unavailable: {e}")


def feed_watchdog():
    if _watchdog is not None:
        try:
            _watchdog.feed()
        except Exception:
            pass


# ── Hardware buttons (UP = next mode, DOWN = cycle brightness) ─────────────────
import digitalio


def _make_button(pin):
    try:
        b = digitalio.DigitalInOut(pin)
        b.switch_to_input(pull=digitalio.Pull.UP)
        return b
    except Exception as e:
        print(f"Button init failed ({pin}): {e}")
        return None


btn_up = _make_button(board.BUTTON_UP)
btn_down = _make_button(board.BUTTON_DOWN)
_btn_up_prev = True       # pulled-up: True = released, False = pressed
_btn_down_prev = True
_btn_last_press = 0
_BTN_DEBOUNCE = 0.3       # seconds
BRIGHTNESS_LEVELS = [0, 10, 25, 50, 75, 100]   # 0 = panel off


def _pressed(btn, prev):
    """Return (is_fresh_press, new_prev) for an active-low button."""
    if btn is None:
        return (False, prev)
    val = btn.value
    return (prev and not val, val)


# ── Mode switching (same rules as the Pi app) ─────────────────────────────────
current_mode_name = None
current_mode = None
manual_mode = False       # user picked the mode (button / web UI)
_was_playing = False


def switch_mode(name, manual=False):
    global current_mode_name, current_mode, manual_mode
    if manual:
        manual_mode = True
    if name not in _mode_constructors:
        print(f"Unknown mode: {name}")
        return
    if name == current_mode_name and current_mode is not None:
        return
    print(f"Switching to mode: {name}{' (manual)' if manual else ''}")
    if current_mode is not None:
        try:
            current_mode.on_exit()
        except Exception as e:
            print(f"on_exit error: {e}")
    # Drop the previous mode's palettes/labels from the dimmer so they can be
    # garbage-collected, then build the new mode at the current brightness.
    dimmer.reset()
    gc.collect()
    current_mode_name = name
    current_mode = get_mode(name)
    current_mode.on_enter()


def cycle_mode():
    order = [m for m in VALID_MODES if m in _mode_constructors]
    idx = order.index(current_mode_name) if current_mode_name in order else -1
    switch_mode(order[(idx + 1) % len(order)], manual=True)


def check_auto_switch(t):
    """Album art when music starts, fallback when it stops, schedules otherwise.
    A mode picked by hand wins until playback *starts* again."""
    global manual_mode, _was_playing
    playing = now_playing.is_playing
    started = playing and not _was_playing
    _was_playing = playing

    if AUTO_SWITCH and now_playing.available and playing and (started or not manual_mode):
        manual_mode = False
        if current_mode_name != "music":
            print("Auto: music started")
            switch_mode("music")
        return

    if manual_mode:
        return

    sched = _scheduled(SCHEDULE, t)
    if sched and sched in VALID_MODES:
        if sched != current_mode_name:
            switch_mode(sched)
        return

    # Music stopped/paused while showing album art -> fallback (after the first
    # real Spotify answer, so we don't flip to the clock during boot)
    if (AUTO_SWITCH and now_playing.available and now_playing.fetched_at
            and current_mode_name == "music" and not playing
            and FALLBACK_MODE in VALID_MODES and FALLBACK_MODE != "music"):
        print("Auto: music stopped")
        switch_mode(FALLBACK_MODE)


# ── Test pattern / clear (from the web dashboard) ─────────────────────────────
_overlay_until = 0


def show_overlay(kind, seconds):
    global _overlay_until
    group = displayio.Group()
    if kind == "test_pattern":
        bmp = make_bitmap(64, 64, 3)
        for x in range(64):
            for y in range(64):
                bmp[x, y] = 0 if x < 21 else (1 if x < 42 else 2)
        group.append(displayio.TileGrid(
            bmp, pixel_shader=make_palette([0xFF0000, 0x00FF00, 0x0000FF])))
    display.root_group = group     # empty group == cleared panel
    _overlay_until = time.monotonic() + seconds


def end_overlay():
    global _overlay_until
    _overlay_until = 0
    if current_mode is not None and getattr(current_mode, "_group", None) is not None:
        display.root_group = current_mode._group


# ── Companion polling ─────────────────────────────────────────────────────────
_seen = {"mode_seq": None, "brightness": None, "command_seq": None}


def poll_companion():
    """One request for everything: mode/brightness changes from the web UI,
    dashboard commands, and the current Spotify track. Also reports this
    device's state so the dashboard shows what's really on screen."""
    url = (f"{COMPANION_URL}/api/matrix/status?mode={current_mode_name}"
           f"&manual={1 if manual_mode else 0}&brightness={current_brightness}"
           f"&board={BOARD_NAME}")
    status, data = network.request("GET", url, retries=1)
    if status != 200 or not data:
        return
    first = _seen["mode_seq"] is None

    # Follow the web UI only when it *changed* something - otherwise the
    # companion's stored values would undo button presses on the device.
    seq = data.get("mode_seq")
    if seq != _seen["mode_seq"]:
        _seen["mode_seq"] = seq
        if not first and data.get("mode") in VALID_MODES:
            switch_mode(data["mode"], manual=True)

    bright = data.get("brightness")
    if bright is not None and bright != _seen["brightness"]:
        _seen["brightness"] = bright
        if not first and int(bright) != current_brightness:
            set_brightness(bright)

    cseq = data.get("command_seq")
    if cseq != _seen["command_seq"]:
        _seen["command_seq"] = cseq
        if not first and data.get("command") in ("test_pattern", "clear"):
            show_overlay(data["command"], 5 if data["command"] == "test_pattern" else 3)

    if "track" in data:
        now_playing.apply_companion(data.get("track"))


# ── Main loop ─────────────────────────────────────────────────────────────────
# Clean up memory only when it's getting low (a full collection on every pass
# stalls scrolling text and animations, especially on the M4).
LOW_MEMORY = 40_000 if not IS_S3 else 200_000

last_companion_poll = -COMPANION_POLL
last_time_sync = time.monotonic()
TIME_SYNC_INTERVAL = 6 * 3600
last_wifi_check = 0
WIFI_CHECK_INTERVAL = 30
last_flush = time.monotonic()
last_scheduled_brightness = None

switch_mode(DEFAULT_MODE if DEFAULT_MODE in VALID_MODES else "clock")
print(f"Started on Matrix Portal {BOARD_NAME} — mode: {current_mode_name}  RAM: {gc.mem_free()} bytes")

while True:
    try:
        feed_watchdog()
        now = time.monotonic()
        t = rtc.RTC().datetime

        # ── Hardware buttons ──────────────────────────────────────────────────
        up_press, _btn_up_prev = _pressed(btn_up, _btn_up_prev)
        down_press, _btn_down_prev = _pressed(btn_down, _btn_down_prev)
        if (up_press or down_press) and (now - _btn_last_press) >= _BTN_DEBOUNCE:
            _btn_last_press = now
            if up_press:
                cycle_mode()
            else:
                nxt = next((lvl for lvl in BRIGHTNESS_LEVELS if lvl > current_brightness),
                           BRIGHTNESS_LEVELS[0])
                set_brightness(nxt)
                print(f"Brightness → {nxt}%")

        # ── WiFi link health (reconnect if it dropped) ────────────────────────
        if WIFI_SSID and (now - last_wifi_check) >= WIFI_CHECK_INTERVAL:
            last_wifi_check = now
            connected = network.ensure_connected()

        # ── Periodic time sync ────────────────────────────────────────────────
        if connected and (now - last_time_sync) >= TIME_SYNC_INTERVAL:
            last_time_sync = now
            network.sync_time()

        # ── Night dimming (brightness schedule) ───────────────────────────────
        if BRIGHT_SCHEDULE:
            sb = _scheduled(BRIGHT_SCHEDULE, t)
            if sb is not None and sb != last_scheduled_brightness:
                last_scheduled_brightness = sb
                set_brightness(sb)

        # ── Data: companion (one request) or Spotify directly ─────────────────
        if connected:
            if COMPANION_URL:
                if now - last_companion_poll >= COMPANION_POLL:
                    last_companion_poll = now
                    poll_companion()
            elif (current_mode_name == "music" or AUTO_SWITCH) and \
                    now_playing.due(now, foreground=current_mode_name == "music"):
                now_playing.poll_spotify()

        check_auto_switch(t)

        # ── Draw ──────────────────────────────────────────────────────────────
        if _overlay_until:
            if now >= _overlay_until:
                end_overlay()
        elif current_mode:
            current_mode.update()

        # ── Housekeeping ──────────────────────────────────────────────────────
        if now - last_flush >= 60:
            last_flush = now
            storage_helper.flush()
        if gc.mem_free() < LOW_MEMORY:
            gc.collect()

        # Yield briefly: lets background tasks (WiFi, display refresh) run and
        # stops the loop pegging the CPU. Animations step on their own timers.
        time.sleep(0.01)

    except MemoryError as e:
        print(f"MemoryError: {e} — switching to clock to recover")
        _mode_instances.clear()
        dimmer.reset()
        gc.collect()
        current_mode_name = None
        current_mode = None
        switch_mode("clock")
        time.sleep(2)

    except Exception as e:
        print(f"Main loop error: {e}")
        time.sleep(0.5)
