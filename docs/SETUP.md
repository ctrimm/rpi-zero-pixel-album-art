# Detailed Setup Guide

Complete step-by-step instructions for setting up your Spotify LED Matrix Display.

## Table of Contents

1. [Hardware Assembly](#hardware-assembly)
2. [Software Installation](#software-installation)
3. [Spotify API Configuration](#spotify-api-configuration)
4. [Testing](#testing)
5. [Auto-Start Configuration](#auto-start-configuration)

---

## Hardware Assembly

### Step 1: Connect Power Supply

**CRITICAL: Double-check polarity before powering on!**

1. Locate the power input terminals on your LED matrix panel
2. Connect the 5V power supply:
   - Red wire → +5V terminal
   - Black wire → GND terminal
3. **DO NOT power on yet** - verify connections first!

### Step 2: Connect Signal Cable

**Option A: Using Adafruit RGB Matrix Bonnet (Recommended)**

1. Power off your Raspberry Pi
2. Attach the RGB Matrix Bonnet to the GPIO header
3. Connect the HUB75 cable from the bonnet to the LED panel
4. Connect power supply to the bonnet's power terminals

**Option B: Manual Wiring**

See [WIRING.md](WIRING.md) for detailed GPIO pin connections.

### Step 3: Initial Power-On Test

1. Connect Raspberry Pi power supply (keep LED panel unpowered)
2. Let Pi boot completely
3. Now connect LED panel power supply
4. Panel should light up (may show random pixels - this is normal)

---

## Software Installation

### Step 1: Prepare Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install git if not already installed
sudo apt install git -y
```

### Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/yourusername/rpi-zero-pixel-album-art.git
cd rpi-zero-pixel-album-art
```

### Step 3: Run Installation Script

```bash
sudo bash install.sh
```

The installer will:
- Install system dependencies
- Configure Raspberry Pi settings
- Install rpi-rgb-led-matrix library
- Install Python dependencies
- Create systemd service
- Set up configuration file

**Reboot after installation:**
```bash
sudo reboot
```

---

## Spotify API Configuration

### Step 1: Create Spotify Application

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click **Create an App**
4. Fill in:
   - **App Name**: "LED Matrix Display" (or any name)
   - **App Description**: "Personal LED album art display"
   - Accept terms and create
5. Click **Edit Settings**
6. Add Redirect URI: `http://127.0.0.1:8888/callback`
7. Save

### Step 2: Get API Credentials

1. On your app's dashboard, find:
   - **Client ID** (show/copy)
   - **Client Secret** (show/copy)
2. Keep these safe - you'll need them next

### Step 3: Configure Application

```bash
cd ~/rpi-zero-pixel-album-art
nano config.json
```

Update the Spotify section:

```json
{
  "spotify": {
    "client_id": "paste_your_client_id_here",
    "client_secret": "paste_your_client_secret_here",
    "redirect_uri": "http://127.0.0.1:8888/callback"
  }
}
```

Save and exit (Ctrl+X, Y, Enter)

### Step 4: Authenticate

```bash
python3 src/main.py
```

On first run:
1. A URL will be displayed in the terminal
2. Open this URL in a browser (can be on another device)
3. Log in to Spotify and authorize the app
4. You'll be redirected to localhost (this is expected)
5. Copy the entire URL from your browser
6. Paste it back into the terminal
7. Authentication complete!

---

## Optional: Weather Configuration

### Get OpenWeatherMap API Key

1. Sign up at [OpenWeatherMap](https://openweathermap.org/api)
2. Subscribe to free tier
3. Get your API key from your account

### Configure Weather

Edit `config.json`:

```json
{
  "weather": {
    "enabled": true,
    "api_key": "your_openweathermap_api_key",
    "location": "New York,US",
    "units": "imperial"
  }
}
```

---

## Testing

### Test 1: Manual Run

```bash
cd ~/rpi-zero-pixel-album-art
python3 src/main.py
```

You should see:
- Initialization messages
- Web server starting
- "Now playing" detection when you play Spotify

### Test 2: Display Test Pattern

```bash
# In another terminal or via web interface
curl http://localhost:5000/api/display/test
```

Should show RGB color bars on the panel.

### Test 3: Web Interface

1. Find your Pi's IP address:
   ```bash
   hostname -I
   ```

2. On any device on the same network, open browser to:
   ```
   http://YOUR_PI_IP:5000
   ```

3. You should see the control panel

### Test 4: Spotify Integration

1. Start playing music on Spotify (any device connected to your account)
2. Within 10 seconds, album art should appear on LED panel
3. Check web interface - should show "Now Playing" info

---

## Auto-Start Configuration

### Enable Service

```bash
sudo systemctl enable spotify-display
sudo systemctl start spotify-display
```

### Check Service Status

```bash
sudo systemctl status spotify-display
```

Should show "active (running)"

### View Logs

```bash
# Live log view
sudo journalctl -u spotify-display -f

# Recent logs
sudo journalctl -u spotify-display -n 50
```

### Restart Service

```bash
sudo systemctl restart spotify-display
```

### Stop Service

```bash
sudo systemctl stop spotify-display
```

---

## Network Access

### Find Pi IP Address

```bash
hostname -I
```

### Set Static IP (Recommended)

Edit `/etc/dhcpcd.conf`:

```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end:

```
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

Adjust values for your network. Restart:

```bash
sudo reboot
```

---

## Next Steps

- Read [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- Check [WIRING.md](WIRING.md) for hardware details
- Customize display modes in `config.json`
- Add schedule for automatic mode switching
- Create custom display modes (see `src/modes/` for examples)

---

## Quick Command Reference

```bash
# Start manually
python3 src/main.py

# Start service
sudo systemctl start spotify-display

# Stop service
sudo systemctl stop spotify-display

# Restart service
sudo systemctl restart spotify-display

# View logs
sudo journalctl -u spotify-display -f

# Edit configuration
nano config.json

# Test display
curl http://localhost:5000/api/display/test
```
