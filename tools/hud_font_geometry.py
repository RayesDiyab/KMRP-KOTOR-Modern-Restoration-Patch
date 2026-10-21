#!/usr/bin/env python3
"""The HUD font (fnt_console) rebuilt from geometry, for the (New) Original HD Font.

The original fnt_console is a pixel font on an 8 by 16 grid: vertical strokes two pixels
wide, horizontal strokes one pixel tall, round letters with their corners cut by a pixel,
slanted strokes drawn as stairs, and slab feet on l, i, I. Helvetica Bold, which the HD
font used for it until 2026-10-21, has none of that (the maintainer saw it in the 4 and
the small l). Tracing the pixels keeps the stairs, or (traced at the original's size)
turns the one pixel bars into wedges, so each letter is written here as exact shapes on
the original's own grid: rectangles where the original is straight, rings with true
round corners where it cuts a corner, and straight bands where it steps. `check()`
draws every letter back at the original's size and counts the pixels that differ from
it, so the shapes are measured against the original rather than drawn by eye.

Units are the original's pixels: x 0 to 8 across the cell, y 0 to 16 down it; a pixel
at column c, row r covers [c, c+1) x [r, r+1). Capitals stand on rows 3 to 11, small
letters on rows 5 to 11, descenders reach row 15.

    python tools/hud_font_geometry.py OUT_DIR      # the check sheet and its report
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

CELL_W, CELL_H = 8, 16
STEM, BAR = 2, 1             # the original's stroke widths: vertical, horizontal
RO, RI = 2.0, 0.8            # a cut corner's radius outside and inside the stroke


# ---- shapes: each returns ("+" or "-", polygon) ----

def _rrect_points(x0, y0, x1, y1, radii):
    """A rectangle whose corners (top left, top right, bottom right, bottom left) are
    rounded by the given radii, as a polygon."""
    tl, tr, br, bl = (min(r, (x1 - x0) / 2, (y1 - y0) / 2) for r in radii)
    pts = []

    def corner(cx, cy, r, a0, a1):
        for k in range(17):
            a = math.radians(a0 + (a1 - a0) * k / 16)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    corner(x0 + tl, y0 + tl, tl, 180, 270) if tl else pts.append((x0, y0))
    corner(x1 - tr, y0 + tr, tr, 270, 360) if tr else pts.append((x1, y0))
    corner(x1 - br, y1 - br, br, 0, 90) if br else pts.append((x1, y1))
    corner(x0 + bl, y1 - bl, bl, 90, 180) if bl else pts.append((x0, y1))
    return pts


def rect(x0, y0, x1, y1):
    return [("+", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])]


def rrect(x0, y0, x1, y1, radii):
    return [("+", _rrect_points(x0, y0, x1, y1, radii))]


def poly(*pts):
    return [("+", list(pts))]


def band(xt, yt, xb, yb, w=STEM):
    """A slanted stroke `w` wide across: its left edge from (xt, yt) to (xb, yb)."""
    return [("+", [(xt, yt), (xt + w, yt), (xb + w, yb), (xb, yb)])]


def ring(x0, y0, x1, y1, corners=(1, 1, 1, 1), ro=RO, ri=RI, stem=STEM, bar=BAR):
    """A closed outline with its outside rounded at the corners flagged (top left, top
    right, bottom right, bottom left), the inside likewise. Used for @, whose strokes are
    one pixel thick."""
    outer = _rrect_points(x0, y0, x1, y1, [ro if c else 0 for c in corners])
    inner = _rrect_points(x0 + stem, y0 + bar, x1 - stem, y1 - bar, [ri if c else 0 for c in corners])
    return [("+", outer), ("-", inner)]


def cut(*shapes):
    """Shapes taken away instead of added."""
    out = []
    for s in shapes:
        out += [("-", p) for _, p in s]
    return out


# ---- the letters ----

T, B, X, D = 3, 12, 5, 16

GLYPHS: dict[str, list] = {}


def glyph(ch, *parts):
    GLYPHS[ch] = [op for part in parts for op in part]


def _hull(points):
    """The convex hull of points, as a polygon (monotone chain)."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _filleted(points, radii, closed):
    """A path through `points`, each corner rounded by its radius, as a dense polyline."""
    n = len(points)
    if isinstance(radii, (int, float)):
        radii = [radii] * n
    out = []
    for i in range(n):
        p = points[i]
        r = radii[i]
        has_prev = closed or i > 0
        has_next = closed or i < n - 1
        if r <= 0 or not (has_prev and has_next):
            out.append(p)
            continue
        a, b = points[i - 1], points[(i + 1) % n]
        ux, uy = a[0] - p[0], a[1] - p[1]
        vx, vy = b[0] - p[0], b[1] - p[1]
        lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
        ux, uy, vx, vy = ux / lu, uy / lu, vx / lv, vy / lv
        cos = max(-1.0, min(1.0, ux * vx + uy * vy))
        theta = math.acos(cos)
        if theta < 1e-3 or abs(theta - math.pi) < 1e-3:
            out.append(p)
            continue
        t = min(r / math.tan(theta / 2), lu / 2, lv / 2)
        r = t * math.tan(theta / 2)
        p1 = (p[0] + ux * t, p[1] + uy * t)
        p2 = (p[0] + vx * t, p[1] + vy * t)
        bx, by = ux + vx, uy + vy
        bl = math.hypot(bx, by)
        d = r / math.sin(theta / 2)
        c = (p[0] + bx / bl * d, p[1] + by / bl * d)
        a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
        a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
        delta = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(17):
            a = a1 + delta * k / 16
            out.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    if closed:
        out.append(out[0])
    return out


def stroke(points, radii=0, pen=(STEM, BAR), closed=False):
    """One stroke of the letter: the pen (STEM wide, BAR tall, the original's strokes)
    drawn along the centre line through `points`, its corners rounded by `radii`. A path
    is one piece, so its joins are clean wherever it turns."""
    path = _filleted(points, radii, closed)
    # The pen: the stroke's box with its corners rounded by PEN_ROUND, so a turn's outside
    # is rounder than its inside by twice that, as an offset curve's is, and a round
    # letter's hole keeps its corners instead of closing to a point.
    q = min(PEN_ROUND, pen[0] / 2 - 0.01, pen[1] / 2 - 0.01)
    corners = [(px, py) for px, py in _rrect_points(-pen[0] / 2, -pen[1] / 2, pen[0] / 2, pen[1] / 2, (q, q, q, q))]
    parts = []
    if len(path) == 1:
        path = path * 2
    for p, q in zip(path, path[1:]):
        pts = [(p[0] + dx, p[1] + dy) for dx, dy in corners] + [(q[0] + dx, q[1] + dy) for dx, dy in corners]
        parts.append(("+", _hull(pts)))
    return parts


def arc(cx, cy, rx, ry, a0, a1, w=STEM, h=BAR):
    """A curved stroke: the part of an ellipse's outline from angle a0 to a1 (degrees,
    0 to the right, 90 down), `w` thick across and `h` thick up and down."""
    out, inn = [], []
    for k in range(33):
        a = math.radians(a0 + (a1 - a0) * k / 32)
        out.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        inn.append((cx + (rx - w) * math.cos(a), cy + (ry - h) * math.sin(a)))
    return [("+", out + inn[::-1])]


def wave():
    """The tilde: one period of a sine, a pixel thick."""
    top, bottom = [], []
    for k in range(41):
        x = 1 + 5 * k / 40
        y = 8 + 0.9 * math.sin((x - 1) / 5 * 2 * math.pi + math.pi)
        top.append((x, y - 0.5))
        bottom.append((x, y + 0.5))
    return [("+", top + bottom[::-1])]


# Centre lines: the left stem's centre is x 2, the right's x 6 (x 7 in the wide M, N, W,
# m, w); a capital's top bar's centre y 3.5, the baseline bar's y 11.5, a small letter's
# top y 5.5. R is the radius of a cut corner's turn.
R = 1.3
PEN_ROUND = 0.35
THIN = (1, 1)
SLANT = (1.7, 1)    # M, N, W, m, w: their diagonals and three stems in the cell's width

# Digits
glyph("0", stroke([(2, 3.5), (6, 3.5), (6, 11.5), (2, 11.5)], R, closed=True))
glyph("1", stroke([(5, 3.5), (5, 11.5)]), stroke([(5, 3.6), (2, 5.5)]))
glyph("2", stroke([(2, 5.5), (2, 3.5), (6, 3.5), (6, 6.5), (2, 10.5), (2, 11.5), (6, 11.5)], [0, R, R, 0.7, 0.5, 0, 0]))
glyph("3", stroke([(2, 5.5), (2, 3.5), (6, 3.5), (6, 7.5), (4, 7.5)], [0, R, R, R, 0]),
      stroke([(4, 7.5), (6, 7.5), (6, 11.5), (2, 11.5), (2, 9.5)], [0, R, R, R, 0]))
glyph("4", stroke([(3, 3.5), (3, 7.4), (2, 8.6), (2, 9.5), (7, 9.5)], [0, 0.6, 0.6, 0, 0]), stroke([(6, 5.5), (6, 11.5)]))
glyph("5", stroke([(6, 3.5), (2, 3.5), (2, 7.5), (6, 7.5), (6, 10.5), (5, 11.5), (2, 11.5)], [0, 0, 0, R, 0.8, 0.8, 0]))
glyph("6", stroke([(2, 6.5), (6, 6.5), (6, 11.5), (2, 11.5)], [0, R, R, R], closed=True),
      stroke([(5, 3.5), (4, 3.5), (2, 6.5)], [0, 0.6, 0]))
glyph("7", stroke([(2, 3.5), (6, 3.5), (6, 4.5), (3, 9.5), (3, 11.5)], [0, 0, 0.6, 0.8, 0]))
glyph("8", stroke([(2, 3.5), (6, 3.5), (6, 7.5), (2, 7.5)], R, closed=True),
      stroke([(2, 7.5), (6, 7.5), (6, 11.5), (2, 11.5)], R, closed=True))
glyph("9", stroke([(2, 3.5), (6, 3.5), (6, 8.5), (2, 8.5)], [R, R, 0, R], closed=True),
      stroke([(6, 8.5), (3.2, 11.5)]))
glyph("A", stroke([(2, 11.5), (2, 5.2), (4, 3.5), (6, 5.2), (6, 11.5)], [0, 1.2, 1.4, 1.2, 0]), stroke([(2, 8.5), (6, 8.5)]))
glyph("B", stroke([(2, 3.5), (2, 11.5)]), stroke([(2, 3.5), (6, 3.5), (6, 7.5), (2, 7.5)], [0, R, R, 0]),
      stroke([(2, 7.5), (6, 7.5), (6, 11.5), (2, 11.5)], [0, R, R, 0]))
glyph("C", stroke([(6, 5.5), (6, 3.5), (2, 3.5), (2, 11.5), (6, 11.5), (6, 9.5)], [0, R, R, R, R, 0]))
glyph("D", stroke([(2, 3.5), (6, 3.5), (6, 11.5), (2, 11.5)], [0, 2.4, 2.4, 0], closed=True))
glyph("E", stroke([(6, 3.5), (2, 3.5), (2, 11.5), (6, 11.5)]), stroke([(2, 7.5), (5, 7.5)]))
glyph("F", stroke([(6, 3.5), (2, 3.5), (2, 11.5)]), stroke([(2, 7.5), (5, 7.5)]))
glyph("G", stroke([(6, 5.5), (6, 3.5), (2, 3.5), (2, 11.5), (6, 11.5), (6, 9.5), (4.5, 9.5)], [0, R, R, R, 0, 0, 0]))
glyph("H", stroke([(2, 3.5), (2, 11.5)]), stroke([(6, 3.5), (6, 11.5)]), stroke([(2, 7.5), (6, 7.5)]))
glyph("I", stroke([(3, 3.5), (5, 3.5)]), stroke([(4, 3.5), (4, 11.5)]), stroke([(3, 11.5), (5, 11.5)]))
glyph("J", stroke([(6, 3.5), (6, 11.5), (2, 11.5), (2, 9.5)], [0, R, R, 0]))
glyph("K", stroke([(2, 3.5), (2, 11.5)]), stroke([(6, 3.5), (6, 4.5), (3.4, 7.5), (6, 10.5), (6, 11.5)], [0, 0.8, 0.4, 0.8, 0]))
glyph("L", stroke([(2, 3.5), (2, 11.5), (6, 11.5)]))
glyph("M", stroke([(2, 3.5), (2, 11.5)], pen=SLANT), stroke([(7, 3.5), (7, 11.5)], pen=SLANT),
      stroke([(2, 3.5), (4.5, 8.6)], pen=SLANT), stroke([(7, 3.5), (4.5, 8.6)], pen=SLANT))
glyph("N", stroke([(2, 3.5), (2, 11.5)], pen=SLANT), stroke([(7, 3.5), (7, 11.5)], pen=SLANT),
      stroke([(2, 3.5), (7, 11.5)], pen=SLANT))
glyph("O", stroke([(2, 3.5), (6, 3.5), (6, 11.5), (2, 11.5)], R, closed=True))
glyph("P", stroke([(2, 11.5), (2, 3.5), (6, 3.5), (6, 7.5), (2, 7.5)], [0, 0, R, R, 0]))
glyph("Q", stroke([(2, 3.5), (6, 3.5), (6, 11.5), (2, 11.5)], R, closed=True), stroke([(5, 12.4), (6, 13.5)]))
glyph("R", stroke([(2, 11.5), (2, 3.5), (6, 3.5), (6, 7.5), (2, 7.5)], [0, 0, R, R, 0]),
      stroke([(4, 7.5), (6, 9.5), (6, 11.5)], [0, 0.6, 0]))
glyph("S", stroke([(6, 4.5), (6, 3.5), (2, 3.5), (2, 5.5), (6, 9.5), (6, 11.5), (2, 11.5), (2, 10.5)],
                  [0, R, R, 0.8, 0.8, R, R, 0]))
glyph("T", stroke([(2, 3.5), (6, 3.5)]), stroke([(4, 3.5), (4, 11.5)]))
glyph("U", stroke([(2, 3.5), (2, 11.5), (6, 11.5), (6, 3.5)], [0, R, R, 0]))
glyph("V", stroke([(2, 3.5), (2, 9.5), (4, 11.5), (6, 9.5), (6, 3.5)], [0, 0.6, 0.5, 0.6, 0]))
glyph("W", stroke([(2, 3.5), (2, 11.5)], pen=SLANT), stroke([(7, 3.5), (7, 11.5)], pen=SLANT),
      stroke([(2, 11.5), (4.5, 6.4)], pen=SLANT), stroke([(7, 11.5), (4.5, 6.4)], pen=SLANT))
glyph("X", stroke([(2, 3.5), (2, 4.5), (6, 10.5), (6, 11.5)], [0, 0.6, 0.6, 0]),
      stroke([(6, 3.5), (6, 4.5), (2, 10.5), (2, 11.5)], [0, 0.6, 0.6, 0]))
glyph("Y", stroke([(2, 3.5), (2, 6.5), (4, 8.2), (6, 6.5), (6, 3.5)], [0, 0.6, 0.5, 0.6, 0]), stroke([(4, 8.2), (4, 11.5)]))
glyph("Z", stroke([(2, 3.5), (6, 3.5), (6, 5.5), (2, 9.5), (2, 11.5), (6, 11.5)], [0, 0, 0.6, 0.6, 0, 0]))

# Small letters
glyph("a", stroke([(3, 5.5), (6, 5.5), (6, 11.5)], [0, R, 0]),
      stroke([(6, 8.5), (2, 8.5), (2, 11.5), (6, 11.5)], [0, R, R, 0]))
glyph("b", stroke([(2, 3.5), (2, 11.5)]), stroke([(2, 5.5), (6, 5.5), (6, 11.5), (2, 11.5)], [0, R, R, 0]))
glyph("c", stroke([(6, 6.5), (6, 5.5), (2, 5.5), (2, 11.5), (6, 11.5), (6, 10.5)], [0, R, R, R, R, 0]))
glyph("d", stroke([(6, 3.5), (6, 11.5)]), stroke([(6, 5.5), (2, 5.5), (2, 11.5), (6, 11.5)], [0, R, R, 0]))
glyph("e", stroke([(2, 8.5), (6, 8.5), (6, 5.5), (2, 5.5), (2, 11.5), (6, 11.5)], [0, 0, R, R, R, 0]))
glyph("f", stroke([(6.5, 3.5), (3, 3.5), (3, 11.5)], [0, R, 0]), stroke([(2, 7.5), (6, 7.5)]))
glyph("g", stroke([(6, 5.5), (2, 5.5), (2, 11.5), (6, 11.5)], [0, R, R, 0]),
      stroke([(6, 5.5), (6, 14), (2, 14)], [0, R, 0], pen=(STEM, 2)))
glyph("h", stroke([(2, 3.5), (2, 11.5)]), stroke([(2, 5.5), (6, 5.5), (6, 11.5)], [0, R, 0]))
glyph("i", rect(3, 2, 5, 4), stroke([(2, 5.5), (4, 5.5), (4, 11.5)]), stroke([(2, 11.5), (6, 11.5)]))
glyph("j", rect(4, 2, 6, 4), stroke([(3, 5.5), (5, 5.5)]), stroke([(5, 5.5), (5, 14), (2, 14)], [0, R, 0], pen=(STEM, 2)))
glyph("k", stroke([(2, 3.5), (2, 11.5)]), stroke([(6, 5.5), (6, 6.5), (3.4, 8.5), (6, 10.5), (6, 11.5)], [0, 0.8, 0.4, 0.8, 0]))
glyph("l", stroke([(2, 3.5), (4, 3.5), (4, 11.5)]), stroke([(2, 11.5), (6, 11.5)]))
glyph("m", stroke([(1.8, 11.5), (1.8, 5.5), (4.5, 5.5), (4.5, 11.5)], [0, 0, 1.0, 0], pen=SLANT),
      stroke([(4.5, 5.5), (7.1, 5.5), (7.1, 11.5)], [0, 1.0, 0], pen=SLANT))
glyph("n", stroke([(2, 5.5), (2, 11.5)]), stroke([(2, 5.5), (6, 5.5), (6, 11.5)], [0, R, 0]))
glyph("o", stroke([(2, 5.5), (6, 5.5), (6, 11.5), (2, 11.5)], R, closed=True))
glyph("p", stroke([(2, 5.5), (2, 14.5)]), stroke([(2, 5.5), (6, 5.5), (6, 11.5), (2, 11.5)], [0, R, R, 0]))
glyph("q", stroke([(6, 5.5), (6, 14.5)]), stroke([(6, 5.5), (2, 5.5), (2, 11.5), (6, 11.5)], [0, R, R, 0]))
# The arm an arch that leaves the stem from inside it (its centre line starts on the
# stem's), so the two are one piece; it ends level, pointing right, and above it the
# stem's top stands free as the original's does (the maintainer, 2026-10-21).
glyph("r", stroke([(2, 5.5), (2, 11.5)]),
      stroke([(2, 10)] + [(5.6 - 3.6 * math.cos(math.radians(t)), 8.6 - 3.1 * math.sin(math.radians(t))) for t in range(0, 91, 5)]
             + [(6.15, 5.5)], pen=SLANT))
glyph("s", stroke([(6, 5.5), (2, 5.5), (2, 8.5), (6, 8.5), (6, 11.5), (2, 11.5)], [0, R, R, R, R, 0]))
glyph("t", stroke([(3, 3.5), (3, 11.5), (6, 11.5)], [0, R, 0]), stroke([(2, 5.5), (6, 5.5)]))
glyph("u", stroke([(2, 5.5), (2, 11.5), (6, 11.5)], [0, R, 0]), stroke([(6, 5.5), (6, 11.5)]))
glyph("v", stroke([(2, 5.5), (2, 9.5), (4, 11.5), (6, 9.5), (6, 5.5)], [0, 0.6, 0.5, 0.6, 0]))
glyph("w", stroke([(2, 5.5), (2, 11.5)], pen=SLANT), stroke([(7, 5.5), (7, 11.5)], pen=SLANT),
      stroke([(2, 11.5), (4.5, 8.0)], pen=SLANT), stroke([(7, 11.5), (4.5, 8.0)], pen=SLANT))
glyph("x", stroke([(2, 5.5), (2, 6.5), (6, 10.5), (6, 11.5)], [0, 0.6, 0.6, 0]),
      stroke([(6, 5.5), (6, 6.5), (2, 10.5), (2, 11.5)], [0, 0.6, 0.6, 0]))
glyph("y", stroke([(2, 5.5), (2, 11.5), (6, 11.5)], [0, R, 0]),
      stroke([(6, 5.5), (6, 11.2), (4.4, 13), (3.2, 14), (2, 14)], [0, 0.6, 0.6, 0.4, 0], pen=(STEM, 2)))
glyph("z", stroke([(2, 5.5), (6, 5.5), (6, 6.5), (2, 10.5), (2, 11.5), (6, 11.5)], [0, 0, 0.6, 0.6, 0, 0]))

# Marks
glyph("!", rrect(1, T, 5, 7, (1.6, 1.6, 0, 0)), poly((1, 6.9), (5, 6.9), (4, 9), (2, 9)), rect(2, 10, 4, B))
glyph('"', rect(2, 4, 3, 8), rect(4, 4, 5, 8))
glyph("#", rect(2, T, 4, B), rect(5, T, 7, B), rect(1, 6, 8, 7), rect(1, 8, 8, 9))
glyph("$", stroke([(6, 5.5), (6, 4.5), (2, 4.5), (2, 7.5), (5, 7.5), (6, 8.5), (6, 11.5), (2, 11.5), (2, 10.5)],
                  [0, 0, R, R, 0.8, 0.8, R, 0, 0]),
      stroke([(4.5, 3), (4.5, 4)], pen=THIN), stroke([(4.5, 12), (4.5, 14)], pen=THIN))
glyph("%", stroke([(1.5, 3.5), (4.5, 3.5), (4.5, 6.5), (1.5, 6.5)], 1.0, pen=THIN, closed=True),
      stroke([(3.5, 8.5), (6.5, 8.5), (6.5, 11.5), (3.5, 11.5)], 1.0, pen=THIN, closed=True),
      stroke([(6, 6.5), (2, 8.5)]))
glyph("&", stroke([(5.5, 4.5), (2, 4.5), (2, 11.5), (6.5, 11.5)], [0, R, 0, 0]),
      stroke([(2.4, 8.5), (5.5, 11)], [0, 0]), stroke([(6, 8.5), (5, 9.6)]))
glyph("'", rect(3, T, 5, 6))
glyph("(", arc(6.9, 8, 5.9, 6, 124, 236))
glyph(")", arc(0.1, 8, 5.9, 6, -56, 56))
glyph("*", stroke([(2, 5.5), (5, 9.5)]), stroke([(5, 5.5), (2, 9.5)]), stroke([(2, 7.5), (6, 7.5)]))
glyph("+", rect(4, X, 5, B), rect(1, 8, 8, 9))
glyph(",", rect(3, 10, 6, B), stroke([(5, 12.4), (4, 13.5)]))
glyph("-", rect(1, 8, 7, 9))
glyph(".", rect(3, 10, 6, B))
glyph("/", band(5.3, 2, 0.7, 14))
glyph("\\", band(0.7, 2, 5.3, 14))
glyph(":", rect(2, X, 5, 7), rect(2, 10, 5, B))
glyph(";", rect(3, X, 6, 7), rect(3, 10, 6, B), stroke([(5, 12.4), (4, 13.5)]))
glyph("<", band(7, 5, 0, 8.5), band(0, 8.5, 7, 12), cut(rect(-1, 0, 1, 16), rect(8, 0, 9, 16)))
glyph("=", rect(1, 7, 7, 8), rect(1, 9, 7, 10))
glyph(">", band(-1, 5, 6, 8.5), band(6, 8.5, -1, 12), cut(rect(-2, 0, 1, 16), rect(8, 0, 9, 16)))
glyph("?", stroke([(2, 5.5), (2, 3.5), (6, 3.5), (6, 5.5), (4, 7.5), (4, 8.5)], [0, R, R, 0.8, 0.6, 0]), rect(3, 10, 5, B))
glyph("@", ring(1, T, 7, 13, ro=2.6, ri=1.8, stem=1), cut(rect(6, 9.4, 7, 11)),
      ring(3, 6, 7, 10, (1, 0, 0, 1), ro=1.3, ri=0.4, stem=1))
glyph("[", rect(3, T, 7, T + 1), rect(3, T, 5, 14), rect(3, 13, 7, 14))
glyph("]", rect(1, T, 5, T + 1), rect(3, T, 5, 14), rect(1, 13, 5, 14))
glyph("^", poly((4, T), (5, T), (7, 7), (6, 7), (4.5, 4.3), (3, 7), (2, 7)))
glyph("_", rect(1, 14, 8, 15))
glyph("`", stroke([(4, 3.5), (4, 5.5), (5, 6.5)], [0, 0.5, 0]))
glyph("{", stroke([(5, 3.5), (4, 3.5), (4, 6.5), (3, 7.5), (4, 8.5), (4, 13.5), (5, 13.5)], [0, 0.6, 0.6, 0, 0.6, 0.6, 0]))
glyph("|", rect(3, T, 5, 14))
glyph("}", stroke([(2, 3.5), (3, 3.5), (3, 6.5), (4, 7.5), (3, 8.5), (3, 13.5), (2, 13.5)], [0, 0.6, 0.6, 0, 0.6, 0.6, 0]))
glyph("~", wave())


def mask(ch: str, scale: float, supersample: int = 4) -> Image.Image:
    """The letter's coverage in a cell `scale` pixels to a unit, edges smoothed by drawing
    at `supersample` times and averaging."""
    s = scale * supersample
    w, h = round(CELL_W * s), round(CELL_H * s)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    for sign, pts in GLYPHS.get(ch, []):
        d.polygon([(x * s, y * s) for x, y in pts], fill=255 if sign == "+" else 0)
    return img.resize((round(CELL_W * scale), round(CELL_H * scale)), Image.BOX)


# ---- measuring against the original ----

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "build/native-runtime/original-fonts/kmrfog08"   # fnt_console, as KMRP's Original Font has it


def original_cells() -> dict[str, np.ndarray]:
    """The original's white letters, each its 8 by 16 cell, True where it is white."""
    im = np.asarray(Image.open(f"{ORIGINAL}.tga").convert("RGBA")).astype(float)
    white = (im[..., :3].mean(2) / 255) * (im[..., 3] / 255) > 0.5
    lines = [l.strip() for l in Path(f"{ORIGINAL}.txi").read_text().splitlines() if l.strip()]
    up = next(i for i, l in enumerate(lines) if l.startswith("upperleftcoords"))
    lo = next(i for i, l in enumerate(lines) if l.startswith("lowerrightcoords"))
    n = im.shape[0]
    cells = {}
    for c in range(33, 127):
        x0, y0 = map(float, lines[up + 1 + c].split()[:2])
        x1, y1 = map(float, lines[lo + 1 + c].split()[:2])
        box = (round(x0 * n), round((1 - y0) * n), round(x1 * n), round((1 - y1) * n))
        cells[chr(c)] = white[box[1]:box[3], box[0]:box[2]]
    return cells


def check(out: Path) -> None:
    """Each letter drawn back at the original's size against the original: the pixels
    that differ, and a sheet of the original (each pixel 6x6) beside the new letter."""
    cells = original_cells()
    report = []
    tiles = []
    for ch in GLYPHS:
        back = np.asarray(mask(ch, 1, 16)) / 255 > 0.5
        orig = cells[ch]
        diff = int((back != orig).sum())
        report.append((diff, ch))
        o = Image.fromarray((orig * 255).astype(np.uint8)).resize((48, 96), Image.NEAREST)
        n = mask(ch, 6, 8)
        tile = Image.new("L", (110, 100), 30)
        tile.paste(o, (2, 2))
        tile.paste(n, (58, 2))
        tiles.append(tile)
    cols = 12
    sheet = Image.new("L", (cols * 112, math.ceil(len(tiles) / cols) * 102), 0)
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 112, (i // cols) * 102))
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / "hud-geometry-check.png")
    for diff, ch in sorted(report, reverse=True):
        print(f"{ch!r}: {diff} pixels differ")


if __name__ == "__main__":
    check(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/hud-geometry")
