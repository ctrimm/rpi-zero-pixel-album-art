"""
Animated pixel-art weather icons for Weather on the 8s.

Every icon is drawn on a 12x12 pixel grid, 8 frames long (played at 10 fps),
and shown either at 1x (next hours / 3-day screens) or pixel-doubled to 24x24
(current conditions). Transparent background.

This module is the single source of truth: the Pi app draws from it directly,
and the Matrix Portal ships sprite sheets exported from it:

    python src/utils/weather_icons.py matrix-portal/icons
"""

import math
import os
import sys

from PIL import Image

SIZE = 12
FRAMES = 8
FPS = 10

KINDS = ("sun", "moon", "partly_day", "partly_night", "cloud", "rain",
         "storm", "snow", "fog", "wind")

# Colours
SUN = (255, 214, 0)
SUN_GLOW = (255, 150, 0)
MOON = (240, 232, 175)
STAR = (255, 255, 210)
CLOUD = (235, 240, 255)
CLOUD_SHADE = (165, 175, 205)
DARK_CLOUD = (120, 125, 150)
DARK_SHADE = (85, 88, 110)
RAIN = (80, 160, 255)
RAIN_LIGHT = (150, 200, 255)
SNOW = (255, 255, 255)
BOLT = (255, 240, 90)
FOG = (160, 170, 200)
FOG_LIGHT = (200, 208, 228)
WIND = (200, 228, 255)
WIND_DIM = (120, 160, 210)

# Every colour an icon can use (index 0 = transparent in exported sheets)
PALETTE = [(0, 0, 0), SUN, SUN_GLOW, MOON, STAR, CLOUD, CLOUD_SHADE, DARK_CLOUD,
           DARK_SHADE, RAIN, RAIN_LIGHT, SNOW, BOLT, FOG, FOG_LIGHT, WIND, WIND_DIM]


# ── drawing primitives on a {(x, y): colour} dict ───────────────────────────

def _disc(px, cx, cy, r, color):
    for y in range(SIZE):
        for x in range(SIZE):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                px[(x, y)] = color


def _put(px, x, y, color):
    if 0 <= x < SIZE and 0 <= y < SIZE:
        px[(x, y)] = color


def _cloud(px, dx=0, dy=0, dark=False, small=False):
    """Puffy cloud with a flat, shaded bottom."""
    body, shade = (DARK_CLOUD, DARK_SHADE) if dark else (CLOUD, CLOUD_SHADE)
    shape = {}
    if small:   # sits in the lower-right, for partly-cloudy icons
        puffs = ((6.5, 8.0, 2.2), (9.0, 7.0, 2.6), (11.0, 8.6, 1.8))
        bottom = 10
    else:
        puffs = ((3.5, 6.5, 2.4), (6.5, 4.8, 3.0), (9.3, 6.6, 2.3))
        bottom = 8
    for cx, cy, r in puffs:
        _disc(shape, cx + dx, cy + dy, r, body)
    for (x, y), c in shape.items():
        if y <= bottom + dy:
            px[(x, y)] = shade if y == bottom + dy else c


def _sun(px, f, cx=6.0, cy=6.0, r=2.7, ray_in=3.6, ray_out=5.4):
    _disc(px, cx, cy, r, SUN)
    # 8 rays; long and short ones swap every 2 frames so the sun twinkles
    phase = (f // 2) % 2
    for i in range(8):
        a = math.radians(i * 45)
        long_ray = (i % 2 == phase)
        out = ray_out if long_ray else ray_in + 0.8
        steps = 3
        for k in range(steps):
            rr = ray_in + (out - ray_in) * k / max(1, steps - 1)
            x = int(round(cx - 0.5 + rr * math.cos(a)))
            y = int(round(cy - 0.5 + rr * math.sin(a)))
            _put(px, x, y, SUN if long_ray else SUN_GLOW)


def _moon(px, f, cx=6.0, cy=6.0, r=4.0, stars=True):
    for y in range(SIZE):
        for x in range(SIZE):
            inside = (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r
            bite = (x + 0.5 - cx - 2.0) ** 2 + (y + 0.5 - cy + 1.2) ** 2 <= (r - 0.6) ** 2
            if inside and not bite:
                px[(x, y)] = MOON
    if stars:
        for i, (sx, sy) in enumerate(((9, 2), (11, 6), (8, 9))):
            if (f + i * 3) % 8 < 5:     # each star blinks on its own beat
                _put(px, sx, sy, STAR)


def _drops(px, f, color=RAIN, light=RAIN_LIGHT, top=8, columns=(2, 5, 8, 11)):
    span = SIZE - top
    for i, x in enumerate(columns):
        y = top + (f + i * 3) % span
        _put(px, x - (y - top) // 3, y, color)       # slight slant
        if y - 1 >= top:
            _put(px, x - (y - 1 - top) // 3, y - 1, light)


def _flakes(px, f, top=8):
    span = SIZE - top
    for i, x in enumerate((2, 6, 10)):
        y = top + ((f // 2) + i * 2) % span
        sway = (0, 1, 1, 0, 0, -1, -1, 0)[(f + i * 2) % 8]
        _put(px, x + sway, y, SNOW)


def _bolt(px):
    for x, y in ((7, 7), (6, 8), (5, 9), (6, 9), (7, 9), (6, 10), (5, 11)):
        _put(px, x, y, BOLT)


def _fog(px, f):
    for row, (y, length, direction) in enumerate(((3, 9, 1), (6, 10, -1), (9, 8, 1))):
        shift = (0, 1, 2, 1, 0, -1, -2, -1)[f % 8] * direction
        start = (SIZE - length) // 2 + shift
        for x in range(start, start + length):
            _put(px, x, y, FOG_LIGHT if row == 1 else FOG)


def _wind(px, f):
    """Gust streaks blowing left to right, with curled tails."""
    gusts = ((3, 7, 0), (6, 9, 3), (9, 6, 5))   # (row, length, phase)
    for y, length, phase in gusts:
        head = (f * 2 + phase * 2) % (SIZE + length) - 1
        for k in range(length):
            x = head - k
            _put(px, x, y, WIND if k < length - 2 else WIND_DIM)
        _put(px, head + 1, y - 1, WIND)   # curl at the front of the gust


DRAW = {
    "sun":          lambda px, f: _sun(px, f),
    "moon":         lambda px, f: _moon(px, f),
    "partly_day":   lambda px, f: (_sun(px, f, cx=4.5, cy=4.5, r=2.4, ray_in=3.2, ray_out=4.6),
                                   _cloud(px, dx=(0, 0, 0, -1, -1, -1, 0, 0)[f], small=True)),
    "partly_night": lambda px, f: (_moon(px, f, cx=4.5, cy=4.5, r=3.4, stars=False),
                                   _put(px, 10, 1, STAR) if f % 8 < 5 else None,
                                   _cloud(px, dx=(0, 0, 0, -1, -1, -1, 0, 0)[f], small=True)),
    "cloud":        lambda px, f: _cloud(px, dx=(0, 0, 1, 1, 1, 1, 0, 0)[f], dy=1),
    "rain":         lambda px, f: (_cloud(px, dy=-1), _drops(px, f)),
    "storm":        lambda px, f: (_cloud(px, dy=-1, dark=f not in (2, 3)),
                                   _drops(px, f, columns=(2, 9, 12)),
                                   _bolt(px) if f in (2, 3, 6) else None),
    "snow":         lambda px, f: (_cloud(px, dy=-1), _flakes(px, f)),
    "fog":          lambda px, f: _fog(px, f),
    "wind":         lambda px, f: _wind(px, f),
}


def frames(kind):
    """List of FRAMES RGBA images (SIZE x SIZE) for an icon kind."""
    draw = DRAW.get(kind, DRAW["cloud"])
    out = []
    for f in range(FRAMES):
        px = {}
        draw(px, f)
        img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        for (x, y), c in px.items():
            img.putpixel((x, y), c + (255,))
        out.append(img)
    return out


_cache = {}


def frame(kind, index, scale=1):
    """One frame (cached), optionally pixel-doubled."""
    key = (kind, scale)
    if key not in _cache:
        imgs = frames(kind)
        if scale != 1:
            imgs = [im.resize((SIZE * scale, SIZE * scale), Image.NEAREST) for im in imgs]
        _cache[key] = imgs
    return _cache[key][index % FRAMES]


def export_sheets(out_dir):
    """Write one paletted BMP sprite sheet per icon (frames side by side,
    palette index 0 = transparent) for the Matrix Portal."""
    os.makedirs(out_dir, exist_ok=True)
    pal_img = Image.new("P", (1, 1))
    flat = [v for c in PALETTE for v in c]
    pal_img.putpalette(flat + [0] * (768 - len(flat)))
    for kind in KINDS:
        sheet = Image.new("P", (SIZE * FRAMES, SIZE), 0)
        sheet.putpalette(pal_img.getpalette())
        for i, im in enumerate(frames(kind)):
            for y in range(SIZE):
                for x in range(SIZE):
                    r, g, b, a = im.getpixel((x, y))
                    if a:
                        sheet.putpixel((i * SIZE + x, y), PALETTE.index((r, g, b)))
        sheet.save(os.path.join(out_dir, f"{kind}.bmp"))


if __name__ == "__main__":
    export_sheets(sys.argv[1] if len(sys.argv) > 1 else "icons")
    print("exported", ", ".join(KINDS))
