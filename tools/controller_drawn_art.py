#!/usr/bin/env python3
"""The controller patch's drawn pictures as outlines, for drawing at the size they are shown.

The LT and RT arrows beside the in-game menu's tab strip (tools/build_tab_arrows.py) and the
remapping screen's three symbols (tools/build_controller_layout.py, _remap_marks) are drawn
with PIL at one size. The controller patch draws every picture at the size its control is
shown (2026-10-27, the maintainer: "everything needs to be run time drawn"), from outlines
in the format tools/controller_glyphs.py sets out. These are those pictures' outlines, from
the same numbers the PIL drawings use: the shapes as polygons, a stroke as its line
widened with round ends, the "?" from the font's own outline. A soft glow (a Gaussian blur
of a shape) is a stack of thin rings around the shape, each as opaque as the blur is at
its distance from the edge, 0.5 x erfc(d / (sigma x sqrt 2)) for a straight edge.

Each picture's box is its texture's square, in the texture's pixels; build_controller_assets
adds them to kmrp-glyphs.bin with the glyphs.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

GLOW_RINGS = 14            # rings in a glow, out to GLOW_REACH sigmas
GLOW_REACH = 3.5
GLOW_ARC = 8               # segments per quarter circle of a glow ring (a soft edge needs few)
SIMPLIFY = 0.02            # an outline kept within this many of the picture's pixels


def _encode(items, size):
    import build_controller_glyph_vectors as vectors
    return vectors.encode(items, (0, 0, size, size))


def _item(geometry, colour, alpha=255):
    """A shapely area as an even-odd item of one colour (holes are outlines too)."""
    import build_controller_glyph_vectors as vectors
    from shapely.geometry import MultiPolygon, Polygon
    polys = []
    geometry = geometry.simplify(SIMPLIFY, preserve_topology=True)
    for part in (geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]):
        if isinstance(part, Polygon) and not part.is_empty:
            polys.append(list(part.exterior.coords)[:-1])
            polys.extend(list(ring.coords)[:-1] for ring in part.interiors)
    return vectors.Item(polys, "evenodd", ("solid", tuple(colour) + (round(alpha),)))


def _glow(shape, sigma, colour, strength, rings=GLOW_RINGS):
    """Rings around `shape`, outside it, as opaque as its blur would be there."""
    items, step = [], GLOW_REACH * sigma / rings
    for k in range(rings):
        inner, outer = k * step, (k + 1) * step
        middle = (inner + outer) / 2
        alpha = 255 * strength * 0.5 * math.erfc(middle / (sigma * math.sqrt(2)))
        if alpha < 1:
            break
        ring = shape.buffer(outer, quad_segs=GLOW_ARC).difference(
            shape.buffer(inner, quad_segs=GLOW_ARC) if inner else shape)
        items.append(_item(ring, colour, alpha))
    # Inside the edge the blur is above one half; under an opaque shape it is not seen,
    # but a stroke's halo shows through the gaps between strokes.
    items.append(_item(shape, colour, 255 * strength * 0.5))
    return items


def tab_arrow(text: str, pointing_left: bool) -> dict:
    """build_tab_arrows.arrow's picture: the glow, the body, the frame, the letters' halo and
    the letters, from its constants."""
    import build_tab_arrows as arrows
    from shapely.geometry import MultiLineString, Polygon
    n = arrows.SIZE
    radius = n * arrows.CORNER
    back = n - n * arrows.EDGE - radius
    tip = back - n * 0.66
    half = n * (arrows.FLAT / 2) - radius
    points = [(tip, n / 2), (back, n / 2 - half), (back, n / 2 + half)]
    if not pointing_left:
        points = [(n - x, y) for x, y in points]
    outer = Polygon(points).buffer(radius, quad_segs=32)
    inner = outer.buffer(-n * 0.028, quad_segs=32)
    items = _glow(outer, n * 0.03, arrows.GLOW, arrows.GLOW_STRENGTH)[:-1]
    items.append(_item(inner, arrows.BODY_TOP, arrows.BODY_ALPHA))
    items.append(_item(outer.difference(inner), arrows.FRAME))
    height, width, gap, stroke = n * 0.20, n * 0.125, n * 0.055, n * 0.034
    total = len(text) * width + (len(text) - 1) * gap
    middle = n * (0.685 if pointing_left else 0.315)
    left, top = middle - total / 2, n / 2 - height / 2
    lines = []
    for index, letter in enumerate(text):
        x0 = left + index * (width + gap)
        for line in arrows.STROKES[letter]:
            lines.append([(x0 + x * width, top + y * height) for x, y in line])
    letters = MultiLineString(lines).buffer(stroke / 2, quad_segs=16)
    items += _glow(letters, n * 0.012, arrows.LETTER_GLOW, 1.0, rings=6)   # 1.5 px of halo
    items.append(_item(letters, arrows.LETTERS))
    return _encode(items, n)


def _font_outline(char: str, font_path: Path, size: float):
    """The character's outline as a shapely area, at `size` px, its ink box centred on (0, 0)."""
    from fontTools.pens.basePen import BasePen
    from fontTools.ttLib import TTFont
    from shapely.geometry import Polygon
    font = TTFont(font_path)
    glyph_set = font.getGlyphSet()
    k = size / font["head"].unitsPerEm

    class Pen(BasePen):
        def __init__(self):
            super().__init__(glyph_set)
            self.loops = []

        def _moveTo(self, p):
            self.loops.append([p])

        def _lineTo(self, p):
            self.loops[-1].append(p)

        def _qCurveToOne(self, c, p):
            p0 = self.loops[-1][-1]
            for i in range(1, 17):
                u = i / 16
                self.loops[-1].append(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * c[0] + u * u * p[0],
                                       (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * c[1] + u * u * p[1]))

        def _curveToOne(self, c1, c2, p):
            p0 = self.loops[-1][-1]
            for i in range(1, 25):
                u = i / 24
                v = 1 - u
                self.loops[-1].append((v ** 3 * p0[0] + 3 * v * v * u * c1[0] + 3 * v * u * u * c2[0] + u ** 3 * p[0],
                                       v ** 3 * p0[1] + 3 * v * v * u * c1[1] + 3 * v * u * u * c2[1] + u ** 3 * p[1]))

        def _closePath(self):
            pass

    pen = Pen()
    glyph_set[font.getBestCmap()[ord(char)]].draw(pen)
    area = None
    for loop in pen.loops:
        poly = Polygon([(x * k, -y * k) for x, y in loop]).buffer(0)
        area = poly if area is None else area.symmetric_difference(poly)
    x0, y0, x1, y1 = area.bounds
    from shapely.affinity import translate
    return translate(area, -(x0 + x1) / 2, -(y0 + y1) / 2)


def remap_marks() -> dict:
    """build_controller_layout._remap_marks's three pictures: name -> outlines."""
    import build_controller_layout as layout
    from shapely.affinity import scale, translate
    from shapely.geometry import Point, box
    size = 128
    navy = (3, 12, 28)
    marks = {}
    # The ring: PIL's ellipse over [6, 6, 121, 121], its 9 px outline inside that.
    centre = (size - 1) / 2
    disc = Point(centre, centre).buffer((size - 13) / 2 + 0.5, quad_segs=64)
    hole = Point(centre, centre).buffer((size - 13) / 2 + 0.5 - 9, quad_segs=64)
    question = translate(_font_outline("?", ROOT / "assets" / "fonts" / "KOTOR_UI_Open.ttf", 76), size / 2, size / 2)
    marks[layout.REMAP_ASK] = _encode([_item(disc, navy), _item(disc.difference(hole), layout.ORANGE),
                                       _item(question, layout.ORANGE)], size)
    # The padlock: the body, the shackle (the top half of an ellipse's 11 px band), its two
    # posts and the keyhole.
    grey = layout.LOCK_GREY
    body = box(30, 58, 98 + 1, 116 + 1).buffer(-10).buffer(10, quad_segs=16)
    ellipse_outer = scale(Point(0, 0).buffer(1, quad_segs=64), 24.5, 30.5).buffer(0)
    ellipse_inner = scale(Point(0, 0).buffer(1, quad_segs=64), 13.5, 19.5).buffer(0)
    band = translate(ellipse_outer.difference(ellipse_inner), 64.5, 48.5)
    shackle = band.intersection(box(0, 0, size, 48.5))
    posts = box(45 - 5.5, 48, 45 + 5.5, 62).union(box(83 - 5.5, 48, 83 + 5.5, 62))
    keyhole = Point(64.5, 82.5).buffer(6.5, quad_segs=32)
    marks[layout.REMAP_LOCK] = _encode([_item(body.union(shackle).union(posts), grey), _item(keyhole, navy)], size)
    # The dot: PIL's ellipse over [24, 24, 103, 103].
    marks[layout.REMAP_DOT] = _encode([_item(Point(64, 64).buffer(40, quad_segs=64), layout.DOT_YELLOW)], size)
    return marks
