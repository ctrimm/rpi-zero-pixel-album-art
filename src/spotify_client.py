"""
Spotify API Client
Handles authentication and track information retrieval
"""

import os
import sys
import logging
import time
import webbrowser
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler

from utils.runtime import cache_dir

DEFAULT_SCOPE = 'user-read-currently-playing user-read-playback-state'


class SpotifyNotAuthorizedError(RuntimeError):
    """Raised when there is no cached Spotify token and we can't prompt for one."""


def browser_available():
    """True if a local GUI web browser can be opened for the OAuth flow.

    On a headless Pi there is no browser; spotipy would then sit on a local
    callback server forever without printing the login URL. Detect that so we
    can use the copy/paste flow instead.
    """
    if sys.platform.startswith('linux') and not (
            os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return False
    try:
        webbrowser.get()
        return True
    except webbrowser.Error:
        return False


def make_auth_manager(spotify_config, open_browser=None):
    """Build the SpotifyOAuth manager shared by the app and spotify_auth.py."""
    if open_browser is None:
        open_browser = browser_available()
    token_path = spotify_config.get('token_cache_path')
    if token_path:
        from pathlib import Path
        Path(token_path).parent.mkdir(parents=True, exist_ok=True)
    else:
        token_dir = cache_dir()
        token_dir.mkdir(parents=True, exist_ok=True)
        token_path = token_dir / 'spotify_token_cache'
    cache_handler = CacheFileHandler(cache_path=str(token_path))
    return SpotifyOAuth(
        client_id=spotify_config['client_id'],
        client_secret=spotify_config['client_secret'],
        redirect_uri=spotify_config.get('redirect_uri', 'http://127.0.0.1:8888/callback'),
        scope=spotify_config.get('scope', DEFAULT_SCOPE),
        cache_handler=cache_handler,
        open_browser=open_browser,
    )


class SpotifyClient:
    """Spotify API client for retrieving currently playing track information"""

    def __init__(self, config):
        """
        Initialize Spotify client

        Args:
            config: Spotify configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.sp = None
        self.current_track_id = None
        self.last_update = 0
        self.update_interval = config.get('update_interval', 10)

        # Adaptive polling.
        # Spotify's Web API has no push/webhook for the currently-playing track,
        # so we have to poll - but we can be smart about *when*. Each poll returns
        # progress_ms/duration_ms, so we can predict when the current track will
        # end naturally and poll tightly only around that transition, slow right
        # down while paused or idle, and keep a modest ceiling mid-track to still
        # catch manual skips. All intervals are seconds and overridable via config.
        self.poll_max_interval = config.get('poll_max_interval', self.update_interval)  # mid-song skip-detection ceiling
        self.poll_paused_interval = config.get('poll_paused_interval', 20)              # while paused
        self.poll_idle_interval = config.get('poll_idle_interval', 30)                  # while nothing is playing
        self.poll_transition_interval = config.get('poll_transition_interval', 2)       # tight poll near a track change
        self.poll_transition_window = config.get('poll_transition_window', 12)          # start tight polling this long before predicted end
        self.poll_error_interval = config.get('poll_error_interval', 15)               # back off after API errors
        self.poll_min_interval = config.get('poll_min_interval', 1)                    # never poll faster than this
        self.next_poll_time = 0  # wall-clock time when the next API poll is allowed

        # Cache the last known track info
        self.cached_track_info = None

        self._initialize_client()

    def _initialize_client(self):
        """Initialize Spotipy client with OAuth"""
        try:
            auth_manager = make_auth_manager(self.config)

            # Running as a service (no terminal): we can't do the interactive
            # OAuth login, and trying would block or crash. Fail fast with a
            # clear message instead; the app keeps running without Spotify and
            # retries periodically, so running spotify_auth.py fixes it live.
            if auth_manager.cache_handler.get_cached_token() is None and not sys.stdin.isatty():
                raise SpotifyNotAuthorizedError(
                    "No Spotify login found. Run 'venv/bin/python src/spotify_auth.py' "
                    "once (as your normal user, not sudo) to sign in."
                )

            self.sp = spotipy.Spotify(auth_manager=auth_manager)

            # Test the connection
            self.sp.current_user()
            self.logger.info("Spotify client initialized successfully")

        except SpotifyNotAuthorizedError:
            raise  # Expected before first login; the app logs a friendly warning
        except Exception as e:
            self.logger.error(f"Failed to initialize Spotify client: {e}")
            raise

    def get_current_track(self, force=False):
        """
        Get currently playing track information

        Args:
            force: If True, bypass rate limiting

        Returns:
            dict: Track information if playing
            None: If nothing is playing (from Spotify API)
            cached_track_info: If adaptive polling prevents a new query
        """
        try:
            # Adaptive rate limiting: only hit the API when the schedule says so.
            current_time = time.time()
            if not force and current_time < self.next_poll_time:
                # Return cached track info instead of None while we're between
                # polls, so the caller can tell "no new data yet" apart from
                # "music stopped".
                return self.cached_track_info

            self.last_update = current_time

            # Get current playback
            current = self.sp.current_user_playing_track()

            if not current:
                # No playback device active - clear cache and return None
                self.cached_track_info = None
                self.current_track_id = None
                self._schedule_next_poll(None)
                return None

            # IMPORTANT: Don't clear cache when paused!
            # Return the track info with is_playing=False so we can keep showing the album art
            track = current.get('item')
            if not track:
                self.cached_track_info = None
                self._schedule_next_poll(None)
                return None

            is_playing = current.get('is_playing', False)

            # Extract track information (even if paused!)
            track_info = {
                'track_id': track['id'],
                'track_name': track['name'],
                'artist_name': track['artists'][0]['name'] if track['artists'] else 'Unknown Artist',
                'album_name': track['album']['name'],
                'album_art_url': self._get_best_album_art(track['album']['images']),
                'duration_ms': track['duration_ms'],
                'progress_ms': current.get('progress_ms', 0),
                'is_playing': is_playing
            }

            # Update current track ID and cache
            if self.current_track_id != track_info['track_id']:
                self.logger.info(f"Now playing: {track_info['artist_name']} - {track_info['track_name']}")
                self.current_track_id = track_info['track_id']

            # Always update cache with latest info
            self.cached_track_info = track_info

            # Decide when to poll next based on this track's state
            self._schedule_next_poll(track_info)

            return track_info

        except Exception as e:
            self.logger.error(f"Error getting current track: {e}")
            # Back off before retrying so a failing API doesn't get hammered,
            # and return cached info if available.
            self._schedule_next_poll(None, error=True)
            return self.cached_track_info

    def _schedule_next_poll(self, track_info, error=False):
        """
        Compute the wall-clock time of the next allowed API poll.

        The goal is to poll as little as possible while keeping the album art
        responsive: tight around a track change, relaxed while paused/idle, and
        capped mid-track so a manual skip still updates within a bounded delay.

        Args:
            track_info: The track info just fetched (or None if nothing playing)
            error: True if the last poll raised, so we back off before retrying
        """
        now = time.time()

        if error:
            delay = self.poll_error_interval
        elif not track_info:
            # Nothing playing - no urgency, check back occasionally.
            delay = self.poll_idle_interval
        elif not track_info.get('is_playing'):
            # Paused - progress is frozen, so there's no transition to predict.
            delay = self.poll_paused_interval
        else:
            duration = track_info.get('duration_ms') or 0
            progress = track_info.get('progress_ms') or 0
            remaining = max(0.0, (duration - progress) / 1000.0)

            if remaining <= self.poll_transition_window:
                # Near (or past) the end - poll tightly to catch the new track.
                delay = self.poll_transition_interval
            else:
                # Sleep until just before the predicted end, but never longer
                # than the ceiling so a manual skip is still caught reasonably.
                delay = min(self.poll_max_interval, remaining - self.poll_transition_window)

        delay = max(self.poll_min_interval, delay)
        self.next_poll_time = now + delay

    def _get_best_album_art(self, images, min_size=128):
        """
        Pick the album art URL to download.

        Spotify usually offers 640px, 300px and 64px versions. The panel is
        64x64, so the 640px one (~100-200 KB) is wasted bandwidth and decode
        time on a Pi Zero. Take the smallest image that's still at least
        min_size (2x the panel) so downscaling stays sharp - normally 300px.

        Args:
            images: List of image objects from Spotify API

        Returns:
            str: URL of the chosen image, or None
        """
        if not images:
            return None
        sized = [img for img in images if img.get('width') and img.get('url')]
        big_enough = [img for img in sized if img['width'] >= min_size]
        if big_enough:
            return min(big_enough, key=lambda img: img['width'])['url']
        if sized:
            return max(sized, key=lambda img: img['width'])['url']
        # No size info: Spotify lists largest first
        return images[0].get('url')

    def is_playing(self):
        """
        Check if Spotify is currently playing

        Reuses the rate-limited get_current_track() path so this can be called
        every display-loop iteration (the auto mode switcher does) without firing
        a fresh Spotify API request each time, which would hammer the API,
        stutter the screensaver animations, and risk hitting rate limits.

        Returns:
            bool: True if playing, False otherwise
        """
        try:
            track = self.get_current_track()
            return bool(track and track.get('is_playing', False))
        except Exception as e:
            self.logger.error(f"Error checking playback status: {e}")
            return False

    def get_playback_state(self):
        """
        Get detailed playback state

        Returns:
            dict: Playback state information
        """
        try:
            playback = self.sp.current_playback()
            if not playback:
                return None

            return {
                'is_playing': playback.get('is_playing', False),
                'shuffle_state': playback.get('shuffle_state', False),
                'repeat_state': playback.get('repeat_state', 'off'),
                'volume': playback.get('device', {}).get('volume_percent', 0),
                'device_name': playback.get('device', {}).get('name', 'Unknown')
            }

        except Exception as e:
            self.logger.error(f"Error getting playback state: {e}")
            return None

    def search_track(self, query):
        """
        Search for tracks

        Args:
            query: Search query string

        Returns:
            list: List of track results
        """
        try:
            results = self.sp.search(q=query, type='track', limit=10)
            tracks = []

            for item in results['tracks']['items']:
                tracks.append({
                    'track_id': item['id'],
                    'track_name': item['name'],
                    'artist_name': item['artists'][0]['name'],
                    'album_name': item['album']['name'],
                    'album_art_url': self._get_best_album_art(item['album']['images'])
                })

            return tracks

        except Exception as e:
            self.logger.error(f"Error searching tracks: {e}")
            return []

    def refresh_token(self):
        """Manually refresh the OAuth token"""
        try:
            if self.sp and self.sp.auth_manager:
                self.sp.auth_manager.get_access_token(as_dict=False, check_cache=False)
                self.logger.info("Spotify token refreshed")
                return True
        except Exception as e:
            self.logger.error(f"Error refreshing token: {e}")
            return False
