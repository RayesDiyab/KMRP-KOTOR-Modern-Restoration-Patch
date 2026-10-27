#!/usr/bin/env python3
"""Makes assets/controller-glyphs/glyphs.json: every controller picture KMRP uses, as
outlines and paints (issue 68). tools/controller_glyphs.py explains the format and draws it.

A maintainer's tool, run when a picture changes; the build only reads its output. Sources:

  * Xelu's vector source, `Vector Source.fla` in third_party/Included/Xelu_Free_
    Controller&Key_Prompts (CC0; kept out of git with the rest of the pack's extras). An
    XFL document: one layer per controller, one frame per button, edges in twips with the
    fills on either side of each edge, quadratic curves, solid and gradient fills and
    strokes (round caps and joins, Flash's default) and static text. FRAMES below says
    which frame each picture is, checked by eye against the PNGs KMRP showed before.
  * The Steam Deck's letters are text in Raleway ExtraBold (SIL OFL 1.1; the wght 800
    instance of Google Fonts' variable font, in third_party/Fonts/Raleway), turned into
    outlines here. Its shoulder digits are Cocogoose Pro, a commercial face KMRP must not
    use, so they are the PS5's own "1" and "2" outlines from the same file, turned and
    placed where the Deck picture has its digit (DECK_DIGITS, measured from Xelu's 256 px
    export).
  * Eight pictures are not in the vector file, or are drawn differently there from the
    PNGs KMRP shows (FITTED): each is split into its flat colours and every colour's edge
    measured and redrawn as lines and cubic arcs with KMRP's own font tools
    (fonts/tools/measure.py, redraw2.py), within 0.5 to 1.6 of 255 of the PNG.
  * The swap-tabs phrase is the family's X-position button from the vector file, where
    the old picture had it, and the yellow arrows redrawn from the 2000 px picture.

Faces: the letter or symbol is moved so its outline's box is centred on the disc (the
maintainer's rule: letters centred), and the picture's box is the disc's with 4% around
it, the room the PNGs had.

    python tools/build_controller_glyph_vectors.py [--fla PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "fonts" / "tools"))
import build_controller_prompt_textures as prompts  # noqa: E402
import measure  # noqa: E402
import redraw2  # noqa: E402

PACK = prompts.GLYPH_PACK
FLA = PACK / "Vector Source.fla"
RALEWAY = ROOT / "third_party" / "Fonts" / "Raleway" / "Raleway-ExtraBold.ttf"
OUT = ROOT / "assets" / "controller-glyphs" / "glyphs.json"
NS = "{http://ns.adobe.com/xfl/2008/}"
TOLERANCE = 0.01          # source pixels a flattened curve may stray from the curve
UNITS = 65536             # a glyph's larger side, in its own units
FACE_ROOM = 0.96          # a face button's disc, of its picture's box

LAYERS = {"xbox": "Xbox 360", "playstation": "Playstation 5", "switch": "Nintendo Switch",
          "steamdeck": "Steam Deck"}
FRAMES = {  # glyph -> frame of the family's layer, or (layer, frame)
    "xbox": {"A": 0, "B": 1, "X": 3, "Y": 2, "LT": 7, "RT": 6, "START": 10, "BACK": 11,
             "DPAD_LEFT": 19, "DPAD_RIGHT": 17, "DPAD_UP": 20, "DPAD_DOWN": 18, "L3": 14,
             "R3": ("Xbox Series", 8), "LSTICK": 12, "RSTICK": 13, "DPAD": 16},
    "playstation": {"A": 4, "B": 1, "X": 3, "Y": 2, "LT": 8, "RT": 7, "START": 15,
                    "BACK": 14, "DPAD_LEFT": 21, "DPAD_RIGHT": 19, "DPAD_UP": 20,
                    "DPAD_DOWN": 22, "L3": 12, "R3": 13, "LSTICK": 10, "RSTICK": 11,
                    "DPAD": 18},
    # by position: KMRP's A is the bottom button, which a Switch labels B
    "switch": {"A": 1, "B": 0, "X": 2, "Y": 3, "LT": 22, "RT": 21, "START": 13, "BACK": 12,
               "DPAD_LEFT": 18, "DPAD_RIGHT": 16, "DPAD_UP": 15, "DPAD_DOWN": 17,
               # the pack's Switch stick clicks are the PS5's drawing
               "L3": ("Playstation 5", 12), "R3": ("Playstation 5", 13), "LSTICK": 8,
               "RSTICK": 9, "DPAD": 14},
    "steamdeck": {"A": 5, "B": 6, "X": 8, "Y": 7, "LB": 23, "RB": 22, "LT": 25, "RT": 24,
                  "START": 17, "BACK": 16, "DPAD_LEFT": 3, "DPAD_RIGHT": 1, "DPAD_UP": 2,
                  "DPAD_DOWN": 4, "L3": 11, "R3": 12, "LSTICK": 9, "RSTICK": 10, "DPAD": 0},
}
SAME = {"switch/RT_NOTICE": "switch/RT", "steamdeck/RT_NOTICE": "steamdeck/RT"}
FITTED = {  # glyph -> the PNG, its colours from the bottom layer up
    "xbox/RT_NOTICE": ("Xbox/360_RT_ALT.png", [(241, 245, 248), (233, 238, 242), (222, 226, 229),
                                               (215, 219, 223), (248, 250, 251), (160, 163, 165)]),
    "playstation/RT_NOTICE": ("PS5/PS5_R2_Light.png", [(241, 245, 248), (233, 238, 242), (23, 33, 38)]),
    "switch/LB": ("Switch/Switch_LB.png", [(27, 27, 27), (79, 79, 79), (98, 98, 98)]),
    "switch/RB": ("Switch/Switch_RB.png", [(27, 27, 27), (79, 79, 79), (98, 98, 98)]),
    "xbox/LB": ("Xbox/360_LB.png", [(64, 64, 64), (215, 215, 215), (245, 245, 245),
                                    (255, 255, 255), (153, 153, 153)]),
    "xbox/RB": ("Xbox/360_RB.png", [(64, 64, 64), (215, 215, 215), (245, 245, 245),
                                    (255, 255, 255), (153, 153, 153)]),
    "playstation/LB": ("PS5/PS5_L1.png", [(27, 27, 27), (49, 49, 49), (79, 79, 79), (98, 98, 98),
                                          (143, 143, 143)]),
    "playstation/RB": ("PS5/PS5_R1.png", [(27, 27, 27), (49, 49, 49), (79, 79, 79), (98, 98, 98),
                                          (143, 143, 143)]),
}
# The Deck shoulders' digit: the PS5 outline's area centroid goes to (cx, cy) of the Deck
# picture, turned by `angle` degrees (clockwise on screen), measured from Xelu's 256 px
# export. L1's tilt is mirrored from R1's.
DECK_DIGITS = {
    "RT": ("2", 66.14833429063756, 32.47393739230327, 0.0),
    "LT": ("2", 50.14860014357502, 32.473510409188805, 0.0),
    "RB": ("1", 72.68718973241313, 61.53741373047585, 19.72029099508103),
    "LB": ("1", 42.79326287978863, 55.725411312597565, -20.253095894913518),
}
DIGIT_COLOUR = (215, 215, 215, 255)
SWAP_SOURCE = "Xbox/Swap_tabs_360.png.png"
SWAP_BOX = (325, 746, 1743, 1384)        # the picture's ink, in the 2000 px source
SWAP_BUTTON = (644.0, 1064.0, 638.0)     # the X button's centre and disc, the same
SWAP_YELLOW = (255, 255, 0, 255)


# ---------------------------------------------------------------- the vector file

def read_fla(path: Path) -> ET.Element:
    """DOMDocument.xml from the XFL archive, read by its local headers (Python's zipfile
    rejects the archive's central directory)."""
    data = path.read_bytes()
    at = 0
    while True:
        at = data.find(b"PK\x03\x04", at)
        if at < 0:
            raise SystemExit(f"{path}: no DOMDocument.xml")
        flags, method = struct.unpack_from("<HH", data, at + 6)
        size, _, name_len, extra_len = struct.unpack_from("<IIHH", data, at + 18)
        name = data[at + 30:at + 30 + name_len].decode("utf-8", "replace")
        start = at + 30 + name_len + extra_len
        if name == "DOMDocument.xml":
            if method == 8:
                body = zlib.decompressobj(-15).decompress(data[start:])
            else:
                body = data[start:start + size]
            return ET.fromstring(body)
        at = start


def num(tok: str) -> float:
    if tok.startswith("#"):
        whole, _, frac = tok[1:].partition(".")
        v = int(whole, 16)
        if v >= 0x800000:
            v -= 0x1000000
        return (v + (int(frac, 16) / (16 ** len(frac)) if frac else 0)) / 20.0
    return float(tok) / 20.0


def quad_steps(p0, c, p1) -> int:
    dd = math.hypot(p0[0] - 2 * c[0] + p1[0], p0[1] - 2 * c[1] + p1[1])
    return max(1, math.ceil(math.sqrt(dd / (8 * TOLERANCE))))


def parse_edges(s: str) -> list[list[tuple[float, float]]]:
    """An XFL edge string as polylines in pixels, curves flattened within TOLERANCE."""
    paths = []
    toks = re.findall(r"[!|\[\]]|S\d+|#[0-9A-Fa-f.]+|-?\d+(?:\.\d+)?", s)
    i, cur, path = 0, None, None
    while i < len(toks):
        t = toks[i]
        if t == "!":
            cur = (num(toks[i + 1]), num(toks[i + 2]))
            path = [cur]
            paths.append(path)
            i += 3
        elif t == "|":
            cur = (num(toks[i + 1]), num(toks[i + 2]))
            path.append(cur)
            i += 3
        elif t in "[]":
            c = (num(toks[i + 1]), num(toks[i + 2]))
            p = (num(toks[i + 3]), num(toks[i + 4]))
            n = quad_steps(cur, c, p)
            for k in range(1, n + 1):
                u = k / n
                path.append(((1 - u) ** 2 * cur[0] + 2 * (1 - u) * u * c[0] + u * u * p[0],
                             (1 - u) ** 2 * cur[1] + 2 * (1 - u) * u * c[1] + u * u * p[1]))
            cur = p
            i += 5
        else:
            i += 1
    return paths


def rgba(colour: str, alpha: float) -> tuple[int, int, int, int]:
    return (int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16), round(alpha * 255))


def paint_of(style: ET.Element):
    """("solid", rgba) or (kind, M, stops): M maps a point to the gradient's own box, where
    Flash draws it from -819.2 to 819.2 (linear along x, radial from the centre)."""
    g = next((c for c in style.iter() if c.tag.endswith("Gradient")), None)
    if g is None:
        sc = style.find(f".//{NS}SolidColor")
        if sc is None:
            return "solid", (255, 0, 255, 255)
        return "solid", rgba(sc.get("color", "#000000"), float(sc.get("alpha", "1")))
    m = g.find(f"{NS}matrix/{NS}Matrix")
    a, b, c, d, tx, ty = [float(m.get(k, dv)) if m is not None else dv
                          for k, dv in (("a", 1), ("b", 0), ("c", 0), ("d", 1), ("tx", 0), ("ty", 0))]
    det = a * d - b * c
    inv = np.array([[d / det, -c / det, (c * ty - d * tx) / det],
                    [-b / det, a / det, (b * tx - a * ty) / det]])
    stops = [(float(e.get("ratio", 0)), rgba(e.get("color", "#000000"), float(e.get("alpha", 1))))
             for e in g.iter(f"{NS}GradientEntry")]
    return ("radial" if "Radial" in g.tag else "linear"), inv, stops


class Item:
    """Polygons (float, in some frame), a fill rule and a paint."""

    def __init__(self, polys, rule, paint):
        self.polys = [np.asarray(p, np.float64) for p in polys if len(p) >= 3]
        self.rule = rule
        self.paint = paint

    def moved(self, scale: float, offset) -> "Item":
        """The item under p -> scale * p + offset."""
        off = np.asarray(offset, np.float64)
        paint = self.paint
        if paint[0] != "solid":
            kind, m, stops = paint
            lin = m[:, :2] / scale
            paint = (kind, np.hstack([lin, (m[:, 2] - lin @ off)[:, None]]), stops)
        return Item([p * scale + off for p in self.polys], self.rule, paint)

    def bbox(self):
        pts = np.vstack(self.polys)
        return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()


def loops_for(edges, style):
    """The closed loops of one fill style: edges with it on the right as they run, those
    with it on the left reversed, chained end to start."""
    pieces = []
    for f0, f1, _, paths in edges:
        for seg in paths:
            if len(seg) < 2:
                continue
            if f1 == style:
                pieces.append(list(seg))
            if f0 == style:
                pieces.append(list(reversed(seg)))
    key = lambda p: (round(p[0], 2), round(p[1], 2))  # noqa: E731
    loops = []
    while pieces:
        loop = pieces.pop()
        for _ in range(100000):
            if key(loop[0]) == key(loop[-1]) and len(loop) > 2:
                break
            nxt = next((k for k, p in enumerate(pieces) if key(p[0]) == key(loop[-1])), None)
            if nxt is None:
                break
            loop += pieces.pop(nxt)[1:]
        loops.append(loop)
    return loops


def stroke_polys(paths, weight):
    """The outline of polylines stroked `weight` wide, round caps and joins."""
    from shapely.geometry import MultiLineString, Polygon, MultiPolygon
    lines = [p for p in paths if len(p) >= 2]
    if not lines:
        return []
    radius = weight / 2
    shape = MultiLineString(lines).buffer(radius, quad_segs=max(8, math.ceil(math.pi / 2 / math.acos(max(0.0, 1 - TOLERANCE / radius)))))
    polys = []
    for part in (shape.geoms if isinstance(shape, MultiPolygon) else [shape]):
        if isinstance(part, Polygon) and not part.is_empty:
            polys.append(list(part.exterior.coords)[:-1])
            polys.extend(list(r.coords)[:-1] for r in part.interiors)
    return polys


class Frame:
    def __init__(self, root, layer: str, index: int):
        self.layer, self.index = layer, index
        for el in root.iter(f"{NS}DOMLayer"):
            if el.get("name") == layer:
                self.frame = list(el.iter(f"{NS}DOMFrame"))[index]
                break
        else:
            raise SystemExit(f"no layer {layer!r} in the vector file")
        shape = self.frame.find(f"{NS}elements/{NS}DOMShape")
        self.fills = {int(f.get("index")): paint_of(f) for f in shape.iter(f"{NS}FillStyle")}
        self.strokes = {}
        for s in shape.iter(f"{NS}StrokeStyle"):
            solid = s.find(f"{NS}SolidStroke")
            self.strokes[int(s.get("index"))] = (float(solid.get("weight", "1")) if solid is not None else 1.0,
                                                 paint_of(s))
        self.edges = [(int(e.get("fillStyle0", 0)), int(e.get("fillStyle1", 0)), int(e.get("strokeStyle", 0)),
                       parse_edges(e.get("edges"))) for e in shape.iter(f"{NS}Edge") if e.get("edges")]

    def ink_box(self):
        pts = [p for _, _, _, paths in self.edges for seg in paths for p in seg]
        pad = max([w for w, _ in self.strokes.values()] or [0]) / 2
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad

    def edge_box(self):
        pts = [p for _, _, _, paths in self.edges for seg in paths for p in seg]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def fill_items(self):
        """(style, Item) per fill, in style order."""
        out = []
        for style in sorted(self.fills):
            loops = loops_for(self.edges, style)
            if loops:
                out.append((style, Item(loops, "nonzero", self.fills[style])))
        return out

    def stroke_items(self):
        out = []
        for style in sorted(self.strokes):
            weight, paint = self.strokes[style]
            paths = [seg for _, _, st, segs in self.edges if st == style for seg in segs]
            polys = stroke_polys(paths, weight)
            if polys:
                out.append(Item(polys, "evenodd", paint))
        return out

    def texts(self):
        """(characters, size in px, colour, matrix, left, width, face) per static text."""
        out = []
        for t in self.frame.iter(f"{NS}DOMStaticText"):
            at = t.find(f".//{NS}DOMTextAttrs").attrib
            m = t.find(f"{NS}matrix/{NS}Matrix")
            mat = [float(m.get(k, dv)) if m is not None else dv
                   for k, dv in (("a", 1), ("b", 0), ("c", 0), ("d", 1), ("tx", 0), ("ty", 0))]
            out.append((t.find(f".//{NS}characters").text or "", float(at.get("size", 12)),
                        rgba(at.get("fillColor", "#000000"), float(at.get("alpha", 1))), mat,
                        float(t.get("left", 0)), float(t.get("width", 0)), at.get("face", "")))
        return out


# ---------------------------------------------------------------- Raleway

_font = None


def letter_polys(ch: str, size: float):
    """The character's outline at `size` px (em), y down, origin on the baseline at the
    left of its advance; and its advance and ascender in px."""
    global _font
    from fontTools.pens.basePen import BasePen
    from fontTools.ttLib import TTFont
    if _font is None:
        _font = TTFont(RALEWAY)
    font = _font
    k = size / font["head"].unitsPerEm
    name = font.getBestCmap()[ord(ch)]
    glyph_set = font.getGlyphSet()

    class Pen(BasePen):
        def __init__(self):
            super().__init__(glyph_set)
            self.polys, self.cur = [], None

        def _moveTo(self, p):
            self.polys.append([p])

        def _lineTo(self, p):
            self.polys[-1].append(p)

        def _qCurveToOne(self, c, p):
            p0 = self.polys[-1][-1]
            n = quad_steps((p0[0] * k, p0[1] * k), (c[0] * k, c[1] * k), (p[0] * k, p[1] * k))
            for i in range(1, n + 1):
                u = i / n
                self.polys[-1].append(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * c[0] + u * u * p[0],
                                       (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * c[1] + u * u * p[1]))

        def _curveToOne(self, c1, c2, p):
            p0 = self.polys[-1][-1]
            n = 32
            for i in range(1, n + 1):
                u = i / n
                v = 1 - u
                self.polys[-1].append((v ** 3 * p0[0] + 3 * v * v * u * c1[0] + 3 * v * u * u * c2[0] + u ** 3 * p[0],
                                       v ** 3 * p0[1] + 3 * v * v * u * c1[1] + 3 * v * u * u * c2[1] + u ** 3 * p[1]))

        def _closePath(self):
            pass

    pen = Pen()
    glyph_set[name].draw(pen)
    polys = [[(x * k, -y * k) for x, y in poly] for poly in pen.polys]
    return polys, glyph_set[name].width * k, font["hhea"].ascent * k


def text_item(ch, size, colour, anchor, angle, mode):
    """A Raleway text as an item. mode "ma": `anchor` is the middle of its advance at the
    ascender line; "mm": the middle of its advance and of its ascender and baseline (PIL's
    anchors, which the approved pictures used), turned by `angle` degrees about it."""
    polys, advance, ascent = letter_polys(ch, size)
    dy = ascent if mode == "ma" else ascent / 2
    a = math.radians(angle)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    out = [(np.asarray(p) - [advance / 2, -dy]) @ rot.T + anchor for p in polys]
    return Item(out, "nonzero", ("solid", colour))


# ---------------------------------------------------------------- pictures

def face(root, family: str, glyph: str, layer=None, index=None):
    """A face button: (items, box). The mark (everything but the disc) moved so its box is
    centred on the disc's; the box the disc's square with FACE_ROOM around it."""
    fr = Frame(root, layer or LAYERS[family], FRAMES[family][glyph] if index is None else index)
    x0, y0, x1, y1 = fr.edge_box()
    side = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # The disc is its rings, every one at least 62 of the 81 px across; a letter is at most
    # 34. (A limit of 0.85 once counted the inner rings as part of the letter, so the box
    # centred was the ring's and the letter kept the source's own offset: 2 px right on the
    # Xbox B, the Deck's letters low.) The PS5's symbols are strokes and stay as Xelu drew
    # them: they are centred already, the triangle raised by its optical weight.
    disc, mark = [], []
    for _, item in fr.fill_items():
        bx0, _, bx1, _ = item.bbox()
        if bx1 - bx0 > 0.6 * (x1 - x0):
            # A ring under the letter has the letter cut out of it; the letter moves, so
            # the cut-out goes (the letter is opaque and drawn over it, so where it lies
            # nothing changes). Left in, it showed the ring below as a ghost letter.
            whole = [p for p in item.polys if np.ptp(p[:, 0]) > 0.6 * (x1 - x0)]
            disc.append(Item(whole, item.rule, item.paint))
        else:
            mark.append(item)
    strokes = fr.stroke_items()
    for ch, size, colour, mat, *_rest in fr.texts():
        face_name = _rest[-1]
        if not face_name.startswith("Raleway"):
            print(f"  {family}/{glyph}: text {ch!r} in {face_name} left out", file=sys.stderr)
            continue
        mark.append(text_item(ch, size * mat[0], colour, (cx, cy), 0.0, "mm"))
    if mark:
        boxes = np.array([m.bbox() for m in mark])
        mx = (boxes[:, 0].min() + boxes[:, 2].max()) / 2
        my = (boxes[:, 1].min() + boxes[:, 3].max()) / 2
        mark = [m.moved(1.0, (cx - mx, cy - my)) for m in mark]
    half = side / FACE_ROOM / 2
    return disc + strokes + mark,(cx - half, cy - half, cx + half, cy + half), side


def plain(root, family: str, glyph: str, layer=None, index=None):
    """Any other picture from the vector file: fills, strokes, Raleway text; the box its
    ink's."""
    spec = FRAMES[family][glyph] if index is None else index
    if isinstance(spec, tuple):
        layer, spec = spec
    fr = Frame(root, layer or LAYERS[family], spec)
    items = [item for _, item in fr.fill_items()] + fr.stroke_items()
    for ch, size, colour, mat, left, width, face_name in fr.texts():
        if not face_name.startswith("Raleway"):
            continue          # the Deck's digits (Cocogoose): deck_digit
        a, b, c, d, tx, ty = mat
        gx, gy = left + width / 2, 2.0           # the middle of its box, under Flash's 2 px gutter
        anchor = np.array([a * gx + c * gy + tx, b * gx + d * gy + ty])
        scale = math.hypot(a, b)
        items.append(text_item(ch, size * scale, colour, anchor, math.degrees(math.atan2(b, a)), "ma"))
    return items, fr.ink_box()


def ps5_digit(root, ch: str):
    """The PS5 label's digit outline and its area centroid: "1" from L1, "2" from L2."""
    fr = Frame(root, "Playstation 5", {"1": 5, "2": 8}[ch])
    loops = loops_for(fr.edges, 3)
    pts = np.array(max(loops, key=lambda lp: min(p[0] for p in lp)))
    x, y = pts[:, 0], pts[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    cr = x * yn - xn * y
    area = cr.sum() / 2
    return pts, np.array([((x + xn) * cr).sum() / (6 * area), ((y + yn) * cr).sum() / (6 * area)])


def coverages(path: Path, layers):
    """Per colour layer (bottom first), the share of each pixel covered by it or any layer
    above: each pixel read as one colour, or a mix of two where that fits clearly better."""
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
    rgb, alpha = a[..., :3], a[..., 3] / 255.0
    cols = np.array(layers, np.float64)
    n = len(cols)
    h, w = alpha.shape
    frac = np.zeros((n, h, w))
    best = np.full((h, w), np.inf)
    pairs = [(i, i) for i in range(n)] + [(i, j) for i in range(n) for j in range(i + 1, n)]
    for i, j in pairs:
        d = cols[i] - cols[j]
        dd = (d * d).sum()
        t = np.clip(((rgb - cols[j]) * d).sum(-1) / dd, 0, 1) if dd > 0 else np.ones((h, w))
        err = ((rgb - (t[..., None] * cols[i] + (1 - t[..., None]) * cols[j])) ** 2).sum(-1)
        pick = err < (best if i == j else best - 50.0)
        best = np.where(pick, err, best)
        for k in range(n):
            if i == j:
                frac[k] = np.where(pick, 1.0 if k == i else 0.0, frac[k])
            else:
                frac[k] = np.where(pick, t if k == i else (1 - t) if k == j else 0.0, frac[k])
    cum = np.zeros_like(frac)
    for k in range(n):
        cum[k] = alpha * frac[k:].sum(0)
    return cum


def flatten(start, parts):
    pts, cur = [start], start
    for p in parts:
        if p[0] == "line":
            pts.append(p[1])
        else:
            end, c1, c2 = p[1], p[2], p[3]
            m = max(math.hypot(cur[0] - 2 * c1[0] + c2[0], cur[1] - 2 * c1[1] + c2[1]),
                    math.hypot(c1[0] - 2 * c2[0] + end[0], c1[1] - 2 * c2[1] + end[1]))
            n = max(1, math.ceil(math.sqrt(0.75 * m / TOLERANCE)))
            for k in range(1, n + 1):
                u = k / n
                v = 1 - u
                pts.append((v ** 3 * cur[0] + 3 * v * v * u * c1[0] + 3 * v * u * u * c2[0] + u ** 3 * end[0],
                            v ** 3 * cur[1] + 3 * v * v * u * c1[1] + 3 * v * u * u * c2[1] + u ** 3 * end[1]))
        cur = p[1]
    return pts


def fit_layer(cov, height):
    """A coverage layer's edges redrawn as lines and cubic arcs, flattened, in the
    picture's pixels (y down)."""
    out = []
    for P in measure.outlines(cov, height, spacing=0.5):
        if len(P) < 8:
            continue
        conv = lambda p: (p[0] / 10.0, height - p[1] / 10.0)  # noqa: E731
        try:
            segs = redraw2.square_lines(redraw2.redraw_contour(P))
        except (np.linalg.LinAlgError, ValueError, IndexError):
            out.append([conv(q) for q in P])     # too small or ragged for arcs: as measured
            continue
        if not segs:
            continue
        parts = [("line", conv(sg[1])) if sg[0] == "line" else ("curve", conv(sg[1]), conv(sg[2]), conv(sg[3]))
                 for sg in segs]
        out.append(flatten(conv(segs[-1][1]), parts))
    return out


def fitted(name: str):
    path, layers = FITTED[name]
    cov = coverages(PACK / path, layers)
    items = [Item(fit_layer(cov[k], cov.shape[1]), "evenodd", ("solid", tuple(layers[k]) + (255,)))
             for k in range(len(layers))]
    boxes = np.array([it.bbox() for it in items if it.polys])
    return items, (boxes[:, 0].min(), boxes[:, 1].min(), boxes[:, 2].max(), boxes[:, 3].max())


_arrows = None


def swap(root, family: str):
    global _arrows
    if _arrows is None:
        a = np.asarray(Image.open(PACK / SWAP_SOURCE).convert("RGBA")).astype(np.float64)
        yellow = np.clip((a[..., :2].mean(-1) - a[..., 2]) / 255.0, 0, 1) * (a[..., 3] / 255)
        yellow[:, :1000] = 0
        _arrows = Item(fit_layer(yellow, a.shape[0]), "evenodd", ("solid", SWAP_YELLOW))
    items, _box, side = face(root, family, "X")
    x0, y0, x1, y1 = Frame(root, LAYERS[family], FRAMES[family]["X"]).edge_box()
    cx, cy, disc = SWAP_BUTTON
    s = disc / side
    button = [it.moved(s, (cx - (x0 + x1) / 2 * s, cy - (y0 + y1) / 2 * s)) for it in items]
    return [_arrows] + button, SWAP_BOX


def deck_shoulder(root, glyph: str):
    items, box = plain(root, "steamdeck", glyph if glyph != "RT_NOTICE" else "RT")
    ch, cx, cy, angle = DECK_DIGITS[glyph if glyph != "RT_NOTICE" else "RT"]
    pts, cen = ps5_digit(root, ch)
    a = math.radians(angle)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    items.append(Item([(pts - cen) @ rot.T + [cx, cy]], "nonzero", ("solid", DIGIT_COLOUR)))
    return items, box


# ---------------------------------------------------------------- output

def encode(items, box) -> dict:
    """Items in a box as glyphs.json holds them: integer units, the larger side UNITS."""
    x0, y0, x1, y1 = box
    k = UNITS / max(x1 - x0, y1 - y0)
    W, H = round((x1 - x0) * k), round((y1 - y0) * k)
    out = []
    for it in items:
        if not it.polys:
            continue
        it = it.moved(k, (-x0 * k, -y0 * k))
        polys = []
        for p in it.polys:
            q = np.round(p).astype(np.int64)
            keep = np.any(q != np.roll(q, 1, axis=0), axis=1)
            q = q[keep]
            if len(q) >= 3:
                polys.append([int(v) for v in q.reshape(-1)])
        if not polys:
            continue
        paint = it.paint
        if paint[0] == "solid":
            enc = {"solid": list(paint[1])}
        else:
            kind, m, stops = paint
            span = 1638.4 if kind == "linear" else 819.2
            # t (1 = 65536) from glyph units, the coefficients scaled by 2^32
            if kind == "linear":
                coef = [m[0, 0] / span, m[0, 1] / span, m[0, 2] / span + 0.5]
            else:
                coef = [m[0, 0] / span, m[0, 1] / span, m[0, 2] / span,
                        m[1, 0] / span, m[1, 1] / span, m[1, 2] / span]
            enc = {kind: [round(v * 2 ** 32) for v in coef],
                   "stops": [[round(r * 65536)] + list(c) for r, c in stops]}
        out.append({"rule": it.rule, "paint": enc, "polygons": polys})
    return {"size": [W, H], "items": out}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fla", type=Path, default=FLA)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if not args.fla.is_file():
        raise SystemExit(f"{args.fla}: Xelu's vector source is needed (Vector Source.fla, CC0)")
    root = read_fla(args.fla)
    result = {}
    for family, (_folder, art) in prompts.GLYPH_FAMILIES.items():
        for glyph in art:
            name = f"{family}/{glyph}"
            if name in SAME:
                result[name] = {"same_as": SAME[name]}
                continue
            if glyph == "SWAP":
                items, box = swap(root, family)
            elif name in FITTED:
                items, box = fitted(name)
            elif glyph in ("A", "B", "X", "Y"):
                items, box, _ = face(root, family, glyph)
            elif family == "steamdeck" and glyph in DECK_DIGITS:
                items, box = deck_shoulder(root, glyph)
            else:
                items, box = plain(root, family, glyph)
            result[name] = encode(items, box)
            print(f"{name}: {len(result[name]['items'])} items", file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # one glyph per line, so a change to one picture is one line of the diff
    lines = [json.dumps(name) + ":" + json.dumps(g, separators=(",", ":")) for name, g in result.items()]
    text = ('{"version":1,"source":"tools/build_controller_glyph_vectors.py","glyphs":{\n'
            + ",\n".join(lines) + "\n}}\n")
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"{args.out}: {args.out.stat().st_size} bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
