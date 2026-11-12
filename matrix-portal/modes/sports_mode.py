# sports_mode.py — Live scores for Matrix Portal 64x64 (same layout as the Pi app)
#
# Data sources:
#   - Companion: /api/matrix/sports returns the exact game dict the Pi app uses.
#   - Standalone: ESPN's per-team endpoint (~20 KB). The league scoreboards the
#     old code fetched are 180-250 KB of JSON - more than the M4's whole RAM.
#
# Screens: score (team-coloured bars + game status), and every third 5s slot a
# records screen.
import displayio
import time
import gc

from utils.display_helper import (
    make_text_label, center_label, make_palette, set_palette_color,
    set_label_color, make_bitmap, COLORS,
)
from utils import storage_helper

SPORTS_CACHE = "/cache_sports.json"

ESPN_TEAM_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/teams/{team}"

LEAGUE_PATHS = {
    "NFL": "football/nfl",
    "NBA": "basketball/nba",
    "WNBA": "basketball/wnba",
    "MLB": "baseball/mlb",
    "NHL": "hockey/nhl",
    "MLS": "soccer/usa.1",
    "NCAAF": "football/college-football",
    "NCAAM": "basketball/mens-college-basketball",
}
PERIOD_PREFIX = {"NFL": "Q", "NCAAF": "Q", "NBA": "Q", "WNBA": "Q", "NCAAM": "H", "NHL": "P"}
DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

LIVE_REFRESH = 60     # seconds between updates during a game
IDLE_REFRESH = 600    # otherwise


def _hex(value, default=0x3C3C3C):
    try:
        return int((value or "").lstrip("#"), 16)
    except ValueError:
        return default


def _rgb_int(c):
    """Accept 0xRRGGBB, [r, g, b] (companion JSON) or a hex string."""
    if isinstance(c, int):
        return c
    if isinstance(c, (list, tuple)) and len(c) == 3:
        return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])
    return _hex(c)


def _bar_color(c, boost=False):
    """Team colour, nudged so very dark colours still show on LEDs."""
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    if max(r, g, b) < 70:
        r, g, b = min(255, r + 70), min(255, g + 70), min(255, b + 70)
    if not boost:
        r, g, b = r * 4 // 5, g * 4 // 5, b * 4 // 5
    return (r << 16) | (g << 8) | b


def _ink_for(c):
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    return 0x000000 if (299 * r + 587 * g + 114 * b) // 1000 > 150 else 0xFFFFFF


class SportsMode:
    def __init__(self, display, network, companion_url="", league="NBA",
                 team="LAL", tz_offset=0):
        self.display = display
        self.network = network
        self.companion_url = companion_url.rstrip("/")
        self.league = league.upper()
        self.team = team.upper()
        self.tz_offset = tz_offset

        self._group = None
        self._score_group = None
        self._record_group = None
        self._bars = []      # [(palette, abbr label, score label)] top, bottom
        self._status = None
        self._rec_rows = []  # [(palette, abbr label, record label)]
        self._message = None

        self.game = None
        self._next_update = 0
        self._screen = None

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def on_enter(self):
        gc.collect()
        self._group = displayio.Group()

        # Score screen: two coloured bars (away on top, home below)
        self._score_group = displayio.Group()
        self._bars = []
        for row in range(2):
            top = 4 + row * 22
            pal = make_palette([0x333333])
            self._score_group.append(displayio.TileGrid(make_bitmap(64, 18, 1), pixel_shader=pal, y=top))
            abbr = make_text_label("", color=COLORS["white"], x=3, y=top + 9)
            score = make_text_label("", color=COLORS["white"], y=top + 9)
            self._score_group.append(abbr)
            self._score_group.append(score)
            self._bars.append((pal, abbr, score))
        self._status = make_text_label("", color=COLORS["gray"], y=56)
        self._score_group.append(self._status)
        self._group.append(self._score_group)

        # Records screen
        self._record_group = displayio.Group()
        self._record_group.hidden = True
        title = make_text_label("RECORD", color=0x969696, y=7)
        center_label(title, y=7)
        self._record_group.append(title)
        self._rec_rows = []
        for row in range(2):
            y = 26 + row * 18
            pal = make_palette([0x333333])
            self._record_group.append(displayio.TileGrid(make_bitmap(4, 9, 1), pixel_shader=pal, x=2, y=y - 4))
            abbr = make_text_label("", color=COLORS["white"], x=9, y=y)
            rec = make_text_label("", color=0xC8C8C8, y=y)
            self._record_group.append(abbr)
            self._record_group.append(rec)
            self._rec_rows.append((pal, abbr, rec))
        self._group.append(self._record_group)

        # Message (no game / offline)
        self._message = make_text_label("", color=0x8C8C8C, y=32)
        self._group.append(self._message)

        self.display.root_group = self._group
        self._next_update = 0
        self._screen = None

        cached = storage_helper.load_json(SPORTS_CACHE)
        if cached and cached.get("team"):
            self.game = cached
            self._render()
        else:
            self._show_message("Loading")

    def on_exit(self):
        self._group = self._score_group = self._record_group = None
        self._bars = []
        self._rec_rows = []
        self._status = self._message = None
        gc.collect()

    def update(self):
        now = time.monotonic()
        if now >= self._next_update:
            self._fetch()
            live = bool(self.game and self.game.get("state") == "in")
            self._next_update = now + (LIVE_REFRESH if live else IDLE_REFRESH)
            self._screen = None
            self._render()
        elif self.game and self._current_screen(now) != self._screen:
            # Alternate score / records every 5 seconds (records every 3rd slot)
            self._render()

    # ── Data ────────────────────────────────────────────────────────────────

    def _fetch(self):
        if self.companion_url:
            status, data = self.network.request("GET", f"{self.companion_url}/api/matrix/sports")
            if status == 200 and data is not None and not data.get("error"):
                self.game = data.get("game")
                self._save()
                return
        path = LEAGUE_PATHS.get(self.league)
        if not path:
            self._show_message("Bad league")
            return
        gc.collect()
        status = data = None
        try:
            status, data = self.network.request(
                "GET", ESPN_TEAM_URL.format(path=path, team=self.team.lower()), retries=1)
        except MemoryError:
            print("Sports: not enough RAM for the ESPN reply - use the companion")
        if status == 200 and data:
            try:
                self.game = self._parse_team(data.get("team", {}))
            except (KeyError, ValueError, TypeError, IndexError) as e:
                print(f"Sports parse error: {e}")
            self._save()
        data = None
        gc.collect()

    def _save(self):
        if self.game:
            storage_helper.save_json(SPORTS_CACHE, self.game)

    def _parse_team(self, team):
        events = team.get("nextEvent") or []
        if not events:
            return None
        event = events[0]
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            return None
        own_color = _hex(team.get("color"))
        own_record = None
        try:
            own_record = team["record"]["items"][0]["summary"]
        except (KeyError, IndexError, TypeError):
            pass

        def info(c):
            t = c.get("team", {})
            abbr = t.get("abbreviation", "???").upper()
            score = c.get("score")
            if isinstance(score, dict):
                score = score.get("displayValue", score.get("value", 0))
            rec = c.get("record")
            if isinstance(rec, list) and rec:
                rec = rec[0].get("displayValue") or rec[0].get("summary")
            if abbr == self.team:
                color, rec = own_color, own_record or rec
            else:
                color = _hex(t.get("color"))
            return {"abbr": abbr, "score": str(score if score is not None else 0),
                    "color": color, "record": rec if isinstance(rec, str) else None,
                    "home": c.get("homeAway") == "home"}

        teams = [info(c) for c in competitors]
        ours = teams[0] if teams[0]["abbr"] == self.team else teams[1]
        theirs = teams[1] if ours is teams[0] else teams[0]
        status = comp.get("status") or event.get("status") or {}
        state = status.get("type", {}).get("state", "pre")
        return {"team": ours, "opponent": theirs, "state": state,
                "status_text": self._status_text(state, status, event.get("date", "")),
                "demo": False}

    def _status_text(self, state, status, date_str):
        stype = status.get("type", {})
        if state == "post":
            detail = stype.get("shortDetail", "Final").upper()
            return "FINAL" if detail.startswith("FINAL") and len(detail) > 9 else detail[:10]
        if state == "in":
            if stype.get("name") == "STATUS_HALFTIME":
                return "HALF"
            if self.league in ("MLB", "MLS"):
                return stype.get("shortDetail", "")[:10].upper()
            prefix = PERIOD_PREFIX.get(self.league, "")
            return f"{prefix}{status.get('period', 0)} {status.get('displayClock', '')}".strip()[:10]
        # Scheduled: "SAT 7:30P" in local time
        try:
            d, t = date_str.rstrip("Z").split("T")
            y, mo, da = (int(v) for v in d.split("-"))
            hh, mm = (int(v) for v in t.split(":")[:2])
            epoch = time.mktime((y, mo, da, hh, mm, 0, 0, -1, -1)) + self.tz_offset * 3600
            lt = time.localtime(epoch)
            hour = lt.tm_hour % 12 or 12
            mins = "" if lt.tm_min == 0 else f":{lt.tm_min:02d}"
            return f"{DAYS[lt.tm_wday]} {hour}{mins}{'P' if lt.tm_hour >= 12 else 'A'}"
        except (ValueError, IndexError, OverflowError):
            return "SOON"

    # ── Rendering ───────────────────────────────────────────────────────────

    def _has_records(self):
        g = self.game or {}
        return bool((g.get("team") or {}).get("record") or (g.get("opponent") or {}).get("record"))

    def _current_screen(self, now):
        return "records" if int(now // 5) % 3 == 2 and self._has_records() else "score"

    def _show_message(self, text):
        self._score_group.hidden = True
        self._record_group.hidden = True
        self._message.text = text
        center_label(self._message, y=32)

    def _render(self):
        if self._group is None:
            return
        g = self.game
        if not g:
            self._show_message("No game")
            self._screen = "message"
            return
        self._message.text = ""
        screen = self._current_screen(time.monotonic())
        self._screen = screen
        self._score_group.hidden = screen != "score"
        self._record_group.hidden = screen != "records"
        if screen == "score":
            self._render_score(g)
        else:
            self._render_records(g)

    def _render_score(self, g):
        team, opp = g["team"], g["opponent"]
        away, home = (opp, team) if team.get("home") else (team, opp)
        show_scores = g.get("state") != "pre"
        for (pal, abbr, score), t in zip(self._bars, (away, home)):
            bar = _bar_color(_rgb_int(t.get("color")))
            set_palette_color(pal, 0, bar)
            ink = _ink_for(bar)
            abbr.text = t.get("abbr", "")[:4]
            set_label_color(abbr, ink)
            score.text = str(t.get("score", "")) if show_scores else ""
            score.x = 61 - score.bounding_box[2]
            set_label_color(score, ink)
        demo = g.get("demo")
        self._status.text = "DEMO" if demo else g.get("status_text", "")
        set_label_color(self._status, 0xFFAA3C if demo else
                        (0xFF5050 if g.get("state") == "in" else 0xAAAAAA))
        center_label(self._status, y=56)

    def _render_records(self, g):
        for (pal, abbr, rec), t in zip(self._rec_rows, (g["team"], g["opponent"])):
            set_palette_color(pal, 0, _bar_color(_rgb_int(t.get("color")), boost=True))
            abbr.text = t.get("abbr", "")[:4]
            rec.text = t.get("record") or "-"
            rec.x = 62 - rec.bounding_box[2]
