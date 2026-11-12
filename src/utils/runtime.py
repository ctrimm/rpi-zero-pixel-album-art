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
    """Sleep up to `seconds`, returning early if wake_modes() is called.

    Returns True if woken early (e.g. the mode was switched away).
    """
    if seconds <= 0:
        return _wake_event.is_set()
    return _wake_event.wait(seconds)


def wait_for_frame(state, interval):
    """Frame pacing for animations.

    Sleeps until the next frame is due (instead of returning immediately and
    letting the display loop spin), so the loop wakes once per frame rather
    than ~200 times a second. Keeps a fixed cadence without drift.

    Args:
        state: dict holding 'next' (the monotonic time the next frame is due)
        interval: seconds per frame

    Returns:
        True if the frame should be drawn, False if a mode switch interrupted.
    """
    import time
    now = time.monotonic()
    due = state.get('next', now)
    if due > now and mode_sleep(due - now):
        return False
    now = time.monotonic()
    # If we fell more than a frame behind (slow Pi, GC pause), resync rather
    # than bursting several frames to catch up.
    state['next'] = due + interval if now - due < interval else now + interval
    return True


def wake_modes():
    """Interrupt any in-progress mode_sleep() (e.g. on a mode switch)."""
    _wake_event.set()


def reset_wake():
    """Re-arm mode_sleep() after a wake (called by the display loop)."""
    _wake_event.clear()
