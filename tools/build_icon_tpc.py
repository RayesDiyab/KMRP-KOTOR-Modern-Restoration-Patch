#!/usr/bin/env python3
"""Compress the HD item icons to DXT5 TPC at their native size.

Why this and not the menu backgrounds: the Inventory and Equipment screens are
the only two that stall, they are the only two that draw dozens of item icons,
and the stall appeared when the HD icon pack was installed. The backgrounds are
identical on every tab and every tab is otherwise fine.

What the pack costs as shipped:

    stock KOTOR   64x64 TPC, DXT compressed, about 4 KB an icon
    HD pack      192x192 TGA, uncompressed 32bpp, 144 KB an icon -- 36x

Size is NOT reduced here, and that is deliberate. `equip.gui` draws item icons
through controls whose EXTENT is exactly 192x192 (BTN_INV_HEAD, LBL_INV_BODY and
the rest), so 192 is the native size on this layout and anything smaller visibly
blurs every equipment slot. Measured against the source at 192px:

    192x192 DXT5   36.1 KB   4.0x smaller   36.3 dB
    192x192 DXT1   18.1 KB   7.9x smaller   26.5 dB
    160x160 DXT5   25.1 KB   5.7x smaller   25.8 dB
    128x128 DXT5   16.1 KB   8.9x smaller   23.9 dB

DXT5 rather than DXT1 because 58% of a sample of these icons carry gradient
alpha, which DXT1 cannot store -- it has one bit. That is the whole 10 dB gap.

TPC takes priority over TGA in the override, so the .tga files are left alone
and this is reverted by deleting the .tpc files.

Usage:
    python tools/build_icon_tpc.py OVERRIDE_DIR [--apply] [--size 192]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import io
import struct
from pathlib import Path

try:
    from PIL import Image
except ImportError:                                      # pragma: no cover
    print("Pillow is required; run this from Bash, not the PowerShell tool.")
    raise

TXI = b"mipmap 0\n"
DXT5 = 4


def build_tpc(image: Image.Image) -> bytes:
    # TPC stores its rows bottom-up, like the source TGAs (descriptor 0x08).
    # Pillow returns top-down pixels, so writing them straight out gives a
    # texture the engine draws upside down. Verified against the stock
    # ia_class4_001.tpc rather than assumed.
    image = image.transpose(Image.FLIP_TOP_BOTTOM)
    buffer = io.BytesIO()
    image.convert("RGBA").save(buffer, format="DDS", pixel_format="DXT5")
    payload = buffer.getvalue()[128:]
    width, height = image.size
    header = struct.pack("<IfHHBB", len(payload), 1.0, width, height, DXT5, 1)
    return header + b"\x00" * (128 - len(header)) + payload + TXI


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("override", type=Path)
    parser.add_argument("--size", type=int, default=192,
                        help="only convert icons of this square size")
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()

    before = after = 0
    converted = 0
    for path in sorted(arguments.override.glob("*.tga")):
        head = path.read_bytes()[:18]
        width, height, depth = struct.unpack_from("<HHB", head, 12)
        if (width, height) != (arguments.size, arguments.size):
            continue
        with Image.open(path) as source:
            blob = build_tpc(source.convert("RGBA"))
        before += path.stat().st_size
        after += len(blob)
        converted += 1
        if arguments.apply:
            path.with_suffix(".tpc").write_bytes(blob)

    if not converted:
        print(f"no {arguments.size}x{arguments.size} icons found")
        return 0
    print(f"{converted} icons at {arguments.size}x{arguments.size}")
    print(f"  {before/1048576:6.1f} MB of TGA -> {after/1048576:6.1f} MB of "
          f"DXT5 TPC  ({before/after:.1f}x smaller)")
    print(f"  {before/converted/1024:.0f} KB -> {after/converted/1024:.0f} KB "
          f"per icon")
    if not arguments.apply:
        print("\n  (dry run; pass --apply)")
    else:
        print("\n  .tga files left in place; TPC takes priority in override")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
