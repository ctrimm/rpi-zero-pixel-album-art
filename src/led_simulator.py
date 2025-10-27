"""
LED Matrix Simulator for Development
Provides a visual window showing the 64x64 LED matrix for local development
"""

import logging
import tkinter as tk
from PIL import Image, ImageTk
import threading
import time


class LEDMatrixSimulator:
    """
    Simulates the LED matrix display in a Tkinter window
    Perfect for development on Mac/Windows/Linux without Pi hardware
    """

    def __init__(self, width=64, height=64, pixel_size=8):
        """
        Initialize the LED matrix simulator

        Args:
            width: Matrix width in pixels (default 64)
            height: Matrix height in pixels (default 64)
            pixel_size: Size of each LED pixel in the window (default 8)
        """
        self.logger = logging.getLogger(__name__)
        self.width = width
        self.height = height
        self.pixel_size = pixel_size

        # Window size
        self.window_width = width * pixel_size
        self.window_height = height * pixel_size

        # Current image
        self.current_image = Image.new('RGB', (width, height), color=(0, 0, 0))

        # Tkinter setup
        self.root = None
        self.canvas = None
        self.tk_image = None
        self.running = False

        # Start GUI in separate thread
        self.gui_thread = threading.Thread(target=self._run_gui, daemon=True)
        self.gui_thread.start()

        # Wait for window to initialize
        time.sleep(0.5)

        self.logger.info(f"🖥️  LED Matrix Simulator initialized ({width}x{height})")
        self.logger.info(f"🪟  Simulator window: {self.window_width}x{self.window_height} pixels")

    def _run_gui(self):
        """Run the Tkinter GUI in a separate thread"""
        self.root = tk.Tk()
        self.root.title(f"LED Matrix Simulator ({self.width}x{self.height})")
        self.root.resizable(False, False)

        # Create canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self.window_width,
            height=self.window_height,
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack()

        # Add info label
        info_frame = tk.Frame(self.root, bg='#2b2b2b')
        info_frame.pack(fill=tk.X)

        info_label = tk.Label(
            info_frame,
            text=f"LED Matrix Emulator - {self.width}x{self.height} | Pixel Size: {self.pixel_size}x",
            bg='#2b2b2b',
            fg='#00ff00',
            font=('Courier', 10),
            pady=5
        )
        info_label.pack()

        mode_label = tk.Label(
            info_frame,
            text="Development Mode - Changes update in real-time",
            bg='#2b2b2b',
            fg='#888888',
            font=('Courier', 9),
            pady=2
        )
        mode_label.pack()

        self.running = True

        # Display initial blank screen
        self._update_display()

        self.root.mainloop()
        self.running = False

    def _update_display(self):
        """Update the display with current image"""
        if not self.running or not self.canvas:
            return

        try:
            # Scale up the image to make pixels visible
            scaled_image = self.current_image.resize(
                (self.window_width, self.window_height),
                Image.NEAREST  # Use NEAREST for pixel-perfect scaling
            )

            # Convert to PhotoImage
            self.tk_image = ImageTk.PhotoImage(scaled_image)

            # Update canvas
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        except Exception as e:
            self.logger.error(f"Error updating simulator display: {e}")

    def display_image(self, image):
        """
        Display a PIL Image on the simulated matrix

        Args:
            image: PIL Image object (will be resized to matrix dimensions)
        """
        if not isinstance(image, Image.Image):
            self.logger.error("Invalid image object")
            return

        # Ensure image is RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Resize to matrix dimensions if needed
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height), Image.LANCZOS)

        self.current_image = image.copy()

        # Schedule display update on GUI thread
        if self.running and self.root:
            self.root.after(0, self._update_display)

    def clear(self):
        """Clear the display (set to black)"""
        blank = Image.new('RGB', (self.width, self.height), color=(0, 0, 0))
        self.display_image(blank)

    def close(self):
        """Close the simulator window"""
        if self.root:
            self.root.quit()
        self.running = False


class SimulatedLEDDisplay:
    """
    Drop-in replacement for LEDDisplay that uses the simulator
    Compatible with the same API as the real LED display
    """

    def __init__(self, config):
        """
        Initialize simulated LED display

        Args:
            config: Display configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        # Get dimensions from config
        self.width = config.get('cols', 64)
        self.height = config.get('rows', 64)
        self.brightness = config.get('brightness', 80)

        # Pixel size for simulator (how big each LED appears)
        pixel_size = config.get('simulator_pixel_size', 8)

        # Initialize simulator
        self.logger.info("🖥️  Initializing LED Matrix Simulator (Development Mode)")
        self.logger.info("📍 Running on Mac/development machine - no Pi hardware needed")

        self.simulator = LEDMatrixSimulator(
            width=self.width,
            height=self.height,
            pixel_size=pixel_size
        )

        self.current_image = None

        self.logger.info(f"✓ Simulated display ready: {self.width}x{self.height}")
        self.logger.info("💡 Display updates will show in the simulator window")

    def display_image(self, image):
        """
        Display a PIL Image on the simulated matrix

        Args:
            image: PIL Image object
        """
        self.current_image = image
        self.simulator.display_image(image)

    def display_text(self, text, font_path=None, font_size=8, color=(255, 255, 255), position=None):
        """Display text on the matrix"""
        from PIL import ImageDraw, ImageFont
        import os

        # Create blank image
        image = Image.new('RGB', (self.width, self.height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Load font
        try:
            if font_path and os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
            else:
                font = ImageFont.load_default()
        except Exception as e:
            self.logger.warning(f"Error loading font: {e}, using default")
            font = ImageFont.load_default()

        # Calculate position if not provided
        if position is None:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((self.width - text_width) // 2, (self.height - text_height) // 2)

        # Draw text
        draw.text(position, text, font=font, fill=color)

        # Display
        self.display_image(image)

    def clear(self):
        """Clear the display"""
        self.simulator.clear()

    def set_brightness(self, brightness):
        """Set display brightness (simulated)"""
        brightness = max(0, min(100, brightness))
        self.brightness = brightness
        self.logger.info(f"💡 Brightness set to {brightness} (simulated)")

    def get_size(self):
        """Get display dimensions"""
        return (self.width, self.height)

    def create_blank_image(self):
        """Create a blank PIL Image matching display size"""
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
        self.logger.info("🎨 Test pattern displayed")

    def close(self):
        """Close the simulator"""
        self.simulator.close()


# Auto-detect function to choose appropriate display
def create_display(config):
    """
    Automatically create the appropriate display based on environment

    Returns LEDDisplay on Raspberry Pi, SimulatedLEDDisplay on dev machines
    """
    import platform
    import os

    # Check if we're on a Raspberry Pi
    is_raspberry_pi = False

    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            if 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo:
                is_raspberry_pi = True
    except:
        pass

    # Check for development mode override
    dev_mode = os.environ.get('LED_SIMULATOR', '').lower() in ('1', 'true', 'yes')

    if dev_mode or not is_raspberry_pi:
        # Use simulator
        print("🖥️  Development Mode: Using LED Matrix Simulator")
        print("💡 Set LED_SIMULATOR=0 to disable simulator on Pi")
        return SimulatedLEDDisplay(config)
    else:
        # Use real LED display
        from led_display import LEDDisplay
        print("🔴 Production Mode: Using real LED Matrix")
        return LEDDisplay(config)
