#!/usr/bin/env python3
"""Close the vertical gap between the area map and its frame in `lbl_map.tga`.

**The gap.** The map screen's whole background, frame included, is one texture:
`map.gui`'s panel draws `lbl_map` as its `BORDER.FILL`, stretched to the screen.
The map surface itself is drawn by the engine on top, `screenHeight // 2` tall.
Those two numbers were never reconciled, so the frame's opening is slightly
taller than the map and the difference shows as a band of empty texture.

Measured at 3440x1440 from a screen capture, reading the pixel column at x=2400
(inside the frame, clear of the drawn structures):

    frame outer line (top)     centred screen row  345
    frame inner line (top)     centred screen row  363, inner edge ~368
    empty texture              rows 369-373                      <- 5 rows
    map surface                rows 374-1093     = exactly 720 = screenHeight//2
    empty texture              row  1094                         <- 1 row
    frame inner line (bottom)  centred screen row 1100
    frame outer line (bottom)  centred screen row 1118

So the opening is 726 rows against a 720-row map: **6 rows of slack, 5 at the top
and 1 at the bottom**. This moves the frame's top edge down 5 and its bottom edge
up 1, which closes both.

**Why the artwork and not the GUI.** `LBL_Map`'s extent is computed per
resolution (see `reverse-engineering/area-map-surface.md`), and moving the map
would only re-centre the slack rather than remove it. The frame is art, so the
art is where the fit belongs. The texture is stretched to the panel at every
resolution, so one edit fixes all 48.

**How, without touching anything else.** Only the block containing the frame is
resampled -- texture columns 680..2190, which is the frame's own span (its border
runs x 694..2172) and excludes the map-note panel on the left and the compass on
the right. Those, and every row above and below the frame, come out
byte-identical.

Within that block the source rows are Lanczos-resampled into a slightly shorter
destination, which moves the borders by the measured amounts. The interior
compresses by 0.8%, which is invisible: it is covered by the map surface, and a
0.8% shift of a 5px line is sub-pixel. The rows the frame vacates are filled with
the background colour read from the texture itself -- rows 332-335 and 1122-1124
are a perfectly uniform (0,0,21,255) across the whole block, so the fill leaves
no seam.

Vertical scale: the texture is 1434 rows stretched to 1440, so one texture row is
0.9958 screen rows -- close enough to 1:1 that the measured screen offsets are
used directly.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


# The frame's own span, plus margin for its glow. Outside this the image is copied.
BLOCK_LEFT, BLOCK_RIGHT = 680, 2190

# The block of rows carrying the frame, and where it should land. Chosen so the
# rows immediately outside are the uniform background used for the fill.
SOURCE_TOP, SOURCE_BOTTOM = 335, 1121        # inclusive
SHIFT_TOP, SHIFT_BOTTOM = 5, 1               # rows down at the top, up at the bottom

BACKGROUND_PROBE = 333                       # a row known uniform inside the block


def fit(source: Path, output: Path) -> None:
    image = Image.open(source).convert("RGBA")
    width, height = image.size
    print(f"  {source.name}  {width}x{height}")

    dest_top = SOURCE_TOP + SHIFT_TOP
    dest_bottom = SOURCE_BOTTOM - SHIFT_BOTTOM
    source_rows = SOURCE_BOTTOM - SOURCE_TOP + 1
    dest_rows = dest_bottom - dest_top + 1

    background = image.getpixel((BLOCK_LEFT + 5, BACKGROUND_PROBE))
    uniform = image.crop((BLOCK_LEFT, BACKGROUND_PROBE, BLOCK_RIGHT, BACKGROUND_PROBE + 1))
    if uniform.getextrema()[:3] != tuple((c, c) for c in background[:3]):
        raise SystemExit(f"row {BACKGROUND_PROBE} is not uniform across the block; "
                         "the fill would leave a seam")

    block = image.crop((BLOCK_LEFT, SOURCE_TOP, BLOCK_RIGHT, SOURCE_BOTTOM + 1))
    resampled = block.resize((block.width, dest_rows), Image.LANCZOS)

    result = image.copy()
    # Clear the whole source band to background, then lay the frame back in place.
    result.paste(background,
                 (BLOCK_LEFT, SOURCE_TOP, BLOCK_RIGHT, SOURCE_BOTTOM + 1))
    result.paste(resampled, (BLOCK_LEFT, dest_top))

    result.save(output, format="TGA", compression=None)

    print(f"  block            x {BLOCK_LEFT}..{BLOCK_RIGHT}, rows {SOURCE_TOP}..{SOURCE_BOTTOM}")
    print(f"  frame top        down {SHIFT_TOP} rows")
    print(f"  frame bottom     up   {SHIFT_BOTTOM} row(s)")
    print(f"  interior scale   {dest_rows}/{source_rows} = {dest_rows / source_rows:.5f}")
    print(f"  wrote {output}  ({output.stat().st_size} bytes)")

    # Everything outside the block must be untouched.
    import numpy as np
    before = np.asarray(image)
    after = np.asarray(Image.open(output).convert("RGBA"))
    outside = np.ones(before.shape[:2], dtype=bool)
    outside[SOURCE_TOP:SOURCE_BOTTOM + 1, BLOCK_LEFT:BLOCK_RIGHT] = False
    changed = int((before[outside] != after[outside]).any(axis=-1).sum())
    print(f"  pixels changed outside the block: {changed}")
    if changed:
        raise SystemExit("the edit escaped its block")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    fit(args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
