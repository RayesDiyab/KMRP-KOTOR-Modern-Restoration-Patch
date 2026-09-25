#!/usr/bin/env python3
"""Collect a read-only KMRP/Proton installation report without game content."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import platform
from pathlib import Path


TRACKED_ROOT_FILES = (
    "swkotor.exe",
    "swkotor.ini",
    "KOTOR_UI_Override_Backup.manifest",
    "KMRP_DPI.manifest",
    "KMRP_DriverCompat.manifest",
    "KMRP_Controller.manifest",
    "dinput8.dll",
    "dinput8.ini",
    "kmrp-controller-runtime.asi",
    "kmrp-controller.module",
    "kmrp-sdl3.dll",
    "kmrp-sdl3-LICENSE.txt",
    "kmrp-kotor-patch-manager-LICENSE.txt",
    "patch_config.toml",
    "kmrp-controller.ini",
    "kmrp-rumble.log",
)
TRACKED_OVERRIDE_FILES = (
    "mipc28x6.gui",
    "mipc210x7.gui",
    "dialogfont10x10.tga",
    "dialogfont10x10.txi",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_record(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"present": False}
    return {"present": True, "size": path.stat().st_size, "sha256": sha256(path)}


def display_resolution(ini_path: Path) -> dict[str, str] | None:
    if not ini_path.is_file():
        return None
    parser = configparser.ConfigParser(strict=False)
    parser.optionxform = str
    try:
        parser.read(ini_path, encoding="utf-8-sig")
        section_name = next(
            name for name in ("Graphics Options", "Display Options") if parser.has_section(name)
        )
        section = parser[section_name]
        return {
            "section": section_name,
            "Width": section.get("Width", ""),
            "Height": section.get("Height", ""),
        }
    except (configparser.Error, KeyError, StopIteration, UnicodeError):
        return {"error": "swkotor.ini could not be parsed"}


def case_collisions(directory: Path) -> list[list[str]]:
    if not directory.is_dir():
        return []
    folded: dict[str, list[str]] = {}
    for child in directory.iterdir():
        folded.setdefault(child.name.casefold(), []).append(child.name)
    return [sorted(names) for names in folded.values() if len(names) > 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_directory", type=Path)
    parser.add_argument("--output", type=Path, help="Write JSON here instead of stdout")
    args = parser.parse_args()

    game = args.game_directory.expanduser().resolve()
    if not game.is_dir():
        parser.error(f"game directory does not exist: {game}")

    override = game / "Override"
    report = {
        "schema": "KMRP-PROTON-REPORT-1",
        "collector_platform": platform.platform(),
        "game_directory": str(game),
        "display_resolution": display_resolution(game / "swkotor.ini"),
        "root_files": {name: file_record(game / name) for name in TRACKED_ROOT_FILES},
        "override_files": {
            name: file_record(override / name) for name in TRACKED_OVERRIDE_FILES
        },
        "root_case_collisions": case_collisions(game),
        "override_case_collisions": case_collisions(override),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
