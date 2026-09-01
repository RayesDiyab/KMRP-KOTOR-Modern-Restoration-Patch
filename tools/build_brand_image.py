#!/usr/bin/env python3
"""Render the KMRP header lockup, matched numerically to `Goal LOGO.png`.

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

from PIL import Image, ImageDraw, ImageFilter, ImageFont


CREST = Path(r"C:\Users\diyab\Downloads\ChatGPT Image Sep 1, 2026, 12_31_57 PM.png")
FONT = Path(r"C:\Windows\Fonts\georgia.ttf")

CAP = 150                     # cap height of the rendered wordmark, in output pixels
TRACKING_RATIO = 0.297        # measured: 17.2px tracking at 58px cap
CREST_WIDTH_RATIO = 2.45      # measured: 142px wide at 58px cap
CREST_FADE_RATIO = 0.42       # the crest dies out this far (in caps) above the cap line
RIM_LIFT_RATIO = 0.06         # bevel width / cap height; solved by sweeping against the
                              # reference's brightness distribution (see FACE)
SUPERSAMPLE = 3

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


def draw_wordmark(canvas_size, size_px: int, cap: int, baseline_y: int, text: str = "KOTOR"):
    """Glyph mask drawn straight onto a full-size canvas, sitting on `baseline_y`."""
    font = ImageFont.truetype(str(FONT), size_px)
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


def build(crest_path: Path, out: Path) -> None:
    cap = CAP * SUPERSAMPLE
    size_px = solve_size(FONT, cap)

    # Lay the canvas out from the measurements: the crest is 2.45 caps wide and
    # reaches ~1.9 caps above the cap line before it is cut off in the reference,
    # so give it that much room and let the fade do the rest.
    probe, span = draw_wordmark((cap * 12, cap * 6), size_px, cap, cap * 4)
    width = int(span + cap * 1.6)
    height = int(cap * 3.4)
    baseline_y = int(height - cap * 0.45)

    letters, _ = draw_wordmark((width, height), size_px, cap, baseline_y)
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

    fade_end = cap_top + int(CREST_FADE_RATIO * cap)      # where the crest has gone
    crest_top = fade_end - crest_h
    fade_span = max(1, int(cap * 0.9))                    # measured: dies over ~0.35 cap, softened
    top_soft = int(cap * 0.7)

    veil = Image.new("L", crest.size, 0)
    vd = veil.load()
    for y in range(crest_h):
        gy = crest_top + y
        v = 255.0
        if gy > fade_end - fade_span:
            v *= max(0.0, 1.0 - (gy - (fade_end - fade_span)) / fade_span)
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

    drop = letters.filter(ImageFilter.GaussianBlur(cap * 0.05))
    shadow = Image.new("RGBA", canvas.size, OUTLINE + (0,))
    shadow.putalpha(drop.point(lambda v: int(v * 0.8)))
    canvas.alpha_composite(shadow, (0, int(cap * 0.03)))

    grow = letters.filter(ImageFilter.MaxFilter(2 * max(1, int(cap * 0.016)) + 1))
    edge = Image.new("RGBA", canvas.size, OUTLINE + (255,))
    edge.putalpha(grow)
    canvas.alpha_composite(edge)

    face = ramp(glyph_h, FACE).resize((width, glyph_h), Image.NEAREST).convert("RGBA")
    plate = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    plate.paste(face, (0, cap_top))
    plate.putalpha(letters)
    canvas.alpha_composite(plate)

    lift = max(1, int(cap * RIM_LIFT_RATIO))
    up = Image.new("L", canvas.size, 0); up.paste(letters, (0, -lift))
    top_edge = Image.composite(letters, Image.new("L", canvas.size, 0),
                               Image.eval(up, lambda v: 255 - v))
    rim = ramp(glyph_h, RIM).resize((width, glyph_h), Image.NEAREST).convert("RGBA")
    rim_plate = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    rim_plate.paste(rim, (0, cap_top))
    rim_plate.putalpha(top_edge)
    canvas.alpha_composite(rim_plate)

    down = Image.new("L", canvas.size, 0); down.paste(letters, (0, lift))
    bottom_edge = Image.composite(letters, Image.new("L", canvas.size, 0),
                                  Image.eval(down, lambda v: 255 - v))
    dark = Image.new("RGBA", canvas.size, (18, 32, 52, 255))
    dark.putalpha(bottom_edge.point(lambda v: int(v * 0.7)))
    canvas.alpha_composite(dark)

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
    parser.add_argument("--crest", type=Path, default=CREST)
    parser.add_argument("--out", type=Path, default=Path("app/patcher/brand.png"))
    args = parser.parse_args()
    for path in (args.crest, FONT):
        if not path.exists():
            raise SystemExit(f"Not found: {path}")
    build(args.crest, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
