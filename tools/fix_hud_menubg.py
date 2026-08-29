#!/usr/bin/env python3
"""Fix the HUD top-right button row's background panel (LBL_MENUBG).

Vanilla KOTOR's LBL_MENUBG (the dark background behind the row of 8 top-right
HUD buttons: BTN_EQU, BTN_INV, BTN_CHAR, BTN_ABI, BTN_MSG, BTN_JOU, BTN_MAP,
BTN_OPT) is sized a few pixels too short to fully contain the buttons -- at
800x600 the buttons overhang the background by 2px top and bottom; at
1920x1080 the same proportional mistake overhangs by 4px. This is present in
literally every mipc*.gui variant at every resolution (confirmed at 800x600,
1920x1080, and even the hand-corrected 3440x1440 gold reference, where the
background falls 1px short on the right and 2px short on the bottom), so it's
an original vanilla/upstream authoring imprecision, not something introduced
by this project or specific to one resolution.

Rather than hand-fixing each resolution's file independently (fragile, 48+
files, and any future upstream update would reintroduce it), this computes
the button row's actual bounding box from whichever file is being processed
and resizes LBL_MENUBG to fully contain it plus a small fixed margin --
correct by construction, at any resolution or aspect ratio.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


BUTTON_TAGS = (
    "BTN_EQU", "BTN_INV", "BTN_CHAR", "BTN_ABI",
    "BTN_MSG", "BTN_JOU", "BTN_MAP", "BTN_OPT",
)
MARGIN_X = 4
MARGIN_Y = 0


def fix_menubg(gui) -> bool:
    controls = gui.root.get_list("CONTROLS")
    if controls is None:
        raise ValueError("GUI has no root CONTROLS list")

    bounds: dict[str, tuple[int, int, int, int]] = {}
    menubg = None
    for control in controls:
        tag = control.get_string("TAG")
        if tag in BUTTON_TAGS:
            extent = control.get_struct("EXTENT")
            bounds[tag] = (
                extent.get_int32("LEFT"), extent.get_int32("TOP"),
                extent.get_int32("WIDTH"), extent.get_int32("HEIGHT"),
            )
        elif tag == "LBL_MENUBG":
            menubg = control

    missing = set(BUTTON_TAGS) - set(bounds)
    if missing:
        raise ValueError(f"Missing button controls: {sorted(missing)}")
    if menubg is None:
        raise ValueError("Missing LBL_MENUBG control")

    left = min(v[0] for v in bounds.values()) - MARGIN_X
    top = min(v[1] for v in bounds.values()) - MARGIN_Y
    right = max(v[0] + v[2] for v in bounds.values()) + MARGIN_X
    bottom = max(v[1] + v[3] for v in bounds.values()) + MARGIN_Y

    extent = menubg.get_struct("EXTENT")
    old = (extent.get_int32("LEFT"), extent.get_int32("TOP"), extent.get_int32("WIDTH"), extent.get_int32("HEIGHT"))
    new = (left, top, right - left, bottom - top)
    if old == new:
        return False
    extent.set_int32("LEFT", new[0])
    extent.set_int32("TOP", new[1])
    extent.set_int32("WIDTH", new[2])
    extent.set_int32("HEIGHT", new[3])
    menubg.set_struct("EXTENT", extent)
    return True


def fix_menubg_file(source: Path, output: Path) -> bool:
    gui = read_gff(source)
    changed = fix_menubg(gui)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gui, output, ResourceType.GUI)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    changed = fix_menubg_file(args.source, args.output)
    print(f"Wrote {args.output} ({'changed' if changed else 'unchanged'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
