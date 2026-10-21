#!/usr/bin/env python3
"""OTF fonts of the (New) Original HD Font, traced from its atlases.

The maintainer asked on 2026-10-21 for font files "that give exactly this font", made
"from the hd font": every letter here is traced from the atlas the game draws
(assets/hd-original-fonts, six times the original's size), so its shapes, its letter
widths and its baseline are the game's.

  * A letter's coverage is doubled in resolution (bicubic) and cut at half coverage,
    which puts its edge where the anti-aliasing says it lies, to a twelfth of an
    original pixel; potrace makes cubic curves of it.
  * Ten font units are one atlas pixel; the em is the cell's height. The ascent is the
    rows above the baseline (the original's baseline times six, as
    build_hd_original_fonts.py stands the letters on it), the descent the rows below.
  * A letter's advance is its cell's width plus the font's spacingR, as the game sets
    text.
  * Each slot's character is the game's (build_font_from_ttf.slot_character, Windows-1252).
  * One file per different font: the game keeps the same letters under several names
    (the small menu font as dialogfont10x10, 10x10a and 16x16a; the light one three
    times; the dialogue one also as fnt_d10x10b), and those are made once, under the
    name of what they are used for: 11 files for the 17 atlases (the maintainer,
    2026-10-21, asked whether the game has 17 fonts; until then one file each).

fnt_galahad14 is not made: HD Original's is the game's own letters enlarged
(build_original_fonts.enlarged), not a face, and stays out of anything kept or shared.
The fonts are built from the faces' letters, so they stay in build/ and are not
committed, as the faces are not.

Usage:
    python tools/build_hd_original_otf.py [OUT_DIR]      (default build/hd-original-otf)
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import potrace
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_font_from_ttf import slot_character  # noqa: E402
from build_hd_original_fonts import FACES, SCALE, Stock  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ATLASES = ROOT / "assets/hd-original-fonts"
ORIGINALS = ROOT / "build/native-runtime/original-fonts"
UNITS = 10          # font units per atlas pixel
UP = 2              # the coverage's resolution is doubled before it is cut
NAMES = {           # what each font is in the game, for its name
    "dialogfont10x10": "Menu Small", "dialogfont10x10a": "Menu Small A", "dialogfont10x10b": "Menu Small B",
    "dialogfont12x16": "Menu Medium", "dialogfont16x16": "Menu", "dialogfont16x16a": "Menu A",
    "dialogfont16x16b": "Menu B", "dialogfont32x32": "Menu Large", "fnt_d16x16": "Dialogue",
    "fnt_d16x16b": "Descriptions", "fnt_d10x10b": "Small Bold", "fnt_credits": "Credits",
    "fnt_creditsb": "Credits Bold", "fnt_console": "Console", "fnt_creditsa": "Light",
    "fnt_d16x16a": "Light", "fnt_dialog16x16": "Dialog Light"}


# The order the fonts are made in: the first of several with the same letters names the file.
ORDER = ("dialogfont10x10", "dialogfont10x10a", "dialogfont16x16a", "dialogfont10x10b", "dialogfont12x16",
         "dialogfont16x16", "dialogfont16x16b", "dialogfont32x32", "fnt_d16x16", "fnt_d10x10b", "fnt_d16x16b",
         "fnt_credits", "fnt_creditsb", "fnt_console", "fnt_d16x16a", "fnt_creditsa", "fnt_dialog16x16")


def letters(resref: str) -> str:
    """What makes two atlases the same font: every cell's pixels and size, the height and
    the spacing (not how the atlas is packed)."""
    head, cells = read_txi(ATLASES / f"{resref}.txi")
    im = np.asarray(Image.open(ATLASES / f"{resref}.tga").convert("RGBA"))[..., 3]
    H, W = im.shape
    h = hashlib.sha256(repr((head.get("fontheight"), head.get("spacingR"), len(cells))).encode())
    for x0, y0, x1, y1 in cells:
        cell = im[round((1 - y0) * H):round((1 - y1) * H), round(x0 * W):round(x1 * W)]
        h.update(repr(cell.shape).encode())
        h.update(cell.tobytes())
    return h.hexdigest()


def read_txi(path: Path):
    text = path.read_text(encoding="latin-1").replace("\r", "")
    lines = [l.split() for l in text.splitlines() if l.strip()]
    head = {l[0]: float(l[1]) for l in lines if len(l) == 2 and re.match(r"[-\d.]+$", l[1])}
    up = next(i for i, l in enumerate(lines) if l[0] == "upperleftcoords")
    lo = next(i for i, l in enumerate(lines) if l[0] == "lowerrightcoords")
    n = int(head["numchars"])
    cells = [tuple(map(float, lines[up + 1 + c][:2])) + tuple(map(float, lines[lo + 1 + c][:2])) for c in range(n)]
    return head, cells


def trace(cov: np.ndarray, baseline: int, pen):
    """Draws the cell's ink into `pen`, in font units, the baseline at zero."""
    h, w = cov.shape
    big = np.asarray(Image.fromarray((cov * 255).astype(np.uint8), "L").resize((w * UP, h * UP), Image.BICUBIC),
                     dtype=np.float64) / 255.0
    # potracer traces the False pixels as the shape: ink is False here.
    bitmap = potrace.Bitmap(big < 0.5)
    try:
        path = bitmap.trace(turdsize=2, alphamax=1.0, opticurve=True, opttolerance=0.2)
    except ValueError:
        # potracer's curve joining takes a square root of a negative on some shapes
        # (opti_penalty); those letters keep their curves unjoined.
        path = potrace.Bitmap(big < 0.5).trace(turdsize=2, alphamax=1.0, opticurve=False)

    def pt(p):
        return (round(p.x / UP * UNITS), round((baseline - p.y / UP) * UNITS))

    for curve in path:
        pen.moveTo(pt(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner:
                pen.lineTo(pt(seg.c))
                pen.lineTo(pt(seg.end_point))
            else:
                pen.curveTo(pt(seg.c1), pt(seg.c2), pt(seg.end_point))
        pen.closePath()


def build(resref: str, out: Path) -> Path:
    head, cells = read_txi(ATLASES / f"{resref}.txi")
    atlas = np.asarray(Image.open(ATLASES / f"{resref}.tga").convert("RGBA"), dtype=np.float64)[..., 3] / 255.0
    H, W = atlas.shape
    stock = Stock(ORIGINALS, resref)
    cell_h = round(head["fontheight"] * 100)
    baseline = round(stock.baseline * SCALE)
    spacing = head.get("spacingR", 0.0) * 100
    names, glyphs, widths, cmap = [".notdef", "space"], {}, {}, {0x20: "space"}
    empty = T2CharStringPen(0, None)
    glyphs[".notdef"], widths[".notdef"] = empty.getCharString(), (round(cell_h * UNITS / 2), 0)
    space_w = cells[0x20][2] - cells[0x20][0] if len(cells) > 0x20 else 0.3
    glyphs["space"], widths["space"] = T2CharStringPen(0, None).getCharString(), (
        round((space_w * W + spacing) * UNITS), 0)
    for c, (x0, y0, x1, y1) in enumerate(cells):
        ch = slot_character(c)
        if ch is None or ch in (" ", " ") or ord(ch) in cmap:
            continue
        l, t, r, b = round(x0 * W), round((1 - y0) * H), round(x1 * W), round((1 - y1) * H)
        if r <= l or b <= t:
            continue
        advance = round((r - l + spacing) * UNITS)
        pen = T2CharStringPen(advance, None)
        cov = atlas[t:b, l:r]
        if cov.max() > 0.5:
            trace(cov, baseline, pen)
        name = f"uni{ord(ch):04X}"
        names.append(name)
        glyphs[name], widths[name] = pen.getCharString(), (advance, 0)
        cmap[ord(ch)] = name
    family = f"KMRP Original HD {NAMES[resref]}"
    fb = FontBuilder(cell_h * UNITS, isTTF=False)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    fb.setupCFF(family.replace(" ", ""), {"FullName": family}, glyphs, {})
    fb.setupHorizontalMetrics(widths)
    ascent, descent = baseline * UNITS, (cell_h - baseline) * UNITS
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent)
    fb.setupNameTable({"familyName": family, "styleName": "Regular",
                       "uniqueFontIdentifier": f"KMRP;{family.replace(' ', '')};{resref}",
                       "version": "Version 1.600",
                       "description": f"KMRP's (New) Original HD Font, {resref}, traced from the game's atlas"})
    fb.setupOS2(sTypoAscender=ascent, sTypoDescender=-descent, sTypoLineGap=0, usWinAscent=ascent,
                usWinDescent=descent, achVendID="KMRP")
    fb.setupPost()
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"KMRP-OriginalHD-{NAMES[resref].replace(' ', '')}.otf"
    fb.save(str(path))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, nargs="?", default=ROOT / "build/hd-original-otf")
    parser.add_argument("--fonts", nargs="*", default=list(ORDER))
    args = parser.parse_args()
    assert set(ORDER) == set(FACES)
    made = {}
    for resref in args.fonts:
        key = letters(resref)
        if key in made:
            print(f"{resref}: the same letters as {made[key]}")
            continue
        made[key] = resref
        path = build(resref, args.out)
        print(f"{resref}: {path.name}, {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
