#!/usr/bin/env python3
"""The LT / RT cues of the in-game menu's tab strip, as arrows in the game's interface style.

The standalone controller patch showed the controller family's own trigger pictures
beside the tab strip. The maintainer asked for arrows instead (2026-10-05): a triangle
with rounded corners pointing the way the trigger moves along the strip, the trigger's
name in its wide end, drawn like the game's panels (a dark blue body in a bright blue
frame with a soft glow). He chose this look from four prototypes and its size and
place on screen in the running game; `K1NativeJoystick.cpp` (BindOneCueK1) does the
placing, and relies on one number here, EDGE: how far the arrow's flat side is inside
its square.

Nothing here is anyone's art or font. The shape is drawn, and so are the letters:
five of them, in straight strokes with round ends, which is how the game's own
interface lettering is built. (The prototypes used a TrueType font that resembles it,
from another mod; a shipped texture must not depend on that.)

Usage:
    python tools/build_tab_arrows.py OUT_DIR      write the eight pictures as PNG, to look at

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

SIZE = 128                 # the texture's side; the cue's control is square
SAMPLES = 4                # drawn this many times larger and reduced
EDGE = 0.03                # the flat side's distance from the square's edge, as a fraction of the side
CORNER = 0.07              # the corners' radius
FLAT = 0.76                # the flat side's length (K1NativeJoystick.cpp sizes the cue by it)
FRAME = (40, 140, 255)
BODY_TOP, BODY_BOTTOM, BODY_ALPHA = (8, 30, 90), (2, 10, 44), 235
GLOW, GLOW_STRENGTH = (30, 110, 255), 0.55
LETTERS, LETTER_GLOW = (60, 190, 255), (0, 60, 160)

# What each controller family calls its two triggers.
NAMES = {"xbox": ("LT", "RT"), "playstation": ("L2", "R2"), "switch": ("ZL", "ZR"), "steamdeck": ("L2", "R2")}

# The letters, as strokes in a cell one unit wide and one unit high (y down).
STROKES = {
    "L": [[(0, 0), (0, 1), (1, 1)]],
    "T": [[(0, 0), (1, 0)], [(0.5, 0), (0.5, 1)]],
    "R": [[(0, 1), (0, 0), (1, 0), (1, 0.5), (0, 0.5)], [(0.45, 0.5), (1, 1)]],
    "Z": [[(0, 0), (1, 0), (0, 1), (1, 1)]],
    "2": [[(0, 0), (1, 0), (1, 0.5), (0, 0.5), (0, 1), (1, 1)]],
}


def _shape(n: int, pointing_left: bool):
    from PIL import Image, ImageDraw

    mask = Image.new("L", (n, n), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(n * CORNER)
    back = n - int(n * EDGE) - radius
    tip = back - int(n * 0.66)
    half = int(n * (FLAT / 2)) - radius
    points = [(tip, n // 2), (back, n // 2 - half), (back, n // 2 + half)]
    if not pointing_left:
        points = [(n - x, y) for x, y in points]
    draw.polygon(points, fill=255)
    draw.line(points + [points[0]], fill=255, width=radius * 2, joint="curve")
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    return mask


def _letters(n: int, text: str, pointing_left: bool):
    """The trigger's name as a mask, in the arrow's wide end."""
    from PIL import Image, ImageDraw

    mask = Image.new("L", (n, n), 0)
    draw = ImageDraw.Draw(mask)
    height, width, gap, stroke = n * 0.20, n * 0.125, n * 0.055, max(2, int(n * 0.034))
    total = len(text) * width + (len(text) - 1) * gap
    middle = n * (0.685 if pointing_left else 0.315)
    left, top = middle - total / 2, n / 2 - height / 2
    for index, letter in enumerate(text):
        x0 = left + index * (width + gap)
        for line in STROKES[letter]:
            points = [(x0 + x * width, top + y * height) for x, y in line]
            draw.line(points, fill=255, width=stroke, joint="curve")
            for x, y in (points[0], points[-1]):
                draw.ellipse((x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2), fill=255)
    return mask


def arrow(text: str, pointing_left: bool, size: int = SIZE):
    """The cue's picture, RGBA."""
    from PIL import Image, ImageChops, ImageFilter

    n = size * SAMPLES
    outer = _shape(n, pointing_left)
    border = int(n * 0.028)
    inner = outer.filter(ImageFilter.MinFilter(2 * (border // 2) + 1)).filter(ImageFilter.MinFilter(2 * (border // 2) + 1))
    canvas = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    glow = Image.new("RGBA", (n, n), GLOW + (0,))
    glow.putalpha(outer.filter(ImageFilter.GaussianBlur(n * 0.03)).point(lambda v: int(v * GLOW_STRENGTH)))
    canvas = Image.alpha_composite(canvas, glow)

    body = Image.new("RGBA", (1, n))
    for y in range(n):
        t = y / (n - 1)
        body.putpixel((0, y), tuple(int(BODY_TOP[i] + (BODY_BOTTOM[i] - BODY_TOP[i]) * t) for i in range(3)) + (BODY_ALPHA,))
    body = body.resize((n, n))
    body.putalpha(ImageChops.multiply(body.split()[3], inner))
    canvas = Image.alpha_composite(canvas, body)

    frame = Image.new("RGBA", (n, n), FRAME + (255,))
    frame.putalpha(ImageChops.subtract(outer, inner))
    canvas = Image.alpha_composite(canvas, frame)

    letters = _letters(n, text, pointing_left)
    halo = Image.new("RGBA", (n, n), LETTER_GLOW + (0,))
    halo.putalpha(letters.filter(ImageFilter.GaussianBlur(n * 0.012)))
    canvas = Image.alpha_composite(canvas, halo)
    ink = Image.new("RGBA", (n, n), LETTERS + (0,))
    ink.putalpha(letters)
    canvas = Image.alpha_composite(canvas, ink)
    return canvas.resize((size, size), Image.LANCZOS)


def arrow_tga(family: str, right: bool, size: int = SIZE) -> bytes:
    """The texture as the patch's other cue textures are: 32-bit, uncompressed, rows from the bottom."""
    image = arrow(NAMES[family][1 if right else 0], not right, size)
    pixels = image.load()
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, size, size, 32, 8)
    rows = [b"".join(bytes((pixels[x, y][2], pixels[x, y][1], pixels[x, y][0], pixels[x, y][3])) for x in range(size))
            for y in range(size - 1, -1, -1)]
    return header + b"".join(rows)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for family, names in NAMES.items():
        for right in (False, True):
            arrow(names[1 if right else 0], not right, 256).save(out / f"tab-arrow-{family}-{names[1 if right else 0]}.png")
    print(f"eight pictures in {out}")
