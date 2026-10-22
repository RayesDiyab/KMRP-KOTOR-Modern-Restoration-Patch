"""Exact edge positions from coverage read as area.

A pixel's coverage is the share of it inside the letter. Across one pixel row, an edge
that rises from outside to inside over pixels k..m sits on average at
    x = k + sum(1 - c_i)        (a left edge: ink to the right)
and a falling one (ink to the left) at
    x = k + sum(c_i),
both in pixel-edge coordinates. For a straight edge this is exact; the 50% crossing
between pixel centres is not (it ripples once per pixel along a slanted edge). Rows are
read for steep edges, columns for flat ones."""
import numpy as np

LO, HI = 0.004, 0.996


def edge_in_line(c, x_guess):
    """The edge position along one row (or column) of coverage c near x_guess (in
    pixel-edge units), or None if the edge there is not a clean single transition."""
    w = len(c)
    j = int(np.floor(x_guess))
    j = min(max(j, 0), w - 1)
    # The transition: the partly covered pixels around j, between a full and an empty one.
    if not (LO < c[j] < HI):
        # The crossing is on a pixel boundary: take the neighbour on the partial side.
        if j + 1 < w and LO < c[j + 1] < HI:
            j += 1
        elif j - 1 >= 0 and LO < c[j - 1] < HI:
            j -= 1
        else:
            # A sharp boundary exactly at a pixel edge.
            if j + 1 < w and (c[j] >= HI) != (c[j + 1] >= HI):
                return float(j + 1)
            if j - 1 >= 0 and (c[j] >= HI) != (c[j - 1] >= HI):
                return float(j)
            return None
    k = j
    while k - 1 >= 0 and LO < c[k - 1] < HI:
        k -= 1
    m = j
    while m + 1 < w and LO < c[m + 1] < HI:
        m += 1
    if m - k > 3:
        return None
    left = c[k - 1] if k - 1 >= 0 else 0.0
    right = c[m + 1] if m + 1 < w else 0.0
    part = c[k:m + 1]
    if left <= LO and right >= HI:          # rising: ink to the right
        return float(k + (1 - part).sum())
    if left >= HI and right <= LO:          # falling: ink to the left
        return float(k + part.sum())
    return None


def refine(loop, cell):
    """The loop's points moved to the area position of their edge: on a steep stretch
    the row readings, on a flat one the column readings; a point that cannot be read
    cleanly (a corner, a stroke thinner than its own blur) keeps its 50% crossing."""
    n = len(loop)
    h, w = cell.shape
    out = []
    for i in range(n):
        p = loop[i]
        d = loop[(i + 1) % n] - loop[(i - 1) % n]
        steep = abs(d[1]) >= abs(d[0])
        on_row = abs(p[1] - (np.floor(p[1]) + 0.5)) < 1e-6
        on_col = abs(p[0] - (np.floor(p[0]) + 0.5)) < 1e-6
        if steep and on_row:
            x = edge_in_line(cell[int(np.floor(p[1]))], p[0]) if 0 <= int(np.floor(p[1])) < h else None
            out.append((x, p[1]) if x is not None and abs(x - p[0]) < 1.0 else (p[0], p[1]))
        elif not steep and on_col:
            y = edge_in_line(cell[:, int(np.floor(p[0]))], p[1]) if 0 <= int(np.floor(p[0])) < w else None
            out.append((p[0], y) if y is not None and abs(y - p[1]) < 1.0 else (p[0], p[1]))
        # Crossings of the other kind on this stretch are the rippling ones: left out,
        # unless the outline turns here (both neighbours of the other kind too).
        else:
            prev_same = i > 0
            out.append(None)
    pts = [q for q in out if q is not None]
    return np.array(pts, dtype=np.float64) if len(pts) >= 4 else loop.copy()
