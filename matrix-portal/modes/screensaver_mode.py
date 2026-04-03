# screensaver_mode.py — Pipes + DVD Logo screensavers for Matrix Portal 64x64
# Both screensavers use a small palette bitmap for very low memory usage.
import displayio
import time
import random
import gc

from utils.display_helper import PALETTE_16, make_palette

W = 64
H = 64
NUM_COLORS = len(PALETTE_16)  # 16

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

    def on_enter(self):
        gc.collect()
        self._palette = make_palette(PALETTE_16)
        self._bitmap = displayio.Bitmap(W, H, NUM_COLORS)
        self._tile_grid = displayio.TileGrid(self._bitmap, pixel_shader=self._palette)

        self._group = displayio.Group()
        self._group.append(self._tile_grid)
        self.display.root_group = self._group

        # Pick first screensaver
        if self.screensaver_type == "dvd":
            self._start_dvd()
        else:
            self._start_pipes()

        self._switch_at = time.monotonic() + self._switch_interval

    def on_exit(self):
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
            "color": random.randint(0, NUM_COLORS - 1),
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
        self._dvd_color = random.randint(0, NUM_COLORS - 1)

    def _tick_dvd(self, now):
        if now - self._last_dvd_tick < self._dvd_tick_interval:
            return
        self._last_dvd_tick = now

        # Erase previous position
        self._draw_dvd_rect(int(self._dvd_x), int(self._dvd_y), 0)

        self._dvd_x += self._dvd_dx
        self._dvd_y += self._dvd_dy

        bounced = False
        if self._dvd_x <= 0:
            self._dvd_x = 0
            self._dvd_dx = abs(self._dvd_dx)
            bounced = True
        elif self._dvd_x + self._dvd_w >= W:
            self._dvd_x = W - self._dvd_w
            self._dvd_dx = -abs(self._dvd_dx)
            bounced = True

        if self._dvd_y <= 0:
            self._dvd_y = 0
            self._dvd_dy = abs(self._dvd_dy)
            bounced = True
        elif self._dvd_y + self._dvd_h >= H:
            self._dvd_y = H - self._dvd_h
            self._dvd_dy = -abs(self._dvd_dy)
            bounced = True

        if bounced:
            # Change color on bounce, rainbow-cycle through palette
            self._dvd_color = (self._dvd_color + 1) % NUM_COLORS

        self._draw_dvd_rect(int(self._dvd_x), int(self._dvd_y), self._dvd_color)

    def _draw_dvd_rect(self, x, y, color_index):
        """Draw or erase the DVD rectangle (filled)."""
        bmp = self._bitmap
        x_end = min(x + self._dvd_w, W)
        y_end = min(y + self._dvd_h, H)
        for py in range(max(0, y), y_end):
            for px in range(max(0, x), x_end):
                bmp[px, py] = color_index

        # Draw "DVD" text pixels (crude 3x5 chars) inside if erasing
        if color_index != 0:
            self._draw_dvd_text(x + 1, y + 2, color_index)

    def _draw_dvd_text(self, x, y, bg_color):
        """Draw 'DVD' in 1-pixel dots as a simple logo mark (inverted)."""
        # Simple 3-char monogram using pixel dots — just a visual marker
        dots = [
            # D
            (0,0),(0,1),(0,2),(0,3),(0,4),
            (1,0),(1,4),(2,1),(2,2),(2,3),
            # V
            (4,0),(4,1),(5,2),(5,3),(6,4),(7,3),(7,2),(8,1),(8,0),
            # D
            (10,0),(10,1),(10,2),(10,3),(10,4),
            (11,0),(11,4),(12,1),(12,2),(12,3),
        ]
        # Use black (index 0) for text pixels (contrast against colored bg)
        text_color = 0
        bmp = self._bitmap
        for dx, dy in dots:
            px, py = x + dx, y + dy
            if 0 <= px < W and 0 <= py < H:
                if bg_color == 0:
                    pass  # erasing — don't draw text
                else:
                    bmp[px, py] = text_color

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _clear_bitmap(self):
        bmp = self._bitmap
        if bmp is None:
            return
        for y in range(H):
            for x in range(W):
                bmp[x, y] = 0
