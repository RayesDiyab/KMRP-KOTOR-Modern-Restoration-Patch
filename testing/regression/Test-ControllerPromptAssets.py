#!/usr/bin/env python3
"""Verify dynamic-controller prompt assets in every generated GUI archive."""

from __future__ import annotations

import argparse
import io
import struct
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from build_controller_prompt_textures import (  # noqa: E402
    GLYPH_ART,
    GLYPH_ART_DIR,
    PROMPT_FALLBACK_STRINGS,
    PROMPT_MANIFEST_NAME,
    PROMPT_STRREFS,
    PROMPT_TARGETS,
    TEXTURE_HEIGHT,
    TEXTURE_WIDTH,
    measure_label,
    parse_font_metrics,
    variant_strings,
)
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

    if set(rows) != {target.resref for target in PROMPT_TARGETS}:
        raise AssertionError(f"{archive_name}: manifest covers {sorted(rows)}")

    for target in PROMPT_TARGETS:
        width, height, baked, encoded = rows[target.resref]
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
        if strref is None or not any(strref in variant for variant in variants):
            raise AssertionError(
                f"{archive_name}: {target.gui}:{target.tag} draws STRREF {strref}, "
                f"which is not among {variants}")

        expected = ";".join("+".join(str(ref) for ref in variant) for variant in variants)
        if encoded != expected:
            raise AssertionError(
                f"{archive_name}: {target.resref} manifest variants {encoded} != {expected}")

        widest = max((measure_label(label, live_advances, live_spacing)
                      for label in variant_strings(variants, PROMPT_FALLBACK_STRINGS)),
                     default=0.0)
        if abs(baked - round(widest, 2)) > 0.01:
            raise AssertionError(
                f"{archive_name}: {target.resref} baked width {baked} != measured {widest:.2f}")


PROFILE_BINS = 12
# A glyph whose letter profile differs from its own mirror by less than this
# cannot decide the question, so the orientation check skips it and says so.
# Measured on the shipped artwork: A 0.0095, Y 0.0121 (decisive);
# B 0.0037, X 0.0029 (near-symmetric).
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
    if len(archives) != 48:
        raise AssertionError(f"Expected 48 GUI archives, found {len(archives)}")

    checked = 0
    for archive_path in archives:
        with zipfile.ZipFile(archive_path) as archive:
            names = {name.lower(): name for name in archive.namelist()}
            gui_cache = {}
            for target in PROMPT_TARGETS:
                gui_name = names.get(target.gui)
                texture_name = names.get(f"{target.resref}.tga")
                if gui_name is None or texture_name is None:
                    raise AssertionError(
                        f"{archive_path.name}: missing {target.gui} or {target.resref}.tga")

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
                        f"{archive_path.name}: unexpected {target.resref}.tga length {len(data)}")
                image_type = data[2]
                width, height, depth, descriptor = struct.unpack_from("<HHBB", data, 12)
                if (image_type, width, height, depth, descriptor) != (
                        2, TEXTURE_WIDTH, TEXTURE_HEIGHT, 32, 0x08):
                    raise AssertionError(
                        f"{archive_path.name}: invalid TGA header for {target.resref}")
                alphas = data[18 + 3:18 + TEXTURE_WIDTH * TEXTURE_HEIGHT * 4:4]
                opaque = [index for index, alpha in enumerate(alphas) if alpha]
                if not opaque:
                    raise AssertionError(
                        f"{archive_path.name}: {target.resref} is fully transparent")
                # The badge now sits immediately before the button's label rather
                # than at a fixed inset, so it is no longer confined to the left
                # quarter -- a short label on a wide button pushes it toward the
                # middle. What must still hold is that it stays in the left half
                # and never reaches the centre, where it would collide with the
                # text the engine draws there.
                rightmost = max(index % TEXTURE_WIDTH for index in opaque)
                if rightmost >= TEXTURE_WIDTH // 2:
                    raise AssertionError(
                        f"{archive_path.name}: {target.resref} badge reaches the "
                        f"centre of the button (x={rightmost} of {TEXTURE_WIDTH}); "
                        "it would sit under the label")

                # Orientation, decided against the source artwork rather than
                # a constant. Only glyphs whose letter is asymmetric enough can
                # settle it; the rest are skipped rather than asserted loosely.
                art_name = GLYPH_ART.get(target.glyph)
                art_path = GLYPH_ART_DIR / art_name if art_name else None
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
                            if inverted < upright:
                                raise AssertionError(
                                    f"{archive_path.name}: {target.resref} matches a MIRRORED "
                                    f"{art_path.name} better than the upright one "
                                    f"({inverted:.4f} < {upright:.4f}); the texture is "
                                    "stored upside down")
                checked += 1

            verify_placement_manifest(archive, archive_path.name, names, gui_cache)

    print(
        f"Controller prompts OK: {len(archives)} archives, "
        f"{checked} target textures, {len(PROMPT_TARGETS)} verified control mappings each, "
        f"placement manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
