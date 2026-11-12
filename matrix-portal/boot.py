# boot.py — runs before code.py on every power-on
#
# IMPORTANT: This remounts the filesystem as writable by CircuitPython code.
# This is required so the device can save album art BMPs to flash.
# As a side-effect, the CIRCUITPY USB drive becomes READ-ONLY on the host.
#
# To edit files on CIRCUITPY:
#   Hold the UP button (board.BUTTON_UP) while plugging in USB.
#   The drive will be writable from the host, but code cannot write files.

import storage
import digitalio
import board
import supervisor

supervisor.runtime.autoreload = False

# Check if UP button is held — if so, give USB write access for file editing
button = digitalio.DigitalInOut(board.BUTTON_UP)
button.switch_to_input(pull=digitalio.Pull.UP)

if button.value:
    # Button NOT held → normal run: code can write files, USB drive is read-only
    storage.remount("/", readonly=False)
# else: button held → USB drive is writable, but code cannot write files
