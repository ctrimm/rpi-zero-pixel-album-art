# Retro Screensavers

Add a nostalgic touch to your LED matrix display with classic screensavers! This feature brings two iconic screensavers to your Raspberry Pi LED matrix: Windows 3D Pipes and the bouncing DVD logo.

## Features

### 🔧 Windows Pipes Screensaver
Relive the classic Windows 95/98/XP screensaver with colorful pipes growing across your display!

**Features:**
- Multiple pipes growing simultaneously
- Random direction changes creating organic patterns
- Vibrant rainbow of colors
- Smooth color transitions and gradients
- Configurable trail fade effect
- Automatic restart when all pipes exit the screen

### 📀 DVD Logo Screensaver
Remember waiting for the DVD logo to hit the corner perfectly? Now you can watch it happen!

**Features:**
- Classic bouncing logo animation
- Random color changes on edge hits
- **Special rainbow mode** when hitting a corner perfectly!
- Corner hit counter displayed on screen
- Configurable logo size and speed
- Black "DVD" text on colored background

## Configuration

Add the screensavers section to your `config.json`:

```json
{
  "screensavers": {
    "pipes": {
      "enabled": true,
      "num_pipes": 4,
      "speed": 0.05,
      "fade_trail": true,
      "background_color": [0, 0, 0]
    },
    "dvd_logo": {
      "enabled": true,
      "speed": 0.05,
      "logo_width": 16,
      "logo_height": 8
    }
  }
}
```

### Pipes Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable pipes screensaver |
| `num_pipes` | integer | `4` | Number of pipes growing simultaneously (1-8 recommended) |
| `speed` | float | `0.05` | Update interval in seconds (lower = faster) |
| `fade_trail` | boolean | `true` | Enable fading trail effect for smoother look |
| `background_color` | array | `[0, 0, 0]` | RGB background color (black by default) |

### DVD Logo Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable DVD logo screensaver |
| `speed` | float | `0.05` | Update interval in seconds (lower = faster) |
| `logo_width` | integer | `16` | Width of the logo in pixels |
| `logo_height` | integer | `8` | Height of the logo in pixels |

## Usage

### Manual Mode Switching

You can switch to the screensavers manually using the web interface or API:

**Via Web Interface:**
1. Open the web interface (usually `http://<raspberry-pi-ip>:5000`)
2. Select "Pipes" or "DVD Logo" from the mode selector
3. Click "Switch Mode"

**Via API:**
```bash
# Switch to pipes screensaver
curl -X POST http://<raspberry-pi-ip>:5000/api/mode -H "Content-Type: application/json" -d '{"mode": "pipes"}'

# Switch to DVD logo screensaver
curl -X POST http://<raspberry-pi-ip>:5000/api/mode -H "Content-Type: application/json" -d '{"mode": "dvd_logo"}'
```

### Scheduled Activation

Add schedule entries to your `config.json` to automatically activate screensavers at specific times:

```json
{
  "modes": {
    "schedule": {
      "pipes": {
        "enabled": true,
        "times": ["22:00-23:00", "02:00-06:00"]
      },
      "dvd_logo": {
        "enabled": true,
        "times": ["01:00-02:00"]
      }
    }
  }
}
```

### Fallback/Idle Mode

Use screensavers when nothing else is active by setting them as fallback:

```json
{
  "modes": {
    "default": "dvd_logo",
    "schedule": {
      "pipes": {
        "enabled": true,
        "fallback": true
      }
    }
  }
}
```

## Tips & Tricks

### Optimizing Performance

**For Raspberry Pi Zero:**
- Reduce `num_pipes` to 2-3 for smoother animation
- Increase `speed` to 0.1 or 0.15 for better performance
- Disable `fade_trail` in pipes mode

**For Raspberry Pi 3/4:**
- Use default settings or increase `num_pipes` to 6-8
- Decrease `speed` to 0.03 for ultra-smooth animation

### Creating Different Effects

**Slow, Meditative Pipes:**
```json
{
  "pipes": {
    "num_pipes": 2,
    "speed": 0.15,
    "fade_trail": true
  }
}
```

**Chaotic Pipe Explosion:**
```json
{
  "pipes": {
    "num_pipes": 8,
    "speed": 0.02,
    "fade_trail": false
  }
}
```

**Fast DVD Logo:**
```json
{
  "dvd_logo": {
    "speed": 0.02,
    "logo_width": 12,
    "logo_height": 6
  }
}
```

**Large, Slow DVD Logo:**
```json
{
  "dvd_logo": {
    "speed": 0.1,
    "logo_width": 20,
    "logo_height": 10
  }
}
```

## Easter Eggs

### DVD Logo Corner Hits
The DVD logo has a special feature: when it hits a corner **exactly** (both horizontal and vertical edges at the same time), it enters **rainbow mode**! The logo will cycle through rainbow colors until it hits another edge, then return to random color changes.

Track your corner hits with the counter displayed in the top-left corner!

### Pipe Color Evolution
Pipes slightly mutate their colors as they grow, creating organic color gradients. Watch closely to see the subtle shifts!

## Development & Testing

### Testing in Simulator

The screensavers work great in the LED simulator for development:

```bash
# Mac/Linux
./run_mac.sh pipes

# Or
source venv/bin/activate
LED_SIMULATOR=1 python3 src/main.py
```

Then manually switch to the screensaver mode via the web interface.

### Creating Your Own Screensaver

Want to create your own screensaver? Follow this pattern:

1. Create a new file in `src/modes/your_screensaver.py`
2. Implement a class with `__init__(self, display, config)` and `update(self)` methods
3. Add configuration to `config.json` under `screensavers.your_screensaver`
4. Import and register your mode in `src/main.py`

Example template:

```python
import logging
from PIL import Image, ImageDraw

class YourScreensaver:
    def __init__(self, display, config):
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config.get('screensavers', {}).get('your_screensaver', {})

        # Get display size
        display_size = self.display.get_size()
        self.width = display_size[0]
        self.height = display_size[1]

        # Your initialization here

    def update(self):
        """Update screensaver - called repeatedly"""
        try:
            # Your animation logic here

            # Create image
            image = Image.new('RGB', (self.width, self.height), (0, 0, 0))
            draw = ImageDraw.Draw(image)

            # Draw your screensaver
            # ...

            # Display it
            self.display.display_image(image)

        except Exception as e:
            self.logger.error(f"Error in screensaver: {e}", exc_info=True)
```

## Troubleshooting

### Pipes are too slow/fast
Adjust the `speed` parameter in config.json. Lower values = faster animation.

### Pipes die too quickly
- Check that `num_pipes` isn't too high for your display size
- Pipes naturally die when they hit the edges - this is expected behavior
- The system automatically creates new pipes when all pipes die

### DVD logo goes through edges
This shouldn't happen. If it does, check:
- Logo size (`logo_width` and `logo_height`) vs display size
- Verify you're using the latest version of the code

### Corner hits not detected
Corner hits require **perfect** timing - both edges must be hit in the exact same frame. This is intentionally rare (just like the real DVD screensaver)!

### Screensaver won't activate
- Verify `enabled: true` in config.json
- Check that the mode is available: `curl http://<pi-ip>:5000/api/status`
- Check logs for any initialization errors
- Ensure you're running the latest code from the branch

## Performance Notes

Both screensavers are optimized for LED matrices:
- Efficient PIL-based rendering
- Rate-limited updates to prevent CPU overuse
- Designed for 64x64 displays but work with any size
- Minimal memory footprint

## Credits

Inspired by:
- **Windows Pipes**: Original screensaver from Windows NT/95/98/XP
- **DVD Logo**: The iconic bouncing logo from DVD players and screensavers

Recreated with love for the retro computing aesthetic! 🎮✨
