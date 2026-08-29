#!/usr/bin/env python3
"""Build the corrected 3440x1440 gameplay HUD GUI.

The large-map HUD layout has three independent defects:

* LBL_MAP is 512x512 although KOTOR module maps use a 512x256 surface,
  allowing the texture to wrap vertically in the minimap.
* LBL_MAPBORDER begins at negative coordinates, clipping its top and left.
* The party panel was reduced to unusually small controls.  The normal 10:7
  HUD uses the intended party-panel scale at the same 3440x1440 root size.

Only control extents are changed; textures, text, IDs, and control types are
retained from the large-minimap source GUI.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


PARTY_TAGS = {
    "LBL_MOULDING1",
    "LBL_MOULDING2",
    "LBL_BACK1",
    "LBL_BACK2",
    "LBL_BACK3",
    *(f"PB_VIT{index}" for index in range(1, 4)),
    *(f"PB_FORCE{index}" for index in range(1, 4)),
    *(f"LBL_CHAR{index}" for index in range(1, 4)),
    *(f"LBL_DISABLE{index}" for index in range(1, 4)),
    *(f"LBL_DEBILATATED{index}" for index in range(1, 4)),
    *(f"LBL_LVLUPBG{index}" for index in range(1, 4)),
    *(f"LBL_LEVELUP{index}" for index in range(1, 4)),
    *(f"LBL_CMBTEFCTRED{index}" for index in range(1, 4)),
    *(f"LBL_CMBTEFCTINC{index}" for index in range(1, 4)),
    *(f"BTN_CHAR{index}" for index in range(1, 4)),
}


def controls_by_tag(root) -> dict[str, object]:
    controls = root.get_list("CONTROLS")
    if controls is None:
        raise ValueError("GUI root has no CONTROLS list")
    result = {}
    for control in controls:
        tag = control.get_string("TAG")
        if tag:
            if tag in result:
                raise ValueError(f"Duplicate top-level control tag: {tag}")
            result[tag] = control
    return result


def extent_tuple(control) -> tuple[int, int, int, int]:
    extent = control.get_struct("EXTENT")
    if extent is None:
        raise ValueError(f"{control.get_string('TAG')} has no EXTENT")
    return tuple(extent.get_int32(name) for name in ("LEFT", "TOP", "WIDTH", "HEIGHT"))


def copy_extent(target, source) -> None:
    source_extent = source.get_struct("EXTENT")
    target_extent = target.get_struct("EXTENT")
    if source_extent is None or target_extent is None:
        raise ValueError("Cannot copy a missing EXTENT")
    for name in ("LEFT", "TOP", "WIDTH", "HEIGHT"):
        target_extent.set_int32(name, source_extent.get_int32(name))
    target.set_struct("EXTENT", target_extent)


def set_extent(control, values: tuple[int, int, int, int]) -> None:
    extent = control.get_struct("EXTENT")
    if extent is None:
        raise ValueError(f"{control.get_string('TAG')} has no EXTENT")
    for name, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), values, strict=True):
        extent.set_int32(name, value)
    control.set_struct("EXTENT", extent)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("large_minimap_source", type=Path)
    parser.add_argument("normal_party_source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.resolve() in {
        args.large_minimap_source.resolve(),
        args.normal_party_source.resolve(),
    }:
        raise ValueError("Output must be separate from both source files")

    gui = read_gff(args.large_minimap_source)
    party_gui = read_gff(args.normal_party_source)
    target_controls = controls_by_tag(gui.root)
    party_controls = controls_by_tag(party_gui.root)

    if extent_tuple(gui.root) != (0, 0, 3440, 1440):
        raise ValueError(f"Unexpected target root extent: {extent_tuple(gui.root)}")
    if extent_tuple(party_gui.root) != (0, 0, 3440, 1440):
        raise ValueError(f"Unexpected party root extent: {extent_tuple(party_gui.root)}")
    if extent_tuple(target_controls["LBL_MAP"]) != (6, 6, 512, 512):
        raise ValueError(f"Unexpected LBL_MAP extent: {extent_tuple(target_controls['LBL_MAP'])}")
    if extent_tuple(target_controls["LBL_MAPBORDER"]) != (-6, -6, 278, 276):
        raise ValueError(
            f"Unexpected LBL_MAPBORDER extent: {extent_tuple(target_controls['LBL_MAPBORDER'])}"
        )

    missing = PARTY_TAGS - target_controls.keys() | PARTY_TAGS - party_controls.keys()
    if missing:
        raise ValueError(f"Missing party controls: {sorted(missing)}")

    set_extent(target_controls["LBL_MAP"], (6, 6, 512, 256))
    set_extent(target_controls["LBL_MAPBORDER"], (0, 0, 278, 276))
    for tag in sorted(PARTY_TAGS):
        copy_extent(target_controls[tag], party_controls[tag])

    write_gff(gui, args.output, ResourceType.GUI)
    print(f"Wrote {args.output}")
    print(f"SHA-256: {hashlib.sha256(args.output.read_bytes()).hexdigest().upper()}")
    print("LBL_MAP: 512x512 -> 512x256")
    print("LBL_MAPBORDER: (-6,-6) -> (0,0)")
    print(f"Party controls restored: {len(PARTY_TAGS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
