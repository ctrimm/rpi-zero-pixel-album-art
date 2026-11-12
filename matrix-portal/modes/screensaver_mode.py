# screensaver_mode.py — Pipes + DVD Logo screensavers for Matrix Portal 64x64
# Both screensavers use a small palette bitmap for very low memory usage.
import displayio
import time
import random
import gc

from utils.display_helper import PALETTE_16, make_palette, set_palette_color

W = 64
H = 64
NUM_COLORS = len(PALETTE_16)  # 16

# 3x5 glyphs for the logo lettering (bit 2 = left column)
_GLYPH_D = (0b110, 0b101, 0b101, 0b101, 0b110)
_GLYPH_V = (0b101, 0b101, 0b101, 0b010, 0b010)

# Pipe directions
_UP, _DOWN, _LEFT, _RIGHT = 0, 1, 2, 3
_TURNS = {
    _UP:    [_UP,    _LEFT, _RIGHT],
    _DOWN:  [_DOWN,  _LEFT, _RIGHT],
    _LEFT:  [_LEFT,  _UP,   _DOWN],
    _RIGHT: [_RIGHT, _UP,   _DOWN],
}
_DX = {_UP: 0, _DOWN: 0, _LEFT: -1, _RIGHT: 1}
_DY = {_UP: -1, _DOWN: 1, _LEFT: 0, _RIGHT: 0}


class ScreensaverMode:
    """
    Alternates between Pipes and DVD Logo screensavers.
    Designed to be very memory-efficient: one shared 64x64 bitmap with a 16-color palette.
    """

    def __init__(self, display, screensaver_type="both"):
        self.display = display
        self.screensaver_type = screensaver_type  # "pipes", "dvd", "both"

        self._group = None
        self._bitmap = None
        self._palette = None
        self._tile_grid = None

        self._current = "pipes"
        self._switch_at = 0
        self._switch_interval = 30  # seconds per screensaver

        # Pipes state
        self._pipes = []
        self._num_pipes = 4
        self._last_pipe_tick = 0
        self._pipe_tick_interval = 0.05
        self._frame_count = 0
        self._clear_at_frame = 300

        # DVD state
        self._dvd_x = 20.0
        self._dvd_y = 20.0
        self._dvd_dx = 0.8
        self._dvd_dy = 0.6
        self._dvd_color = 0
        self._dvd_w = 16
        self._dvd_h = 8
        self._last_dvd_tick = 0
        self._dvd_tick_interval = 0.04
        self._dvd_grid = None
        self._dvd_palette = None

    def on_enter(self):
        gc.collect()
        # Index 0 must be black: the bitmap is cleared to 0. (PALETTE_16[0] is red,
        # which used to make the whole screensaver background solid red.)
        self._palette = make_palette([0x000000] + PALETTE_16[1:])
        self._bitmap = displayio.Bitmap(W, H, NUM_COLORS)
        self._tile_grid = displayio.TileGrid(self._bitmap, pixel_shader=self._palette)

        self._group = displayio.Group()
        self._group.append(self._tile_grid)

        # DVD logo: a small 16x8 bitmap that is *moved* each frame (TileGrid
        # x/y), instead of erasing and redrawing ~256 pixels from Python.
        # Index 0 = logo colour, 1 = black lettering.
        self._dvd_palette = make_palette([PALETTE_16[0], 0x000000])
        logo = displayio.Bitmap(self._dvd_w, self._dvd_h, 2)
        tx = (self._dvd_w - 11) // 2
        ty = (self._dvd_h - 5) // 2
        for i, glyph in enumerate((_GLYPH_D, _GLYPH_V, _GLYPH_D)):
            for row, bits in enumerate(glyph):
                for col in range(3):
                    if bits & (4 >> col):
                        logo[tx + i * 4 + col, ty + row] = 1
        self._dvd_grid = displayio.TileGrid(logo, pixel_shader=self._dvd_palette)
        self._dvd_grid.hidden = True
        self._group.append(self._dvd_grid)
        self.display.root_group = self._group

        # Pick first screensaver
        if self.screensaver_type == "dvd":
            self._start_dvd()
        else:
            self._start_pipes()

        self._switch_at = time.monotonic() + self._switch_interval

    def on_exit(self):
        self._dvd_grid = None
        self._dvd_palette = None
        self._group = None
        self._bitmap = None
        self._palette = None
        self._tile_grid = None
        self._pipes = []
        gc.collect()

    def update(self):
        now = time.monotonic()

        if self.screensaver_type == "both" and now >= self._switch_at:
            if self._current == "pipes":
                self._start_dvd()
            else:
                self._start_pipes()
            self._switch_at = now + self._switch_interval

        if self._current == "pipes":
            self._tick_pipes(now)
        else:
            self._tick_dvd(now)

    # ------------------------------------------------------------------
    # Pipes
    # ------------------------------------------------------------------

    def _start_pipes(self):
        self._current = "pipes"
        if self._dvd_grid is not None:
            self._dvd_grid.hidden = True
        self._clear_bitmap()
        self._pipes = []
        self._frame_count = 0
        for _ in range(self._num_pipes):
            self._pipes.append(self._new_pipe())

    def _new_pipe(self):
        return {
            "x":     random.randint(0, W - 1),
            "y":     random.randint(0, H - 1),
            "dir":   random.randint(0, 3),
            "color": random.randint(1, NUM_COLORS - 1),
            "len":   0,
        }

    def _tick_pipes(self, now):
        if now - self._last_pipe_tick < self._pipe_tick_interval:
            return
        self._last_pipe_tick = now

        self._frame_count += 1
        if self._frame_count >= self._clear_at_frame:
            self._frame_count = 0
            self._clear_bitmap()
            self._pipes = [self._new_pipe() for _ in range(self._num_pipes)]

        for pipe in self._pipes:
            x, y = pipe["x"], pipe["y"]
            if 0 <= x < W and 0 <= y < H:
                self._bitmap[x, y] = pipe["color"]

            # Occasionally turn
            turn_chance = 8  # 1-in-N chance to turn each step
            choices = _TURNS[pipe["dir"]]
            if random.randint(0, turn_chance) == 0:
                pipe["dir"] = choices[random.randint(1, len(choices) - 1)]
            else:
                pipe["dir"] = choices[0]

            pipe["x"] += _DX[pipe["dir"]]
            pipe["y"] += _DY[pipe["dir"]]
            pipe["len"] += 1

            # Wrap at edges
            pipe["x"] %= W
            pipe["y"] %= H

            # Occasionally restart pipe
            if pipe["len"] > random.randint(40, 120):
                pipe.update(self._new_pipe())

    # ------------------------------------------------------------------
    # DVD Logo
    # ------------------------------------------------------------------

    def _start_dvd(self):
        self._current = "dvd"
        self._clear_bitmap()
        self._dvd_x = float(W // 2)
        self._dvd_y = float(H // 2)
        self._dvd_dx = 0.8
        self._dvd_dy = 0.6
        self._dvd_color = random.randint(1, NUM_COLORS - 1)
        set_palette_color(self._dvd_palette, 0, PALETTE_16[self._dvd_color])
        self._dvd_grid.hidden = False
        self._place_dvd()

    def _tick_dvd(self, now):
        if now - self._last_dvd_tick < self._dvd_tick_interval:
            return
        self._last_dvd_tick = now

        self._dvd_x += self._dvd_dx
        self._dvd_y += self._dvd_dy

        hit_x = hit_y = False
        if self._dvd_x <= 0:
            self._dvd_x = 0
            self._dvd_dx = abs(self._dvd_dx)
            hit_x = True
        elif self._dvd_x + self._dvd_w >= W:
            self._dvd_x = W - self._dvd_w
            self._dvd_dx = -abs(self._dvd_dx)
            hit_x = True

        if self._dvd_y <= 0:
            self._dvd_y = 0
            self._dvd_dy = abs(self._dvd_dy)
            hit_y = True
        elif self._dvd_y + self._dvd_h >= H:
            self._dvd_y = H - self._dvd_h
            self._dvd_dy = -abs(self._dvd_dy)
            hit_y = True

        if hit_x or hit_y:
            # New colour on every bounce (skip index 0 = black-ish red repeat)
            self._dvd_color = self._dvd_color % (NUM_COLORS - 1) + 1
            set_palette_color(self._dvd_palette, 0, PALETTE_16[self._dvd_color])

        self._place_dvd()

    def _place_dvd(self):
        # Moving a TileGrid is O(1) - no pixel writes at all
        x, y = int(self._dvd_x), int(self._dvd_y)
        if self._dvd_grid.x != x:
            self._dvd_grid.x = x
        if self._dvd_grid.y != y:
            self._dvd_grid.y = y

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _clear_bitmap(self):
        bmp = self._bitmap
        if bmp is None:
            return
        # displayio.Bitmap.fill() is a C-level call (CircuitPython 7+),
        # far faster than the equivalent 4096-iteration Python loop.
        bmp.fill(0)
