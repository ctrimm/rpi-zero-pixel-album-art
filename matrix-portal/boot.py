# boot.py — runs before code.py on every power-on
# To edit files on CIRCUITPY, hold BOOT button while plugging in USB
# to re-enable the USB drive temporarily.

import supervisor

# Disable auto-reload so the display isn't interrupted by file saves.
# Comment this out during development if you want live reload.
supervisor.runtime.autoreload = False
