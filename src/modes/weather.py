"""
Weather Mode - Display current weather and forecast
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


class WeatherMode:
    """Weather mode - displays current weather conditions"""

    def __init__(self, display, config):
        """
        Initialize weather mode

        Args:
            display: LEDDisplay instance
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config
        self.weather_config = config.get('weather', {})
        self.image_processor = ImageProcessor(config.get('image_processing', {}))

        self.enabled = self.weather_config.get('enabled', False)
        self.api_key = self.weather_config.get('api_key', '')
        self.location = self.weather_config.get('location', 'New York,US')
        self.units = self.weather_config.get('units', 'imperial')
        self.update_interval = self.weather_config.get('update_interval', 600)

        self.last_update = 0
        self.weather_data = None

        if self.enabled and not self.api_key:
            self.logger.warning("Weather mode enabled but no API key configured")
            self.enabled = False

        self.logger.info(f"Weather mode initialized (enabled={self.enabled})")

    def update(self):
        """Update weather display"""
        if not self.enabled:
            self._display_disabled_message()
            time.sleep(10)
            return

        try:
            # Check if we need to fetch new data
            current_time = time.time()
            if current_time - self.last_update >= self.update_interval or self.weather_data is None:
                self.weather_data = self._fetch_weather()
                self.last_update = current_time

            # Display weather
            if self.weather_data:
                self._display_weather(self.weather_data)
            else:
                self._display_error()

            time.sleep(5)

        except Exception as e:
            self.logger.error(f"Error in weather mode update: {e}")
            self._display_error()
            time.sleep(10)

    def _fetch_weather(self):
        """
        Fetch weather data from OpenWeatherMap API

        Returns:
            dict: Weather data or None
        """
        try:
            # OpenWeatherMap API endpoint
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                'q': self.location,
                'appid': self.api_key,
                'units': self.units
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            weather_info = {
                'temperature': round(data['main']['temp']),
                'feels_like': round(data['main']['feels_like']),
                'description': data['weather'][0]['description'].title(),
                'icon': data['weather'][0]['icon'],
                'humidity': data['main']['humidity'],
                'wind_speed': round(data['wind']['speed']),
                'city': data['name']
            }

            self.logger.info(f"Weather updated: {weather_info['temperature']}° {weather_info['description']}")
            return weather_info

        except requests.RequestException as e:
            self.logger.error(f"Error fetching weather data: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing weather data: {e}")
            return None

    def _display_weather(self, weather_data):
        """
        Display weather information

        Args:
            weather_data: Weather data dictionary
        """
        try:
            display_size = self.display.get_size()
            image = Image.new('RGB', display_size, color=(0, 0, 30))
            draw = ImageDraw.Draw(image)

            # Temperature (large)
            temp_text = f"{weather_data['temperature']}°"
            font = ImageFont.load_default()

            # Draw temperature centered
            bbox = draw.textbbox((0, 0), temp_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            temp_pos = ((display_size[0] - text_width) // 2, display_size[1] // 3)
            draw.text(temp_pos, temp_text, font=font, fill=(255, 255, 255))

            # Condition description (small, below temperature)
            desc_text = weather_data['description'][:15]  # Truncate if too long
            bbox = draw.textbbox((0, 0), desc_text, font=font)
            text_width = bbox[2] - bbox[0]
            desc_pos = ((display_size[0] - text_width) // 2, display_size[1] // 2 + 10)
            draw.text(desc_pos, desc_text, font=font, fill=(200, 200, 200))

            self.display.display_image(image)

        except Exception as e:
            self.logger.error(f"Error displaying weather: {e}")
            self._display_error()

    def _display_disabled_message(self):
        """Display message when weather mode is disabled"""
        display_size = self.display.get_size()
        placeholder = self.image_processor.create_text_image(
            "Weather\nDisabled",
            display_size,
            color=(100, 100, 100)
        )
        self.display.display_image(placeholder)

    def _display_error(self):
        """Display error message"""
        display_size = self.display.get_size()
        error = self.image_processor.create_text_image(
            "Weather\nError",
            display_size,
            color=(255, 100, 100)
        )
        self.display.display_image(error)
