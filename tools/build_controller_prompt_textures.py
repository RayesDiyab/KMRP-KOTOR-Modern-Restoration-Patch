#!/usr/bin/env python3
"""Build resolution-matched controller badges for existing KOTOR buttons.

The PC renderer stretches a button's BORDER.FILL across the whole control.  Each
texture is therefore generated from the final control extent for that resolution;
the circle and letter are pre-compensated so they remain round after stretching.
The controller runtime assigns these otherwise-unused fills only while a gamepad
is the last active input device.
"""

from __future__ import annotations

import math
import struct
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

from pykotor.resource.formats.gff import read_gff


TEXTURE_WIDTH = 512
TEXTURE_HEIGHT = 64
TGA_FOOTER = b"\x00" * 8 + b"TRUEVISION-XFILE." + b"\x00"

# Real controller artwork, not drawn here: Xelu's Free Controller & Key Prompts,
# CC0 1.0 (public domain). The licence and the author's own terms are vendored
# beside the images -- "any project you want to (be it commercial or not)".
#
# The Xbox 360 set is used rather than Series X or Xbox One. Those two draw a
# grey disc with a coloured letter, which loses most of its contrast at badge
# size against KOTOR's dark blue panels; the 360 set is a solid coloured disc,
# which is also how the original Xbox build of KOTOR drew its prompts.
#
# Do NOT substitute Microsoft's official glyphs. They are trademarked and
# licensed for Xbox-licensed titles; this repository is public and GPL-3.0.
GLYPH_PACK = (Path(__file__).resolve().parents[1] / "third_party" / "Included"
              / "Xelu_Free_Controller&Key_Prompts")

# The prompt vocabulary is a set of ACTIONS, not a set of Xbox pictures. Every
# badge in the patch names an action here; only the file behind it changes with
# the family. All four families are built and shipped, and the module chooses
# one at run time from the controller it finds -- see FAMILY_LETTERS below and
# docs/controller-support.md.
GLYPH_FAMILIES = {
    "xbox": ("Xbox", {
        "A": "360_A.png", "B": "360_B.png", "X": "360_X.png", "Y": "360_Y.png",
        "LB": "360_LB.png", "RB": "360_RB.png",
        # Series X for the triggers, to match the R3 cue beside them. No
        # caption badge uses either glyph, so this reaches only the cues.
        "LT": "XboxSeriesX_LT.png", "RT": "XboxSeriesX_RT.png",
        "START": "360_Start.png", "BACK": "360_Back.png",
        "DPAD_LEFT": "360_Dpad_Left.png", "DPAD_RIGHT": "360_Dpad_Right.png",
        "DPAD_UP": "360_Dpad_Up.png", "DPAD_DOWN": "360_Dpad_Down.png",
        # R3 is the Series X art, which is the file the badge was asked for by
        # name. L3 is left on the 360 art deliberately rather than changed to
        # match: nothing uses it yet, and silently restyling an unused glyph
        # is a change nobody asked for. If L3 is ever badged, pick one.
        # Not a button: the whole "press X to swap tabs" phrase, X and
        # arrows together, as one piece of art.
        "SWAP": "Swap_tabs.png",
        "L3": "360_Left_Stick_Click.png",
        "R3": "XboxSeriesX_Right_Stick_Click.png",
        # The sticks and D-pad as whole controls, for the Controller Layout
        # screen, which names what a stick does rather than what clicking it does.
        "LSTICK": "360_Left_Stick.png", "RSTICK": "360_Right_Stick.png",
        "DPAD": "360_Dpad.png",
    }),
    "playstation": ("PS5", {
        "A": "PS5_Cross.png", "B": "PS5_Circle.png",
        "X": "PS5_Square.png", "Y": "PS5_Triangle.png",
        "LB": "PS5_L1.png", "RB": "PS5_R1.png",
        "LT": "PS5_L2.png", "RT": "PS5_R2.png",
        "START": "PS5_Options.png", "BACK": "PS5_Share.png",
        "DPAD_LEFT": "PS5_Dpad_Left.png", "DPAD_RIGHT": "PS5_Dpad_Right.png",
        "DPAD_UP": "PS5_Dpad_Up.png", "DPAD_DOWN": "PS5_Dpad_Down.png",
        "L3": "PS5_Left_Stick_Click.png", "R3": "PS5_Right_Stick_Click.png",
        "LSTICK": "PS5_Left_Stick.png", "RSTICK": "PS5_Right_Stick.png",
        "DPAD": "PS5_Dpad.png",
    }),
    # By POSITION, not by letter. The module reads XInput, where A is the bottom
    # face button whatever the pad calls it, and on a Switch Pro the bottom button
    # is labelled B, the right one A, the left one Y and the top one X. So the
    # badge beside a KMRP "A" action shows Nintendo's B. This assumes the layer
    # between the pad and XInput (Steam Input with "Use Nintendo Button Layout"
    # off, or any positional mapper) maps by position -- untested, and exactly
    # backwards for a label-based mapping.
    "switch": ("Switch", {
        "A": "Switch_B.png", "B": "Switch_A.png",
        "X": "Switch_Y.png", "Y": "Switch_X.png",
        "LB": "Switch_LB.png", "RB": "Switch_RB.png",
        "LT": "Switch_LT.png", "RT": "Switch_RT.png",
        "START": "Switch_Plus.png", "BACK": "Switch_Minus.png",
        "DPAD_LEFT": "Switch_Dpad_Left.png", "DPAD_RIGHT": "Switch_Dpad_Right.png",
        "DPAD_UP": "Switch_Dpad_Up.png", "DPAD_DOWN": "Switch_Dpad_Down.png",
        "L3": "Switch_Left_Stick_Click.png", "R3": "Switch_Right_Stick_Click.png",
        "LSTICK": "Switch_Left_Stick.png", "RSTICK": "Switch_Right_Stick.png",
        "DPAD": "Switch_Dpad.png",
    }),
    "steamdeck": ("Steam Deck", {
        "A": "SteamDeck_A.png", "B": "SteamDeck_B.png",
        "X": "SteamDeck_X.png", "Y": "SteamDeck_Y.png",
        "LB": "SteamDeck_L1.png", "RB": "SteamDeck_R1.png",
        "LT": "SteamDeck_L2.png", "RT": "SteamDeck_R2.png",
        # The Deck labels these Menu and Dots rather than Start and View.
        "START": "SteamDeck_Menu.png", "BACK": "SteamDeck_Dots.png",
        "DPAD_LEFT": "SteamDeck_Dpad_Left.png",
        "DPAD_RIGHT": "SteamDeck_Dpad_Right.png",
        "DPAD_UP": "SteamDeck_Dpad_Up.png",
        "DPAD_DOWN": "SteamDeck_Dpad_Down.png",
        "L3": "SteamDeck_Left_Stick_Click.png",
        "R3": "SteamDeck_Right_Stick_Click.png",
        "LSTICK": "SteamDeck_Left_Stick.png",
        "RSTICK": "SteamDeck_Right_Stick.png",
        "DPAD": "SteamDeck_Dpad.png",
    }),
}

# The default family, and the one the badge tables in the module name. Xbox,
# because KOTOR's own retained prompts are Xbox ones and the badges sit on a 2003
# Xbox-derived UI; it is also what an unrecognised pad gets.
GLYPH_FAMILY = "xbox"

# Every family is shipped, and the module picks one at run time from the pad it
# finds (issue #19). A family's textures differ from the Xbox ones in the fourth
# letter of the resref only -- "kmrpb_charexit" is the Xbox B badge,
# "kmrsb_charexit" the PlayStation one -- so no name grows past the 16 characters
# a resref holds, and the Xbox names are exactly the ones already shipping. The
# module rewrites that one letter when it assigns a fill; these letters must
# match K1_GLYPH_FAMILY_LETTERS in src/controller-native/K1NativeJoystick.cpp.
FAMILY_LETTERS = {"xbox": "p", "playstation": "s", "switch": "n", "steamdeck": "d"}


def family_resref(resref: str, family: str) -> str:
    """The resref of `resref`'s art in `family`. Xbox names come back unchanged."""
    if not resref.startswith("kmrp"):
        raise ValueError(f"{resref!r} is not a KMRP prompt resref")
    return "kmr" + FAMILY_LETTERS[family] + resref[4:]


GLYPH_ART_DIR = GLYPH_PACK / GLYPH_FAMILIES[GLYPH_FAMILY][0]
GLYPH_ART = GLYPH_FAMILIES[GLYPH_FAMILY][1]

# Fallback palette for _legacy_drawn_tga only, used if the artwork is missing.
# Measured off original-Xbox KOTOR screenshots (modal colour inside each disc,
# antialiased edges discarded): A (137,210,9)/(134,209,2), B (183,42,0)/(194,45,0),
# Y (236,181,12)/(235,177,0). X could not be sampled cleanly -- its blue overlaps
# KOTOR's own cyan UI in hue -- so that one value is the standard Xbox blue and is
# the single unmeasured entry.
GLYPH_COLORS = {
    "A": (134, 209, 5),
    "B": (190, 44, 0),
    "X": (42, 111, 219),
    "Y": (235, 179, 4),
}
GLYPH_FALLBACK = (77, 215, 255)
GLYPH_INK = (16, 20, 24)


@dataclass(frozen=True)
class PromptTarget:
    gui: str
    tag: str
    control_index: int
    glyph: str
    resref: str


# These are zero-based entries in each GUI GFF control list. The generator
# verifies the tag at every index in every resolution and uses the control's
# rectangle to shape its badge. Runtime lookup uses verified embedded-object
# offsets instead; GUI list order is not an object-layout contract.
PROMPT_TARGETS = (
    PromptTarget("character.gui", "BTN_EXIT", 60, "B", "kmrpb_charexit"),
    PromptTarget("character.gui", "BTN_SCRIPTS", 61, "X", "kmrpx_charscr"),
    PromptTarget("container.gui", "BTN_OK", 2, "A", "kmrpa_contok"),
    PromptTarget("container.gui", "BTN_GIVEITEMS", 3, "X", "kmrpx_contgive"),
    PromptTarget("container.gui", "BTN_CANCEL", 4, "B", "kmrpb_contback"),
    PromptTarget("saveload.gui", "BTN_DELETE", 8, "X", "kmrpx_savdel"),
    PromptTarget("saveload.gui", "BTN_BACK", 9, "B", "kmrpb_savback"),
    PromptTarget("saveload.gui", "BTN_SAVELOAD", 10, "A", "kmrpa_savload"),
    PromptTarget("upgradesel.gui", "BTN_UPGRADEITEMS", 9, "A", "kmrpa_upgitem"),
    PromptTarget("upgradesel.gui", "BTN_BACK", 10, "B", "kmrpb_upgback"),

    # The in-game tab screens: Inventory, Messages, Journal and Map.
    #
    # These were previously generated by tools/build_tab_screen_prompts.py from
    # extents measured by hand on a live 3440x1440 game, and written straight
    # into the game folder -- so they never entered the patcher at all. The
    # symptom was precise: with a controller active those four screens drew
    # their buttons as flat white/green, because the prompt system swaps
    # BORDER.FILL to a texture that was not installed, while a mouse left the
    # fill alone and looked fine.
    #
    # Every one of these buttons is an ordinary control in the .gui with an
    # empty fill, so the standard generator can shape them from each
    # resolution's real extents. That also corrects the hand measurements: the
    # Inventory buttons are 785 and 1177 wide here, not the 770 and 1166 that
    # were read off the screen.
    #
    # Glyphs are the measured ones -- B closes, X acts, Y sorts, A activates --
    # see docs/controller-behaviour-matrix.md.
    # The main menu. All five are A, and only the focused one is ever painted --
    # the module clears the rest -- but each needs its own texture because a badge
    # is stretched across the button it sits on, and BTN_EXIT is 81 tall where the
    # other four are 66.
    PromptTarget("mainmenu.gui", "BTN_NEWGAME", 7, "A", "kmrpa_mmnew"),
    PromptTarget("mainmenu.gui", "BTN_LOADGAME", 6, "A", "kmrpa_mmload"),
    PromptTarget("mainmenu.gui", "BTN_MOVIES", 8, "A", "kmrpa_mmmovi"),
    PromptTarget("mainmenu.gui", "BTN_OPTIONS", 9, "A", "kmrpa_mmopt"),
    PromptTarget("mainmenu.gui", "BTN_EXIT", 11, "A", "kmrpa_mmexit"),

    # The equipment and quest items screens, which had no badge art at all.
    # B closes both: CSWGuiInGameEquip implements 0x28 at 0x006BA41F.
    # Script Selection. Its dispatcher at 0x006E9BC0 lands both 0x27 and 0x28 on
    # real handlers (0x006E9BEF, 0x006E9C56), so neither badge depends on focus.
    PromptTarget("scriptselect.gui", "BTN_Accept", 4, "A", "kmrpa_scrsel"),
    PromptTarget("scriptselect.gui", "BTN_Back", 3, "B", "kmrpb_scrback"),

    # Select Party Members. PARTY_SELECT implements 0x28 and nothing else, so
    # only Cancel is unconditional; Add and OK answer to A while focused, which
    # is what their FocusOnly binding in the module says.
    PromptTarget("partyselection.gui", "BTN_ACCEPT", 38, "A", "kmrpa_ptyadd"),
    PromptTarget("partyselection.gui", "BTN_DONE", 36, "A", "kmrpa_ptyok"),
    PromptTarget("partyselection.gui", "BTN_BACK", 37, "B", "kmrpb_ptyback"),

    PromptTarget("equip.gui", "BTN_EQUIP", 37, "A", "kmrpa_eqpequip"),
    PromptTarget("equip.gui", "BTN_BACK", 36, "B", "kmrpb_eqpback"),
    PromptTarget("questitem.gui", "BTN_BACK", 3, "B", "kmrpb_qitback"),

    PromptTarget("inventory.gui", "BTN_EXIT", 14, "B", "kmrpb_invclose"),
    PromptTarget("inventory.gui", "BTN_USEITEM", 13, "A", "kmrpa_invuse"),
    PromptTarget("inventory.gui", "BTN_QUESTITEMS", 10, "X", "kmrpx_invnew"),

    PromptTarget("messages.gui", "BTN_EXIT", 2, "B", "kmrpb_msgclose"),
    PromptTarget("messages.gui", "BTN_SHOW", 4, "X", "kmrpx_msgfeed"),

    PromptTarget("journal.gui", "BTN_QUESTITEMS", 3, "X", "kmrpx_jrnitems"),
    PromptTarget("journal.gui", "BTN_SWAPTEXT", 4, "A", "kmrpa_jrndone"),
    PromptTarget("journal.gui", "BTN_SORT", 5, "Y", "kmrpy_jrnsort"),
    PromptTarget("journal.gui", "BTN_EXIT", 6, "B", "kmrpb_jrnclose"),

    PromptTarget("map.gui", "BTN_RETURN", 7, "X", "kmrpx_mapebon"),
    PromptTarget("map.gui", "BTN_PRTYSLCT", 6, "A", "kmrpa_mapparty"),
    PromptTarget("map.gui", "BTN_EXIT", 8, "B", "kmrpb_mapclose"),

    # Every remaining screen the controller can navigate, added 2026-09-06.
    #
    # These are all B, and B is the one glyph that can be asserted rather than
    # assumed: the module rewrites B's Delete scancode to Escape whenever a menu
    # panel is open (K1XboxControls.cpp, the DIK_DELETE branch of
    # CaptureActionBarInputK1), and the rewrite is suppressed only for the four
    # transient overlays in IsK1DeleteEscapeSuppressedPanel -- floaty text, bark
    # bubbles, the message box and the controller-loss box. None of these is one.
    #
    # The tags are not trustworthy and were not trusted: `optgraphicsadv.gui`
    # and `optsoundadv.gui` both call their OK button BTN_BACK and their real
    # back button BTN_CANCEL, so each target below was chosen by the STRREF the
    # button actually draws, not by its name.
    PromptTarget("optionsmain.gui", "BTN_BACK", 7, "B", "kmrpb_optmain"),
    PromptTarget("optionsingame.gui", "BTN_EXIT", 10, "B", "kmrpb_optingame"),
    PromptTarget("optgameplay.gui", "BTN_BACK", 10, "B", "kmrpb_optgame"),
    PromptTarget("optautopause.gui", "BTN_BACK", 7, "B", "kmrpb_optpause"),
    PromptTarget("optfeedback.gui", "BTN_BACK", 2, "B", "kmrpb_optfeed"),
    PromptTarget("optmouse.gui", "BTN_BACK", 2, "B", "kmrpb_optmouse"),
    PromptTarget("optgraphics.gui", "BTN_BACK", 5, "B", "kmrpb_optgfx"),
    PromptTarget("optgraphicsadv.gui", "BTN_CANCEL", 3, "B", "kmrpb_optgfxadv"),
    PromptTarget("optsound.gui", "BTN_BACK", 11, "B", "kmrpb_optsnd"),
    PromptTarget("optsoundadv.gui", "BTN_CANCEL", 8, "B", "kmrpb_optsndadv"),
    PromptTarget("optkeymapping.gui", "BTN_Cancel", 3, "B", "kmrpb_optkeys"),
    PromptTarget("upgrade.gui", "BTN_BACK", 28, "B", "kmrpb_upgasm"),
    PromptTarget("upgradeitems.gui", "BTN_BACK", 4, "B", "kmrpb_upgitm"),
    # The resolution screen was the one Options screen with no badge at all.
    # Its dispatcher at 0x006E0CF0 closes on 0x28 through
    # CSWGuiManager::PopModalPanel, so B is Cancel here as everywhere else.
    PromptTarget("optresolution.gui", "BTN_CANCEL", 1, "B", "kmrpb_rescancel"),

    # A on each screen's primary action. Weaker than the B badges above and
    # deliberately marked as such: A is Return, which activates whatever control
    # currently has focus, so this is a CONVENTION -- "A is how you commit on this
    # screen" -- not a guarantee that A hits this particular button from anywhere.
    # It is the same convention the original ten already used for Load, Get Items
    # and Upgrade Items. No badge is put on any "Default" button, because no
    # controller button performs restore-defaults at all.
    PromptTarget("optkeymapping.gui", "BTN_Accept", 2, "A", "kmrpa_optkeys"),
    PromptTarget("optgraphicsadv.gui", "BTN_BACK", 4, "A", "kmrpa_optgfxadv"),
    PromptTarget("optsoundadv.gui", "BTN_BACK", 3, "A", "kmrpa_optsndadv"),
    PromptTarget("upgradeitems.gui", "BTN_UPGRADEITEM", 3, "A", "kmrpa_upgitm"),
    PromptTarget("upgrade.gui", "BTN_ASSEMBLE", 24, "A", "kmrpa_upgasm"),
    PromptTarget("abilities.gui", "BTN_EXIT", 14, "B", "kmrpb_abilexit"),

    # Its sibling on the resolution screen. That dispatcher DOES implement
    # 0x27, at 0x006E0F14, calling CSWGuiOptionsResolution::OnResolutionChosen
    # regardless of focus, so KMRP routes A away from it when Cancel holds
    # focus -- see ResolveResolutionConfirmK1 in the module.
    PromptTarget("optresolution.gui", "BTN_OK", 0, "A", "kmrpa_resok"),
)


def _distance_to_segment(px: float, py: float, ax: float, ay: float,
                         bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _glyph_distance(glyph: str, x: float, y: float, cx: float, cy: float,
                    radius: float) -> float:
    s = radius * 0.58
    if glyph == "A":
        return min(
            _distance_to_segment(x, y, cx - s * 0.62, cy + s, cx, cy - s),
            _distance_to_segment(x, y, cx, cy - s, cx + s * 0.62, cy + s),
            _distance_to_segment(x, y, cx - s * 0.34, cy + s * 0.20,
                                 cx + s * 0.34, cy + s * 0.20),
        )
    if glyph == "X":
        return min(
            _distance_to_segment(x, y, cx - s * 0.65, cy - s * 0.85,
                                 cx + s * 0.65, cy + s * 0.85),
            _distance_to_segment(x, y, cx + s * 0.65, cy - s * 0.85,
                                 cx - s * 0.65, cy + s * 0.85),
        )
    if glyph == "Y":
        # Two arms meeting just above centre, then a stem to the base. Without
        # this branch "Y" fell through to the B shape below and drew a B on a
        # yellow disc. No current target uses Y, so nothing shipped wrong -- but
        # the original Xbox build puts Y on "Recommended" during character
        # generation, so the first Y target would have hit it.
        return min(
            _distance_to_segment(x, y, cx - s * 0.58, cy - s * 0.85,
                                 cx, cy - s * 0.05),
            _distance_to_segment(x, y, cx + s * 0.58, cy - s * 0.85,
                                 cx, cy - s * 0.05),
            _distance_to_segment(x, y, cx, cy - s * 0.05, cx, cy + s * 0.85),
        )
    # B: a spine plus two rounded bowls.  Trim the left half of each circle so
    # the letter reads as B rather than an 8 next to a line.
    spine = _distance_to_segment(x, y, cx - s * 0.52, cy - s,
                                 cx - s * 0.52, cy + s)
    upper = abs(math.hypot(x - (cx - s * 0.15), y - (cy - s * 0.48)) - s * 0.50)
    lower = abs(math.hypot(x - (cx - s * 0.15), y - (cy + s * 0.48)) - s * 0.50)
    if x < cx - s * 0.48:
        upper = lower = radius
    return min(spine, upper, lower)


def _blend(pixel: tuple[float, float, float, float], color: tuple[int, int, int],
           alpha: float) -> tuple[float, float, float, float]:
    src_a = max(0.0, min(1.0, alpha))
    dst_r, dst_g, dst_b, dst_a = pixel
    out_a = src_a + dst_a * (1.0 - src_a)
    if out_a <= 0:
        return 0.0, 0.0, 0.0, 0.0
    return (
        (color[0] * src_a + dst_r * dst_a * (1.0 - src_a)) / out_a,
        (color[1] * src_a + dst_g * dst_a * (1.0 - src_a)) / out_a,
        (color[2] * src_a + dst_b * dst_a * (1.0 - src_a)) / out_a,
        out_a,
    )


@lru_cache(maxsize=None)
def _load_glyph_art(glyph: str, family: str = GLYPH_FAMILY):
    """`family`'s CC0 glyph for `glyph`, cropped to its ink, or None.

    SWAP -- the whole "press X to swap tabs" phrase -- exists as art for Xbox
    only; another family shows its own X-position button there instead.

    A missing file falls back to the procedurally drawn badge, and that fallback
    is SILENT by design -- which is how the whole set came to be drawn discs
    after the art moved: the directory simply stopped existing and every badge
    quietly changed appearance. `check_glyph_art` exists so a build can ask.
    """
    from PIL import Image
    folder, art = GLYPH_FAMILIES[family]
    name = art.get(glyph)
    if name is None and glyph == "SWAP":
        name = art.get("X")
    if name is None:
        return None
    path = GLYPH_PACK / folder / name
    if not path.is_file():
        return None
    art = Image.open(path).convert("RGBA")
    box = art.getbbox()
    return art.crop(box) if box else art


def check_glyph_art(family: str = GLYPH_FAMILY):
    """(present, missing) action names for `family`. Loud where loading is quiet."""
    folder, art = GLYPH_FAMILIES[family]
    directory = GLYPH_PACK / folder
    present, missing = [], []
    for glyph, name in sorted(art.items()):
        (present if (directory / name).is_file() else missing).append(glyph)
    return present, missing


def vocabulary():
    """Every action the prompt system can depict, family-independent."""
    return sorted(GLYPH_FAMILIES[GLYPH_FAMILY][1])


def _composite_glyph_tga(control_width: int, control_height: int, glyph: str,
                         center_x: float, center_y: float, radius: float,
                         family: str = GLYPH_FAMILY) -> bytes:
    """Place the real glyph artwork, pre-compensated for the button stretch.

    The engine stretches BORDER.FILL across the whole control, so a square in
    CONTROL space is a rectangle in TEXTURE space. The art is therefore resized
    to that rectangle and comes out round in game.
    """
    art = _load_glyph_art(glyph, family)
    if art is None:
        return _legacy_drawn_tga(control_width, control_height, glyph)

    from PIL import Image
    # Fit the art inside the badge box while keeping its own proportions. The
    # face buttons are square (82x82) and unaffected, but the triggers are not
    # (LT and RT are 74x85), and scaling them to a square stretched them into
    # something that was recognisably not an Xbox trigger.
    diameter = radius * 2.0
    aspect = art.width / art.height
    box_w = diameter * aspect if aspect < 1.0 else diameter
    box_h = diameter / aspect if aspect > 1.0 else diameter
    dst_w = max(1, round(box_w * TEXTURE_WIDTH / control_width))
    dst_h = max(1, round(box_h * TEXTURE_HEIGHT / control_height))
    left = round((center_x - box_w / 2.0) * TEXTURE_WIDTH / control_width)
    top = round((center_y - box_h / 2.0) * TEXTURE_HEIGHT / control_height)

    sheet = Image.new("RGBA", (TEXTURE_WIDTH, TEXTURE_HEIGHT), (0, 0, 0, 0))
    resized = art.resize((dst_w, dst_h), Image.LANCZOS)
    # paste() clips anything past the edge instead of raising, and the sheet is
    # empty, so using the art's own alpha as the mask is a correct composite.
    sheet.paste(resized, (left, top), resized)

    # Store bottom-up: the descriptor below declares a bottom-left origin, which
    # is what all 40 sampled shipped KOTOR textures use.
    sheet = sheet.transpose(Image.FLIP_TOP_BOTTOM)
    r, g, b, a = sheet.split()
    header = struct.pack(
        "<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
        TEXTURE_WIDTH, TEXTURE_HEIGHT, 32, 0x08)
    return header + Image.merge("RGBA", (b, g, r, a)).tobytes() + TGA_FOOTER


@lru_cache(maxsize=None)
def build_prompt_tga(control_width: int, control_height: int, glyph: str,
                     label_width: float = 0.0,
                     radius_height: int = 0,
                     family: str = GLYPH_FAMILY) -> bytes:
    if control_width <= 0 or control_height <= 0:
        raise ValueError(f"Invalid prompt control extent {control_width}x{control_height}")
    center_y = control_height * 0.50
    # A badge in a group takes its size from the group's shortest control rather
    # than its own, so five entries in a menu carry five identical glyphs. Quit
    # is 81 tall where the rest are 66, and sizing it from itself made its A a
    # fifth larger than the others.
    sizing_height = radius_height if radius_height > 0 else control_height
    # The badge is sized from the button, but the LABEL is the same height on
    # every button, so on a short control 0.29 produced a glyph the player
    # reads as a dot beside full-size text -- visible on the Map screen's
    # 39px-tall Party Selection and Return To Ebon Hawk rows. Short controls
    # take a larger share of their height; normal ones are untouched.
    radius = sizing_height * (0.40 if sizing_height < 60 else 0.29)

    # Sit the badge immediately before the label, as the original Xbox build
    # does, instead of at a fixed inset from the button's left edge. KOTOR
    # centres a button's text, so on a 978px-wide button a left-pinned badge
    # floated most of a screen away from the words it belongs to.
    #
    # `label_width` is the measured pixel width of the label for this resolution
    # (font-atlases.md: the engine renders one texel per pixel). When it is
    # unknown -- no metrics, or a label we do not carry -- fall back to the old
    # fixed inset rather than guessing a position.
    if label_width > 0:
        gap = radius * 0.55
        center_x = (control_width - label_width) / 2.0 - gap - radius
        # Never let it leave the button, however long the label.
        center_x = max(radius * 1.15, center_x)
    else:
        center_x = control_height * 0.58
    return _composite_glyph_tga(control_width, control_height, glyph,
                                center_x, center_y, radius, family)


# A cue that is nothing but a glyph sits on its own square control, so unlike
# the caption badges it needs no pre-compensation for a button's stretch and one
# texture is correct at every resolution.
SQUARE_GLYPH_SIZE = 128
# How much of the square the glyph fills. Short of 1.0 so the art is not flush
# against the edges of the control, which reads as clipped.
SQUARE_GLYPH_FILL = 0.86


def build_square_glyph_tga(glyph: str, size: int = SQUARE_GLYPH_SIZE,
                           height: int | None = None,
                           family: str = GLYPH_FAMILY) -> bytes:
    """The glyph centred on a transparent texture, at its own proportions.

    `height` defaults to `size`, which is what a cue on a square control wants.
    Art that is not square -- the swap-tabs phrase is about two to one -- gets a
    texture of its own shape instead, and the control is given the same shape, so
    the engine's stretch is equal on both axes and nothing is distorted.

    Fails rather than falling back to the drawn placeholder: this texture IS the
    control, so a missing glyph would ship a screen with an empty box on it
    rather than a slightly worse badge.
    """
    if height is None:
        height = size
    art = _load_glyph_art(glyph, family)
    if art is None:
        raise ValueError(
            f"No artwork for {glyph!r}; a standalone cue has nothing else to draw")

    from PIL import Image

    aspect = art.width / art.height
    draw_w = size * SQUARE_GLYPH_FILL
    draw_h = draw_w / aspect
    if draw_h > height * SQUARE_GLYPH_FILL:
        draw_h = height * SQUARE_GLYPH_FILL
        draw_w = draw_h * aspect
    resized = art.resize((max(1, round(draw_w)), max(1, round(draw_h))),
                         Image.LANCZOS)

    sheet = Image.new("RGBA", (size, height), (0, 0, 0, 0))
    sheet.paste(resized,
                ((size - resized.width) // 2, (height - resized.height) // 2),
                resized)

    # Bottom-up, as every shipped KOTOR texture is.
    sheet = sheet.transpose(Image.FLIP_TOP_BOTTOM)
    r, g, b, a = sheet.split()
    header = struct.pack(
        "<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, size, height, 32, 0x08)
    return header + Image.merge("RGBA", (b, g, r, a)).tobytes() + TGA_FOOTER


def _legacy_drawn_tga(control_width: int, control_height: int, glyph: str) -> bytes:
    """The original procedurally drawn badge. Superseded by the CC0 artwork and
    kept only so a build can fall back if the artwork is ever unavailable."""
    center_x = control_height * 0.58
    center_y = control_height * 0.50
    radius = control_height * 0.29
    ring_width = max(1.5, control_height * 0.045)
    glyph_width = max(1.4, control_height * 0.047)
    pixels = bytearray(TEXTURE_WIDTH * TEXTURE_HEIGHT * 4)

    margin = max(ring_width, glyph_width) + 1.0
    source_x_end = min(
        TEXTURE_WIDTH,
        math.ceil((center_x + radius + margin) * TEXTURE_WIDTH / control_width),
    )
    source_y_start = max(
        0,
        math.floor((center_y - radius - margin) * TEXTURE_HEIGHT / control_height),
    )
    source_y_end = min(
        TEXTURE_HEIGHT,
        math.ceil((center_y + radius + margin) * TEXTURE_HEIGHT / control_height),
    )

    for sy in range(source_y_start, source_y_end):
        y = (sy + 0.5) * control_height / TEXTURE_HEIGHT
        for sx in range(source_x_end):
            x = (sx + 0.5) * control_width / TEXTURE_WIDTH
            radial = math.hypot(x - center_x, y - center_y)
            pixel = (0.0, 0.0, 0.0, 0.0)
            face = GLYPH_COLORS.get(glyph, GLYPH_FALLBACK)
            # Solid disc in the button's own colour, letter knocked out dark, as
            # the original Xbox build draws it. See GLYPH_COLORS for the measured
            # values and for why the previous ringed style read as UI decoration.
            fill_coverage = max(0.0, min(1.0, radius + 0.6 - radial))
            if fill_coverage:
                pixel = _blend(pixel, face, fill_coverage)
            letter_distance = _glyph_distance(
                glyph, x, y, center_x, center_y, radius)
            letter_coverage = max(0.0, min(1.0, glyph_width + 0.55 - letter_distance))
            if letter_coverage:
                pixel = _blend(pixel, GLYPH_INK, letter_coverage)

            r, g, b, a = pixel
            # Store bottom-up. The header declares descriptor 0x08 (bottom-left
            # origin), which is what every shipped KOTOR texture uses -- 40 of 40
            # sampled from assets/override-3440x1440 are depth 32, descriptor
            # 0x08 -- but this loop walks `sy` from the TOP of the control down.
            # Writing row `sy` straight to file row `sy` therefore stored every
            # badge mirrored, and the asymmetric glyphs (A, B, Y) rendered upside
            # down in game. X is symmetric about the horizontal axis, which is why
            # it looked correct and hid the fault.
            row = TEXTURE_HEIGHT - 1 - sy
            offset = (row * TEXTURE_WIDTH + sx) * 4
            pixels[offset:offset + 4] = bytes((round(b), round(g), round(r), round(a * 255)))

    header = struct.pack(
        "<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
        TEXTURE_WIDTH, TEXTURE_HEIGHT, 32, 0x08)
    return header + pixels + TGA_FOOTER



# Which dialog.tlk string each prompt button draws, so the badge can sit beside
# the TEXT rather than at a fixed inset. The engine centres a button's label, so
# a badge pinned to the left edge of a 978px-wide button floats far from the
# words it belongs to; the original Xbox build puts the glyph immediately before
# them.
#
# These are STRREFs read out of the buttons themselves, not names chosen here.
# Every one of the ten carries TEXT.STRREF and no inline TEXT string, so the
# label is whatever the player's own dialog.tlk holds for that reference -- which
# is why the installer resolves them again against the real file (see
# `kmrp_prompts.txt` below and ControllerPromptGenerator in the patcher). The
# English widths baked here are only the fallback for an install whose dialog.tlk
# cannot be read.
#
# A hand-written table keyed by tag used to live here and was wrong for five of
# the ten: BTN_CANCEL and both BTN_BACKs are STRREF 1582 "Close", not "Cancel" or
# "Back", and BTN_SAVELOAD is 1587 "Save", not "Load". BTN_GIVEITEMS was measured
# as the 20-character "Switch To Give Items" when the strings are 47884
# "Switch To" and 47885 "Give Item".
#
# Two of them are set by code at runtime rather than from a single reference, so
# each target carries a tuple of VARIANTS and is measured against the widest:
#   BTN_SAVELOAD  1587 "Save" on the save screen, 1589 "Load" on the load screen.
#   BTN_GIVEITEMS 47884 + 47885 concatenated. dialog.tlk holds no "Take Item",
#                 so only the give-side wording is known and measured.
PROMPT_STRREFS = {
    ("character.gui", "BTN_EXIT"): ((1582,),),
    ("character.gui", "BTN_SCRIPTS"): ((1067,),),
    ("container.gui", "BTN_OK"): ((38542,),),
    ("container.gui", "BTN_GIVEITEMS"): ((47884, 47885),),
    ("container.gui", "BTN_CANCEL"): ((1582,),),
    ("saveload.gui", "BTN_DELETE"): ((1560,),),
    ("saveload.gui", "BTN_BACK"): ((1581,),),
    ("saveload.gui", "BTN_SAVELOAD"): ((1587,), (1589,)),
    ("upgradesel.gui", "BTN_UPGRADEITEMS"): ((42295,),),
    ("upgradesel.gui", "BTN_BACK"): ((1582,),),

    # The in-game tab screens. Every STRREF read from the button's own
    # TEXT.STRREF in the .gui, not guessed: the badge is placed against the
    # measured width of the real label, and a missing entry silently falls back
    # to a fixed inset that leaves the glyph floating on a 1500px button.
    ("mainmenu.gui", "BTN_NEWGAME"): ((1586,),),
    ("mainmenu.gui", "BTN_LOADGAME"): ((1585,),),
    ("mainmenu.gui", "BTN_MOVIES"): ((1583,),),
    ("mainmenu.gui", "BTN_OPTIONS"): ((1584,),),
    ("mainmenu.gui", "BTN_EXIT"): ((42172,),),
    ("scriptselect.gui", "BTN_Accept"): ((236,),),
    ("scriptselect.gui", "BTN_Back"): ((1581,),),
    # The caption swaps: the branch at 0x006BECD0 pushes 38455 "Add" or
    # 38456 "Remove". Placed against the wider of the two, so it never lands
    # on the letters.
    ("partyselection.gui", "BTN_ACCEPT"): ((38455,), (38456,)),
    ("partyselection.gui", "BTN_DONE"): ((1580,),),
    ("partyselection.gui", "BTN_BACK"): ((1581,),),

    ("equip.gui", "BTN_EQUIP"): ((1580,),),
    ("equip.gui", "BTN_BACK"): ((1582,),),
    ("questitem.gui", "BTN_BACK"): ((1582,),),

    ("inventory.gui", "BTN_EXIT"): ((1582,),),
    ("inventory.gui", "BTN_USEITEM"): ((333,),),
    # Not 32182. That is the bare words "Quest Items", which this button never
    # says: CSWGuiInGameInventory builds the caption as STRREF 42359 "Show"
    # followed by the filter it will switch to (0x006B3AAC pushes 0xA577, two
    # appends at 0x006B3ADD and 0x006B3AF6).
    #
    # ORDER MATTERS HERE. These are the six entries of the engine's own STRREF
    # table at 0x00756444, in its order, because the module picks the matching
    # texture by the same index the engine uses -- the byte at CGuiInGame+0xBC1,
    # plus one, wrapping at six (0x006B3A5D..0x006B3A6E).
    #
    # Six, not five: an earlier pass listed the consecutive strings 41818..41822
    # and missed "New Items", which sits apart at 42165 and is the one the
    # resref kmrpx_invnew was named for.
    ("inventory.gui", "BTN_QUESTITEMS"): ((42359, 41822),    # 0 All Items
                                          (42359, 42165),    # 1 New Items
                                          (42359, 41818),    # 2 Quest Items
                                          (42359, 41821),    # 3 Equippable Items
                                          (42359, 41819),    # 4 Utility Items
                                          (42359, 41820)),   # 5 Useable Items
    ("messages.gui", "BTN_EXIT"): ((1582,),),
    # Toggles: "Show Feedback" / "Show Dialog". The first is the wider, so this
    # was already placed correctly in English -- but the installer re-measures
    # against the player's own dialog.tlk, where the other may be wider.
    ("messages.gui", "BTN_SHOW"): ((42142,), (42143,)),
    ("journal.gui", "BTN_QUESTITEMS"): ((32182,),),
    # Toggles: "Completed Quests" / "Active Quests".
    ("journal.gui", "BTN_SWAPTEXT"): ((32177,), (32178,)),
    # Cycles the four sort orders. "by Order Received" is the widest in English.
    ("journal.gui", "BTN_SORT"): ((32173,), (32174,), (32175,), (32176,)),
    ("journal.gui", "BTN_EXIT"): ((1582,),),
    ("map.gui", "BTN_RETURN"): ((32179,),),
    ("map.gui", "BTN_PRTYSLCT"): ((32180,),),
    ("map.gui", "BTN_EXIT"): ((1582,),),

    # The screens added 2026-09-06. 1582 "Close", 1581 "Cancel" -- read from each
    # button's own TEXT.STRREF, which is why two of them are Cancel where the tag
    # says BACK and the other way round.
    ("optionsmain.gui", "BTN_BACK"): ((1582,),),
    ("optionsingame.gui", "BTN_EXIT"): ((1582,),),
    ("optgameplay.gui", "BTN_BACK"): ((1582,),),
    ("optautopause.gui", "BTN_BACK"): ((1582,),),
    ("optfeedback.gui", "BTN_BACK"): ((1582,),),
    ("optmouse.gui", "BTN_BACK"): ((1582,),),
    ("optgraphics.gui", "BTN_BACK"): ((1582,),),
    ("optgraphicsadv.gui", "BTN_CANCEL"): ((1581,),),
    ("optsound.gui", "BTN_BACK"): ((1582,),),
    ("optsoundadv.gui", "BTN_CANCEL"): ((1581,),),
    ("optkeymapping.gui", "BTN_Cancel"): ((1581,),),
    ("upgrade.gui", "BTN_BACK"): ((1581,),),
    ("upgradeitems.gui", "BTN_BACK"): ((1582,),),
    ("optresolution.gui", "BTN_CANCEL"): ((1581,),),
    ("optresolution.gui", "BTN_OK"): ((1580,),),
    ("optkeymapping.gui", "BTN_Accept"): ((1580,),),
    ("optgraphicsadv.gui", "BTN_BACK"): ((1580,),),
    ("optsoundadv.gui", "BTN_BACK"): ((1580,),),
    ("upgradeitems.gui", "BTN_UPGRADEITEM"): ((42294,),),
    ("upgrade.gui", "BTN_ASSEMBLE"): ((42021,),),
    ("abilities.gui", "BTN_EXIT"): ((1582,),),
}

# The English text of every STRREF above, as shipped in the retail dialog.tlk.
# Used only to bake the fallback placement into the texture; the installer
# overrides it from the player's own file whenever that file can be read.
PROMPT_FALLBACK_STRINGS = {
    1067: "Scripts",
    1560: "Delete",
    1581: "Cancel",
    1580: "OK",
    1582: "Close",
    1587: "Save",
    1589: "Load",
    38542: "Get Items",
    42295: "Upgrade Items",
    47884: "Switch To",
    42021: "Assemble",
    42294: "Upgrade Item",
    47885: "Give Item",

    # The captions the toggling buttons build at runtime. Only used when the
    # installer cannot read the player's dialog.tlk -- it re-resolves all of
    # these against the real file and re-centres each badge.
    42359: "Show",
    41818: "Quest Items",
    41819: "Utility Items",
    41820: "Useable Items",
    41821: "Equippable Items",
    41822: "All Items",
    42165: "New Items",
    1583: "Movies",
    1584: "Options",
    1585: "Load Game",
    1586: "New Game",
    42172: "Quit",
    236: "Select",
    38455: "Add",
    38456: "Remove",
    42142: "Show Feedback",
    42143: "Show Dialog",
    32177: "Completed Quests",
    32178: "Active Quests",
    32173: "by Order Received",
    32174: "by Name",
    32175: "by Priority",
    32176: "by Planet",
}

# Buttons that get one badge texture PER CAPTION, named <resref><index>, chosen
# at runtime by the module from the engine's own state. Everything else keeps a
# single texture placed against its widest wording, which never overlaps but can
# sit a little wide of a short caption.
#
# Only worth it where the captions differ a lot and the module has an index it
# can read without guessing. The inventory filter is both: six wordings from
# "Show All Items" to "Show Equippable Items", and the index is a byte at
# CGuiInGame+0xBC1.
# Badges that must line up as a column rather than each hugging its own label,
# and share one glyph size. The main menu is a list of entries, and five A's that
# step left and right down it -- one of them larger than the rest -- read as a
# mistake rather than a layout.
#
# Every member is placed against the widest label in its group and sized from the
# shortest control in it.
BADGE_GROUPS = {
    ("mainmenu.gui", "BTN_NEWGAME"): "mainmenu",
    ("mainmenu.gui", "BTN_LOADGAME"): "mainmenu",
    ("mainmenu.gui", "BTN_MOVIES"): "mainmenu",
    ("mainmenu.gui", "BTN_OPTIONS"): "mainmenu",
    ("mainmenu.gui", "BTN_EXIT"): "mainmenu",
}

PER_CAPTION_TARGETS = frozenset({
    ("inventory.gui", "BTN_QUESTITEMS"),
})

PROMPT_MANIFEST_NAME = "kmrp_prompts.txt"


def variant_strings(variants, strings):
    """Each variant rendered as the single line the button will show."""
    out = []
    for variant in variants:
        parts = [strings.get(ref) for ref in variant]
        if any(part is None for part in parts):
            continue
        out.append(" ".join(parts))
    return out


def parse_font_metrics(txi_path: Path):
    """Per-character pixel advances for a KOTOR font atlas.

    The engine renders one texel per pixel, so a glyph's on-screen width is
    `(lowerright.u - upperleft.u) * texturewidth * 100` -- see
    `reverse-engineering/font-atlases.md`. Returns (advances, spacing_px), both
    already in pixels for the resolution this TXI was generated for.
    """
    text = txi_path.read_text(encoding="ascii", errors="replace").splitlines()
    texture_width = 0.0
    spacing = 0.0
    upper: list[float] = []
    lower: list[float] = []
    mode = None
    for line in text:
        parts = line.split()
        if not parts:
            continue
        head = parts[0].lower()
        if head == "texturewidth" and len(parts) > 1:
            texture_width = float(parts[1]); mode = None
        elif head == "spacingr" and len(parts) > 1:
            spacing = float(parts[1]); mode = None
        elif head == "upperleftcoords":
            mode = "upper"
        elif head == "lowerrightcoords":
            mode = "lower"
        elif mode and len(parts) >= 2:
            try:
                value = float(parts[0])
            except ValueError:
                mode = None
                continue
            (upper if mode == "upper" else lower).append(value)
    if not texture_width or not upper or len(lower) < len(upper):
        return None, 0.0
    advances = [(lower[i] - upper[i]) * texture_width * 100.0
                for i in range(min(len(upper), len(lower)))]
    return advances, spacing * texture_width * 100.0


def measure_label(label: str, advances, spacing_px: float) -> float:
    if not advances:
        return 0.0
    total = 0.0
    for index, ch in enumerate(label):
        code = ord(ch)
        if code < len(advances):
            total += advances[code]
        if index:
            total += spacing_px
    return total


def build_prompt_textures(gui_files: list[Path], output_dir: Path) -> list[Path]:
    by_name = {path.name.lower(): path for path in gui_files}
    output_dir.mkdir(parents=True, exist_ok=True)
    # The button font's metrics for THIS resolution, so the badge can be placed
    # against the real label width rather than a guess.
    txi = by_name.get("dialogfont16x16.txi")
    advances, spacing_px = parse_font_metrics(txi) if txi else (None, 0.0)
    results: list[Path] = []
    manifest = []
    loaded = {}

    def control_for(target):
        path = by_name.get(target.gui)
        if path is None:
            raise ValueError(f"Controller prompt source is missing: {target.gui}")
        controls = loaded.get(target.gui)
        if controls is None:
            controls = read_gff(path).root.get_list("CONTROLS")
            loaded[target.gui] = controls
        if controls is None or target.control_index >= len(controls):
            raise ValueError(f"{target.gui}: missing control index {target.control_index}")
        return controls[target.control_index]

    # First pass: what does each GROUP look like as a whole? Members are placed
    # against the widest label in the group and sized from the shortest control
    # in it, so a menu carries one column of identical glyphs instead of five
    # that step sideways and change size.
    group_label_width: dict = {}
    group_height: dict = {}
    group_variants: dict = {}
    for target in PROMPT_TARGETS:
        group = BADGE_GROUPS.get((target.gui, target.tag))
        if group is None:
            continue
        control = control_for(target)
        extent = control.get_struct("EXTENT")
        if extent is None:
            raise ValueError(f"{target.gui}:{target.tag} has no extent")
        height = extent.get_int32("HEIGHT")
        variants = PROMPT_STRREFS.get((target.gui, target.tag), ())
        width = max((measure_label(label, advances, spacing_px)
                     for label in variant_strings(variants, PROMPT_FALLBACK_STRINGS)),
                    default=0.0)
        group_label_width[group] = max(group_label_width.get(group, 0.0), width)
        group_height[group] = min(group_height.get(group, height), height)
        group_variants.setdefault(group, [])
        for variant in variants:
            if variant not in group_variants[group]:
                group_variants[group].append(variant)

    for target in PROMPT_TARGETS:
        path = by_name.get(target.gui)
        if path is None:
            raise ValueError(f"Controller prompt source is missing: {target.gui}")
        controls = loaded.get(target.gui)
        if controls is None:
            controls = read_gff(path).root.get_list("CONTROLS")
            loaded[target.gui] = controls
        if controls is None or target.control_index >= len(controls):
            raise ValueError(f"{target.gui}: missing control index {target.control_index}")
        control = controls[target.control_index]
        actual_tag = control.get_string("TAG")
        if actual_tag != target.tag:
            raise ValueError(
                f"{target.gui}[{target.control_index}] is {actual_tag!r}, expected {target.tag!r}")
        extent = control.get_struct("EXTENT")
        border = control.get_struct("BORDER")
        if extent is None or border is None:
            raise ValueError(f"{target.gui}:{target.tag} has no extent or normal border")
        if str(border.get_resref("FILL")):
            raise ValueError(f"{target.gui}:{target.tag} has a non-empty normal fill")
        variants = PROMPT_STRREFS.get((target.gui, target.tag), ())
        labels = variant_strings(variants, PROMPT_FALLBACK_STRINGS)
        # The widest wording the button can show. A badge measured against the
        # narrower one would be overlapped by the wider one; measured against the
        # wider one it merely sits a little further out on the narrow variant.
        label_width = max(
            (measure_label(label, advances, spacing_px) for label in labels),
            default=0.0)
        width = extent.get_int32("WIDTH")
        height = extent.get_int32("HEIGHT")

        # A grouped badge is placed and sized against its group, and carries the
        # group's combined variants into the manifest. That last part is what
        # keeps the column aligned after the installer re-measures against the
        # player's own dialog.tlk: its shift works out to (baked - measured) / 2,
        # so identical variants give identical shifts.
        group = BADGE_GROUPS.get((target.gui, target.tag))
        radius_height = 0
        if group is not None:
            label_width = group_label_width[group]
            radius_height = group_height[group]
            variants = tuple(group_variants[group])

        # Once per family, identically placed: only the art differs, so the
        # installer's re-centring treats every family's copy the same way.
        for family in GLYPH_FAMILIES:
            resref = family_resref(target.resref, family)
            output = output_dir / f"{resref}.tga"
            output.write_bytes(build_prompt_tga(
                width, height, target.glyph, round(label_width, 2), radius_height,
                family))
            results.append(output)
            manifest.append((resref, width, height, round(label_width, 2),
                             variants))

        # One texture per caption, for the buttons the module can index. Each is
        # placed against its OWN wording and carries only that wording in the
        # manifest, so the installer re-centres each against the player's real
        # dialog.tlk exactly as it does a single-caption button.
        #
        # The plain resref above stays, placed against the widest, as the
        # fallback for a module that cannot read the index.
        if (target.gui, target.tag) in PER_CAPTION_TARGETS:
            if len(target.resref) > 12:
                raise ValueError(
                    f"{target.resref} leaves no room for a variant suffix "
                    f"within a 16-character resref")
            for index, variant in enumerate(variants):
                one = variant_strings((variant,), PROMPT_FALLBACK_STRINGS)
                one_width = measure_label(one[0], advances, spacing_px) if one else 0.0
                for family in GLYPH_FAMILIES:
                    resref = family_resref(f"{target.resref}{index}", family)
                    path = output_dir / f"{resref}.tga"
                    path.write_bytes(build_prompt_tga(
                        width, height, target.glyph, round(one_width, 2), 0, family))
                    results.append(path)
                    manifest.append((resref, width, height, round(one_width, 2),
                                     (variant,)))

    # Placement manifest for the installer. The badge artwork does not depend on
    # the label -- only its horizontal position does, and that position moves by
    # exactly half of any change in label width (center_x = (w - label) / 2 - gap
    # - radius). So the installer never re-renders anything: it resolves these
    # STRREFs against the player's real dialog.tlk, measures with the advances
    # carried here, and slides the already-composited badge sideways.
    #
    # The advances are embedded rather than left to the installer to parse out of
    # dialogfont16x16.txi, because that TXI is written by this same build into the
    # same archive and depending on install ORDER for correctness would be a trap.
    if advances and manifest:
        lines = ["# KMRP controller prompt placement. Generated; do not edit.",
                 "version 1",
                 f"texture {TEXTURE_WIDTH} {TEXTURE_HEIGHT}",
                 f"spacing {spacing_px:.6f}",
                 "advances " + " ".join(f"{value:.6f}" for value in advances)]
        for resref, width, height, baked, variants in manifest:
            encoded = ";".join("+".join(str(ref) for ref in variant)
                               for variant in variants) or "-"
            lines.append(f"prompt {resref} {width} {height} {baked:.2f} {encoded}")
        path = output_dir / PROMPT_MANIFEST_NAME
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        results.append(path)
    return results
