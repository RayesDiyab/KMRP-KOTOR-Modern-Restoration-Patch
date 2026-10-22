#!/usr/bin/env python3
"""OTF fonts of the (New) Original HD Font, traced from its atlases.

Superseded on 2026-10-22 by the KMRP Original HD fonts in fonts/otf (fonts/README.md),
redrawn as lines, corners and arcs, from which tools/build_hd_original_atlases.py now
draws the atlases. Kept as the record of the first OTFs; fonts/tools reads them for
their metrics and names.

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
  * The letters alone: the black outline the game draws round the HUD font's letters is
    not in its file; the KMRP Font Converter adds it to whatever font makes the HUD's.
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
    python tools/build_hd_original_otf.py [OUT_DIR]      (default build/fonts/KMRP-OriginalHD-OTF)

The fonts and a README.txt of which file is for which text go into OUT_DIR, and both into
a zip beside it (build/fonts/KMRP-OriginalHD-OTF.zip).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
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
    # The letters' own coverage, their brightness times opacity: the HUD font's atlas has
    # a black outline round each letter (2026-10-21), which is the game's drawing of it,
    # not part of the letter. In every other atlas the letters are white, so this is
    # their opacity.
    rgba = np.asarray(Image.open(ATLASES / f"{resref}.tga").convert("RGBA"), dtype=np.float64) / 255.0
    atlas = rgba[..., :3].mean(axis=2) * rgba[..., 3]
    # The letters only: the HUD's black ring is the game's drawing of them, which the KMRP
    # Font Converter adds when it makes the game's HUD font (the maintainer, 2026-10-21).
    H, W = atlas.shape
    stock = Stock(ORIGINALS, resref)
    cell_h = round(head["fontheight"] * 100)
    baseline = round(stock.baseline * SCALE)
    spacing = head.get("spacingR", 0.0) * 100
    names, glyphs, widths, cmap = [".notdef", "space"], {}, {}, {0x20: "space"}
    # Each empty glyph's charstring carries its advance too, as the letters' do: browsers
    # read it there, and a zero closed up every word space (found 2026-10-21).
    notdef_w = round(cell_h * UNITS / 2)
    glyphs[".notdef"], widths[".notdef"] = T2CharStringPen(notdef_w, None).getCharString(), (notdef_w, 0)
    space_w = cells[0x20][2] - cells[0x20][0] if len(cells) > 0x20 else 0.3
    space_adv = round((space_w * W + spacing) * UNITS)
    glyphs["space"], widths["space"] = T2CharStringPen(space_adv, None).getCharString(), (space_adv, 0)
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


# What each file is for in the game, for README.txt: the text it draws, and the game's
# fonts that hold the same letters.
USES = {
    "Menu": ("Screen titles and menu buttons", "dialogfont16x16, dialogfont16x16b"),
    "MenuSmall": ("Option lists and small labels in menus", "dialogfont10x10, dialogfont10x10a, dialogfont16x16a"),
    "MenuSmallB": ("Tabs and small bold labels in menus", "dialogfont10x10b"),
    "MenuMedium": ("Save and load lists, mid-size menu text", "dialogfont12x16"),
    "MenuLarge": ("The largest headings", "dialogfont32x32"),
    "Dialogue": ("What people say in conversations, and subtitles", "fnt_d16x16, fnt_d10x10b"),
    "Descriptions": ("Your reply choices, and item, skill and power descriptions", "fnt_d16x16b"),
    "Light": ("The journal and other longer reading", "fnt_d16x16a, fnt_creditsa, fnt_dialog16x16"),
    "Console": ("The HUD: credits, level and XP numbers in play", "fnt_console"),
    "Credits": ("Job titles in the end credits", "fnt_credits"),
    "CreditsBold": ("Names in the end credits", "fnt_creditsb"),
}


def readme(out: Path) -> Path:
    """README.txt beside the fonts: which file is for which text."""
    lines = ["KMRP 1.6, (New) Original HD Font, as OTF files", "",
             "KOTOR's own fonts redrawn in high resolution for KMRP, traced from the files the game",
             "draws. One file for each different font the game uses:", ""]
    width = max(len(f"KMRP-OriginalHD-{k}.otf") for k in USES)
    for key, (use, games) in USES.items():
        lines.append(f"  {f'KMRP-OriginalHD-{key}.otf'.ljust(width)}  {use}")
        lines.append(f"  {''.ljust(width)}  (in the game: {games})")
    lines += ["",
              "The game draws the HUD's numbers with a black outline. That outline is not in these",
              "files: the KMRP Font Converter adds it when it turns a font into the game's HUD font.", "",
              "Letter widths, spacing and the baseline are the game's, so text set in these fonts lines",
              "up as it does in KOTOR.", "",
              "https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch", ""]
    path = out / "README.txt"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\r\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, nargs="?", default=ROOT / "build/fonts/KMRP-OriginalHD-OTF")
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
    # The fonts and their README in one zip beside the folder.
    notes = readme(args.out)
    archive = args.out.parent / f"{args.out.name}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(notes, notes.name)
        for font in sorted(args.out.glob("*.otf")):
            zf.write(font, font.name)
    print(f"{archive}: {archive.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
