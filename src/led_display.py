"""
LED Matrix Display Controller
Handles the RGB LED matrix hardware interface
Auto-detects environment and uses simulator on development machines
"""

import logging
import os
import platform
from PIL import Image, ImageDraw, ImageFont

# Check if we should use simulator
def should_use_simulator():
    """Detect if we should use the simulator instead of real hardware"""
    # Check environment variable override
    if os.environ.get('LED_SIMULATOR', '').lower() in ('1', 'true', 'yes'):
        return True

    # Check if running on Raspberry Pi
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            if 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo:
                return False  # We're on a Pi, use real hardware
    except:
        pass

    # Not on Pi, use simulator
    return True

# Try to import RGB matrix library (only works on Pi)
MATRIX_AVAILABLE = False
if not should_use_simulator():
    try:
        from rgbmatrix import RGBMatrix, RGBMatrixOptions
        MATRIX_AVAILABLE = True
    except ImportError:
        print("⚠️  Warning: rgbmatrix library not found. Using simulator mode.")
        print("   Install with: cd ~/rpi-rgb-led-matrix && make install-python")


class LEDDisplay:
    """LED Matrix display controller"""

    def __init__(self, config):
        """
        Initialize LED display

        Args:
            config: Display configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.matrix = None
        self.offscreen_canvas = None
        self.current_image = None

        if MATRIX_AVAILABLE:
            self._initialize_matrix()
        else:
            self.logger.warning("Running in simulation mode (no LED matrix connected)")
            # Create a virtual canvas for development/testing
            self.width = config.get('cols', 64)
            self.height = config.get('rows', 64)

    def _initialize_matrix(self):
        """Initialize the RGB matrix hardware"""
        try:
            options = RGBMatrixOptions()

            # Basic settings
            options.rows = self.config.get('rows', 64)
            options.cols = self.config.get('cols', 64)
            options.chain_length = self.config.get('chain_length', 1)
            options.parallel = self.config.get('parallel', 1)
            options.brightness = self.config.get('brightness', 80)

            # Hardware settings
            options.hardware_mapping = self.config.get('hardware_mapping', 'regular')
            options.gpio_slowdown = self.config.get('gpio_slowdown', 2)

            # Advanced settings
            options.pwm_bits = self.config.get('pwm_bits', 11)
            options.pwm_lsb_nanoseconds = self.config.get('pwm_lsb_nanoseconds', 130)
            options.led_rgb_sequence = self.config.get('led_rgb_sequence', 'RGB')
            options.show_refresh_rate = self.config.get('show_refresh_rate', False)

            # Disable hardware pulsing
            options.disable_hardware_pulsing = True

            self.matrix = RGBMatrix(options=options)
            self.offscreen_canvas = self.matrix.CreateFrameCanvas()
            self.width = options.cols
            self.height = options.rows

            self.logger.info(f"LED matrix initialized: {self.width}x{self.height}")

        except Exception as e:
            self.logger.error(f"Failed to initialize LED matrix: {e}")
            raise

    def display_image(self, image):
        """
        Display a PIL Image on the matrix

        Args:
            image: PIL Image object (will be resized to fit display)
        """
        if not isinstance(image, Image.Image):
            self.logger.error("Invalid image object")
            return

        # Ensure image is RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Resize to display dimensions if needed
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height), Image.LANCZOS)

        self.current_image = image

        if MATRIX_AVAILABLE and self.matrix:
            self.matrix.SetImage(image)
        else:
            # In simulation mode, optionally save to file for debugging
            self.logger.debug(f"Simulation: Would display {image.size} image")

    def display_text(self, text, font_path=None, font_size=8, color=(255, 255, 255), position=None):
        """
        Display text on the matrix

        Args:
            text: Text string to display
            font_path: Path to font file (optional)
            font_size: Font size
            color: RGB color tuple
            position: (x, y) position tuple (optional, defaults to center)
        """
        # Create blank image
        image = Image.new('RGB', (self.width, self.height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Load font
        try:
            if font_path and os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
            else:
                # Use default bitmap font
                font = ImageFont.load_default()
        except Exception as e:
            self.logger.warning(f"Error loading font: {e}, using default")
            font = ImageFont.load_default()

        # Calculate text position if not provided
        if position is None:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((self.width - text_width) // 2, (self.height - text_height) // 2)

        # Draw text
        draw.text(position, text, font=font, fill=color)

        # Display the image
        self.display_image(image)

    def scroll_text(self, text, color=(255, 255, 255), speed=2):
        """
        Scroll text across the display

        Args:
            text: Text to scroll
            color: RGB color tuple
            speed: Scroll speed (pixels per frame)
        """
        # This is a simplified version - implement full scrolling in mode classes
        self.display_text(text, color=color)

    def clear(self):
        """Clear the display"""
        blank = Image.new('RGB', (self.width, self.height), color=(0, 0, 0))
        self.display_image(blank)

    def set_brightness(self, brightness):
        """
        Set display brightness

        Args:
            brightness: Brightness value (0-100)
        """
        brightness = max(0, min(100, brightness))

        if MATRIX_AVAILABLE and self.matrix:
            self.matrix.brightness = brightness
            self.logger.info(f"Brightness set to {brightness}")
        else:
            self.logger.debug(f"Simulation: Brightness set to {brightness}")

        self.config['brightness'] = brightness

    def get_size(self):
        """
        Get display dimensions

        Returns:
            tuple: (width, height)
        """
        return (self.width, self.height)

    def create_blank_image(self):
        """
        Create a blank PIL Image matching display size

        Returns:
            PIL.Image: Blank RGB image
        """
        return Image.new('RGB', (self.width, self.height), color=(0, 0, 0))

    def test_pattern(self):
        """Display a test pattern"""
        image = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(image)

        # Draw color bars
        bar_width = self.width // 3
        draw.rectangle([(0, 0), (bar_width, self.height)], fill=(255, 0, 0))
        draw.rectangle([(bar_width, 0), (bar_width * 2, self.height)], fill=(0, 255, 0))
        draw.rectangle([(bar_width * 2, 0), (self.width, self.height)], fill=(0, 0, 255))

        self.display_image(image)
        self.logger.info("Test pattern displayed")


# Simulation mode helper class
class SimulatedDisplay(LEDDisplay):
    """Simulated display for development without hardware"""

    def __init__(self, config):
        """Initialize simulated display"""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.width = config.get('cols', 64)
        self.height = config.get('rows', 64)
        self.current_image = None
        self.logger.info(f"Simulated display initialized: {self.width}x{self.height}")

    def display_image(self, image):
        """Save image to file instead of displaying"""
        self.current_image = image
        # Optionally save for debugging
        debug_path = 'debug_display.png'
        try:
            # Scale up for easier viewing
            scaled = image.resize((self.width * 4, self.height * 4), Image.NEAREST)
            scaled.save(debug_path)
            self.logger.debug(f"Simulated display saved to {debug_path}")
        except Exception as e:
            self.logger.debug(f"Could not save debug image: {e}")
