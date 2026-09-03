#!/usr/bin/env python3
"""Scale the hex icon-frame textures that list rows draw behind item icons.

The Inventory / Abilities / Store row classes draw their icon frame as a
**tiled fill**, not a stretched image. The stock art is 56x56 -- exactly the
vanilla row icon box -- so one tile fills the box and the tiling is invisible.

Once the row/icon constants are scaled (see `RowSizeGroups` in
`KmrpPatcher.cs` and `reverse-engineering/inventory-item-rows.md`),
the box no longer matches the art: at 1440p the box is 112px and the 56px frame
tiles **2x2, drawing four borders per row**. Observed in game, and the reason
this module exists. Intermediate scales are worse, not better -- 1.5x leaves a
half tile.

The fix is to ship the frame art at the same size the box is, per resolution, so
it stays exactly one tile. These are therefore resolution-dependent and must NOT
go in the shared common archive.

`lbl_hex_7` and plain `lbl_hex` are not in the project's Override set at all --
they come from the game's own texture pack -- but they are drawn by the same row
classes, so they are extracted and scaled here too. Leaving them behind would
tile them exactly the way this fixes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc

from build_scaled_fonts import write_tga


# Every hex frame referenced by the row-drawing code (found by xref on the
# resref strings at 0x00755EBC / 0x00756778 / 0x00756784).
FRAME_RESREFS = ("lbl_hex", "lbl_hex_3", "lbl_hex_6", "lbl_hex_7")

# The vanilla row icon box, and the native size of this art. Keep in step with
# the gold values in RowSizeGroups.
NATIVE_SIZE = 56


def resize_rgba(pixels: bytes, width: int, height: int,
                new_width: int, new_height: int) -> bytes:
    """Bilinear resize of a top-down RGBA buffer. Pure stdlib on purpose.

    The build runs under a PowerShell-launched interpreter that cannot see a
    Bash-installed Pillow, so image work here has to be hand-rolled -- the same
    constraint documented for the font pipeline in `docs/font-scaling.md`.
    """
    if (new_width, new_height) == (width, height):
        return pixels
    out = bytearray(new_width * new_height * 4)
    x_ratio = width / new_width
    y_ratio = height / new_height
    for y in range(new_height):
        # Sample at pixel centres so the result stays centred rather than
        # drifting half a texel towards the origin.
        sy = (y + 0.5) * y_ratio - 0.5
        y0 = max(0, min(height - 1, int(sy)))
        y1 = min(height - 1, y0 + 1)
        wy = sy - y0
        if wy < 0:
            wy = 0.0
        for x in range(new_width):
            sx = (x + 0.5) * x_ratio - 0.5
            x0 = max(0, min(width - 1, int(sx)))
            x1 = min(width - 1, x0 + 1)
            wx = sx - x0
            if wx < 0:
                wx = 0.0
            i00 = (y0 * width + x0) * 4
            i01 = (y0 * width + x1) * 4
            i10 = (y1 * width + x0) * 4
            i11 = (y1 * width + x1) * 4
            o = (y * new_width + x) * 4
            for c in range(4):
                top = pixels[i00 + c] * (1 - wx) + pixels[i01 + c] * wx
                bot = pixels[i10 + c] * (1 - wx) + pixels[i11 + c] * wx
                out[o + c] = int(top * (1 - wy) + bot * wy + 0.5)
    return bytes(out)


def export_frames(erf_path: Path, output_dir: Path, scale: float) -> list[Path]:
    """Write every hex frame at `NATIVE_SIZE * scale`. Returns the paths."""
    target = max(1, int(round(NATIVE_SIZE * scale)))
    erf = read_erf(erf_path)
    wanted = {name: None for name in FRAME_RESREFS}
    for resource in erf:
        name = str(resource.resref).lower()
        if name in wanted and wanted[name] is None:
            wanted[name] = resource.data

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, data in wanted.items():
        if data is None:
            raise ValueError(f"{name} is missing from {erf_path}")
        tpc = read_tpc(data)
        tpc.convert(TPCTextureFormat.RGBA)
        mip = tpc.get(0)
        stride = mip.width * 4
        # A decoded TPC's first row is the image's BOTTOM; write_tga expects
        # top-down input and flips it back (see font-atlases.md, format fact 6).
        top_down = b"".join(mip.data[y * stride:(y + 1) * stride]
                            for y in range(mip.height - 1, -1, -1))
        scaled = resize_rgba(top_down, mip.width, mip.height, target, target)
        path = output_dir / f"{name}.tga"
        write_tga(path, target, target, scaled)
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("texture_pack", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, required=True)
    args = parser.parse_args()
    for path in export_frames(args.texture_pack, args.output, args.scale):
        print(f"{path.name:<16} {int(round(NATIVE_SIZE * args.scale))}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
