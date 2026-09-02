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
seven HUD status icons, and `i_attack`.

**Eight of the thirteen are shared.** `i_attack` is a feat icon that
`scale_ability_icons.py` already sizes for the Abilities chain rows, and the
seven `lbl_i*` are HUD status icons KMRP ships in `override-common.zip`.
Enlarging those in place would break them everywhere else they appear. So this
writes the scaled copies under a **new prefix** and rewrites `tutorial.2da`'s
`icon` column to point at them -- the popup gets big icons and nothing else in
the game changes.

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
    # No row flip. TPC pixel rows already run bottom-up, and descriptor 0x08
    # is bottom-up too, so reversing them writes the image upside down --
    # exactly what AbilityIconGenerator.cs notes: "TPC pixel rows run
    # bottom-up, and so does the TGA we write, so no [flip]". Seen in play
    # as upside-down tutorial icons.
    path.write_bytes(header + bgra.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", type=int, default=128,
                        help="edge every icon is normalised to; must equal the icon rect")
    parser.add_argument("--prefix", default="tut_",
                        help="resref prefix for the popup's private copies (16 char limit)")
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
    renamed: dict[str, str] = {}
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

        new_name = args.prefix + name.replace("lbl_icn_", "").replace("lbl_i", "").replace("i_", "")
        if len(new_name) > 16:
            raise SystemExit(f"resref {new_name!r} exceeds the 16 character limit")
        renamed[name] = new_name
        write_tga(args.output / f"{new_name}.tga", out)
        print(f"  {name:22s} {mip.width}x{mip.height} -> {args.size}x{args.size}"
              f"  ({how})  as {new_name}")
        written += 1

    print()
    print("source sizes: " + ", ".join(f"{w}x{h} x{n}" for (w, h), n in sorted(sizes.items())))
    print(f"wrote {written} icons to {args.output}")
    # Rewrite the 2DA so only the popup uses the enlarged copies.
    from pykotor.resource.formats.twoda import write_2da
    for row in table:
        cur = str(row.get_string("icon") or "").strip().lower()
        if cur in renamed:
            row.set_string("icon", renamed[cur])
    write_2da(table, args.output / "tutorial.2da", ResourceType.TwoDA)
    print(f"wrote tutorial.2da repointed at the {args.prefix}* copies")
    print(f"Pair with build_message_popup_size.py --icon-size {args.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
