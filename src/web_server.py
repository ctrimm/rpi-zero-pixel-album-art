"""
Web Server - Flask-based web interface for controlling the display
"""

import logging
import os
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_from_directory
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

        # Setup routes
        self._setup_routes()

        self.logger.info("Web server initialized")

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.flask_app.route('/')
        def index():
            """Serve main page"""
            return send_from_directory('../web', 'index.html')

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
