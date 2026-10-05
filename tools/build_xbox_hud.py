#!/usr/bin/env python3
"""Lay a PC HUD out the way the Xbox game laid its HUD out.

The PC data still holds the Xbox HUD's layout files (maininterface.gui at 640x480,
mi8x6.gui at 800x600) and all of its art, but the PC executable binds none of their
controls (it has no LBL_ICON1, LBH_ARROW1 and so on), so those files cannot simply be
loaded. The Xbox look is made from the PC HUD's own controls instead, each placed and
dressed as mi8x6.gui places and dresses its counterpart:

  action box       bottom left    LBL_ACTIONDESCBG 256x90 at (45, 446), lbl_mitextbox
  action slots     in the box     one row of six, as the Xbox had; the PC has seven
                                  (three for the target, four personal), so two of
                                  them share a place
  target name      top left       LBL_NAME 247x26 at (57, 38) in the lbl_miindic01f frame
  portraits        bottom right   leader 58x58 at (643, 498), the others 32x32 above it
  minimap          top right      78x78 border at (673, 34)
  queue box        bottom         128x64 at (399, 504), lbl_micombat

The console drew maininterface.gui, the 640x480 file, stretched over the whole
picture. mi8x6.gui holds the same rectangles at the same pixel sizes, moved out to an
800x600 screen's edges (every right-hand piece 160 further right, every bottom piece
120 further down), so its numbers serve with one change: a length is scaled by
height / 480, not height / 600. Scaled by 600 the HUD came out a fifth too small
against the Xbox game (the maintainer saw it, 2026-10-05: the action box 28% of the
screen's width where the reference video has 35%). Left and top pieces stay at their scaled
place, right-hand pieces keep their scaled distance from the right edge, bottom pieces
from the bottom edge, centred pieces from the middle.

The target's name, health bar and three slots are not ordinary HUD controls: the
engine draws them as one menu (CSWGuiTargetActionMenu) that it moves to the target.
The module's Xbox HUD hook pins that menu's origin to the screen's corner, so these
controls are laid out here in screen coordinates like the rest.

Usage:
    python tools/build_xbox_hud.py SOURCE.gui OUTPUT.gui

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from pykotor.common.misc import ResRef
from pykotor.resource.formats.gff import read_gff, write_gff

BASE_W, BASE_H = 800, 600          # the screen mi8x6.gui's edges are measured on
SCALE_H = 480                      # the screen height its pixel sizes were drawn for
SLOT_PITCH = 36                    # LBH_BORDER1B to LBH_BORDER2B
SLOT_BORDER = (51, 515, 41, 41)    # LBH_BORDER1B: the first slot's frame
SLOT_ICON = (61, 524, 21, 21)      # LBL_ICON1B
SLOT_ARROW = (66, 515, 11, 41)     # LBH_ARROW1B
NAME_FRAME = (47, 24, 271, 64)     # LBL_INDICATE; the module keeps LBL_NAMEBG on it
OFFSCREEN = -4000
OUT_X, OUT_Y = 38, 30              # how far each group is moved out towards its corner
DISENGAGE_FILL = "kmrpb_cmbt"      # the B glyph (tools/build_controller_assets.py makes it per family)
SEAM_OVERLAP = 1                   # screen pixels the action box's upper half reaches into its lower one


def scale_value(value: int, height: int) -> int:
    """Scale a layout length to the screen, rounding half up (the module does the same)."""
    return (2 * value * height + SCALE_H) // (2 * SCALE_H)


def build(source: Path, output: Path, font: str | None = None) -> dict:
    gff = read_gff(source)
    root = gff.root
    panel = root.get_struct("EXTENT")
    width, height = panel.get_int32("WIDTH"), panel.get_int32("HEIGHT")
    controls = root.get_list("CONTROLS")
    by_tag = {c.get_string("TAG"): c for c in controls}
    placed: set[str] = set()

    def s(value):
        return scale_value(value, height)

    # The Xbox layout keeps 45 units clear at every edge, a television's margin. On
    # a monitor that reads as the HUD floating in from the corners, and the
    # maintainer asked for each group nearer its own corner (2026-10-05): the action
    # box left and down, the party right and down, the minimap right, the target's
    # bar left. Sideways by OUT_X, the bottom pieces down by OUT_Y.
    anchors = {
        "left": lambda x: s(x - OUT_X),
        "right": lambda x: width - s(BASE_W - x - OUT_X),
        "centre": lambda x: width // 2 + s(x - BASE_W // 2) if x >= BASE_W // 2 else width // 2 - s(BASE_W // 2 - x),
    }

    def top_of(y, edge):
        return s(y) if edge == "top" else height - s(BASE_H - y - OUT_Y)

    def place(tag, box, side="left", edge="bottom", fill=None, hilight=None, progress=None, font=None, shift=0):
        """Put a control on an mi8x6 rectangle (left, top, width, height); `shift` is
        screen pixels to the right of where that puts it."""
        if tag not in by_tag:
            return
        control = by_tag[tag]
        extent = control.get_struct("EXTENT")
        extent.set_int32("LEFT", anchors[side](box[0]) + shift)
        extent.set_int32("TOP", top_of(box[1], edge))
        extent.set_int32("WIDTH", max(1, s(box[2])))
        extent.set_int32("HEIGHT", max(1, s(box[3])))
        control.set_struct("EXTENT", extent)
        for field, value in (("BORDER", fill), ("HILIGHT", hilight), ("PROGRESS", progress)):
            if value is not None and control.exists(field):
                border = control.get_struct(field)
                border.set_resref("FILL", ResRef(value))
                control.set_struct(field, border)
        if font is not None and control.exists("TEXT"):
            text = control.get_struct("TEXT")
            text.set_resref("FONT", ResRef(font))
            control.set_struct("TEXT", text)
        placed.add(tag)

    def hide(tag):
        if tag not in by_tag:
            return
        control = by_tag[tag]
        extent = control.get_struct("EXTENT")
        extent.set_int32("LEFT", OFFSCREEN)
        extent.set_int32("TOP", OFFSCREEN)
        control.set_struct("EXTENT", extent)
        placed.add(tag)

    # The text. The Xbox drew dialogfont16x16 on 480 lines, so its capitals are 9.2
    # units tall (measured in the reference video: "Sith Soldier", "Attack"), 14.7 px
    # at 768 lines, and the game's own font is 9 px at every size. The standalone
    # patch carries no font, by the maintainer's decision (2026-10-05: KMRP's HD font
    # is KMRP's; this patch works on the game as it is), so `font` is the game's
    # unless a caller names another. No other font works here yet: with any font but
    # the two this layout already uses (dialogfont10x10, dialogfont16x16) on either
    # label, the game crashed while loading a save (docs/controller-xbox-hud.md).
    font = font or "dialogfont16x16"

    # The action box. The PC HUD's three mouldings are always drawn, so they carry the
    # Xbox HUD's fixed art. The panel draws its controls in the file's order, and the
    # description label comes after LBL_MOULDING1 and before LBL_MOULDING3: the box
    # has to be the first, or it is drawn over the text (seen 2026-10-05, the
    # description a dim navy under the box). The description's own background cannot
    # be the box: the engine shows it only with a description and shrinks it to the
    # text (seen the same day), so it is left without art.
    order = [c.get_string("TAG") for c in controls]
    if not order.index("LBL_MOULDING1") < order.index("LBL_ACTIONDESC") < order.index("LBL_MOULDING3"):
        raise ValueError(f"{source.name}: the mouldings no longer bracket the action description")
    place("LBL_MOULDING1", (45, 446, 256, 90), fill="lbl_mitextbox")
    place("LBL_MOULDING3", (45, 537, 256, 32), fill="lbl_mitextbox2")
    # The box's upper half reaches one screen pixel down into the lower one. The
    # file leaves a unit between them (446 + 90, then 537), and each texture's body
    # runs to its edge, where the engine's filtering takes the row at the edge half
    # from the texture's empty far side: laid out by the file's numbers the pair
    # showed a light line across the slots (seen 2026-10-05; the Xbox game shows
    # none). The lower half stays exactly where the file has it, since its rim is the
    # box's bottom edge and the slots' lower arrowheads sit just inside that edge.
    # (For a few hours that day the lower half was moved up two pixels as well, which
    # raised the rim onto the arrowheads; the maintainer saw them outside the frame.)
    upper, lower = by_tag["LBL_MOULDING1"].get_struct("EXTENT"), by_tag["LBL_MOULDING3"].get_struct("EXTENT")
    upper.set_int32("HEIGHT", lower.get_int32("TOP") + SEAM_OVERLAP - upper.get_int32("TOP"))
    by_tag["LBL_MOULDING1"].set_struct("EXTENT", upper)
    place("LBL_MOULDING2", (723, 467, 32, 72), side="right", fill="lbl_micurve")
    place("LBL_ACTIONDESCBG", (56, 455, 210, 50), fill="")
    place("LBL_ACTIONDESC", (56, 455, 210, 50), font=font)

    # The slots: the target's three, then the four personal ones. The Xbox arrow is
    # one strip with both arrowheads; the PC has an up and a down button, so the up
    # button wears the strip and the down button is its lower half, undrawn.
    # Every slot is the first one moved a whole number of scaled pitches, so the row
    # is even at every size and the module can place a slot from another.
    # Six places for the PC's seven slots, in the Xbox row's order: attacks, skills,
    # Force powers, grenades, medical, items. The mines' slot (the fourth personal
    # one) shares the fourth place with the target's grenade slot, and the module
    # shows whichever applies (K1XboxHud.cpp, kPlace).
    # The first place has no slot: the module draws the target's default action there
    # (K1XboxHud.cpp). The target's first slot, kept to its other entries, shares the
    # second place with the character's skills.
    slots = [("TARGET", 0, 1), ("ACTION", 0, 1), ("TARGET", 1, 2), ("TARGET", 2, 3),
             ("ACTION", 1, 4), ("ACTION", 2, 5), ("ACTION", 3, 3)]
    arrow = SLOT_ARROW
    for kind, i, index in slots:
        shift = index * s(SLOT_PITCH)
        place(f"BTN_{kind}{i}", SLOT_BORDER, fill="lbl_mibox01", hilight="lbl_mibox02", shift=shift)
        place(f"LBL_{kind}{i}", SLOT_ICON, shift=shift)
        place(f"BTN_{kind}UP{i}", arrow, fill="lbl_miarrow01", hilight="lbl_miarrow02", shift=shift)
        place(f"BTN_{kind}DOWN{i}", (arrow[0], arrow[1] + arrow[3] // 2, arrow[2], arrow[3] - arrow[3] // 2),
              fill="", hilight="", shift=shift)

    # The target's name and health bar, top left.
    place("LBL_NAME", (57, 38, 247, 26), edge="top", font=font)
    place("LBL_NAMEBG", NAME_FRAME, edge="top", fill="lbl_miindic01f")
    place("PB_HEALTH", (58, 64, 247, 9), edge="top")
    place("LBL_HEALTHBG", (58, 64, 247, 9), edge="top", fill="")

    # Portraits, bottom right: (leader, second, third) as mi8x6 has LBL_CHAR1..3.
    portraits = {1: (643, 498, 58, 58), 2: (694, 461, 32, 32), 3: (705, 425, 32, 32)}
    for i, box in portraits.items():
        for stem in ("LBL_CHAR", "BTN_CHAR", "LBL_DISABLE", "LBL_DEBILATATED", "LBL_LVLUPBG", "LBL_LEVELUP"):
            place(f"{stem}{i}", box, side="right")
    place("LBL_BACK1", (633, 495, 78, 64), side="right", fill="lbl_miport")
    place("LBL_BACK2", (687, 459, 45, 36), side="right", fill="lbl_miport")
    place("LBL_BACK3", (699, 423, 44, 36), side="right", fill="lbl_miport")
    bars = {"PB_VIT1": (626, 495, 16, 64), "PB_FORCE1": (702, 495, 16, 64),
            "PB_VIT2": (683, 459, 11, 36), "PB_FORCE2": (726, 459, 11, 36),
            "PB_VIT3": (694, 423, 11, 36), "PB_FORCE3": (737, 423, 11, 36)}
    for tag, box in bars.items():
        vit = tag.startswith("PB_VIT")
        place(tag, box, side="right", fill="lbl_health2" if vit else "lbl_force2",
              progress="lbl_health" if vit else "lbl_force")
    effects = {"LBL_CMBTEFCTRED1": (683, 519, 16, 16), "LBL_CMBTEFCTINC1": (645, 519, 16, 16),
               "LBL_CMBTEFCTRED2": (717, 473, 8, 8), "LBL_CMBTEFCTINC2": (695, 473, 8, 8),
               "LBL_CMBTEFCTRED3": (728, 437, 8, 8), "LBL_CMBTEFCTINC3": (706, 437, 8, 8)}
    for tag, box in effects.items():
        place(tag, box, side="right")

    # Minimap, top right.
    place("LBL_MAPBORDER", (673, 34, 78, 78), side="right", edge="top", fill="lbl_minimap")
    place("LBL_MAPVIEW", (678, 39, 68, 68), side="right", edge="top")
    place("BTN_MINIMAP", (678, 39, 68, 68), side="right", edge="top")
    if "LBL_MAP" in by_tag:
        e = by_tag["LBL_MAP"].get_struct("EXTENT")
        place("LBL_MAP", (678, 39, 0, 0), side="right", edge="top")
        e2 = by_tag["LBL_MAP"].get_struct("EXTENT")
        e2.set_int32("WIDTH", e.get_int32("WIDTH"))
        e2.set_int32("HEIGHT", e.get_int32("HEIGHT"))
        by_tag["LBL_MAP"].set_struct("EXTENT", e2)
    place("LBL_ARROW", (698, 58, 32, 32), side="right", edge="top")

    # The combat queue box, bottom, between the action box and the portraits.
    # The queue stays where mi8x6.gui has it, right of the middle. (It was centred on
    # the screen for one build on 2026-10-05 and the maintainer took that back.)
    q = 0
    place("LBL_COMBATBG1", (399 - q, 504, 128, 64), side="centre", fill="lbl_micombat")
    place("LBL_QUEUE0", (483 - q, 518, 32, 32), side="centre")
    for i, x in ((1, 445), (2, 428), (3, 411)):
        place(f"LBL_QUEUE{i}", (x - q, 526, 16, 16), side="centre")
    place("BTN_CLEARONE", (399 - q, 504, 64, 64), side="centre")
    place("BTN_CLEARONE2", (463 - q, 504, 64, 64), side="centre")
    for tag in ("LBL_COMBATBG2", "LBL_COMBATBG3", "BTN_CLEARALL"):
        hide(tag)
    # Beside the queue only Y, which takes the last action off it. X, which
    # disengages, is the button in the combat-mode message (K1XboxHud.cpp puts it
    # there while that message is shown).
    # Beside the box and on its middle line: the box's art is the upper part of its
    # 64 rows (measured on screen at 1024x768: the queue's middle at 710, the button's within a pixel of it).
    place("LBL_KMRPY", (399 - q + 6 - 24, 523, 22, 22), side="centre")
    hide("LBL_KMRPX")
    if "LBL_KMRPX" in by_tag:
        border = by_tag["LBL_KMRPX"].get_struct("BORDER")
        border.set_resref("FILL", ResRef(DISENGAGE_FILL))
        by_tag["LBL_KMRPX"].set_struct("BORDER", border)

    # The combat-mode message: one row across the top, on the strip the module draws
    # there in combat mode (K1XboxHud.cpp), in the font of the HUD's other text and
    # with no box of its own, as the Xbox has it.
    # The background label is the second half of the line when the module splits it
    # around the pad's button.
    for tag in ("LBL_CMBTMODEMSG", "LBL_CMBTMSGBG"):
        if tag not in by_tag:
            continue
        control = by_tag[tag]
        extent = control.get_struct("EXTENT")
        for field, value in (("LEFT", 0), ("TOP", s(12)), ("WIDTH", width), ("HEIGHT", s(22))):
            extent.set_int32(field, value)
        control.set_struct("EXTENT", extent)
        border = control.get_struct("BORDER")
        border.set_resref("FILL", ResRef(""))
        control.set_struct("BORDER", border)
        text = control.get_struct("TEXT")
        text.set_resref("FONT", ResRef(font))
        if tag == "LBL_CMBTMSGBG":
            text.set_string("TEXT", "")
        control.set_struct("TEXT", text)
        placed.add(tag)

    # The status icons, top centre.
    status = {"LBL_JOURNAL": 390, "LBL_CASH": 423, "LBL_PLOTXP": 456, "LBL_STEALTHXP": 456,
              "LBL_DARKSHIFT": 489, "LBL_LIGHTSHIFT": 489, "LBL_ITEMRCVD": 522, "LBL_ITEMLOST": 555}
    for tag, x in status.items():
        place(tag, (x, 41, 32, 32), side="centre", edge="top")

    # What the Xbox HUD does not have: the row of eight menu buttons and the three
    # toggles. (LBL_MENUBG and TB_PAUSE also give the target menu its bounds, at
    # construction; the module's hook replaces those bounds, so they can go too.)
    for tag in ("BTN_EQU", "BTN_INV", "BTN_CHAR", "BTN_ABI", "BTN_MSG", "BTN_JOU", "BTN_MAP", "BTN_OPT",
                "LBL_MENUBG", "TB_PAUSE", "TB_SOLO", "TB_STEALTH"):
        hide(tag)

    # The module puts the curved lbl_health (lbl_healthp when poisoned) on the vitality
    # bars at every draw, and the engine puts its flat redfill or greenfill back at
    # every update. Two parked buttons hold all four textures for as long as the HUD
    # lives, so that changing a bar's fill twice a frame never loads or frees one.
    # A third holds the two frames the engine gives the target's slots, which the
    # module replaces with the Xbox frame in the same way.
    for tag, normal, focused in (("BTN_EQU", "lbl_health", "lbl_healthp"), ("BTN_INV", "redfill", "greenfill"),
                                 ("BTN_ABI", "lbl_miscroll_h", "lbl_miscroll_f"),
                                 ("BTN_MSG", "i_noaction", "i_noaction"),
                                 ("BTN_JOU", "blackfill", "whitefill")):
        for field, name in (("BORDER", normal), ("HILIGHT", focused)):
            border = by_tag[tag].get_struct(field)
            border.set_resref("FILL", ResRef(name))
            by_tag[tag].set_struct(field, border)

    root.set_list("CONTROLS", controls)
    write_gff(gff, output)
    return {"size": (width, height), "placed": len(placed), "untouched": sorted(set(by_tag) - placed)}


if __name__ == "__main__":
    logging.disable(logging.DEBUG)
    print(build(Path(sys.argv[1]), Path(sys.argv[2])))
