#!/usr/bin/env python3
"""The controller button pictures as geometry, and the one way they are drawn (issue 68).

Every controller picture KMRP shows (21 per family: the face buttons, shoulders, triggers,
Start and Back, the D-pad and its directions, the sticks, and the swap-tabs phrase) is kept
as outlines and paints in assets/controller-glyphs/glyphs.json, made from Xelu's vector
source by tools/build_controller_glyph_vectors.py. They used to be Xelu's 100 px PNGs,
shrunk with Lanczos into each badge, which came out soft at the 18 to 40 px most buttons
use (issue 68, the Steam Deck). Drawn from their outlines at the size they are shown, the
edges are as sharp as the screen allows at every resolution.

The same picture is drawn in three places: here for the build's sets, by
src/patcher/GuiBlend.cs for a resolution the Windows installer blends, and by
macos/tools/kmrp-guiblend.c for the Mac's installer and both games' patch DLLs. They
must agree byte for byte (testing/regression/Test-GuiBlendHelper.py), so the drawing is
integer arithmetic only; no floating point reaches a pixel. The rules, which the other two
copies follow step for step:

  * A glyph is a box of W x H units (its larger side 65536) and items painted in order.
    An item is a set of closed polygons with integer vertices, a fill rule (nonzero or
    even-odd) and a paint: a solid RGBA, or a linear or radial gradient given as integer
    coefficients (below) and stops.
  * The glyph is drawn into a dst_w x dst_h rectangle at whole pixel (left, top). A vertex
    (x, y) lands at X = left * 2048 + floor(x * dst_w * 2048 / W) in 1/2048 of a pixel, and
    likewise Y with dst_h and H.
  * Each pixel holds 8 x 8 samples, at (k * 256 + 128) for sample column k (and row), in
    the same 1/2048 units. An item covers a sample by its fill rule, from the winding of
    its edges: an edge from (x0, y0) to (x1, y1) with y0 != y1 crosses the sample row at
    sy when min(y0, y1) <= sy < max(y0, y1), at x = x0 + floor((x1 - x0) * (sy - y0) /
    (y1 - y0)), adding +1 (y1 > y0) or -1 to the winding of every sample of that row with
    its centre at or right of x.
  * The paint is taken once per pixel, at its centre in glyph units: xa = floor((2 * (px
    - left) + 1) * W / (2 * dst_w)), likewise ya. Linear: t = floor((A * xa + B * ya + C) /
    65536); radial: u and v the same from their three coefficients and t = isqrt(u * u +
    v * v). t is clamped to 0..65536 and the colour is interpolated between the stops
    around it, each channel c0 + floor(((c1 - c0) * (t - p0) * 2 + (p1 - p0)) / (2 * (p1 -
    p0))).
  * A sample keeps premultiplied P = colour x alpha (0..65025) per channel and Q = 255 x
    alpha. A covered sample takes the item's colour (c, a) over itself: P = c * a + (P *
    (255 - a) + 127) // 255, Q = 255 * a + (Q * (255 - a) + 127) // 255.
  * A pixel sums its 64 samples' P and Q. On a backing (b, ba) the backing is added under
    it: P += (b * ba * (64 * 65025 - Q)) // 65025, Q += (255 * ba * (64 * 65025 - Q)) //
    65025. Then alpha = (Q + 64 * 127) // (64 * 255) and each colour (255 * P + Q // 2) //
    Q (0 where Q is 0, at most 255).
  * Nothing is drawn outside the rectangle: a pixel of the rectangle off the texture is
    skipped, and geometry outside the rectangle is cut off at its edge.

Divisions are floor divisions throughout (Python's //; C and C# need a helper, since their
division truncates and a crossing's divisor y1 - y0 is negative on every upward edge). The
largest products stay below 2^47.

    python tools/controller_glyphs.py FAMILY GLYPH WIDTH HEIGHT OUT.png   (a picture)
"""
from __future__ import annotations

import json
import struct
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GLYPH_DATA = ROOT / "assets" / "controller-glyphs" / "glyphs.json"
SS = 8                    # samples per pixel, each way
SUB = 2048                # vertex units per pixel
SAMPLE = SUB // SS        # 256 per sample
SAMPLES = SS * SS
FULL = SAMPLES * 65025    # a pixel's Q when every sample is opaque
NONZERO, EVENODD = 0, 1
SOLID, LINEAR, RADIAL = 0, 1, 2


@lru_cache(maxsize=None)
def glyphs() -> dict:
    """family/glyph -> {"size": [W, H], "items": [...]}, as glyphs.json holds them."""
    data = json.loads(GLYPH_DATA.read_text(encoding="utf-8"))
    out = {}
    for name, glyph in data["glyphs"].items():
        while "same_as" in glyph:
            glyph = data["glyphs"][glyph["same_as"]]
        out[name] = glyph
    return out


def glyph(family: str, name: str) -> dict | None:
    return glyphs().get(f"{family}/{name}")


def glyph_size(family: str, name: str) -> tuple[int, int] | None:
    g = glyph(family, name)
    return None if g is None else tuple(g["size"])


def pack(g: dict) -> bytes:
    """One glyph as gui-blend.bin carries it (build_gui_blend_table.py's badge section):
    u32 W, u32 H, u32 items; per item: u8 rule, u8 paint, then the paint (solid: 4 bytes
    RGBA; linear: 3 x i64; radial: 6 x i64, then u32 stops, per stop u32 position and 4
    bytes RGBA), u32 polygons, per polygon u32 n and n x (i32 x, i32 y)."""
    out = struct.pack("<III", g["size"][0], g["size"][1], len(g["items"]))
    for item in g["items"]:
        paint = item["paint"]
        rule = EVENODD if item["rule"] == "evenodd" else NONZERO
        if "solid" in paint:
            out += struct.pack("<BB4B", rule, SOLID, *paint["solid"])
        else:
            kind = LINEAR if "linear" in paint else RADIAL
            coef = paint["linear"] if kind == LINEAR else paint["radial"]
            out += struct.pack("<BB", rule, kind) + struct.pack(f"<{len(coef)}q", *coef)
            out += struct.pack("<I", len(paint["stops"]))
            for stop in paint["stops"]:
                out += struct.pack("<I4B", *stop)
        out += struct.pack("<I", len(item["polygons"]))
        for poly in item["polygons"]:
            out += struct.pack("<I", len(poly) // 2) + struct.pack(f"<{len(poly)}i", *poly)
    return out


def _isqrt(n: np.ndarray) -> np.ndarray:
    r = np.floor(np.sqrt(n.astype(np.float64))).astype(np.int64)
    r = np.where(r * r > n, r - 1, r)
    r = np.where((r + 1) * (r + 1) <= n, r + 1, r)
    return r


def _paint(paint: dict, xa: np.ndarray, ya: np.ndarray) -> np.ndarray:
    """RGBA (int64, ... x 4) of a paint at glyph points xa, ya."""
    if "solid" in paint:
        return np.broadcast_to(np.array(paint["solid"], np.int64), xa.shape + (4,))
    if "linear" in paint:
        a, b, c = paint["linear"]
        t = (a * xa + b * ya + c) // 65536
    else:
        a1, b1, c1, a2, b2, c2 = paint["radial"]
        u = (a1 * xa + b1 * ya + c1) // 65536
        v = (a2 * xa + b2 * ya + c2) // 65536
        t = _isqrt(u * u + v * v)
    t = np.clip(t, 0, 65536)
    stops = paint["stops"]
    out = np.empty(xa.shape + (4,), np.int64)
    out[...] = np.array(stops[0][1:], np.int64)
    for (p0, *c0), (p1, *c1) in zip(stops, stops[1:]):
        c0 = np.array(c0, np.int64)
        c1 = np.array(c1, np.int64)
        if p1 > p0:
            inside = (t >= p0)[..., None]
            k = ((c1 - c0) * (t - p0)[..., None] * 2 + (p1 - p0)) // (2 * (p1 - p0))
            out = np.where(inside, c0 + k, out)
        out = np.where((t >= p1)[..., None], c1, out)
    return out


@lru_cache(maxsize=None)
def _edges(family: str, name: str) -> tuple:
    """Per item its edges as arrays (x0, y0, x1, y1, in glyph units), the polygons closed."""
    out = []
    for item in glyph(family, name)["items"]:
        parts = [np.array(poly, np.int64).reshape(-1, 2) for poly in item["polygons"]]
        v0 = np.concatenate(parts)
        v1 = np.concatenate([np.roll(q, -1, axis=0) for q in parts])
        out.append((v0[:, 0], v0[:, 1], v1[:, 0], v1[:, 1]))
    return tuple(out)


@lru_cache(maxsize=4096)
def _tile(family: str, name: str, dst_w: int, dst_h: int) -> tuple[np.ndarray, np.ndarray]:
    """The summed P (dst_h x dst_w x 3) and Q (dst_h x dst_w) of the glyph drawn into a
    dst_w x dst_h rectangle at (0, 0). Drawing is the same at any whole-pixel position."""
    g = glyph(family, name)
    W, H = g["size"]
    rows, cols = dst_h * SS, dst_w * SS
    P = np.zeros((rows, cols, 3), np.int64)
    Q = np.zeros((rows, cols), np.int64)
    px = np.arange(dst_w, dtype=np.int64)
    py = np.arange(dst_h, dtype=np.int64)
    xa = ((2 * px + 1) * W) // (2 * dst_w)
    ya = ((2 * py + 1) * H) // (2 * dst_h)
    for item, (ex0, ey0, ex1, ey1) in zip(g["items"], _edges(family, name)):
        x0, y0 = (ex0 * dst_w * SUB) // W, (ey0 * dst_h * SUB) // H
        x1, y1 = (ex1 * dst_w * SUB) // W, (ey1 * dst_h * SUB) // H
        keep = y0 != y1
        x0, y0, x1, y1 = x0[keep], y0[keep], x1[keep], y1[keep]
        lo, hi = np.minimum(y0, y1), np.maximum(y0, y1)
        # Each edge only on the sample rows it crosses (lo <= sy < hi), not every edge on
        # every row: the rows first..last, as one flat list of (row, edge) pairs.
        first = np.maximum(-((SAMPLE // 2 - lo) // SAMPLE), 0)
        last = np.minimum(-((SAMPLE // 2 - hi) // SAMPLE) - 1, rows - 1)
        span = np.maximum(last - first + 1, 0)
        e = np.repeat(np.arange(len(span)), span)
        if len(e) == 0:
            continue
        r = first[e] + (np.arange(len(e)) - np.repeat(np.cumsum(span) - span, span))
        sy = r * SAMPLE + SAMPLE // 2
        xc = x0[e] + ((x1[e] - x0[e]) * (sy - y0[e])) // (y1[e] - y0[e])
        # the first sample column whose centre is at or right of the crossing
        k = np.clip(-((SAMPLE // 2 - xc) // SAMPLE), 0, cols)
        direction = np.where(y1[e] > y0[e], 1, -1)
        # Only the rows and columns the item's crossings reach can be covered.
        r0, r1 = int(r.min()), int(r.max()) + 1
        k0, k1 = int(k.min()), min(cols, int(k.max()))
        if k1 <= k0:
            continue
        width = cols + 1 - k0
        diff = np.bincount((r - r0) * width + (k - k0), weights=direction,
                           minlength=(r1 - r0) * width).reshape(r1 - r0, width)
        winding = np.cumsum(diff[:, :k1 - k0], axis=1).astype(np.int64)
        if item["rule"] == "evenodd":
            rr, kk = np.nonzero(winding % 2 != 0)
        else:
            rr, kk = np.nonzero(winding != 0)
        if len(rr) == 0:
            continue
        rr += r0
        kk += k0
        # the covered samples alone, each with its pixel's paint
        rgba = _paint(item["paint"], xa[kk // SS], ya[rr // SS])
        c, a = rgba[:, :3], rgba[:, 3]
        inv = 255 - a
        P[rr, kk] = c * a[:, None] + (P[rr, kk] * inv[:, None] + 127) // 255
        Q[rr, kk] = 255 * a + (Q[rr, kk] * inv + 127) // 255
    P = P.reshape(dst_h, SS, dst_w, SS, 3).sum(axis=(1, 3))
    Q = Q.reshape(dst_h, SS, dst_w, SS).sum(axis=(1, 3))
    return P, Q


def draw_into(sheet: np.ndarray, family: str, name: str, left: int, top: int,
              dst_w: int, dst_h: int, backing: tuple | None = None) -> None:
    """Draws the glyph into `sheet` (height x width x 4 uint8, top row first, all
    transparent, or all `backing` when there is one) at (left, top), dst_w x dst_h."""
    P, Q = _tile(family, name, dst_w, dst_h)
    if backing is not None:
        b, ba = np.array(backing[:3], np.int64), int(backing[3])
        rest = FULL - Q
        P = P + (b * ba * rest[..., None]) // 65025
        Q = Q + (255 * ba * rest) // 65025
    alpha = (Q + SAMPLES * 127) // (SAMPLES * 255)
    safe = np.where(Q > 0, Q, 1)
    colour = np.where(Q[..., None] > 0, np.minimum((255 * P + (safe // 2)[..., None]) // safe[..., None], 255), 0)
    out = np.concatenate([colour, alpha[..., None]], axis=-1).astype(np.uint8)
    th, tw = sheet.shape[:2]
    x0, y0 = max(0, left), max(0, top)
    x1, y1 = min(tw, left + dst_w), min(th, top + dst_h)
    if x0 < x1 and y0 < y1:
        sheet[y0:y1, x0:x1] = out[y0 - top:y1 - top, x0 - left:x1 - left]


def picture(family: str, name: str, width: int, height: int):
    """The glyph fitted into width x height keeping its proportions, centred (a PIL image)."""
    from PIL import Image
    W, H = glyph_size(family, name)
    k = min(width / W, height / H)
    dw, dh = max(1, round(W * k)), max(1, round(H * k))
    sheet = np.zeros((height, width, 4), np.uint8)
    draw_into(sheet, family, name, (width - dw) // 2, (height - dh) // 2, dw, dh)
    return Image.fromarray(sheet, "RGBA")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        raise SystemExit(__doc__.rsplit("\n\n", 1)[-1])
    picture(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])).save(sys.argv[5])
