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
        # The 360 triggers, like the rest of the set (chosen 2026-09-24; they
        # were the Series X art, to match the R3 cue). No caption badge uses
        # either glyph, so this reaches the tab-strip cues and the Controller
        # Layout screen's LT and RT rows.
        "LT": "360_LT.png", "RT": "360_RT.png",
        "START": "360_Start.png", "BACK": "360_Back.png",
        "DPAD_LEFT": "360_Dpad_Left.png", "DPAD_RIGHT": "360_Dpad_Right.png",
        "DPAD_UP": "360_Dpad_Up.png", "DPAD_DOWN": "360_Dpad_Down.png",
        # R3 is the Series X art, which is the file the badge was asked for by
        # name. L3 is left on the 360 art deliberately rather than changed to
        # match: nothing uses it yet, and silently restyling an unused glyph
        # is a change nobody asked for. If L3 is ever badged, pick one.
        # Not a button: the whole "press X to swap tabs" phrase, X and
        # arrows together, as one piece of art. One per family since
        # 2026-09-24, drawn to match; the Xbox file's doubled extension is its
        # real name on disk.
        "SWAP": "Swap_tabs_360.png.png",
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
        "SWAP": "Swap_tabs_PS5.png",
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
        "SWAP": "Swap_tabs_Switch.png",
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
        "SWAP": "Swap_tabs_SteamDeck.png",
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
    # The button's own fill, a key of BACKINGS, when it has one: the badge is
    # drawn on it rather than on an empty sheet, and the module puts it back
    # whenever the badge is not shown. Empty for the usual empty-fill button.
    backing: str = ""
    # The tag of a control on the same screen whose height sizes the glyph,
    # for a button much taller than the screen's others. Empty: its own.
    size_like: str = ""


# A button fill a badge can stand on, as the uniform colour it is. Measured,
# not assumed: a fill that is not one colour cannot be a backing, because the
# installer slides badges sideways and fills the gap from the edge column.
BACKINGS = {
    # swpc_tex_gui.erf: 16x16, every texel (0, 0, 0, 128), TXI "mipmap 0"
    # (read 2026-09-26). The box behind the Character screen's Level Up and
    # Auto Level Up, and the status summary's panel.
    "dialog2": (0, 0, 0, 128),
}


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
    # The Movies screen, from the main menu. Its dispatcher at 0x006DCE80 closes on
    # 0x28 (and 0x2E) through 0x006DCEA0, so B is Close here too.
    PromptTarget("titlemovie.gui", "BTN_BACK", 2, "B", "kmrpb_movies"),
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
    # and Upgrade Items. No badge was put on any "Default" button, because no
    # controller button performed restore-defaults at all; since 2026-09-25 Y
    # does, and every Default carries a Y (the settings block at the end).
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

    # Character creation and level-up, added 2026-09-25. Tags, indices, empty
    # fills and widths checked in all 49 archives before these went in. Each
    # glyph is the button the screen's own dispatcher answers: B closes or steps
    # back everywhere; Y is Recommended (Attributes, Skills, Feats, Powers) and
    # Random Name; X is Feats' Add and Powers' Select (Feats' A and X are swapped
    # by the module to match); A is OK, or the focused step on
    # the step lists, and the screen's A elsewhere -- see the module's tables
    # for the variants and docs/controller-prompt-specification.md for why.
    # The class portraits carry art and take no badge. The +/- arrows carry art
    # too, and keep it.
    PromptTarget("classsel.gui", "BTN_BACK", 6, "B", "kmrpb_clsback"),
    PromptTarget("qorcpnl.gui", "QUICK_CHAR_BTN", 4, "A", "kmrpa_qcquick"),
    PromptTarget("qorcpnl.gui", "CUST_CHAR_BTN", 5, "A", "kmrpa_qccust"),
    PromptTarget("qorcpnl.gui", "BTN_BACK", 1, "B", "kmrpb_qcback"),
    PromptTarget("custpnl.gui", "BTN_STEPNAME1", 7, "A", "kmrpa_cust1"),
    PromptTarget("custpnl.gui", "BTN_STEPNAME2", 9, "A", "kmrpa_cust2"),
    PromptTarget("custpnl.gui", "BTN_STEPNAME3", 11, "A", "kmrpa_cust3"),
    PromptTarget("custpnl.gui", "BTN_STEPNAME4", 13, "A", "kmrpa_cust4"),
    PromptTarget("custpnl.gui", "BTN_STEPNAME5", 15, "A", "kmrpa_cust5"),
    PromptTarget("custpnl.gui", "BTN_STEPNAME6", 17, "A", "kmrpa_cust6"),
    PromptTarget("custpnl.gui", "BTN_BACK", 19, "B", "kmrpb_custback"),
    PromptTarget("custpnl.gui", "BTN_CANCEL", 20, "A", "kmrpa_custcncl"),
    PromptTarget("quickpnl.gui", "BTN_STEPNAME1", 6, "A", "kmrpa_quik1"),
    PromptTarget("quickpnl.gui", "BTN_STEPNAME2", 8, "A", "kmrpa_quik2"),
    PromptTarget("quickpnl.gui", "BTN_STEPNAME3", 10, "A", "kmrpa_quik3"),
    PromptTarget("quickpnl.gui", "BTN_BACK", 1, "B", "kmrpb_quikback"),
    PromptTarget("quickpnl.gui", "BTN_CANCEL", 2, "A", "kmrpa_quikcncl"),
    PromptTarget("portcust.gui", "BTN_ACCEPT", 11, "A", "kmrpa_portok"),
    PromptTarget("portcust.gui", "BTN_BACK", 12, "B", "kmrpb_portback"),
    PromptTarget("abchrgen.gui", "BTN_ACCEPT", 35, "A", "kmrpa_abcgok"),
    PromptTarget("abchrgen.gui", "BTN_RECOMMENDED", 34, "Y", "kmrpy_abcgrec"),
    PromptTarget("abchrgen.gui", "BTN_BACK", 36, "B", "kmrpb_abcgback"),
    PromptTarget("skchrgen.gui", "BTN_ACCEPT", 41, "A", "kmrpa_skcgok"),
    PromptTarget("skchrgen.gui", "BTN_RECOMMENDED", 40, "Y", "kmrpy_skcgrec"),
    PromptTarget("skchrgen.gui", "BTN_BACK", 42, "B", "kmrpb_skcgback"),
    PromptTarget("ftchrgen.gui", "BTN_SELECT", 9, "X", "kmrpx_ftcgadd"),
    PromptTarget("ftchrgen.gui", "BTN_ACCEPT", 10, "A", "kmrpa_ftcgok"),
    PromptTarget("ftchrgen.gui", "BTN_RECOMMENDED", 8, "Y", "kmrpy_ftcgrec"),
    PromptTarget("ftchrgen.gui", "BTN_BACK", 11, "B", "kmrpb_ftcgback"),
    PromptTarget("name.gui", "END_BTN", 3, "A", "kmrpa_nameok"),
    PromptTarget("name.gui", "BTN_RANDOM", 4, "Y", "kmrpy_namernd"),
    PromptTarget("name.gui", "BTN_BACK", 5, "B", "kmrpb_nameback"),
    PromptTarget("leveluppnl.gui", "BTN_STEPNAME1", 13, "A", "kmrpa_lvl1"),
    PromptTarget("leveluppnl.gui", "BTN_STEPNAME2", 14, "A", "kmrpa_lvl2"),
    PromptTarget("leveluppnl.gui", "BTN_STEPNAME3", 15, "A", "kmrpa_lvl3"),
    PromptTarget("leveluppnl.gui", "BTN_STEPNAME4", 12, "A", "kmrpa_lvl4"),
    PromptTarget("leveluppnl.gui", "BTN_STEPNAME5", 16, "A", "kmrpa_lvl5"),
    PromptTarget("leveluppnl.gui", "BTN_BACK", 1, "B", "kmrpb_lvlback"),
    PromptTarget("pwrlvlup.gui", "ACCEPT_BTN", 10, "A", "kmrpa_pwrok"),
    PromptTarget("pwrlvlup.gui", "SELECT_BTN", 9, "X", "kmrpx_pwrsel"),
    PromptTarget("pwrlvlup.gui", "RECOMMENDED_BTN", 8, "Y", "kmrpy_pwrrec"),
    PromptTarget("pwrlvlup.gui", "BACK_BTN", 11, "B", "kmrpb_pwrback"),

    # Every settings screen, completed 2026-09-25 at the maintainer's request
    # ("add glyphs to all settings screens"). Tags, indices, empty fills and
    # STRREFs are checked in all 49 archives by the build and by
    # Test-ControllerPromptAssets.py.
    #
    # Y is Default. No settings panel answers Y itself -- the five Y
    # registrations on Graphics and Sound are their sliders' own change
    # callbacks (0x006E0190, 0x006E0F50), not a button -- so the module presses
    # the screen's Default button for it (PressDefaultK1 in K1NativeJoystick.cpp).
    # That reverses the rule stated above, "no badge on any Default button",
    # which held only while no controller button performed it.
    #
    # A follows the focus on the buttons that open another screen and down the
    # two Options lists, like the main menu's: A activates the focused control,
    # so the badge is true only on that one (FocusOnly in the module).
    PromptTarget("optgraphics.gui", "BTN_DEFAULT", 4, "Y", "kmrpy_optgfxdef"),
    PromptTarget("optgraphics.gui", "BTN_RESOLUTION", 6, "A", "kmrpa_optgfxres"),
    PromptTarget("optgraphics.gui", "BTN_ADVANCED", 9, "A", "kmrpa_optgfxadvn"),
    PromptTarget("optgraphicsadv.gui", "BTN_DEFAULT", 2, "Y", "kmrpy_optgfxadef"),
    PromptTarget("optsound.gui", "BTN_DEFAULT", 10, "Y", "kmrpy_optsnddef"),
    PromptTarget("optsound.gui", "BTN_ADVANCED", 12, "A", "kmrpa_optsndadvn"),
    PromptTarget("optsoundadv.gui", "BTN_DEFAULT", 2, "Y", "kmrpy_optsndadef"),
    PromptTarget("optgameplay.gui", "BTN_DEFAULT", 11, "Y", "kmrpy_optgamedef"),
    PromptTarget("optgameplay.gui", "BTN_MOUSE", 13, "A", "kmrpa_optgamemse"),
    PromptTarget("optgameplay.gui", "BTN_KEYMAP", 12, "A", "kmrpa_optgamekey"),
    # KMRP's own entry, bound at run time (K1ControllerLayout.cpp), so its A is
    # painted there rather than through the offset table.
    PromptTarget("optgameplay.gui", "BTN_KMRPLAY", 14, "A", "kmrpa_optgamelay"),
    PromptTarget("optmouse.gui", "BTN_DEFAULT", 3, "Y", "kmrpy_optmsedef"),
    PromptTarget("optfeedback.gui", "BTN_DEFAULT", 3, "Y", "kmrpy_optfeeddef"),
    PromptTarget("optautopause.gui", "BTN_DEFAULT", 8, "Y", "kmrpy_optpsedef"),
    PromptTarget("optkeymapping.gui", "BTN_Default", 1, "Y", "kmrpy_optkeysdef"),
    PromptTarget("optionsmain.gui", "BTN_GAMEPLAY", 1, "A", "kmrpa_omgame"),
    PromptTarget("optionsmain.gui", "BTN_FEEDBACK", 5, "A", "kmrpa_omfeed"),
    PromptTarget("optionsmain.gui", "BTN_AUTOPAUSE", 2, "A", "kmrpa_ompause"),
    PromptTarget("optionsmain.gui", "BTN_GRAPHICS", 3, "A", "kmrpa_omgfx"),
    PromptTarget("optionsmain.gui", "BTN_SOUND", 4, "A", "kmrpa_omsnd"),
    PromptTarget("optionsingame.gui", "BTN_LOADGAME", 0, "A", "kmrpa_oiload"),
    PromptTarget("optionsingame.gui", "BTN_SAVEGAME", 1, "A", "kmrpa_oisave"),
    PromptTarget("optionsingame.gui", "BTN_GAMEPLAY", 2, "A", "kmrpa_oigame"),
    PromptTarget("optionsingame.gui", "BTN_FEEDBACK", 5, "A", "kmrpa_oifeed"),
    PromptTarget("optionsingame.gui", "BTN_AUTOPAUSE", 6, "A", "kmrpa_oipause"),
    PromptTarget("optionsingame.gui", "BTN_GRAPHICS", 7, "A", "kmrpa_oigfx"),
    PromptTarget("optionsingame.gui", "BTN_SOUND", 8, "A", "kmrpa_oisnd"),
    PromptTarget("optionsingame.gui", "BTN_QUIT", 3, "A", "kmrpa_oiquit"),
    # Pazaak's wager. Its dispatcher (0x0067E150) accepts on A and quits on B
    # whatever holds focus, and moves the wager on the D-pad itself.
    PromptTarget("pazaakwager.gui", "BTN_WAGER", 7, "A", "kmrpa_pzkwager"),
    PromptTarget("pazaakwager.gui", "BTN_QUIT", 6, "B", "kmrpb_pzkquit"),

    # The Character screen's Level Up and Auto Level Up (2026-09-26). The
    # screen levels up on A and auto-levels on Y itself (0x006B2295,
    # 0x006B233C), with nothing focused, so neither badge follows the focus;
    # the buttons are drawn only while the member on screen can level up.
    # They stand on the buttons' own box, dialog2, and are sized like the
    # screen's Close and Scripts badges -- sized from themselves, 120 and
    # 156 px tall at 3440x1440, they came out half as large again.
    PromptTarget("character.gui", "BTN_LEVELUP", 63, "A", "kmrpa_charlvl",
                 backing="dialog2", size_like="BTN_EXIT"),
    PromptTarget("character.gui", "BTN_AUTO", 62, "Y", "kmrpy_charauto",
                 backing="dialog2", size_like="BTN_EXIT"),
    # "You have been granted the following feat(s) this level" (skillinfo.gui),
    # the notice Feats opens with. Its dispatcher (0x006CD3C0) closes it on A
    # whatever holds focus.
    PromptTarget("skillinfo.gui", "BTN_OK", 2, "A", "kmrpa_skillok"),
)


# The - and + arrows keep the game's own art. From 2026-09-25 to 2026-09-28
# they showed the D-pad's left and right in its place (ArrowTarget,
# ARROW_TARGETS); removed at the maintainer's request.


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

    SWAP -- the whole "press X to swap tabs" phrase -- has art for every family
    since 2026-09-24; a family without it would show its own X-position button
    there instead.

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
                         family: str = GLYPH_FAMILY,
                         backing: tuple | None = None) -> bytes:
    """Place the real glyph artwork, pre-compensated for the button stretch.

    The engine stretches BORDER.FILL across the whole control, so a square in
    CONTROL space is a rectangle in TEXTURE space. The art is therefore resized
    to that rectangle and comes out round in game.
    """
    art = _load_glyph_art(glyph, family)
    if art is None:
        if backing is not None:
            # The drawn fallback has no backing; a button that keeps its box
            # must not lose it to a missing file.
            raise ValueError(f"No {family} artwork for {glyph!r} on a backed badge")
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
    if backing is None:
        # paste() clips anything past the edge instead of raising, and the sheet
        # is empty, so using the art's own alpha as the mask is a correct
        # composite.
        sheet.paste(resized, (left, top), resized)
    else:
        # On the button's own fill: the art laid over it as the engine would
        # blend it, so its edges fade into the box rather than punching
        # through it.
        sheet.paste(resized, (left, top))
        sheet = Image.alpha_composite(
            Image.new("RGBA", (TEXTURE_WIDTH, TEXTURE_HEIGHT), backing), sheet)

    # Store bottom-up: the descriptor below declares a bottom-left origin, which
    # is what all 40 sampled shipped KOTOR textures use.
    sheet = sheet.transpose(Image.FLIP_TOP_BOTTOM)
    r, g, b, a = sheet.split()
    header = struct.pack(
        "<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
        TEXTURE_WIDTH, TEXTURE_HEIGHT, 32, 0x08)
    return header + Image.merge("RGBA", (b, g, r, a)).tobytes() + TGA_FOOTER


BADGE_GAP = 0.55          # of the radius, between the badge and the label
BADGE_EDGE = 1.15         # of the radius, the least from the button's edge to the badge's centre
BADGE_RADIUS = 0.29       # of the sizing height
BADGE_RADIUS_SHORT = 0.40  # of the sizing height, for a control shorter than BADGE_SHORT_BELOW
BADGE_SHORT_BELOW = 60
BADGE_CENTER_Y = 0.50     # of the control's height, where the badge's centre sits
BADGE_FALLBACK_X = 0.58   # of the control's height, the centre when the label width is unknown
# (Carried into gui-blend.bin too, for the installers' Container fit and the badges
# they make for a size with no set: tools/build_gui_blend_table.py.)


def badge_radius(sizing_height: int) -> float:
    # The badge is sized from the button, but the LABEL is the same height on
    # every button, so on a short control 0.29 produced a glyph the player
    # reads as a dot beside full-size text -- visible on the Map screen's
    # 39px-tall Party Selection and Return To Ebon Hawk rows. Short controls
    # take a larger share of their height; normal ones are untouched.
    return sizing_height * (BADGE_RADIUS_SHORT if sizing_height < BADGE_SHORT_BELOW else BADGE_RADIUS)


def badge_fit_width(label_width: float, sizing_height: int, inset: int = 0) -> float:
    """The narrowest button that shows its centred label with the badge at the
    designed gap, rather than pushed against the button's edge and onto the
    text (build_prompt_tga's clamp).

    `inset`: the button's border's fill inset (fill_inset). The badge is then fitted
    to the smaller area and kept BADGE_EDGE radii inside it, so the button needs the
    inset on both sides as well. Without it the Container's Give Items badge sat up
    to 3 px nearer its caption than designed at 24 blended sizes
    (Test-GuiBlendHelper.py, 2026-10-05)."""
    radius = badge_radius(sizing_height)
    if inset > 0:
        radius = min(radius, (sizing_height - 2 * inset) / 2.0 - FIT_MARGIN)
    return label_width + 2.0 * (inset + radius * (BADGE_GAP + 1.0 + BADGE_EDGE))


@lru_cache(maxsize=None)
def build_prompt_tga(control_width: int, control_height: int, glyph: str,
                     label_width: float = 0.0,
                     radius_height: int = 0,
                     family: str = GLYPH_FAMILY,
                     backing: tuple | None = None,
                     inset: int = 0, fit: bool = False) -> bytes:
    """`inset`: how far inside the control the engine draws this border's fill, on
    every side (fill_inset). The badge is designed on the whole control, as before,
    and then mapped onto the smaller area the texture is actually stretched across,
    so it keeps its shape and its place. 0 is the whole control.

    `fit`: keep the badge whole inside the inset area, smaller if it must be.
    Measured 2026-10-05 on the original Close button (142x28, focused border 6 px):
    a 22 px badge in a 16 px fill came out with its top and bottom cut off. Each
    border's texture is fitted to its own area, so a button keeps its full-size
    badge while it is not focused. (Fitting both to the smaller area was tried the
    same day: the Map screen's 13 px rows, whose focused border leaves 1 px, lost
    their badges altogether.) An area under MIN_BADGE_AREA tall holds no badge."""
    if control_width <= 0 or control_height <= 0:
        raise ValueError(f"Invalid prompt control extent {control_width}x{control_height}")
    if inset < 0 or control_width - 2 * inset <= 0 or control_height - 2 * inset <= 0:
        raise ValueError(f"Fill inset {inset} leaves nothing of {control_width}x{control_height}")
    center_y = control_height * BADGE_CENTER_Y
    # A badge in a group takes its size from the group's shortest control rather
    # than its own, so five entries in a menu carry five identical glyphs. Quit
    # is 81 tall where the rest are 66, and sizing it from itself made its A a
    # fifth larger than the others.
    sizing_height = radius_height if radius_height > 0 else control_height
    radius = badge_radius(sizing_height)
    if fit and inset > 0:
        if control_height - 2 * inset < MIN_BADGE_AREA:
            return _empty_tga()
        # Half a pixel short of the area, so the disc's soft edge is inside the
        # texture rather than on its last row.
        radius = min(radius, (control_height - 2 * inset) / 2.0 - FIT_MARGIN)

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
        gap = radius * BADGE_GAP
        center_x = (control_width - label_width) / 2.0 - gap - radius
        # Never let it leave the button, however long the label. A button too
        # narrow for this puts the badge on the text; badge_fit_width is the
        # width that avoids it (prepare_universal_resources.py widens the
        # Container's buttons to it).
        center_x = max(radius * BADGE_EDGE, center_x)
    else:
        center_x = control_height * BADGE_FALLBACK_X
    if fit and inset > 0:
        # The same least distance from the area's edge as from a button's
        # (BADGE_EDGE). With no margin a badge clamped to a small area sat on the
        # texture's first column (the Auto Level Up button at 1024x576, whose 16 px
        # border leaves 8 px; Test-ControllerPromptAssets.py, 2026-10-05).
        center_x = max(center_x, inset + radius * BADGE_EDGE)
    return _composite_glyph_tga(control_width - 2 * inset, control_height - 2 * inset, glyph,
                                center_x - inset, center_y - inset, radius, family, backing)


# A border with corner art draws its fill INSIDE the border, not across the control:
# CSWGuiBorder::Draw (0x004168C0) starts the fill at the corner's size from the left
# and top and shortens it by twice that, and the corner's size is the border's
# DIMENSION when that is not zero (CSWGuiBorderParams::GetBorderDim, 0x00414CD0).
# With no corner image the fill covers the whole extent. Read from the decompiled
# functions on 2026-10-05 and measured in the game's original Options screen: a
# 240x40 button with DIMENSION 6 drew a badge made for 240x40 as 28x20, not round.
#
# A button has two borders, BORDER and HILIGHT (the one drawn while it has focus),
# and they need not agree: the original Close buttons have no normal border and a
# 6 px focused one. Where they differ the badge needs a second texture for the
# focused state, named with FOCUS_PREFIX; the module makes the same comparison on
# the live control and asks for it (SetK1ControllerPromptFill).
FOCUS_PREFIX = "kmf"
# The shortest fill area, in pixels, that is given a badge at all.
MIN_BADGE_AREA = 8
# Kept free above and below a badge fitted to its area, in pixels.
FIT_MARGIN = 0.5


def _empty_tga() -> bytes:
    """A fully transparent badge texture."""
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
                         TEXTURE_WIDTH, TEXTURE_HEIGHT, 32, 0x08)
    return header + b"\x00" * (TEXTURE_WIDTH * TEXTURE_HEIGHT * 4) + TGA_FOOTER


def fill_inset(border) -> int:
    """How far inside its control a border draws its fill: see above."""
    # Corner ART decides it, not the DIMENSION alone. The main menu's buttons name no
    # corner or edge art and have DIMENSION 4, and their fill covers the whole
    # 235x24: a badge made for the whole button drew 17x16 there, round within the
    # measurement, and one made for a 4 px inset (this function returned the
    # DIMENSION regardless for one build on 2026-10-05) drew 14x20.
    if border is None or not str(border.get_resref("CORNER")):
        return 0
    dimension = border.get_int32("DIMENSION")
    if dimension <= 0:
        raise ValueError("A border with corner art and no DIMENSION takes its inset "
                         "from the art's size, which this generator does not read")
    return dimension


def focus_resref(resref: str) -> str:
    """The focused-state texture of a badge whose two borders inset differently."""
    if not resref.startswith("kmr"):
        raise ValueError(f"{resref} is not a badge resref")
    return FOCUS_PREFIX + resref[3:]


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
    # Read from titlemovie.gui at 800x600, 1920x1080 and 3440x1440: 1582 "Close".
    ("titlemovie.gui", "BTN_BACK"): ((1582,),),
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

    # Character creation and level-up (2026-09-25): each button's own
    # TEXT.STRREF, read from its .gui. Feats' Add and Powers' Select also carry
    # the captions their panels build at run time -- 38455 "Add" or 38456
    # "Remove", a space, then 42487 "Feat" (0x006F4229..0x006F4340) or 42488
    # "Power" (from 0x006F2645) -- so the badge is placed against the widest.
    ("classsel.gui", "BTN_BACK"): ((1581,),),
    ("qorcpnl.gui", "QUICK_CHAR_BTN"): ((239,),),
    ("qorcpnl.gui", "CUST_CHAR_BTN"): ((240,),),
    ("qorcpnl.gui", "BTN_BACK"): ((1581,),),
    ("custpnl.gui", "BTN_STEPNAME1"): ((231,),),
    ("custpnl.gui", "BTN_STEPNAME2"): ((209,),),
    ("custpnl.gui", "BTN_STEPNAME3"): ((233,),),
    ("custpnl.gui", "BTN_STEPNAME4"): ((232,),),
    ("custpnl.gui", "BTN_STEPNAME5"): ((234,),),
    ("custpnl.gui", "BTN_STEPNAME6"): ((235,),),
    ("custpnl.gui", "BTN_BACK"): ((219,),),
    ("custpnl.gui", "BTN_CANCEL"): ((1581,),),
    ("quickpnl.gui", "BTN_STEPNAME1"): ((231,),),
    ("quickpnl.gui", "BTN_STEPNAME2"): ((234,),),
    ("quickpnl.gui", "BTN_STEPNAME3"): ((235,),),
    ("quickpnl.gui", "BTN_BACK"): ((219,),),
    ("quickpnl.gui", "BTN_CANCEL"): ((1581,),),
    ("portcust.gui", "BTN_ACCEPT"): ((1580,),),
    ("portcust.gui", "BTN_BACK"): ((1581,),),
    ("abchrgen.gui", "BTN_ACCEPT"): ((1580,),),
    ("abchrgen.gui", "BTN_RECOMMENDED"): ((221,),),
    ("abchrgen.gui", "BTN_BACK"): ((1581,),),
    ("skchrgen.gui", "BTN_ACCEPT"): ((1580,),),
    ("skchrgen.gui", "BTN_RECOMMENDED"): ((221,),),
    ("skchrgen.gui", "BTN_BACK"): ((1581,),),
    ("ftchrgen.gui", "BTN_ACCEPT"): ((1580,),),
    ("ftchrgen.gui", "BTN_RECOMMENDED"): ((221,),),
    ("ftchrgen.gui", "BTN_BACK"): ((1581,),),
    ("name.gui", "END_BTN"): ((1580,),),
    ("name.gui", "BTN_RANDOM"): ((48579,),),
    ("name.gui", "BTN_BACK"): ((1581,),),
    ("leveluppnl.gui", "BTN_STEPNAME1"): ((209,),),
    ("leveluppnl.gui", "BTN_STEPNAME2"): ((233,),),
    ("leveluppnl.gui", "BTN_STEPNAME3"): ((232,),),
    ("leveluppnl.gui", "BTN_STEPNAME4"): ((1072,),),
    ("leveluppnl.gui", "BTN_STEPNAME5"): ((1073,),),
    ("leveluppnl.gui", "BTN_BACK"): ((219,),),
    ("pwrlvlup.gui", "ACCEPT_BTN"): ((1580,),),
    ("pwrlvlup.gui", "RECOMMENDED_BTN"): ((221,),),
    ("pwrlvlup.gui", "BACK_BTN"): ((1581,),),
    ("ftchrgen.gui", "BTN_SELECT"): ((38455,), (38455, 42487), (38456, 42487)),
    ("pwrlvlup.gui", "SELECT_BTN"): ((236,), (38455, 42488), (38456, 42488)),

    # The settings screens and Pazaak's wager (2026-09-25), each button's own
    # TEXT.STRREF as its .gui carries it. BTN_KMRPLAY is absent on purpose: its
    # caption is KMRP's own inline text (PROMPT_INLINE_LABELS).
    ("optgraphics.gui", "BTN_DEFAULT"): ((42010,),),
    ("optgraphics.gui", "BTN_RESOLUTION"): ((47966,),),
    ("optgraphics.gui", "BTN_ADVANCED"): ((48580,),),
    ("optgraphicsadv.gui", "BTN_DEFAULT"): ((42010,),),
    ("optsound.gui", "BTN_DEFAULT"): ((42010,),),
    ("optsound.gui", "BTN_ADVANCED"): ((48580,),),
    ("optsoundadv.gui", "BTN_DEFAULT"): ((42010,),),
    ("optgameplay.gui", "BTN_DEFAULT"): ((42010,),),
    ("optgameplay.gui", "BTN_MOUSE"): ((48449,),),
    ("optgameplay.gui", "BTN_KEYMAP"): ((48142,),),
    ("optmouse.gui", "BTN_DEFAULT"): ((42010,),),
    ("optfeedback.gui", "BTN_DEFAULT"): ((42010,),),
    ("optautopause.gui", "BTN_DEFAULT"): ((42010,),),
    ("optkeymapping.gui", "BTN_Default"): ((42010,),),
    ("optionsmain.gui", "BTN_GAMEPLAY"): ((42166,),),
    ("optionsmain.gui", "BTN_FEEDBACK"): ((42167,),),
    ("optionsmain.gui", "BTN_AUTOPAUSE"): ((42168,),),
    ("optionsmain.gui", "BTN_GRAPHICS"): ((47994,),),
    ("optionsmain.gui", "BTN_SOUND"): ((47995,),),
    ("optionsingame.gui", "BTN_LOADGAME"): ((1585,),),
    ("optionsingame.gui", "BTN_SAVEGAME"): ((1588,),),
    ("optionsingame.gui", "BTN_GAMEPLAY"): ((42166,),),
    ("optionsingame.gui", "BTN_FEEDBACK"): ((42167,),),
    ("optionsingame.gui", "BTN_AUTOPAUSE"): ((42168,),),
    ("optionsingame.gui", "BTN_GRAPHICS"): ((47994,),),
    ("optionsingame.gui", "BTN_SOUND"): ((47995,),),
    ("optionsingame.gui", "BTN_QUIT"): ((48581,),),
    ("pazaakwager.gui", "BTN_WAGER"): ((42393,),),
    ("pazaakwager.gui", "BTN_QUIT"): ((42172,),),
    ("character.gui", "BTN_LEVELUP"): ((1071,),),
    ("character.gui", "BTN_AUTO"): ((36812,),),
    ("skillinfo.gui", "BTN_OK"): ((1580,),),
}

# Buttons whose caption is inline text in the .gui rather than a STRREF: KMRP's
# own. English only and never re-placed by the installer, so their manifest row
# carries no variants ("-"), which the installer skips.
PROMPT_INLINE_LABELS = {
    ("optgameplay.gui", "BTN_KMRPLAY"): "Controller Layout",
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
    # The settings screens and Pazaak's wager, 2026-09-25.
    42010: "Default",
    47966: "Screen Resolution",
    48580: "Advanced Options",
    48142: "Key Mapping",
    48449: "Mouse Settings",
    42166: "Gameplay",
    42167: "Feedback",
    42168: "Auto-Pause",
    47994: "Graphics",
    47995: "Sound",
    1588: "Save Game",
    48581: "Exit Game",
    42393: "Wager",
    1071: "Level Up",
    36812: "Auto Level Up",
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
    # The two Options lists, the same shape as the main menu (2026-09-25).
    ("optionsmain.gui", "BTN_GAMEPLAY"): "optionsmain",
    ("optionsmain.gui", "BTN_FEEDBACK"): "optionsmain",
    ("optionsmain.gui", "BTN_AUTOPAUSE"): "optionsmain",
    ("optionsmain.gui", "BTN_GRAPHICS"): "optionsmain",
    ("optionsmain.gui", "BTN_SOUND"): "optionsmain",
    ("optionsingame.gui", "BTN_LOADGAME"): "optionsingame",
    ("optionsingame.gui", "BTN_SAVEGAME"): "optionsingame",
    ("optionsingame.gui", "BTN_GAMEPLAY"): "optionsingame",
    ("optionsingame.gui", "BTN_FEEDBACK"): "optionsingame",
    ("optionsingame.gui", "BTN_AUTOPAUSE"): "optionsingame",
    ("optionsingame.gui", "BTN_GRAPHICS"): "optionsingame",
    ("optionsingame.gui", "BTN_SOUND"): "optionsingame",
    ("optionsingame.gui", "BTN_QUIT"): "optionsingame",
    # Gameplay's two sub-screen buttons, stacked. Controller Layout below them
    # is left out: its inline caption has no STRREF for the installer to
    # re-measure, and a group is re-placed as one.
    ("optgameplay.gui", "BTN_MOUSE"): "optgame",
    ("optgameplay.gui", "BTN_KEYMAP"): "optgame",
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


def target_labels(target, variants):
    """The wordings a target's button can show: its STRREF variants, or the
    inline caption of a button that has none."""
    inline = PROMPT_INLINE_LABELS.get((target.gui, target.tag))
    if inline is not None:
        return [inline]
    return variant_strings(variants, PROMPT_FALLBACK_STRINGS)


def parse_font_metrics(txi_path: Path):
    """Per-character pixel advances for a KOTOR font atlas.

    The engine renders one texel per pixel, so a glyph's on-screen width is
    `(lowerright.u - upperleft.u) * texturewidth * 100` -- see
    `reverse-engineering/font-atlases.md`. Returns (advances, spacing_px), both
    already in pixels for the resolution this TXI was generated for.

    `spacingR` is `spacingR * 100` pixels, NOT scaled by `texturewidth`: KMRP
    writes it as a flat half pixel (`apply_letter_spacing`, 0.005), and the
    engine adds 0.5 px a glyph when it measures a line (`0x0045ABDF`, the status
    summary's measurement in the CHANGELOG).

    *Corrected 2026-09-30:* this returned `spacingR * texturewidth * 100`, which
    is 2.56 px at `texturewidth` 5.12 and 5.12 px at 10.24 instead of 0.5, so
    every caption measured long by 2 to 5 px a letter -- more at higher
    resolutions. The game drew them at 0.88 of the measure at 3440x1440 (below),
    and seven Options captions read off a 3024x1964 screenshot inked 0.825 to
    0.843 of it; their ink is 0.96 to 0.97 of the corrected measure, the rest
    being the glyphs' side bearings. Every badge
    therefore sat about twice its designed gap from its words, and where a long
    caption filled its button the clamp below pushed the badge onto the text:
    the Container's "Switch To Give Item" at 3024x1964, seen in play on the Mac.
    Windows draws and places the same, so it had the same offset. The Controller
    Layout screen's RENDER_FACTOR had absorbed the error as a 0.88 draw ratio
    measured at 3440x1440.
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
    return advances, spacing * 100.0


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


def build_prompt_textures(gui_files: list[Path], output_dir: Path,
                          widened: dict[str, int] | None = None,
                          fitted: dict[tuple[str, str], int] | None = None,
                          fill_insets: bool = False) -> list[Path]:
    """`widened`: pixels a screen was widened by to fit a caption and its badge
    (prepare_universal_resources.py), recorded in the manifest so the Mac's blend
    table can take the widening back out and its installer put it in again for a
    resolution with no set (tools/build_gui_blend_table.py). `fitted`: the same for
    the lists made as tall as whole rows, by (screen, list), in pixels of height
    (scale_listbox_padding.py, fit_list_to_rows).

    `fill_insets`: make each badge for the area its border really fills (fill_inset),
    with a focused-state texture where the two borders differ. Every build passes it
    since 2026-10-05: KMRP's own sets (prepare_universal_resources.py), whose badges
    were until then made for the whole control and so drawn about 13% wider than
    tall on a bordered 720x90 button, and the standalone controller patch
    (build_controller_assets.py). The blend table (version 5), kmrp-guiblend.c and
    GuiBlend.cs draw the same for a size with no set. False is the old behaviour,
    kept for comparing against sets built before."""
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
                     for label in target_labels(target, variants)),
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
        # Empty, or exactly the backing the badge carries and the module puts back.
        fills = (str(border.get_resref("FILL")),
                 str(control.get_struct("HILIGHT").get_resref("FILL"))
                 if control.exists("HILIGHT") else "")
        if target.backing:
            if target.backing not in BACKINGS:
                raise ValueError(f"{target.resref}: unknown backing {target.backing!r}")
            if fills != (target.backing, target.backing):
                raise ValueError(
                    f"{target.gui}:{target.tag} carries {fills}, but its badge "
                    f"stands on {target.backing!r}")
        elif fills[0]:
            raise ValueError(f"{target.gui}:{target.tag} has a non-empty normal fill")
        variants = PROMPT_STRREFS.get((target.gui, target.tag), ())
        labels = target_labels(target, variants)
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
        elif target.size_like:
            like = next((c for c in controls if c.get_string("TAG") == target.size_like),
                        None)
            if like is None:
                raise ValueError(f"{target.gui} has no {target.size_like} to size "
                                 f"{target.tag}'s badge like")
            radius_height = like.get_struct("EXTENT").get_int32("HEIGHT")
        backing = BACKINGS[target.backing] if target.backing else None
        normal_inset = focus_inset = 0
        if fill_insets:
            normal_inset = fill_inset(border)
            focus_inset = (fill_inset(control.get_struct("HILIGHT"))
                           if control.exists("HILIGHT") else normal_inset)

        # Once per family, identically placed: only the art differs, so the
        # installer's re-centring treats every family's copy the same way.
        for family in GLYPH_FAMILIES:
            resref = family_resref(target.resref, family)
            output = output_dir / f"{resref}.tga"
            output.write_bytes(build_prompt_tga(
                width, height, target.glyph, round(label_width, 2), radius_height,
                family, backing, normal_inset, fill_insets))
            results.append(output)
            manifest.append((resref, width, height, round(label_width, 2),
                             variants))
            if focus_inset != normal_inset:
                focused = output_dir / f"{focus_resref(resref)}.tga"
                focused.write_bytes(build_prompt_tga(
                    width, height, target.glyph, round(label_width, 2), radius_height,
                    family, backing, focus_inset, fill_insets))
                results.append(focused)

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
                        width, height, target.glyph, round(one_width, 2), 0, family,
                        None, normal_inset, fill_insets))
                    results.append(path)
                    if focus_inset != normal_inset:
                        focused = output_dir / f"{focus_resref(resref)}.tga"
                        focused.write_bytes(build_prompt_tga(
                            width, height, target.glyph, round(one_width, 2), 0, family,
                            None, focus_inset, fill_insets))
                        results.append(focused)
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
        # Ignored by the Windows installer, which skips a line it does not know.
        for gui, pixels in sorted((widened or {}).items()):
            lines.append(f"widened {gui} {pixels}")
        for (gui, tag), pixels in sorted((fitted or {}).items()):
            lines.append(f"fitted {gui} {tag} {pixels}")
        for resref, width, height, baked, variants in manifest:
            encoded = ";".join("+".join(str(ref) for ref in variant)
                               for variant in variants) or "-"
            lines.append(f"prompt {resref} {width} {height} {baked:.2f} {encoded}")
        path = output_dir / PROMPT_MANIFEST_NAME
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        results.append(path)
    return results
