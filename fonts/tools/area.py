"""Exact-area coverage of polygons on a pixel grid (signed area accumulation, the method
of font rasterisers): each pixel gets the exact fraction of it inside the outline."""
import math
import numpy as np
try:
    from numba import njit          # compiled when numba is installed (fast)
except ImportError:                 # plain Python otherwise (the same result, slower)
    def njit(*args, **kwargs):
        return args[0] if args and callable(args[0]) else (lambda f: f)


def coverage(polys, x0, y0, w, h, scale):
    """polys in units, y up; grid origin (x0, y0) top left in units; `scale` px per unit."""
    W = w + 3
    acc = np.zeros(h * W + 3)
    for poly in polys:
        q = np.empty((len(poly), 2))
        q[:, 0] = (poly[:, 0] - x0) * scale
        q[:, 1] = (y0 - poly[:, 1]) * scale
        draw_poly(acc, W, h, q)
    cov = np.cumsum(acc[:h * W].reshape(h, W), axis=1)[:, :w]
    return np.minimum(np.abs(cov), 1.0)


@njit(cache=True)
def draw_poly(acc, W, h, q):
    n = q.shape[0]
    for i in range(n):
        j = (i + 1) % n
        line(acc, W, h, (q[i, 0], q[i, 1]), (q[j, 0], q[j, 1]))


@njit(cache=True)
def line(a, W, h, p0, p1):
    if p0[1] == p1[1]:
        return
    if p0[1] < p1[1]:
        d0, (x0p, y0p), (x1p, y1p) = 1.0, p0, p1
    else:
        d0, (x0p, y0p), (x1p, y1p) = -1.0, p1, p0
    dxdy = (x1p - x0p) / (y1p - y0p)
    x = x0p
    ystart = max(0, int(math.floor(y0p)))
    if y0p < 0:
        x -= y0p * dxdy
    yend = min(h, int(math.ceil(y1p)))
    for y in range(ystart, yend):
        ls = y * W
        dy = min(y + 1.0, y1p) - max(float(y), y0p)
        xnext = x + dxdy * dy
        d = dy * d0
        xa, xb = (x, xnext) if x < xnext else (xnext, x)
        xaf = math.floor(xa)
        xai = int(xaf)
        xbc = math.ceil(xb)
        xbi = int(xbc)
        if xai < 0 or xbi + 1 >= W:
            xai = max(xai, 0)
        if xbi <= xai + 1:
            xmf = 0.5 * (x + xnext) - xaf
            a[ls + xai] += d - d * xmf
            a[ls + xai + 1] += d * xmf
        else:
            s = 1.0 / (xb - xa)
            x0f = xa - xaf
            a0 = 0.5 * s * (1.0 - x0f) ** 2
            x1f = xb - xbc + 1.0
            am = 0.5 * s * x1f * x1f
            a[ls + xai] += d * a0
            if xbi == xai + 2:
                a[ls + xai + 1] += d * (1.0 - a0 - am)
            else:
                a1 = s * (1.5 - x0f)
                a[ls + xai + 1] += d * (a1 - a0)
                for xi in range(xai + 2, xbi - 1):
                    a[ls + xi] += d * s
                a2 = a1 + (xbi - xai - 3) * s
                a[ls + xbi - 1] += d * (1.0 - a2 - am)
            a[ls + xbi] += d * am
        x = xnext
