#!/usr/bin/env python3
"""
companion.py — Desktop companion server for Matrix Portal M4
Runs on your Mac/PC/Linux machine on the same WiFi network as the Matrix Portal.

Usage:
    # First-time Spotify auth:
    python companion.py --auth

    # Run the server:
    python companion.py

    # Custom port:
    python companion.py --port 5001

The Matrix Portal polls this server for:
  GET /api/matrix/status          — current mode + brightness (set via web UI)
  GET /api/matrix/track           — current Spotify track info
  GET /api/matrix/album_art.bmp   — 64x64 256-color BMP of current album art
  GET /api/matrix/weather         — current weather + 3-day forecast
  GET /api/matrix/sports          — current team game data

The existing web control panel (web/) is served at http://localhost:5001/
"""

import argparse
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

import requests
import spotipy
from flask import Flask, jsonify, request, send_from_directory, send_file, session, redirect, url_for
from flask_cors import CORS
from PIL import Image

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
WEB_DIR    = BASE_DIR.parent / "web"
TOKEN_FILE = BASE_DIR / ".spotify_token.json"
CONFIG_FILE = BASE_DIR / "companion_config.json"

# ── Default config ─────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "spotify": {
        "client_id": "",
        "client_secret": "",
        "redirect_uri": "http://127.0.0.1:8888/callback",
    },
    "weather": {
        "api_key": "",
        "location": "New York,US",
        "units": "imperial",
    },
    "sports": {
        "league": "NBA",
        "team": "LAL",
    },
    "display": {
        "brightness": 50,
        "mode": "music",
    },
    "web": {
        "host": "0.0.0.0",
        "port": 5001,
        "admin_password": "admin",
        "secret_key": "change_me_in_production",
    },
}

# ── Config helpers ─────────────────────────────────────────────────────────────
def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        # Merge with defaults so new keys are always present
        for section, values in DEFAULT_CONFIG.items():
            if section not in cfg:
                cfg[section] = values
            else:
                for k, v in values.items():
                    cfg[section].setdefault(k, v)
        return cfg
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


config = load_config()

# ── Spotify ────────────────────────────────────────────────────────────────────
SPOTIFY_SCOPE = "user-read-playback-state user-read-currently-playing"


class SpotifyManager:
    def __init__(self):
        self._sp = None
        self._lock = threading.Lock()
        self._current_track = {}
        self._last_poll = 0
        self._poll_interval = 10
        self._art_cache = {}  # track_id → PIL.Image
        self._current_art_id = None
        self._current_art_img = None

    def _make_sp(self):
        cfg = config["spotify"]
        if not cfg["client_id"] or not cfg["client_secret"]:
            return None
        cache = spotipy.cache_handler.CacheFileHandler(cache_path=str(TOKEN_FILE))
        auth = spotipy.SpotifyOAuth(
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            redirect_uri=cfg["redirect_uri"],
            scope=SPOTIFY_SCOPE,
            cache_handler=cache,
            open_browser=False,
        )
        return spotipy.Spotify(auth_manager=auth)

    def authenticate(self):
        """Run interactive OAuth flow. Call with --auth flag."""
        cfg = config["spotify"]
        if not cfg["client_id"] or not cfg["client_secret"]:
            print("\nERROR: Set spotify.client_id and spotify.client_secret in companion_config.json first.\n")
            sys.exit(1)

        cache = spotipy.cache_handler.CacheFileHandler(cache_path=str(TOKEN_FILE))
        auth = spotipy.SpotifyOAuth(
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            redirect_uri=cfg["redirect_uri"],
            scope=SPOTIFY_SCOPE,
            cache_handler=cache,
            open_browser=True,
        )
        print(f"\nOpening browser for Spotify authentication…")
        print(f"Redirect URI must be set to: {cfg['redirect_uri']}")
        print("After authorizing, paste the full redirect URL here.\n")
        auth_url = auth.get_authorize_url()
        print(f"Auth URL: {auth_url}\n")
        response = input("Paste redirect URL: ").strip()
        code = auth.parse_response_code(response)
        token = auth.get_access_token(code)
        print(f"\nAuthentication successful! Token saved to {TOKEN_FILE}")
        print("You can now run companion.py without --auth.\n")

    def _ensure_sp(self):
        if self._sp is None:
            self._sp = self._make_sp()
        return self._sp

    def poll(self):
        """Background thread: poll Spotify every N seconds."""
        while True:
            try:
                sp = self._ensure_sp()
                if sp:
                    result = sp.current_playback()
                    if result and result.get("is_playing") and result.get("item"):
                        item = result["item"]
                        artists = item.get("artists", [])
                        artist = artists[0]["name"] if artists else "Unknown"
                        images = item.get("album", {}).get("images", [])
                        # Use the 300px image if available, fall back to any size
                        art_url = ""
                        for img in images:
                            if img.get("width", 0) >= 300:
                                art_url = img["url"]
                                break
                        if not art_url and images:
                            art_url = images[0]["url"]

                        track_id = item.get("id", "")
                        with self._lock:
                            self._current_track = {
                                "is_playing": True,
                                "track_id":   track_id,
                                "title":      item.get("name", ""),
                                "artist":     artist,
                                "album":      item.get("album", {}).get("name", ""),
                                "art_url":    art_url,
                            }
                            # Pre-fetch art if track changed
                            if track_id and track_id != self._current_art_id:
                                self._fetch_art(art_url, track_id)
                    else:
                        with self._lock:
                            self._current_track = {"is_playing": False}
            except Exception as e:
                print(f"[Spotify] Poll error: {e}")
            time.sleep(self._poll_interval)

    def _fetch_art(self, art_url, track_id):
        """Download and resize album art to 64x64 256-color BMP. Caller holds lock."""
        if not art_url:
            return
        try:
            resp = requests.get(art_url, timeout=10)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            img = img.resize((64, 64), Image.LANCZOS)
            # Quantize to 256 colors for CircuitPython compatibility
            img = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
            self._current_art_img = img
            self._current_art_id = track_id
            print(f"[Spotify] Art ready for: {track_id}")
        except Exception as e:
            print(f"[Spotify] Art fetch failed: {e}")

    def get_track(self):
        with self._lock:
            return dict(self._current_track)

    def get_art_bmp(self):
        """Return 64x64 256-color BMP bytes, or None if not available."""
        with self._lock:
            img = self._current_art_img
        if img is None:
            return None
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        buf.seek(0)
        return buf


spotify_mgr = SpotifyManager()

# ── Weather ────────────────────────────────────────────────────────────────────
_weather_cache = {}
_weather_last_fetch = 0
_WEATHER_TTL = 600  # 10 minutes


def get_weather():
    global _weather_last_fetch, _weather_cache
    now = time.time()
    if now - _weather_last_fetch < _WEATHER_TTL and _weather_cache:
        return _weather_cache

    cfg = config["weather"]
    if not cfg["api_key"]:
        return {"error": "No API key"}

    try:
        current_url = (
            f"http://api.openweathermap.org/data/2.5/weather"
            f"?q={cfg['location']}&appid={cfg['api_key']}&units={cfg['units']}"
        )
        resp = requests.get(current_url, timeout=10)
        resp.raise_for_status()
        c = resp.json()

        fc_url = (
            f"http://api.openweathermap.org/data/2.5/forecast"
            f"?q={cfg['location']}&appid={cfg['api_key']}&units={cfg['units']}&cnt=24"
        )
        fc_resp = requests.get(fc_url, timeout=10)
        fc_resp.raise_for_status()
        fc_data = fc_resp.json()

        forecast = []
        seen = set()
        for entry in fc_data.get("list", []):
            day = entry["dt_txt"][:10]
            if day not in seen and len(forecast) < 3:
                seen.add(day)
                forecast.append({
                    "day":  day[-5:],
                    "temp": entry["main"]["temp"],
                    "main": entry["weather"][0]["main"],
                })

        weather = c.get("weather", [{}])
        _weather_cache = {
            "temp":       c["main"]["temp"],
            "feels_like": c["main"]["feels_like"],
            "humidity":   c["main"]["humidity"],
            "condition":  weather[0].get("main", "Clear") if weather else "Clear",
            "description": weather[0].get("description", "") if weather else "",
            "city":       c.get("name", cfg["location"]),
            "units":      cfg["units"],
            "forecast":   forecast,
        }
        _weather_last_fetch = now
        return _weather_cache

    except Exception as e:
        print(f"[Weather] Fetch error: {e}")
        return {"error": str(e)}


# ── Sports ─────────────────────────────────────────────────────────────────────
_SPORT_MAP = {
    "NFL": ("football", "nfl"),
    "NBA": ("basketball", "nba"),
    "MLB": ("baseball", "mlb"),
    "NHL": ("hockey", "nhl"),
}
_sports_cache = {}
_sports_last_fetch = 0
_SPORTS_TTL = 60


def get_sports():
    global _sports_last_fetch, _sports_cache
    now = time.time()
    if now - _sports_last_fetch < _SPORTS_TTL and _sports_cache:
        return _sports_cache

    cfg = config["sports"]
    league = cfg["league"].upper()
    team = cfg["team"].upper()
    sport, league_path = _SPORT_MAP.get(league, ("basketball", "nba"))

    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league_path}/scoreboard"
        # ESPN rejects requests without a browser-like User-Agent.
        resp = requests.get(url, timeout=10,
                            headers={"User-Agent": "Mozilla/5.0 (Matrix Portal Companion)"})
        resp.raise_for_status()
        data = resp.json()

        for event in data.get("events", []):
            for comp in event.get("competitions", []):
                for c in comp.get("competitors", []):
                    if c.get("team", {}).get("abbreviation", "").upper() == team:
                        status = event.get("status", {}).get("type", {})
                        home = next((x for x in comp["competitors"] if x.get("homeAway") == "home"), {})
                        away = next((x for x in comp["competitors"] if x.get("homeAway") == "away"), {})
                        _sports_cache = {
                            "home_team":  home.get("team", {}).get("abbreviation", "???"),
                            "away_team":  away.get("team", {}).get("abbreviation", "???"),
                            "home_score": home.get("score", "-"),
                            "away_score": away.get("score", "-"),
                            "status":     status.get("shortDetail", status.get("name", "???")),
                            "completed":  status.get("completed", False),
                        }
                        _sports_last_fetch = now
                        return _sports_cache

        _sports_cache = {"status": "No game today", "home_team": team, "away_team": "---",
                         "home_score": "-", "away_score": "-", "completed": False}
        _sports_last_fetch = now
        return _sports_cache

    except Exception as e:
        print(f"[Sports] Fetch error: {e}")
        return {"error": str(e)}


# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(WEB_DIR))
CORS(app)

# State shared between web UI and Matrix Portal
_matrix_state = {
    "mode": config["display"]["mode"],
    "brightness": config["display"]["brightness"],
    "manual": False,
}


# ── Matrix Portal endpoints ────────────────────────────────────────────────────

@app.get("/api/matrix/status")
def matrix_status():
    return jsonify(_matrix_state)


@app.get("/api/matrix/track")
def matrix_track():
    return jsonify(spotify_mgr.get_track())


@app.get("/api/matrix/album_art.bmp")
def matrix_album_art():
    buf = spotify_mgr.get_art_bmp()
    if buf is None:
        return "", 204
    return send_file(buf, mimetype="image/bmp", as_attachment=False,
                     download_name="album_art.bmp")


@app.get("/api/matrix/weather")
def matrix_weather():
    return jsonify(get_weather())


@app.get("/api/matrix/sports")
def matrix_sports():
    return jsonify(get_sports())


# ── Web control panel endpoints (compatible with existing web/) ────────────────

WEB_MODES = ["music", "weather", "sports", "clock", "screensaver"]


@app.get("/api/status")
def web_status():
    track = spotify_mgr.get_track()
    playing = track.get("is_playing", False)
    return jsonify({
        # Keys the bundled web/ front-end (originally written for the Pi
        # server) actually reads:
        "current_mode":    _matrix_state["mode"],
        "available_modes": WEB_MODES,
        "brightness":      _matrix_state["brightness"],
        "spotify_playing": playing,
        "running":         True,
        # Original companion keys, kept for any other consumers:
        "mode":            _matrix_state["mode"],
        "is_playing":      playing,
        "track":           track.get("title", ""),
        "artist":          track.get("artist", ""),
        "album":           track.get("album", ""),
    })


@app.get("/api/spotify/current")
def web_spotify_current():
    """Now-playing info in the shape the bundled web/script.js expects."""
    track = spotify_mgr.get_track()
    if not track.get("is_playing"):
        return jsonify({"message": "Nothing playing"})
    return jsonify({
        "track_name":    track.get("title", ""),
        "artist_name":   track.get("artist", ""),
        "album_name":    track.get("album", ""),
        "album_art_url": track.get("art_url", ""),
        "is_playing":    True,
    })


@app.get("/api/auth/check")
def web_auth_check():
    # The companion has no admin login - it's configured via
    # companion_config.json (or the companion's own /api/config endpoint),
    # so report unauthenticated. The web UI then keeps the admin settings
    # panel hidden while the mode/brightness/now-playing controls work.
    return jsonify({"authenticated": False})


@app.post("/api/mode")
def set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "")
    valid = {"music", "weather", "sports", "clock", "screensaver"}
    if mode not in valid:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400
    _matrix_state["mode"] = mode
    _matrix_state["manual"] = True
    config["display"]["mode"] = mode
    save_config(config)
    return jsonify({"ok": True, "mode": mode})


@app.post("/api/brightness")
def set_brightness():
    data = request.get_json(silent=True) or {}
    brightness = data.get("brightness", 50)
    brightness = max(5, min(100, int(brightness)))
    _matrix_state["brightness"] = brightness
    config["display"]["brightness"] = brightness
    save_config(config)
    return jsonify({"ok": True, "brightness": brightness})


@app.get("/api/config")
def get_config_endpoint():
    # Don't expose secrets to the web UI
    safe = dict(config)
    safe["spotify"] = {k: "***" if "secret" in k or "token" in k else v
                       for k, v in config["spotify"].items()}
    return jsonify(safe)


@app.post("/api/config")
def post_config_endpoint():
    data = request.get_json(silent=True) or {}
    for section in ("weather", "sports", "display"):
        if section in data:
            config[section].update(data[section])
    # Allow updating non-secret spotify fields
    if "spotify" in data:
        for k in ("client_id", "redirect_uri"):
            if k in data["spotify"]:
                config["spotify"][k] = data["spotify"][k]
    save_config(config)
    return jsonify({"ok": True})


# ── Static web UI ──────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return send_from_directory(str(WEB_DIR), "index.html")


@app.get("/<path:filename>")
def static_web(filename):
    return send_from_directory(str(WEB_DIR), filename)


# ── Auth CLI ───────────────────────────────────────────────────────────────────

def run_auth():
    spotify_mgr.authenticate()


def run_server(host, port):
    # Start Spotify background polling
    t = threading.Thread(target=spotify_mgr.poll, daemon=True)
    t.start()

    print(f"\n{'='*55}")
    print(f"  Matrix Portal Companion")
    print(f"  Web control panel → http://{host}:{port}/")
    print(f"  Matrix Portal URL → http://<your-ip>:{port}/")
    print(f"{'='*55}\n")

    app.secret_key = config["web"].get("secret_key", "dev_secret")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Matrix Portal Companion Server")
    parser.add_argument("--auth", action="store_true",
                        help="Run interactive Spotify OAuth flow")
    parser.add_argument("--host", default=config["web"].get("host", "0.0.0.0"),
                        help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=config["web"].get("port", 5001),
                        help="Port to listen on (default: 5001)")
    args = parser.parse_args()

    if args.auth:
        run_auth()
    else:
        run_server(args.host, args.port)
