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
import struct
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


LISTBOX_CONTROLTYPE = 11

# Gutter in pixels at font scale 1.0 (720p), scaled linearly from there. 36
# yields the 72 confirmed by play-test at 3440x1440, where the scale is 2.0.
# Chosen in game from a 40/56/72 comparison against the original 12 (24px there),
# which cleared the scrollbar but read as cramped.
GUTTER_AT_UNIT_SCALE = 36.0

# Selection lists want a much smaller gutter than description panes: it sits
# beside an icon column rather than a paragraph, and 25px at 3440x1440 was
# chosen in game. This only became usable once the exe stopped tying three other
# effects to the same byte -- see tools/build_listbox_padding_fix.py. Before that
# patch, PADDING on a multi-row list also spaced the rows apart, inset the right
# edge and pushed the first row down, which is why these tags were excluded.
LIST_GUTTER_AT_UNIT_SCALE = 12.5

# Everything else -- message logs, text-only selection lists -- gets a small
# baseline so no box renders text hard against its frame. These were previously
# left at their authored values (often 0: messages.gui LB_DIALOG, LB_MESSAGES 5,
# computer/confirm LB_MESSAGE 2-3), on the reasoning that a paragraph-sized
# gutter beside a wall of short lines reads as a broken margin. That is right
# about 72px and wrong about zero, so they get their own much smaller tier
# rather than an exclusion. Applied with tags=None, and `apply` never reduces a
# gutter, so the 72 and 25 tiers set before it stand.
BASELINE_GUTTER_AT_UNIT_SCALE = 10.0

# The HUD's combat action queue. These are listboxes, but of icons, not text:
# a gutter would shift the queue rather than open a margin. They appear in the
# mipc*.gui HUD variants (not mipc210x7, which has none) and are the only
# non-text listboxes the baseline pass would otherwise reach.
BASELINE_EXCLUDED = {f"LB_ACTIONS{i}" for i in range(6)}


def list_gutter_for(scale: float) -> int:
    return int(round(LIST_GUTTER_AT_UNIT_SCALE * scale))


def gutter_for(scale: float) -> int:
    return int(round(GUTTER_AT_UNIT_SCALE * scale))


def apply(struct, gutter: int, tags: set[str] | None, changed: list,
          exclude: set[str] | None = None, force: bool = False) -> None:
    if struct.acquire("CONTROLTYPE", None) == LISTBOX_CONTROLTYPE:
        tag = struct.acquire("TAG", "")
        if (tags is None or tag.upper() in tags) and not (
                exclude and tag.upper() in exclude):
            # Never REDUCE a gutter an author deliberately set larger -- unless
            # `force`, which is how a value hand-set on a specific gold file
            # overrides a broader tier applied before it. Without that escape the
            # broader tier silently wins and the hand-set value is lost: equip.gui
            # LB_DESC was hand-set to 20 and the 72 description tier kept it at 72,
            # with nothing reported, because 20 < 72.
            current = struct.acquire("PADDING", 0) or 0
            if force or current < gutter:
                if current != gutter:
                    struct.set_int32("PADDING", gutter)
                    changed.append((tag, current, gutter))
    controls = struct.acquire("CONTROLS", None)
    if controls is not None:
        for child in controls:
            apply(child, gutter, tags, changed, exclude, force)


def scale_listbox_padding(source: Path, dest: Path, scale: float,
                          tags: set[str] | None = None,
                          unit_gutter: float | None = None,
                          exclude: set[str] | None = None,
                          force: bool = False) -> list:
    """Set the gutter on `tags` (every listbox when None) for this scale.

    `unit_gutter` overrides GUTTER_AT_UNIT_SCALE, so selection lists can take a
    smaller gutter than description panes in a second pass over the same file.
    """
    gutter = (gutter_for(scale) if unit_gutter is None
              else int(round(unit_gutter * scale)))
    gff = read_gff(source)
    changed: list = []
    apply(gff.root, gutter, tags, changed, exclude, force)
    write_gff(gff, dest, ResourceType.GUI)
    return changed


# Script Selection's option list, and the box its background art draws around
# it. The frame is not a control: it is part of lbl_char_scr.tpc, one 2868x1436
# texture shared by every resolution and stretched across the whole screen, so
# its lines sit at fixed fractions of the screen WIDTH. Read from the texture on
# 2026-09-24: the left box's left line at x 300..305, its right line at 1409.
# Measured against a 3440x1440 screenshot the same day: 361 and 1688 there,
# against 363 and 1690 from these fractions.
SCRIPTSELECT_FRAME = (302.5 / 2868, 1409 / 2868)


def centre_rows_in_frame(source: Path, dest: Path, screen_width: int, tag: str,
                         frame: tuple[float, float]) -> int:
    """Set a left-scrollbar list's PADDING so its rows sit centred in `frame`.

    Since gold v12 a list with `LEFTSCROLLBAR` lays its rows out from
    `list.left + scrollbarWidth + PADDING` to `list.left + list.width`: PADDING
    moves the left edge only. Script Selection shipped PADDING 2, so its rows
    started 12px outside the art's frame on the left while stopping 17px inside
    it on the right (3440x1440, reported 2026-09-24). This picks the PADDING
    that gives both sides the same margin, from this resolution's own list
    geometry. The row prototypes are not touched -- see
    Test-GeneratedGuiGeometry.py for why they must not be.
    """
    gff = read_gff(source)
    target = None
    for control in gff.root.get_list("CONTROLS"):
        if control.acquire("TAG", "").upper() == tag.upper():
            target = control
    if target is None:
        raise ValueError(f"{source.name}: no {tag}")
    extent = target.get_struct("EXTENT")
    left, width = extent.get_int32("LEFT"), extent.get_int32("WIDTH")
    bar = target.get_struct("SCROLLBAR").get_struct("EXTENT").get_int32("WIDTH")
    frame_left, frame_right = (f * screen_width for f in frame)
    rows_right = left + width
    padding = int(round(frame_left + frame_right - rows_right - left - bar))
    # A byte in the engine, and validated against half the content width.
    padding = max(0, min(padding, 255, (width - bar) // 2 - 1))
    target.set_int32("PADDING", padding)
    write_gff(gff, dest, ResourceType.GUI)
    return padding


# The journal's quest list, spaced as the inventory is. A list box shares the
# height its visible rows leave over between them (CSWGuiListBox::
# OrganizeControls: 0x0041B140 on Windows, 0x1004A82B4 on the Mac):
#     inner = height - 2 * BORDER.DIMENSION,  n = inner // row,
#     gap   = (inner - n * row) // n
# A quest row is the list's PROTOITEM height times the row scale s = max(1, H/720)
# (the .kfs hook at 0x00417992; on the Mac CSWGuiButton::Initialize, in
# macos/patches/kmrp-layout/resolution_sizes.cpp), rounded half to even.
# Upstream's template is 78 at every size, twice vanilla's 39, so four rows fit
# and each gap is 22% of a row: 47 px under 213-px rows at 3024x1964, 25 under
# 117 at 1920x1080. The inventory's gaps are 8 to 10% of its rows (15 under 153
# at 3024x1964), and vanilla's journal showed six rows 2 px apart at 640x480.
# Reported from play at 3024x1964, 2026-09-30.
JOURNAL_ROWS = 6
# Of a row: the inventory's gap, as macos/patches/kmrp-layout/granted_popup.cpp
# spaces the level-up popup's rows.
ROW_GAP = 1 / 11


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def row_height(template: int, height: int) -> int:
    """A template row's height on screen at a screen `height`: the template times
    the row scale, both single precision, rounded half to even, as the Mac module
    and the Windows x87 code compute it (ResolutionPatch.ScaleForHeight)."""
    scale = max(1.0, _f32(height / 720.0))
    return round(_f32(_f32(template) * scale))


def fit_rows_to_list(source: Path, dest: Path, screen_height: int, tag: str,
                     rows: int) -> tuple[int, int, int]:
    """Size `tag`'s row template so `rows` rows fill the list, each ROW_GAP of a
    row from the next, and return (template, row on screen, gap on screen).

    The largest template whose rows leave at least ROW_GAP of a row between them.
    Only PROTOITEM's HEIGHT changes; its LEFT, TOP and WIDTH are left as upstream
    ships them (Test-GeneratedGuiGeometry.py, check_list_prototypes).
    """
    gff = read_gff(source)
    controls = gff.root.get_list("CONTROLS")
    target = next((c for c in controls if c.acquire("TAG", "").upper() == tag.upper()), None)
    if target is None:
        raise ValueError(f"{source.name}: no {tag}")
    inner = (target.get_struct("EXTENT").get_int32("HEIGHT")
             - 2 * target.get_struct("BORDER").get_int32("DIMENSION"))
    scale = max(1.0, _f32(screen_height / 720.0))
    fits = lambda t: row_height(t, screen_height) * rows * (1 + ROW_GAP) <= inner
    template = int(inner / (rows * (1 + ROW_GAP)) / scale)
    while not fits(template):
        template -= 1
    while fits(template + 1):
        template += 1
    row = row_height(template, screen_height)
    if inner // row != rows:
        raise ValueError(f"{source.name} {tag}: {inner} px fits {inner // row} rows of {row}, "
                         f"not {rows}")
    proto = target.get_struct("PROTOITEM")
    extent = proto.get_struct("EXTENT")
    extent.set_int32("HEIGHT", template)
    proto.set_struct("EXTENT", extent)
    target.set_struct("PROTOITEM", proto)
    gff.root.set_list("CONTROLS", controls)
    write_gff(gff, dest, ResourceType.GUI)
    return template, row, (inner - rows * row) // rows



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("--scale", type=float, required=True)
    parser.add_argument("--tags", default=None,
                        help="comma-separated listbox tags; default is every listbox")
    parser.add_argument("--unit-gutter", type=float, default=None,
                        help=f"pixels at scale 1.0 (default {GUTTER_AT_UNIT_SCALE}; "
                             f"selection lists ship {LIST_GUTTER_AT_UNIT_SCALE})")
    args = parser.parse_args()
    tags = ({t.strip().upper() for t in args.tags.split(",")}
            if args.tags else None)
    for tag, before, after in scale_listbox_padding(args.source, args.dest,
                                                    args.scale, tags,
                                                    args.unit_gutter):
        print(f"{tag:<24} PADDING {before} -> {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
