#!/usr/bin/env python3
"""Scale the feat and Force-power icons drawn inside ability chain rows.

The Abilities screen's Powers and Feats tabs draw each feat/power as an icon
inside a chain-row slot. Read live under x32dbg at 3440x1440:

    frame (border) rect   {0, 0, 80, 80}      <- scales with the row height
    icon control rect     {2, 2, 76, 76}      <- also scales
    icon texture          i_2weap01, 32x32    <- does NOT

The icon *box* grows with the row, but the artwork is drawn at the texture's
native size, so enlarging the rows leaves a small icon floating in a big frame.
This is the same one-texel-per-pixel behaviour documented for the fonts and for
`lbl_hex_3` in `font-atlases.md`.

**Both prefixes matter.** Feats are `i_*` (148 textures at 32x32) and powers are
`ip_*` (52 at 32x32). An earlier attempt scaled only `ip_*` and appeared to do
nothing, because the Feats tab -- the obvious place to look -- was untouched.
The 64x64 variants the game already ships are left alone.

**Why 64 and not the box size.** The source art is 32x32. Upscaling beyond 2x
adds no detail, only blur, and the cost is steep: shipping box-sized icons for
every resolution would add 120-300 MB to the patcher, against 63 MB at 64px.
64px was confirmed in play at 3440x1440. Above roughly a 64px box the icons stop
growing; that is a limit of the source artwork, not of this code.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc

from build_scaled_fonts import write_tga
from scale_row_icon_frames import resize_rgba


NATIVE = 32
MAX_SIZE = 64          # 2x the source; beyond this is blur, see docstring
FEAT_ROW_BASE = 50     # must match the feat/power group in RowSizeGroups
ICON_INSET = 4         # icon control is the row height minus this (read live)


def icon_size_for(scale: float) -> int:
    """Icon edge in pixels: the row's icon box, capped at MAX_SIZE."""
    box = int(round(FEAT_ROW_BASE * scale)) - ICON_INSET
    return max(NATIVE, min(box, MAX_SIZE))


def export_ability_icons(erf_path: Path, output_dir: Path, scale: float) -> list[Path]:
    target = icon_size_for(scale)
    if target == NATIVE:
        return []                      # vanilla art already fits; ship nothing
    erf = read_erf(erf_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for resource in erf:
        name = str(resource.resref).lower()
        if not (name.startswith("i_") or name.startswith("ip_")):
            continue
        try:
            tpc = read_tpc(resource.data)
            tpc.convert(TPCTextureFormat.RGBA)
            mip = tpc.get(0)
        except Exception:
            continue
        if (mip.width, mip.height) != (NATIVE, NATIVE):
            continue               # the 64x64 originals are already big enough
        stride = mip.width * 4
        # A decoded TPC's first row is the image's BOTTOM; write_tga wants top-down.
        top_down = b"".join(mip.data[y * stride:(y + 1) * stride]
                            for y in range(mip.height - 1, -1, -1))
        path = output_dir / f"{name}.tga"
        write_tga(path, target, target,
                  resize_rgba(top_down, mip.width, mip.height, target, target))
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("texture_pack", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, required=True)
    args = parser.parse_args()
    paths = export_ability_icons(args.texture_pack, args.output, args.scale)
    print(f"{len(paths)} ability icons at {icon_size_for(args.scale)}px "
          f"(scale {args.scale:g})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
