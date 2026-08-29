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

# LBL_MAPBORDER (the blue frame ring, texture lbl_minimap.tga) and BTN_MINIMAP
# (the click target) are positioned RELATIVE TO LBL_MAPVIEW in the gold build:
# the frame sits just a couple of pixels outside the map content. The upstream
# high-resolution GUI files instead keep LBL_MAPVIEW and LBL_MAPBORDER frozen at
# their 800x600 values (120x120 and 136x137) for every resolution, which leaves
# the frame a full 8px away from the map content on each side -- ~6.7% of the
# view's size, versus ~0.7% in gold. That dead space inside the ring is what
# reads in game as an oversized blue border around a too-small map.
#
# So rather than freezing or independently scaling these, derive both from
# whatever LBL_MAPVIEW the file actually has, using gold's own offsets scaled by
# the view's size relative to gold's. Applied to the gold values themselves this
# formula is an identity, and for screens above BASE_HEIGHT it reproduces the
# previous proportional-scaling behaviour exactly (e.g. at 2160p: view 405,
# border 414, button 408x405), so only resolutions at or below BASE_HEIGHT --
# where the frozen upstream values were wrong -- actually change.
BORDER_DELTA = tuple(BASE_BORDER[i] - BASE_VIEW[i] for i in range(4))  # (-2, -2, +6, +6)
BUTTON_DELTA = tuple(BASE_BUTTON[i] - BASE_VIEW[i] for i in range(4))  # ( 0,  0, +2,  0)


def round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def derive_extents(view: tuple[int, int, int, int]) -> dict[str, tuple[int, int, int, int]]:
    """Place LBL_MAPBORDER and BTN_MINIMAP around a given LBL_MAPVIEW."""
    factor = view[2] / BASE_VIEW[2]
    return {
        "LBL_MAPVIEW": view,
        "LBL_MAPBORDER": tuple(
            round_half_up(view[i] + BORDER_DELTA[i] * factor) for i in range(4)
        ),
        "BTN_MINIMAP": tuple(
            round_half_up(view[i] + BUTTON_DELTA[i] * factor) for i in range(4)
        ),
    }


def scaled_view(screen_height: int) -> tuple[int, int, int, int]:
    """The LBL_MAPVIEW to use: gold's, scaled to this screen's height.

    The minimap keeps the same share of screen height at every resolution
    (gold's 270px on a 1440px-tall screen, i.e. 18.75%). Upstream instead
    freezes it at the 800x600 value of 120x120 everywhere, which is only 11.1%
    of a 1080p screen -- noticeably smaller than the play-tested gold HUD.
    """
    scale = screen_height / BASE_HEIGHT
    view_size = round_half_up(BASE_VIEW[2] * scale)
    effective_scale = view_size / BASE_VIEW[2]
    return (
        round_half_up(BASE_VIEW[0] * effective_scale),
        round_half_up(BASE_VIEW[1] * effective_scale),
        view_size,
        view_size,
    )


def scaled_extents(screen_height: int) -> dict[str, tuple[int, int, int, int]]:
    return derive_extents(scaled_view(screen_height))


# Always-visible HUD icons that sit to the right of the minimap. (The target
# name bar and BTN_TARGET* reticles also share that corner but only appear while
# something is targeted, and overlap them even in the gold build, so they are not
# treated as obstacles.) On a screen that is narrow relative to its height --
# 1280x1080 is the one stock entry that qualifies -- a height-proportional
# minimap would grow underneath these, so it gets clamped to stay clear.
GUARD_TAGS = (
    "LBL_JOURNAL", "LBL_CASH", "LBL_PLOTXP", "LBL_ITEMRCVD", "LBL_ITEMLOST",
    "LBL_STEALTHXP", "LBL_DARKSHIFT", "LBL_LIGHTSHIFT", "LBL_CMBTMSGBG",
)
GUARD_MARGIN = 8


def clamp_view(view: tuple[int, int, int, int], guard_left: int | None) -> tuple[int, int, int, int]:
    """Shrink the view if its border would reach the icons to its right."""
    if guard_left is None:
        return view
    # border_right == view.left + view.width * (1 + border_width_delta_share)
    factor = 1 + (BORDER_DELTA[2] + BORDER_DELTA[0]) / BASE_VIEW[2]
    limit = guard_left - GUARD_MARGIN
    if view[0] + view[2] * factor <= limit:
        return view
    size = int((limit - view[0]) / factor)
    if size < 1:
        return view
    effective_scale = size / BASE_VIEW[2]
    return (
        round_half_up(BASE_VIEW[0] * effective_scale),
        round_half_up(BASE_VIEW[1] * effective_scale),
        size,
        size,
    )


def guard_left_edge(gui) -> int | None:
    lefts = [
        control.get_struct("EXTENT").get_int32("LEFT")
        for control in gui.root.get_list("CONTROLS")
        if control.get_string("TAG") in GUARD_TAGS and control.get_struct("EXTENT") is not None
    ]
    return min(lefts) if lefts else None


def read_view(gui, source: Path) -> tuple[int, int, int, int]:
    for control in gui.root.get_list("CONTROLS"):
        if control.get_string("TAG") == "LBL_MAPVIEW":
            extent = control.get_struct("EXTENT")
            return (
                extent.get_int32("LEFT"), extent.get_int32("TOP"),
                extent.get_int32("WIDTH"), extent.get_int32("HEIGHT"),
            )
    raise ValueError(f"{source}: no LBL_MAPVIEW control")


def patch_gui(source: Path, output: Path, screen_height: int) -> bool:
    gui = read_gff(source)
    controls = gui.root.get_list("CONTROLS")
    if controls is None:
        raise ValueError(f"{source} has no root CONTROLS list")

    targets = derive_extents(clamp_view(scaled_view(screen_height), guard_left_edge(gui)))
    found: set[str] = set()

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
