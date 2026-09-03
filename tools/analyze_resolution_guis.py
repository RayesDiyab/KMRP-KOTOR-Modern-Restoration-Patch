#!/usr/bin/env python3
"""Inspect KOTOR resolution GUI sets and emit map geometry as JSON.

KMRP uses the per-resolution ``map.gui`` files as the source
of truth for where the large map is drawn.  This helper keeps that derivation
auditable instead of hiding resolution-specific coordinates in the patcher.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pykotor.resource.formats.gff import read_gff


RESOLUTION_RE = re.compile(r"gui\.(\d+)x(\d+)$", re.IGNORECASE)


def extent(struct) -> dict[str, int]:
    value = struct.get_struct("EXTENT")
    return {
        "left": value.get_int32("LEFT"),
        "top": value.get_int32("TOP"),
        "width": value.get_int32("WIDTH"),
        "height": value.get_int32("HEIGHT"),
    }


def geometry(gui_path: Path) -> dict:
    root = read_gff(gui_path).root
    controls = root.get_list("CONTROLS")
    map_control = None
    for control in controls:
        if control.get_string("TAG") == "LBL_Map":
            map_control = control
            break
    if map_control is None:
        raise ValueError(f"LBL_Map was not found in {gui_path}")

    match = RESOLUTION_RE.match(gui_path.parent.name)
    if not match:
        raise ValueError(f"Resolution folder is not recognized: {gui_path.parent}")
    width, height = (int(value) for value in match.groups())
    root_extent = extent(root)
    map_extent = extent(map_control)

    # Geometry rule -- see reverse-engineering/area-map-surface.md.
    #
    # The map picture is drawn onto the CANVAS; the fog grid and markers live in
    # the MARKER OVERLAY, which is canvas * 440/512 because only 440 of the map
    # atlas's 512 columns carry picture. The remaining 72/512 is surplus, and
    # vanilla hides it by making LBL_Map exactly the overlay so the control crops
    # it. KMRP used to set canvas = screen//2 with LBL_Map inherited from k1hrm
    # (2365 px at 3440x1440, wider than the canvas), so nothing cropped and the
    # surplus showed as an unfogged 242 px strip down the right of the map.
    #
    # Instead, size the canvas so the *content* fills the frame. The frame art's
    # interior measures screen//2 (measured at 3440x1440), so:
    #
    #     overlay = screen // 2                     the visible map
    #     canvas  = overlay * 512/440               overlay + the cropped surplus
    #
    # and LBL_Map is set to the overlay, which crops the surplus. For LBL_Map to
    # crop from the canvas's own left edge the centring domains must equal the
    # screen -- canvas_left = LBL_Map.left + (screenWidth - centringX) / 2, so
    # centringX == screenWidth puts the canvas origin exactly at LBL_Map.left.
    # KOTOR's renderer adds a 14 px top inset, which LBL_Map.top absorbs.
    overlay_width = width // 2
    canvas_height = height // 2
    canvas_width = round(overlay_width * 512 / 440)
    center_x_domain = width
    center_y_domain = height
    map_control_target = {
        "left": (width - overlay_width) // 2,
        "top": (height - canvas_height) // 2 + 14,
        "width": overlay_width,
        "height": canvas_height,
    }
    render_left = map_control_target["left"]
    render_top = map_control_target["top"]

    return {
        "resolution": f"{width}x{height}",
        "aspect_folder": gui_path.parent.parent.name,
        "width": width,
        "height": height,
        "root": root_extent,
        "map_control": map_extent,
        "map_control_target": map_control_target,
        "map_canvas": {"width": canvas_width, "height": canvas_height},
        "marker_overlay": {"width": overlay_width, "height": canvas_height},
        "centering_domain": {"width": center_x_domain, "height": center_y_domain},
        "render_origin": {"left": render_left, "top": render_top},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gui_root", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()

    records = [geometry(path) for path in args.gui_root.rglob("map.gui")]
    records.sort(key=lambda item: (item["width"] / item["height"], item["width"], item["height"]))
    text = json.dumps({"schema_version": 1, "resolutions": records}, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
