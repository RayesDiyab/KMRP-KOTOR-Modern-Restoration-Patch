#!/usr/bin/env python3
"""Recreate KOTOR's UI typeface as a scalable TrueType font.

The menus ship as small bitmap atlases -- `dialogfont16x16` rasterises its
glyphs at 16px -- so scaling the UI up stretches those bitmaps and the text
goes visibly blocky. Bitmaps cannot be sharpened after the fact (the engine
draws one texel per pixel, so there is nothing to supersample), which leaves
one option: rebuild the letterforms as outlines and rasterise them at whatever
size each resolution actually needs.

**Master source.** Of the 18 shipped atlases, `dialogfont32x32` carries the
same typeface at **32px** -- double the resolution of the 16px atlas the menus
use, 255 characters, and by far the best tracing source in the game files.
Everything here is traced from it.

**How the trace works.** The letterforms are geometric: axis-aligned stems,
flat terminals, simple corners. So rather than fitting curves, each glyph's
filled pixels are converted to their exact boundary polygon (every pixel
contributes the edges that face an empty neighbour, chained into closed loops),
then simplified. Simplification runs in two passes: collinear points are
dropped, then Douglas-Peucker with a sub-pixel tolerance removes the staircase
along diagonals and curves while leaving long straight runs exactly where they
were. That keeps the crispness of the original design instead of rounding it
off.

Edges are emitted counter-clockwise around each filled pixel in font
coordinates, so outer contours come out counter-clockwise and enclosed
counters (the hole in 'O', 'A', 'e') come out clockwise -- already the winding
TrueType's non-zero fill rule wants, with no post-hoc orientation fixing.

**Metrics.** `unitsPerEm` is set so ascent + descent equals exactly one em,
with the split taken from the master's own `baselineheight`. Rendering the
result at N pixels therefore reproduces a glyph box N pixels tall, which is
what `build_font_from_ttf.py` assumes when it picks a point size.

**This script produces a STARTING POINT, not the final font.** Automated
tracing can round the steps convincingly but cannot invent the curve the
original designer would have drawn -- it only approximates what the pixels
imply. `assets/fonts/KOTOR_UI_Open.ttf` is intended to be hand-refined in a
font editor (FontForge, Glyphr Studio) and committed in that refined state.

    *** Re-running this script OVERWRITES that file and destroys any hand   ***
    *** editing. Write to a different path if you only want to regenerate   ***
    *** the automated base: build_kotor_font.py ERF /tmp/base.ttf           ***

Nothing downstream re-derives the font: `build_font_from_ttf.py` simply reads
whatever TTF it is pointed at, so a hand-edited file flows into the atlases
with no code changes.

Provenance note: these outlines are traced from BioWare's shipped artwork.
The project ships the font only inside the patcher and makes no standalone
release -- see the licensing section in `reverse-engineering/font-atlases.md`.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image, ImageFilter
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import read_tpc, TPCTextureFormat

from build_scaled_fonts import raw_txi


MASTER_RESREF = "dialogfont32x32"
UNITS_PER_EM = 1024
INK_THRESHOLD = 110       # alpha above this counts as filled
SIMPLIFY_TOLERANCE = 0.55 # px; trims trace noise before corners are classified

# Tracing the 32px bitmap directly yields a staircase, and splining over it
# afterwards only rounds the steps -- the outline is still built from them. So
# the glyph is first reconstructed at sub-pixel resolution: blown up by
# SUPERSAMPLE, blurred by SMOOTH_RADIUS source-pixels, then re-thresholded. The
# blur is what turns a 1px step into a genuine curve, since a step contributes
# far less mass than a real corner and gets rounded away while long straight
# runs and true corners survive. The boundary is then traced at 1/SUPERSAMPLE
# precision, so the resulting outline describes a smooth shape rather than a
# finer staircase.
SUPERSAMPLE = 8
SMOOTH_RADIUS = 0.62      # in source pixels

# A vertex is a real corner only when the outline runs a meaningful distance on
# BOTH sides of it. A stem's 90-degree corner has multi-pixel runs either side;
# a staircase step along a curve or diagonal has 1px runs. Everything that is
# not a corner becomes an off-curve control point, so TrueType's quadratic
# spline rounds the staircase away while genuine corners stay perfectly sharp.
CORNER_MIN_RUN = 2.0      # px


def load_master(erf_path: Path, resref: str):
    """Return (alpha rows top-down, width, height, txi text)."""
    for resource in read_erf(erf_path):
        if str(resource.resref).lower() != resref.lower():
            continue
        raw = bytes(resource.data)
        tpc = read_tpc(raw)
        tpc.convert(TPCTextureFormat.RGBA)
        mipmap = tpc.get(0)
        width, height = mipmap.width, mipmap.height
        pixels = bytes(mipmap.data)
        stride = width * 4
        # A decoded TPC's first row is the image's BOTTOM; flip to top-down.
        rows = [pixels[y * stride:(y + 1) * stride] for y in range(height)][::-1]
        alpha = [[rows[y][x * 4 + 3] for x in range(width)] for y in range(height)]
        return alpha, width, height, raw_txi(raw).replace("\r\n", "\n")
    raise ValueError(f"{resref} not found in {erf_path}")


def parse_metrics(txi: str):
    def field(name: str) -> float:
        return float(re.search(rf"^{name} (\S+)$", txi, re.M).group(1))

    lines = txi.splitlines()
    upper = next(i for i, l in enumerate(lines) if l.startswith("upperleftcoords"))
    count = int(lines[upper].split()[1])
    lower = next(i for i, l in enumerate(lines) if l.startswith("lowerrightcoords"))
    ul, lr = [], []
    for index in range(count):
        a = lines[upper + 1 + index].split()
        b = lines[lower + 1 + index].split()
        ul.append((float(a[0]), float(a[1])))
        lr.append((float(b[0]), float(b[1])))
    return field("fontheight") * 100, field("baselineheight") * 100, \
        field("texturewidth") * 100, ul, lr, count


def trace(mask: list[list[bool]]) -> list[list[tuple[float, float]]]:
    """Exact pixel-boundary contours of a binary mask, in image coordinates.

    Each filled pixel contributes the edges facing an empty neighbour, directed
    so that walking them keeps the filled side consistent; chaining the directed
    edges yields closed loops with outer/hole windings already opposed.

    Where two filled pixels meet only at a corner -- which happens all over the
    diagonals in '/', 'v', 'Y', '7' -- **two** edges leave that corner, so a
    plain point->point mapping silently drops one and loses part of the outline.
    Outgoing edges are therefore kept as a list, and at such a junction the
    walk takes the sharpest clockwise turn available. That treats the
    foreground as 8-connected, keeping a diagonal stroke a single continuous
    shape instead of splitting it into disconnected squares.
    """
    height = len(mask)
    width = len(mask[0]) if height else 0
    edges: dict[tuple[float, float], list[tuple[float, float]]] = {}

    def filled(x: int, y: int) -> bool:
        return 0 <= x < width and 0 <= y < height and mask[y][x]

    def add(start, end):
        edges.setdefault(start, []).append(end)

    for y in range(height):
        for x in range(width):
            if not mask[y][x]:
                continue
            left, right, top, bottom = x, x + 1, y, y + 1
            # Counter-clockwise in y-up space == this order in y-down image space.
            if not filled(x, y + 1):
                add((left, bottom), (right, bottom))
            if not filled(x + 1, y):
                add((right, bottom), (right, top))
            if not filled(x, y - 1):
                add((right, top), (left, top))
            if not filled(x - 1, y):
                add((left, top), (left, bottom))

    def take(point, incoming):
        """Pop one outgoing edge, preferring the sharpest clockwise turn."""
        options = edges.get(point)
        if not options:
            return None
        if len(options) > 1 and incoming is not None:
            ix, iy = incoming

            def turn(candidate):
                dx = candidate[0] - point[0]
                dy = candidate[1] - point[1]
                cross = ix * dy - iy * dx
                dot = ix * dx + iy * dy
                # Order a full turn so the sharpest clockwise option sorts first.
                return (-cross, -dot)

            options.sort(key=turn)
        nxt = options.pop(0)
        if not options:
            del edges[point]
        return nxt

    contours = []
    while edges:
        start = next(iter(edges))
        contour = [start]
        current = start
        incoming = None
        while True:
            nxt = take(current, incoming)
            if nxt is None:
                break
            incoming = (nxt[0] - current[0], nxt[1] - current[1])
            if nxt == start:
                break
            contour.append(nxt)
            current = nxt
        if len(contour) >= 3:
            contours.append(contour)
    return contours


def drop_collinear(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    kept = []
    count = len(points)
    for index in range(count):
        ax, ay = points[index - 1]
        bx, by = points[index]
        cx, cy = points[(index + 1) % count]
        if (bx - ax) * (cy - by) != (by - ay) * (cx - bx):
            kept.append((bx, by))
    return kept or points


def simplify(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas-Peucker on a closed ring, anchored at its two farthest points."""
    if len(points) < 4:
        return points

    def furthest(seq):
        ax, ay = seq[0]
        bx, by = seq[-1]
        dx, dy = bx - ax, by - ay
        norm = (dx * dx + dy * dy) ** 0.5
        best_index, best_distance = 0, -1.0
        for index in range(1, len(seq) - 1):
            px, py = seq[index]
            if norm == 0:
                distance = ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
            else:
                distance = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if distance > best_distance:
                best_index, best_distance = index, distance
        return best_index, best_distance

    def run(seq):
        index, distance = furthest(seq)
        if distance <= tolerance:
            return [seq[0], seq[-1]]
        return run(seq[:index + 1])[:-1] + run(seq[index:])

    # Anchor on the pair of points farthest apart so the ring is split sensibly.
    anchor = max(range(len(points)),
                 key=lambda i: (points[i][0] - points[0][0]) ** 2
                 + (points[i][1] - points[0][1]) ** 2)
    ring = points[anchor:] + points[:anchor]
    half = len(ring) // 2
    first = run(ring[:half + 1])
    second = run(ring[half:] + [ring[0]])
    merged = first[:-1] + second[:-1]
    return merged if len(merged) >= 3 else points


def reconstruct(mask: list[list[bool]]) -> list[list[bool]]:
    """Re-sample a glyph mask at sub-pixel resolution with its steps rounded.

    A margin is added so the blur has room to work at the glyph's edges, and
    removed again by the caller via the returned offset convention (the margin
    is symmetric, so subtracting it in source pixels restores the origin).
    """
    height = len(mask)
    width = len(mask[0])
    margin = 2
    image = Image.new("L", (width + margin * 2, height + margin * 2), 0)
    image.putdata([255 if (0 <= y - margin < height and 0 <= x - margin < width
                           and mask[y - margin][x - margin]) else 0
                   for y in range(height + margin * 2)
                   for x in range(width + margin * 2)])
    image = image.resize((image.width * SUPERSAMPLE, image.height * SUPERSAMPLE),
                         Image.NEAREST)
    image = image.filter(ImageFilter.GaussianBlur(SMOOTH_RADIUS * SUPERSAMPLE))
    pixels = image.load()
    return [[pixels[x, y] > 127 for x in range(image.width)]
            for y in range(image.height)]


def classify_corners(points: list[tuple[float, float]]) -> list[bool]:
    """True where the outline genuinely turns, False on staircase steps."""
    count = len(points)
    runs = []
    for index in range(count):
        ax, ay = points[index]
        bx, by = points[(index + 1) % count]
        runs.append(((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5)
    return [min(runs[index - 1], runs[index]) >= CORNER_MIN_RUN
            for index in range(count)]


def emit_contour(pen, points: list[tuple[float, float]],
                 corners: list[bool], to_units) -> None:
    """Draw one contour, sharp at corners and splined everywhere else."""
    count = len(points)
    if not any(corners):
        # No corners at all (a fully round counter): an all-off-curve contour,
        # which TrueType closes with implied on-curve midpoints throughout.
        pen.qCurveTo(*[to_units(p) for p in points], None)
        pen.closePath()
        return

    start = corners.index(True)
    pen.moveTo(to_units(points[start]))
    pending: list[tuple[float, float]] = []
    for step in range(1, count + 1):
        index = (start + step) % count
        point = points[index]
        if corners[index]:
            if pending:
                pen.qCurveTo(*[to_units(p) for p in pending], to_units(point))
                pending = []
            else:
                pen.lineTo(to_units(point))
        else:
            pending.append(point)
    if pending:
        pen.qCurveTo(*[to_units(p) for p in pending], to_units(points[start]))
    pen.closePath()


def build(erf_path: Path, output: Path, family: str, raw: bool = False) -> None:
    alpha, atlas_w, atlas_h, txi = load_master(erf_path, MASTER_RESREF)
    glyph_h, baseline_px, texture_w, ul, lr, count = parse_metrics(txi)
    scale = UNITS_PER_EM / glyph_h          # font units per source pixel

    glyph_order = [".notdef"]
    glyphs, advances, bearings, cmap = {}, {}, {}, {}
    pen = TTGlyphPen(None)
    glyphs[".notdef"] = pen.glyph()
    advances[".notdef"] = int(round(glyph_h * 0.5 * scale))
    bearings[".notdef"] = 0

    traced = 0
    for code in range(count):
        if not (32 <= code < 127):
            continue
        name = f"uni{code:04X}"
        x0 = int(round(ul[code][0] * atlas_w))
        x1 = int(round(lr[code][0] * atlas_w))
        y0 = int(round((1 - ul[code][1]) * atlas_h))
        y1 = int(round((1 - lr[code][1]) * atlas_h))
        advance_px = max(0.0, (lr[code][0] - ul[code][0]) * texture_w)

        mask = [[alpha[y][x] > INK_THRESHOLD
                 for x in range(max(0, x0), min(x1, atlas_w))]
                for y in range(max(0, y0), min(y1, atlas_h))]

        emitted_x: list[int] = []

        def to_units(point):
            px, py = point
            ux = round(px * scale)
            emitted_x.append(ux)
            return (ux, round((baseline_px - py) * scale))

        pen = TTGlyphPen(None)
        if mask and mask[0] and any(any(row) for row in mask):
            if raw:
                # Lossless: the exact pixel boundary, every vertex on a pixel
                # corner and every segment straight. Only collinear points are
                # dropped, which changes nothing about the shape. This is the
                # honest original geometry to hand-draw over -- no smoothing has
                # guessed at anything yet.
                for contour in trace(mask):
                    points = drop_collinear(contour)
                    if len(points) < 3:
                        continue
                    emit_contour(pen, points, [True] * len(points), to_units)
                    traced += 1
            else:
                margin = 2
                for contour in trace(reconstruct(mask)):
                    # Back to source-pixel units: undo supersample and margin.
                    scaled = [(x / SUPERSAMPLE - margin, y / SUPERSAMPLE - margin)
                              for x, y in contour]
                    simplified = simplify(drop_collinear(scaled), SIMPLIFY_TOLERANCE)
                    if len(simplified) < 3:
                        continue
                    emit_contour(pen, simplified, classify_corners(simplified), to_units)
                    traced += 1

        glyphs[name] = pen.glyph()
        advances[name] = int(round(advance_px * scale))
        # The left side bearing must equal the outline's own xMin. Declaring 0
        # while the ink starts further right makes renderers shift the glyph
        # left by that amount -- which silently moved every inset glyph ('/',
        # 'v', 'Y', '7' ...) one pixel off its design position.
        bearings[name] = min(emitted_x) if emitted_x else 0
        cmap[code] = name
        glyph_order.append(name)

    ascent = int(round(baseline_px * scale))
    descent = int(round((glyph_h - baseline_px) * scale))

    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(
        {n: (advances[n], bearings.get(n, 0)) for n in glyph_order})
    builder.setupHorizontalHeader(ascent=ascent, descent=-descent)
    builder.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "fullName": family,
        "psName": family.replace(" ", ""),
        "version": "Version 1.000",
        "copyright": "Outlines traced from the KOTOR UI bitmap atlases.",
    })
    builder.setupOS2(sTypoAscender=ascent, sTypoDescender=-descent,
                     usWinAscent=ascent, usWinDescent=descent)
    builder.setupPost()
    output.parent.mkdir(parents=True, exist_ok=True)
    builder.save(output)

    print(f"master        : {MASTER_RESREF} ({glyph_h:.0f}px glyphs, {atlas_w}x{atlas_h})")
    print(f"glyphs        : {len(glyph_order) - 1} (printable ASCII)")
    print(f"contours      : {traced}")
    print(f"unitsPerEm    : {UNITS_PER_EM}  ascent {ascent}  descent {descent}")
    print(f"wrote         : {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("erf", type=Path, help="TexturePacks/swpc_tex_gui.erf")
    parser.add_argument("output", type=Path)
    parser.add_argument("--family", default="KOTOR UI Open")
    parser.add_argument("--raw", action="store_true",
                        help="lossless pixel-exact outlines with no smoothing, "
                             "the honest starting point for hand-drawing")
    args = parser.parse_args()
    build(args.erf, args.output, args.family, raw=args.raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
