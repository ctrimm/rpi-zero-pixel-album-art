#!/bin/bash
# Raspberry Pi Spotify LED Matrix Display - Installation Script
#
# Works on Raspberry Pi OS Bookworm and Trixie (Python 3.11+).
# Everything Python goes into a virtualenv at ./venv, because current Pi OS
# blocks system-wide `pip install` (PEP 668 "externally-managed-environment").

set -e  # Exit on error

echo "======================================"
echo "Spotify LED Matrix Display Installer"
echo "======================================"
echo ""

# Check for root/sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run with sudo"
    echo "Usage: sudo bash install.sh"
    exit 1
fi

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null && ! grep -q "BCM" /proc/cpuinfo 2>/dev/null \
   && ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "Installation will continue, but LED matrix may not work without hardware"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# The real (non-root) user who ran sudo. The service starts as root (needed
# for flicker-free LED timing) and then drops to this user.
ACTUAL_USER=${SUDO_USER:-$USER}
if [ -z "$ACTUAL_USER" ] || [ "$ACTUAL_USER" = "root" ]; then
    echo "❌ Please run this with sudo from your normal user account (not as root directly)"
    exit 1
fi
USER_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$INSTALL_DIR/venv"
as_user() { sudo -u "$ACTUAL_USER" -H "$@"; }

# Python 3.11+ is required by the LED matrix library
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "❌ Python 3.11 or newer is required (found $(python3 --version 2>&1))."
    echo "   Please flash Raspberry Pi OS Bookworm or newer."
    exit 1
fi

echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 \
    python3-venv \
    python3-dev \
    python3-pip \
    git \
    build-essential \
    cmake \
    cython3 \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype-dev \
    liblcms2-dev \
    libwebp-dev \
    libopenjp2-7 \
    libtiff-dev

echo ""
echo "🔧 Configuring Raspberry Pi for LED matrix..."

# Pi OS Bookworm (2023+) moved the boot config to /boot/firmware/.
# Detect the correct location so these tweaks don't silently land in a file
# that the bootloader never reads.
BOOT_DIR="/boot/firmware"
[ -f "$BOOT_DIR/config.txt" ] || BOOT_DIR="/boot"
CONFIG_TXT="$BOOT_DIR/config.txt"
CMDLINE_TXT="$BOOT_DIR/cmdline.txt"

if [ -f "$CONFIG_TXT" ]; then
    echo "✓ Using boot config at $CONFIG_TXT"

    # Disable audio (conflicts with LED matrix PWM)
    if grep -q "^dtparam=audio=on" "$CONFIG_TXT"; then
        sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$CONFIG_TXT"
        echo "✓ Disabled onboard audio"
    elif ! grep -q "dtparam=audio=off" "$CONFIG_TXT"; then
        echo "dtparam=audio=off" >> "$CONFIG_TXT"
        echo "✓ Disabled onboard audio"
    fi

    # Disable Bluetooth (optional, for stability)
    if ! grep -q "dtoverlay=disable-bt" "$CONFIG_TXT"; then
        echo "dtoverlay=disable-bt" >> "$CONFIG_TXT"
        echo "✓ Disabled Bluetooth"
        systemctl disable hciuart 2>/dev/null || true
    fi

    # For Pi 4: Isolate CPU core for LED refresh (optional but recommended)
    if grep -q "Raspberry Pi 4" /proc/cpuinfo /proc/device-tree/model 2>/dev/null; then
        if ! grep -q "isolcpus=3" "$CMDLINE_TXT"; then
            sed -i '$ s/$/ isolcpus=3/' "$CMDLINE_TXT"
            echo "✓ Isolated CPU core 3 for LED matrix (Pi 4)"
        fi
    fi
else
    echo "⚠️  No boot config.txt found - skipping Pi boot tweaks"
fi

# The onboard sound module also grabs the PWM hardware; blacklist it.
echo "blacklist snd_bcm2835" > /etc/modprobe.d/blacklist-rgb-matrix.conf

echo ""
echo "🐍 Creating Python virtual environment at $VENV_DIR..."
chown -R "$ACTUAL_USER":"$ACTUAL_USER" "$INSTALL_DIR"
if [ ! -x "$VENV_DIR/bin/python" ]; then
    as_user python3 -m venv "$VENV_DIR"
fi
as_user "$VENV_DIR/bin/pip" install --upgrade pip wheel
as_user "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
echo "✓ Python dependencies installed"

echo ""
echo "📚 Installing rpi-rgb-led-matrix library (this takes a while on a Pi Zero)..."
RGB_MATRIX_DIR="$USER_HOME/rpi-rgb-led-matrix"
if [ ! -d "$RGB_MATRIX_DIR/.git" ]; then
    as_user git clone --depth 1 https://github.com/hzeller/rpi-rgb-led-matrix.git "$RGB_MATRIX_DIR"
else
    as_user git -C "$RGB_MATRIX_DIR" pull --ff-only || echo "⚠️  Couldn't update $RGB_MATRIX_DIR, using existing copy"
fi
# Upstream builds the Python bindings with `pip install .` from the repo root.
as_user "$VENV_DIR/bin/pip" install "$RGB_MATRIX_DIR"
if "$VENV_DIR/bin/python" -c "import rgbmatrix" 2>/dev/null; then
    echo "✓ rgbmatrix library installed"
else
    echo "❌ rgbmatrix failed to import - see the output above"
    exit 1
fi

echo ""
echo "⚙️  Setting up configuration..."

# Create config from example if it doesn't exist
if [ ! -f "$INSTALL_DIR/config.json" ]; then
    as_user cp "$INSTALL_DIR/config.example.json" "$INSTALL_DIR/config.json"
    echo "✓ Created config.json from template"
    echo ""
    echo "⚠️  IMPORTANT: You must edit config.json and add your Spotify API credentials!"
    echo "   See README.md for instructions on getting Spotify API keys"
else
    echo "✓ config.json already exists"
fi

echo ""
echo "🔧 Installing systemd service..."

# Runs as root so the LED library can use the precise timing hardware; the
# library then immediately drops privileges to $ACTUAL_USER.
cat > /etc/systemd/system/spotify-display.service <<EOF
[Unit]
Description=Spotify LED Matrix Display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=SPOTIFY_DISPLAY_USER=$ACTUAL_USER
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "✓ Systemd service installed"

IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo "✅ Installation complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Add your Spotify API credentials (https://developer.spotify.com/dashboard):"
echo "   nano $INSTALL_DIR/config.json"
echo ""
echo "2. Sign in to Spotify (as your normal user - NOT with sudo):"
echo "   cd $INSTALL_DIR && venv/bin/python src/spotify_auth.py"
echo ""
echo "3. Start the display and enable it on boot:"
echo "   sudo systemctl enable --now spotify-display"
echo ""
echo "4. Open the web interface:"
echo "   http://${IP_ADDR:-<your-pi-ip>}:5000"
echo "   Admin login: admin / changeme  (change this in the admin panel!)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  A reboot is recommended for the audio/Bluetooth changes to take effect:"
echo "   sudo reboot"
echo ""
