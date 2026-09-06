#!/usr/bin/env python3
"""Verify reported GUI geometry repairs and the active HUD at every resolution.

Run this after ``build_kmrp.ps1``.  The test reads the packaged GUI archives,
not intermediate files, so it catches both geometry regressions and packaging
mistakes.
"""

from __future__ import annotations

import re
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from apply_gold_hud_proportions import (  # noqa: E402
    TOP_LEFT_TRANSIENT_TAGS,
    gold_extents,
    placed_top_left,
    walk_controls,
)
from pykotor.resource.formats.gff import read_gff  # noqa: E402


EXPECTED_ARCHIVE_COUNT = 48
FEEDBACK_LISTS = ("LB_OPTIONS", "LB_DESC")
SCRIPTSELECT_LISTS = ("LST_AIState", "LB_DESC")
ARCHIVE_PATTERN = re.compile(r"gui-(\d+)x(\d+)\.zip$")


def extent_values(struct) -> tuple[int, int, int, int]:
    extent = struct.get_struct("EXTENT")
    if extent is None:
        raise AssertionError("control has no EXTENT")
    return tuple(extent.get_int32(field) for field in ("LEFT", "TOP", "WIDTH", "HEIGHT"))


def controls_by_tag(gui) -> dict[str, object]:
    return {control.get_string("TAG"): control for control in walk_controls(gui)}


UPSTREAM_GUI_ROOT = ROOT / "third_party" / "Included" / "kotor-high-resolution-menus-1.5"


def upstream_gui(resolution: str, name: str):
    """The untouched High Resolution Menus file for this resolution, or None."""
    matches = list(UPSTREAM_GUI_ROOT.glob(f"*/gui.{resolution}/{name}"))
    return matches[0] if matches else None


def check_list_prototypes(path: Path, resolution: str, screen: str,
                          tags: tuple[str, ...]) -> list[str]:
    """Assert the embedded row prototypes are left EXACTLY as upstream ships them.

    This assertion is inverted from its first version, which required the
    prototype to be rewritten to the parent's content area beside the scrollbar.
    That rewrite shipped, and the Character Scripts screen came back broken from
    play-testing on 2026-09-06.

    The play-tested 3440x1440 gold files settle it: they leave these extents at
    the vanilla values -- scriptselect `LST_AIState` (71, 84, 241) and optfeedback
    `LB_OPTIONS` (76, 90, 240) -- identical to upstream, while the parent listbox
    around them is fully scaled. So PROTOITEM LEFT/TOP/WIDTH are not the parent's
    coordinate space; upstream's own values put the prototype above and to the
    left of its parent, which no absolute interpretation can explain.

    Issue #12's 3840x2160 report is therefore still open and needs a different
    diagnosis. Whatever that turns out to be, it must not move these extents
    without evidence that beats a play-test.
    """
    errors: list[str] = []
    source = upstream_gui(resolution, path.name)
    if source is None:
        return [f"{resolution} {screen}: no upstream {path.name} to compare against"]
    packaged = controls_by_tag(read_gff(path))
    original = controls_by_tag(read_gff(source))
    for tag in tags:
        control = packaged.get(tag)
        reference = original.get(tag)
        if control is None or reference is None:
            errors.append(f"{resolution} {screen}: missing {tag}")
            continue
        proto = control.get_struct("PROTOITEM")
        ref_proto = reference.get_struct("PROTOITEM")
        if proto is None or ref_proto is None:
            errors.append(f"{resolution} {screen}: {tag} lacks PROTOITEM")
            continue
        actual = extent_values(proto)[:3]
        expected = extent_values(ref_proto)[:3]
        if actual != expected:
            errors.append(
                f"{resolution} {screen} {tag}: prototype {actual}, upstream ships "
                f"{expected}; these must not be rewritten (see this docstring)"
            )
    return errors


def check_confirmation(path: Path, resolution: str) -> list[str]:
    errors: list[str] = []
    gui = read_gff(path)
    _, _, panel_width, panel_height = extent_values(gui.root)
    for control in gui.root.get_list("CONTROLS") or []:
        tag = control.get_string("TAG")
        left, top, width, height = extent_values(control)
        if left < 0 or top < 0 or left + width > panel_width or top + height > panel_height:
            errors.append(
                f"{resolution} confirm {tag}: {(left, top, width, height)} "
                f"escapes panel {(panel_width, panel_height)}"
            )
    return errors


def check_hud(path: Path, resolution: str, height: int,
              gold: dict[str, tuple[int, int, int, int]]) -> list[str]:
    errors: list[str] = []
    controls = controls_by_tag(read_gff(path))
    scale = max(1.0, height / 720.0) / 2.0
    for tag in TOP_LEFT_TRANSIENT_TAGS:
        control = controls.get(tag)
        if control is None:
            errors.append(f"{resolution} HUD: missing {tag}")
            continue
        expected = placed_top_left(gold[tag], scale)
        actual = extent_values(control)
        if actual != expected:
            errors.append(f"{resolution} HUD {tag}: {actual}, expected {expected}")
    return errors


def main() -> int:
    archive_dir = ROOT / "build" / "kmrp" / "resources"
    archives = sorted(archive_dir.glob("gui-*.zip"))
    if len(archives) != EXPECTED_ARCHIVE_COUNT:
        print(f"FAIL: found {len(archives)} GUI archives; expected {EXPECTED_ARCHIVE_COUNT}")
        return 1

    gold = gold_extents(ROOT / "assets" / "override-3440x1440" / "mipc210x7.gui")
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="kmrp-gui-regression-") as temp_name:
        temp = Path(temp_name)
        for archive in archives:
            match = ARCHIVE_PATTERN.fullmatch(archive.name)
            if match is None:
                errors.append(f"unrecognized archive name: {archive.name}")
                continue
            width, height = (int(value) for value in match.groups())
            resolution = f"{width}x{height}"
            active_hud = "mipc210x7.gui" if resolution == "3440x1440" else "mipc28x6.gui"
            extract_dir = temp / resolution
            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())
                required = {"optfeedback.gui", "scriptselect.gui", "confirm.gui", active_hud}
                missing = required - names
                if missing:
                    errors.append(f"{resolution}: package is missing {sorted(missing)}")
                    continue
                package.extract("optfeedback.gui", extract_dir)
                package.extract("scriptselect.gui", extract_dir)
                package.extract("confirm.gui", extract_dir)
                package.extract(active_hud, extract_dir)
            errors.extend(check_list_prototypes(
                extract_dir / "optfeedback.gui", resolution, "optfeedback", FEEDBACK_LISTS
            ))
            errors.extend(check_list_prototypes(
                extract_dir / "scriptselect.gui", resolution, "scriptselect", SCRIPTSELECT_LISTS
            ))
            errors.extend(check_confirmation(extract_dir / "confirm.gui", resolution))
            errors.extend(check_hud(extract_dir / active_hud, resolution, height, gold))

    if errors:
        print(f"FAIL: {len(errors)} generated GUI geometry error(s)")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"PASS: Reported GUI repairs and active HUD geometry in {len(archives)} archives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
