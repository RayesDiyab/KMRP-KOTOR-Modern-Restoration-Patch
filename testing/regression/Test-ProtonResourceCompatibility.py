#!/usr/bin/env python3
"""Audit packaged resources for Linux/Proton-sensitive filename failures.

Run this after ``build_kmrp.ps1``. The test reads the final ZIP archives and
performs case-sensitive checks even on Windows, where the host filesystem would
otherwise hide case-only mistakes.
"""

from __future__ import annotations

import re
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from apply_gold_hud_proportions import walk_controls  # noqa: E402
from pykotor.resource.formats.gff import read_gff  # noqa: E402


EXPECTED_ARCHIVE_COUNT = 49   # 48 upstream + 2880x1620, derived since 2026-09-25
ARCHIVE_PATTERN = re.compile(r"gui-(\d+)x(\d+)\.zip$")
TARGET_TAG = "LBL_NAME"
TARGET_FONT = "dialogfont10x10"


def unsafe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not name
        or "\\" in name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
    )


def case_collisions(names: set[str]) -> list[list[str]]:
    folded: dict[str, list[str]] = {}
    for name in names:
        folded.setdefault(name.casefold(), []).append(name)
    return [sorted(values) for values in folded.values() if len(values) > 1]


def font_refs(gui_path: Path) -> set[str]:
    fonts: set[str] = set()
    gui = read_gff(gui_path)
    for control in walk_controls(gui):
        text = control.get_struct("TEXT")
        if text is None:
            continue
        font = str(text.get_resref("FONT"))
        if font:
            fonts.add(font)
    return fonts


def target_font(gui_path: Path) -> str | None:
    gui = read_gff(gui_path)
    for control in walk_controls(gui):
        if control.get_string("TAG") != TARGET_TAG:
            continue
        text = control.get_struct("TEXT")
        return None if text is None else str(text.get_resref("FONT"))
    return None


def main() -> int:
    archive_dir = ROOT / "build" / "kmrp" / "resources"
    common_path = archive_dir / "override-common.zip"
    archives = sorted(archive_dir.glob("gui-*.zip"))
    errors: list[str] = []

    if not common_path.is_file():
        print(f"FAIL: missing {common_path}")
        return 1
    if len(archives) != EXPECTED_ARCHIVE_COUNT:
        print(f"FAIL: found {len(archives)} GUI archives; expected {EXPECTED_ARCHIVE_COUNT}")
        return 1

    with zipfile.ZipFile(common_path) as common:
        common_names = set(common.namelist())
    for name in sorted(common_names):
        if unsafe_member(name):
            errors.append(f"override-common.zip: unsafe or non-portable member {name!r}")
    for collision in case_collisions(common_names):
        errors.append(f"override-common.zip: case-insensitive collision {collision}")

    checked_guis = 0
    checked_fonts: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="kmrp-proton-audit-") as temp_name:
        temp = Path(temp_name)
        for archive in archives:
            match = ARCHIVE_PATTERN.fullmatch(archive.name)
            if match is None:
                errors.append(f"unrecognized archive name: {archive.name}")
                continue
            resolution = "x".join(match.groups())
            active_hud = "mipc210x7.gui" if resolution == "3440x1440" else "mipc28x6.gui"
            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())
                for name in sorted(names):
                    if unsafe_member(name):
                        errors.append(f"{archive.name}: unsafe or non-portable member {name!r}")
                for collision in case_collisions(names):
                    errors.append(f"{archive.name}: case-insensitive collision {collision}")

                gui_names = sorted(name for name in names if name.endswith(".gui"))
                if active_hud not in names:
                    errors.append(f"{resolution}: active HUD {active_hud} is missing")
                    continue
                for gui_name in gui_names:
                    package.extract(gui_name, temp / resolution)

            available = common_names | names
            for gui_name in gui_names:
                gui_path = temp / resolution / gui_name
                checked_guis += 1
                for font in font_refs(gui_path):
                    checked_fonts.add(font)
                    for suffix in (".tga", ".txi"):
                        resource = font + suffix
                        if resource not in available:
                            folded = sorted(name for name in available if name.casefold() == resource.casefold())
                            detail = f"; case-only match {folded}" if folded else ""
                            errors.append(
                                f"{resolution} {gui_name}: FONT {font!r} lacks exact {resource!r}{detail}"
                            )

            hud_font = target_font(temp / resolution / active_hud)
            if hud_font != TARGET_FONT:
                errors.append(
                    f"{resolution} {active_hud} {TARGET_TAG}: FONT {hud_font!r}, "
                    f"expected {TARGET_FONT!r}"
                )

    if errors:
        print(f"FAIL: {len(errors)} Proton resource compatibility error(s)")
        for error in errors:
            print(f"  {error}")
        return 1
    print(
        f"PASS: {len(archives)} archives, {checked_guis} packaged GUIs and "
        f"{len(checked_fonts)} referenced fonts are case-exact and collision-free"
    )
    print(
        f"PASS: active HUD {TARGET_TAG} resolves {TARGET_FONT}.tga/.txi at all "
        f"{len(archives)} resolutions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
