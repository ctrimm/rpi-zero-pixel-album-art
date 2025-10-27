#!/usr/bin/env python3
"""
Development Mode Launcher
Runs the LED Matrix Display with visual simulator on Mac/dev machines
"""

import os
import sys

# Force simulator mode
os.environ['LED_SIMULATOR'] = '1'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("""
╔══════════════════════════════════════════════════════════════╗
║     LED Matrix Display - DEVELOPMENT MODE                   ║
║     Visual Simulator for Mac/Windows/Linux                  ║
╚══════════════════════════════════════════════════════════════╝

🖥️  Running with LED Matrix Simulator
🪟  A window will open showing the 64x64 display
💡  All features work exactly like on the real Pi
🔄  Changes update in real-time

Press Ctrl+C to stop
""")

# Import and run main
from src.main import main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down development server...")
        sys.exit(0)
