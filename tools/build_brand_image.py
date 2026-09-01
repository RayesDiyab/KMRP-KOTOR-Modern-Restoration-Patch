#!/usr/bin/env python3
"""Render the KMRP brand lockup: the crest fading into the background, and a
metallic 3D "KOTOR" wordmark over it.

Baked at build time rather than drawn at runtime. GDI+ can do gradients, but not
a convincing chrome bevel without a lot of per-frame work, and the patcher should
not be doing image compositing every time the window repaints. The result is
embedded as `KotorUniversalUI.brand` and blitted once.

The crest is the project author's own artwork. It is alpha-ramped from the middle
outwards so it dissolves into the window's dark background instead of ending at a
hard edge, and dimmed where the wordmark crosses it so the letters stay legible.

The wordmark uses **Cinzel Black**, a Trajan-derived serif in the same family as
the lettering on the reference art. It is built in four passes:

  1. a soft dark drop, offset down, for weight against the background
  2. a dark outline, so the letters hold their shape on any backdrop
  3. the metal itself -- a vertical gradient with a bright band across the
     upper middle, the way brushed steel catches a light above it
  4. a one-pixel top highlight and a bottom rim, which is what reads as bevel

Run from the repo root:

    python tools/build_brand_image.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


CREST = Path(r"C:\Users\diyab\Downloads\ChatGPT Image Sep 1, 2026, 12_31_57 PM.png")
CINZEL = Path(r"C:\Windows\Fonts\Cinzel-Black.ttf")

WIDTH, HEIGHT = 1200, 620
SUPERSAMPLE = 2

# Vertical stops for the metal, top to bottom: cool steel, a bright specular band
# a little above centre, then shadow, then a lifted rim so the base does not die.
METAL = [
    (0.00, (196, 210, 228)),
    (0.26, (243, 248, 255)),
    (0.42, (255, 255, 255)),
    (0.52, (150, 168, 188)),
    (0.72, (74, 90, 110)),
    (0.88, (120, 140, 163)),
    (1.00, (196, 212, 230)),
]


def gradient(width: int, height: int, stops) -> Image.Image:
    ramp = Image.new("RGB", (1, height))
    px = ramp.load()
    for y in range(height):
        t = y / max(1, height - 1)
        lower = stops[0]
        upper = stops[-1]
        for index in range(len(stops) - 1):
            if stops[index][0] <= t <= stops[index + 1][0]:
                lower, upper = stops[index], stops[index + 1]
                break
        span = max(1e-6, upper[0] - lower[0])
        k = (t - lower[0]) / span
        px[0, y] = tuple(int(round(lower[1][i] + (upper[1][i] - lower[1][i]) * k)) for i in range(3))
    return ramp.resize((width, height), Image.NEAREST)


def letter_spaced(draw: ImageDraw.ImageDraw, font, text: str, tracking: int):
    """Pillow has no tracking, so place each glyph by hand and report the extent."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    return widths, total


def draw_tracked(target: Image.Image, xy, font, text: str, tracking: int, fill):
    draw = ImageDraw.Draw(target)
    widths, total = letter_spaced(draw, font, text, tracking)
    x = xy[0] - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, xy[1]), ch, font=font, fill=fill, anchor="lt")
        x += w + tracking
    return total


def build(crest_path: Path, out: Path) -> None:
    w, h = WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # --- the crest, dissolved into the background -------------------------
    crest = Image.open(crest_path).convert("RGBA")
    px = crest.load()
    for y in range(crest.height):
        for x in range(crest.width):
            r, g, b, _ = px[x, y]
            px[x, y] = (r, g, b, max(r, g, b))      # black backdrop -> transparent
    crest = crest.crop(crest.getbbox())

    crest_h = int(h * 0.60)
    crest_w = int(crest.width * crest_h / crest.height)
    crest = crest.resize((crest_w, crest_h), Image.LANCZOS)

    # Radial ramp: full strength at the middle, gone by the edges, so there is no
    # boundary where the art stops and the window begins.
    fade = Image.new("L", crest.size, 0)
    fd = fade.load()
    cx, cy = crest_w / 2, crest_h / 2
    for y in range(crest_h):
        for x in range(crest_w):
            d = (((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2) ** 0.5
            fd[x, y] = 255 if d < 0.55 else (0 if d > 1.0 else int(255 * (1.0 - (d - 0.55) / 0.45) ** 1.4))
    fade = fade.filter(ImageFilter.GaussianBlur(6 * SUPERSAMPLE))
    alpha = crest.split()[3].point(lambda v: v)
    crest.putalpha(Image.eval(Image.merge("L", (alpha,)), lambda v: v).point(lambda v: v))
    crest = Image.composite(crest, Image.new("RGBA", crest.size, (0, 0, 0, 0)), fade)

    canvas.alpha_composite(crest, ((w - crest_w) // 2, int(h * 0.02)))

    # --- the wordmark ------------------------------------------------------
    text = "KOTOR"
    size = int(h * 0.275)
    font = ImageFont.truetype(str(CINZEL), size)
    tracking = int(size * 0.10)
    baseline = int(h * 0.565)
    centre = w // 2

    mask = Image.new("L", (w, h), 0)
    draw_tracked(mask, (centre, baseline), font, text, tracking, 255)
    box = mask.getbbox()

    # 1. weight beneath the letters
    drop = mask.filter(ImageFilter.GaussianBlur(9 * SUPERSAMPLE))
    shadow = Image.new("RGBA", (w, h), (4, 10, 18, 0))
    shadow.putalpha(drop.point(lambda v: int(v * 0.75)))
    canvas.alpha_composite(shadow, (0, int(6 * SUPERSAMPLE)))

    # 2. outline
    outline = mask.filter(ImageFilter.MaxFilter(2 * SUPERSAMPLE * 2 + 1))
    edge = Image.new("RGBA", (w, h), (8, 16, 27, 255))
    edge.putalpha(outline)
    canvas.alpha_composite(edge)

    # 3. the metal
    metal = gradient(w, box[3] - box[1], METAL).convert("RGBA")
    plate = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    plate.paste(metal, (0, box[1]))
    plate.putalpha(mask)
    canvas.alpha_composite(plate)

    # 4. bevel: a lit top edge and a darker bottom rim
    up = Image.new("L", (w, h), 0)
    up.paste(mask, (0, -2 * SUPERSAMPLE))
    top = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    top.putalpha(Image.composite(mask, Image.new("L", (w, h), 0), Image.eval(up, lambda v: 255 - v))
                 .point(lambda v: int(v * 0.55)))
    canvas.alpha_composite(top)

    down = Image.new("L", (w, h), 0)
    down.paste(mask, (0, 2 * SUPERSAMPLE))
    rim = Image.new("RGBA", (w, h), (20, 34, 52, 255))
    rim.putalpha(Image.composite(mask, Image.new("L", (w, h), 0), Image.eval(down, lambda v: 255 - v))
                 .point(lambda v: int(v * 0.65)))
    canvas.alpha_composite(rim)

    canvas = canvas.resize((WIDTH, HEIGHT), Image.LANCZOS)
    # Trim to content, but keep a margin: the drop shadow and the bevel's bottom
    # rim live outside the glyph mask, and a tight crop shears them off.
    box = canvas.getbbox()
    pad = 14
    canvas = canvas.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                          min(canvas.width, box[2] + pad), min(canvas.height, box[3] + pad)))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    print(f"{out}  {canvas.size[0]}x{canvas.size[1]}  {out.stat().st_size} bytes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crest", type=Path, default=CREST)
    parser.add_argument("--out", type=Path, default=Path("app/patcher/brand.png"))
    args = parser.parse_args()
    if not args.crest.exists():
        raise SystemExit(f"Crest artwork not found: {args.crest}")
    if not CINZEL.exists():
        raise SystemExit(f"Cinzel Black not found: {CINZEL}")
    build(args.crest, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
