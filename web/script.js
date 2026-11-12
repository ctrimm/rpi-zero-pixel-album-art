// Spotify LED Matrix Display - Web Interface JavaScript

// API base URL (adjust if needed)
const API_BASE = window.location.origin;

// Auto-refresh interval (ms)
const REFRESH_INTERVAL = 5000;
let refreshTimer = null;

// Auth state
let isAuthenticated = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Spotify LED Matrix Display interface...');
    checkAuthentication();
    refreshStatus();
    startAutoRefresh();
});

// Start automatic status refresh
function startAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    refreshTimer = setInterval(refreshStatus, REFRESH_INTERVAL);
}

// Stop automatic refresh
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// Refresh status from API
async function refreshStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        if (!response.ok) throw new Error('Failed to fetch status');

        const status = await response.json();
        updateUI(status);
        updateConnectionStatus(true);

        // /api/status already includes the current track, so there's no
        // need for a second request every refresh
        if (status.current_track && status.current_track.track_name) {
            displayTrackInfo(status.current_track);
        } else {
            displayNoTrack();
        }

    } catch (error) {
        console.error('Error fetching status:', error);
        updateConnectionStatus(false);
    }

    updateLastUpdateTime();
}

// Update UI with status data
// Friendly names for mode buttons the page doesn't have built in
const MODE_LABELS = {
    music: '🎵 Music', weather: '🌤️ Weather', sports: '⚽ Sports', clock: '🕐 Clock',
    pipes: '🔧 Pipes', dvd_logo: '📀 DVD Logo', screensaver: '✨ Screensaver',
};

// Match the mode buttons to the modes this server actually supports (the
// Matrix Portal companion has a different set than the Pi app).
function syncModeButtons(modes) {
    if (!Array.isArray(modes) || !modes.length) return;
    const selector = document.querySelector('.mode-selector');
    if (!selector) return;
    modes.forEach(mode => {
        if (!selector.querySelector(`.mode-btn[data-mode="${mode}"]`)) {
            const btn = document.createElement('button');
            btn.className = 'mode-btn';
            btn.dataset.mode = mode;
            btn.textContent = MODE_LABELS[mode] || mode;
            btn.addEventListener('click', () => switchMode(mode));
            selector.appendChild(btn);
        }
    });
    selector.querySelectorAll('.mode-btn').forEach(btn => {
        btn.style.display = modes.includes(btn.dataset.mode) ? '' : 'none';
    });
}

function updateUI(status) {
    syncModeButtons(status.available_modes);
    // Servers without the Pi's config layout use the admin panel only
    if (status.quick_settings === false) {
        const quick = document.getElementById('settingsSection');
        if (quick) { quick.dataset.disabled = '1'; quick.style.display = 'none'; }
    }

    // Update current mode
    document.getElementById('currentMode').textContent = status.current_mode || '-';

    // Update mode buttons
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === status.current_mode);
    });

    // Update brightness
    if (status.brightness !== undefined) {
        document.getElementById('brightnessSlider').value = status.brightness;
        document.getElementById('brightnessValue').textContent = status.brightness;
    }

    // Update Spotify status
    const spotifyStatus = status.spotify_connected === false
        ? 'Not linked'
        : (status.spotify_playing ? 'Playing' : 'Not Playing');
    document.getElementById('spotifyStatus').textContent = spotifyStatus;

    // Update display status
    document.getElementById('displayStatus').textContent = status.running ? 'Active' : 'Stopped';
}

// Display track information
function displayTrackInfo(track) {
    document.getElementById('trackName').textContent = track.track_name || '-';
    document.getElementById('artistName').textContent = track.artist_name || '-';
    document.getElementById('albumName').textContent = track.album_name || '-';

    const albumArtDiv = document.getElementById('albumArt');
    if (track.album_art_url) {
        // Only swap the <img> when the art actually changes (avoids a flicker
        // and a re-download every 5s refresh). Built via DOM, not innerHTML,
        // so album names with quotes/HTML can't break the markup.
        const existing = albumArtDiv.querySelector('img');
        if (!existing || existing.src !== track.album_art_url) {
            const img = document.createElement('img');
            img.src = track.album_art_url;
            img.alt = track.album_name || '';
            albumArtDiv.replaceChildren(img);
        }
    } else {
        albumArtDiv.innerHTML = '<div class="placeholder">No Album Art</div>';
    }
}

// Display "no track" state
function displayNoTrack() {
    document.getElementById('trackName').textContent = '-';
    document.getElementById('artistName').textContent = '-';
    document.getElementById('albumName').textContent = '-';
    document.getElementById('albumArt').innerHTML = '<div class="placeholder">No Music Playing</div>';
}

// Switch display mode
async function switchMode(mode) {
    try {
        const response = await fetch(`${API_BASE}/api/mode`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ mode })
        });

        if (!response.ok) throw new Error('Failed to switch mode');

        const result = await response.json();
        console.log(`Switched to ${mode} mode`);

        // Update UI immediately
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        document.getElementById('currentMode').textContent = mode;

        // Refresh status
        setTimeout(refreshStatus, 500);

    } catch (error) {
        console.error('Error switching mode:', error);
        alert(`Failed to switch to ${mode} mode`);
    }
}

// Update brightness
let brightnessTimeout = null;
async function updateBrightness(value) {
    // Update display immediately
    document.getElementById('brightnessValue').textContent = value;

    // Debounce API calls
    if (brightnessTimeout) {
        clearTimeout(brightnessTimeout);
    }

    brightnessTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/brightness`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ brightness: parseInt(value) })
            });

            if (!response.ok) throw new Error('Failed to set brightness');

            console.log(`Brightness set to ${value}`);

        } catch (error) {
            console.error('Error setting brightness:', error);
        }
    }, 300);
}

// Test display pattern
async function testDisplay() {
    try {
        const response = await fetch(`${API_BASE}/api/display/test`);
        if (!response.ok) throw new Error('Failed to display test pattern');

        console.log('Test pattern displayed');
        alert('Test pattern is showing on the LED matrix for 5 seconds');

    } catch (error) {
        console.error('Error displaying test pattern:', error);
        alert('Failed to display test pattern');
    }
}

// Clear display
async function clearDisplay() {
    try {
        const response = await fetch(`${API_BASE}/api/display/clear`);
        if (!response.ok) throw new Error('Failed to clear display');

        console.log('Display cleared');

    } catch (error) {
        console.error('Error clearing display:', error);
        alert('Failed to clear display');
    }
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    const statusText = document.getElementById('statusText');
    const dot = document.querySelector('.status-indicator .dot');

    if (connected) {
        statusText.textContent = 'Connected';
        dot.style.background = '#1DB954';
    } else {
        statusText.textContent = 'Disconnected';
        dot.style.background = '#FF0000';
    }
}

// Update last update time
function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    document.getElementById('lastUpdate').textContent = timeString;
}

// Error handling
window.addEventListener('error', (event) => {
    console.error('JavaScript error:', event.error);
});

// Handle page visibility changes (pause refresh when hidden)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        refreshStatus();
        startAutoRefresh();
    }
});

// ===== AUTHENTICATION =====

async function checkAuthentication() {
    try {
        const response = await fetch(`${API_BASE}/api/auth/check`);
        const data = await response.json();

        isAuthenticated = data.authenticated || false;
        updateAuthUI();

        if (isAuthenticated) {
            loadSettings();
        }
    } catch (error) {
        console.error('Error checking authentication:', error);
        isAuthenticated = false;
        updateAuthUI();
    }
}

function updateAuthUI() {
    const authBtn = document.getElementById('authBtn');
    const settingsSection = document.getElementById('settingsSection');

    if (isAuthenticated) {
        authBtn.textContent = 'Logout';
        authBtn.classList.add('logout');
        settingsSection.style.display = settingsSection.dataset.disabled ? 'none' : 'block';
    } else {
        authBtn.textContent = 'Login';
        authBtn.classList.remove('logout');
        settingsSection.style.display = 'none';
    }
}

async function handleAuth() {
    if (isAuthenticated) {
        // Logout
        try {
            await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST' });
            isAuthenticated = false;
            updateAuthUI();
            alert('Logged out successfully');
        } catch (error) {
            console.error('Error logging out:', error);
        }
    } else {
        // Redirect to login page
        window.location.href = '/login';
    }
}

// ===== SETTINGS =====

async function loadSettings() {
    if (!isAuthenticated) {
        alert('Please login to view settings');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/admin/config`);
        if (!response.ok) throw new Error('Failed to load settings');

        const config = await response.json();

        // Display settings
        document.getElementById('defaultMode').value = config.modes?.default || 'music';
        document.getElementById('autoSwitch').checked = config.modes?.auto_switch !== false;

        // Weather settings
        document.getElementById('weatherEnabled').checked = config.weather?.enabled || false;
        document.getElementById('weatherApiKey').value = config.weather?.api_key || '';
        document.getElementById('weatherLocation').value = config.weather?.location || 'New York,US';

        // Sports settings
        document.getElementById('sportsEnabled').checked = config.sports?.enabled || false;
        document.getElementById('sportsLeague').value = config.sports?.league || 'NFL';
        document.getElementById('sportsTeam').value = config.sports?.team || '';

        // Screensaver settings
        document.getElementById('pipesEnabled').checked = config.screensavers?.pipes?.enabled !== false;
        document.getElementById('dvdLogoEnabled').checked = config.screensavers?.dvd_logo?.enabled !== false;

        console.log('Settings loaded successfully');
    } catch (error) {
        console.error('Error loading settings:', error);
        alert('Failed to load settings. Please check authentication.');
    }
}

async function saveSettings() {
    if (!isAuthenticated) {
        alert('Please login to save settings');
        return;
    }

    try {
        // Get current config first
        const response = await fetch(`${API_BASE}/api/admin/config`);
        if (!response.ok) throw new Error('Failed to load current config');

        const config = await response.json();

        // Update with form values
        config.modes = config.modes || {};
        config.modes.default = document.getElementById('defaultMode').value;
        config.modes.auto_switch = document.getElementById('autoSwitch').checked;

        config.weather = config.weather || {};
        config.weather.enabled = document.getElementById('weatherEnabled').checked;
        config.weather.api_key = document.getElementById('weatherApiKey').value;
        config.weather.location = document.getElementById('weatherLocation').value;

        config.sports = config.sports || {};
        config.sports.enabled = document.getElementById('sportsEnabled').checked;
        config.sports.league = document.getElementById('sportsLeague').value;
        config.sports.team = document.getElementById('sportsTeam').value;

        config.screensavers = config.screensavers || {};
        config.screensavers.pipes = config.screensavers.pipes || {};
        config.screensavers.pipes.enabled = document.getElementById('pipesEnabled').checked;
        config.screensavers.dvd_logo = config.screensavers.dvd_logo || {};
        config.screensavers.dvd_logo.enabled = document.getElementById('dvdLogoEnabled').checked;

        // Save config
        const saveResponse = await fetch(`${API_BASE}/api/admin/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        if (!saveResponse.ok) {
            const error = await saveResponse.json();
            throw new Error(error.error || 'Failed to save settings');
        }

        alert('✓ Settings saved successfully! Changes applied immediately.');
        refreshStatus();
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Failed to save settings: ' + error.message);
    }
}
