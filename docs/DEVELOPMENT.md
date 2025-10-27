# Development Guide

**Develop and test on your Mac without deploying to Raspberry Pi!**

This guide shows you how to run the LED Matrix Display with a visual simulator on your development machine, allowing for rapid iteration and debugging without constantly deploying to the Pi.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Visual Simulator](#visual-simulator)
3. [Development Setup](#development-setup)
4. [Testing Features](#testing-features)
5. [Debugging Tips](#debugging-tips)
6. [Development Workflow](#development-workflow)

---

## Quick Start

### On Your Mac (or Windows/Linux)

```bash
# 1. Clone the repository
git clone https://github.com/ctrimm/rpi-zero-pixel-album-art.git
cd rpi-zero-pixel-album-art

# 2. Install Python dependencies
pip3 install -r requirements.txt

# 3. Copy development config
cp config.dev.json config.json

# 4. Add your Spotify credentials to config.json
nano config.json
# Add your Client ID and Client Secret

# 5. Authenticate with Spotify
python3 src/spotify_auth.py

# 6. Run in development mode
python3 dev_run.py
```

**A window will pop up showing the 64x64 LED matrix!** 🎉

All features work exactly like they would on the real Pi, but you see the output in a window on your Mac.

---

## Visual Simulator

### What It Does

The LED Matrix Simulator provides:

✅ **Visual Window** - Shows exactly what would appear on the LED matrix
✅ **Real-time Updates** - Changes appear instantly
✅ **Perfect Emulation** - Same 64x64 resolution as the real display
✅ **All Features Work** - Spotify, Weather on 8s, modes, etc.
✅ **Fast Iteration** - No deployment needed!

### How It Looks

```
┌─────────────────────────────────────┐
│   LED Matrix Simulator (64x64)      │
├─────────────────────────────────────┤
│                                     │
│     [Your album art or display]     │
│                                     │
│        Shown pixel-perfect          │
│         in a window                 │
│                                     │
├─────────────────────────────────────┤
│ LED Matrix Emulator - 64x64 | 10x   │
│ Development Mode - Real-time updates│
└─────────────────────────────────────┘
```

Each pixel is enlarged (10x by default) so you can see details clearly.

### Pixel Size

Adjust how big each LED pixel appears:

```json
{
  "display": {
    "simulator_pixel_size": 10
  }
}
```

- `8` - Smaller window, harder to see details
- `10` - Default, good balance (640x640 window)
- `12` - Larger, easier to see (768x768 window)
- `15` - Very large, great for presentations

---

## Development Setup

### Prerequisites

**On Mac:**

⚠️ **IMPORTANT:** Modern macOS requires using a virtual environment!

```bash
# Quick setup (recommended)
bash setup_mac.sh

# This creates a virtual environment and installs all dependencies
# See docs/MAC_SETUP.md for detailed instructions
```

**Or manual setup:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it (do this every time you start a new terminal)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**On Windows:**
- Download Python 3.7+ from python.org (includes Tkinter)

**On Linux:**
```bash
sudo apt install python3-tk
```

### Install Dependencies

```bash
# Production dependencies
pip3 install -r requirements.txt

# Development dependencies (optional but recommended)
pip3 install -r requirements-dev.txt
```

### Configuration

**Use the development config:**

```bash
cp config.dev.json config.json
```

**Key differences from production config:**

```json
{
  "display": {
    "simulator_pixel_size": 10,  // How big each pixel appears
  },
  "logging": {
    "level": "DEBUG",  // More verbose logging
    "file": "dev_spotify-display.log"
  },
  "web_server": {
    "debug": true,  // Better error messages
    "host": "127.0.0.1"  // Localhost only
  },
  "weather_on_8s": {
    "display_duration": 45  // Shorter for faster testing
  }
}
```

---

## Testing Features

### Test Spotify Integration

**1. Start the simulator:**
```bash
python3 dev_run.py
```

**2. Play music on Spotify**
- Use any device (phone, computer, web player)
- Album art should appear in simulator window!

**3. Test mode switching:**

Open another terminal:
```bash
# Switch to clock mode
curl http://localhost:5000/api/mode -X POST \
  -H "Content-Type: application/json" \
  -d '{"mode":"clock"}'

# Back to music
curl http://localhost:5000/api/mode -X POST \
  -H "Content-Type: application/json" \
  -d '{"mode":"music"}'
```

### Test Weather on the 8s

**Quick test without waiting:**

Edit `src/modes/weather_on_the_8s.py`:

```python
def should_activate(self):
    """Force activation for testing"""
    return True  # Always activate
```

Or wait for the next trigger time (:08, :18, :28, :38, :48, :58).

### Test Display Patterns

```bash
# In Python console
python3
```

```python
import os
os.environ['LED_SIMULATOR'] = '1'

from src.led_simulator import SimulatedLEDDisplay
from PIL import Image, ImageDraw

config = {'rows': 64, 'cols': 64, 'simulator_pixel_size': 10}
display = SimulatedLEDDisplay(config)

# Test pattern
display.test_pattern()

# Custom image
img = Image.new('RGB', (64, 64), 'blue')
draw = ImageDraw.Draw(img)
draw.text((10, 20), "Hello!", fill='white')
display.display_image(img)
```

---

## Debugging Tips

### Enable Debug Logging

In `config.json`:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

### View Logs

```bash
# Watch logs in real-time
tail -f dev_spotify-display.log
```

### Python Debugger

```python
# Add breakpoints in code
import pdb; pdb.set_trace()

# Or use ipdb (if installed)
import ipdb; ipdb.set_trace()
```

### Common Issues

**Problem:** Simulator window doesn't open

**Solution:**
```bash
# Check Tkinter is installed
python3 -c "import tkinter; tkinter._test()"

# Should open a small test window
```

**Problem:** "Module not found" errors

**Solution:**
```bash
# Install dependencies
pip3 install -r requirements.txt

# Check Python path
python3 -c "import sys; print(sys.path)"
```

**Problem:** Spotify not connecting

**Solution:**
```bash
# Re-authenticate
python3 src/spotify_auth.py

# Check credentials
cat config.json | grep spotify -A 5
```

---

## Development Workflow

### Recommended Workflow

```
┌─────────────────────────────────────────────┐
│ 1. Make changes to code on Mac              │
│    └─ Edit Python files in src/            │
│                                             │
│ 2. Test with simulator                      │
│    └─ python3 dev_run.py                   │
│    └─ See changes instantly                 │
│                                             │
│ 3. Debug and iterate                        │
│    └─ Check logs                            │
│    └─ Test different scenarios              │
│                                             │
│ 4. When working: Deploy to Pi               │
│    └─ git push                              │
│    └─ ssh into Pi                           │
│    └─ git pull                              │
│    └─ sudo systemctl restart spotify-display│
│                                             │
│ 5. Verify on real hardware                  │
│    └─ Check actual LED display              │
│    └─ Verify brightness, colors, etc.       │
└─────────────────────────────────────────────┘
```

### Fast Iteration Loop

**For rapid development:**

```bash
# Terminal 1: Run simulator
python3 dev_run.py

# Terminal 2: Watch logs
tail -f dev_spotify-display.log

# Terminal 3: Make changes
vim src/modes/weather_on_the_8s.py

# Kill and restart dev_run.py to see changes
```

### Testing Modes

```bash
# Create a test script
cat > test_mode.py << 'EOF'
import os
os.environ['LED_SIMULATOR'] = '1'

from src.led_simulator import SimulatedLEDDisplay
from src.modes.weather_on_the_8s import WeatherOnThe8sMode
import json

# Load config
with open('config.json') as f:
    config = json.load(f)

# Initialize
display = SimulatedLEDDisplay(config['display'])
weather = WeatherOnThe8sMode(display, config)

# Force display
weather.start_display()

# Run until complete
import time
while weather.is_active():
    weather.update()
    time.sleep(1)

print("Done!")
EOF

python3 test_mode.py
```

### Web Development

The web interface works in development mode:

```bash
# Start dev server
python3 dev_run.py

# Open browser
open http://localhost:5000
```

Changes to web files (HTML/CSS/JS) are loaded on refresh.

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-new-feature

# Make changes, test with simulator
# ... code changes ...

# Commit
git add .
git commit -m "Add new feature"

# Push to remote
git push origin feature/my-new-feature

# Deploy to Pi for testing
ssh pi@your-pi-ip
cd ~/rpi-zero-pixel-album-art
git fetch
git checkout feature/my-new-feature
sudo systemctl restart spotify-display
```

---

## Environment Variables

Control behavior with environment variables:

```bash
# Force simulator mode (even on Pi)
export LED_SIMULATOR=1
python3 src/main.py

# Use real hardware (even on Mac, will fail gracefully)
export LED_SIMULATOR=0
python3 src/main.py

# Increase log verbosity
export LOG_LEVEL=DEBUG
python3 dev_run.py
```

---

## IDE Setup

### VS Code

**Recommended extensions:**
- Python
- Pylance
- GitLens

**.vscode/settings.json:**
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

**.vscode/launch.json:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Dev Mode",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/dev_run.py",
      "console": "integratedTerminal",
      "env": {
        "LED_SIMULATOR": "1"
      }
    }
  ]
}
```

Now you can press F5 to start debugging!

### PyCharm

**Run Configuration:**
1. Run → Edit Configurations
2. Add new Python configuration
3. Script path: `/path/to/dev_run.py`
4. Environment variables: `LED_SIMULATOR=1`
5. Python interpreter: Select your Python 3.7+

---

## Testing Without Spotify

For testing display without Spotify Premium:

```python
# Mock Spotify data
from src.led_simulator import SimulatedLEDDisplay
from src.modes.music import MusicMode

# Create mock Spotify client
class MockSpotify:
    def get_current_track(self):
        return {
            'track_id': 'test123',
            'track_name': 'Test Track',
            'artist_name': 'Test Artist',
            'album_name': 'Test Album',
            'album_art_url': 'https://i.scdn.co/image/ab67616d0000b273...',
            'is_playing': True
        }

    def is_playing(self):
        return True

# Use it
mock_spotify = MockSpotify()
# ... rest of your test
```

---

## Performance Profiling

```bash
# Profile code
python3 -m cProfile -o profile.stats dev_run.py

# View results
python3 -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('time').print_stats(20)"
```

---

## Tips & Tricks

💡 **Tip:** Use `config.dev.json` for development, `config.json` for production

💡 **Tip:** Simulator window stays open even if app crashes - easier debugging

💡 **Tip:** Take screenshots of simulator window to document features

💡 **Tip:** Adjust `simulator_pixel_size` based on your screen resolution

💡 **Tip:** Use `DEBUG` logging during development, `INFO` in production

💡 **Tip:** Test Weather on 8s by setting `should_activate()` to always return True

---

## Next Steps

Once your feature works in the simulator:

1. ✅ Test thoroughly with different scenarios
2. ✅ Check logs for errors
3. ✅ Verify web interface works
4. ✅ Commit your changes
5. ✅ Deploy to actual Raspberry Pi
6. ✅ Test on real LED hardware
7. ✅ Adjust brightness/colors if needed

---

**Happy developing! 🚀**

The simulator makes development 10x faster. Code → Test → Iterate without touching the Pi!
