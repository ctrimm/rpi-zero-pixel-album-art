#!/usr/bin/env bash
# install_service.sh — install the Matrix Portal companion as a background
# service that starts on login/boot. Supports macOS (launchd) and Linux (systemd --user).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPANION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$COMPANION_DIR/.." && pwd)"
PYTHON="$COMPANION_DIR/venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "❌ Virtualenv not found at $PYTHON"
    echo "   Create it first:"
    echo "     cd $COMPANION_DIR && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

OS="$(uname -s)"
case "$OS" in
    Darwin)
        PLIST="$HOME/Library/LaunchAgents/com.matrixportal.companion.plist"
        echo "🍎 Installing launchd agent → $PLIST"
        mkdir -p "$HOME/Library/LaunchAgents"
        sed "s#__REPO__#$REPO_DIR#g" "$SCRIPT_DIR/com.matrixportal.companion.plist" > "$PLIST"
        launchctl unload "$PLIST" 2>/dev/null || true
        launchctl load "$PLIST"
        echo "✓ Loaded. Logs: /tmp/matrixportal-companion.log"
        echo "  Stop with:  launchctl unload $PLIST"
        ;;
    Linux)
        UNIT_DIR="$HOME/.config/systemd/user"
        echo "🐧 Installing systemd user service → $UNIT_DIR/matrix-portal-companion.service"
        mkdir -p "$UNIT_DIR"
        # %h expands to the user home inside systemd; the unit assumes the repo
        # is at ~/rpi-zero-pixel-album-art. Rewrite if it lives elsewhere.
        sed "s#%h/rpi-zero-pixel-album-art#$REPO_DIR#g" \
            "$SCRIPT_DIR/matrix-portal-companion.service" > "$UNIT_DIR/matrix-portal-companion.service"
        systemctl --user daemon-reload
        systemctl --user enable --now matrix-portal-companion.service
        echo "✓ Started. Status:  systemctl --user status matrix-portal-companion"
        echo "  (Run 'loginctl enable-linger $USER' to keep it running while logged out.)"
        ;;
    *)
        echo "❌ Unsupported OS: $OS (install manually using the files in $SCRIPT_DIR)"
        exit 1
        ;;
esac
