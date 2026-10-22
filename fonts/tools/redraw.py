"""Redraws a glyph as a type designer draws one: straight strokes as lines (exactly
horizontal or vertical where they are), curves as cubic arcs with their points at the
extremes and horizontal or vertical handles, sharp corners kept sharp. Each arc is fitted
to dense measurements of the old letter until it lies within TOL font units of it.

Units are the fonts' own: 10 per atlas pixel.
"""
from __future__ import annotations

import math
import numpy as np
from scipy.spatial import cKDTree

SPACING = 0.5      # measurement spacing along the old outline, units
TOL = 0.2          # largest distance of a measurement from the new outline, units
GRID = 8           # new units per old unit: the new fonts' points sit on a grid 8 times finer
CORNER_W = 2.0     # arc length either side used to judge a corner, units
CORNER_DEG = 32.0  # turn over that window that makes a corner
LINE_TOL = 0.15    # largest deviation of a straight run from its line, units
LINE_MIN = 8.0     # shortest straight run kept as a line, units
LINE_RADIUS = 1500.0  # a run bending more than a circle this size is a curve
AXIS_MOVE = 0.15   # a line made exactly horizontal or vertical moves its ends at most this far


# ---------------------------------------------------------------- measuring the old letter

def bez(p0, p1, p2, p3, t):
    t = np.asarray(t, dtype=np.float64)[:, None]
    u = 1 - t
    return u ** 3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t ** 3 * p3


def even(pts):
    """Points along a piece, about SPACING apart, its two ends kept exactly."""
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(1, int(math.ceil(s[-1] / SPACING)))
    q = np.linspace(0, s[-1], n + 1)
    return np.stack([np.interp(q, s, pts[:, 0]), np.interp(q, s, pts[:, 1])], 1)


def contours_of(recording) -> list[np.ndarray]:
    """Points about SPACING apart along each closed contour of a RecordingPen's value,
    every point of the old outline among them, so a corner is measured at its tip."""
    out, cur, start, last = [], [], None, None
    for op, args in recording:
        if op == "moveTo":
            start = last = np.array(args[0], dtype=np.float64)
            cur = []
        elif op == "lineTo":
            p = np.array(args[0], dtype=np.float64)
            if np.linalg.norm(p - last) > 1e-9:
                cur.append(even(np.stack([last, p]))[1:])
            last = p
        elif op == "curveTo":
            c1, c2, p = (np.array(a, dtype=np.float64) for a in args)
            est = np.linalg.norm(c1 - last) + np.linalg.norm(c2 - c1) + np.linalg.norm(p - c2)
            fine = bez(last, c1, c2, p, np.linspace(0, 1, max(8, int(est * 4))))
            cur.append(even(fine)[1:])
            last = p
        elif op in ("closePath", "endPath"):
            if np.linalg.norm(last - start) > 1e-9:
                cur.append(even(np.stack([last, start]))[1:])
            pts = np.concatenate(cur)
            if np.linalg.norm(pts[-1] - pts[0]) < 1e-9:
                pts = pts[:-1]
            keep = np.concatenate([[True], np.linalg.norm(np.diff(pts, axis=0), axis=1) > 1e-6])
            out.append(pts[keep])
            cur = []
    return out


# ---------------------------------------------------------------- fitting one arc

def cap(node, handle, chord):
    """A handle no longer than 1.2 chords: longer ones make loops."""
    v = handle - node
    L = np.linalg.norm(v)
    return node + v * (chord * 1.2 / L) if L > chord * 1.2 else handle


def fit_cubic(Q: np.ndarray, t0, t3):
    """Cubic from Q[0] to Q[-1] through Q. t0, t3: unit tangents at the ends (t3 the
    direction of travel at the end) or None to leave that handle free. Returns the four
    points and the largest distance of Q from the curve."""
    P0, P3 = Q[0], Q[-1]
    chord = np.linalg.norm(P3 - P0)
    d = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    t = np.concatenate([[0], np.cumsum(d)])
    t = t / t[-1] if t[-1] > 0 else np.linspace(0, 1, len(Q))
    best = None
    for _ in range(12):
        u = 1 - t
        b0, b1, b2, b3 = u ** 3, 3 * u * u * t, 3 * u * t * t, t ** 3
        R = Q - b0[:, None] * P0 - b3[:, None] * P3
        cols = []
        base = np.zeros_like(Q)
        # Unknowns: start handle (a along t0, or free x, y), end handle likewise.
        if t0 is not None:
            base += b1[:, None] * P0
            cols.append(b1[:, None] * t0)
        else:
            cols.append(b1[:, None] * np.array([1.0, 0.0]))
            cols.append(b1[:, None] * np.array([0.0, 1.0]))
        if t3 is not None:
            base += b2[:, None] * P3
            cols.append(-b2[:, None] * t3)
        else:
            cols.append(b2[:, None] * np.array([1.0, 0.0]))
            cols.append(b2[:, None] * np.array([0.0, 1.0]))
        A = np.stack([c.reshape(-1) for c in cols], axis=1)
        rhs = (R - base).reshape(-1)
        sol, *_ = np.linalg.lstsq(A, rhs, rcond=None)
        k = 0
        if t0 is not None:
            a = sol[k]; k += 1
            if not 0 < a <= chord * 1.2:
                a = min(max(a, chord / 3) if a > 0 else chord / 3, chord * 1.2)
            P1 = P0 + a * t0
        else:
            P1 = cap(P0, np.array([sol[k], sol[k + 1]]), chord)
            k += 2
        if t3 is not None:
            b = sol[k]; k += 1
            if not 0 < b <= chord * 1.2:
                b = min(max(b, chord / 3) if b > 0 else chord / 3, chord * 1.2)
            P2 = P3 - b * t3
        else:
            P2 = cap(P3, np.array([sol[k], sol[k + 1]]), chord)
            k += 2
        # Newton step on each parameter: the nearest point of the curve.
        u = 1 - t
        B = bez(P0, P1, P2, P3, t)
        d1 = (3 * u * u)[:, None] * (P1 - P0) + (6 * u * t)[:, None] * (P2 - P1) + (3 * t * t)[:, None] * (P3 - P2)
        d2 = (6 * u)[:, None] * (P2 - 2 * P1 + P0) + (6 * t)[:, None] * (P3 - 2 * P2 + P1)
        diff = B - Q
        num = (diff * d1).sum(1)
        den = (d1 * d1).sum(1) + (diff * d2).sum(1)
        step = np.where(np.abs(den) > 1e-12, num / np.where(np.abs(den) > 1e-12, den, 1), 0)
        t = np.clip(t - step, 0, 1)
        t[0], t[-1] = 0.0, 1.0
        err = np.linalg.norm(bez(P0, P1, P2, P3, t) - Q, axis=1)
        e = err.max()
        if best is None or e < best[1]:
            best = ((P0, P1, P2, P3), e, err)
    return best


def tangent_at(P: np.ndarray, i: int, w: float = 1.5) -> np.ndarray:
    n = len(P)
    k = max(1, int(round(w / SPACING)))
    v = P[(i + k) % n] - P[(i - k) % n]
    return v / (np.linalg.norm(v) + 1e-12)


def one_sided(P: np.ndarray, i: int, direction: int, w: float = 2.0) -> np.ndarray:
    """Tangent leaving node i forward (direction 1) or arriving backward (-1), from a
    line fitted through the points on that side."""
    n = len(P)
    k = max(2, int(round(w / SPACING)))
    idx = [(i + direction * j) % n for j in range(k + 1)]
    pts = P[idx]
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c)
    v = vt[0]
    if np.dot(v, pts[-1] - pts[0]) < 0:
        v = -v
    return v if direction > 0 else -v  # always the direction of travel


def fit_run(P, i0, i1, t0, t3, depth=0):
    """Arcs from node i0 to node i1 (indices into the closed polyline). Returns a list of
    ('curve', P1, P2, end) or ('line', end) and the largest error."""
    n = len(P)
    idx = np.arange(i0, i0 + ((i1 - i0) % n or n) + 1) % n
    Q = P[idx]
    if len(Q) < 4:
        return [["line", Q[-1].copy(), None, None, Q, None, None]], 0.0
    pts, e, err = fit_cubic(Q, t0, t3)
    if e <= TOL or depth > 40 or len(Q) < 6:
        return [["curve", pts[3].copy(), pts[1], pts[2], Q, t0, t3]], e
    # Split where it is worst, as a smooth point with the measured tangent.
    j = int(np.argmax(err[2:-2])) + 2
    m = idx[j]
    tm = tangent_at(P, m)
    if np.dot(tm, Q[min(j + 2, len(Q) - 1)] - Q[max(j - 2, 0)]) < 0:
        tm = -tm
    a, ea = fit_run(P, i0, m, t0, tm, depth + 1)
    b, eb = fit_run(P, m, i1, tm, t3, depth + 1)
    return a + b, max(ea, eb)


# ---------------------------------------------------------------- the structure of a contour

def turn_angles(P):
    n = len(P)
    k = max(1, int(round(CORNER_W / SPACING)))
    a = P - np.roll(P, k, axis=0)
    b = np.roll(P, -k, axis=0) - P
    ang = np.degrees(np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], (a * b).sum(1)))
    return ang, k


def find_corners(P):
    ang, k = turn_angles(P)
    mag = np.abs(ang)
    n = len(P)
    corners = []
    for i in np.argsort(-mag):
        if mag[i] < CORNER_DEG:
            break
        if all(min((i - c) % n, (c - i) % n) > 2 * k for c in corners):
            corners.append(int(i))
    # A corner's exact point: the sharpest within its window, judged at a short reach.
    exact = []
    for c in corners:
        best, bi = -1, c
        for j in range(c - k, c + k + 1):
            jj = j % n
            a = P[jj] - P[(jj - 1) % n]
            b = P[(jj + 1) % n] - P[jj]
            t = abs(math.degrees(math.atan2(a[0] * b[1] - a[1] * b[0], (a * b).sum())))
            if t > best:
                best, bi = t, jj
        exact.append(bi)
    return sorted(set(exact))


def straight_runs(P, nodes):
    """Straight runs between the given nodes: (start, end) index pairs."""
    n = len(P)
    runs = []
    bounds = nodes if nodes else [0]
    spans = [(bounds[i], bounds[(i + 1) % len(bounds)]) for i in range(len(bounds))]
    if not nodes:
        spans = [(0, 0)]
    for s0, s1 in spans:
        length = (s1 - s0) % n or n
        def ok(i, j):
            """Points i..j lie on a straight line: within LINE_TOL of their own best line,
            and bending less than a circle of radius LINE_RADIUS would (a gentle bowl
            is a curve, however flat any stretch of it looks)."""
            a, b = (s0 + i) % n, (s0 + j) % n
            seg = P[np.arange(s0 + i, s0 + j + 1) % n]
            d = P[b] - P[a]
            L = np.linalg.norm(d)
            if L <= 0:
                return False
            u = d / L
            nrm = np.array([-u[1], u[0]])
            rel = seg - P[a]
            s = rel @ u
            h = rel @ nrm
            A = np.stack([np.ones_like(s), s, s * s], 1)
            coef, *_ = np.linalg.lstsq(A, h, rcond=None)
            if abs(2 * coef[2]) > 1 / LINE_RADIUS:
                return False
            A1 = A[:, :2]
            c1, *_ = np.linalg.lstsq(A1, h, rcond=None)
            return np.abs(h - A1 @ c1).max() <= LINE_TOL and np.abs(h).max() <= LINE_TOL * 2

        need = int(math.ceil(LINE_MIN / SPACING))
        i = 0
        while i < length:
            # The longest j with the points from i to j on one line: doubling, then halving.
            good = None
            if i + need <= length and ok(i, i + need):
                lo, step = i + need, need
                while lo + step <= length and ok(i, lo + step):
                    lo += step
                    step *= 2
                hi = min(lo + step, length + 1)
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if ok(i, mid):
                        lo = mid
                    else:
                        hi = mid
                good = lo
            if good is not None and (good - i) * SPACING >= LINE_MIN:
                runs.append(((s0 + i) % n, (s0 + good) % n))
                i = good
            else:
                i += 1
    return runs


def extrema(P, i0, i1):
    """Indices strictly inside a smooth run where x or y turns: the designer's points."""
    n = len(P)
    m = (i1 - i0) % n or n
    idx = np.arange(i0, i0 + m + 1) % n
    Q = P[idx]
    if len(Q) < 7:
        return []
    k = 2
    out = []
    for axis in (0, 1):
        v = Q[:, axis]
        dv = v[k:] - v[:-k]
        sgn = np.sign(dv)
        for j in range(1, len(sgn)):
            if sgn[j] != 0 and sgn[j - 1] != 0 and sgn[j] != sgn[j - 1]:
                c = j + k // 2
                if 4 <= c <= len(Q) - 5:
                    out.append((int(idx[c]), axis, c))
    # Plateaus give runs of flips; keep the middle of points within 3 units.
    out.sort(key=lambda o: o[2])
    merged = []
    for o in out:
        if merged and o[1] == merged[-1][-1][1] and o[2] - merged[-1][-1][2] <= 6:
            merged[-1].append(o)
        else:
            merged.append([o])
    res = []
    for group in merged:
        o = group[len(group) // 2]
        # The extreme itself: the point where the coordinate peaks within the group's reach.
        lo, hi = group[0][2] - 2, group[-1][2] + 2
        seg = Q[max(lo, 0):min(hi, len(Q) - 1) + 1, o[1]]
        c = max(lo, 0) + int(np.argmax(np.abs(seg - seg.mean())))
        if 4 <= c <= len(Q) - 5:
            res.append((int(idx[c]), o[1]))
    return res


def line_error(P, a, b):
    n = len(P)
    seg = P[np.arange(a, a + ((b - a) % n) + 1) % n]
    d = P[b] - P[a]
    L = np.linalg.norm(d)
    if L == 0:
        return 0.0
    nrm = np.array([-d[1], d[0]]) / L
    return float(np.abs((seg - P[a]) @ nrm).max())


def redraw_contour(P: np.ndarray):
    """The new contour as a list of segments (each ending at a node; the contour starts
    where its last segment ends) with the kinds of its nodes, and its largest error."""
    n = len(P)
    corners = find_corners(P)
    runs = straight_runs(P, corners)
    kind = {}          # index -> 'corner' | 'line' | ('ext', axis)
    for c in corners:
        kind[c] = "corner"
    line_end = {}
    # Neighbouring runs that are one line together become one (a stem found in parts).
    merged = []
    for a, b in runs:
        if merged and merged[-1][1] == a and a not in corners and line_error(P, merged[-1][0], b) <= LINE_TOL:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    if len(merged) > 1 and merged[-1][1] == merged[0][0] and merged[0][0] not in corners \
            and line_error(P, merged[-1][0], merged[0][1]) <= LINE_TOL:
        merged[0] = (merged[-1][0], merged[0][1])
        merged.pop()
    runs = merged
    for a, b in runs:
        line_end[a] = b
        kind.setdefault(a, "line")
        kind.setdefault(b, "line")
    nodes = sorted(kind)
    if not nodes:
        top = int(np.argmax(P[:, 1]))
        kind[top] = ("ext", 1)
        nodes = [top]
    # The extremes inside each curved span are the designer's points.
    spans = [(nodes[i], nodes[(i + 1) % len(nodes)]) for i in range(len(nodes))]
    for a, b in spans:
        if line_end.get(a) == b:
            continue
        for e, axis in extrema(P, a, b):
            kind.setdefault(e, ("ext", axis))
    # Nodes closer than 1.5 units are one: a corner outranks a line end, a line end an extreme.
    rank = lambda i: 0 if kind[i] == "corner" else 1 if kind[i] == "line" else 2
    near = max(1, int(round(1.5 / SPACING)))
    changed = True
    while changed and len(kind) > 2:
        changed = False
        order = sorted(kind)
        for x, y in zip(order, order[1:] + order[:1]):
            if x != y and (y - x) % n <= near:
                drop = y if rank(y) >= rank(x) else x
                if kind[drop] == "line":
                    # A line end can only go if its line goes with it: keep both then.
                    if rank(x) == rank(y):
                        continue
                    for a2, b2 in list(line_end.items()):
                        if a2 == drop or b2 == drop:
                            del line_end[a2]
                            runs.remove((a2, b2))
                            other = b2 if a2 == drop else a2
                            if other in kind and kind[other] == "line" and all(other not in r for r in runs):
                                kind[other] = ("ext", 0) if False else kind[other]
                del kind[drop]
                changed = True
                break
    nodes = sorted(kind)
    if len(nodes) == 1:
        j = int(np.argmin(P[:, 1]))
        kind.setdefault(j, ("ext", 1))
        nodes = sorted(kind)

    def run_dir(i):
        for a, b in runs:
            if a == i or b == i:
                d = P[b] - P[a]
                return d / (np.linalg.norm(d) + 1e-12)
        return None

    def node_tangent(i, side):
        """Direction of travel at node i for the arc leaving it (side 1) or arriving
        at it (-1); None leaves the handle free."""
        kd = kind[i]
        if kd == "corner":
            return None
        if isinstance(kd, tuple):
            t = tangent_at(P, i)
            v = np.array([0.0, 1.0]) if kd[1] == 0 else np.array([1.0, 0.0])
            return v if np.dot(v, t) >= 0 else -v
        d = run_dir(i)
        # The arc continues the line only if it leaves in the line's direction.
        arc = one_sided(P, i, side, w=2.0)
        if d is not None and math.degrees(math.acos(max(-1, min(1, float(np.dot(arc, d)))))) < 12:
            return d
        return None

    segs, worst = [], 0.0
    N = len(nodes)
    for k in range(N):
        a, b = nodes[k], nodes[(k + 1) % N]
        if line_end.get(a) == b:
            idx = np.arange(a, a + ((b - a) % n) + 1) % n
            segs.append(["line", P[b].copy(), None, None, P[idx], None, None])
            worst = max(worst, line_error(P, a, b))
            continue
        t0, t3 = node_tangent(a, 1), node_tangent(b, -1)
        s, e = fit_run(P, a, b, t0, t3)
        if e > TOL:
            # A constrained line end that does not fit is a soft corner: free it.
            f0 = None if kind[a] == "line" else t0
            f3 = None if kind[b] == "line" else t3
            if (f0 is None) != (t0 is None) or (f3 is None) != (t3 is None):
                s2, e2 = fit_run(P, a, b, f0, f3)
                if e2 < e:
                    s, e = s2, e2
        segs.extend(s)
        worst = max(worst, e)
    return (segs, [kind[i] for i in nodes]), worst


def seg_line_error(segs, k):
    """How far line k's measurements are from it as it stands now."""
    p, q, Q = segs[k - 1][1], segs[k][1], segs[k][4]
    d = q - p
    L = np.linalg.norm(d)
    return float(np.abs((Q - p) @ (np.array([-d[1], d[0]]) / L)).max()) if L > 0 else 0.0


def snap_axes(contour):
    """Lines that can be made exactly horizontal or vertical by moving their ends no
    more than AXIS_MOVE are made so, unless that takes this line or a neighbouring one
    beyond TOL."""
    segs, kinds = contour
    n = len(segs)
    for k, sg in enumerate(segs):
        if sg[0] != "line":
            continue
        p, q = segs[k - 1][1], sg[1]
        d = q - p
        axis = None
        if abs(d[1]) <= 2 * AXIS_MOVE and abs(d[1]) < abs(d[0]):
            axis = 1
        elif abs(d[0]) <= 2 * AXIS_MOVE and abs(d[0]) < abs(d[1]):
            axis = 0
        if axis is None:
            continue
        before = (p[axis], q[axis])
        m = (p[axis] + q[axis]) / 2
        p[axis] = q[axis] = m
        near = [j % n for j in (k - 1, k, k + 1) if segs[j % n][0] == "line"]
        if any(seg_line_error(segs, j) > TOL for j in near):
            p[axis], q[axis] = before
    return segs, kinds


def curve_error(p0, c1, c2, p3, Q):
    """Largest distance of the measurements Q from the cubic."""
    t = np.linspace(0, 1, max(24, len(Q) * 2))
    B = bez(np.asarray(p0, float), np.asarray(c1, float), np.asarray(c2, float), np.asarray(p3, float), t)
    # Both ways: every measurement near the curve, and every part of the curve near them.
    d1, _ = cKDTree(B).query(Q)
    d2, _ = cKDTree(Q).query(B)
    return float(max(d1.max(), d2.max()))


def handle_options(node, v, guess):
    """Whole-unit positions to try for a handle: along direction v (exactly horizontal
    or vertical directions keep the handle on the node's line) or free."""
    g = GRID
    if v is not None and (abs(v[0]) < 1e-9 or abs(v[1]) < 1e-9):
        L = float(np.dot(guess - node, v)) * g
        return [node + l / g * v for l in (math.floor(L), math.ceil(L))]
    gx, gy = guess * g
    return [np.array([x, y]) / g for x in (math.floor(gx), math.ceil(gx)) for y in (math.floor(gy), math.ceil(gy))]


def realize(contour):
    """The contour on the whole-unit grid: points rounded, then each arc's handles fitted
    again to its measurements with the rounded ends, and of the whole-unit positions next
    to them the pair that fits best kept. Returns the contour and its largest error."""
    segs, kinds = contour
    ends = [np.round(sg[1] * GRID) / GRID for sg in segs]
    out, worst = [], 0.0
    for k, sg in enumerate(segs):
        p0, p3 = ends[k - 1], ends[k]
        if sg[0] == "line":
            Q = sg[4]
            d = p3 - p0
            L = np.linalg.norm(d)
            e = float(np.abs((Q - p0) @ (np.array([-d[1], d[0]]) / L)).max()) if L > 0 else 0.0
            out.append(("line", p3))
            worst = max(worst, e)
            continue
        Q, t0, t3 = sg[4], sg[5], sg[6]
        if np.linalg.norm(p3 - p0) < 2.0:
            out.append(("line", p3))
            continue
        Q = np.vstack([p0, Q[1:-1], p3]) if len(Q) > 2 else Q
        (_, c1, c2, _), e, _ = fit_cubic(Q, t0, t3)
        best = None
        for h1 in handle_options(p0, t0, c1):
            for h2 in handle_options(p3, None if t3 is None else -t3, c2):
                err = curve_error(p0, h1, h2, p3, Q)
                if best is None or err < best[0]:
                    best = (err, h1, h2)
        out.append(("curve", p3, best[1], best[2]))
        worst = max(worst, best[0])
    return out, worst


def draw(contours, pen, scale=1):
    """Draws the contours, in old units (scale 1, for comparing) or the new fonts' finer
    units (scale GRID; whole numbers then)."""
    for segs in contours:
        if scale == 1:
            r = lambda p: (float(p[0]), float(p[1]))
        else:
            r = lambda p: (int(round(p[0] * scale)), int(round(p[1] * scale)))
        s0 = r(segs[-1][1])
        pen.moveTo(s0)
        last = s0
        for i, sg in enumerate(segs):
            end = r(sg[1])
            if sg[0] == "line":
                # The last line back to the start is the contour's own closing.
                if end != last and not (i == len(segs) - 1 and end == s0):
                    pen.lineTo(end)
            else:
                pen.curveTo(r(sg[2]), r(sg[3]), end)
            last = end
        pen.closePath()


def redraw(recording):
    """New contours for a glyph and the largest fitting error in units."""
    out, worst = [], 0.0
    for P in contours_of(recording):
        c, e = redraw_contour(P)
        r, e2 = realize(snap_axes(c))
        out.append(r)
        worst = max(worst, e2)
    return out, worst
