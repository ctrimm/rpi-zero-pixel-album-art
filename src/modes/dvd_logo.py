"""
DVD Logo Screensaver Mode - Bouncing DVD Logo
Classic bouncing logo that changes color on edges, rainbow on corner hits
"""

import logging
import time
import random
from PIL import Image, ImageDraw, ImageFont
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor


PIXEL_TEXT = "DVD"
# 3x5 glyphs, one int per row, bit 2 = left column
PIXEL_GLYPHS = {
    'D': [0b110, 0b101, 0b101, 0b101, 0b110],
    'V': [0b101, 0b101, 0b101, 0b010, 0b010],
}


class DVDLogoMode:
    """DVD Logo screensaver mode - Bouncing logo with color changes"""

    def __init__(self, display, config):
        """
        Initialize DVD Logo screensaver mode

        Args:
            display: LEDDisplay instance
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config
        self.dvd_config = config.get('screensavers', {}).get('dvd_logo', {})
        self.image_processor = ImageProcessor(config.get('image_processing', {}))

        # Configuration
        self.enabled = self.dvd_config.get('enabled', True)
        self.speed = self.dvd_config.get('speed', 0.016)  # ~60 FPS for smooth animation
        self.logo_width = self.dvd_config.get('logo_width', 16)
        self.logo_height = self.dvd_config.get('logo_height', 8)

        # Display size
        display_size = self.display.get_size()
        self.width = display_size[0]
        self.height = display_size[1]

        # State
        self.x = random.randint(0, self.width - self.logo_width)
        self.y = random.randint(0, self.height - self.logo_height)
        self.dx = 1  # velocity x
        self.dy = 1  # velocity y
        self.color = self._random_color()
        self.rainbow_mode = False
        self.rainbow_index = 0
        self.last_update = 0

        # Corner hit counter
        self.corner_hits = 0

        self.logger.info("📀 DVD Logo screensaver initialized")

    def _random_color(self):
        """Get a random vibrant color"""
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 128, 0),  # Orange
            (128, 0, 255),  # Purple
        ]
        return random.choice(colors)

    def _get_rainbow_color(self):
        """Get rainbow color based on index"""
        # Cycle through rainbow
        rainbow = [
            (255, 0, 0),    # Red
            (255, 127, 0),  # Orange
            (255, 255, 0),  # Yellow
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (75, 0, 130),   # Indigo
            (148, 0, 211),  # Violet
        ]
        self.rainbow_index = (self.rainbow_index + 1) % (len(rainbow) * 3)
        return rainbow[self.rainbow_index // 3]

    def update(self):
        """Update DVD logo screensaver"""
        try:
            # Rate limiting for smooth animation
            current_time = time.time()
            if current_time - self.last_update < self.speed:
                return  # Skip frame but don't sleep - keeps animation smooth

            self.last_update = current_time

            # Move logo
            new_x = self.x + self.dx
            new_y = self.y + self.dy

            # Check for collisions
            hit_horizontal = False
            hit_vertical = False
            hit_corner = False

            # Check horizontal edges
            if new_x <= 0 or new_x + self.logo_width >= self.width:
                self.dx = -self.dx
                hit_horizontal = True
                new_x = max(0, min(new_x, self.width - self.logo_width))

            # Check vertical edges
            if new_y <= 0 or new_y + self.logo_height >= self.height:
                self.dy = -self.dy
                hit_vertical = True
                new_y = max(0, min(new_y, self.height - self.logo_height))

            # Check for corner hit (both edges at same time)
            if hit_horizontal and hit_vertical:
                hit_corner = True
                self.corner_hits += 1
                self.logger.info(f"🎯 CORNER HIT! Total corner hits: {self.corner_hits}")

            # Update position
            self.x = new_x
            self.y = new_y

            # Update color
            if hit_corner:
                # CORNER HIT! Enter rainbow mode
                self.rainbow_mode = True
                self.rainbow_index = 0
                self.color = self._get_rainbow_color()
                self.logger.debug("🌈 Rainbow mode activated!")
            elif hit_horizontal or hit_vertical:
                if self.rainbow_mode:
                    # Exit rainbow mode
                    self.rainbow_mode = False
                    self.color = self._random_color()
                    self.logger.debug("Exited rainbow mode")
                else:
                    # Normal edge hit - change color
                    self.color = self._random_color()
            elif self.rainbow_mode:
                # Continue rainbow animation
                self.color = self._get_rainbow_color()

            # Draw
            self._draw_frame()

        except Exception as e:
            self.logger.error(f"Error in DVD logo mode update: {e}", exc_info=True)
            time.sleep(1)

    def _draw_frame(self):
        """Draw current frame"""
        # Create black background
        image = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        logo_x = int(self.x)
        logo_y = int(self.y)

        # Logo box (inclusive coords, so subtract 1 to keep it logo_width wide)
        draw.rectangle(
            [(logo_x, logo_y), (logo_x + self.logo_width - 1, logo_y + self.logo_height - 1)],
            fill=self.color
        )

        # "DVD" in a tiny 3x5 pixel font so it fits inside the 16x8 box
        text_w = len(PIXEL_TEXT) * 4 - 1
        tx = logo_x + (self.logo_width - text_w) // 2
        ty = logo_y + (self.logo_height - 5) // 2
        for i, ch in enumerate(PIXEL_TEXT):
            for row, bits in enumerate(PIXEL_GLYPHS[ch]):
                for col in range(3):
                    if bits & (4 >> col):
                        draw.point((tx + i * 4 + col, ty + row), fill=(0, 0, 0))

        # Corner hit counter, bottom-right in dim grey
        if self.corner_hits > 0:
            font = ImageFont.load_default()
            counter_text = str(self.corner_hits)
            bbox = draw.textbbox((0, 0), counter_text, font=font)
            draw.text((self.width - (bbox[2] - bbox[0]) - 2, self.height - 12), counter_text,
                      font=font, fill=(80, 80, 80))

        # Display
        self.display.display_image(image)
