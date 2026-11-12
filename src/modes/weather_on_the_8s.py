"""
Weather on the 8s - Classic Weather Channel style local forecast

Takes over the display at :08, :18, :28, :38, :48 and :58 with a ~46 second
sequence (intro, current conditions, details, next hours, 3-day, outro), then
hands the screen back to whatever was showing.

Uses the weather_on_8s settings, falling back to the main weather settings
for the API key / location / units when those are left blank.
"""

import logging
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import requests
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.weather_data import summarize
from utils import weather_icons

OWM_CURRENT = "https://api.openweathermap.org/data/2.5/weather"
OWM_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"

TRIGGER_MINUTES = (8, 18, 28, 38, 48, 58)
LATE_START_LIMIT = 45      # still start if we notice the slot up to this many seconds late
DATA_MAX_AGE = 600         # refresh data older than 10 minutes
STALE_LIMIT = 3 * 3600     # never show data older than 3 hours

# Colours (Weather Channel-ish)
BG_TOP = (0, 12, 70)
BG_BOTTOM = (10, 40, 120)
HEADER = (35, 65, 175)
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
GREY = (170, 180, 210)
LIGHT_BLUE = (140, 190, 255)
COND_COLORS = {
    "Clear": (255, 214, 0), "Cloudy": (190, 190, 200), "Rain": (90, 160, 255),
    "Drizzle": (120, 180, 255), "Storms": (255, 140, 40), "Snow": (235, 245, 255),
}

# (screen, seconds)
SEQUENCE = (
    ("intro", 3), ("current", 8), ("details", 8),
    ("hourly0", 8), ("hourly1", 8), ("daily", 8), ("outro", 3),
)


def _font():
    try:
        return ImageFont.load_default_imagefont()   # crisp bitmap font (Pillow >= 10.1)
    except AttributeError:
        return ImageFont.load_default()


class WeatherOnThe8sMode:
    """Weather on the 8s - takes over the display every 10 minutes."""

    def __init__(self, display, config):
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config
        cfg = config.get('weather_on_8s', {})
        main = config.get('weather', {})

        def pick(key, default):
            value = cfg.get(key)
            if not value or str(value).startswith('your_'):
                value = main.get(key)
            if not value or str(value).startswith('your_'):
                value = default
            return value

        self.enabled = bool(cfg.get('enabled', False))
        self.api_key = pick('api_key', '')
        self.location = pick('location', 'New York,US')
        self.units = pick('units', 'imperial')
        self.max_duration = cfg.get('display_duration', 90)

        self.font = _font()
        self.data = None
        self.fetched_at = 0
        self.animation_start = None
        self._last_slot = None
        self._last_screen = None
        self._sequence = SEQUENCE
        self._screen_cache = {}

        if self.enabled and not self.api_key:
            self.logger.warning("Weather on the 8s: no OpenWeatherMap API key "
                                "(set one under Weather or Weather on the 8s)")
            self.enabled = False

        self.logger.info(f"Weather on the 8s initialized (enabled={self.enabled})")

    # ── Scheduling ──────────────────────────────────────────────────────────

    def _slot(self, now):
        """The (day, hour, minute) slot if `now` is inside a trigger minute."""
        if now.minute in TRIGGER_MINUTES and now.second < LATE_START_LIMIT:
            return (now.day, now.hour, now.minute)
        return None

    def should_activate(self):
        slot = self._slot(datetime.now())
        return slot is not None and slot != self._last_slot

    def is_active(self):
        if self.animation_start is None:
            return False
        total = min(self.max_duration, sum(d for _, d in self._sequence))
        return time.time() - self.animation_start < total

    def start_display(self):
        """Start the sequence (if we have usable data)."""
        self._last_slot = self._slot(datetime.now())
        if time.time() - self.fetched_at > DATA_MAX_AGE:
            self._fetch_weather_data()
        if not self.data or time.time() - self.fetched_at > STALE_LIMIT:
            self.logger.warning("Weather on the 8s skipped: no recent weather data")
            return
        # Drop screens we have nothing for
        seq = []
        for name, seconds in SEQUENCE:
            if name.startswith('hourly') and len(self.data['hourly']) < 2 * int(name[-1]) + 1:
                continue
            if name == 'daily' and not self.data['daily']:
                continue
            seq.append((name, seconds))
        self._sequence = tuple(seq)
        self.logger.info("🌤️ Weather on the 8s!")
        self.animation_start = time.time()
        self._last_screen = None

    def update(self):
        """Called every display-loop pass. Returns True while it owns the screen."""
        if not self.enabled:
            return False
        if not self.is_active():
            if self.animation_start is not None:
                self.animation_start = None   # finished: hand the screen back
            if self.should_activate():
                self.start_display()
            else:
                # Pre-fetch a minute ahead so the sequence starts instantly
                now = datetime.now()
                if now.minute % 10 == 7 and now.second >= 30 and time.time() - self.fetched_at > DATA_MAX_AGE:
                    self._fetch_weather_data()
        if self.is_active():
            self._render_sequence()
            return True
        return False

    # ── Data ────────────────────────────────────────────────────────────────

    def _fetch_weather_data(self):
        params = {'q': self.location, 'appid': self.api_key, 'units': self.units}
        try:
            current = requests.get(OWM_CURRENT, params=params, timeout=10)
            current.raise_for_status()
            forecast = requests.get(OWM_FORECAST, params=dict(params, cnt=32), timeout=10)
            forecast.raise_for_status()
            self.data = summarize(current.json(), forecast.json(), self.units)
            self.fetched_at = time.time()
            self.logger.info(f"Weather on the 8s data: {self.data['temp']}° {self.data['condition']}")
        except Exception as e:
            # Keep the previous (recent) data rather than inventing numbers
            self.logger.error(f"Weather on the 8s fetch failed: {e}")

    # ── Rendering ───────────────────────────────────────────────────────────

    def _current_screen(self):
        elapsed = time.time() - self.animation_start
        for name, seconds in self._sequence:
            if elapsed < seconds:
                return name
            elapsed -= seconds
        return self._sequence[-1][0]

    def _render_sequence(self):
        screen = self._current_screen()
        t = time.time() - self.animation_start
        frame = int(t * weather_icons.FPS)
        key = (screen, frame % weather_icons.FRAMES if self._icons_for(screen) else 0)
        if key == self._last_screen and self.display.current_image is getattr(self, '_last_frame', None):
            return  # nothing changed (static screen, or same animation frame)
        self._last_screen = key
        self.display.display_image(self.render_screen(screen, t))
        self._last_frame = self.display.current_image

    def render_screen(self, screen, t=0.0):
        """Draw one screen of the sequence at time t (seconds) into it.
        The static part is cached; only the animated icons are drawn per frame."""
        base, icons = self._static_screen(screen)
        if not icons:
            return base
        img = base.copy()
        frame = int(t * weather_icons.FPS)
        for kind, x, y, scale in icons:
            icon = weather_icons.frame(kind, frame, scale)
            img.paste(icon, (x, y), icon)
        return img

    def _icons_for(self, screen):
        return self._static_screen(screen)[1]

    def _static_screen(self, screen):
        key = (screen, id(self.data))
        cached = self._screen_cache.get(key)
        if cached is None:
            cached = self._draw_static(screen)
            self._screen_cache = {k: v for k, v in self._screen_cache.items() if k[1] == id(self.data)}
            self._screen_cache[key] = cached
        return cached

    def _draw_static(self, screen):
        """Background + text for a screen, and where its icons go:
        returns (image, [(kind, x, y, scale)])."""
        width, height = self.display.get_size()
        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            f = y / max(1, height - 1)
            draw.line([(0, y), (width, y)], fill=tuple(int(a + (b - a) * f) for a, b in zip(BG_TOP, BG_BOTTOM)))
        d = self.data or {}
        sym = '°'
        icons = []

        if screen == 'intro':
            self._center(draw, "WEATHER", 6, WHITE)
            self._center(draw, "on the", 18, GREY)
            self._big_center(img, "8s", 31, YELLOW)
        elif screen == 'outro':
            self._center(draw, "That's the", 16, WHITE)
            self._center(draw, "local", 28, WHITE)
            self._center(draw, "forecast", 40, YELLOW)
        elif screen == 'current':
            self._header(draw, d.get('city') or "NOW")
            temp = f"{d.get('temp', '--')}{sym}"
            temp_w = self._w(temp) * 2
            # Big (24px) icon beside the big temperature; small icon if the
            # temperature needs the room (e.g. "100°", "-12°")
            big = temp_w <= width - 28
            kind = d.get('kind') or 'cloud'
            icons.append((kind, 2, 14 if big else 20, 2 if big else 1))
            if d.get('windy'):
                icons.append(('wind', 2, 14 if big else 20, 2 if big else 1))
            self._big_text(img, temp, width - 1 - temp_w, 15 if big else 16, YELLOW)
            cond = d.get('condition', '')
            self._center(draw, cond, 40, COND_COLORS.get(cond, WHITE))
            if d.get('hi') is not None:
                self._center(draw, f"H{d['hi']}{sym} L{d['lo']}{sym}", 51, LIGHT_BLUE)
        elif screen == 'details':
            self._header(draw, "CONDITIONS")
            rows = [("Hum", f"{d.get('humidity', '--')}%"), ("Wind", d.get('wind', '--')),
                    ("Feel", f"{d.get('feels', '--')}{sym}"), ("Vis", d.get('visibility') or '--')]
            for i, (label, value) in enumerate(rows):
                y = 15 + i * 12
                draw.text((2, y), label, font=self.font, fill=LIGHT_BLUE)
                draw.text((width - 2 - self._w(value), y), value, font=self.font, fill=WHITE)
        elif screen.startswith('hourly'):
            self._header(draw, "NEXT HOURS")
            start = 2 * int(screen[-1])
            for col, h in enumerate(d.get('hourly', [])[start:start + 2]):
                cx = 16 + col * 32
                self._center(draw, h['time'], 13, WHITE, cx)
                icons.append((h.get('kind') or 'cloud', cx - 6, 24, 1))
                self._center(draw, f"{h['temp']}{sym}", 37, YELLOW, cx)
                if h.get('pop', 0) >= 20:
                    self._center(draw, f"{h['pop']}%", 48, LIGHT_BLUE, cx)
            draw.line([(32, 15), (32, 60)], fill=HEADER)
        elif screen == 'daily':
            self._header(draw, "3-DAY")
            for i, day in enumerate(d.get('daily', [])[:3]):
                y = 15 + i * 16
                draw.text((1, y + 1), day['day'], font=self.font, fill=WHITE)
                icons.append((day.get('kind') or 'cloud', 20, y, 1))
                # High (yellow) and low (light blue), right-aligned
                hi, lo = str(day['hi']), str(day['lo'])
                lo_x = width - 2 - self._w(lo)
                hi_x = lo_x - 3 - self._w(hi)
                draw.text((hi_x, y + 1), hi, font=self.font, fill=YELLOW)
                draw.text((lo_x, y + 1), lo, font=self.font, fill=LIGHT_BLUE)
        return img, icons

    def _w(self, text):
        return int(self.font.getlength(text)) if hasattr(self.font, 'getlength') else self.font.getbbox(text)[2]

    def _fit(self, text, max_width):
        while text and self._w(text) > max_width:
            text = text[:-1]
        return text

    def _center(self, draw, text, y, color, cx=None):
        width = self.display.get_size()[0]
        max_w = width - 2 if cx is None else 31
        text = self._fit(str(text), max_w)
        cx = width // 2 if cx is None else cx
        draw.text((cx - self._w(text) // 2, y), text, font=self.font, fill=color)

    def _header(self, draw, text):
        width = self.display.get_size()[0]
        draw.rectangle([0, 0, width - 1, 11], fill=HEADER)
        self._center(draw, str(text).upper(), 1, YELLOW)

    def _big_text(self, img, text, x, y, color):
        """2x pixel-doubled text at (x, y)."""
        w = self._w(text)
        mask = Image.new('L', (max(1, w), 11))
        ImageDraw.Draw(mask).text((0, 0), text, font=self.font, fill=255)
        img.paste(color, (x, y), mask.resize((w * 2, 22), Image.NEAREST))

    def _big_center(self, img, text, y, color):
        """2x pixel-doubled text (chunky, crisp on LEDs)."""
        w = self._w(text)
        mask = Image.new('L', (max(1, w), 11))
        ImageDraw.Draw(mask).text((0, 0), text, font=self.font, fill=255)
        mask = mask.resize((w * 2, 22), Image.NEAREST)
        img.paste(color, ((img.width - w * 2) // 2, y), mask)
