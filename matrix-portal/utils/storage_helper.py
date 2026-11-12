# storage_helper.py — tiny persistent caches on the CIRCUITPY filesystem.
#
# Used to persist the last-good weather/sports/track payloads and album art so
# a reboot can show real content immediately instead of placeholders.
#
# Flash wear: the CIRCUITPY drive is a FAT filesystem on flash rated for
# ~100k erase cycles, with no wear levelling. Writing the same file every few
# seconds (as the track cache used to, on every poll) would wear those sectors
# out within weeks. So writes only happen when the content actually changed,
# and at most once per `min_interval` per file; newer data waiting out the
# interval is kept and written later by flush().
#
# All operations are best-effort: if the filesystem is read-only (the UP button
# was held at boot) or the file is missing/corrupt, they quietly do nothing.
import json
import time

DEFAULT_MIN_INTERVAL = 900  # seconds between writes of the same file (15 min)

_last_written = {}   # path -> data last written (or loaded)
_last_time = {}      # path -> monotonic time of last write
_pending = {}        # path -> (data, is_bytes) waiting for its interval


def _write(path, data, is_bytes):
    try:
        if is_bytes:
            with open(path, "wb") as f:
                f.write(data)
        else:
            with open(path, "w") as f:
                json.dump(data, f)
        _last_written[path] = data
        _last_time[path] = time.monotonic()
        return True
    except (OSError, ValueError):
        # OSError: read-only filesystem / no space. ValueError: not serializable.
        return False


def _save(path, data, is_bytes, min_interval):
    if _last_written.get(path) == data:
        _pending.pop(path, None)
        return False  # unchanged: no write
    last = _last_time.get(path)
    if last is not None and time.monotonic() - last < min_interval:
        _pending[path] = (data, is_bytes)  # write later (flush)
        return False
    _pending.pop(path, None)
    return _write(path, data, is_bytes)


def save_json(path, data, min_interval=DEFAULT_MIN_INTERVAL):
    """Persist JSON if it changed, rate-limited per file. Returns True if written."""
    return _save(path, data, False, min_interval)


def save_bytes(path, data, min_interval=DEFAULT_MIN_INTERVAL):
    """Persist raw bytes (e.g. album art) if changed, rate-limited per file."""
    return _save(path, bytes(data), True, min_interval)


def flush(min_interval=DEFAULT_MIN_INTERVAL):
    """Write pending data whose interval has elapsed. Call occasionally."""
    if not _pending:
        return
    now = time.monotonic()
    for path in list(_pending):
        if now - _last_time.get(path, 0) >= min_interval:
            data, is_bytes = _pending.pop(path)
            _write(path, data, is_bytes)


def load_json(path):
    """Read JSON from path. Returns the data, or None if missing/unreadable."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
        _last_written[path] = data
        return data
    except (OSError, ValueError):
        return None


def load_bytes(path):
    """Read raw bytes from path, or None."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        _last_written[path] = data
        return data
    except OSError:
        return None
