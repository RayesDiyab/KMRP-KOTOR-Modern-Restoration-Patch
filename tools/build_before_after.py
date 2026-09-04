#!/usr/bin/env python3
"""Compose one before/after comparison image from two screenshots.

Built for the mod pages: a reader who has only ever seen KOTOR at 1080p cannot
tell what KMRP changed from a single frame, so every screenshot that sells this
project is a pair.

**The split is a tilted line through the centre, not a corner-to-corner
diagonal.** On a 16:9 frame a true corner diagonal is so shallow that the two
halves stop reading as left and right, and the labels end up stranded in thin
slivers. A line through the centre leaning ~18 degrees off vertical keeps both
halves rectangular enough to read while still looking like a slash rather than a
sober vertical wipe. `--tilt 0` gives the straight split; `--direction backslash`
leans it the other way.

**Both images are cropped identically.** The whole claim of a before/after is
that only one variable changed, so the tool takes a single `--crop` and applies
it to both, and refuses to proceed if the two images are different sizes without
one. Two frames cropped to different regions is the classic way to make an honest
comparison look dishonest.

**Colours come from `UiTheme`** in `src/patcher/KmrpPatcher.cs`, read at run time
via `build_release_cover.read_theme`, so the comparison plates match the patcher
and the release cover rather than approximating them.

Usage:

    python tools/build_before_after.py --before vanilla.png --after kmrp.png \\
        --out docs/shots/inventory.png --caption "Inventory - 3440x1440"

`--demo` renders the template with obviously synthetic panels, for checking the
treatment before real screenshots exist.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from build_brand_image import DEFAULT_FONT
from build_release_cover import read_theme, tracked, THEME_SOURCE

SEAM_CORE = 3          # px, at 1920 wide; scaled with the image
SEAM_GLOW = 26
LABEL_CAP_RATIO = 0.048   # label cap height / image height
DEFAULT_TILT = 18.0

# BEFORE/AFTER are set in Georgia Bold, not the regular weight the rest of the
# project uses. They sit on top of a screenshot rather than on a flat ground, so
# they have to hold their own against whatever is behind them; the regular weight
# read as a caption instead of a label. Same family as the wordmark, so it is a
# weight change and not a second typeface. Falls back to --font if the bold face
# is not installed.
LABEL_FONT = Path(r"C:\Windows\Fonts\georgiab.ttf")


def parse_crop(spec: str):
    parts = [int(v.strip()) for v in spec.split(",")]
    if len(parts) != 4:
        raise SystemExit("--crop wants x,y,width,height")
    x, y, w, h = parts
    if w <= 0 or h <= 0:
        raise SystemExit("--crop width and height must be positive")
    return (x, y, x + w, y + h)


def placeholder(size, title: str, tint, theme: dict, font_path: Path,
                at_left: bool) -> Image.Image:
    """A synthetic panel for --demo. Deliberately looks synthetic: this is here to
    show the treatment, never to stand in for a real screenshot."""
    width, height = size
    img = Image.new("RGB", size, tuple(tint))
    d = ImageDraw.Draw(img)
    step = max(24, height // 18)
    for x in range(0, width, step):
        d.line([(x, 0), (x, height)], fill=theme["Border"] + (0,), width=1)
    for y in range(0, height, step):
        d.line([(0, y), (width, y)], fill=theme["Border"], width=1)
    try:
        big = ImageFont.truetype(str(font_path), int(height * 0.075))
        small = ImageFont.truetype(str(font_path), int(height * 0.030))
    except OSError:
        big = small = ImageFont.load_default()
    # Sit the caption in this panel's own half, so the two do not collide across
    # the seam and spell nonsense.
    cx = width * (0.26 if at_left else 0.74)
    d.text((cx, height * 0.44), title, font=big, fill=theme["Text"], anchor="mm")
    d.text((cx, height * 0.55), "PLACEHOLDER - NOT A REAL SCREENSHOT",
           font=small, fill=theme["TextMuted"], anchor="mm")
    return img


def tracked_ink(text: str, font, tracking: float) -> Image.Image:
    """Tracked text as an alpha mask cropped to its ink, for exact centring."""
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    widths = [probe.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    pad = int(max(8, font.size))
    sheet = Image.new("L", (int(total) + pad * 2, int(font.size * 3)), 0)
    sd = ImageDraw.Draw(sheet)
    x, baseline = float(pad), sheet.height * 0.72
    for ch, w in zip(text, widths):
        sd.text((x, baseline), ch, font=font, fill=255, anchor="ls")
        x += w + tracking
    box = sheet.getbbox()
    return sheet.crop(box) if box else sheet


def fit_pair(before: Image.Image, after: Image.Image, theme: dict):
    """Put two differently sized shots on one canvas, without faking a match.

    The smaller image is scaled to the taller one's height with its aspect kept,
    then centred on a ground of the patcher's window colour. It is NOT stretched
    to fill: a 4:3 shot stretched into 16:9 would misrepresent both.
    """
    target = (max(before.width, after.width), max(before.height, after.height))

    def place(img):
        if img.size == target:
            return img
        scale = target[1] / img.height
        sized = img.resize((max(1, int(round(img.width * scale))), target[1]),
                           Image.LANCZOS)
        sheet = Image.new("RGB", target, tuple(theme["Window"]))
        sheet.paste(sized, ((target[0] - sized.width) // 2, 0))
        return sheet

    return place(before), place(after)


def pair_panels(before: Image.Image, after: Image.Image, region: str, frac: float,
                tilt: float, height: int | None = None):
    """The SAME region of each shot, side by side, scaled to a common height.

    This is the mode to use when the two shots are at different resolutions. A
    wipe assumes the two frames are aligned, so at different resolutions it lands
    vanilla's save list next to the patched portrait panel and there is nothing to
    compare. Cropping the same *fraction* of each frame and matching heights puts
    the same control beside itself, which is the comparison a reader wants.

    The two crops end up different widths -- 400x600 from a 4:3 shot against
    960x1080 from a 16:9 one -- and that is the point: after scaling to a common
    height, the width difference *is* the aspect change, shown rather than hidden.

    They overlap by `height * tan(tilt)` so the seam has somewhere to lean; without
    that the tilt would run off the edge of one panel and show bare canvas.
    """
    def cut(img):
        w, h = img.size
        span = max(1, int(round(w * frac)))
        if region == "right":
            box = (w - span, 0, w, h)
        elif region == "centre":
            box = ((w - span) // 2, 0, (w + span) // 2, h)
        else:
            box = (0, 0, span, h)
        return img.crop(box)

    left, right = cut(before), cut(after)
    target_h = height or max(left.height, right.height)

    def to_height(img):
        scale = target_h / img.height
        return img.resize((max(1, int(round(img.width * scale))), target_h), Image.LANCZOS)

    left, right = to_height(left), to_height(right)
    overlap = int(round(target_h * math.tan(math.radians(abs(tilt)))))
    overlap = min(overlap, left.width - 1, right.width - 1)
    canvas_w = left.width + right.width - overlap

    a = Image.new("RGB", (canvas_w, target_h))
    a.paste(left, (0, 0))
    a.paste(left, (0, 0))
    b = Image.new("RGB", (canvas_w, target_h))
    b.paste(right, (canvas_w - right.width, 0))
    # Fill each canvas's far side with its own edge column, so the seam never
    # exposes bare background wherever it leans.
    a.paste(left.crop((left.width - 1, 0, left.width, target_h)).resize(
        (canvas_w - left.width, target_h)), (left.width, 0))
    b.paste(right.crop((0, 0, 1, target_h)).resize(
        (canvas_w - right.width, target_h)), (0, 0))
    return a, b


def whole_frames(before: Image.Image, after: Image.Image, theme: dict,
                 canvas_size, tilt: float, direction: str,
                 label_before: str, label_after: str, caption: str | None,
                 font_path: Path, label_font_path: Path | None,
                 seam: bool = False) -> Image.Image:
    """Both shots whole, side by side, on a fixed-aspect canvas.

    Nothing is cropped and nothing is zoomed: each frame is scaled to fit its half
    with its own aspect kept, so a 4:3 vanilla shot stays 4:3 and keeps its bezel.
    The two therefore end up different heights, which is the aspect change stated
    plainly rather than hidden by cropping one to match the other.

    The canvas is a fixed 16:9 by default, so every composite in a set is the same
    shape -- mod-page galleries lay out badly when each image has its own aspect.

    No divider is drawn between the panels. In wipe mode the seam *is* the boundary
    and has to be there; here the two frames are already separate objects with their
    own borders and a gutter between them, so a line through the gap only adds
    furniture. `seam=True` restores it.
    """
    width, height = canvas_size
    scale = width / 1920.0
    canvas = Image.new("RGBA", canvas_size, theme["Window"] + (255,))

    bar = int(height * 0.068) if caption else 0
    content_h = height - bar
    margin = int(width * 0.022)
    gutter = int(width * 0.030)

    # Both panels get the SAME HEIGHT, not the same box. Fitting each into an equal
    # half makes the 16:9 shot the shorter one -- so the patched screenshot came out
    # visibly smaller than the vanilla it is meant to beat, which is backwards.
    # Equal height matches the vertical scale, and the after simply ends up wider:
    # that width difference is the widescreen gain, shown rather than described.
    ar_b = before.width / before.height
    ar_a = after.width / after.height
    usable_w = width - margin * 2 - gutter
    panel_h = int(min(content_h - margin * 2, usable_w / (ar_b + ar_a)))

    w_b, w_a = int(panel_h * ar_b), int(panel_h * ar_a)
    x0 = (width - (w_b + gutter + w_a)) // 2
    y0 = margin + (content_h - margin * 2 - panel_h) // 2

    panels = []
    for img, x, w in ((before, x0, w_b), (after, x0 + w_b + gutter, w_a)):
        sized = img.convert("RGB").resize((w, panel_h), Image.LANCZOS)
        canvas.paste(sized, (x, y0))
        panels.append((x, y0, w, panel_h))

    half = x0 + w_b + gutter // 2      # the seam lives in the gutter

    # A hairline around each frame, so a dark screenshot does not bleed into the
    # ground and the vanilla bezel still reads as an edge.
    d = ImageDraw.Draw(canvas)
    for x, y, w, h in panels:
        d.rectangle([x - 1, y - 1, x + w, y + h],
                    outline=theme["Border"] + (200,), width=max(1, int(scale * 2)))

    if seam:
        lean = math.tan(math.radians(tilt)) * (-1.0 if direction == "backslash" else 1.0)
        seam_top, seam_bottom = y0 - margin // 2, y0 + panel_h + margin // 2
        mid_y = (seam_top + seam_bottom) / 2.0
        x_top = half + (mid_y - seam_top) * lean
        x_bottom = half + (mid_y - seam_bottom) * lean
        wide = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        ImageDraw.Draw(wide).line([(x_top, seam_top), (x_bottom, seam_bottom)],
                                  fill=theme["Accent"] + (150,),
                                  width=max(3, int(SEAM_CORE * scale * 5)))
        glow = wide.filter(ImageFilter.GaussianBlur(max(3.0, SEAM_GLOW * scale * 0.7)))
        canvas.alpha_composite(glow)
        d.line([(x_top, seam_top), (x_bottom, seam_bottom)],
               fill=theme["Accent"] + (255,), width=max(1, int(SEAM_CORE * scale)))

    cap = max(11, int(height * LABEL_CAP_RATIO))
    font = None
    for candidate in (label_font_path, font_path):
        if candidate is None:
            continue
        try:
            font = ImageFont.truetype(str(candidate), cap)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    def plate(centre_x, centre_y, text, ink):
        glyphs = tracked_ink(text, font, cap * 0.34)
        bw, bh = glyphs.size
        pad_x, pad_y = cap * 0.85, cap * 0.60
        d.rounded_rectangle([centre_x - bw / 2 - pad_x, centre_y - bh / 2 - pad_y,
                             centre_x + bw / 2 + pad_x, centre_y + bh / 2 + pad_y],
                            radius=max(2, int(cap * 0.22)),
                            fill=theme["Card"] + (226,), outline=theme["Border"] + (235,),
                            width=max(1, int(scale * 2)))
        tinted = Image.new("RGBA", glyphs.size, ink)
        tinted.putalpha(glyphs)
        canvas.alpha_composite(tinted, (int(centre_x - bw / 2), int(centre_y - bh / 2)))

    bx, by, bw, bh = panels[0]
    ax, ay, aw, ah = panels[1]
    plate(bx + bw * 0.5, by + bh - cap * 1.5, label_before, theme["TextMuted"] + (255,))
    plate(ax + aw * 0.5, ay + cap * 1.5, label_after, theme["Accent"] + (255,))

    if caption:
        csize = max(10, int(bar * 0.42))
        room = width - bar
        while csize > 9:
            try:
                cfont = ImageFont.truetype(str(font_path), csize)
            except OSError:
                cfont = ImageFont.load_default()
                break
            span = tracked(ImageDraw.Draw(Image.new("RGBA", (8, 8))), (0, 0),
                           caption.upper(), cfont, (0, 0, 0, 0), csize * 0.30)
            if span <= room:
                break
            csize -= 1
        tracked(d, (0, content_h + bar * 0.68), caption.upper(), cfont,
                theme["TextMuted"] + (255,), csize * 0.30, anchor_centre_x=width / 2)

    d.rectangle([0, 0, width - 1, height - 1],
                outline=theme["Border"] + (255,), width=max(1, int(scale * 2)))
    return canvas


def showcase(shot: Image.Image, theme: dict, canvas_size, badge: str,
             caption: str | None, font_path: Path,
             label_font_path: Path | None) -> Image.Image:
    """One shot on its own, framed to match the before/after set.

    For resolutions that need no comparison to make their point -- an ultrawide
    grab says "this works at 21:9" by existing. Same ground, border, badge and
    caption bar as the pairs, so a mod-page gallery reads as one set rather than
    two batches made on different days.

    The shot keeps its own aspect and is never cropped; the canvas is sized from
    it, so a 21:9 grab yields a 21:9 card rather than being letterboxed into 16:9.
    """
    width, height = canvas_size
    scale = width / 1920.0
    canvas = Image.new("RGBA", canvas_size, theme["Window"] + (255,))

    bar = int(height * 0.075) if caption else 0
    margin = int(width * 0.014)
    cell = (width - margin * 2, height - bar - margin * 2)
    k = min(cell[0] / shot.width, cell[1] / shot.height)
    sized = shot.convert("RGB").resize((max(1, int(shot.width * k)),
                                        max(1, int(shot.height * k))), Image.LANCZOS)
    x = (width - sized.width) // 2
    y = margin + (cell[1] - sized.height) // 2
    canvas.paste(sized, (x, y))

    d = ImageDraw.Draw(canvas)
    d.rectangle([x - 1, y - 1, x + sized.width, y + sized.height],
                outline=theme["Border"] + (200,), width=max(1, int(scale * 2)))

    if badge:
        cap = max(11, int(height * LABEL_CAP_RATIO))
        font = None
        for candidate in (label_font_path, font_path):
            if candidate is None:
                continue
            try:
                font = ImageFont.truetype(str(candidate), cap)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()
        glyphs = tracked_ink(badge, font, cap * 0.34)
        bw, bh = glyphs.size
        pad_x, pad_y = cap * 0.85, cap * 0.60
        cx, cy = x + sized.width - bw / 2 - pad_x - margin, y + bh / 2 + pad_y + margin
        d.rounded_rectangle([cx - bw / 2 - pad_x, cy - bh / 2 - pad_y,
                             cx + bw / 2 + pad_x, cy + bh / 2 + pad_y],
                            radius=max(2, int(cap * 0.22)),
                            fill=theme["Card"] + (226,), outline=theme["Border"] + (235,),
                            width=max(1, int(scale * 2)))
        tinted = Image.new("RGBA", glyphs.size, theme["Accent"] + (255,))
        tinted.putalpha(glyphs)
        canvas.alpha_composite(tinted, (int(cx - bw / 2), int(cy - bh / 2)))

    if caption:
        csize = max(10, int(bar * 0.42))
        room = width - bar
        while csize > 9:
            try:
                cfont = ImageFont.truetype(str(font_path), csize)
            except OSError:
                cfont = ImageFont.load_default()
                break
            span = tracked(ImageDraw.Draw(Image.new("RGBA", (8, 8))), (0, 0),
                           caption.upper(), cfont, (0, 0, 0, 0), csize * 0.30)
            if span <= room:
                break
            csize -= 1
        tracked(d, (0, height - bar * 0.32), caption.upper(), cfont,
                theme["TextMuted"] + (255,), csize * 0.30, anchor_centre_x=width / 2)

    d.rectangle([0, 0, width - 1, height - 1],
                outline=theme["Border"] + (255,), width=max(1, int(scale * 2)))
    return canvas


def compose(before: Image.Image, after: Image.Image, theme: dict, font_path: Path,
            tilt: float, direction: str, label_before: str, label_after: str,
            caption: str | None, label_font_path: Path | None = None) -> Image.Image:
    width, height = before.size
    scale = width / 1920.0

    # Boundary x for each row: a line through the centre, leaning `tilt` off vertical.
    lean = math.tan(math.radians(tilt)) * (-1.0 if direction == "backslash" else 1.0)
    ys = np.arange(height, dtype=np.float32)
    boundary = (width / 2.0) + (height / 2.0 - ys) * lean

    xs = np.arange(width, dtype=np.float32)[None, :]
    # Soft edge of ~1px so the seam is not aliased.
    mask = np.clip(xs - boundary[:, None] + 0.5, 0.0, 1.0)
    mask_img = Image.fromarray((mask * 255).astype(np.uint8), "L")

    canvas = Image.composite(after, before, mask_img).convert("RGBA")

    # --- the seam: accent core with a glow, the patcher's own accent -------
    x_top = boundary[0]
    x_bottom = boundary[-1]
    # The glow source is deliberately wider than the core: blurring a hairline
    # spreads it so thin it disappears, which is what the first attempt did.
    wide = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(wide).line([(x_top, 0), (x_bottom, height)],
                              fill=theme["Accent"] + (170,),
                              width=max(3, int(SEAM_CORE * scale * 6)))
    glow = wide.filter(ImageFilter.GaussianBlur(max(3.0, SEAM_GLOW * scale)))
    canvas.alpha_composite(glow)
    canvas.alpha_composite(glow)
    sd2 = ImageDraw.Draw(canvas)
    sd2.line([(x_top, 0), (x_bottom, height)],
             fill=theme["Accent"] + (255,), width=max(1, int(SEAM_CORE * scale)))

    # --- labels, each inside its own half ---------------------------------
    cap = max(11, int(height * LABEL_CAP_RATIO))
    font = None
    for candidate in (label_font_path, font_path):
        if candidate is None:
            continue
        try:
            font = ImageFont.truetype(str(candidate), cap)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(canvas)

    def plate(centre_x, centre_y, text, ink):
        """A label centred on its plate by measured ink, both axes.

        The obvious version -- box from `baseline - cap` to `baseline`, text drawn
        on the baseline -- is wrong twice over. `ImageFont.truetype(path, cap)`
        sets the em size, and Georgia's cap height is about 0.7 of that, so the
        box was ~30% taller than the letters and they sat low in it. Cap height
        also ignores that BEFORE and AFTER have no descenders, so even a correct
        cap measurement would leave the optical centre off. Rendering the tracked
        text once and reading its actual bounding box settles both, and costs one
        small allocation per label.
        """
        glyphs = tracked_ink(text, font, cap * 0.34)
        box_w, box_h = glyphs.size
        pad_x, pad_y = cap * 0.85, cap * 0.60
        box = [centre_x - box_w / 2 - pad_x, centre_y - box_h / 2 - pad_y,
               centre_x + box_w / 2 + pad_x, centre_y + box_h / 2 + pad_y]
        d.rounded_rectangle(box, radius=max(2, int(cap * 0.22)),
                            fill=theme["Card"] + (216,), outline=theme["Border"] + (235,),
                            width=max(1, int(scale * 2)))
        tinted = Image.new("RGBA", glyphs.size, ink)
        tinted.putalpha(glyphs)
        canvas.alpha_composite(tinted, (int(centre_x - box_w / 2),
                                        int(centre_y - box_h / 2)))

    inset = height * 0.085
    # Each label sits in the widest part of its own half, so neither crosses the seam.
    plate(min(boundary[-1], width) * 0.5, height - inset, label_before,
          theme["TextMuted"] + (255,))
    plate(max(boundary[0], 0) + (width - max(boundary[0], 0)) * 0.5,
          inset, label_after, theme["Accent"] + (255,))

    # --- frame and optional caption ---------------------------------------
    if caption:
        bar = max(28, int(height * 0.072))
        out = Image.new("RGBA", (width, height + bar), theme["Window"] + (255,))
        out.alpha_composite(canvas, (0, 0))
        cd = ImageDraw.Draw(out)
        # Shrink the caption until it fits the bar. Tracked text is much wider than
        # its untracked measure, so a caption sized only from the bar height runs
        # off both ends of a narrow composite -- which is what the first batch did.
        csize = max(10, int(bar * 0.40))
        room = width - bar          # half a bar of margin at each end
        while csize > 9:
            try:
                cfont = ImageFont.truetype(str(font_path), csize)
            except OSError:
                cfont = ImageFont.load_default()
                break
            span = tracked(ImageDraw.Draw(Image.new("RGBA", (8, 8))), (0, 0),
                           caption.upper(), cfont, (0, 0, 0, 0), csize * 0.30)
            if span <= room:
                break
            csize -= 1
        tracked(cd, (0, height + bar * 0.66), caption.upper(), cfont,
                theme["TextMuted"] + (255,), csize * 0.30, anchor_centre_x=width / 2)
        canvas = out

    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, canvas.width - 1, canvas.height - 1],
                outline=theme["Border"] + (255,), width=max(1, int(scale * 2)))
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--crop", help="x,y,width,height applied to BOTH images")
    parser.add_argument("--tilt", type=float, default=DEFAULT_TILT,
                        help="degrees off vertical; 0 is a straight split")
    parser.add_argument("--direction", choices=("slash", "backslash"), default="slash")
    parser.add_argument("--label-before", default="BEFORE")
    parser.add_argument("--label-after", default="AFTER")
    parser.add_argument("--caption", default=None)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--label-font", type=Path, default=LABEL_FONT,
                        help="face for BEFORE/AFTER; falls back to --font if absent")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--mode", choices=("wipe", "pair", "whole", "solo"), default="wipe",
                        help="wipe: diagonal across two aligned frames. "
                             "pair: the same region of each, side by side -- use this "
                             "when the shots are at different resolutions. "
                             "whole: both frames entire, side by side, uncropped. "
                             "solo: one shot on its own, framed to match the set")
    parser.add_argument("--badge", default="KMRP",
                        help="solo mode: the plate in the shot's top-right corner")
    parser.add_argument("--seam", action="store_true",
                        help="whole mode only: draw the accent divider in the gutter")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--region", choices=("left", "centre", "right"), default="left")
    parser.add_argument("--region-frac", type=float, default=0.5,
                        help="fraction of each frame's width to show, in pair mode")
    parser.add_argument("--fit", action="store_true",
                        help="scale a smaller image onto the larger canvas; see fit_pair")
    parser.add_argument("--demo", action="store_true",
                        help="render the template with synthetic panels")
    args = parser.parse_args()

    theme = read_theme(args.root / THEME_SOURCE)

    if args.demo:
        size = (1920, 1080)
        before = placeholder(size, "VANILLA", (26, 26, 30), theme, args.font, True)
        after = placeholder(size, "KMRP", theme["Card"], theme, args.font, False)
    else:
        if args.mode == "solo":
            if not (args.after or args.before):
                raise SystemExit("solo mode needs --after (or --before) as the image")
        elif not args.before or not args.after:
            raise SystemExit("--before and --after are required unless --demo is given")
        before = Image.open(args.before).convert("RGB") if args.before else None
        after = Image.open(args.after).convert("RGB") if args.after else None
        if args.crop and before is not None and after is not None:
            box = parse_crop(args.crop)
            before, after = before.crop(box), after.crop(box)
        if (before is not None and after is not None
                and before.size != after.size and args.mode not in ("pair", "whole")):
            if not args.fit:
                raise SystemExit(
                    f"the two images differ in size ({before.size} vs {after.size}). "
                    "Pass --crop so both are cut to the same region, or --fit to scale "
                    "the smaller onto the larger's canvas. Note what --fit means before "
                    "using it: a comparison across two resolutions shows the resolution "
                    "change as well as the patch, and a reader is entitled to say so.")
            before, after = fit_pair(before, after, theme)

    if args.mode == "pair":
        before, after = pair_panels(before, after, args.region, args.region_frac,
                                    args.tilt)

    if args.mode == "solo":
        shot = Image.open(args.after or args.before)
        w = args.width
        h = int(round(w * shot.height / shot.width)) + int(w * 0.042)
        out = showcase(shot, theme, (w, h), args.badge, args.caption,
                       args.font, args.label_font)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        out.convert("RGB").save(args.out, quality=95)
        print(f"  {args.out}  {out.width}x{out.height}  {args.out.stat().st_size} bytes")
        return 0

    if args.mode == "whole":
        out = whole_frames(before, after, theme, (args.width, args.height),
                           args.tilt, args.direction, args.label_before,
                           args.label_after, args.caption, args.font, args.label_font,
                           args.seam)
    else:
        out = compose(before, after, theme, args.font, args.tilt, args.direction,
                      args.label_before, args.label_after, args.caption, args.label_font)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.convert("RGB").save(args.out, quality=95)
    print(f"  {args.out}  {out.width}x{out.height}  {args.out.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
