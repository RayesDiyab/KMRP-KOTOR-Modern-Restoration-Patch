#!/usr/bin/env python3
"""The Controller Layout screen's backdrop and edge art.

The screen is full-screen, so it needs something behind it, but what it shows is
the controller: everything here stays dim and at the edges.

  * `kmrlytbg`   -- deep navy with a soft centre glow and a vignette. It is the
    panel root's fill and so the only texture stretched to the screen, which is
    why it is a smooth gradient and nothing else: a pattern would stretch with it.
  * `kmrlytcn0..3` -- corner brackets, one per corner.
  * `kmrlythair` -- a hairline that fades out at both ends. Stretched along its
    length only, and it has no feature that would show the stretch.
  * `kmrlytrd0/1` -- two small status readouts.
  * `kmrlytgun`  -- a turret gunnery station: targeting scope, target data,
    twin-grip yoke on its pivot, power cells and switches. Left margin.
  * `kmrlytship` -- a light freighter drawn as a deck plan, top view and side
    elevation, its dorsal turret ringed. Right margin.

All drawing is original. The writing on it is real Aurebesh, set in SilvinoR's
OFL-1.1 font (third_party/aurebesh-font), whose 26 letters were checked against
the canonical chart. Aurebesh is a letter-for-letter cipher of English, so every
label is an English phrase that means what it says -- `aurebesh()` refuses any
text that the font cannot spell correctly. Canon writes CH, AE, EO, KH, NG, OO,
SH and TH with letters of their own, which this no-ligature font lacks, so
labels simply avoid those pairs rather than spelling them wrongly.

Everything but the backdrop keeps its aspect on screen: `placements()` sizes each
piece from the screen and the design scale, and hides the two illustrations
when the margins beside the 760-unit board are too narrow to hold them.
"""
from __future__ import annotations

import math
from pathlib import Path

INK = (0, 168, 250)          # KOTOR's cyan, as the diagram uses
STEEL = (120, 170, 205)      # the paler, quieter line
AMBER = (250, 196, 70)       # status lights and the one thing that matters

SS = 3                       # supersampling for every line drawing

AUREBESH_FONT = (Path(__file__).resolve().parent.parent / "third_party" /
                 "aurebesh-font" / "AurebeshNL.ttf")
# Letters canon writes with a digraph letter of their own. The no-ligature font
# would spell them as two letters, which a reader of Aurebesh reads as wrong.
DIGRAPHS = ("CH", "AE", "EO", "KH", "NG", "OO", "SH", "TH")

# Design units, the same space the layout uses (720 units = screen height).
CORNER = 110
EDGE_GAP = 14
READOUT = (150, 40)
HAIR_H = 6
ART_MAX_W, ART_MIN_W = 200, 110
ART_MARGIN = 20              # clear space either side of an illustration
READOUT_INSET = 22           # the readouts, in from the corner brackets' gap
HAIR_OVERLAP = 0.7           # of a corner bracket, how far the hairlines run into it

# The fill of DECO_00, DECO_01, ... in ID order after the rows. The runtime
# binds DECO_nn by tag; K1_LAYOUT_DECOR in K1ControllerLayout.cpp must equal
# len(DECOR), and Test-ControllerPromptAssets.py checks that it does.
DECOR = [
    "kmrlytcn0", "kmrlytcn1", "kmrlytcn2", "kmrlytcn3",
    "kmrlythair", "kmrlythair",
    "kmrlytrd0", "kmrlytrd1",
    "kmrlytgun", "kmrlytship",
]
TEXTURES = ["kmrlytbg", "kmrlytcn0", "kmrlytcn1", "kmrlytcn2", "kmrlytcn3",
            "kmrlythair", "kmrlytrd0", "kmrlytrd1", "kmrlytgun", "kmrlytship"]


# ---------------------------------------------------------------- placement

def placements(width: int, height: int, scale: float, top: float,
               design_w: float, upper_y: float, lower_y: float):
    """Screen-pixel extents (x, y, w, h), one per DECOR entry, in order.

    `top` is the pixel row of design y=0; `upper_y`/`lower_y` are the design
    rows the two hairlines run along. A hidden piece gets a zero extent, which
    the engine draws as nothing but still lets the runtime bind the tag.
    """
    s = scale
    gap, c = EDGE_GAP * s, CORNER * s
    out = [
        (gap, gap, c, c),
        (width - gap - c, gap, c, c),
        (gap, height - gap - c, c, c),
        (width - gap - c, height - gap - c, c, c),
    ]
    # Hairlines run between the corner brackets.
    x0, x1 = gap + c * HAIR_OVERLAP, width - gap - c * HAIR_OVERLAP
    for y in (upper_y, lower_y):
        cy = top + y * s
        out.append((x0, cy - HAIR_H * s / 2, x1 - x0, HAIR_H * s))
    rw, rh = READOUT[0] * s, READOUT[1] * s
    inset = gap + READOUT_INSET * s
    out.append((inset, inset, rw, rh))
    out.append((width - inset - rw, height - inset - rh, rw, rh))

    # The illustrations sit in the margin beside the board, centred in it.
    margin = (width / s - design_w) / 2                  # design units
    w = min(ART_MAX_W, margin - 2 * ART_MARGIN, (height / s - 2 * CORNER) / 2)
    for side in (0, 1):
        if w < ART_MIN_W:
            out.append((0, 0, 0, 0))
            continue
        cx = margin / 2 if side == 0 else width / s - margin / 2
        out.append(((cx - w / 2) * s, height / 2 - w * s, w * s, 2 * w * s))
    return [tuple(round(v) for v in e) for e in out]


# ---------------------------------------------------------------- drawing

def aurebesh(text: str) -> str:
    """Check a label is something the font spells correctly, and return it."""
    upper = text.upper()
    bad = [d for d in DIGRAPHS if d in upper.replace(" ", "|")]
    if bad or any(not (ch.isalnum() and ch.isascii() or ch == " ") for ch in upper):
        raise ValueError(f"{text!r} cannot be written correctly in this font "
                         f"(digraphs {bad})")
    return upper


def _rgba(colour, alpha):
    return tuple(colour) + (max(0, min(255, round(alpha))),)


class Pen:
    """Draws in logical units on a supersampled canvas; `finish()` downsamples.

    `res` is output texture pixels per logical unit, so a piece can be drawn
    once in simple coordinates and delivered at a resolution that stays sharp
    on a 4K screen.
    """

    def __init__(self, size, res=1):
        from PIL import Image, ImageDraw
        self.size, self.res = size, res
        self.k = SS * res
        self.image = Image.new("RGBA", (round(size[0] * self.k), round(size[1] * self.k)),
                               (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.image)
        self._fonts = {}

    def _p(self, pts):
        return [(x * self.k, y * self.k) for x, y in pts]

    def _w(self, width):
        return max(1, round(width * self.k))

    def line(self, pts, colour, alpha, width=1.0):
        self.d.line(self._p(pts), fill=_rgba(colour, alpha), width=self._w(width),
                    joint="curve")

    def poly(self, pts, colour, alpha, fill_alpha=0, width=1.0):
        pts = self._p(pts)
        if fill_alpha:
            self.d.polygon(pts, fill=_rgba(colour, fill_alpha))
        if alpha:
            self.d.line(pts + [pts[0]], fill=_rgba(colour, alpha), width=self._w(width),
                        joint="curve")

    def _box(self, c, r):
        return [(c[0] - r) * self.k, (c[1] - r) * self.k,
                (c[0] + r) * self.k, (c[1] + r) * self.k]

    def circle(self, c, r, colour, alpha, width=1.0, fill_alpha=0):
        if fill_alpha:
            self.d.ellipse(self._box(c, r), fill=_rgba(colour, fill_alpha))
        if alpha:
            self.d.ellipse(self._box(c, r), outline=_rgba(colour, alpha),
                           width=self._w(width))

    def arc(self, c, r, a0, a1, colour, alpha, width=1.0):
        self.d.arc(self._box(c, r), a0, a1, fill=_rgba(colour, alpha),
                   width=self._w(width))

    def wedge(self, c, r, a0, a1, colour, alpha):
        self.d.pieslice(self._box(c, r), a0, a1, fill=_rgba(colour, alpha))

    def rect(self, box, colour, alpha, fill_alpha=0, width=1.0):
        x0, y0, x1, y1 = box
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], colour, alpha,
                  fill_alpha, width)

    def fill(self, box, colour, alpha):
        x0, y0, x1, y1 = box
        self.d.rectangle([x0 * self.k, y0 * self.k, x1 * self.k, y1 * self.k],
                         fill=_rgba(colour, alpha))

    def dashed(self, a, b, colour, alpha, width=1.0, dash=6.0, gap=4.0):
        (x0, y0), (x1, y1) = a, b
        length = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        t = 0.0
        while t < length:
            e = min(length, t + dash)
            self.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * e, y0 + uy * e)],
                      colour, alpha, width)
            t = e + gap

    def text(self, xy, text, size, colour, alpha, anchor="ls"):
        """Aurebesh at cap height `size`; returns the text's logical width."""
        from PIL import ImageFont
        px = round(size * self.k * 1.25)
        font = self._fonts.get(px)
        if font is None:
            font = self._fonts[px] = ImageFont.truetype(str(AUREBESH_FONT), px)
        value = aurebesh(text)
        self.d.text((xy[0] * self.k, xy[1] * self.k), value, font=font,
                    fill=_rgba(colour, alpha), anchor=anchor)
        return self.d.textlength(value, font=font) / self.k

    def finish(self, flip_x=False, flip_y=False):
        from PIL import Image
        out = (round(self.size[0] * self.res), round(self.size[1] * self.res))
        image = self.image.resize(out, Image.LANCZOS)
        if flip_x:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        if flip_y:
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
        return image


class OutlinePen:
    """Pen's twin that keeps outlines instead of pixels, for the controller patch to draw
    each piece at the size it is shown (2026-10-27): the same calls, the same numbers.

    PIL's drawing on an RGBA image replaces the pixels a shape covers rather than blending
    over them, so each shape here is cut by every shape drawn after it; what is left of the
    shapes then never overlaps, and those of one colour are one item. A line is its path
    widened with round joins and flat ends, as PIL's joint="curve" draws it; a circle's or
    an arc's outline lies inside its radius, as PIL's does. `finish()` gives the outlines as
    tools/controller_glyphs.py holds them, the box the piece's logical size.
    """

    def __init__(self, size, res=1):
        self.size, self.res = size, res
        self.k = SS * res
        self.shapes = []                          # (geometry, RGBA), in drawing order

    def _add(self, geometry, colour, alpha):
        a = max(0, min(255, round(alpha)))
        if a and not geometry.is_empty:
            self.shapes.append((geometry, tuple(colour) + (a,)))

    def _w(self, width):
        return max(1, round(width * self.k)) / self.k

    def _stroke(self, pts, width, closed=False):
        from shapely.geometry import LinearRing, LineString
        line = LinearRing(pts) if closed else LineString(pts)
        return line.buffer(self._w(width) / 2, quad_segs=16, cap_style="flat", join_style="round")

    def line(self, pts, colour, alpha, width=1.0):
        self._add(self._stroke(pts, width), colour, alpha)

    def poly(self, pts, colour, alpha, fill_alpha=0, width=1.0):
        from shapely.geometry import Polygon
        if fill_alpha:
            self._add(Polygon(pts).buffer(0), colour, fill_alpha)
        if alpha:
            self._add(self._stroke(pts, width, closed=True), colour, alpha)

    def _disc(self, c, r):
        from shapely.geometry import Point
        return Point(c).buffer(r, quad_segs=32)

    def circle(self, c, r, colour, alpha, width=1.0, fill_alpha=0):
        if fill_alpha:
            self._add(self._disc(c, r), colour, fill_alpha)
        if alpha:
            inner = r - self._w(width)
            ring = self._disc(c, r)
            self._add(ring.difference(self._disc(c, inner)) if inner > 0 else ring, colour, alpha)

    def _sector(self, c, r0, r1, a0, a1):
        from shapely.geometry import Polygon
        steps = max(2, math.ceil(abs(a1 - a0) / 3))
        angles = [math.radians(a0 + (a1 - a0) * i / steps) for i in range(steps + 1)]
        outer = [(c[0] + r1 * math.cos(a), c[1] + r1 * math.sin(a)) for a in angles]
        inner = ([(c[0] + r0 * math.cos(a), c[1] + r0 * math.sin(a)) for a in reversed(angles)]
                 if r0 > 0 else [tuple(c)])
        return Polygon(outer + inner).buffer(0)

    def arc(self, c, r, a0, a1, colour, alpha, width=1.0):
        self._add(self._sector(c, max(0.0, r - self._w(width)), r, a0, a1), colour, alpha)

    def wedge(self, c, r, a0, a1, colour, alpha):
        self._add(self._sector(c, 0, r, a0, a1), colour, alpha)

    def rect(self, box, colour, alpha, fill_alpha=0, width=1.0):
        x0, y0, x1, y1 = box
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], colour, alpha, fill_alpha, width)

    def fill(self, box, colour, alpha):
        from shapely.geometry import box as rectangle
        self._add(rectangle(*box), colour, alpha)

    dashed = Pen.dashed

    def text(self, xy, text, size, colour, alpha, anchor="ls"):
        """Aurebesh at cap height `size`, from the font's outlines at the size Pen.text
        sets it (its kerning too); returns the text's logical width."""
        from shapely.affinity import affine_transform
        value = aurebesh(text)
        em = round(size * self.k * 1.25) / self.k
        font = _aurebesh_font()
        scale = em / font["units"]
        x, shapes = 0.0, []
        previous = None
        for ch in value:
            name = font["cmap"][ord(ch)]
            if previous is not None:
                x += font["kern"].get((previous, name), 0) * scale
            outline = font["outlines"][name]
            if outline is not None:
                shapes.append(affine_transform(outline, [scale, 0, 0, -scale, x, 0]))
            x += font["advance"][name] * scale
            previous = name
        dx = {"l": 0.0, "m": -x / 2, "r": -x}[anchor[0]]
        if anchor[1] != "s":
            raise ValueError(f"anchor {anchor!r}: only baseline anchors are drawn")
        for shape in shapes:
            self._add(affine_transform(shape, [1, 0, 0, 1, xy[0] + dx, xy[1]]), colour, alpha)
        return x

    def finish(self, flip_x=False, flip_y=False, dim=1.0):
        """The outlines: each shape less what was drawn over it, merged by colour, flipped
        across the piece as asked; `dim` scales every alpha (_dim)."""
        import build_controller_glyph_vectors as vectors
        from shapely.affinity import scale as flip
        from shapely.geometry import MultiPolygon, Polygon
        from shapely.ops import unary_union
        w, h = self.size
        above, kept = None, {}
        for geometry, rgba in reversed(self.shapes):
            seen = geometry if above is None else geometry.difference(above)
            above = geometry if above is None else above.union(geometry)
            if not seen.is_empty:
                kept.setdefault(rgba, []).append(seen)
        items = []
        for (r, g, b, a), parts in sorted(kept.items(), key=lambda kv: kv[0]):
            area = unary_union(parts).simplify(0.01, preserve_topology=True)
            if flip_x or flip_y:
                area = flip(area, -1 if flip_x else 1, -1 if flip_y else 1, origin=(w / 2, h / 2))
            polys = []
            for part in getattr(area, "geoms", [area]):
                if isinstance(part, Polygon) and not part.is_empty:
                    polys.append(list(part.exterior.coords)[:-1])
                    polys.extend(list(ring.coords)[:-1] for ring in part.interiors)
            if polys:
                items.append(vectors.Item(polys, "evenodd", ("solid", (r, g, b, round(a * dim)))))
        return vectors.encode(items, (0, 0, w, h))


_FONT = None


def _aurebesh_font():
    """The Aurebesh font's outlines (shapely, font units, y up), advances, kerning pairs."""
    global _FONT
    if _FONT is None:
        from fontTools.pens.recordingPen import DecomposingRecordingPen
        from fontTools.ttLib import TTFont
        from shapely.geometry import Polygon
        font = TTFont(AUREBESH_FONT)
        glyph_set = font.getGlyphSet()
        outlines = {}
        for name in glyph_set.keys():
            pen = DecomposingRecordingPen(glyph_set)
            glyph_set[name].draw(pen)
            loops, loop = [], []
            for op, args in pen.value:
                if op == "moveTo":
                    loop = [args[0]]
                elif op == "lineTo":
                    loop.append(args[0])
                elif op == "qCurveTo":
                    # TrueType: implied on-curve points between consecutive off-curve ones.
                    points = list(args)
                    start = loop[-1]
                    for i, c in enumerate(points[:-1]):
                        end = points[-1] if i == len(points) - 2 else (
                            ((c[0] + points[i + 1][0]) / 2, (c[1] + points[i + 1][1]) / 2))
                        for s in range(1, 9):
                            u = s / 8
                            loop.append(((1 - u) ** 2 * start[0] + 2 * (1 - u) * u * c[0] + u * u * end[0],
                                         (1 - u) ** 2 * start[1] + 2 * (1 - u) * u * c[1] + u * u * end[1]))
                        start = end
                elif op in ("closePath", "endPath"):
                    if len(loop) >= 3:
                        loops.append(loop)
                    loop = []
            area = None
            for points in loops:
                ring = Polygon(points).buffer(0)
                area = ring if area is None else area.symmetric_difference(ring)
            outlines[name] = area
        kern = {}
        if "kern" in font:
            for table in font["kern"].kernTables:
                kern.update(table.kernTable)
        _FONT = {"units": font["head"].unitsPerEm, "cmap": font.getBestCmap(),
                 "advance": {n: font["hmtx"][n][0] for n in glyph_set.keys()},
                 "kern": kern, "outlines": outlines}
    return _FONT


def _screw(p, c, r=3.2, alpha=110):
    p.circle(c, r, STEEL, alpha, 1.0, fill_alpha=alpha * 0.25)
    p.line([(c[0] - r * 0.6, c[1] - r * 0.6), (c[0] + r * 0.6, c[1] + r * 0.6)],
           STEEL, alpha, 0.9)


def _gauge(p, x, y, cells, lit, w=17, h=24, step=24, colour=INK):
    for k in range(cells):
        cx = x + k * step
        p.fill((cx, y, cx + w, y + h), colour, 150 if k < lit else 32)
        p.rect((cx, y, cx + w, y + h), colour, 60 if k < lit else 40, width=0.8)


# ---------------------------------------------------------------- the pieces

def backdrop():
    """Deep navy, a soft centre glow, a vignette. 1024x512, opaque."""
    import numpy as np
    from PIL import Image
    w, h = 1024, 512
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = x / (w - 1), y / (h - 1)
    top, bottom = np.array([11, 22, 42], np.float32), np.array([3, 7, 17], np.float32)
    base = top[None, None] * (1 - v[..., None]) + bottom[None, None] * v[..., None]
    d = np.sqrt(((u - 0.5) / 0.55) ** 2 + ((v - 0.46) / 0.62) ** 2)
    glow = np.clip(1 - d, 0, 1) ** 1.8
    base += glow[..., None] * np.array([0, 44, 78], np.float32)
    vignette = np.clip(np.sqrt(((u - 0.5) / 0.72) ** 2 + ((v - 0.5) / 0.78) ** 2), 0, 1.4)
    base *= (1 - 0.45 * np.clip(vignette - 0.45, 0, 1))[..., None]
    # A little noise so the gradient does not band once it is stretched.
    base += np.random.default_rng(7).uniform(-1.2, 1.2, base.shape).astype(np.float32)
    rgb = np.clip(base, 0, 255).astype(np.uint8)
    alpha = np.full((h, w, 1), 255, np.uint8)
    return Image.fromarray(np.concatenate([rgb, alpha], axis=2), "RGBA")


def corner(index, pen=None):
    """A top-left bracket, turned for the other three corners. 256x256."""
    p = (pen or Pen)((256, 256))
    t = 3
    # Main L, with the corner itself cut at 45 degrees.
    p.line([(t, 150), (t, 22), (22, t), (150, t)], INK, 150, 3)
    p.line([(t, 150), (t, 196)], INK, 55, 3)
    p.line([(150, t), (196, t)], INK, 55, 3)
    # An inner, thinner echo, shorter.
    p.line([(16, 92), (16, 30), (30, 16), (92, 16)], STEEL, 80, 1.4)
    # Ticks along the long arms.
    for k in range(5):
        p.line([(t + 8, 110 + k * 8), (t + 14, 110 + k * 8)], STEEL, 70, 1.2)
        p.line([(110 + k * 8, t + 8), (110 + k * 8, t + 14)], STEEL, 70, 1.2)
    # A node where the echo ends, and one amber light.
    p.circle((92, 16), 3, INK, 140, 1.3)
    p.circle((16, 92), 2.2, AMBER, 0, fill_alpha=150)
    return p.finish(flip_x=index in (1, 3), flip_y=index in (2, 3))


def hairline():
    """1024x32: a line that fades out at both ends, brightest in the middle."""
    import numpy as np
    from PIL import Image
    w, h = 1024, 32
    u = np.linspace(0, 1, w, dtype=np.float32)
    along = np.clip(1 - np.abs(u - 0.5) / 0.5, 0, 1) ** 0.8
    rows = np.zeros(h, np.float32)
    rows[15:17] = 1.0
    rows[14] = rows[17] = 0.35
    alpha = (np.outer(rows, along) * 150).astype(np.uint8)
    rgb = np.broadcast_to(np.array(INK, np.uint8), (h, w, 3))
    return Image.fromarray(np.dstack([rgb, alpha[..., None]]), "RGBA")


# What the two readouts say. Top left reports the controller link; bottom
# right is the ship's navigation status.
READOUTS = (
    ("INPUT LINK", "GAMEPAD SYNC", "STATUS READY", 7),
    ("NAV COMPUTER", "COURSE PLOTTED", "SYSTEMS NOMINAL", 5),
)


def readout(index, pen=None):
    """512x128 at 2x: a status light, three lines of Aurebesh, a short gauge."""
    title, line2, line3, lit = READOUTS[index]
    p = (pen or Pen)((256, 64), res=2)
    p.circle((6, 9), 3, AMBER, 0, fill_alpha=180)
    w = p.text((14, 13), title, 10, INK, 200)
    p.line([(18 + w, 9), (250, 9)], STEEL, 50, 0.6)
    p.text((14, 28), line2, 7, STEEL, 150)
    p.text((14, 41), line3, 7, STEEL, 130)
    _gauge(p, 14, 50, 10, lit, w=8, h=6, step=11)
    p.line([(128, 53), (250, 53)], STEEL, 50, 0.6)
    return p.finish()


def gunnery_station(pen=None):
    """1024x2048: a turret gunner's station, drawn at 512x1024 logical."""
    p = (pen or Pen)((512, 1024), res=2)

    # Header plate.
    p.circle((40, 42), 5, AMBER, 0, fill_alpha=190)
    w = p.text((54, 50), "TURRET CONTROL", 22, INK, 210)
    p.line([(40, 64), (472, 64)], INK, 110, 1.6)
    p.line([(40, 70), (220, 70)], STEEL, 70, 1)
    p.text((472, 50), "GUNNER", 12, STEEL, 150, anchor="rs")

    # ---- Targeting scope.
    c, R = (256, 268), 160
    # Bezel with mounting lugs.
    p.circle(c, R + 30, STEEL, 70, 1.6)
    p.circle(c, R + 20, STEEL, 45, 1.0)
    for k in range(8):
        a = math.radians(22.5 + k * 45)
        lx, ly = c[0] + (R + 25) * math.cos(a), c[1] + (R + 25) * math.sin(a)
        _screw(p, (lx, ly), 4.2, 120)
    p.circle(c, R, INK, 170, 3, fill_alpha=22)
    # Sweep: a fading wedge trailing the beam.
    for k in range(24):
        p.wedge(c, R - 4, -62 + k * 1.7, -60 + k * 1.7, INK, 2 + k * 1.3)
    a = math.radians(-20)
    p.line([c, (c[0] + (R - 4) * math.cos(a), c[1] + (R - 4) * math.sin(a))], INK, 170, 1.6)
    # Bearing ticks, cardinal pointers.
    for k in range(120):
        ang = math.radians(k * 3)
        major = k % 10 == 0
        r0 = R - (18 if major else 8 if k % 5 == 0 else 5)
        p.line([(c[0] + r0 * math.cos(ang), c[1] + r0 * math.sin(ang)),
                (c[0] + R * math.cos(ang), c[1] + R * math.sin(ang))],
               INK, 150 if major else 80, 1.8 if major else 1.0)
    for k in range(4):
        ang = math.radians(k * 90 - 90)
        tip = (c[0] + (R + 12) * math.cos(ang), c[1] + (R + 12) * math.sin(ang))
        side = math.radians(k * 90)
        base = [(tip[0] + 9 * math.cos(ang) + 7 * math.cos(side),
                 tip[1] + 9 * math.sin(ang) + 7 * math.sin(side)),
                (tip[0] + 9 * math.cos(ang) - 7 * math.cos(side),
                 tip[1] + 9 * math.sin(ang) - 7 * math.sin(side))]
        p.poly([tip] + base, AMBER if k == 0 else INK, 170, 90)
    # Range rings, dashed middle ring.
    for k in range(36):
        p.arc(c, 118, k * 10, k * 10 + 6, STEEL, 100, 1.4)
    p.circle(c, 60, STEEL, 80, 1.2)
    # Crosshair with a gap and mil dots.
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p.line([(c[0] + dx * 22, c[1] + dy * 22), (c[0] + dx * (R - 22), c[1] + dy * (R - 22))],
               INK, 120, 1.4)
        for m in range(1, 7):
            q = (c[0] + dx * m * 22, c[1] + dy * m * 22)
            p.circle(q, 1.8, INK, 0, fill_alpha=150)
    p.circle(c, 5, INK, 170, 1.2)
    # Contacts: two faint returns and the locked target.
    for q in ((c[0] - 96, c[1] + 58), (c[0] - 40, c[1] + 120)):
        p.circle(q, 3.2, STEEL, 0, fill_alpha=150)
        p.circle(q, 7, STEEL, 60, 0.8)
    tx, ty = c[0] + 62, c[1] - 52
    p.poly([(tx, ty - 11), (tx + 5, ty), (tx, ty + 7), (tx - 5, ty)], INK, 210, 60, 1.4)
    for sgn in (-1, 1):
        p.poly([(tx + sgn * 4, ty - 2), (tx + sgn * 24, ty - 13),
                (tx + sgn * 26, ty - 7), (tx + sgn * 5, ty + 4)], INK, 190, 40, 1.2)
    b = 30
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = tx + sx * b, ty + sy * b * 0.8
        p.line([(x, y - sy * 10), (x, y), (x - sx * 10, y)], AMBER, 200, 2)
    # Lead pip, where to aim for the shot to meet it.
    lead = (tx - 34, ty + 20)
    p.circle(lead, 5, AMBER, 190, 1.4)
    p.dashed((tx - 6, ty + 5), lead, AMBER, 120, 1.0, 4, 3)

    # ---- Target data.
    y0 = 470
    p.rect((56, y0, 456, y0 + 76), STEEL, 90, 14, 1.2)
    p.fill((56, y0, 62, y0 + 76), AMBER, 150)
    p.text((74, y0 + 24), "TARGET LOCK", 15, AMBER, 210)
    p.text((440, y0 + 24), "HOSTILE", 11, INK, 170, anchor="rs")
    p.line([(74, y0 + 34), (440, y0 + 34)], STEEL, 60, 0.8)
    p.text((74, y0 + 54), "DISTANCE", 10, STEEL, 150)
    p.text((250, y0 + 54), "2400", 10, INK, 180, anchor="rs")
    p.text((270, y0 + 54), "SPEED", 10, STEEL, 150)
    p.text((440, y0 + 54), "410", 10, INK, 180, anchor="rs")
    for k in range(24):
        h = 3 + 5 * abs(math.sin(k * 0.9))
        p.fill((74 + k * 15, y0 + 70 - h, 74 + k * 15 + 8, y0 + 70), INK, 110)

    # ---- Twin-grip yoke on its pivot.
    yc = 736
    # Pivot column, hydraulic struts and base plate first, so the yoke is on top.
    p.rect((244, yc + 30, 268, 900), STEEL, 110, 30, 1.4)
    for k in range(5):
        p.line([(244, yc + 50 + k * 22), (268, yc + 50 + k * 22)], STEEL, 60, 0.8)
    for sgn in (-1, 1):
        p.line([(256 + sgn * 18, yc + 70), (256 + sgn * 92, 892)], STEEL, 100, 5)
        p.line([(256 + sgn * 18, yc + 70), (256 + sgn * 55, yc + 110)], INK, 110, 2.4)
        p.circle((256 + sgn * 92, 892), 4, STEEL, 120, 1.0)
    p.poly([(150, 896), (362, 896), (382, 922), (130, 922)], STEEL, 120, 30, 1.6)
    for x in (148, 200, 312, 364):
        _screw(p, (x, 910), 3.4, 120)
    # Cable run from base to the right grip.
    p.line([(362, 906), (420, 880), (440, 800), (420, yc + 10)], STEEL, 70, 2.2)
    # Crossbar, doubled for thickness.
    bar = [(100, yc - 12), (150, yc + 12), (362, yc + 12), (412, yc - 12)]
    p.line(bar, INK, 170, 6)
    p.line([(x, y + 12) for x, y in bar[1:3]], STEEL, 70, 1.6)
    # Hub with six bolts.
    p.circle((256, yc + 8), 34, INK, 170, 2.6, fill_alpha=40)
    p.circle((256, yc + 8), 22, STEEL, 100, 1.2)
    for k in range(6):
        a = math.radians(k * 60)
        _screw(p, (256 + 28 * math.cos(a), yc + 8 + 28 * math.sin(a)), 2.4, 140)
    p.circle((256, yc + 8), 8, AMBER, 150, 1.4, fill_alpha=70)
    for sgn in (-1, 1):
        gx = 256 + sgn * 156
        top = yc - 124
        grip = [(gx - 20, top), (gx + 20, top), (gx + 24, yc - 6), (gx - 24, yc - 6)]
        p.poly(grip, INK, 190, 34, 2.4)
        # Finger grooves on the inboard side.
        for k in range(3):
            y = top + 40 + k * 24
            p.arc((gx - sgn * 20, y), 9, 270 if sgn < 0 else 90,
                  450 if sgn < 0 else 270, STEEL, 110, 1.2)
        # Trigger and guard.
        p.rect((gx - sgn * 26 - 5, top + 28, gx - sgn * 26 + 5, top + 60), AMBER, 160, 60, 1.2)
        p.arc((gx - sgn * 26, top + 44), 18, 90 if sgn > 0 else 270,
              270 if sgn > 0 else 450, STEEL, 100, 1.2)
        # Head: fire button and a hat switch.
        p.rect((gx - 16, top - 30, gx + 16, top), INK, 170, 40, 1.8)
        p.circle((gx - 6, top - 15), 5, AMBER if sgn > 0 else INK, 170, 1.2,
                 fill_alpha=110 if sgn > 0 else 40)
        p.circle((gx + 8, top - 15), 3.5, STEEL, 120, 1.0)
    p.text((256, yc - 36), "FIRE", 11, AMBER, 170, anchor="ms")

    # ---- Power cells and switches.
    y1 = 966
    p.text((56, y1), "POWER CELLS", 12, STEEL, 170)
    _gauge(p, 56, y1 + 10, 12, 9, w=19, h=20, step=25)
    p.text((456, y1), "ARMED", 12, AMBER, 190, anchor="rs")
    p.circle((456 - 58, y1 - 5), 3.2, AMBER, 0, fill_alpha=200)
    return p.finish()


def freighter(pen=None):
    """1024x2048: a light freighter's deck plan, drawn at 512x1024 logical."""
    p = (pen or Pen)((512, 1024), res=2)
    cx = 256

    # Header plate.
    p.circle((40, 42), 5, AMBER, 0, fill_alpha=190)
    p.text((54, 50), "LIGHT FREIGHTER", 22, INK, 210)
    p.line([(40, 64), (472, 64)], INK, 110, 1.6)
    p.line([(292, 70), (472, 70)], STEEL, 70, 1)
    p.text((472, 88), "DECK PLAN", 11, STEEL, 150, anchor="rs")

    # ---- Top view. Blunt-nosed and broad-shouldered: a hauler, not a fighter.
    oy = 20
    hull = [(cx - 30, 96), (cx + 30, 96), (cx + 62, 140), (cx + 84, 260),
            (cx + 92, 420), (cx + 128, 520), (cx + 134, 600), (cx + 102, 690),
            (cx + 62, 720), (cx - 62, 720), (cx - 102, 690), (cx - 134, 600),
            (cx - 128, 520), (cx - 92, 420), (cx - 84, 260), (cx - 62, 140)]
    hull = [(x, y * 0.78 + oy + 30) for x, y in hull]
    Y = lambda y: y * 0.78 + oy + 30          # noqa: E731 -- plan rows
    p.poly(hull, INK, 180, 26, 2.6)
    # Inner hull line, a plating inset.
    inner = [(cx + (x - cx) * 0.9, Y(((y - oy - 30) / 0.78 - 400) * 0.97 + 400))
             for x, y in hull]
    p.poly(inner, STEEL, 60, 0, 0.8)
    # Cockpit with window mullions.
    canopy = [(cx - 20, Y(112)), (cx + 20, Y(112)), (cx + 30, Y(150)), (cx + 22, Y(184)),
              (cx - 22, Y(184)), (cx - 30, Y(150))]
    p.poly(canopy, INK, 170, 50, 1.6)
    for dx in (-10, 0, 10):
        p.line([(cx + dx, Y(114)), (cx + dx * 1.4, Y(182))], STEEL, 90, 0.8)
    # Forward cargo-bay doors, hatched.
    for sgn in (-1, 1):
        x0, x1 = cx + sgn * 44 - 18, cx + sgn * 44 + 18
        p.rect((x0, Y(200), x1, Y(280)), STEEL, 90, 16, 1.2)
        for k in range(5):
            p.line([(x0 + 3, Y(206 + k * 15)), (x1 - 3, Y(206 + k * 15))], STEEL, 45, 0.7)
    # Plating seams.
    for y, half in ((300, 80), (360, 86), (420, 90), (520, 126), (610, 116), (680, 100)):
        p.line([(cx - half, Y(y)), (cx + half, Y(y))], STEEL, 55, 0.9)
    p.line([(cx, Y(290)), (cx, Y(460))], STEEL, 60, 0.9)
    p.line([(cx, Y(540)), (cx, Y(700))], STEEL, 60, 0.9)
    for sgn in (-1, 1):
        p.line([(cx + sgn * 92, Y(420)), (cx + sgn * 96, Y(640)), (cx + sgn * 62, Y(720))],
               STEEL, 70, 1.2)
        # Side pods with intake grilles.
        x0, x1 = cx + sgn * 108 - 14, cx + sgn * 108 + 14
        p.rect((min(x0, x1), Y(530), max(x0, x1), Y(610)), STEEL, 100, 20, 1.4)
        for k in range(6):
            p.line([(min(x0, x1) + 3, Y(538 + k * 12)), (max(x0, x1) - 3, Y(538 + k * 12))],
                   STEEL, 60, 0.7)
        # Landing pads, dashed: they are under the hull.
        p.dashed((cx + sgn * 60, Y(330)), (cx + sgn * 60, Y(372)), STEEL, 70, 0.9, 4, 3)
        p.dashed((cx + sgn * 76, Y(640)), (cx + sgn * 76, Y(676)), STEEL, 70, 0.9, 4, 3)
    # Sensor dish, off the centreline.
    p.circle((cx - 56, Y(400)), 13, STEEL, 110, 1.2, fill_alpha=20)
    p.circle((cx - 56, Y(400)), 4, STEEL, 120, 1.0)
    p.line([(cx - 56, Y(400)), (cx - 48, Y(388))], STEEL, 110, 1)
    # Ventral boarding ramp, dashed.
    p.poly([(cx - 22, Y(560)), (cx + 22, Y(560)), (cx + 22, Y(640)), (cx - 22, Y(640))],
           STEEL, 0, 12)
    for a, b in (((cx - 22, Y(560)), (cx + 22, Y(560))), ((cx + 22, Y(560)), (cx + 22, Y(640))),
                 ((cx + 22, Y(640)), (cx - 22, Y(640))), ((cx - 22, Y(640)), (cx - 22, Y(560)))):
        p.dashed(a, b, STEEL, 80, 0.8, 5, 3)
    # Sublight drives with their exhaust.
    for k in range(3):
        x = cx - 60 + k * 60
        p.rect((x - 22, Y(716), x + 22, Y(744)), INK, 150, 36, 1.6)
        for j in range(6):
            p.fill((x - 16 + j, Y(746) + j * 3, x + 16 - j, Y(746) + j * 3 + 3), AMBER, 120 - j * 18)
    # The dorsal turret: ringed, twin barrels, and its callout.
    tc = (cx, Y(500))
    p.circle(tc, 22, INK, 220, 2.2, fill_alpha=55)
    p.circle(tc, 9, INK, 180, 1.2)
    p.circle(tc, 36, AMBER, 170, 1.4)
    for k in range(12):
        p.arc(tc, 44, k * 30, k * 30 + 14, AMBER, 110, 1)
    for dx in (-5, 5):
        p.line([(cx + dx, Y(488)), (cx + dx, Y(438))], INK, 210, 2.6)
    p.line([(cx + 26, Y(478)), (cx + 150, Y(400)), (cx + 216, Y(400))], AMBER, 160, 1.4)
    p.text((cx + 216, Y(394)), "DORSAL TURRET", 10, AMBER, 200, anchor="rs")
    # Callouts to the cockpit and drives.
    p.line([(cx - 28, Y(150)), (cx - 150, Y(150)), (cx - 200, Y(150))], STEEL, 110, 1.1)
    p.text((cx - 200, Y(143)), "COCKPIT", 10, INK, 170, anchor="ls")
    p.line([(cx + 60, Y(752)), (cx + 150, Y(790)), (cx + 216, Y(790))], STEEL, 110, 1.1)
    p.text((cx + 216, Y(784)), "SUBLIGHT DRIVE", 9, INK, 170, anchor="rs")

    # Dimension lines.
    y_top, y_bot = Y(96), Y(744)
    p.line([(40, y_top), (40, y_bot)], STEEL, 80, 1)
    for y in (y_top, y_bot):
        p.line([(32, y), (48, y)], STEEL, 100, 1.2)
        p.line([(48, y), (cx - 40, y)], STEEL, 25, 0.6)
    p.text((48, (y_top + y_bot) / 2), "HULL", 9, STEEL, 150)
    p.text((48, (y_top + y_bot) / 2 + 13), "26M", 9, INK, 170)
    yb = Y(800)
    p.line([(cx - 134, yb), (cx + 134, yb)], STEEL, 80, 1)
    for x in (cx - 134, cx + 134):
        p.line([(x, yb - 8), (x, yb + 8)], STEEL, 100, 1.2)
    p.text((cx, yb - 5), "BEAM 19M", 9, STEEL, 160, anchor="ms")

    # ---- Side elevation.
    ey = 720
    side = [(cx - 150, ey + 16), (cx - 130, ey - 2), (cx - 40, ey - 12), (cx + 40, ey - 12),
            (cx + 118, ey - 4), (cx + 150, ey + 6), (cx + 150, ey + 24), (cx - 150, ey + 30)]
    p.poly(side, INK, 170, 24, 1.8)
    p.poly([(cx + 118, ey - 4), (cx + 140, ey - 2), (cx + 150, ey + 6)], INK, 150, 50, 1)
    p.poly([(cx - 20, ey - 12), (cx - 14, ey - 22), (cx + 14, ey - 22), (cx + 20, ey - 12)],
           AMBER, 170, 50, 1.2)
    p.line([(cx + 10, ey - 18), (cx + 42, ey - 20)], INK, 190, 1.8)
    for x in (cx - 100, cx - 10, cx + 90):
        p.line([(x, ey + 30), (x, ey + 44)], STEEL, 110, 1.4)
        p.line([(x - 8, ey + 44), (x + 8, ey + 44)], STEEL, 110, 1.4)
    p.line([(cx - 190, ey + 44), (cx + 190, ey + 44)], STEEL, 40, 0.8)
    for k in range(4):
        p.fill((cx - 164 - k * 6, ey + 8 + k, cx - 152 - k * 6, ey + 22 - k), AMBER, 100 - k * 20)

    # ---- Title block.
    tb = (60, 800, 452, 960)
    p.rect(tb, STEEL, 90, 14, 1.2)
    p.line([(60, 836), (452, 836)], STEEL, 70, 0.9)
    p.line([(60, 900), (452, 900)], STEEL, 70, 0.9)
    p.line([(300, 836), (300, 960)], STEEL, 70, 0.9)
    p.text((74, 826), "REPUBLIC REGISTRY", 12, INK, 200)
    p.circle((436, 818), 4, AMBER, 0, fill_alpha=180)
    p.text((74, 862), "CLASS", 9, STEEL, 140)
    p.text((74, 886), "LIGHT FREIGHTER", 10, INK, 180)
    p.text((314, 862), "CREW", 9, STEEL, 140)
    p.text((314, 886), "2", 10, INK, 180)
    p.text((74, 926), "ARMAMENT", 9, STEEL, 140)
    p.text((74, 950), "DORSAL TURRET", 10, INK, 180)
    p.text((314, 926), "PLATE", 9, STEEL, 140)
    p.text((314, 950), "2 OF 4", 10, INK, 180)
    return p.finish()


def backdrop_outlines():
    """backdrop() as outlines, 1024x512: the vertical gradient, the centre glow and the
    vignette. The glow adds to the base, which painting over cannot; it is a colour over the
    base at half its strength, chosen so the sum matches where the glow is (the base there
    is about 7, 15, 30). The vignette darkens by a factor, which black over it does exactly.
    No noise: drawn at the size it is shown, nothing is stretched into bands."""
    import build_controller_glyph_vectors as vectors
    import controller_drawn_art as drawn
    import numpy as np
    w, h = 1024, 512
    span = 1638.4
    whole = [[(0, 0), (w, 0), (w, h), (0, h)]]
    down = ("linear", np.array([[0.0, span / h, -span / 2]]),
            [(0.0, (11, 22, 42, 255)), (1.0, (3, 7, 17, 255))])
    glow = [(i / 8, (7, 103, 187, int((1 - i / 8) ** 1.8 * 0.5 * 255))) for i in range(9)]
    vignette = [(0.0, (0, 0, 0, 0)), (0.45, (0, 0, 0, 0)), (1.0, (0, 0, 0, round(0.45 * 0.55 * 255)))]
    items = [vectors.Item(whole, "nonzero", down),
             vectors.Item(whole, "nonzero", drawn._radial((0.5 * w, 0.46 * h), (0.55 * w, 0.62 * h), glow)),
             vectors.Item(whole, "nonzero", drawn._radial((0.5 * w, 0.5 * h), (0.72 * w, 0.78 * h), vignette))]
    return vectors.encode(items, (0, 0, w, h))


def hairline_outlines():
    """hairline() as outlines, 1024x32: two rows at full strength, one either side at 0.35,
    fading to both ends as (1 - |u - 0.5| / 0.5) ^ 0.8 of 150."""
    import build_controller_glyph_vectors as vectors
    import numpy as np
    w, h = 1024, 32
    span = 1638.4
    items = []
    for (y0, y1), f in (((15, 17), 1.0), ((14, 15), 0.35), ((17, 18), 0.35)):
        # 13 stops, one in the middle: the drawer takes at most 16 (kmrp_glyph_read).
        stops = [(i / 12, INK + (int((1 - abs(i / 12 - 0.5) / 0.5) ** 0.8 * 150 * f),)) for i in range(13)]
        paint = ("linear", np.array([[span / w, 0.0, -span / 2]]), stops)
        items.append(vectors.Item([[(0, y0), (w, y0), (w, y1), (0, y1)]], "nonzero", paint))
    return vectors.encode(items, (0, 0, w, h))


def outlines():
    """{resref: outlines} for every texture in TEXTURES, for the controller patch to draw
    at the size each is shown."""
    art = {"kmrlytbg": backdrop_outlines(), "kmrlythair": hairline_outlines(),
           "kmrlytrd0": readout(0, OutlinePen), "kmrlytrd1": readout(1, OutlinePen),
           "kmrlytgun": _dim(gunnery_station(OutlinePen), 0.8),
           "kmrlytship": _dim(freighter(OutlinePen), 0.8)}
    for i in range(4):
        art[f"kmrlytcn{i}"] = corner(i, OutlinePen)
    assert set(art) == set(TEXTURES)
    return art


def _dim(image, factor):
    """Scale an image's alpha: the illustrations sit back behind the diagram. Outlines
    (OutlinePen) have every paint's alpha scaled the same way."""
    if isinstance(image, dict):
        for item in image["items"]:
            item["paint"]["solid"][3] = round(item["paint"]["solid"][3] * factor)
        return image
    image.putalpha(image.getchannel("A").point(lambda a: round(a * factor)))
    return image


def build_all():
    """{resref: image} for every texture in TEXTURES."""
    art = {"kmrlytbg": backdrop(), "kmrlythair": hairline(),
           "kmrlytrd0": readout(0), "kmrlytrd1": readout(1),
           "kmrlytgun": _dim(gunnery_station(), 0.8),
           "kmrlytship": _dim(freighter(), 0.8)}
    for i in range(4):
        art[f"kmrlytcn{i}"] = corner(i)
    assert set(art) == set(TEXTURES)
    return art
