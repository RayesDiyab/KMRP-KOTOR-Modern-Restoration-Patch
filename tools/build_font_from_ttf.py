#!/usr/bin/env python3
"""Render a KOTOR font atlas from a TrueType font.

Upscaling the stock atlases can only round off their staircased edges -- the
detail was never there to recover. Rendering from a vector font gives genuinely
crisp glyphs. This is an open reimplementation of what the old closed "KOTOR
Font Tool (NWN Font Maker)" did, written against the format as measured from
the shipped assets rather than against that tool.

Format, established by measuring all 18 stock atlases:

  * `fontheight * 100` is the rendered glyph height in pixels and
    `baselineheight * 100` the baseline offset within that box.
  * `texturewidth * 100` must equal the atlas's own pixel width -- it is how
    coordinates become texels. Declaring anything else garbles the text.
  * **The engine renders one texel per pixel.** Glyph width on screen is the
    glyph's texel count; height comes from `fontheight`. So a larger atlas makes
    text physically bigger rather than sharper, and oversampling it stretches
    the glyphs horizontally. The atlas is therefore built at exactly the size
    the text should appear, and sharpness comes from rasterising the outlines at
    that size.
  * Glyphs are **not** laid out on a uniform grid. `fnt_galahad14` packs them
    proportionally -- 154 distinct u positions across 8 rows -- while others use
    fixed cells. Since this writes its own coordinates it always packs
    proportionally, which fits any font and wastes no space.

Text sizing is thus a property of the atlas, so the output must NOT be run
through tools/build_scaled_fonts.py afterwards -- that would double-apply it.
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

# Gap left around every glyph. 1px is not enough: the atlas is rasterised at the
# top of the scale range and filtered back down at every smaller resolution, and
# bilinear sampling reaches past the glyph's own rectangle -- with a 1px gap it
# picks up the ascenders of the row underneath, which show up in game as stray
# dots beneath the text. 4px keeps neighbouring rows out of the filter kernel.
GLYPH_PADDING = 4


class Reference:
    """Metrics read from a stock font atlas."""

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
        self.glyph_height = round(float(self.header["fontheight"]) * 100)
        self.baseline = round(float(self.header.get("baselineheight",
                                                    self.header["fontheight"])) * 100)
        self.stock_widths = self._read_stock_widths()

    def _read_stock_widths(self) -> list[int]:
        """Per-glyph advance widths, in pixels, as the stock atlas declares them.

        Every one of the 256 entries is non-zero in all 18 shipped fonts (the
        narrowest is 4px) -- the engine's word-wrap relies on it, see the note
        in `measure`. These are the fallback when a TrueType face reports no
        advance of its own for a character.
        """
        lines = self.txi.splitlines()
        texture_width = round(float(self.header["texturewidth"]) * 100)
        try:
            upper = next(i for i, line in enumerate(lines)
                         if line.startswith("upperleftcoords"))
            lower = next(i for i, line in enumerate(lines)
                         if line.startswith("lowerrightcoords"))
        except StopIteration:
            return [0] * self.numchars

        widths = []
        for index in range(self.numchars):
            left = float(lines[upper + 1 + index].split()[0])
            right = float(lines[lower + 1 + index].split()[0])
            widths.append(max(0, round((right - left) * texture_width)))
        return widths


def next_power_of_two(value: int) -> int:
    size = 1
    while size < value:
        size *= 2
    return size


def measure(font: ImageFont.FreeTypeFont, numchars: int,
            fallback: list[int], scale: float) -> tuple[list[int], dict[int, int]]:
    """Advance width per glyph, in pixels. Never zero -- see below.

    A zero-advance glyph crashes the game. `CAurGUIString`'s word-wrap
    (0x0045A2F0) breaks a line that will not fit by backing up one character
    (`dec ebx` at 0x0045A5E3) and restarting the line there; its only
    termination guard compares against the start of the whole *string*
    (0x0045A5E4), not the start of the current *line*. A character that cannot
    advance the cursor therefore walks the pointer backwards one byte per
    iteration, appending a line-break entry each time, until the entry array's
    doubling growth asks for an allocation the game cannot satisfy -- observed
    live as a NULL write after a 67-million-element request, crashing Inventory
    on any item whose description contains a newline.

    All 18 stock atlases keep every one of their 256 entries non-zero (the
    narrowest is 4px), including control codes like `\\n` that are never drawn,
    which is why vanilla never hits this. So characters the TrueType face has
    no advance for -- control codes, unmapped codepoints -- inherit the stock
    atlas's own width for that slot, scaled to match.
    """
    scratch = ImageDraw.Draw(Image.new("L", (1, 1)))
    widths = []
    offsets: dict[int, int] = {}
    for index in range(numchars):
        character = chr(index)
        try:
            advance = int(round(scratch.textlength(character, font=font)))
        except Exception:
            advance = 0
        if not character.isprintable():
            advance = 0
        if advance <= 0:
            stock = fallback[index] if index < len(fallback) else 0
            advance = max(1, round(stock * scale))
        else:
            # In this format a glyph's cell width IS its advance -- there is no
            # side bearing to overhang into, so any ink outside the cell is cut
            # off. Typefaces routinely spill past the advance on both sides:
            # 'f', 'w', 'y', 'V' overhang to the right, and 'j', 'w', '(', 'Y'
            # start LEFT of the pen origin. Widen the cell to contain the ink on
            # whichever sides it escapes; `offsets` records how far each glyph
            # must then be nudged right so its leftmost ink lands inside.
            try:
                box = font.getbbox(character)
                left = min(0, box[0])
                right = box[2] - left
                if right > advance:
                    advance = int(right) + (1 if right % 1 else 0)
                offsets[index] = -left
            except Exception:
                pass
        widths.append(advance)
    return widths, offsets


def pack(widths: list[int], glyph_height: int, atlas_size: int) -> list[tuple[int, int]] | None:
    """Place each glyph left to right, wrapping rows; None if it will not fit."""
    positions = []
    x = y = 0
    row_advance = glyph_height + GLYPH_PADDING
    for width in widths:
        span = width + GLYPH_PADDING
        if x + span > atlas_size:
            x = 0
            y += row_advance
        if y + glyph_height > atlas_size:
            return None
        positions.append((x, y))
        x += span
    return positions


def render(font_path: Path, reference: Reference, scale: float):
    """Rasterise every glyph at the target size and pack it into an atlas."""
    glyph_height = max(1, round(reference.glyph_height * scale))
    baseline = max(1, round(reference.baseline * scale))

    # Choose the point size whose ascent+descent fills the glyph box, so
    # descenders are preserved rather than clipped.
    point = glyph_height
    while point > 1:
        font = ImageFont.truetype(str(font_path), point)
        ascent, descent = font.getmetrics()
        if ascent + descent <= glyph_height:
            break
        point -= 1
    font = ImageFont.truetype(str(font_path), point)
    ascent, _ = font.getmetrics()

    widths, offsets = measure(font, reference.numchars, reference.stock_widths, scale)
    # Never go smaller than the stock atlas. Crashed in game when fnt_d16x16b
    # packed tighter (256px) than its stock size (512px) -- some code path
    # likely assumes/hardcodes the original texture dimension for specific
    # fonts rather than reading it from the loaded texture, so a genuinely
    # smaller atlas can read out of bounds. Confirmed by isolation: this file
    # alone in Override crashed Inventory even though the exact same font
    # renders fine elsewhere (the Skills description panel), which rules out
    # glyph content and points at the atlas itself.
    atlas_size = next_power_of_two(max(64, glyph_height, reference.atlas_size))
    while True:
        positions = pack(widths, glyph_height, atlas_size)
        if positions is not None:
            break
        atlas_size *= 2

    image = Image.new("L", (atlas_size, atlas_size), 0)
    draw = ImageDraw.Draw(image)
    for index, ((x, y), width) in enumerate(zip(positions, widths)):
        if width <= 0:
            continue
        draw.text((x + offsets.get(index, 0), y + ascent), chr(index),
                  font=font, fill=255, anchor="ls")

    rgba = Image.new("RGBA", image.size, (255, 255, 255, 0))
    rgba.putalpha(image)
    return rgba, positions, widths, glyph_height, baseline, atlas_size


def build_txi(reference: Reference, positions, widths, glyph_height: int,
              baseline: int, atlas_size: int) -> str:
    header = dict(reference.header)
    header["texturewidth"] = f"{atlas_size / 100.0:.6f}"
    header["fontheight"] = f"{glyph_height / 100.0:.6f}"
    header["baselineheight"] = f"{baseline / 100.0:.6f}"
    lines = [f"{field} {header[field]}" for field in HEADER_FIELDS if field in header]

    lines.append(f"upperleftcoords {reference.numchars}")
    for (x, y) in positions:
        lines.append(f"{x / atlas_size:.6f} {1.0 - y / atlas_size:.6f} 0")

    lines.append(f"lowerrightcoords {reference.numchars}")
    for (x, y), width in zip(positions, widths):
        lines.append(f"{(x + width) / atlas_size:.6f} "
                     f"{1.0 - (y + glyph_height) / atlas_size:.6f} 0")

    return "\n".join(lines) + "\n"


def build_font(ttf: Path, erf: Path, output: Path, resref: str, scale: float) -> tuple[int, int]:
    reference = Reference(erf, resref)
    atlas, positions, widths, glyph_height, baseline, atlas_size = render(ttf, reference, scale)
    output.mkdir(parents=True, exist_ok=True)
    write_tga(output / f"{resref}.tga", atlas.width, atlas.height, atlas.tobytes())
    (output / f"{resref}.txi").write_bytes(
        build_txi(reference, positions, widths, glyph_height, baseline, atlas_size).encode("ascii")
    )
    return glyph_height, atlas_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ttf", type=Path)
    parser.add_argument("erf", type=Path, help="TexturePacks/swpc_tex_gui.erf")
    parser.add_argument("output", type=Path)
    parser.add_argument("--fonts", nargs="*", default=["dialogfont16x16"])
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Render scale: the atlas is built at the size the text should appear")
    args = parser.parse_args()

    if not 0.5 <= args.scale <= 8.0:
        raise ValueError("Scale must be between 0.5 and 8.0")

    for resref in args.fonts:
        glyph_height, atlas_size = build_font(args.ttf, args.erf, args.output, resref, args.scale)
        print(f"{resref}: {glyph_height}px glyphs -> {atlas_size}x{atlas_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
