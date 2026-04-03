# clock_mode.py — Digital clock with date for Matrix Portal 64x64
import displayio
import time
import rtc
import gc

from utils.display_helper import make_text_label, center_label, COLORS

DAYS   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ClockMode:
    def __init__(self, display):
        self.display = display
        self._group = None
        self._time_label = None
        self._ampm_label = None
        self._date_label = None
        self._last_minute = -1

    def on_enter(self):
        gc.collect()
        self._group = displayio.Group()

        # Large time (HH:MM) — scale 2 = 12px per char, "00:00" = 60px wide
        self._time_label = make_text_label("00:00", color=COLORS["green"], y=20, scale=2)
        center_label(self._time_label, y=20)
        self._group.append(self._time_label)

        # AM/PM indicator
        self._ampm_label = make_text_label("AM", color=COLORS["dim"], y=38, scale=1)
        self._ampm_label.x = 50
        self._group.append(self._ampm_label)

        # Date line
        self._date_label = make_text_label("Mon Jan  1", color=COLORS["gray"], y=52, scale=1)
        center_label(self._date_label, y=52)
        self._group.append(self._date_label)

        self.display.root_group = self._group
        self._last_minute = -1
        self._render()

    def on_exit(self):
        self._group = None
        self._time_label = None
        self._ampm_label = None
        self._date_label = None
        gc.collect()

    def update(self):
        t = rtc.RTC().datetime
        if t.tm_min != self._last_minute:
            self._last_minute = t.tm_min
            self._render()

    def _render(self):
        t = rtc.RTC().datetime
        hour_24 = t.tm_hour
        minute = t.tm_min

        # 12-hour conversion
        am_pm = "PM" if hour_24 >= 12 else "AM"
        hour_12 = hour_24 % 12
        if hour_12 == 0:
            hour_12 = 12

        time_str = f"{hour_12:2d}:{minute:02d}"
        self._time_label.text = time_str
        center_label(self._time_label, y=20)

        self._ampm_label.text = am_pm

        day_name   = DAYS[t.tm_wday]
        month_name = MONTHS[t.tm_mon - 1]
        date_str = f"{day_name} {month_name} {t.tm_mday:2d}"
        self._date_label.text = date_str
        center_label(self._date_label, y=52)
