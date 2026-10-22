"""The HD font drawn again: every straight edge one straight line, every corner where its
two edges meet, every round part a few cubic arcs. Drawn over the HD atlas's measured
edge (measure.py); nothing is blurred or smoothed.

Units: 10 per atlas pixel, as the current HD OTFs.
"""
from __future__ import annotations

import math
import numpy as np

import redraw as R
from redraw import SPACING, fit_cubic, realize, draw, contours_of  # noqa: F401

JAG = 2.6          # the measured edge of a straight stroke strays up to this from its line
BOW = 0.6          # a straight stroke does not bow by more than this over its length
RUN_LONG = 20.0    # a straight edge is at least this long (2 atlas pixels)...
RUN_SHORT = 6.0    # ...or this long if its measurements lie within CLEAN of it
CLEAN = 0.3
ARC_RMS = 0.6      # an arc's measurements lie on average within this of it...
ARC_MAX = 1.5      # ...and none further than this
GAP = 80.0         # two straight edges this close may meet in a corner...
CORNER_FIT = 3.0   # ...if the outline between them lies this close to that corner (a square one)
BEND = 30.0        # two straight edges meeting at less than this bend into each other
RELATIVE = 0.006   # a long straight edge may waver by this share of its length (the atlas's own)
AXIS = 1.2         # a line within this of horizontal or vertical over its length is made so


# ---------------------------------------------------------------- straight edges

def tls(pts):
    """The least-squares line through points: a point on it and its direction."""
    c = pts.mean(0)
    d = pts - c
    # The principal direction of the 2 x 2 scatter matrix: the least-squares line.
    _, vec = np.linalg.eigh(d.T @ d)
    u = vec[:, 1]
    if np.dot(u, pts[-1] - pts[0]) < 0:
        u = -u
    return c, u


def straight(pts):
    """One straight edge: its points scatter around one line (the pixel ripple of a
    diagonal) but do not bend away from it."""
    L = np.linalg.norm(pts[-1] - pts[0])
    if L < RUN_SHORT:
        return False
    c, u = tls(pts)
    r = (pts - c) @ np.array([-u[1], u[0]])
    dev = np.abs(r).max()
    if dev <= CLEAN:
        # Short clean pieces count only along the axes or from 12 units: a diagonal's
        # ripple has clean stretches that are not edges of their own.
        axis = min(abs(u[0]), abs(u[1])) < math.sin(math.radians(2))
        return axis or L >= 20.0
    if L < RUN_LONG or dev > max(JAG, RELATIVE * L):
        return False
    s = (pts - c) @ u
    coef, *_ = np.linalg.lstsq(np.stack([np.ones_like(s), s, s * s], 1), r, rcond=None)
    bow = abs(coef[2]) * (L / 2) ** 2
    # Over a few ripples the bend is hard to read; over many it is plain.
    return bow <= (1.0 if L < 4 * RUN_LONG else max(BOW, RELATIVE * L))


def straight_runs(P):
    """Maximal straight runs along the closed outline, as (first, last) indices."""
    n = len(P)
    tries = [int(math.ceil(x / SPACING)) for x in (2 * RUN_LONG, RUN_LONG, RUN_SHORT)]

    def ok(i, j):
        return straight(P[np.arange(i, j + 1) % n])

    # Start where the outline is least straight, so no run is cut by the start.
    start = 0
    runs, i = [], 0
    while i < n:
        a = start + i
        first = None
        for need in tries:
            if i + need < n and ok(a, a + need):
                first = need
                break
        if first is None:
            i += 1
            continue
        lo, step = first, first
        while i + lo + step < n and ok(a, a + lo + step):
            lo += step
            step *= 2
        hi = min(lo + step, n - i)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ok(a, a + mid):
                lo = mid
            else:
                hi = mid
        runs.append([a % n, (a + lo) % n])
        i += lo
    # Neighbouring runs that together are still one straight line are one.
    def one_line(j0, j1, k0, k1):
        """Runs j0..j1 and k0..k1 are one line: together still straight, and (if both
        are long) in nearly the same direction."""
        A = P[np.arange(j0, j0 + ((j1 - j0) % n) + 1) % n]
        B = P[np.arange(k0, k0 + ((k1 - k0) % n) + 1) % n]
        if min(len(A), len(B)) * SPACING >= 60.0:
            if np.dot(tls(A)[1], tls(B)[1]) < math.cos(math.radians(1.5)):
                return False
        return straight(P[np.arange(j0, j0 + ((k1 - j0) % n) + 1) % n])

    merged = []
    for r in runs:
        if merged and (r[0] - merged[-1][1]) % n * SPACING <= 12.0 and one_line(merged[-1][0], merged[-1][1], r[0], r[1]):
            merged[-1][1] = r[1]
            continue
        merged.append(r)
    runs = merged
    # A run that ends where the first one starts may continue it round the start.
    if len(runs) > 1 and runs[-1][1] == runs[0][0]:
        j0, j1 = runs[-1][0], runs[0][1]
        if straight(P[np.arange(j0, j0 + ((j1 - j0) % n) + 1) % n]):
            runs[0][0] = j0
            runs.pop()
    return [tuple(r) for r in runs]


def meet(c1, u1, c2, u2):
    den = u1[0] * u2[1] - u1[1] * u2[0]
    if abs(den) < math.sin(math.radians(10)):
        return None
    d = c2 - c1
    return c1 + (d[0] * u2[1] - d[1] * u2[0]) / den * u1


# ---------------------------------------------------------------- arcs

def fit_arc(P, i0, i1, p0, p3, t0, t3, depth=0):
    """Cubic arcs from p0 to p3 through the measurements P[i0..i1]. Accepted when their
    distance from the measurements is ARC_RMS on average and ARC_MAX at most; split at
    the worst point otherwise."""
    n = len(P)
    idx = np.arange(i0, i0 + ((i1 - i0) % n or n) + 1) % n
    Q = P[idx].copy()
    Q[0], Q[-1] = p0, p3
    if len(Q) < 4 or np.linalg.norm(p3 - p0) < 1.0:
        return [["line", p3.copy(), None, None, Q, None, None]]
    pts, e, err = fit_cubic(Q, t0, t3)
    rms = float(np.sqrt((err ** 2).mean()))
    if (rms <= ARC_RMS and e <= ARC_MAX) or depth > 30 or len(Q) < 12:
        return [["curve", p3.copy(), pts[1], pts[2], Q, t0, t3]]
    j = int(np.argmax(err[3:-3])) + 3
    m = idx[j]
    # The split point and its direction from the line through the points around it.
    k = max(3, int(round(4.0 / SPACING)))
    near = P[np.arange(m - k, m + k + 1) % n]
    c, u = tls(near)
    pm = c + np.dot(P[m] - c, u) * u
    return fit_arc(P, i0, m, p0, pm, t0, u, depth + 1) + fit_arc(P, m, i1, pm, p3, u, t3, depth + 1)


def extremes(P, i0, i1):
    """The extremes of a round part (where it runs horizontal or vertical): their indices,
    the axis, and the point itself from a parabola through the points around it."""
    n = len(P)
    idx = np.arange(i0, i0 + ((i1 - i0) % n or n) + 1) % n
    Q = P[idx]
    m = len(Q)
    w = int(round(6.0 / SPACING))
    if m < 4 * w:
        return []
    res = []
    for axis in (0, 1):
        v = Q[:, axis]
        # Points that are the largest or smallest within 6 units either way; a flat
        # stretch at an extreme gives a row of them, and its middle is the point.
        for sign in (1, -1):
            cand = [j for j in range(w, m - w) if sign * v[j] >= sign * v[j - w:j + w + 1].max() * (1 if sign > 0 else 1) - 1e-9
                    and (sign * v[j]) >= max(sign * v[j - w:j + w + 1]) - 1e-9]
            groups = []
            for j in cand:
                if groups and j - groups[-1][-1] <= 2:
                    groups[-1].append(j)
                else:
                    groups.append([j])
            for g in groups:
                j = g[len(g) // 2]
                # A real extreme: the outline goes back on both sides of it.
                lo, hi = max(0, g[0] - 3 * w), min(m - 1, g[-1] + 3 * w)
                if sign * (v[j] - v[lo]) < 0.3 or sign * (v[j] - v[hi]) < 0.3:
                    continue
                if j < 2 * w or j > m - 2 * w:
                    continue
                p = Q[j].copy()
                if len(g) <= 2:
                    # A rounded extreme: the vertex of a parabola through the points around it.
                    o = 1 - axis
                    near = Q[max(0, j - w):j + w + 1]
                    ref = near[:, o].mean()
                    coef = np.polyfit(near[:, o] - ref, near[:, axis], 2)
                    if abs(coef[0]) > 1e-9:
                        t = -coef[1] / (2 * coef[0])
                        if abs(t) <= np.ptp(near[:, o]):
                            p[o] = t + ref
                            p[axis] = np.polyval(coef, t)
                else:
                    # A flat extreme: its line, at the middle.
                    p[axis] = Q[g, axis].mean()
                res.append((j, axis, int(idx[j]), p))
    return [(gi, axis, p) for _, axis, gi, p in res]


# ---------------------------------------------------------------- one outline

def angle_between(u1, u2):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(u1, u2))))))


def seg_dist(q, a, b):
    d = b - a
    t = np.clip(((q - a) @ d) / max(np.dot(d, d), 1e-12), 0, 1)
    return np.linalg.norm(q - (a + t[:, None] * d), axis=1)


def redraw_contour(P):
    n = len(P)
    runs = straight_runs(P)
    span = lambda a, b: P[np.arange(a, a + ((b - a) % n) + 1) % n]
    L = [dict(a=a, b=b, line=tls(span(a, b))) for a, b in runs]
    length = lambda r: ((r["b"] - r["a"]) % n) * SPACING

    # A short straight piece in a chain of pieces bending gently into each other is a
    # piece of a curve: it goes back to the curve.
    def bends_gently(r1, r2):
        return ((r2["a"] - r1["b"]) % n) * SPACING <= 20.0 and 2.0 <= angle_between(r1["line"][1], r2["line"][1]) < 45.0
    if len(L) > 1:
        drop = set()
        for k, r in enumerate(L):
            if length(r) >= 45.0:
                continue
            if bends_gently(L[k - 1], r) or bends_gently(r, L[(k + 1) % len(L)]):
                drop.add(k)
        L = [r for k, r in enumerate(L) if k not in drop]

    nodes = {}
    for r in L:
        c, u = r["line"]
        for idx in (r["a"], r["b"]):
            nodes.setdefault(idx, {"kind": "line", "pos": c + np.dot(P[idx] - c, u) * u})

    for k in range(len(L)):
        if len(L) < 2:
            break
        r1, r2 = L[k], L[(k + 1) % len(L)]
        gap = (r2["a"] - r1["b"]) % n
        if gap * SPACING > GAP:
            continue
        ang = angle_between(r1["line"][1], r2["line"][1])
        if ang < 2.0 and straight(span(r1["a"], r2["b"])):
            # Two pieces of one straight edge.
            nodes.pop(r1["b"], None)
            nodes.pop(r2["a"], None)
            r1["b"] = r2["a"]
            r2["a"] = r1["b"]
            nodes[r1["b"]] = {"kind": "line", "pos": r2["line"][0] + np.dot(P[r1["b"]] - r2["line"][0], r2["line"][1]) * r2["line"][1]}
            continue
        if ang < BEND:
            # A gentle bend between two straight edges is a curve: room for an arc
            # tangent to both, taken from the ends of the lines.
            if gap * SPACING < 12.0:
                t = int(round(min(12.0, length(r1) / 4, length(r2) / 4) / SPACING))
                for idx in (r1["b"], r2["a"]):
                    nodes.pop(idx, None)
                r1["b"] = (r1["b"] - t) % n
                r2["a"] = (r2["a"] + t) % n
                for r, idx in ((r1, r1["b"]), (r2, r2["a"])):
                    c, u = r["line"]
                    nodes[idx] = {"kind": "line", "pos": c + np.dot(P[idx] - c, u) * u}
            continue
        m = meet(*r1["line"], *r2["line"])
        if m is None or np.linalg.norm(m - P[r1["b"]]) > GAP:
            continue
        # The outline between the two edges must follow the sharp corner they make.
        between = P[np.arange(r1["b"], r1["b"] + gap + 1) % n]
        c1, u1 = r1["line"]
        c2, u2 = r2["line"]
        e1 = c1 + np.dot(P[r1["b"]] - c1, u1) * u1
        e2 = c2 + np.dot(P[r2["a"]] - c2, u2) * u2
        # Anti-aliasing fills an acute corner's tip more than a square one's.
        half = math.radians(180.0 - ang) / 2
        allow = min(CORNER_FIT / max(math.sin(half), 0.2), 8.0)
        # A stroke's cut end: a short horizontal or vertical edge against a long stroke.
        # Its corners are sharp however much the small sizes blur them.
        def is_cut(r):
            u = r["line"][1]
            return length(r) < 60.0 and min(abs(u[0]), abs(u[1])) < math.sin(math.radians(3))
        if (is_cut(r1) and length(r2) >= 80.0) or (is_cut(r2) and length(r1) >= 80.0):
            allow = max(allow, 10.0)
        # Both edges end close to the corner, the outline between follows it, and the
        # corner itself is where the outline turns (not out in the open).
        if np.linalg.norm(m - e1) > 2 * allow + 3 or np.linalg.norm(m - e2) > 2 * allow + 3:
            continue
        near_pts = np.vstack([between, e1[None], e2[None]])
        if np.linalg.norm(near_pts - m, axis=1).min() > allow:
            continue
        if len(between) > 2 and np.minimum(seg_dist(between, e1, m), seg_dist(between, m, e2)).max() > allow:
            continue
        nodes.pop(r1["b"], None)
        nodes.pop(r2["a"], None)
        r1["b"] = r2["a"] if gap == 0 else r1["b"]
        nodes[r1["b"]] = {"kind": "corner", "pos": m}
        r2["a"] = r1["b"]
    keep = []
    for r in L:
        corners = (nodes.get(r["a"], {}).get("kind") == "corner") + (nodes.get(r["b"], {}).get("kind") == "corner")
        # A short straight edge runs between corners (a stroke's cut end); in the
        # middle of a curve it is a chord of that curve.
        if not (length(r) >= 80.0 or corners == 2 or (corners == 1 and length(r) >= 40.0)):
            for idx in (r["a"], r["b"]):
                if nodes.get(idx, {}).get("kind") == "line" and not any(o is not r and idx in (o["a"], o["b"]) for o in L):
                    nodes.pop(idx, None)
            continue
        keep.append(r)
    L = keep
    ends = {r["b"]: r for r in L}
    starts = {r["a"]: r for r in L}

    # Round parts between straight edges: their extremes are points, horizontal or vertical.
    if not nodes:
        # A round outline: it starts at its top, and its extremes are found from there.
        top = int(np.argmax(P[:, 1]))
        nodes[top] = {"kind": ("ext", 1), "pos": P[top].copy()}
    order = sorted(nodes)
    spans = [(order[i], order[(i + 1) % len(order)]) for i in range(len(order))]
    for a, b in spans:
        if a in starts and starts[a]["b"] == b:
            continue
        for gi, axis, p in extremes(P, a, b):
            if gi not in nodes:
                nodes[gi] = {"kind": ("ext", axis), "pos": p}
    if not nodes:
        top = int(np.argmax(P[:, 1]))
        nodes[top] = {"kind": ("ext", 1), "pos": P[top].copy()}
    if len(nodes) == 1:
        bot = int(np.argmin(P[:, 1]))
        nodes[bot] = {"kind": ("ext", 1), "pos": P[bot].copy()}
    order = sorted(nodes)

    def direction(i, side):
        """The direction the outline travels at node i, for the arc leaving (1) or
        arriving (-1); None leaves it free."""
        nd = nodes[i]
        if isinstance(nd["kind"], tuple):
            axis = nd["kind"][1]
            v = np.array([0.0, 1.0]) if axis == 0 else np.array([1.0, 0.0])
            ahead = P[(i + 4) % n] - P[(i - 4) % n]
            return v if np.dot(v, ahead) >= 0 else -v
        if nd["kind"] == "corner":
            return None
        r = starts.get(i) if side == -1 else ends.get(i)
        if r is None:
            return None
        u = r["line"][1]
        # The arc carries on in the line's direction only if it really leaves that way.
        k = int(round(4.0 / SPACING))
        far = P[(i + side * k) % n] - P[i]
        if side == -1:
            far = -far
        cosang = np.dot(far, u) / (np.linalg.norm(far) + 1e-12)
        return u if cosang > math.cos(math.radians(15)) else None

    segs = []
    for k in range(len(order)):
        a, b = order[k], order[(k + 1) % len(order)]
        if a in starts and starts[a]["b"] == b:
            segs.append(["line", nodes[b]["pos"].copy(), None, None,
                         P[np.arange(a, a + ((b - a) % n) + 1) % n], None, None])
            continue
        segs.extend(fit_arc(P, a, b, nodes[a]["pos"], nodes[b]["pos"], direction(a, 1), direction(b, -1)))
    return segs


def square_lines(segs):
    """A line within AXIS of horizontal or vertical over its length is made exactly so."""
    for k, sg in enumerate(segs):
        if sg[0] != "line":
            continue
        p, q = segs[k - 1][1], sg[1]
        d = q - p
        if abs(d[1]) <= AXIS and abs(d[1]) < abs(d[0]):
            p[1] = q[1] = (p[1] + q[1]) / 2
        elif abs(d[0]) <= AXIS and abs(d[0]) < abs(d[1]):
            p[0] = q[0] = (p[0] + q[0]) / 2
    return segs


def redraw(recording=None, loops=None, name=None):
    """From the HD atlas's measured outlines (loops), or an outline recording. The rings
    of the copyright and registered signs are exact circles or ovals (rings.py)."""
    import rings
    loops = loops if loops is not None else contours_of(recording)
    exact = {}
    if name in rings.RING_GLYPHS:
        got = rings.ring_contours(loops, R.GRID)
        if got:
            exact = got[0]
    out = []
    for i, P in enumerate(loops):
        if i in exact:
            out.append(exact[i])
            continue
        segs = square_lines(redraw_contour(P))
        r, _ = realize((segs, None))
        out.append(r)
    return out, 0.0
