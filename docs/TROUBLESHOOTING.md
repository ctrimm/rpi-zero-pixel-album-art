# Troubleshooting Guide

Common issues and solutions for the Spotify LED Matrix Display.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Display Problems](#display-problems)
- [Spotify Connection Issues](#spotify-connection-issues)
- [Web Interface Issues](#web-interface-issues)
- [Performance Issues](#performance-issues)
- [Service/Systemd Issues](#servicesystemd-issues)

---

## Installation Issues

### Python Dependencies Won't Install

**Problem:** `pip3 install` fails with errors

**Solutions:**
```bash
# Update pip
sudo pip3 install --upgrade pip

# Install missing system libraries
sudo apt-get install python3-dev libatlas-base-dev

# Try installing problematic packages individually
sudo pip3 install Pillow
sudo pip3 install spotipy
```

### rpi-rgb-led-matrix Won't Build

**Problem:** Compilation errors when building LED matrix library

**Solutions:**
```bash
# Install build dependencies
sudo apt-get install build-essential python3-dev cython3

# Clean and rebuild
cd ~/rpi-rgb-led-matrix
make clean
make build-python PYTHON=$(which python3)
sudo make install-python PYTHON=$(which python3)
```

### Permission Denied Errors

**Problem:** Can't access GPIO or create files

**Solutions:**
```bash
# Run with sudo for GPIO access
sudo python3 src/main.py

# Or add user to gpio group
sudo usermod -a -G gpio $USER
# Then logout and back in

# Fix file permissions
sudo chown -R $USER:$USER ~/rpi-zero-pixel-album-art
```

---

## Display Problems

### LED Panel Doesn't Light Up

**Checklist:**
1. [ ] Power supply connected and turned on?
2. [ ] Verify voltage: should be 4.9-5.1V DC
   ```bash
   # Measure with multimeter at panel terminals
   ```
3. [ ] Check polarity (red=+5V, black=GND)
4. [ ] HUB75 cable fully inserted?
5. [ ] Common ground connected?

**Test power supply:**
```bash
# Disconnect from panel, measure voltage
# Should read very close to 5.0V
```

**Quick hardware test:**
```bash
cd ~/rpi-rgb-led-matrix/examples-api-use
sudo python3 simple-square.py
```

If this works but main program doesn't, it's a software issue.

### Display Shows Wrong Colors

**Problem:** Colors are incorrect or swapped

**Solution:** Try different RGB sequences in `config.json`:
```json
{
  "display": {
    "led_rgb_sequence": "RGB"  // Try: RBG, BRG, BGR, GRB, GBR
  }
}
```

Common mappings:
- Standard panels: `RGB`
- Some Chinese panels: `RBG` or `GRB`

### Display Flickers

**Problem:** Panel flickers or has visible refresh lines

**Solutions:**

1. **Increase slowdown:**
```json
{
  "display": {
    "gpio_slowdown": 3  // Try 2, 3, or 4
  }
}
```

2. **Add capacitor:**
- Solder 1000-3300μF capacitor across +5V and GND
- Place as close to panel as possible
- Observe polarity!

3. **Better power supply:**
- Use higher quality 5V supply
- Ensure adequate current rating
- Shorter, thicker power wires (16-18 AWG)

4. **Reduce brightness temporarily:**
```json
{
  "display": {
    "brightness": 50
  }
}
```

### Ghosting or Double Images

**Problem:** Previous image visible or ghosting

**Solutions:**

1. **Shorten HUB75 cable:**
- Keep under 6 inches if possible
- Longer cables cause signal degradation

2. **Check connections:**
```bash
# Verify all pins are making good contact
# Reseat HUB75 connector
```

3. **Adjust PWM settings:**
```json
{
  "display": {
    "pwm_bits": 11,
    "pwm_lsb_nanoseconds": 130
  }
}
```

### Only Part of Display Works

**Problem:** Only top half or specific rows light up

**Solutions:**

1. **Check address lines:**
- Verify A, B, C, D (and E if 64px high) connections
- Try reconfiguring in `config.json`:
```json
{
  "display": {
    "rows": 64,  // or 32
    "hardware_mapping": "regular"  // try "adafruit-hat" or "regular"
  }
}
```

2. **Different hardware mapping:**
```bash
# Test different mappings
sudo python3 src/main.py
# Edit config.json and try: regular, adafruit-hat, regular-pi1, classic-pi1
```

---

## Spotify Connection Issues

### "Spotify client failed to initialize"

**Problem:** Can't connect to Spotify API

**Checklist:**
1. [ ] Client ID and Secret correct in config.json?
2. [ ] Redirect URI exactly matches Spotify dashboard?
3. [ ] Internet connection working?
   ```bash
   ping google.com
   ```

**Re-authenticate:**
```bash
# Delete cached token
rm -rf ~/.cache/spotify-display/

# Run again - will prompt for authentication
python3 src/main.py
```

### "Nothing playing" even when Spotify is running

**Problem:** Display shows "No Music Playing" but Spotify is active

**Solutions:**

1. **Check Spotify account:**
- Must be Spotify Premium (free accounts have API limitations)
- Must be actively playing (not paused)

2. **Verify API scopes:**
Edit `config.json`:
```json
{
  "spotify": {
    "scope": "user-read-currently-playing user-read-playback-state"
  }
}
```

3. **Re-authenticate:**
```bash
rm -rf ~/.cache/spotify-display/
python3 src/main.py
```

4. **Check Spotify privacy settings:**
- Go to Spotify → Settings → Social
- Ensure "Make my listening activity private" is OFF

### Token Expired Errors

**Problem:** "Token expired" or authentication errors

**Solution:**
```bash
# Delete token cache
rm -rf ~/.cache/spotify-display/spotify_token_cache

# Restart application - will re-authenticate
sudo systemctl restart spotify-display
```

---

## Web Interface Issues

### Can't Access Web Interface

**Problem:** Browser can't load `http://PI_IP:5000`

**Checklist:**

1. **Verify service is running:**
```bash
sudo systemctl status spotify-display
```

2. **Check if port is listening:**
```bash
sudo netstat -tlnp | grep 5000
```
Should show python listening on port 5000

3. **Try localhost:**
```bash
# On the Pi itself
curl http://localhost:5000
```

4. **Check firewall:**
```bash
# If using firewall, allow port 5000
sudo ufw allow 5000
```

5. **Find correct IP:**
```bash
hostname -I
```
Use first IP address shown

### Web Interface Shows "Disconnected"

**Problem:** Web UI loads but shows "Disconnected"

**Solutions:**

1. **Check backend:**
```bash
# View logs
sudo journalctl -u spotify-display -f
```

2. **Restart service:**
```bash
sudo systemctl restart spotify-display
```

3. **Test API directly:**
```bash
curl http://localhost:5000/api/status
```
Should return JSON status

### Changes in Web Interface Don't Work

**Problem:** Mode changes or brightness adjustments don't take effect

**Solutions:**

1. **Check logs for errors:**
```bash
sudo journalctl -u spotify-display -n 50
```

2. **Verify API responses:**
```bash
# Test mode switch
curl -X POST http://localhost:5000/api/mode \
  -H "Content-Type: application/json" \
  -d '{"mode":"clock"}'
```

3. **Clear browser cache:**
- Ctrl+Shift+R to hard refresh
- Or clear browser cache completely

---

## Performance Issues

### High CPU Usage

**Problem:** Python process using excessive CPU

**Solutions:**

1. **For Pi 4, isolate CPU core:**
Add to `/boot/cmdline.txt`:
```
isolcpus=3
```
Then reboot.

2. **Reduce update frequency:**
Edit `config.json`:
```json
{
  "spotify": {
    "update_interval": 15  // Increase from 10
  }
}
```

3. **Disable advanced features:**
```json
{
  "image_processing": {
    "enhance_contrast": false,
    "enhance_saturation": false
  }
}
```

### Slow Image Updates

**Problem:** Album art takes a long time to update

**Solutions:**

1. **Enable image caching:**
```json
{
  "image_processing": {
    "cache_images": true,
    "cache_size_mb": 100
  }
}
```

2. **Check network speed:**
```bash
ping 8.8.8.8
# Should be under 50ms
```

3. **Pre-process images at lower resolution:**
Images are downloaded at full Spotify resolution then resized - this is expected to take 2-5 seconds on first load per track.

---

## Service/Systemd Issues

### Service Won't Start

**Problem:** `systemctl start spotify-display` fails

**Diagnosis:**
```bash
# Check status
sudo systemctl status spotify-display

# View detailed logs
sudo journalctl -u spotify-display -n 100

# Check for config errors
python3 ~/rpi-zero-pixel-album-art/src/main.py
```

**Common fixes:**

1. **Config file errors:**
```bash
# Validate JSON
python3 -c "import json; json.load(open('config.json'))"
```

2. **Missing dependencies:**
```bash
cd ~/rpi-zero-pixel-album-art
sudo pip3 install -r requirements.txt
```

3. **Permission issues:**
```bash
# Fix permissions
sudo chown -R $USER:$USER ~/rpi-zero-pixel-album-art
```

### Service Keeps Restarting

**Problem:** Service shows "activating" but never stays running

**Check logs:**
```bash
sudo journalctl -u spotify-display -f
```

Look for:
- Python errors
- Missing configuration
- Hardware access issues

**Fix service file:**
```bash
sudo nano /etc/systemd/system/spotify-display.service
```

Ensure `WorkingDirectory` and `ExecStart` paths are correct.

### Service Doesn't Auto-Start on Boot

**Problem:** Service works manually but not on boot

**Solutions:**

1. **Enable service:**
```bash
sudo systemctl enable spotify-display
```

2. **Check dependencies:**
Service needs network to connect to Spotify. Ensure it waits for network:
```bash
sudo nano /etc/systemd/system/spotify-display.service
```
Verify line:
```
After=network.target
```

3. **Test boot:**
```bash
sudo reboot
# Wait for boot, then check
sudo systemctl status spotify-display
```

---

## Logs and Debugging

### Enable Debug Logging

Edit `config.json`:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

Restart service:
```bash
sudo systemctl restart spotify-display
```

### View Logs

**Systemd logs:**
```bash
# Live view
sudo journalctl -u spotify-display -f

# Last 100 lines
sudo journalctl -u spotify-display -n 100

# Since last boot
sudo journalctl -u spotify-display -b
```

**Application log file:**
```bash
tail -f /var/log/spotify-display.log
```

### Common Error Messages

**"Could not initialize matrix"**
- Hardware connection issue
- Run with `sudo` for GPIO access
- Check wiring

**"Spotify authentication failed"**
- Invalid credentials
- Check Client ID/Secret
- Re-authenticate

**"Module 'rgbmatrix' not found"**
- LED matrix library not installed
- Run installation script again

**"Port 5000 already in use"**
- Another program using port
- Change port in config or stop other program:
```bash
sudo lsof -i :5000
sudo kill <PID>
```

---

## Getting Help

If you're still stuck:

1. **Check logs thoroughly:**
```bash
sudo journalctl -u spotify-display -n 200 > ~/debug.log
```

2. **Test each component:**
- Hardware test: LED examples from rpi-rgb-led-matrix
- Spotify test: Simple spotipy script
- Web server test: Check Flask logs

3. **Create minimal test case:**
```python
# test_display.py
from rgbmatrix import RGBMatrix, RGBMatrixOptions

options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
matrix = RGBMatrix(options=options)
print("Matrix initialized successfully!")
```

4. **Search existing issues:**
- [rpi-rgb-led-matrix issues](https://github.com/hzeller/rpi-rgb-led-matrix/issues)
- [Spotipy issues](https://github.com/plamere/spotipy/issues)

5. **Report bug with:**
- Hardware details (Pi model, panel size)
- Full error messages
- Relevant log excerpts
- Steps to reproduce

---

## Reset to Default

If all else fails, completely reset:

```bash
# Stop service
sudo systemctl stop spotify-display
sudo systemctl disable spotify-display

# Remove installation
cd ~
rm -rf rpi-zero-pixel-album-art

# Start fresh
git clone https://github.com/yourusername/rpi-zero-pixel-album-art.git
cd rpi-zero-pixel-album-art
sudo bash install.sh
```
