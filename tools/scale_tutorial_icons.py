#!/usr/bin/env python3
"""Normalise the tutorial popup's icons to the size of its icon rect.

The message popup's icon control is created in code with a 32x32 rect
(`0x00626F94`), and the engine draws GUI textures **one texel per pixel** -- the
same rule the fonts and ability icons hit. So the rect and the texture must be
the same size:

* a texture SMALLER than the rect **tiles** -- at rect 64 a 32x32 icon draws as
  four copies, confirmed in play;
* a texture LARGER than the rect is **cropped** -- which is what vanilla does
  today to the 48x48 and 64x64 icons sitting in a 32px rect.

`tutorial.2da`'s `icon` column names 13 distinct textures across its 43 rows, and
they are not one size: five `lbl_icn_*3` at 32x32 (only in the GUI texture pack),
seven at 48x48, and `i_attack` at 64x64. This normalises every one to a single
edge so a larger rect shows exactly one icon whatever the row selects.

Nearest-neighbour on exact multiples, deliberately: these are small, hard-edged
HUD glyphs with flat colour and a 1px outline, and smooth filtering turns them to
mush -- the same reasoning as `scale_ability_icons.py`. Non-multiples fall back
to Lanczos because there is no integer option.

TGAs are written bottom-up with descriptor 0x08, matching every asset the game
ships; pykotor emits 0x28 and a loader that ignores the origin bit reads that
upside down (see `build_padded_minimap_atlases.py`).
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image

from pykotor.extract.installation import Installation
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc
from pykotor.resource.formats.twoda import read_2da
from pykotor.resource.type import ResourceType


def write_tga(path: Path, pixels: np.ndarray) -> None:
    """Uncompressed 32-bit TGA, bottom-up, as the game's own assets are."""
    height, width = pixels.shape[:2]
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 0x08)
    bgra = pixels[..., [2, 1, 0, 3]]
    path.write_bytes(header + bgra[::-1].tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", type=int, default=64,
                        help="edge every icon is normalised to; must equal the icon rect")
    args = parser.parse_args()

    if not 32 <= args.size <= 256:
        raise SystemExit("--size must be 32..256")

    inst = Installation(str(args.game))
    table = read_2da(inst.resource("tutorial", ResourceType.TwoDA).data)
    names = sorted({str(r.get_string("icon") or "").strip().lower()
                    for r in table
                    if str(r.get_string("icon") or "").strip() not in ("", "****")})
    print(f"{len(names)} distinct tutorial icons")

    # The lbl_icn_*3 icons live only in the GUI texture pack, which the
    # Installation lookup does not cover.
    pack = read_erf(args.game / "TexturePacks" / "swpc_tex_gui.erf")
    from_pack = {r.resref.get().lower(): r.data for r in pack}

    args.output.mkdir(parents=True, exist_ok=True)
    written = 0
    sizes: dict[tuple[int, int], int] = {}
    for name in names:
        res = inst.resource(name, ResourceType.TPC) or inst.resource(name, ResourceType.TGA)
        data = res.data if res is not None else from_pack.get(name)
        if data is None:
            print(f"  {name:22s} NOT FOUND, skipped")
            continue
        tpc = read_tpc(data)
        tpc.convert(TPCTextureFormat.RGBA)
        mip = tpc.get()
        px = np.frombuffer(mip.data, np.uint8).reshape(mip.height, mip.width, 4)
        sizes[(mip.width, mip.height)] = sizes.get((mip.width, mip.height), 0) + 1

        if args.size == mip.width == mip.height:
            out, how = px, "unchanged"
        elif args.size % mip.width == 0 and args.size % mip.height == 0:
            factor = args.size // mip.width
            out, how = px.repeat(factor, axis=0).repeat(factor, axis=1), f"nearest x{factor}"
        else:
            out = np.asarray(Image.fromarray(px).resize((args.size, args.size), Image.LANCZOS))
            how = "lanczos"

        write_tga(args.output / f"{name}.tga", out)
        print(f"  {name:22s} {mip.width}x{mip.height} -> {args.size}x{args.size}  ({how})")
        written += 1

    print()
    print("source sizes: " + ", ".join(f"{w}x{h} x{n}" for (w, h), n in sorted(sizes.items())))
    print(f"wrote {written} icons to {args.output}")
    print(f"Pair with build_message_popup_size.py --icon-size {args.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
