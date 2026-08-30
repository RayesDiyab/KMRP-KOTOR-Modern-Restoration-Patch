#!/usr/bin/env python3
"""Export the vanilla glyphs as tracing templates for hand-drawing the font.

`build_kotor_font.py` can only approximate what a 32px bitmap implies. Drawing
the letterforms by hand beats it, and this produces the references to draw
over: one PNG per glyph, plus a contact sheet for an overview.

**Every image is a full em SQUARE**, not cropped to the glyph. A font editor
places a background image against the em square, so an image sized to the
glyph's own advance width gets scaled to fit and lands nowhere near the
outline -- which is exactly what happened with the first version of this
script. Padding each one out to a square makes the placement unambiguous: the
glyph sits at its true position inside that square, so the default import
lines it up with the outline.

At the default `--scale 32` one image pixel is exactly one font unit (a 32px
em x 32 = 1024 = `UNITS_PER_EM` in `build_kotor_font.py`), so a distance
measured on the image is directly a coordinate in the editor.

A faint baseline and advance-width guide are drawn in; `--clean` omits them if
you would rather trace the bare shape.

FontForge: open the glyph, File > Import, pick the PNG, choose "as background".
Then draw over it and delete the background layer when done.

The templates come from `dialogfont32x32`, the highest-resolution copy of the
typeface the game ships (32px, versus the 16px atlas the menus actually use).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from build_kotor_font import MASTER_RESREF, INK_THRESHOLD, load_master, parse_metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("erf", type=Path, help="TexturePacks/swpc_tex_gui.erf")
    parser.add_argument("output", type=Path, help="directory for the templates")
    parser.add_argument("--scale", type=int, default=32,
                        help="pixels per source pixel (default 32 -> one image "
                             "pixel per font unit, 1024px em square)")
    parser.add_argument("--clean", action="store_true",
                        help="omit the baseline/advance guides")
    parser.add_argument("--centered", action="store_true",
                        help="centre the ink in the square. Looks tidier but "
                             "destroys the glyph's true position, so anything "
                             "traced over it renders displaced -- use only as a "
                             "shape reference, never to redraw in place")
    args = parser.parse_args()

    alpha, atlas_w, atlas_h, txi = load_master(args.erf, MASTER_RESREF)
    glyph_h, baseline_px, texture_w, ul, lr, count = parse_metrics(txi)
    scale = args.scale
    box_h = int(round(glyph_h * scale))

    args.output.mkdir(parents=True, exist_ok=True)
    sheet_cells = []

    # Where the letters actually sit, measured rather than assumed. The TXI's
    # `baselineheight` is an engine metric and is NOT the visual baseline: it
    # reads 21 on a 32px em while every glyph -- 'g', 'p' and 'y' included, as
    # this face is small-caps and has no descenders -- bottoms out at row 27.
    # Drawing the declared value put the guide straight through the letters.
    bottoms = []
    for code in range(count):
        if not (33 <= code < 127):
            continue
        bx0 = int(round(ul[code][0] * atlas_w))
        bx1 = int(round(lr[code][0] * atlas_w))
        by0 = int(round((1 - ul[code][1]) * atlas_h))
        by1 = int(round((1 - lr[code][1]) * atlas_h))
        if bx1 <= bx0:
            continue
        rows = [y for y in range(by0, min(by1, atlas_h))
                if any(alpha[y][x] > INK_THRESHOLD
                       for x in range(max(0, bx0), min(bx1, atlas_w)))]
        if rows:
            bottoms.append(rows[-1] - by0)
    visual_baseline = (max(set(bottoms), key=bottoms.count) + 1) if bottoms else baseline_px

    for code in range(count):
        if not (33 <= code < 127):
            continue
        x0 = int(round(ul[code][0] * atlas_w))
        x1 = int(round(lr[code][0] * atlas_w))
        y0 = int(round((1 - ul[code][1]) * atlas_h))
        y1 = int(round((1 - lr[code][1]) * atlas_h))
        advance_px = max(1.0, (lr[code][0] - ul[code][0]) * texture_w)
        box_w = int(round(advance_px * scale))
        if box_w < 1 or x1 <= x0:
            continue

        cell = Image.new("L", (max(1, x1 - x0), max(1, y1 - y0)), 0)
        cell.putdata([255 if alpha[y][x] > INK_THRESHOLD else 0
                      for y in range(max(0, y0), min(y1, atlas_h))
                      for x in range(max(0, x0), min(x1, atlas_w))])

        # NEAREST keeps every source pixel a crisp square, so the intended
        # geometry stays legible instead of being blurred into guesswork.
        glyph = cell.resize((cell.width * scale, cell.height * scale), Image.NEAREST)

        canvas = Image.new("RGB", (box_h, box_h), (255, 255, 255))
        if args.centered:
            # Nicer to look at, but the letter no longer sits where it belongs:
            # anything traced over it renders displaced. Shape reference only.
            offset_x = (box_h - glyph.width) // 2
            offset_y = (box_h - glyph.height) // 2
        else:
            # Default: the glyph's TRUE position in the em. Tracing over this
            # reproduces the original's spacing and baseline exactly, which is
            # the point -- the drawing should differ from vanilla only in being
            # smooth, never in where it sits.
            offset_x = 0
            offset_y = 0
        ink = Image.new("RGB", glyph.size, (40, 48, 60))
        canvas.paste(ink, (offset_x, offset_y), glyph)

        if not args.clean:
            draw = ImageDraw.Draw(canvas)
            base_y = offset_y + int(round(visual_baseline * scale))
            if 0 <= base_y < box_h:
                draw.line([(0, base_y), (box_h, base_y)], fill=(220, 90, 90), width=1)
            advance_x = offset_x + box_w - 1
            if 0 <= advance_x < box_h:
                draw.line([(advance_x, 0), (advance_x, box_h)],
                          fill=(120, 170, 230), width=1)

        canvas.save(args.output / f"U+{code:04X}_{chr(code) if chr(code).isalnum() else 'sym'}.png")
        sheet_cells.append((chr(code), canvas))

    columns = 12
    cell_w = max(c.width for _, c in sheet_cells) + 8
    cell_h = box_h + 8
    rows = (len(sheet_cells) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (250, 250, 250))
    for index, (_, cell) in enumerate(sheet_cells):
        cx = (index % columns) * cell_w + 4
        cy = (index // columns) * cell_h + 4
        sheet.paste(cell, (cx, cy))
    sheet.save(args.output / "_contact_sheet.png")

    print(f"master     : {MASTER_RESREF} ({glyph_h:.0f}px em, baseline {baseline_px:.0f}px)")
    print(f"templates  : {len(sheet_cells)} glyphs at {scale}x -> {box_h}px em")
    print(f"written to : {args.output}")
    print(f"contact    : {args.output / '_contact_sheet.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
