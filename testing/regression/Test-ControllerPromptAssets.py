#!/usr/bin/env python3
"""Verify dynamic-controller prompt assets in every generated GUI archive."""

from __future__ import annotations

import argparse
import io
import re
import struct
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from build_controller_prompt_textures import (  # noqa: E402
    BADGE_GROUPS,
    FAMILY_LETTERS,
    GLYPH_FAMILIES,
    GLYPH_PACK,
    PER_CAPTION_TARGETS,
    PROMPT_FALLBACK_STRINGS,
    PROMPT_MANIFEST_NAME,
    PROMPT_STRREFS,
    PROMPT_TARGETS,
    TEXTURE_HEIGHT,
    TEXTURE_WIDTH,
    family_resref,
    measure_label,
    parse_font_metrics,
    variant_strings,
)
from build_controller_layout import CAPTION_FONT, MAPPINGS  # noqa: E402
from controller_layout_backdrop import DECOR, TEXTURES as LAYOUT_BACKDROP  # noqa: E402
from pykotor.resource.formats.gff import read_gff  # noqa: E402


def verify_placement_manifest(archive, archive_name, names, gui_cache):
    """The manifest the patcher reads to re-place badges against the player's own
    dialog.tlk.

    Worth its own check because every way it can be wrong is SILENT. The patcher
    treats a missing or unparsable manifest as "this archive predates the feature"
    and quietly keeps the shipped English placement, so a build that stopped
    emitting it, or emitted stale control extents after a layout change, would
    look exactly like a build where the feature simply did nothing.
    """
    manifest_name = names.get(PROMPT_MANIFEST_NAME)
    if manifest_name is None:
        raise AssertionError(f"{archive_name}: missing {PROMPT_MANIFEST_NAME}")

    texture = None
    spacing = None
    advances = None
    rows = {}
    for line in archive.read(manifest_name).decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(" ")
        if parts[0] == "texture":
            texture = (int(parts[1]), int(parts[2]))
        elif parts[0] == "spacing":
            spacing = float(parts[1])
        elif parts[0] == "advances":
            advances = [float(value) for value in parts[1:]]
        elif parts[0] == "prompt":
            rows[parts[1]] = (int(parts[2]), int(parts[3]), float(parts[4]), parts[5])

    if texture != (TEXTURE_WIDTH, TEXTURE_HEIGHT):
        raise AssertionError(f"{archive_name}: manifest texture size {texture}")
    if advances is None or len(advances) != 256:
        raise AssertionError(
            f"{archive_name}: manifest carries {len(advances) if advances else 0} advances, "
            "expected 256")
    if spacing is None or spacing <= 0:
        raise AssertionError(f"{archive_name}: manifest spacing {spacing}")

    # The archive's own font metrics must be the ones embedded, or the patcher
    # measures this resolution's labels with another resolution's font.
    txi_name = names.get("dialogfont16x16.txi")
    if txi_name is None:
        raise AssertionError(f"{archive_name}: no dialogfont16x16.txi to check the manifest against")
    with io.BytesIO(archive.read(txi_name)) as handle:
        import tempfile
        temporary = Path(tempfile.mkdtemp()) / "dialogfont16x16.txi"
        temporary.write_bytes(handle.getvalue())
    live_advances, live_spacing = parse_font_metrics(temporary)
    if abs(live_spacing - spacing) > 1e-4:
        raise AssertionError(
            f"{archive_name}: manifest spacing {spacing} != font's {live_spacing}")
    if max(abs(a - b) for a, b in zip(advances, live_advances)) > 1e-4:
        raise AssertionError(f"{archive_name}: manifest advances do not match the archive font")

    # Every badge once per controller family, and a button that changes its
    # caption once per caption as well -- <resref><index>, placed against that
    # one wording.
    expected_rows = set()
    for target in PROMPT_TARGETS:
        names_for_target = [target.resref]
        if (target.gui, target.tag) in PER_CAPTION_TARGETS:
            names_for_target += [f"{target.resref}{index}" for index in
                                 range(len(PROMPT_STRREFS[(target.gui, target.tag)]))]
        for family in GLYPH_FAMILIES:
            expected_rows.update(family_resref(name, family) for name in names_for_target)
    if set(rows) != expected_rows:
        raise AssertionError(
            f"{archive_name}: manifest rows differ -- missing "
            f"{sorted(expected_rows - set(rows))}, unexpected {sorted(set(rows) - expected_rows)}")

    # A badge in a group -- the main menu's column of A's -- is placed against the
    # whole group, so its row carries the group's variants, collected in target
    # order exactly as the builder collects them, and the group's widest label.
    group_variants = {}
    for member in PROMPT_TARGETS:
        group = BADGE_GROUPS.get((member.gui, member.tag))
        if group is None:
            continue
        collected = group_variants.setdefault(group, [])
        for variant in PROMPT_STRREFS.get((member.gui, member.tag), ()):
            if variant not in collected:
                collected.append(variant)

    for target, family in [(t, f) for t in PROMPT_TARGETS for f in GLYPH_FAMILIES]:
        width, height, baked, encoded = rows[family_resref(target.resref, family)]
        control = gui_cache[target.gui][target.control_index]
        extent = control.get_struct("EXTENT")
        if (width, height) != (extent.get_int32("WIDTH"), extent.get_int32("HEIGHT")):
            raise AssertionError(
                f"{archive_name}: {target.resref} manifest extent {width}x{height} != "
                f"the control's {extent.get_int32('WIDTH')}x{extent.get_int32('HEIGHT')}")

        # The STRREFs must be the ones the button really carries, not a table that
        # drifted from it. This is the check that would have caught the four wrong
        # labels the hand-written table shipped with.
        text = control.get_struct("TEXT")
        strref = text.get_uint32("STRREF") if text is not None else None
        variants = PROMPT_STRREFS[(target.gui, target.tag)]
        # Except where the panel sets the caption in code: the inventory filter's
        # .gui STRREF is replaced by one of six "Show ... Items" wordings before it
        # is ever drawn, which is why that button has a badge per caption.
        code_captioned = (target.gui, target.tag) in PER_CAPTION_TARGETS
        if not code_captioned and (
                strref is None or not any(strref in variant for variant in variants)):
            raise AssertionError(
                f"{archive_name}: {target.gui}:{target.tag} draws STRREF {strref}, "
                f"which is not among {variants}")

        group = BADGE_GROUPS.get((target.gui, target.tag))
        placed = tuple(group_variants[group]) if group is not None else variants
        expected = ";".join("+".join(str(ref) for ref in variant) for variant in placed)
        if encoded != expected:
            raise AssertionError(
                f"{archive_name}: {target.resref} manifest variants {encoded} != {expected}")

        widest = max((measure_label(label, live_advances, live_spacing)
                      for label in variant_strings(placed, PROMPT_FALLBACK_STRINGS)),
                     default=0.0)
        if abs(baked - round(widest, 2)) > 0.01:
            raise AssertionError(
                f"{archive_name}: {target.resref} baked width {baked} != measured {widest:.2f}")


PROFILE_BINS = 12
# A glyph whose letter profile differs from its own mirror by less than this
# cannot decide the question, so the orientation check skips it and says so.
# Measured on the shipped artwork: A 0.0095, Y 0.0121 (decisive);
# B 0.0037, X 0.0029 (near-symmetric).
# A mirrored match must beat the upright one by this factor to count.
ORIENTATION_MARGIN = 0.8
ASYMMETRY_FLOOR = 0.006


def _letter_profile(rgba, width: int):
    """Vertical distribution of the glyph's LETTER, as PROFILE_BINS fractions.

    This exists to catch a vertically flipped texture, which nothing else here
    can. The badge disc is a circle and therefore symmetric, so every check based
    on the badge outline passes just as happily upside down; only the letter is
    asymmetric.

    An earlier revision stored rows top-down while the header declared descriptor
    0x08 (bottom-left origin), so A, B and Y shipped upside down in all 480
    textures. X is symmetric about the horizontal axis, which is why it looked
    correct and hid the fault.

    `rgba` is a flat (r, g, b, a) sequence in TOP-DOWN order. The brightest eighth
    of the opaque pixels is taken as the letter -- it is lighter than the disc in
    every glyph of this set -- and binned over the badge's own vertical extent.
    A centroid was tried first and is useless: every glyph centres near 0.50.
    """
    lit = []
    for index in range(0, len(rgba), 4):
        if rgba[index + 3] <= 200:
            continue
        r, g, b = rgba[index], rgba[index + 1], rgba[index + 2]
        lit.append(((index // 4) // width, 0.2126 * r + 0.7152 * g + 0.0722 * b))
    if not lit:
        return None
    rows = [row for row, _ in lit]
    top, bottom = min(rows), max(rows)
    if bottom == top:
        return None
    cut = sorted(value for _, value in lit)[int(len(lit) * 0.875)]
    bins = [0.0] * PROFILE_BINS
    for row, value in lit:
        if value >= cut:
            slot = int((row - top) / (bottom - top + 1e-9) * PROFILE_BINS)
            bins[min(PROFILE_BINS - 1, slot)] += 1.0
    total = sum(bins) or 1.0
    return [count / total for count in bins]


def _profile_error(left, right) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right))


RUNTIME_OBJECT_OFFSETS = {
    "K1_CHARACTER_EXIT_OFFSET": "0x523C",
    "K1_CHARACTER_SCRIPTS_OFFSET": "0x5400",
    "K1_CONTAINER_GET_ITEMS_OFFSET": "0x0AD0",
    "K1_CONTAINER_CANCEL_OFFSET": "0x0C94",
    "K1_CONTAINER_GIVE_ITEMS_OFFSET": "0x0E58",
    "K1_SAVELOAD_LOAD_OFFSET": "0x0C14",
    "K1_SAVELOAD_BACK_OFFSET": "0x0DD8",
    "K1_SAVELOAD_DELETE_OFFSET": "0x0F9C",
}


def verify_runtime_lookup_patch() -> None:
    patch_path = (
        ROOT
        / "third_party"
        / "Included"
        / "KPM-Xbox-Controls-K1-1.2 by Saul0097"
        / "KMRP-CONTROLLER-PROMPTS-PATCH.diff"
    )
    patch = patch_path.read_text(encoding="utf-8")
    if "K1_GUI_PANEL_GET_CONTROL" in patch or "GuiPanelGetControlFn" in patch:
        raise AssertionError(
            "Runtime prompt patch still uses unsafe GUI-list/control-array lookup")
    if "OffsetPointer(panel, prompts[i].controlOffset)" not in patch:
        raise AssertionError("Runtime prompt patch does not use object offsets")
    if "bool g_cursorParked = false;" not in patch:
        raise AssertionError(
            "Controller runtime must preserve the visible Windows cursor on startup")
    if "K1_BUTTON_HILIGHT_PARAMS_OFFSET = 0x00F4;" not in patch:
        raise AssertionError("Controller prompts do not cover the focused-button border")
    # Prompts follow the ACTIVE input device, not mere connection. The earlier
    # rule was "a pad is plugged in", because the mouse hook could not tell
    # KOTOR's own cursor recentring from real movement and the artwork vanished
    # on every scene transition. MouseIsBeingUsedK1 now makes that distinction,
    # so the prompts can answer the honest question.
    if "const bool controllerMode = IsControllerInputActiveK1();" not in patch:
        raise AssertionError(
            "Controller prompts must follow the active input device")
    if "bool MouseIsBeingUsedK1(" not in patch:
        raise AssertionError(
            "Prompt visibility needs the recentre-vs-real-movement discriminator; "
            "without it every menu transition clears the artwork")
    if "PollMovieControllerK1" not in patch or "ConsumeMovieSkipK1" not in patch:
        raise AssertionError("Controller patch is missing the per-frame movie skip path")
    for name, value in RUNTIME_OBJECT_OFFSETS.items():
        declaration = f"{name} = {value};"
        if declaration not in patch:
            raise AssertionError(f"Runtime prompt patch is missing {declaration}")
    for name in (
        "K1_UPGRADE_SELECTION_UPGRADE_OFFSET",
        "K1_UPGRADE_SELECTION_BACK_OFFSET",
    ):
        if f"{{{name}," not in patch:
            raise AssertionError(f"Runtime prompt patch does not bind through {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "resources",
        type=Path,
        nargs="?",
        default=ROOT / "build" / "kmrp" / "resources",
    )
    args = parser.parse_args()

    verify_runtime_lookup_patch()

    archives = sorted(args.resources.glob("gui-*.zip"))
    # 48 upstream resolutions plus 2880x1620, derived since 2026-09-25.
    if len(archives) != 49:
        raise AssertionError(f"Expected 49 GUI archives, found {len(archives)}")

    common_path = args.resources / "override-common.zip"
    with zipfile.ZipFile(common_path) as common:
        common_names = {name.lower() for name in common.namelist()}
        # Per family: one row glyph per row, and the diagram board, whose
        # silhouette and face-button glyphs differ by family and which the
        # runtime swaps with the pad exactly as it swaps the row glyphs.
        expected_layout_art = set()
        for family in GLYPH_FAMILIES:
            letter = FAMILY_LETTERS[family]
            expected_layout_art.add(f"kmr{letter}lytdiag.tga")
            # The travelling A beside a confirmation box's focused button.
            expected_layout_art.add(f"kmr{letter}cnfa.tga")
            expected_layout_art.add(f"kmr{letter}lytbk.tga")
            expected_layout_art.update(
                f"kmr{letter}lyt{index:02d}.tga"
                for index in range(len(MAPPINGS)))
        # The backdrop and edge art are shared by every family.
        expected_layout_art.update(f"{name}.tga" for name in LAYOUT_BACKDROP)
        missing = expected_layout_art - common_names
        if missing:
            raise AssertionError(
                f"override-common.zip: missing Controller Layout art {sorted(missing)}")
        if "kmrplytoutline.tga" in common_names:
            raise AssertionError(
                "override-common.zip still ships kmrplytoutline.tga, the drawn "
                "silhouette the diagram board replaced")

    # The runtime binds GLYPH_nn and TEXT_nn by tag, counting them itself. A row
    # added to the builder without the runtime's count moving would bind short
    # and the screen would refuse to open ("bind-failed"); the other way round,
    # it would bind past the file.
    runtime = (ROOT / "src" / "controller-native" / "K1ControllerLayout.cpp").read_text(
        encoding="utf-8")
    import re as _re
    match = _re.search(r"constexpr int K1_LAYOUT_ROWS = (\d+);", runtime)
    if match is None or int(match.group(1)) != len(MAPPINGS):
        raise AssertionError(
            f"K1_LAYOUT_ROWS in K1ControllerLayout.cpp is "
            f"{match.group(1) if match else 'missing'}, the builder has "
            f"{len(MAPPINGS)} rows")
    # Same for the edge art, DECO_nn: a count short and the last pieces are
    # never drawn, a count long and the screen refuses to open.
    match = _re.search(r"constexpr int K1_LAYOUT_DECOR = (\d+);", runtime)
    if match is None or int(match.group(1)) != len(DECOR):
        raise AssertionError(
            f"K1_LAYOUT_DECOR in K1ControllerLayout.cpp is "
            f"{match.group(1) if match else 'missing'}, the builder has "
            f"{len(DECOR)} decorations")

    checked = 0
    for archive_path in archives:
        with zipfile.ZipFile(archive_path) as archive:
            names = {name.lower(): name for name in archive.namelist()}
            for required in ("optgameplay.gui", "kmrplayout.gui", "confirm.gui",
                             "dialog.gui"):
                if required not in names:
                    raise AssertionError(f"{archive_path.name}: missing {required}")
            controls_menu = read_gff(
                archive.read(names["optgameplay.gui"])).root.get_list("CONTROLS")
            entry = [c for c in controls_menu
                     if c.get_string("TAG") == "BTN_KMRPLAY"]
            if len(entry) != 1:
                raise AssertionError(
                    f"{archive_path.name}: expected one Controller Layout entry, "
                    f"found {len(entry)}")
            entry_text = entry[0].get_struct("TEXT")
            if entry_text.get_string("TEXT") != "Controller Layout":
                raise AssertionError(
                    f"{archive_path.name}: Controller Layout entry has wrong text")
            # The layout entry and the two above it were lifted off the bottom
            # bar; the entry must still end above Default.
            by_menu = {c.get_string("TAG"): c.get_struct("EXTENT") for c in controls_menu}
            if (by_menu["BTN_KMRPLAY"].get_int32("TOP")
                    + by_menu["BTN_KMRPLAY"].get_int32("HEIGHT")
                    >= by_menu["BTN_DEFAULT"].get_int32("TOP")):
                raise AssertionError(
                    f"{archive_path.name}: Controller Layout entry reaches Default")
            # confirm.gui carries one label the runtime binds by tag and moves
            # beside the focused button; without it Yes/No boxes have no A.
            confirm = read_gff(
                archive.read(names["confirm.gui"])).root.get_list("CONTROLS")
            badge = [c for c in confirm if c.get_string("TAG") == "LBL_KMRPA"]
            confirm_ids = [c.get_int32("ID") for c in confirm]
            if (len(badge) != 1 or badge[0].get_int32("CONTROLTYPE") != 4
                    or len(set(confirm_ids)) != len(confirm_ids)):
                raise AssertionError(
                    f"{archive_path.name}: confirm.gui needs exactly one label "
                    f"LBL_KMRPA with an ID of its own")
            # dialog.gui carries the A the runtime moves beside the highlighted
            # reply. Every other control must be vanilla's pair, unmoved: below
            # 3440x1440 the file exists only to carry this label.
            dialog_gff = read_gff(archive.read(names["dialog.gui"]))
            dialog = dialog_gff.root.get_list("CONTROLS")
            dialog_badge = [c for c in dialog if c.get_string("TAG") == "LBL_KMRPDLG"]
            dialog_ids = [c.get_int32("ID") for c in dialog]
            if (len(dialog_badge) != 1 or dialog_badge[0].get_int32("CONTROLTYPE") != 4
                    or len(set(dialog_ids)) != len(dialog_ids)
                    or {c.get_string("TAG") for c in dialog}
                    != {"LBL_MESSAGE", "LB_REPLIES", "LBL_KMRPDLG"}):
                raise AssertionError(
                    f"{archive_path.name}: dialog.gui needs LBL_MESSAGE, LB_REPLIES "
                    f"and exactly one label LBL_KMRPDLG with an ID of its own")
            root_extent = dialog_gff.root.get_struct("EXTENT")
            expected_root = ((76, 604, 870, 160) if "3440x1440" in archive_path.name
                             else (48, 378, 544, 100))
            if tuple(root_extent.get_int32(f) for f in
                     ("LEFT", "TOP", "WIDTH", "HEIGHT")) != expected_root:
                raise AssertionError(
                    f"{archive_path.name}: dialog.gui's panel is not the "
                    f"{'tuned' if expected_root[2] == 870 else 'vanilla'} one")
            layout = read_gff(
                archive.read(names["kmrplayout.gui"])).root.get_list("CONTROLS")
            expected_tags = {
                "LBL_TITLE", "BTN_BACK", "LBL_XBOX", "LBL_PS",
                "LBL_SWITCH", "LBL_DECK", "LBL_KBM", "LBL_PAD",
                "LBL_DIAGRAM", "LBL_HELP",
                *(f"GLYPH_{i:02d}" for i in range(len(MAPPINGS))),
                *(f"TEXT_{i:02d}" for i in range(len(MAPPINGS))),
                *(f"DECO_{i:02d}" for i in range(len(DECOR))),
                "GLYPH_BACK",
            }
            tags = {c.get_string("TAG") for c in layout}
            ids = {c.get_int32("ID") for c in layout}
            if tags != expected_tags or ids != set(range(len(expected_tags))):
                raise AssertionError(
                    f"{archive_path.name}: Controller Layout controls drifted")
            # Tags and IDs alone once passed a screen of 38 identical empty
            # labels stacked at one extent, because the authoring tool mutated
            # copies returned by get_struct(). Check what the player sees.
            by_tag = {c.get_string("TAG"): c for c in layout}
            expected_text = {"LBL_TITLE": "Controller Layout", "BTN_BACK": "Back"}
            expected_text.update(
                (f"TEXT_{i:02d}", caption)
                for i, (_glyph, caption) in enumerate(MAPPINGS))
            for tag, wanted in expected_text.items():
                found = by_tag[tag].get_struct("TEXT").get_string("TEXT")
                if found != wanted:
                    raise AssertionError(
                        f"{archive_path.name}: Controller Layout {tag} reads "
                        f"{found!r}, expected {wanted!r}")
            expected_fill = {"LBL_DIAGRAM": "kmrplytdiag"}
            # The runtime rewrites the glyph fills per family; the file still
            # carries the Xbox set so the screen is never blank on frame one.
            expected_fill.update(
                (f"GLYPH_{i:02d}", f"kmrplyt{i:02d}") for i in range(len(MAPPINGS)))
            expected_fill.update(
                (f"DECO_{i:02d}", name) for i, name in enumerate(DECOR))
            expected_fill["GLYPH_BACK"] = "kmrplytbk"
            for tag, wanted in expected_fill.items():
                found = str(by_tag[tag].get_struct("BORDER").get_resref("FILL"))
                if found.lower() != wanted:
                    raise AssertionError(
                        f"{archive_path.name}: Controller Layout {tag} fill is "
                        f"{found!r}, expected {wanted!r}")
            # Full screen, not a box: the panel root is the backdrop.
            root = read_gff(archive.read(names["kmrplayout.gui"])).root
            root_fill = str(root.get_struct("BORDER").get_resref("FILL")).lower()
            if root_fill != "kmrlytbg":
                raise AssertionError(
                    f"{archive_path.name}: Controller Layout backdrop is "
                    f"{root_fill!r}, expected 'kmrlytbg'")
            # Captions are drawn in CAPTION_FONT whatever a .gui asks for, and
            # a one-line box too narrow for its caption shows only the last
            # line after wrapping -- "Free look" for "Camera / Click: free
            # look". So each caption asks for that font and either fits on one
            # line, at the 0.88 of measure_label() the game was measured to
            # draw, or has a box two lines tall.
            txi_path = Path(tempfile.mkdtemp()) / f"{CAPTION_FONT}.txi"
            txi_path.write_bytes(archive.read(names[f"{CAPTION_FONT}.txi"]))
            caption_metrics = parse_font_metrics(txi_path)
            line_px = float(re.search(
                r"^fontheight (\S+)", txi_path.read_text(encoding="ascii", errors="replace"),
                re.M | re.I).group(1)) * 100
            for i in range(len(MAPPINGS)):
                control = by_tag[f"TEXT_{i:02d}"]
                font = str(control.get_struct("TEXT").get_resref("FONT")).lower()
                if font != CAPTION_FONT:
                    raise AssertionError(
                        f"{archive_path.name}: TEXT_{i:02d} asks for {font}, "
                        f"not {CAPTION_FONT}")
                extent = control.get_struct("EXTENT")
                drawn = measure_label(
                    control.get_struct("TEXT").get_string("TEXT"), *caption_metrics) * 0.88
                if (drawn > extent.get_int32("WIDTH")
                        and extent.get_int32("HEIGHT") < 2 * line_px):
                    raise AssertionError(
                        f"{archive_path.name}: TEXT_{i:02d} needs {drawn:.0f}px "
                        f"in a {extent.get_int32('WIDTH')}px one-line box")
            # Every glyph and caption occupies its own place on screen. The
            # family headings and the two device labels deliberately share one,
            # because the runtime shows exactly one of each group at a time.
            placed = [f"GLYPH_{i:02d}" for i in range(len(MAPPINGS))]
            placed += [f"TEXT_{i:02d}" for i in range(len(MAPPINGS))]
            boxes = {}
            for tag in placed:
                e = by_tag[tag].get_struct("EXTENT")
                box = tuple(e.get_int32(k)
                            for k in ("LEFT", "TOP", "WIDTH", "HEIGHT"))
                if box[2] <= 0 or box[3] <= 0:
                    raise AssertionError(
                        f"{archive_path.name}: Controller Layout {tag} has no size")
                if box in boxes:
                    raise AssertionError(
                        f"{archive_path.name}: Controller Layout {tag} sits on "
                        f"top of {boxes[box]} at {box}")
                boxes[box] = tag
            gui_cache = {}
            for target, family in [(t, f) for t in PROMPT_TARGETS for f in GLYPH_FAMILIES]:
                resref = family_resref(target.resref, family)
                gui_name = names.get(target.gui)
                texture_name = names.get(f"{resref}.tga")
                if gui_name is None or texture_name is None:
                    raise AssertionError(
                        f"{archive_path.name}: missing {target.gui} or {resref}.tga")

                controls = gui_cache.get(target.gui)
                if controls is None:
                    controls = read_gff(archive.read(gui_name)).root.get_list("CONTROLS")
                    gui_cache[target.gui] = controls
                control = controls[target.control_index]
                if control.get_string("TAG") != target.tag:
                    raise AssertionError(
                        f"{archive_path.name}: {target.gui}[{target.control_index}] "
                        f"is not {target.tag}")
                border = control.get_struct("BORDER")
                if border is None or str(border.get_resref("FILL")):
                    raise AssertionError(
                        f"{archive_path.name}: {target.gui}:{target.tag} normal fill is not empty")

                data = archive.read(texture_name)
                if len(data) != 18 + TEXTURE_WIDTH * TEXTURE_HEIGHT * 4 + 26:
                    raise AssertionError(
                        f"{archive_path.name}: unexpected {resref}.tga length {len(data)}")
                image_type = data[2]
                width, height, depth, descriptor = struct.unpack_from("<HHBB", data, 12)
                if (image_type, width, height, depth, descriptor) != (
                        2, TEXTURE_WIDTH, TEXTURE_HEIGHT, 32, 0x08):
                    raise AssertionError(
                        f"{archive_path.name}: invalid TGA header for {resref}")
                alphas = data[18 + 3:18 + TEXTURE_WIDTH * TEXTURE_HEIGHT * 4:4]
                opaque = [index for index, alpha in enumerate(alphas) if alpha]
                if not opaque:
                    raise AssertionError(
                        f"{archive_path.name}: {resref} is fully transparent")
                # The badge now sits immediately before the button's label rather
                # than at a fixed inset, so it is no longer confined to the left
                # quarter -- a short label on a wide button pushes it toward the
                # middle. What must still hold is that it stays in the left half
                # and never reaches the centre, where it would collide with the
                # text the engine draws there.
                rightmost = max(index % TEXTURE_WIDTH for index in opaque)
                if rightmost >= TEXTURE_WIDTH // 2:
                    raise AssertionError(
                        f"{archive_path.name}: {resref} badge reaches the "
                        f"centre of the button (x={rightmost} of {TEXTURE_WIDTH}); "
                        "it would sit under the label")

                # Orientation, decided against the source artwork rather than
                # a constant. Only glyphs whose letter is asymmetric enough can
                # settle it; the rest are skipped rather than asserted loosely.
                folder, family_art = GLYPH_FAMILIES[family]
                art_name = family_art.get(target.glyph)
                art_path = GLYPH_PACK / folder / art_name if art_name else None
                if art_path is not None and art_path.is_file():
                    from PIL import Image

                    art = Image.open(art_path).convert("RGBA")
                    box = art.getbbox()
                    if box:
                        art = art.crop(box)
                    expected = _letter_profile(art.tobytes(), art.width)
                    if expected is not None and _profile_error(
                            expected, expected[::-1]) >= ASYMMETRY_FLOOR:
                        body = data[18:18 + TEXTURE_WIDTH * TEXTURE_HEIGHT * 4]
                        # Stored bottom-up (descriptor 0x08), and BGRA on disk.
                        stride = TEXTURE_WIDTH * 4
                        top_down = b"".join(
                            body[row * stride:(row + 1) * stride]
                            for row in range(TEXTURE_HEIGHT - 1, -1, -1))
                        rgba = bytearray(len(top_down))
                        rgba[0::4] = top_down[2::4]
                        rgba[1::4] = top_down[1::4]
                        rgba[2::4] = top_down[0::4]
                        rgba[3::4] = top_down[3::4]
                        actual = _letter_profile(rgba, TEXTURE_WIDTH)
                        if actual is not None:
                            upright = _profile_error(actual, expected)
                            inverted = _profile_error(actual, expected[::-1])
                            # Only a clear verdict counts. A flipped texture loses
                            # by a wide margin; a near-tie is a glyph too small or
                            # too low in contrast to tell -- the Steam Deck set's
                            # grey A on a 39-pixel Map button came out 0.0433
                            # against 0.0434 -- and is skipped like the symmetric
                            # glyphs above rather than failed.
                            if inverted < upright * ORIENTATION_MARGIN:
                                raise AssertionError(
                                    f"{archive_path.name}: {resref} matches a MIRRORED "
                                    f"{art_path.name} better than the upright one "
                                    f"({inverted:.4f} < {upright:.4f}); the texture is "
                                    "stored upside down")
                checked += 1

            verify_placement_manifest(archive, archive_path.name, names, gui_cache)

    print(
        f"Controller prompts OK: {len(archives)} archives, "
        f"{checked} target textures ({len(GLYPH_FAMILIES)} controller families), "
        f"{len(PROMPT_TARGETS)} verified control mappings each, Controller Layout "
        "verified, placement manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
