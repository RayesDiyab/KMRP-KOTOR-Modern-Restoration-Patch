"""Old and new font files against the HD atlas, glyph by glyph, without redrawing.
    python check.py [font names...]  -> check.json, outliers printed"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

import area
import atlasref
from finish import FINAL
from run import NEW, OLD, flatten

HERE = Path(__file__).resolve().parent


def one(args):
    stem, name, rec_old, rec_new, scale = args
    ref = atlasref.cells(stem).get(name)
    if ref is None:
        return None
    cell, base = ref
    h, w = cell.shape
    co = area.coverage(flatten(rec_old, 0.25), 0, base * 10, w, h, 0.1)
    polys = [p / scale for p in flatten(rec_new, 0.25 * scale)]
    cn = area.coverage(polys, 0, base * 10, w, h, 0.1)
    ink = cell > 0.02
    m = lambda c: float(np.abs(c - cell)[ink].mean()) if ink.any() else 0.0
    return dict(name=name, old_max=float(np.abs(co - cell).max()), new_max=float(np.abs(cn - cell).max()),
                old_mean=m(co), new_mean=m(cn))


if __name__ == "__main__":
    want = sys.argv[1:]
    out = {}
    with Pool(15) as pool:
        for f in sorted(FINAL.glob("*.otf")):
            stem = f.stem
            if want and stem.split("-")[-1] not in want:
                continue
            fo, fn = TTFont(OLD / f.name), TTFont(f)
            scale = fn["head"].unitsPerEm / fo["head"].unitsPerEm
            jobs = []
            # The same character in both (the new fonts use production glyph names).
            new_by_char = fn.getBestCmap()
            for u, g in sorted(fo.getBestCmap().items()):
                if u not in new_by_char:
                    continue
                po, pn = RecordingPen(), RecordingPen()
                fo.getGlyphSet()[g].draw(po)
                fn.getGlyphSet()[new_by_char[u]].draw(pn)
                if po.value:
                    jobs.append((stem, g, po.value, pn.value, scale))
            res = [r for r in pool.map(one, jobs) if r]
            out[stem] = res
            om, nm = np.mean([r["old_mean"] for r in res]), np.mean([r["new_mean"] for r in res])
            print(f"{stem:34} old {om * 100:.2f}%  new {nm * 100:.2f}%  max old {max(r['old_max'] for r in res) * 100:.0f}%  new {max(r['new_max'] for r in res) * 100:.0f}%")
            for r in sorted(res, key=lambda r: -r["new_max"]):
                if r["new_max"] > 0.6 or r["new_mean"] > r["old_mean"] or r["new_mean"] > 0.05:
                    print(f"    {r['name']} {chr(int(r['name'][3:], 16))} max {r['new_max']:.2f} (old {r['old_max']:.2f}) mean {r['new_mean'] * 100:.1f}% (old {r['old_mean'] * 100:.1f}%)")
    (NEW / "check.json").write_text(json.dumps(out))
