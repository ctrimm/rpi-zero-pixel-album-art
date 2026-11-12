# clock_mode.py — Digital or analog clock for Matrix Portal 64x64
#
# CLOCK_STYLE = "digital" | "analog", TIME_FORMAT = "12h" | "24h"
# (same options as the Pi app). Redraws only when something visible changes:
# once a minute for digital, once a second for the analog second hand - and the
# analog hands only touch the pixels they cover, never the whole bitmap.
import displayio
import math
import rtc
import gc

from utils.display_helper import make_text_label, center_label, make_palette, COLORS

DAYS   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Analog clock palette indices
_BG, _RING, _TICK, _HOUR, _MIN, _SEC = 0, 1, 2, 3, 4, 5
_C = 31.5  # centre of a 64px panel
_R = 30


def _line(x0, y0, x1, y1):
    """Integer Bresenham line from (x0, y0) to (x1, y1) - list of points."""
    pts = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return pts
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _hand(angle_deg, length, thick=False):
    a = math.radians(angle_deg - 90)
    x1 = int(round(_C + length * math.cos(a)))
    y1 = int(round(_C + length * math.sin(a)))
    pts = _line(31, 31, x1, y1) + _line(32, 32, x1, y1)  # 2px-wide centre
    if thick:
        pts += _line(32, 31, x1, y1) + _line(31, 32, x1, y1)
    return pts


class ClockMode:
    def __init__(self, display, style="digital", time_format="12h"):
        self.display = display
        self.style = style if style in ("digital", "analog") else "digital"
        self.time_format = time_format
        self._group = None
        self._time_label = None
        self._ampm_label = None
        self._date_label = None
        self._bitmap = None
        self._hand_pixels = []   # [(x, y, previous value)] to erase next tick
        self._last_key = None

    def on_enter(self):
        gc.collect()
        self._group = displayio.Group()
        if self.style == "analog":
            self._build_analog()
        else:
            self._build_digital()
        self.display.root_group = self._group
        self._last_key = None
        self.update()

    def on_exit(self):
        self._group = None
        self._time_label = None
        self._ampm_label = None
        self._date_label = None
        self._bitmap = None
        self._hand_pixels = []
        gc.collect()

    def update(self):
        t = rtc.RTC().datetime
        key = (t.tm_hour, t.tm_min, t.tm_sec if self.style == "analog" else 0)
        if key == self._last_key:
            return
        self._last_key = key
        if self.style == "analog":
            self._render_analog(t)
        else:
            self._render_digital(t)

    # ── Digital ─────────────────────────────────────────────────────────────

    def _build_digital(self):
        # Large time (HH:MM) — scale 2 = 12px per char, "00:00" = 60px wide
        self._time_label = make_text_label("00:00", color=COLORS["green"], y=20, scale=2)
        self._group.append(self._time_label)
        # AM/PM indicator (12h only)
        self._ampm_label = make_text_label("", color=COLORS["dim"], y=38, scale=1)
        self._group.append(self._ampm_label)
        # Date line
        self._date_label = make_text_label("", color=COLORS["gray"], y=52, scale=1)
        self._group.append(self._date_label)

    def _render_digital(self, t):
        if self.time_format == "24h":
            time_str = f"{t.tm_hour:02d}:{t.tm_min:02d}"
            ampm = ""
        else:
            hour_12 = t.tm_hour % 12 or 12
            time_str = f"{hour_12}:{t.tm_min:02d}"
            ampm = "PM" if t.tm_hour >= 12 else "AM"
        self._time_label.text = time_str
        center_label(self._time_label, y=20)
        self._ampm_label.text = ampm
        center_label(self._ampm_label, y=37)
        self._date_label.text = f"{DAYS[t.tm_wday]} {MONTHS[t.tm_mon - 1]} {t.tm_mday}"
        center_label(self._date_label, y=52)

    # ── Analog ──────────────────────────────────────────────────────────────

    def _build_analog(self):
        palette = make_palette([0x000000, 0x444444, 0xAAAAAA, 0xFFFFFF, 0xC8C8C8, 0xFF3232])
        self._bitmap = displayio.Bitmap(64, 64, 6)
        bmp = self._bitmap
        # Ring + hour ticks are drawn once
        for i in range(360):
            a = math.radians(i)
            bmp[int(round(_C + _R * math.cos(a))), int(round(_C + _R * math.sin(a)))] = _RING
        for h in range(12):
            a = math.radians(h * 30 - 90)
            for r in ((_R - 3, _R - 1) if h % 3 == 0 else (_R - 2, _R - 1)):
                bmp[int(round(_C + r * math.cos(a))), int(round(_C + r * math.sin(a)))] = _TICK
        self._group.append(displayio.TileGrid(bmp, pixel_shader=palette))
        self._hand_pixels = []

    def _render_analog(self, t):
        bmp = self._bitmap
        # Erase last frame's hands, restoring what was underneath
        for x, y, v in reversed(self._hand_pixels):
            bmp[x, y] = v
        self._hand_pixels = []
        hour = t.tm_hour % 12
        hands = (
            (_HOUR, _hand(hour * 30 + t.tm_min * 0.5, _R * 0.5, thick=True)),
            (_MIN, _hand(t.tm_min * 6 + t.tm_sec * 0.1, _R * 0.78)),
            (_SEC, _line(32, 32, *[int(round(_C + _R * 0.88 * f(math.radians(t.tm_sec * 6 - 90))))
                                   for f in (math.cos, math.sin)])),
        )
        for color, pts in hands:
            for x, y in pts:
                if 0 <= x < 64 and 0 <= y < 64:
                    self._hand_pixels.append((x, y, bmp[x, y]))
                    bmp[x, y] = color
        for x in (31, 32):
            for y in (31, 32):
                self._hand_pixels.append((x, y, bmp[x, y]))
                bmp[x, y] = _HOUR
