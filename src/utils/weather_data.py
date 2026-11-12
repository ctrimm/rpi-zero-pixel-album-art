"""
Weather summary shared by Weather on the 8s (Pi) and the Matrix Portal
companion, so both show exactly the same numbers.

Input: OpenWeatherMap "current weather" + "5 day / 3 hour forecast" replies.
Times are converted with the *location's* UTC offset (OWM's city.timezone),
so "3PM" means 3 PM where the weather is, whatever the machine's timezone.
"""

import time

DAY_NAMES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

# Short, panel-friendly names for OWM's "main" condition groups
CONDITION_NAMES = {
    "Clear": "Clear", "Clouds": "Cloudy", "Rain": "Rain", "Drizzle": "Drizzle",
    "Thunderstorm": "Storms", "Snow": "Snow", "Mist": "Mist", "Fog": "Fog",
    "Haze": "Haze", "Smoke": "Smoke", "Dust": "Dust", "Sand": "Sand",
    "Ash": "Ash", "Squall": "Squall", "Tornado": "Tornado",
}


def condition_name(main):
    return CONDITION_NAMES.get(main or "", (main or "?")[:7])


def wind_direction(degrees):
    return COMPASS[int(round((degrees or 0) / 45.0)) % 8]


def _hour_label(hour):
    h12 = hour % 12 or 12
    return f"{h12}{'AM' if hour < 12 else 'PM'}"


def summarize(current, forecast, units="imperial"):
    """Return a compact dict:

    city, temp, feels, hi, lo, condition, humidity, wind (e.g. "NW 12"),
    visibility (e.g. "10mi"), units, hourly [4 x {time, temp, condition, pop}],
    daily [up to 3 x {day, hi, lo, condition}]
    """
    tz = (forecast or {}).get("city", {}).get("timezone", current.get("timezone", 0)) or 0
    main = current.get("main", {})
    weather = (current.get("weather") or [{}])[0]
    wind = current.get("wind", {})
    vis_m = current.get("visibility")
    imperial = units == "imperial"

    entries = (forecast or {}).get("list", [])
    now_utc = current.get("dt") or time.time()

    # Today's high/low: current reading plus forecast entries for the rest of today
    today = time.gmtime(now_utc + tz)[:3]
    today_temps = [main.get("temp_max", main.get("temp")), main.get("temp_min", main.get("temp"))]
    for e in entries:
        if time.gmtime(e["dt"] + tz)[:3] == today:
            today_temps.append(e["main"]["temp"])
    today_temps = [t for t in today_temps if t is not None]

    hourly = []
    for e in entries[:4]:
        t = time.gmtime(e["dt"] + tz)
        hourly.append({
            "time": _hour_label(t.tm_hour),
            "temp": round(e["main"]["temp"]),
            "condition": condition_name(e["weather"][0]["main"]),
            "pop": round((e.get("pop") or 0) * 100),
        })

    # Next days: min/max per local date, condition from the midday-ish entry
    days = {}
    order = []
    for e in entries:
        t = time.gmtime(e["dt"] + tz)
        key = t[:3]
        if key == today:
            continue
        if key not in days:
            days[key] = {"day": DAY_NAMES[t.tm_wday], "temps": [], "cond": None, "best": 99}
            order.append(key)
        d = days[key]
        d["temps"].append(e["main"]["temp"])
        closeness = abs(t.tm_hour - 13)
        if closeness < d["best"]:
            d["best"] = closeness
            d["cond"] = e["weather"][0]["main"]
    daily = []
    for key in order[:3]:
        d = days[key]
        if len(d["temps"]) >= 2:  # skip a day we only have one reading for
            daily.append({"day": d["day"], "hi": round(max(d["temps"])),
                          "lo": round(min(d["temps"])), "condition": condition_name(d["cond"])})

    return {
        "city": current.get("name", ""),
        "temp": round(main.get("temp", 0)),
        "feels": round(main.get("feels_like", main.get("temp", 0))),
        "hi": round(max(today_temps)) if today_temps else None,
        "lo": round(min(today_temps)) if today_temps else None,
        "condition": condition_name(weather.get("main")),
        "humidity": main.get("humidity"),
        "wind": f"{wind_direction(wind.get('deg'))} {round(wind.get('speed', 0))}",
        "visibility": (f"{round(vis_m / (1609.34 if imperial else 1000))}{'mi' if imperial else 'km'}"
                       if vis_m is not None else None),
        "units": units,
        "hourly": hourly,
        "daily": daily,
    }
