#!/usr/bin/env python3
"""
Spotify Authentication Helper
Standalone script to authenticate with Spotify and cache credentials
"""

import os
import sys
import json
from pathlib import Path
import spotipy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spotify_client import make_auth_manager, browser_available
from utils.runtime import cache_dir


def load_config():
    """Load configuration from config.json"""
    config_path = Path('config.json')

    if not config_path.exists():
        print("❌ Error: config.json not found!")
        print("Please run this script from the project root directory.")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in config.json: {e}")
        sys.exit(1)


def main():
    """Main authentication flow"""
    print("""
    ╔══════════════════════════════════════════╗
    ║  Spotify LED Matrix Display              ║
    ║  Authentication Helper                   ║
    ╚══════════════════════════════════════════╝
    """)

    # Load configuration
    print("📋 Loading configuration...")
    config = load_config()
    spotify_config = config.get('spotify', {})

    # Validate configuration
    client_id = spotify_config.get('client_id', '')
    client_secret = spotify_config.get('client_secret', '')

    if not client_id or not client_secret:
        print("❌ Error: Spotify credentials not configured!")
        print("\nPlease edit config.json and add your Spotify API credentials:")
        print("  1. Go to https://developer.spotify.com/dashboard")
        print("  2. Create an app")
        print("  3. Copy Client ID and Client Secret")
        print("  4. Add them to config.json")
        sys.exit(1)

    if client_id == "your_spotify_client_id_here" or client_secret == "your_spotify_client_secret_here":
        print("❌ Error: Please replace placeholder values in config.json")
        print("\nYour Spotify credentials are still set to example values.")
        print("Get real credentials from https://developer.spotify.com/dashboard")
        sys.exit(1)

    print(f"✓ Client ID: {client_id[:10]}...")
    print(f"✓ Client Secret: {client_secret[:10]}...")

    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        print("❌ Please run this as your normal user, not with sudo.")
        print("   The display service reads the login from your home directory.")
        sys.exit(1)

    cache_path = cache_dir()
    cache_file = cache_path / 'spotify_token_cache'
    print(f"✓ Cache directory: {cache_path}")

    # Initialize authentication
    print("\n🔐 Initializing Spotify authentication...")

    has_browser = browser_available()
    if not has_browser:
        print("""
No web browser on this machine (normal for a headless Pi). Here's what to do:
  1. Copy the URL printed below and open it on your phone or computer
  2. Log in to Spotify and click Agree
  3. Your browser lands on a 127.0.0.1:8888 page that won't load - that's OK
  4. Copy that whole URL from the address bar and paste it back here
""")

    try:
        auth_manager = make_auth_manager(spotify_config, open_browser=has_browser)

        # This will open a browser and prompt for authentication
        sp = spotipy.Spotify(auth_manager=auth_manager)

        # Test the authentication
        print("\n🔍 Testing authentication...")
        user = sp.current_user()

        print("\n✅ Authentication successful!")
        print(f"\n👤 Logged in as: {user['display_name']}")
        print(f"📧 Email: {user.get('email', 'N/A')}")
        print(f"🎵 Account type: {user.get('product', 'N/A')}")

        if user.get('product') == 'premium':
            print("✓ Premium account - full API access available")
        else:
            print("⚠️  Warning: Free account - some features may be limited")

        # Try to get currently playing
        print("\n🎵 Checking for currently playing track...")
        current = sp.current_user_playing_track()

        if current and current.get('is_playing'):
            track = current['item']
            print(f"\n♫ Now Playing:")
            print(f"   Track: {track['name']}")
            print(f"   Artist: {track['artists'][0]['name']}")
            print(f"   Album: {track['album']['name']}")
        else:
            print("   No track currently playing")

        print(f"\n💾 Token cached to: {cache_file}")
        print("\n✨ Setup complete! If the display service is already running it will")
        print("   pick up the login within a minute. Otherwise start it with:")
        print("   sudo systemctl enable --now spotify-display")

    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check that Client ID and Secret are correct")
        print("  2. Verify redirect URI matches Spotify dashboard:")
        print(f"     {spotify_config.get('redirect_uri')}")
        print("  3. Ensure you accepted the authorization prompt")
        sys.exit(1)


if __name__ == '__main__':
    main()
