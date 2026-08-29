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
from build_scaled_fonts import export_font_txis, scale_txi
from fix_hud_menubg import fix_menubg_file
from scale_hud_minimap import patch_gui
from transfer_gold_gui_geometry import transfer_geometry


MENUBG_TEXTURE_NAME = "lbl_mileftbot.tga"

# Font sizing is applied to the atlases' TXI metrics rather than at runtime (see
# ResolutionPatch in KotorUniversalPatcher.cs). Must stay in step with that class's
# ScaleForHeight, which scales list-row heights by the same rule so rows always grow
# with the text: 1.25x at 1080p, 1.75x at 1440p, 2.75x at 2160p, clamped at 1.0.
FONT_HEIGHT_DIVISOR = 720.0
FONT_SCALE_OFFSET = 0.25


def font_scale_for(height: int) -> float:
    return max(1.0, height / FONT_HEIGHT_DIVISOR - FONT_SCALE_OFFSET)


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

GOLD_GEOMETRY_TEMPLATES = {
    "abchrgen.gui", "barkbubble.gui", "computer.gui", "confirm.gui",
    "container.gui", "custpnl.gui", "equip.gui", "ftchrgen.gui",
    "galaxymap.gui", "inventory.gui", "journal.gui", "loadscreen.gui",
    "map.gui", "messages.gui", "pause.gui", "saveload.gui", "tooltip6x4.gui",
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
    common_tga_files = [path for path in tga_files if path.name.lower() != MENUBG_TEXTURE_NAME]
    if len(common_tga_files) != len(tga_files) - 1:
        raise ValueError(f"Expected exactly one {MENUBG_TEXTURE_NAME} among the shared TGA assets")
    # The HD font atlases are byte-identical at every resolution -- only their TXI
    # metrics differ -- so they ship once here rather than being duplicated into all
    # 48 per-resolution archives.
    hd_font_atlases = sorted(args.hd_fonts.glob("*.tga"))
    if not hd_font_atlases:
        raise ValueError(f"No HD font atlases found in {args.hd_fonts}")
    write_zip(args.output / "override-common.zip", common_tga_files + hd_font_atlases)

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
                    scaled.write_bytes(
                        scale_txi(metrics.read_text(encoding="ascii"), scale).encode("ascii")
                    )
                    packaged_files.append(scaled)
                    replaced.add(atlas.stem.lower())
                for path in export_font_txis(args.texture_pack, font_dir, scale):
                    if path.stem.lower() not in replaced:
                        packaged_files.append(path)

                write_zip(args.output / f"gui-{resolution}.zip", packaged_files)

    (args.output / "resolutions.tsv").write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")
    shutil.copy2(args.upstream / "LICENSE.txt", args.output / "GPL-3.0-KOTOR-High-Resolution-Menus.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
