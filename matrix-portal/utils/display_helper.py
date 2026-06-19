# display_helper.py — Display utilities for Matrix Portal 64x64
import displayio
import time

try:
    from adafruit_display_text import label
    import terminalio
    _HAS_TEXT = True
except ImportError:
    _HAS_TEXT = False


COLORS = {
    "white":  0xFFFFFF,
    "black":  0x000000,
    "red":    0xFF0000,
    "green":  0x00FF00,
    "blue":   0x0088FF,
    "yellow": 0xFFFF00,
    "cyan":   0x00FFFF,
    "magenta":0xFF00FF,
    "orange": 0xFF6600,
    "gray":   0x888888,
    "dim":    0x444444,
}

# 16-color palette for screensavers (index → RGB int)
PALETTE_16 = [
    0xFF0000, 0xFF6600, 0xFFFF00, 0x00FF00,
    0x00FFFF, 0x0088FF, 0x8800FF, 0xFF00FF,
    0xFF4444, 0xFFAA44, 0xAAFF44, 0x44FFAA,
    0x44AAFF, 0xAA44FF, 0xFF44AA, 0xFFFFFF,
]


def make_palette(color_list):
    p = displayio.Palette(len(color_list))
    for i, c in enumerate(color_list):
        p[i] = c
    return p


def make_bitmap(width, height, num_colors=2):
    return displayio.Bitmap(width, height, num_colors)


def fill_bitmap(bitmap, color_index, x0=0, y0=0, x1=None, y1=None):
    """Fill a rectangular region of a bitmap with a color index."""
    if x1 is None:
        x1 = bitmap.width
    if y1 is None:
        y1 = bitmap.height
    for y in range(y0, y1):
        for x in range(x0, x1):
            bitmap[x, y] = color_index


def make_text_label(text, color=0xFFFFFF, x=0, y=0, scale=1):
    if not _HAS_TEXT:
        return None
    lbl = label.Label(terminalio.FONT, text=text, color=color, scale=scale)
    lbl.x = x
    lbl.y = y
    return lbl


def center_label(lbl, display_width=64, y=None):
    """Horizontally center a label.

    bounding_box is in unscaled glyph pixels, so multiply by the label's
    scale to get the real on-screen width - otherwise scale>1 labels (the
    clock time, weather temp, sports score, splash) end up pushed to the
    right and clipped off the edge.
    """
    if lbl is None:
        return
    width = lbl.bounding_box[2] * getattr(lbl, "scale", 1)
    lbl.x = max(0, (display_width - width) // 2)
    if y is not None:
        lbl.y = y


class ScrollingLabel:
    """Scrolls a text label horizontally across the display."""

    def __init__(self, text, color=0xFFFFFF, y=0, scale=1,
                 display_width=64, speed=1):
        self.display_width = display_width
        self.speed = speed
        self._pos = display_width  # start off-screen right
        self._paused_at = None
        self._pause_duration = 1.5  # seconds to pause at start

        self.label = make_text_label(text, color=color, x=display_width, y=y, scale=scale)
        self._text_width = self._calc_width(text, scale)

    def _calc_width(self, text, scale):
        # terminalio.FONT is 6px wide per char
        return len(text) * 6 * scale

    def set_text(self, text):
        if self.label:
            self.label.text = text
            self._text_width = self._calc_width(text, self.label.scale)
            self._pos = self.display_width
            self._paused_at = None

    def update(self):
        """Call each frame. Updates label.x."""
        if self.label is None:
            return

        # If text fits on screen, just center it and don't scroll
        if self._text_width <= self.display_width:
            self.label.x = max(0, (self.display_width - self._text_width) // 2)
            return

        now = time.monotonic()

        if self._paused_at is not None:
            if now - self._paused_at < self._pause_duration:
                return
            self._paused_at = None

        self._pos -= self.speed
        if self._pos < -self._text_width:
            self._pos = self.display_width
            self._paused_at = now

        self.label.x = int(self._pos)


def load_bmp(filepath):
    """Load a BMP file and return (tile_grid, group_entry). Returns None on error."""
    try:
        import adafruit_imageload
        bitmap, palette = adafruit_imageload.load(
            filepath,
            bitmap=displayio.Bitmap,
            palette=displayio.Palette,
        )
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        return tile_grid
    except Exception as e:
        print(f"BMP load failed ({filepath}): {e}")
        return None
