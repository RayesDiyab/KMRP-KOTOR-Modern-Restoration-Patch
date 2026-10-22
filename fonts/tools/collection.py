"""All 11 fonts in one TrueType collection: fonts/KMRP-OriginalHD.ttc.

Each finished OTF (fonts/otf) is converted to TrueType outlines: its cubic curves made
quadratic within MAX_ERR units of 1000 (fontTools' cu2qu), contours turned clockwise
outside as TrueType expects, a glyf/loca table instead of CFF; then hinted with
ttfautohint and gathered into one .ttc, the tables they share stored once. A collection
installs all 11 fonts in one go on Windows, macOS and Linux.

    python collection.py
"""
import ctypes
import sys
from pathlib import Path

import ttfautohint
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.ttCollection import TTCollection

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OTF = ROOT / "build/fonts/final"      # the finished OTFs (finish.py)
STAGE = ROOT / "build/fonts/ttf"
OUT = ROOT / "fonts/KMRP-OriginalHD.ttc"
MAX_ERR = 0.5          # font units of 1000: how far a quadratic curve may stray from the cubic


def to_truetype(otf: Path) -> TTFont:
    font = TTFont(otf)
    order = font.getGlyphOrder()
    gs = font.getGlyphSet()
    glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = {}
    for g in order:
        pen = TTGlyphPen(None)
        # PostScript outlines run counter-clockwise outside; TrueType's clockwise.
        gs[g].draw(Cu2QuPen(pen, MAX_ERR, reverse_direction=True))
        glyf.glyphs[g] = pen.glyph()
    del font["CFF "]
    if "VORG" in font:
        del font["VORG"]
    font["glyf"] = glyf
    font["loca"] = newTable("loca")
    font["maxp"] = newTable("maxp")
    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    for k in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
              "maxStackElements", "maxSizeOfInstructions", "maxComponentElements"):
        setattr(maxp, k, 0)
    maxp.maxZones = 1
    font["head"].glyphDataFormat = 0
    font["head"].indexToLocFormat = 0
    post = font["post"]
    post.formatType = 2.0
    post.extraNames = []
    post.mapping = {}
    post.glyphOrder = order
    font.sfntVersion = "\x00\x01\x00\x00"
    # Bounds, and each glyph's left side bearing as its leftmost point (TrueType's rule).
    hmtx = font["hmtx"].metrics
    for g in order:
        glyph = glyf.glyphs[g]
        glyph.recalcBounds(glyf)
        hmtx[g] = (hmtx[g][0], getattr(glyph, "xMin", 0))
    font["maxp"].recalc(font)
    return font


def main() -> int:
    STAGE.mkdir(parents=True, exist_ok=True)
    hinted = []
    for otf in sorted(OTF.glob("*.otf")):
        raw = STAGE / f"{otf.stem}.unhinted.ttf"
        to_truetype(otf).save(raw)
        out = STAGE / f"{otf.stem}.ttf"
        ttfautohint.ttfautohint(in_file=str(raw), out_file=str(out), hinting_range_min=8, hinting_range_max=50,
                                increase_x_height=14, windows_compatibility=True)
        raw.unlink()
        t = TTFont(out)
        t["head"].flags |= 1 << 3        # hinted: sizes in whole pixels (ttfautohint leaves it)
        t.save(out)
        hinted.append(out)
        print(f"{out.name}: {out.stat().st_size:,} bytes")
    c = TTCollection()
    c.fonts = [TTFont(p) for p in hinted]
    c.save(OUT, shareTables=True)
    n = 0
    if sys.platform == "win32":
        gdi = ctypes.windll.gdi32
        n = gdi.AddFontResourceExW(str(OUT), 0x10, 0)
        if n:
            gdi.RemoveFontResourceExW(str(OUT), 0x10, 0)
    print(f"{OUT}: {OUT.stat().st_size:,} bytes, {len(c.fonts)} fonts" + (f"; Windows loads {n}" if sys.platform == "win32" else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
