#!/usr/bin/env python3
"""Give HUD clusters the gold build's proportions at any resolution.

The upstream high-resolution GUI files scale the bottom-left party cluster and
the bottom-right action-button cluster consistently across resolutions (unlike
the minimap, which they freeze at its 800x600 size -- see
tools/scale_hud_minimap.py), but they scale them to different proportions than
the play-tested 3440x1440 gold layout: the party portrait is 9.5% of screen
height upstream versus 7.9% in gold, the moulding panel 16.5% versus 13.6%,
and so on. The result is a bottom HUD that is consistent with itself but
noticeably chunkier than the gold reference.

This transfers gold's proportions directly, the same way the minimap fix does:
every control is scaled by the target screen's height relative to gold's 1440
and anchored to its own corner (bottom-left cluster to the left and bottom
edges, bottom-right cluster to the right and bottom edges). Scaling by height
alone -- rather than by width, or by each axis independently -- keeps every
control's aspect ratio intact, so the artwork is never stretched, and corner
anchoring keeps the clusters tucked into the corners at any aspect ratio.

Applied to gold's own 3440x1440 values this is an exact identity.

The bottom-centre combat-queue cluster (LBL_COMBATBG*, BTN_CLEAR*, LBL_QUEUE*)
is deliberately left alone: it is centre-anchored rather than corner-anchored,
so it needs different handling and is not part of what this transfers.

The transient top-left controls need a related but distinct rule. High
Resolution Menus scales their positions and rectangles from screen width, which
makes the target/container nameplate 960 pixels wide and the XP/item/journal
icons 115 pixels square at 3840x2160. The play-tested gold HUD uses 400 and 64
at 3440x1440. They scale with KMRP's font/HUD rule instead:
``max(1, height / 720)`` relative to gold's 2x values, anchored at top-left.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


GOLD_WIDTH = 3440
GOLD_HEIGHT = 1440

BOTTOM_LEFT_TAGS = (
    "LBL_MOULDING1", "LBL_MOULDING2", "TB_PAUSE", "TB_SOLO", "TB_STEALTH",
    "LBL_BACK1", "LBL_BACK2", "LBL_BACK3",
    "LBL_CHAR1", "LBL_CHAR2", "LBL_CHAR3",
    "BTN_CHAR1", "BTN_CHAR2", "BTN_CHAR3",
    "LBL_DISABLE1", "LBL_DISABLE2", "LBL_DISABLE3",
    "LBL_DEBILATATED1", "LBL_DEBILATATED2", "LBL_DEBILATATED3",
    "LBL_LVLUPBG1", "LBL_LVLUPBG2", "LBL_LVLUPBG3",
    "LBL_LEVELUP1", "LBL_LEVELUP2", "LBL_LEVELUP3",
    "PB_VIT1", "PB_VIT2", "PB_VIT3",
    "PB_FORCE1", "PB_FORCE2", "PB_FORCE3",
    "LBL_CMBTEFCTINC1", "LBL_CMBTEFCTINC2", "LBL_CMBTEFCTINC3",
    "LBL_CMBTEFCTRED1", "LBL_CMBTEFCTRED2", "LBL_CMBTEFCTRED3",
)

BOTTOM_RIGHT_TAGS = (
    "LBL_ACTIONDESC", "LBL_ACTIONDESCBG", "LBL_MOULDING3",
    "BTN_ACTION0", "BTN_ACTION1", "BTN_ACTION2", "BTN_ACTION3",
    "LBL_ACTION0", "LBL_ACTION1", "LBL_ACTION2", "LBL_ACTION3",
    "BTN_ACTIONUP0", "BTN_ACTIONUP1", "BTN_ACTIONUP2", "BTN_ACTIONUP3",
    "BTN_ACTIONDOWN0", "BTN_ACTIONDOWN1", "BTN_ACTIONDOWN2", "BTN_ACTIONDOWN3",
)

TOP_LEFT_TRANSIENT_TAGS = (
    # Target/container name and health strip.
    "LBL_NAMEBG", "LBL_NAME", "LBL_HEALTHBG", "PB_HEALTH",
    # Short-lived feedback icons: journal, credits, XP, items, alignment.
    "LBL_JOURNAL", "LBL_CASH", "LBL_PLOTXP", "LBL_ITEMRCVD", "LBL_ITEMLOST",
    "LBL_STEALTHXP", "LBL_DARKSHIFT", "LBL_LIGHTSHIFT",
)


# The target's action buttons under the strip (2026-10-01). The engine clips the target menu
# at LBL_NAME's right edge; with the strip scaled by height and the buttons left at High
# Resolution Menus' width-scaled places, the second and third button were cut off at every size
# but 3440x1440 (a tester's 1920x1200: the strip 250 px, the buttons to 377). They are gold's
# buttons at TARGET_BUTTON_FACTOR times the strip's scale (the maintainer, at 1512x982, asked for
# them twice the size, then settled on 1.5x), and the strip widens just enough to hold them
# (target_menu_extents).
TARGET_BUTTON_FACTOR = 1.5
# The buttons start this far (in gold pixels, scaled with the strip) below the health line:
# gold's own overlap the strip, and at 1.5x their frames touched the bar (the maintainer,
# 1512x982, 2026-10-01).
TARGET_BUTTON_GAP = 8
TARGET_BUTTON_TAGS = (
    "BTN_TARGET0", "BTN_TARGET1", "BTN_TARGET2",
    "BTN_TARGETUP0", "BTN_TARGETUP1", "BTN_TARGETUP2",
    "BTN_TARGETDOWN0", "BTN_TARGETDOWN1", "BTN_TARGETDOWN2",
    "LBL_TARGET0", "LBL_TARGET1", "LBL_TARGET2",
)
TARGET_STRIP_TAGS = ("LBL_NAMEBG", "LBL_NAME", "LBL_HEALTHBG", "PB_HEALTH")


def target_menu_extents(gold: dict[str, tuple[int, int, int, int]],
                        target_height: int) -> dict[str, tuple[int, int, int, int]]:
    """The target menu at this height: the name strip at max(1, H/720) / 2 times gold, the
    buttons at TARGET_BUTTON_FACTOR times that, each strip control widened to the buttons'
    right edge where it falls short."""
    strip_scale = max(1.0, target_height / 720.0) / 2.0
    out = {tag: placed_top_left(gold[tag], strip_scale * TARGET_BUTTON_FACTOR) for tag in TARGET_BUTTON_TAGS if tag in gold}
    strip = {tag: placed_top_left(gold[tag], strip_scale) for tag in TARGET_STRIP_TAGS if tag in gold}
    if not out or not strip:
        return {**out, **strip}
    # One bar width for the whole strip: the widest of its controls (the dark bar), or the
    # buttons' span where that is wider. The engine clips the menu at LBL_NAME's right edge, so
    # the name box takes the full width too.
    first = min(left for left, _, _, _ in out.values())
    span = max(left + width for left, _, width, _ in out.values()) - first
    bar = max(max(width for _, _, width, _ in strip.values()), span)
    # The buttons centred under the bar (gold's sit 43 px from its left and 24 from its right),
    # and below the health line by the gap.
    dx = (bar - span) // 2 - first
    below = max(top + height for _, top, _, height in strip.values()) + round_half_up(TARGET_BUTTON_GAP * strip_scale)
    dy = max(0, below - min(top for _, top, _, _ in out.values()))
    out = {tag: (left + dx, top + dy, width, height) for tag, (left, top, width, height) in out.items()}
    for tag, (left, top, _, height) in strip.items():
        out[tag] = (left, top, bar, height)
    return out


def round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def walk_controls(gui):
    def walk(control):
        yield control
        children = control.get_list("CONTROLS")
        if children is not None:
            for child in children:
                yield from walk(child)

    root = gui.root.get_list("CONTROLS")
    if root is None:
        raise ValueError("GUI has no root CONTROLS list")
    for control in root:
        yield from walk(control)


def gold_extents(gold_path: Path) -> dict[str, tuple[int, int, int, int]]:
    gui = read_gff(gold_path)
    extents = {}
    for control in walk_controls(gui):
        extent = control.get_struct("EXTENT")
        if extent is None:
            continue
        extents[control.get_string("TAG")] = (
            extent.get_int32("LEFT"), extent.get_int32("TOP"),
            extent.get_int32("WIDTH"), extent.get_int32("HEIGHT"),
        )
    # Gold's first target slot has its arrows the wrong way up (BTN_TARGETUP0 at the bottom of
    # the button, BTN_TARGETDOWN0 at the top), a slip in its hand editing: the other two slots
    # and High Resolution Menus' own 3440x1440 file put the up arrow on top. Read as the other
    # slots have them.
    for slot in range(3):
        up, down = f"BTN_TARGETUP{slot}", f"BTN_TARGETDOWN{slot}"
        if up in extents and down in extents and extents[up][1] > extents[down][1]:
            (ul, ut, uw, uh), (dl, dt, dw, dh) = extents[up], extents[down]
            extents[up], extents[down] = (ul, dt, uw, uh), (dl, ut, dw, dh)
    return extents


def apply_target_menu(gold_path: Path, source: Path, output: Path, target_height: int) -> None:
    """Writes source with only its target menu laid out by target_menu_extents: for the
    3440x1440 HUD, which is gold's own file and otherwise shipped as it is (gold's arrows the
    right way up, the buttons at TARGET_BUTTON_FACTOR, centred under the bar, clear of it)."""
    menu = target_menu_extents(gold_extents(gold_path), target_height)
    gui = read_gff(source)
    for control in walk_controls(gui):
        tag = control.get_string("TAG")
        extent = control.get_struct("EXTENT")
        if tag not in menu or extent is None:
            continue
        for field, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), menu[tag], strict=True):
            extent.set_int32(field, value)
        control.set_struct("EXTENT", extent)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gui, output, ResourceType.GUI)


def placed(gold: tuple[int, int, int, int], scale: float, target_width: int,
           target_height: int, anchor_right: bool) -> tuple[int, int, int, int]:
    gold_left, gold_top, gold_width, gold_height = gold
    width = round_half_up(gold_width * scale)
    height = round_half_up(gold_height * scale)
    if anchor_right:
        margin = round_half_up((GOLD_WIDTH - gold_left - gold_width) * scale)
        left = target_width - margin - width
    else:
        left = round_half_up(gold_left * scale)
    bottom_margin = round_half_up((GOLD_HEIGHT - gold_top - gold_height) * scale)
    top = target_height - bottom_margin - height
    return (left, top, width, height)


def placed_top_left(gold: tuple[int, int, int, int], scale: float) -> tuple[int, int, int, int]:
    return tuple(round_half_up(value * scale) for value in gold)


def apply_proportions(gold_path: Path, source: Path, output: Path,
                      target_width: int, target_height: int) -> int:
    gold = gold_extents(gold_path)
    gui = read_gff(source)
    bottom_scale = target_height / GOLD_HEIGHT
    transient_scale = max(1.0, target_height / 720.0) / 2.0
    target_menu = target_menu_extents(gold, target_height)
    changed = 0

    for control in walk_controls(gui):
        tag = control.get_string("TAG")
        anchor_right = tag in BOTTOM_RIGHT_TAGS
        transient = tag in TOP_LEFT_TRANSIENT_TAGS
        if not anchor_right and tag not in BOTTOM_LEFT_TAGS and not transient and tag not in target_menu:
            continue
        if tag not in gold:
            continue
        extent = control.get_struct("EXTENT")
        if extent is None:
            continue
        values = (target_menu[tag] if tag in target_menu else
                  placed_top_left(gold[tag], transient_scale) if transient else
                  placed(gold[tag], bottom_scale, target_width, target_height, anchor_right))
        for field, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), values, strict=True):
            extent.set_int32(field, value)
        control.set_struct("EXTENT", extent)
        changed += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gui, output, ResourceType.GUI)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gold", type=Path, help="Gold 3440x1440 mipc210x7.gui reference")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("resolution", help="Target resolution, e.g. 1920x1080")
    args = parser.parse_args()

    width, height = (int(value) for value in args.resolution.split("x"))
    changed = apply_proportions(args.gold, args.source, args.output, width, height)
    print(f"Wrote {args.output} ({changed} controls repositioned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
