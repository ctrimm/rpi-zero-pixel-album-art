"""
Clock Mode - Display time and date
"""

import logging
import time
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor
from utils.runtime import mode_sleep


class ClockMode:
    """Clock mode - displays time and date"""

    def __init__(self, display, config):
        """
        Initialize clock mode

        Args:
            display: LEDDisplay instance
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config
        self.image_processor = ImageProcessor(config.get('image_processing', {}))

        # Clock settings
        self.style = config.get('modes', {}).get('schedule', {}).get('clock', {}).get('style', 'digital')
        self.time_format = config.get('clock', {}).get('time_format', '12h')  # 12h or 24h
        self.show_seconds = config.get('clock', {}).get('show_seconds', True)
        self.show_date = config.get('clock', {}).get('show_date', True)
        self.color = tuple(config.get('clock', {}).get('color', [255, 255, 255]))

        self.logger.info(f"Clock mode initialized - style: {self.style}")

    def update(self):
        """Update clock display"""
        try:
            if self.style == 'analog':
                self._display_analog_clock()
            else:
                self._display_digital_clock()

            mode_sleep(1)  # Update every second

        except Exception as e:
            self.logger.error(f"Error in clock mode update: {e}")
            mode_sleep(5)

    def _display_digital_clock(self):
        """Display current time and date in digital format"""
        try:
            display_size = self.display.get_size()
            image = Image.new('RGB', display_size, color=(0, 0, 0))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()

            now = datetime.now()
            width, height = display_size

            def centered(text, y, fill):
                bbox = draw.textbbox((0, 0), text, font=font)
                draw.text(((width - (bbox[2] - bbox[0])) // 2 - bbox[0], y), text, font=font, fill=fill)

            # Time on its own line; AM/PM goes on a second line so the time
            # never runs off the 64px panel.
            if self.time_format == '12h':
                fmt = '%I:%M:%S' if self.show_seconds else '%I:%M'
                time_str = now.strftime(fmt).lstrip('0')
                suffix = now.strftime('%p')
            else:
                time_str = now.strftime('%H:%M:%S' if self.show_seconds else '%H:%M')
                suffix = None

            if self.show_date:
                centered(time_str, 8, self.color)
                if suffix:
                    centered(suffix, 20, (150, 150, 150))
                centered(now.strftime('%a').upper(), 36, (150, 150, 150))
                centered(now.strftime('%b %d').upper(), 48, self.color)
            else:
                centered(time_str, height // 2 - 10, self.color)
                if suffix:
                    centered(suffix, height // 2 + 4, (150, 150, 150))

            self.display.display_image(image)

        except Exception as e:
            self.logger.error(f"Error displaying digital clock: {e}")

    def _display_analog_clock(self):
        """Display analog clock with hour, minute, and second hands"""
        try:
            display_size = self.display.get_size()
            image = Image.new('RGB', display_size, color=(0, 0, 0))
            draw = ImageDraw.Draw(image)

            now = datetime.now()

            # Calculate center and radius
            center_x = display_size[0] // 2
            center_y = display_size[1] // 2
            radius = min(center_x, center_y) - 2

            # Draw clock circle
            draw.ellipse(
                [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                outline=(100, 100, 100),
                width=1
            )

            # Calculate angles (12 o'clock is at -90 degrees)
            hour = now.hour % 12
            minute = now.minute
            second = now.second

            # Hour hand (shorter, thicker)
            hour_angle = math.radians((hour * 30 + minute * 0.5) - 90)
            hour_length = radius * 0.5
            hour_x = center_x + hour_length * math.cos(hour_angle)
            hour_y = center_y + hour_length * math.sin(hour_angle)
            draw.line(
                [(center_x, center_y), (hour_x, hour_y)],
                fill=(255, 255, 255),
                width=2
            )

            # Minute hand (longer, medium thickness)
            minute_angle = math.radians((minute * 6) - 90)
            minute_length = radius * 0.75
            minute_x = center_x + minute_length * math.cos(minute_angle)
            minute_y = center_y + minute_length * math.sin(minute_angle)
            draw.line(
                [(center_x, center_y), (minute_x, minute_y)],
                fill=(200, 200, 200),
                width=2
            )

            # Second hand (longest, thin) - only if show_seconds is enabled
            if self.show_seconds:
                second_angle = math.radians((second * 6) - 90)
                second_length = radius * 0.9
                second_x = center_x + second_length * math.cos(second_angle)
                second_y = center_y + second_length * math.sin(second_angle)
                draw.line(
                    [(center_x, center_y), (second_x, second_y)],
                    fill=(255, 50, 50),
                    width=1
                )

            # Draw center dot
            dot_radius = 2
            draw.ellipse(
                [center_x - dot_radius, center_y - dot_radius,
                 center_x + dot_radius, center_y + dot_radius],
                fill=(255, 255, 255)
            )

            self.display.display_image(image)

        except Exception as e:
            self.logger.error(f"Error displaying analog clock: {e}")
