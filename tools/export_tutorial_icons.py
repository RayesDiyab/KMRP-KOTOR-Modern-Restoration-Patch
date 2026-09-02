#!/usr/bin/env python3
"""Export the tutorial popup's icons at this resolution's icon-rect size.

The message popup's icon control is created in code with a square rect
(`0x00626F94`), and the engine draws GUI textures **one texel per pixel**. So the
rect and the texture must be the same size:

* a texture SMALLER than the rect **tiles** -- at rect 64 a 32x32 icon draws as
  four copies, confirmed in play;
* a texture LARGER than the rect is **cropped**.

The rect is scaled per resolution by `ResolutionPatch` (`PopupSizeGroups` in
`KotorUniversalPatcher.cs`), so these textures are **resolution-dependent** and
must ship in `gui-<res>.zip`, never in the shared archive -- the same rule the
hex row frames follow, and for the same reason.

**Eight of the thirteen source textures are shared.** `i_attack` is a feat icon
`scale_ability_icons.py` sizes for the Abilities rows, and the seven `lbl_i*` are
HUD status icons KMRP ships in `override-common.zip`. Enlarging those in place
would break them everywhere else they appear, so the popup gets private copies
under a `tut_` prefix and `tutorial.2da` is repointed at them
(`assets/override-common/tutorial.2da`). Nothing else in the game changes.

Sources are read from the **stock texture pack**, deliberately not through an
`Installation`: the game's Override holds KMRP's own scaled copies of those same
seven HUD icons, so an Installation lookup re-reads our output and compounds its
scaling. From the pack they are a clean 32x32 (six) and 64x64 (seven).

Nearest-neighbour on exact multiples, bilinear otherwise -- these are small,
hard-edged HUD glyphs with flat colour and a 1px outline, and smooth filtering
turns them to mush. Same reasoning as `scale_ability_icons.py`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc

from build_scaled_fonts import write_tga
from scale_row_icon_frames import resize_rgba


# Original resref -> the popup's private copy. Must stay in step with the `icon`
# column of assets/override-common/tutorial.2da, which names the right-hand side.
ICON_RENAMES = {
    "lbl_icn_abi3": "tut_abi3",
    "lbl_icn_char3": "tut_char3",
    "lbl_icn_inv3": "tut_inv3",
    "lbl_icn_map3": "tut_map3",
    "lbl_icn_msg3": "tut_msg3",
    "i_attack": "tut_attack",
    "lbl_icredits": "tut_credits",
    "lbl_idside": "tut_dside",
    "lbl_ilside": "tut_lside",
    "lbl_iplotxp": "tut_plotxp",
    "lbl_iquest": "tut_quest",
    "lbl_ireceive": "tut_receive",
    "lbl_itaken": "tut_taken",
}

# The icon rect at scale 1.0. ResolutionPatch scales the in-executable rect by
# the same rule, so these must move together -- see PopupSizeGroups.
NATIVE_SIZE = 64


def nearest_rgba(pixels: bytes, width: int, height: int, factor: int) -> bytes:
    """Integer nearest-neighbour upscale of a top-down RGBA buffer."""
    out = bytearray()
    row_bytes = width * 4
    for y in range(height):
        row = pixels[y * row_bytes:(y + 1) * row_bytes]
        wide = bytearray()
        for x in range(width):
            wide += row[x * 4:(x + 1) * 4] * factor
        out += bytes(wide) * factor
    return bytes(out)


def export_tutorial_icons(erf_path: Path, output_dir: Path, scale: float) -> list[Path]:
    """Write every tutorial icon at `NATIVE_SIZE * scale`. Returns the paths."""
    target = max(1, int(round(NATIVE_SIZE * scale)))
    erf = read_erf(erf_path)
    wanted: dict[str, bytes | None] = {name: None for name in ICON_RENAMES}
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
        if mip.width == mip.height and target % mip.width == 0:
            scaled = nearest_rgba(top_down, mip.width, mip.height, target // mip.width)
        else:
            scaled = resize_rgba(top_down, mip.width, mip.height, target, target)
        path = output_dir / f"{ICON_RENAMES[name]}.tga"
        write_tga(path, target, target, scaled)
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("texture_pack", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, required=True)
    args = parser.parse_args()
    for path in export_tutorial_icons(args.texture_pack, args.output, args.scale):
        print(f"{path.name:<16} {int(round(NATIVE_SIZE * args.scale))}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
