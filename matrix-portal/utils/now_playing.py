# now_playing.py — Spotify "now playing" state, shared by the main loop and
# music mode so auto mode switching works no matter what's on screen.
#
# Two sources:
#   - Companion (COMPANION_URL set): the companion polls Spotify itself and
#     includes the track in its /api/matrix/status reply, so the device makes
#     one small LAN request per poll for everything (mode, brightness, track).
#   - Direct (SPOTIFY_REFRESH_TOKEN set, no companion): the device calls the
#     Spotify Web API itself, using the same adaptive schedule as the Pi app:
#     poll tightly only around a predicted track change, back off when paused
#     or idle.
import binascii
import time

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"

# Adaptive polling (seconds) - mirrors the Pi app's defaults
POLL_MAX = 10           # mid-song ceiling (catches manual skips)
POLL_PAUSED = 20
POLL_IDLE = 30
POLL_TRANSITION = 2     # near the end of a track
TRANSITION_WINDOW = 12  # start tight polling this long before the predicted end
POLL_ERROR = 15
POLL_BACKGROUND = 30    # while another mode is showing (only to detect "music started")


def _pick_art_url(images, min_size=64):
    """Smallest image that is at least min_size px (Spotify's 64px one is a
    perfect fit for the panel and only ~2-4 KB)."""
    best = None
    for img in images or []:
        w = img.get("width") or 0
        if w >= min_size and (best is None or w < (best.get("width") or 0)):
            best = img
    if best is None and images:
        best = images[-1]
    return best.get("url", "") if best else ""


class NowPlaying:
    def __init__(self, network, companion_url="", client_id="",
                 client_secret="", refresh_token=""):
        self.network = network
        self.companion_url = companion_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

        self.track = None        # dict or None
        self.version = 0         # bumps whenever the track or play state changes
        self.fetched_at = 0
        self.next_poll = 0
        self.last_attempt = -POLL_BACKGROUND
        self.error = None
        self._access_token = None
        self._token_expiry = 0

    # ------------------------------------------------------------------ state

    @property
    def available(self):
        return bool(self.companion_url or self.refresh_token)

    @property
    def is_playing(self):
        return bool(self.track and self.track.get("is_playing"))

    def progress_ms(self, now=None):
        """Current position, advanced locally between polls while playing."""
        if not self.track:
            return 0
        pos = self.track.get("progress", 0) or 0
        if self.track.get("is_playing"):
            pos += ((now or time.monotonic()) - self.fetched_at) * 1000
        return min(pos, self.track.get("duration", 0) or pos)

    def _set(self, track):
        old = self.track
        changed = (
            (old is None) != (track is None)
            or (old and track and (
                old.get("id") != track.get("id")
                or old.get("is_playing") != track.get("is_playing")
                or old.get("art_version") != track.get("art_version")))
        )
        self.track = track
        self.fetched_at = time.monotonic()
        if changed:
            self.version += 1
        return changed

    # ------------------------------------------------------------- companion

    def apply_companion(self, data):
        """Update from the `track` part of the companion's status reply."""
        if not data or not data.get("track_id"):
            return self._set(None)
        return self._set({
            "id":          data.get("track_id", ""),
            "title":       data.get("title", ""),
            "artist":      data.get("artist", ""),
            "art_url":     data.get("art_url", ""),
            "art_version": data.get("art_version", 0),
            "progress":    data.get("progress_ms", 0) or 0,
            "duration":    data.get("duration_ms", 0) or 0,
            "is_playing":  bool(data.get("is_playing")),
        })

    # ---------------------------------------------------------- direct Spotify

    def due(self, now, foreground):
        """Is a direct Spotify poll due? (Companion polling is driven by code.py.)"""
        if self.companion_url or not self.refresh_token:
            return False
        if now < self.next_poll:
            return False  # adaptive schedule / error back-off
        if foreground:
            return True
        # Another mode is showing: only check occasionally, to notice playback
        # starting (auto-switch back to album art).
        return now >= self.last_attempt + POLL_BACKGROUND

    def poll_spotify(self):
        """Fetch now-playing from the Spotify Web API. Returns True if changed."""
        self.last_attempt = time.monotonic()
        token = self._get_access_token()
        if not token:
            self._schedule(error=True)
            return False
        status, data = self.network.request(
            "GET", SPOTIFY_NOW_PLAYING_URL,
            headers={"Authorization": f"Bearer {token}"}, retries=1)
        if status == 401:
            self._access_token = None  # expired early; refresh next time
        if status is None or status >= 400:
            self.error = f"Spotify HTTP {status}"
            self._schedule(error=True)
            return False
        self.error = None
        item = (data or {}).get("item") if status == 200 else None
        if not item or data.get("currently_playing_type", "track") != "track":
            changed = self._set(None)
        else:
            artists = item.get("artists", [])
            changed = self._set({
                "id":         item.get("id", ""),
                "title":      item.get("name", ""),
                "artist":     artists[0]["name"] if artists else "Unknown",
                "art_url":    _pick_art_url(item.get("album", {}).get("images", [])),
                "progress":   data.get("progress_ms", 0) or 0,
                "duration":   item.get("duration_ms", 0) or 0,
                "is_playing": bool(data.get("is_playing")),
            })
        self._schedule()
        return changed

    def _schedule(self, error=False):
        if error:
            delay = POLL_ERROR
        elif not self.track:
            delay = POLL_IDLE
        elif not self.track.get("is_playing"):
            delay = POLL_PAUSED
        else:
            remaining = ((self.track.get("duration", 0) or 0) - (self.track.get("progress", 0) or 0)) / 1000
            if remaining <= TRANSITION_WINDOW:
                delay = POLL_TRANSITION
            else:
                delay = min(POLL_MAX, remaining - TRANSITION_WINDOW)
        self.next_poll = time.monotonic() + max(1, delay)

    def _get_access_token(self):
        now = time.monotonic()
        if self._access_token and now < self._token_expiry - 30:
            return self._access_token
        creds = f"{self.client_id}:{self.client_secret}".encode()
        b64 = binascii.b2a_base64(creds).decode().strip()
        status, data = self.network.request(
            "POST", SPOTIFY_TOKEN_URL,
            headers={"Authorization": f"Basic {b64}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data=f"grant_type=refresh_token&refresh_token={self.refresh_token}",
            retries=1)
        if status != 200 or not data or "access_token" not in data:
            self.error = "Spotify login failed - check SPOTIFY_* settings"
            print(f"Token refresh failed (HTTP {status})")
            return None
        self._access_token = data["access_token"]
        self._token_expiry = now + data.get("expires_in", 3600)
        return self._access_token
