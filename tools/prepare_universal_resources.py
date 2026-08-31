#!/usr/bin/env python3
"""Build compact common-art and per-resolution GUI resources."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from apply_gold_hud_proportions import apply_proportions
from build_menubg_texture import build_texture_for_gui
from build_scaled_fonts import export_font_txis, export_fonts, scale_txi
from fix_hud_menubg import fix_menubg_file
from scale_hud_minimap import patch_gui
from transfer_gold_gui_geometry import transfer_geometry
from scale_listbox_padding import LIST_GUTTER_AT_UNIT_SCALE, scale_listbox_padding
from scale_row_icon_frames import FRAME_RESREFS, export_frames


MENUBG_TEXTURE_NAME = "lbl_mileftbot.tga"

# Font sizing is applied to the atlases' TXI metrics rather than at runtime (see
# ResolutionPatch in KotorUniversalPatcher.cs). Must stay in step with that class's
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

GOLD_GEOMETRY_TEMPLATES = {
    "abchrgen.gui", "barkbubble.gui", "computer.gui", "confirm.gui",
    "container.gui", "custpnl.gui", "equip.gui", "ftchrgen.gui",
    "galaxymap.gui", "inventory.gui", "journal.gui", "loadscreen.gui",
    "map.gui", "messages.gui", "pause.gui", "questitem.gui", "saveload.gui",
    "tooltip6x4.gui",
}


def write_zip(output: Path, files: list[Path]) -> None:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:
        for path in sorted(files, key=lambda item: item.name.lower()):
            archive.write(path, path.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("geometry", type=Path)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("gold_override", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("texture_pack", type=Path,
                        help="TexturePacks/swpc_tex_gui.erf, source of the stock font metrics")
    parser.add_argument("hd_fonts", type=Path,
                        help="Pre-rendered HD font atlases (assets/hd-fonts)")
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

    tga_files = list(args.gold_override.glob("*.tga"))
    if len(tga_files) != 240:
        raise ValueError(f"Expected 240 shared TGA assets, found {len(tga_files)}")
    # lbl_mileftbot.tga (the top-right button-row background art) is generated
    # per resolution below and shipped in each resolution's GUI archive instead
    # of here: its 8 pre-drawn boxes have to match that resolution's own button
    # width/pitch relative to LBL_MENUBG's span, which differs per resolution.
    # It must appear in exactly one archive -- OverrideOperations.Install rejects
    # the same relative path carrying different content across the two archives.
    # The hex icon frames behind list-row item icons are a TILED fill sized to the
    # row's icon box. That box is now scaled per resolution (RowSizeGroups in
    # KotorUniversalPatcher.cs), so 56px art tiles 2x2 at 1440p and draws four
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
        write_zip(args.output / "override-common.zip",
                  common_tga_files + hd_font_atlases + stock_atlases)

    catalog_lines = ["# category\twidth\theight\tcanvasWidth\tcanvasHeight\toverlayWidth\tcenteringWidth\tcenteringHeight"]
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
                for gui_file in gui_files:
                    if resolution == "3440x1440":
                        packaged_files.append(gui_file)
                        continue

                    name = gui_file.name.lower()
                    patched = temp_dir / gui_file.name
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
                    elif name in GOLD_GEOMETRY_TEMPLATES:
                        transfer_geometry(
                            args.upstream / "21-by-9" / "gui.3440x1440" / gui_file.name,
                            args.gold_override / gui_file.name,
                            gui_file,
                            patched,
                        )
                        packaged_files.append(patched)
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
                    scale_listbox_padding(path, gutter_file, font_scale_for(height),
                                          DESCRIPTION_LISTBOXES)
                    # Selection lists, at their own smaller scale.
                    scale_listbox_padding(gutter_file, gutter_file,
                                          font_scale_for(height), LIST_LISTBOXES,
                                          unit_gutter=LIST_GUTTER_AT_UNIT_SCALE)
                    packaged_files[index] = gutter_file

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
                for atlas in hd_font_atlases:
                    metrics = atlas.with_suffix(".txi")
                    scaled = font_dir / metrics.name
                    # These metrics already carry HD_FONT_BAKE_SCALE, so undo it
                    # before applying this resolution's own scale -- otherwise the
                    # baked-in enlargement would be multiplied a second time.
                    scaled.write_bytes(
                        apply_letter_spacing(
                            scale_txi(
                                metrics.read_text(encoding="ascii"),
                                scale / HD_FONT_BAKE_SCALE,
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

                # Hex icon frames at this resolution's row-icon size, so the
                # tiled fill stays exactly one tile (see scale_row_icon_frames).
                packaged_files.extend(
                    export_frames(args.texture_pack, temp_dir / "frames",
                                  font_scale_for(height)))


                write_zip(args.output / f"gui-{resolution}.zip", packaged_files)

    (args.output / "resolutions.tsv").write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")
    shutil.copy2(args.upstream / "LICENSE.txt", args.output / "GPL-3.0-KOTOR-High-Resolution-Menus.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
