#!/usr/bin/env python3
"""The mouse and keyboard HUD's layout: where each of its controls goes, as a table.

Until 2026-10-18 the PC HUD stood wherever the layout file the game loaded put it:
KMRP's own `mipc*.gui` for each screen size, or another widescreen mod's. Since then
KMRP's module places the HUD itself, the way the Xbox-style HUD has been placed since
2026-10-05 (tools/build_xbox_hud.py): from a table, for the screen the game is really
drawing, whichever file was loaded (the maintainer's direction, 2026-10-18: "draw it
like the current controller GUI ... so it's compatible with any other widescreen
mods"). The file still gives the controls their art and fonts; only their places come
from here. And each part of the HUD can then be made larger or smaller about its
corner of the screen (the HUD Size page, K1HudOptions.cpp).

The table is read from KMRP's HUD at 3440x1440, `assets/override-3440x1440/mipc210x7.gui`,
the one HUD file corrected by hand (tools/prepare_universal_resources.py says so), with
the three changes the packager makes to it before it ships, made here by the packager's
own functions: the target menu's slots one and a half times larger, centred under the
name and below it (apply_gold_hud_proportions.target_menu_extents; the first slot's
arrows the right way up, gold_extents), the action description three lines tall
(action_description_extents), and the combat-mode message 1120 wide
(prepare_universal_resources.COMBAT_MESSAGE_WIDTHS). So at 3440x1440 the HUD is placed
exactly as the game loads it today (compared with the file in the running game's cache
on 2026-10-18: every rectangle the same). On another screen a length is
scaled by the screen's height over 1440, and each piece keeps its scaled distance from
the screen's edges that its part of the HUD belongs to: the menu buttons from the top
right corner, the minimap from the top left, the action bar from the bottom right, the
portraits from the bottom left, the combat queue and its Disengage button from the
middle of the bottom edge. Nothing depends on the screen's shape.

Two groups are not on the screen but inside something that moves: the target's menu
(its name, health bar and three action slots), which the engine draws at the target,
in its own coordinates; and the two combat-effect arrows of each portrait, which the
engine keeps relative to the portrait (CSWGuiMainInterfaceChar::Initialize,
0x006898A0). Those are scaled from their own origin.

Usage:
    python tools/build_pc_hud.py            write the table
    python tools/build_pc_hud.py --check    exit 1 if the table on disk is stale

Needs pykotor (run with plain `python`, not `python -I`).

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import sys
from fnmatch import fnmatchcase
from pathlib import Path

from pykotor.resource.formats.gff import read_gff

from apply_gold_hud_proportions import action_description_extents, gold_extents, target_menu_extents
from prepare_universal_resources import COMBAT_MESSAGE_TAGS, COMBAT_MESSAGE_WIDTHS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "override-3440x1440" / "mipc210x7.gui"
TABLE = ROOT / "src" / "controller-native" / "K1PcHudLayout.inc"
BASE_W, BASE_H = 3440, 1440

# The parts of the HUD, numbered as KmrpHudOptions::Element (K1HudOptionsPolicy.h).
MENU, MINIMAP, ACTIONS, PORTRAITS, ATTACK, DISENGAGE = range(6)
NONE = -1           # placed with the screen, never sized by a slider

# How a piece is anchored (K1PcHudLayout.h, PcAnchor).
TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT, BOTTOM_CENTRE, MENU_SPACE, CHAR_SPACE = range(7)
ANCHOR_NAMES = ["kPcTopLeft", "kPcTopRight", "kPcBottomLeft", "kPcBottomRight", "kPcBottomCentre",
                "kPcMenuSpace", "kPcCharSpace"]

# What a piece is besides a control (K1PcHudLayout.h, flags).
WINDOW = 1          # LBL_MAPVIEW: the rectangle the map is drawn in, not a control the HUD keeps
ARROW = 2           # LBL_ARROW: the player's arrow, centred in the map's window by the engine
FOLLOW = 4          # moves with the minimap's right edge, at the screen's scale only
PREVIEW = 8         # drawn by the HUD Size page's preview

# Each part's controls by tag (fnmatch patterns). The preview draws the ones marked so:
# the HUD as it usually shows, not the notices, effects and states that come and go.
PARTS = [
    (MENU, TOP_RIGHT, ["BTN_EQU", "BTN_INV", "BTN_CHAR", "BTN_ABI", "BTN_MSG", "BTN_JOU", "BTN_MAP", "BTN_OPT",
                       "LBL_MENUBG"], True),
    (MINIMAP, TOP_LEFT, ["LBL_MAPBORDER", "BTN_MINIMAP", "LBL_MAPVIEW", "LBL_ARROW"], True),
    # The notices beside the minimap (CSWGuiMainInterfaceStatus: journal, credits, XP,
    # items, alignment): the engine moves them with the minimap in combat mode
    # (ShowActionQueue, 0x006874C0), so they are part of it.
    (MINIMAP, TOP_LEFT, ["LBL_JOURNAL", "LBL_CASH", "LBL_PLOTXP", "LBL_STEALTHXP", "LBL_ITEMRCVD",
                         "LBL_ITEMLOST", "LBL_DARKSHIFT", "LBL_LIGHTSHIFT"], False),
    (ACTIONS, BOTTOM_RIGHT, ["BTN_ACTION[0-9]", "BTN_ACTIONUP[0-9]", "BTN_ACTIONDOWN[0-9]", "LBL_ACTION[0-9]",
                             "LBL_ACTIONDESC", "LBL_ACTIONDESCBG", "LBL_MOULDING3"], True),
    (PORTRAITS, BOTTOM_LEFT, ["LBL_BACK[1-3]", "LBL_CHAR[1-3]", "BTN_CHAR[1-3]", "PB_VIT[1-3]", "PB_FORCE[1-3]",
                              "LBL_MOULDING1", "LBL_MOULDING2", "TB_PAUSE", "TB_SOLO", "TB_STEALTH"], True),
    (PORTRAITS, BOTTOM_LEFT, ["LBL_DISABLE[1-3]", "LBL_DEBILATATED[1-3]", "LBL_LVLUPBG[1-3]",
                              "LBL_LEVELUP[1-3]"], False),
    (PORTRAITS, CHAR_SPACE, ["LBL_CMBTEFCTINC[1-3]", "LBL_CMBTEFCTRED[1-3]"], False),
    (ATTACK, MENU_SPACE, ["BTN_TARGET[0-2]", "BTN_TARGETUP[0-2]", "BTN_TARGETDOWN[0-2]", "LBL_TARGET[0-2]"], True),
    (NONE, MENU_SPACE, ["LBL_NAME", "LBL_NAMEBG", "PB_HEALTH", "LBL_HEALTHBG"], False),
    # The combat queue as the engine shows it (ShowActionQueue, 0x006874C0, sets all of
    # these visible together): the black backing (LBL_COMBATBG2, lbl_mirightbotb), the
    # frame round the queue and the Disengage button (LBL_COMBATBG3, lbl_mirightbot),
    # the ring round the action under way (LBL_COMBATBG1, lbl_micomb), the slots, and
    # Disengage itself, a word with no picture. The file draws them in that order.
    (DISENGAGE, BOTTOM_CENTRE, ["LBL_COMBATBG1", "LBL_COMBATBG2", "LBL_COMBATBG3", "LBL_QUEUE[0-3]",
                                "BTN_CLEARONE", "BTN_CLEARONE2", "BTN_CLEARALL"], True),
    # The combat-mode message, right of the minimap: it keeps its size and moves with
    # the minimap's right edge, so a larger minimap does not cover it.
    (MINIMAP, TOP_LEFT, ["LBL_CMBTMODEMSG", "LBL_CMBTMSGBG"], False),
]
FOLLOWERS = {"LBL_CMBTMODEMSG", "LBL_CMBTMSGBG"}
# Left as the file has them: the map's picture, which the engine sizes and moves inside
# the window itself (InitializeMap, DrawMap), and the rectangle a target's circle may
# stand in, which the module works out from the placed HUD.
LEFT_ALONE = {"LBL_MAP", "LBL_ARROW_MARGIN"}


def _extent(struct) -> tuple[int, int, int, int]:
    e = struct.get_struct("EXTENT")
    return tuple(e.get_int32(n) for n in ("LEFT", "TOP", "WIDTH", "HEIGHT"))


def _fill(struct) -> str:
    for name in ("BORDER", "PROGRESS"):
        if struct.exists(name):
            sub = struct.get_struct(name)
            if sub.exists("FILL"):
                value = str(sub.get_resref("FILL")).strip()
                if value:
                    return value.lower()
    return ""


def shipped() -> dict[str, tuple[int, int, int, int]]:
    """The rectangles of the 3440x1440 HUD as KMRP ships it (the module's docstring)."""
    boxes = gold_extents(SOURCE)
    boxes.update(target_menu_extents(boxes, BASE_H))
    boxes.update(action_description_extents(boxes, BASE_W, BASE_H))
    for tag in COMBAT_MESSAGE_TAGS:
        left, top, _, height = boxes[tag]
        boxes[tag] = (left, top, COMBAT_MESSAGE_WIDTHS["%dx%d" % (BASE_W, BASE_H)], height)
    return boxes


def controls() -> list[tuple[str, tuple[int, int, int, int], str]]:
    """Every control of the source file, nested ones too, in the file's order, at its
    shipped rectangle."""
    out = []
    boxes = shipped()

    def walk(struct):
        for child in struct.get_list("CONTROLS") or []:
            tag = child.get_string("TAG")
            out.append((tag, boxes.get(tag, _extent(child)), _fill(child)))
            if child.exists("CONTROLS"):
                walk(child)

    walk(read_gff(SOURCE.read_bytes()).root)
    return out


def pieces() -> list[dict]:
    found = controls()
    by_tag = {tag: box for tag, box, _ in found}
    out = []
    for tag, box, fill in found:
        if tag in LEFT_ALONE:
            continue
        match = [(e, a, p) for e, a, patterns, p in PARTS if any(fnmatchcase(tag, pat) for pat in patterns)]
        if len(match) != 1:
            raise ValueError(f"{tag}: {'no part' if not match else 'several parts'}")
        element, anchor, preview = match[0]
        flags = (PREVIEW if preview else 0)
        if tag == "LBL_MAPVIEW":
            flags |= WINDOW
        if tag == "LBL_ARROW":
            flags |= ARROW
            flags &= ~PREVIEW
        if tag in FOLLOWERS:
            flags |= FOLLOW
        if anchor == CHAR_SPACE:
            # Kept by the engine relative to its portrait's LBL_CHARn.
            char = by_tag["LBL_CHAR" + tag[-1]]
            box = (box[0] - char[0], box[1] - char[1], box[2], box[3])
        out.append({"tag": tag, "element": element, "anchor": anchor, "box": box, "fill": fill, "flags": flags})
    return out


def table() -> str:
    lines = [
        "// Generated by tools/build_pc_hud.py from assets/override-3440x1440/mipc210x7.gui.",
        "// Do not edit: change the tool and run it (Test-HudOptions.py checks this file against it).",
        "//",
        "// The mouse and keyboard HUD's controls by tag: the part of the HUD each belongs to",
        "// (KmrpHudOptions::Element, -1 for none), how its rectangle is anchored, the rectangle",
        "// at 3440x1440 (in the target menu's or the portrait's own coordinates where the",
        "// anchor says so), its art for the preview, and flags (K1PcHudLayout.h).",
        "constexpr int kPcBaseWidth = %d, kPcBaseHeight = %d;" % (BASE_W, BASE_H),
        "constexpr PcPiece kPcPieces[] = {",
    ]
    for p in pieces():
        lines.append('    {"%s", %d, %s, {%d, %d, %d, %d}, "%s", %d},' % (
            p["tag"], p["element"], ANCHOR_NAMES[p["anchor"]], *p["box"], p["fill"], p["flags"]))
    lines.append("};")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    text = table()
    if "--check" in sys.argv:
        current = TABLE.read_text(encoding="utf-8").replace("\r\n", "\n") if TABLE.exists() else ""
        if current != text:
            sys.exit(f"{TABLE.name} is stale: run tools/build_pc_hud.py")
        print(f"{TABLE.name} is current: {len(pieces())} pieces")
    else:
        TABLE.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {TABLE} ({len(pieces())} pieces)")
