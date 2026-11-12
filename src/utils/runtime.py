"""
Runtime helpers shared across the app.

- app_home(): the home directory that owns the Spotify token / image caches.
  On a Pi the service starts as root (the LED library needs root for
  flicker-free timing) and then drops privileges to a normal user, so the
  caches must live in *that* user's home, not /root.
- service_user(): the unprivileged user the LED library should drop to.
- mode_sleep() / wake_modes(): an interruptible sleep for display modes, so a
  mode switch from the web UI takes effect immediately instead of waiting for
  the previous mode's sleep to finish.
"""

import os
import threading
from pathlib import Path

_wake_event = threading.Event()


def service_user():
    """Name of the non-root user the app should run/own files as, if known."""
    return os.environ.get('SPOTIFY_DISPLAY_USER') or os.environ.get('SUDO_USER') or None


def app_home():
    """Home directory used for caches (Spotify token, album art)."""
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        user = service_user()
        if user and user != 'root':
            try:
                import pwd
                return Path(pwd.getpwnam(user).pw_dir)
            except (KeyError, ImportError):
                pass
    return Path.home()


def cache_dir():
    """Base cache directory for the app."""
    return app_home() / '.cache' / 'spotify-display'


def mode_sleep(seconds):
    """Sleep up to `seconds`, returning early if wake_modes() is called."""
    _wake_event.wait(seconds)


def wake_modes():
    """Interrupt any in-progress mode_sleep() (e.g. on a mode switch)."""
    _wake_event.set()


def reset_wake():
    """Re-arm mode_sleep() after a wake (called by the display loop)."""
    _wake_event.clear()
