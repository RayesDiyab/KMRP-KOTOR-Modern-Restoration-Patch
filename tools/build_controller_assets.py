#!/usr/bin/env python3
"""Build the files the standalone controller patch embeds: the controller's layout
changes and art, made for the game's ORIGINAL interface.

KMRP's own patch carries these inside its resolution sets, made from KMRP's scaled
layouts. The standalone controller patch ("KMRP Controller.kpatch",
tools/build_controller_kpatch.py) runs without KMRP, on the layouts the game ships,
so the same steps are run here on those:

  the R3 party cue                abilities, character, equip, inventory
  the swap-tabs cue               abilities
  the LT and RT cues              top
  the Controller Layout entry     optgameplay, and the screen itself (kmrplayout)
  the travelling A                confirm, dialog
  X and Y beside the HUD's combat buttons    every mipc*.gui
  the Container's column          container, where a caption and its badge do not fit
  the button badges               one texture per button and controller family

The game's menus are one 640x480 layout at every resolution it offers, and its four
main-menu files above 640x480 share one geometry, so one set serves them all. Only
the HUD has a file per resolution, and every one of them gets the combat cues.

Inputs are game-derived and never committed (build-inputs/README.md):

  build-inputs/vanilla-gui/*.gui    the game's own layout files, written by --extract
  build-inputs/swpc_tex_gui.erf     for the game's own font metrics

Output, under ignored build/controller-standalone/:

  controller-assets.bin             the bank the module embeds (KCAST001)
  ControllerAssets.generated.h      its build id
  controller-assets.rc              the resource script
  files/                            the same files loose, for inspection and tests

Usage:
    python tools/build_controller_assets.py --extract "C:\\path\\to\\clean game"
    python tools/build_controller_assets.py

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pykotor.resource.formats.gff import GFFList, read_gff, write_gff                   # noqa: E402

import build_native_assets                                              # noqa: E402
from build_controller_layout import (DIALOG_BADGE_TAG, add_confirm_badge,  # noqa: E402
                                     add_entry as add_controller_layout_entry,
                                     build_art as build_controller_layout_art,
                                     build_gui as build_controller_layout_gui)
from build_controller_prompt_textures import (GLYPH_FAMILIES, PROMPT_MANIFEST_NAME,  # noqa: E402
                                              PROMPT_TARGETS, build_prompt_textures,  # noqa: E402
                                              build_square_glyph_tga, family_resref)
from build_scaled_fonts import export_font_txis                         # noqa: E402
from build_xbox_hud import build as build_xbox_hud                      # noqa: E402
from prepare_universal_resources import (COMBAT_CUES, CONTAINER_SCREEN, R3_CUE_FILL,  # noqa: E402
                                         R3_CUE_SCREENS, SWAP_CUE_ASPECT, SWAP_CUE_FILL,
                                         SWAP_CUE_GLYPH, SWAP_CUE_SCREEN, TAB_CUES,
                                         TAB_CUE_SCREEN, add_combat_cues,
                                         add_party_switch_cue, add_subtab_swap_cue,
                                         add_tab_strip_cues, fit_container_to_caption)

VANILLA_GUI = ROOT / "build-inputs/vanilla-gui"
TEXTURE_PACK = ROOT / "build-inputs/swpc_tex_gui.erf"
OUT = ROOT / "build/controller-standalone"
# An Xbox-style HUD layout's name: its original's, with this in place of "mipc".
XBOX_HUD_PREFIX = "kmxh"
# The button in the Xbox-style HUD's combat-mode message: B, which disengages there.
XBOX_HUD_DISENGAGE_FILL = "kmrpb_cmbt"
GUI_TYPE = 2047
EXPECTED_GUI_FILES = 84
# The main menu the game loads above 640x480. Its four files (8x6, 10x7, 12x9, 16x12)
# hold one geometry (asserted below); mainmenu.gui is the 640x480 one, 210x22 buttons
# against these 235x24, and the badges are made for the size nearly everyone runs.
LAYOUT_SCREEN = (800, 600)
MAIN_MENU_LOADED = ("mainmenu8x6.gui", "mainmenu10x7.gui", "mainmenu12x9.gui", "mainmenu16x12.gui")


def extract(game: Path) -> int:
    """Write the game's .gui files to build-inputs/vanilla-gui, from chitin.key."""
    key = (game / "chitin.key").read_bytes()
    if key[:8] != b"KEY V1  ":
        raise ValueError(f"{game / 'chitin.key'} is not a KEY V1 file")
    bif_count, key_count, bif_offset, key_offset = struct.unpack_from("<IIII", key, 8)
    bifs = []
    for i in range(bif_count):
        _, name_offset, name_length, _ = struct.unpack_from("<IIHH", key, bif_offset + i * 12)
        bifs.append(key[name_offset:name_offset + name_length].rstrip(b"\0").decode().replace("\\", "/"))
    VANILLA_GUI.mkdir(parents=True, exist_ok=True)
    loaded = {}
    count = 0
    for i in range(key_count):
        name, kind, rid = struct.unpack_from("<16sHI", key, key_offset + i * 22)
        if kind != GUI_TYPE:
            continue
        bif = bifs[rid >> 20]
        data = loaded.setdefault(bif, (game / bif).read_bytes())
        _, _, table = struct.unpack_from("<III", data, 8)
        _, offset, size, _ = struct.unpack_from("<IIII", data, table + (rid & 0xFFFFF) * 16)
        (VANILLA_GUI / (name.rstrip(b"\0").decode().lower() + ".gui")).write_bytes(data[offset:offset + size])
        count += 1
    if count != EXPECTED_GUI_FILES:
        raise ValueError(f"Extracted {count} layout files, expected {EXPECTED_GUI_FILES}")
    return count


def _extents(path: Path) -> dict:
    result = {}
    for control in read_gff(path).root.get_list("CONTROLS"):
        e = control.get_struct("EXTENT")
        result[control.get_string("TAG")] = (e.get_int32("WIDTH"), e.get_int32("HEIGHT"))
    return result


def add_dialog_badge(source: Path, output: Path, label_source: Path) -> None:
    """The travelling A beside the highlighted dialogue reply."""
    add_confirm_badge(source, output, label_source, tag=DIALOG_BADGE_TAG)


def make(work: Path) -> dict:
    """Run the controller's layout and art steps on the game's own layouts. Returns
    name -> path of every file the patch carries."""
    sources = {p.name.lower(): p for p in sorted(VANILLA_GUI.glob("*.gui"))}
    if len(sources) != EXPECTED_GUI_FILES:
        raise ValueError(f"{VANILLA_GUI} holds {len(sources)} layout files, expected "
                         f"{EXPECTED_GUI_FILES}; run with --extract <clean game folder>")
    current = dict(sources)          # name -> the file as it stands after the steps so far
    changed = set()

    def step(name: str, function, *args) -> object:
        target = work / "gui" / function.__name__ / name
        target.parent.mkdir(parents=True, exist_ok=True)
        result = function(current[name], target, *args)
        if target.exists():
            current[name] = target
            changed.add(name)
        return result

    for name in R3_CUE_SCREENS:
        if not step(name, add_party_switch_cue):
            raise ValueError(f"{name}: the R3 cue was not placed")
    if not step(SWAP_CUE_SCREEN, add_subtab_swap_cue):
        raise ValueError("the sub-tab swap cue was not placed")
    if step(TAB_CUE_SCREEN, add_tab_strip_cues) != len(TAB_CUES):
        raise ValueError("the tab-strip cues were not all placed")
    step("optgameplay.gui", add_controller_layout_entry)
    controls_gui = current["optgameplay.gui"]
    step("confirm.gui", add_confirm_badge, controls_gui)
    step("dialog.gui", add_dialog_badge, controls_gui)
    huds = [name for name in sorted(current) if name.startswith("mipc")]
    cued = [name for name in huds if step(name, add_combat_cues)]
    if cued != huds:
        raise ValueError(f"the combat cues reached {cued} of {huds}")

    # The game's own button font, at its own size.
    fonts = work / "fonts"
    fonts.mkdir()
    txis = {p.name.lower(): p for p in export_font_txis(TEXTURE_PACK, fonts, 1.0)}
    caption_txi = txis.get("dialogfont16x16.txi")
    if caption_txi is None:
        raise ValueError("the texture pack has no dialogfont16x16 metrics")

    # The Controller Layout screen is a panel of its own, and its design is 760 units
    # wide: on the Gameplay screen's 640x480 its captions were cut short ("ally / Prev
    # tab", seen in the scratch game on 2026-10-05). It is laid out for 800x600
    # instead, the size of the game's own main-menu panel above 640x480 and its
    # smallest listed resolution; the game centres a panel on a larger screen.
    layout_gui = work / "gui" / "kmrplayout.gui"
    build_controller_layout_gui(controls_gui, layout_gui, *LAYOUT_SCREEN, caption_txi,
                                separate_top=True)
    # build_gui keeps its source's root, which in KMRP's sets is already the whole
    # screen. Here it is the Gameplay screen's 640x480, which cut the 800x600 layout
    # off at the right and bottom (seen 2026-10-05), so the root is given the size the
    # layout was made for.
    layout = read_gff(layout_gui)
    extent = layout.root.get_struct("EXTENT")
    for field, value in (("LEFT", 0), ("TOP", 0), ("WIDTH", LAYOUT_SCREEN[0]), ("HEIGHT", LAYOUT_SCREEN[1])):
        extent.set_int32(field, value)
    layout.root.set_struct("EXTENT", extent)
    write_gff(layout, layout_gui)
    current["kmrplayout.gui"] = layout_gui
    changed.add("kmrplayout.gui")

    widened = step(CONTAINER_SCREEN, fit_container_to_caption, caption_txi)

    # The Xbox-style HUD: a twin of every HUD layout the executable loads, made from
    # the layout as it stands (with the combat cues), under a name of its own. The
    # module copies the twins over the originals in its temporary folder when the
    # option is on (K1ControllerStandalone.cpp). The HUD's constructor (0x0068C100)
    # names mipc28x6, mipc210x7, mipc212x9, mipc212x10 and mipc216x12; the data has
    # no mipc212x10, and its mipc8x6 to mipc16x12 are an older set nothing loads.
    xbox_huds = {}
    for name in (name for name in huds if name.startswith("mipc2")):
        twin = work / "gui" / "xbox-hud" / (XBOX_HUD_PREFIX + name[len("mipc"):])
        twin.parent.mkdir(parents=True, exist_ok=True)
        build_xbox_hud(current[name], twin)
        xbox_huds[twin.name] = twin

    # The badges, from the buttons as the game will draw them: the main menu's from
    # the file it loads above 640x480, under the name the generator looks up.
    badged = {t.tag for t in PROMPT_TARGETS if t.gui == "mainmenu.gui"}
    loaded = [{tag: size for tag, size in _extents(sources[name]).items() if tag in badged}
              for name in MAIN_MENU_LOADED]
    if len(loaded[0]) != len(badged) or any(other != loaded[0] for other in loaded[1:]):
        raise ValueError("the game's main-menu layouts no longer share their buttons' sizes")
    prompt_inputs = dict(current)
    alias = work / "gui" / "mainmenu-loaded" / "mainmenu.gui"
    alias.parent.mkdir(parents=True)
    # The generator checks each button's place in mainmenu.gui's own control list,
    # which the larger files order differently. So it is given the loaded file with
    # its controls in mainmenu.gui's order: their sizes AND their borders are the
    # loaded file's. (Until later on 2026-10-05 this copied only the sizes onto
    # mainmenu.gui's controls, through get_struct(), which returns a copy: nothing
    # was written, and the badges were made for 210x22 with mainmenu.gui's borders.
    # testing/regression/Test-ControllerKpatch.py found it, as a Quit badge 12% off
    # round and a focused texture where the loaded file needs none.)
    order = [c.get_string("TAG") for c in read_gff(sources["mainmenu.gui"]).root.get_list("CONTROLS")]
    menu = read_gff(sources[MAIN_MENU_LOADED[0]])
    by_tag = {c.get_string("TAG"): c for c in menu.root.get_list("CONTROLS")}
    if sorted(by_tag) != sorted(order):
        raise ValueError("mainmenu.gui and the loaded main menu no longer hold the same controls")
    reordered = GFFList()
    for tag in order:
        reordered.append(by_tag[tag])
    menu.root.set_list("CONTROLS", reordered)
    write_gff(menu, alias)
    prompt_inputs["mainmenu.gui"] = alias
    prompts = build_prompt_textures(list(prompt_inputs.values()) + [caption_txi],
                                    work / "prompts", widened={CONTAINER_SCREEN: widened or 0},
                                    fill_insets=True)

    art = work / "art"
    art.mkdir()
    common = []
    for family in GLYPH_FAMILIES:
        cues = [(R3_CUE_FILL, "R3")] + [(fill, glyph) for _, fill, glyph in TAB_CUES] \
            + [(fill, glyph) for _, fill, glyph, _ in COMBAT_CUES] + [(XBOX_HUD_DISENGAGE_FILL, "B")]
        for fill, glyph in cues:
            path = art / f"{family_resref(fill, family)}.tga"
            path.write_bytes(build_square_glyph_tga(glyph, family=family))
            common.append(path)
        path = art / f"{family_resref(SWAP_CUE_FILL, family)}.tga"
        path.write_bytes(build_square_glyph_tga(SWAP_CUE_GLYPH, 256, 256 // SWAP_CUE_ASPECT, family=family))
        common.append(path)
    common += build_controller_layout_art(art / "layout")

    files = {name: current[name] for name in sorted(changed)}
    files.update(xbox_huds)
    for path in prompts + common:
        if path.name == PROMPT_MANIFEST_NAME:
            continue   # for KMRP's installer, which re-centres badges; nothing reads it here
        if path.name.lower() in files:
            raise ValueError(f"two steps wrote {path.name}")
        files[path.name.lower()] = path
    return files


def pack(files: dict, sdl: Path, out: Path) -> dict:
    """The bank: KCAST001, u32 file count, then per file a name (u16 length, ASCII),
    its SHA-256, its size, its compressed size and its XPRESS-Huffman stream."""
    compressor = build_native_assets.Compressor()
    try:
        entries = dict(files)
        entries["kmrp-sdl3.dll"] = sdl
        blob = bytearray(b"KCAST001" + struct.pack("<I", len(entries)))
        for name in sorted(entries):
            data = entries[name].read_bytes()
            packed = compressor.compress(data)
            blob += build_native_assets.text(name) + hashlib.sha256(data).digest()
            blob += struct.pack("<II", len(data), len(packed)) + packed
    finally:
        compressor.close()
    out.mkdir(parents=True, exist_ok=True)
    (out / "controller-assets.bin").write_bytes(blob)
    build_id = hashlib.sha256(blob).hexdigest()
    (out / "ControllerAssets.generated.h").write_text(
        f'#pragma once\n#define KMRP_CONTROLLER_ASSET_BUILD L"{build_id}"\n')
    (out / "controller-assets.rc").write_text('101 RCDATA "controller-assets.bin"\n')
    loose = out / "files"
    shutil.rmtree(loose, ignore_errors=True)
    loose.mkdir()
    for name, path in files.items():
        shutil.copyfile(path, loose / name)
    kinds = {}
    for name in files:
        kinds[name.rsplit(".", 1)[-1]] = kinds.get(name.rsplit(".", 1)[-1], 0) + 1
    return {"files": len(entries), "by_kind": kinds, "bytes": len(blob), "sha256": build_id.upper()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extract", type=Path, metavar="GAME",
                        help="Write the game's layout files to build-inputs/vanilla-gui and stop")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--sdl", type=Path, default=ROOT / "build/deps/kmrp-sdl3.dll")
    args = parser.parse_args()
    logging.disable(logging.DEBUG)      # pykotor and PIL narrate every struct and chunk
    if args.extract:
        print(f"{extract(args.extract)} layout files written to {VANILLA_GUI}")
        return 0
    with tempfile.TemporaryDirectory(prefix="kmrp-controller-assets-") as temp:
        result = pack(make(Path(temp)), args.sdl, args.out)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
