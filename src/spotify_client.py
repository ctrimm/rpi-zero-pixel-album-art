"""
Spotify API Client
Handles authentication and track information retrieval
"""

import os
import logging
import time
from pathlib import Path
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler


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
        self.cache_path = Path.home() / '.cache' / 'spotify-display'

        # Cache the last known track info
        self.cached_track_info = None

        # Ensure cache directory exists
        self.cache_path.mkdir(parents=True, exist_ok=True)

        self._initialize_client()

    def _initialize_client(self):
        """Initialize Spotipy client with OAuth"""
        try:
            cache_handler = CacheFileHandler(
                cache_path=str(self.cache_path / 'spotify_token_cache')
            )

            auth_manager = SpotifyOAuth(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret'],
                redirect_uri=self.config['redirect_uri'],
                scope=self.config.get('scope', 'user-read-currently-playing user-read-playback-state'),
                cache_handler=cache_handler,
                open_browser=True
            )

            self.sp = spotipy.Spotify(auth_manager=auth_manager)

            # Test the connection
            self.sp.current_user()
            self.logger.info("Spotify client initialized successfully")

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
            cached_track_info: If rate limiting prevents new query
        """
        try:
            # Check if we should update (rate limiting)
            current_time = time.time()
            if not force and current_time - self.last_update < self.update_interval:
                # Return cached track info instead of None during rate limiting
                # This allows the caller to know we're rate limited, not that music stopped
                return self.cached_track_info

            self.last_update = current_time

            # Get current playback
            current = self.sp.current_user_playing_track()

            if not current:
                # No playback device active - clear cache and return None
                self.cached_track_info = None
                self.current_track_id = None
                return None

            # IMPORTANT: Don't clear cache when paused!
            # Return the track info with is_playing=False so we can keep showing the album art
            track = current.get('item')
            if not track:
                self.cached_track_info = None
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

            return track_info

        except Exception as e:
            self.logger.error(f"Error getting current track: {e}")
            # On error, return cached info if available
            return self.cached_track_info

    def _get_best_album_art(self, images):
        """
        Get the best quality album art URL

        Args:
            images: List of image objects from Spotify API

        Returns:
            str: URL of the highest resolution image
        """
        if not images:
            return None

        # Spotify returns images sorted by size (largest first)
        # For a 64x64 display, we can use the smallest available
        # But we'll use the largest to maintain quality during processing
        return images[0]['url']

    def is_playing(self):
        """
        Check if Spotify is currently playing

        Returns:
            bool: True if playing, False otherwise
        """
        try:
            current = self.sp.current_user_playing_track()
            return current is not None and current.get('is_playing', False)
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
