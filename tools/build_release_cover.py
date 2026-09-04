#!/usr/bin/env python3
"""Compose the release cover art from the patcher's own assets.

**Nothing here is drawn fresh.** Every element comes from something the project
already ships, which is the point: a cover generated from scratch would look like
the patcher's sibling rather than the patcher.

| element | source |
| --- | --- |
| crest + `KOTOR` lockup | `src/patcher/brand.png`, the artwork the patcher's own header draws |
| `KMRP` wordmark | rendered here, through `build_brand_image`'s measured metal ramps and tracking |
| every colour of the ground | `UiTheme` in `src/patcher/KmrpPatcher.cs` |

**The metal.** `build_brand_image.py` measured the reference lockup's bevel and
recorded it as constants: `FACE` and `RIM` are per-height colour ramps sampled off
the artwork, `EDGE_LUM`/`PLATEAU_LUM` the luminances they are levelled to, and
`BEVEL_TAU_RATIO` the decay length of the lit edge. Those constants are imported
rather than copied, so the `KMRP` wordmark is shaded by the same measurements as
`KOTOR` and the two cannot drift apart.

The shading *loop* is reproduced here rather than shared, because in
`build_brand_image` it is inlined in `build()` alongside the crest compositing
that this tool does not want. Extracting it would mean editing the script that
produces shipped artwork, and that script cannot currently be run to check the
output is unchanged -- the crest source is not committed and `python-docx`-style
missing inputs make a before/after comparison impossible. Duplicating ~30 lines is
the smaller risk. **If `build_brand_image` is ever made runnable again, merge the
two.**

**Colours are read out of the C# at run time**, not transcribed, so a change to
`UiTheme` reaches the cover without anyone remembering to update this file.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import math
import random
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from build_brand_image import (
    BEVEL_TAU_RATIO,
    EDGE_LUM,
    FACE,
    OUTLINE,
    OUTLINE_RATIO,
    PLATEAU_LUM,
    RIM,
    SIDE_LIGHT,
    TRACKING_RATIO,
    DEFAULT_FONT,
    ramp,
    solve_size,
    draw_wordmark,
)

SUPERSAMPLE = 3
THEME_SOURCE = Path("src/patcher/KmrpPatcher.cs")
LOCKUP = Path("src/patcher/brand.png")

# Fallbacks only. read_theme() replaces these from the C# when it can.
THEME = {
    "Window": (7, 12, 21),
    "Card": (13, 21, 34),
    "Border": (34, 103, 132),
    "Accent": (42, 198, 239),
    "Text": (236, 243, 248),
    "TextMuted": (177, 195, 208),
}


def read_theme(source: Path) -> dict:
    """Pull UiTheme's colours out of the C# so the cover cannot drift from the app."""
    theme = dict(THEME)
    try:
        text = source.read_text(encoding="utf-8", errors="replace")
    except OSError:
        print(f"  ! {source} unreadable; using fallback palette")
        return theme
    pattern = re.compile(
        r"Color\s+(\w+)\s*=\s*Color\.FromArgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
    found = {m.group(1): (int(m.group(2)), int(m.group(3)), int(m.group(4)))
             for m in pattern.finditer(text)}
    for name in theme:
        if name in found:
            theme[name] = found[name]
    missing = [n for n in theme if n not in found]
    if missing:
        print(f"  ! not found in {source.name}, kept fallback: {', '.join(missing)}")
    return theme


def metal_text(text: str, cap: int, font_path: Path) -> Image.Image:
    """`text` in the lockup's typeface and bevel. See the module docstring."""
    cap_ss = cap * SUPERSAMPLE
    size_px = solve_size(font_path, cap_ss)

    probe, span = draw_wordmark((cap_ss * 14, cap_ss * 6), size_px, cap_ss,
                                cap_ss * 4, font_path, text)
    width = int(span + cap_ss * 1.2)
    height = int(cap_ss * 2.4)
    baseline_y = int(height - cap_ss * 0.7)
    letters, _ = draw_wordmark((width, height), size_px, cap_ss, baseline_y,
                               font_path, text)
    box = letters.getbbox()
    cap_top, baseline = box[1], box[3]
    glyph_h = baseline - cap_top

    alpha = np.asarray(letters).astype(np.float32) / 255.0
    solid = alpha > 0.5

    # Distance below each stroke's top edge, and right of its left edge: the bevel
    # is lit from above and from the left.
    depth = np.zeros(alpha.shape, dtype=np.float32)
    run = np.zeros(alpha.shape[1], dtype=np.float32)
    for y in range(alpha.shape[0]):
        run = np.where(solid[y], run + 1.0, 0.0)
        depth[y] = np.maximum(run - 1.0, 0.0)
    side = np.zeros(alpha.shape, dtype=np.float32)
    run = np.zeros(alpha.shape[0], dtype=np.float32)
    for x in range(alpha.shape[1]):
        run = np.where(solid[:, x], run + 1.0, 0.0)
        side[:, x] = np.maximum(run - 1.0, 0.0)

    tau = max(1.0, BEVEL_TAU_RATIO * cap_ss)
    lit = np.maximum(np.exp(-depth / tau), SIDE_LIGHT * np.exp(-side / tau))[..., None]

    def levelled(stops, target_lum):
        arr = np.asarray(ramp(alpha.shape[0], stops), dtype=np.float32).reshape(-1, 3)
        return (arr * (target_lum / max(1e-6, arr.max(axis=1).mean()))).reshape(-1, 1, 3)

    t = np.clip((np.arange(alpha.shape[0]) - cap_top) / max(1, glyph_h), 0.0, 1.0)
    idx = np.clip((t * (alpha.shape[0] - 1)).astype(int), 0, alpha.shape[0] - 1)
    shaded = levelled(FACE, PLATEAU_LUM)[idx] * (1.0 - lit) \
        + levelled(RIM, EDGE_LUM)[idx] * lit

    face = Image.fromarray(np.clip(shaded, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    face.putalpha(letters)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    grow = letters.filter(ImageFilter.MaxFilter(2 * max(1, int(cap_ss * OUTLINE_RATIO)) + 1))
    edge = Image.new("RGBA", canvas.size, OUTLINE + (255,))
    edge.putalpha(grow)
    drop = letters.filter(ImageFilter.GaussianBlur(cap_ss * 0.035))
    shadow = Image.new("RGBA", canvas.size, OUTLINE + (0,))
    shadow.putalpha(drop.point(lambda v: int(v * 0.7)))
    canvas.alpha_composite(shadow, (0, int(cap_ss * 0.025)))
    canvas.alpha_composite(edge)
    canvas.alpha_composite(face)

    canvas = canvas.resize((width // SUPERSAMPLE, height // SUPERSAMPLE), Image.LANCZOS)
    return canvas.crop(canvas.getbbox())


def ground(size, theme: dict, seed: int = 20260904) -> Image.Image:
    """The patcher's dark shell, lifted toward the centre, with a quiet starfield.

    The app itself is a flat panel; a cover needs depth, so the lift and the stars
    are this tool's additions. Both are built from UiTheme colours rather than new
    ones, and the starfield is seeded so the cover is reproducible.
    """
    width, height = size
    window = np.array(theme["Window"], dtype=np.float32)
    card = np.array(theme["Card"], dtype=np.float32)
    accent = np.array(theme["Accent"], dtype=np.float32)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cx, cy = width / 2.0, height * 0.42
    r = np.sqrt(((xx - cx) / (width * 0.62)) ** 2 + ((yy - cy) / (height * 0.72)) ** 2)
    lift = np.clip(1.0 - r, 0.0, 1.0)[..., None] ** 1.7

    base = window + (card - window) * lift
    # Accent bloom behind where the crest lands, at the strength the app uses for
    # its own focus glow rather than an arbitrary one.
    glow = np.clip(1.0 - np.sqrt(((xx - cx) / (width * 0.30)) ** 2
                                 + ((yy - cy) / (height * 0.42)) ** 2), 0.0, 1.0)[..., None] ** 2.4
    base = base + (accent - base) * glow * 0.16

    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    stars = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(stars)
    rng = random.Random(seed)
    tint = theme["Text"]
    for _ in range(int(width * height / 5200)):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        # Thin them out where the artwork sits, so nothing reads through the type.
        if math.hypot((x - cx) / (width * 0.26), (y - cy) / (height * 0.34)) < 1.0 \
                and rng.random() < 0.82:
            continue
        a = rng.randint(20, 130)
        rad = 0.6 if rng.random() < 0.86 else 1.15
        sd.ellipse([x - rad, y - rad, x + rad, y + rad], fill=tint + (a,))
    img.alpha_composite(stars)

    # Vignette, so the edges hold the type in.
    vg = np.clip((r - 0.75) / 0.85, 0.0, 1.0)[..., None] ** 1.5
    arr = np.asarray(img).astype(np.float32)
    arr[..., :3] *= (1.0 - vg * 0.55)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def tracked(draw, xy, text, font, fill, tracking, anchor_centre_x=None):
    """Letter-spaced text. PIL has no tracking, so glyphs are placed one at a time."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (anchor_centre_x - total / 2) if anchor_centre_x is not None else xy[0]
    for ch, w in zip(text, widths):
        draw.text((x, xy[1]), ch, font=font, fill=fill, anchor="ls")
        x += w + tracking
    return total


def build(out: Path, size, font_path: Path, root: Path) -> None:
    theme = read_theme(root / THEME_SOURCE)
    width, height = size
    canvas = ground(size, theme)

    lockup_path = root / LOCKUP
    if not lockup_path.exists():
        raise SystemExit(f"Not found: {lockup_path} -- the patcher's own lockup is the "
                         "one thing this cannot substitute for")
    lockup = Image.open(lockup_path).convert("RGBA")
    lockup = lockup.crop(lockup.getbbox())

    # The lockup is the hero: give it 62% of the width, and let everything else
    # follow from its cap height so the composition scales with the canvas.
    target_w = int(width * 0.62)
    lockup = lockup.resize((target_w, int(lockup.height * target_w / lockup.width)),
                           Image.LANCZOS)
    lockup_y = int(height * 0.085)
    canvas.alpha_composite(lockup, ((width - lockup.width) // 2, lockup_y))

    cursor = lockup_y + lockup.height

    # KMRP, in the lockup's own metal, at a third of KOTOR's presence.
    kmrp = metal_text("KMRP", max(18, int(height * 0.088)), font_path)
    kmrp_y = cursor + int(height * 0.012)
    canvas.alpha_composite(kmrp, ((width - kmrp.width) // 2, kmrp_y))

    draw = ImageDraw.Draw(canvas)

    # Flanking rules at the KMRP mid-line, in the app's border colour.
    mid = kmrp_y + kmrp.height // 2
    gap = kmrp.width // 2 + int(width * 0.055)
    rule = int(width * 0.085)
    for direction in (-1, 1):
        x0 = width // 2 + direction * gap
        x1 = x0 + direction * rule
        draw.line([(min(x0, x1), mid), (max(x0, x1), mid)],
                  fill=theme["Border"] + (215,), width=max(1, height // 540))

    sub_size = max(11, int(height * 0.033))
    try:
        sub_font = ImageFont.truetype(str(font_path), sub_size)
    except OSError:
        sub_font = ImageFont.load_default()
    sub_y = kmrp_y + kmrp.height + int(height * 0.072)
    tracked(draw, (0, sub_y), "MODERN RESTORATION PATCH", sub_font,
            theme["Accent"] + (255,), sub_size * 0.42, anchor_centre_x=width / 2)

    foot_size = max(9, int(height * 0.019))
    try:
        foot_font = ImageFont.truetype(str(font_path), foot_size)
    except OSError:
        foot_font = ImageFont.load_default()
    foot_y = sub_y + int(height * 0.052)
    tracked(draw, (0, foot_y), "48 RESOLUTIONS   4:3 TO 32:9", foot_font,
            theme["TextMuted"] + (190,), foot_size * 0.34, anchor_centre_x=width / 2)

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=95)
    print(f"  {out}  {width}x{height}  {out.stat().st_size} bytes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("assets/branding/release-cover.png"))
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    if not args.font.exists():
        raise SystemExit(f"Not found: {args.font}")
    build(args.out, (args.width, args.height), args.font, args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
