"""Finishes the redrawn fonts into release files, following the OpenType recommendations
for CFF fonts (Microsoft's "Recommendations for OpenType Fonts", Adobe's AFDKO, the
font-production practice fontbakery checks):

  * 1000 units per em and the CFF FontMatrix exactly 1/1000. Windows' CFF rasteriser
    left W, w and @ blank at 7680 (found 2026-10-22), and much software assumes 1000.
  * Outer contours counter-clockwise (the PostScript convention), overlaps removed.
  * Production glyph names (A, a, eacute: the Adobe Glyph List), .notdef a visible box.
  * The PostScript name (name ID 6, as the CFF's own font name); Windows will not load a
    CFF font without it. fsSelection: Regular, USE_TYPO_METRICS.
  * Vertical metrics: hhea, typo and win the same where they can be; win ascent and
    descent at least the font's highest and lowest points, as Windows clips beyond them.
  * The licence in the name table: SIL Open Font License 1.1.
  * Hinted (Adobe otfautohint, alignment zones and stems measured from the letters),
    then subroutinised (cffsubr).

    python finish.py [SOURCE_DIR]    reads SOURCE_DIR/*.otf (default build/fonts/redrawn),
                                     writes fonts/otf
"""
import json
import os
import shutil
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import cffsubr
import freetype
import numpy as np
from fontTools.agl import UV2AGL
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.removeOverlaps import removeOverlaps

import atlasref

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NEW, FINAL = ROOT / "build/fonts/redrawn", ROOT / "fonts/otf"
# Written here first and copied into FINAL when all are done (a font open in a viewer is
# locked on Windows; the copy says which).
STAGE = ROOT / "build/fonts/final"
# Adobe's otfautohint (pip install afdko; it needs a Python AFDKO has wheels for).
AUTOHINT = os.environ.get("OTFAUTOHINT") or shutil.which("otfautohint") or "otfautohint"
UPM = 1000
COPYRIGHT = "Copyright 2026 RaymanGT (https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch)"
LICENSE = ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
           "This license is available with a FAQ at: https://openfontlicense.org")
LICENSE_URL = "https://openfontlicense.org"
VENDOR_URL = "https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch"


# Glyphs drawn as a plain bar instead of what the atlas shows, in units of 1000:
# (left, bottom, right, top). MenuSmall's underscore sits on the very bottom edge of its
# atlas cell, which cuts it to an 11-unit sliver (0.18 px at 16 px, which TrueType hinting
# rounds away); drawn here 38 units thick, as the Menu font's, on the same bottom line.
BARS = {("KMRP-OriginalHD-MenuSmall", 0x5F): (21, -197, 515, -159)}


def glyph_name(uv):
    """The Adobe Glyph List name of a character, else uniXXXX."""
    return UV2AGL.get(uv, f"uni{uv:04X}")


def contours(rec):
    """A RecordingPen value split into its contours."""
    out, cur = [], []
    for op, args in rec:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            out.append(cur)
            cur = []
    return out


def built_ydieresis(gs, cmap, k):
    """ÿ made from the font's own y and the two dots of its ä, the dots centred over
    the y as they are over the a: for the fonts whose atlas has no ÿ (the game's Light
    and Menu Large fonts have fewer characters)."""
    from fontTools.pens.boundsPen import BoundsPen as BP
    y, a_uml, a = cmap.get(0x79), cmap.get(0xE4), cmap.get(0x61)
    if not (y and a_uml and a):
        return None

    def rec_of(g):
        r = RecordingPen()
        gs[g].draw(TransformPen(r, (k, 0, 0, k, 0, 0)))
        return r.value

    def box(rv):
        bp = BP(None)
        for op, args in rv:
            getattr(bp, op)(*args)
        return bp.bounds

    a_box = box(rec_of(a))
    # The dots: the contours of ä that lie wholly above the a.
    dots = [c for c in contours(rec_of(a_uml)) if box(c) and box(c)[1] > a_box[3]]
    if not dots:
        return None
    y_rec = rec_of(y)
    dx = (box(y_rec)[0] + box(y_rec)[2]) / 2 - (a_box[0] + a_box[2]) / 2
    out = list(y_rec)
    for c in dots:
        out += [(op, tuple((x + dx, yy) for x, yy in args)) for op, args in c]
    return out


def signed_area(rec):
    """Signed area of each contour of a RecordingPen value (on-curve points only, enough
    to tell the direction of a closed outline)."""
    areas, pts = [], []
    for op, args in rec:
        if op == "moveTo":
            pts = [args[0]]
        elif op in ("lineTo", "curveTo", "qCurveTo"):
            pts.append(args[-1])
        elif op in ("closePath", "endPath"):
            if len(pts) > 2:
                p = np.array(pts, float)
                areas.append(0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])))
            pts = []
    return areas


def rebuild(src: Path) -> TTFont:
    """The font at 1000 units per em, with production names and full tables; outlines
    unhinted (hinting follows)."""
    font = TTFont(src)
    k = UPM / font["head"].unitsPerEm
    gs, cmap, hm = font.getGlyphSet(), font.getBestCmap(), font["hmtx"].metrics
    rev = {g: uv for uv, g in cmap.items()}
    names = {".notdef": ".notdef"}
    for g in font.getGlyphOrder():
        if g in rev:
            names[g] = "space" if rev[g] == 0x20 else glyph_name(rev[g])
    order = [names[g] for g in font.getGlyphOrder() if g in names]
    extra = {}
    if 0xFF not in cmap:
        built = built_ydieresis(gs, cmap, k)
        if built:
            extra["ydieresis"] = (built, round(hm[cmap[0x79]][0] * k))
            order.append("ydieresis")
    charstrings, widths = {}, {}
    hh = font["hhea"]
    ascent, descent = round(hh.ascent * k), round(-hh.descent * k)
    # One width for every character (Console, the HUD's font): monospaced.
    advs = {round(hm[g][0] * k) for g in names if g != ".notdef" and hm[g][0] > 0}
    mono = advs.pop() if len(advs) == 1 else None
    for old, new in names.items():
        adv = round(hm[old][0] * k)
        pen = T2CharStringPen(adv, None)
        if old == ".notdef":
            # A visible box: a rectangle with a rectangular hole, half an em wide.
            w = mono or (adv if adv > 0 else UPM // 2)
            m, t = round(w * 0.1), round(UPM * 0.05)
            top = round(ascent * 0.9)
            for (x0, y0, x1, y1), ccw in (((m, 0, w - m, top), True), ((m + t, t, w - m - t, top - t), False)):
                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)] if ccw else [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
                pen.moveTo(pts[0])
                for p in pts[1:]:
                    pen.lineTo(p)
                pen.closePath()
            widths[new] = (w, 0)
        elif (src.stem, rev.get(old)) in BARS:
            x0, y0, x1, y1 = BARS[(src.stem, rev[old])]
            pen.moveTo((x0, y0))
            for p in ((x1, y0), (x1, y1), (x0, y1)):
                pen.lineTo(p)
            pen.closePath()
            widths[new] = (adv, 0)
        else:
            rec = RecordingPen()
            gs[old].draw(TransformPen(rec, (k, 0, 0, k, 0, 0)))
            # PostScript outlines run counter-clockwise outside, clockwise in the holes;
            # the redraw kept the tracing's opposite convention.
            areas = signed_area(rec.value)
            if areas and areas[int(np.argmax(np.abs(areas)))] < 0:
                rec2 = RecordingPen()
                rec.replay(ReverseContourPen(rec2))
                rec = rec2
            rounded = RecordingPen()
            for op, args in rec.value:
                getattr(rounded, op)(*[(round(x), round(y)) for x, y in args])
            rounded.replay(pen)
            widths[new] = (adv, 0)
        charstrings[new] = pen.getCharString()
    for new, (rv, adv) in extra.items():
        pen = T2CharStringPen(adv, None)
        rounded = RecordingPen()
        for op, args in rv:
            getattr(rounded, op)(*[(round(x), round(y)) for x, y in args])
        if signed_area(rounded.value) and max(signed_area(rounded.value), key=abs) < 0:
            r2 = RecordingPen()
            rounded.replay(ReverseContourPen(r2))
            rounded = r2
        rounded.replay(pen)
        charstrings[new] = pen.getCharString()
        widths[new] = (adv, 0)
    old_names = font["name"]
    family = old_names.getDebugName(1)
    ps = family.replace(" ", "")
    fb = FontBuilder(UPM, isTTF=False)
    fb.setupGlyphOrder(order)
    char_map = {uv: names[g] for uv, g in cmap.items()}
    if "ydieresis" in extra:
        char_map[0xFF] = "ydieresis"
    char_map.setdefault(0xA0, "space")                  # the no-break space: a space
    fb.setupCharacterMap(char_map)
    fb.setupCFF(ps, {"FullName": family, "FamilyName": family, "Weight": "Regular", "Notice": COPYRIGHT},
                charstrings, {})
    fb.setupHorizontalMetrics(widths)
    # The font's own extremes: Windows clips what reaches beyond the win metrics.
    y_max, y_min = 0, 0
    bp_set = fb.font.getGlyphSet()
    for g in order:
        bp = BoundsPen(bp_set)
        bp_set[g].draw(bp)
        if bp.bounds:
            y_min, y_max = min(y_min, bp.bounds[1]), max(y_max, bp.bounds[3])
    win_ascent, win_descent = max(ascent, int(np.ceil(y_max))), max(descent, int(np.ceil(-y_min)))
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent, lineGap=0)
    fb.setupNameTable({
        "copyright": COPYRIGHT, "familyName": family, "styleName": "Regular",
        "uniqueFontIdentifier": f"1.600;KMRP;{ps}", "fullName": family, "version": "Version 1.600",
        "psName": ps, "designer": "RaymanGT", "manufacturer": "KMRP",
        "description": f"{family}: KOTOR's font redrawn in high resolution for KMRP as lines, corners and arcs",
        "vendorURL": VENDOR_URL, "designerURL": VENDOR_URL,
        "licenseDescription": LICENSE, "licenseInfoURL": LICENSE_URL,
    }, mac=False)                                        # Windows names only, as current practice
    fb.setupOS2(version=4, achVendID="KMRP", usWeightClass=400, usWidthClass=5,
                fsSelection=0x40 | 0x80,                 # REGULAR, USE_TYPO_METRICS
                fsType=0,                                # installable: no embedding restrictions
                sTypoAscender=ascent, sTypoDescender=-descent, sTypoLineGap=0,
                usWinAscent=win_ascent, usWinDescent=win_descent)
    fb.setupPost()
    fb.font["head"].fontRevision = 1.6
    font = fb.font
    # One width for every character (Console, the HUD's font): declared monospaced, and
    # .notdef given that width too.
    if mono:
        font["post"].isFixedPitch = 1
        font["OS/2"].panose.bFamilyType = 2              # Latin text
        font["OS/2"].panose.bProportion = 9              # monospaced
    font["OS/2"].recalcUnicodeRanges(font)
    font["OS/2"].recalcCodePageRanges(font)
    font["CFF "].cff.topDictIndex[0].FontMatrix = [0.001, 0, 0, 0.001, 0, 0]
    return font


def bounds(font, ch):
    g = font.getBestCmap().get(ord(ch))
    if g is None:
        return None
    bp = BoundsPen(font.getGlyphSet())
    font.getGlyphSet()[g].draw(bp)
    return bp.bounds


def ink_runs(font, ch, at, vertical=False):
    """Lengths of the ink runs where a horizontal line at height `at` (or a vertical
    line at x = `at`) crosses the glyph."""
    from run import flatten
    g = font.getBestCmap().get(ord(ch))
    if g is None:
        return []
    rp = RecordingPen()
    font.getGlyphSet()[g].draw(rp)
    xs = []
    for poly in flatten(rp.value, 0.5):
        q = np.vstack([poly, poly[:1]])
        a_, b_ = (q[:, 0], q[:, 1]) if vertical else (q[:, 1], q[:, 0])
        for i in range(len(q) - 1):
            if (a_[i] - at) * (a_[i + 1] - at) < 0:
                t = (at - a_[i]) / (a_[i + 1] - a_[i])
                xs.append(b_[i] + t * (b_[i + 1] - b_[i]))
    xs.sort()
    return [xs[i + 1] - xs[i] for i in range(0, len(xs) - 1, 2)]


def set_zones(font):
    """Alignment zones and stems for hinting, measured from the font's own letters:
    the baseline (and how far round letters dip below it), the x-height and the cap
    height (and how far round letters rise above them), the descender."""
    zones = []
    H, x, O, o, p = (bounds(font, c) for c in "HxOop")
    base_over = min(v[1] for v in (O, o) if v) if (O or o) else -10
    zones += [min(int(np.floor(base_over)), -1), 0]
    if x:
        xo = o[3] if o else x[3] + 10
        zones += [int(round(x[3])), int(round(max(xo, x[3] + 1)))]
    if H:
        co = O[3] if O else H[3] + 10
        zones += [int(round(H[3])), int(round(max(co, H[3] + 1)))]
    priv = font["CFF "].cff.topDictIndex[0].Private
    priv.BlueValues = zones
    if p:
        q = bounds(font, "q") or p
        priv.OtherBlues = [int(round(min(p[1], q[1]))) - 1, int(round(max(p[1], q[1])))]
    if H:
        v = ink_runs(font, "H", (H[1] + H[3]) / 2 + (H[3] - H[1]) * 0.2)
        if v:
            priv.StdVW = int(round(float(np.median(v))))
        hz = ink_runs(font, "H", (H[0] + H[2]) / 2, vertical=True)
        if hz:
            priv.StdHW = int(round(min(hz)))


def finish(src: Path) -> Path:
    STAGE.mkdir(parents=True, exist_ok=True)
    font = rebuild(src)
    removeOverlaps(font)
    set_zones(font)
    tmp = STAGE / f"{src.stem}.unhinted.otf"
    font.save(tmp)
    out = STAGE / src.name
    r = subprocess.run([str(AUTOHINT), str(tmp), "-o", str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit(f"otfautohint failed on {src.name}")
    font = TTFont(out)
    cffsubr.subroutinize(font)
    font.save(out)
    tmp.unlink()
    return out


def ft_compare(args):
    """FreeType's rendering of each glyph at the atlas's own size against the atlas."""
    path, stem = args
    face = freetype.Face(str(path))
    cells = atlasref.cells(stem)
    any_cell = next(iter(cells.values()))[0]
    px_per_em = any_cell.shape[0]                 # the em is the cell's height
    face.set_char_size(int(round(px_per_em * 64)), 0, 72, 72)
    diffs = []
    for name, (cell, base) in cells.items():
        ch = chr(int(name[3:], 16))
        if face.get_char_index(ch) == 0:
            continue
        face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_TARGET_NORMAL)
        g = face.glyph
        bm = g.bitmap
        if bm.width == 0 or bm.rows == 0:
            continue
        img = np.array(bm.buffer, dtype=np.float64).reshape(bm.rows, bm.pitch)[:, :bm.width] / 255.0
        h, w = cell.shape
        canvas = np.zeros((h + 40, w + 40))
        top = base - g.bitmap_top + 20
        left = g.bitmap_left + 20
        y0, x0 = max(top, 0), max(left, 0)
        y1, x1 = min(top + bm.rows, canvas.shape[0]), min(left + bm.width, canvas.shape[1])
        if y1 > y0 and x1 > x0:
            canvas[y0:y1, x0:x1] = img[y0 - top:y1 - top, x0 - left:x1 - left]
        ft = canvas[20:20 + h, 20:20 + w]
        ink = cell > 0.02
        if ink.any():
            diffs.append((name, float(np.abs(ft - cell)[ink].mean()), float(np.abs(ft - cell).max())))
    return stem, diffs


if __name__ == "__main__":
    src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else NEW
    outs = []
    for f in sorted(src_dir.glob("*.otf")):
        out = finish(f)
        t = TTFont(out)
        print(f"{out.name}: {out.stat().st_size:,} bytes, {len(t.getGlyphOrder())} glyphs, units per em {t['head'].unitsPerEm}")
        outs.append((out, f.stem))
    FINAL.mkdir(parents=True, exist_ok=True)
    for out, _ in outs:
        try:
            shutil.copyfile(out, FINAL / out.name)
        except PermissionError:
            print(f"{out.name}: could not be copied into {FINAL} (open in a font viewer?)")
    with Pool(11) as pool:
        res = pool.map(ft_compare, outs)
    for stem, diffs in res:
        m = np.mean([d[1] for d in diffs])
        print(f"FreeType vs HD atlas, {stem.split('-')[-1]:13} mean {m * 100:.2f}%")
