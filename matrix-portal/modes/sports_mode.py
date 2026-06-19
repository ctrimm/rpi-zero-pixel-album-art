# sports_mode.py — Live sports scores via ESPN API for Matrix Portal 64x64
import displayio
import time
import gc

from utils.display_helper import make_text_label, center_label, COLORS, ScrollingLabel
from utils import storage_helper

SPORTS_CACHE = "/cache_sports.json"

# ESPN API — no auth required
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"

SPORT_MAP = {
    "NFL": ("football", "nfl"),
    "NBA": ("basketball", "nba"),
    "MLB": ("baseball", "mlb"),
    "NHL": ("hockey", "nhl"),
}

LEAGUE_COLORS = {
    "NFL": 0x013369,
    "NBA": 0xC9082A,
    "MLB": 0x002D72,
    "NHL": 0x000000,
}


def _sport_for_league(league):
    return SPORT_MAP.get(league.upper(), ("basketball", "nba"))


class SportsMode:
    def __init__(self, display, network, companion_url="",
                 league="NBA", team="LAL"):
        self.display = display
        self.network = network
        self.companion_url = companion_url.rstrip("/")
        self.league = league.upper()
        self.team = team.upper()

        self._group = None
        self._league_label = None
        self._team_label = None
        self._score_label = None
        self._status_label = None
        self._detail_label = None
        self._matchup_scroller = None

        self._last_update = 0
        self._update_interval = 60

    def on_enter(self):
        gc.collect()
        self._group = displayio.Group()
        league_color = LEAGUE_COLORS.get(self.league, COLORS["white"])

        # League header
        self._league_label = make_text_label(
            self.league, color=league_color, y=5, scale=1
        )
        center_label(self._league_label, y=5)
        self._group.append(self._league_label)

        # Team name / matchup scroller
        self._matchup_scroller = ScrollingLabel(
            self.team, color=COLORS["white"], y=16, scale=1
        )
        self._group.append(self._matchup_scroller.label)

        # Score — big
        self._score_label = make_text_label("  VS  ", color=COLORS["yellow"], y=32, scale=2)
        center_label(self._score_label, y=32)
        self._group.append(self._score_label)

        # Game status (Q3, Final, etc.)
        self._status_label = make_text_label("Loading...", color=COLORS["gray"], y=48)
        center_label(self._status_label, y=48)
        self._group.append(self._status_label)

        # Record / detail line
        self._detail_label = make_text_label("", color=COLORS["dim"], y=58)
        center_label(self._detail_label, y=58)
        self._group.append(self._detail_label)

        self.display.root_group = self._group
        self._last_update = 0

        # Show last-good game immediately (before the first network fetch)
        cached = storage_helper.load_json(SPORTS_CACHE)
        if cached:
            try:
                self._render_game(cached)
            except Exception as e:
                print(f"Sports cache render failed: {e}")

    def on_exit(self):
        self._group = None
        self._league_label = None
        self._score_label = None
        self._status_label = None
        self._detail_label = None
        self._matchup_scroller = None
        gc.collect()

    def update(self):
        now = time.monotonic()
        if now - self._last_update >= self._update_interval:
            self._last_update = now
            self._fetch_and_render()

        if self._matchup_scroller:
            self._matchup_scroller.update()

    def _fetch_and_render(self):
        if self.companion_url:
            data = self.network.get_json(f"{self.companion_url}/api/matrix/sports")
            if data and not data.get("error"):
                self._render_game(data)
                storage_helper.save_json(SPORTS_CACHE, data)
                return

        sport, league_path = _sport_for_league(self.league)
        url = ESPN_URL.format(sport=sport, league=league_path)
        data = self.network.get_json(url)
        gc.collect()

        if not data:
            self._set_status("No data")
            return

        game = self._find_team_game(data)
        if game:
            self._render_game(game)
            storage_helper.save_json(SPORTS_CACHE, game)
        else:
            self._set_status("No game today")

    def _find_team_game(self, data):
        events = data.get("events", [])
        for event in events:
            comps = event.get("competitions", [])
            for comp in comps:
                competitors = comp.get("competitors", [])
                for c in competitors:
                    abbrev = c.get("team", {}).get("abbreviation", "").upper()
                    if abbrev == self.team:
                        return self._parse_competition(comp, event)
        return None

    def _parse_competition(self, comp, event):
        competitors = comp.get("competitors", [])
        status = event.get("status", {})
        status_type = status.get("type", {})

        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})

        return {
            "home_team":  home.get("team", {}).get("abbreviation", "???"),
            "away_team":  away.get("team", {}).get("abbreviation", "???"),
            "home_score": home.get("score", "-"),
            "away_score": away.get("score", "-"),
            "status":     status_type.get("shortDetail", status_type.get("name", "???")),
            "completed":  status_type.get("completed", False),
        }

    def _render_game(self, game):
        home  = game.get("home_team", "???")
        away  = game.get("away_team", "???")
        hs    = game.get("home_score", "-")
        as_   = game.get("away_score", "-")
        state = game.get("status", "")
        done  = game.get("completed", False)

        matchup = f"{away} @ {home}"
        self._matchup_scroller.set_text(matchup)

        score_str = f"{as_}-{hs}"
        self._score_label.text = score_str
        self._score_label.color = COLORS["green"] if done else COLORS["yellow"]
        center_label(self._score_label, y=32)

        self._status_label.text = state[:12]
        center_label(self._status_label, y=48)

        record = game.get("record", "")
        self._detail_label.text = record[:12] if record else ""
        center_label(self._detail_label, y=58)

    def _set_status(self, text):
        if self._status_label:
            self._status_label.text = text
            center_label(self._status_label, y=48)
        if self._score_label:
            self._score_label.text = "  --  "
            center_label(self._score_label, y=32)
