#!/usr/bin/env python3
"""Live Adaptive Layout: lay a screen's .gui out for any screen size at run time.

    python tools/build_live_layout.py            write macos/tools/kmrp-livelayout-table.h
    python tools/build_live_layout.py --check    stop if that file is not what this makes

KMRP's per-size layouts are High Resolution Menus' hand-made sets with KMRP's
corrections on top, made at build time. A GUI mod's file in Override takes the place of
KMRP's whole file, laid out for 640x480, so the screen is drawn small in a corner. Live
Adaptive Layout (the maintainer's name, 2026-10-27) lays out whichever file the game would
load, the game's own or a mod's, for the size in use, at run time: KmrpLiveLayout in
macos/tools/kmrp-guiadapt.c, shared by the Windows module and the Mac. This script makes the
table it reads and holds the same layout in Python (`layout`), which
testing/regression/Test-LiveLayout.py compares with the build's sets and with the C.

The rules (measured 2026-10-28; docs/live-adaptive-layout.md has the figures)
---------------------------------------------------------------------------
Upstream lays each size out by hand, but every control follows one of a few rules applied
to its value in the game's own file, with s = H / BH (BW x BH: the file's own size, which
is its root panel's when that fills the screen from 0,0, else 640x480; mainmenu10x7.gui,
for one, is an 800x600 layout):

    scale    v * s                                 tops and heights; most squares' widths
    stretch  v * W / BW                            lefts and widths of most controls
    aspect   (v + w/2) * W / BW - w * s / 2        a square's left: it keeps its shape and is
                                                   centred where the stretched one would be
    fixed    v                                     list row prototypes (PROTOITEM)
    centre   W/2 + (v - BW/2) * s,  right  W - (BW - v) * s
    aspect_centre                                  aspect's value, but gold carried on the
                                                   control's centre (aspect_left; chosen by
                                                   aspect_centre_fits, 2026-10-30)

One rule per field reproduces 92.1% of the fields of upstream's 48 sets exactly in every
set and 99.0% of the values. KMRP's own changes are, per field, the gold 3440x1440 file's
value against the rule's there, and the build carries them to every size as a ratio
(tools/transfer_gold_gui_geometry.py); so does this. Rule and gold together give 95.1% of
the values of KMRP's 66 sets exactly and 99.1% within a pixel, over the screens that are
not the HUD or made by a step of their own; the gold set itself comes out as it is. The
pixel is rounding, accepted by the maintainer on 2026-10-28 for every size but gold.

The table
---------
Per file this moves, per structure of the game's file that has an EXTENT (the root, each
control by TAG, and a list's PROTOITEM and SCROLLBAR): each field's rule, chosen on
upstream's sets (the default where it fits as well), and the gold file's value. The C
applies a structure's gold values only while the file it lays out has the game's own
extent there: a control a mod moved keeps the mod's place, laid out by its rule alone. A
control the table does not know (a mod's own) gets the default rule:

    a list row prototype is fixed; tops and heights scale;
    a square control (width / height 0.8 to 1.25) that is not a list box keeps its shape;
    everything else stretches.

With it go the list gutters (PADDING) the build sets (prepare_universal_resources.py:
DESCRIPTION_LISTBOXES, LIST_LISTBOXES, HAND_TUNED_GUTTERS), at the build's font scale, and
a PADDING the gold file sets by hand, which the build ships at 3440x1440 only, so this does;
a text alignment the gold file changes, at every size; and, for the screens that have them,
the build's lists made as tall as whole rows (scale_listbox_padding.py ROW_LISTS) and the
R3 cue by the party portraits (add_party_switch_cue), the Abilities sub-tab swap cue,
and the menu strip's LT/RT cues. The Python here runs the build's own functions on a
file; the C repeats them, adding controls by appending to the GFF's sections.

The table holds rule numbers and the gold file's values, which are in this repository;
nothing of the game's. The game's own files are read at run time from chitin.key, and here
from build-inputs/vanilla-gui.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import tempfile

from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, GFFStruct, read_gff, write_gff
from pykotor.resource.type import ResourceType
from pykotor.common.misc import ResRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from prepare_universal_resources import (COMBAT_CUE_SCALE, COMBAT_CUE_TEMPLATE, COMBAT_CUES,  # noqa: E402
                                         add_combat_cues)
from prepare_universal_resources import GOLD_GEOMETRY_EXCLUDED  # noqa: E402
from prepare_universal_resources import (CONTAINER_FIT_TAG, CONTAINER_SCREEN,  # noqa: E402
                                         CONTAINER_WIDENED, DESCRIPTION_LISTBOXES, FONT_HEIGHT_DIVISOR,
                                         FONT_SCALE_OFFSET, HAND_TUNED_GUTTERS, LIST_LISTBOXES,
                                         R3_CUE_BLOCKING_TYPES, R3_CUE_FILL, R3_CUE_GAP_MARGIN,
                                         R3_CUE_SCALE, R3_CUE_SCREENS, R3_CUE_TAG,
                                         SUBTAB_TAGS, SWAP_CUE_ASPECT, SWAP_CUE_BESIDE,
                                         SWAP_CUE_FILL, SWAP_CUE_SCREEN, SWAP_CUE_TAG,
                                         TAB_CUES, TAB_CUE_SCREEN, TAB_TAGS,
                                         add_party_switch_cue, add_subtab_swap_cue, add_tab_strip_cues,
                                         widen_container)
from scale_listbox_padding import (FEEDBACK_LIST, GUTTER_AT_UNIT_SCALE, JOURNAL_ROWS,  # noqa: E402
                                   LIST_GUTTER_AT_UNIT_SCALE, LOOSE_GAP, ROW_GAP_DIVISOR, ROW_LISTS,
                                   SCRIPTSELECT_FRAME, centre_rows_in_frame, fit_list_to_rows,
                                   fit_rows_to_list, scale_row_template)
import build_controller_prompt_textures as prompts  # noqa: E402
from build_controller_layout import (CONFIRM_BADGE_STEM, CONFIRM_BADGE_TAG, DIALOG_BADGE_TAG, ENTRY_CAPTION,  # noqa: E402
                                     ENTRY_FALLBACK_STEP, ENTRY_LIFT_DIVISOR, ENTRY_PREVIOUS, ENTRY_SCREEN,
                                     ENTRY_TAG, ENTRY_TEMPLATE, add_confirm_badge, add_entry)
from scale_message_popup import (MESSAGE_PADDING, TUNED, TUNED_SCALE,  # noqa: E402
                                 apply_tuned as apply_popup_layout)

# The screens the build gives a controller badge label, cloned from the size's
# kmrplayout.gui (add_confirm_badge): the confirmation box's travelling A and the
# dialogue reply's.
BADGE_SCREENS = {"confirm.gui": CONFIRM_BADGE_TAG, "dialog.gui": DIALOG_BADGE_TAG}
POPUP_SCREEN = "confirm.gui"
BADGE_DONOR = "kmrplayout.gui"
MAP_SCREEN, MAP_TAG = "map.gui", "LBL_Map"


def map_control_box(width: int, height: int) -> tuple[int, int, int, int]:
    """LBL_Map's extent on a screen, as analyze_resolution_guis.geometry has it."""
    overlay, canvas = width // 2, height // 2
    return (width - overlay) // 2, (height - canvas) // 2 + 14, overlay, canvas

VANILLA = ROOT / "build-inputs" / "vanilla-gui"
UPSTREAM = ROOT / "third_party" / "Included" / "kotor-high-resolution-menus-1.5"
GOLD = ROOT / "assets" / "override-3440x1440"
TABLE = ROOT / "macos" / "tools" / "kmrp-livelayout-table.h"
GOLD_SIZE = (3440, 1440)

# The screens laid out at run time. The options screens first (2026-10-28): rules and
# gold alone make them, with nothing of KMRP's own added. Then (the same day) Inventory, Equipment and
# Character, which GUI mods change most: those take two of the build's steps as well,
# Equipment's list made as tall as whole rows (ROW_LISTS) and the R3 cue by the party
# portraits that the controller patch prompts with (add_party_switch_cue).
FILES = (
    "optionsmain.gui", "optionsingame.gui", "optautopause.gui", "optgraphics.gui",
    "optgraphicsadv.gui", "optmouse.gui", "optsound.gui", "optsoundadv.gui",
    "optkeymapping.gui", "optkeyentry.gui", "optresolution.gui",
    "inventory.gui", "equip.gui", "character.gui",
    # The screens KMRP's build gives no step of its own (2026-10-28, the maintainer: "Ok
    # lets start"): character creation, saving and loading, messages, the galaxy map,
    # Pazaak, the workbench, and the screens with nothing to fit. startscreen.gui is in no
    # set, so the build ships the game's own.
    "abchrgen.gui", "maincg.gui", "name.gui", "portcust.gui", "skchrgen.gui",
    "custpnl.gui", "qorcpnl.gui", "quickpnl.gui", "leveluppnl.gui",
    "saveload.gui", "savename.gui", "messages.gui", "questitem.gui", "galaxymap.gui",
    "areatransition.gui", "barkbubble.gui", "computercamera.gui", "maininterface.gui",
    "pazaakgame.gui", "pazaaksetup.gui", "pazaakwager.gui", "upgrade.gui", "upgradesel.gui",
    "loadscreen.gui", "splashscreen.gui", "titlemovie.gui", "credits.gui", "fade.gui",
    "debug.gui", "ntscpat.gui",
    "classsel.gui",
    # Custom build steps repeated live: Abilities row fitting/party/swap cues and
    # the tab strip's LT/RT cues (2026-10-29).
    "abilities.gui", "top.gui",
    "optgameplay.gui", "optfeedback.gui",
    # The lists the build fits to their rows (2026-10-30, the maintainer: "Row-fitted
    # lists"): ROW_LISTS as for Equipment, Script Selection's rows centred in its art's
    # frame, the Journal's six quest rows, and the Container widened for its Give Items
    # caption, whose width the size's prompt manifest carries.
    "computer.gui", "container.gui", "ftchrgen.gui", "journal.gui", "pwrlvlup.gui",
    "scriptselect.gui", "skillinfo.gui", "store.gui", "upgradeitems.gui",
    # The pause notice (2026-10-30): rules and gold alone make every set's file. The
    # module's Pause (K1TextLayout.cpp) then places it under the live menu row, taking its
    # margins from the loaded file, so it reads the same numbers either way.
    "pause.gui",
    # Party selection: laid out here unless the 32-slot roster is active, whose file
    # AdaptPartyRosterK1 builds from the set's and keeps (K1RuntimeAssets.cpp skips it).
    "partyselection.gui",
    # The tooltips, one file per base size (2026-10-30): rules and gold alone make every
    # set's file, and nothing else in KMRP changes them.
    "tooltip6x4.gui", "tooltip8x6.gui", "tooltip10x8.gui", "tooltip12x9.gui", "tooltip16x12.gui",
    # The main menu's five files (2026-10-30): laid out here, then the module puts the
    # buttons on the bars of their art (AdaptMainMenuK1, KmrpMainMenuBars) from this result.
    "mainmenu.gui", "mainmenu8x6.gui", "mainmenu10x7.gui", "mainmenu12x9.gui", "mainmenu16x12.gui",
    # The message popup (2026-10-30): gold at 3440x1440 only, as the build has it
    # (GOLD_GEOMETRY_EXCLUDED); then its measured table by the font scale and the
    # controller's badge label from the size's kmrplayout.gui.
    "confirm.gui",
    # The area map (2026-10-30): gold at 3440x1440 only, as the build has it, and LBL_Map
    # from the screen's size (map_control_box).
    "map.gui",
    # The conversation box (2026-10-30): upstream ships none, so every size but 3440x1440
    # shows the game's own numbers (vanilla_dialog_gui), 3440x1440 gold's; the module places
    # the box at run time. Then the dialogue A's label from the size's kmrplayout.gui.
    "dialog.gui",
)

# The prompt manifest row whose caption width the Container is widened for.
CAPTION_ROW = next(t.resref for t in prompts.PROMPT_TARGETS
                   if (t.gui, t.tag) == (CONTAINER_SCREEN, CONTAINER_FIT_TAG))

# The mouse and keyboard HUD's files (2026-10-30): not laid out here, because KMRP's module
# places that HUD from a table of its own whichever file was loaded (K1PcHud.cpp, since
# 2026-10-18), but a mod's file is given the combat cues the build adds to KMRP's
# (add_combat_cues), which that table then places beside the buttons (hud_cues below).
HUD_FILES = tuple(sorted(p.name.lower() for p in VANILLA.glob("mipc*.gui")))
# add_combat_cues sizes both cues by the Disengage button's height, BTN_CLEARALL.
assert COMBAT_CUES[1][3] == "BTN_CLEARALL", "add_combat_cues sizes the cues by BTN_CLEARALL"

FIELDS = ("LEFT", "TOP", "WIDTH", "HEIGHT")
# Rule numbers, as kmrp-guiadapt.c has them.
RULES = ("scale", "stretch", "fixed", "aspect", "centre", "right", "frame", "frame_inclusive", "aspect_centre")
FRAME_MARGIN = 10
LISTBOX = 11
SUBS = ("PROTOITEM", "SCROLLBAR")
BORDER_PARTS = (("BORDER", "CORNER"), ("BORDER", "EDGE"), ("HILIGHT", "CORNER"), ("HILIGHT", "EDGE"))
# Upstream sets more than 2% off their family's shape are no family's (the 21-by-9
# folder's 1280x1080).
OFF_FAMILY = {(1280, 1080)}


def rhalf(x: float) -> int:
    """Round half away from zero, as the C's lround."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def font_scale(height: int) -> float:
    return max(1.0, height / FONT_HEIGHT_DIVISOR - FONT_SCALE_OFFSET)


def gutter(unit: float, height: int) -> int:
    # Python's round, half to even, as scale_listbox_padding.py has it (the C: nearbyint).
    return int(round(unit * font_scale(height)))


def child(struct: GFFStruct, label: str) -> GFFStruct | None:
    """A structure-valued field itself (pykotor's get_struct returns a copy)."""
    return struct.acquire(label, None, GFFStruct)


def extent(struct: GFFStruct) -> list[int] | None:
    e = child(struct, "EXTENT")
    if e is None:
        return None
    return [e.get_int32(f) for f in FIELDS]


def base_of(root: GFFStruct) -> tuple[int, int]:
    e = extent(root)
    if e and e[0] == 0 and e[1] == 0 and e[2] >= 640 and e[3] >= 480:
        return e[2], e[3]
    return 640, 480


def structures(root: GFFStruct):
    """(key, structure, CONTROLTYPE) of every structure with an EXTENT: the root as ("", ""),
    a control as (TAG, ""), its prototype and scroll bar as (TAG, "PROTOITEM"/"SCROLLBAR")."""
    yield ("", ""), root, -1
    if not root.exists("CONTROLS"):
        return
    for index, control in enumerate(root.acquire("CONTROLS", None, GFFList)):
        # An untagged control by its place, never the root's key.
        tag = (control.get_string("TAG") if control.exists("TAG") else "") or f"#{index}"
        ctype = control.get_int32("CONTROLTYPE") if control.exists("CONTROLTYPE") else -1
        if extent(control) is not None:
            yield (tag, ""), control, ctype
        for sub in SUBS:
            inner = child(control, sub)
            if inner is not None and extent(inner) is not None:
                yield (tag, sub), inner, ctype


def rule_origin(rule: str, field: int) -> int:
    if rule not in ("frame", "frame_inclusive"):
        return 0
    return -FRAME_MARGIN if field < 2 else 2 * FRAME_MARGIN + int(rule == "frame_inclusive" and field == 3)


def value(rule: str, field: int, v: int, w: int, width: int, height: int, base: tuple[int, int]) -> float:
    """A rule's unrounded value for field `field` (0..3) of `v`, `w` the structure's width."""
    bw, bh = base
    s = height / bh
    if rule == "scale":
        return v * s
    if rule == "fixed":
        return float(v)
    if rule == "stretch":
        return v * width / bw
    if rule in ("aspect", "aspect_centre"):
        return (v + w / 2) * width / bw - w * s / 2 if field == 0 else v * s
    if rule == "centre":
        return width / 2 + (v - bw / 2) * s if field == 0 else v * s
    if rule == "right":
        return width - (bw - v) * s if field == 0 else v * s
    if rule in ("frame", "frame_inclusive"):
        origin = rule_origin(rule, field)
        factor = width / bw if field in (0, 2) else s
        return (v - origin) * factor + origin
    raise ValueError(rule)


def alignment(struct: GFFStruct) -> int | None:
    """A structure's TEXT.ALIGNMENT, or None."""
    text = child(struct, "TEXT")
    return text.get_int32("ALIGNMENT") if text is not None and text.exists("ALIGNMENT") else None


def dimension(struct: GFFStruct) -> int | None:
    """A structure's BORDER.DIMENSION, or None."""
    border = child(struct, "BORDER")
    return border.get_int32("DIMENSION") if border is not None and border.exists("DIMENSION") else None


def fill_style(struct: GFFStruct) -> int | None:
    """A structure's BORDER.FILLSTYLE, or None."""
    border = child(struct, "BORDER")
    return border.get_int32("FILLSTYLE") if border is not None and border.exists("FILLSTYLE") else None


def default_rule(field: int, sub: str, ctype: int, e: list[int]) -> str:
    if sub == "PROTOITEM":
        return "fixed"
    if field in (1, 3):
        return "scale"
    w, h = e[2], e[3]
    if not sub and ctype != LISTBOX and ctype != -1 and h > 0 and 0.8 <= w / h <= 1.25:
        return "aspect" if field == 0 else "scale"
    return "stretch"


def placed(field: int, rule: str, v4: list[int], gold: int | None, width: int, height: int,
           base: tuple[int, int]) -> int:
    """A field on the screen: its rule, carried by gold's ratio where gold differs from it."""
    r = value(rule, field, v4[field], v4[2], width, height, base)
    if gold is None:
        return rhalf(r)
    at_gold = value(rule, field, v4[field], v4[2], *GOLD_SIZE, base)
    if gold == rhalf(at_gold):
        return rhalf(r)
    origin = rule_origin(rule, field)
    if at_gold == origin:
        return rhalf(r + gold - at_gold)
    return rhalf((gold - origin) * ((r - origin) / (at_gold - origin)) + origin)


def aspect_left(rules: list[str], v4: list[int], gold: list, out: list[int], width: int, height: int,
                base: tuple[int, int]) -> int:
    """An aspect_centre LEFT where gold differs from the rule: gold's centre carried by the
    rule's centre, which grows with the screen's width alone, then half the laid-out width
    off it. Elsewhere `out[0]`.

    Carrying gold on the LEFT instead (placed) moves the centre with the height too, since
    the width scales by the height: the main menu's logo was 4 to 9 px from every set at
    7680x4320 and up, whose logo stands a fixed share of the width from the middle at
    every height (+414.5 px at every 3840-wide size; 2026-10-30). Not for every kept-shape
    control: done for all of them it put the galaxy map's planets and Terminal's icons up to
    23 px from the sets, which carry gold on the LEFT where gold moved a control
    (transfer_gold_gui_geometry). So choose_rules picks it per control (aspect_centre_fits)."""
    if rules[0] != "aspect_centre" or gold[0] is None or gold[2] is None:
        return out[0]
    rule_left = value("aspect", 0, v4[0], v4[2], *GOLD_SIZE, base)
    if gold[0] == rhalf(rule_left):
        return out[0]
    centre_at_gold = rule_left + value(rules[2], 2, v4[2], v4[2], *GOLD_SIZE, base) / 2
    if centre_at_gold == 0:
        return out[0]
    centre = value("aspect", 0, v4[0], v4[2], width, height, base) + value(rules[2], 2, v4[2], v4[2], width, height, base) / 2
    return rhalf((gold[0] + gold[2] / 2) * (centre / centre_at_gold) - out[2] / 2)


# ----------------------------------------------------------------------------- the table
def upstream_sets() -> list[tuple[tuple[int, int], Path]]:
    sets = []
    for family in sorted(p for p in UPSTREAM.iterdir() if p.is_dir()):
        for folder in sorted(family.glob("gui.*x*")):
            w, h = (int(x) for x in folder.name[4:].split("x"))
            if (w, h) not in OFF_FAMILY:
                sets.append(((w, h), folder))
    return sets


def upstream_ships(name: str) -> bool:
    """Does High Resolution Menus ship this file in any of its sets?"""
    return any((folder / name).is_file() for _, folder in upstream_sets())


def gold_size_only(name: str) -> bool:
    """Is gold's geometry this file's at 3440x1440 alone? For the files the build never carries
    it from (GOLD_GEOMETRY_EXCLUDED), and for those upstream ships none of, which every other
    size shows as the game's own (dialog.gui, vanilla_dialog_gui; 2026-10-30)."""
    return name in GOLD_GEOMETRY_EXCLUDED or not upstream_ships(name)


def choose_rules(name: str, sets) -> dict:
    """Per structure key of the game's file: its four rules, chosen on upstream's sets. A file
    upstream ships none of keeps the game's own numbers at every size: every field fixed."""
    vanilla = read_gff(VANILLA / name).root
    if not any((folder / name).is_file() for _, folder in sets):
        return {key: ["fixed"] * 4 for key, _, _ in structures(vanilla)}
    base = base_of(vanilla)
    gold = {key: extent(s) for key, s, _ in structures(read_gff(GOLD / name).root)} if (GOLD / name).is_file() else {}
    seen = {}
    for (w, h), folder in sets:
        for key, struct, _ in structures(read_gff(folder / name).root):
            seen.setdefault(key, []).append(((w, h), extent(struct)))
    chosen = {}
    for key, struct, ctype in structures(vanilla):
        if key in chosen:
            raise ValueError(f"{name}: two structures are {key}; the table keys by TAG")
        v4 = extent(struct)
        rules = []
        for field in range(4):
            default = default_rule(field, key[1], ctype, v4)
            # Only class selection is migrated to the fixed-frame rule in this batch.
            candidates = ("scale", "fixed") if field in (1, 3) else RULES[:6]
            if name == "classsel.gui":
                candidates += ("frame",)
                if field == 3:
                    candidates += ("frame_inclusive",)

            def hits(rule, scaled):
                # Scaled: up to the factor between upstream's 3440x1440 value and the
                # rule's there, which the run time's ratio to gold supplies. Character's
                # LBL_LEVEL is half as wide as stretching makes it at every size, and no
                # rule fitted it unscaled ("fixed" was picked: 296 px at every size).
                factor = 1.0
                if scaled:
                    at = value(rule, field, v4[field], v4[2], *GOLD_SIZE, base)
                    up = next((e[field] for size, e in seen.get(key, ()) if size == GOLD_SIZE), None)
                    origin = rule_origin(rule, field)
                    if at != origin and up is not None:
                        factor = (up - origin) / (at - origin)
                origin = rule_origin(rule, field)
                return sum(abs(e[field] - (factor * (value(rule, field, v4[field], v4[2], w, h, base) - origin) + origin)) <= 1.5
                           for (w, h), e in seen.get(key, ()))
            best = max(candidates, key=lambda r: (hits(r, True), hits(r, False), r == default))
            rules.append(best)
        if rules[0] == "aspect" and aspect_centre_fits(v4, rules, seen.get(key, ()), gold.get(key), base):
            rules[0] = "aspect_centre"
        chosen[key] = rules
    return chosen


def aspect_centre_fits(v4: list[int], rules: list[str], seen, gold: list[int] | None,
                       base: tuple[int, int]) -> bool:
    """Should a kept-shape control's LEFT carry gold by its centre (aspect_left)? Only where
    gold left it where upstream's 3440x1440 set has it, so the build carried nothing and the
    sets keep upstream's own places, and where carrying the centre puts it at upstream's own
    place, within a pixel and a half, at strictly more of upstream's sizes than carrying the
    LEFT does (2026-10-30)."""
    up = next((e for size, e in seen if size == GOLD_SIZE), None)
    if gold is None or up is None or gold[0] != up[0] or gold[2] != up[2]:
        return False
    if gold[0] == rhalf(value("aspect", 0, v4[0], v4[2], *GOLD_SIZE, base)):
        return False
    by_left = by_centre = 0
    for (w, h), e in seen:
        left = placed(0, "aspect", v4, up[0], w, h, base)
        width = placed(2, rules[2], v4, up[2], w, h, base)
        centred = aspect_left(["aspect_centre", rules[1], rules[2], rules[3]], v4, [up[0], None, up[2], None],
                              [left, 0, width, 0], w, h, base)
        by_left += abs(e[0] - left) <= 1.5
        by_centre += abs(e[0] - centred) <= 1.5
    return by_centre > by_left


def table_entries() -> list[tuple[str, list]]:
    sets = upstream_sets()
    files = []
    for name in FILES:
        rules = choose_rules(name, sets)
        vanilla = read_gff(VANILLA / name).root
        gold_root = read_gff(GOLD / name).root
        gold = {key: (extent(s), s) for key, s, _ in structures(gold_root)}
        rows = []
        for key, struct, ctype in structures(vanilla):
            g, gs = gold.get(key, (None, None))
            vpad = struct.get_int32("PADDING") if struct.exists("PADDING") else None
            gpad = gs.get_int32("PADDING") if gs is not None and gs.exists("PADDING") else None
            # A text alignment the gold file changed: transfer_gold_gui_geometry carries it
            # to every size as it is (Character's LBL_LEVEL, 12 to 10).
            valign, galign = alignment(struct), alignment(gs) if gs is not None else None
            # And a border's fill style it changed, which every size's set has from
            # upstream (Pazaak's BTN_PLRSIDE1, 1 to 2: its card back stretched).
            vfill, gfill = fill_style(struct), fill_style(gs) if gs is not None else None
            clear = 0
            for bit, (border_name, part) in enumerate(BORDER_PARTS):
                vb = child(struct, border_name)
                gb = child(gs, border_name) if gs is not None else None
                if (vb is not None and gb is not None and vb.exists(part) and gb.exists(part)
                        and str(vb.get_resref(part)) and not str(gb.get_resref(part))):
                    clear |= 1 << bit
            # A border's thickness the gold file changed, which only 3440x1440 has (the build
            # ships gold's whole file there): dialog.gui's reply list, 4 to 8 and 0 to 4.
            vdim, gdim = dimension(struct), dimension(gs) if gs is not None else None
            rows.append((key, rules[key], g, gpad if gpad is not None and gpad != vpad else None,
                         galign if galign is not None and valign is not None and galign != valign else None,
                         gfill if gfill is not None and vfill is not None and gfill != vfill else None, clear,
                         gdim if gdim is not None and vdim is not None and gdim != vdim else None))
        files.append((name, rows))
    return files


def c_string(text: str) -> str:
    if any(c in text for c in '"\\') or not text.isascii():
        raise ValueError(f"a TAG this table cannot hold: {text!r}")
    return f'"{text}"'


def render() -> str:
    lines = [
        "/* Generated by tools/build_live_layout.py from the gold 3440x1440 layout and High",
        " * Resolution Menus' sets; do not edit. testing/regression/Test-LiveLayout.py fails",
        " * when this is not what the script makes. Read by kmrp-guiadapt.c. */",
        "#ifndef KMRP_LIVELAYOUT_TABLE_H",
        "#define KMRP_LIVELAYOUT_TABLE_H",
        "",
        "/* Rules: " + ", ".join(f"{i} {r}" for i, r in enumerate(RULES)) + ". NO_GOLD: the gold",
        " * file has no such structure. NO_PADDING: the gold file sets no PADDING of its own.",
        " * NO_ALIGN: the gold file keeps the game's TEXT.ALIGNMENT. */",
        "#define LL_NO_GOLD (-2147483647 - 1)",
        "#define LL_NO_PADDING (-1)",
        "#define LL_NO_ALIGN (-1)",
        "#define LL_NO_FILL (-1)",
        "#define LL_NO_DIMENSION (-1)",
        "",
        "typedef struct { const char *tag, *sub; unsigned char rule[4]; int gold[4]; int gold_padding; int gold_align; int gold_fill; unsigned char clear_border; int gold_dimension; } LLRow;",
        "typedef struct { const char *name; const LLRow *rows; int count; int gold_size_only; } LLFile;",
        "typedef struct { const char *tag; double unit; int force; } LLGutter;",
        "",
        f"#define LL_GOLD_WIDTH {GOLD_SIZE[0]}",
        f"#define LL_GOLD_HEIGHT {GOLD_SIZE[1]}",
        f"#define LL_FRAME_MARGIN {FRAME_MARGIN}",
        f"#define LL_FONT_HEIGHT_DIVISOR {FONT_HEIGHT_DIVISOR!r}",
        f"#define LL_FONT_SCALE_OFFSET {FONT_SCALE_OFFSET!r}",
        "",
        "/* The build's list gutters, in its order: description panes, selection lists, then",
        " * the per-file hand-set ones, which may reduce a gutter (force). */",
        "static const LLGutter LL_GUTTERS[] = {",
    ]
    for tag in sorted(DESCRIPTION_LISTBOXES):
        lines.append(f"    {{ {c_string(tag)}, {GUTTER_AT_UNIT_SCALE!r}, 0 }},")
    for tag in sorted(LIST_LISTBOXES):
        lines.append(f"    {{ {c_string(tag)}, {LIST_GUTTER_AT_UNIT_SCALE!r}, 0 }},")
    lines.append("};")
    lines.append("")
    lines.append("typedef struct { const char *file, *tag; double unit; } LLFileGutter;")
    lines.append("static const LLFileGutter LL_FILE_GUTTERS[] = {")
    for file in sorted(HAND_TUNED_GUTTERS):
        for tags, unit in HAND_TUNED_GUTTERS[file]:
            for tag in sorted(tags):
                lines.append(f"    {{ {c_string(file)}, {c_string(tag)}, {unit!r} }},")
    lines.append("};")
    lines.append("")
    # The lists made as tall as whole rows (scale_listbox_padding.py ROW_LISTS,
    # fit_list_to_rows), for the screens this lays out.
    lines.append("/* Lists made as tall as whole rows (fit_list_to_rows): popup lists grow or shrink and")
    lines.append(" * move what is below them; a screen's list only shrinks, when its rows are loose. */")
    lines.append("typedef struct { const char *file, *tag; int popup; int bases[4]; int count; } LLRowList;")
    lines.append(f"#define LL_ROW_GAP_DIVISOR {ROW_GAP_DIVISOR}")
    lines.append(f"#define LL_LOOSE_GAP {LOOSE_GAP!r}")
    lines.append("static const LLRowList LL_ROW_LISTS[] = {")
    rows_listed = [(s, t, k, b) for (s, t), (k, b) in sorted(ROW_LISTS.items()) if s in FILES]
    for screen, tag, kind, bases in rows_listed:
        if len(bases) > 4:
            raise ValueError(f"{screen} {tag}: more than four row kinds")
        padded = ", ".join(str(x) for x in (list(bases) + [0] * 4)[:4])
        lines.append(f"    {{ {c_string(screen)}, {c_string(tag)}, {int(kind == 'popup')}, {{ {padded} }}, {len(bases)} }},")
    if not rows_listed:
        lines.append("    { 0, 0, 0, { 0 }, 0 },")
    lines.append("};")
    lines.append(f"#define LL_ROW_LIST_COUNT {len(rows_listed)}")
    lines.append("")
    # Script Selection's rows centred in its art's frame (centre_rows_in_frame) and the
    # Journal's quest rows (fit_rows_to_list), both scale_listbox_padding.py.
    lines.append("/* Script Selection's list PADDING centring its rows in the art's frame, at these")
    lines.append(" * fractions of the screen width (centre_rows_in_frame); the Journal's row template")
    lines.append(" * sized so JOURNAL_ROWS rows fill its list (fit_rows_to_list). */")
    lines.append(f"#define LL_CENTRE_SCREEN {c_string('scriptselect.gui')}")
    lines.append(f"#define LL_CENTRE_TAG {c_string('LST_AIState')}")
    lines.append(f"#define LL_CENTRE_FRAME_LEFT {SCRIPTSELECT_FRAME[0]!r}")
    lines.append(f"#define LL_CENTRE_FRAME_RIGHT {SCRIPTSELECT_FRAME[1]!r}")
    lines.append(f"#define LL_JOURNAL_SCREEN {c_string('journal.gui')}")
    lines.append(f"#define LL_JOURNAL_TAG {c_string('LB_ITEMS')}")
    lines.append(f"#define LL_JOURNAL_ROWS {JOURNAL_ROWS}")
    lines.append("")
    # The Container widened for its caption (prepare_universal_resources.py
    # fit_container_to_caption, build_controller_prompt_textures.py badge_fit_width).
    caption_row = CAPTION_ROW
    lines.append("/* The Container widened until its Give Items button holds the caption the size's")
    lines.append(" * prompt manifest gives (row CAPTION_ROW) and its badge (fit_container_to_caption). */")
    lines.append(f"#define LL_WIDEN_SCREEN {c_string(CONTAINER_SCREEN)}")
    lines.append(f"#define LL_WIDEN_TAG {c_string(CONTAINER_FIT_TAG)}")
    lines.append(f"#define LL_WIDEN_CAPTION_ROW {c_string(caption_row)}")
    lines.append("static const char *const LL_WIDENED[] = { " + ", ".join(map(c_string, CONTAINER_WIDENED)) + " };")
    # The message popup's measured table (scale_message_popup.apply_tuned), by the font scale.
    lines.append("/* The message popup, confirm.gui: its panel and these controls from the table measured at")
    lines.append(" * font scale POPUP_SCALE, times the size's font scale over it, half up; the panel centred")
    lines.append(" * where it was; LB_MESSAGE's PADDING and its scroll bar's width 0 (apply_tuned). */")
    lines.append(f"#define LL_POPUP_SCREEN {c_string(POPUP_SCREEN)}")
    lines.append(f"#define LL_POPUP_SCALE {TUNED_SCALE!r}")
    lines.append(f"#define LL_POPUP_PADDING {MESSAGE_PADDING}")
    lines.append(f"#define LL_POPUP_WIDTH {TUNED['TGuiPanel'][0]}")
    lines.append(f"#define LL_POPUP_HEIGHT {TUNED['TGuiPanel'][1]}")
    lines.append('#define LL_POPUP_MESSAGE "LB_MESSAGE"')
    lines.append("typedef struct { const char *tag; int box[4]; } LLPopupRow;")
    lines.append("static const LLPopupRow LL_POPUP_ROWS[] = {")
    for tag, box in TUNED.items():
        if tag != "TGuiPanel":
            lines.append(f"    {{ {c_string(tag)}, {{ {', '.join(map(str, box))} }} }},")
    lines.append("};")
    # The area map's picture control (map_control_box).
    lines.append("/* The area map's LBL_Map: half the screen each way, centred, MAP_INSET lower for the")
    lines.append(" * renderer's top inset (analyze_resolution_guis.geometry). */")
    lines.append(f"#define LL_MAP_SCREEN {c_string(MAP_SCREEN)}")
    lines.append(f"#define LL_MAP_TAG {c_string(MAP_TAG)}")
    lines.append(f"#define LL_MAP_INSET {map_control_box(0, 0)[1]}")
    # The controller badge labels (add_confirm_badge), cloned from the size's kmrplayout.gui.
    lines.append("/* The controller badge label a screen is given (add_confirm_badge): a clone of the size's")
    lines.append(" * kmrplayout.gui's LBL_TITLE with this tag, no text, picture kmrpcnfa, extent 0. */")
    lines.append("typedef struct { const char *screen, *tag; } LLBadge;")
    lines.append("static const LLBadge LL_BADGES[] = {")
    for screen, tag in sorted(BADGE_SCREENS.items()):
        lines.append(f"    {{ {c_string(screen)}, {c_string(tag)} }},")
    lines.append("};")
    lines.append(f"#define LL_BADGE_DONOR {c_string(BADGE_DONOR)}")
    lines.append('#define LL_BADGE_DONOR_TAG "LBL_TITLE"')
    lines.append(f'#define LL_BADGE_FILL "kmrp{CONFIRM_BADGE_STEM}"')
    lines.append("")
    # The HUD's combat cues (prepare_universal_resources.add_combat_cues), given to a mod's
    # mipc*.gui that lacks them (KmrpHudCues): the HUD's places come from the module's
    # table (K1PcHud.cpp), which places these cues too, so only the controls are added.
    lines.append("/* The combat cues KMRP adds to every mipc*.gui (add_combat_cues): tag, picture and the")
    lines.append(" * button each stands left of; cloned from TEMPLATE, sized by SCALE of the first's button. */")
    lines.append("typedef struct { const char *tag, *fill, *button; } LLCombatCue;")
    lines.append("static const LLCombatCue LL_COMBAT_CUES[] = {")
    for tag, fill, _glyph, button in COMBAT_CUES:
        lines.append(f"    {{ {c_string(tag)}, {c_string(fill)}, {c_string(button)} }},")
    lines.append("};")
    lines.append(f"#define LL_COMBAT_TEMPLATE {c_string(COMBAT_CUE_TEMPLATE)}")
    lines.append(f"#define LL_COMBAT_SCALE {COMBAT_CUE_SCALE!r}")
    lines.append(f"#define LL_COMBAT_SIZE_BUTTON {c_string(COMBAT_CUES[1][3])}")
    lines.append("static const char *const LL_HUD_FILES[] = { " + ", ".join(c_string(n) for n in HUD_FILES) + ", 0 };")
    lines.append("")
    for key, number in (("BADGE_RADIUS", prompts.BADGE_RADIUS), ("BADGE_RADIUS_SHORT", prompts.BADGE_RADIUS_SHORT),
                        ("BADGE_SHORT_BELOW", prompts.BADGE_SHORT_BELOW), ("BADGE_GAP", prompts.BADGE_GAP),
                        ("BADGE_EDGE", prompts.BADGE_EDGE), ("FIT_MARGIN", prompts.FIT_MARGIN)):
        lines.append(f"#define LL_{key} {number!r}")
    lines.append("")
    # The R3 cue (prepare_universal_resources.py add_party_switch_cue, r3_cue_extent).
    blocking = 0
    for t in R3_CUE_BLOCKING_TYPES:
        blocking |= 1 << t
    lines.append("/* The R3 cue by the party portraits (add_party_switch_cue): its side is R3_PERCENT of")
    lines.append(" * the portraits' height, centred in their gap when the gap holds it with R3_MARGIN of")
    lines.append(" * it free each side, else a third of it right of the second portrait. */")
    lines.append(f"#define LL_R3_TAG {c_string(R3_CUE_TAG)}")
    lines.append(f"#define LL_R3_FILL {c_string(R3_CUE_FILL)}")
    lines.append(f"#define LL_R3_PERCENT {round(R3_CUE_SCALE * 100)}")
    lines.append(f"#define LL_R3_MARGIN {R3_CUE_GAP_MARGIN!r}")
    lines.append(f"#define LL_R3_BLOCKING 0x{blocking:X}u   /* CONTROLTYPEs a cue may not cover */")
    lines.append("static const char *const LL_R3_SCREENS[] = {")
    for screen in sorted(s for s in R3_CUE_SCREENS if s in FILES):
        lines.append(f"    {c_string(screen)},")
    lines.append("    0,")
    lines.append("};")
    lines.append("")
    lines.append(f"#define LL_SWAP_SCREEN {c_string(SWAP_CUE_SCREEN)}")
    lines.append(f"#define LL_SWAP_TAG {c_string(SWAP_CUE_TAG)}")
    lines.append(f"#define LL_SWAP_FILL {c_string(SWAP_CUE_FILL)}")
    lines.append(f"#define LL_SWAP_BESIDE {c_string(SWAP_CUE_BESIDE)}")
    lines.append(f"#define LL_SWAP_ASPECT {SWAP_CUE_ASPECT}")
    lines.append("static const char *const LL_SUBTABS[] = { " + ", ".join(map(c_string, SUBTAB_TAGS)) + " };")
    lines.append(f"#define LL_TAB_SCREEN {c_string(TAB_CUE_SCREEN)}")
    lines.append("static const char *const LL_TABS[] = { " + ", ".join(map(c_string, TAB_TAGS)) + " };")
    lines.append("static const char *const LL_TAB_TAGS[] = { " + ", ".join(c_string(t) for t, _, _ in TAB_CUES) + " };")
    lines.append("static const char *const LL_TAB_FILLS[] = { " + ", ".join(c_string(f) for _, f, _ in TAB_CUES) + " };")
    for key, text in (("ENTRY_SCREEN", ENTRY_SCREEN), ("ENTRY_TAG", ENTRY_TAG),
                      ("ENTRY_TEMPLATE", ENTRY_TEMPLATE), ("ENTRY_PREVIOUS", ENTRY_PREVIOUS),
                      ("ENTRY_CAPTION", ENTRY_CAPTION), ("FEEDBACK_SCREEN", FEEDBACK_LIST[0]),
                      ("FEEDBACK_TAG", FEEDBACK_LIST[1])):
        lines.append(f"#define LL_{key} {c_string(text)}")
    lines.append(f"#define LL_ENTRY_FALLBACK_STEP {ENTRY_FALLBACK_STEP!r}")
    lines.append(f"#define LL_ENTRY_LIFT_DIVISOR {ENTRY_LIFT_DIVISOR}")
    lines.append("")
    entries = table_entries()
    for index, (name, rows) in enumerate(entries):
        lines.append(f"static const LLRow LL_ROWS_{index}[] = {{  /* {name} */")
        for (tag, sub), rules, gold, pad, align, fill, clear, dim in rows:
            r = ", ".join(str(RULES.index(x)) for x in rules)
            g = ", ".join("LL_NO_GOLD" if gold is None else str(x) for x in (gold or [None] * 4))
            p = "LL_NO_PADDING" if pad is None else str(pad)
            a = "LL_NO_ALIGN" if align is None else str(align)
            fs = "LL_NO_FILL" if fill is None else str(fill)
            d = "LL_NO_DIMENSION" if dim is None else str(dim)
            lines.append(f"    {{ {c_string(tag)}, {c_string(sub)}, {{ {r} }}, {{ {g} }}, {p}, {a}, {fs}, {clear}, {d} }},")
        lines.append("};")
    lines.append("")
    lines.append("static const LLFile LL_FILES[] = {")
    for index, (name, rows) in enumerate(entries):
        lines.append(f"    {{ {c_string(name)}, LL_ROWS_{index}, {len(rows)}, {int(gold_size_only(name))} }},")
    lines.append("};")
    lines.append("")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- the layout
def table_by_file() -> dict:
    return {name: {key: (rules, gold, pad, align, fill, clear, dim) for key, rules, gold, pad, align, fill, clear, dim in rows}
            for name, rows in table_entries()}


def game_size(source: GFFStruct, vanilla: GFFStruct) -> bool:
    """Is `source` laid out for the game's size: the game's own base, its root inside it?"""
    base, root = base_of(source), extent(source)
    return (base == base_of(vanilla) and root is not None and root[0] >= 0 and root[1] >= 0
            and root[0] + root[2] <= base[0] and root[1] + root[3] <= base[1])


def manifest_caption(manifest: str) -> float | None:
    """The Container's caption width a prompt manifest (kmrp_prompts.txt) gives, or None."""
    for line in manifest.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "prompt" and parts[1] == CAPTION_ROW:
            return float(parts[4])
    return None


def layout(name: str, vanilla: GFFStruct, source: GFFStruct, width: int, height: int,
           rows: dict, caption: float | None = None, donor: Path | None = None) -> GFFStruct | None:
    """`source` (the game's file or a mod's) laid out for width x height, in place, or None
    when it is not laid out for the game's size (game_size). What KmrpLiveLayout
    (kmrp-guiadapt.c) does, in Python. `caption`: the Container's caption width from the
    size's prompt manifest; without it the Container is not widened. `donor`: the size's
    kmrplayout.gui, whose LBL_TITLE the controller badge labels are cloned from; without it
    none is added."""
    if not game_size(source, vanilla):
        return None
    base = base_of(source)
    own = {key: extent(s) for key, s, _ in structures(vanilla)}
    own_align = {key: alignment(s) for key, s, _ in structures(vanilla)}
    own_fill = {key: fill_style(s) for key, s, _ in structures(vanilla)}
    own_structs = {key: s for key, s, _ in structures(vanilla)}
    # The build carries gold's geometry to other sizes for every file but these, whose
    # geometry another step owns (prepare_universal_resources.GOLD_GEOMETRY_EXCLUDED): theirs
    # is gold's at 3440x1440 only, upstream's (the rules') elsewhere. confirm.gui's gold popup
    # sits left of the middle, on purpose, at 3440x1440 alone (2026-10-30). Only the
    # geometry: text alignment and the rest stay gold's, which are upstream's there too
    # (map.gui's two labels, 18 where the game's file has 10).
    if gold_size_only(name) and (width, height) != GOLD_SIZE:
        rows = {key: (row[0], None, None, *row[3:]) for key, row in rows.items()}
    for key, struct, ctype in structures(source):
        v4 = extent(struct)
        row = rows.get(key)
        unmoved = row is not None and own.get(key) == v4
        rules = row[0] if row else [default_rule(f, key[1], ctype, v4) for f in range(4)]
        gold = row[1] if unmoved and row[1] is not None else [None] * 4
        e = child(struct, "EXTENT")
        out = [placed(f, rules[f], v4, gold[f], width, height, base) for f in range(4)]
        out[0] = aspect_left(rules, v4, gold, out, width, height, base)
        for f, x in zip(FIELDS, out):
            e.set_int32(f, x)
        if unmoved and row[2] is not None and (width, height) == GOLD_SIZE and struct.exists("PADDING"):
            struct.set_int32("PADDING", row[2])
        # Gold's text alignment, where the file still has the game's own.
        align = alignment(struct)
        if row is not None and row[3] is not None and align is not None and align == own_align.get(key):
            child(struct, "TEXT").set_int32("ALIGNMENT", row[3])
        # And its border's fill style, the same way.
        fill = fill_style(struct)
        if row is not None and row[4] is not None and fill is not None and fill == own_fill.get(key):
            child(struct, "BORDER").set_int32("FILLSTYLE", row[4])
        if row is not None and row[5]:
            for bit, (border_name, part) in enumerate(BORDER_PARTS):
                if not row[5] & (1 << bit):
                    continue
                border = child(struct, border_name)
                own_border = child(own_structs[key], border_name)
                if (border is not None and border.exists(part) and own_border is not None
                        and str(border.get_resref(part)) == str(own_border.get_resref(part))):
                    border.set_resref(part, ResRef.from_blank())
        # Gold's border thickness, at 3440x1440 only and where the file still has the game's.
        dim = dimension(struct)
        if (row is not None and row[6] is not None and (width, height) == GOLD_SIZE and dim is not None
                and dim == dimension(own_structs[key])):
            child(struct, "BORDER").set_int32("DIMENSION", row[6])
    # The build's gutters, never reducing one but for the hand-set ones.
    for key, struct, ctype in structures(source):
        if key[1] or ctype != LISTBOX or not struct.exists("PADDING"):
            continue
        tag = key[0].upper()
        for tags, unit, force in ((DESCRIPTION_LISTBOXES, GUTTER_AT_UNIT_SCALE, False),
                                  (LIST_LISTBOXES, LIST_GUTTER_AT_UNIT_SCALE, False),
                                  *((t, u, True) for t, u in HAND_TUNED_GUTTERS.get(name, ()))):
            if tag in tags:
                g = gutter(unit, height)
                if force or struct.get_int32("PADDING") < g:
                    struct.set_int32("PADDING", g)
    lists = [(t, k, b) for (s, t), (k, b) in sorted(ROW_LISTS.items()) if s == name]
    cue = name in R3_CUE_SCREENS and cue_template(source) is not None
    extra_cues = name in (SWAP_CUE_SCREEN, TAB_CUE_SCREEN)
    feedback = name == FEEDBACK_LIST[0]
    entry = name == ENTRY_SCREEN
    centre = name == "scriptselect.gui"
    journal = name == "journal.gui"
    widen = name == CONTAINER_SCREEN and caption is not None
    popup = name == POPUP_SCREEN
    badge = BADGE_SCREENS.get(name) if donor is not None else None
    # The area map's picture control: half the screen's width and height, centred, 14 px
    # lower for the renderer's top inset (analyze_resolution_guis.geometry,
    # set_map_control_extent; reverse-engineering/area-map-surface.md). Every size, 3440x1440 too.
    if name == MAP_SCREEN:
        target = next((s for k, s, _ in structures(source) if k == (MAP_TAG, "")), None)
        if target is not None:
            box = map_control_box(width, height)
            for f, v in zip(FIELDS, box):
                child(target, "EXTENT").set_int32(f, v)
    if (not lists and not cue and not extra_cues and not feedback and not entry
            and not (centre or journal or widen or popup or badge)):
        return source
    # The build's own steps, on a file: the lists made as tall as whole rows, then the R3
    # cue. A list or a cue the file cannot have (a mod's without the control, a row that
    # does not fit, portraits the cue would cover) is left out, as the C leaves it out.
    with tempfile.TemporaryDirectory(prefix="kmrp-livelayout-") as tmp:
        path = Path(tmp) / name
        gff = GFF(GFFContent.GUI)
        gff.root = source
        write_gff(gff, path, ResourceType.GUI)
        # In the build's order: the rows centred and the Journal's fitted after the
        # gutters, then the Feedback rows and the row lists, the Container widened last.
        # A list without a PADDING keeps none, as the C, which adds no fields, leaves it.
        centred = [c for c in source.acquire("CONTROLS", GFFList(), GFFList)
                   if c.acquire("TAG", "").upper() == "LST_AISTATE"]
        if centre and centred and centred[-1].exists("PADDING"):
            try:
                centre_rows_in_frame(path, path, width, "LST_AIState", SCRIPTSELECT_FRAME)
            except (ValueError, AttributeError, KeyError):
                pass
        if journal:
            try:
                fit_rows_to_list(path, path, height, "LB_ITEMS", JOURNAL_ROWS)
            except (ValueError, AttributeError, KeyError, ZeroDivisionError):
                pass
        if feedback and feedback_template(source) is not None:
            try:
                scale_row_template(path, path, height, FEEDBACK_LIST[1])
            except (ValueError, AttributeError):
                pass
        for tag, kind, bases in lists:
            try:
                fit_list_to_rows(path, path, height, tag, bases, popup=kind == "popup")
            except (ValueError, AttributeError):
                pass
        if widen:
            try:
                widen_container(path, path, caption)
            except (ValueError, AttributeError, KeyError):
                pass
        # The message popup sized from its measured table by the font scale, centred where
        # the panel was (scale_message_popup.apply_tuned); then the badge label.
        if popup:
            try:
                apply_popup_layout(path, path, font_scale(height))
            except (ValueError, AttributeError, KeyError):
                pass
        if badge:
            try:
                add_confirm_badge(path, path, donor, tag=badge)
            except (ValueError, AttributeError, KeyError):
                pass
        if cue:
            try:
                add_party_switch_cue(path, path)
            except (ValueError, AttributeError):
                pass
        if extra_cues and extra_cue_template(read_gff(path).root, name) is not None:
            try:
                (add_subtab_swap_cue if name == SWAP_CUE_SCREEN else add_tab_strip_cues)(path, path)
            except (ValueError, AttributeError):
                pass
        if entry and entry_template(read_gff(path).root) is not None:
            try:
                add_entry(path, path)
            except (ValueError, AttributeError):
                pass
        return read_gff(path).root


def hud_cues(source: GFFStruct) -> GFFStruct | None:
    """A HUD file with the build's combat cues added (add_combat_cues), or None where the
    build would leave it as it is or stop with an error. What KmrpHudCues
    (kmrp-guiadapt.c) does, in Python. The C changes fields in place and adds none, so a
    template label without a field the cue sets gives no cues on either side."""
    by_tag = {c.get_string("TAG"): c for c in source.acquire("CONTROLS", GFFList(), GFFList) if c.exists("TAG")}
    template = by_tag.get(COMBAT_CUE_TEMPLATE)
    border = child(template, "BORDER") if template is not None else None
    if (template is None or not template.exists("ID") or extent(template) is None or border is None
            or not border.exists("FILL")):
        return None
    with tempfile.TemporaryDirectory(prefix="kmrp-hudcues-") as tmp:
        path = Path(tmp) / "hud.gui"
        gff = GFF(GFFContent.GUI)
        gff.root = source
        write_gff(gff, path, ResourceType.GUI)
        try:
            if not add_combat_cues(path, path):
                return None
        except (ValueError, AttributeError, KeyError):
            return None
        return read_gff(path).root


def entry_template(root: GFFStruct) -> GFFStruct | None:
    """A button the writer can clone, adding an inline caption when needed."""
    by_tag = {c.get_string("TAG"): c for c in root.acquire("CONTROLS", GFFList(), GFFList)}
    template = by_tag.get(ENTRY_TEMPLATE)
    if template is None:
        return None
    border, text = child(template, "BORDER"), child(template, "TEXT")
    return template if (template.exists("ID") and template.exists("TAG") and extent(template) is not None
                        and border is not None and border.exists("FILL") and text is not None
                        and text.exists("STRREF")) else None


def feedback_template(root: GFFStruct) -> GFFStruct | None:
    target = next((c for c in root.acquire("CONTROLS", GFFList(), GFFList)
                   if c.get_string("TAG").upper() == FEEDBACK_LIST[1].upper()), None)
    proto = child(target, "PROTOITEM") if target is not None else None
    return proto if proto is not None and extent(proto) is not None else None


def extra_cue_template(root: GFFStruct, name: str) -> GFFStruct | None:
    """Use the build's template choice, but require the fields the C writer replaces."""
    controls = root.acquire("CONTROLS", GFFList(), GFFList)
    by_tag = {c.get_string("TAG"): c for c in controls}
    if name == SWAP_CUE_SCREEN:
        template = by_tag.get(SUBTAB_TAGS[0])
    else:
        template = next((c for c in controls if c.acquire("CONTROLTYPE", -1) == 4),
                        by_tag.get(TAB_TAGS[0]))
    if template is None:
        return None
    border = child(template, "BORDER")
    return template if (template.exists("ID") and template.exists("TAG") and extent(template) is not None
                        and border is not None and border.exists("FILL")) else None


def cue_template(root: GFFStruct) -> GFFStruct | None:
    """The label the R3 cue is cloned from (add_party_switch_cue: the first CONTROLTYPE 4),
    when it has every field the cue sets, else None: the C changes fields in place and adds
    none, so a template without one gets no cue on either side."""
    for control in root.acquire("CONTROLS", GFFList(), GFFList):
        if control.exists("CONTROLTYPE") and control.get_int32("CONTROLTYPE") == 4:
            border = child(control, "BORDER")
            ok = (control.exists("ID") and control.exists("TAG") and extent(control) is not None
                  and border is not None and border.exists("FILL"))
            return control if ok else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="stop if the table is out of date")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not TABLE.is_file() or TABLE.read_text(encoding="ascii") != text:
            print(f"{TABLE} is out of date: run python tools/build_live_layout.py", file=sys.stderr)
            return 1
        print(f"{TABLE} is current")
        return 0
    TABLE.write_bytes(text.encode("ascii"))
    print(f"wrote {TABLE}: {len(FILES)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
