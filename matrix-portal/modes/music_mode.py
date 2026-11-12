# music_mode.py — Spotify album art + track info for Matrix Portal 64x64
#
# Track data comes from the shared NowPlaying object (utils/now_playing.py),
# which code.py keeps up to date - via the companion, or by calling Spotify
# directly. This mode only renders it.
#
# Album art:
#   - With the companion: a pre-processed 64x64 256-colour BMP (contrast /
#     saturation tuned for LEDs, same processing as the Pi app).
#   - Without the companion on an S3: Spotify's 64px JPEG, decoded on the
#     device with the built-in jpegio module.
#   - Without the companion on an M4 (no jpegio): text only.
#
# Polish:
#   - A now-playing progress bar along the bottom (advances locally between fetches).
#   - A dark band behind the scrolling text so it stays legible over bright art.
#   - Last-good caching: album art + track text persist across reboots (written
#     to flash only when changed and rate-limited, to spare the flash).

import displayio
import gc

from utils.display_helper import (
    make_text_label, center_label, load_bmp, decode_jpeg, COLORS, ScrollingLabel,
    make_bitmap, make_palette, fill_bitmap, dimmer,
)
from utils import storage_helper

ART_PATH = "/album_art.bmp"
ART_JPEG_PATH = "/album_art.jpg"
TRACK_CACHE = "/cache_track.json"

# Layout
_ARTIST_Y = 48
_TITLE_Y = 56
_BAND_Y = 44
_BAND_H = 20
_PROGRESS_Y = 62
_STATUS_Y = 22


class MusicMode:
    def __init__(self, display, network, now_playing, companion_url=""):
        self.display = display
        self.network = network
        self.now_playing = now_playing
        self.companion_url = companion_url.rstrip("/")

        self._group = None
        self._art_grid = None
        self._band_grid = None
        self._progress_bmp = None
        self._progress_grid = None
        self._artist_scroller = None
        self._title_scroller = None
        self._status_label = None

        self._seen_version = -1
        self._art_key = None
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
        bg_bmp.fill(1)
        self._group.append(displayio.TileGrid(bg_bmp, pixel_shader=bg_pal))

        # 1: dark band behind the text (legibility over bright album art)
        band_bmp = make_bitmap(64, _BAND_H, 1)
        band_pal = make_palette([0x000000])
        self._band_grid = displayio.TileGrid(band_bmp, pixel_shader=band_pal, x=0, y=_BAND_Y)
        self._group.append(self._band_grid)

        # 2: status / "no music" label
        self._status_label = make_text_label("", color=COLORS["gray"], y=_STATUS_Y)
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
        self._seen_version = -1
        self._art_key = None
        self._last_progress_cols = -1

        # Show last-good content immediately (before the first network result)
        if self.now_playing.track is None:
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
        np = self.now_playing
        if np.version != self._seen_version:
            self._seen_version = np.version
            if np.track:
                self._render_track(np.track)
            elif np.fetched_at:
                self._remove_art()
                self._artist_scroller.set_text("")
                self._title_scroller.set_text("")
                self._show_status("No music")
            elif not np.available:
                self._show_status("Not set up")

        # Animate scrolling text + progress bar
        self._artist_scroller.update()
        self._title_scroller.update()
        self._update_progress_bar()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_track(self, track):
        art_key = (track.get("id"), track.get("art_version"))
        if art_key != self._art_key:
            self._art_key = art_key
            self._load_album_art(track)

        self._artist_scroller.set_text(track.get("artist", ""))
        self._title_scroller.set_text(track.get("title", ""))
        # Paused: keep the album art up (like the Pi app); say so if there's no art
        self._show_status("" if track.get("is_playing") or self._art_grid else "Paused")

        # Persist last-good track text for the next reboot (only if changed,
        # and rate-limited - see storage_helper)
        storage_helper.save_json(TRACK_CACHE, {
            "id": track.get("id", ""),
            "artist": track.get("artist", ""),
            "title": track.get("title", ""),
        })

    def _load_album_art(self, track):
        self._remove_art()
        gc.collect()

        if self.companion_url:
            # Companion serves a pre-processed 64x64 256-color BMP. Loaded
            # straight from memory (no write-then-read through flash).
            data = self.network.get_bytes(
                f"{self.companion_url}/api/matrix/album_art.bmp?v={track.get('art_version', 0)}",
                retries=1)
            if data:
                self._insert_art(load_bmp(data))
                storage_helper.save_bytes(ART_PATH, data)
        elif track.get("art_url"):
            # No companion: decode Spotify's small JPEG on-device (S3 only)
            data = self.network.get_bytes(track["art_url"], retries=1)
            if data:
                grid = decode_jpeg(data)
                if grid:
                    self._insert_art(grid)
                    storage_helper.save_bytes(ART_JPEG_PATH, data)
        data = None
        gc.collect()

    def _remove_art(self):
        if self._art_grid is not None:
            try:
                self._group.remove(self._art_grid)
            except Exception:
                pass
            shader = self._art_grid.pixel_shader
            if isinstance(shader, displayio.Palette):
                dimmer.forget_palette(shader)
            else:
                dimmer.forget_bitmap(self._art_grid.bitmap)
            self._art_grid = None

    def _insert_art(self, tile_grid):
        """Insert art just above the background (index 1)."""
        if tile_grid is None or self._group is None:
            return
        self._remove_art()
        self._art_grid = tile_grid
        self._group.insert(1, self._art_grid)
        self._show_status("")

    def _update_progress_bar(self):
        if not self._progress_bmp:
            return
        track = self.now_playing.track
        duration = (track or {}).get("duration", 0) or 0
        if duration <= 0:
            cols = 0
        else:
            frac = self.now_playing.progress_ms() / duration
            cols = int(max(0, min(1, frac)) * 64)

        if cols == self._last_progress_cols:
            return
        prev = max(0, self._last_progress_cols)
        self._last_progress_cols = cols
        # Only touch the columns that changed (usually just one)
        if cols > prev:
            fill_bitmap(self._progress_bmp, 1, prev, 0, cols, 2)
        else:
            fill_bitmap(self._progress_bmp, 0, cols, 0, 64, 2)

    def _show_status(self, text):
        if self._status_label is not None and self._status_label.text != text:
            self._status_label.text = text
            center_label(self._status_label, y=_STATUS_Y)

    def _restore_cache(self):
        """Show last-good album art + track text from flash on mode entry."""
        if self.companion_url:
            data = storage_helper.load_bytes(ART_PATH)
            grid = load_bmp(data) if data else None
        else:
            data = storage_helper.load_bytes(ART_JPEG_PATH)
            grid = decode_jpeg(data) if data else None
        self._insert_art(grid)
        cached = storage_helper.load_json(TRACK_CACHE)
        if cached:
            self._artist_scroller.set_text(cached.get("artist", ""))
            self._title_scroller.set_text(cached.get("title", ""))
        elif not self._art_grid:
            self._show_status("Loading" if self.now_playing.available else "Not set up")
