#!/usr/bin/env python3
"""
companion.py — Companion server for the Adafruit Matrix Portal (S3 or M4)

Runs on any always-on computer on the same network as the Matrix Portal
(a Raspberry Pi, Mac, PC or Linux box). It handles what the microcontroller
can't do well itself:
  - Spotify login (OAuth) and polling
  - Album art: download, crop, LED colour tuning, convert to a 64x64 BMP
  - The web dashboard + admin panel (same UI as the Pi version)
  - Proxying weather and sports data

It reuses the Raspberry Pi app's code (../src) for Spotify polling, album-art
processing and sports scores, so both versions look and behave the same.

Usage:
    python companion.py --auth      # first-time Spotify sign-in
    python companion.py             # run the server
    python companion.py --port 5001

The Matrix Portal polls:
  GET /api/matrix/status          — mode/brightness/commands + current track (one request)
  GET /api/matrix/album_art.bmp   — 64x64 256-color BMP of the current album art
  GET /api/matrix/weather         — current weather + 3-day forecast
  GET /api/matrix/sports          — current team game data
"""

import argparse
import copy
import functools
import hmac
import io
import json
import logging
import os
import secrets
import sys
import threading
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory, send_file, session
from flask_cors import CORS

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
REPO_DIR    = BASE_DIR.parent
WEB_DIR     = REPO_DIR / "web"
TOKEN_FILE  = BASE_DIR / ".spotify_token.json"
CONFIG_FILE = BASE_DIR / "companion_config.json"

# Reuse the Pi app's modules (Spotify client, image processing, sports parsing)
sys.path.insert(0, str(REPO_DIR / "src"))
from spotify_client import SpotifyClient, make_auth_manager, browser_available  # noqa: E402
from utils.image_processor import ImageProcessor  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("companion")

MATRIX_MODES = ["music", "weather", "sports", "clock", "screensaver"]
LEAGUES = ["NFL", "NBA", "WNBA", "MLB", "NHL", "MLS", "NCAAF", "NCAAM"]

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
        "enabled": True,
        "league": "NBA",
        "team": "LAL",
        "update_interval": 60,
    },
    "display": {
        "brightness": 50,
        "mode": "music",
    },
    "image_processing": {
        "enhance_contrast": True,
        "contrast_factor": 1.2,
        "enhance_saturation": True,
        "saturation_factor": 1.1,
        "cache_images": True,
        "cache_size_mb": 50,
    },
    "web": {
        "host": "0.0.0.0",
        "port": 5001,
        "admin_username": "admin",
        "admin_password": "admin",
        "secret_key": "",
    },
}


def _merge_defaults(cfg):
    for section, values in DEFAULT_CONFIG.items():
        if not isinstance(cfg.get(section), dict):
            cfg[section] = copy.deepcopy(values)
        else:
            for k, v in values.items():
                cfg[section].setdefault(k, v)
    return cfg


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    else:
        cfg = {}
    cfg = _merge_defaults(cfg)
    if not cfg["web"].get("secret_key") or cfg["web"]["secret_key"] == "change_me_in_production":
        cfg["web"]["secret_key"] = secrets.token_hex(32)
        save_config(cfg)
    return cfg


def save_config(cfg):
    tmp = CONFIG_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


config = load_config()


def spotify_settings():
    """Spotify config for the shared SpotifyClient (keeps the companion's own token file)."""
    cfg = dict(config["spotify"])
    cfg["token_cache_path"] = str(TOKEN_FILE)
    return cfg


# ── Spotify + album art ────────────────────────────────────────────────────────

class SpotifyManager:
    """Polls Spotify in the background (adaptive schedule from the Pi app) and
    keeps the current track plus a ready-to-serve 64x64 BMP of its album art."""

    RETRY_INTERVAL = 60

    def __init__(self):
        self._lock = threading.Lock()
        self._client = None
        self.error = None
        self._last_attempt = 0
        self._track = None
        self._art_track_id = None
        self._art_bmp = None          # bytes, built once per track
        self.art_version = 0
        self._processor = ImageProcessor(config["image_processing"])

    def reconfigure(self):
        """Settings changed: reconnect and re-process art on next poll."""
        with self._lock:
            self._client = None
            self._last_attempt = 0
            self._art_track_id = None
            self._processor = ImageProcessor(config["image_processing"])

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if time.time() - self._last_attempt < self.RETRY_INTERVAL:
            return None
        self._last_attempt = time.time()
        cfg = config["spotify"]
        if not cfg.get("client_id") or not cfg.get("client_secret"):
            self.error = "Add your Spotify Client ID and secret in the admin panel"
            return None
        try:
            self._client = SpotifyClient(spotify_settings())
            self.error = None
            log.info("Spotify connected")
        except Exception as e:
            self.error = str(e).replace("venv/bin/python src/spotify_auth.py", "python companion.py --auth")
            log.warning("Spotify unavailable: %s", self.error)
        return self._client

    def poll_forever(self):
        while True:
            try:
                client = self._ensure_client()
                if client:
                    # Cheap: the client only hits the API when its adaptive
                    # schedule says so and returns cached data in between.
                    track = client.get_current_track()
                    with self._lock:
                        self._track = track
                    if track and track.get("track_id") != self._art_track_id:
                        self._build_art(track)
            except Exception as e:
                log.error("Spotify poll error: %s", e)
            time.sleep(1)

    def _build_art(self, track):
        track_id = track.get("track_id")
        url = track.get("album_art_url")
        bmp = None
        if url:
            img = self._processor.process_album_art(url, size=(64, 64))
            if img is not None:
                # 256-colour paletted BMP: what adafruit_imageload handles best
                img = img.quantize(colors=256, method=0)  # 0 = median cut
                buf = io.BytesIO()
                img.save(buf, format="BMP")
                bmp = buf.getvalue()
        with self._lock:
            self._art_track_id = track_id
            self._art_bmp = bmp
            self.art_version += 1

    def track(self):
        with self._lock:
            return dict(self._track) if self._track else None

    def art_bmp(self):
        with self._lock:
            return self._art_bmp

    @property
    def connected(self):
        return self._client is not None

    def authenticate(self):
        """Interactive sign-in. On a headless machine this prints the URL and
        asks you to paste the redirect back (same flow as the Pi app)."""
        cfg = config["spotify"]
        if not cfg["client_id"] or not cfg["client_secret"]:
            print(f"\nERROR: Set spotify.client_id and spotify.client_secret in {CONFIG_FILE} first")
            print("(or run the server and use the admin panel).\n")
            sys.exit(1)
        import spotipy
        if not browser_available():
            print("\nNo web browser here. Open the URL below on your phone or computer,")
            print("sign in, then paste the 127.0.0.1:8888 address you land on back here.\n")
        auth = make_auth_manager(spotify_settings(), open_browser=browser_available())
        user = spotipy.Spotify(auth_manager=auth).current_user()
        token = auth.cache_handler.get_cached_token() or {}
        print(f"\n✅ Signed in as {user.get('display_name')}. Token saved to {TOKEN_FILE}")
        if token.get("refresh_token"):
            print("\nTo run the Matrix Portal WITHOUT the companion, put this in settings.toml:")
            print(f'  SPOTIFY_REFRESH_TOKEN = "{token["refresh_token"]}"\n')


spotify_mgr = SpotifyManager()


# ── Weather ────────────────────────────────────────────────────────────────────
_weather = {"data": {}, "fetched": 0}
_WEATHER_TTL = 600  # 10 minutes


def get_weather():
    now = time.time()
    if _weather["data"] and now - _weather["fetched"] < _WEATHER_TTL:
        return _weather["data"]
    cfg = config["weather"]
    if not cfg["api_key"]:
        return {"error": "No API key"}
    params = {"q": cfg["location"], "appid": cfg["api_key"], "units": cfg["units"]}
    try:
        resp = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=10)
        resp.raise_for_status()
        c = resp.json()
        fc_resp = requests.get("https://api.openweathermap.org/data/2.5/forecast",
                               params=dict(params, cnt=24), timeout=10)
        fc_resp.raise_for_status()
        forecast, seen = [], set()
        for entry in fc_resp.json().get("list", []):
            day = entry["dt_txt"][:10]
            if day not in seen and len(forecast) < 3:
                seen.add(day)
                forecast.append({"day": day[-5:], "temp": entry["main"]["temp"],
                                 "main": entry["weather"][0]["main"]})
        weather = c.get("weather", [{}])
        _weather["data"] = {
            "temp":        c["main"]["temp"],
            "feels_like":  c["main"]["feels_like"],
            "humidity":    c["main"]["humidity"],
            "condition":   weather[0].get("main", "Clear") if weather else "Clear",
            "description": weather[0].get("description", "") if weather else "",
            "city":        c.get("name", cfg["location"]),
            "units":       cfg["units"],
            "forecast":    forecast,
        }
        _weather["fetched"] = now
        return _weather["data"]
    except Exception as e:
        log.error("Weather fetch error: %s", e)
        return {"error": str(e)}


# ── Sports (same parsing as the Pi app) ────────────────────────────────────────
_sports = {"mode": None, "game": None, "fetched": 0}


def _sports_mode():
    if _sports["mode"] is None:
        from modes.sports import SportsMode
        _sports["mode"] = SportsMode(display=None, config={"sports": dict(config["sports"], enabled=True),
                                                          "image_processing": {"cache_images": False}})
    return _sports["mode"]


def get_sports():
    game = _sports["game"]
    live = bool(game and game.get("state") == "in")
    ttl = int(config["sports"].get("update_interval", 60)) if live else 600
    if _sports["fetched"] and time.time() - _sports["fetched"] < ttl:
        return game
    mode = _sports_mode()
    game = mode._fetch_game_data()
    if game is None and mode.fetch_failed:
        return _sports["game"]  # keep last good data through an outage
    _sports["game"] = game
    _sports["fetched"] = time.time()
    return game


# ── Shared state between the web UI and the Matrix Portal ─────────────────────
_state_lock = threading.Lock()
_state = {
    "mode": config["display"]["mode"] if config["display"]["mode"] in MATRIX_MODES else "music",
    "mode_seq": 0,
    "brightness": int(config["display"]["brightness"]),
    "command": None,
    "command_seq": 0,
    "device": {},          # what the device last reported
    "device_seen": 0,
}
START_TIME = time.time()
DEVICE_TIMEOUT = 30  # seconds without a poll = device offline


def _device_online():
    return time.time() - _state["device_seen"] < DEVICE_TIMEOUT


def _track_for_device(track):
    if not track:
        return None
    return {
        "track_id":    track.get("track_id", ""),
        "title":       track.get("track_name", ""),
        "artist":      track.get("artist_name", ""),
        "art_url":     track.get("album_art_url", ""),
        "art_version": spotify_mgr.art_version,
        "progress_ms": track.get("progress_ms", 0) or 0,
        "duration_ms": track.get("duration_ms", 0) or 0,
        "is_playing":  bool(track.get("is_playing")),
    }


# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)
app.secret_key = config["web"]["secret_key"]
CORS(app)


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("authenticated"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return wrapper


# ── Matrix Portal endpoints ────────────────────────────────────────────────────

@app.get("/api/matrix/status")
def matrix_status():
    """Everything the device needs in one small reply. The device reports its
    own state in the query string so the dashboard shows what's on screen."""
    args = request.args
    with _state_lock:
        if args.get("mode"):
            _state["device"] = {
                "mode": args.get("mode"),
                "manual": args.get("manual") == "1",
                "brightness": int(args.get("brightness", _state["brightness"])),
                "board": args.get("board", ""),
            }
            _state["device_seen"] = time.time()
        reply = {k: _state[k] for k in ("mode", "mode_seq", "brightness", "command", "command_seq")}
    reply["track"] = _track_for_device(spotify_mgr.track())
    return jsonify(reply)


@app.get("/api/matrix/track")
def matrix_track():
    # Kept for older firmware; new firmware gets the track from /status
    track = _track_for_device(spotify_mgr.track()) or {"is_playing": False}
    return jsonify(track)


@app.get("/api/matrix/album_art.bmp")
def matrix_album_art():
    data = spotify_mgr.art_bmp()
    if data is None:
        return "", 204
    return send_file(io.BytesIO(data), mimetype="image/bmp", download_name="album_art.bmp")


@app.get("/api/matrix/weather")
def matrix_weather():
    return jsonify(get_weather())


@app.get("/api/matrix/sports")
def matrix_sports():
    game = get_sports()
    if isinstance(game, dict):
        game = json.loads(json.dumps(game))  # tuples (colours) -> lists
    return jsonify({"game": game})


# ── Web dashboard API (same shape as the Pi app) ──────────────────────────────

@app.get("/api/status")
def web_status():
    track = spotify_mgr.track()
    online = _device_online()
    device = _state["device"] if online else {}
    current_track = None
    if track:
        current_track = {
            "track_name":    track.get("track_name", ""),
            "artist_name":   track.get("artist_name", ""),
            "album_name":    track.get("album_name", ""),
            "album_art_url": track.get("album_art_url", ""),
            "is_playing":    bool(track.get("is_playing")),
        }
    return jsonify({
        "running":           True,
        "current_mode":      device.get("mode", _state["mode"]),
        "available_modes":   MATRIX_MODES,
        "brightness":        device.get("brightness", _state["brightness"]),
        "spotify_playing":   bool(track and track.get("is_playing")),
        "spotify_connected": spotify_mgr.connected,
        "spotify_error":     spotify_mgr.error,
        "manual_mode":       device.get("manual", False),
        "current_track":     current_track,
        "uptime":            time.time() - START_TIME,
        "device":            {"online": online, "board": _state["device"].get("board", ""),
                              "last_seen": _state["device_seen"] or None},
        "quick_settings":    False,   # the admin panel has all settings
    })


@app.get("/api/spotify/current")
def web_spotify_current():
    track = spotify_mgr.track()
    if not track:
        return jsonify({"message": "Nothing playing"})
    return jsonify(track)


@app.post("/api/mode")
def set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "")
    if mode not in MATRIX_MODES:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400
    with _state_lock:
        _state["mode"] = mode
        _state["mode_seq"] += 1
    return jsonify({"status": "success", "mode": mode})


@app.post("/api/brightness")
def set_brightness():
    data = request.get_json(silent=True) or {}
    try:
        brightness = max(0, min(100, int(data.get("brightness", 50))))
    except (TypeError, ValueError):
        return jsonify({"error": "brightness must be a number"}), 400
    with _state_lock:
        _state["brightness"] = brightness
    return jsonify({"status": "success", "brightness": brightness})


def _command(name):
    with _state_lock:
        _state["command"] = name
        _state["command_seq"] += 1
    if not _device_online():
        return jsonify({"error": "Matrix Portal hasn't checked in recently"}), 503
    return jsonify({"status": "success", "message": f"Sent to the Matrix Portal"})


@app.get("/api/display/test")
def display_test():
    return _command("test_pattern")


@app.get("/api/display/clear")
def display_clear():
    return _command("clear")


# ── Login ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    user_ok = hmac.compare_digest(str(data.get("username", "")), str(config["web"]["admin_username"]))
    pw_ok = hmac.compare_digest(str(data.get("password", "")), str(config["web"]["admin_password"]))
    if user_ok and pw_ok:
        session["authenticated"] = True
        return jsonify({"status": "success"})
    log.warning("Failed admin login for %r", data.get("username"))
    return jsonify({"error": "Invalid credentials"}), 401


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"status": "success"})


@app.get("/api/auth/check")
def auth_check():
    ok = bool(session.get("authenticated"))
    reply = {"authenticated": ok}
    if ok:
        reply["default_password"] = config["web"]["admin_password"] in ("admin", "changeme")
    return jsonify(reply)


# ── Admin config ───────────────────────────────────────────────────────────────

ADMIN_SCHEMA = {
    "subtitle": "Matrix Portal companion",
    "modes": [["music", "Music (album art)"], ["clock", "Clock"], ["weather", "Weather"],
              ["sports", "Sports"], ["screensaver", "Screensaver"]],
    "sections": [
        {"id": "general", "icon": "🎛️", "title": "General", "desc": "What the Matrix Portal shows.",
         "cards": [{"title": "Display", "fields": [
             {"path": "display.brightness", "label": "Brightness", "type": "range", "min": 0, "max": 100,
              "def": 50, "suffix": "%", "help": "0 turns the panel off."},
             {"path": "display.mode", "label": "Mode after the companion restarts", "type": "select",
              "def": "music", "options": [["music", "Music (album art)"], ["clock", "Clock"],
                                          ["weather", "Weather"], ["sports", "Sports"],
                                          ["screensaver", "Screensaver"]]},
         ], "note": "Clock style, time format, auto-switching and schedules are set in the board's "
                    "<code>settings.toml</code>."}]},
        {"id": "spotify", "icon": "🎵", "title": "Spotify", "desc": "Credentials from developer.spotify.com/dashboard.",
         "cards": [{"title": "Connection", "status": "spotify", "fields": [
             {"path": "spotify.client_id", "label": "Client ID", "type": "text"},
             {"path": "spotify.client_secret", "label": "Client secret", "type": "secret"},
             {"path": "spotify.redirect_uri", "label": "Redirect URI", "type": "text",
              "def": "http://127.0.0.1:8888/callback",
              "help": "Must exactly match the one in your Spotify app settings."},
         ], "note": "After changing credentials, sign in once on the companion machine with "
                    "<code>python companion.py --auth</code>. The companion reconnects within a minute."}]},
        {"id": "weather", "icon": "🌤️", "title": "Weather", "desc": "Uses a free OpenWeatherMap API key.",
         "cards": [{"title": "Weather", "fields": [
             {"path": "weather.api_key", "label": "OpenWeatherMap API key", "type": "secret"},
             {"path": "weather.location", "label": "Location", "type": "text",
              "help": "City,State,Country, e.g. <code>Chicago,IL,US</code>"},
             {"path": "weather.units", "label": "Units", "type": "segmented", "def": "imperial",
              "options": [["imperial", "°F"], ["metric", "°C"]]},
         ]}]},
        {"id": "sports", "icon": "🏈", "title": "Sports", "desc": "Live scores from ESPN. No API key needed.",
         "cards": [{"title": "Team", "fields": [
             {"path": "sports.league", "label": "League", "type": "select", "def": "NBA",
              "options": [[x, x] for x in LEAGUES]},
             {"path": "sports.team", "label": "Team abbreviation", "type": "text", "upper": True,
              "help": "As ESPN shows it, e.g. <code>GB</code>, <code>CHI</code>, <code>LAL</code>."},
             {"path": "sports.update_interval", "label": "Refresh during a live game every", "type": "number",
              "min": 15, "max": 600, "def": 60, "unit": "s"},
         ]}]},
        {"id": "art", "icon": "🖼️", "title": "Album art", "desc": "Tuning for how covers look on LEDs.",
         "cards": [{"title": "Image processing", "fields": [
             {"path": "image_processing.enhance_contrast", "label": "Boost contrast", "type": "toggle", "def": True},
             {"path": "image_processing.contrast_factor", "label": "Contrast amount", "type": "number",
              "min": 1, "max": 2, "step": 0.05, "def": 1.2, "dependsOn": "image_processing.enhance_contrast"},
             {"path": "image_processing.enhance_saturation", "label": "Boost saturation", "type": "toggle", "def": True},
             {"path": "image_processing.saturation_factor", "label": "Saturation amount", "type": "number",
              "min": 1, "max": 2, "step": 0.05, "def": 1.1, "dependsOn": "image_processing.enhance_saturation"},
         ]}]},
        {"id": "security", "icon": "🔒", "title": "Security", "desc": "Who can change these settings.",
         "cards": [{"title": "Admin login", "fields": [
             {"path": "web.admin_username", "label": "Username", "type": "text", "def": "admin"},
             {"path": "web.admin_password", "label": "New password", "type": "newpassword",
              "help": "Leave blank to keep the current password."},
         ]}, {"title": "Web server", "badge": ["Restart required", "warn"], "fields": [
             {"path": "web.port", "label": "Port", "type": "number", "min": 1, "max": 65535, "def": 5001},
         ]}]},
    ],
}


def validate(cfg):
    errors = []
    if not isinstance(cfg, dict):
        return ["Configuration must be a JSON object"]
    for section in ("spotify", "weather", "sports", "display", "web"):
        if section in cfg and not isinstance(cfg[section], dict):
            errors.append(f"{section} must be an object")
    disp = cfg.get("display", {})
    b = disp.get("brightness", 50)
    if not isinstance(b, (int, float)) or not 0 <= b <= 100:
        errors.append("display.brightness must be between 0 and 100")
    if disp.get("mode", "music") not in MATRIX_MODES:
        errors.append(f"display.mode must be one of {', '.join(MATRIX_MODES)}")
    port = cfg.get("web", {}).get("port", 5001)
    if not isinstance(port, int) or not 1 <= port <= 65535:
        errors.append("web.port must be between 1 and 65535")
    if cfg.get("sports", {}).get("league", "NBA") not in LEAGUES:
        errors.append(f"sports.league must be one of {', '.join(LEAGUES)}")
    return errors


@app.get("/api/admin/schema")
def admin_schema():
    return jsonify(ADMIN_SCHEMA)


@app.get("/api/admin/config")
@login_required
def admin_get_config():
    safe = copy.deepcopy(config)
    safe["web"].pop("secret_key", None)
    return jsonify(safe)


@app.post("/api/admin/config/validate")
@login_required
def admin_validate():
    errors = validate(request.get_json(silent=True))
    return (jsonify({"valid": True}) if not errors else (jsonify({"valid": False, "errors": errors}), 400))


@app.post("/api/admin/config")
@login_required
def admin_save_config():
    new = request.get_json(silent=True)
    errors = validate(new)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    old = copy.deepcopy(config)
    new = _merge_defaults(copy.deepcopy(new))
    new["web"]["secret_key"] = config["web"]["secret_key"]
    if not new["web"].get("admin_password"):
        new["web"]["admin_password"] = config["web"]["admin_password"]
    config.clear()
    config.update(new)
    save_config(config)

    # Apply live
    if config["spotify"] != old["spotify"] or config["image_processing"] != old["image_processing"]:
        spotify_mgr.reconfigure()
    if config["weather"] != old["weather"]:
        _weather["fetched"] = 0
    if config["sports"] != old["sports"]:
        _sports.update(mode=None, game=None, fetched=0)
    with _state_lock:
        if config["display"]["brightness"] != old["display"]["brightness"]:
            _state["brightness"] = int(config["display"]["brightness"])
    return jsonify({"status": "success"})


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return send_from_directory(str(WEB_DIR), "index.html")


@app.get("/admin")
def admin_page():
    return send_from_directory(str(WEB_DIR), "admin.html")


@app.get("/login")
def login_page():
    return send_from_directory(str(WEB_DIR), "login.html")


@app.get("/<path:filename>")
def static_web(filename):
    return send_from_directory(str(WEB_DIR), filename)


# ── Server ─────────────────────────────────────────────────────────────────────

def advertise_mdns(port):
    """Advertise as 'matrixportal-companion.local' (optional 'zeroconf' package)."""
    try:
        import socket
        from zeroconf import Zeroconf, ServiceInfo
    except ImportError:
        print("(mDNS advertising disabled — 'pip install zeroconf' to enable)")
        return None
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        if local_ip.startswith("127."):
            # Find the LAN address by "connecting" a UDP socket (no packets sent)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            local_ip = s.getsockname()[0]
            s.close()
        zc = Zeroconf()
        zc.register_service(ServiceInfo(
            "_http._tcp.local.", "matrixportal-companion._http._tcp.local.",
            addresses=[socket.inet_aton(local_ip)], port=port, properties={"path": "/"},
            server="matrixportal-companion.local."))
        print(f"mDNS: advertising matrixportal-companion.local → {local_ip}:{port}")
        return zc
    except Exception as e:
        print(f"(mDNS advertising failed: {e})")
        return None


def run_server(host, port):
    threading.Thread(target=spotify_mgr.poll_forever, daemon=True).start()
    _zc = advertise_mdns(port)  # noqa: F841 (keep a reference alive)
    print(f"\n{'=' * 55}")
    print("  Matrix Portal Companion")
    print(f"  Dashboard     → http://{host}:{port}/")
    print(f"  Admin panel   → http://{host}:{port}/admin")
    print(f"  COMPANION_URL → http://<this-computer's-ip>:{port}")
    if _zc is not None:
        print(f"           or → http://matrixportal-companion.local:{port}")
    if config["web"]["admin_password"] in ("admin", "changeme"):
        print("  ⚠️  Default admin password - change it in the admin panel")
    print(f"{'=' * 55}\n")
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Matrix Portal Companion Server")
    parser.add_argument("--auth", action="store_true", help="Sign in to Spotify")
    parser.add_argument("--host", default=config["web"].get("host", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=config["web"].get("port", 5001))
    args = parser.parse_args()
    if args.auth:
        spotify_mgr.authenticate()
    else:
        run_server(args.host, args.port)
