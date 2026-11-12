# display_helper.py — Display utilities for Matrix Portal 64x64 (M4 and S3)
#
# Brightness: CircuitPython's rgbmatrix can't dim the panel - its `brightness`
# is effectively on/off ("0.0 turns the display off entirely and any other
# value up to 1.0 turns the display on fully"). So dimming is done in software:
# every palette and label colour created through these helpers is remembered
# at full brightness and rescaled when the brightness changes.
import displayio
import time

try:
    from adafruit_display_text import label
    import terminalio
    _HAS_TEXT = True
except ImportError:
    _HAS_TEXT = False

try:
    import bitmaptools  # C-accelerated drawing (S3; not in the M4 build)
except ImportError:
    bitmaptools = None


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


# ── Software dimming ──────────────────────────────────────────────────────────

class _Dimmer:
    def __init__(self):
        self.level = 100          # percent
        self._palettes = []       # [palette, [base colors]]
        self._labels = []         # [label, base color]
        self._rgb565 = []         # [src bitmap, dest bitmap, colorspace, black bitmap]

    def scale(self, color):
        if self.level >= 100:
            return color
        f = self.level
        r = ((color >> 16) & 0xFF) * f // 100
        g = ((color >> 8) & 0xFF) * f // 100
        b = (color & 0xFF) * f // 100
        return (r << 16) | (g << 8) | b

    def reset(self):
        """Forget everything registered (call on mode switch so the previous
        mode's palettes/labels can be garbage-collected)."""
        self._palettes = []
        self._labels = []
        self._rgb565 = []

    def add_palette(self, palette, base_colors):
        self._palettes.append([palette, list(base_colors)])
        for i, c in enumerate(base_colors):
            palette[i] = self.scale(c)

    def forget_palette(self, palette):
        self._palettes = [p for p in self._palettes if p[0] is not palette]

    def add_label(self, lbl, color):
        if lbl is None:
            return
        for entry in self._labels:
            if entry[0] is lbl:
                entry[1] = color
                break
        else:
            self._labels.append([lbl, color])
        lbl.color = self.scale(color)

    def add_rgb565(self, src, dest, colorspace):
        """Register an RGB565 bitmap (e.g. a decoded JPEG) for dimming.
        `src` keeps the full-brightness pixels; `dest` is what's displayed."""
        black = displayio.Bitmap(src.width, src.height, 65535)
        entry = [src, dest, colorspace, black]
        self._rgb565.append(entry)
        self._apply_rgb565(entry)

    def forget_bitmap(self, dest):
        self._rgb565 = [e for e in self._rgb565 if e[1] is not dest]

    def _apply_rgb565(self, entry):
        src, dest, colorspace, black = entry
        if bitmaptools is None:
            return
        # C-level: dest = src * level (+ black * 0)
        bitmaptools.alphablend(dest, src, black, colorspace, self.level / 100, 0.0)

    def set_level(self, pct):
        pct = max(1, min(100, int(pct)))
        if pct == self.level:
            return
        self.level = pct
        for palette, base in self._palettes:
            for i, c in enumerate(base):
                palette[i] = self.scale(c)
        for lbl, color in self._labels:
            lbl.color = self.scale(color)
        for entry in self._rgb565:
            self._apply_rgb565(entry)


dimmer = _Dimmer()


def set_label_color(lbl, color):
    """Change a label's colour (use this instead of `lbl.color = ...` so the
    current brightness is applied)."""
    dimmer.add_label(lbl, color)


def make_palette(color_list):
    p = displayio.Palette(len(color_list))
    dimmer.add_palette(p, color_list)
    return p


def set_palette_color(palette, index, color):
    """Change one palette entry, respecting the current brightness."""
    for entry in dimmer._palettes:
        if entry[0] is palette:
            entry[1][index] = color
            break
    palette[index] = dimmer.scale(color)


def register_palette(palette):
    """Register a palette created elsewhere (e.g. by adafruit_imageload)."""
    dimmer.add_palette(palette, [palette[i] for i in range(len(palette))])
    return palette


def make_bitmap(width, height, num_colors=2):
    return displayio.Bitmap(width, height, num_colors)


def fill_bitmap(bitmap, color_index, x0=0, y0=0, x1=None, y1=None):
    """Fill a rectangular region of a bitmap with a color index."""
    if x1 is None:
        x1 = bitmap.width
    if y1 is None:
        y1 = bitmap.height
    if x0 <= 0 and y0 <= 0 and x1 >= bitmap.width and y1 >= bitmap.height:
        bitmap.fill(color_index)
        return
    if bitmaptools is not None:
        bitmaptools.fill_region(bitmap, x0, y0, x1, y1, color_index)
        return
    for y in range(y0, y1):
        for x in range(x0, x1):
            bitmap[x, y] = color_index


def make_text_label(text, color=0xFFFFFF, x=0, y=0, scale=1):
    if not _HAS_TEXT:
        return None
    lbl = label.Label(terminalio.FONT, text=text, color=dimmer.scale(color), scale=scale)
    lbl.x = x
    lbl.y = y
    dimmer.add_label(lbl, color)
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
    """Shows a text label; if it's wider than the panel, pans it back and forth.

    Text that fits is centred. Longer text starts left-aligned, pauses, slides
    left just far enough to reveal the end, pauses, and jumps back - so it's
    always readable (a classic marquee that scrolls fully off-screen leaves
    the line blank for a third of the time).
    """

    def __init__(self, text, color=0xFFFFFF, y=0, scale=1,
                 display_width=64, speed=1, frame_interval=0.04):
        self.display_width = display_width
        self.speed = speed
        self._pause_duration = 1.5  # seconds to hold at each end
        # Step at a fixed rate (25 px/s) rather than once per main-loop pass,
        # so the speed doesn't depend on how fast the loop happens to spin.
        self._frame_interval = frame_interval
        self._next_step = 0
        self._pos = 0
        self._hold_until = 0

        self.label = make_text_label(text, color=color, x=0, y=y, scale=scale)
        self._text = text
        self._text_width = self._calc_width(text, scale)
        self._place_initial()

    def _calc_width(self, text, scale):
        # terminalio.FONT is 6px wide per char
        return len(text) * 6 * scale

    def _place_initial(self):
        if self.label is None:
            return
        if self.scrolling:
            self._pos = 1
            self._hold_until = time.monotonic() + self._pause_duration
        else:
            self._pos = max(0, (self.display_width - self._text_width) // 2)
        self.label.x = self._pos

    def set_text(self, text):
        if not self.label or text == self._text:
            return  # unchanged: don't restart the scroll on every poll
        self._text = text
        self.label.text = text
        self._text_width = self._calc_width(text, self.label.scale)
        self._place_initial()

    @property
    def scrolling(self):
        return self._text_width > self.display_width - 2

    def update(self):
        """Call each frame. Updates label.x."""
        if self.label is None or not self.scrolling:
            return
        now = time.monotonic()
        if now < self._hold_until or now < self._next_step:
            return
        self._next_step = now + self._frame_interval
        end = self.display_width - self._text_width - 1   # right edge just visible
        if self._pos <= end:
            # Reached the end: hold, then jump back to the start and hold again
            self._pos = 1
            self._hold_until = now + self._pause_duration
        else:
            self._pos = max(end, self._pos - self.speed)
            if self._pos == end:
                self._hold_until = now + self._pause_duration
        self.label.x = int(self._pos)


def load_bmp(source):
    """Load a paletted BMP (filename, file object or bytes) into a TileGrid
    whose palette follows the brightness setting. Returns None on error."""
    try:
        import adafruit_imageload
        if isinstance(source, (bytes, bytearray)):
            import io
            source = io.BytesIO(source)
        bitmap, palette = adafruit_imageload.load(
            source,
            bitmap=displayio.Bitmap,
            palette=displayio.Palette,
        )
        register_palette(palette)
        return displayio.TileGrid(bitmap, pixel_shader=palette)
    except Exception as e:
        print(f"BMP load failed: {e}")
        return None


_jpeg_decoder = None


def decode_jpeg(data):
    """Decode JPEG bytes into a dimmable 64x64 TileGrid using the built-in
    jpegio module (ESP32-S3 builds). Returns None if unsupported or on error."""
    global _jpeg_decoder
    try:
        import jpegio
    except ImportError:
        return None
    try:
        if _jpeg_decoder is None:
            # One decoder for the whole session avoids heap fragmentation
            _jpeg_decoder = jpegio.JpegDecoder()
        w, h = _jpeg_decoder.open(data)
        # jpegio can scale by 1/2^n while decoding: pick the smallest >= 64px
        scale = 0
        while scale < 3 and (w >> (scale + 1)) >= 64 and (h >> (scale + 1)) >= 64:
            scale += 1
        sw, sh = w >> scale, h >> scale
        full = displayio.Bitmap(sw, sh, 65535)
        _jpeg_decoder.decode(full, scale=scale)
        if (sw, sh) == (64, 64):
            src = full
        else:
            # Centre-crop to 64x64
            src = displayio.Bitmap(64, 64, 65535)
            ox, oy = max(0, (sw - 64) // 2), max(0, (sh - 64) // 2)
            if bitmaptools is not None:
                bitmaptools.blit(src, full, 0, 0, x1=ox, y1=oy,
                                 x2=min(sw, ox + 64), y2=min(sh, oy + 64))
            else:
                for y in range(min(64, sh)):
                    for x in range(min(64, sw)):
                        src[x, y] = full[ox + x, oy + y]
        full = None
        colorspace = displayio.Colorspace.RGB565_SWAPPED
        if bitmaptools is None:
            dest = src  # can't dim without bitmaptools; show at full brightness
        else:
            dest = displayio.Bitmap(64, 64, 65535)
            dimmer.add_rgb565(src, dest, colorspace)
        return displayio.TileGrid(dest, pixel_shader=displayio.ColorConverter(input_colorspace=colorspace))
    except Exception as e:
        print(f"JPEG decode failed: {e}")
        return None
