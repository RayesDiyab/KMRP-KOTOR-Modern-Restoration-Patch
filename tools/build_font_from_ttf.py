#!/usr/bin/env python3
"""Render a KOTOR font atlas from a TrueType font.

Upscaling the stock atlases can only round off their staircased edges -- the
detail was never there to recover. Rendering from a vector font instead gives
genuinely crisp glyphs at any size. This is an open reimplementation of what
the old "KOTOR Font Tool (NWN Font Maker)" did, written against the format as
measured from the shipped assets rather than against that tool.

Format, established by measuring all 18 stock atlases:

  * Glyphs sit on a square grid. The column count is the reciprocal of the
    `upperleftcoords` u-step -- 16 for `dialogfont16x16` (16px cells in a 256px
    atlas), 32 for `fnt_d16x16` (16px cells in a 512px atlas).
  * `fontheight * 100` is the rendered glyph height in pixels, and may be less
    than the cell height (`fnt_d16x16` draws 10px glyphs in 16px cells).
  * `texturewidth * 100` is the width that UV deltas are multiplied by to get
    rendered pixel widths. Every stock atlas sets it to its own texture width,
    i.e. vanilla renders exactly one texel per pixel.

That last point is what makes high-resolution atlases work: `texturewidth` is a
rendering scale, not a description of the texture. Keeping the stock metrics
while enlarging the atlas leaves text exactly the same size on screen but
supersampled -- so the glyph coordinates, and the executable, need no changes.

The metrics are therefore copied from whichever stock font is being replaced,
and only the texel density changes. Text sizing stays the job of
tools/build_scaled_fonts.py, which scales those metrics per resolution.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import read_tpc

from build_scaled_fonts import raw_txi, write_tga


HEADER_FIELDS = (
    "mipmap", "filter", "compresstexture", "downsamplemax", "downsamplemin",
    "numchars", "fontheight", "baselineheight", "texturewidth",
    "spacingR", "spacingB", "caretindent",
)


class Reference:
    """Layout and metrics read from a stock font atlas."""

    def __init__(self, erf_path: Path, resref: str):
        for resource in read_erf(erf_path):
            if str(resource.resref).lower() != resref.lower():
                continue
            raw = bytes(resource.data)
            # Stock TXIs use CRLF; normalise so the field patterns below match.
            self.txi = raw_txi(raw).replace("\r\n", "\n").replace("\r", "\n")
            self.atlas_size = read_tpc(raw).dimensions()[0]
            break
        else:
            raise ValueError(f"{resref} not found in {erf_path}")

        self.header = {}
        for field in HEADER_FIELDS:
            match = re.search(rf"^{field} (\S+)$", self.txi, re.M)
            if match:
                self.header[field] = match.group(1)

        self.numchars = int(float(self.header["numchars"]))
        coords = self._coords("upperleftcoords")
        # Count columns by finding where u wraps back to the left edge, rather
        # than from the first u-step: some atlases (fnt_console) repeat a
        # coordinate at the start, which makes that first step zero.
        self.columns = next(
            (i for i in range(1, len(coords)) if coords[i][0] <= coords[0][0]),
            len(coords),
        )
        self.cell = self.atlas_size // self.columns
        self.glyph_height = round(float(self.header["fontheight"]) * 100)

    def _coords(self, header: str) -> list[tuple[float, float]]:
        # The header carries its own entry count, e.g. "upperleftcoords 256".
        lines = self.txi.splitlines()
        start = next(i for i, line in enumerate(lines)
                     if line.strip().lower().startswith(header))
        out = []
        for line in lines[start + 1:]:
            parts = line.split()
            if len(parts) != 3:
                break
            out.append((float(parts[0]), float(parts[1])))
        return out


def render_atlas(font_path: Path, reference: Reference, upscale: int,
                 size_ratio: float) -> tuple[Image.Image, list[int]]:
    """Draw every glyph into its cell; return the atlas and per-glyph widths."""
    cell = reference.cell * upscale
    atlas_size = cell * reference.columns
    glyph_height = reference.glyph_height * upscale

    # Pick the point size whose ascent+descent fills the glyph box, so the art
    # occupies the same share of each cell as the stock font's does.
    point = max(1, int(glyph_height * size_ratio))
    font = ImageFont.truetype(str(font_path), point)
    ascent, descent = font.getmetrics()
    while ascent + descent > glyph_height and point > 1:
        point -= 1
        font = ImageFont.truetype(str(font_path), point)
        ascent, descent = font.getmetrics()

    image = Image.new("L", (atlas_size, atlas_size), 0)
    draw = ImageDraw.Draw(image)
    widths: list[int] = []

    for index in range(reference.numchars):
        column = index % reference.columns
        row = index // reference.columns
        x = column * cell
        y = row * cell
        character = chr(index)
        try:
            advance = int(round(draw.textlength(character, font=font)))
        except Exception:
            advance = 0
        if character.isprintable() and advance > 0:
            draw.text((x, y + ascent), character, font=font, fill=255, anchor="ls")
        widths.append(min(advance, cell))

    rgba = Image.new("RGBA", image.size, (255, 255, 255, 0))
    rgba.putalpha(image)
    return rgba, widths


def build_txi(reference: Reference, widths: list[int], upscale: int) -> str:
    """Stock metrics, with coordinates regenerated for the new glyph widths."""
    atlas_size = reference.cell * upscale * reference.columns
    lines = [f"{field} {reference.header[field]}" for field in HEADER_FIELDS
             if field in reference.header]

    step = 1.0 / reference.columns
    glyph_v = (reference.glyph_height * upscale) / atlas_size

    lines.append(f"upperleftcoords {reference.numchars}")
    for index in range(reference.numchars):
        u = (index % reference.columns) * step
        v = 1.0 - (index // reference.columns) * step
        lines.append(f"{u:.6f} {v:.6f} 0")

    lines.append(f"lowerrightcoords {reference.numchars}")
    for index in range(reference.numchars):
        u = (index % reference.columns) * step + widths[index] / atlas_size
        v = 1.0 - (index // reference.columns) * step - glyph_v
        lines.append(f"{u:.6f} {v:.6f} 0")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ttf", type=Path)
    parser.add_argument("erf", type=Path, help="TexturePacks/swpc_tex_gui.erf")
    parser.add_argument("output", type=Path)
    parser.add_argument("--fonts", nargs="*", default=["dialogfont16x16"],
                        help="Stock atlases to replace; each supplies its own layout and metrics")
    parser.add_argument("--upscale", type=int, default=4, help="Texel density multiplier")
    parser.add_argument("--size-ratio", type=float, default=1.0,
                        help="Point size as a fraction of the glyph box; trim if glyphs look too heavy")
    args = parser.parse_args()

    if not 1 <= args.upscale <= 8:
        raise ValueError("Upscale must be between 1 and 8")
    args.output.mkdir(parents=True, exist_ok=True)

    for resref in args.fonts:
        reference = Reference(args.erf, resref)
        # Two stock atlases do not describe a layout we can reproduce: fnt_console
        # repeats its first coordinate (so no column pitch can be read from it),
        # and fnt_galahad14 declares 17px glyphs in 8px cells. Rendering into
        # either would overlap neighbouring cells, so they are left as vanilla art
        # rather than shipped broken.
        if reference.columns < 2 or reference.cell * reference.columns != reference.atlas_size:
            print(f"{resref}: skipped -- unreadable grid ({reference.columns} columns)")
            continue
        if reference.glyph_height > reference.cell:
            print(f"{resref}: skipped -- {reference.glyph_height}px glyphs "
                  f"exceed {reference.cell}px cells")
            continue
        atlas, widths = render_atlas(args.ttf, reference, args.upscale, args.size_ratio)
        write_tga(args.output / f"{resref}.tga", atlas.width, atlas.height, atlas.tobytes())
        (args.output / f"{resref}.txi").write_bytes(build_txi(reference, widths, args.upscale).encode("ascii"))
        print(f"{resref}: {reference.columns} cols, {reference.cell}px cell, "
              f"{reference.glyph_height}px glyphs -> {atlas.width}x{atlas.height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
