// Spotify LED Matrix Display - Web Interface JavaScript

// API base URL (adjust if needed)
const API_BASE = window.location.origin;

// Auto-refresh interval (ms)
const REFRESH_INTERVAL = 5000;
let refreshTimer = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Spotify LED Matrix Display interface...');
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

        // Also fetch current track if in music mode
        if (status.current_mode === 'music') {
            fetchCurrentTrack();
        }

    } catch (error) {
        console.error('Error fetching status:', error);
        updateConnectionStatus(false);
    }

    updateLastUpdateTime();
}

// Update UI with status data
function updateUI(status) {
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
    const spotifyStatus = status.spotify_playing ? 'Playing' : 'Not Playing';
    document.getElementById('spotifyStatus').textContent = spotifyStatus;

    // Update display status
    document.getElementById('displayStatus').textContent = status.running ? 'Active' : 'Stopped';
}

// Fetch current Spotify track
async function fetchCurrentTrack() {
    try {
        const response = await fetch(`${API_BASE}/api/spotify/current`);
        if (!response.ok) throw new Error('Failed to fetch track');

        const track = await response.json();

        if (track && track.track_name) {
            displayTrackInfo(track);
        } else {
            displayNoTrack();
        }

    } catch (error) {
        console.error('Error fetching current track:', error);
        displayNoTrack();
    }
}

// Display track information
function displayTrackInfo(track) {
    document.getElementById('trackName').textContent = track.track_name || '-';
    document.getElementById('artistName').textContent = track.artist_name || '-';
    document.getElementById('albumName').textContent = track.album_name || '-';

    const albumArtDiv = document.getElementById('albumArt');
    if (track.album_art_url) {
        albumArtDiv.innerHTML = `<img src="${track.album_art_url}" alt="${track.album_name}">`;
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
        alert('Test pattern displayed on LED matrix');

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
