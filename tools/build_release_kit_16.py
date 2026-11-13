"""The KMRP 1.6 press kit: twelve 1920x1080 pages in releases/v1.6.0/press-kit.

The look is the one the maintainer settled on 2026-11-13 over the mockup rounds: a night sky
of mixed stars, the crest's blue glow, thin red and orange smoke along the bottom, KOTOR in
polished silver (the serif-foot patches of src/patcher/brand.png smoothed on the cover only),
KMRP in gold on the same bevel, 1.6 in cyan metal with a soft glow, white feature lines and
holo-blue page titles. The metal lettering is tools/build_release_cover.py's, so the wordmarks
keep the 1.5 kit's bevel.

Frames are whole screenshots scaled down, never cropped or retouched. The 1.6 frames are the
maintainer's 1920x1080 screenshots of 2026-11-13 in releases/v1.6.0; the frames reused from
the 1.5 kit come from build/controller-standalone/shots and say so in their label.

    python tools/build_release_kit_16.py

Documentation standard: see docs/documentation-standard.md.
"""
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(r"E:\KMRP - KOTOR Modern Restoration Patch")
sys.path.insert(0, str(ROOT / "tools"))
import build_release_cover as cover  # noqa: E402
from build_brand_image import DEFAULT_FONT  # noqa: E402

NEW = ROOT / "releases" / "v1.6.0"
OUT = NEW / "press-kit"
SHOTS15 = ROOT / "build" / "controller-standalone" / "shots"     # the 1.5 kit's source frames
BOLD = Path(r"C:\Windows\Fonts\georgiab.ttf")

# The proposed 1.6 palette.
P = {
    "Night":   (6, 9, 20),       # #060914  ground, the sky at the top
    "Deep":    (9, 22, 40),      # #091628  ground, lower down
    "Bloom":   (20, 64, 98),     # #144062  the blue glow behind the crest and KOTOR
    "Glow":    (255, 190, 136),  # #FFBE88  light orange: the smoke's upper wisps
    "Ember":   (244, 112, 92),   # #F4705C  light red: the smoke nearest the edge
    "Gold":    (232, 190, 96),   # #E8BE60  KMRP: the 1.5 cover's gold on the same bevel
    "Saber":   (64, 206, 255),   # #40CEFF  1.6: a white core in cyan light
    "Bronze":  (205, 140, 80),   # #CD8C50  bronze: feature lines, captions
    "BronzeHi": (232, 186, 128), # #E8BA80  light bronze: the platforms line
    "Holo":    (64, 200, 236),   # #40C8EC  1.6, subjects, frames, subtitle: the game's UI blue
    "Ice":     (190, 236, 250),  # #BEECFA  feature lines and captions
    "Rule":    (30, 84, 108),    # #1E546C  rules
    "Text":    (236, 243, 248),  # #ECF3F8  cool white
}
HOLO_RAMP = ((74, 40, 14), (196, 124, 58), (255, 220, 168))   # bronze: dark, middle, highlight


def neon_glow(canvas, image, xy, radius):
    """A neon tube's light: the letters' own shape, blurred, in neon yellow, under them."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shape = Image.new("L", canvas.size, 0)
    shape.paste(image.getchannel("A"), xy)
    halo = shape.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * 0.5))
    layer = Image.new("RGBA", canvas.size, P["Neon"] + (0,))
    layer.putalpha(halo)
    canvas.alpha_composite(layer)
FILES = {
    "pazaak-wager": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 20.02.55.12.png",
    "pazaak-sidedeck": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 20.03.22.41.png",
    "pazaak-table": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 20.03.34.19.png",
    "swoop": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 20.04.28.35.png",
    "hud-keyboard": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 20.20.33.89.png",
    "hud-controller": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 20.20.40.25.png",
    "text-size": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 20.20.46.25.png",
    "remap": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 20.21.03.75.png",
    "layout": "Star Wars  Knights Of The Old Republic Screenshot 2026.11.13 - 22.38.19.59.png",  # 3440x1440
}
W, H = 1920, 1080


def font(path, size):
    return ImageFont.truetype(str(path), size)


SABER_CORE = (238, 253, 255)     # the blade's white-hot core
SABER_GLOW = ((150, 236, 255), (64, 206, 255), (24, 150, 255))   # tight, middle, wide


def saber(image):
    """Text drawn like a lightsaber blade: a white core in layers of cyan light.

    Returns (picture, offset): the picture is larger than `image` by the glow's reach, and
    offset is where `image`'s top left falls inside it.
    """
    alpha = image.getchannel("A")
    cap = image.height
    pad = int(cap * 0.9)
    shape = Image.new("L", (image.width + 2 * pad, image.height + 2 * pad), 0)
    shape.paste(alpha, (pad, pad))
    out = Image.new("RGBA", shape.size, (0, 0, 0, 0))
    # one soft cyan glow behind, not a neon tube
    halo = shape.filter(ImageFilter.GaussianBlur(max(2, cap * 0.20))).point(lambda v: min(255, int(v * 0.80)))
    layer = Image.new("RGBA", shape.size, SABER_GLOW[1] + (0,))
    layer.putalpha(halo)
    out.alpha_composite(layer)
    # the numerals themselves: the silver bevel's light and shade in cyan, like KMRP's metal
    arr = np.asarray(image).astype(np.float32)
    lum = arr[..., :3].max(axis=2) / 255.0
    low, mid, high = (np.array(c, dtype=np.float32) for c in CYAN_RAMP)
    lower = low + (mid - low) * np.clip(lum / 0.6, 0, 1)[..., None]
    upper = mid + (high - mid) * np.clip((lum - 0.6) / 0.4, 0, 1)[..., None]
    rgb = np.where((lum < 0.6)[..., None], lower, upper)
    metal = Image.fromarray(np.clip(np.dstack([rgb, arr[..., 3:4]]), 0, 255).astype(np.uint8), "RGBA")
    out.alpha_composite(metal, (pad, pad))
    return out, (pad, pad)


CYAN_RAMP = ((28, 128, 182), (104, 226, 255), (238, 253, 255))   # dark, middle, highlight


SHINY_GOLD = ((92, 54, 6), (226, 170, 48), (255, 226, 120), (255, 252, 232))   # shadow, body, light, glint


def shiny_gold(metal):
    """The silver bevel's own light and shade in polished gold: deeper shadows, a bright
    body, and the lit edge pushed to a near-white glint, so it reads as shiny metal."""
    arr = np.asarray(metal).astype(np.float32)
    lum = arr[..., :3].max(axis=2) / 255.0
    lum = np.clip((lum - 0.18) / 0.72, 0, 1) ** 0.85            # more contrast than the silver
    stops = [np.array(c, dtype=np.float32) for c in SHINY_GOLD]
    at = (0.0, 0.45, 0.80, 1.0)
    rgb = np.zeros(arr.shape[:2] + (3,), dtype=np.float32)
    for i in range(3):
        lo, hi = at[i], at[i + 1]
        k = np.clip((lum - lo) / (hi - lo), 0, 1)[..., None]
        inside = ((lum >= lo) & (lum <= hi))[..., None]
        rgb = np.where(inside, stops[i] + (stops[i + 1] - stops[i]) * k, rgb)
    # polished metal: a reflected sky in the upper half, a dark horizon line just below the
    # middle, warm light again at the foot. Multiplied in, so the bevel's shading stays.
    solid = arr[..., 3] > 128
    ys = np.where(solid.any(axis=1))[0]
    top, bottom = (ys[0], ys[-1]) if len(ys) else (0, arr.shape[0] - 1)
    t = np.clip((np.arange(arr.shape[0], dtype=np.float32) - top) / max(1, bottom - top), 0, 1)
    marks = np.array([0.0, 0.40, 0.50, 0.56, 0.80, 1.0], dtype=np.float32)
    gain = np.array([1.28, 1.12, 0.96, 0.72, 0.96, 1.10], dtype=np.float32)
    band = np.interp(t, marks, gain)[:, None, None]
    rgb = rgb * band
    # the lit edge of the bevel goes toward a pale glint
    glint = np.clip((lum - 0.82) / 0.18, 0, 1)[..., None] ** 1.5
    rgb = rgb + (255 - rgb) * glint * 0.55
    return Image.fromarray(np.clip(np.dstack([rgb, arr[..., 3:4]]), 0, 255).astype(np.uint8), "RGBA")


def polish_silver(lockup):
    """KOTOR's silver letters in the lockup, polished: more contrast in their own bevel, a
    bright reflected sky in the upper half, a soft dark line below the middle, and the lit
    edges pushed toward white. Only grey pixels change, so the blue crest stays as it is."""
    arr = np.asarray(lockup).astype(np.float32)
    rgb, alpha = arr[..., :3], arr[..., 3]
    hi, lo = rgb.max(axis=2), rgb.min(axis=2)
    sat = (hi - lo) / np.maximum(hi, 1)
    grey = np.clip((0.30 - sat) / 0.15, 0, 1) * (alpha > 8)            # 1 on silver, 0 on blue
    lum = hi / 255.0
    letters = (grey > 0.5) & (alpha > 128) & (lum > 0.25)
    ys = np.where(letters.sum(axis=1) > letters.shape[1] * 0.06)[0]    # rows KOTOR fills, not the thin blade
    if not len(ys):
        return lockup
    top, bottom = ys[0], ys[-1]
    rows = np.zeros(arr.shape[0], dtype=np.float32)
    rows[max(0, top - 3):bottom + 4] = 1
    grey = grey * rows[:, None]                                         # the blade above is left alone
    t = np.clip((np.arange(arr.shape[0], dtype=np.float32) - top) / max(1, bottom - top), 0, 1)
    # The source art (src/patcher/brand.png, on the 1.5 covers too) has lighter patches where
    # each stem meets its bottom serif. In the feet, no pixel is let brighter than the feet's
    # usual silver, so the patches go and the darker bevel shading stays.
    feet = np.clip((t - 0.82) / 0.05, 0, 1)[:, None]                    # 0 above, 1 in the serifs
    in_feet = letters & (feet[:, 0] >= 1)[:, None]
    if in_feet.any():
        ceiling = float(np.percentile(lum[in_feet], 50))
        lum = lum - np.maximum(lum - ceiling, 0) * feet
    marks = np.array([0.0, 0.38, 0.50, 0.57, 0.80, 1.0], dtype=np.float32)
    gain = np.array([1.40, 1.24, 1.04, 0.58, 0.92, 1.14], dtype=np.float32)
    band = np.interp(t, marks, gain)[:, None]
    stretched = np.clip((lum - 0.30) / 0.55, 0, 1) ** 0.9               # more contrast
    base = 84 + 171 * stretched
    polished = base * band
    glint = np.clip((lum - 0.72) / 0.28, 0, 1) ** 1.3
    polished = polished + (255 - polished) * glint * 0.75
    # a whisper of cool blue in the shadows, as polished steel picks up the sky
    out_rgb = np.dstack([polished * 0.97, polished * 0.99, np.minimum(255, polished * 1.04)])
    k = grey[..., None]
    rgb = rgb * (1 - k) + out_rgb * k
    return Image.fromarray(np.clip(np.dstack([rgb, alpha]), 0, 255).astype(np.uint8), "RGBA")


def gold_pop(canvas, word, xy, sparkles=True):
    """Shiny gold on the page: a warm halo behind the letters, the letters, and two small
    four-pointed sparkles where light catches the top of the first and last letter."""
    cap = word.height
    shape = Image.new("L", canvas.size, 0)
    shape.paste(word.getchannel("A"), xy)
    halo = shape.filter(ImageFilter.GaussianBlur(max(2, cap * 0.20))).point(lambda v: int(v * 0.16))
    layer = Image.new("RGBA", canvas.size, (255, 196, 80, 0))
    layer.putalpha(halo)
    canvas.alpha_composite(layer)
    canvas.alpha_composite(word, xy)
    if not sparkles:
        return
    a = np.asarray(word.getchannel("A"))
    cols = np.where(a.max(axis=0) > 128)[0]
    for x in (cols[0] + cap * 0.22, cols[-1] - cap * 0.30):
        x = int(x)
        rows = np.where(a[:, max(0, min(a.shape[1] - 1, x))] > 128)[0]
        if not len(rows):
            continue
        sparkle(canvas, (xy[0] + x, xy[1] + rows[0] + int(cap * 0.04)), cap * 0.32)


def sparkle(canvas, centre, size):
    """A four-pointed star of light with a soft glow, white at the centre, gold at the tips."""
    s = int(size * 2.4)
    star = Image.new("L", (2 * s, 2 * s), 0)
    d = ImageDraw.Draw(star)
    c, long, thin = s, size, max(1.5, size * 0.11)
    d.polygon([(c, c - long), (c + thin, c), (c, c + long), (c - thin, c)], fill=255)
    d.polygon([(c - long * 0.9, c), (c, c - thin), (c + long * 0.9, c), (c, c + thin)], fill=255)
    core = star.filter(ImageFilter.GaussianBlur(max(1, size * 0.03)))
    glow = star.filter(ImageFilter.GaussianBlur(max(2, size * 0.18))).point(lambda v: min(255, v * 2))
    x0, y0 = int(centre[0] - s), int(centre[1] - s)
    for mask, colour in ((glow, (255, 214, 120)), (core, (255, 252, 236))):
        layer = Image.new("RGBA", (2 * s, 2 * s), colour + (0,))
        layer.putalpha(mask)
        canvas.alpha_composite(layer, (x0, y0))


def holo_metal(metal):
    arr = np.asarray(metal).astype(np.float32)
    lum = arr[..., :3].max(axis=2) / 255.0
    low, mid, high = (np.array(c, dtype=np.float32) for c in HOLO_RAMP)
    lower = low + (mid - low) * np.clip(lum / 0.6, 0, 1)[..., None]
    upper = mid + (high - mid) * np.clip((lum - 0.6) / 0.4, 0, 1)[..., None]
    rgb = np.where((lum < 0.6)[..., None], lower, upper)
    return Image.fromarray(np.clip(np.dstack([rgb, arr[..., 3:4]]), 0, 255).astype(np.uint8), "RGBA")


def smoke(seed):
    """Soft fractal noise in 0..1, its cells wider than tall so it drifts sideways like smoke."""
    rng = np.random.default_rng(seed)
    total = np.zeros((H, W), dtype=np.float32)
    weight_sum = 0.0
    for octave in range(6):
        cols, rows = 5 * 2 ** octave, 3 * 2 ** octave
        cells = rng.random((rows, cols)).astype(np.float32)
        layer = Image.fromarray((cells * 255).astype(np.uint8), "L").resize((W, H), Image.BICUBIC)
        layer = layer.filter(ImageFilter.GaussianBlur(max(1, 40 // (octave + 1))))
        w = 0.55 ** octave
        total += np.asarray(layer, dtype=np.float32) / 255 * w
        weight_sum += w
    n = total / weight_sum
    n = (n - n.min()) / max(1e-6, n.max() - n.min())
    wisps = (1 - np.abs(2 * n - 1)) ** 3                                # thin bright ridges
    out = 0.65 * n + 0.35 * wisps
    return (out - out.min()) / max(1e-6, out.max() - out.min())


def dusk(stars=True, seed=20261113, grid=True):
    """Night sky, a holo bloom behind the crest, and a faint holo floor grid at the bottom."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = yy / H
    night, deep, bloom, glow, ember = (np.array(P[k], dtype=np.float32)
                                       for k in ("Night", "Deep", "Bloom", "Glow", "Ember"))
    base = night + (deep - night) * (np.clip(t, 0, 1)[..., None] ** 1.3)
    d = np.sqrt(((xx - W / 2) / (W * 0.32)) ** 2 + ((yy - H * 0.36) / (H * 0.44)) ** 2)
    base = base + (bloom - base) * (np.clip(1 - d, 0, 1)[..., None] ** 2.0) * 0.75
    # the bottom glow as smoke: red and orange drifting in wide wisps, edge to edge
    puff = smoke(seed)
    tint = smoke(seed + 7)
    rise = np.clip((t - 0.60) / 0.40, 0, 1) ** 2.0                     # faint behind the text, full at the edge
    edge = np.clip((t - 0.78) / 0.22, 0, 1)                            # the last fifth: more red
    amount = np.clip(rise * (0.05 + 1.0 * puff ** 2.2), 0, 0.85)[..., None]   # thin wisps, clear gaps
    mix = np.clip(0.25 + 0.9 * tint - 0.55 * edge, 0, 1)[..., None]     # 0 red, 1 orange
    colour = ember + (glow - ember) * mix
    base = base + (colour - base) * amount * 0.50
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    if grid:     # a hologram projector's floor: lines to a vanishing point, rows closer near it
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(layer)
        horizon, vx = H * 0.80, W / 2
        for i in range(-24, 25):
            g.line([(vx + i * 14, horizon), (vx + i * 230, H + 40)], fill=P["Holo"] + (34,), width=1)
        for k in range(1, 12):
            y = horizon + (H - horizon + 40) * (k / 11) ** 2.2
            g.line([(0, y), (W, y)], fill=P["Holo"] + (int(14 + 30 * k / 11),), width=1)
        fade = Image.new("L", (W, H), 0)
        fd = ImageDraw.Draw(fade)
        for y in range(int(horizon), H):
            fd.line([(0, y), (W, y)], fill=int(255 * min(1, (y - horizon) / (H - horizon) * 1.4)))
        side = Image.linear_gradient("L").rotate(90, expand=True).resize((W // 2, H))
        mask = Image.new("L", (W, H), 0)
        mask.paste(side, (0, 0))
        mask.paste(side.transpose(Image.FLIP_LEFT_RIGHT), (W // 2, 0))
        layer.putalpha(Image.fromarray((np.asarray(layer.getchannel("A")).astype(np.float32)
                                        * np.asarray(fade) / 255 * np.asarray(mask) / 255).astype(np.uint8)))
        img.alpha_composite(layer)
    if stars:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        rng = random.Random(seed)
        halos = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(halos)
        for _ in range(W * H // 2000):     # about 1,000 stars, two and a half times as many
            x, y = rng.uniform(0, W), rng.uniform(0, H * 0.78)
            fade = 1 - y / (H * 0.78)
            pick = rng.random()
            # half are smaller faint stars; the rest keep the sizes the cover had
            r = 0.55 if pick < 0.50 else (1.0 if pick < 0.85 else (1.7 if pick < 0.965 else 2.5))
            a = int(rng.randint(40, 170) * fade)
            d.ellipse([x - r, y - r, x + r, y + r], fill=P["Text"] + (a,))
            if r > 2:     # the biggest stars get a soft halo
                hd.ellipse([x - r * 3, y - r * 3, x + r * 3, y + r * 3], fill=P["Ice"] + (a // 3,))
        img.alpha_composite(halos.filter(ImageFilter.GaussianBlur(3)))
        img.alpha_composite(layer)
    return img


def tracked(draw, y, text, face, fill, tracking, centre=None, x=None, right=None):
    widths = [draw.textlength(c, font=face) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    if centre is not None:
        x = centre - total / 2
    if right is not None:
        x = right - total
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=face, fill=fill, anchor="ls")
        x += w + tracking
    return total


def build_cover():
    canvas = dusk(grid=False)
    lockup = Image.open(ROOT / cover.LOCKUP).convert("RGBA")
    lockup = lockup.crop(lockup.getbbox())
    tw = int(W * 0.54)
    lockup = lockup.resize((tw, int(lockup.height * tw / lockup.width)), Image.LANCZOS)
    lockup = polish_silver(lockup)
    # a faint cool halo around KOTOR's letters only, so the silver lifts off the sky
    shine = np.asarray(lockup).astype(np.float32)
    grey = (shine[..., :3].max(axis=2) - shine[..., :3].min(axis=2)) < 40
    solid = grey & (shine[..., 3] > 128)
    rows = solid.sum(axis=1) > solid.shape[1] * 0.06                    # KOTOR's rows only
    solid = solid & rows[:, None]
    shape = Image.fromarray((solid * 255).astype(np.uint8), "L")
    halo = shape.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.22))
    glow_layer = Image.new("RGBA", lockup.size, (220, 236, 255, 0))
    glow_layer.putalpha(halo)
    canvas.alpha_composite(glow_layer, ((W - tw) // 2, int(H * 0.03)))
    y = int(H * 0.03)
    canvas.alpha_composite(lockup, ((W - tw) // 2, y))
    cursor = y + lockup.height
    cap = int(H * 0.088)
    word = shiny_gold(cover.metal_text("KMRP", cap, DEFAULT_FONT))   # the same bevel, in gold
    num = cover.metal_text("1.6", cap, DEFAULT_FONT)
    word, num = word.crop(word.getbbox()), num.crop(num.getbbox())
    gap = int(H * 0.05)
    both = Image.new("RGBA", (word.width + gap + num.width, max(word.height, num.height)), (0, 0, 0, 0))
    ky = cursor + int(H * 0.012)
    gold_pop(canvas, word, ((W - both.width) // 2, ky + both.height - word.height), sparkles=False)
    blade, (px, py) = saber(num)
    canvas.alpha_composite(blade, ((W - both.width) // 2 + word.width + gap - px,
                                   ky + both.height - num.height - py))
    draw = ImageDraw.Draw(canvas)
    mid = ky + both.height // 2
    sub = font(DEFAULT_FONT, int(H * 0.033))
    sy = ky + both.height + int(H * 0.05)
    tracked(draw, sy, "MODERN RESTORATION PATCH", sub, P["Holo"] + (255,), sub.size * 0.42, centre=W / 2)
    face = font(BOLD, int(H * 0.029))
    lines = ("ORIGINAL XBOX CONTROLS  \u00b7  REMAPPING  \u00b7  PAZAAK  \u00b7  SWOOP RACING",
             "TEXT SIZE  \u00b7  HUD SIZE  \u00b7  ICON SIZE  \u00b7  LIVE ADAPTIVE LAYOUT")
    fy = sy + int(H * 0.066)
    rows = [(fy + r * int(face.size * 1.75), line, face.size * 0.2) for r, line in enumerate(lines)]
    rows.append((fy + 2 * int(face.size * 1.75), "WINDOWS  \u00b7  LINUX  \u00b7  macOS", face.size * 0.3))
    # a soft dark shadow first, so the white words stand in front of the smoke
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y, line, track in rows:
        tracked(sd, y + 2, line, face, (2, 4, 12, 210), track, centre=W / 2)
    canvas.alpha_composite(shade.filter(ImageFilter.GaussianBlur(2)))     # a thin drop shadow, no band
    draw = ImageDraw.Draw(canvas)
    for y, line, track in rows:
        tracked(draw, y, line, face, P["Text"] + (255,), track, centre=W / 2)
    return canvas


# The page header's wordmark and tag. tools/build_controller_kit_10.py sets these for the
# controller mod's kit and draws its pages with this file's page builders.
HEADER_WORD, HEADER_VERSION, NEW_TAG = "KMRP", "1.6", "NEW IN 1.6"


def header(canvas, subject, new=True):
    draw = ImageDraw.Draw(canvas)
    x, base = 56, 92
    word = shiny_gold(cover.metal_text(HEADER_WORD, 44, DEFAULT_FONT))
    num = cover.metal_text(HEADER_VERSION, 44, DEFAULT_FONT)
    wb, nb = word.getbbox(), num.getbbox()
    gold_pop(canvas, word.crop(wb), (x, base - (wb[3] - wb[1]) + 6), sparkles=False)
    nx = x + (wb[2] - wb[0]) + 26
    blade, (px, py) = saber(num.crop(nb))
    canvas.alpha_composite(blade, (nx - px, base - (nb[3] - nb[1]) + 6 - py))
    end = nx + (nb[2] - nb[0])
    title = font(BOLD, 30)
    tw = tracked(draw, base - 8, subject, title, P["Holo"] + (255,), 6, right=W - 56)
    if new and NEW_TAG:     # the NEW tag: holo, with night letters
        tag = font(BOLD, 20)
        label = NEW_TAG
        lw = draw.textlength(label, font=tag) + 3 * (len(label) - 1)
        rx = W - 56 - tw - 28
        draw.rounded_rectangle([rx - lw - 24, base - 36, rx, base - 4], radius=4, fill=P["Holo"] + (255,))
        tracked(draw, base - 13, label, tag, P["Night"] + (255,), 3, x=rx - lw - 12)
    draw.line([(56, 118), (W - 56, 118)], fill=P["Rule"] + (255,), width=2)
    draw.line([(56, 118), (end + 20, 118)], fill=P["Holo"] + (255,), width=3)


def footer(canvas, line):
    draw = ImageDraw.Draw(canvas)
    if not line:     # a page without a footer line
        return
    face = font(DEFAULT_FONT, 27)
    while draw.textlength(line, font=face) > W - 140 and face.size > 16:
        face = font(DEFAULT_FONT, face.size - 1)
    draw.text((W / 2, H - 40), line, font=face, fill=P["Text"] + (255,), anchor="ms")   # white (the maintainer, 2026-11-13)


SILVER = (198, 206, 218)       # the original game's frames: a plain silver edge, no glow


def frame(canvas, shot, x, y, width, label, kmrp=True):
    """One screenshot, whole, scaled to `width`; KMRP's with a holo edge and glow, the
    original game's with a plain silver edge."""
    height = round(shot.height * width / shot.width)
    small = shot.resize((width, height), Image.LANCZOS)
    edge = P["Holo"] if kmrp else SILVER
    if kmrp:
        halo = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(halo).rectangle([x - 6, y - 6, x + width + 6, y + height + 6], fill=edge + (110,))
        canvas.alpha_composite(halo.filter(ImageFilter.GaussianBlur(18)))
    canvas.paste(small, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([x - 2, y - 2, x + width + 1, y + height + 1], outline=edge + (255,), width=2)
    if label:
        tracked(draw, y + height + 30, label, font(DEFAULT_FONT, 20),
                (P["Bronze"] if kmrp else SILVER) + (255,), 4, x=x)
    return height


def old_shot(name):
    """A frame from the 1.5 kit's sources."""
    path = SHOTS15 / (name + ".png")
    if not path.exists():
        raise SystemExit(f"Not found: {path}")
    return Image.open(path).convert("RGB")


def card_page(subject, silver, gold, facts, line, new=True):
    """An announcement in words: a silver line, a gold line, and its facts."""
    canvas = page_ground()
    header(canvas, subject, new)
    top, cap = 270, 84
    for row, (words, metal) in enumerate(((silver, False), (gold, True))):
        image = cover.metal_text(words, cap, DEFAULT_FONT)
        if metal:
            image = shiny_gold(image)
        image = image.crop(image.getbbox())
        if image.width > 1700:
            image = image.resize((1700, round(image.height * 1700 / image.width)), Image.LANCZOS)
        canvas.alpha_composite(image, ((W - image.width) // 2, top + row * int(cap * 1.55)))
    draw = ImageDraw.Draw(canvas)
    face = font(DEFAULT_FONT, 36)
    widest = max(draw.textlength(f, font=face) for f in facts)
    while widest + 34 > 1640 and face.size > 20:
        face = font(DEFAULT_FONT, face.size - 1)
        widest = max(draw.textlength(f, font=face) for f in facts)
    x = (W - widest - 34) // 2
    y = top + int(cap * 3.75)
    for fact in facts:
        draw.rectangle([x, y - 17, x + 12, y - 5], fill=P["Holo"] + (255,))
        draw.text((x + 34, y), fact, font=face, fill=P["Text"] + (255,), anchor="ls")
        y += 70
    footer(canvas, line)
    return canvas


def card_with_picture(subject, silver, gold, facts, picture, label, line, new=True):
    """A card's words on the left and one 1.6 screenshot on the right."""
    canvas = page_ground()
    header(canvas, subject, new)
    left, limit, cap, top = 80, 740, 62, 250
    for row, (words, metal) in enumerate(((silver, False), (gold, True))):
        image = cover.metal_text(words, cap, DEFAULT_FONT)
        if metal:
            image = shiny_gold(image)
        image = image.crop(image.getbbox())
        if image.width > limit:
            image = image.resize((limit, round(image.height * limit / image.width)), Image.LANCZOS)
        canvas.alpha_composite(image, (left, top + row * int(cap * 1.6)))
    draw = ImageDraw.Draw(canvas)
    face = font(DEFAULT_FONT, 32)
    widest = max(draw.textlength(f, font=face) for f in facts)
    while widest + 34 > limit and face.size > 18:
        face = font(DEFAULT_FONT, face.size - 1)
        widest = max(draw.textlength(f, font=face) for f in facts)
    y = top + int(cap * 4.1)
    for fact in facts:
        draw.rectangle([left, y - 16, left + 12, y - 4], fill=P["Holo"] + (255,))
        draw.text((left + 34, y), fact, font=face, fill=P["Text"] + (255,), anchor="ls")
        y += 62
    width = 940
    height = round(picture.height * width / picture.width)
    frame(canvas, picture, W - 64 - width, 160 + (800 - height) // 2, width, label)
    footer(canvas, line)
    return canvas


def three_page(subject, big, top_right, bottom_right, labels, line, new=True):
    """One large 1.6 screenshot on the left and two smaller ones stacked on the right."""
    canvas = page_ground()
    header(canvas, subject, new)
    top, big_w = 168, 1240
    big_h = frame(canvas, big, 56, top, big_w, labels[0])
    small_w = W - 56 - (56 + big_w + 40)
    small_h = round(1080 * small_w / 1920)
    gap = big_h - 2 * small_h
    frame(canvas, top_right, 56 + big_w + 40, top, small_w, "")
    frame(canvas, bottom_right, 56 + big_w + 40, top + small_h + gap, small_w, "")
    draw = ImageDraw.Draw(canvas)
    lab = font(DEFAULT_FONT, 20)
    tracked(draw, top + small_h + 30, labels[1], lab, P["Bronze"] + (255,), 4, x=56 + big_w + 40)
    tracked(draw, top + big_h + 30, labels[2], lab, P["Bronze"] + (255,), 4, x=56 + big_w + 40)
    footer(canvas, line)
    return canvas


def pair_page(subject, before, after, before_label, after_label, line, new=False):
    """The original game small on the left, KMRP large on the right, each frame whole."""
    canvas = page_ground()
    header(canvas, subject, new)
    a, b = old_shot(before), old_shot(after)
    before_w, after_w = 560, 1196
    before_h = round(a.height * before_w / a.width)
    after_h = round(b.height * after_w / b.width)
    top = 160 + (800 - after_h) // 2
    frame(canvas, a, 56, top + (after_h - before_h) // 2, before_w, "ORIGINAL GAME  " + before_label, kmrp=False)
    frame(canvas, b, W - 56 - after_w, top, after_w, after_label)
    draw = ImageDraw.Draw(canvas)
    mid = top + after_h // 2
    ax = 56 + before_w + (W - 112 - before_w - after_w) // 2
    draw.polygon([(ax - 12, mid - 22), (ax + 14, mid), (ax - 12, mid + 22)], fill=P["Holo"] + (255,))
    footer(canvas, line)
    return canvas


def wide_page(subject, before, after, before_label, after_label, line, new=False):
    """The original game small at the top left, an ultrawide KMRP frame across the page."""
    canvas = page_ground()
    header(canvas, subject, new)
    a, b = old_shot(before), old_shot(after)
    after_w = 1380                       # fits above the footer at 1080 lines
    before_w = 240
    before_h = round(a.height * before_w / a.width)
    x0 = (W - after_w) // 2
    frame(canvas, a, x0, 160, before_w, "", kmrp=False)
    draw = ImageDraw.Draw(canvas)
    big = font(BOLD, 44)
    tx = x0 + before_w + 56
    tracked(draw, 160 + 58, "THE SAME SCREEN,", big, P["Text"] + (255,), 5, x=tx)
    tracked(draw, 160 + 116, "MADE FOR YOUR DISPLAY", big, P["Holo"] + (255,), 5, x=tx)
    note = font(DEFAULT_FONT, 23)
    draw.text((tx, 160 + 160), "Left: the original game at " + before_label + ", all it offers on this monitor.",
              font=note, fill=(200, 208, 220, 255), anchor="ls")
    draw.text((tx, 160 + 192), "Below: KMRP at the monitor's own resolution.", font=note,
              fill=(200, 208, 220, 255), anchor="ls")
    frame(canvas, b, x0, 160 + before_h + 44, after_w, after_label)
    footer(canvas, line)
    return canvas


def solo_old_page(subject, name, label, line, new=False):
    return solo_page(subject, old_shot(name), label, line, new)


def solo_page(subject, picture, label, line, new=True):
    """One frame across the page, whole; a wide one (21:9) is centred in the room a 16:9
    one fills, from 160 down, with its label under it."""
    canvas = page_ground()
    header(canvas, subject, new)
    width = 1420
    height = round(picture.height * width / picture.width)
    top = max(160, 160 + (800 - height - 50) // 2)
    frame(canvas, picture, (W - width) // 2, top, width, label)
    footer(canvas, line)
    return canvas


def shot(key):
    return Image.open(NEW / FILES[key]).convert("RGB")


def page_ground():
    """Pages: the cover's sky without stars, darker, so the frames carry the colour."""
    g = dusk(stars=False, grid=False)
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 120))
    g.alpha_composite(dark)
    return g


def build_pazaak():
    canvas = page_ground()
    header(canvas, "PAZAAK WITH A PAD")
    top = 168
    big_w = 1240
    big_h = frame(canvas, shot("pazaak-table"), 56, top, big_w, "THE TABLE  1920x1080")
    small_w = W - 56 - (56 + big_w + 40)
    small_h = round(1080 * small_w / 1920)
    gap = (big_h - 2 * small_h)
    frame(canvas, shot("pazaak-sidedeck"), 56 + big_w + 40, top, small_w, "")
    frame(canvas, shot("pazaak-wager"), 56 + big_w + 40, top + small_h + gap, small_w, "")
    draw = ImageDraw.Draw(canvas)
    lab = font(DEFAULT_FONT, 20)
    tracked(draw, top + small_h + 30, "SIDE DECK", lab, P["Bronze"] + (255,), 4, x=56 + big_w + 40)
    tracked(draw, top + big_h + 30, "THE WAGER", lab, P["Bronze"] + (255,), 4, x=56 + big_w + 40)
    footer(canvas, "X plays the card you picked, LB flips it, A ends the turn and Y stands, as on the Xbox.")
    return canvas


def build_swoop():
    canvas = page_ground()
    header(canvas, "SWOOP RACING WITH A PAD")
    width = 1420
    frame(canvas, shot("swoop"), (W - width) // 2, 160, width, "KMRP 1.6  1920x1080")
    footer(canvas, "Swoop racing and the gun turret, played with a controller (issue 47).")
    return canvas


def build_palette():
    canvas = page_ground()
    header(canvas, "THE 1.6 PALETTE: NIGHT, HOLO AND BRONZE", new=False)
    draw = ImageDraw.Draw(canvas)
    rows = (("Night", "#060914", "Ground: the sky at the top"),
            ("Deep", "#091628", "Ground: lower down"),
            ("Bloom", "#144062", "The blue glow behind the crest and KOTOR"),
            ("Glow", "#FFBE88", "Light orange: the smoke's upper wisps"),
            ("Ember", "#F4705C", "Light red: the smoke nearest the edge"),
            ("Gold", "#E8BE60", "KMRP: gold on the same metal bevel"),
            ("Saber", "#40CEFF", "1.6: a white core in cyan lightsaber light"),
            ("Bronze", "#CD8C50", "Feature lines and captions"),
            ("BronzeHi", "#E8BA80", "Light bronze: the platforms line"),
            ("Holo", "#40C8EC", "Subjects, frames, tags: the game's UI blue"),
            ("Rule", "#1E546C", "Rules"))
    name_f, hex_f, use_f = font(BOLD, 24), font(DEFAULT_FONT, 21), font(DEFAULT_FONT, 22)
    y = 160
    for name, hx, use in rows:
        draw.rounded_rectangle([96, y - 4, 196, y + 52], radius=7, fill=P[name] + (255,),
                               outline=(255, 255, 255, 60), width=1)
        draw.text((226, y + 18), name, font=name_f, fill=P["Text"] + (255,), anchor="ls")
        draw.text((226, y + 45), hx, font=hex_f, fill=P["Bronze"] + (255,), anchor="ls")
        draw.text((440, y + 32), use, font=use_f, fill=(214, 204, 190, 255), anchor="ls")
        y += 78
    # beside it: the cover, small, to show it in use
    small = build_cover().convert("RGB").resize((800, 450), Image.LANCZOS)
    frame(canvas, small, W - 96 - 800, 300, 800, "THE COVER IN THIS PALETTE")
    footer(canvas, "Kept from 1.5: the silver KOTOR metal and the crest. New: gold KMRP, a lightsaber 1.6, red and orange smoke, bronze words.")
    return canvas



# (file name, builder): the order to show them in.
PAGES = (
    ("01-cover", build_cover),
    ("02-controller-xbox-controls", lambda: card_with_picture(
        "CONTROLLER", "THE ORIGINAL", "XBOX CONTROLS", (
            "LB pauses, RB switches party member",
            "The triggers change target",
            "X queues, Y flourishes, B disengages",
            "Start opens the menus where you left them",
            "Every button can be remapped",
        ), shot("remap"), "CONTROLLER LAYOUT: REMAPPING  1920x1080",
        "PlayStation, Steam Deck and other controllers show their own button icons in the game too.")),
    ("03-controller-layout", lambda: solo_page(
        "CONTROLLER LAYOUT", shot("layout"), "CONTROLLER LAYOUT  3440x1440",
        "Every button of the Xbox layout at a glance, drawn for your pad. Remap changes them.")),
    ("04-pazaak", build_pazaak),
    ("05-swoop-racing", build_swoop),
    ("06-text-hud-icon-size", lambda: three_page(
        "TEXT, HUD AND ICON SIZE", shot("text-size"), shot("hud-keyboard"), shot("hud-controller"),
        ("TEXT SIZE AND FONT  1920x1080", "HUD SIZE: MOUSE & KEYBOARD", "HUD SIZE: CONTROLLER"),
        "Text, font, feat and skill icons, and every part of both HUDs, sized in the game's own options.")),
    ("07-live-adaptive-layout", lambda: card_page(
        "LIVE ADAPTIVE LAYOUT", "EVERY SCREEN", "LAID OUT LIVE", (
            "The game's menus are laid out as it runs, for your screen's shape",
            "Every layout file the game uses, a mod's as well as the game's",
            "A GUI mod keeps its own design and is fitted like the rest",
            "Controller prompts added to any screen, KMRP's or a mod's",
        ), "Menus made for your screen while the game runs.")),
    ("08-inventory-1080p", lambda: pair_page(
        "WIDESCREEN: INVENTORY", "v960-inventory", "k1080-inventory", "1280x960", "KMRP 1.5  1920x1080",
        "Rows, icons and text sized for the screen. Nothing cut off.")),
    ("09-inventory-ultrawide", lambda: wide_page(
        "INVENTORY, ULTRAWIDE", "v1200-inventory", "k1440-inventory", "1600x1200", "KMRP 1.5  3440x1440",
        "21:9 has its own layout: not stretched, not letterboxed.")),
    ("10-4k", lambda: solo_old_page(
        "4K", "k2160-game", "KMRP 1.5  3840x2160",
        "On a 4K television the display and its text are made for 3840x2160.")),
    ("11-installing", lambda: card_page(
        "INSTALLING", "ONE INSTALLER,", "READY AT ONCE", (
            "The Windows installer: 57 MiB, down from 140 MiB in 1.5.1",
            "Every resolution made before the game first starts",
            "Starts and resolution changes in about a second and a half",
            "KMRP's own files in one KMRP folder",
            "Restore Original undoes every change",
        ), "", new=False)),
    ("12-platforms", lambda: card_page(
        "PLATFORMS", "WINDOWS, LINUX", "AND macOS", (
            "Windows: one installer for the Steam and GOG games",
            "Linux: a native installer, an AppImage, for the game under Proton",
            "macOS: its own installer for Aspyr's Mac game",
        ), "", new=False)),
)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in PAGES:
        if only and not name.startswith(only):
            continue
        img = fn().convert("RGB")
        assert img.size == (W, H), img.size
        path = OUT / f"{name}.png"
        img.save(path)
        print(path, img.size)


if __name__ == "__main__":
    main()
