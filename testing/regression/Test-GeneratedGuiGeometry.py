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


def check_feedback_gutter(path: Path, resolution: str, height: int) -> list[str]:
    """The Feedback list keeps a gap between its left scrollbar and the circles.

    CSWGuiOptionsCheckbox::SetExtent (0x006DE000) draws each circle as a fixed
    25px square at its row's very left, and rows start where the scrollbar ends,
    so with vanilla's PADDING 0 the circles sat against the scrollbar. Since gold
    v12 PADDING is a horizontal gutter on the scrollbar side, and it comes from
    HAND_TUNED_GUTTERS in prepare_universal_resources.py -- the prototypes are
    left alone, which check_list_prototypes insists on.
    """
    from prepare_universal_resources import HAND_TUNED_GUTTERS, font_scale_for
    unit = dict((next(iter(tags)), value)
                for tags, value in HAND_TUNED_GUTTERS["optfeedback.gui"])["LB_OPTIONS"]
    expected = int(round(unit * font_scale_for(height)))
    control = controls_by_tag(read_gff(path)).get("LB_OPTIONS")
    if control is None:
        return [f"{resolution} optfeedback: missing LB_OPTIONS"]
    padding = control.acquire("PADDING", 0)
    if padding != expected or padding < 1:
        return [f"{resolution} optfeedback LB_OPTIONS: PADDING {padding}, expected "
                f"{expected} (the gap between the scrollbar and the circles)"]
    return []


def check_scriptselect_centred(path: Path, resolution: str, width: int) -> list[str]:
    """Script Selection's rows sit centred in the box its background art draws.

    The box is part of lbl_char_scr.tpc, stretched across the screen, so it is
    at fixed fractions of the screen width (SCRIPTSELECT_FRAME). With a left
    scrollbar the rows run from list.left + scrollbar + PADDING to list.left +
    list.width; vanilla's PADDING 2 put them 12px outside the frame on the left
    at 3440x1440. centre_rows_in_frame computes the PADDING per resolution.
    """
    from scale_listbox_padding import SCRIPTSELECT_FRAME
    control = controls_by_tag(read_gff(path)).get("LST_AIState")
    if control is None:
        return [f"{resolution} scriptselect: missing LST_AIState"]
    left, _, list_width, _ = extent_values(control)
    bar = extent_values(control.get_struct("SCROLLBAR"))[2]
    padding = control.acquire("PADDING", 0)
    frame_left, frame_right = (f * width for f in SCRIPTSELECT_FRAME)
    left_margin = left + bar + padding - frame_left
    right_margin = frame_right - (left + list_width)
    if left_margin < 0 or right_margin < 0 or abs(left_margin - right_margin) > 2:
        return [f"{resolution} scriptselect LST_AIState: rows {left_margin:.1f}px "
                f"inside the frame on the left, {right_margin:.1f}px on the right"]
    return []


def check_party_switch_cue(path: Path, resolution: str) -> list[str]:
    """The R3 cue is 90% of a portrait, between the portraits or right of them.

    Between them, centred, wherever the gap holds it with a tenth of it free
    either side; right of the second portrait, a third of a cue away, wherever
    it does not -- 4:3, 16:10 and 16:9. It never covers a button or a list, and
    is centred on the portraits vertically. Checked against the packaged
    portraits, so a GUI pack that moves them is caught. The cue filled the gap
    until 2026-09-24, which left it 5 px wide at 800x600.
    """
    from prepare_universal_resources import (R3_CUE_BLOCKING_TYPES, R3_CUE_GAP_MARGIN,
                                             R3_CUE_SCALE, R3_CUE_TAG)
    screen = path.stem
    gui = read_gff(path)
    controls = controls_by_tag(gui)
    missing = [tag for tag in (R3_CUE_TAG, "BTN_CHANGE1", "BTN_CHANGE2")
               if tag not in controls]
    if missing:
        return [f"{resolution} {screen}: missing {', '.join(missing)}"]
    first = extent_values(controls["BTN_CHANGE1"])
    second = extent_values(controls["BTN_CHANGE2"])
    left, top, width, height = extent_values(controls[R3_CUE_TAG])
    where = f"{resolution} {screen} {R3_CUE_TAG} {(left, top, width, height)}"
    errors: list[str] = []
    if width != height or abs(width - R3_CUE_SCALE * first[3]) > 1:
        errors.append(f"{where}: not a square {R3_CUE_SCALE:.0%} of the "
                      f"{first[3]} px portrait")
    size = width
    gap_left = first[0] + first[2]
    gap = second[0] - gap_left
    fits = gap >= size + 2 * int(size * R3_CUE_GAP_MARGIN)
    if fits:
        # Twice the centres, so a half-pixel offset from an odd remainder is exact.
        if abs((2 * left + width) - (2 * gap_left + gap)) > 1:
            errors.append(f"{where}: the {gap} px gap holds it, but it is not "
                          f"centred in {gap_left}..{second[0]}")
    elif left - (second[0] + second[2]) != size // 3:
        errors.append(f"{where}: the {gap} px gap cannot hold it, so it belongs "
                      f"{size // 3} px right of the portrait ending at {second[0] + second[2]}")
    if abs((2 * top + height) - (2 * first[1] + first[3])) > 1:
        errors.append(f"{where}: not centred on the portraits' "
                      f"{first[1]}..{first[1] + first[3]}")
    _, _, panel_width, panel_height = extent_values(gui.root)
    if left < 0 or top < 0 or left + width > panel_width or top + height > panel_height:
        errors.append(f"{where}: leaves the {panel_width}x{panel_height} panel")
    for tag, control in controls.items():
        if control.acquire("CONTROLTYPE", -1) not in R3_CUE_BLOCKING_TYPES:
            continue
        x, y, w, h = extent_values(control)
        if left < x + w and x < left + width and top < y + h and y < top + height:
            errors.append(f"{where}: covers {tag} {(x, y, w, h)}")
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
    from prepare_universal_resources import R3_CUE_SCREENS
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
                required = {"optfeedback.gui", "scriptselect.gui", "confirm.gui", active_hud,
                            *R3_CUE_SCREENS}
                missing = required - names
                if missing:
                    errors.append(f"{resolution}: package is missing {sorted(missing)}")
                    continue
                for name in sorted(required):
                    package.extract(name, extract_dir)
            errors.extend(check_list_prototypes(
                extract_dir / "optfeedback.gui", resolution, "optfeedback", FEEDBACK_LISTS
            ))
            errors.extend(check_list_prototypes(
                extract_dir / "scriptselect.gui", resolution, "scriptselect", SCRIPTSELECT_LISTS
            ))
            errors.extend(check_feedback_gutter(
                extract_dir / "optfeedback.gui", resolution, height))
            errors.extend(check_scriptselect_centred(
                extract_dir / "scriptselect.gui", resolution, width))
            for name in R3_CUE_SCREENS:
                errors.extend(check_party_switch_cue(extract_dir / name, resolution))
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
