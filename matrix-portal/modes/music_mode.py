# music_mode.py — Spotify album art + track info for Matrix Portal 64x64
#
# Two operation modes:
#   1. With companion (COMPANION_URL set): fetches pre-processed 64x64 BMP from companion.
#      The companion handles OAuth and image resizing.
#   2. Without companion: calls Spotify API directly using a stored refresh token.
#      Without companion, only track/artist text is shown (no album art).
#
# Polish:
#   - A now-playing progress bar along the bottom (advances locally between fetches).
#   - A dark band behind the scrolling text so it stays legible over bright art.
#   - Last-good caching: the album art BMP and track text persist across reboots,
#     so a restart shows real content immediately instead of "No music".

import displayio
import time
import gc

from utils.display_helper import (
    make_text_label, center_label, load_bmp, COLORS, ScrollingLabel,
    make_bitmap, make_palette,
)
from utils import storage_helper

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"

ART_PATH = "/album_art.bmp"
TRACK_CACHE = "/cache_track.json"

# Layout
_ARTIST_Y = 48
_TITLE_Y = 56
_BAND_Y = 44
_BAND_H = 20
_PROGRESS_Y = 62


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
        self._band_grid = None
        self._progress_bmp = None
        self._progress_grid = None
        self._artist_scroller = None
        self._title_scroller = None
        self._status_label = None

        self._access_token = None
        self._token_expiry = 0
        self._current_track_id = None
        self._last_update = 0
        self._update_interval = 10  # seconds

        # Progress tracking (advanced locally between fetches)
        self._progress_ms = 0
        self._duration_ms = 0
        self._progress_fetched_at = 0
        self._last_progress_cols = -1

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self):
        gc.collect()
        self._group = displayio.Group()

        # 0: placeholder background (dark)
        bg_bmp = make_bitmap(64, 64, 2)
        bg_pal = make_palette([0x000000, 0x111111])
        bg_bmp.fill(1)  # C-level fill, far faster than a 4096-iteration loop
        self._group.append(displayio.TileGrid(bg_bmp, pixel_shader=bg_pal))

        # 1: dark band behind the text (legibility over bright album art)
        band_bmp = make_bitmap(64, _BAND_H, 1)
        band_pal = make_palette([0x000000])
        self._band_grid = displayio.TileGrid(band_bmp, pixel_shader=band_pal, x=0, y=_BAND_Y)
        self._group.append(self._band_grid)

        # 2: status / "no music" label
        self._status_label = make_text_label("No music", color=COLORS["gray"], y=30)
        center_label(self._status_label, y=30)
        self._group.append(self._status_label)

        # 3: scrolling artist
        self._artist_scroller = ScrollingLabel("", color=COLORS["cyan"], y=_ARTIST_Y, scale=1)
        self._group.append(self._artist_scroller.label)

        # 4: scrolling title
        self._title_scroller = ScrollingLabel("", color=COLORS["white"], y=_TITLE_Y, scale=1)
        self._group.append(self._title_scroller.label)

        # 5: progress bar (2px tall at the very bottom)
        self._progress_bmp = make_bitmap(64, 2, 2)
        prog_pal = make_palette([0x222222, 0x1DB954])  # track gray, Spotify green
        self._progress_grid = displayio.TileGrid(
            self._progress_bmp, pixel_shader=prog_pal, x=0, y=_PROGRESS_Y
        )
        self._group.append(self._progress_grid)

        self.display.root_group = self._group
        self._last_update = 0  # force immediate fetch

        # Show last-good content immediately (before the first network fetch)
        self._restore_cache()

    def on_exit(self):
        self._group = None
        self._art_grid = None
        self._band_grid = None
        self._progress_bmp = None
        self._progress_grid = None
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
                self._progress_ms = 0
                self._duration_ms = 0

        # Animate scrolling text + progress bar every frame
        if self._artist_scroller:
            self._artist_scroller.update()
        if self._title_scroller:
            self._title_scroller.update()
        self._update_progress_bar(now)

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
            "id":       data.get("track_id", ""),
            "title":    data.get("title", ""),
            "artist":   data.get("artist", ""),
            "art_url":  data.get("art_url", ""),
            "progress": data.get("progress_ms", 0),
            "duration": data.get("duration_ms", 0),
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
            "id":       item.get("id", ""),
            "title":    item.get("name", ""),
            "artist":   artist,
            "art_url":  art_url,
            "progress": data.get("progress_ms", 0),
            "duration": item.get("duration_ms", 0),
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

        # Progress
        self._duration_ms = int(track.get("duration", 0) or 0)
        self._progress_ms = int(track.get("progress", 0) or 0)
        self._progress_fetched_at = time.monotonic()

        # Hide "no music" label
        self._show_status("")

        # Persist last-good track text for the next reboot
        storage_helper.save_json(TRACK_CACHE, {
            "id": track_id,
            "artist": track["artist"],
            "title": track["title"],
        })

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
            # Without companion we can't easily decode JPEG on-device.
            pass

        if downloaded:
            self._insert_art_from_file()

    def _insert_art_from_file(self):
        """Load ART_PATH and insert it just above the background (index 1)."""
        tile_grid = load_bmp(ART_PATH)
        if tile_grid:
            if self._art_grid is not None:
                try:
                    self._group.remove(self._art_grid)
                except Exception:
                    pass
            self._art_grid = tile_grid
            self._group.insert(1, self._art_grid)

    def _update_progress_bar(self, now):
        if not self._progress_grid or not self._progress_bmp:
            return
        if self._duration_ms <= 0:
            cols = 0
        else:
            elapsed = (now - self._progress_fetched_at) * 1000
            pos = self._progress_ms + elapsed
            frac = pos / self._duration_ms
            if frac < 0:
                frac = 0
            elif frac > 1:
                frac = 1
            cols = int(frac * 64)

        if cols == self._last_progress_cols:
            return
        self._last_progress_cols = cols
        bmp = self._progress_bmp
        for x in range(64):
            v = 1 if x < cols else 0
            bmp[x, 0] = v
            bmp[x, 1] = v

    def _show_status(self, text):
        if self._status_label:
            self._status_label.text = text
            center_label(self._status_label, y=30)

    def _restore_cache(self):
        """Show last-good album art + track text from flash on mode entry."""
        # Album art BMP persists across reboots
        self._insert_art_from_file()
        cached = storage_helper.load_json(TRACK_CACHE)
        if cached:
            if self._artist_scroller:
                self._artist_scroller.set_text(cached.get("artist", ""))
            if self._title_scroller:
                self._title_scroller.set_text(cached.get("title", ""))
            if cached.get("artist") or cached.get("title"):
                self._show_status("")
