"""Redraws every glyph of the old fonts, writes the new fonts, compares old and new.

    python run.py [font names...]
"""
import json
import os
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

import redraw as R
import redraw2 as RD
import area
import atlasref
import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# The traced HD fonts (tools/build_hd_original_otf.py): read for their metrics and names only.
OLD = Path(os.environ.get("KMRP_TRACED_FONTS", ROOT / "build/fonts/KMRP-OriginalHD-OTF"))
NEW = ROOT / "build/fonts/redrawn"
UNITS_PER_PX = 10.0


def flatten(recording, step=1.0):
    """Polygons (lists of points) of a RecordingPen value, about `step` units apart."""
    polys, cur, last = [], [], None
    for op, args in recording:
        if op == "moveTo":
            last = np.array(args[0], float)
            cur = [last]
        elif op == "lineTo":
            last = np.array(args[0], float)
            cur.append(last)
        elif op == "curveTo":
            c1, c2, p = (np.array(a, float) for a in args)
            est = np.linalg.norm(c1 - last) + np.linalg.norm(c2 - c1) + np.linalg.norm(p - c2)
            n = max(2, int(math.ceil(est / step)))
            for q in R.bez(last, c1, c2, p, np.arange(1, n + 1) / n):
                cur.append(q)
            last = p
        elif op in ("closePath", "endPath"):
            if len(cur) > 2:
                polys.append(np.array(cur))
            cur = []
    return polys


def raster(polys, x0, y0, w, h, scale, ss=4):
    """Coverage (0..1) of polygons on a w x h grid, `scale` pixels per unit, origin at
    (x0, y0) in units (top left), y up in units."""
    W, H = w * ss, h * ss
    acc = np.zeros((H, W), dtype=bool)
    for p in polys:
        im = Image.new("1", (W, H), 0)
        xy = [((q[0] - x0) * scale * ss, (y0 - q[1]) * scale * ss) for q in p]
        ImageDraw.Draw(im).polygon(xy, fill=1)
        acc ^= np.asarray(im, dtype=bool)
    return acc.reshape(h, ss, w, ss).mean(axis=(1, 3))


def dense(polys, step=0.5):
    out = []
    for p in polys:
        q = np.vstack([p, p[:1]])
        seg = np.linalg.norm(np.diff(q, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        n = max(4, int(s[-1] / step))
        t = np.linspace(0, s[-1], n, endpoint=False)
        out.append(np.stack([np.interp(t, s, q[:, 0]), np.interp(t, s, q[:, 1])], 1))
    return np.vstack(out) if out else np.zeros((0, 2))


def nearest(a, polys, chunk=400):
    """For each point of a, the distance to the nearest point of the closed polylines
    (densified to 0.1 units, searched with a KD-tree)."""
    from scipy.spatial import cKDTree
    pts = dense(polys, 0.1)
    return cKDTree(pts).query(a)[0]


def work(item):
    name, rec, stem = item
    t = time.time()
    if RD is not R:
        ref = atlasref.cells(stem).get(name)
        loops = measure.outlines(*ref) if ref is not None and ref[0].max() >= 0.5 else []
        contours, fit = RD.redraw(loops=loops, name=name) if loops else ([], 0.0)
    else:
        contours, fit = RD.redraw(rec)
    pen = RecordingPen()
    R.draw(contours, pen)
    new = pen.value
    op, np_ = flatten(rec), flatten(new)
    stats = {"name": name, "fit": fit, "old_segs": sum(1 for o, _ in rec if o in ("lineTo", "curveTo")),
             "new_segs": sum(1 for o, _ in new if o in ("lineTo", "curveTo")) + sum(1 for o, _ in new if o == "closePath"),
             "contours_old": sum(1 for o, _ in rec if o == "moveTo"), "contours_new": len(contours)}
    if op:
        A, B = dense(op), dense(np_) if np_ else np.zeros((0, 2))
        if len(B):
            d1, d2 = nearest(A, flatten(new, 0.5)), nearest(B, flatten(rec, 0.5))
            stats["haus"] = float(max(d1.max(), d2.max()))
            stats["mean"] = float((d1.mean() + d2.mean()) / 2)
        else:
            stats["haus"] = 1e9
            stats["mean"] = 1e9
        allp = np.vstack(op + np_)
        x0 = math.floor(allp[:, 0].min() / UNITS_PER_PX) * UNITS_PER_PX - UNITS_PER_PX
        y1 = math.ceil(allp[:, 1].max() / UNITS_PER_PX) * UNITS_PER_PX + UNITS_PER_PX
        w = int(math.ceil((allp[:, 0].max() - x0) / UNITS_PER_PX)) + 2
        h = int(math.ceil((y1 - allp[:, 1].min()) / UNITS_PER_PX)) + 2
        fo, fn = flatten(rec, 0.25), flatten(new, 0.25)
        a = area.coverage(fo, x0, y1, w, h, 1 / UNITS_PER_PX)
        b = area.coverage(fn, x0, y1, w, h, 1 / UNITS_PER_PX)
        stats["covmax"] = float(np.abs(a - b).max())
        stats["covsum"] = float(np.abs(a - b).sum() / max(a.sum(), 1e-9))
        ref = atlasref.cells(stem).get(name)
        if ref is not None:
            cell, base = ref
            hh, ww = cell.shape
            co = area.coverage(fo, 0, base * 10, ww, hh, 0.1)
            cn = area.coverage(fn, 0, base * 10, ww, hh, 0.1)
            ink = cell > 0.02
            stats["old_atlas_max"] = float(np.abs(co - cell).max())
            stats["new_atlas_max"] = float(np.abs(cn - cell).max())
            stats["old_atlas_mean"] = float(np.abs(co - cell)[ink].mean()) if ink.any() else 0.0
            stats["new_atlas_mean"] = float(np.abs(cn - cell)[ink].mean()) if ink.any() else 0.0
    stats["secs"] = time.time() - t
    return stats, new


def build(fontfile: Path, pool, only=None):
    font = TTFont(fontfile)
    gs = font.getGlyphSet()
    order = font.getGlyphOrder()
    items = []
    for g in order:
        p = RecordingPen()
        gs[g].draw(p)
        items.append((g, p.value, fontfile.stem))
    results = pool.map(work, items if only is None else [i for i in items if i[0] in only], chunksize=2)
    newrec = {s["name"]: rec for s, rec in results}
    hm = font["hmtx"].metrics
    G = R.GRID
    cs = {}
    for g in order:
        adv = hm[g][0] * G
        pen = T2CharStringPen(adv, None)
        rec = newrec.get(g)
        for op, args in rec:
            getattr(pen, op)(*[(int(round(x * G)), int(round(y * G))) for x, y in args])
        cs[g] = pen.getCharString()
    upm = font["head"].unitsPerEm * G
    fb = FontBuilder(upm, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(font.getBestCmap())
    names = {r.nameID: r.toUnicode() for r in font["name"].names if r.platformID == 3}
    family = names[1]
    fb.setupCFF(family.replace(" ", ""), {"FullName": family}, cs, {})
    fb.setupHorizontalMetrics({g: (hm[g][0] * G, hm[g][1] * G) for g in order})
    hh = font["hhea"]
    fb.setupHorizontalHeader(ascent=hh.ascent * G, descent=hh.descent * G)
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": names[3],
                       "version": "Version 1.600", "description": names.get(10, "")})
    os2 = font["OS/2"]
    fb.setupOS2(sTypoAscender=os2.sTypoAscender * G, sTypoDescender=os2.sTypoDescender * G, sTypoLineGap=0,
                usWinAscent=os2.usWinAscent * G, usWinDescent=os2.usWinDescent * G, achVendID="KMRP")
    fb.setupPost()
    NEW.mkdir(exist_ok=True)
    out = NEW / fontfile.name
    fb.save(str(out))
    return [s for s, _ in results]


def summary(name, stats):
    ink = [s for s in stats if "haus" in s]
    h = np.array([s["haus"] for s in ink])
    m = np.array([s["mean"] for s in ink])
    c = np.array([s["covmax"] for s in ink])
    os_ = sum(s["old_segs"] for s in ink)
    ns = sum(s["new_segs"] for s in ink)
    bad = sorted(ink, key=lambda s: -s["haus"])[:6]
    print(f"{name:34} glyphs {len(ink):4}  outline gap max {h.max():5.2f} u  mean {m.mean():5.3f} u  "
          f"over 1u {int((h > 1).sum()):3}  pixel coverage diff max {c.max():.3f}  segments {os_} -> {ns}")
    print("    worst:", ", ".join(f"{s['name']} {s['haus']:.2f}" for s in bad))
    at = [s for s in ink if "new_atlas_mean" in s]
    if at:
        om = np.mean([s["old_atlas_mean"] for s in at]); nm = np.mean([s["new_atlas_mean"] for s in at])
        worse = [s for s in at if s["new_atlas_mean"] > s["old_atlas_mean"] * 1.1 + 0.002]
        print(f"    against the HD atlas: old mean {om * 100:.2f}%, new mean {nm * 100:.2f}%, "
              f"old max {max(s['old_atlas_max'] for s in at) * 100:.1f}%, new max {max(s['new_atlas_max'] for s in at) * 100:.1f}%, "
              f"glyphs further from the atlas than old: {len(worse)}"
              + (" (" + ", ".join(s['name'] for s in sorted(worse, key=lambda s: s['old_atlas_mean'] - s['new_atlas_mean'])[:8]) + ")" if worse else ""))


if __name__ == "__main__":
    wanted = sys.argv[1:]
    files = sorted(OLD.glob("*.otf"))
    if wanted:
        files = [f for f in files if any(w.lower() == f.stem.split("-")[-1].lower() for w in wanted)]
    report = {}
    with Pool(15) as pool:
        for f in files:
            t = time.time()
            stats = build(f, pool)
            report[f.stem] = stats
            summary(f.stem, stats)
            print(f"    {time.time() - t:.0f} s")
    (NEW / "report.json").write_text(json.dumps(report, indent=0))
