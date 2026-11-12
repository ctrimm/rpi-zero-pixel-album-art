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
from utils.runtime import wake_modes, reset_wake
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
        self.using_simulator = False  # True when running the dev GUI simulator
        self.start_time = time.time()  # For uptime reporting
        self.weather_on_8s = None
        self.spotify_error = None  # Why Spotify isn't connected (shown in the UI)
        self._last_spotify_attempt = 0
        self._spotify_retry_interval = 60
        self._was_playing = False  # For detecting "music just started"
        self.hold_until = 0  # Pause mode updates (e.g. while a test pattern shows)

    def _setup_logging(self):
        """Configure application logging"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'), logging.INFO)
        log_file = log_config.get('file', '/var/log/spotify-display.log')

        # Always log to stdout (captured by systemd/journald).
        handlers = [logging.StreamHandler(sys.stdout)]

        # Add a file handler only if the path is actually writable. The default
        # /var/log location is not writable by a non-root service user, and the
        # directory already exists, so we cannot rely on the makedirs fallback -
        # creating the FileHandler would raise PermissionError and crash the app
        # before logging is even initialised. Fall back to the working directory,
        # and if that also fails, log to stdout only.
        file_handler = self._make_file_handler(log_file)
        if file_handler is None and os.path.basename(log_file) != 'spotify-display.log':
            file_handler = self._make_file_handler('spotify-display.log')
        if file_handler is not None:
            handlers.insert(0, file_handler)

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

        if file_handler is None:
            logging.getLogger(__name__).warning(
                "File logging disabled (no writable log file at %s); using stdout only",
                log_file
            )

    def _make_file_handler(self, log_file):
        """Create a logging FileHandler, or return None if it isn't writable."""
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            return logging.FileHandler(log_file)
        except OSError:
            return None

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
                self.using_simulator = True
            else:
                self.display = LEDDisplay(self.config['display'])
                self.using_simulator = False

            # Initialize Spotify client. A failure here (no login yet, bad
            # credentials, no network) must not take the whole display down:
            # clocks, weather and screensavers still work, and we retry
            # periodically so signing in later fixes it without a restart.
            self._connect_spotify()

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

    def _connect_spotify(self):
        """Try to (re)connect to Spotify. Returns True on success."""
        self._last_spotify_attempt = time.time()
        self.logger.info("Initializing Spotify client...")
        try:
            self.spotify = SpotifyClient(self.config['spotify'])
            self.spotify_error = None
        except Exception as e:
            self.spotify = None
            self.spotify_error = str(e)
            self.logger.warning(
                f"Spotify unavailable ({e}). Other modes still work; "
                f"retrying every {self._spotify_retry_interval}s."
            )
        music = self.modes.get('music')
        if music:
            music.spotify = self.spotify
        return self.spotify is not None

    def _ensure_spotify(self):
        """Periodically retry the Spotify connection if it isn't up."""
        if self.spotify is None and time.time() - self._last_spotify_attempt >= self._spotify_retry_interval:
            if self._connect_spotify():
                self.logger.info("Spotify connected")

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

        # Check if we're using the simulator (needs main thread for tkinter on macOS).
        # Use a flag set during initialize() rather than importing led_simulator here,
        # because importing it pulls in tkinter which is typically absent on a headless Pi.
        if self.using_simulator:
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
                # Re-arm the interruptible sleep used by modes (a mode switch
                # wakes it so the new mode renders immediately).
                reset_wake()

                # Something (e.g. the test pattern) asked to hold the screen
                if time.time() < self.hold_until:
                    time.sleep(0.1)
                    continue

                self._ensure_spotify()

                # PRIORITY 1: Check if Weather on the 8s should activate
                # This overrides all other modes during its display time
                if self.weather_on_8s and self.weather_on_8s.enabled:
                    if self.weather_on_8s.update():
                        # Weather on the 8s owns the screen; ~10 fps for its
                        # animated icons (frames are only pushed when they change)
                        time.sleep(0.05)
                        continue

                # PRIORITY 2: Check if we should auto-switch modes
                if self.config['modes'].get('auto_switch', True):
                    self._check_auto_mode_switch()

                # PRIORITY 3: Get current mode handler
                mode_handler = self.modes.get(self.current_mode)

                started = time.monotonic()
                if mode_handler:
                    # Update the current mode
                    mode_handler.update()
                else:
                    self.logger.warning(f"Unknown mode: {self.current_mode}")
                    time.sleep(5)

                # Floor sleep so a mode that returns instantly can't turn this
                # into a 100% CPU busy-wait. Modes normally pace themselves
                # (mode_sleep / wait_for_frame), so skip it when update()
                # already slept - that avoids a second wake-up per frame.
                if time.monotonic() - started < 0.002:
                    time.sleep(0.005)

            except Exception as e:
                self.logger.error(f"Error in display loop: {e}", exc_info=True)
                time.sleep(5)

    def _check_auto_mode_switch(self):
        """Check if mode should be automatically switched"""
        from datetime import datetime

        current_time = datetime.now().strftime('%H:%M')
        schedule = self.config['modes'].get('schedule', {})
        is_playing = bool(self.spotify and self.spotify.is_playing())
        music_just_started = is_playing and not self._was_playing
        self._was_playing = is_playing

        # Check music mode - switch if Spotify is playing.
        # A mode the user picked by hand wins over "music is playing", so you
        # can look at the clock or a screensaver mid-song. The one exception is
        # playback *starting* (stopped -> playing): that's a fresh signal that
        # the user wants album art, so it takes over and clears the manual pick.
        music_config = schedule.get('music', {})
        if music_config.get('enabled') and music_config.get('auto') and is_playing:
            if music_just_started or not self.manual_mode:
                if self.current_mode != 'music':
                    self.logger.info("Auto-switching to music mode (Spotify playing)")
                    self.switch_mode('music', manual=False)
                self.manual_mode = False
                return  # Stay in music mode, don't check other modes

        # Skip schedules and fallback if user manually selected a mode
        if self.manual_mode:
            return

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

        # Fall back to clock ONLY if music is not playing
        # This prevents switching away from music mode during brief API check gaps
        clock_config = schedule.get('clock', {})
        if clock_config.get('fallback'):
            # Only switch to clock if we're not in music mode OR music has actually stopped
            if self.current_mode == 'music' and not is_playing:
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
            self.hold_until = 0  # A mode switch ends any test-pattern hold

            # Set manual mode flag to prevent auto-switching from overriding
            if manual:
                self.manual_mode = True
                self.logger.debug(f"Manual mode activated for {mode_name}")

            # Clear display for new mode, and wake the display loop if the
            # previous mode is mid-sleep so the new one renders right away.
            self.display.clear()
            wake_modes()
            return True
        else:
            self.logger.warning(f"Unknown mode: {mode_name}")
            return False

    def show_test_pattern(self, seconds=5):
        """Show the colour-bar test pattern and keep it up for a few seconds."""
        self.hold_until = time.time() + seconds
        wake_modes()
        self.display.test_pattern()

    def clear_display(self, seconds=3):
        """Blank the panel briefly (modes resume afterwards)."""
        self.hold_until = time.time() + seconds
        wake_modes()
        self.display.clear()

    def get_status(self):
        """Get current application status"""
        spotify_status = self.spotify.get_current_track() if self.spotify else None

        return {
            'running': self.running,
            'current_mode': self.current_mode,
            'available_modes': list(self.modes.keys()),
            'brightness': self.config['display']['brightness'],
            'spotify_playing': self.spotify.is_playing() if self.spotify else False,
            'spotify_connected': self.spotify is not None,
            'spotify_error': self.spotify_error,
            'manual_mode': self.manual_mode,
            'current_track': spotify_status,
            'uptime': time.time() - self.start_time
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
            old_default = self.config.get('modes', {}).get('default')

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

            # Reconnect Spotify if its settings changed (or it isn't connected)
            if 'spotify' in new_config and (
                    self.spotify is None or new_config['spotify'] != getattr(self.spotify, 'config', None)):
                self.logger.info("Spotify configuration changed - reconnecting")
                self._connect_spotify()

            # Apply new admin credentials to the running web server
            if 'web_server' in new_config and self.web_server:
                self.web_server.update_credentials(self.config['web_server'])

            # Song/artist overlay on/off
            if self.modes.get('music'):
                self.modes['music'].configure(self.config)

            # Clock style/format changes
            self.modes['clock'] = ClockMode(self.display, self.config)

            # Weather on the 8s settings
            if 'weather_on_8s' in new_config:
                self.weather_on_8s = WeatherOnThe8sMode(self.display, self.config)

            # Switch to the default mode only if the default itself changed
            # (saving unrelated settings shouldn't yank the display around)
            if 'modes' in new_config and 'default' in new_config['modes']:
                new_default = new_config['modes']['default']
                if new_default != old_default and new_default != self.current_mode and new_default in self.modes:
                    self.switch_mode(new_default)

            # Make sure the currently showing mode redraws with new settings
            wake_modes()

            # Reinitialize weather mode if config changed
            if 'weather' in new_config:
                self.logger.info("Reinitializing weather mode with new configuration")
                from modes.weather import WeatherMode
                self.modes['weather'] = WeatherMode(self.display, self.config)

            # Reinitialize sports mode if config changed
            if 'sports' in new_config:
                self.logger.info("Reinitializing sports mode with new configuration")
                from modes.sports import SportsMode
                self.modes['sports'] = SportsMode(self.display, self.config)

            # Reinitialize screensavers if config changed
            if 'screensavers' in new_config:
                self.logger.info("Reinitializing screensaver modes with new configuration")
                from modes.pipes import PipesMode
                from modes.dvd_logo import DVDLogoMode
                self.modes['pipes'] = PipesMode(self.display, self.config)
                self.modes['dvd_logo'] = DVDLogoMode(self.display, self.config)

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
