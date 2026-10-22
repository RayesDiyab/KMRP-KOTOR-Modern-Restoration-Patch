#!/usr/bin/env python3
"""Bake an HD version of the game's own fonts: the original's design, sizes and spacing,
drawn from vector faces at six times the original's size (the size 100% text is
drawn at on a 2160-line screen; the game fits each atlas to the size it is drawn at,
K1RuntimeAssets.cpp FitAtlas).

No longer run since 2026-10-22: the atlases are drawn from the KMRP Original HD fonts
(fonts/otf) by tools/build_hd_original_atlases.py. Kept as the record of how they were
first made (docs/hd-original-font.md).

The 18 stock atlases (`swpc_tex_gui.erf`) are hand-made pixel fonts in three designs,
measured on 2026-10-18 (each original letter against each face, scaled to the same box,
and the stroke, widths and gaps):

  menu fonts   Bank Gothic, lower case drawn as small capitals, with letters redrawn
               at some sizes (a round O at 16 and 10 pixels, square O at 12, slightly
               rounded corners at 32): dialogfont10x10, 10x10a, 10x10b, 12x16, 16x16,
               16x16a, 16x16b, 32x32
  body fonts   a Helvetica-style sans, bold (stroke 0.18 of the capital height):
               fnt_d16x16, fnt_d16x16b, fnt_d10x10b, fnt_credits, fnt_creditsb; and the
               HUD's fnt_console, the same letters in cells of one width
  light fonts  the same sans, light (stroke 0.12): fnt_creditsa, fnt_d16x16a,
               fnt_dialog16x16
  fnt_galahad14, a decorative face of its own (no face for it here), is the original
  enlarged and sharpened, as the Original Sharpened style that HD Original replaces was.
  Because that is the game's own art, it is not made here or committed: the bank build
  makes it from the game's files every time (build_original_fonts.enlarged,
  build_native_assets.hd_original; the maintainer, 2026-10-19).

Each atlas keeps the original's layout, read from the stock atlas itself:
  * every character's cell is the original cell's width times the scale, so letter
    gaps, word spaces and the HUD's even cells are the original's, and a line is as
    long as it was;
  * the capital height, the small capitals' height and the baseline are the original's
    times the scale;
  * the letters are narrowed or widened by one factor per font, the median over its
    letters and digits of the original's ink width over the face's, so their width to
    height is the original's (one factor, not one per letter);
  * each letter is centred where the original's ink is centred;
  * the strokes are made as heavy as the original's (only heavier, never lighter).
Every size is read to a fraction of a pixel (Stock.span, stroke, bar): the originals are
anti-aliased, and an edge pixel's coverage says how far into it the edge lies. Counted
in whole pixels the 16 pixel small capitals were 7 tall instead of 7.47 and the
horizontal strokes 2 instead of 1.68.

Where the original drew a letter differently from its face, the original's shape is
followed, decided slot by slot from the original's pixels:
  * in the menu fonts (Bank Gothic's O is square), O-shaped letters (O o Ò-Ö Ø ò-ö ø Q
    q 0) whose original is round (an empty run of at least a fifth of its width at the
    corners of its top row) are drawn as the original's own ring: a superellipse whose
    centre, width, height, squareness and strokes are fitted to the original's pixels
    (fit_ring). Diacritics and Ø's bar are the face's own;
  * ¤ is a square ring with four corner ticks, as the original draws it (a face may hold
    a euro sign there);
  * @ is the face's, fitted to the original's box;
  * ß, when the face has none of its own shape (Bank Gothic draws "SS"), is a plain
    sans ß (SZLIG_DONOR's) placed, sized and made as heavy as the largest original of
    the design that has one (fit_donor).
Characters the face lacks are made from its own parts, as in build_font_from_ttf.py's
note on coverage: the soft hyphen its hyphen; ð þ its Ð Þ at its small-capital size;
Ž ž its Z z with the caron of Š š; € from a face that has one. Where the original holds
only a placeholder box, the real character is drawn at the face's own width.

The faces are not in the repository: put them in build-inputs/local-fonts (ignored by
git) or pass --fonts-dir. Only the atlases are made from them.

Usage:
    python tools/build_hd_original_fonts.py build/native-runtime/original-fonts assets/hd-original-fonts
"""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw, ImageFont

from build_font_from_ttf import GLYPH_PADDING, next_power_of_two, pack, slot_character
from build_scaled_fonts import FONT_RESREFS, write_tga
import hud_font_geometry

ROOT = Path(__file__).resolve().parents[1]
SCALE = 6.0
MENU = ("dialogfont10x10", "dialogfont10x10a", "dialogfont10x10b", "dialogfont12x16", "dialogfont16x16",
        "dialogfont16x16a", "dialogfont16x16b", "dialogfont32x32")
BODY = ("fnt_d16x16", "fnt_d16x16b", "fnt_d10x10b", "fnt_credits", "fnt_creditsb", "fnt_console")
LIGHT = ("fnt_creditsa", "fnt_d16x16a", "fnt_dialog16x16")
FACES = {**{n: "BankGothicMedium.otf" for n in MENU}, **{n: "Helvetica-Bold.ttf" for n in BODY},
         **{n: "Helvetica.ttf" for n in LIGHT}}
EURO_DONOR = ROOT / "assets/fonts/Arimo-Medium.ttf"
# The menu fonts' ß is not Bank Gothic's (it has an "SS" there) but a plain sans ß, as
# Windows' fallback face drew it: fitted to the 16 pixel original's pixels (2026-10-18,
# error left over, less is closer: Microsoft Sans Serif 3.9, Arial 4.3, Arimo Medium
# 4.4, Arial Bold 4.8, Helvetica Bold 7.7). Arimo, Arial's open twin, is in the repository.
SZLIG_DONOR = ROOT / "assets/fonts/Arimo-Medium.ttf"
ROUND_CANDIDATES = "OoQq0ÒÓÔÕÖØòóôõöø"
# The superellipse exponent of the whole-pixel menu fonts' o (round_letter): 2 is an
# ellipse, larger is squarer.
WHOLE_PIXEL_O_SQUARENESS = 3.0
OVERSAMPLE = 4      # shapes drawn at four times the atlas's size, then reduced
# The originals have a faint halo around every letter (6 to 10 percent of full coverage
# on the row or column beside it); coverage up to this much beside a letter is not ink.
HALO = 0.15


# ---------------------------------------------------------------------------------
# The stock atlas: its header, cells and each character's ink.
class Stock:
    """The original as the game uses it: KMRP's Original Font copy (kmrfogNN, written
    by tools/build_original_fonts.py from the texture pack), whose TXI for fnt_d10x10b
    and fnt_d16x16 is repaired: the texture pack's own describes another packing."""

    def __init__(self, originals: Path, resref: str):
        index = FONT_RESREFS.index(resref)
        self.txi = (originals / f"kmrfog{index:02d}.txi").read_text().replace("\r\n", "\n").replace("\r", "\n")
        self.image = Image.open(originals / f"kmrfog{index:02d}.tga").convert("RGBA")
        lines = [l.strip() for l in self.txi.splitlines() if l.strip()]
        self.header = {}
        for line in lines:
            parts = line.split()
            if len(parts) == 2 and parts[0] in ("mipmap", "filter", "compresstexture", "downsamplemax",
                                                "downsamplemin", "numchars", "fontheight", "baselineheight",
                                                "texturewidth", "spacingR", "spacingB", "caretindent"):
                self.header[parts[0]] = parts[1]
        self.numchars = int(float(self.header["numchars"]))
        upper = next(i for i, l in enumerate(lines) if l.startswith("upperleftcoords"))
        lower = next(i for i, l in enumerate(lines) if l.startswith("lowerrightcoords"))
        W, H = self.image.size
        self.cells, self.ink = [], []
        for c in range(self.numchars):
            x0, y0 = map(float, lines[upper + 1 + c].split()[:2])
            x1, y1 = map(float, lines[lower + 1 + c].split()[:2])
            box = (round(x0 * W), round((1 - y0) * H), round(x1 * W), round((1 - y1) * H))
            self.cells.append(box)
            ink = None
            if box[2] > box[0] and box[3] > box[1]:
                cell = self.image.crop(box)
                lum = cell.convert("RGB").convert("L")
                mask = Image.eval(cell.getchannel("A"), lambda v: 255 if v > 127 else 0)
                # The letter is bright and opaque; the originals keep a dark outline in alpha.
                ink = Image.eval(Image.composite(lum, Image.new("L", cell.size, 0), mask),
                                 lambda v: 255 if v > 127 else 0)
            self.ink.append(ink)
        self.height = max(b[3] - b[1] for b in self.cells)
        h = self.box(ord("H"))
        self.cap = h[3] - h[1]
        self.baseline = h[3]                  # within the cell, from its top
        # Coverage (brightness times opacity) against the atlas's fullest pixel: the
        # 32 pixel font is drawn dimmer than the others.
        rgba = np.asarray(self.image, dtype=np.float64)
        self._coverage = (rgba[..., 0] * 0.299 + rgba[..., 1] * 0.587 + rgba[..., 2] * 0.114) * rgba[..., 3]
        self._coverage /= self._coverage.max()
        top, bottom = self.span(ord("H"), 1)
        self.cap_height = bottom - top
        # Anti-aliased (16 to 59 percent of the inked pixels partly covered), or drawn in
        # whole pixels (dialogfont10x10, 10x10a, 16x16a and the 1-bit body fonts: at most
        # 1.3 percent).
        inked = self._coverage[self._coverage > 0.02]
        self.antialiased = bool(len(inked)) and float((inked < 0.85).mean()) >= 0.05

    def coverage(self, c):
        """The character's cell as coverage, 0 to 1."""
        x0, y0, x1, y1 = self.cells[c]
        return self._coverage[y0:y1, x0:x1]

    def span(self, c, axis):
        """Where the character's ink starts and ends across (axis 0) or down (axis 1) its
        cell, to a fraction of a pixel. The originals are anti-aliased: a letter's edge
        pixel is covered by as much of the letter as stands in it, so the edge lies that
        far into it (the 16 pixel small capitals' top row is 40 percent covered: they are
        7.47 pixels tall, not the 7 their solid rows count). The faint halo beyond the
        edge pixel is the edge's own, blurred outward: it is counted back in."""
        cov = self.coverage(c)
        prof = cov.max(axis=axis)        # across: each column's fullest pixel; down: each row's
        inked = np.nonzero(prof > HALO)[0]
        if not len(inked):
            return None
        first, last = int(inked[0]), int(inked[-1])
        before = prof[first - 1] if first > 0 else 0.0
        after = prof[last + 1] if last + 1 < len(prof) else 0.0
        return first + 1 - (prof[first] + before), last + prof[last] + after

    def small_cap_height(self):
        """The small capitals' height, x's (o is a round letter), to a fraction of a pixel."""
        c = ord("x") if self.box(ord("x")) else ord("o")
        top, bottom = self.span(c, 1)
        return bottom - top

    def box(self, c):
        ink = self.ink[c] if c < self.numchars else None
        return ink.getbbox() if ink is not None else None

    def width(self, c):
        b = self.cells[c]
        return b[2] - b[0]

    def placeholder(self, c):
        """The original has only a placeholder box in this slot (its 0x81 box, or a box
        with a dot), not a letter."""
        ink = self.ink[c] if c < self.numchars else None
        if ink is None or not ink.getbbox():
            return True
        ref = self.ink[0x81] if self.numchars > 0x81 else None
        if ref is not None and ref.getbbox() and ink.size == ref.size and ink.tobytes() == ref.tobytes():
            return True
        b = ink.getbbox()
        w, h = b[2] - b[0], b[3] - b[1]
        if h >= self.cap * 1.3 and w >= 3:
            # A tall rectangle outline, perhaps with a dot: the edges full, the inside nearly
            # empty. At least 3 wide, so it has an inside: the 32 pixel font's | is a solid
            # bar 2 wide, and was taken for a box until 2026-10-18 (Test-TextOptions.py).
            crop = ink.crop(b)
            edge = all(crop.getpixel((x, 0)) and crop.getpixel((x, h - 1)) for x in range(w))
            inner = sum(1 for x in range(1, w - 1) for y in range(1, h - 1) if crop.getpixel((x, y)))
            return edge and inner <= max(2, (w - 2) * (h - 2) // 6)
        return False

    def round(self, c):
        """The original's O-shape is round: its top row starts (and ends) a fifth of its
        width or more in from its box."""
        b = self.box(c)
        if not b or self.placeholder(c):
            return False
        ink = self.ink[c]
        w = b[2] - b[0]
        body_top = b[1]
        # Skip diacritics: the body starts at the first row of the run that reaches the cap line.
        cap_top = self.baseline - (self.cap if chr(c) not in "oqòóôõöø" else self.small_cap())
        body_top = max(b[1], cap_top)
        row = [x for x in range(b[0], b[2]) if ink.getpixel((x, body_top))]
        if not row:
            return False
        inset = min(row[0] - b[0], b[2] - 1 - row[-1])
        # A fifth of the width in whole pixels: the 10 pixel menu fonts' o is 6 wide with
        # one pixel off each corner, round as the original draws it at that size, and
        # was taken for square (w / 5 = 1.2) until the maintainer saw it on 2026-10-21.
        return inset >= max(1, w // 5)

    def small_cap(self):
        b = self.box(ord("x")) or self.box(ord("o"))   # x: o is a round letter
        return (b[3] - b[1]) if b else self.cap

    def stroke(self):
        """The vertical stroke: I's width at half its height, the coverage across it (the
        16 pixel I: 0.71, 1 and 0.39 of a pixel, 2.1)."""
        b = self.box(ord("I"))
        row = self.coverage(ord("I"))[(b[1] + b[3]) // 2]
        return float(row[row > HALO].sum())

    def bar(self):
        """The horizontal stroke: H's crossbar, the coverage down H's middle column (the
        16 pixel H: 0.51, 1 and 0.17, 1.68; counted in whole pixels it was 2)."""
        b = self.box(ord("H"))
        col = self.coverage(ord("H"))[:, (b[0] + b[2]) // 2]
        return float(col[col > HALO].sum())


# ---------------------------------------------------------------------------------
# Drawing. Letters are drawn at OVERSAMPLE times, narrowed by the font's factor, made
# as heavy as the original (GROW: pixels added to the vertical and to the horizontal
# strokes, at the atlas's size; negative takes away), and reduced.
GROW = [0.0, 0.0]


class Pen:
    """A face at one size: its horizontal factor and how much heavier it is drawn."""

    def __init__(self, font, xscale, grow):
        self.font, self.xscale, self.grow = font, xscale, list(grow)

    def use(self):
        GROW[0], GROW[1] = self.grow
        return self.font, self.xscale


def _spread(im: Image.Image, pixels: int, horizontal: bool) -> Image.Image:
    """Every stroke `pixels` wider (or narrower, when negative) along one direction,
    half on each side: the maximum (minimum) over shifted copies."""
    if pixels == 0:
        return im
    n = abs(pixels)
    pad = (n, 0) if horizontal else (0, n)
    base = Image.new("L", (im.width + 2 * pad[0], im.height + 2 * pad[1]), 0)
    base.paste(im, pad)
    out = base.copy()
    op = ImageChops.lighter if pixels > 0 else ImageChops.darker
    for s in range(-(n // 2), n - n // 2 + 1):
        if s == 0:
            continue
        shifted = Image.new("L", base.size, 0)
        shifted.paste(base, (s, 0) if horizontal else (0, s))
        out = op(out, shifted)
    return out


def glyph_ink(font: ImageFont.FreeTypeFont, ch: str, xscale: float, thin: float = 0.0):
    """The face's letter as an L image (its ink box only) and the baseline's row in it.
    `thin` takes that many pixels (at the atlas's size) off its vertical strokes after it
    is made heavier (the round o, round_o_letter)."""
    big = ImageFont.truetype(font.path, max(1, round(font.size * OVERSAMPLE)))
    l, t, r, b = big.getbbox(ch, anchor="ls")
    if r <= l or b <= t:
        return None, 0
    pad = 4 * OVERSAMPLE
    im = Image.new("L", (math.ceil(r - l) + 2 * pad, math.ceil(b - t) + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad - l, pad - t), ch, font=big, fill=255, anchor="ls")
    baseline_row = pad - t
    if abs(xscale - 1.0) > 1e-3:
        im = im.resize((max(1, round(im.width * xscale)), im.height), Image.LANCZOS)
    gx, gy = round((GROW[0] - thin) * OVERSAMPLE), round(GROW[1] * OVERSAMPLE)
    if gx:
        im = _spread(im, gx, True)
    if gy:
        im = _spread(im, gy, False)
        # The spread padded |gy| rows above; it also grew the letter about half of gy
        # below its baseline. It is to stand on the baseline, as the original's do: the
        # baseline moves down with it (the face was drawn gy smaller, so the letter's
        # top then lands on the capital line).
        baseline_row += abs(gy) + (gy - gy // 2 if gy > 0 else 0)
    # Reduce on the oversampled grid's own boundaries, so the baseline stays on a row.
    top_pad = baseline_row % OVERSAMPLE
    W = math.ceil(im.width / OVERSAMPLE) * OVERSAMPLE
    H = math.ceil((im.height + (OVERSAMPLE - top_pad) % OVERSAMPLE) / OVERSAMPLE) * OVERSAMPLE
    canvas = Image.new("L", (W, H), 0)
    shift = (OVERSAMPLE - top_pad) % OVERSAMPLE
    canvas.paste(im, (0, shift))
    small = canvas.resize((W // OVERSAMPLE, H // OVERSAMPLE), Image.BOX)
    box = small.getbbox()
    if not box:
        return None, 0
    return small.crop(box), (baseline_row + shift) // OVERSAMPLE - box[1]


def drawn_width(font: ImageFont.FreeTypeFont, ch: str) -> float:
    """The letter's drawn ink width. Not getbbox's: for Bank Gothic's CFF outlines that
    includes the side bearings (H: 46 pixels against 35 drawn at size 52)."""
    big = ImageFont.truetype(font.path, max(1, round(font.size * OVERSAMPLE)))
    l, t, r, b = big.getbbox(ch, anchor="ls")
    if r <= l or b <= t:
        return 0.0
    im = Image.new("L", (math.ceil(r - l) + 8, math.ceil(b - t) + 8), 0)
    ImageDraw.Draw(im).text((4 - l, 4 - t), ch, font=big, fill=255, anchor="ls")
    box = Image.eval(im, lambda v: 255 if v >= 128 else 0).getbbox()
    return (box[2] - box[0]) / OVERSAMPLE if box else 0.0


def face_strokes(font: ImageFont.FreeTypeFont, xscale: float):
    """The face's vertical and horizontal strokes (I's width, H's crossbar), narrowed by
    `xscale`, at the atlas's size, measured on the oversampled drawing."""
    big = ImageFont.truetype(font.path, max(1, round(font.size * OVERSAMPLE)))

    def draw(ch):
        l, t, r, b = big.getbbox(ch, anchor="ls")
        im = Image.new("L", (math.ceil(r - l) + 8, math.ceil(b - t) + 8), 0)
        ImageDraw.Draw(im).text((4 - l, 4 - t), ch, font=big, fill=255, anchor="ls")
        im = im.resize((max(1, round(im.width * xscale)), im.height), Image.LANCZOS)
        return Image.eval(im, lambda v: 255 if v >= 128 else 0)

    i, h = draw("I"), draw("H")
    bi, bh = i.getbbox(), h.getbbox()
    y = (bi[1] + bi[3]) // 2
    stem = sum(1 for x in range(bi[0], bi[2]) if i.getpixel((x, y)))
    x = (bh[0] + bh[2]) // 2
    bar = sum(1 for yy in range(bh[1], bh[3]) if h.getpixel((x, yy)))
    return stem / OVERSAMPLE, bar / OVERSAMPLE


def ink_span(prof) -> tuple[float, float] | None:
    """Where a coverage profile's ink starts and ends, to a fraction of a pixel (the rule
    Stock.span reads the originals by)."""
    inked = np.nonzero(prof > HALO)[0]
    if not len(inked):
        return None
    first, last = int(inked[0]), int(inked[-1])
    before = prof[first - 1] if first > 0 else 0.0
    after = prof[last + 1] if last + 1 < len(prof) else 0.0
    return first + 1 - (prof[first] + before), last + prof[last] + after


def ink_box(img: Image.Image):
    """An L image's ink width and height, to a fraction of a pixel, and its middle row's
    left half's coverage (an o's side stroke)."""
    cov = np.asarray(img, dtype=np.float64) / 255.0
    x0, x1 = ink_span(cov.max(axis=0))
    y0, y1 = ink_span(cov.max(axis=1))
    mid = cov[int((y0 + y1) / 2), : int((x0 + x1) / 2)]
    return x1 - x0, y1 - y0, float(mid[mid > HALO].sum())


# The lower-case o and its accented forms, in the body and light designs. The face's o,
# narrowed by the font's one factor, is taller than wide there (the 16 pixel bold one
# 49.99 x 53.53 at six times), where the bold original's is round (8.51 x 8.59). The
# maintainer, on 2026-10-21: "this specific letter should be wider so its new width
# equals the already present height"; the bold designs (BODY), not the light ones.
O_FAMILY = "oòóôõöø"
# The least room a round o leaves at either side of its cell, in original pixels; the
# cell is widened where the o would come closer (the light fonts' 6 pixel cells).
O_MIN_GAP = 1 / 6


class RoundO:
    """How the round o is drawn for one font: the face's o widened by `factor` beyond the
    font's own and its vertical strokes made `thin` pixels lighter again, so it is as wide
    as it is tall and its sides as heavy as every other letter's.

    Widened by k, the o is k times its width w and its side stroke s is k s; taking the
    extra stroke off again leaves k w - (k - 1) s, which is its height h when
    k = (h - s) / (w - s). Settled on the drawn letter by the secant method, since the
    drawing rounds to the oversampled grid."""

    def __init__(self, font, xscale):
        img, _ = glyph_ink(font, "o", xscale)
        w, self.height, s = ink_box(img)
        self.before = w
        k = (self.height - s) / (w - s) if self.height > w else 1.0
        self.factor, self.thin = k, (k - 1.0) * s

        def width(kk):
            im, _ = glyph_ink(font, "o", xscale * kk, (kk - 1.0) * s)
            return ink_box(im)[0]
        if k > 1.0:
            k0, w0 = 1.0, w
            k1, w1 = k, width(k)
            for _ in range(4):
                if abs(w1 - self.height) < 0.05 or w1 == w0:
                    break
                k0, w0, k1 = k1, w1, k1 + (self.height - w1) * (k1 - k0) / (w1 - w0)
                w1 = width(k1)
            self.factor, self.thin = k1, (k1 - 1.0) * s
        self.width = width(self.factor) if self.factor > 1.0 else w


def round_o_letter(ch, font, xscale, shape: RoundO):
    """The round o (RoundO), and an accented one: the face's accent, from its accented
    letter less its plain o, centred over the round o, as round_letter puts the face's
    accents on the menu fonts' rings. ø is widened whole, its bar with it."""
    if ch in "oø":
        return glyph_ink(font, ch, xscale * shape.factor, shape.thin)
    body, bbase = glyph_ink(font, "o", xscale * shape.factor, shape.thin)
    acc, ab = glyph_ink(font, ch, xscale)
    pla, pbase = glyph_ink(font, "o", xscale)
    rise = max(0, ab - pbase)                       # rows of the accent above the o's top
    out = Image.new("L", (max(body.width, acc.width), max(body.height + rise, acc.height)), 0)
    out.paste(body, ((out.width - body.width) // 2, rise))
    plain_canvas = Image.new("L", acc.size, 0)
    plain_canvas.paste(pla, ((acc.width - pla.width) // 2, rise))
    extra = Image.composite(Image.new("L", acc.size, 0), acc, plain_canvas)
    out.paste(255, ((out.width - acc.width) // 2, 0), extra)
    return out, bbase + rise


def ring_coverage(columns, rows, ring, over):
    """A ring's coverage of a grid of `columns` by `rows` pixels: the outer superellipse
    |x/a|^n + |y/b|^n <= 1 less the inner one (half-axes less the strokes), sampled
    `over` times each way in every pixel and averaged. `ring` is (centre x, centre y,
    half-width a, half-height b, n, side stroke, top stroke), in the grid's pixels."""
    cx, cy, a, b, n, tx, ty = ring
    xs = (np.arange(columns * over) + 0.5) / over - cx
    ys = (np.arange(rows * over) + 0.5) / over - cy
    ax = np.abs(xs)[None, :]
    ay = np.abs(ys)[:, None]
    outer = (ax / a) ** n + (ay / b) ** n <= 1
    inner = (ax / max(0.05, a - tx)) ** n + (ay / max(0.05, b - ty)) ** n <= 1
    inside = (outer & ~inner).astype(np.float64)
    return inside.reshape(rows, over, columns, over).mean(axis=(1, 3))


def _nelder_mead(f, start, steps, iterations=4000):
    """The minimum of f near `start` (the downhill simplex)."""
    points = [np.array(start, dtype=np.float64)]
    points += [points[0] + np.eye(len(start))[i] * steps[i] for i in range(len(start))]
    values = [f(p) for p in points]
    for _ in range(iterations):
        order = np.argsort(values)
        points, values = [points[i] for i in order], [values[i] for i in order]
        if values[-1] - values[0] < 1e-10 + 1e-8 * values[0] and \
                max(np.abs(p - points[0]).max() for p in points[1:]) < 1e-4:
            break
        centre = np.mean(points[:-1], axis=0)
        reflected = centre + (centre - points[-1])
        fr = f(reflected)
        if fr < values[0]:
            expanded = centre + 2 * (centre - points[-1])
            fe = f(expanded)
            points[-1], values[-1] = (expanded, fe) if fe < fr else (reflected, fr)
        elif fr < values[-2]:
            points[-1], values[-1] = reflected, fr
        else:
            contracted = centre + 0.5 * (points[-1] - centre)
            fc = f(contracted)
            if fc < values[-1]:
                points[-1], values[-1] = contracted, fc
            else:
                points = [points[0]] + [points[0] + 0.5 * (p - points[0]) for p in points[1:]]
                values = [values[0]] + [f(p) for p in points[1:]]
    best = int(np.argmin(values))
    return points[best], values[best]


def fit_ring(stock: Stock, c: int):
    """The ring most like the original's O-shape in slot `c`: centre, width, height,
    squareness and strokes, fitted by least squares to its anti-aliased pixels, so known
    to a fraction of a pixel (the 16 pixel O: 10.53 wide, 9.02 tall, n 2.26, the sides
    2.06 and the top and bottom 1.69; its o 9.04 by 7.39; each within 0.3 percent of the
    original's coverage). Read as whole pixels its box was 10 by 9 (o 10 by 7), and an O
    drawn into that box read as an oval.

    A font drawn in whole pixels has no partial edge to read: its ring is the ellipse
    that fills the original's box, with its strokes (fitted to the 6 pixel O's stepped
    outline the ring came out nearly a diamond)."""
    b = stock.box(c)
    t = stock.stroke()
    if not stock.antialiased:
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, (b[2] - b[0]) / 2, (b[3] - b[1]) / 2, 2.0, t, stock.bar())
    target = stock.coverage(c)
    rows, columns = target.shape
    over = max(4, math.ceil(160 / max(rows, columns)))

    def error(p):
        if p[2] <= 0.5 or p[3] <= 0.5 or p[4] < 1.2 or p[5] < 0.3 or p[6] < 0.3:
            return 1e9
        return float(((ring_coverage(columns, rows, p, over) - target) ** 2).sum())

    best, best_error = None, math.inf
    for n in (2.0, 3.5):
        start = [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2, (b[2] - b[0]) / 2, (b[3] - b[1]) / 2, n, t, t]
        p, e = _nelder_mead(error, start, [0.3, 0.3, 0.4, 0.4, 0.5, 0.4, 0.4])
        if e < best_error:
            best, best_error = p, e
    return tuple(float(v) for v in best)


def ring_image(ring, scale):
    """The fitted ring at `scale`, anti-aliased, on the atlas's pixel grid: the image and
    the cell column and row of its top left pixel."""
    cx, cy, a, b, n, tx, ty = ring
    left, top = math.floor((cx - a) * scale), math.floor((cy - b) * scale)
    columns = math.ceil((cx + a) * scale) - left
    rows = math.ceil((cy + b) * scale) - top
    local = (cx * scale - left, cy * scale - top, a * scale, b * scale, n, tx * scale, ty * scale)
    cov = ring_coverage(columns, rows, local, OVERSAMPLE * 2)
    return Image.fromarray(np.round(cov * 255).astype(np.uint8), "L"), left, top


def compose_missing(ch, font, cmap, xscale, font_path):
    """A character the face lacks, from its own parts (see the module's note)."""
    if ch == "­" and ord("-") in cmap:
        return glyph_ink(font, "-", xscale)
    caps = {"ð": "Ð", "þ": "Þ"}
    if ch in caps and ord(caps[ch]) in cmap:
        hx = font.getbbox("x", anchor="ls")
        hX = font.getbbox("X", anchor="ls")
        ratio = (hx[3] - hx[1]) / (hX[3] - hX[1])
        small = ImageFont.truetype(str(font_path), max(1, round(font.size * ratio)))
        return glyph_ink(small, caps[ch], xscale)
    carons = {"Ž": ("Z", "Š", "S"), "ž": ("z", "š", "s")}
    if ch in carons and all(ord(x) in cmap for x in carons[ch]):
        base, ref, refbase = carons[ch]
        accented, ab = glyph_ink(font, ref, xscale)
        plain, pb = glyph_ink(font, refbase, xscale)
        letter, lb = glyph_ink(font, base, xscale)
        # The caron: the rows of Š above S's top, centred over Z as it is over S.
        rise = ab - pb                       # how much taller Š is above the baseline
        accent = accented.crop((0, 0, accented.width, max(1, rise)))
        out = Image.new("L", (max(letter.width, accent.width), letter.height + rise), 0)
        out.paste(letter, ((out.width - letter.width) // 2, rise))
        abox = accent.getbbox()
        if abox:
            piece = accent.crop(abox)
            out.paste(255, ((out.width - piece.width) // 2, abox[1]), piece)
        return out, lb + rise
    if ch == "€":
        donor = ImageFont.truetype(str(EURO_DONOR), font.size)
        hd = donor.getbbox("H", anchor="ls")
        hf = font.getbbox("H", anchor="ls")
        donor = ImageFont.truetype(str(EURO_DONOR), max(1, round(font.size * (hf[3] - hf[1]) / (hd[3] - hd[1]))))
        return glyph_ink(donor, ch, xscale)
    return None, 0


def currency_sign(width, height, stroke):
    """¤ as the original draws it: a square ring with a tick out of each corner."""
    over = OVERSAMPLE
    W, H, s = round(width * over), round(height * over), max(1, round(stroke * over))
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    inset = round(min(W, H) * 0.11)   # the 16 pixel original: a 7 pixel ring in a 9 pixel box
    d.rectangle((inset, inset, W - 1 - inset, H - 1 - inset), outline=255, width=s)
    for (x0, y0, x1, y1) in ((0, 0, inset + s // 2, inset + s // 2), (W - 1, 0, W - 1 - inset - s // 2, inset + s // 2),
                             (0, H - 1, inset + s // 2, H - 1 - inset - s // 2),
                             (W - 1, H - 1, W - 1 - inset - s // 2, H - 1 - inset - s // 2)):
        d.line((x0, y0, x1, y1), fill=255, width=s)
    return im.resize((max(1, round(width)), max(1, round(height))), Image.LANCZOS)


def donor_master(path: Path, ch: str) -> Image.Image:
    """A face's letter drawn large (800 pixels to the em), cropped to its ink."""
    f = ImageFont.truetype(str(path), 800)
    l, t, r, b = f.getbbox(ch)
    im = Image.new("L", (r - l + 40, b - t + 40), 0)
    ImageDraw.Draw(im).text((20 - l, 20 - t), ch, font=f, fill=255)
    return im.crop(im.getbbox())


def placed(master, box, grow, columns, rows, over):
    """`master` with its ink box at `box` (left, top, width, height, in pixels of a grid of
    `columns` by `rows`) and made `grow` pixels heavier across and down, as coverage of
    that grid, sampled `over` times each way in every pixel."""
    x0, y0, w, h = box
    sx, sy = master.width / (w * over), master.height / (h * over)
    im = master.transform((columns * over, rows * over), Image.AFFINE,
                          (sx, 0, -x0 * over * sx, 0, sy, -y0 * over * sy), resample=Image.BILINEAR)
    n = round(grow * over)
    if n > 0:
        im = _spread(im, n, True).crop((n, 0, n + columns * over, rows * over))
        im = _spread(im, n, False).crop((0, n, columns * over, n + rows * over))
    return np.asarray(im, dtype=np.float64).reshape(rows, over, columns, over).mean(axis=(1, 3)) / 255


def fit_donor(stock: Stock, c: int, path: Path):
    """Where and how heavy the face at `path` draws the original's letter in slot `c`:
    its ink box (left, top, width, height) and how much heavier, in the original's
    pixels, fitted by least squares to the original's anti-aliased pixels."""
    master = donor_master(path, chr(c))
    target = stock.coverage(c)
    rows, columns = target.shape
    across, down = stock.span(c, 0), stock.span(c, 1)
    start = [across[0], down[0], across[1] - across[0], down[1] - down[0]]
    best, best_error = None, math.inf
    for grow in (0.0, 0.15, 0.3, 0.45, 0.6, 0.75):
        error = lambda p: (float(((placed(master, p, grow, columns, rows, 16) - target) ** 2).sum())
                           if p[2] > 1 and p[3] > 1 else 1e9)
        p, e = _nelder_mead(error, start, [0.3, 0.3, 0.4, 0.4])
        if e < best_error:
            best, best_error = tuple(float(v) for v in p) + (grow,), e
    return best


def donor_letter(stock: Stock, fit, path: Path, ch: str, k: float):
    """The fitted face letter at `k` atlas pixels per pixel of the original it was fitted
    to: the image (its ink only) and its baseline's row."""
    x0, y0, w, h, grow = fit
    master = donor_master(path, ch)
    margin = math.ceil(grow * k) + 2
    top = (y0 - stock.baseline) * k                   # from the baseline, negative above it
    row0 = math.floor(top) - margin                   # the canvas's top row, from the baseline
    columns = math.ceil((w + grow) * k) + 2 * margin
    rows = math.ceil(top - row0 + (h + grow) * k) + margin
    cov = placed(master, (margin, top - row0, w * k, h * k), grow * k, columns, rows, OVERSAMPLE)
    im = Image.fromarray(np.round(cov * 255).astype(np.uint8), "L")
    box = im.getbbox()
    return im.crop(box), -row0 - box[1]


# ---------------------------------------------------------------------------------
def build(erf: Path, resref: str, fonts_dir: Path, output: Path, scale: float, references: dict) -> dict:
    stock = Stock(erf, resref)
    font_path = fonts_dir / FACES[resref]
    cmap = TTFont(str(font_path)).getBestCmap()
    probe = ImageFont.truetype(str(font_path), 400)
    # Only made heavier, never lighter, and only where the original is large enough to
    # show its weight: a 6 pixel capital can only have 1 pixel strokes, which is the
    # pixel grid's limit, not the design's (thinning to it lost thin punctuation).
    measurable = stock.cap >= 9

    def fitted(target, probe_ch, letters, grow_x, grow_y):
        """The face at the size, and the horizontal factor, at which `letters`, once made
        `grow_x` and `grow_y` pixels heavier (which widens and heightens them by as much),
        have the original's height (`probe_ch`'s, `target`) and ink widths."""
        pb = probe.getbbox(probe_ch, anchor="ls")
        font = ImageFont.truetype(str(font_path), max(1.0, 400 * (target - grow_y) / (pb[3] - pb[1])))
        ratios = []
        for ch in letters:
            c = ord(ch)
            if c >= stock.numchars or stock.placeholder(c) or c not in cmap:
                continue
            across = stock.span(c, 0)
            drawn = drawn_width(font, ch)
            if across and drawn:
                ratios.append(((across[1] - across[0]) * scale - grow_x) / drawn)
        return font, (statistics.median(ratios) if ratios else 1.0)

    def settled(target, probe_ch, letters):
        """The face, its one horizontal factor (the original's ink widths over the face's,
        median) and how much heavier it is made (the original's strokes against the
        face's): each depends on the others, so they are settled together. Three rounds;
        the changes after the second are below a tenth of a pixel."""
        grow = [0.0, 0.0]
        for _ in range(3):
            font, xs = fitted(target, probe_ch, letters, *grow)
            face_stem, face_bar = face_strokes(font, xs)
            grow = [max(0.0, stock.stroke() * scale - face_stem) if measurable else 0.0,
                    max(0.0, stock.bar() * scale - face_bar) if measurable else 0.0]
        font, xs = fitted(target, probe_ch, letters, *grow)
        return Pen(font, xs, grow)

    # Capitals and digits at the original's capital height. In the menu design the lower
    # case is small capitals, a pen of their own at the original's small-capital height
    # (its x, measured to a fraction of a pixel: the 16 pixel one is 7.47 of 9, Bank
    # Gothic's own 0.83), with their own width factor and weight.
    caps = settled(stock.cap_height * scale, "H", "ABCDEFGHJKLMNPRSTUVWXYZ23456789")
    small_caps = resref in MENU and stock.box(ord("x")) is not None
    lower = settled(stock.small_cap_height() * scale, "x", "abcdefghjkmnprstuvwxyz") if small_caps else caps
    font, xscale = caps.font, caps.xscale
    GROW[0], GROW[1] = caps.grow

    glyph_height = round(stock.height * scale)
    baseline = round(stock.baseline * scale)
    fit_cache = {}
    round_o = None
    # The bold designs only. The light fonts had it for a day; the maintainer saw it too
    # wide there ("It's supposed to be less wide ... light text only", 2026-10-21): their
    # original o is 5 by 6 pixels, and Helvetica's own o, narrowed, is as near as that.
    if resref in BODY and ord("o") in cmap:
        round_o = RoundO(*lower.use())
        caps.use()

    def is_round(c):
        """The original draws this O-shape round. In an anti-aliased font a plain O, o or 0
        is round when the ring fitted to it is (an exponent of 3 or less: the 16 pixel O
        2.2, its 0 6.0); the corner test misses dialogfont10x10b's o, whose top row is
        nearly full but whose fit is 2.1. Accented letters and fonts drawn in whole
        pixels go by the corner test (Stock.round)."""
        if stock.round(c):
            return True
        if not stock.antialiased or chr(c) not in "Oo0":
            return False
        if c not in fit_cache:
            fit_cache[c] = fit_ring(stock, c)
        return fit_cache[c][4] <= 3.0
    cells, widths, report = [], [], {"round": [], "composed": [], "placeholder": [], "missing": [], "fitted": [], "clipped": [], "widened": []}
    for c in range(stock.numchars):
        ch = slot_character(c)
        width = max(1, round(stock.width(c) * scale))
        cell = Image.new("L", (width, glyph_height), 0)
        if resref in GEOMETRIC:
            # Drawn from geometry on the original's own grid (tools/hud_font_geometry.py),
            # each letter's cell the original's at `scale` times, and wider on the right
            # by the outline's width: the original's letters reach their cell's last
            # column (the 4's bar, M, N, W, m, w), which left their ring no room there.
            # The spacing after each letter is that much less (below), so every letter
            # still stands where the original's does (the maintainer, 2026-10-21).
            if resref in OUTLINED:
                width += round(OUTLINED[resref] * scale)
                cell = Image.new("L", (width, glyph_height), 0)
            if ch is not None and ch in hud_font_geometry.GLYPHS:
                cell.paste(hud_font_geometry.mask(ch, scale).crop((0, 0, width, glyph_height)), (0, 0))
            cells.append(cell)
            widths.append(width)
            continue
        if ch is not None and ch != " " and ch != " ":
            placeholder = stock.placeholder(c)
            caps.use()                 # every letter starts from the capitals' pen
            img, base_row = None, 0
            centre = None
            ob = None if placeholder else stock.box(c)
            if ob:
                across = stock.span(c, 0)
                centre = (across[0] + across[1]) / 2 * scale
            if resref in MENU and ch in ROUND_CANDIDATES and is_round(c):
                # Only the menu design: Bank Gothic's O is square where the original's is
                # round. The body faces' O is round already.
                pen = lower if ch.islower() else caps
                pen_font, pen_xscale = pen.use()
                img, base_row, left = round_letter(stock, c, ch, pen_font, cmap, pen_xscale, scale, fit_cache)
                centre = left + img.width / 2      # where the original's ring stands
                report["round"].append(f"{c:02X}")
            elif ch == "¤":
                body = stock.box(c) if not placeholder else None
                w = (body[2] - body[0]) * scale if body else font.size * 0.6
                h = (body[3] - body[1]) * scale if body else stock.cap * scale
                img = currency_sign(w, h, stock.stroke() * scale * 0.5)   # its ring is half the letters' stroke
                base_row = round(((stock.baseline - body[1]) * scale) if body else h)
            elif ch == "ß" and resref in MENU:
                src = references.get("szlig")
                if src is not None:
                    ref_stock, fit = src
                    img, base_row = donor_letter(ref_stock, fit, SZLIG_DONOR, "ß",
                                                 scale * stock.cap_height / ref_stock.cap_height)
            elif ch == "@" and ord("@") in cmap and ob:
                face, row = glyph_ink(font, "@", 1.0)
                tw, th = (ob[2] - ob[0]) * scale, (ob[3] - ob[1]) * scale
                img = face.resize((max(1, round(tw)), max(1, round(th))), Image.LANCZOS)
                base_row = round((stock.baseline - ob[1]) * scale)
            elif small_caps and ch in ("ð", "þ"):
                # ð þ, which the face lacks: its Ð Þ drawn with the small-capital pen.
                pen_font, pen_xscale = lower.use()
                img, base_row = glyph_ink(pen_font, {"ð": "Ð", "þ": "Þ"}[ch], pen_xscale)
                report["composed"].append(f"{c:02X}")
            elif round_o is not None and ch in O_FAMILY and ord(ch) in cmap:
                pen_font, pen_xscale = lower.use()
                img, base_row = round_o_letter(ch, pen_font, pen_xscale, round_o)
                report["widened"].append(f"{c:02X}")
            elif ord(ch) in cmap:
                pen_font, pen_xscale = (lower if ch.islower() else caps).use()
                img, base_row = glyph_ink(pen_font, ch, pen_xscale)
            else:
                pen_font, pen_xscale = (lower if ch.islower() else caps).use()
                img, base_row = compose_missing(ch, pen_font, cmap, pen_xscale, font_path)
                report["composed" if img is not None else "missing"].append(f"{c:02X}")
            if placeholder:
                report["placeholder"].append(f"{c:02X}")
                if img is not None:
                    # No original letter here: the face's own width, a third of its stroke either side.
                    width = img.width + max(2, round(stock.stroke() * scale))
                    cell = Image.new("L", (width, glyph_height), 0)
            if img is not None:
                # What stands above the cell or below it is brought inside, and only that:
                # an accent above the capital line is pressed into the room above it, a
                # tail below the baseline (a cedilla, the underscore) into the room below,
                # and the letter itself keeps its size, as the original's do. A letter
                # wider than its cell is narrowed to it.
                f = 1.0
                cap_px = round(stock.cap * scale)
                above_cap = base_row - cap_px                 # rows above the capital line
                room_cap = baseline - cap_px
                if base_row > baseline and above_cap > 0 and room_cap >= 1:
                    top = img.crop((0, 0, img.width, above_cap)).resize((img.width, room_cap), Image.LANCZOS)
                    rest = img.crop((0, above_cap, img.width, img.height))
                    joined = Image.new("L", (img.width, room_cap + rest.height), 0)
                    joined.paste(top, (0, 0))
                    joined.paste(rest, (0, room_cap))
                    img, base_row, f = joined, cap_px + room_cap, 0.999
                below, room_below = img.height - base_row, glyph_height - baseline
                if below > room_below and room_below >= 1:
                    # A letter wholly below the baseline (the comma, the underscore) starts
                    # `gap` rows under it; its tail is pressed into what is left of the room.
                    split, gap = max(0, base_row), max(0, -base_row)
                    room = room_below - gap
                    if room >= 1:
                        tail = img.crop((0, split, img.width, img.height)).resize((img.width, room), Image.LANCZOS)
                        joined = Image.new("L", (img.width, split + room), 0)
                        if split:
                            joined.paste(img.crop((0, 0, img.width, split)), (0, 0))
                        joined.paste(tail, (0, split))
                        img, f = joined, 0.999
                if base_row > baseline or img.height - base_row > glyph_height - baseline:
                    # No room to press into: the whole letter, about its baseline.
                    g = min(baseline / base_row if base_row > baseline else 1.0,
                            (glyph_height - baseline) / max(1, img.height - base_row)
                            if img.height - base_row > glyph_height - baseline else 1.0)
                    img = img.resize((img.width, max(1, round(img.height * g))), Image.LANCZOS)
                    base_row = round(base_row * g)
                    f = 0.999
                if resref in MENU and not stock.antialiased and ob and not placeholder:
                    # The whole-pixel menu fonts (dialogfont10x10, 10x10a, 16x16a): every
                    # original letter ends one pixel before its cell does, so letters stand
                    # six atlas pixels apart. Bank Gothic's are wider than the original's at
                    # the font's one factor (M 46.5 against 42, W 58.8 against 54), which ate
                    # that gap ("M" and "o" 0.6 apart); a letter is narrowed to the
                    # original's ink width (the maintainer, 2026-10-21: "the same like in the
                    # original").
                    cov = np.asarray(img, dtype=np.float64) / 255.0
                    across = ink_span(cov.max(axis=0))
                    limit = (ob[2] - ob[0]) * scale
                    if across and across[1] - across[0] > limit:
                        img = img.resize((max(1, round(img.width * limit / (across[1] - across[0]))), img.height),
                                         Image.LANCZOS)
                        f = min(f, 0.999)
                if round_o is not None and ch in O_FAMILY and resref != "fnt_console":
                    # The round o about the original's centre, moved in from a side it would
                    # come closer to than O_MIN_GAP, and its cell widened only where it cannot
                    # fit so (the light fonts'). fnt_console's cells are all one width, and
                    # its o fits.
                    cx = centre if centre is not None else width / 2
                    m = O_MIN_GAP * scale
                    half = round_o.width / 2
                    if round_o.width + 2 * m > width:
                        # Widened by as much as the o grew, so it keeps the room it had on
                        # both sides: the light fonts' cells, 36 to 43 at six times.
                        left = cx - round_o.before / 2
                        width = math.ceil(width + round_o.width - round_o.before)
                        cell = Image.new("L", (width, glyph_height), 0)
                        cx = left + half
                    centre = min(max(cx, m + half), width - m - half)
                if img.width > width:
                    img = img.resize((width, img.height), Image.LANCZOS)
                    f = min(f, 0.999)
                if f < 1.0:
                    report["fitted"].append(f"{c:02X}")
                cx = centre if centre is not None else width / 2
                x = min(max(0, round(cx - img.width / 2)), width - img.width)
                y = min(max(0, baseline - base_row), glyph_height - img.height)
                if y != baseline - base_row:
                    report["clipped"].append(f"{c:02X}")
                cell.paste(img, (x, y), img)
        cells.append(cell)
        widths.append(width)

    positions, atlas_size = None, next_power_of_two(max(64, glyph_height))
    while positions is None:
        positions = pack(widths, glyph_height, atlas_size)
        if positions is None:
            atlas_size *= 2
    atlas = Image.new("L", (atlas_size, atlas_size), 0)
    for (x, y), cell in zip(positions, cells):
        atlas.paste(cell, (x, y))
    rgba = Image.new("RGBA", atlas.size, (255, 255, 255, 0))
    rgba.putalpha(atlas)
    if resref in OUTLINED:
        rgba = outlined(cells, positions, atlas_size, OUTLINED[resref] * scale, report)
    output.mkdir(parents=True, exist_ok=True)
    write_tga(output / f"{resref}.tga", atlas_size, atlas_size, rgba.tobytes())

    header = dict(stock.header)
    header["texturewidth"] = f"{atlas_size / 100.0:.6f}"
    header["fontheight"] = f"{glyph_height / 100.0:.6f}"
    # The original's own baselineheight, scaled as Old HD's is: the engine's value, not
    # the row the letters stand on (the 16 pixel menu fonts say 0.16, the cell's height,
    # where H stands on row 14; written as 0.84 until 2026-10-18, which
    # Test-TextOptions.py caught).
    for key in ("baselineheight", "spacingR", "spacingB"):
        if key in header:
            header[key] = f"{float(header[key]) * scale:.6f}"
    if resref in GEOMETRIC and resref in OUTLINED and "spacingR" in header:
        # The cells grew by the outline's width on the right; the spacing gives it back.
        header["spacingR"] = f"{float(header['spacingR']) - round(OUTLINED[resref] * scale) / 100.0:.6f}"
    order = ("mipmap", "filter", "compresstexture", "downsamplemax", "downsamplemin", "numchars", "fontheight",
             "baselineheight", "texturewidth", "spacingR", "spacingB", "caretindent")
    lines = [f"{k} {header[k]}" for k in order if k in header]
    lines.append(f"upperleftcoords {stock.numchars}")
    lines += [f"{x / atlas_size:.6f} {1.0 - y / atlas_size:.6f} 0" for x, y in positions]
    lines.append(f"lowerrightcoords {stock.numchars}")
    lines += [f"{(x + w) / atlas_size:.6f} {1.0 - (y + glyph_height) / atlas_size:.6f} 0"
              for (x, y), w in zip(positions, widths)]
    (output / f"{resref}.txi").write_bytes(("\n".join(lines) + "\n").encode("ascii"))
    if round_o is not None:
        report["round_o"] = (f"{round_o.before:.2f} -> {round_o.width:.2f} x {round_o.height:.2f}, "
                             f"x{round_o.factor:.3f}, sides -{round_o.thin:.2f} px")
    report.update(face=FACES[resref], xscale=round(xscale, 3), cap=stock.cap, atlas=atlas_size,
                  grow=(round(GROW[0], 2), round(GROW[1], 2)),
                  rings={chr(k): f"{2 * r[2]:.2f}x{2 * r[3]:.2f} n {r[4]:.2f} strokes {r[5]:.2f}/{r[6]:.2f}"
                         for k, r in fit_cache.items()})
    return report


# Fonts the original draws with a black outline round every letter, and its width in the
# original's pixels. Measured from the stock atlases: fnt_console's white strokes, two
# pixels wide, stand in a one-pixel black ring that fills the corners too (black, alpha
# 204 to 255); 70% of its ink is that ring. No other text font has one (fnt_galahad14 is
# game art). The HD Original font had none until 2026-10-21, when a player pointed out
# the HUD's numbers need it to read over any map ("This font could really benefit from
# keeping the black border"; the maintainer agreed).
OUTLINED = {"fnt_console": 1.0}

# Fonts whose letters are drawn from geometry rather than a typeface: fnt_console, whose
# original design (an 8 by 16 console font: slab-footed l, i, I and 1, an open 4) no
# typeface has. Helvetica Bold drew it until 2026-10-21 (the maintainer: the 4 and the
# small l did not match the original).
GEOMETRIC = ("fnt_console",)


def outlined(cells, positions, atlas_size, radius, report) -> Image.Image:
    """The atlas with each letter in a black ring `radius` pixels wide: white letters over
    their outline, the outline the letter's coverage spread by a disc with a soft edge.
    Kept inside each letter's own cell, like the original's; how often the ring reaches
    the cell's edge is reported as "outline_clipped"."""
    letters = np.zeros((atlas_size, atlas_size), dtype=np.float64)
    ring = np.zeros((atlas_size, atlas_size), dtype=np.float64)
    reach = int(math.ceil(radius + 1))
    offsets = [(dx, dy, min(1.0, max(0.0, radius + 0.5 - math.hypot(dx, dy))))
               for dy in range(-reach, reach + 1) for dx in range(-reach, reach + 1)]
    offsets = [o for o in offsets if o[2] > 0]
    clipped = 0
    for (x, y), cell in zip(positions, cells):
        cov = np.asarray(cell, dtype=np.float64) / 255.0
        h, w = cov.shape
        if not cov.any():
            continue
        spread = np.zeros_like(cov)
        for dx, dy, weight in offsets:
            shifted = np.zeros_like(cov)
            sx0, sx1 = max(0, dx), min(w, w + dx)
            sy0, sy1 = max(0, dy), min(h, h + dy)
            shifted[sy0:sy1, sx0:sx1] = cov[sy0 - dy:sy1 - dy, sx0 - dx:sx1 - dx]
            np.maximum(spread, shifted * weight, out=spread)
        ink = cov > 0.02
        if ink[:, :reach].any() or ink[:, -reach:].any() or ink[:reach].any() or ink[-reach:].any():
            clipped += 1
        letters[y:y + h, x:x + w] = cov
        ring[y:y + h, x:x + w] = spread
    alpha = letters + ring * (1.0 - letters)
    white = np.divide(letters, alpha, out=np.zeros_like(alpha), where=alpha > 0)
    rgba = np.zeros((atlas_size, atlas_size, 4), dtype=np.uint8)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = np.round(white * 255).astype(np.uint8)
    rgba[..., 3] = np.round(alpha * 255).astype(np.uint8)
    report["outline"] = f"{radius:.1f} px"
    report["outline_clipped"] = clipped
    return Image.fromarray(rgba, "RGBA")


def round_letter(stock, c, ch, font, cmap, xscale, scale, fit_cache):
    """A round O-shape: the original's own ring (fit_ring) at the new size, standing where
    the original's stands in its cell, and the face's own diacritic or bar on it. Returns
    the image, its baseline's row and its left column in the cell.

    The original's O is not a circle: it is a little wider than tall (the 16 pixel O 1.17
    times, its o 1.22) and as tall as the flat letters beside it. Earlier rules, each
    replaced at the maintainer's review on 2026-10-18: the original's whole-pixel box
    (an oval, the o much too wide), then a circle as wide as that box (too large), then a
    circle Helvetica's overshoot taller than the line, its cell narrowed to keep the gaps
    (too round; the maintainer had it copy the original's proportions)."""
    small = ch in "oqòóôõöø"
    plain = ch if ch in "Oo0" else "o" if small else "O"
    pc = ord(plain)
    if pc not in fit_cache:
        fit_cache[pc] = fit_ring(stock, pc)
    ring = fit_cache[pc]
    if small and not stock.antialiased:
        # The whole-pixel menu fonts' o (dialogfont10x10, 10x10a, 16x16a): 6 by 5 with a
        # pixel off each corner. Neither the circle that fits it nor Bank Gothic's box,
        # but a box with rounder corners, outside and inside (the maintainer, 2026-10-21).
        ring = ring[:4] + (WHOLE_PIXEL_O_SQUARENESS,) + ring[5:]
    # An accented letter's body is the plain one's, where its box starts.
    pb, cb = stock.box(pc), stock.box(c)
    ring = (ring[0] + cb[0] - pb[0],) + ring[1:]
    img, left, top = ring_image(ring, scale)
    baseline = round(stock.baseline * scale)
    if ch == plain or ord(ch) not in cmap or pc not in cmap:
        return img, baseline - top, left
    # Diacritic or bar: the face's accented letter less the face's plain one.
    acc, ab = glyph_ink(font, ch, xscale)
    pla, pbase = glyph_ink(font, plain, xscale)
    rise = ab - pbase                               # rows of the accented letter above the plain one's top
    out = Image.new("L", (max(img.width, acc.width), max(img.height + max(0, rise), acc.height)), 0)
    ox = (out.width - img.width) // 2
    out.paste(img, (ox, max(0, rise)))
    # The parts of the accented face letter that are not its plain letter.
    plain_canvas = Image.new("L", acc.size, 0)
    plain_canvas.paste(pla, ((acc.width - pla.width) // 2, max(0, rise)))
    extra = Image.composite(Image.new("L", acc.size, 0), acc, plain_canvas)
    out.paste(255, ((out.width - acc.width) // 2, 0), extra)
    return out, baseline - top + max(0, rise), left - ox


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("originals", type=Path, help="build/native-runtime/original-fonts (kmrfogNN)")
    parser.add_argument("output", type=Path)
    parser.add_argument("--fonts-dir", type=Path, default=ROOT / "build-inputs/local-fonts")
    parser.add_argument("--scale", type=float, default=SCALE)
    parser.add_argument("--fonts", nargs="*", default=list(FACES))
    args = parser.parse_args()
    erf = args.originals
    for face in set(FACES.values()):
        if not (args.fonts_dir / face).is_file():
            raise SystemExit(f"missing face: {args.fonts_dir / face}")
    # The menu design's ß: SZLIG_DONOR's, fitted to the largest original that has a real one.
    references = {}
    for name in ("dialogfont16x16", "dialogfont10x10b", "dialogfont10x10"):
        s = Stock(erf, name)
        if not s.placeholder(0xDF):
            references["szlig"] = (s, fit_donor(s, 0xDF, SZLIG_DONOR))
            break
    for resref in args.fonts:
        if resref not in FACES:
            raise SystemExit(f"{resref} has no face here: the bank build makes it "
                             "(build_original_fonts.enlarged)")
        r = build(erf, resref, args.fonts_dir, args.output, args.scale, references)
        print(f"{resref}: {r['face']}, cap {r['cap']} px, width x{r['xscale']}, atlas {r['atlas']}; "
              f"round {' '.join(r['round']) or '-'} (rings {r['rings'] or '-'}); "
              f"strokes +{r['grow'][0]}/+{r['grow'][1]} px; composed {' '.join(r['composed']) or '-'}; "
              f"placeholders {len(r['placeholder'])}; missing {' '.join(r['missing']) or '-'}; "
              f"fitted {len(r['fitted'])}; off the baseline {' '.join(r['clipped']) or '-'}; "
              f"round o {r.get('round_o', '-')} ({' '.join(r['widened']) or '-'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
