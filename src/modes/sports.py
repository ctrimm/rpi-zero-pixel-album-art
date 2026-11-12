"""
Sports Mode - Display live scores and game information

Uses ESPN's public scoreboard feed (no API key needed) to find the configured
team's game for the current week/day and shows the score, game clock and team
records. When sports is disabled in the config it shows clearly-labelled demo
data instead, so the mode can still be previewed.
"""

import logging
import random
import time
from datetime import datetime, timezone

import requests
from PIL import Image, ImageDraw, ImageFont
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_processor import ImageProcessor
from utils.runtime import mode_sleep

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"

LEAGUE_PATHS = {
    'NFL': 'football/nfl',
    'NBA': 'basketball/nba',
    'WNBA': 'basketball/wnba',
    'MLB': 'baseball/mlb',
    'NHL': 'hockey/nhl',
    'MLS': 'soccer/usa.1',
    'NCAAF': 'football/college-football',
    'NCAAM': 'basketball/mens-college-basketball',
}

# How often to refresh when there's no live game (seconds)
IDLE_REFRESH = 600


class SportsMode:
    """Sports mode - displays live scores and game information"""

    def __init__(self, display, config):
        self.logger = logging.getLogger(__name__)
        self.display = display
        self.config = config
        self.sports_config = config.get('sports', {})
        self.image_processor = ImageProcessor(config.get('image_processing', {}))

        self.enabled = self.sports_config.get('enabled', False)
        self.league = str(self.sports_config.get('league', 'NFL')).upper()
        self.team = str(self.sports_config.get('team', 'NO')).upper()
        self.update_interval = self.sports_config.get('update_interval', 60)

        self.last_update = 0
        self.game_data = None
        self.fetch_failed = False

        if self.enabled and self.league not in LEAGUE_PATHS:
            self.logger.warning(
                f"Unknown league '{self.league}'. Supported: {', '.join(LEAGUE_PATHS)}"
            )

        self.logger.info(f"Sports mode initialized (enabled={self.enabled}, league={self.league}, team={self.team})")

    # ------------------------------------------------------------------ update

    def update(self):
        """Update sports display"""
        try:
            now = time.time()
            if self._needs_refresh(now):
                if self.enabled:
                    data = self._fetch_game_data()
                    # Keep showing the last good data through a brief outage
                    if data is not None or not self.fetch_failed:
                        self.game_data = data
                else:
                    self.game_data = self._demo_game_data()
                self.last_update = now

            if self.enabled and self.fetch_failed and self.game_data is None:
                self._display_message("Sports\nOffline", (255, 120, 100))
            elif self.game_data:
                self._display_game(self.game_data)
            else:
                self._display_message(f"{self.team}\nNo game", (140, 140, 140))

            mode_sleep(5)

        except Exception as e:
            self.logger.error(f"Error in sports mode update: {e}", exc_info=True)
            self._display_message("Sports\nError", (255, 100, 100))
            mode_sleep(10)

    def _needs_refresh(self, now):
        if self.game_data is None and self.last_update == 0:
            return True
        live = bool(self.game_data and self.game_data.get('state') == 'in')
        interval = self.update_interval if (live or not self.enabled) else IDLE_REFRESH
        return now - self.last_update >= interval

    # ------------------------------------------------------------------- data

    def _fetch_game_data(self):
        """Fetch the configured team's current game from ESPN. None if no game."""
        path = LEAGUE_PATHS.get(self.league)
        if not path:
            self.fetch_failed = True
            return None
        try:
            response = requests.get(ESPN_SCOREBOARD.format(path=path), timeout=10)
            response.raise_for_status()
            events = response.json().get('events', [])
            self.fetch_failed = False
        except Exception as e:
            self.logger.error(f"Error fetching {self.league} scoreboard: {e}")
            self.fetch_failed = True
            return None

        for event in events:
            competition = (event.get('competitions') or [{}])[0]
            competitors = competition.get('competitors', [])
            abbrs = [c.get('team', {}).get('abbreviation', '').upper() for c in competitors]
            if self.team in abbrs and len(competitors) == 2:
                return self._parse_competition(competition, event)

        self.logger.info(f"No {self.league} game found for {self.team} on the current scoreboard")
        return None

    def _parse_competition(self, competition, event):
        """Turn an ESPN competition into the dict the renderer uses."""
        def team_info(c):
            team = c.get('team', {})
            records = c.get('records') or []
            return {
                'abbr': team.get('abbreviation', '???').upper(),
                'score': c.get('score', '0') or '0',
                'color': _hex_to_rgb(team.get('color')),
                'alt_color': _hex_to_rgb(team.get('alternateColor')),
                'record': records[0].get('summary') if records else None,
                'home': c.get('homeAway') == 'home',
            }

        teams = [team_info(c) for c in competition.get('competitors', [])]
        ours = next(t for t in teams if t['abbr'] == self.team)
        theirs = next(t for t in teams if t is not ours)
        status = competition.get('status') or event.get('status') or {}
        status_type = status.get('type', {})
        state = status_type.get('state', 'pre')  # pre / in / post

        return {
            'team': ours,
            'opponent': theirs,
            'state': state,
            'status_text': self._status_text(state, status, competition.get('date') or event.get('date')),
            'demo': False,
        }

    def _status_text(self, state, status, date_str):
        """Short status line that fits on 64px: 'Q3 7:42', 'FINAL', 'SUN 1PM'."""
        status_type = status.get('type', {})
        if state == 'post':
            detail = status_type.get('shortDetail', 'Final').upper()
            return 'FINAL' if detail.startswith('FINAL') and len(detail) > 9 else detail[:10]
        if state == 'in':
            period = status.get('period', 0)
            clock = status.get('displayClock', '')
            prefix = {'NFL': 'Q', 'NCAAF': 'Q', 'NBA': 'Q', 'WNBA': 'Q', 'NHL': 'P', 'MLB': 'INN'}.get(self.league, '')
            if self.league in ('MLB', 'MLS'):
                return status_type.get('shortDetail', '')[:10].upper()
            if status_type.get('name') == 'STATUS_HALFTIME':
                return 'HALF'
            return f"{prefix}{period} {clock}".strip()[:10]
        # Scheduled: show local day + time
        try:
            start = datetime.strptime(date_str, '%Y-%m-%dT%H:%MZ').replace(tzinfo=timezone.utc).astimezone()
            hour = start.strftime('%I').lstrip('0')
            minute = start.strftime('%M')
            ampm = start.strftime('%p')[0]
            when = f"{hour}{'' if minute == '00' else ':' + minute}{ampm}"
            return f"{start.strftime('%a').upper()} {when}"
        except (TypeError, ValueError):
            return 'SOON'

    def _demo_game_data(self):
        """Clearly-labelled sample data shown when sports is disabled."""
        team_score = random.randint(17, 31)
        opp_score = max(0, team_score + random.randint(-7, 7))
        return {
            'team': {'abbr': self.team, 'score': str(team_score), 'color': (0, 80, 160),
                     'alt_color': (255, 255, 255), 'record': '7-3', 'home': True},
            'opponent': {'abbr': 'ATL', 'score': str(opp_score), 'color': (160, 20, 40),
                         'alt_color': (255, 255, 255), 'record': '5-5', 'home': False},
            'state': 'in',
            'status_text': 'Q3 7:42',
            'demo': True,
        }

    # -------------------------------------------------------------- rendering

    def _display_game(self, game):
        """Alternate between the score and the team records every 5 seconds."""
        has_records = game['team'].get('record') or game['opponent'].get('record')
        if has_records and int(time.time() // 5) % 3 == 2:
            self._render_records(game)
        else:
            self._render_score(game)

    def _render_score(self, game):
        width, height = self.display.get_size()
        image = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        # Away team on top, home team below (scoreboard convention)
        away, home = (game['opponent'], game['team']) if game['team']['home'] else (game['team'], game['opponent'])
        show_scores = game['state'] != 'pre'

        for row, team in enumerate((away, home)):
            top = 4 + row * 22
            bar = _team_bar_color(team['color'])
            draw.rectangle([0, top, width - 1, top + 17], fill=bar)
            ink = (0, 0, 0) if _luminance(bar) > 150 else (255, 255, 255)
            draw.text((3, top + 3), team['abbr'][:4], font=font, fill=ink)
            if show_scores:
                score = str(team['score'])
                w = _text_width(draw, score, font)
                winning = _score_val(team) > _score_val(away if team is home else home)
                draw.text((width - w - 3, top + 3), score, font=font, fill=ink)
                if winning and game['state'] == 'post':
                    draw.rectangle([width - w - 3, top + 15, width - 4, top + 15], fill=ink)

        status = 'DEMO' if game.get('demo') else game['status_text']
        status_color = (255, 170, 60) if game.get('demo') else (
            (255, 80, 80) if game['state'] == 'in' else (170, 170, 170))
        w = _text_width(draw, status, font)
        draw.text(((width - w) // 2, height - 14), status, font=font, fill=status_color)

        self.display.display_image(image)

    def _render_records(self, game):
        width, height = self.display.get_size()
        image = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        title = 'RECORD'
        draw.text(((width - _text_width(draw, title, font)) // 2, 2), title, font=font, fill=(150, 150, 150))
        for row, team in enumerate((game['team'], game['opponent'])):
            y = 20 + row * 18
            draw.rectangle([2, y + 2, 5, y + 10], fill=_team_bar_color(team['color'], boost=True))
            draw.text((9, y), team['abbr'][:4], font=font, fill=(255, 255, 255))
            record = team.get('record') or '-'
            draw.text((width - _text_width(draw, record, font) - 2, y), record, font=font, fill=(200, 200, 200))

        self.display.display_image(image)

    def _display_message(self, text, color):
        image = self.image_processor.create_text_image(text, self.display.get_size(), color=color)
        self.display.display_image(image)


def _hex_to_rgb(value):
    try:
        value = (value or '').lstrip('#')
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (60, 60, 60)


def _team_bar_color(rgb, boost=False):
    """Team colour, nudged so very dark colours still show up on LEDs."""
    r, g, b = rgb
    if max(r, g, b) < 70:
        r, g, b = (min(255, c + 70) for c in (r, g, b))
    return (r, g, b) if boost else tuple(int(c * 0.8) for c in (r, g, b))


def _luminance(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _score_val(team):
    try:
        return int(team['score'])
    except (TypeError, ValueError):
        return 0
