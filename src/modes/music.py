"""
Music Mode - Display Spotify album art
"""

import logging
import time
from PIL import Image, ImageDraw, ImageFont
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor


class MusicMode:
    """Music mode - displays Spotify album artwork"""

    def __init__(self, display, spotify_client, config):
        """
        Initialize music mode

        Args:
            display: LEDDisplay instance
            spotify_client: SpotifyClient instance
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.spotify = spotify_client
        self.config = config
        self.image_processor = ImageProcessor(config.get('image_processing', {}))

        self.current_track_id = None
        self.last_update = 0
        self.update_interval = 5  # Check every 5 seconds
        self.first_update = True  # Flag for first update

        # Display settings
        self.show_track_info = config.get('advanced', {}).get('show_track_info', True)
        self.track_info_duration = config.get('advanced', {}).get('track_info_duration', 5)

        self.logger.info("Music mode initialized")

    def update(self):
        """Update music display"""
        try:
            # Rate limiting (but skip on first update)
            current_time = time.time()
            if not self.first_update and current_time - self.last_update < self.update_interval:
                time.sleep(1)
                return

            self.last_update = current_time

            # Get current track
            # spotify_client now returns cached track during rate limiting,
            # so we always get useful data (either fresh or cached)
            track_info = self.spotify.get_current_track(force=self.first_update)
            self.first_update = False  # Clear flag after first update

            if not track_info:
                # Spotify explicitly says nothing is playing (not rate limited)
                self.logger.debug("No track currently playing")
                self._display_placeholder()
                self.current_track_id = None
                time.sleep(2)
                return

            # Check if track changed
            if track_info['track_id'] != self.current_track_id:
                self.logger.info(f"Track changed: {track_info['artist_name']} - {track_info['track_name']}")
                self.current_track_id = track_info['track_id']

                # Display album art and keep showing it
                self._display_album_art(track_info)

            # Track is still playing - just sleep and check again later
            # The album art stays on screen continuously (no need to redraw)
            time.sleep(1)

        except Exception as e:
            self.logger.error(f"Error in music mode update: {e}", exc_info=True)
            time.sleep(5)

    def _display_album_art(self, track_info):
        """
        Display album artwork

        Args:
            track_info: Track information dictionary
        """
        try:
            album_art_url = track_info.get('album_art_url')

            if not album_art_url:
                self._display_placeholder()
                return

            # Process and display album art
            display_size = self.display.get_size()
            processed_image = self.image_processor.process_album_art(
                album_art_url,
                size=display_size
            )

            if processed_image:
                self.display.display_image(processed_image)
                self.logger.debug(f"Displayed album art for: {track_info['track_name']}")
            else:
                self._display_placeholder()

        except Exception as e:
            self.logger.error(f"Error displaying album art: {e}")
            self._display_placeholder()

    def _display_track_info(self, track_info):
        """
        Display track information overlay

        Args:
            track_info: Track information dictionary
        """
        try:
            # Create a semi-transparent overlay with track info
            # For now, just log it - full implementation would use scrolling text
            info_text = f"{track_info['artist_name']} - {track_info['track_name']}"
            self.logger.info(f"Track info: {info_text}")

            # Could implement scrolling text here
            # self.display.scroll_text(info_text)

        except Exception as e:
            self.logger.error(f"Error displaying track info: {e}")

    def _display_placeholder(self):
        """Display placeholder when nothing is playing"""
        try:
            display_size = self.display.get_size()
            placeholder = self.image_processor.create_text_image(
                "No Music\nPlaying",
                display_size,
                color=(100, 100, 100)
            )
            self.display.display_image(placeholder)

        except Exception as e:
            self.logger.error(f"Error displaying placeholder: {e}")
            self.display.clear()
