"""
Pipes Screensaver Mode - Classic Windows 3D Pipes
Nostalgic screensaver with colorful pipes growing across the display
"""

import logging
import time
import random
from PIL import Image, ImageDraw
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor


class Pipe:
    """A single pipe that grows across the screen"""

    def __init__(self, x, y, direction, color, width, height):
        self.x = x
        self.y = y
        self.direction = direction  # 0=up, 1=right, 2=down, 3=left
        self.color = color
        self.segments = [(x, y)]
        self.alive = True
        self.width = width
        self.height = height
        self.pipe_width = 2

    def grow(self):
        """Extend the pipe in current direction"""
        if not self.alive:
            return

        # Randomly change direction sometimes
        if random.random() < 0.15:  # 15% chance to turn
            self.direction = random.randint(0, 3)

        # Calculate next position
        next_x, next_y = self.x, self.y

        if self.direction == 0:  # up
            next_y -= 1
        elif self.direction == 1:  # right
            next_x += 1
        elif self.direction == 2:  # down
            next_y += 1
        elif self.direction == 3:  # left
            next_x -= 1

        # Check boundaries
        if next_x < 0 or next_x >= self.width or next_y < 0 or next_y >= self.height:
            self.alive = False
            return

        # Add segment
        self.x = next_x
        self.y = next_y
        self.segments.append((next_x, next_y))

        # Randomly change color slightly
        if random.random() < 0.1:  # 10% chance to shift color
            r, g, b = self.color
            r = max(0, min(255, r + random.randint(-30, 30)))
            g = max(0, min(255, g + random.randint(-30, 30)))
            b = max(0, min(255, b + random.randint(-30, 30)))
            self.color = (r, g, b)


class PipesMode:
    """Pipes screensaver mode - Classic Windows 3D Pipes aesthetic"""

    def __init__(self, display, config):
        """
        Initialize Pipes screensaver mode

        Args:
            display: LEDDisplay instance
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config
        self.pipes_config = config.get('screensavers', {}).get('pipes', {})
        self.image_processor = ImageProcessor(config.get('image_processing', {}))

        # Configuration
        self.enabled = self.pipes_config.get('enabled', True)
        self.num_pipes = self.pipes_config.get('num_pipes', 4)
        self.speed = self.pipes_config.get('speed', 0.05)  # seconds between updates
        self.fade_trail = self.pipes_config.get('fade_trail', True)
        self.background_color = tuple(self.pipes_config.get('background_color', [0, 0, 0]))

        # Display size
        display_size = self.display.get_size()
        self.width = display_size[0]
        self.height = display_size[1]

        # State
        self.pipes = []
        self.canvas = None
        self.last_update = 0

        # Initialize
        self._initialize_pipes()

        self.logger.info(f"🔧 Pipes screensaver initialized ({self.num_pipes} pipes)")

    def _initialize_pipes(self):
        """Create initial pipes"""
        self.pipes = []

        # Create canvas
        self.canvas = Image.new('RGB', (self.width, self.height), self.background_color)

        # Generate vibrant colors
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

        for i in range(self.num_pipes):
            # Random starting position
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            direction = random.randint(0, 3)
            color = random.choice(colors)

            pipe = Pipe(x, y, direction, color, self.width, self.height)
            self.pipes.append(pipe)

    def update(self):
        """Update pipes screensaver"""
        try:
            # Rate limiting
            current_time = time.time()
            if current_time - self.last_update < self.speed:
                time.sleep(0.01)
                return

            self.last_update = current_time

            # Fade the canvas slightly for trail effect
            if self.fade_trail:
                self.canvas = self._fade_image(self.canvas, 0.95)

            # Update all pipes
            active_pipes = 0
            for pipe in self.pipes:
                if pipe.alive:
                    pipe.grow()
                    self._draw_pipe_segment(pipe)
                    active_pipes += 1

            # If no pipes are alive, restart
            if active_pipes == 0:
                self.logger.debug("All pipes died, restarting...")
                self._initialize_pipes()

            # Display
            self.display.display_image(self.canvas.copy())

        except Exception as e:
            self.logger.error(f"Error in pipes mode update: {e}", exc_info=True)
            time.sleep(1)

    def _draw_pipe_segment(self, pipe):
        """Draw the latest segment of a pipe"""
        draw = ImageDraw.Draw(self.canvas)

        # Draw the new segment
        if len(pipe.segments) >= 2:
            x1, y1 = pipe.segments[-2]
            x2, y2 = pipe.segments[-1]

            # Draw thicker line
            draw.line([(x1, y1), (x2, y2)], fill=pipe.color, width=pipe.pipe_width)

            # Draw junction point
            draw.rectangle(
                [(x2 - 1, y2 - 1), (x2 + 1, y2 + 1)],
                fill=pipe.color
            )

    def _fade_image(self, image, factor):
        """Fade image for trail effect"""
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(factor)
