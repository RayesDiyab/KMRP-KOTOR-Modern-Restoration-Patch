"""The rings of the copyright and registered signs as exact geometry: a circle or an
axis-aligned oval, whichever the HD letter's ring is closer to, both edges of the ring
around one centre, each drawn as four quarter arcs with points at the extremes."""
import numpy as np

KAPPA = 0.5522847498307936       # handle length of a quarter circle, per unit radius
RING_GLYPHS = ("uni00A9", "uni00AE")


def area(P):
    return 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))


def fit_ellipse(P):
    """Axis-aligned ellipse A x^2 + B y^2 + C x + D y = 1: centre and semi-axes."""
    x, y = P[:, 0], P[:, 1]
    M = np.stack([x * x, y * y, x, y], 1)
    (A, B, C, D), *_ = np.linalg.lstsq(M, np.ones(len(P)), rcond=None)
    cx, cy = -C / (2 * A), -D / (2 * B)
    k = 1 + A * cx * cx + B * cy * cy
    return np.array([cx, cy]), np.sqrt(k / A), np.sqrt(k / B)


def ellipse_rms(P, c, a, b):
    """Distance of the points from the ellipse, approximately (radial)."""
    d = P - c
    ang = np.arctan2(d[:, 1] / b, d[:, 0] / a)
    q = c + np.stack([a * np.cos(ang), b * np.sin(ang)], 1)
    return float(np.sqrt(((P - q) ** 2).sum(1).mean()))


def axes_about(P, c):
    """Semi-axes of the ellipse about a given centre that fits the points best."""
    d = P - c
    M = np.stack([d[:, 0] ** 2, d[:, 1] ** 2], 1)
    (A, B), *_ = np.linalg.lstsq(M, np.ones(len(P)), rcond=None)
    return 1 / np.sqrt(A), 1 / np.sqrt(B)


def quarter_arcs(c, a, b, clockwise):
    """Four cubic quarter arcs, starting at the top: ('curve', end, c1, c2) each."""
    cx, cy = c
    top, left, bot, right = (np.array(p) for p in ((cx, cy + b), (cx - a, cy), (cx, cy - b), (cx + a, cy)))
    ka, kb = KAPPA * a, KAPPA * b
    ccw = [  # top -> left -> bottom -> right -> top
        (left, top + [-ka, 0], left + [0, kb]),
        (bot, left - [0, kb], bot + [-ka, 0]),
        (right, bot + [ka, 0], right - [0, kb]),
        (top, right + [0, kb], top + [ka, 0]),
    ]
    if not clockwise:
        return [("curve", e, h1, h2) for e, h1, h2 in ccw]
    # The same arcs travelled the other way: top -> right -> bottom -> left -> top.
    cw = [
        (right, top + [ka, 0], right + [0, kb]),
        (bot, right - [0, kb], bot + [ka, 0]),
        (left, bot + [-ka, 0], left - [0, kb]),
        (top, left + [0, kb], top + [-ka, 0]),
    ]
    return [("curve", e, h1, h2) for e, h1, h2 in cw]


def ring_contours(loops, grid):
    """Indices of the two ring loops and their exact replacements, or None. The outer
    edge sets the centre; the shape (circle or oval) is the one the outer edge is closer
    to, unless the oval is no real improvement."""
    if len(loops) < 2:
        return None
    sizes = [np.ptp(P[:, 0]) + np.ptp(P[:, 1]) for P in loops]
    order = np.argsort(sizes)[::-1]
    outer = loops[order[0]]
    c, a, b = fit_ellipse(outer)
    r = float(np.linalg.norm(outer - c, axis=1).mean())
    circ = float(np.sqrt(((np.linalg.norm(outer - c, axis=1) - r) ** 2).mean()))
    ell = ellipse_rms(outer, c, a, b)
    oval = ell < 0.7 * circ and abs(a - b) / max(a, b) > 0.01
    # The ring's inner edge: the next largest loop, round about the same centre.
    inner_i = None
    for i in order[1:]:
        P = loops[i]
        cc = P.mean(0)
        if np.linalg.norm(cc - c) < 0.08 * r and sizes[i] > 0.6 * sizes[order[0]]:
            inner_i = int(i)
            break
    if inner_i is None:
        return None
    inner = loops[inner_i]
    if oval:
        ai, bi = axes_about(inner, c)
        ao, bo = a, b
    else:
        ao = bo = r
        ai = bi = float(np.linalg.norm(inner - c, axis=1).mean())
    snap = lambda v: np.round(np.asarray(v, dtype=float) * grid) / grid
    out = {}
    for idx, (sa, sb) in ((int(order[0]), (ao, bo)), (inner_i, (ai, bi))):
        cw = area(loops[idx]) < 0
        arcs = quarter_arcs(c, sa, sb, cw)
        out[idx] = [(k, snap(e), snap(h1), snap(h2)) for k, e, h1, h2 in arcs]
    return out, ("oval" if oval else "circle"), (ao, bo, ai, bi)
