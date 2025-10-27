#!/bin/bash
# Mac Development Setup Script
# Creates virtual environment and installs dependencies

set -e

echo "🍎 Setting up development environment on Mac..."
echo ""

# Check Python version
echo "📍 Checking Python version..."
python3 --version

# Create virtual environment
echo ""
echo "🔧 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "✓ Virtual environment created"
echo ""
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "📚 Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 NEXT STEPS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Configure Spotify credentials:"
echo "   cp config.example.json config.json"
echo "   nano config.json"
echo ""
echo "2. Activate virtual environment (do this every time):"
echo "   source venv/bin/activate"
echo ""
echo "3. Authenticate with Spotify:"
echo "   python3 src/spotify_auth.py"
echo ""
echo "4. Run the simulator:"
echo "   python3 dev_run.py"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 TIP: Add 'source venv/bin/activate' to your shell startup file"
echo "    to automatically activate the environment in this directory"
echo ""
