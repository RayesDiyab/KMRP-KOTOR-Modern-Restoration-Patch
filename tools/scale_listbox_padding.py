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
# spaces the level-up popup's rows (row + row / 11, in integers).
ROW_GAP_DIVISOR = 11
ROW_GAP = 1 / ROW_GAP_DIVISOR


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


# Lists whose rows are sized in code, not by a template: their list is made as
# tall as whole rows instead. Rows at round(base * s), as resolution_sizes.cpp
# and the Windows patcher's RowSizeGroups scale them; a list shown on more than
# one tab holds more than one kind.
#   popup   the list sits in a popup whose panel art stretches to its extent: the
#           controls below the list move with its bottom, and the panel grows or
#           shrinks about its centre. Fitted at every size, to the rows that fit
#           now. For the Container, one row more (5 at 3024x1964, the panel 166 px
#           taller) was tried in play against the 4 that fit and declined
#           (2026-09-30).
#   screen  a full-screen menu drawn over fixed art: only the list's height
#           changes, and only where the engine's gap is looser than LOOSE_GAP.
# Measured 2026-09-30 over the 66 sets (engine gap as a share of the row, what
# the inventory keeps under 12.5% everywhere):
#   container.gui LB_ITEMS   22% at 3024x1964 (4 rows of 153, 34 px), over 13% in 64 sets
#   skillinfo.gui LB_SKILLS  22% at 3024x1964 (4 rows of 115, 26 px), over 13% in 64 sets
#   ftchrgen.gui LB_FEATS    14% at 3024x1964 (7 rows of 136, 19 px), up to 18%
#   and, below 1024x768 and at 1920x540 only: abilities, store, equip, upgrade
#   items, level-up powers.
# The Abilities list serves the Skills tab and the Feats and Powers tabs at one
# height. With skill rows at 42s and chain rows at 50s, one tab stayed loose in 11
# of the 66 sets (Skills gaps of 8 to 11 px, 18 to 21% of a row, from 800x600 to
# 1470x956; Feats and Powers 10 px at 1920x540 and 1024x576), and fitting either
# would have taken a row off the other. First accepted as it was, then (the
# maintainer's choice, 2026-09-30, the same day) the skill rows were scaled from
# 50 like the chain rows (resolution_sizes.cpp, RowSizeGroups), so the one list
# fits all three tabs. Also in the granted popup, which shows skill rows.
ROW_LISTS = {
    ("container.gui", "LB_ITEMS"): ("popup", (56,)),      # store/container row
    ("skillinfo.gui", "LB_SKILLS"): ("popup", (50,)),     # skill row (the granted popup)
    ("ftchrgen.gui", "LB_FEATS"): ("screen", (50,)),      # feat chain row
    ("pwrlvlup.gui", "LB_POWERS"): ("screen", (50,)),     # power chain row
    ("abilities.gui", "LB_ABILITY"): ("screen", (50,)),   # Skills, Feats and Powers tabs
    ("store.gui", "LB_INVITEMS"): ("screen", (56,)),
    ("store.gui", "LB_SHOPITEMS"): ("screen", (56,)),
    ("equip.gui", "LB_ITEMS"): ("screen", (56,)),
    ("upgradeitems.gui", "LB_ITEMS"): ("screen", (56,)),
}
# A full-screen list is left alone up to the loosest the inventory gets.
LOOSE_GAP = 1 / 8


def _extent(struct) -> list[int]:
    e = struct.get_struct("EXTENT")
    return [e.get_int32(k) for k in ("LEFT", "TOP", "WIDTH", "HEIGHT")]


def _set_extent(struct, values) -> None:
    e = struct.get_struct("EXTENT")
    for key, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), values):
        e.set_int32(key, value)
    struct.set_struct("EXTENT", e)


def fit_list_to_rows(source: Path, dest: Path, screen_height: int, tag: str,
                     bases: tuple[int, ...], popup: bool) -> int:
    """Make `tag` as tall as whole rows, each an eleventh of a row (row //
    ROW_GAP_DIVISOR, as granted_popup.cpp spaces them) from the next, and return
    the change in height (0: left alone, nothing written).

    The Mac installer redoes this on a blended set (macos/tools/kmrp-guiblend.c,
    fit_rows), from each set's "fitted" manifest line: keep the two in step.

    Each kind of row keeps the count the engine fits now; a list with several
    kinds takes the tallest of their fits, so none loses a row. A full-screen list (`popup` false) is changed only when a kind's gap is
    looser than LOOSE_GAP, and only made shorter.
    """
    gff = read_gff(source)
    root = gff.root
    controls = root.get_list("CONTROLS")
    target = next((c for c in controls if c.acquire("TAG", "").upper() == tag.upper()), None)
    if target is None:
        raise ValueError(f"{source.name}: no {tag}")
    left, top, width, height = _extent(target)
    border = 2 * target.get_struct("BORDER").get_int32("DIMENSION")
    inner = height - border
    fits, loose = [], False
    for base in bases:
        row = row_height(base, screen_height)
        rows = inner // row
        if rows < 1:
            raise ValueError(f"{source.name} {tag}: no {row}-px row fits {inner} px")
        loose |= (inner - (inner // row) * row) // (inner // row) > row * LOOSE_GAP
        fits.append(rows * (row + row // ROW_GAP_DIVISOR))
    new_inner = max(fits)
    change = new_inner - inner
    if change == 0 or (not popup and (not loose or change > 0)):
        return 0
    _set_extent(target, [left, top, width, height + change])
    if target.exists("SCROLLBAR"):
        bar = target.get_struct("SCROLLBAR")
        values = _extent(bar)
        values[3] += change
        _set_extent(bar, values)
        target.set_struct("SCROLLBAR", bar)
    if popup:
        bottom = top + height
        for control in controls:
            if control is not target and _extent(control)[1] >= bottom:
                values = _extent(control)
                values[1] += change
                _set_extent(control, values)
        panel = _extent(root)
        panel[1] -= change // 2
        panel[3] += change
        _set_extent(root, panel)
    root.set_list("CONTROLS", controls)
    write_gff(gff, dest, ResourceType.GUI)
    return change


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
