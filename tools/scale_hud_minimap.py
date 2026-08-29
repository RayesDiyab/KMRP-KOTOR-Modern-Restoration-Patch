#!/usr/bin/env python3
"""Scale KOTOR's gameplay minimap viewport for high-resolution HUDs.

The upstream high-resolution GUI files scale the HUD root and most controls,
but leave LBL_MAPVIEW at 120x120 and LBL_MAPBORDER at 136x137 for every
resolution.  That is acceptable through 1440 pixels of vertical resolution,
but becomes progressively smaller at 2160p and above.

LBL_MAP is deliberately left untouched.  It is the engine-owned 512x256 map
surface whose retail-sized domain prevents the vertical texture-wrap
duplication bug.  Only the visible viewport and its decorative border scale.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


BASE_HEIGHT = 1440
# These are the final, play-tested 3440x1440 gold HUD values rather than the
# undersized upstream defaults (120x120 and 136x137).
BASE_VIEW = (2, 2, 270, 270)
BASE_BORDER = (0, 0, 276, 276)
BASE_BUTTON = (2, 2, 272, 270)


def round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def scaled_extents(screen_height: int) -> dict[str, tuple[int, int, int, int]]:
    scale = max(1.0, screen_height / BASE_HEIGHT)
    view_size = round_half_up(BASE_VIEW[2] * scale)
    effective_scale = view_size / BASE_VIEW[2]
    return {
        "LBL_MAPVIEW": (
            round_half_up(BASE_VIEW[0] * effective_scale),
            round_half_up(BASE_VIEW[1] * effective_scale),
            view_size,
            view_size,
        ),
        "LBL_MAPBORDER": tuple(
            round_half_up(value * effective_scale) for value in BASE_BORDER
        ),
        "BTN_MINIMAP": tuple(
            round_half_up(value * effective_scale) for value in BASE_BUTTON
        ),
    }


def patch_gui(source: Path, output: Path, screen_height: int) -> bool:
    gui = read_gff(source)
    targets = scaled_extents(screen_height)
    found: set[str] = set()

    controls = gui.root.get_list("CONTROLS")
    if controls is None:
        raise ValueError(f"{source} has no root CONTROLS list")

    for control in controls:
        tag = control.get_string("TAG")
        if tag not in targets:
            continue
        extent = control.get_struct("EXTENT")
        if extent is None:
            raise ValueError(f"{source}: {tag} has no EXTENT")
        for field, value in zip(
            ("LEFT", "TOP", "WIDTH", "HEIGHT"), targets[tag], strict=True
        ):
            extent.set_int32(field, value)
        control.set_struct("EXTENT", extent)
        found.add(tag)

    missing = set(targets) - found
    if missing:
        raise ValueError(f"{source}: missing minimap controls {sorted(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gui, output, ResourceType.GUI)
    return source.read_bytes() != output.read_bytes()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("screen_height", type=int)
    args = parser.parse_args()
    changed = patch_gui(args.source, args.output, args.screen_height)
    print(f"Wrote {args.output} ({'changed' if changed else 'unchanged'})")
    for tag, values in scaled_extents(args.screen_height).items():
        print(f"{tag}: {values}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
