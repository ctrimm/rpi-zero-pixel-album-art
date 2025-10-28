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
        # Always show demo data if ESPN API is not available or not configured
        show_demo = not self.enabled or not ESPN_API_AVAILABLE

        try:
            # Check if we need to fetch new data
            current_time = time.time()
            if current_time - self.last_update >= self.update_interval or self.game_data is None:
                self.game_data = self._fetch_game_data(demo=show_demo)
                self.last_update = current_time

            # Display game info
            if self.game_data:
                self._display_game(self.game_data, demo=show_demo)
            else:
                self._display_no_game()

            time.sleep(5)

        except Exception as e:
            self.logger.error(f"Error in sports mode update: {e}")
            self._display_error()
            time.sleep(10)

    def _fetch_game_data(self, demo=False):
        """
        Fetch game data for configured team

        Args:
            demo: If True, return demo/mock data

        Returns:
            dict: Game data or None
        """
        try:
            if demo or not self.enabled:
                # Return demo data showing a close game with stats
                import random

                # Vary the score slightly each time for visual interest
                team_score = random.randint(17, 31)
                opp_score = team_score + random.randint(-7, 7)

                game_info = {
                    'team_abbr': self.team,
                    'opponent_abbr': 'ATL',
                    'team_score': max(0, team_score),
                    'opponent_score': max(0, opp_score),
                    'status': 'DEMO',  # Mark as demo
                    'quarter': '3rd',
                    'time_remaining': '7:42',
                    'demo': True,
                    # Add some stats
                    'team_stats': {
                        'passing_yards': 287,
                        'rushing_yards': 112,
                        'turnovers': 1
                    },
                    'opp_stats': {
                        'passing_yards': 245,
                        'rushing_yards': 98,
                        'turnovers': 2
                    }
                }

                self.logger.info(f"Demo game data: {game_info['team_abbr']} {game_info['team_score']} - {game_info['opponent_score']} {game_info['opponent_abbr']}")
                return game_info

            # Real ESPN API implementation would go here
            # For now, even with enabled=True, we show demo data
            return self._fetch_game_data(demo=True)

        except Exception as e:
            self.logger.error(f"Error fetching game data: {e}")
            return None

    def _display_game(self, game_data, demo=False):
        """
        Display game information

        Args:
            game_data: Game data dictionary
            demo: If True, show demo indicator
        """
        try:
            display_size = self.display.get_size()
            width, height = display_size

            # Create multi-screen display that cycles through different views
            current_second = int(time.time() % 15)  # Cycle every 15 seconds

            if current_second < 5:
                # Screen 1: Score
                self._display_score_screen(game_data, demo)
            elif current_second < 10:
                # Screen 2: Team stats
                self._display_stats_screen(game_data, team=True)
            else:
                # Screen 3: Opponent stats
                self._display_stats_screen(game_data, team=False)

        except Exception as e:
            self.logger.error(f"Error displaying game: {e}")
            self._display_error()

    def _display_score_screen(self, game_data, demo=False):
        """Display the score screen"""
        display_size = self.display.get_size()
        width, height = display_size

        # Green field background
        image = Image.new('RGB', display_size, color=(20, 60, 20))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Determine colors based on who's winning
        team_score = game_data['team_score']
        opp_score = game_data['opponent_score']

        team_color = (100, 255, 100) if team_score > opp_score else (255, 255, 255)
        opp_color = (100, 255, 100) if opp_score > team_score else (200, 200, 200)

        # Draw team abbr and score (top)
        team_text = game_data['team_abbr']
        score_text = str(team_score)

        draw.text((2, 8), team_text, font=font, fill=team_color)
        draw.text((width - 15, 8), score_text, font=font, fill=team_color)

        # Draw VS in middle
        draw.text((width // 2 - 6, height // 2 - 4), "VS", font=font, fill=(180, 180, 180))

        # Draw opponent abbr and score (bottom)
        opp_text = game_data['opponent_abbr']
        opp_score_text = str(opp_score)

        draw.text((2, height - 16), opp_text, font=font, fill=opp_color)
        draw.text((width - 15, height - 16), opp_score_text, font=font, fill=opp_color)

        # Draw status/quarter
        if game_data.get('demo'):
            status_text = "DEMO"
            draw.text((2, 2), status_text, font=font, fill=(255, 200, 100))
        elif game_data['status'] == 'IN_PROGRESS':
            status_text = game_data['quarter']
            draw.text((width // 2 - 8, 2), status_text, font=font, fill=(255, 200, 100))

        self.display.display_image(image)

    def _display_stats_screen(self, game_data, team=True):
        """Display team or opponent stats"""
        display_size = self.display.get_size()
        width, height = display_size

        image = Image.new('RGB', display_size, color=(10, 10, 40))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        if team:
            abbr = game_data['team_abbr']
            stats = game_data.get('team_stats', {})
            color = (100, 200, 255)
        else:
            abbr = game_data['opponent_abbr']
            stats = game_data.get('opp_stats', {})
            color = (255, 150, 100)

        # Draw team name
        draw.text((2, 2), abbr, font=font, fill=color)
        draw.text((width - 30, 2), "STATS", font=font, fill=(150, 150, 150))

        # Draw stats
        y_pos = 14
        if 'passing_yards' in stats:
            text = f"Pass: {stats['passing_yards']}"
            draw.text((2, y_pos), text, font=font, fill=(255, 255, 255))
            y_pos += 10

        if 'rushing_yards' in stats:
            text = f"Rush: {stats['rushing_yards']}"
            draw.text((2, y_pos), text, font=font, fill=(255, 255, 255))
            y_pos += 10

        if 'turnovers' in stats:
            text = f"TO: {stats['turnovers']}"
            to_color = (255, 100, 100) if stats['turnovers'] > 0 else (100, 255, 100)
            draw.text((2, y_pos), text, font=font, fill=to_color)

        self.display.display_image(image)

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
