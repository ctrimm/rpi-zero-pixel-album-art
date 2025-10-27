# Raspberry Pi Spotify LED Matrix Display

A standalone Raspberry Pi solution that displays album art, weather, and sports scores on a 64x64 LED matrix panel. No Home Assistant required - runs completely independently on your local network.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.7+-blue.svg)

## Features

- **Real-time Spotify Integration**: Automatically displays album art from your currently playing Spotify track
- **Multiple Display Modes**:
  - 🎵 Music: Album artwork with artist/track info
  - 🌤️ Weather: Current conditions and forecast
  - ⚽ Sports: Live scores and game updates
  - 🕐 Clock: Time and date display
  - 🔧 Pipes: Classic Windows 3D Pipes screensaver
  - 📀 DVD Logo: Bouncing DVD logo with rainbow corner hits
- **Web Interface**: Simple browser-based control accessible from any device on your network
- **Automatic Mode Switching**: Smart scheduling based on time and activity
- **Standalone Operation**: No cloud dependencies or Home Assistant required

## Hardware Requirements

### What You Need

**Core Components** (~$50-80):
- Raspberry Pi Zero 2 W ($15) or Raspberry Pi 4B 2GB ($45)
- MicroSD Card 32GB Class 10 ($8)
- Adafruit RGB Matrix Bonnet ($15) or generic adapter ($10)
- P3-2121 LED Matrix Panel 64x64 pixels (you have this)
- 5V 5A Power Supply ($15) - for panel power
- Power cable (you have this)

**Optional**:
- Frame/enclosure ($10-20)
- Diffuser panel for smoother image ($5)

### Where to Buy

**Option 1: Amazon (Best for Speed)**
- [Raspberry Pi Zero 2 W](https://amazon.com/s?k=raspberry+pi+zero+2+w) - $15-20
- [SanDisk 32GB MicroSD](https://amazon.com/dp/B08GY9NYRM) - $7-10
- [5V 5A Power Supply](https://amazon.com/s?k=5v+5a+power+supply) - $12-18

**Option 2: Adafruit (Best Quality)**
- [Raspberry Pi Zero 2 W](https://www.adafruit.com/product/5291) - $15
- [RGB Matrix Bonnet](https://www.adafruit.com/product/3211) - $15
- [5V 4A Power Supply](https://www.adafruit.com/product/1466) - $15

**Option 3: AliExpress (Best Price)**
- Generic RGB Matrix adapter boards - $8-12
- HUB75 cables and connectors - $3-5
- Slower shipping (2-4 weeks)

### Complete Budget Options

| Build Option | Total Cost | Best For |
|-------------|------------|----------|
| Pi Zero 2 W | ~$51 | Budget builds, low power |
| Pi 4B 2GB | ~$81 | Better performance, faster image processing |
| ESP32 Alternative | ~$39 | Ultra-low power, advanced users |

## Quick Start

### 1. Hardware Assembly

**Power Connection**:
1. Connect 5V power supply to LED panel power terminals (red=+5V, black=GND)
2. CRITICAL: Double-check polarity before powering on!

**Signal Connection**:
- Use Adafruit RGB Matrix Bonnet (easiest): Just plug onto Pi GPIO header
- OR manual wiring: See [wiring diagram](docs/WIRING.md) for pin connections

### 2. Software Installation

```bash
# Clone this repository
git clone https://github.com/yourusername/rpi-zero-pixel-album-art.git
cd rpi-zero-pixel-album-art

# Run automated installation script
sudo bash install.sh

# Configure your settings
cp config.example.json config.json
nano config.json  # Add your Spotify API credentials
```

### 3. Spotify API Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Note your **Client ID** and **Client Secret**
4. Add redirect URI: `http://localhost:8888/callback`
5. Add credentials to `config.json`

### 4. First Run

```bash
# Start the display
python3 src/main.py

# Or run as a service
sudo systemctl start spotify-display
```

Visit `http://your-pi-ip:5000` in your browser to access the web interface!

## Configuration

Edit `config.json`:

```json
{
  "spotify": {
    "client_id": "your_client_id_here",
    "client_secret": "your_client_secret_here",
    "redirect_uri": "http://localhost:8888/callback"
  },
  "display": {
    "rows": 64,
    "cols": 64,
    "brightness": 80,
    "gpio_slowdown": 2
  },
  "modes": {
    "default": "music",
    "schedule": {
      "weather": ["06:00-09:00"],
      "music": ["auto"],
      "sports": ["18:00-23:00"]
    }
  },
  "weather": {
    "api_key": "your_openweather_api_key",
    "location": "New York,US"
  },
  "sports": {
    "team": "NO",
    "league": "NFL"
  }
}
```

## Usage

### Web Interface

Access the control panel at `http://your-pi-ip:5000`:
- Switch between display modes
- Adjust brightness
- View currently playing track
- Configure schedules

### Manual Mode Switching

```bash
# Display album art
curl http://your-pi-ip:5000/api/mode -X POST -d '{"mode":"music"}'

# Show weather
curl http://your-pi-ip:5000/api/mode -X POST -d '{"mode":"weather"}'

# Sports scores
curl http://your-pi-ip:5000/api/mode -X POST -d '{"mode":"sports"}'
```

### Auto-start on Boot

```bash
# Enable systemd service
sudo systemctl enable spotify-display
sudo systemctl start spotify-display

# Check status
sudo systemctl status spotify-display
```

## Display Modes

### Music Mode
- Displays current Spotify album artwork
- Shows artist and track name scrolling text
- Auto-updates when track changes
- Supports Spotify Connect from any device

### Weather Mode
- Current temperature and conditions
- Weather icons
- 3-day forecast
- Uses OpenWeatherMap API (free tier)

### Sports Mode
- Live scores during games
- Team logos
- Game schedule
- Supports NFL, NBA, MLB, NHL via ESPN API

### Clock Mode
- Large time display
- Date and day of week
- Customizable colors

### Retro Screensavers

**Pipes Mode** 🔧
- Classic Windows 3D Pipes aesthetic
- Multiple colorful pipes growing across the display
- Configurable number of pipes, speed, and trail effects
- Perfect for nostalgic ambiance

**DVD Logo Mode** 📀
- Iconic bouncing DVD logo animation
- Random color changes on edge hits
- **Special rainbow mode** when hitting corners perfectly!
- Corner hit counter display
- Adjustable logo size and speed

See [docs/SCREENSAVERS.md](docs/SCREENSAVERS.md) for detailed configuration and tips.

## Troubleshooting

### Display doesn't light up
- Check power supply voltage (should be 4.9-5.1V)
- Verify polarity (reverse polarity destroys panels!)
- Ensure power supply provides enough current (5A for 64x64)

### Wrong colors or flickering
- Try different `gpio_slowdown` values (2-4)
- Check all GPIO connections
- Add 1000μF capacitor across power terminals

### Spotify not connecting
- Run `python3 src/spotify_auth.py` to re-authenticate
- Check Client ID/Secret in config.json
- Verify redirect URI matches Spotify dashboard

### Web interface not accessible
- Check Pi IP address: `hostname -I`
- Ensure port 5000 not blocked by firewall
- Try accessing from same network

## Advanced Features

### Custom Display Scripts

Create your own display modes in `src/modes/`:

```python
# src/modes/custom.py
from PIL import Image, ImageDraw, ImageFont

def render(matrix, config):
    image = Image.new('RGB', (64, 64))
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), "Hello!", fill=(255, 255, 255))
    matrix.SetImage(image)
```

### API Endpoints

- `GET /api/status` - Current status and playing track
- `POST /api/mode` - Switch display mode
- `POST /api/brightness` - Adjust brightness (0-100)
- `GET /api/spotify/current` - Current Spotify track info
- `POST /api/display/text` - Display custom text

## Project Structure

```
rpi-zero-pixel-album-art/
├── src/
│   ├── main.py                 # Main application
│   ├── spotify_client.py       # Spotify API integration
│   ├── led_display.py          # LED matrix control
│   ├── web_server.py           # Web interface
│   ├── modes/                  # Display mode implementations
│   │   ├── music.py
│   │   ├── weather.py
│   │   ├── sports.py
│   │   ├── clock.py
│   │   ├── pipes.py            # Windows Pipes screensaver
│   │   └── dvd_logo.py         # DVD Logo screensaver
│   └── utils/
│       ├── image_processor.py  # Image optimization for LED
│       └── config_manager.py   # Configuration handling
├── docs/
│   └── SCREENSAVERS.md         # Screensaver documentation
├── web/                        # Web interface files
│   ├── index.html
│   ├── style.css
│   └── script.js
├── install.sh                  # Automated installation
├── requirements.txt            # Python dependencies
├── config.example.json         # Configuration template
├── spotify-display.service     # Systemd service file
└── README.md
```

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) by Henner Zeller
- Spotify Web API
- Inspired by commercial products like TuneShine

## Support

For issues and questions:
- Check [Troubleshooting](#troubleshooting) section
- Open an issue on GitHub
- See [docs/](docs/) folder for detailed guides

## Roadmap

- [ ] Apple Music integration
- [ ] Tidal support
- [ ] Home Assistant MQTT integration (optional)
- [ ] Mobile app for control
- [ ] Multiple panel support
- [ ] Animated transitions
- [ ] Voice control via Alexa/Google

---

**Total Cost**: $51-81 vs $199 for commercial alternatives

**Setup Time**: ~1 hour including software installation

**Difficulty**: Beginner-friendly with basic Linux knowledge
