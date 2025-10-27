# Complete Raspberry Pi Setup Guide

**From blank SD card to running Spotify LED Matrix Display**

This guide walks you through every step needed to get your Raspberry Pi ready to run the Spotify LED Matrix Display, starting with a brand new, unformatted SD card.

---

## Table of Contents

1. [What You'll Need](#what-youll-need)
2. [Step 1: Flash Raspberry Pi OS](#step-1-flash-raspberry-pi-os)
3. [Step 2: First Boot and Initial Setup](#step-2-first-boot-and-initial-setup)
4. [Step 3: Connect to Network](#step-3-connect-to-network)
5. [Step 4: System Configuration](#step-4-system-configuration)
6. [Step 5: Install the Application](#step-5-install-the-application)
7. [Step 6: Hardware Connection](#step-6-hardware-connection)
8. [Step 7: Configure and Run](#step-7-configure-and-run)
9. [Step 8: Setup Auto-Start](#step-8-setup-auto-start)
10. [Troubleshooting](#troubleshooting)

---

## What You'll Need

### Hardware
- [ ] Raspberry Pi Zero 2 W or Raspberry Pi 4B
- [ ] MicroSD card (32GB minimum, Class 10 recommended)
- [ ] MicroSD card reader (USB adapter)
- [ ] Computer (Windows, Mac, or Linux)
- [ ] LED Matrix Panel (64x64)
- [ ] RGB Matrix Bonnet or adapter board
- [ ] 5V power supply for LED panel
- [ ] Micro USB cable (for Pi Zero) or USB-C cable (for Pi 4)
- [ ] Power supply for Raspberry Pi

### Optional but Recommended
- [ ] HDMI cable and monitor (for initial setup)
- [ ] USB keyboard and mouse
- [ ] Ethernet cable (alternative to WiFi)

### Software Downloads (we'll get these)
- Raspberry Pi Imager
- This project from GitHub

---

## Step 1: Flash Raspberry Pi OS

### 1.1 Download Raspberry Pi Imager

**On Windows/Mac/Linux:**

1. Go to https://www.raspberrypi.com/software/
2. Download **Raspberry Pi Imager** for your operating system
3. Install the application

### 1.2 Prepare the SD Card

1. **Insert your microSD card** into your card reader
2. **Plug the card reader** into your computer
3. **Open Raspberry Pi Imager**

### 1.3 Flash the OS

**Step-by-step in Raspberry Pi Imager:**

1. **Click "Choose Device"**
   - Select your Raspberry Pi model:
     - `Raspberry Pi Zero 2 W` (if you have Zero 2 W)
     - `Raspberry Pi 4` (if you have Pi 4)

2. **Click "Choose OS"**
   - Select: `Raspberry Pi OS (other)`
   - Then select: `Raspberry Pi OS Lite (64-bit)` ← **Recommended for headless**
   - OR select: `Raspberry Pi OS (64-bit)` ← If you want desktop GUI

   **💡 Recommendation:** Use **Lite** version - it's faster and uses less resources since we don't need the desktop for this project.

3. **Click "Choose Storage"**
   - Select your SD card from the list
   - ⚠️ **WARNING:** All data on this card will be erased!

4. **Click "Next"**

5. **Click "Edit Settings"** when prompted (IMPORTANT!)

### 1.4 Configure OS Settings (CRITICAL STEP!)

In the OS Customization screen:

**General Tab:**
```
✓ Set hostname:              spotify-display
✓ Set username and password:
  Username: pi
  Password: [choose a secure password]
✓ Configure wireless LAN:
  SSID: [Your WiFi Network Name]
  Password: [Your WiFi Password]
  Wireless LAN country: [Your Country - e.g., US]
✓ Set locale settings:
  Time zone: [Your timezone - e.g., America/New_York]
  Keyboard layout: [Your layout - e.g., us]
```

**Services Tab:**
```
✓ Enable SSH
  • Use password authentication
```

**Options Tab:**
```
✓ Eject media when finished
✓ Enable telemetry: [Your choice]
```

6. **Click "Save"**

7. **Click "Yes"** to apply OS customization settings

8. **Click "Yes"** to confirm you want to erase the SD card

9. **Wait for the process to complete** (5-10 minutes)
   - Writing...
   - Verifying...
   - Done!

10. **Remove the SD card** when prompted

---

## Step 2: First Boot and Initial Setup

### 2.1 Insert SD Card and Power On

1. **Insert the flashed microSD card** into your Raspberry Pi
2. **DO NOT connect LED panel yet** - we'll do this later
3. **Connect Raspberry Pi power supply**
4. **Wait 1-2 minutes** for first boot

The Pi will:
- Boot up
- Resize filesystem
- Connect to WiFi (if configured correctly)
- Enable SSH

### 2.2 Find Your Pi's IP Address

**Method 1: Check Your Router**
1. Log into your router's admin page (usually 192.168.1.1 or 192.168.0.1)
2. Look for connected devices
3. Find device named "spotify-display" or "raspberrypi"
4. Note the IP address (e.g., 192.168.1.100)

**Method 2: Use Network Scanner**
1. Download "Angry IP Scanner" or "Fing" app on your phone
2. Scan your network
3. Look for "Raspberry Pi" or hostname "spotify-display"

**Method 3: Use nmap (Linux/Mac)**
```bash
nmap -sn 192.168.1.0/24
# Look for "Raspberry Pi Foundation" in results
```

### 2.3 Connect via SSH

**On Windows:**
1. Open **Command Prompt** or **PowerShell**
2. Type:
   ```cmd
   ssh pi@[YOUR_PI_IP_ADDRESS]
   ```
   Example: `ssh pi@192.168.1.100`

**On Mac/Linux:**
1. Open **Terminal**
2. Type:
   ```bash
   ssh pi@[YOUR_PI_IP_ADDRESS]
   ```
   Example: `ssh pi@192.168.1.100`

**First Connection:**
- You'll see a warning about host authenticity
- Type `yes` and press Enter
- Enter the password you set during SD card setup
- You should see the Raspberry Pi command prompt!

```
pi@spotify-display:~ $
```

🎉 **Success!** You're now connected to your Raspberry Pi!

---

## Step 3: Connect to Network

If you already connected via WiFi in Step 1.4, you can skip this section. Otherwise:

### 3.1 Configure WiFi Manually

```bash
sudo raspi-config
```

1. Select: `System Options` → `Wireless LAN`
2. Enter your WiFi SSID (network name)
3. Enter your WiFi password
4. Select `Finish`
5. Reboot: `sudo reboot`

### 3.2 Set Static IP (Recommended)

This prevents your Pi's IP address from changing:

```bash
sudo nano /etc/dhcpcd.conf
```

Add to the end of the file:

```
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

**Adjust these values for your network:**
- `192.168.1.100` - Choose an unused IP in your network range
- `192.168.1.1` - Your router's IP address
- If using Ethernet instead of WiFi, change `wlan0` to `eth0`

**Save and exit:**
- Press `Ctrl + X`
- Press `Y`
- Press `Enter`

**Reboot:**
```bash
sudo reboot
```

Wait 30 seconds, then reconnect via SSH using your new static IP.

---

## Step 4: System Configuration

### 4.1 Update System

**Update package list and upgrade all packages:**

```bash
sudo apt update
sudo apt upgrade -y
```

This may take 5-15 minutes depending on your Pi model and internet speed.

### 4.2 Install Basic Tools

```bash
sudo apt install -y git vim htop
```

### 4.3 Configure System Settings

**Open Raspberry Pi Configuration:**

```bash
sudo raspi-config
```

Make these changes:

**1. System Options → Boot / Auto Login**
   - Select: `Console Autologin` (optional, for convenience)

**2. Interface Options → I2C**
   - Select: `No` (not needed for this project)

**3. Performance Options → GPU Memory**
   - Set to: `16` MB (we don't need much GPU memory)

**4. Localization Options**
   - Verify timezone is correct

**5. Advanced Options → Expand Filesystem**
   - This should already be done, but verify

**Select Finish → Reboot**

```bash
sudo reboot
```

---

## Step 5: Install the Application

### 5.1 Clone the Repository

```bash
cd ~
git clone https://github.com/ctrimm/rpi-zero-pixel-album-art.git
cd rpi-zero-pixel-album-art
```

### 5.2 Run the Installation Script

```bash
sudo bash install.sh
```

The installer will:
- ✓ Install system dependencies
- ✓ Configure Pi for LED matrix (disable audio, etc.)
- ✓ Install rpi-rgb-led-matrix library
- ✓ Install Python dependencies
- ✓ Create systemd service
- ✓ Set up configuration file

**This takes 10-20 minutes.** Let it run!

### 5.3 Reboot After Installation

The installer will recommend a reboot:

```bash
sudo reboot
```

Wait 30 seconds, then reconnect via SSH.

---

## Step 6: Hardware Connection

**⚠️ POWER OFF YOUR RASPBERRY PI BEFORE CONNECTING HARDWARE! ⚠️**

```bash
sudo shutdown -h now
```

Wait for the green LED to stop blinking, then unplug power.

### 6.1 Connect RGB Matrix Bonnet (If Using)

**If you have an Adafruit RGB Matrix Bonnet or similar:**

1. **Align the bonnet** with the 40-pin GPIO header on the Pi
2. **Press down firmly** until fully seated
3. **Connect HUB75 cable** from bonnet to LED panel
4. **Connect power:**
   - Power supply → LED panel power terminals (red=+5V, black=GND)
   - ⚠️ **Verify polarity with multimeter before powering on!**
   - Connect a ground wire from panel GND to bonnet GND terminal

### 6.2 Manual GPIO Wiring (If Not Using Bonnet)

See [docs/WIRING.md](WIRING.md) for complete pinout diagram.

**Critical connections:**

| HUB75 Pin | Pi GPIO | Physical Pin |
|-----------|---------|--------------|
| R1 | GPIO 11 | Pin 23 |
| G1 | GPIO 27 | Pin 13 |
| B1 | GPIO 7 | Pin 26 |
| CLK | GPIO 17 | Pin 11 |
| LAT | GPIO 4 | Pin 7 |
| OE | GPIO 18 | Pin 12 |
| GND | GND | Multiple |

**Power connections:**
- LED panel has separate 5V power supply
- Connect common ground between Pi and panel power
- Never power panel from Pi's 5V pins!

### 6.3 Safety Check

Before powering on:

- [ ] HUB75 cable fully inserted both ends
- [ ] Power supply is 5V (measure with multimeter)
- [ ] Power polarity is correct (red=+5V, black=GND)
- [ ] Common ground connected
- [ ] No loose wires touching each other
- [ ] Raspberry Pi GPIO connections secure

---

## Step 7: Configure and Run

### 7.1 Get Spotify API Credentials

1. **Go to:** https://developer.spotify.com/dashboard
2. **Log in** with your Spotify account
3. **Click "Create an App"**
4. **Fill in:**
   - App name: `LED Matrix Display`
   - App description: `Personal LED album art display`
   - Redirect URI: `http://127.0.0.1:8888/callback`
   - Check the terms box
   - Click **Create**
5. **Click "Settings"**
6. **Note your:**
   - Client ID (looks like: `a1b2c3d4e5f6...`)
   - Client Secret (click "View client secret")

### 7.2 Configure the Application

```bash
cd ~/rpi-zero-pixel-album-art
cp config.example.json config.json
nano config.json
```

**Edit the following sections:**

```json
{
  "spotify": {
    "client_id": "PASTE_YOUR_CLIENT_ID_HERE",
    "client_secret": "PASTE_YOUR_CLIENT_SECRET_HERE",
    "redirect_uri": "http://127.0.0.1:8888/callback"
  }
}
```

**Optional - Configure Weather on the 8s:**

Get a free API key from https://openweathermap.org/api

```json
{
  "weather_on_8s": {
    "enabled": true,
    "api_key": "PASTE_YOUR_OPENWEATHER_KEY_HERE",
    "location": "Your City,US",
    "units": "imperial"
  }
}
```

**Save and exit:**
- `Ctrl + X`
- `Y`
- `Enter`

### 7.3 Authenticate with Spotify

```bash
python3 src/spotify_auth.py
```

**Follow the prompts:**

1. A URL will be displayed - it looks like:
   ```
   https://accounts.spotify.com/authorize?client_id=...
   ```

2. **Copy the entire URL**

3. **Open it in a web browser** (on your computer or phone)

4. **Log in to Spotify** and click **Agree**

5. **You'll be redirected** to a localhost URL that won't load - that's OK!

6. **Copy the ENTIRE URL** from your browser's address bar
   ```
   http://127.0.0.1:8888/callback?code=AQD...
   ```

7. **Paste it back** into the terminal and press Enter

8. You should see: `✅ Authentication successful!`

### 7.4 Test the Display

**Power on your LED panel now!**

Then run:

```bash
cd ~/rpi-zero-pixel-album-art
python3 src/main.py
```

**You should see:**
```
    ╔══════════════════════════════════════════╗
    ║  Raspberry Pi Spotify LED Matrix Display ║
    ║  Standalone Network Version              ║
    ╚══════════════════════════════════════════╝

Initializing Spotify LED Matrix Display...
Initializing LED display...
Initializing Spotify client...
Initializing display modes...
🌤️ Weather on the 8s enabled! Will show at :08, :18, :28, :38, :48, :58
Initializing web server...
Application started successfully!
Web interface available at http://0.0.0.0:5000
```

**Test checklist:**

- [ ] LED panel lights up (may show random colors initially)
- [ ] No error messages in terminal
- [ ] Web server starts on port 5000

**Test the display pattern:**

Open another terminal and run:

```bash
curl http://localhost:5000/api/display/test
```

You should see RGB color bars on your LED panel!

**Test Spotify integration:**

1. Start playing music on Spotify (any device)
2. Wait 10-15 seconds
3. Album art should appear on LED panel!

### 7.5 Access Web Interface

**From another device on your network:**

1. Open web browser
2. Go to: `http://[YOUR_PI_IP]:5000`
   - Example: `http://192.168.1.100:5000`
3. You should see the control panel!

**Web interface features:**
- View currently playing track
- Switch display modes
- Adjust brightness
- View system status

---

## Step 8: Setup Auto-Start

Once everything is working, make it start automatically on boot.

### 8.1 Stop the Manual Process

If `main.py` is still running:
- Press `Ctrl + C` to stop it

### 8.2 Enable the Service

```bash
sudo systemctl enable spotify-display
sudo systemctl start spotify-display
```

### 8.3 Check Service Status

```bash
sudo systemctl status spotify-display
```

You should see:
```
● spotify-display.service - Spotify LED Matrix Display
   Loaded: loaded (/etc/systemd/system/spotify-display.service; enabled)
   Active: active (running) since...
```

### 8.4 View Live Logs

```bash
sudo journalctl -u spotify-display -f
```

Press `Ctrl + C` to stop viewing logs.

### 8.5 Test Auto-Start

```bash
sudo reboot
```

After reboot:
1. Wait 1-2 minutes
2. Check if display is working
3. Check web interface is accessible
4. Check service status: `sudo systemctl status spotify-display`

---

## Troubleshooting

### Display Not Working

**Problem:** LED panel stays dark

**Solutions:**
```bash
# Check power supply voltage
# Should be 4.9-5.1V DC

# Check if matrix library is installed
ls ~/rpi-rgb-led-matrix/

# Test with library examples
cd ~/rpi-rgb-led-matrix/examples-api-use
sudo python3 simple-square.py
```

**Problem:** Wrong colors or flickering

**Solutions:**
```bash
# Edit config.json
nano ~/rpi-zero-pixel-album-art/config.json

# Try different gpio_slowdown values
"gpio_slowdown": 3  # or 4

# Try different RGB sequences
"led_rgb_sequence": "RBG"  # or "GRB", "BGR", etc.
```

### SSH Connection Issues

**Problem:** Can't connect via SSH

**Solutions:**
1. Verify Pi is powered on (green LED blinking)
2. Check WiFi credentials in Imager settings
3. Try Ethernet cable instead
4. Connect monitor and keyboard directly
5. Re-flash SD card with correct settings

### Spotify Not Working

**Problem:** "No music playing" always shown

**Solutions:**
```bash
# Re-authenticate
cd ~/rpi-zero-pixel-album-art
rm -rf ~/.cache/spotify-display/
python3 src/spotify_auth.py

# Check credentials
cat config.json | grep spotify -A 5

# Check Spotify is playing
# (Must be Premium account)
```

### Service Won't Start

**Problem:** `systemctl status` shows "failed"

**Solutions:**
```bash
# View detailed logs
sudo journalctl -u spotify-display -n 100

# Check config file
python3 -c "import json; json.load(open('~/rpi-zero-pixel-album-art/config.json'))"

# Test manually
cd ~/rpi-zero-pixel-album-art
python3 src/main.py
# Look for error messages
```

### Performance Issues

**Problem:** Slow or laggy display

**Solutions:**
```bash
# For Pi 4, isolate CPU core
sudo nano /boot/cmdline.txt
# Add to end: isolcpus=3

# Reduce brightness
# Edit config.json
"brightness": 50  # instead of 80

# Disable extra features
"weather_on_8s": {
  "enabled": false
}
```

### Weather on the 8s Not Showing

**Problem:** Weather doesn't display at :08, :18, etc.

**Solutions:**
```bash
# Check system time
date
# Should match your local time

# Sync time
sudo timedatectl set-ntp true

# Check logs at trigger time
sudo journalctl -u spotify-display -f
# Wait for :08, :18, :28, etc.

# Verify config
cat config.json | grep weather_on_8s -A 10
```

---

## Useful Commands Reference

```bash
# Application control
sudo systemctl start spotify-display    # Start service
sudo systemctl stop spotify-display     # Stop service
sudo systemctl restart spotify-display  # Restart service
sudo systemctl status spotify-display   # Check status

# View logs
sudo journalctl -u spotify-display -f   # Live logs
sudo journalctl -u spotify-display -n 100  # Last 100 lines

# Manual run (for testing)
cd ~/rpi-zero-pixel-album-art
python3 src/main.py

# Update application
cd ~/rpi-zero-pixel-album-art
git pull
sudo systemctl restart spotify-display

# Edit configuration
nano ~/rpi-zero-pixel-album-art/config.json

# Check Pi temperature
vcgencmd measure_temp

# Check network
ip addr show wlan0
ping google.com

# Reboot
sudo reboot

# Shutdown
sudo shutdown -h now
```

---

## Next Steps

✅ **Your Raspberry Pi is now fully set up!**

**What to do next:**

1. **Customize your display:**
   - Edit `config.json` to adjust brightness, modes, schedules
   - See [README.md](../README.md) for configuration options

2. **Explore features:**
   - Try Weather on the 8s (wait for :08, :18, :28, :38, :48, :58)
   - Switch modes via web interface
   - Configure sports scores
   - Set up mode schedules

3. **Build an enclosure:**
   - 3D print a case
   - Use a picture frame
   - Add a diffuser for better image quality

4. **Advanced customization:**
   - Create custom display modes (see `src/modes/` for examples)
   - Adjust colors and animations
   - Add more data sources

---

## Additional Resources

- **Main Documentation:** [README.md](../README.md)
- **Hardware Wiring:** [docs/WIRING.md](WIRING.md)
- **Detailed Setup:** [docs/SETUP.md](SETUP.md)
- **Troubleshooting:** [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Weather on 8s:** [docs/WEATHER_ON_8S.md](WEATHER_ON_8S.md)

- **Raspberry Pi Documentation:** https://www.raspberrypi.com/documentation/
- **rpi-rgb-led-matrix Library:** https://github.com/hzeller/rpi-rgb-led-matrix
- **Spotify API Docs:** https://developer.spotify.com/documentation/web-api

---

## Tips for Success

💡 **Save your work:** Your configuration is in `config.json` - back it up!

💡 **Start simple:** Get Spotify working first, then add weather, sports, etc.

💡 **Monitor logs:** Use `journalctl -f` to watch what's happening in real-time

💡 **Use static IP:** Makes finding your Pi much easier

💡 **Keep it updated:** Run `sudo apt update && sudo apt upgrade` monthly

💡 **Be patient:** First-time setup takes time, but it's worth it!

---

**🎉 Congratulations! You've successfully set up your Raspberry Pi Spotify LED Matrix Display!**

Enjoy your custom album art display with nostalgic Weather on the 8s! 🌤️🎵
