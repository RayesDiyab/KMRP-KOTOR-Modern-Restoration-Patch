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

# Per-glyph letter spacing, in pixels, added by the engine on top of each
# glyph's own advance (`advance = (uvWidth * texturewidth + spacingR) * 100`).
#
# The shared atlas is rasterised once and bilinear-downscaled for every
# resolution below the top of the curve; that resampling, followed by the
# engine's alpha threshold, renders ink roughly 2% wider than the pure ratio.
# The extra width comes out of the gap between letters, and since it is a
# near-constant number of pixels it hurts small text proportionally most --
# measured, menu text at 1080p had a gap/ink ratio of 0.098 against 0.126 at
# 1440p, i.e. visibly cramped.
#
# The amount needed is MEASURED per font and per scale, not modelled: the
# baseline ratios are not monotonic in how hard the atlas is downscaled (menu
# text measures 0.114 at 720p, 0.098 at 1080p, 0.126 at 1440p, 0.120 at 2160p),
# because what actually varies is integer rounding of each glyph's advance at
# each specific pixel size. A smooth `f = scale / bake` curve chases that noise
# and overshoots badly at small sizes -- one measured a 720p menu at 0.198
# against a 0.120 target. `tools/measure_letter_spacing.py` solves for the
# correction that returns each font to its own ratio at the native baked size
# and writes `assets/letter-spacing.json`; in practice only the menu font at
# 1080p needs anything (0.35px), which is why a flat constant was visibly wrong
# at other resolutions.
#
# This is a pixel-space correction, so it must NOT be scaled with the
# resolution the way the other metrics are -- hence `spacingR` is overwritten
# after `scale_txi` rather than passed through it.
LETTER_SPACING_FILE = "letter-spacing.json"


def letter_spacing_for(table: dict, resref: str, scale: float) -> float:
    """Measured pixels of extra per-glyph spacing for this font at this scale."""
    return float(table.get(resref.lower(), {}).get(f"{scale:.4f}", 0.0))


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
    hd_font_stems = {path.stem.lower() for path in hd_font_atlases}

    # Measured per-font, per-scale letter spacing (see LETTER_SPACING_FILE).
    spacing_path = args.hd_fonts.parent / LETTER_SPACING_FILE
    if not spacing_path.exists():
        raise ValueError(
            f"{spacing_path} is missing -- regenerate it with "
            f"tools/measure_letter_spacing.py after re-baking the atlases")
    letter_spacing = {k.lower(): v for k, v in
                      json.loads(spacing_path.read_text(encoding="ascii")).items()}

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
                            letter_spacing_for(letter_spacing, atlas.stem, scale),
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
                        packaged_files.append(path)

                write_zip(args.output / f"gui-{resolution}.zip", packaged_files)

    (args.output / "resolutions.tsv").write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")
    shutil.copy2(args.upstream / "LICENSE.txt", args.output / "GPL-3.0-KOTOR-High-Resolution-Menus.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
