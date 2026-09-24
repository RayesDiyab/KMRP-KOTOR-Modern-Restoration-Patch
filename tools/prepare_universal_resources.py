#!/usr/bin/env python3
"""Build compact common-art and per-resolution GUI resources."""

from __future__ import annotations

import argparse
import copy
import io
import json
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path

from pykotor.resource.formats.gff import GFFStruct, read_gff, write_gff

from apply_gold_hud_proportions import apply_proportions
from build_controller_prompt_textures import (GLYPH_FAMILIES,
                                              build_prompt_textures,
                                              build_square_glyph_tga,
                                              family_resref)
from build_controller_layout import (add_confirm_badge,
                                     add_entry as add_controller_layout_entry,
                                     build_art as build_controller_layout_art,
                                     build_gui as build_controller_layout_gui)
from build_menubg_texture import build_texture_for_gui
from build_scaled_fonts import export_font_txis, export_fonts, scale_txi
from fix_hud_menubg import fix_menubg_file
from scale_hud_minimap import patch_gui
from transfer_gold_gui_geometry import transfer_geometry
from scale_listbox_padding import (LIST_GUTTER_AT_UNIT_SCALE, SCRIPTSELECT_FRAME,
                                   centre_rows_in_frame, scale_listbox_padding)
from scale_message_popup import apply_tuned as apply_popup_layout
from export_tutorial_icons import export_tutorial_icons
from fix_feedback_list_prototypes import fix_feedback_prototypes, fix_scriptselect_prototypes
from scale_row_icon_frames import FRAME_RESREFS, export_frames


MENUBG_TEXTURE_NAME = "lbl_mileftbot.tga"

# Font sizing is applied to the atlases' TXI metrics rather than at runtime (see
# ResolutionPatch in KmrpPatcher.cs). Must stay in step with that class's
# ScaleForHeight, which scales list-row heights by the same rule so rows always grow
# with the text: 1.25x at 1080p, 1.75x at 1440p, 2.75x at 2160p, clamped at 1.0.
FONT_HEIGHT_DIVISOR = 720.0
# No offset: 1.00x at 720p, 1.50x at 1080p, 2.00x at 1440p, 3.00x at 2160p.
# An earlier -0.25 gave 1.75x/2.75x at 1440p/2160p, which play-tested too small.
FONT_SCALE_OFFSET = 0.0

# The HD atlases under assets/hd-fonts are rendered at the LARGEST scale any
# resolution asks for, so every resolution scales them *down* rather than up.
# The engine draws one texel per pixel, so an atlas stretched past the size it
# was rasterised at is simply blurry -- baking at the top of the range and
# shrinking keeps every resolution crisp. Must match the --scale that
# tools/build_font_from_ttf.py was run with to produce assets/hd-fonts.
HD_FONT_BAKE_SCALE = 3.0

# `spacingR` is added to each glyph's advance ONLY where the engine measures
# text for line breaking (`fadd [edi+0x10]` at 0x0045A5C9). The path that
# actually draws the glyphs (0x0045A806) does not read it. **Proven in game**:
# raising it from 0.02px to 0.4px stopped long descriptions being clipped and
# left the visible letter spacing completely unchanged.
#
# That makes it a wrap-safety margin, not a typographic control. It is needed
# because the engine's own line measurement UNDERESTIMATES: comparing the
# per-line widths it stores against the widths implied by the atlas's glyph
# advances, it runs consistently ~3% low (203 vs 208, 106 vs 109, 1202 vs
# 1238 -- read live out of the description listbox). It truncates each glyph's
# advance to an integer, losing up to a pixel per character, so a long line it
# believes fits in the 1293px content area really renders ~39px wider and the
# last word is sliced off at the clip edge. Vanilla text rarely reached the
# limit, so the bug only shows once the font is enlarged.
#
# Half a pixel per glyph covers the average truncation loss regardless of font
# size -- the error is bounded by one pixel per character whatever the scale --
# so a flat value is right here and does not need to scale with resolution.
# `spacingR` is written AFTER `scale_txi` for exactly that reason.
LETTER_SPACING_PX = 0.5


def letter_spacing_for(scale: float) -> float:
    """Pixels of per-glyph wrap margin. Affects line breaking only, not drawing."""
    return LETTER_SPACING_PX


def font_scale_for(height: int) -> float:
    return max(1.0, height / FONT_HEIGHT_DIVISOR - FONT_SCALE_OFFSET)


def apply_letter_spacing(txi: str, pixels: float) -> str:
    """Force `spacingR` to a fixed pixel amount, overriding any scaled value."""
    lines = []
    for line in txi.splitlines():
        if line.split(" ", 1)[0] == "spacingR":
            lines.append(f"spacingR {pixels / 100.0:g}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


GROUPS = {
    "4:3": [
        "800x600", "960x720", "1024x768", "1280x960", "1400x1050", "1440x1080",
        "1600x1200", "1856x1392", "1920x1440", "2048x1536", "3200x2400", "4096x3072",
    ],
    "16:10": [
        "1024x640", "1152x720", "1280x800", "1440x900", "1680x1050", "1920x1200",
        "2048x1280", "2304x1440", "2560x1600", "2880x1800", "3840x2400", "5120x3200",
    ],
    "16:9": [
        "1024x576", "1152x648", "1280x720", "1360x768", "1366x768", "1600x900",
        "1920x1080", "2048x1152", "2560x1440", "3840x2160", "5120x2880", "6016x3384",
        "7680x4320", "8192x4608", "15360x8640",
    ],
    "21:9": ["1280x1080", "2560x1080", "3440x1440", "3840x1600", "5120x2160"],
    "32:9": ["1920x540", "3840x1080", "5120x1440", "7680x2160"],
}

ASPECT_FOLDERS = {
    "4:3": "4-by-3",
    "16:10": "16-by-10",
    "16:9": "16-by-9",
    "21:9": "21-by-9",
    "32:9": "32-by-9",
}

# Single-item description panes: one wrapped paragraph beside a scrollbar. These
# are the controls the missing gutter actually disfigures, and LB_DESCRIPTION is
# the one confirmed by play-test. Selection lists get their own, much smaller
# gutter below -- see LIST_LISTBOXES.
DESCRIPTION_LISTBOXES = {
    "LB_DESCRIPTION", "LB_DESC", "LBL_ITEM_DESCRIPTION",
    # questitem.gui names its pane LB_ITEM_DESCRIPTION -- journal.gui's is
    # LBL_ITEM_DESCRIPTION. One missing letter meant the quest-item description
    # got no gutter and clipped under its scrollbar, found in play. upgrade.gui's
    # LB_DESC_LS is the same shape as LB_DESC.
    "LB_ITEM_DESCRIPTION", "LB_DESC_LS",
    # Deliberately NOT included: LB_MESSAGE (computer, confirm), LB_MESSAGES
    # (messages) and LB_DIALOG. Those are multi-line logs -- a paragraph-sized
    # gutter beside a wall of short lines reads as a broken margin.
}

# Multi-row selection lists. The gutter here sits beside an icon column, not a
# paragraph, so it is a quarter of the description one (25px at 3440x1440,
# chosen in game). Only usable since gold v11 made PADDING a pure left inset:
# before that it also set row pitch, inset the right edge and pushed the first
# row down. See tools/build_listbox_padding_fix.py.
#
# Restricted to lists with an icon column, which is what the gap is for.
# Text-only lists (LB_GAMES, LB_MODULES, LB_OPTIONS, LB_RESOLUTIONS,
# LST_EventList) and the message logs are left at their authored values.
LIST_LISTBOXES = {
    "LB_ITEMS", "LB_ABILITY", "LB_FEATS", "LB_POWERS",
    "LB_SHOPITEMS", "LB_INVITEMS",
}

# confirm.gui is deliberately NOT here. It is the shared message popup, and its
# layout is generated from the play-tested table in scale_message_popup.py at
# every resolution instead -- see the branch in the per-resolution loop, and the
# TUNED_SCALE comment for why a ratio transfer is the wrong tool for this one.
# Gutters hand-set on the gold 3440x1440 files, kept per FILE because every one
# of these tags is shared with a file that must NOT inherit the value:
# LB_MESSAGE is also confirm.gui's, which the popup layout owns; LB_REPLIES is
# also dialog.gui's; and LB_DESC is in 18 files at 72 where only equip.gui was
# hand-set to 20. Stored at unit scale so they still scale per resolution rather
# than pinning a 3440x1440 pixel count at every size, and applied LAST so they
# win over the broader tiers above.
HAND_TUNED_GUTTERS = {
    "computer.gui": [({"LB_MESSAGE"}, 20.0), ({"LB_REPLIES"}, 5.0)],
    "equip.gui": [({"LB_DESC"}, 10.0)],
    # Feedback Options: a list of options checkboxes with its scrollbar on the
    # left. CSWGuiOptionsCheckbox::SetExtent (0x006DE000) draws each circle as
    # a fixed 25px square at the row's very left, and the engine starts rows
    # where the scrollbar ends and forces the scrollbar to the list's edge
    # (0x0041BFC0, 0x00419C0D), so with vanilla's PADDING 0 every circle sat
    # against the scrollbar -- reported 2026-09-24 at 3440x1440. Since gold v12
    # PADDING is a horizontal gutter on the scrollbar side and nothing else, so
    # it opens the gap without moving the rows apart: 12px at 3440x1440, about
    # half a circle.
    "optfeedback.gui": [({"LB_OPTIONS"}, 6.0)],
}

# Files whose 3440x1440 gold layout is NOT transferred to other resolutions.
#
# The transfer used to be an explicit allow-list, and it drifted: 23 hand-tuned
# files were missing from it -- abilities.gui, store.gui, pwrlvlup.gui, every
# options screen -- so at every resolution except 3440x1440 those screens kept
# upstream's extents and their text boxes ran to the edge of the artwork instead
# of sitting inside it. It is now derived: every gold file whose extents differ
# from its upstream counterpart is transferred, so tuning a new file is picked up
# without editing a list. Only the files below are held back, each because
# something else already owns their geometry.
GOLD_GEOMETRY_EXCLUDED = {
    # Sized from this resolution's own font scale by apply_popup_layout, which
    # runs before the 3440x1440 passthrough and so already covers every case.
    "confirm.gui",
    # LBL_Map is computed per resolution from the marker overlay, not inherited.
    "map.gui",
}


# The full-screen menu backgrounds: 2867x1434 at the authored resolution, 15.68 MB
# each uncompressed, and 49 of them. They are the bulk of an installed Override
# once the item icons are compressed -- 768 MB of 1008 MB measured on a real
# install, against 12.4 MB for all 351 icons.
#
# Selected by pixel area rather than by name, because the set is not a list
# anyone maintains. The threshold sits below their 4,111,278 pixels and above
# everything else in the shared assets, whose next largest is 1,555,211.
MENU_BACKGROUND_MIN_PIXELS = 3_000_000

# ...except font atlases, which are LARGER than the backgrounds -- dialogfont32x32
# is 2048x2048, 4,194,304 pixels -- and must never be block-compressed: DXT on
# glyph edges damages every line of text in the game.
FONT_ATLAS_MARKERS = ("font", "fnt_")

# Asserted so that a change to the shared assets fails the build rather than
# quietly compressing something it should not, or quietly stopping.
EXPECTED_MENU_BACKGROUNDS = 49


def tpc_from_image(image, encoding: int, pixel_format: str) -> bytes:
    """A stock-layout TPC: 128-byte header, the DXT blocks, then a TXI.

    TPC stores rows bottom-up, the way the source TGAs do (descriptor 0x08), and
    Pillow hands back top-down pixels -- so the flip here is what keeps the
    texture the right way up. The icons shipped upside down once for want of it.

    DXT encodes 4x4 blocks, so both dimensions are padded up to the block grid by
    repeating the last row and column. Padding rather than cropping: the added
    pixels duplicate the frame border, where a crop would shave it away.
    """
    import io

    from PIL import Image

    width, height = image.size
    padded_w = width + (-width % 4)
    padded_h = height + (-height % 4)
    if (padded_w, padded_h) != (width, height):
        padded = Image.new("RGBA", (padded_w, padded_h))
        padded.paste(image, (0, 0))
        if padded_w > width:
            edge = image.crop((width - 1, 0, width, height))
            for x in range(width, padded_w):
                padded.paste(edge, (x, 0))
        if padded_h > height:
            row = padded.crop((0, height - 1, padded_w, height))
            for y in range(height, padded_h):
                padded.paste(row, (0, y))
        image = padded

    upright = image.transpose(Image.FLIP_TOP_BOTTOM)
    buffer = io.BytesIO()
    if pixel_format == "DXT1":
        upright.convert("RGB").save(buffer, format="DDS", pixel_format="DXT1")
    else:
        upright.save(buffer, format="DDS", pixel_format="DXT5")
    payload = buffer.getvalue()[128:]
    header = struct.pack("<IfHHBB", len(payload), 1.0,
                         image.width, image.height, encoding, 1)
    return header + b"\x00" * (128 - len(header)) + payload + b"mipmap 0\n"


def compress_menu_backgrounds(files: list[Path], staging: Path) -> list[Path]:
    """Return `files` with every full-screen background replaced by a DXT TPC.

    DXT1 for the ones that are fully opaque -- every lbl_* menu background, which
    is 27 of the 49 -- because with no alpha to carry it spends its whole budget
    on colour: measured 37.7 dB at 8.0x smaller, BETTER than the 36.9 dB the item
    icons get from DXT5, where half the bits go to an alpha channel.

    DXT5 for the 22 loading screens, which carry alpha on 0.49% of their pixels.
    """
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow unavailable; shipping the backgrounds uncompressed")
        return files

    staging.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    opaque = translucent = before = after = 0
    for path in files:
        if path.suffix.lower() != ".tga":
            result.append(path)
            continue
        lowered = path.name.lower()
        if any(marker in lowered for marker in FONT_ATLAS_MARKERS):
            result.append(path)
            continue
        head = path.read_bytes()[:18]
        width, height = struct.unpack_from("<HH", head, 12)
        if width * height < MENU_BACKGROUND_MIN_PIXELS:
            result.append(path)
            continue

        with Image.open(path) as source:
            image = source.convert("RGBA")
            histogram = image.getchannel("A").histogram()
            is_opaque = histogram[255] == image.width * image.height
            blob = tpc_from_image(image, 2 if is_opaque else 4,
                                  "DXT1" if is_opaque else "DXT5")
        if is_opaque:
            opaque += 1
        else:
            translucent += 1
        target = staging / (path.stem + ".tpc")
        target.write_bytes(blob)
        before += path.stat().st_size
        after += len(blob)
        result.append(target)

    converted = opaque + translucent
    if converted != EXPECTED_MENU_BACKGROUNDS:
        raise ValueError(
            f"Expected {EXPECTED_MENU_BACKGROUNDS} full-screen backgrounds, "
            f"compressed {converted}. The shared assets changed: check that no "
            f"font atlas is being caught and that none has been dropped.")
    print(f"  compressed {converted} menu backgrounds "
          f"({opaque} DXT1, {translucent} DXT5): "
          f"{before/1048576:.0f} MB -> {after/1048576:.0f} MB "
          f"({before/after:.1f}x)")
    return result


# The size the item icons ship at. The pack authors them at 192, which is exactly
# the EXTENT of an equipment slot at the authored resolution, so 192 is native
# and anything below it is upsampled on the largest place icons are drawn.
#
# 160 is a deliberate trade of sharpness for bytes: 12.4 MB to 8.5 MB across the
# 351 of them, costing 24.1 dB against 27.8 dB on colour weighted by visibility.
# Set this back to ICON_SOURCE_SIZE to undo it; nothing else has to change.
#
# The free version of this saving does not exist. DXT1 would halve the size at
# 34 dB, because with no alpha to carry it spends its whole budget on colour --
# but it needs one bit of alpha and this executable has no
# GL_COMPRESSED_RGBA_S3TC_DXT1. The format table at 0x0073F36C holds the no-alpha
# 0x83F0 and DXT5's 0x83F3 and nothing else, and repointing 0x83F0 at 0x83F1
# would hand the transparent three-colour mode to all 5,229 shipped DXT1
# textures, 1,387 of which use it -- holes through character skins and the
# BioWare logo.
ICON_SOURCE_SIZE = 192
ICON_TEXTURE_SIZE = 160


def resize_premultiplied(image, size: int):
    """Lanczos on premultiplied colour, then divided back out.

    Not an optimisation -- a correctness fix. The RGB of a fully transparent
    pixel in these icons is arbitrary, and a straight resize blends it into the
    visible edge as a dark or coloured fringe. Measured on twelve icons, the two
    approaches differ by 30.5 dB, which is the same order as the compression
    error itself.
    """
    from PIL import Image

    raw = bytearray(image.tobytes())
    for i in range(0, len(raw), 4):
        alpha = raw[i + 3]
        if alpha != 255:
            raw[i] = raw[i] * alpha // 255
            raw[i + 1] = raw[i + 1] * alpha // 255
            raw[i + 2] = raw[i + 2] * alpha // 255
    premultiplied = Image.frombytes("RGBA", image.size, bytes(raw))

    small = premultiplied.resize((size, size), Image.LANCZOS)

    out = bytearray(small.tobytes())
    for i in range(0, len(out), 4):
        alpha = out[i + 3]
        if alpha == 0:
            out[i] = out[i + 1] = out[i + 2] = 0
        elif alpha != 255:
            out[i] = min(255, out[i] * 255 // alpha)
            out[i + 1] = min(255, out[i + 1] * 255 // alpha)
            out[i + 2] = min(255, out[i + 2] * 255 // alpha)
    return Image.frombytes("RGBA", small.size, bytes(out))


def compress_bundled_icons(files: list[Path], staging: Path) -> list[Path]:
    """Return `files` with every 192x192 icon replaced by a DXT5 TPC of itself.

    The HD icon pack ships 192x192 uncompressed 32-bit TGA -- 144 KB an icon,
    against about 15 KB for the 64x64 DXT5 TPC the game itself ships, so 9.5x
    the bytes of vanilla. The Inventory and Equipment screens draw dozens at
    once, which is why those two screens, and only those two, stall and flash
    when switched between quickly.

    DXT5 at 4.0x smaller, and then scaled to ICON_TEXTURE_SIZE. DXT5 rather than
    DXT1 because every one of these icons carries soft alpha -- a survey of all
    351 found not one with alpha that is purely opaque or purely clear -- and
    because this executable cannot upload DXT1 with alpha at all; see the note
    on ICON_TEXTURE_SIZE.

    Anything that is not ICON_SOURCE_SIZE square passes through untouched.
    """
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow unavailable; shipping the icons uncompressed")
        return files

    staging.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    converted = before = after = 0
    for path in files:
        head = path.read_bytes()[:18]
        width, height = struct.unpack_from("<HH", head, 12)
        if (width, height) != (ICON_SOURCE_SIZE, ICON_SOURCE_SIZE):
            result.append(path)
            continue
        width = height = ICON_TEXTURE_SIZE
        # TPC stores its rows bottom-up, the same way these source TGAs do
        # (descriptor 0x08, bottom-left origin). Pillow hands back top-down
        # pixels, so writing them straight out produces a texture the engine
        # draws upside down -- confirmed by decoding the stock
        # ia_class4_001.tpc and comparing: mine scored 9.35 flipped against
        # 12.73 as-is. Reported from play as "all the inventory items are
        # upside down".
        with Image.open(path) as source:
            image = source.convert("RGBA")
            if ICON_TEXTURE_SIZE != ICON_SOURCE_SIZE:
                image = resize_premultiplied(image, ICON_TEXTURE_SIZE)
            upright = image.transpose(Image.FLIP_TOP_BOTTOM)
            buffer = io.BytesIO()
            upright.save(buffer, format="DDS", pixel_format="DXT5")
        payload = buffer.getvalue()[128:]
        # The stock TPC layout: 128-byte header, the blocks, then a TXI.
        # `mipmap 0` is what the stock GUI textures carry; without it the engine
        # mips art that is only ever drawn at 1:1.
        header = struct.pack("<IfHHBB", len(payload), 1.0, width, height, 4, 1)
        blob = header + b"\x00" * (128 - len(header)) + payload + b"mipmap 0\n"
        target = staging / (path.stem + ".tpc")
        target.write_bytes(blob)
        before += path.stat().st_size
        after += len(blob)
        converted += 1
        result.append(target)
    if converted:
        print(f"  compressed {converted} icons to {ICON_TEXTURE_SIZE}px DXT5 TPC: "
              f"{before/1048576:.1f} MB -> {after/1048576:.1f} MB "
              f"({before/after:.1f}x)")
    return result


def write_zip(output: Path, files: list[Path]) -> None:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:
        for path in sorted(files, key=lambda item: item.name.lower()):
            archive.write(path, path.name)



# The R3 party-switch cue.
#
# R3 changes which party member Character, Equipment, Inventory and the
# Skills/Powers/Feats screen are showing. There is nowhere in those screens to
# advertise it: the two portrait buttons' BORDER.FILL *is* the portrait, rewritten
# per character by the panel, and the gap between them holds no control at all.
#
# So one is added here -- and it only becomes real because the module binds it at
# runtime. A panel constructs the controls it knows by name and nothing else, so a
# control added to a .gui alone is never built and never drawn; that was measured
# by adding one and looking. See reverse-engineering/custom-gui-controls.md.
R3_CUE_TAG = "LBL_KMRPR3"
R3_CUE_FILL = "kmrpr3_party"
R3_CUE_SCREENS = ("abilities.gui", "character.gui", "equip.gui", "inventory.gui")
# The cue's side as a fraction of the portrait height. Until 2026-09-24 it filled
# the space between the portraits, the gap or their height, whichever was
# smaller; play-testing made it 10% smaller, and where the gap is too narrow for
# that size it now sits beside the portraits instead (r3_cue_extent).
R3_CUE_SCALE = 0.9
# Where it does fit, the gap must leave this fraction of the cue free each side.
R3_CUE_GAP_MARGIN = 0.1
# Anything else a cue cannot be drawn over. Labels are left out on purpose: the
# screens' background frames are labels whose extents reach into the portrait
# row while their art stops short of it -- Equipment's LBL_ATTACK_INFO by 18 px
# at 1920x1080 -- so an extent test on them would reject a clear spot.
R3_CUE_BLOCKING_TYPES = {6, 7, 8, 9, 10, 11}   # button, checkbox, slider, scroll, progress, list


# LT and RT change which menu screen is open, and the tab strip they act on says
# nothing about them either. Same mechanism as the R3 cue and the same reason it
# is needed: top.gui owns the strip, and a control added to it is only real once
# the module binds it.
TAB_CUE_SCREEN = "top.gui"
TAB_CUES = (("LBL_KMRPLT", "kmrplt_menu", "LT"),
            ("LBL_KMRPRT", "kmrprt_menu", "RT"))
TAB_TAGS = ("BTN_EQU", "BTN_INV", "BTN_CHAR", "BTN_ABI",
            "BTN_MSG", "BTN_JOU", "BTN_MAP", "BTN_OPT")


def _clone_cue_control(controls, template, tag: str, fill: str,
                       left: int, top: int, size: int, width: int = 0):
    """A new control modelled on one already in the file.

    Cloned rather than built field by field: the loader reads what it expects to
    find, and a hand-built struct missing a field fails by simply not drawing,
    which is indistinguishable from the control not existing.
    """
    cue = GFFStruct(template.struct_id)
    cue._fields = copy.deepcopy(template._fields)
    cue.set_string("TAG", tag)

    # The panel files controls into an array indexed BY ID and grows it when an
    # id lands past the end, so counting on from the highest in use is free.
    ids = [control.get_int32("ID") for control in controls if control.exists("ID")]
    cue.set_int32("ID", max(ids) + 1)

    extent = cue.get_struct("EXTENT")
    extent.set_int32("LEFT", left)
    extent.set_int32("TOP", top)
    extent.set_int32("WIDTH", width or size)
    extent.set_int32("HEIGHT", size)
    cue.set_struct("EXTENT", extent)

    border = cue.get_struct("BORDER")
    border.set_resref("FILL", fill)
    for field in ("CORNER", "EDGE"):
        if border.exists(field):
            border.set_resref(field, "")
    if border.exists("DIMENSION"):
        border.set_int32("DIMENSION", 0)
    cue.set_struct("BORDER", border)

    # The template's caption would otherwise come along with it.
    if cue.exists("TEXT"):
        text = cue.get_struct("TEXT")
        if text.exists("TEXT"):
            text.set_string("TEXT", "")
        if text.exists("STRREF"):
            text.set_uint32("STRREF", 0xFFFFFFFF)
        cue.set_struct("TEXT", text)

    controls.append(cue)
    return cue


def add_tab_strip_cues(source: Path, destination: Path) -> int:
    """Put LT and RT one tab-width outside each end of the menu strip.

    Everything is derived from the strip itself -- its size, its pitch and its
    vertical centre -- so the cues land correctly at every resolution and stay
    correct if the strip is ever re-laid-out.
    """
    gff = read_gff(source)
    root = gff.root
    controls = root.get_list("CONTROLS")
    by_tag = {control.get_string("TAG"): control for control in controls}

    if any(tag in by_tag for tag, _, _ in TAB_CUES):
        return 0

    tabs = []
    for tag in TAB_TAGS:
        control = by_tag.get(tag)
        if control is None:
            raise ValueError(f"{source.name} has no {tag}; it does not own the "
                             f"menu tab strip")
        extent = control.get_struct("EXTENT")
        tabs.append((extent.get_int32("LEFT"), extent.get_int32("TOP"),
                     extent.get_int32("WIDTH"), extent.get_int32("HEIGHT")))
    tabs.sort()

    # Just outside each end of the strip, separated by a third of a cue.
    #
    # A full tab pitch was tried first and read as floating away from the row
    # rather than belonging to it -- the tabs are spaced more than twice their own
    # width apart, so "one more slot" is a long way out. The gap is a fraction of
    # the cue instead, which keeps the same proportion at every resolution.
    size = tabs[0][3]
    gap = size // 3
    centre_y = tabs[0][1] + size // 2
    left_centre = tabs[0][0] - gap - size // 2
    right_centre = tabs[-1][0] + tabs[-1][2] + gap + size // 2

    template = next(
        (control for control in controls
         if control.exists("CONTROLTYPE") and control.get_int32("CONTROLTYPE") == 4),
        None)
    if template is None:
        # top.gui is all highlight-labels and buttons; either is a fine model,
        # and the module constructs a plain label whatever this says.
        template = by_tag[TAB_TAGS[0]]

    for (tag, fill, _), centre in zip(TAB_CUES, (left_centre, right_centre)):
        _clone_cue_control(controls, template, tag, fill,
                           centre - size // 2, centre_y - size // 2, size)

    root.set_list("CONTROLS", controls)
    write_gff(gff, destination)
    return len(TAB_CUES)


# X cycles the Skills / Powers / Feats sub-tab. Confirmed from the handler the
# ABILITIES panel registers for 0x29 (0x006AE714): it reads a byte at
# CGuiInGame+0xBC0, switches on 0/1/2, and the third arm writes 0 back -- a
# three-state cycle that wraps. Nothing on the screen said so.
#
# One control, not two: Swap_tabs.png is already the whole phrase, the X button
# and the arrows together.
SWAP_CUE_SCREEN = "abilities.gui"
SWAP_CUE_TAG = "LBL_KMRPSWAP"
SWAP_CUE_FILL = "kmrpswap_abi"
SWAP_CUE_GLYPH = "SWAP"
# The art is close to two to one, and the control is given the same shape so the
# engine's stretch does not distort it.
SWAP_CUE_ASPECT = 2
SUBTAB_TAGS = ("BTN_SKILLS", "BTN_POWERS", "BTN_FEATS")


def add_subtab_swap_cue(source: Path, destination: Path) -> bool:
    """Put the swap-tabs cue just past the last sub-tab, on its row."""
    gff = read_gff(source)
    root = gff.root
    controls = root.get_list("CONTROLS")
    by_tag = {control.get_string("TAG"): control for control in controls}

    if SWAP_CUE_TAG in by_tag:
        return False

    tabs = []
    for tag in SUBTAB_TAGS:
        control = by_tag.get(tag)
        if control is None:
            raise ValueError(f"{source.name} has no {tag}; it has no sub-tabs")
        extent = control.get_struct("EXTENT")
        tabs.append((extent.get_int32("LEFT"), extent.get_int32("TOP"),
                     extent.get_int32("WIDTH"), extent.get_int32("HEIGHT")))
    tabs.sort()

    last = tabs[-1]
    height = last[3]
    gap = height // 3
    left = last[0] + last[2] + gap
    _clone_cue_control(controls, by_tag[SUBTAB_TAGS[0]], SWAP_CUE_TAG,
                       SWAP_CUE_FILL, left, last[1], height,
                       width=height * SWAP_CUE_ASPECT)

    root.set_list("CONTROLS", controls)
    write_gff(gff, destination)
    return True


def r3_cue_size(portrait_height: int) -> int:
    """The R3 cue's side, in pixels: R3_CUE_SCALE of the portrait height.

    Rounded half up in integers rather than through round(), which would round
    a .5 to even and make the size depend on floating-point noise in the scale.
    """
    return max(1, (portrait_height * round(R3_CUE_SCALE * 100) + 50) // 100)


def r3_cue_extent(first: tuple[int, int, int, int],
                  second: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Where the R3 cue goes, from the two portraits' (left, top, width, height).

    Centred in the gap between them when the gap holds the cue at full size with
    R3_CUE_GAP_MARGIN of it free either side: every 21:9 and 32:9 resolution but
    1280x1080, 3440x1440 among them. Otherwise just right of the second portrait,
    a third of a cue away, like the tab-strip cues. At 4:3, 16:10 and 16:9 the
    gap is narrower than the cue -- 6 px at 800x600, 36 px at 1920x1080 against
    a 57 px cue -- and a cue shrunk to fit it was 5 px wide at 800x600.

    Right, not left: the portraits sit at the curved left end of a bar the
    background art draws, and a cue on that side was rendered crowding the
    curve on all four screens, while the bar runs on empty to the right. Always
    vertically centred on the portraits.
    """
    size = r3_cue_size(first[3])
    top = first[1] + (first[3] - size) // 2
    gap_left = first[0] + first[2]
    gap = second[0] - gap_left
    if gap >= size + 2 * int(size * R3_CUE_GAP_MARGIN):
        return gap_left + (gap - size) // 2, top, size, size
    return second[0] + second[2] + size // 3, top, size, size


def add_party_switch_cue(source: Path, destination: Path) -> bool:
    """Put the R3 cue by a screen's two party portraits -- between or beside them.

    Placed from the portraits' own extents rather than from a table of numbers,
    so it lands correctly at every resolution without anything to keep in sync.
    r3_cue_extent decides where.

    Cloned from a label already in the same file, not built field by field: the
    loader reads what it expects to find, and a hand-built struct missing a field
    fails in a way that looks like the control simply not drawing. Only what has
    to differ is changed.
    """
    gff = read_gff(source)
    root = gff.root
    controls = root.get_list("CONTROLS")

    by_tag = {control.get_string("TAG"): control for control in controls}
    if R3_CUE_TAG in by_tag:
        return False                      # already present: nothing to do

    for required in ("BTN_CHANGE1", "BTN_CHANGE2"):
        if required not in by_tag:
            raise ValueError(f"{source.name} has no {required}; it is not a "
                             f"party screen and should not be in R3_CUE_SCREENS")

    def box(control) -> tuple[int, int, int, int]:
        extent = control.get_struct("EXTENT")
        return tuple(extent.get_int32(field)
                     for field in ("LEFT", "TOP", "WIDTH", "HEIGHT"))

    first, second = box(by_tag["BTN_CHANGE1"]), box(by_tag["BTN_CHANGE2"])
    if second[0] < first[0] + first[2]:
        raise ValueError(f"{source.name}: the portraits overlap "
                         f"({first[0] + first[2]}..{second[0]})")
    # Square, so one square texture is correct at every resolution with no
    # aspect pre-compensation -- unlike the caption badges, which are stretched
    # across oblong buttons.
    x, y, size, _ = r3_cue_extent(first, second)

    # A GUI pack that rearranged the row would otherwise have the cue drawn over
    # a button or a list without a word, so say so instead.
    _, _, panel_width, panel_height = box(root)
    if x < 0 or y < 0 or x + size > panel_width or y + size > panel_height:
        raise ValueError(f"{source.name}: the R3 cue at {(x, y, size)} leaves "
                         f"the {panel_width}x{panel_height} panel")
    for control in controls:
        if (not control.exists("CONTROLTYPE")
                or control.get_int32("CONTROLTYPE") not in R3_CUE_BLOCKING_TYPES):
            continue
        left, top, width, height = box(control)
        if x < left + width and left < x + size and y < top + height and top < y + size:
            raise ValueError(f"{source.name}: the R3 cue at {(x, y, size)} "
                             f"covers {control.get_string('TAG')}")

    template = next(
        (control for control in controls
         if control.exists("CONTROLTYPE") and control.get_int32("CONTROLTYPE") == 4),
        None)
    if template is None:
        raise ValueError(f"{source.name} has no label to clone")

    cue = GFFStruct(template.struct_id)
    cue._fields = copy.deepcopy(template._fields)
    cue.set_string("TAG", R3_CUE_TAG)

    # The array the panel files controls into is indexed BY ID, and the binder
    # grows it when an id lands past the end, so one past the highest is free.
    ids = [control.get_int32("ID") for control in controls if control.exists("ID")]
    cue.set_int32("ID", max(ids) + 1)

    extent = cue.get_struct("EXTENT")
    extent.set_int32("LEFT", x)
    extent.set_int32("TOP", y)
    extent.set_int32("WIDTH", size)
    extent.set_int32("HEIGHT", size)
    cue.set_struct("EXTENT", extent)

    border = cue.get_struct("BORDER")
    border.set_resref("FILL", R3_CUE_FILL)
    # No frame of any kind: the glyph is the whole control.
    for field in ("CORNER", "EDGE"):
        if border.exists(field):
            border.set_resref(field, "")
    if border.exists("DIMENSION"):
        border.set_int32("DIMENSION", 0)
    cue.set_struct("BORDER", border)

    # The template's caption would otherwise be inherited wholesale.
    if cue.exists("TEXT"):
        text = cue.get_struct("TEXT")
        if text.exists("TEXT"):
            text.set_string("TEXT", "")
        if text.exists("STRREF"):
            text.set_uint32("STRREF", 0xFFFFFFFF)
        cue.set_struct("TEXT", text)

    controls.append(cue)
    # Every getter in this pykotor hands back a copy, the control list included,
    # so the list has to be written back or the file is unchanged on disk.
    root.set_list("CONTROLS", controls)
    write_gff(gff, destination)
    return True


def set_map_control_extent(source: Path, destination: Path, extent: dict) -> None:
    """Rewrite LBL_Map's EXTENT in a map.gui, leaving every other control alone."""
    gff = read_gff(source)
    for control in gff.root.get_list("CONTROLS"):
        if control.get_string("TAG") == "LBL_Map":
            # get_struct returns a copy in this pykotor version -- editing it
            # in place is silently discarded, so the result must be set back.
            target = control.get_struct("EXTENT")
            target.set_int32("LEFT", extent["left"])
            target.set_int32("TOP", extent["top"])
            target.set_int32("WIDTH", extent["width"])
            target.set_int32("HEIGHT", extent["height"])
            control.set_struct("EXTENT", target)
            break
    else:
        raise ValueError(f"LBL_Map was not found in {source}")
    write_gff(gff, destination)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("geometry", type=Path)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("gold_override", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("texture_pack", type=Path,
                        help="TexturePacks/swpc_tex_gui.erf, source of the stock font metrics")
    parser.add_argument("--bundled-override", type=Path, nargs="*", default=[],
                        help="Third-party Override mods bundled with their authors' "
                             "permission. Every *.tga beneath each directory goes into "
                             "override-common.zip. See THIRD_PARTY_NOTICES.md; omit to "
                             "ship without them.")
    parser.add_argument("--shared-assets", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets" / "override-common",
                        help="resolution-independent files copied straight into "
                             "override-common.zip (currently tutorial.2da)")
    parser.add_argument("hd_fonts", type=Path,
                        help="Pre-rendered HD font atlases (assets/hd-fonts)")
    parser.add_argument("--font-scale-sets", type=Path,
                        help="directory of per-scale atlas sets from "
                             "tools/build_font_scale_sets.py. A resolution whose "
                             "scale has a set there ships that set instead of the "
                             "shared 3.0 bake, which makes texturewidth the "
                             "atlas's real width and stops the engine resampling "
                             "the text (issue #16)")
    args = parser.parse_args()

    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    geometry_data = json.loads(args.geometry.read_text(encoding="utf-8"))["resolutions"]
    geometry = {item["resolution"]: item for item in geometry_data}
    requested = [resolution for values in GROUPS.values() for resolution in values]
    if len(requested) != 48 or len(set(requested)) != 48:
        raise ValueError("The requested resolution list must contain 48 unique entries")
    missing = sorted(set(requested) - set(geometry))
    if missing:
        raise ValueError(f"Geometry is missing for: {', '.join(missing)}")

    # 239, not 240: `lbl_equip - Copy.tga` was a stray duplicate of lbl_equip.tga
    # that no GUI referenced and nothing in the tree named. It shipped 15.7 MB of
    # dead weight to every install and was counted here as though it were ours.
    # This assertion caught its removal, which is what it is for.
    tga_files = list(args.gold_override.glob("*.tga"))
    if len(tga_files) != 239:
        raise ValueError(f"Expected 239 shared TGA assets, found {len(tga_files)}")
    # lbl_mileftbot.tga (the top-right button-row background art) is generated
    # per resolution below and shipped in each resolution's GUI archive instead
    # of here: its 8 pre-drawn boxes have to match that resolution's own button
    # width/pitch relative to LBL_MENUBG's span, which differs per resolution.
    # It must appear in exactly one archive -- OverrideOperations.Install rejects
    # the same relative path carrying different content across the two archives.
    # The hex icon frames behind list-row item icons are a TILED fill sized to the
    # row's icon box. That box is now scaled per resolution (RowSizeGroups in
    # KmrpPatcher.cs), so 56px art tiles 2x2 at 1440p and draws four
    # borders per row -- seen in game. They therefore ship per resolution, scaled
    # to match, and must NOT go in the shared archive.
    frame_tga_names = {f"{name}.tga" for name in FRAME_RESREFS}
    common_tga_files = [path for path in tga_files
                        if path.name.lower() != MENUBG_TEXTURE_NAME
                        and path.name.lower() not in frame_tga_names]
    menubg_count = sum(1 for path in tga_files if path.name.lower() == MENUBG_TEXTURE_NAME)
    if menubg_count != 1:
        raise ValueError(f"Expected exactly one {MENUBG_TEXTURE_NAME} among the shared TGA assets, "
                         f"found {menubg_count}")
    excluded_frames = sorted(path.name.lower() for path in tga_files
                             if path.name.lower() in frame_tga_names)
    if len(common_tga_files) != len(tga_files) - 1 - len(excluded_frames):
        raise ValueError("Shared TGA exclusion did not remove the expected files")
    print(f"Shared TGAs: {len(common_tga_files)} "
          f"(per-resolution instead: {MENUBG_TEXTURE_NAME}, {', '.join(excluded_frames)})")
    # The HD font atlases are byte-identical at every resolution -- only their TXI
    # metrics differ -- so they ship once here rather than being duplicated into all
    # 48 per-resolution archives.
    hd_font_atlases = sorted(args.hd_fonts.glob("*.tga"))
    if not hd_font_atlases:
        raise ValueError(f"No HD font atlases found in {args.hd_fonts}")
    hd_font_stems = {path.stem.lower() for path in hd_font_atlases}

    # A set baked at the resolution's own scale, where one exists. Those atlases
    # travel in the per-resolution archive, because they differ per resolution;
    # the shared 3.0 bake above stays for any scale that has no set.
    def scale_set_for(height: int):
        if not args.font_scale_sets:
            return None
        candidate = args.font_scale_sets / f"{font_scale_for(height):.6f}"
        return candidate if (candidate / "dialogfont16x16.tga").is_file() else None


    with tempfile.TemporaryDirectory(prefix="kotor-stock-fonts-") as stock_name:
        # Stock artwork for every font we are NOT replacing. A scaled `.txi` alone
        # does NOT take effect: with the artwork left inside the packed `.tpc` the
        # engine keeps that file's embedded metrics and the text never changes size.
        # Shipping the unmodified atlas beside the scaled `.txi` is what makes the
        # override win, so these 17 keep the authentic KOTOR typeface and still
        # scale. The artwork is resolution-independent, so it ships once here.
        stock_fonts = export_fonts(args.texture_pack, Path(stock_name), 1.0, textures=True)
        stock_atlases = [path for path in stock_fonts
                         if path.suffix.lower() == ".tga" and path.stem.lower() not in hd_font_stems]
        # Resolution-independent data files. tutorial.2da is the stock table with
        # its `icon` column repointed at the popup's private tut_* copies (see
        # tools/export_tutorial_icons.py); it is committed rather than generated
        # because building it needs to read the game's BIFs, which this build
        # does not have a path to.
        shared_data = sorted(args.shared_assets.glob("*")) if args.shared_assets.is_dir() else []
        if not shared_data:
            raise ValueError(f"No shared data files found in {args.shared_assets}")
        print(f"Shared data: {', '.join(path.name for path in shared_data)}")

        # Third-party Override mods, bundled with permission. Separate inputs rather
        # than dropped into the gold override, so the 240-asset assertion above keeps
        # meaning "our own shared art" and each mod's provenance stays legible.
        #
        # These are not optional at install time: they are art, they replace nothing of
        # ours, and OverrideOperations backs up whatever they displace, so a restore
        # puts the player's own files back.
        bundled = []
        icon_staging = tempfile.mkdtemp(prefix="kmrp-icons-")
        seen = {path.name.lower(): "KMRP shared art" for path in common_tga_files}
        for source in args.bundled_override:
            if not source.is_dir():
                raise ValueError(f"Bundled Override mod not found: {source}")
            files = sorted(source.rglob("*.tga"))
            if not files:
                raise ValueError(f"No .tga files under {source}")
            for path in files:
                key = path.name.lower()
                # OverrideOperations.Install refuses the same relative path carrying
                # different content across archives, and one mod silently shadowing
                # another would be worse than a build failure.
                if key in seen:
                    raise ValueError(f"{path.name} appears in both {seen[key]} "
                                     f"and {source.name}")
                seen[key] = source.name
            files = compress_bundled_icons(files, Path(icon_staging))
            bundled.extend(files)
            # A mod whose files sit in its own Override/ subfolder would otherwise
            # report as "Override", which names nothing.
            label = (source.parent.name if source.name.lower() == "override"
                     else source.name)
            print(f"Bundled Override: {len(files):4} files from {label}")

        # The full-screen backgrounds are OUR shared art, not a bundled mod, so
        # they are compressed here rather than alongside the bundled icons.
        common_tga_files = compress_menu_backgrounds(common_tga_files,
                                                     Path(icon_staging))

        # The R3 party-switch cue's glyph. Shared rather than per-resolution
        # because the control it fills is square at every resolution, so the art
        # needs no aspect pre-compensation and one texture is correct everywhere
        # -- unlike the caption badges, which are stretched across oblong buttons
        # and are built per resolution for exactly that reason.
        #
        # Every cue once per controller family. The .gui names the Xbox art; the
        # module rewrites the resref's fourth letter to the family it detects.
        for family in GLYPH_FAMILIES:
            cue_art = Path(icon_staging) / f"{family_resref(R3_CUE_FILL, family)}.tga"
            cue_art.write_bytes(build_square_glyph_tga("R3", family=family))
            common_tga_files = common_tga_files + [cue_art]

            # The same, for the two menu-strip cues.
            for _, fill, glyph in TAB_CUES:
                art = Path(icon_staging) / f"{family_resref(fill, family)}.tga"
                art.write_bytes(build_square_glyph_tga(glyph, family=family))
                common_tga_files = common_tga_files + [art]

            # The swap-tabs phrase, on a texture of its own shape rather than a
            # square, because its control is that shape too. Only Xbox has the
            # phrase as art; the others show their X-position button on it.
            swap_art = Path(icon_staging) / f"{family_resref(SWAP_CUE_FILL, family)}.tga"
            swap_art.write_bytes(build_square_glyph_tga(
                SWAP_CUE_GLYPH, 256, 256 // SWAP_CUE_ASPECT, family=family))
            common_tga_files = common_tga_files + [swap_art]

        # Controller Layout uses the same physical-position glyph sources as
        # the HUD prompts. Its art is resolution-independent; its geometry is
        # authored below from each resolution's final Controls screen.
        common_tga_files += build_controller_layout_art(Path(icon_staging))

        # Font atlases never ship here. They differ per resolution now, and the
        # installer refuses a build where override-common.zip and a resolution
        # archive disagree about the same file -- "Two interface archives
        # disagree about dialogfont10x10.tga", which is exactly what a shared
        # copy alongside the per-resolution ones produces.
        write_zip(args.output / "override-common.zip",
                  common_tga_files + stock_atlases + shared_data + bundled)
        shutil.rmtree(icon_staging, ignore_errors=True)

        # The names of the bundled art, so the installer can tell it apart from our
        # own files and defer to whatever is already in Override. K1CP, for one,
        # replaces two icons the HD pack also ships; art we merely bundle should
        # never win over a mod the player installed on purpose.
        (args.output / "bundled-override.txt").write_text(
            chr(10).join(path.name for path in bundled) + chr(10),
            encoding="utf-8")

    catalog_lines = ["# category\twidth\theight\tcanvasWidth\tcanvasHeight\toverlayWidth\tcenteringWidth\tcenteringHeight"]
    # Progress for the build script's bar: it turns "[done/total] label" lines
    # into bar updates. This is the long stage -- 48 resolutions of GUI and
    # texture work -- and without a heartbeat the build looks hung.
    total_resolutions = sum(len(items) for items in GROUPS.values())
    completed_resolutions = 0

    for category, resolutions in GROUPS.items():
        for resolution in resolutions:
            width, height = (int(value) for value in resolution.split("x"))
            item = geometry[resolution]
            catalog_lines.append("\t".join(str(value) for value in (
                category,
                width,
                height,
                item["map_canvas"]["width"],
                item["map_canvas"]["height"],
                item["marker_overlay"]["width"],
                item["centering_domain"]["width"],
                item["centering_domain"]["height"],
            )))

            if resolution == "3440x1440":
                gui_source = args.gold_override
            else:
                gui_source = args.upstream / ASPECT_FOLDERS[category] / f"gui.{resolution}"
            gui_files = list(gui_source.glob("*.gui"))
            if len(gui_files) < 81:
                raise ValueError(f"Expected at least 81 GUI files for {resolution}, found {len(gui_files)}")
            with tempfile.TemporaryDirectory(prefix=f"kotor-gui-{resolution}-") as temp_name:
                temp_dir = Path(temp_name)
                packaged_files: list[Path] = []
                transferred: list[str] = []
                for gui_file in gui_files:
                    name = gui_file.name.lower()
                    patched = temp_dir / gui_file.name
                    if name == "confirm.gui":
                        # The shared message popup, sized for THIS resolution's
                        # font scale. Handled ahead of the 3440x1440 passthrough
                        # below because it applies at every resolution including
                        # that one: the layout is absolute, so running it over
                        # the already-tuned gold copy reproduces it exactly.
                        apply_popup_layout(gui_file, patched, font_scale_for(height))
                        packaged_files.append(patched)
                        continue
                    if name == "map.gui":
                        # LBL_Map must equal the marker overlay, which is how
                        # vanilla (440x256 control over a 512x256 canvas) crops
                        # the map atlas's 72/512 of surplus columns. Upstream
                        # ships LBL_Map at width*440/640, which is the overlay
                        # for hires_patcher's geometry but not for ours -- left
                        # alone it is wider than our canvas, crops nothing, and
                        # the surplus shows as an unfogged strip down the right
                        # of the map. See reverse-engineering/area-map-surface.md.
                        # Ahead of the 3440x1440 passthrough because it applies
                        # at every resolution, that one included.
                        set_map_control_extent(gui_file, patched,
                                               item["map_control_target"])
                        packaged_files.append(patched)
                        continue
                    if resolution == "3440x1440":
                        packaged_files.append(gui_file)
                        continue

                    if name == "mipc210x7.gui":
                        # This is the ONE mipc variant actually hand-corrected at
                        # 3440x1440 (assets/override-3440x1440/mipc210x7.gui) --
                        # transfer that specific correction ratio onto this
                        # resolution's own stock mipc210x7.gui.
                        intermediate = temp_dir / f"gold-{gui_file.name}"
                        transfer_geometry(
                            args.upstream / "21-by-9" / "gui.3440x1440" / "mipc210x7.gui",
                            args.gold_override / "mipc210x7.gui",
                            gui_file,
                            intermediate,
                        )
                        patch_gui(intermediate, patched, height)
                        fix_menubg_file(patched, patched)
                        packaged_files.append(patched)
                    elif name.startswith("mipc"):
                        # Every OTHER mipc*.gui bucket has correct, non-overlapping
                        # stock geometry on its own (verified: e.g. mipc28x6.gui at
                        # 1920x1080 has no overlap in its untouched upstream form).
                        # Previously ALL mipc* files were run through the
                        # mipc210x7-derived ratio above, which was tuned for a
                        # completely different aspect ratio and shifted controls
                        # (LBL_JOURNAL, LBL_CMBTMSGBG, etc.) into the minimap's
                        # footprint. Only apply the height-based minimap-frame
                        # scaling (patch_gui), not the mismatched ratio transfer.
                        patch_gui(gui_file, patched, height)
                        # Give the bottom-left party cluster and bottom-right
                        # action buttons the gold build's proportions (scaled by
                        # screen height, anchored to their corners) instead of
                        # upstream's chunkier ones.
                        apply_proportions(
                            args.gold_override / "mipc210x7.gui", patched, patched, width, height
                        )
                        # LBL_MENUBG (the top-right button row's background) ships
                        # a few pixels too short to contain its 8 buttons in every
                        # upstream mipc*.gui variant at every resolution (a vanilla
                        # authoring imprecision, not resolution-specific) -- resize
                        # it to the buttons' own bounding box + a small margin.
                        fix_menubg_file(patched, patched)
                        packaged_files.append(patched)
                    elif name not in GOLD_GEOMETRY_EXCLUDED and (
                            args.gold_override / gui_file.name).is_file() and (
                            args.upstream / "21-by-9" / "gui.3440x1440" / gui_file.name).is_file():
                        try:
                            transfer_geometry(
                                args.upstream / "21-by-9" / "gui.3440x1440" / gui_file.name,
                                args.gold_override / gui_file.name,
                                gui_file,
                                patched,
                            )
                            packaged_files.append(patched)
                            transferred.append(name)
                        except ValueError:
                            # transfer_geometry raises when the reference pair has no
                            # changed extents -- that file was never hand-tuned, so
                            # upstream's own layout is what should ship.
                            packaged_files.append(gui_file)
                    else:
                        packaged_files.append(gui_file)

                # Whichever branch produced them, every .gui gets its description
                # panes' scrollbar gutter scaled for this resolution. `PADDING` is
                # a horizontal inset the engine subtracts from the wrap width;
                # vanilla left it at 0 on six description boxes and never scaled it
                # on the ones it did set, so enlarged text runs right up under the
                # scrollbar. Confirmed in game -- see tools/scale_listbox_padding.py.
                gutter_dir = temp_dir / "gutter"
                gutter_dir.mkdir(exist_ok=True)
                for index, path in enumerate(packaged_files):
                    if path.suffix.lower() != ".gui":
                        continue
                    gutter_file = gutter_dir / path.name
                    # DISABLED 2026-09-06 -- see fix_feedback_list_prototypes.py.
                    # Rewriting PROTOITEM extents to the parent's content area
                    # broke the Character Scripts screen in play, and the
                    # play-tested 3440x1440 gold files leave those extents at
                    # their vanilla values (scriptselect LST_AIState 71,84,241;
                    # optfeedback LB_OPTIONS 76,90,240). Gold is the authority
                    # here, and it disagrees with the repair. Issue #12's
                    # 3840x2160 report needs a different diagnosis.
                    #
                    # if path.name.lower() == "optfeedback.gui":
                    #     fix_feedback_prototypes(path, gutter_file)
                    #     path = gutter_file
                    # elif path.name.lower() == "scriptselect.gui":
                    #     fix_scriptselect_prototypes(path, gutter_file)
                    #     path = gutter_file
                    scale_listbox_padding(path, gutter_file, font_scale_for(height),
                                          DESCRIPTION_LISTBOXES)
                    # Selection lists, at their own smaller scale.
                    scale_listbox_padding(gutter_file, gutter_file,
                                          font_scale_for(height), LIST_LISTBOXES,
                                          unit_gutter=LIST_GUTTER_AT_UNIT_SCALE)
                    # A third, smaller tier for the message logs and text-only
                    # lists (BASELINE_GUTTER_AT_UNIT_SCALE, BASELINE_EXCLUDED in
                    # scale_listbox_padding.py) is deliberately NOT applied. It
                    # was built, shipped once and rolled back: listboxes are 81
                    # of the game's 640 text-bearing controls, so padding them
                    # alone reads as partial rather than uniform. Wire it in only
                    # as part of a pass that also covers labels and buttons --
                    # see reverse-engineering/text-padding.md.
                    # Last, so a hand-set gutter wins over the tiers above.
                    for tags, unit in HAND_TUNED_GUTTERS.get(path.name.lower(), ()):
                        scale_listbox_padding(gutter_file, gutter_file,
                                              font_scale_for(height), tags,
                                              unit_gutter=unit, force=True)
                    # Script Selection's rows, centred in the box its background
                    # art draws -- computed, not tuned, because that box is at a
                    # fixed fraction of the screen width while the list is not.
                    if path.name.lower() == "scriptselect.gui":
                        centre_rows_in_frame(gutter_file, gutter_file, width,
                                             "LST_AIState", SCRIPTSELECT_FRAME)
                    packaged_files[index] = gutter_file

                # The R3 party-switch cue, on the four screens that switch.
                # Placed from each resolution's own portrait extents, so there is
                # no table of coordinates to keep in step with the GUI packs.
                #
                # This only puts the control in the file. A panel builds the
                # controls it knows by name and nothing else, so the module binds
                # this one at runtime; without that it is never constructed and
                # never drawn. See reverse-engineering/custom-gui-controls.md.
                cue_dir = temp_dir / "cue"
                cue_dir.mkdir(exist_ok=True)
                cued = 0
                for index, path in enumerate(packaged_files):
                    if path.name.lower() not in R3_CUE_SCREENS:
                        continue
                    cue_file = cue_dir / path.name
                    if add_party_switch_cue(path, cue_file):
                        packaged_files[index] = cue_file
                        cued += 1
                if cued != len(R3_CUE_SCREENS):
                    raise ValueError(
                        f"{resolution}: the R3 cue reached {cued} of "
                        f"{len(R3_CUE_SCREENS)} party screens")

                # X, beside the Skills / Powers / Feats sub-tabs.
                swap_dir = temp_dir / "cue-swap"
                swap_dir.mkdir(exist_ok=True)
                swapped = False
                for index, path in enumerate(packaged_files):
                    if path.name.lower() != SWAP_CUE_SCREEN:
                        continue
                    # Its own directory, keeping the NAME: later steps find
                    # these files by filename -- the badge generator looks up
                    # "abilities.gui" -- so a prefixed name silently removes
                    # the screen from their view. It failed the build, loudly,
                    # which is the only reason this was cheap to find.
                    cue_file = swap_dir / path.name
                    if add_subtab_swap_cue(path, cue_file):
                        packaged_files[index] = cue_file
                        swapped = True
                if not swapped:
                    raise ValueError(
                        f"{resolution}: the sub-tab swap cue was not placed")

                # LT and RT, either side of the menu tab strip in top.gui.
                tabbed = 0
                for index, path in enumerate(packaged_files):
                    if path.name.lower() != TAB_CUE_SCREEN:
                        continue
                    cue_file = cue_dir / path.name
                    tabbed = add_tab_strip_cues(path, cue_file)
                    if tabbed:
                        packaged_files[index] = cue_file
                if tabbed != len(TAB_CUES):
                    raise ValueError(
                        f"{resolution}: the tab-strip cues reached {tabbed} of "
                        f"{len(TAB_CUES)}")

                # Add one entry to Settings / Controls and author the dedicated
                # layout screen from that resolution's final KOTOR geometry.
                # This must happen after every upstream and KMRP GUI transform,
                # so the new screen inherits the exact panel dimensions and
                # font metrics the game will load.
                layout_dir = temp_dir / "controller-layout"
                layout_dir.mkdir(exist_ok=True)
                # The entry sits on the Gameplay screen, under Keymapping.
                # Options does not list Mouse, so Mouse is itself two screens in.
                controls_index = next(
                    (i for i, path in enumerate(packaged_files)
                     if path.name.lower() == "optgameplay.gui"), None)
                if controls_index is None:
                    raise ValueError(f"{resolution}: optgameplay.gui is missing")
                controls_gui = layout_dir / "optgameplay.gui"
                add_controller_layout_entry(
                    packaged_files[controls_index], controls_gui)
                packaged_files[controls_index] = controls_gui

                # The travelling A beside a confirmation box's focused button.
                confirm_index = next(
                    (i for i, path in enumerate(packaged_files)
                     if path.name.lower() == "confirm.gui"), None)
                if confirm_index is None:
                    raise ValueError(f"{resolution}: confirm.gui is missing")
                confirm_gui = layout_dir / "confirm.gui"
                add_confirm_badge(packaged_files[confirm_index], confirm_gui,
                                  controls_gui)
                packaged_files[confirm_index] = confirm_gui

                # Generate this resolution's button-row background art from the
                # mipc*.gui file the engine will actually load at this
                # resolution. The in-executable variant selector compares the
                # live screen width against a single hardcoded 3440, so only
                # 3440x1440 loads mipc210x7.gui; every other resolution falls
                # through to vanilla's default, mipc28x6.gui. Deriving the
                # texture from that exact file keeps the 8 drawn boxes aligned
                # with the 8 real buttons at every resolution.
                active_mipc = "mipc210x7.gui" if resolution == "3440x1440" else "mipc28x6.gui"
                source_mipc = next(
                    (path for path in packaged_files if path.name.lower() == active_mipc), None
                )
                if source_mipc is None:
                    raise ValueError(f"{resolution}: {active_mipc} is missing from the packaged GUI files")
                menubg_texture = temp_dir / MENUBG_TEXTURE_NAME
                build_texture_for_gui(source_mipc, menubg_texture)
                packaged_files.append(menubg_texture)

                # Font sizing rides on the atlases' TXI metrics rather than on a
                # runtime patch, so each resolution ships its own metric files.
                # The atlases themselves are pre-rendered from a TrueType font by
                # tools/build_font_from_ttf.py and committed under assets/, because
                # that step needs Pillow and this build's interpreter has none.
                # Fonts with no HD replacement fall back to the stock artwork,
                # which still needs its metrics scaled to match.
                font_dir = temp_dir / "fonts"
                font_dir.mkdir(parents=True, exist_ok=True)
                scale = font_scale_for(height)
                replaced: set[str] = set()
                # Prefer a set baked at this resolution's own scale. Then the
                # factor below is exactly 1.0, `texturewidth` stays the atlas's
                # real width, and one texel lands on one pixel -- no resampling,
                # which is what made the text ragged at 1080p and 1440p. Without
                # a set, fall back to the shared 3.0 bake and its rescale.
                scale_set = scale_set_for(height)
                source_atlases = (sorted(scale_set.glob("*.tga")) if scale_set
                                  else hd_font_atlases)
                bake_scale = scale if scale_set else HD_FONT_BAKE_SCALE
                for atlas in source_atlases:
                    # Always in this archive, never in override-common.zip: a
                    # resolution with no set of its own still needs its copy of
                    # the shared bake here, or the two archives disagree.
                    packaged_files.append(atlas)
                    metrics = atlas.with_suffix(".txi")
                    scaled = font_dir / metrics.name
                    # These metrics already carry the bake scale, so undo it
                    # before applying this resolution's own scale -- otherwise the
                    # baked-in enlargement would be multiplied a second time.
                    scaled.write_bytes(
                        apply_letter_spacing(
                            scale_txi(
                                metrics.read_text(encoding="ascii"),
                                scale / bake_scale,
                            ),
                            letter_spacing_for(scale),
                        ).encode("ascii")
                    )
                    packaged_files.append(scaled)
                    replaced.add(atlas.stem.lower())
                # Into a SEPARATE directory: export_font_txis writes a file for every
                # one of the 18 resrefs, so pointing it at font_dir would silently
                # overwrite the HD metrics written above -- shipping stock coordinates
                # against the HD atlas, whose glyphs sit at completely different
                # positions, which renders as unreadable garbage.
                stock_dir = font_dir / "stock"
                for path in export_font_txis(args.texture_pack, stock_dir, scale):
                    if path.stem.lower() not in replaced:
                        # The wrap margin is not specific to our own atlases: the
                        # engine truncates every glyph advance, so an enlarged stock
                        # font clips its last word just the same.
                        path.write_bytes(
                            apply_letter_spacing(
                                path.read_text(encoding="ascii"),
                                letter_spacing_for(scale),
                            ).encode("ascii")
                        )
                        packaged_files.append(path)

                root_extent = read_gff(controls_gui).root.get_struct("EXTENT")
                layout_gui = layout_dir / "kmrplayout.gui"
                # The Controller Layout screen, built here rather than beside
                # its entry above because its caption boxes are sized from
                # this resolution's own font, which is only packaged now.
                caption_txi = next(
                    (path for path in packaged_files
                     if path.name.lower() == "dialogfont16x16.txi"), None)
                if caption_txi is None:
                    raise ValueError(f"{resolution}: dialogfont16x16.txi is missing")
                build_controller_layout_gui(
                    controls_gui, layout_gui,
                    root_extent.get_int32("WIDTH"),
                    root_extent.get_int32("HEIGHT"),
                    caption_txi)
                packaged_files.append(layout_gui)

                # Hex icon frames at this resolution's row-icon size, so the
                # tiled fill stays exactly one tile (see scale_row_icon_frames).
                packaged_files.extend(
                    export_frames(args.texture_pack, temp_dir / "frames",
                                  font_scale_for(height)))

                # The message popup's icons, at this resolution's icon rect (the
                # rect is scaled by ResolutionPatch's PopupSizeGroups). The engine
                # draws GUI textures one texel per pixel, so a mismatch TILES or
                # CROPS -- hence per resolution, not in the shared archive.
                packaged_files.extend(
                    export_tutorial_icons(args.texture_pack, temp_dir / "tuticons",
                                          font_scale_for(height)))

                # Original KMRP artwork for the optional controller runtime. The
                # PC renderer stretches BORDER.FILL to each button, so these are
                # generated from this resolution's final button extents. They are
                # inert unless the runtime selects them after gamepad input.
                packaged_files.extend(build_prompt_textures(
                    packaged_files, temp_dir / "controller-prompts"))


                if transferred:
                    print(f"  {resolution}: gold geometry transferred to "
                          f"{len(transferred)} GUI files")
                write_zip(args.output / f"gui-{resolution}.zip", packaged_files)
                completed_resolutions += 1
                print(f"[{completed_resolutions}/{total_resolutions}] {resolution}", flush=True)

    (args.output / "resolutions.tsv").write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")
    shutil.copy2(args.upstream / "LICENSE.txt", args.output / "GPL-3.0-KOTOR-High-Resolution-Menus.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
