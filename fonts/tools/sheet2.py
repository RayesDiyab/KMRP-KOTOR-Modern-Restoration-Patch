"""Comparison sheets for the redraw.

  sheets2/<font>.png   every glyph: the HD atlas (what the game draws), the old OTF, the new
                       OTF, at the same size, exact area coverage
  sheets2/closeup.png  chosen letters large: the old outline (orange) and the new one
                       (cyan) over the HD atlas

    python sheet2.py [font names...]
"""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

import area
import atlasref
from finish import FINAL
from run import NEW, OLD, flatten

HERE = Path(__file__).resolve().parent
OUT = NEW / "sheets"
CELL = 80
COLS = 16
INK = np.array([0.93, 0.95, 1.0])
BG = np.array([0.06, 0.08, 0.11])


def font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def atlas_image(cell, base, x0, y0, w, h, s):
    """The atlas cell resampled onto the glyph's grid (x0, y0 top left in units, s px per unit)."""
    ch, cw = cell.shape
    big = Image.fromarray((cell * 255).astype(np.uint8)).resize((max(1, round(cw * 10 * s)), max(1, round(ch * 10 * s))), Image.BOX)
    out = np.zeros((h, w))
    ox, oy = round((0 - x0) * s), round((y0 - base * 10) * s)
    b = np.asarray(big, dtype=np.float64) / 255
    ya, xa = max(oy, 0), max(ox, 0)
    yb, xb = min(oy + b.shape[0], h), min(ox + b.shape[1], w)
    if yb > ya and xb > xa:
        out[ya:yb, xa:xb] = b[ya - oy:yb - oy, xa - ox:xb - ox]
    return out


def glyph_images(args):
    stem, name, rec_old, rec_new, uo, un, asc, desc, adv = args
    s = CELL / uo
    w = max(8, int(np.ceil(adv * s)) + 8)
    h = int(np.ceil((asc - desc) * s)) + 8
    x0, y0 = -4 / s, asc + 4 / s
    ref = atlasref.cells(stem).get(name)
    at = atlas_image(*ref, x0, y0, w, h, s) if ref else np.zeros((h, w))
    a = area.coverage(flatten(rec_old, 0.5), x0, y0, w, h, s) if rec_old else np.zeros((h, w))
    polys = [p * (uo / un) for p in flatten(rec_new, 0.5 * un / uo)] if rec_new else []
    b = area.coverage(polys, x0, y0, w, h, s) if polys else np.zeros((h, w))
    return at, a, b


def load(stem):
    fo, fn = TTFont(OLD / f"{stem}.otf"), TTFont(FINAL / f"{stem}.otf")
    return fo, fn


def sheet(stem):
    fo, fn = load(stem)
    go, gn = fo.getGlyphSet(), fn.getGlyphSet()
    uo, un = fo["head"].unitsPerEm, fn["head"].unitsPerEm
    asc, desc = fo["hhea"].ascent, fo["hhea"].descent
    names = [g for g in fo.getGlyphOrder() if g not in (".notdef", "space")]
    by_char = {g: u for u, g in fo.getBestCmap().items()}
    ncm = fn.getBestCmap()
    names = [g for g in names if by_char.get(g) in ncm]
    nmap = {g: ncm[by_char[g]] for g in names}       # old glyph name -> new (production names)
    jobs = []
    for g in names:
        po, pn = RecordingPen(), RecordingPen()
        go[g].draw(po)
        gn[nmap[g]].draw(pn)
        jobs.append((stem, g, po.value, pn.value, uo, un, asc, desc, fo["hmtx"][g][0]))
    with Pool(15) as pool:
        imgs = pool.map(glyph_images, jobs)
    cw = max(i[0].shape[1] for i in imgs) + 6
    ch = imgs[0][0].shape[0]
    band = ch * 3 + 22
    rows = (len(imgs) + COLS - 1) // COLS
    W, H = COLS * cw + 130, rows * band + 70
    out = np.zeros((H, W, 3))
    out[:] = BG
    for i, (at, a, b) in enumerate(imgs):
        r, c = divmod(i, COLS)
        x, y = 120 + c * cw, 60 + r * band
        hh, ww = at.shape
        for k, img in enumerate((at, a, b)):
            reg = out[y + k * ch:y + k * ch + hh, x:x + ww]
            out[y + k * ch:y + k * ch + hh, x:x + ww] = reg * (1 - img[..., None]) + img[..., None] * INK
    im = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.text((10, 14), f"{stem}: each band shows the HD atlas the game draws, the current OTF, the redrawn OTF", fill=(230, 235, 245), font=font(20))
    for r in range(rows):
        y = 60 + r * band
        for k, label in enumerate(("HD atlas", "old OTF", "new OTF")):
            d.text((10, y + k * ch + ch // 2 - 9), label, fill=(150, 160, 175), font=font(16))
    OUT.mkdir(exist_ok=True)
    im.save(OUT / f"{stem}.png")


def sheet_hd_new(stem):
    """Every glyph twice: the HD atlas the game draws, then the redrawn font."""
    fo, fn = load(stem)
    go, gn = fo.getGlyphSet(), fn.getGlyphSet()
    uo, un = fo["head"].unitsPerEm, fn["head"].unitsPerEm
    asc, desc = fo["hhea"].ascent, fo["hhea"].descent
    names = [g for g in fo.getGlyphOrder() if g not in (".notdef", "space")]
    by_char = {g: u for u, g in fo.getBestCmap().items()}
    ncm = fn.getBestCmap()
    names = [g for g in names if by_char.get(g) in ncm]
    nmap = {g: ncm[by_char[g]] for g in names}       # old glyph name -> new (production names)
    jobs = []
    for g in names:
        po, pn = RecordingPen(), RecordingPen()
        go[g].draw(po)
        gn[nmap[g]].draw(pn)
        jobs.append((stem, g, po.value, pn.value, uo, un, asc, desc, fo["hmtx"][g][0]))
    with Pool(15) as pool:
        imgs = pool.map(glyph_images, jobs)
    cw = max(i[0].shape[1] for i in imgs) + 6
    ch = imgs[0][0].shape[0]
    band = ch * 2 + 22
    rows = (len(imgs) + COLS - 1) // COLS
    W, H = COLS * cw + 130, rows * band + 70
    out = np.zeros((H, W, 3))
    out[:] = BG
    for i, (at, _, b) in enumerate(imgs):
        r, c = divmod(i, COLS)
        x, y = 120 + c * cw, 60 + r * band
        hh, ww = at.shape
        for k, img in enumerate((at, b)):
            reg = out[y + k * ch:y + k * ch + hh, x:x + ww]
            out[y + k * ch:y + k * ch + hh, x:x + ww] = reg * (1 - img[..., None]) + img[..., None] * INK
    im = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.text((10, 14), f"{stem.split('-')[-1]}: the HD font as the game draws it (HD atlas), and the redrawn font", fill=(230, 235, 245), font=font(20))
    for r in range(rows):
        y = 60 + r * band
        for k, label in enumerate(("HD font", "new font")):
            d.text((10, y + k * ch + ch // 2 - 9), label, fill=(150, 160, 175), font=font(16))
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / f"{stem}-hd-vs-new.png")


def closeup(items, path, size=420):
    """Letters large: HD atlas in grey, old outline orange, new outline cyan."""
    tiles = []
    for stem, name in items:
        fo, fn = load(stem)
        uo, un = fo["head"].unitsPerEm, fn["head"].unitsPerEm
        po, pn = RecordingPen(), RecordingPen()
        fo.getGlyphSet()[name].draw(po)
        fn.getGlyphSet()[fn.getBestCmap()[int(name[3:], 16)]].draw(pn)
        old = flatten(po.value, 0.5)
        new = [p * (uo / un) for p in flatten(pn.value, 0.5 * un / uo)]
        allp = np.vstack(old + new)
        pad = 15
        x0, y1 = allp[:, 0].min() - pad, allp[:, 1].max() + pad
        Wu, Hu = allp[:, 0].max() + pad - x0, y1 - (allp[:, 1].min() - pad)
        s = size / Hu
        w, h = int(Wu * s), size
        cell, base = atlasref.cells(stem)[name]
        at = atlas_image(cell, base, x0, y1, w, h, s)
        img = Image.fromarray(((1 - at[..., None] * 0.22) * 255 * np.ones(3)).astype(np.uint8))
        d = ImageDraw.Draw(img)
        T = lambda p: ((p[0] - x0) * s, (y1 - p[1]) * s)
        for poly in old:
            d.line([T(q) for q in poly] + [T(poly[0])], fill=(235, 120, 30), width=2)
        for poly in new:
            d.line([T(q) for q in poly] + [T(poly[0])], fill=(0, 150, 200), width=2)
        d.text((8, 6), f"{stem.split('-')[-1]} {chr(int(name[3:], 16))}", fill=(60, 60, 60), font=font(18))
        tiles.append(img)
    W = sum(t.width for t in tiles) + 10 * (len(tiles) + 1)
    sheet = Image.new("RGB", (W, size + 60), "white")
    x = 10
    for t in tiles:
        sheet.paste(t, (x, 40))
        x += t.width + 10
    ImageDraw.Draw(sheet).text((10, 8), "Grey: HD atlas (what the game draws).  Orange: current OTF.  Blue: redrawn OTF.", fill=(40, 40, 40), font=font(20))
    OUT.mkdir(exist_ok=True)
    sheet.save(path)


if __name__ == "__main__":
    want = [a for a in sys.argv[1:] if not a.startswith('--')]
    for f in sorted(FINAL.glob("*.otf")):
        if want and f.stem.split("-")[-1] not in want:
            continue
        if "--hd" in sys.argv:
            sheet_hd_new(f.stem)
        else:
            sheet(f.stem)
        print(f.stem)
