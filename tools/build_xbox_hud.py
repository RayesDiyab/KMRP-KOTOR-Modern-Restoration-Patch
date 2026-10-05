#!/usr/bin/env python3
"""The Xbox-style HUD's layout: where each of the PC HUD's controls goes, and in what art.

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

Until 2026-10-05 this tool rewrote a copy of each PC HUD layout file, and the patch
loaded the copy in the original's place. That tied the HUD to the four screen sizes
the files exist for, replaced whatever HUD layout another mod had installed, and
could not be undone while the game ran. Now the tool writes a table instead
(src/controller-native/K1XboxHudLayout.inc) and the module (K1XboxHud.cpp) moves and
dresses the live controls from it, for the screen the game is really drawing, and
puts them back when the mouse is used.

A control is named here by its tag and found in the game by its place in the HUD
object, CSWGuiMainInterface: the executable builds every HUD control as a member at
a fixed offset whatever layout file it loads. (A control's ID, its index in the
panel's array, comes from the file and differs between the game's own four files.)
OFFSETS was read from the running CD 1.03 game on 2026-10-05: each tag's ID in
mipc210x7.gui looked up in the panel's array, and the controls the panel does not
list (the target's menu, the combat-effect arrows) found by their class and ID in
the object's memory.

The console drew maininterface.gui, the 640x480 file, stretched over the whole
picture. mi8x6.gui holds the same rectangles at the same pixel sizes, moved out to an
800x600 screen's edges (every right-hand piece 160 further right, every bottom piece
120 further down), so its numbers serve with one change: a length is scaled by
height / 480, not height / 600. Scaled by 600 the HUD came out a fifth too small
against the Xbox game (the maintainer saw it, 2026-10-05: the action box 28% of the
screen's width where the reference video has 35%). Left and top pieces stay at their
scaled place, right-hand pieces keep their scaled distance from the right edge,
bottom pieces from the bottom edge, centred pieces from the middle. Nothing depends
on the screen's shape.

Usage:
    python tools/build_xbox_hud.py            write the table
    python tools/build_xbox_hud.py --check    exit 1 if the table on disk is stale

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_xbox_hud_art import HAIRLINE, PORTRAIT_INSET, SLOT_BOX_CENTRE, hd_name      # noqa: E402  the frames' drawings (kmrx_*)

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "src" / "controller-native" / "K1XboxHudLayout.inc"

BASE_W, BASE_H = 800, 600          # the screen mi8x6.gui's edges are measured on
SCALE_H = 480                      # the screen height its pixel sizes were drawn for
SLOT_PITCH = 36                    # LBH_BORDER1B to LBH_BORDER2B
SLOT_BORDER = (51, 515, 41, 41)    # LBH_BORDER1B: the first slot's frame
SLOT_ICON = (61, 524, 21, 21)      # LBL_ICON1B
SLOT_ARROW = (66, 515, 11, 41)     # LBH_ARROW1B
NAME_FRAME = (47, 24, 271, 64)     # LBL_INDICATE; the module keeps LBL_NAMEBG on it
MAP_VIEW = (678, 39, 68, 68)       # LBL_MAPVIEW: the rectangle the map is drawn in
DESCRIPTION = (56, 455, 210, 50)   # LBL_ACTIONDESC
MESSAGE_ROW = (12, 22)             # the combat-mode message's top and height
# The box a line of speech or a notice appears in (the engine's "bark bubble", a panel
# of its own): left, top and width. Measured in a frame of the Xbox game the
# maintainer sent on 2026-10-05, in 640x480 units: the box from 49 to 509 across with
# its top at 82, the target's bar from 53 to 307 and down to 73. So it starts a
# little left of the bar's frame and right under it. It is 460 wide there; the
# maintainer asked for one and a half times the bar's width instead (2026-10-05),
# and the bar's frame is 254 wide.
BARK = (49, 82, 381)
OUT_X, OUT_Y = 38, 30              # how far each group is moved out towards its corner
DISENGAGE_FILL = "kmrpb_cmbt"      # the B glyph (tools/build_controller_assets.py makes it per family)
QUEUE_CUE = (381, 523, 22, 22)     # the Y cue beside the queue (a label the patch adds; K1NativeJoystick.cpp)
SEAM_OVERLAP = 0                   # screen pixels the action box's upper half reaches into its lower one
# The party's group (portraits, bars, the curve beside them) is drawn smaller than
# the Xbox layout has it, about its bottom right corner: the maintainer found it too
# big (2026-10-05). In hundredths.
PARTY_SCALE = 85
PARTY_CORNER = (755, 559)          # the curve's right edge, the leader's bars' bottom
FONT = "dialogfont16x16"           # the Xbox HUD's text; the PC layout has dialogfont10x10 on these labels

LABEL, BUTTON, TOGGLE, PROGRESS = 4, 6, 7, 10      # CONTROLTYPE, as the layout files have it

# Tag: (offset in CSWGuiMainInterface, CONTROLTYPE).
OFFSETS = {
    "BTN_TARGET0": (0x0110, 6), "LBL_TARGET0": (0x02D4, 6), "BTN_TARGETUP0": (0x0498, 6),
    "BTN_TARGETDOWN0": (0x065C, 6), "BTN_TARGET1": (0x082C, 6), "LBL_TARGET1": (0x09F0, 6),
    "BTN_TARGETUP1": (0x0BB4, 6), "BTN_TARGETDOWN1": (0x0D78, 6), "BTN_TARGET2": (0x0F48, 6),
    "LBL_TARGET2": (0x110C, 6), "BTN_TARGETUP2": (0x12D0, 6), "BTN_TARGETDOWN2": (0x1494, 6),
    "LBL_NAME": (0x1688, 4), "LBL_NAMEBG": (0x17C8, 4), "LBL_HEALTHBG": (0x1908, 4), "PB_HEALTH": (0x1A48, 10),
    "LBL_MOULDING1": (0x1BC8, 4), "LBL_MOULDING2": (0x1D08, 4), "LBL_MOULDING3": (0x1E48, 4),
    "LBL_BACK1": (0x1FB0, 4), "LBL_DEBILATATED1": (0x20F0, 4), "LBL_LEVELUP1": (0x2370, 4),
    "LBL_LVLUPBG1": (0x24B0, 4), "LBL_CHAR1": (0x25F0, 4), "PB_VIT1": (0x2730, 10), "PB_FORCE1": (0x2880, 10),
    "LBL_CMBTEFCTINC1": (0x29D0, 4), "LBL_CMBTEFCTRED1": (0x2B10, 4), "BTN_CHAR1": (0x2C50, 6),
    "LBL_BACK2": (0x2E58, 4), "LBL_DEBILATATED2": (0x2F98, 4), "LBL_LEVELUP2": (0x3218, 4),
    "LBL_LVLUPBG2": (0x3358, 4), "LBL_CHAR2": (0x3498, 4), "PB_VIT2": (0x35D8, 10), "PB_FORCE2": (0x3728, 10),
    "LBL_CMBTEFCTINC2": (0x3878, 4), "LBL_CMBTEFCTRED2": (0x39B8, 4), "BTN_CHAR2": (0x3AF8, 6),
    "LBL_BACK3": (0x3D00, 4), "LBL_DEBILATATED3": (0x3E40, 4), "LBL_LEVELUP3": (0x40C0, 4),
    "LBL_LVLUPBG3": (0x4200, 4), "LBL_CHAR3": (0x4340, 4), "PB_VIT3": (0x4480, 10), "PB_FORCE3": (0x45D0, 10),
    "LBL_CMBTEFCTINC3": (0x4720, 4), "LBL_CMBTEFCTRED3": (0x4860, 4), "BTN_CHAR3": (0x49A0, 6),
    "LBL_MAPBORDER": (0x5CC0, 4), "BTN_MINIMAP": (0x6098, 6), "LBL_QUEUE0": (0x625C, 4), "LBL_QUEUE1": (0x639C, 4),
    "LBL_QUEUE2": (0x64DC, 4), "LBL_QUEUE3": (0x661C, 4), "LBL_COMBATBG1": (0x675C, 4), "LBL_COMBATBG2": (0x689C, 4),
    "LBL_COMBATBG3": (0x69DC, 4), "BTN_CLEARONE": (0x6CD0, 6), "BTN_CLEARONE2": (0x6E94, 6),
    "BTN_CLEARALL": (0x7058, 6), "LBL_CMBTMODEMSG": (0x735C, 4), "LBL_CMBTMSGBG": (0x749C, 4),
    "BTN_ACTION0": (0x772C, 6), "LBL_ACTION0": (0x78F0, 6), "BTN_ACTIONUP0": (0x7AB4, 6),
    "BTN_ACTIONDOWN0": (0x7C78, 6), "BTN_ACTION1": (0x7E48, 6), "LBL_ACTION1": (0x800C, 6),
    "BTN_ACTIONUP1": (0x81D0, 6), "BTN_ACTIONDOWN1": (0x8394, 6), "BTN_ACTION2": (0x8564, 6),
    "LBL_ACTION2": (0x8728, 6), "BTN_ACTIONUP2": (0x88EC, 6), "BTN_ACTIONDOWN2": (0x8AB0, 6),
    "BTN_ACTION3": (0x8C80, 6), "LBL_ACTION3": (0x8E44, 6), "BTN_ACTIONUP3": (0x9008, 6),
    "BTN_ACTIONDOWN3": (0x91CC, 6), "LBL_ACTIONDESC": (0xA1D4, 4), "LBL_ACTIONDESCBG": (0xA314, 4),
    "LBL_JOURNAL": (0xA460, 4), "LBL_CASH": (0xA5AC, 4), "LBL_PLOTXP": (0xA6F8, 4), "LBL_STEALTHXP": (0xA844, 4),
    "LBL_DARKSHIFT": (0xA990, 4), "LBL_LIGHTSHIFT": (0xAADC, 4), "LBL_ITEMRCVD": (0xAD74, 4),
    "LBL_ITEMLOST": (0xAEC0, 4), "BTN_EQU": (0xB00C, 6), "BTN_INV": (0xB1D0, 6), "BTN_CHAR": (0xB394, 6),
    "BTN_ABI": (0xB558, 6), "BTN_MSG": (0xB71C, 6), "BTN_JOU": (0xB8E0, 6), "BTN_MAP": (0xBAA4, 6),
    "BTN_OPT": (0xBC68, 6), "LBL_MENUBG": (0xBE2C, 4), "LBL_ARROW_MARGIN": (0xBF6C, 4), "TB_PAUSE": (0xC0AC, 7),
    "TB_SOLO": (0xC360, 7), "TB_STEALTH": (0xC614, 7),
}

# How a piece's rectangle is turned into screen pixels.
LEFT, RIGHT, CENTRE, RELATIVE = 0, 1, 2, 3     # sideways
TOP, BOTTOM = 0, 1                             # up and down (RELATIVE ignores it)
# Flags.
HIDE = 1        # parked off the screen at its own size
ROW = 2         # the full width of the screen (the rectangle gives top and height)
SET_FONT = 4    # the Xbox HUD's font
PARTY = 8       # one of the party's group, drawn at PARTY_SCALE


def scale_value(value: int, height: int) -> int:
    """Scale a layout length to the screen, rounding half up (the module does the same)."""
    return (2 * value * height + SCALE_H) // (2 * SCALE_H)


def pieces() -> list[dict]:
    """Every control the Xbox HUD moves or dresses, in the order the module applies them."""
    out: list[dict] = []
    seen: set[str] = set()

    def place(tag, box, side=LEFT, edge=BOTTOM, fill=None, hilight=None, progress=None, flags=0, places=0):
        if tag in seen:
            raise ValueError(f"{tag} placed twice")
        seen.add(tag)
        # The frames are named here as the game names them, and dressed in their
        # drawings (tools/build_xbox_hud_art.py); a texture with no drawing keeps its name.
        fill, hilight, progress = (None if name is None else hd_name(name) for name in (fill, hilight, progress))
        out.append({"tag": tag, "box": tuple(box), "side": side, "edge": edge, "fill": fill, "hilight": hilight,
                    "progress": progress, "flags": flags, "places": places})

    def hide(tag, fill=None, hilight=None):
        place(tag, (0, 0, 0, 0), fill=fill, hilight=hilight, flags=HIDE)

    # The action box. The PC HUD's three mouldings are always drawn, so they carry the
    # Xbox HUD's fixed art. The panel draws its controls in the layout file's order,
    # and the description label comes after LBL_MOULDING1 and before LBL_MOULDING3:
    # the box has to be the first, or it is drawn over the text (seen 2026-10-05, the
    # description a dim navy under the box). The description's own background cannot
    # be the box: the engine shows it only with a description and shrinks it to the
    # text (seen the same day), so it is left without art.
    # The module makes the box's upper half reach SEAM_OVERLAP screen pixels into the
    # lower one. The file leaves a unit between them (446 + 90, then 537), and each
    # texture's body runs to its edge, where the engine's filtering takes the row at
    # the edge half from the texture's empty far side: laid out by the file's numbers
    # the pair showed a light line across the slots (seen 2026-10-05; the Xbox game
    # shows none). The lower half stays exactly where the file has it, since its rim
    # is the box's bottom edge and the slots' lower arrowheads sit just inside it.
    # That was with the game's own art, and the overlap was 1. The box is drawn art now
    # (tools/build_xbox_hud_art.py) whose textures do not repeat ("clamp 3"), so the
    # row at the edge is whole, and a pixel of overlap showed as a DARK line instead,
    # the two halves' shade twice (seen later the same day). The upper half now ends
    # exactly where the lower begins: an overlap of 0.
    place("LBL_MOULDING1", (45, 446, 256, 90), fill="lbl_mitextbox")
    place("LBL_MOULDING3", (45, 537, 256, 32), fill="lbl_mitextbox2")
    place("LBL_MOULDING2", (723, 467, 32, 72), side=RIGHT, fill="lbl_micurve", flags=PARTY)
    place("LBL_ACTIONDESCBG", DESCRIPTION, fill="")
    place("LBL_ACTIONDESC", DESCRIPTION, flags=SET_FONT)

    # The slots: the target's three, then the four personal ones. The Xbox arrow is
    # one strip with both arrowheads; the PC has an up and a down button, so the up
    # button wears the strip and the down button is its lower half, undrawn.
    # Every slot is the first one moved a whole number of scaled pitches, so the row
    # is even at every size and the module can place a slot from another.
    # Six places for the PC's seven slots, in the Xbox row's order: attacks, skills,
    # Force powers, grenades, medical, items. The mines' slot (the fourth personal
    # one) shares the fourth place with the target's grenade slot, and the module
    # shows whichever applies (K1XboxHud.cpp, kPlace).
    # The first place has no slot: the module draws the target's default action there.
    # The target's first slot, kept to its other entries, shares the second place
    # with the character's skills.
    slots = [("TARGET", 0, 1), ("ACTION", 0, 1), ("TARGET", 1, 2), ("TARGET", 2, 3),
             ("ACTION", 1, 4), ("ACTION", 2, 5), ("ACTION", 3, 3)]
    arrow = SLOT_ARROW
    for kind, i, index in slots:
        place(f"BTN_{kind}{i}", SLOT_BORDER, fill="lbl_mibox01", hilight="lbl_mibox02", places=index)
        place(f"LBL_{kind}{i}", SLOT_ICON, places=index)
        place(f"BTN_{kind}UP{i}", arrow, fill="lbl_miarrow01", hilight="lbl_miarrow02", places=index)
        place(f"BTN_{kind}DOWN{i}", (arrow[0], arrow[1] + arrow[3] // 2, arrow[2], arrow[3] - arrow[3] // 2),
              fill="", hilight="", places=index)

    # The target's name and health bar, top left. The engine draws these in the
    # target menu's own viewport, which the module pins to the whole screen.
    place("LBL_NAME", (57, 38, 247, 26), edge=TOP, flags=SET_FONT)
    place("LBL_NAMEBG", NAME_FRAME, edge=TOP, fill="lbl_miindic01f")
    place("PB_HEALTH", (58, 64, 247, 9), edge=TOP)
    place("LBL_HEALTHBG", (58, 64, 247, 9), edge=TOP, fill="")

    # Portraits, bottom right: (leader, second, third) as mi8x6 has LBL_CHAR1..3.
    portraits = {1: (643, 498, 58, 58), 2: (694, 461, 32, 32), 3: (705, 425, 32, 32)}
    for i, box in portraits.items():
        for stem in ("LBL_CHAR", "BTN_CHAR", "LBL_DEBILATATED", "LBL_LVLUPBG", "LBL_LEVELUP"):
            place(f"{stem}{i}", box, side=RIGHT, flags=PARTY)
    place("LBL_BACK1", (633, 495, 78, 64), side=RIGHT, fill="lbl_miport", flags=PARTY)
    place("LBL_BACK2", (687, 459, 45, 36), side=RIGHT, fill="lbl_miport", flags=PARTY)
    place("LBL_BACK3", (699, 423, 44, 36), side=RIGHT, fill="lbl_miport", flags=PARTY)
    bars = {"PB_VIT1": (626, 495, 16, 64), "PB_FORCE1": (702, 495, 16, 64),
            "PB_VIT2": (683, 459, 11, 36), "PB_FORCE2": (726, 459, 11, 36),
            "PB_VIT3": (694, 423, 11, 36), "PB_FORCE3": (737, 423, 11, 36)}
    for tag, box in bars.items():
        vit = tag.startswith("PB_VIT")
        place(tag, box, side=RIGHT, fill="lbl_health2" if vit else "lbl_force2",
              progress="lbl_health" if vit else "lbl_force", flags=PARTY)
    # The combat-effect arrows on a portrait. The engine keeps these relative to the
    # portrait's corner (in the running game LBL_CMBTEFCTINC1 was at (2, 23) where
    # the layout file has (8, 727) and LBL_CHAR1 (6, 704)), so they are given so.
    effects = {"LBL_CMBTEFCTRED1": (683, 519, 16, 16), "LBL_CMBTEFCTINC1": (645, 519, 16, 16),
               "LBL_CMBTEFCTRED2": (717, 473, 8, 8), "LBL_CMBTEFCTINC2": (695, 473, 8, 8),
               "LBL_CMBTEFCTRED3": (728, 437, 8, 8), "LBL_CMBTEFCTINC3": (706, 437, 8, 8)}
    for tag, box in effects.items():
        portrait = portraits[int(tag[-1])]
        place(tag, (box[0] - portrait[0], box[1] - portrait[1], box[2], box[3]), side=RELATIVE, flags=PARTY)

    # Minimap, top right. The map itself is drawn in a rectangle the HUD keeps beside
    # these controls (MAP_VIEW; the module sets it). LBL_MAP and LBL_ARROW are moved
    # by the engine inside that rectangle and are left to it.
    place("LBL_MAPBORDER", (673, 34, 78, 78), side=RIGHT, edge=TOP, fill="lbl_minimap")
    place("BTN_MINIMAP", MAP_VIEW, side=RIGHT, edge=TOP)

    # The combat queue box, bottom, between the action box and the portraits.
    # The queue stays where mi8x6.gui has it, right of the middle. (It was centred on
    # the screen for one build on 2026-10-05 and the maintainer took that back.)
    place("LBL_COMBATBG1", (399, 504, 128, 64), side=CENTRE, fill="lbl_micombat")
    place("LBL_QUEUE0", (483, 518, 32, 32), side=CENTRE)
    for i, x in ((1, 445), (2, 428), (3, 411)):
        place(f"LBL_QUEUE{i}", (x, 526, 16, 16), side=CENTRE)
    place("BTN_CLEARONE", (399, 504, 64, 64), side=CENTRE)
    place("BTN_CLEARONE2", (463, 504, 64, 64), side=CENTRE)
    for tag in ("LBL_COMBATBG2", "LBL_COMBATBG3", "BTN_CLEARALL"):
        hide(tag)

    # The combat-mode message: one row across the top, on the strip the module draws
    # there in combat mode, in the font of the HUD's other text and with no box of
    # its own, as the Xbox has it. The background label is the second half of the
    # line when the module splits it around the pad's button.
    for tag in ("LBL_CMBTMODEMSG", "LBL_CMBTMSGBG"):
        place(tag, (0, MESSAGE_ROW[0], 0, MESSAGE_ROW[1]), edge=TOP, fill="", flags=ROW | SET_FONT)

    # The status icons, top centre.
    status = {"LBL_JOURNAL": 390, "LBL_CASH": 423, "LBL_PLOTXP": 456, "LBL_STEALTHXP": 456,
              "LBL_DARKSHIFT": 489, "LBL_LIGHTSHIFT": 489, "LBL_ITEMRCVD": 522, "LBL_ITEMLOST": 555}
    for tag, x in status.items():
        place(tag, (x, 41, 32, 32), side=CENTRE, edge=TOP)

    # What the Xbox HUD does not have: the row of eight menu buttons and the three
    # toggles. Five of the parked buttons hold textures the module swaps in and out
    # before every draw, for as long as the Xbox HUD is up, so that changing a fill
    # twice a frame never loads or frees one: the curved and the flat vitality bars
    # (the engine puts its flat redfill or greenfill back at every update), the two
    # frames the engine gives the target's slots, the first place's icon without a
    # target, the combat strip's two plain fills, and the minimap's frame for when
    # the module draws it (beside a patch that keeps moving the engine's).
    held = {"BTN_EQU": ("lbl_health", "lbl_healthp"), "BTN_INV": ("redfill", "greenfill"),
            "BTN_ABI": ("lbl_miscroll_h", "lbl_miscroll_f"), "BTN_MSG": ("i_noaction", "i_noaction"),
            "BTN_JOU": ("blackfill", "whitefill"), "BTN_MAP": ("lbl_minimap", "lbl_minimap")}
    for tag in ("BTN_EQU", "BTN_INV", "BTN_CHAR", "BTN_ABI", "BTN_MSG", "BTN_JOU", "BTN_MAP", "BTN_OPT",
                "LBL_MENUBG", "TB_PAUSE", "TB_SOLO", "TB_STEALTH"):
        hide(tag, *held.get(tag, (None, None)))

    for piece in out:
        piece["offset"], piece["kind"] = OFFSETS[piece["tag"]]
        if piece["progress"] is not None and piece["kind"] != PROGRESS:
            raise ValueError(f"{piece['tag']} is not a progress bar")
        if piece["hilight"] is not None and piece["kind"] != BUTTON:
            raise ValueError(f"{piece['tag']} is not a button")
        if piece["flags"] & SET_FONT and piece["kind"] != LABEL:
            raise ValueError(f"{piece['tag']} is not a label")
    return out


def rectangle(piece: dict, width: int, height: int, portraits: dict | None = None) -> tuple[int, int, int, int] | None:
    """A piece's rectangle on a screen, as the module computes it; None for a parked piece."""
    def s(value):
        return scale_value(value, height)

    def exact(value):       # a length that need not be whole, rounded half up as the module rounds it
        return int((value * height) / SCALE_H + 0.5)

    x, y, w, h = piece["box"]
    if piece["flags"] & HIDE:
        return None
    if piece["flags"] & PARTY:
        f = PARTY_SCALE / 100
        if piece["side"] == RELATIVE:
            return (exact(x * f), exact(y * f), max(1, exact(w * f)), max(1, exact(h * f)))
        right, bottom = PARTY_CORNER
        left = width - exact(BASE_W - OUT_X - right + (right - x) * f)
        top = height - exact(BASE_H - OUT_Y - bottom + (bottom - y) * f)
        return (left, top, max(1, exact(w * f)), max(1, exact(h * f)))
    if piece["flags"] & ROW:
        return (0, s(y), width, s(h))
    if piece["side"] == RELATIVE:
        return (s(x), s(y), max(1, s(w)), max(1, s(h)))
    if piece["side"] == LEFT:
        left = s(x - OUT_X)
    elif piece["side"] == RIGHT:
        left = width - s(BASE_W - x - OUT_X)
    else:
        left = width // 2 + s(x - BASE_W // 2) if x >= BASE_W // 2 else width // 2 - s(BASE_W // 2 - x)
    top = s(y) if piece["edge"] == TOP else height - s(BASE_H - y - OUT_Y)
    return (left + piece["places"] * s(SLOT_PITCH), top, max(1, s(w)), max(1, s(h)))


def table() -> str:
    def name(value):
        return "nullptr" if value is None else '"%s"' % value

    side = {LEFT: "kLeft", RIGHT: "kRight", CENTRE: "kCentre", RELATIVE: "kRelative"}
    edge = {TOP: "kTop", BOTTOM: "kBottom"}
    kind = {LABEL: "kLabel", BUTTON: "kButton", TOGGLE: "kToggle", PROGRESS: "kProgress"}
    lines = [
        "// Generated by tools/build_xbox_hud.py, which says where every number comes from.",
        "// Do not edit: change the tool and run it (Test-ControllerKpatch.py checks this file against it).",
        "//",
        "// Each of the PC HUD's controls the Xbox-style HUD moves or dresses: its place in",
        "// CSWGuiMainInterface, its class, its rectangle in mi8x6.gui's units and how that is",
        "// anchored, how many slot pitches to its right it goes, and the art it wears",
        "// (nullptr: as it is; \"\": none).",
        "constexpr int kLayoutWidth = %d, kLayoutHeight = %d;" % (BASE_W, BASE_H),
        "constexpr int kOutX = %d, kOutY = %d;" % (OUT_X, OUT_Y),
        "constexpr int kSlotPitch = %d;" % SLOT_PITCH,
        "constexpr int kPartyScale = %d;                         // hundredths" % PARTY_SCALE,
        "constexpr int kPartyCorner[2] = {%d, %d};             // right, bottom" % PARTY_CORNER,
        "constexpr int kSeamOverlap = %d;" % SEAM_OVERLAP,
        "constexpr int kMapView[4] = {%d, %d, %d, %d};          // right, top" % MAP_VIEW,
        "constexpr int kDescriptionBottom = %d;                  // left, bottom" % (DESCRIPTION[1] + DESCRIPTION[3]),
        "constexpr int kMessageRow[2] = {%d, %d};                 // top and height, across the screen" % MESSAGE_ROW,
        "constexpr int kBark[3] = {%d, %d, %d};                 // left, top; width" % BARK,
        "constexpr int kQueueCue[4] = {%d, %d, %d, %d};        // centre, bottom" % QUEUE_CUE,
        'constexpr char kLayoutFont[16] = "%s";' % FONT,
        'constexpr char kDisengageFill[16] = "%s";' % DISENGAGE_FILL,
        "constexpr double kSlotBoxCentre[2] = {%s, %s};          // of the slot box's 64: its middle, which is not the texture's" % SLOT_BOX_CENTRE,
        "constexpr double kPortraitHairline = %s;                // of the frame's 64: the black line beside a portrait" % HAIRLINE,
        "constexpr double kPortraitInset[2] = {%s, %s};        // of the frame's 64: where a portrait's side edge goes, the middle of its top line" % PORTRAIT_INSET,
        "constexpr Piece kPieces[] = {",
    ]
    for p in pieces():
        flags = " | ".join(n for bit, n in ((HIDE, "kHide"), (ROW, "kRow"), (SET_FONT, "kSetFont"), (PARTY, "kParty")) if p["flags"] & bit) or "0"
        lines.append("    {0x%04X, %s, %s, %s, {%d, %d, %d, %d}, %d, %s, %s, %s, %s},   // %s" % (
            p["offset"], kind[p["kind"]], side[p["side"]], edge[p["edge"]], *p["box"], p["places"], flags,
            name(p["fill"]), name(p["hilight"]), name(p["progress"]), p["tag"]))
    lines.append("};")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    text = table()
    if "--check" in sys.argv:
        current = TABLE.read_text(encoding="utf-8").replace("\r\n", "\n") if TABLE.exists() else ""
        if current != text:
            sys.exit(f"{TABLE.name} is stale: run tools/build_xbox_hud.py")
        print(f"{TABLE.name} is current: {len(pieces())} pieces")
    else:
        TABLE.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {TABLE} ({len(pieces())} pieces)")
