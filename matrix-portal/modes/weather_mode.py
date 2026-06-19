# weather_mode.py — Current weather + 3-day forecast for Matrix Portal 64x64
import displayio
import time
import gc

from utils.display_helper import make_text_label, center_label, COLORS, ScrollingLabel
from utils import storage_helper

WEATHER_CACHE = "/cache_weather.json"

OWM_CURRENT_URL = (
    "http://api.openweathermap.org/data/2.5/weather"
    "?q={location}&appid={key}&units={units}"
)
OWM_FORECAST_URL = (
    "http://api.openweathermap.org/data/2.5/forecast"
    "?q={location}&appid={key}&units={units}&cnt=24"
)

# Map OWM condition codes to simple text icons (no image files needed)
CONDITION_ICONS = {
    "Thunderstorm": "T-STORM",
    "Drizzle":      "DRIZZLE",
    "Rain":         "  RAIN ",
    "Snow":         "  SNOW ",
    "Clear":        " CLEAR ",
    "Clouds":       "CLOUDY ",
    "Mist":         "  MIST ",
    "Fog":          "  FOG  ",
    "Haze":         "  HAZE ",
    "Smoke":        " SMOKE ",
    "Dust":         "  DUST ",
    "Tornado":      "TORNADO",
}

UNIT_SYMBOL = {"imperial": "F", "metric": "C", "standard": "K"}

# Colors for conditions
CONDITION_COLORS = {
    "Clear":  0xFFDD00,
    "Clouds": 0xAAAAAA,
    "Rain":   0x4488FF,
    "Snow":   0xCCEEFF,
    "Thunderstorm": 0xFF8800,
}


def _condition_color(main):
    return CONDITION_COLORS.get(main, COLORS["white"])


class WeatherMode:
    def __init__(self, display, network, companion_url="",
                 api_key="", location="New York,US", units="imperial"):
        self.display = display
        self.network = network
        self.companion_url = companion_url.rstrip("/")
        self.api_key = api_key
        self.location = location
        self.units = units

        self._group = None
        self._temp_label = None
        self._condition_label = None
        self._feels_label = None
        self._forecast_labels = []
        self._city_scroller = None

        self._last_update = 0
        self._update_interval = 600  # 10 minutes

    def on_enter(self):
        gc.collect()
        self._group = displayio.Group()

        # City name (scrolling, top)
        self._city_scroller = ScrollingLabel(
            self.location.split(",")[0], color=COLORS["cyan"], y=4, scale=1
        )
        self._group.append(self._city_scroller.label)

        # Main temperature — big
        self._temp_label = make_text_label("---°F", color=COLORS["white"], y=18, scale=2)
        center_label(self._temp_label, y=18)
        self._group.append(self._temp_label)

        # Condition text
        self._condition_label = make_text_label("Loading...", color=COLORS["gray"], y=34)
        center_label(self._condition_label, y=34)
        self._group.append(self._condition_label)

        # Feels like
        self._feels_label = make_text_label("Feels --°", color=COLORS["dim"], y=43)
        center_label(self._feels_label, y=43)
        self._group.append(self._feels_label)

        # 3-day forecast row — one compact temperature per column.
        # (A two-line day+temp cell doesn't fit: "MM/DD" overflows the ~21px
        # columns and a second line clips off the bottom of the 64px panel.)
        self._forecast_labels = []
        positions = [3, 25, 47]
        for i, x in enumerate(positions):
            lbl = make_text_label("--", color=COLORS["gray"], x=x, y=58, scale=1)
            self._forecast_labels.append(lbl)
            self._group.append(lbl)

        self.display.root_group = self._group
        self._last_update = 0  # force immediate fetch

        # Show last-good weather immediately (before the first network fetch)
        cached = storage_helper.load_json(WEATHER_CACHE)
        if cached:
            try:
                self._render(cached)
            except Exception as e:
                print(f"Weather cache render failed: {e}")

    def on_exit(self):
        self._group = None
        self._temp_label = None
        self._condition_label = None
        self._feels_label = None
        self._forecast_labels = []
        self._city_scroller = None
        gc.collect()

    def update(self):
        now = time.monotonic()
        if now - self._last_update >= self._update_interval:
            self._last_update = now
            self._fetch_and_render()

        if self._city_scroller:
            self._city_scroller.update()

    def _fetch_and_render(self):
        if self.companion_url:
            data = self.network.get_json(f"{self.companion_url}/api/matrix/weather")
            if data and not data.get("error"):
                self._render(data)
                storage_helper.save_json(WEATHER_CACHE, data)
                return

        if not self.api_key:
            self._condition_label.text = "No API key"
            return

        url = OWM_CURRENT_URL.format(
            location=self.location, key=self.api_key, units=self.units
        )
        current = self.network.get_json(url)
        gc.collect()

        forecast_days = []
        fc_url = OWM_FORECAST_URL.format(
            location=self.location, key=self.api_key, units=self.units
        )
        fc_data = self.network.get_json(fc_url)
        gc.collect()

        if fc_data and "list" in fc_data:
            # Get one entry per day (every 8th entry = ~24h apart at 3h intervals)
            seen_days = set()
            for entry in fc_data["list"]:
                day = entry["dt_txt"][:10]
                if day not in seen_days and len(forecast_days) < 3:
                    seen_days.add(day)
                    forecast_days.append({
                        "day": day[-5:],  # MM-DD
                        "temp": entry["main"]["temp"],
                        "main": entry["weather"][0]["main"],
                    })

        if current:
            payload = {"current": current, "forecast": forecast_days}
            self._render(payload)
            storage_helper.save_json(WEATHER_CACHE, payload)

    def _render(self, data):
        unit_sym = UNIT_SYMBOL.get(self.units, "F")

        if "current" in data:
            c = data["current"]
            temp = c.get("temp", c.get("main", {}).get("temp", 0))
            if isinstance(temp, dict):
                temp = temp.get("temp", 0)
            feels = c.get("feels_like", c.get("main", {}).get("feels_like", temp))
            if isinstance(feels, dict):
                feels = feels.get("feels_like", temp)

            weather = c.get("weather", [{}])
            main_cond = weather[0].get("main", "Clear") if weather else "Clear"
            icon_text = CONDITION_ICONS.get(main_cond, main_cond[:7].upper())

            self._temp_label.text = f"{int(temp):>3d}{chr(176)}{unit_sym}"
            center_label(self._temp_label, y=18)

            self._condition_label.text = icon_text
            self._condition_label.color = _condition_color(main_cond)
            center_label(self._condition_label, y=34)

            self._feels_label.text = f"Feels {int(feels)}{chr(176)}"
            center_label(self._feels_label, y=43)

            city_name = c.get("name", self.location.split(",")[0])
            self._city_scroller.set_text(city_name)
        elif "temp" in data:
            # Companion flat format
            temp = data["temp"]
            feels = data.get("feels_like", temp)
            main_cond = data.get("condition", "Clear")
            icon_text = CONDITION_ICONS.get(main_cond, main_cond[:7].upper())

            self._temp_label.text = f"{int(temp):>3d}{chr(176)}{unit_sym}"
            center_label(self._temp_label, y=18)
            self._condition_label.text = icon_text
            self._condition_label.color = _condition_color(main_cond)
            center_label(self._condition_label, y=34)
            self._feels_label.text = f"Feels {int(feels)}{chr(176)}"
            center_label(self._feels_label, y=43)

        # Forecast row — one temperature per column, colored by condition.
        forecast = data.get("forecast", [])
        for i, lbl in enumerate(self._forecast_labels):
            if i < len(forecast):
                f = forecast[i]
                temp_val = f.get("temp", f.get("main", {}).get("temp", 0) if isinstance(f.get("main"), dict) else 0)
                lbl.text = f"{int(temp_val)}{chr(176)}"
                lbl.color = _condition_color(f.get("main", "Clear"))
            else:
                lbl.text = ""
