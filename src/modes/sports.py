"""
Sports Mode - Display live scores and game information
"""

import logging
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor

try:
    from espn_api.football import League as NFLLeague
    from espn_api.basketball import League as NBALeague
    ESPN_API_AVAILABLE = True
except ImportError:
    ESPN_API_AVAILABLE = False


class SportsMode:
    """Sports mode - displays live scores and game information"""

    def __init__(self, display, config):
        """
        Initialize sports mode

        Args:
            display: LEDDisplay instance
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config
        self.sports_config = config.get('sports', {})
        self.image_processor = ImageProcessor(config.get('image_processing', {}))

        self.enabled = self.sports_config.get('enabled', False)
        self.league = self.sports_config.get('league', 'NFL')
        self.team = self.sports_config.get('team', 'NO')
        self.update_interval = self.sports_config.get('update_interval', 60)

        self.last_update = 0
        self.game_data = None

        if self.enabled and not ESPN_API_AVAILABLE:
            self.logger.warning("Sports mode enabled but ESPN API not available")
            self.enabled = False

        self.logger.info(f"Sports mode initialized (enabled={self.enabled}, team={self.team})")

    def update(self):
        """Update sports display"""
        if not self.enabled:
            self._display_disabled_message()
            time.sleep(10)
            return

        try:
            # Check if we need to fetch new data
            current_time = time.time()
            if current_time - self.last_update >= self.update_interval or self.game_data is None:
                self.game_data = self._fetch_game_data()
                self.last_update = current_time

            # Display game info
            if self.game_data:
                self._display_game(self.game_data)
            else:
                self._display_no_game()

            time.sleep(5)

        except Exception as e:
            self.logger.error(f"Error in sports mode update: {e}")
            self._display_error()
            time.sleep(10)

    def _fetch_game_data(self):
        """
        Fetch game data for configured team

        Returns:
            dict: Game data or None
        """
        try:
            # This is a simplified implementation
            # Full implementation would use ESPN API or similar

            # For now, return mock data
            game_info = {
                'team_abbr': self.team,
                'opponent_abbr': 'ATL',
                'team_score': 24,
                'opponent_score': 21,
                'status': 'IN_PROGRESS',
                'quarter': '3rd',
                'time_remaining': '7:42'
            }

            self.logger.info(f"Game data: {game_info['team_abbr']} {game_info['team_score']} - {game_info['opponent_score']} {game_info['opponent_abbr']}")
            return game_info

        except Exception as e:
            self.logger.error(f"Error fetching game data: {e}")
            return None

    def _display_game(self, game_data):
        """
        Display game information

        Args:
            game_data: Game data dictionary
        """
        try:
            display_size = self.display.get_size()
            image = Image.new('RGB', display_size, color=(10, 30, 10))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()

            # Score display
            score_text = f"{game_data['team_abbr']} {game_data['team_score']}"
            opp_text = f"{game_data['opponent_score']} {game_data['opponent_abbr']}"

            # Draw team score
            bbox = draw.textbbox((0, 0), score_text, font=font)
            text_width = bbox[2] - bbox[0]
            pos = ((display_size[0] - text_width) // 2, display_size[1] // 3)
            draw.text(pos, score_text, font=font, fill=(255, 255, 255))

            # Draw opponent score
            bbox = draw.textbbox((0, 0), opp_text, font=font)
            text_width = bbox[2] - bbox[0]
            pos = ((display_size[0] - text_width) // 2, display_size[1] // 2)
            draw.text(pos, opp_text, font=font, fill=(200, 200, 200))

            # Draw status
            if game_data['status'] == 'IN_PROGRESS':
                status_text = f"{game_data['quarter']} {game_data['time_remaining']}"
                bbox = draw.textbbox((0, 0), status_text, font=font)
                text_width = bbox[2] - bbox[0]
                pos = ((display_size[0] - text_width) // 2, display_size[1] * 2 // 3)
                draw.text(pos, status_text, font=font, fill=(100, 255, 100))

            self.display.display_image(image)

        except Exception as e:
            self.logger.error(f"Error displaying game: {e}")
            self._display_error()

    def _display_no_game(self):
        """Display message when no game is active"""
        display_size = self.display.get_size()
        placeholder = self.image_processor.create_text_image(
            f"{self.team}\nNo Game",
            display_size,
            color=(100, 100, 100)
        )
        self.display.display_image(placeholder)

    def _display_disabled_message(self):
        """Display message when sports mode is disabled"""
        display_size = self.display.get_size()
        placeholder = self.image_processor.create_text_image(
            "Sports\nDisabled",
            display_size,
            color=(100, 100, 100)
        )
        self.display.display_image(placeholder)

    def _display_error(self):
        """Display error message"""
        display_size = self.display.get_size()
        error = self.image_processor.create_text_image(
            "Sports\nError",
            display_size,
            color=(255, 100, 100)
        )
        self.display.display_image(error)
