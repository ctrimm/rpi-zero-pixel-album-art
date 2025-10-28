#!/usr/bin/env python3
"""
Raspberry Pi Spotify LED Matrix Display
Main application entry point
"""

import sys
import os
import signal
import time
import threading
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config_manager import ConfigManager
from spotify_client import SpotifyClient
from led_display import LEDDisplay
from web_server import WebServer
from modes.music import MusicMode
from modes.weather import WeatherMode
from modes.sports import SportsMode
from modes.clock import ClockMode
from modes.pipes import PipesMode
from modes.dvd_logo import DVDLogoMode
from modes.weather_on_the_8s import WeatherOnThe8sMode


class SpotifyDisplayApp:
    """Main application orchestrator"""

    def __init__(self, config_path='config.json'):
        """Initialize the application"""
        # Load configuration
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config

        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Spotify LED Matrix Display...")

        # Initialize components
        self.display = None
        self.spotify = None
        self.web_server = None
        self.modes = {}

        # Application state
        self.current_mode = self.config['modes']['default']
        self.running = False
        self.mode_thread = None
        self.manual_mode = False  # Track if user manually selected a mode
        self.manual_mode_time = 0  # Time of last manual mode change

    def _setup_logging(self):
        """Configure application logging"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', '/var/log/spotify-display.log')

        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except:
                log_file = 'spotify-display.log'  # Fallback to current dir

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def initialize(self):
        """Initialize all components"""
        try:
            # Initialize LED display (auto-detects simulator vs real hardware)
            self.logger.info("Initializing LED display...")

            # Check if we should use simulator
            import os
            if os.environ.get('LED_SIMULATOR', '').lower() in ('1', 'true', 'yes'):
                from led_simulator import SimulatedLEDDisplay
                self.display = SimulatedLEDDisplay(self.config['display'])
            else:
                self.display = LEDDisplay(self.config['display'])

            # Initialize Spotify client
            self.logger.info("Initializing Spotify client...")
            self.spotify = SpotifyClient(self.config['spotify'])

            # Initialize display modes
            self.logger.info("Initializing display modes...")
            self.modes = {
                'music': MusicMode(self.display, self.spotify, self.config),
                'weather': WeatherMode(self.display, self.config),
                'sports': SportsMode(self.display, self.config),
                'clock': ClockMode(self.display, self.config),
                'pipes': PipesMode(self.display, self.config),
                'dvd_logo': DVDLogoMode(self.display, self.config)
            }

            # Initialize Weather on the 8s (special override mode)
            self.weather_on_8s = WeatherOnThe8sMode(self.display, self.config)
            if self.weather_on_8s.enabled:
                self.logger.info("🌤️ Weather on the 8s enabled! Will show at :08, :18, :28, :38, :48, :58")

            # Initialize web server
            if self.config.get('web_server', {}).get('enabled', True):
                self.logger.info("Initializing web server...")
                self.web_server = WebServer(
                    self.config['web_server'],
                    self
                )

            self.logger.info("Initialization complete!")
            return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    def start(self):
        """Start the application"""
        if not self.initialize():
            self.logger.error("Failed to initialize. Exiting.")
            return False

        self.running = True

        # Start web server in separate thread
        if self.web_server:
            web_thread = threading.Thread(target=self.web_server.start, daemon=True)
            web_thread.start()
            self.logger.info(f"Web interface available at http://0.0.0.0:{self.config['web_server']['port']}")

        # Start main display loop in background thread
        self.mode_thread = threading.Thread(target=self._run_display_loop, daemon=True)
        self.mode_thread.start()

        self.logger.info("Application started successfully!")

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Check if we're using the simulator (needs main thread for tkinter on macOS)
        from led_simulator import SimulatedLEDDisplay
        if isinstance(self.display, SimulatedLEDDisplay):
            self.logger.info("🖥️  Starting simulator GUI on main thread (required for macOS)")
            # Run tkinter mainloop on main thread (blocking)
            # This is required for macOS - background threads run the app logic
            try:
                self.display.mainloop()
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
        else:
            # Real hardware - keep main thread alive
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")

        return True

    def _run_display_loop(self):
        """Main display loop - runs in background thread"""
        self.logger.info("Starting display loop...")

        # Give Spotify client time to initialize and check playback state
        time.sleep(2)

        while self.running:
            try:
                # PRIORITY 1: Check if Weather on the 8s should activate
                # This overrides all other modes during its display time
                if self.weather_on_8s and self.weather_on_8s.enabled:
                    if self.weather_on_8s.update():
                        # Weather on 8s is active and handled the update
                        time.sleep(1)
                        continue

                # PRIORITY 2: Check if we should auto-switch modes
                if self.config['modes'].get('auto_switch', True):
                    self._check_auto_mode_switch()

                # PRIORITY 3: Get current mode handler
                mode_handler = self.modes.get(self.current_mode)

                if mode_handler:
                    # Update the current mode
                    mode_handler.update()
                else:
                    self.logger.warning(f"Unknown mode: {self.current_mode}")
                    time.sleep(5)

            except Exception as e:
                self.logger.error(f"Error in display loop: {e}", exc_info=True)
                time.sleep(5)

    def _check_auto_mode_switch(self):
        """Check if mode should be automatically switched"""
        from datetime import datetime

        current_time = datetime.now().strftime('%H:%M')
        schedule = self.config['modes'].get('schedule', {})

        # Check music mode - switch if Spotify is playing
        music_config = schedule.get('music', {})
        if music_config.get('enabled') and music_config.get('auto'):
            if self.spotify.is_playing():
                if self.current_mode != 'music':
                    self.logger.info("Auto-switching to music mode (Spotify playing)")
                    self.switch_mode('music', manual=False)
                    self.manual_mode = False  # Clear manual mode when auto-switching
                return  # Stay in music mode, don't check other modes

        # Check time-based schedules
        for mode_name, mode_config in schedule.items():
            if not mode_config.get('enabled'):
                continue

            time_ranges = mode_config.get('times', [])
            for time_range in time_ranges:
                if '-' in time_range:
                    start, end = time_range.split('-')
                    if start <= current_time <= end:
                        if self.current_mode != mode_name:
                            self.logger.info(f"Auto-switching to {mode_name} mode (scheduled)")
                            self.switch_mode(mode_name, manual=False)
                            self.manual_mode = False  # Clear manual mode when auto-switching
                        return

        # Skip fallback logic if user manually selected a mode
        if self.manual_mode:
            return

        # Fall back to clock ONLY if music is not playing
        # This prevents switching away from music mode during brief API check gaps
        clock_config = schedule.get('clock', {})
        if clock_config.get('fallback'):
            # Only switch to clock if we're not in music mode OR music has actually stopped
            if self.current_mode == 'music' and not self.spotify.is_playing():
                self.logger.info("Music stopped - switching to clock mode (fallback)")
                self.switch_mode('clock', manual=False)
            elif self.current_mode != 'clock' and self.current_mode != 'music':
                self.logger.info("Switching to clock mode (fallback)")
                self.switch_mode('clock', manual=False)

    def switch_mode(self, mode_name, manual=True):
        """
        Switch to a different display mode

        Args:
            mode_name: Name of the mode to switch to
            manual: True if user manually selected this mode, False if auto-switched
        """
        if mode_name in self.modes:
            self.logger.info(f"Switching to {mode_name} mode")

            # Reset music mode's display tracker when leaving music mode
            # This ensures album art is redrawn when we return
            if self.current_mode == 'music' and mode_name != 'music':
                music_mode = self.modes.get('music')
                if music_mode and hasattr(music_mode, 'last_displayed_track_id'):
                    music_mode.last_displayed_track_id = None

            self.current_mode = mode_name

            # Set manual mode flag to prevent auto-switching from overriding
            if manual:
                self.manual_mode = True
                self.manual_mode_time = time.time()
                self.logger.debug(f"Manual mode activated for {mode_name}")

            # Clear display for new mode
            self.display.clear()
            return True
        else:
            self.logger.warning(f"Unknown mode: {mode_name}")
            return False

    def get_status(self):
        """Get current application status"""
        spotify_status = self.spotify.get_current_track() if self.spotify else None

        return {
            'running': self.running,
            'current_mode': self.current_mode,
            'available_modes': list(self.modes.keys()),
            'brightness': self.config['display']['brightness'],
            'spotify_playing': self.spotify.is_playing() if self.spotify else False,
            'current_track': spotify_status,
            'uptime': time.time()  # Could track actual uptime
        }

    def set_brightness(self, brightness):
        """Set display brightness (0-100)"""
        brightness = max(0, min(100, brightness))
        self.config['display']['brightness'] = brightness
        if self.display:
            self.display.set_brightness(brightness)
        self.logger.info(f"Brightness set to {brightness}")

    def update_config(self, new_config):
        """
        Update configuration and apply changes live

        Args:
            new_config: New configuration dictionary

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Update configuration via config manager
            if not self.config_manager.update_config(new_config):
                return False

            # Reload configuration reference
            self.config = self.config_manager.config

            # Apply configuration changes without restart
            self.logger.info("Applying configuration changes...")

            # Update display brightness if changed
            if 'display' in new_config and 'brightness' in new_config['display']:
                self.set_brightness(new_config['display']['brightness'])

            # Update Spotify settings if needed
            if 'spotify' in new_config and self.spotify:
                # Spotify client would need to be reinitialized for some changes
                # For now, just log that a restart may be needed
                self.logger.info("Spotify configuration changed - some changes may require restart")

            # Update mode if changed
            if 'modes' in new_config and 'default' in new_config['modes']:
                new_default = new_config['modes']['default']
                if new_default != self.current_mode and new_default in self.modes:
                    self.switch_mode(new_default)

            self.logger.info("Configuration changes applied successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error updating configuration: {e}", exc_info=True)
            return False

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()

    def stop(self):
        """Stop the application gracefully"""
        self.logger.info("Stopping application...")
        self.running = False

        # Clear display
        if self.display:
            self.display.clear()

        # Stop web server
        if self.web_server:
            self.web_server.stop()

        self.logger.info("Application stopped")
        sys.exit(0)


def main():
    """Application entry point"""
    print("""
    ╔══════════════════════════════════════════╗
    ║  Raspberry Pi Spotify LED Matrix Display ║
    ║  Standalone Network Version              ║
    ╚══════════════════════════════════════════╝
    """)

    # Check for config file
    config_path = 'config.json'
    if not os.path.exists(config_path):
        print(f"\n❌ Error: Configuration file '{config_path}' not found!")
        print("Please copy config.example.json to config.json and configure your settings.")
        print("\nQuick setup:")
        print("  1. cp config.example.json config.json")
        print("  2. nano config.json  # Add your Spotify API credentials")
        print("  3. python3 src/main.py\n")
        sys.exit(1)

    # Create and start application
    app = SpotifyDisplayApp(config_path)

    try:
        app.start()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
