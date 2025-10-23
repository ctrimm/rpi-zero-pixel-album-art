"""
Weather on the 8s Mode - Classic Weather Channel Style
Displays weather forecast every 10 minutes at :08, :18, :28, :38, :48, :58
"""

import logging
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import requests
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor


class WeatherOnThe8sMode:
    """
    Weather on the 8s - Classic Weather Channel inspired display
    Shows detailed weather forecast at specific times ending in 8
    """

    def __init__(self, display, config):
        """
        Initialize Weather on the 8s mode

        Args:
            display: LEDDisplay instance
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config
        self.weather_config = config.get('weather_on_8s', {})
        self.image_processor = ImageProcessor(config.get('image_processing', {}))

        # Configuration
        self.enabled = self.weather_config.get('enabled', True)
        self.api_key = self.weather_config.get('api_key', '')
        self.location = self.weather_config.get('location', 'New York,US')
        self.units = self.weather_config.get('units', 'imperial')
        self.display_duration = self.weather_config.get('display_duration', 90)  # seconds

        # State
        self.weather_data = None
        self.forecast_data = None
        self.last_fetch = 0
        self.fetch_interval = 600  # Fetch new data every 10 minutes

        # Animation state
        self.animation_start = None
        self.current_screen = 0

        # Screens to show
        self.screens = [
            'intro',
            'current',
            'forecast_day1',
            'forecast_day2',
            'forecast_day3',
            'details',
            'outro'
        ]

        if not self.api_key:
            self.logger.warning("Weather on the 8s: No API key configured")
            self.enabled = False

        self.logger.info(f"Weather on the 8s initialized (enabled={self.enabled})")

    def should_activate(self):
        """
        Check if current time should trigger Weather on the 8s

        Returns:
            bool: True if current minute ends in 8
        """
        now = datetime.now()
        minute = now.minute
        second = now.second

        # Trigger at :08, :18, :28, :38, :48, :58
        # Give a 5-second window to catch it
        target_minutes = [8, 18, 28, 38, 48, 58]

        if minute in target_minutes and second < 5:
            return True

        return False

    def is_active(self):
        """
        Check if Weather on the 8s is currently displaying

        Returns:
            bool: True if currently showing weather
        """
        if self.animation_start is None:
            return False

        elapsed = time.time() - self.animation_start
        return elapsed < self.display_duration

    def start_display(self):
        """Start the Weather on the 8s display sequence"""
        self.logger.info("🌤️ Starting Weather on the 8s display!")
        self.animation_start = time.time()
        self.current_screen = 0

        # Fetch fresh weather data
        self._fetch_weather_data()

    def update(self):
        """Update display - called continuously"""
        if not self.enabled:
            return False

        # Check if we should activate
        if not self.is_active() and self.should_activate():
            self.start_display()

        # If active, show the sequence
        if self.is_active():
            self._render_sequence()
            return True

        return False

    def _fetch_weather_data(self):
        """Fetch current weather and forecast from API"""
        try:
            # Check if we should fetch new data
            current_time = time.time()
            if current_time - self.last_fetch < self.fetch_interval and self.weather_data:
                return  # Use cached data

            self.logger.info("Fetching weather data...")

            # Fetch current weather
            current_url = "https://api.openweathermap.org/data/2.5/weather"
            current_params = {
                'q': self.location,
                'appid': self.api_key,
                'units': self.units
            }

            response = requests.get(current_url, params=current_params, timeout=10)
            response.raise_for_status()
            self.weather_data = self._parse_current_weather(response.json())

            # Fetch forecast
            forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
            forecast_params = {
                'q': self.location,
                'appid': self.api_key,
                'units': self.units,
                'cnt': 8  # 8 forecasts (24 hours, 3-hour intervals)
            }

            response = requests.get(forecast_url, params=forecast_params, timeout=10)
            response.raise_for_status()
            self.forecast_data = self._parse_forecast(response.json())

            self.last_fetch = current_time
            self.logger.info("Weather data fetched successfully")

        except Exception as e:
            self.logger.error(f"Error fetching weather data: {e}")
            # Create fallback data
            self.weather_data = self._create_fallback_data()

    def _parse_current_weather(self, data):
        """Parse current weather API response"""
        return {
            'temperature': round(data['main']['temp']),
            'feels_like': round(data['main']['feels_like']),
            'temp_min': round(data['main']['temp_min']),
            'temp_max': round(data['main']['temp_max']),
            'description': data['weather'][0]['description'].title(),
            'icon': data['weather'][0]['icon'],
            'humidity': data['main']['humidity'],
            'wind_speed': round(data['wind']['speed']),
            'wind_deg': data['wind'].get('deg', 0),
            'pressure': data['main']['pressure'],
            'visibility': data.get('visibility', 0) // 1000,  # Convert to km
            'city': data['name']
        }

    def _parse_forecast(self, data):
        """Parse forecast API response"""
        forecasts = []

        for item in data['list'][:8]:  # Next 24 hours
            forecasts.append({
                'time': datetime.fromtimestamp(item['dt']).strftime('%I%p'),
                'temperature': round(item['main']['temp']),
                'description': item['weather'][0]['description'].title(),
                'icon': item['weather'][0]['icon'],
                'pop': round(item.get('pop', 0) * 100)  # Probability of precipitation
            })

        return forecasts

    def _create_fallback_data(self):
        """Create fallback weather data if API fails"""
        return {
            'temperature': 72,
            'feels_like': 70,
            'temp_min': 68,
            'temp_max': 78,
            'description': 'Partly Cloudy',
            'icon': '02d',
            'humidity': 65,
            'wind_speed': 8,
            'wind_deg': 180,
            'pressure': 1013,
            'visibility': 10,
            'city': self.location.split(',')[0]
        }

    def _render_sequence(self):
        """Render the current screen in the sequence"""
        elapsed = time.time() - self.animation_start

        # Each screen shows for different durations
        screen_durations = {
            'intro': 3,
            'current': 8,
            'forecast_day1': 8,
            'forecast_day2': 8,
            'forecast_day3': 8,
            'details': 8,
            'outro': 3
        }

        # Calculate which screen we should be showing
        cumulative_time = 0
        current_screen_index = 0

        for i, screen in enumerate(self.screens):
            duration = screen_durations.get(screen, 5)
            if elapsed < cumulative_time + duration:
                current_screen_index = i
                break
            cumulative_time += duration

        # Render the appropriate screen
        screen_name = self.screens[current_screen_index]

        if screen_name == 'intro':
            self._render_intro()
        elif screen_name == 'current':
            self._render_current_weather()
        elif screen_name.startswith('forecast_'):
            day_index = int(screen_name.split('_')[1].replace('day', '')) - 1
            self._render_forecast_screen(day_index)
        elif screen_name == 'details':
            self._render_details()
        elif screen_name == 'outro':
            self._render_outro()

    def _render_intro(self):
        """Render intro screen with classic styling"""
        display_size = self.display.get_size()
        image = Image.new('RGB', display_size, color=(0, 51, 102))  # Classic weather blue
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Title
        title = "WEATHER"
        bbox = draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 15), title,
                 font=font, fill=(255, 255, 255))

        # Subtitle
        subtitle = "on the"
        bbox = draw.textbbox((0, 0), subtitle, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 28), subtitle,
                 font=font, fill=(200, 200, 200))

        # "8s" in large text
        eights = "8s"
        bbox = draw.textbbox((0, 0), eights, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 40), eights,
                 font=font, fill=(255, 255, 0))

        self.display.display_image(image)

    def _render_current_weather(self):
        """Render current weather conditions"""
        if not self.weather_data:
            return

        display_size = self.display.get_size()
        image = Image.new('RGB', display_size, color=(0, 51, 102))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # City name at top
        city = self.weather_data['city'][:12]  # Truncate if needed
        bbox = draw.textbbox((0, 0), city, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 2), city,
                 font=font, fill=(255, 255, 255))

        # Temperature - large
        temp_text = f"{self.weather_data['temperature']}°"
        bbox = draw.textbbox((0, 0), temp_text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 18), temp_text,
                 font=font, fill=(255, 255, 0))

        # Condition description
        desc = self.weather_data['description'][:15]
        bbox = draw.textbbox((0, 0), desc, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 35), desc,
                 font=font, fill=(200, 255, 200))

        # High/Low
        hl_text = f"H:{self.weather_data['temp_max']}° L:{self.weather_data['temp_min']}°"
        bbox = draw.textbbox((0, 0), hl_text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 48), hl_text,
                 font=font, fill=(150, 200, 255))

        self.display.display_image(image)

    def _render_forecast_screen(self, day_index):
        """Render forecast for a specific time period"""
        if not self.forecast_data or day_index * 2 >= len(self.forecast_data):
            return

        display_size = self.display.get_size()
        image = Image.new('RGB', display_size, color=(0, 51, 102))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Show two forecast periods side by side
        forecasts = self.forecast_data[day_index * 2:(day_index * 2) + 2]

        for i, forecast in enumerate(forecasts):
            x_offset = i * (display_size[0] // 2)

            # Time
            time_text = forecast['time']
            bbox = draw.textbbox((0, 0), time_text, font=font)
            text_width = bbox[2] - bbox[0]
            draw.text((x_offset + (display_size[0] // 4) - text_width // 2, 5),
                     time_text, font=font, fill=(255, 255, 255))

            # Temperature
            temp_text = f"{forecast['temperature']}°"
            bbox = draw.textbbox((0, 0), temp_text, font=font)
            text_width = bbox[2] - bbox[0]
            draw.text((x_offset + (display_size[0] // 4) - text_width // 2, 20),
                     temp_text, font=font, fill=(255, 255, 0))

            # Condition (abbreviated)
            condition = forecast['description'][:8]
            bbox = draw.textbbox((0, 0), condition, font=font)
            text_width = bbox[2] - bbox[0]
            draw.text((x_offset + (display_size[0] // 4) - text_width // 2, 35),
                     condition, font=font, fill=(200, 255, 200))

            # Precipitation chance if significant
            if forecast['pop'] > 20:
                pop_text = f"{forecast['pop']}%"
                bbox = draw.textbbox((0, 0), pop_text, font=font)
                text_width = bbox[2] - bbox[0]
                draw.text((x_offset + (display_size[0] // 4) - text_width // 2, 50),
                         pop_text, font=font, fill=(100, 200, 255))

        self.display.display_image(image)

    def _render_details(self):
        """Render detailed weather information"""
        if not self.weather_data:
            return

        display_size = self.display.get_size()
        image = Image.new('RGB', display_size, color=(0, 51, 102))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Details title
        draw.text((2, 2), "DETAILS", font=font, fill=(255, 255, 255))

        # Humidity
        draw.text((2, 14), f"Humid: {self.weather_data['humidity']}%",
                 font=font, fill=(200, 255, 200))

        # Wind
        wind_dir = self._get_wind_direction(self.weather_data['wind_deg'])
        unit = "mph" if self.units == "imperial" else "m/s"
        draw.text((2, 26), f"Wind: {wind_dir} {self.weather_data['wind_speed']}{unit}",
                 font=font, fill=(200, 255, 200))

        # Visibility
        vis_unit = "mi" if self.units == "imperial" else "km"
        draw.text((2, 38), f"Vis: {self.weather_data['visibility']}{vis_unit}",
                 font=font, fill=(200, 255, 200))

        # Feels like
        draw.text((2, 50), f"Feels: {self.weather_data['feels_like']}°",
                 font=font, fill=(200, 255, 200))

        self.display.display_image(image)

    def _render_outro(self):
        """Render outro screen"""
        display_size = self.display.get_size()
        image = Image.new('RGB', display_size, color=(0, 51, 102))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Thank you message
        text = "Thank you"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 20), text,
                 font=font, fill=(255, 255, 255))

        text2 = "for watching"
        bbox = draw.textbbox((0, 0), text2, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((display_size[0] - text_width) // 2, 35), text2,
                 font=font, fill=(255, 255, 255))

        self.display.display_image(image)

    def _get_wind_direction(self, degrees):
        """Convert wind degrees to cardinal direction"""
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / 45) % 8
        return directions[index]

    def _display_error(self):
        """Display error message"""
        display_size = self.display.get_size()
        error = self.image_processor.create_text_image(
            "Weather\nError",
            display_size,
            color=(255, 100, 100)
        )
        self.display.display_image(error)
