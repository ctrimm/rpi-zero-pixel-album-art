# Weather on the 8s - Classic Weather Channel Feature

A nostalgic recreation of the classic Weather Channel "Local on the 8s" feature that displays detailed weather forecasts every 10 minutes at specific times.

## Overview

Remember waiting for the Weather Channel to show your local forecast "on the 8s"? This feature recreates that experience on your LED matrix display!

**Weather on the 8s automatically displays at:**
- :08 minutes past the hour
- :18 minutes past the hour
- :28 minutes past the hour
- :38 minutes past the hour
- :48 minutes past the hour
- :58 minutes past the hour

The display runs for about 90 seconds, showing a complete weather forecast sequence, then returns to your regular display mode.

## Features

### Classic Presentation Style

The display mimics the classic Weather Channel aesthetic with:
- **Intro screen** - "Weather on the 8s" title
- **Current conditions** - Temperature, description, high/low
- **Forecast screens** - 3 screens showing upcoming hours
- **Details screen** - Humidity, wind, visibility, feels-like
- **Outro screen** - "Thank you for watching"

### Automatic Triggering

Weather on the 8s takes priority over all other display modes during its 90-second window. When the time hits :08, :18, :28, :38, :48, or :58, it automatically:
1. Interrupts the current display
2. Shows the weather sequence
3. Returns to the previous mode when complete

### Live Weather Data

Pulls real-time weather from OpenWeatherMap API including:
- Current temperature and conditions
- High and low temperatures
- Hourly forecast (next 24 hours)
- Wind speed and direction
- Humidity percentage
- Visibility distance
- "Feels like" temperature
- Probability of precipitation

## Configuration

### Basic Setup

Edit `config.json` and add your OpenWeatherMap API key:

```json
{
  "weather_on_8s": {
    "enabled": true,
    "api_key": "your_openweathermap_api_key_here",
    "location": "New York,US",
    "units": "imperial",
    "display_duration": 90
  }
}
```

### Get OpenWeatherMap API Key

1. Sign up at [OpenWeatherMap](https://openweathermap.org/api)
2. Subscribe to the **free tier** (no credit card required)
3. Go to "API keys" section
4. Copy your API key
5. Paste into `config.json`

**Note:** Free tier includes:
- 1,000 API calls per day (more than enough)
- Current weather data
- 5-day forecast
- No cost!

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable Weather on the 8s |
| `api_key` | string | `""` | Your OpenWeatherMap API key |
| `location` | string | `"New York,US"` | City name and country code |
| `units` | string | `"imperial"` | `imperial` (°F) or `metric` (°C) |
| `display_duration` | number | `90` | How long to show weather (seconds) |

### Location Format

Specify location as `"City,CountryCode"`:
- `"New York,US"`
- `"London,GB"`
- `"Tokyo,JP"`
- `"Paris,FR"`
- `"Sydney,AU"`

Or use city ID for more precision:
```json
{
  "location": "5128581"  // New York City ID
}
```

Find city IDs at: http://bulk.openweathermap.org/sample/

## Display Sequence

The Weather on the 8s display shows 7 screens in sequence:

### 1. Intro Screen (3 seconds)
```
┌──────────────┐
│   WEATHER    │
│   on the     │
│      8s      │
└──────────────┘
```

### 2. Current Conditions (8 seconds)
```
┌──────────────┐
│  New York    │
│     72°      │
│ Partly Cloudy│
│  H:78° L:68° │
└──────────────┘
```

### 3-5. Forecast Screens (8 seconds each)
Shows two time periods per screen:
```
┌──────────────┐
│ 2PM    5PM   │
│ 75°    73°   │
│Sunny  Cloudy │
│ 10%    30%   │
└──────────────┘
```

### 6. Details Screen (8 seconds)
```
┌──────────────┐
│   DETAILS    │
│ Humid: 65%   │
│ Wind: S 8mph │
│ Vis: 10mi    │
│ Feels: 70°   │
└──────────────┘
```

### 7. Outro Screen (3 seconds)
```
┌──────────────┐
│  Thank you   │
│for watching  │
│              │
└──────────────┘
```

**Total duration:** ~46 seconds (configurable up to 120 seconds)

## Usage Examples

### Example 1: Classic Setup

Show weather every 10 minutes, just like the old days:

```json
{
  "weather_on_8s": {
    "enabled": true,
    "api_key": "abc123...",
    "location": "Chicago,US",
    "display_duration": 90
  }
}
```

### Example 2: Quick Updates

Shorter display for faster updates:

```json
{
  "weather_on_8s": {
    "enabled": true,
    "display_duration": 45
  }
}
```

### Example 3: Metric Units

For international locations:

```json
{
  "weather_on_8s": {
    "enabled": true,
    "location": "Toronto,CA",
    "units": "metric"
  }
}
```

### Example 4: Disable Weather on 8s

Keep regular weather mode but disable automatic interruptions:

```json
{
  "weather_on_8s": {
    "enabled": false
  }
}
```

## Troubleshooting

### Weather on 8s Not Showing

**Check configuration:**
```bash
# Verify config.json
cat config.json | grep -A 5 weather_on_8s
```

**Check logs:**
```bash
sudo journalctl -u spotify-display -f | grep -i weather
```

**Common issues:**
- API key not configured
- API key invalid
- `enabled` set to `false`
- System time incorrect

### Wrong Location Showing

**Verify location string:**
- Must be exact city name
- Include country code
- Check spelling

**Test API directly:**
```bash
curl "https://api.openweathermap.org/data/2.5/weather?q=YourCity,US&appid=YOUR_API_KEY"
```

### Timing Issues

**Verify system time:**
```bash
date
```

Should show correct time and timezone.

**Sync time:**
```bash
sudo timedatectl set-ntp true
```

### API Rate Limits

Free tier allows 1,000 calls/day.

**Check current usage:**
- Login to OpenWeatherMap dashboard
- View API statistics

**Reduce calls:**
Weather on 8s fetches data once every 10 minutes (144 times/day), well within limits.

## Testing

### Manual Test

Force Weather on 8s to display:

```python
# test_weather_8s.py
from src.modes.weather_on_the_8s import WeatherOnThe8sMode
from src.led_display import LEDDisplay
import json

# Load config
with open('config.json') as f:
    config = json.load(f)

# Initialize
display = LEDDisplay(config['display'])
weather = WeatherOnThe8sMode(display, config)

# Force display
weather.start_display()

# Keep showing for full duration
import time
while weather.is_active():
    weather.update()
    time.sleep(1)
```

Run:
```bash
python3 test_weather_8s.py
```

### Wait for Next Trigger

Check when next display will occur:

```bash
# Current time
date +%M

# Next trigger will be at :08, :18, :28, :38, :48, or :58
```

## Tips & Tricks

### Customize Colors

Edit `src/modes/weather_on_the_8s.py`:

```python
# Change background color
image = Image.new('RGB', display_size, color=(0, 51, 102))  # Weather blue
# Try: (0, 0, 0) for black, (20, 20, 40) for dark blue, etc.

# Change text colors
fill=(255, 255, 255)  # White text
fill=(255, 255, 0)    # Yellow for temperature
fill=(200, 255, 200)  # Light green for conditions
```

### Adjust Timing

Change how long each screen shows:

```python
# In src/modes/weather_on_the_8s.py
screen_durations = {
    'intro': 3,        # Make longer for dramatic effect
    'current': 8,      # Main screen
    'forecast_day1': 8,
    'forecast_day2': 8,
    'forecast_day3': 8,
    'details': 8,
    'outro': 3
}
```

### Multiple Locations

Create location rotation by modifying config:

```json
{
  "weather_on_8s": {
    "locations": ["New York,US", "London,GB", "Tokyo,JP"],
    "rotate": true
  }
}
```

(Requires custom code modification)

## Credits

Inspired by The Weather Channel's legendary "Local on the 8s" feature that aired from 1982-2013.

> "Some of the best TV wasn't TV at all – it was waiting for the local forecast to come on every 10 minutes."
> — Every 90s kid

## API Information

### OpenWeatherMap Free Tier

- **Cost:** Free
- **Calls:** 1,000/day
- **Data:** Current weather + 5-day forecast
- **Signup:** https://openweathermap.org/api

### Alternative Weather APIs

If you want to use a different weather service, edit `src/modes/weather_on_the_8s.py` to integrate:

- **Weather.gov** (US only, no API key needed)
- **Tomorrow.io** (formerly ClimaCell)
- **Weatherbit**
- **Visual Crossing**

## FAQ

**Q: Can I change when it displays?**
A: Yes, edit `should_activate()` in `weather_on_the_8s.py`:
```python
target_minutes = [8, 18, 28, 38, 48, 58]  # Change these
```

**Q: Can I make it show on demand?**
A: Yes, via web interface (feature coming soon) or call:
```python
weather_on_8s.start_display()
```

**Q: Will it interrupt my music?**
A: Yes, but only for 90 seconds, then music resumes automatically.

**Q: Can I disable it temporarily?**
A: Yes, set `"enabled": false` in config.json or restart without the feature.

**Q: Does it work offline?**
A: No, it requires internet connection for weather data. If API fails, it won't display.

## See Also

- [Main README](../README.md)
- [Configuration Guide](SETUP.md)
- [Weather Mode Documentation](../README.md#weather-mode)
- [Troubleshooting Guide](TROUBLESHOOTING.md)

---

**Enjoy your nostalgic weather experience! 🌤️**
