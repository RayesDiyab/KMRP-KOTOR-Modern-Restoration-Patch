#!/usr/bin/env python3
"""Clip the HUD minimap surface to one native 512x256 map tile.

KOTOR's HUD pans the LBL_MAP control behind LBL_MAPVIEW.  Ultrawide GUI
packages commonly leave LBL_MAP at 512x512 even though module map images use
a 512x256 render domain.  Near the lower edge of a map that exposes a second,
vertically tiled copy.  This diagnostic changes only LBL_MAP's height.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


def patch_map_surface(struct, found: list[tuple[int, int]]) -> None:
    if struct.get_string("TAG") == "LBL_MAP":
        extent = struct.get_struct("EXTENT")
        if extent is None:
            raise ValueError("LBL_MAP has no EXTENT")
        width = extent.get_int32("WIDTH")
        height = extent.get_int32("HEIGHT")
        if width != 512 or height != 512:
            raise ValueError(f"Unexpected LBL_MAP size: {width}x{height}")
        extent.set_int32("HEIGHT", 256)
        struct.set_struct("EXTENT", extent)
        found.append((width, height))

    controls = struct.get_list("CONTROLS")
    if controls is not None:
        for child in controls:
            patch_map_surface(child, found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be separate")

    gff = read_gff(args.source)
    found: list[tuple[int, int]] = []
    patch_map_surface(gff.root, found)
    if found != [(512, 512)]:
        raise ValueError(f"Expected exactly one LBL_MAP, found {len(found)}")
    write_gff(gff, args.output, ResourceType.GUI)

    print(f"Wrote {args.output}")
    print(f"SHA-256: {hashlib.sha256(args.output.read_bytes()).hexdigest().upper()}")
    print("LBL_MAP: 512x512 -> 512x256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
