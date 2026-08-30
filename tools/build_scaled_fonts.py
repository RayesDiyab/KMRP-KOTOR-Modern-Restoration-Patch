#!/usr/bin/env python3
"""Export KOTOR's font atlases with their metrics pre-scaled in the TXI.

KOTOR stores each font as a TPC texture atlas whose embedded TXI block carries
both the glyph layout (`numchars`, and per-glyph `upperleftcoords` /
`lowerrightcoords` as normalised UVs) and five metric fields that control the
rendered size:

    fontheight  baselineheight  texturewidth  spacingR  spacingB

The executable font-scale patch (tools/build_font_scale_wrapper.py) multiplies
those same five fields at runtime, lazily, the first time each CAurFontInfo is
drawn. That turned out to be a frame too late: the engine measures and centres
text using the very same fields, so on the FIRST draw after launch the layout
was computed from unscaled metrics while the glyphs rendered at the new size --
visibly shifting the loading screen's hint text. Every later load found the
font already scaled (the patch caches which instances it has touched), so the
problem appeared exactly once per session. Confirmed by playtest: with the
executable's scale set to 1.0, the shift disappears.

Scaling the metrics here instead -- in the asset the engine loads -- means the
values are already correct before anything measures them, so layout and
rendering can never disagree and no runtime mutation is needed at all.

Fonts are written as `.tga` + `.txi` pairs for the Override folder, which take
precedence over the packed `.tpc` originals. The glyph UV coordinates are
copied through untouched, so this is purely a metric change; it composes with
(and is a prerequisite for) replacing the atlas artwork with higher-resolution
renders, since the UVs stay valid at any texture size.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc


# Every font atlas the GUI can reference, from swpc_tex_gui.erf.
FONT_RESREFS = (
    "dialogfont10x10", "dialogfont10x10a", "dialogfont10x10b",
    "dialogfont12x16", "dialogfont16x16", "dialogfont16x16a",
    "dialogfont16x16b", "dialogfont32x32",
    "fnt_console", "fnt_credits", "fnt_creditsa", "fnt_creditsb",
    "fnt_d10x10b", "fnt_d16x16", "fnt_d16x16a", "fnt_d16x16b",
    "fnt_dialog16x16", "fnt_galahad14",
)

SCALED_FIELDS = ("fontheight", "baselineheight", "texturewidth", "spacingR", "spacingB")

# The game's own font TGAs are uncompressed 32-bit, bottom-up (descriptor 0x08),
# with BGRA pixel order. pykotor's TGA writer emits top-down (0x28) instead, so
# the bytes are written directly here to match the shipped assets exactly.
TGA_DESCRIPTOR = 0x08


def raw_txi(tpc_bytes: bytes) -> str:
    """Return the TXI text exactly as stored, without reparsing it.

    pykotor exposes a *reconstructed* TXI: it silently drops commands it does
    not model (e.g. `compresstexture`) and reorders others, which produces a
    file the engine chokes on. The TXI is a trailing block of printable ASCII,
    so it is recovered here by walking back from the end of the resource.
    """
    end = len(tpc_bytes)
    start = end
    while start > 0:
        byte = tpc_bytes[start - 1]
        if byte in (0x09, 0x0A, 0x0D) or 0x20 <= byte <= 0x7E:
            start -= 1
            continue
        break
    text = tpc_bytes[start:end].decode("ascii")
    if "numchars" not in text:
        raise ValueError("Could not locate the TXI block in this atlas")
    return text


def write_tga(path: Path, width: int, height: int, rgba: bytes) -> None:
    """Write uncompressed 32-bit BGRA TGA in the game's own bottom-up layout."""
    header = struct.pack(
        "<BBBHHBHHHHBB",
        0, 0, 2,      # no id field, no colour map, uncompressed true-colour
        0, 0, 0,      # colour map spec
        0, 0,         # x/y origin
        width, height,
        32, TGA_DESCRIPTOR,
    )
    stride = width * 4
    rows = []
    for y in range(height - 1, -1, -1):  # bottom-up
        row = bytearray(rgba[y * stride:(y + 1) * stride])
        row[0::4], row[2::4] = row[2::4], row[0::4]  # RGBA -> BGRA
        rows.append(bytes(row))
    path.write_bytes(header + b"".join(rows))


def scale_txi(txi: str, scale: float) -> str:
    """Multiply the five metric fields, leaving glyph coordinates untouched.

    The coordinate blocks that follow `upperleftcoords` / `lowerrightcoords`
    are bare number triples, so parsing stops at the first coordinate header to
    avoid rewriting anything inside them.
    """
    lines = txi.splitlines()
    output: list[str] = []
    in_coords = False
    for line in lines:
        head = line.strip().split(" ", 1)[0].lower()
        if head in ("upperleftcoords", "lowerrightcoords"):
            in_coords = True
        if not in_coords:
            parts = line.split()
            if len(parts) == 2 and parts[0] in SCALED_FIELDS:
                output.append(f"{parts[0]} {float(parts[1]) * scale:g}")
                continue
        output.append(line)
    return "\n".join(output) + "\n"


def export_fonts(erf_path: Path, output_dir: Path, scale: float, textures: bool = True) -> list[Path]:
    """Write scaled `.txi` files, and optionally the `.tga` atlases beside them.

    **A standalone `.txi` in Override does NOT take effect.** With the artwork
    still inside the packed `.tpc`, the engine uses that file's own embedded
    metrics and the scaled `.txi` is ignored -- text simply never changes size.
    Playtested: shipping only the `.txi` for 17 of the 18 fonts left every menu
    at stock size. The unmodified atlas has to be written beside it for the
    override to win, so pass `textures=True` unless the caller is supplying its
    own artwork for that resref.
    """
    erf = read_erf(erf_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    seen: set[str] = set()
    wanted = {name.lower() for name in FONT_RESREFS}

    for resource in erf:
        name = str(resource.resref).lower()
        if name not in wanted:
            continue
        original = bytes(resource.data)
        if textures:
            tpc = read_tpc(original)
            tpc.convert(TPCTextureFormat.RGBA)
            mipmap = tpc.get(0)
            tga = output_dir / f"{name}.tga"
            # A decoded TPC's first row is the BOTTOM of the image, while
            # write_tga takes top-down input (it reverses what it is given to
            # produce the game's bottom-up file layout). Handing it the TPC rows
            # untouched mirrors the atlas vertically, so every glyph lookup lands
            # on the wrong row and all text renders as unreadable symbols.
            # Verified by rendering 'A' out of the result: only bottom-up source
            # rows, read back with an inverted v, form the letter.
            stride = mipmap.width * 4
            pixels = bytes(mipmap.data)
            top_down = b"".join(
                pixels[y * stride:(y + 1) * stride]
                for y in range(mipmap.height - 1, -1, -1)
            )
            write_tga(tga, mipmap.width, mipmap.height, top_down)
            written.append(tga)
        txi = output_dir / f"{name}.txi"
        txi.write_bytes(scale_txi(raw_txi(original), scale).encode("ascii"))
        written.append(txi)
        seen.add(name)

    missing = sorted(wanted - seen)
    if missing:
        raise ValueError(f"Font atlases not found in {erf_path}: {', '.join(missing)}")
    return written


def export_font_txis(erf_path: Path, output_dir: Path, scale: float) -> list[Path]:
    """Metric-only export: the `.txi` files, without replacing any artwork."""
    return export_fonts(erf_path, output_dir, scale, textures=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("erf", type=Path, help="TexturePacks/swpc_tex_gui.erf")
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, required=True)
    parser.add_argument("--txi-only", action="store_true",
                        help="Write only the metric files, leaving the packed artwork in place")
    args = parser.parse_args()

    if not 0.1 <= args.scale <= 8.0:
        raise ValueError("Scale must be between 0.1 and 8.0")
    written = export_fonts(args.erf, args.output, args.scale, textures=not args.txi_only)
    print(f"Wrote {len(written)} files to {args.output} at scale {args.scale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
