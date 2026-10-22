"""The HD letters' edges, measured from the atlas: where the coverage crosses one half,
found between pixel centres to a fraction of a pixel (marching squares with linear
interpolation). Returns closed outlines in font units (10 per atlas pixel, y up, the
baseline at 0), the ink on each outline's right, as the current HD OTFs have them."""
import math
import numpy as np
import refine as RF

LEVEL = 0.5


def iso_loops(v):
    """Closed polylines (x, y in pixel units, y down, pixel centres at +0.5) where v
    crosses LEVEL. v is padded with zeros so every loop closes."""
    v = np.pad(v, 1)
    h, w = v.shape
    inside = v >= LEVEL

    def pt(edge):
        kind, i, j = edge
        if kind == "h":      # between (i, j) and (i, j + 1)
            a, b = v[i, j], v[i, j + 1]
            t = (LEVEL - a) / (b - a)
            return (j + t + 0.5 - 1, i + 0.5 - 1)
        a, b = v[i, j], v[i + 1, j]  # between (i, j) and (i + 1, j)
        t = (LEVEL - a) / (b - a)
        return (j + 0.5 - 1, i + t + 0.5 - 1)

    adj = {}

    def link(e1, e2):
        adj.setdefault(e1, []).append(e2)
        adj.setdefault(e2, []).append(e1)

    for i in range(h - 1):
        for j in range(w - 1):
            a, b, c, d = inside[i, j], inside[i, j + 1], inside[i + 1, j + 1], inside[i + 1, j]
            case = a * 8 + b * 4 + c * 2 + d
            if case in (0, 15):
                continue
            T, Rr, B, L = ("h", i, j), ("v", i, j + 1), ("h", i + 1, j), ("v", i, j)
            if case in (5, 10):
                # Two opposite corners inside: the centre decides which pair is joined.
                # The corners cut off are the outside ones if the centre is inside.
                centre = (v[i, j] + v[i, j + 1] + v[i + 1, j + 1] + v[i + 1, j]) / 4 >= LEVEL
                cut_ac = (case == 5) == centre      # cut off corners a and c, else b and d
                if cut_ac:
                    link(T, L)
                    link(Rr, B)
                else:
                    link(T, Rr)
                    link(B, L)
                continue
            edges = []
            if a != b:
                edges.append(T)
            if b != c:
                edges.append(Rr)
            if c != d:
                edges.append(B)
            if d != a:
                edges.append(L)
            link(edges[0], edges[1])
    loops = []
    seen = set()
    for start in adj:
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        prev, cur = None, start
        while True:
            nxt = [e for e in adj[cur] if e != prev]
            if not nxt:
                break
            e = nxt[0]
            if e == start:
                break
            if e in seen:
                break
            loop.append(e)
            seen.add(e)
            prev, cur = cur, e
        if len(loop) >= 3:
            loops.append(np.array([pt(e) for e in loop], dtype=np.float64))
    return loops


def bilinear(v, x, y):
    """Coverage at (x, y) in pixel units, y down."""
    h, w = v.shape
    fx, fy = x - 0.5, y - 0.5
    j0, i0 = int(math.floor(fx)), int(math.floor(fy))
    tx, ty = fx - j0, fy - i0

    def at(i, j):
        return v[i, j] if 0 <= i < h and 0 <= j < w else 0.0

    return (at(i0, j0) * (1 - tx) * (1 - ty) + at(i0, j0 + 1) * tx * (1 - ty)
            + at(i0 + 1, j0) * (1 - tx) * ty + at(i0 + 1, j0 + 1) * tx * ty)


def outlines(cell, baseline, spacing=0.5):
    """The letter's outlines in font units, ink on the right, about `spacing` apart."""
    out = []
    for L in iso_loops(cell):
        # Ink on the right in y-up units is ink on the left in y-down pixels.
        a, b = L[0], L[1]
        d = b - a
        m = (a + b) / 2
        left = m + np.array([d[1], -d[0]]) / (np.linalg.norm(d) + 1e-12) * 0.2
        if bilinear(cell, left[0], left[1]) < LEVEL:
            L = L[::-1]
        L = RF.refine(L, cell)
        U = np.stack([L[:, 0] * 10.0, (baseline - L[:, 1]) * 10.0], 1)
        out.append(resample(U, spacing))
    return out


def resample(P, spacing):
    closed = np.vstack([P, P[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(8, int(round(s[-1] / spacing)))
    q = np.linspace(0, s[-1], n, endpoint=False)
    return np.stack([np.interp(q, s, closed[:, 0]), np.interp(q, s, closed[:, 1])], 1)
