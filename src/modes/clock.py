"""
Clock Mode - Display time and date
"""

import logging
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor


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
        self.time_format = config.get('clock', {}).get('time_format', '12h')  # 12h or 24h
        self.show_seconds = config.get('clock', {}).get('show_seconds', True)
        self.show_date = config.get('clock', {}).get('show_date', True)
        self.color = tuple(config.get('clock', {}).get('color', [255, 255, 255]))

        self.logger.info("Clock mode initialized")

    def update(self):
        """Update clock display"""
        try:
            self._display_time()
            time.sleep(1)  # Update every second

        except Exception as e:
            self.logger.error(f"Error in clock mode update: {e}")
            time.sleep(5)

    def _display_time(self):
        """Display current time and date"""
        try:
            display_size = self.display.get_size()
            image = Image.new('RGB', display_size, color=(0, 0, 0))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()

            now = datetime.now()

            # Format time
            if self.time_format == '12h':
                if self.show_seconds:
                    time_str = now.strftime('%I:%M:%S %p')
                else:
                    time_str = now.strftime('%I:%M %p')
            else:  # 24h
                if self.show_seconds:
                    time_str = now.strftime('%H:%M:%S')
                else:
                    time_str = now.strftime('%H:%M')

            # Draw time
            bbox = draw.textbbox((0, 0), time_str, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            if self.show_date:
                # Position time in upper portion
                time_pos = ((display_size[0] - text_width) // 2, display_size[1] // 3)
            else:
                # Center time
                time_pos = ((display_size[0] - text_width) // 2, (display_size[1] - text_height) // 2)

            draw.text(time_pos, time_str, font=font, fill=self.color)

            # Draw date if enabled
            if self.show_date:
                date_str = now.strftime('%b %d')
                bbox = draw.textbbox((0, 0), date_str, font=font)
                text_width = bbox[2] - bbox[0]
                date_pos = ((display_size[0] - text_width) // 2, display_size[1] * 2 // 3)
                draw.text(date_pos, date_str, font=font, fill=self.color)

                # Day of week
                day_str = now.strftime('%A')[:3]  # Abbreviated day
                bbox = draw.textbbox((0, 0), day_str, font=font)
                text_width = bbox[2] - bbox[0]
                day_pos = ((display_size[0] - text_width) // 2, display_size[1] // 2 + 5)
                draw.text(day_pos, day_str, font=font, fill=(150, 150, 150))

            self.display.display_image(image)

        except Exception as e:
            self.logger.error(f"Error displaying time: {e}")
