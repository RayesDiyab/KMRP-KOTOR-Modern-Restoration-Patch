#!/usr/bin/env python3
"""Measure the per-glyph letter spacing each resolution needs, and table it.

Text rendered from the shared atlas comes out slightly tighter at some sizes
than others. The cause is not a smooth resampling artifact -- measured baseline
gap/ink ratios for the menu font run 0.114 at 720p, 0.098 at 1080p, 0.126 at
1440p and 0.120 at 2160p, which is **not monotonic** in how hard the atlas is
downscaled. It is integer rounding of each glyph's advance landing differently
at each specific pixel size. No formula in `f = scale / bake` can track that,
and one that tries overshoots badly at the small end (a 720p menu measured
0.198 against a 0.120 target).

So this measures instead of modelling. For every font and every distinct scale
the resolution list asks for, it reconstructs how the engine will rasterise the
atlas at that size, measures the mean ink width and the mean gap that follows
it, and solves for the `spacingR` that brings the ratio back to the font's own
value at the native baked size -- where nothing is resampled and the spacing is
therefore the typeface's true design spacing. Fonts already at or above their
native ratio get nothing; the correction only ever loosens, never tightens.

Output: `assets/letter-spacing.json`, a `{resref: {scale: pixels}}` table read
by `prepare_universal_resources.py`. That step is deliberately kept
pure-stdlib (see the PIL/PowerShell note in docs/font-scaling.md), which is why
the measuring lives here and the result is committed rather than computed
during the build.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

from PIL import Image


INK_THRESHOLD = 110
# Representative of real UI text: mixed case, no unusually wide or narrow runs.
SAMPLE = "Party Inventory All Items Awareness Restricted 0123"


def load_atlas(tga: Path) -> tuple[Image.Image, int, int]:
    data = tga.read_bytes()
    width, height = struct.unpack_from("<HH", data, 12)
    pixels = data[18:18 + width * height * 4]
    stride = width * 4
    # The file is bottom-up, so reverse to get row 0 = top.
    rows = [pixels[y * stride:(y + 1) * stride] for y in range(height)][::-1]
    image = Image.new("L", (width, height))
    image.putdata([rows[y][x * 4 + 3] for y in range(height) for x in range(width)])
    return image, width, height


def read_metrics(txi: Path):
    text = txi.read_text(encoding="ascii").replace("\r\n", "\n")
    lines = text.splitlines()

    def field(name: str) -> float:
        return float(re.search(rf"^{name} (\S+)$", text, re.M).group(1))

    upper = next(i for i, l in enumerate(lines) if l.startswith("upperleftcoords"))
    lower = next(i for i, l in enumerate(lines) if l.startswith("lowerrightcoords"))
    # Not every atlas carries 256 entries -- several declare 255 -- so take the
    # count from the header rather than assuming.
    count = int(lines[upper].split()[1])
    ul = [tuple(map(float, lines[upper + 1 + i].split()[:2])) for i in range(count)]
    lr = [tuple(map(float, lines[lower + 1 + i].split()[:2])) for i in range(count)]
    return field("fontheight") * 100, field("texturewidth") * 100, ul, lr


def ratio_at(atlas, width, height, baked_height, baked_texture, ul, lr,
             factor: float) -> tuple[float, float]:
    """Mean ink width and mean trailing gap, in pixels, at this scale factor."""
    font_height = baked_height * factor
    texture_width = baked_texture * factor
    inks, gaps = [], []
    for character in SAMPLE:
        if character == " ":
            continue
        index = ord(character)
        if index >= len(ul):
            continue
        advance = (lr[index][0] - ul[index][0]) * texture_width
        x0, x1 = ul[index][0] * width, lr[index][0] * width
        y0, y1 = (1 - ul[index][1]) * height, (1 - lr[index][1]) * height
        cell = atlas.crop((round(x0), round(y0),
                           max(round(x0) + 1, round(x1)),
                           max(round(y0) + 1, round(y1))))
        drawn = cell.resize((max(1, round(advance)), max(1, round(font_height))),
                            Image.BILINEAR)
        box = drawn.point(lambda v: 255 if v > INK_THRESHOLD else 0).getbbox()
        if not box:
            continue
        inks.append(box[2] - box[0])
        gaps.append(round(advance) - box[2])
    if not inks:
        return 0.0, 0.0
    return sum(inks) / len(inks), sum(gaps) / len(gaps)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("hd_fonts", type=Path, help="assets/hd-fonts")
    parser.add_argument("output", type=Path, help="assets/letter-spacing.json")
    parser.add_argument("--bake-scale", type=float, default=3.0,
                        help="must match HD_FONT_BAKE_SCALE")
    args = parser.parse_args()

    # Every distinct scale the 48 shipped resolutions ask for.
    heights = sorted({540, 576, 600, 640, 648, 720, 768, 800, 900, 1050, 1080,
                      1152, 1200, 1280, 1392, 1440, 1536, 1600, 1800, 2160,
                      2400, 2880, 3072, 3200, 3384, 4320, 4608, 8640})
    scales = sorted({max(1.0, h / 720.0) for h in heights})

    table: dict[str, dict[str, float]] = {}
    for tga in sorted(args.hd_fonts.glob("*.tga")):
        resref = tga.stem
        txi = tga.with_suffix(".txi")
        if not txi.exists():
            continue
        atlas, width, height = load_atlas(tga)
        baked_height, baked_texture, ul, lr = read_metrics(txi)

        native_ink, native_gap = ratio_at(atlas, width, height, baked_height,
                                          baked_texture, ul, lr, 1.0)
        target = (native_gap / native_ink) if native_ink else 0.0

        entries: dict[str, float] = {}
        for scale in scales:
            factor = scale / args.bake_scale
            ink, gap = ratio_at(atlas, width, height, baked_height,
                                baked_texture, ul, lr, factor)
            if not ink:
                continue
            needed = (target - gap / ink) * ink
            # Only ever loosen, and keep it sub-pixel-ish; a correction larger
            # than a pixel means something else is wrong.
            entries[f"{scale:.4f}"] = round(min(max(needed, 0.0), 1.0), 3)
        table[resref] = entries

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n",
                           encoding="ascii")

    print(f"measured {len(table)} fonts across {len(scales)} scales -> {args.output}")
    for resref in ("dialogfont16x16", "fnt_d16x16b"):
        if resref in table:
            row = table[resref]
            shown = {s: row[s] for s in ("1.0000", "1.5000", "2.0000", "3.0000") if s in row}
            print(f"  {resref:18s} " +
                  "  ".join(f"scale {s}: {v}px" for s, v in shown.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
