#!/bin/bash
# Raspberry Pi Spotify LED Matrix Display - Installation Script

set -e  # Exit on error

echo "======================================"
echo "Spotify LED Matrix Display Installer"
echo "======================================"
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null && ! grep -q "BCM" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "Installation will continue, but LED matrix may not work without hardware"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for root/sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run with sudo"
    echo "Usage: sudo bash install.sh"
    exit 1
fi

# Get the actual user (not root when using sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$ACTUAL_USER)

echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    build-essential \
    libatlas-base-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev

echo ""
echo "🔧 Configuring Raspberry Pi for LED matrix..."

# Pi OS Bookworm (2023+) moved the boot config to /boot/firmware/.
# Detect the correct location so these tweaks don't silently land in a file
# that the bootloader never reads.
BOOT_DIR="/boot/firmware"
[ -f "$BOOT_DIR/config.txt" ] || BOOT_DIR="/boot"
CONFIG_TXT="$BOOT_DIR/config.txt"
CMDLINE_TXT="$BOOT_DIR/cmdline.txt"
echo "✓ Using boot config at $CONFIG_TXT"

# Disable audio (conflicts with LED matrix PWM)
if ! grep -q "dtparam=audio=off" "$CONFIG_TXT"; then
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
if grep -q "Raspberry Pi 4" /proc/cpuinfo; then
    if ! grep -q "isolcpus=3" "$CMDLINE_TXT"; then
        sed -i '$ s/$/ isolcpus=3/' "$CMDLINE_TXT"
        echo "✓ Isolated CPU core 3 for LED matrix (Pi 4)"
    fi
fi

echo ""
echo "📚 Installing rpi-rgb-led-matrix library..."

# Clone and build rpi-rgb-led-matrix if not already present
RGB_MATRIX_DIR="$USER_HOME/rpi-rgb-led-matrix"
if [ ! -d "$RGB_MATRIX_DIR" ]; then
    sudo -u $ACTUAL_USER git clone https://github.com/hzeller/rpi-rgb-led-matrix.git "$RGB_MATRIX_DIR"
    cd "$RGB_MATRIX_DIR"
    make build-python PYTHON=$(which python3)
    make install-python PYTHON=$(which python3)
    echo "✓ rpi-rgb-led-matrix library installed"
else
    echo "✓ rpi-rgb-led-matrix already installed"
fi

echo ""
echo "🐍 Installing Python dependencies..."

# Get current directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

# Install Python requirements
pip3 install -r requirements.txt
echo "✓ Python dependencies installed"

echo ""
echo "⚙️  Setting up configuration..."

# Create config from example if it doesn't exist
if [ ! -f config.json ]; then
    cp config.example.json config.json
    echo "✓ Created config.json from template"
    echo ""
    echo "⚠️  IMPORTANT: You must edit config.json and add your Spotify API credentials!"
    echo "   See README.md for instructions on getting Spotify API keys"
else
    echo "✓ config.json already exists"
fi

# Set correct ownership
chown -R $ACTUAL_USER:$ACTUAL_USER "$INSTALL_DIR"

echo ""
echo "🔧 Installing systemd service..."

# Create systemd service file
cat > /etc/systemd/system/spotify-display.service <<EOF
[Unit]
Description=Spotify LED Matrix Display
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload
echo "✓ Systemd service installed"

echo ""
echo "✅ Installation complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Configure Spotify API credentials:"
echo "   nano config.json"
echo ""
echo "2. Get Spotify API credentials from:"
echo "   https://developer.spotify.com/dashboard"
echo ""
echo "3. (Optional) Configure weather and sports:"
echo "   - OpenWeatherMap API: https://openweathermap.org/api"
echo "   - Edit config.json to enable and configure"
echo ""
echo "4. Test the display:"
echo "   python3 src/main.py"
echo ""
echo "5. Enable auto-start on boot:"
echo "   sudo systemctl enable spotify-display"
echo "   sudo systemctl start spotify-display"
echo ""
echo "6. Access web interface:"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  A reboot is recommended for all changes to take effect:"
echo "   sudo reboot"
echo ""
