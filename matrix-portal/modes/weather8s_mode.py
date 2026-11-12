# weather8s_mode.py — Weather on the 8s for the Matrix Portal (S3 / M4)
#
# Same sequence and look as the Pi version: at :08, :18, :28, :38, :48 and :58
# it takes over the panel for ~46 seconds (intro, current conditions, details,
# next hours x2, 3-day, outro) and then hands the screen back.
#
# Data: the companion's /api/matrix/weather "w8" block, or OpenWeatherMap
# directly (utils/weather_summary.py - a port of the Pi's summary code).
import displayio
import gc
import time

from utils.display_helper import (
    make_text_label, make_palette, make_bitmap, fill_bitmap, set_label_color, dimmer,
    register_palette,
)
from utils.weather_summary import summarize

OWM_CURRENT = "https://api.openweathermap.org/data/2.5/weather?q={q}&appid={k}&units={u}"
OWM_FORECAST = "https://api.openweathermap.org/data/2.5/forecast?q={q}&appid={k}&units={u}&cnt={n}"

TRIGGER_MINUTES = (8, 18, 28, 38, 48, 58)
LATE_START_LIMIT = 45
DATA_MAX_AGE = 600
STALE_LIMIT = 3 * 3600

YELLOW, WHITE, GREY, LIGHT_BLUE = 0xFFD600, 0xFFFFFF, 0xAAB4D2, 0x8CBEFF
HEADER = 0x2341AF
COND_COLORS = {"Clear": 0xFFD600, "Cloudy": 0xBEBEC8, "Rain": 0x5AA0FF,
               "Drizzle": 0x78B4FF, "Storms": 0xFF8C28, "Snow": 0xEBF5FF}
DEG = chr(176)

SEQUENCE = (("intro", 3), ("current", 8), ("details", 8),
            ("hourly0", 8), ("hourly1", 8), ("daily", 8), ("outro", 3))
_POOL = 10   # labels reused across screens
ICON_DIR = "/icons"   # sprite sheets exported from src/utils/weather_icons.py
ICON_SIZE = 12
ICON_FRAMES = 8
ICON_FPS = 10


def _fit(text, max_px=62):
    text = str(text)
    return text[:max(1, max_px // 6)]


class WeatherOn8s:
    def __init__(self, display, network, companion_url="", api_key="",
                 location="New York,US", units="imperial", enabled=False, small_ram=False):
        self.display = display
        self.network = network
        self.companion_url = companion_url.rstrip("/")
        self.api_key = api_key
        self.location = location
        self.units = units
        self.enabled = enabled
        self.small_ram = small_ram   # M4: fetch a shorter forecast

        self.group = None
        self.data = None
        self.fetched_at = None
        self._start = None
        self._sequence = SEQUENCE
        self._screen = None
        self._last_slot = None
        self._labels = []
        self._header = None
        self._divider = None
        self._palettes = []
        self._sheets = {}      # kind -> (bitmap, palette), loaded per sequence
        self._icons = []       # TileGrids showing on the current screen
        self._icon_layer = None
        self._frame = -1

    # ── Scheduling ──────────────────────────────────────────────────────────

    @property
    def available(self):
        return bool(self.companion_url or self.api_key)

    @property
    def active(self):
        return self._start is not None

    def _slot(self, t):
        if t.tm_min in TRIGGER_MINUTES and t.tm_sec < LATE_START_LIMIT:
            return (t.tm_mday, t.tm_hour, t.tm_min)
        return None

    def due(self, t):
        if not self.enabled or self.active or not self.available:
            return False
        slot = self._slot(t)
        return slot is not None and slot != self._last_slot

    def maybe_prefetch(self, t, now):
        """Fetch at :x7:30 so the sequence can start instantly."""
        if (self.enabled and self.available and not self.active and t.tm_min % 10 == 7
                and t.tm_sec >= 30 and self._age(now) > DATA_MAX_AGE):
            self._fetch(now)

    def _age(self, now):
        return 1e9 if self.fetched_at is None else now - self.fetched_at

    def start(self, t, now):
        """Begin the sequence. Returns False (and skips this slot) without
        recent data - it never shows made-up numbers."""
        self._last_slot = self._slot(t)
        if self._age(now) > DATA_MAX_AGE:
            self._fetch(now)
        if not self.data or self._age(now) > STALE_LIMIT:
            print("Weather on the 8s skipped: no recent weather data")
            return False
        d = self.data
        self._sequence = tuple(
            (name, sec) for name, sec in SEQUENCE
            if not (name.startswith("hourly") and len(d.get("hourly", [])) < 2 * int(name[-1]) + 1)
            and not (name == "daily" and not d.get("daily")))
        self._build()
        self._start = now
        self._screen = None
        print("Weather on the 8s!")
        return True

    def update(self, now):
        """Draw the current screen. Returns False when the sequence is over."""
        if not self.active:
            return False
        elapsed = now - self._start
        screen = None
        for name, seconds in self._sequence:
            if elapsed < seconds:
                screen = name
                break
            elapsed -= seconds
        if screen is None:
            self.stop()
            return False
        if screen != self._screen:
            self._screen = screen
            self._render(screen)
            self._frame = -1
        # Animate the icons: just pick the next tile of each sprite sheet
        frame = int((now - self._start) * ICON_FPS) % ICON_FRAMES
        if frame != self._frame:
            self._frame = frame
            for grid in self._icons:
                grid[0] = frame
        return True

    def stop(self):
        dimmer.forget(self._labels, self._palettes + [p for _, p in self._sheets.values()])
        self._palettes = []
        self._sheets = {}
        self._icons = []
        self._icon_layer = None
        self._start = None
        self.group = None
        self._labels = []
        self._header = self._divider = None
        gc.collect()

    # ── Data ────────────────────────────────────────────────────────────────

    def _fetch(self, now):
        gc.collect()
        data = None
        if self.companion_url:
            status, reply = self.network.request("GET", f"{self.companion_url}/api/matrix/weather", retries=1)
            if status == 200 and reply and reply.get("w8"):
                data = reply["w8"]
        elif self.api_key:
            q = self.location.replace(" ", "%20")
            _, current = self.network.request(
                "GET", OWM_CURRENT.format(q=q, k=self.api_key, u=self.units), retries=1)
            gc.collect()
            if current:
                n = 16 if self.small_ram else 32
                _, forecast = self.network.request(
                    "GET", OWM_FORECAST.format(q=q, k=self.api_key, u=self.units, n=n), retries=1)
                try:
                    data = summarize(current, forecast or {}, self.units)
                except (KeyError, ValueError, TypeError) as e:
                    print(f"Weather on the 8s parse error: {e}")
                current = forecast = None
        if data:
            self.data = data
            self.fetched_at = now
        gc.collect()

    # ── Rendering ───────────────────────────────────────────────────────────

    def _build(self):
        gc.collect()
        g = displayio.Group()
        # Background: blue gradient in 8 bands
        shades = []
        for i in range(8):
            f = i / 7
            shades.append((int(0 + 10 * f) << 16) | (int(12 + 28 * f) << 8) | int(70 + 50 * f))
        bg = make_bitmap(64, 64, 8)
        for i in range(8):
            fill_bitmap(bg, i, 0, i * 8, 64, i * 8 + 8)
        self._palettes = [make_palette(shades), make_palette([HEADER]), make_palette([HEADER])]
        g.append(displayio.TileGrid(bg, pixel_shader=self._palettes[0]))
        self._header = displayio.TileGrid(make_bitmap(64, 12, 1), pixel_shader=self._palettes[1])
        g.append(self._header)
        self._divider = displayio.TileGrid(make_bitmap(1, 46, 1), pixel_shader=self._palettes[2], x=32, y=15)
        g.append(self._divider)
        self._icon_layer = displayio.Group()
        g.append(self._icon_layer)
        self._labels = []
        for _ in range(_POOL):
            lbl = make_text_label("", color=WHITE)
            self._labels.append(lbl)
            g.append(lbl)
        self.group = g

    def _sheet(self, kind):
        if kind not in self._sheets:
            try:
                import adafruit_imageload
                bitmap, palette = adafruit_imageload.load(
                    f"{ICON_DIR}/{kind}.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)
                palette.make_transparent(0)
                register_palette(palette)
                self._sheets[kind] = (bitmap, palette)
            except (OSError, ValueError) as e:
                print(f"Weather icon {kind} missing: {e}")
                self._sheets[kind] = None
        return self._sheets[kind]

    def _icon(self, kind, x, y, scale=1):
        """Show an animated icon (12px, or 24px with scale=2) at (x, y)."""
        sheet = self._sheet(kind or "cloud")
        if sheet is None:
            return
        grid = displayio.TileGrid(sheet[0], pixel_shader=sheet[1], width=1, height=1,
                                  tile_width=ICON_SIZE, tile_height=ICON_SIZE, default_tile=0)
        holder = displayio.Group(scale=scale, x=x, y=y)
        holder.append(grid)
        self._icon_layer.append(holder)
        self._icons.append(grid)

    def _put(self, i, text, color, y, align="c", x=32, scale=1, max_px=None):
        lbl = self._labels[i]
        if max_px is None:
            max_px = 62 if align == "c" and x == 32 else 31
        lbl.text = _fit(text, max_px // scale)
        lbl.scale = scale
        set_label_color(lbl, color)
        w = len(lbl.text) * 6 * scale
        if align == "c":
            lbl.x = x - w // 2
        elif align == "r":
            lbl.x = x - w
        else:
            lbl.x = x
        lbl.y = y

    def _render(self, screen):
        d = self.data or {}
        for lbl in self._labels:
            lbl.text = ""
        while len(self._icon_layer):
            self._icon_layer.pop()
        self._icons = []
        self._header.hidden = screen in ("intro", "outro")
        self._divider.hidden = not screen.startswith("hourly")
        if screen == "intro":
            self._put(0, "WEATHER", WHITE, 11)
            self._put(1, "on the", GREY, 23)
            self._put(2, "8s", YELLOW, 40, scale=2)
        elif screen == "outro":
            self._put(0, "That's the", WHITE, 21)
            self._put(1, "local", WHITE, 33)
            self._put(2, "forecast", YELLOW, 45)
        elif screen == "current":
            self._put(0, (d.get("city") or "NOW").upper(), YELLOW, 5)
            temp = f"{d.get('temp', '--')}{DEG}"
            # Big icon beside the big temperature; small one if it needs the room
            big = len(temp) * 12 <= 64 - 28
            kind = d.get("kind") or "cloud"
            iy = 14 if big else 20
            self._icon(kind, 2, iy, 2 if big else 1)
            if d.get("windy"):
                self._icon("wind", 2, iy, 2 if big else 1)
            self._put(1, temp, YELLOW, 25, align="r", x=64, scale=2, max_px=64 - (28 if big else 16))
            cond = d.get("condition", "")
            self._put(2, cond, COND_COLORS.get(cond, WHITE), 45)
            if d.get("hi") is not None:
                self._put(3, f"H{d['hi']}{DEG} L{d['lo']}{DEG}", LIGHT_BLUE, 56)
        elif screen == "details":
            self._put(0, "CONDITIONS", YELLOW, 5)
            rows = (("Hum", f"{d.get('humidity', '--')}%"), ("Wind", d.get("wind") or "--"),
                    ("Feel", f"{d.get('feels', '--')}{DEG}"), ("Vis", d.get("visibility") or "--"))
            for i, (label, value) in enumerate(rows):
                y = 20 + i * 12
                self._put(1 + 2 * i, label, LIGHT_BLUE, y, align="l", x=2)
                self._put(2 + 2 * i, value, WHITE, y, align="r", x=62)
        elif screen.startswith("hourly"):
            self._put(0, "NEXT HOURS", YELLOW, 5)
            start = 2 * int(screen[-1])
            for col, h in enumerate(d.get("hourly", [])[start:start + 2]):
                cx = 16 + col * 32
                base = 1 + col * 3
                self._put(base, h["time"], WHITE, 18, x=cx)
                self._icon(h.get("kind"), cx - 6, 25)
                self._put(base + 1, f"{h['temp']}{DEG}", YELLOW, 43, x=cx)
                if h.get("pop", 0) >= 20:
                    self._put(base + 2, f"{h['pop']}%", LIGHT_BLUE, 54, x=cx)
        elif screen == "daily":
            self._put(0, "3-DAY", YELLOW, 5)
            for i, day in enumerate(d.get("daily", [])[:3]):
                y = 15 + i * 16
                self._put(1 + 3 * i, day["day"], WHITE, y + 6, align="l", x=1)
                self._icon(day.get("kind"), 20, y)
                lo = str(day["lo"])
                lo_x = 62 - len(lo) * 6
                self._put(2 + 3 * i, day["hi"], YELLOW, y + 6, align="r", x=lo_x - 3)
                self._put(3 + 3 * i, lo, LIGHT_BLUE, y + 6, align="r", x=62)
