# storage_helper.py — tiny JSON cache helpers for the CIRCUITPY filesystem.
#
# Used to persist the last-good weather/sports/track payloads so a reboot can
# show real content immediately instead of placeholders until the first fetch.
#
# All operations are best-effort: if the filesystem is read-only (the UP button
# was held at boot) or the file is missing/corrupt, they quietly do nothing.
import json


def save_json(path, data):
    """Write data to path as JSON. Returns True on success, False otherwise."""
    try:
        with open(path, "w") as f:
            json.dump(data, f)
        return True
    except (OSError, ValueError):
        # OSError: read-only filesystem / no space. ValueError: not serializable.
        return False


def load_json(path):
    """Read JSON from path. Returns the data, or None if missing/unreadable."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
