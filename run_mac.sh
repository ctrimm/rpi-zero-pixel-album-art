#!/bin/bash
# Quick run script for Mac development
# Automatically activates venv if needed

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: bash setup_mac.sh"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set simulator mode
export LED_SIMULATOR=1

# Run the application
echo "🚀 Starting LED Matrix Simulator..."
echo "🪟 A window will open showing the 64x64 display"
echo ""
python3 src/main.py
