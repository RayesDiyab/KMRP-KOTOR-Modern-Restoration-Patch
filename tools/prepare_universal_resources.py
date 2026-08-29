#!/usr/bin/env python3
"""Build compact common-art and per-resolution GUI resources."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from scale_hud_minimap import patch_gui
from transfer_gold_gui_geometry import transfer_geometry


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
    write_zip(args.output / "override-common.zip", tga_files)

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
                    if name.startswith("mipc"):
                        intermediate = temp_dir / f"gold-{gui_file.name}"
                        transfer_geometry(
                            args.upstream / "21-by-9" / "gui.3440x1440" / "mipc210x7.gui",
                            args.gold_override / "mipc210x7.gui",
                            gui_file,
                            intermediate,
                        )
                        patch_gui(intermediate, patched, height)
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
                write_zip(args.output / f"gui-{resolution}.zip", packaged_files)

    (args.output / "resolutions.tsv").write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")
    shutil.copy2(args.upstream / "LICENSE.txt", args.output / "GPL-3.0-KOTOR-High-Resolution-Menus.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
