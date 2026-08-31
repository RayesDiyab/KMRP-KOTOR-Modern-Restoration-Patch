#!/usr/bin/env python3
"""Give every scrolling text box a resolution-scaled gutter beside its scrollbar.

A listbox's `PADDING` is a HORIZONTAL inset: the engine lays text out inside
`width - scrollbarWidth - 2*borderDimension - PADDING`, so raising it pulls the
wrap edge away from the scrollbar. **Confirmed in game** at 3440x1440 -- setting
`inventory.gui`'s `LB_DESCRIPTION` from 0 to 24 re-wrapped the description and
opened a clear gap, where `BORDER.INNEROFFSET` (tested alongside it) did nothing
at all.

Two separate vanilla defects make this necessary:

1. **BioWare set the gutter on some description boxes and not others.**
   `equip.gui LB_DESC` has 4, `computer.gui LB_MESSAGE` 3, `confirm.gui
   LB_MESSAGE` 2 -- but `inventory.gui LB_DESCRIPTION`, `journal.gui
   LBL_ITEM_DESCRIPTION`, `abilities.gui LB_DESC`, `abchrgen.gui LB_DESC`,
   `ftchrgen.gui LB_DESC` and `messages.gui LB_DIALOG` all have 0.

2. **`PADDING` is geometry that the upstream HD mod never scaled.** A vanilla
   `4`, authored against a 640-pixel-wide box at 800x600, is still `4` against a
   1403-pixel box at 3440x1440 -- proportionally a twentieth of the gutter it
   was drawn to be.

Neither matters in vanilla, where the text is small enough that lines rarely
reach the edge. Both matter once the font is enlarged. This is the cosmetic
half of the problem; the half that actually CLIPPED characters is the engine's
line-measurement underestimate, corrected by the `spacingR` wrap margin in
`prepare_universal_resources.py`. Keep both: `spacingR` stops text crossing the
edge, `PADDING` decides how far short of it text stops.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


LISTBOX_CONTROLTYPE = 11

# Gutter in pixels at font scale 1.0 (720p), scaled linearly from there. 20
# yields the 40 confirmed by play-test at 3440x1440, where the scale is 2.0.
# The earlier 12 (24px there) cleared the scrollbar but read as cramped; 40 was
# chosen in game from a 40/56/72 comparison.
GUTTER_AT_UNIT_SCALE = 20.0


def gutter_for(scale: float) -> int:
    return int(round(GUTTER_AT_UNIT_SCALE * scale))


def apply(struct, gutter: int, tags: set[str] | None, changed: list) -> None:
    if struct.acquire("CONTROLTYPE", None) == LISTBOX_CONTROLTYPE:
        tag = struct.acquire("TAG", "")
        if tags is None or tag.upper() in tags:
            # Never REDUCE a gutter an author deliberately set larger.
            current = struct.acquire("PADDING", 0) or 0
            if current < gutter:
                struct.set_int32("PADDING", gutter)
                changed.append((tag, current, gutter))
    controls = struct.acquire("CONTROLS", None)
    if controls is not None:
        for child in controls:
            apply(child, gutter, tags, changed)


def scale_listbox_padding(source: Path, dest: Path, scale: float,
                          tags: set[str] | None = None) -> list:
    gff = read_gff(source)
    changed: list = []
    apply(gff.root, gutter_for(scale), tags, changed)
    write_gff(gff, dest, ResourceType.GUI)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("--scale", type=float, required=True)
    parser.add_argument("--tags", default=None,
                        help="comma-separated listbox tags; default is every listbox")
    args = parser.parse_args()
    tags = ({t.strip().upper() for t in args.tags.split(",")}
            if args.tags else None)
    for tag, before, after in scale_listbox_padding(args.source, args.dest,
                                                    args.scale, tags):
        print(f"{tag:<24} PADDING {before} -> {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
