#!/usr/bin/env python3
"""HD Original's atlases rendered from the KMRP Original HD fonts.

The (New) Original HD Font's 17 atlases (assets/hd-original-fonts) are drawn from the
11 OTF files in fonts/otf, KMRP's own fonts under the SIL Open Font License 1.1
(fonts/README.md). Until 2026-10-22 they were rendered from Bank Gothic Medium and
Helvetica by tools/build_hd_original_fonts.py; the fonts in fonts/otf were redrawn from
those atlases as straight lines, corners and arcs, so no other foundry's file is needed
any more.

Each atlas keeps its TXI exactly: the same cells, positions, sizes, spacing and
baseline. Every cell whose character the font has is rendered again with exact area
coverage (each pixel the fraction of it inside the outline), its letter standing on the
baseline the stock font sets (as the fonts were measured); the rest keep their pixels.
fnt_console, the HUD's font, gets its black ring the way build_hd_original_fonts.py
gives it (outlined()).

Usage:
    python tools/build_hd_original_atlases.py            write assets/hd-original-fonts
    python tools/build_hd_original_atlases.py --check    compare only, write nothing
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "fonts" / "tools"))
from build_font_from_ttf import slot_character  # noqa: E402
from build_hd_original_fonts import OUTLINED, SCALE, Stock, outlined  # noqa: E402
from build_hd_original_otf import USES, read_txi  # noqa: E402
from build_scaled_fonts import write_tga  # noqa: E402
import area  # noqa: E402  (fonts/tools/area.py: exact area coverage)

ATLASES = ROOT / "assets/hd-original-fonts"
FONTS = ROOT / "fonts/otf"
ORIGINALS = ROOT / "build/native-runtime/original-fonts"


def polygons(recording, step):
    """Closed polygons of an outline, its curves cut into pieces about `step` long."""
    out, cur, last = [], [], None
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
            t = (np.arange(1, n + 1) / n)[:, None]
            u = 1 - t
            cur.extend(u ** 3 * last + 3 * u * u * t * c1 + 3 * u * t * t * c2 + t ** 3 * p)
            last = p
        elif op in ("closePath", "endPath"):
            if len(cur) > 2:
                out.append(np.array(cur))
            cur = []
    return out


def render(resref: str, key: str):
    """The atlas `resref` drawn from KMRP-OriginalHD-<key>.otf: its RGBA pixels and,
    per rendered cell, how far the new letter's coverage is from the old one's."""
    head, cells = read_txi(ATLASES / f"{resref}.txi")
    old = np.asarray(Image.open(ATLASES / f"{resref}.tga").convert("RGBA"))
    H, W = old.shape[:2]
    letters_old = old[..., :3].astype(np.float64).mean(2) / 255 * (old[..., 3] / 255.0)
    font = TTFont(FONTS / f"KMRP-OriginalHD-{key}.otf")
    cmap, glyphs = font.getBestCmap(), font.getGlyphSet()
    cell_h = round(head["fontheight"] * 100)
    upp = font["head"].unitsPerEm / cell_h              # font units per atlas pixel
    baseline = round(Stock(ORIGINALS, resref).baseline * SCALE)
    letters = letters_old.copy()
    cell_images, positions, diffs = [], [], []
    for c, (x0, y0, x1, y1) in enumerate(cells):
        l, t, r, b = round(x0 * W), round((1 - y0) * H), round(x1 * W), round((1 - y1) * H)
        if r <= l or b <= t:
            continue
        ch = slot_character(c)
        g = cmap.get(ord(ch)) if ch not in (None, " ") else None
        if g is not None:
            rp = RecordingPen()
            glyphs[g].draw(rp)
            polys = polygons(rp.value, 0.25 * upp / 10)
            if polys:
                cov = area.coverage(polys, 0, baseline * upp, r - l, b - t, 1 / upp)
                was = letters_old[t:b, l:r]
                ink = (was > 0.02) | (cov > 0.02)
                if ink.any():
                    diffs.append((ch, float(np.abs(cov - was)[ink].mean())))
                letters[t:b, l:r] = cov
        cell_images.append(Image.fromarray(np.round(letters[t:b, l:r] * 255).astype(np.uint8), "L"))
        positions.append((l, t))
    if resref in OUTLINED:
        report = {}
        rgba = np.asarray(outlined(cell_images, positions, W, OUTLINED[resref] * SCALE, report))
    else:
        rgba = np.zeros((H, W, 4), dtype=np.uint8)
        rgba[..., :3] = 255
        rgba[..., 3] = np.round(letters * 255).astype(np.uint8)
    return rgba, diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare only, write nothing")
    args = parser.parse_args()
    total = []
    for key, (_, games) in USES.items():
        for resref in (s.strip() for s in games.split(",")):
            rgba, diffs = render(resref, key)
            mean = float(np.mean([d for _, d in diffs])) if diffs else 0.0
            worst = max(diffs, key=lambda d: d[1]) if diffs else ("-", 0.0)
            total.append(mean)
            print(f"{resref:18} from {key:12} {len(diffs):3} letters, mean change {mean * 100:5.2f}% "
                  f"(most: {worst[0]!r} {worst[1] * 100:.1f}%)")
            if not args.check:
                h, w = rgba.shape[:2]
                write_tga(ATLASES / f"{resref}.tga", w, h, rgba.tobytes())
    print(f"{len(total)} atlases, mean change {np.mean(total) * 100:.2f}%" + ("" if args.check else ", written"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
