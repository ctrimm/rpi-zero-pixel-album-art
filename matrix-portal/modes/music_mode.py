# music_mode.py — Spotify album art + track info for Matrix Portal 64x64
#
# Two operation modes:
#   1. With companion (COMPANION_URL set): fetches pre-processed 64x64 BMP from companion.
#      The companion handles OAuth and image resizing.
#   2. Without companion: calls Spotify API directly using a stored refresh token.
#      Album art is downloaded as JPEG and saved to /album_art.bmp via companion.
#      Without companion, only track/artist text is shown (no album art).

import displayio
import time
import gc
import os

from utils.display_helper import (
    make_text_label, center_label, load_bmp, COLORS, ScrollingLabel
)

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"

ART_PATH = "/album_art.bmp"

_BLANK_TRACK = {"title": "", "artist": "", "album": "", "art_url": ""}


class MusicMode:
    def __init__(self, display, network, companion_url="",
                 client_id="", client_secret="", refresh_token=""):
        self.display = display
        self.network = network
        self.companion_url = companion_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

        self._group = None
        self._art_grid = None
        self._artist_scroller = None
        self._title_scroller = None
        self._status_label = None

        self._access_token = None
        self._token_expiry = 0
        self._current_track_id = None
        self._last_update = 0
        self._update_interval = 10  # seconds

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self):
        gc.collect()
        self._group = displayio.Group()

        # Placeholder background (dark)
        from utils.display_helper import make_bitmap, make_palette, fill_bitmap
        bg_bmp = make_bitmap(64, 64, 2)
        bg_pal = make_palette([0x000000, 0x111111])
        fill_bitmap(bg_bmp, 1)
        self._group.append(displayio.TileGrid(bg_bmp, pixel_shader=bg_pal))

        # Status / "no music" label
        self._status_label = make_text_label("No music", color=COLORS["gray"], y=30)
        center_label(self._status_label, y=30)
        self._group.append(self._status_label)

        # Scrolling artist (below art area, y=50)
        self._artist_scroller = ScrollingLabel("", color=COLORS["cyan"], y=50, scale=1)
        self._group.append(self._artist_scroller.label)

        # Scrolling title (y=58)
        self._title_scroller = ScrollingLabel("", color=COLORS["white"], y=58, scale=1)
        self._group.append(self._title_scroller.label)

        self.display.root_group = self._group
        self._last_update = 0  # force immediate fetch

    def on_exit(self):
        self._group = None
        self._art_grid = None
        self._artist_scroller = None
        self._title_scroller = None
        self._status_label = None
        gc.collect()

    def update(self):
        now = time.monotonic()

        # Fetch track info periodically
        if now - self._last_update >= self._update_interval:
            self._last_update = now
            track = self._fetch_track()
            if track:
                self._render_track(track)
            else:
                self._show_status("No music")

        # Animate scrolling text every frame
        if self._artist_scroller:
            self._artist_scroller.update()
        if self._title_scroller:
            self._title_scroller.update()

    # ------------------------------------------------------------------
    # Track fetching
    # ------------------------------------------------------------------

    def _fetch_track(self):
        if self.companion_url:
            return self._fetch_from_companion()
        elif self.refresh_token:
            return self._fetch_from_spotify()
        return None

    def _fetch_from_companion(self):
        data = self.network.get_json(f"{self.companion_url}/api/matrix/track")
        if not data or not data.get("is_playing"):
            return None
        return {
            "id":     data.get("track_id", ""),
            "title":  data.get("title", ""),
            "artist": data.get("artist", ""),
            "art_url": data.get("art_url", ""),
        }

    def _fetch_from_spotify(self):
        token = self._get_access_token()
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}"}
        data = self.network.get_json(SPOTIFY_NOW_PLAYING_URL, headers=headers)
        if not data or data.get("currently_playing_type") != "track":
            return None
        item = data.get("item", {})
        if not item:
            return None
        artists = item.get("artists", [])
        artist = artists[0]["name"] if artists else "Unknown"
        images = item.get("album", {}).get("images", [])
        art_url = images[-1]["url"] if images else ""  # smallest image
        return {
            "id":     item.get("id", ""),
            "title":  item.get("name", ""),
            "artist": artist,
            "art_url": art_url,
        }

    def _get_access_token(self):
        import binascii
        now = time.monotonic()
        if self._access_token and now < self._token_expiry - 30:
            return self._access_token

        # Base64-encode client_id:client_secret
        creds = f"{self.client_id}:{self.client_secret}".encode()
        b64 = binascii.b2a_base64(creds).decode().strip()

        headers = {
            "Authorization": f"Basic {b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body = f"grant_type=refresh_token&refresh_token={self.refresh_token}"
        # Use requests directly for form-encoded POST
        try:
            resp = self.network.requests.post(
                SPOTIFY_TOKEN_URL,
                data=body,
                headers=headers,
            )
            data = resp.json()
            resp.close()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self._token_expiry = now + expires_in
            return self._access_token
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_track(self, track):
        track_id = track["id"]
        art_changed = track_id != self._current_track_id

        if art_changed:
            self._current_track_id = track_id
            self._load_album_art(track)

        if self._artist_scroller:
            self._artist_scroller.set_text(track["artist"])
        if self._title_scroller:
            self._title_scroller.set_text(track["title"])

        # Hide "no music" label
        self._show_status("")

    def _load_album_art(self, track):
        # Remove old art from group
        if self._art_grid is not None:
            try:
                self._group.remove(self._art_grid)
            except Exception:
                pass
            self._art_grid = None
        gc.collect()

        downloaded = False

        if self.companion_url:
            # Companion serves a pre-processed 64x64 256-color BMP
            downloaded = self.network.save_url_to_file(
                f"{self.companion_url}/api/matrix/album_art.bmp",
                ART_PATH,
            )
        elif track.get("art_url"):
            # Without companion: we can't easily decode JPEG on-device.
            # Future: add JPEG decode if memory allows.
            pass

        if downloaded:
            tile_grid = load_bmp(ART_PATH)
            if tile_grid:
                # Insert art at position 1 (after background, before text)
                self._art_grid = tile_grid
                self._group.insert(1, self._art_grid)

    def _show_status(self, text):
        if self._status_label:
            self._status_label.text = text
            center_label(self._status_label, y=30)
