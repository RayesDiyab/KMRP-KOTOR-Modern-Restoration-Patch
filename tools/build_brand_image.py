#!/usr/bin/env python3
"""Render the KMRP header lockup, matched numerically to `assets/branding/logo.png`.

Every constant below was measured off the reference rather than chosen by eye.
The reference is 513x226; the wordmark occupies x 87..446, cap top y=117,
baseline y=174, so **cap height = 58px** and the five glyphs span 360px.

**Typeface.** Each glyph was cut out of the reference, and every serif installed
on the machine was rendered, normalised to that glyph's box, and scored by pixel
IoU plus aspect and stroke-weight error:

    Sitka       IoU 0.633   score 0.589
    Georgia     IoU 0.620   score 0.582      <- chosen
    Constantia  IoU 0.606   score 0.571
    Bookman     IoU 0.607   score 0.571
    Cinzel Black IoU 0.545  score 0.444      <- what this file used before

Georgia at cap 58 needs 83px em and 17.2px of tracking to reproduce the
reference's 360px span, i.e. **tracking = 0.297 x cap height**.

**Metal.** Sampled two ways, and the disagreement is the point. The stroke
interior (mask eroded twice, so no edge pixels) is cool and mid-toned, running
137 -> 103 -> 168 -> 95 in luminance. The brightest twelfth of each band reaches
236 at the top and 198-205 lower down. That is a bevel: a bright rim over a
darker face, not a bright face. FACE below is the measured interior; the rim is
applied separately.

Note the hue: cool blue-grey throughout the face, and the reference's highlights
turn faintly warm (198,181,159) across the lower middle, which is why a purely
cool ramp read as flat.

**Crest.** Above the cap line it spans 142px = **2.45 x cap height** wide, is
centred on the wordmark to within 5px, and runs off the top of the reference
frame. Approaching the letters it dims from mean blue 156 at y=96 to 99 at
y=114 while its pixel count falls 129 -> 70: it fades out into the letters over
about 0.35 cap rather than ending. Drawn before the wordmark, so it passes
behind it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# The crest artwork this composes is **not committed** -- only the rendered
# result, `src/patcher/brand.png`, ships. So `--crest` is required and has no
# default: it used to carry one author's Downloads folder, which worked on
# exactly one machine and silently pointed everyone else at a file that does not
# exist.
#
# Georgia is the measured typeface (see the header), not a preference, so it is
# the default. `--font` exists because that path is Windows-specific and nothing
# else in this tool is.
DEFAULT_FONT = Path(r"C:\Windows\Fonts\georgia.ttf")

CAP = 150                     # cap height of the rendered wordmark, in output pixels
TRACKING_RATIO = 0.297        # measured: 17.2px tracking at 58px cap
CREST_WIDTH_RATIO = 3.43      # 2.45 is the measured reference width (142px at 58px cap);
                              # 3.43 is that +40%. Height follows, since the aspect is fixed,
                              # and the crest grows upward because it is anchored by its wing
                              # line rather than its bounding box.
# Measured: the crest's wings fade out just above the cap line (-0.03 cap), while
# the saber runs on down THROUGH the letters to the baseline (+0.98 cap), showing
# 6-14 bright pixels per row in the gaps between glyphs. So the artwork's bottom
# sits on the baseline and the veil dims it as it passes behind the text.
WING_BOTTOM_AT = 0.50         # where the wings' lower tips land, in caps below the cap line.
                              # 0.00 puts them exactly on it, which is where the reference has
                              # them. The crest is 2.45 caps tall, so each 0.245 here moves it
                              # 10% of its own height; 0.50 sits it 10% lower than the 0.25 that
                              # first dipped the tips behind the letters (15%, at 0.62, was too
                              # much). The fade is anchored to this line, so it travels with it.
# The fade must END at the crest's own bottom edge, or the artwork runs out while
# the veil is still part-way and there is no visible fade at all. That was the bug:
# FADE_TO sat 1.00 cap below the wing line, but the crest only reaches 0.36 cap
# below it, so the veil never got past 57% and the crest simply stopped, at full
# brightness, behind the letters.
#
# So the fade is anchored to the crest bottom and only its LENGTH is a parameter.
# Measured on the reference for shape: the wings hold ~0.85 of peak down to
# -0.24 cap, fall to 0.53 by the cap line, and are gone just below.
FADE_START_ABOVE_WING = 1.32  # caps above the wing line where dimming begins. It has to start
                              # well above: the wings end at 85% of the crest's height, so a fade
                              # that only begins at the wing line covers just the hilt and leaves
                              # the wings at full brightness -- which is why earlier attempts read
                              # as no fade at all.
SUPERSAMPLE = 3

BEVEL_TAU_RATIO = 0.048       # bevel decay length / cap height, fitted to the reference's
                              # luminance-vs-depth profile (163 at depth 1 -> 118 by depth 10)
OUTLINE_RATIO = 0.008         # outline half-width / cap height (one pixel at cap 58)
EDGE_LUM = 195.0              # fitted, not the raw 163 measured at depth 1: that sample is
                              # diluted by antialiasing, so the underlying edge is brighter
PLATEAU_LUM = 118.0           # measured interior level at depth 10+
SIDE_LIGHT = 0.75             # left-edge lighting relative to the top edge; swept against the
                              # reference (mean luminance 130.6 vs 132.1, lit edge 160.3 vs 163.1)

# Stroke interior, sampled per height band as the mean of pixels above that band's
# 70th luminance percentile -- i.e. the lit face of the stroke, with the dark
# outline and the antialiased edge excluded. An earlier attempt eroded the mask
# twice instead and came out far too dark: on 6-9px strokes the erosion keeps
# exactly the pixels the outline bleeds into. Measured against the reference, that
# version put 5.2% of glyph pixels above luminance 180 where the reference has
# 27.7%; this one gives 29.5%, and mean luminance 132.6 against 132.1.
FACE = [
    (0.000, (226, 235, 248)),
    (0.031, (222, 231, 244)),
    (0.094, (163, 187, 221)),
    (0.156, (166, 189, 218)),
    (0.219, (156, 179, 209)),
    (0.281, (148, 170, 197)),
    (0.344, (148, 169, 195)),
    (0.406, (157, 175, 193)),
    (0.469, (166, 175, 183)),
    (0.531, (159, 165, 175)),
    (0.594, (144, 149, 158)),
    (0.656, (146, 148, 152)),
    (0.719, (145, 146, 150)),
    (0.781, (145, 148, 151)),
    (0.844, (151, 151, 154)),
    (0.906, (150, 150, 152)),
    (0.969, (160, 162, 165)),
    (1.000, (162, 164, 167)),
]

# Brightest twelfth of each band -- the bevel rim. Cool at the top, faintly warm
# through the lower middle, which is what makes it read as metal and not plastic.
RIM = [
    (0.00, (236, 242, 249)),
    (0.19, (188, 207, 230)),
    (0.31, (174, 190, 208)),
    (0.44, (198, 202, 201)),
    (0.56, (196, 184, 170)),
    (0.69, (198, 181, 159)),
    (0.81, (202, 193, 182)),
    (1.00, (205, 203, 201)),
]

OUTLINE = (7, 26, 52)         # measured shadow floor around the glyphs


def ramp(height: int, stops) -> Image.Image:
    strip = Image.new("RGB", (1, height))
    px = strip.load()
    for y in range(height):
        t = y / max(1, height - 1)
        lo, hi = stops[0], stops[-1]
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                lo, hi = stops[i], stops[i + 1]
                break
        k = (t - lo[0]) / max(1e-6, hi[0] - lo[0])
        px[0, y] = tuple(int(round(lo[1][c] + (hi[1][c] - lo[1][c]) * k)) for c in range(3))
    return strip


def solve_size(path: Path, cap: int) -> int:
    """Point size whose cap height is exactly `cap`, found by bisection."""
    lo, hi = 4.0, cap * 6.0
    for _ in range(50):
        mid = (lo + hi) / 2
        font = ImageFont.truetype(str(path), max(1, int(round(mid))))
        probe = Image.new("L", (cap * 8, cap * 8), 0)
        ImageDraw.Draw(probe).text((cap, cap), "K", font=font, fill=255)
        box = probe.getbbox()
        if box is None or (box[3] - box[1]) < cap:
            lo = mid
        else:
            hi = mid
    return max(1, int(round((lo + hi) / 2)))


def draw_wordmark(canvas_size, size_px: int, cap: int, baseline_y: int,
                  font_path: Path, text: str = "KOTOR"):
    """Glyph mask drawn straight onto a full-size canvas, sitting on `baseline_y`."""
    font = ImageFont.truetype(str(font_path), size_px)
    measure = ImageDraw.Draw(Image.new("L", (8, 8)))
    widths = [measure.textlength(ch, font=font) for ch in text]
    tracking = TRACKING_RATIO * cap
    total = sum(widths) + tracking * (len(text) - 1)
    mask = Image.new("L", canvas_size, 0)
    draw = ImageDraw.Draw(mask)
    x = (canvas_size[0] - total) / 2
    for ch, w in zip(text, widths):
        draw.text((x, baseline_y), ch, font=font, fill=255, anchor="ls")
        x += w + tracking
    return mask, total


def build(crest_path: Path, out: Path, font_path: Path) -> None:
    cap = CAP * SUPERSAMPLE
    size_px = solve_size(font_path, cap)

    # Lay the canvas out from the measurements: the crest is 2.45 caps wide and
    # reaches ~1.9 caps above the cap line before it is cut off in the reference,
    # so give it that much room and let the fade do the rest.
    probe, span = draw_wordmark((cap * 12, cap * 6), size_px, cap, cap * 4, font_path)
    width = int(span + cap * 1.6)
    height = int(cap * 4.2)
    baseline_y = int(height - cap * 0.9)

    letters, _ = draw_wordmark((width, height), size_px, cap, baseline_y, font_path)
    lbox = letters.getbbox()
    cap_top, baseline = lbox[1], lbox[3]
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # --- crest, behind the letters ---------------------------------------
    crest = Image.open(crest_path).convert("RGBA")
    px = crest.load()
    for y in range(crest.height):
        for x in range(crest.width):
            r, g, b, _ = px[x, y]
            px[x, y] = (r, g, b, max(r, g, b))
    crest = crest.crop(crest.getbbox())
    crest_w = int(CREST_WIDTH_RATIO * cap)
    crest_h = int(crest.height * crest_w / crest.width)
    crest = crest.resize((crest_w, crest_h), Image.LANCZOS)

    # Anchor by the artwork's own anatomy: find where the wings stop and only the
    # hilt continues, and land that on the cap line, which is where the reference
    # puts it. Everything below is the hilt passing behind the letters.
    ink = np.asarray(crest.split()[3]) > 55
    widths = np.array([np.count_nonzero(r) and (np.nonzero(r)[0].max() - np.nonzero(r)[0].min() + 1) or 0
                       for r in ink])
    wide = np.nonzero(widths > 0.55 * widths.max())[0]
    wing_bottom = (wide.max() + 1) / crest_h if wide.size else 0.85

    crest_top = int(cap_top + WING_BOTTOM_AT * cap - wing_bottom * crest_h)
    wing_line = cap_top + WING_BOTTOM_AT * cap
    fade_to = crest_top + crest_h          # the crest's own bottom: the fade must finish here
    fade_from = wing_line - FADE_START_ABOVE_WING * cap
    top_soft = int(cap * 0.7)

    veil = Image.new("L", crest.size, 0)
    vd = veil.load()
    for y in range(crest_h):
        gy = crest_top + y
        if gy <= fade_from:
            v = 255.0
        elif gy >= fade_to:
            v = 0.0
        else:
            k = (gy - fade_from) / max(1e-6, fade_to - fade_from)
            v = 255.0 * (1.0 - (k * k * (3.0 - 2.0 * k)))     # smoothstep, so it eases out
        if gy < top_soft:
            v *= max(0.0, gy / max(1, top_soft))
        for x in range(crest_w):
            vd[x, y] = int(v)
    veil = veil.filter(ImageFilter.GaussianBlur(cap * 0.05))
    crest = Image.composite(crest, Image.new("RGBA", crest.size, (0, 0, 0, 0)), veil)

    paste_y = crest_top
    if paste_y < 0:                                        # crest runs off the top: keep the part we have
        crest = crest.crop((0, -paste_y, crest_w, crest_h))
        paste_y = 0
    canvas.alpha_composite(crest, ((width - crest_w) // 2, paste_y))

    # --- the wordmark ------------------------------------------------------
    glyph_h = baseline - cap_top

    # --- shading: a bevel measured off the reference ----------------------
    # For every glyph pixel the reference's luminance depends on how far it sits
    # below its own stroke's top edge, not on absolute height:
    #     depth 0  102 (outline/antialias)   depth 1  163   depth 3  134
    #     depth 6  122                       depth 10+ ~118
    # So: a bright lit edge decaying to a plateau. Fitting 165 -> 118 through
    # depth 3 = 134 gives tau = 2.8px at cap 58, i.e. 0.048 x cap.
    alpha = np.asarray(letters).astype(np.float32) / 255.0
    solid = alpha > 0.5
    depth = np.zeros(alpha.shape, dtype=np.float32)
    run = np.zeros(alpha.shape[1], dtype=np.float32)
    for y in range(alpha.shape[0]):
        row = solid[y]
        run = np.where(row, run + 1.0, 0.0)
        depth[y] = np.maximum(run - 1.0, 0.0)

    # A bevel is lit from above AND from the left -- the reference's overall mean
    # luminance (132.1) sits well above its depth plateau (118), which only works
    # if the vertical edges are lit too. Weighted below the top edge.
    side = np.zeros(alpha.shape, dtype=np.float32)
    run = np.zeros(alpha.shape[0], dtype=np.float32)
    for x in range(alpha.shape[1]):
        col = solid[:, x]
        run = np.where(col, run + 1.0, 0.0)
        side[:, x] = np.maximum(run - 1.0, 0.0)

    tau = max(1.0, BEVEL_TAU_RATIO * cap)
    lit = np.maximum(np.exp(-depth / tau), SIDE_LIGHT * np.exp(-side / tau))[..., None]

    t = np.clip((np.arange(alpha.shape[0]) - cap_top) / max(1, glyph_h), 0.0, 1.0)
    def levelled(stops, target_lum):
        arr = np.asarray(ramp(alpha.shape[0], stops), dtype=np.float32).reshape(-1, 3)
        mean = arr.max(axis=1).mean()
        return (arr * (target_lum / max(1e-6, mean))).reshape(-1, 1, 3)

    plate_col = levelled(FACE, PLATEAU_LUM)
    edge_col = levelled(RIM, EDGE_LUM)
    # `ramp` spans the glyph, so index it by the same normalised height.
    idx = np.clip((t * (alpha.shape[0] - 1)).astype(int), 0, alpha.shape[0] - 1)
    plate_col = plate_col[idx]
    edge_col = edge_col[idx]

    shaded = plate_col * (1.0 - lit) + edge_col * lit
    rgb = np.clip(shaded, 0, 255).astype(np.uint8)
    face_img = Image.fromarray(rgb, "RGB").convert("RGBA")
    face_img.putalpha(letters)

    # A hairline outline only -- the reference's is one pixel at cap 58.
    grow = letters.filter(ImageFilter.MaxFilter(2 * max(1, int(cap * OUTLINE_RATIO)) + 1))
    edge = Image.new("RGBA", canvas.size, OUTLINE + (255,))
    edge.putalpha(grow)

    drop = letters.filter(ImageFilter.GaussianBlur(cap * 0.035))
    shadow = Image.new("RGBA", canvas.size, OUTLINE + (0,))
    shadow.putalpha(drop.point(lambda v: int(v * 0.7)))
    canvas.alpha_composite(shadow, (0, int(cap * 0.025)))
    canvas.alpha_composite(edge)
    canvas.alpha_composite(face_img)

    canvas = canvas.resize((width // SUPERSAMPLE, height // SUPERSAMPLE), Image.LANCZOS)
    box = canvas.getbbox()
    pad = 10
    canvas = canvas.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                          min(canvas.width, box[2] + pad), min(canvas.height, box[3] + pad)))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    print(f"{out}  {canvas.size[0]}x{canvas.size[1]}  em {size_px // SUPERSAMPLE}px  cap {CAP}px  {out.stat().st_size} bytes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crest", type=Path, required=True,
                        help="the crest artwork; not committed, see the note in this file")
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--out", type=Path, default=Path("src/patcher/brand.png"))
    args = parser.parse_args()
    for path in (args.crest, args.font):
        if not path.exists():
            raise SystemExit(f"Not found: {path}")
    build(args.crest, args.out, args.font)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
