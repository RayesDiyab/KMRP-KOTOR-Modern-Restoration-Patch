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
    target_menu_extents,
    gold_extents,
    placed_top_left,
    walk_controls,
)
from pykotor.resource.formats.gff import read_gff  # noqa: E402


EXPECTED_ARCHIVE_COUNT = 66   # 48 upstream + 2880x1620 (2026-09-25) + 17 macOS (2026-09-29)
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


_DERIVED_ROOT: Path | None = None


def upstream_gui(resolution: str, name: str):
    """The untouched High Resolution Menus file for this resolution, or None.

    A resolution upstream does not ship (2880x1620) is compared against the set
    the build derives for it, made by the same tool from the same two upstream
    sets (tools/derive_resolution_gui_set.py).
    """
    global _DERIVED_ROOT
    matches = list(UPSTREAM_GUI_ROOT.glob(f"*/gui.{resolution}/{name}"))
    if matches:
        return matches[0]
    sys.path.insert(0, str(ROOT / "tools"))
    from derive_resolution_gui_set import DERIVED_GUI_SETS, derive_gui_set, derive_resolution
    if _DERIVED_ROOT is None:
        _DERIVED_ROOT = Path(tempfile.mkdtemp(prefix="kmrp-test-derived-"))
    target = _DERIVED_ROOT / f"gui.{resolution}"
    if not target.is_dir():
        if resolution in DERIVED_GUI_SETS:
            low, high, position = DERIVED_GUI_SETS[resolution]
            folder = next(UPSTREAM_GUI_ROOT.glob(f"*/gui.{low}")).parent
            derive_gui_set(folder / f"gui.{low}", folder / f"gui.{high}", target, position)
        else:
            # The macOS group (2026-09-29): blended from the upstream sets around it,
            # exactly as prepare_universal_resources.py derives it.
            width, height = (int(v) for v in resolution.split("x"))
            derive_resolution(UPSTREAM_GUI_ROOT, width, height, target)
    derived = target / name
    return derived if derived.is_file() else None


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


def check_feedback_rows(path: Path, resolution: str, height: int) -> list[str]:
    """The Feedback list's check box rows grow with the resolution.

    The engine builds them at the template's own height (the row hook does not
    reach them), so the build scales the template instead: round(43s), where the
    template is upstream's. Unscaled, the 25s circles overlapped in 43-px rows
    (seen at 3440x1440 on 2026-09-30; scale_listbox_padding.py, FEEDBACK_LIST).
    """
    from scale_listbox_padding import FEEDBACK_LIST, row_height
    source = upstream_gui(resolution, path.name)
    if source is None:
        return [f"{resolution} optfeedback: no upstream {path.name} to compare against"]
    tag = FEEDBACK_LIST[1]
    control = controls_by_tag(read_gff(path)).get(tag)
    reference = controls_by_tag(read_gff(source)).get(tag)
    if control is None or reference is None:
        return [f"{resolution} optfeedback: missing {tag}"]
    template = extent_values(reference.get_struct("PROTOITEM"))[3]
    actual = extent_values(control.get_struct("PROTOITEM"))[3]
    if actual != row_height(template, height):
        return [f"{resolution} optfeedback {tag}: rows {actual} px, expected "
                f"{row_height(template, height)} (upstream's {template}, scaled)"]
    return []


def check_journal_rows(path: Path, resolution: str, height: int) -> list[str]:
    """The journal shows six quest rows, spaced as the inventory's.

    The list box shares the height its rows leave between them, so with
    upstream's 78-unit template four rows fit and each gap was 22% of a row
    (47 px at 3024x1964). fit_rows_to_list sizes the template per resolution;
    this recomputes the engine's layout from the packaged file: six rows, each
    gap between a thirteenth and an eighth of a row (the inventory's are 8 to
    10%; ROW_GAP is an eleventh).
    """
    from scale_listbox_padding import JOURNAL_ROWS, row_height
    control = controls_by_tag(read_gff(path)).get("LB_ITEMS")
    if control is None:
        return [f"{resolution} journal: missing LB_ITEMS"]
    inner = extent_values(control)[3] - 2 * control.get_struct("BORDER").get_int32("DIMENSION")
    row = row_height(extent_values(control.get_struct("PROTOITEM"))[3], height)
    rows = inner // row
    gap = (inner - rows * row) // rows
    if rows != JOURNAL_ROWS or not row / 13 <= gap <= row / 8:
        return [f"{resolution} journal LB_ITEMS: {rows} rows of {row} px, {gap} px apart; "
                f"expected {JOURNAL_ROWS}, about a tenth of a row apart"]
    return []


def check_row_lists(extract_dir: Path, resolution: str, height: int) -> list[str]:
    """Lists of code-sized rows are as tall as whole rows (ROW_LISTS).

    The engine shares the height left under the last whole row between the
    rows. In a popup (the Container, the granted popup) the list is fitted at
    every size: each gap is exactly row // 11, and every control below the list
    starts under it, inside the panel. A full-screen list keeps its gaps within
    LOOSE_GAP of a row, for at least one kind of row where it has two (the
    Abilities list serves the Skills tab and the Feats and Powers tabs, and
    one height cannot fit both; see scale_listbox_padding.py).
    """
    from scale_listbox_padding import LOOSE_GAP, ROW_LISTS, row_height
    errors: list[str] = []
    for (screen, tag), (kind, bases) in ROW_LISTS.items():
        root = read_gff(extract_dir / screen).root
        controls = root.get_list("CONTROLS")
        control = controls_by_tag(read_gff(extract_dir / screen)).get(tag)
        if control is None:
            errors.append(f"{resolution} {screen}: missing {tag}")
            continue
        _, top, _, list_height = extent_values(control)
        inner = list_height - 2 * control.get_struct("BORDER").get_int32("DIMENSION")
        gaps = []
        for base in bases:
            row = row_height(base, height)
            rows = inner // row
            gaps.append(((inner - rows * row) // rows, row, rows))
        if kind == "popup":
            gap, row, rows = gaps[0]
            if gap != row // 11:
                errors.append(f"{resolution} {screen} {tag}: {rows} rows of {row} px, {gap} px apart, "
                              f"not {row // 11}")
            panel_height = extent_values(root)[3]
            for other in controls:
                _, other_top, _, other_height = extent_values(other)
                if other_top > top and other_top < top + list_height:
                    errors.append(f"{resolution} {screen}: {other.get_string('TAG')} starts inside {tag}")
                if other_top + other_height > panel_height:
                    errors.append(f"{resolution} {screen}: {other.get_string('TAG')} ends below the panel")
        elif min(gap / row for gap, row, _ in gaps) > LOOSE_GAP:
            errors.append(f"{resolution} {screen} {tag}: rows " +
                          ", ".join(f"{rows} of {row} px {gap} apart" for gap, row, rows in gaps))
    return errors


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


def check_swap_cue(path: Path, resolution: str) -> list[str]:
    """The swap-tabs cue sits in Abilities' bottom bar, just left of Close.

    Since 2026-09-25, at the maintainer's request; it sat past the last sub-tab
    before. The sub-tabs' height, twice as wide, a third of its height clear of
    Close and centred on it, inside the panel, and over no button, list or cue.
    """
    from prepare_universal_resources import (R3_CUE_BLOCKING_TYPES, SUBTAB_TAGS,
                                             SWAP_CUE_ASPECT, SWAP_CUE_BESIDE,
                                             SWAP_CUE_TAG)
    gui = read_gff(path)
    controls = controls_by_tag(gui)
    missing = [tag for tag in (SWAP_CUE_TAG, SWAP_CUE_BESIDE, *SUBTAB_TAGS)
               if tag not in controls]
    if missing:
        return [f"{resolution} abilities: missing {', '.join(missing)}"]
    left, top, width, height = extent_values(controls[SWAP_CUE_TAG])
    close = extent_values(controls[SWAP_CUE_BESIDE])
    where = f"{resolution} abilities {SWAP_CUE_TAG} {(left, top, width, height)}"
    errors: list[str] = []
    tab_height = max(extent_values(controls[tag])[3] for tag in SUBTAB_TAGS)
    if height != tab_height or width != height * SWAP_CUE_ASPECT:
        errors.append(f"{where}: not {SWAP_CUE_ASPECT}:1 at the sub-tabs' "
                      f"{tab_height} px height")
    if close[0] - (left + width) != height // 3:
        errors.append(f"{where}: not {height // 3} px left of Close at {close[0]}")
    # Twice the centres, so a half-pixel offset from an odd remainder is exact.
    if abs((2 * top + height) - (2 * close[1] + close[3])) > 1:
        errors.append(f"{where}: not centred on Close's {close[1]}..{close[1] + close[3]}")
    _, _, panel_width, panel_height = extent_values(gui.root)
    if left < 0 or top < 0 or left + width > panel_width or top + height > panel_height:
        errors.append(f"{where}: leaves the {panel_width}x{panel_height} panel")
    for tag, control in controls.items():
        if tag == SWAP_CUE_TAG or not (
                control.acquire("CONTROLTYPE", -1) in R3_CUE_BLOCKING_TYPES
                or tag.startswith("LBL_KMRP")):
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
    menu = target_menu_extents(gold, height)
    for tag in (*TOP_LEFT_TRANSIENT_TAGS, *(t for t in menu if t not in TOP_LEFT_TRANSIENT_TAGS)):
        control = controls.get(tag)
        if control is None:
            errors.append(f"{resolution} HUD: missing {tag}")
            continue
        expected = menu[tag] if tag in menu else placed_top_left(gold[tag], scale)
        actual = extent_values(control)
        if actual != expected:
            errors.append(f"{resolution} HUD {tag}: {actual}, expected {expected}")
    # The engine clips the target menu at the name label's right edge: every action button
    # must end inside it (2026-10-01, buttons cut off at 1920x1200).
    name = controls.get("LBL_NAME")
    if name is not None:
        name_right = sum(extent_values(name)[0::2])
        for slot in range(3):
            button = controls.get(f"BTN_TARGET{slot}")
            if button is not None and sum(extent_values(button)[0::2]) > name_right:
                errors.append(f"{resolution} HUD BTN_TARGET{slot} ends at "
                              f"{sum(extent_values(button)[0::2])}, past LBL_NAME's {name_right}")
    return errors


def check_combat_cues(path: Path, resolution: str) -> list[str]:
    """X and Y sit square, left of their combat buttons, inside the panel, and
    over no button and no action-queue icon."""
    from prepare_universal_resources import COMBAT_CUE_SCALE, COMBAT_CUES
    errors: list[str] = []
    gui = read_gff(path)
    _, _, panel_width, panel_height = extent_values(gui.root)
    controls = controls_by_tag(gui)
    clear_all = controls.get("BTN_CLEARALL")
    if clear_all is None:
        return [f"{resolution} HUD: missing BTN_CLEARALL"]
    size = max(8, round(extent_values(clear_all)[3] * COMBAT_CUE_SCALE))
    placed = []
    for tag, fill, _glyph, button in COMBAT_CUES:
        cue, target = controls.get(tag), controls.get(button)
        if cue is None or target is None:
            errors.append(f"{resolution} HUD: missing {tag if cue is None else button}")
            continue
        left, top, width, height = extent_values(cue)
        b_left, b_top, _, b_height = extent_values(target)
        where = f"{resolution} HUD {tag} {(left, top, width, height)}"
        if (width, height) != (size, size):
            errors.append(f"{where}: not a {size} px square")
        if left + width > b_left or abs((top + height / 2) - (b_top + b_height / 2)) > 1:
            errors.append(f"{where}: not left of {button}, centred on it")
        if left < 0 or top < 0 or left + width > panel_width or top + height > panel_height:
            errors.append(f"{where}: escapes the panel")
        if cue.get_struct("BORDER").get_resref("FILL") != fill:
            errors.append(f"{where}: fill is not {fill}")
        placed.append((tag, left, top, width, height))
    for other in gui.root.get_list("CONTROLS") or []:
        other_tag = other.get_string("TAG")
        if other_tag in {tag for tag, *_ in COMBAT_CUES}:
            continue
        if other.acquire("CONTROLTYPE", -1) != 6 and not other_tag.startswith("LBL_QUEUE"):
            continue
        x, y, w, h = extent_values(other)
        for tag, left, top, width, height in placed:
            if left < x + w and x < left + width and top < y + h and y < top + height:
                errors.append(f"{resolution} HUD {tag}: covers {other_tag} {(x, y, w, h)}")
    return errors


# The combat-mode message in both wordings, dialog.tlk 48208 and 48413.
COMBAT_MESSAGES = (
    "COMBAT MODE engaged. Press the Disengage button to cancel.",
    'COMBAT MODE engaged. Press the "F" key to disengage.',
)
# dialogfont10x10 draws at this multiple of the width measure_label reads from
# its TXI. Calibrated on the play-test screenshot of 2026-09-25 at 3440x1440,
# where a 300 px box broke the first wording into exactly five lines: "the
# Disengage" measures 165 px and drew 230 (1.39), and "button to cancel." did
# not fit 300 (216 x 1.39). One measurement; 1.40 leaves it a little margin.
COMBAT_MESSAGE_WIDTH_FACTOR = 1.40
# A line's height at 1440 lines: 32 px, dialogfont16x16's fontheight 0.32 at one
# texel per pixel -- the font the label is drawn in, whatever its .gui says (the
# width factor above is the same fact). Other heights scale with font_scale_for.
# *Corrected 2026-09-25:* this was 25, read from the first screenshot as "its 50
# px box held two lines". A second screenshot, of the 660 px fix, showed a
# two-line message with only its second line visible: two 32 px lines do not
# fit, and the engine skips a line that starts above the box. At 25 this check
# had passed that build.
COMBAT_MESSAGE_LINE_AT_1440 = 32


def wrapped_lines(text: str, width: float, advances, spacing: float) -> int:
    from build_controller_prompt_textures import measure_label
    lines, current = 1, ""
    for word in text.split():
        trial = f"{current} {word}" if current else word
        if current and measure_label(trial, advances, spacing) * COMBAT_MESSAGE_WIDTH_FACTOR > width:
            lines, current = lines + 1, word
        else:
            current = trial
    return lines


def check_combat_message(path: Path, txi: Path, resolution: str, height: int) -> list[str]:
    """The combat-mode message, in both wordings, fits the lines its box can show."""
    from build_controller_prompt_textures import parse_font_metrics
    from prepare_universal_resources import font_scale_for
    controls = controls_by_tag(read_gff(path))
    label = controls.get("LBL_CMBTMODEMSG")
    if label is None:
        return [f"{resolution} HUD: missing LBL_CMBTMODEMSG"]
    advances, spacing = parse_font_metrics(txi)
    if not advances:
        return [f"{resolution}: no metrics in {txi.name}"]
    _, _, width, box_height = extent_values(label)
    line = COMBAT_MESSAGE_LINE_AT_1440 * font_scale_for(height) / font_scale_for(1440)
    room = max(1, int(box_height // line))
    errors = []
    for message in COMBAT_MESSAGES:
        needed = wrapped_lines(message, width, advances, spacing)
        if needed > room:
            errors.append(f"{resolution} HUD LBL_CMBTMODEMSG {width}x{box_height}: "
                          f"{message!r} needs {needed} lines, the box shows {room}")
    return errors


def main() -> int:
    from prepare_universal_resources import R3_CUE_SCREENS
    archive_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "kmrp" / "resources"
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
                from scale_listbox_padding import ROW_LISTS
                required = {"optfeedback.gui", "scriptselect.gui", "confirm.gui", "journal.gui",
                            *(screen for screen, _ in ROW_LISTS), active_hud,
                            "dialogfont10x10.txi", *R3_CUE_SCREENS}
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
            errors.extend(check_feedback_rows(
                extract_dir / "optfeedback.gui", resolution, height))
            errors.extend(check_scriptselect_centred(
                extract_dir / "scriptselect.gui", resolution, width))
            errors.extend(check_journal_rows(extract_dir / "journal.gui", resolution, height))
            errors.extend(check_row_lists(extract_dir, resolution, height))
            for name in R3_CUE_SCREENS:
                errors.extend(check_party_switch_cue(extract_dir / name, resolution))
            errors.extend(check_swap_cue(extract_dir / "abilities.gui", resolution))
            errors.extend(check_confirmation(extract_dir / "confirm.gui", resolution))
            errors.extend(check_hud(extract_dir / active_hud, resolution, height, gold))
            errors.extend(check_combat_cues(extract_dir / active_hud, resolution))
            errors.extend(check_combat_message(extract_dir / active_hud,
                                               extract_dir / "dialogfont10x10.txi",
                                               resolution, height))

    if errors:
        print(f"FAIL: {len(errors)} generated GUI geometry error(s)")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"PASS: Reported GUI repairs, the journal's and other lists' rows, the cues and active HUD geometry "
          f"in {len(archives)} archives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
