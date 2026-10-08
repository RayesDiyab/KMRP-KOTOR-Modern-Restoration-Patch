"""A measured boundary turned into exact geometry.

    regularize(contour_px) -> shape, (stray mean, stray max), made

The boundary (a closed chain of pixels) is rebuilt from four kinds of piece, each fitted by least squares:
    circle / ellipse   the whole boundary, when it keeps to one
    arc                a stretch that runs along a circle (50 degrees of it or more, or from corner to corner)
    line               a straight stretch; its direction is set on a multiple of 15 degrees when within 2.2 of one
    curve              anything else: cubic Bezier curves (Schneider's fitting), tangent-continuous from piece to piece
Corners are found by measurement (the turn of the boundary at two scales: at a corner it is the same at both, on a
curve it halves with the scale); only at a corner may the direction jump. Pieces meet where they intersect.

shape is one of
    ["circle", cx, cy, r]      ["ellipse", cx, cy, rx, ry, degrees]
    ["path", [["M", x, y], ["L", x, y], ["A", cx, cy, r, a0, a1], ["C", x1, y1, x2, y2, x, y], ...]]
All lengths in units of the 32-unit frame; angles of arcs in radians (atan2 of y - cy, x - cx; y runs down).
"""
import math
import numpy as np
import cv2
from scipy import ndimage as ndi

K = 16.0                       # pixels per unit (512 / 32)
T = dict(
    circle_tol=0.13, circle_min=4.0, arc_sweep=0.87,       # arcs found by consensus: tolerance, least length, least sweep (rad)
    line_tol=0.11,             # a whole stretch between two corners within this of its chord is a line
    dp=0.07, line_min=1.6,     # inside a longer stretch: runs within `dp` of a chord and at least this long are lines
    facet=2.5,                 # degrees: two lines meeting at more than this without a corner are facets of a curve
    corner=28.0, corner_ratio=0.72,
    curve_tol=0.11,            # Bezier fitting tolerance
    ellipse_tol=0.11,
    snap=2.2,
)
RNG = np.random.default_rng(7)
# STRICT: the outline is built from straight lines and circular arcs ONLY (no free curves): a stretch that is nearly
# straight is a line, anything curved is a chain of circular arcs; lines of nearly one direction are made exactly
# parallel. For the flat symbols, which are drawn with a ruler and compasses.
STRICT = False


def unit(v):
    L = math.hypot(v[0], v[1])
    return v / L if L > 1e-12 else np.array([1.0, 0.0])


def lsq_circle(pts):
    A = np.c_[2 * pts, np.ones(len(pts))]
    (cx, cy, k), *_ = np.linalg.lstsq(A, (pts ** 2).sum(axis=1), rcond=None)
    return cx, cy, math.sqrt(max(k + cx * cx + cy * cy, 1e-9))


def runs_of(flags):
    """Cyclic runs of True: [(start, length)]."""
    n = len(flags)
    if flags.all():
        return [(0, n)]
    out, start, length = [], None, 0
    first_false = int(np.argmin(flags))
    for k in range(n + 1):
        i = (first_false + k) % n
        on = bool(flags[i]) and k < n
        if on and start is None:
            start, length = i, 0
        if on:
            length += 1
        if not on and start is not None:
            out.append((start, length)); start = None
    return out


def resample(contour_px):
    """The pixel chain as points one pixel apart along its length, the staircase smoothed out; in units."""
    p = contour_px.astype(np.float64) + 0.5
    nxt = np.roll(p, -1, axis=0)
    d = np.hypot(*(nxt - p).T)
    s = np.r_[0, np.cumsum(d)]
    m = max(8, int(round(s[-1])))
    t = np.arange(m) * s[-1] / m
    q = np.c_[np.interp(t, s, np.r_[p[:, 0], p[0, 0]]), np.interp(t, s, np.r_[p[:, 1], p[0, 1]])]
    q = np.c_[ndi.gaussian_filter1d(q[:, 0], 1.2, mode="wrap"), ndi.gaussian_filter1d(q[:, 1], 1.2, mode="wrap")]
    return q / K


def find_corners(q):
    m = len(q)
    w1 = max(3, min(int(round(0.7 * K)), m // 6))
    w2 = max(2, w1 // 2)

    def turn(w):
        a = np.roll(q, -w, axis=0) - q
        b = q - np.roll(q, w, axis=0)
        return np.angle(np.exp(1j * (np.arctan2(a[:, 1], a[:, 0]) - np.arctan2(b[:, 1], b[:, 0]))))
    t1, t2 = turn(w1), turn(w2)
    strong = (np.abs(t1) > math.radians(T["corner"])) & (np.abs(t2) > T["corner_ratio"] * np.abs(t1)) & (np.sign(t1) == np.sign(t2))
    score = np.where(strong, np.abs(t1) + np.abs(t2), 0.0)
    taken = np.zeros(m, bool)
    out = []
    for i in np.argsort(-score):
        if score[i] <= 0:
            break
        if taken[i]:
            continue
        out.append(int(i))
        taken[(i + np.arange(-w1, w1 + 1)) % m] = True
    return sorted(out)


def find_arcs(q, max_circles=3):
    """Circles the curve runs along for a good stretch. Returns a label per point (-1 or the circle's index) and the circles."""
    n = len(q)
    label = np.full(n, -1, np.int32)
    circles = []
    least = max(12, int(T["circle_min"] * K))
    for _ in range(max_circles):
        free = np.nonzero(label < 0)[0]
        if len(free) < least:
            break
        best = None
        for _t in range(300):
            i, j, k = q[RNG.choice(free, 3, replace=False)]
            d = 2 * (i[0] * (j[1] - k[1]) + j[0] * (k[1] - i[1]) + k[0] * (i[1] - j[1]))
            if abs(d) < 1e-9:
                continue
            ux = ((i @ i) * (j[1] - k[1]) + (j @ j) * (k[1] - i[1]) + (k @ k) * (i[1] - j[1])) / d
            uy = ((i @ i) * (k[0] - j[0]) + (j @ j) * (i[0] - k[0]) + (k @ k) * (j[0] - i[0])) / d
            r = math.hypot(i[0] - ux, i[1] - uy)
            if r < 0.8 or r > 48:
                continue
            on = (np.abs(np.hypot(q[:, 0] - ux, q[:, 1] - uy) - r) <= T["circle_tol"]) & (label < 0)
            if best is None or on.sum() > best[0]:
                best = (int(on.sum()), ux, uy, r)
        if best is None or best[0] < least:
            break
        _, cx, cy, r = best
        for _i in range(4):
            on = (np.abs(np.hypot(q[:, 0] - cx, q[:, 1] - cy) - r) <= T["circle_tol"]) & (label < 0)
            if on.sum() < 8:
                break
            cx, cy, r = lsq_circle(q[on])
        on = (np.abs(np.hypot(q[:, 0] - cx, q[:, 1] - cy) - r) <= 1.3 * T["circle_tol"]) & (label < 0)
        gap = max(2, int(0.35 * K))
        closed = on.copy()
        for s, L in runs_of(~on):
            if L <= gap:
                idx = (s + np.arange(L)) % n
                closed[idx] = label[idx] < 0
        # the curve must run ALONG the circle (not double back beside it), and for a good sweep
        th = np.arctan2(q[:, 1] - cy, q[:, 0] - cx)
        step = max(2, int(0.25 * K))
        dth = np.angle(np.exp(1j * (np.roll(th, -step) - th)))
        expect = step / (r * K)
        along = np.abs(np.abs(dth) - expect) <= 0.6 * expect
        keep = np.zeros(n, bool)
        for s, L in runs_of(closed & along):
            idx = (s + np.arange(L)) % n
            if L / (K * r) >= T["arc_sweep"] and L >= 1.4 * K and abs(np.sign(dth[idx]).mean()) > 0.9:
                keep[idx] = True
        if keep.sum() < least:
            break
        label[keep] = len(circles)
        circles.append((float(cx), float(cy), float(r)))
    return label, circles


def dp_indices(pts, eps):
    n = len(pts)
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        seg = pts[a:b + 1]
        ch = pts[b] - pts[a]
        L = math.hypot(*ch)
        d = np.hypot(*(seg - pts[a]).T) if L < 1e-9 else np.abs((seg[:, 0] - pts[a, 0]) * ch[1] - (seg[:, 1] - pts[a, 1]) * ch[0]) / L
        i = int(np.argmax(d))
        if d[i] > eps:
            keep[a + i] = True
            stack.append((a, a + i)); stack.append((a + i, b))
    return np.nonzero(keep)[0]


# ---- cubic Bezier fitting (P. Schneider, "An Algorithm for Automatically Fitting Digitized Curves") ----------------
def bez_eval(c, t):
    mt = 1 - t
    return (mt ** 3)[:, None] * c[0] + (3 * mt * mt * t)[:, None] * c[1] + (3 * mt * t * t)[:, None] * c[2] + (t ** 3)[:, None] * c[3]


def _generate(pts, u, t1, t2):
    p0, p3 = pts[0], pts[-1]
    b0, b1, b2, b3 = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
    A1, A2 = b1[:, None] * t1, b2[:, None] * t2
    c00, c01, c11 = (A1 * A1).sum(), (A1 * A2).sum(), (A2 * A2).sum()
    tmp = pts - (p0[None] * (b0 + b1)[:, None] + p3[None] * (b2 + b3)[:, None])
    x0, x1 = (A1 * tmp).sum(), (A2 * tmp).sum()
    det = c00 * c11 - c01 * c01
    seg = math.hypot(*(p3 - p0))
    a1 = a2 = 0.0
    if abs(det) > 1e-12:
        a1, a2 = (x0 * c11 - x1 * c01) / det, (c00 * x1 - c01 * x0) / det
    path = float(np.hypot(*(pts[1:] - pts[:-1]).T).sum())
    if a1 < 1e-6 * max(seg, 1e-6) or a2 < 1e-6 * max(seg, 1e-6) or a1 > 1.5 * path or a2 > 1.5 * path:
        a1 = a2 = max(seg, 0.3 * path) / 3.0
    return np.array([p0, p0 + t1 * a1, p3 + t2 * a2, p3])


def _reparam(pts, c, u):
    d = bez_eval(c, u) - pts
    q1 = 3 * (c[1:] - c[:-1]); q2 = 2 * (q1[1:] - q1[:-1])
    mt = 1 - u
    d1 = (mt * mt)[:, None] * q1[0] + (2 * mt * u)[:, None] * q1[1] + (u * u)[:, None] * q1[2]
    d2 = mt[:, None] * q2[0] + u[:, None] * q2[1]
    num = (d * d1).sum(1); den = (d1 * d1).sum(1) + (d * d2).sum(1)
    return np.clip(np.where(np.abs(den) > 1e-12, u - num / np.where(den == 0, 1, den), u), 0, 1)


def fit_curve(pts, t1, t2, tol, depth=0):
    """Cubic Beziers through pts within tol. t1: direction leaving the first point; t2: direction leaving the last
    point back into the curve."""
    m = len(pts)
    if m <= 2:
        d = math.hypot(*(pts[-1] - pts[0])) / 3.0
        return [np.array([pts[0], pts[0] + t1 * d, pts[-1] + t2 * d, pts[-1]])]
    d = np.hypot(*(pts[1:] - pts[:-1]).T)
    u = np.r_[0, np.cumsum(d)]
    if u[-1] < 1e-9:
        return [np.array([pts[0], pts[0], pts[-1], pts[-1]])]
    u = u / u[-1]
    c = _generate(pts, u, t1, t2)
    e = np.hypot(*(bez_eval(c, u) - pts).T)
    if e.max() <= tol or depth > 12:
        return [c]
    if e.max() <= 4 * tol:
        for _ in range(4):
            u = _reparam(pts, c, u)
            c = _generate(pts, u, t1, t2)
            e = np.hypot(*(bez_eval(c, u) - pts).T)
            if e.max() <= tol:
                return [c]
    s = int(np.clip(np.argmax(e), 1, m - 2))
    tc = unit(pts[max(s - 2, 0)] - pts[min(s + 2, m - 1)])
    return fit_curve(pts[:s + 1], t1, tc, tol, depth + 1) + fit_curve(pts[s:], -tc, t2, tol, depth + 1)


# ---- the pieces ------------------------------------------------------------------------------------------------------
def snap_dir(d):
    ang = math.degrees(math.atan2(d[1], d[0]))
    near = round(ang / 15.0) * 15.0
    if abs(ang - near) <= T["snap"]:
        ang = near
    a = math.radians(ang)
    return np.array([math.cos(a), math.sin(a)])


def tessellate(prims, bez_step=0.1):
    pts = []
    x = y = 0.0
    for p in prims:
        if p[0] in ("M", "L"):
            x, y = p[1], p[2]
            pts.append((x, y))
        elif p[0] == "A":
            _, cx, cy, r, a0, a1 = p
            n = max(2, int(math.ceil(abs(a1 - a0) / math.sqrt(8 * 0.003 / max(r, 0.05)))))
            for i in range(1, n + 1):
                a = a0 + (a1 - a0) * i / n
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            x, y = pts[-1]
        elif p[0] == "C":
            c = np.array([[x, y], [p[1], p[2]], [p[3], p[4]], [p[5], p[6]]])
            L = float(np.hypot(*(c[1:] - c[:-1]).T).sum())
            n = max(3, int(math.ceil(L / bez_step)))
            for pt in bez_eval(c, np.arange(1, n + 1) / n):
                pts.append((float(pt[0]), float(pt[1])))
            x, y = p[5], p[6]
    return np.array(pts)


def _stray(shape_pts, q):
    poly = (shape_pts * K).astype(np.float32).reshape(-1, 1, 2)
    sample = q[:: max(1, len(q) // 240)] * K
    d = np.array([abs(cv2.pointPolygonTest(poly, (float(x), float(y)), True)) for x, y in sample]) / K
    return float(d.mean()), float(d.max())


def regularize(contour):
    made = dict(circles=0, ellipses=0, arcs=0, lines=0, curves=0)
    q = resample(contour)
    m = len(q)
    if m < 16:
        prims = [["M", round(q[0, 0], 3), round(q[0, 1], 3)]] + [["L", round(x, 3), round(y, 3)] for x, y in q[1::2]]
        return ["path", prims], (0.0, 0.0), made
    on_frame = np.minimum(np.minimum(q[:, 0], 32 - q[:, 0]), np.minimum(q[:, 1], 32 - q[:, 1])) < 0.14
    drawn = ~on_frame
    area = cv2.contourArea(contour.reshape(-1, 1, 2).astype(np.int32)) / (K * K)
    # ---- one circle?
    if drawn.sum() >= 24:
        cx, cy, r = lsq_circle(q[drawn])
        for _ in range(2):
            dev = np.abs(np.hypot(q[:, 0] - cx, q[:, 1] - cy) - r)
            cx, cy, r = lsq_circle(q[drawn & (dev <= np.percentile(dev[drawn], 90))])
        dev = np.abs(np.hypot(q[:, 0] - cx, q[:, 1] - cy) - r)[drawn]
        ang = np.degrees(np.arctan2(q[drawn, 1] - cy, q[drawn, 0] - cx))
        covered = len(np.unique(np.round(ang / 10.0))) * 10.0
        full = math.pi * r * r
        whole = bool(drawn.all())
        if (r >= 0.6 and np.percentile(dev, 50) <= max(0.1, 0.015 * r) and np.percentile(dev, 90) <= max(0.26, 0.042 * r) and covered >= (200 if whole else 110)
                and (abs(area - full) <= 0.12 * full if whole else 0.45 * full <= area <= 1.05 * full)):
            made["circles"] = 1
            return ["circle", round(cx, 4), round(cy, 4), round(r, 4)], (float(dev.mean()), float(dev.max())), made
    corners = find_corners(q)
    # ---- one ellipse?
    if not corners and drawn.all() and m >= 30:
        (ex, ey), (ma, mi), deg = cv2.fitEllipse((q * K).astype(np.float32))
        if min(ma, mi) > 0.5 * K:
            t = np.linspace(0, 2 * math.pi, 181)[:-1]
            co, si = math.cos(math.radians(deg)), math.sin(math.radians(deg))
            ep = np.c_[ex + ma / 2 * np.cos(t) * co - mi / 2 * np.sin(t) * si, ey + ma / 2 * np.cos(t) * si + mi / 2 * np.sin(t) * co] / K
            mean, worst = _stray(ep, q)
            if worst <= T["ellipse_tol"] * 1.6 and mean <= T["ellipse_tol"] * 0.5:
                made["ellipses"] = 1
                return ["ellipse", round(ex / K, 4), round(ey / K, 4), round(ma / 2 / K, 4), round(mi / 2 / K, 4), round(deg, 2)], (mean, worst), made
    label, circles = find_arcs(q)
    is_corner = np.zeros(m, bool)
    is_corner[corners] = True
    near_corner = lambda i: bool(is_corner[(i + np.arange(-4, 5)) % m].any())
    P = lambda a, b: q[np.arange(a, b + 1) % m]                    # the points of a piece (b may run past m)

    def fit_line(p):
        pts = P(p["a"], p["b"])
        trim = int(0.12 * len(pts)) if len(pts) >= 12 else 0
        core = pts[trim:len(pts) - trim]
        mid = core.mean(axis=0)
        _, _, vt = np.linalg.svd(core - mid)
        d = vt[0] if vt[0] @ (pts[-1] - pts[0]) >= 0 else -vt[0]
        p["mid"], p["d"] = mid, snap_dir(d)
        return p

    def arc_pieces(a, b, cs, depth=0):
        """A stretch as straight lines and circular arcs only: one line if it is straight (to within 2 per cent of its
        length), else one arc if it keeps to a circle, else cut where it strays most from its chord and each part again."""
        pts = P(a, b)
        n_ = len(pts)
        ch = pts[-1] - pts[0]
        L = math.hypot(*ch)
        dev = np.abs((pts[:, 0] - pts[0, 0]) * ch[1] - (pts[:, 1] - pts[0, 1]) * ch[0]) / max(L, 1e-9)
        if L >= 0.3 and (n_ < 6 or dev.max() <= max(0.14, 0.02 * L)) and b - a < m:
            return [fit_line(dict(kind="line", a=a, b=b, cs=cs))]
        if n_ >= 6:
            cx, cy, r = lsq_circle(pts)
            path = float(np.hypot(*(pts[1:] - pts[:-1]).T).sum())
            d = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r)
            if 0.3 <= r <= 80 and d.max() <= max(0.13, 0.016 * path) and b - a < m:
                return [dict(kind="arc", a=a, b=b, cs=cs, circle=(float(cx), float(cy), float(r)))]
        if depth >= 5 or n_ < 16:
            return [dict(kind="free", a=a, b=b, cs=cs)]
        k = int(np.clip(np.argmax(dev), n_ // 5, n_ - 1 - n_ // 5)) if L > 0.3 else n_ // 2
        return arc_pieces(a, a + k, cs, depth + 1) + arc_pieces(a + k, b, False, depth + 1)

    def split_open(a, b, cs):
        """A stretch with no corner inside: lines where it runs straight, free curve between."""
        pts = P(a, b)
        n = len(pts)
        ch = pts[-1] - pts[0]
        L = math.hypot(*ch)
        if n < 6:
            return [dict(kind="free", a=a, b=b, cs=cs)]
        dev = np.abs((pts[:, 0] - pts[0, 0]) * ch[1] - (pts[:, 1] - pts[0, 1]) * ch[0]) / max(L, 1e-9)
        # (a long stretch may stray a little more: within 1.2 per cent of its length it is straight. The bottom edge
        # of a bust, 20 units long and soft, wavered by 0.2 and was fitted as a row of shallow curves.)
        if L >= 0.5 and dev.max() <= max(T["line_tol"], 0.012 * L) and b - a < m:
            return [fit_line(dict(kind="line", a=a, b=b, cs=cs))]
        if STRICT:
            return arc_pieces(a, b, cs)
        idx = dp_indices(pts, T["dp"])
        out = []
        for i0, i1 in zip(idx[:-1], idx[1:]):
            long = math.hypot(*(pts[i1] - pts[i0])) >= T["line_min"]
            kind = "line" if long else "free"
            if out and kind == "free" and out[-1]["kind"] == "free":
                out[-1]["b"] = a + int(i1)
            else:
                out.append(dict(kind=kind, a=a + int(i0), b=a + int(i1), cs=cs if not out else False))
        for p in out:
            if p["kind"] == "line":
                fit_line(p)
        return out

    # ---- the boundary as a cycle of pieces
    change = label != np.roll(label, 1)
    brk = np.nonzero(is_corner | change)[0]
    pieces = []
    if len(brk) == 0:
        far = int(np.argmax(np.hypot(*(q - q.mean(axis=0)).T)))
        pieces = split_open(far, far + m, False)
    else:
        for j, a in enumerate(brk):
            a = int(a)
            b = int(brk[(j + 1) % len(brk)])
            if b <= a:
                b += m
            cs = near_corner(a)
            if label[a] >= 0:
                pieces.append(dict(kind="arc", a=a, b=b, cs=cs, circle=circles[label[a]]))
            else:
                pieces += split_open(a, b, cs)
    # ---- facets: two lines meeting without a corner are one line (same direction) or parts of a curve (not)
    changed = True
    while changed and len(pieces) > 1:
        changed = False
        for k in range(len(pieces)):
            A, B = pieces[k - 1], pieces[k]
            if A["kind"] == "line" and B["kind"] == "line" and not B["cs"]:
                ang = math.degrees(math.acos(float(np.clip(A["d"] @ B["d"], -1, 1))))
                if ang <= (4.0 if STRICT else T["facet"]):
                    A["b"] = B["b"] if B["b"] > A["a"] else B["b"] + m
                    fit_line(A)
                    pieces.pop(k)
                elif STRICT:
                    B["cs"] = True                                 # two straight lines at an angle: a corner
                else:
                    A["kind"] = B["kind"] = "free"
                changed = True
                break
    k = 0
    while len(pieces) > 1 and k < len(pieces):
        A, B = pieces[k - 1], pieces[k]
        if A["kind"] == "free" and B["kind"] == "free" and not B["cs"]:
            A["b"] = B["b"] if B["b"] > A["a"] else B["b"] + m
            pieces.pop(k)
        else:
            k += 1
    if STRICT:
        # lines of nearly one direction (within 3 degrees) are parallel: all get their common direction (weighted by
        # length; on a multiple of 15 degrees when within 2.2 of one)
        lines = [p for p in pieces if p["kind"] == "line"]
        if len(lines) > 1:
            ang = np.array([math.degrees(math.atan2(p["d"][1], p["d"][0])) % 180.0 for p in lines])
            length = np.array([max(p["b"] - p["a"], 1) for p in lines], float)
            order = [int(i) for i in np.argsort(ang)]
            groups = [[order[0]]]
            for i in order[1:]:
                if ang[i] - ang[groups[-1][-1]] <= 3.0:
                    groups[-1].append(i)
                else:
                    groups.append([i])
            if len(groups) > 1 and ang[groups[0][0]] + 180.0 - ang[groups[-1][-1]] <= 3.0:
                first = groups.pop(0)
                for i in first:
                    ang[i] += 180.0
                groups[-1] += first
            for g in groups:
                mean = float(np.average(ang[g], weights=length[g]))
                near = round(mean / 15.0) * 15.0
                if abs(mean - near) <= T["snap"]:
                    mean = near
                v = np.array([math.cos(math.radians(mean)), math.sin(math.radians(mean))])
                for i in g:
                    lines[i]["d"] = v if v @ lines[i]["d"] >= 0 else -v
    # a free stretch from corner to corner that keeps to one circle is an arc
    for k, p in enumerate(pieces):
        if p["kind"] == "free" and len(pieces) > 1 and p["cs"] and pieces[(k + 1) % len(pieces)]["cs"]:
            pts = P(p["a"], p["b"])
            if len(pts) >= 12:
                cx, cy, r = lsq_circle(pts)
                dev = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r)
                if r <= 40 and dev.max() <= 0.09 and len(pts) / (K * r) >= 0.45:
                    p["kind"], p["circle"] = "arc", (float(cx), float(cy), float(r))
    M = len(pieces)

    # ---- where pieces meet
    def project(p, pt):
        if p["kind"] == "line":
            return p["mid"] + ((pt - p["mid"]) @ p["d"]) * p["d"]
        if p["kind"] == "arc":
            cx, cy, r = p["circle"]
            v = pt - np.array([cx, cy])
            return np.array([cx, cy]) + unit(v) * r
        return pt

    def meet(A, B, raw):
        J = None
        if A["kind"] == "line" and B["kind"] == "line":
            den = A["d"][0] * B["d"][1] - A["d"][1] * B["d"][0]
            if abs(den) > 0.15:
                t = ((B["mid"][0] - A["mid"][0]) * B["d"][1] - (B["mid"][1] - A["mid"][1]) * B["d"][0]) / den
                J = A["mid"] + t * A["d"]
        elif "line" in (A["kind"], B["kind"]) and "arc" in (A["kind"], B["kind"]):
            Ln, Ar = (A, B) if A["kind"] == "line" else (B, A)
            cx, cy, r = Ar["circle"]
            f = Ln["mid"] - np.array([cx, cy])
            bq = f @ Ln["d"]
            disc = bq * bq - (f @ f - r * r)
            if disc >= 0:
                s = math.sqrt(disc)
                J = min((Ln["mid"] + (-bq + s) * Ln["d"], Ln["mid"] + (-bq - s) * Ln["d"]), key=lambda z: math.hypot(*(z - raw)))
        elif A["kind"] == "arc" and B["kind"] == "arc" and A["circle"] != B["circle"]:
            (x1, y1, r1), (x2, y2, r2) = A["circle"], B["circle"]
            d = math.hypot(x2 - x1, y2 - y1)
            if 1e-6 < d <= r1 + r2 and d >= abs(r1 - r2):
                a_ = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
                h = math.sqrt(max(r1 * r1 - a_ * a_, 0))
                mx, my = x1 + a_ * (x2 - x1) / d, y1 + a_ * (y2 - y1) / d
                J = min((np.array([mx + h * (y2 - y1) / d, my - h * (x2 - x1) / d]), np.array([mx - h * (y2 - y1) / d, my + h * (x2 - x1) / d])),
                        key=lambda z: math.hypot(*(z - raw)))
        if J is not None and math.hypot(*(J - raw)) <= 0.7:
            return J
        exact = [p for p in (A, B) if p["kind"] != "free"]
        if len(exact) == 2:
            return 0.5 * (project(A, raw) + project(B, raw))
        return project(exact[0], raw) if exact else raw.copy()
    if M == 1:
        J = [q[pieces[0]["a"] % m].copy()]
    else:
        J = [meet(pieces[k - 1], pieces[k], q[pieces[k]["a"] % m]) for k in range(M)]

    def forward(p, at):                                             # the direction of travel along an exact piece at a point
        if p["kind"] == "line":
            return p["d"]
        cx, cy, r = p["circle"]
        a = math.atan2(at[1] - cy, at[0] - cx)
        return np.array([-math.sin(a), math.cos(a)]) * p["turn"]
    # arcs: their sweep
    for k, p in enumerate(pieces):
        if p["kind"] == "arc":
            cx, cy, r = p["circle"]
            pts = P(p["a"], p["b"])
            th = np.unwrap(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx))
            sweep = th[-1] - th[0]
            J0, J1 = J[k], J[(k + 1) % M]
            a0 = math.atan2(J0[1] - cy, J0[0] - cx)
            dl = math.atan2(J1[1] - cy, J1[0] - cx) - a0
            while dl - sweep > math.pi: dl -= 2 * math.pi
            while dl - sweep < -math.pi: dl += 2 * math.pi
            p["a0"], p["a1"], p["turn"] = a0, a0 + dl, (1.0 if dl >= 0 else -1.0)
    prims = [["M", J[0][0], J[0][1]]]
    for k, p in enumerate(pieces):
        J0, J1 = J[k], J[(k + 1) % M]
        prev, nxt = pieces[k - 1], pieces[(k + 1) % M]
        if p["kind"] == "line":
            edge = lambda z: (z[0] < 0.14, z[0] > 31.86, z[1] < 0.14, z[1] > 31.86)
            side = [s0 and s1 for s0, s1 in zip(edge(J0), edge(J1))]
            if any(side):                                           # along the frame's edge: the frame cut it; run on past the frame
                off = np.array([-0.8 if side[0] else 0.8 if side[1] else 0.0, -0.8 if side[2] else 0.8 if side[3] else 0.0])
                prims += [["L", *(J0 + off)], ["L", *(J1 + off)]]
            prims.append(["L", J1[0], J1[1]])
            made["lines"] += 1
        elif p["kind"] == "arc":
            cx, cy, r = p["circle"]
            prims.append(["A", cx, cy, r, p["a0"], p["a1"]])
            end = np.array([cx + r * math.cos(p["a1"]), cy + r * math.sin(p["a1"])])
            if math.hypot(*(end - J1)) > 1e-6:
                prims.append(["L", J1[0], J1[1]])
            made["arcs"] += 1
        else:
            pts = P(p["a"], p["b"])
            sub = pts[::2] if len(pts) > 6 else pts
            if not np.array_equal(sub[-1], pts[-1]):
                sub = np.vstack([sub, pts[-1]])
            sub = sub.copy()
            sub[0], sub[-1] = J0, J1
            n = len(sub)
            d1 = unit(sub[min(3, n - 1)] - sub[0])
            d2 = unit(sub[max(n - 4, 0)] - sub[-1])
            if M == 1:                                             # a closed curve: three parts, tangent-continuous all round
                tang = lambda i: unit(pts[(i + 3) % len(pts)] - pts[(i - 3) % len(pts)])
                cuts = [0, len(pts) // 3, 2 * len(pts) // 3, len(pts) - 1]
                curves = []
                for c0, c1 in zip(cuts[:-1], cuts[1:]):
                    part = pts[c0:c1 + 1][::2]
                    if not np.array_equal(part[-1], pts[c1]):
                        part = np.vstack([part, pts[c1]])
                    curves += fit_curve(part, tang(c0), -tang(c1 % (len(pts) - 1)), T["curve_tol"])
            else:
                t1, t2 = d1, d2
                if not p["cs"] and prev["kind"] != "free":
                    f = forward(prev, J0)
                    if f @ d1 > 0.9:
                        t1 = f
                if not nxt["cs"] and nxt["kind"] != "free":
                    f = -forward(nxt, J1)
                    if f @ d2 > 0.9:
                        t2 = f
                curves = fit_curve(sub, t1, t2, T["curve_tol"])
            for c in curves:
                prims.append(["C", c[1][0], c[1][1], c[2][0], c[2][1], c[3][0], c[3][1]])
            made["curves"] += len(curves)
    prims = [[p[0]] + [round(float(v), 4) for v in p[1:]] for p in prims]
    pts = tessellate(prims)
    if len(pts) < 3:
        prims = [["M", round(q[0, 0], 3), round(q[0, 1], 3)]] + [["L", round(x, 3), round(y, 3)] for x, y in q[2::3]]
        return ["path", prims], (0.0, 0.0), made
    return ["path", prims], _stray(pts, q), made
