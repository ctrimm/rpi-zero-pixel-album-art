"""
Music Mode - Display Spotify album art, with the song and artist on top

The artist (cyan) and song title (white) sit on a darkened band along the
bottom of the album art. Names too long for the 64px panel scroll: they hold
at the start, slide until the end is visible, hold, and jump back - so the
text is always readable. Turn the overlay off with advanced.show_track_info
(admin panel: General > Now playing).
"""

import logging
import time
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor
from utils.runtime import mode_sleep, wait_for_frame

ARTIST_COLOR = (0, 230, 255)
TITLE_COLOR = (255, 255, 255)
BAND_HEIGHT = 22          # two 11px lines
BAND_DARKEN = 0.25        # album art brightness behind the text
SCROLL_SPEED = 25         # pixels per second
SCROLL_HOLD = 1.5         # seconds to pause at each end
FRAME_INTERVAL = 0.04     # 25 fps while text is scrolling


def _load_font():
    """A crisp bitmap font (no anti-aliasing, which smears on LEDs)."""
    try:
        return ImageFont.load_default_imagefont()   # Pillow >= 10.1
    except AttributeError:
        return ImageFont.load_default()


class Marquee:
    """Horizontal position of one line of text over time (ping-pong scroll)."""

    def __init__(self, text_width, view_width, speed=SCROLL_SPEED, hold=SCROLL_HOLD):
        self.text_width = text_width
        self.view_width = view_width
        self.travel = max(0, text_width - (view_width - 2))   # 1px margin each side
        self.speed = speed
        self.hold = hold
        self.start = time.monotonic()

    @property
    def scrolls(self):
        return self.travel > 0

    def x(self, now=None):
        if not self.scrolls:
            return (self.view_width - self.text_width) // 2   # centred
        slide = self.travel / self.speed
        t = ((time.monotonic() if now is None else now) - self.start) % (self.hold + slide + self.hold)
        if t < self.hold:
            offset = 0
        elif t < self.hold + slide:
            offset = (t - self.hold) * self.speed
        else:
            offset = self.travel
        return 1 - int(offset)


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
        self.font = _load_font()

        self.current_track_id = None
        self.last_displayed_track_id = None  # Track what's currently displayed
        self.first_update = True  # Flag for first update
        self.last_frame = None  # The exact image we last pushed to the display

        # Current album art and text overlay
        self._art = None          # processed album art (no text)
        self._base = None         # art with the bottom band darkened
        self._lines = []          # [(mask image, colour, y, Marquee)]
        self._text_key = None
        self._frame_clock = {}

        self.show_track_info = True
        self.configure(config)
        self.logger.info("Music mode initialized")

    def configure(self, config):
        """Apply settings (called again when they change in the admin panel)."""
        self.config = config
        show = bool(config.get('advanced', {}).get('show_track_info', True))
        if show != self.show_track_info:
            self.show_track_info = show
            self._text_key = None     # rebuild the overlay
            self.last_frame = None
        self.show_track_info = show

    def update(self):
        """Update music display"""
        try:
            if self.spotify is None:
                self._show_message("Spotify\nnot linked", (200, 120, 60))
                self.last_displayed_track_id = None
                mode_sleep(2)
                return

            # The Spotify client owns the real API cadence (adaptive polling)
            # and returns cached data between polls, so asking often is cheap.
            track_info = self.spotify.get_current_track(force=self.first_update)
            self.first_update = False

            if not track_info:
                self._display_placeholder()
                self.current_track_id = None
                self.last_displayed_track_id = None
                self._art = None
                mode_sleep(2)
                return

            if track_info['track_id'] != self.current_track_id:
                self.logger.info(f"Track changed: {track_info['artist_name']} - {track_info['track_name']}")
                self.current_track_id = track_info['track_id']

            # New track (or we just came back to music mode): load the art
            if track_info['track_id'] != self.last_displayed_track_id:
                self._load_album_art(track_info)
                self.last_displayed_track_id = track_info['track_id']

            if self._art is None:
                mode_sleep(1)
                return

            self._prepare_overlay(track_info)

            if self._is_animating():
                # Scrolling text: draw a frame at a steady 25 fps
                if wait_for_frame(self._frame_clock, FRAME_INTERVAL):
                    self._push(self._compose())
            else:
                # Static: draw once, then only if something else drew over it
                # (test pattern, clear, Weather on the 8s...)
                if self.last_frame is None or self.display.current_image is not self.last_frame:
                    self._push(self._compose())
                mode_sleep(1)

        except Exception as e:
            self.logger.error(f"Error in music mode update: {e}", exc_info=True)
            mode_sleep(5)

    # ── Album art ─────────────────────────────────────────────────────────

    def _load_album_art(self, track_info):
        self._art = None
        self._base = None
        self._text_key = None
        self.last_frame = None
        album_art_url = track_info.get('album_art_url')
        if not album_art_url:
            self._display_placeholder()
            return
        try:
            art = self.image_processor.process_album_art(album_art_url, size=self.display.get_size())
        except Exception as e:
            self.logger.error(f"Error displaying album art: {e}")
            art = None
        if art is None:
            self._display_placeholder()
            return
        self._art = art.convert('RGB')
        width, height = self._art.size
        band_top = height - BAND_HEIGHT
        base = self._art.copy()
        band = base.crop((0, band_top, width, height))
        base.paste(ImageEnhance.Brightness(band).enhance(BAND_DARKEN), (0, band_top))
        self._base = base

    # ── Text overlay ──────────────────────────────────────────────────────

    def _prepare_overlay(self, track_info):
        """(Re)build the text strips when the song/artist or setting changes."""
        key = (track_info.get('artist_name'), track_info.get('track_name'), self.show_track_info)
        if key == self._text_key:
            return
        self._text_key = key
        self._lines = []
        self.last_frame = None
        if not self.show_track_info:
            return
        width, height = self.display.get_size()
        band_top = height - BAND_HEIGHT
        for text, color, y in (
            (track_info.get('artist_name') or '', ARTIST_COLOR, band_top),
            (track_info.get('track_name') or '', TITLE_COLOR, band_top + 11),
        ):
            if not text:
                continue
            text_width = int(self.font.getlength(text)) if hasattr(self.font, 'getlength') \
                else self.font.getbbox(text)[2]
            mask = Image.new('L', (max(1, text_width), 11))
            ImageDraw.Draw(mask).text((0, 0), text, font=self.font, fill=255)
            self._lines.append((mask, color, y, Marquee(text_width, width)))

    def _is_animating(self):
        return any(line[3].scrolls for line in self._lines)

    def _compose(self):
        if not self.show_track_info or not self._lines:
            return self._art
        frame = self._base.copy()
        now = time.monotonic()
        for mask, color, y, marquee in self._lines:
            frame.paste(color, (marquee.x(now), y), mask)
        return frame

    def _push(self, frame):
        self.display.display_image(frame)
        self.last_frame = self.display.current_image

    # ── Messages ──────────────────────────────────────────────────────────

    def _display_placeholder(self):
        """Display placeholder when nothing is playing"""
        self._show_message("No Music\nPlaying", (100, 100, 100))

    def _show_message(self, text, color):
        """Show a centred status message"""
        try:
            # Already on screen? Don't re-render and re-push the same frame.
            if (getattr(self, '_message_key', None) == (text, color)
                    and self.display.current_image is getattr(self, '_message_frame', None)):
                return
            display_size = self.display.get_size()
            placeholder = self.image_processor.create_text_image(
                text,
                display_size,
                color=color
            )
            self.display.display_image(placeholder)
            self.last_frame = None
            self._message_key = (text, color)
            self._message_frame = self.display.current_image

        except Exception as e:
            self.logger.error(f"Error displaying placeholder: {e}")
            self.display.clear()
