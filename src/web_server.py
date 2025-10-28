"""
Web Server - Flask-based web interface for controlling the display
"""

import logging
import os
import json
import hashlib
import secrets
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, jsonify, request, send_from_directory, session, redirect, url_for
from flask_cors import CORS


class WebServer:
    """Web server for display control and status"""

    def __init__(self, config, app_instance):
        """
        Initialize web server

        Args:
            config: Web server configuration
            app_instance: Main application instance
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.app_instance = app_instance

        # Create Flask app
        self.flask_app = Flask(
            __name__,
            static_folder='../web',
            template_folder='../web'
        )
        CORS(self.flask_app)

        # Setup session secret key
        self.flask_app.secret_key = self.config.get('secret_key', secrets.token_hex(32))

        # Admin credentials (in production, use proper password hashing and database)
        self.admin_username = self.config.get('admin_username', 'admin')
        self.admin_password_hash = self._hash_password(
            self.config.get('admin_password', 'changeme')
        )

        # Setup routes
        self._setup_routes()

        self.logger.info("Web server initialized")

    def _hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def _check_password(self, password):
        """Check if password is correct"""
        return self._hash_password(password) == self.admin_password_hash

    def _login_required(self, f):
        """Decorator to require login for admin routes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('authenticated'):
                return jsonify({'error': 'Authentication required'}), 401
            return f(*args, **kwargs)
        return decorated_function

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.flask_app.route('/')
        def index():
            """Serve main page"""
            return send_from_directory('../web', 'index.html')

        @self.flask_app.route('/style.css')
        def serve_css():
            """Serve CSS file"""
            return send_from_directory('../web', 'style.css')

        @self.flask_app.route('/script.js')
        def serve_js():
            """Serve JavaScript file"""
            return send_from_directory('../web', 'script.js')

        @self.flask_app.route('/admin')
        def admin():
            """Serve admin panel page"""
            return send_from_directory('../web', 'admin.html')

        @self.flask_app.route('/login')
        def login_page():
            """Serve login page"""
            return send_from_directory('../web', 'login.html')

        @self.flask_app.route('/api/auth/login', methods=['POST'])
        def login():
            """Authenticate user"""
            try:
                data = request.get_json()
                username = data.get('username')
                password = data.get('password')

                if not username or not password:
                    return jsonify({'error': 'Username and password required'}), 400

                if username == self.admin_username and self._check_password(password):
                    session['authenticated'] = True
                    session['username'] = username
                    self.logger.info(f"User {username} logged in")
                    return jsonify({'status': 'success', 'message': 'Login successful'})
                else:
                    self.logger.warning(f"Failed login attempt for user {username}")
                    return jsonify({'error': 'Invalid credentials'}), 401

            except Exception as e:
                self.logger.error(f"Error during login: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/auth/logout', methods=['POST'])
        def logout():
            """Logout user"""
            session.clear()
            return jsonify({'status': 'success', 'message': 'Logged out'})

        @self.flask_app.route('/api/auth/check')
        def check_auth():
            """Check if user is authenticated"""
            return jsonify({'authenticated': session.get('authenticated', False)})

        @self.flask_app.route('/api/status')
        def get_status():
            """Get current status"""
            try:
                status = self.app_instance.get_status()
                return jsonify(status)
            except Exception as e:
                self.logger.error(f"Error getting status: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/mode', methods=['POST'])
        def set_mode():
            """Switch display mode"""
            try:
                data = request.get_json()
                mode = data.get('mode')

                if not mode:
                    return jsonify({'error': 'Mode not specified'}), 400

                success = self.app_instance.switch_mode(mode)

                if success:
                    return jsonify({'status': 'success', 'mode': mode})
                else:
                    return jsonify({'error': 'Invalid mode'}), 400

            except Exception as e:
                self.logger.error(f"Error setting mode: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/brightness', methods=['POST'])
        def set_brightness():
            """Set display brightness"""
            try:
                data = request.get_json()
                brightness = data.get('brightness')

                if brightness is None:
                    return jsonify({'error': 'Brightness not specified'}), 400

                self.app_instance.set_brightness(int(brightness))
                return jsonify({'status': 'success', 'brightness': brightness})

            except Exception as e:
                self.logger.error(f"Error setting brightness: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/spotify/current')
        def get_current_track():
            """Get currently playing track"""
            try:
                if self.app_instance.spotify:
                    track = self.app_instance.spotify.get_current_track()
                    if track:
                        return jsonify(track)
                    else:
                        return jsonify({'message': 'Nothing playing'})
                else:
                    return jsonify({'error': 'Spotify not available'}), 503

            except Exception as e:
                self.logger.error(f"Error getting current track: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/display/test')
        def test_display():
            """Display test pattern"""
            try:
                if self.app_instance.display:
                    self.app_instance.display.test_pattern()
                    return jsonify({'status': 'success', 'message': 'Test pattern displayed'})
                else:
                    return jsonify({'error': 'Display not available'}), 503

            except Exception as e:
                self.logger.error(f"Error displaying test pattern: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/display/clear')
        def clear_display():
            """Clear display"""
            try:
                if self.app_instance.display:
                    self.app_instance.display.clear()
                    return jsonify({'status': 'success', 'message': 'Display cleared'})
                else:
                    return jsonify({'error': 'Display not available'}), 503

            except Exception as e:
                self.logger.error(f"Error clearing display: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/admin/config', methods=['GET'])
        @self._login_required
        def get_config():
            """Get current configuration (admin only)"""
            try:
                config = self.app_instance.config_manager.config
                return jsonify(config)
            except Exception as e:
                self.logger.error(f"Error getting config: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/admin/config', methods=['POST'])
        @self._login_required
        def update_config():
            """Update configuration (admin only)"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No configuration data provided'}), 400

                # Update the configuration
                success = self.app_instance.update_config(data)

                if success:
                    return jsonify({
                        'status': 'success',
                        'message': 'Configuration updated successfully'
                    })
                else:
                    return jsonify({'error': 'Failed to update configuration'}), 500

            except Exception as e:
                self.logger.error(f"Error updating config: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/admin/config/validate', methods=['POST'])
        @self._login_required
        def validate_config():
            """Validate configuration without applying (admin only)"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No configuration data provided'}), 400

                # Validate the configuration
                valid, errors = self.app_instance.config_manager.validate_config(data)

                if valid:
                    return jsonify({
                        'valid': True,
                        'message': 'Configuration is valid'
                    })
                else:
                    return jsonify({
                        'valid': False,
                        'errors': errors
                    }), 400

            except Exception as e:
                self.logger.error(f"Error validating config: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/health')
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'running': self.app_instance.running
            })

    def start(self):
        """Start the web server"""
        try:
            host = self.config.get('host', '0.0.0.0')
            port = self.config.get('port', 5000)
            debug = self.config.get('debug', False)

            self.logger.info(f"Starting web server on {host}:{port}")

            self.flask_app.run(
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,  # Disable reloader in production
                threaded=True
            )

        except Exception as e:
            self.logger.error(f"Error starting web server: {e}")
            raise

    def stop(self):
        """Stop the web server"""
        self.logger.info("Stopping web server")
        # Flask doesn't have a built-in stop method when running with .run()
        # In production, use a proper WSGI server like gunicorn
