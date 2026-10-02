#!/usr/bin/env python3
"""The Mac package's art: KMRP's icon, and the disk image's window background.

    python macos/tools/make_package_art.py OUTDIR [VERSION]

writes OUTDIR/Icon.iconset and OUTDIR/Icon.icns, KMRP's icon on the Mac (the Jedi crest with its lightsaber, cut
out of the lockup, over "KMRP"), which macos/build.sh makes into KMRP Installer's AppIcon.icns
and the disk image's .VolumeIcon.icns; and OUTDIR/background.png (640x460) and
OUTDIR/background@2x.png (1280x920), which it joins into one HiDPI TIFF for Finder. The window holds KMRP Installer on the
left and a link to /Applications on the right; the art draws the arrow between them, what to
do, and the one step a first launch needs, since the app is signed ad hoc.

The installer's art direction in another composition: its navy (UiTheme.Window), smoke lit
from above and blue motes, the brand lockup (src/patcher/brand.png) and its tagline, and the
accent blue, here as a glowing arrow. Finder draws icon labels black in Light Mode and white in
Dark Mode whatever the background, so each label sits on a slate plate (luminance about
0.18: both come out near 4.5:1). The smoke is fractal noise, seeded, so the art is the same
every build. Finder's window is exactly the art's size (its saved bounds are the content,
640x460).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "src" / "patcher" / "brand.png"
FONT_BOLD = ROOT / "assets" / "fonts" / "Arimo-SemiBold.ttf"
FONT_TEXT = ROOT / "assets" / "fonts" / "Arimo-Medium.ttf"

WIDTH, HEIGHT = 640, 460            # points; the build sets Finder's window to this
WINDOW = (7, 12, 21)                # UiTheme.Window
ACCENT = (42, 198, 239)             # UiTheme.Accent
ACCENT_STRONG = (0, 166, 214)       # UiTheme.AccentStrong
TEXT_MUTED = (177, 195, 208)        # UiTheme.TextMuted
PLATE, PLATE_EDGE = (104, 118, 138), (74, 150, 196)
TAGLINE = "M O D E R N .   R E S T O R E D .   S I M P L E ."
WORDMARK_INK = (0.0216, 0.9774)     # MainForm.WordmarkInkLeft/Right
BRAND_WIDTH, BRAND_TOP = 285, 10
# The icons' centres and size, as the build sets them in Finder, and each label's plate.
APP_CENTRE, APPLICATIONS_CENTRE = (170, 262), (470, 262)
ICON = 104
# Finder writes each label just under its icon, the capitals' middle at y 331 (measured on
# macOS 27 at icon size 104, text size 13); each plate is centred on that.
PLATE_WIDTH, PLATE_TOP, PLATE_HEIGHT = 150, 319, 24
# The crest in brand.png (tools/build_brand_image.py composes it; its source art is not in the
# repository): the wordmark is taken out of the lockup, and the crest is whatever is left. The
# letters start at row 345 and are the lockup's metal, grey or warm where the crest is blue;
# they are removed with a 3-pixel margin, which takes their dark outlines too.
WORDMARK_TOP, METAL_MARGIN = 342, 3


def smoke(size: tuple[int, int], s: int) -> Image.Image:
    """White smoke hanging from the top edge: fractal noise with a ragged front, as LightField's."""
    rng = random.Random(20260901)
    w, h = size
    field = Image.new("L", size, 0)
    for octave, (cell, weight) in enumerate(((48, 0.55), (22, 0.30), (10, 0.15))):
        cw, ch = max(2, w // (cell * s) + 2), max(2, h // (cell * s) + 2)
        noise = Image.new("L", (cw, ch))
        noise.putdata([rng.randrange(256) for _ in range(cw * ch)])
        layer = noise.resize(size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(cell * s * 0.35))
        field = ImageChops.add(field, layer.point(lambda v, k=weight: v * k))
    # Dense at the top, a front about a third down, wisps below it.
    ramp = Image.new("L", (1, h))
    ramp.putdata([max(0, min(255, round(255 * (1.0 - (y / h) / 0.42) ** 1.6))) if y / h < 0.42 else 0
                  for y in range(h)])
    ramp = ramp.resize(size)
    shaped = ImageChops.multiply(field.point(lambda v: max(0, min(255, (v - 96) * 2.4))), ramp)
    return shaped.filter(ImageFilter.GaussianBlur(1.5 * s))


def text_centred(draw, y, text, font, fill, s, cx=WIDTH / 2):
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    draw.text((cx * s - (right - left) / 2 - left, y * s), text, font=font, fill=fill)


def render(scale: int, version: str) -> Image.Image:
    s = scale
    size = (WIDTH * s, HEIGHT * s)
    image = Image.new("RGBA", size, WINDOW + (255,))

    # Smoke lit from above, then blue motes falling through it.
    alpha = smoke(size, s).point(lambda v: round(v * 0.62))
    image.alpha_composite(Image.merge("RGBA", (Image.new("L", size, 214), Image.new("L", size, 222),
                                               Image.new("L", size, 234), alpha)))
    rng = random.Random(1983)
    motes = Image.new("RGBA", size, (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(motes)
    for _ in range(70):
        x, y = rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT * 0.62)
        r = rng.uniform(0.7, 1.9)
        mdraw.ellipse([(x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s],
                      fill=(110, 180, 255, round(rng.uniform(90, 230) * (1 - y / (HEIGHT * 0.62)))))
    image.alpha_composite(motes.filter(ImageFilter.GaussianBlur(0.6 * s)))

    # The lockup and its tagline, set to the wordmark's ink width.
    brand = Image.open(BRAND).convert("RGBA")
    height = round(brand.height * BRAND_WIDTH / brand.width)
    image.alpha_composite(brand.resize((BRAND_WIDTH * s, height * s), Image.LANCZOS),
                          (round((WIDTH - BRAND_WIDTH) / 2 * s), BRAND_TOP * s))
    draw = ImageDraw.Draw(image)
    target = (WORDMARK_INK[1] - WORDMARK_INK[0]) * BRAND_WIDTH * s
    probe = ImageFont.truetype(str(FONT_BOLD), 20 * s)
    left, _, right, _ = draw.textbbox((0, 0), TAGLINE, font=probe)
    tagline = ImageFont.truetype(str(FONT_BOLD), max(1, round(20 * s * target / (right - left))))
    text_centred(draw, BRAND_TOP + height + 3, TAGLINE, tagline, ACCENT, s)

    # The arrow, in the accent blue with its glow, from the app to Applications.
    y = APP_CENTRE[1]
    x0, x1 = APP_CENTRE[0] + ICON / 2 + 34, APPLICATIONS_CENTRE[0] - ICON / 2 - 34
    shaft, head, head_length = 10, 38, 30
    arrow = [(x0, y - shaft / 2), (x1 - head_length, y - shaft / 2), (x1 - head_length, y - head / 2), (x1, y),
             (x1 - head_length, y + head / 2), (x1 - head_length, y + shaft / 2), (x0, y + shaft / 2)]
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon([(px * s, py * s) for px, py in arrow], fill=ACCENT + (200,))
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(9 * s)))
    body = Image.new("RGBA", size, (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(body)
    for i in range(round(head * s) + 1):   # a vertical gradient, lit at the top as the buttons are
        t = i / max(1, head * s)
        colour = tuple(round(a + (b - a) * t) for a, b in zip(ACCENT, ACCENT_STRONG))
        bdraw.line([(0, (y - head / 2) * s + i), (WIDTH * s, (y - head / 2) * s + i)], fill=colour + (255,))
    mask = Image.new("L", size, 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.polygon([(px * s, py * s) for px, py in arrow], fill=255)
    mdraw.ellipse([(x0 - shaft / 2) * s, (y - shaft / 2) * s, (x0 + shaft / 2) * s, (y + shaft / 2) * s], fill=255)
    image.paste(body, (0, 0), mask)

    # The label plates, where Finder writes each icon's name.
    draw = ImageDraw.Draw(image)
    for cx, _ in (APP_CENTRE, APPLICATIONS_CENTRE):
        box = [(cx - PLATE_WIDTH / 2) * s, PLATE_TOP * s, (cx + PLATE_WIDTH / 2) * s, (PLATE_TOP + PLATE_HEIGHT) * s]
        draw.rounded_rectangle(box, radius=PLATE_HEIGHT / 2 * s, fill=PLATE, outline=PLATE_EDGE, width=max(1, s))

    text_centred(draw, 364, "Drag KMRP Installer to Applications, then open it from there.",
                 ImageFont.truetype(str(FONT_BOLD), 15 * s), (236, 243, 248), s)
    text_centred(draw, 390, "The first time, if macOS will not open it: System Settings, Privacy & Security, "
                            "Open Anyway.", ImageFont.truetype(str(FONT_TEXT), 11 * s), TEXT_MUTED, s)
    if version:
        text_centred(draw, 410, f"KMRP {version} for macOS", ImageFont.truetype(str(FONT_TEXT), 11 * s),
                     (122, 138, 154), s)
    return image.convert("RGB")


def crest() -> Image.Image:
    """The lockup without its wordmark, cropped to the crest's blue ink."""
    art = np.array(Image.open(BRAND).convert("RGBA")).astype(np.int16)
    r, b, a = art[..., 0], art[..., 2], art[..., 3]
    rows = np.arange(art.shape[0])[:, None]
    metal = (b - r < 40) & (a > 30) & (rows > WORDMARK_TOP)
    grown = np.array(Image.fromarray((metal * 255).astype(np.uint8))
                     .filter(ImageFilter.MaxFilter(2 * METAL_MARGIN + 1))) > 0
    art[..., 3] = np.where(grown, 0, a)
    # Cropped to the crest's bright ink (its glow reaches across the whole lockup): x 305-650,
    # down to row 345, where the lockup's fade has taken the wing tips just above the letters.
    # The top is the image's, where the saber's faint tip runs out; below, room for the glow.
    ink = (b > 100) & (b - r > 40) & (a > 120) & (rows <= WORDMARK_TOP + 3)
    ys, xs = np.nonzero(ink)
    bottom = ys.max()
    box = (max(0, xs.min() - 24), 0, min(art.shape[1], xs.max() + 24), min(art.shape[0], bottom + 28))
    # Below the ink only glow and specks of the letters' tops are left: the specks (grey, not
    # blue) go, and the glow fades out.
    below = rows > bottom - 4
    art[..., 3] = np.where(below & (b - r < 60) & (np.maximum(np.maximum(r, art[..., 1]), b) > 40), 0, art[..., 3])
    for y in range(bottom, box[3]):
        art[y, :, 3] = art[y, :, 3] * (box[3] - y) // (box[3] - bottom)
    return Image.fromarray(art.astype(np.uint8)).crop(box)


def serif(size: int) -> ImageFont.FreeTypeFont:
    """Georgia, the wordmark's measured typeface (tools/build_brand_image.py); every Mac has it."""
    for path in ("/System/Library/Fonts/Supplemental/Georgia.ttf", "/Library/Fonts/Georgia.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.truetype(str(FONT_BOLD), size)


def metal_text(text: str, cap: int, tracking: float) -> Image.Image:
    """Text in the wordmark's metal: a cool silver face, brighter at the top, a warm glint low
    down, and a dark outline."""
    font = serif(round(cap / 0.69))
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    widths = [probe.textbbox((0, 0), ch, font=font) for ch in text]
    advance = [w[2] - w[0] for w in widths]
    width = sum(advance) + round(tracking * cap) * (len(text) - 1) + 20
    top = min(w[1] for w in widths)
    height = max(w[3] for w in widths) - top + 20
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    x = 10
    for ch, w, adv in zip(text, widths, advance):
        draw.text((x - w[0], 10 - top), ch, font=font, fill=255)
        x += adv + round(tracking * cap)
    face = Image.new("RGBA", mask.size)
    stops = [(0.0, (238, 242, 247)), (0.45, (150, 162, 178)), (0.72, (206, 196, 180)), (1.0, (118, 128, 144))]
    fdraw = ImageDraw.Draw(face)
    for y in range(height):
        t = y / max(1, height - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                fdraw.line([(0, y), (width, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(c0, c1)) + (255,))
                break
    out = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    outline = mask.filter(ImageFilter.MaxFilter(5))
    out.paste(Image.new("RGBA", mask.size, (12, 18, 28, 255)), (0, 0), outline)
    out.paste(face, (0, 0), mask)
    return out


def icon(size: int) -> Image.Image:
    """The crest on the installer's navy, in a rounded square as the app icon is."""
    crest_art = crest()
    big = 1024
    icon = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    plate = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    inset = 100                           # macOS icons leave this margin round their shape
    pdraw = ImageDraw.Draw(plate)
    pdraw.rounded_rectangle([inset, inset, big - inset, big - inset], radius=185, fill=WINDOW + (255,))
    glow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([260, 190, 764, 700], fill=(38, 84, 150, 150))
    plate.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle([inset, inset, big - inset, big - inset], radius=185, fill=255)
    plate.putalpha(ImageChops.multiply(plate.getchannel("A"), mask))
    icon.alpha_composite(plate)
    ImageDraw.Draw(icon).rounded_rectangle([inset, inset, big - inset, big - inset], radius=185,
                                           outline=(34, 103, 132, 255), width=6)   # UiTheme.Border
    # The crest large in the plate's upper part, KMRP under it in the wordmark's metal, both
    # clipped to the plate so the glow stays in.
    fit = min(720 / crest_art.width, 540 / crest_art.height)
    scaled = crest_art.resize((round(crest_art.width * fit), round(crest_art.height * fit)), Image.LANCZOS)
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    word = metal_text("KMRP", 104, 0.12)   # tighter than the KOTOR wordmark's 0.297
    gap = 10
    top = inset + (big - 2 * inset - (scaled.height + gap + word.height)) // 2   # the pair centred
    layer.alpha_composite(scaled, ((big - scaled.width) // 2, top))
    layer.alpha_composite(word, ((big - word.width) // 2, top + scaled.height + gap))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    icon.alpha_composite(layer)
    return icon.resize((size, size), Image.LANCZOS) if size != big else icon


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    out = Path(sys.argv[1])
    version = sys.argv[2] if len(sys.argv) == 3 else ""
    out.mkdir(parents=True, exist_ok=True)
    render(1, version).save(out / "background.png", dpi=(72, 72))
    render(2, version).save(out / "background@2x.png", dpi=(144, 144))
    iconset = out / "Icon.iconset"
    iconset.mkdir(exist_ok=True)
    for points in (16, 32, 128, 256, 512):
        icon(points).save(iconset / f"icon_{points}x{points}.png")
        icon(points * 2).save(iconset / f"icon_{points}x{points}@2x.png")
    # Pillow writes the same PNG-backed ICNS family directly. On macOS 26.0.1,
    # iconutil rejects both this complete iconset and an iconset it just extracted
    # from Apple's QuickTime icon as "Invalid Iconset"; its ICNS decoder accepts
    # the file Pillow writes here.
    icon(1024).save(out / "Icon.icns", format="ICNS")
    print(f"background.png {WIDTH}x{HEIGHT}, background@2x.png {WIDTH * 2}x{HEIGHT * 2}, "
          "Icon.iconset, Icon.icns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
