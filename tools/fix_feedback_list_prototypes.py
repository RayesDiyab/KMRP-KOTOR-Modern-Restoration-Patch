#!/usr/bin/env python3
"""Repair stale embedded list-row geometry in reported full-screen GUIs.

KOTOR High Resolution Menus scales the two listbox controls and their
scrollbars, but leaves each listbox's PROTOITEM at its original 640x480
coordinates and 240-pixel width. At 3840x2160 this strands the option rows near
the left edge and makes both option and description text lay out in a narrow
vanilla-width rectangle.

The parent listbox and scrollbar already describe the intended pane. Anchor the
prototype at the parent's top edge, put it on the content side of the scrollbar,
and extend it to the opposite edge. Height is deliberately untouched: KMRP's
runtime list-row hook scales constructed row heights with the font.
``scriptselect.gui`` has the same defect in ``LST_AIState`` and ``LB_DESC`` and
uses the same repair.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


FEEDBACK_TARGETS = {"LB_OPTIONS", "LB_DESC"}
SCRIPTSELECT_TARGETS = {"LST_AIState", "LB_DESC"}


def get_extent(control):
    extent = control.get_struct("EXTENT")
    if extent is None:
        raise ValueError("control has no EXTENT")
    return extent


def fix_prototypes(source: Path, output: Path, targets: set[str], context: str) -> bool:
    gui = read_gff(source)
    found: set[str] = set()

    for control in gui.root.get_list("CONTROLS") or []:
        tag = control.get_string("TAG")
        if tag not in targets:
            continue
        parent = get_extent(control)
        proto = control.get_struct("PROTOITEM")
        scrollbar = control.get_struct("SCROLLBAR")
        if proto is None or scrollbar is None:
            raise ValueError(f"{source}: {tag} is missing PROTOITEM or SCROLLBAR")

        proto_extent = get_extent(proto)
        scroll_extent = get_extent(scrollbar)
        parent_left = parent.get_int32("LEFT")
        parent_top = parent.get_int32("TOP")
        parent_right = parent_left + parent.get_int32("WIDTH")
        scroll_left = scroll_extent.get_int32("LEFT")
        scroll_right = scroll_left + scroll_extent.get_int32("WIDTH")
        if scroll_right <= parent_left or scroll_left >= parent_right:
            raise ValueError(
                f"{source}: {tag} scrollbar lies outside its parent; "
                "run the gold-geometry transfer first"
            )

        if scroll_left <= parent_left + parent.get_int32("WIDTH") // 2:
            content_left = scroll_right
            content_right = parent_right
        else:
            content_left = parent_left
            content_right = scroll_left
        if content_right <= content_left:
            raise ValueError(f"{source}: {tag} has no content area beside its scrollbar")

        proto_extent.set_int32("LEFT", content_left)
        proto_extent.set_int32("TOP", parent_top)
        proto_extent.set_int32("WIDTH", content_right - content_left)
        proto.set_struct("EXTENT", proto_extent)
        control.set_struct("PROTOITEM", proto)
        found.add(tag)

    missing = targets - found
    if missing:
        raise ValueError(f"{source}: missing {context} listboxes {sorted(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gui, output, ResourceType.GUI)
    return source.read_bytes() != output.read_bytes()


def fix_feedback_prototypes(source: Path, output: Path) -> bool:
    return fix_prototypes(source, output, FEEDBACK_TARGETS, "feedback")


def fix_scriptselect_prototypes(source: Path, output: Path) -> bool:
    return fix_prototypes(source, output, SCRIPTSELECT_TARGETS, "script selection")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    changed = fix_feedback_prototypes(args.source, args.output)
    print(f"Wrote {args.output} ({'changed' if changed else 'unchanged'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
