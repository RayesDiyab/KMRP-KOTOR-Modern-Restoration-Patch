#!/usr/bin/env python3
"""Restore stock clipping extents for the enlarged 3440x1440 HUD minimap."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


TARGET_EXTENTS = {
    "LBL_MAPVIEW": (6, 6, 120, 120),
    "LBL_MAPBORDER": (-2, -3, 136, 137),
}


def patch_controls(struct, found: set[str]) -> None:
    tag = struct.get_string("TAG")
    if tag in TARGET_EXTENTS:
        extent = struct.get_struct("EXTENT")
        if extent is None:
            raise ValueError(f"{tag} has no EXTENT")
        for field, value in zip(
            ("LEFT", "TOP", "WIDTH", "HEIGHT"), TARGET_EXTENTS[tag], strict=True
        ):
            extent.set_int32(field, value)
        struct.set_struct("EXTENT", extent)
        found.add(tag)

    controls = struct.get_list("CONTROLS")
    if controls is not None:
        for child in controls:
            patch_controls(child, found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be separate")

    gff = read_gff(args.source)
    found: set[str] = set()
    patch_controls(gff.root, found)
    missing = set(TARGET_EXTENTS) - found
    if missing:
        raise ValueError(f"Missing controls: {sorted(missing)}")
    write_gff(gff, args.output, ResourceType.GUI)

    print(f"Wrote {args.output}")
    print(f"SHA-256: {hashlib.sha256(args.output.read_bytes()).hexdigest().upper()}")
    for tag, values in TARGET_EXTENTS.items():
        print(f"{tag}: {values}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
