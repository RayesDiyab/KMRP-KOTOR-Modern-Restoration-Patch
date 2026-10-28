#!/usr/bin/env python3
"""Build the files the standalone controller patch embeds: the controller's layout
changes and art, made for the game's ORIGINAL interface.

KMRP's own patch carries these inside its resolution sets, made from KMRP's scaled
layouts. The standalone controller patch ("KOTOR 1 Native Controller Mod + Xbox HUD.kpatch",
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
import build_tab_arrows                                                 # noqa: E402
import build_xbox_hud_art                                               # noqa: E402
from build_controller_layout import (DIALOG_BADGE_TAG, add_confirm_badge,  # noqa: E402
                                     add_entry as add_controller_layout_entry,
                                     build_art as build_controller_layout_art,
                                     build_gui as build_controller_layout_gui)
from build_controller_prompt_textures import (BADGE_BOXES_NAME, FAMILY_LETTERS,  # noqa: E402
                                              GLYPH_FAMILIES, PROMPT_MANIFEST_NAME,  # noqa: E402
                                              PROMPT_TARGETS, build_prompt_textures,  # noqa: E402
                                              build_square_glyph_tga, family_resref,  # noqa: E402
                                              register_scene)
from build_scaled_fonts import export_font_txis                         # noqa: E402
from build_xbox_hud import DISENGAGE_FILL as XBOX_HUD_DISENGAGE_FILL    # noqa: E402
from build_xbox_hud import PAUSE_FILL as XBOX_HUD_PAUSE_FILL            # noqa: E402
from prepare_universal_resources import (COMBAT_CUES, CONTAINER_SCREEN, R3_CUE_FILL,  # noqa: E402
                                         R3_CUE_GLYPH, R3_CUE_SCREENS, SWAP_CUE_ASPECT, SWAP_CUE_FILL,
                                         SWAP_CUE_GLYPH, SWAP_CUE_SCREEN, TAB_CUES,
                                         TAB_CUE_SCREEN, add_combat_cues,
                                         add_party_switch_cue, add_subtab_swap_cue,
                                         add_tab_strip_cues, fit_container_to_caption)

VANILLA_GUI = ROOT / "build-inputs/vanilla-gui"
TEXTURE_PACK = ROOT / "build-inputs/swpc_tex_gui.erf"
OUT = ROOT / "build/controller-standalone"
# XBOX_HUD_DISENGAGE_FILL is the button in the Xbox-style HUD's combat-mode message:
# B, which disengages there. The Xbox-style HUD needs no file besides that glyph: the
# module lays the live HUD out itself (K1XboxHud.cpp, from tools/build_xbox_hud.py's
# table).
GUI_TYPE = 2047
EXPECTED_GUI_FILES = 84
# The main menu the game loads above 640x480. Its four files (8x6, 10x7, 12x9, 16x12)
# hold one geometry (asserted below); mainmenu.gui is the 640x480 one, 210x22 buttons
# against these 235x24, and the badges are made for the size nearly everyone runs.
LAYOUT_SCREEN = (800, 600)
MAIN_MENU_LOADED = ("mainmenu8x6.gui", "mainmenu10x7.gui", "mainmenu12x9.gui", "mainmenu16x12.gui")


def build_swoop_prompt_tga(family: str) -> bytes:
    """A glyph inside Plane14's measured UV window, without changing the model."""
    from io import BytesIO
    from PIL import Image

    # m17mg_camera.mdl Plane14: u=.185497..842288, v=.134816..867799.
    # The TGA is bottom-up; Pillow's canvas uses the top-left corner.
    from build_controller_prompt_textures import SCENES
    tile_tga = build_square_glyph_tga("A", 84, 94, family=family)
    tile = Image.open(BytesIO(tile_tga))
    canvas = Image.new("RGBA", (128, 128))
    canvas.paste(tile, (24, 17))
    canvas = canvas.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, 128, 128, 32, 0x08)
    tga = header + canvas.tobytes("raw", "BGRA") + b"\0" * 8 + b"TRUEVISION-XFILE.\0"
    # The module draws it for the screen's size (KmrpDrawnPictureK1, vendor/K1XboxControls.cpp):
    # the tile's A where the tile is pasted.
    parts = [(f, glyph, left + 24, top + 17, w, h)
             for f, glyph, left, top, w, h in SCENES[hashlib.sha256(tile_tga).hexdigest()][2]]
    return register_scene(tga, 128, 128, parts)


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
    # Each badge's glyph and its exact box, for K1ControllerBadgeShapes.inc (badge_shapes),
    # and every glyph's outlines: the module draws each badge again at the size of the label
    # it shows it on (issue 68, vendor/K1XboxControls.cpp).
    # The boxes are compiled into the module, so they go beside the bank, not into it.
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(work / "prompts" / BADGE_BOXES_NAME, OUT / BADGE_BOXES_NAME)
    glyph_bank = work / "prompts" / GLYPH_BANK_NAME
    glyph_bank.write_bytes(pack_glyphs())
    prompts.append(glyph_bank)

    art = work / "art"
    art.mkdir()
    common = []
    for family in GLYPH_FAMILIES:
        swoop = art / f"{family_resref('kmrpp_swoop', family)}.tga"
        swoop.write_bytes(build_swoop_prompt_tga(family))
        common.append(swoop)
        # The HUD's Disengage badge and the Xbox-style HUD's combat-mode message
        # show one B picture, so it is made once. The pause notice's lighter RT
        # is not shown on Windows since Pause moved to LB (issue 49, 2026-10-19);
        # it is still made for the Mac's patch, which shows it until it moves too
        # (docs/macos-changes-from-windows.md).
        cues = dict([(R3_CUE_FILL, R3_CUE_GLYPH)] + [(fill, glyph) for _, fill, glyph in TAB_CUES]
                    + [(fill, glyph) for _, fill, glyph, _ in COMBAT_CUES]
                    + [(XBOX_HUD_DISENGAGE_FILL, "B"), (XBOX_HUD_PAUSE_FILL, "RT_NOTICE")])
        for fill, glyph in cues.items():
            path = art / f"{family_resref(fill, family)}.tga"
            # The tab strip's two cues are arrows in the game's style, not the
            # family's trigger pictures (tools/build_tab_arrows.py; this patch only).
            if glyph in ("LT", "RT"):
                # Drawn by the module at the size it is shown, from its outlines
                # (controller_drawn_art.tab_arrow, in kmrp-glyphs.bin as TAB_LEFT/TAB_RIGHT).
                size = build_tab_arrows.SIZE
                path.write_bytes(register_scene(build_tab_arrows.arrow_tga(family, glyph == "RT"), size, size,
                                                [(family, "TAB_RIGHT" if glyph == "RT" else "TAB_LEFT",
                                                  0, 0, size, size)]))
            else:
                path.write_bytes(build_square_glyph_tga(glyph, family=family))
            common.append(path)
        path = art / f"{family_resref(SWAP_CUE_FILL, family)}.tga"
        path.write_bytes(build_square_glyph_tga(SWAP_CUE_GLYPH, 256, 256 // SWAP_CUE_ASPECT, family=family))
        common.append(path)
    common += build_controller_layout_art(art / "layout")
    # The Xbox-style HUD's frames, drawn (not the game's art): tools/build_xbox_hud_art.py.
    common += build_xbox_hud_art.build(art / "xbox-hud")

    files = {name: current[name] for name in sorted(changed)}
    for path in prompts + common:
        if path.name == PROMPT_MANIFEST_NAME:
            continue   # for KMRP's installer, which re-centres badges; nothing reads it here
        if path.name.lower() in files:
            raise ValueError(f"two steps wrote {path.name}")
        files[path.name.lower()] = path
    # The outlines again, now with what every texture made from them shows (scenes_for).
    scenes = scenes_for(files)
    glyph_bank.write_bytes(pack_glyphs(scenes))
    # The badges and the pictures made from one glyph are drawn by the module at the size
    # they are shown (vendor/K1XboxControls.cpp), so the patch does not carry them
    # (2026-10-27). They are still made, for the badge table (badge_shapes) and the tests,
    # into build/controller-standalone/made (pack). With --carry-drawn they are carried
    # again, as they were until then: the module shows a carried one wherever drawing fails
    # (the maintainer, the same day: keep the fallback in the repository, in case they are
    # wanted back).
    unshipped = {f"{scene[0]}.tga" for scene in scenes}
    # A drawn picture's TXI goes with it (the HUD frames' "clamp 3"; the module writes
    # its own beside each picture it draws).
    unshipped |= {f"{scene[0]}.txi" for scene in scenes}
    unshipped |= {path.name.lower() for path in prompts if path.suffix.lower() == ".tga"}
    UNSHIPPED.clear()
    if not CARRY_DRAWN:
        UNSHIPPED.update({name: files.pop(name) for name in sorted(unshipped) if name in files})
    return files


# --carry-drawn: carry the drawn pictures in the patch too, as a fallback (make).
CARRY_DRAWN = False


# Made by make() and not carried in the patch: name -> path (pack writes them to out/made).
UNSHIPPED: dict = {}


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
    made = out / "made"
    shutil.rmtree(made, ignore_errors=True)
    made.mkdir()
    for name, path in UNSHIPPED.items():
        shutil.copyfile(path, made / name)
    kinds = {}
    for name in files:
        kinds[name.rsplit(".", 1)[-1]] = kinds.get(name.rsplit(".", 1)[-1], 0) + 1
    return {"files": len(entries), "by_kind": kinds, "bytes": len(blob), "sha256": build_id.upper()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extract", type=Path, metavar="GAME",
                        help="Write the game's layout files to build-inputs/vanilla-gui and stop")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--carry-drawn", action="store_true",
                        help="carry the badges and one-glyph pictures the module draws at run time "
                             "in the patch as well, for it to show wherever drawing fails")
    parser.add_argument("--sdl", type=Path, default=ROOT / "build/deps/kmrp-sdl3.dll")
    args = parser.parse_args()
    logging.disable(logging.DEBUG)      # pykotor and PIL narrate every struct and chunk
    global CARRY_DRAWN
    CARRY_DRAWN = args.carry_drawn
    if args.extract:
        print(f"{extract(args.extract)} layout files written to {VANILLA_GUI}")
        return 0
    with tempfile.TemporaryDirectory(prefix="kmrp-controller-assets-") as temp:
        result = pack(make(Path(temp)), args.sdl, args.out)
    print(result)
    return 0



# The area each badge was made for. A badge is a texture stretched over the area its
# button's border fills, so it is round only on a button of the shape it was made
# for. The module compares that shape with the live button's and, where another patch
# has reshaped the button, draws the badge on a label of the right shape instead
# (K1XboxControls.cpp, K1BadgeOverlay). The textures themselves are padded to powers
# of two and do not say.
BADGE_SHAPES = ROOT / "src/controller-native/K1ControllerBadgeShapes.inc"


GLYPH_BANK_NAME = "kmrp-glyphs.bin"


def scenes_for(files: dict) -> list:
    """(texture name, width, height, [(glyph name, left, top, width, height)]) for every texture
    among `files` that build_square_glyph_tga made: the glyph it shows and its box, in the
    texture's pixels. The module draws these again at the size each control shows them."""
    from build_controller_prompt_textures import SCENES
    out = []
    for name, path in sorted(files.items()):
        if not name.endswith(".tga"):
            continue
        scene = SCENES.get(hashlib.sha256(path.read_bytes()).hexdigest())
        if scene is None:
            continue
        width, height, parts, stretch, cap = scene
        out.append((name[:-4], width, height,
                    [(f"{FAMILY_LETTERS[family] if family else '-'}/{glyph}", left, top, w, h)
                     for family, glyph, left, top, w, h in parts], stretch, cap))
    return out


def pack_glyphs(scenes: list = ()) -> bytes:
    """Every family's glyphs for the module: "KGLY", u32 count, then per glyph its name (u16
    length, "<family letter>/<glyph>", as "p/RT_NOTICE") and its outlines as
    controller_glyphs.pack writes them, which kmrp_glyph_read reads. Then "SCEN", u32 count,
    per scene its texture's name (u16 length, ASCII), u32 width and height, u32 parts, u32
    flags (1: each glyph fills its box, else it keeps its proportions in it) and u32 cap (the
    most pixels it is drawn on its longer side, 0 for any), per part the glyph's name (u16
    length) and its box (4 x i32: left, top, width, height in the texture's pixels)
    (scenes_for)."""
    import controller_drawn_art
    import controller_glyphs
    import controller_layout_backdrop
    out = b"KGLY"
    entries = []

    def add(name: str, g: dict) -> None:
        entries.append(struct.pack("<H", len(name)) + name.encode("ascii") + controller_glyphs.pack(g))

    for family, (_, art) in GLYPH_FAMILIES.items():
        for glyph in sorted(art):
            g = controller_glyphs.glyph(family, glyph)
            if g is None:
                raise ValueError(f"no {family} outlines for {glyph}")
            add(f"{FAMILY_LETTERS[family]}/{glyph}", g)
        # The patch's own drawn pictures: the tab strip's arrows, named for the family.
        left, right = build_tab_arrows.NAMES[family]
        add(f"{FAMILY_LETTERS[family]}/TAB_LEFT", controller_drawn_art.tab_arrow(left, True))
        add(f"{FAMILY_LETTERS[family]}/TAB_RIGHT", controller_drawn_art.tab_arrow(right, False))
        # The Controller Layout's board: the silhouette with its glow, and the leader lines.
        body, leaders, _ = controller_drawn_art.layout_diagram(family)
        add(f"{FAMILY_LETTERS[family]}/LAYOUT_BODY", body)
        add(f"{FAMILY_LETTERS[family]}/LAYOUT_LINES", leaders)
    # And the remapping screen's symbols and the Controller Layout's backdrop and edge art,
    # the same for every controller.
    for name, g in controller_drawn_art.remap_marks().items():
        add(f"-/{name}", g)
    for name, g in controller_layout_backdrop.outlines().items():
        add(f"-/{name}", g)
    # And the Xbox-style HUD's frames (tools/build_xbox_hud_art.py).
    for name, g in build_xbox_hud_art.outlines().items():
        add(f"-/{name}", g)
    out += struct.pack("<I", len(entries)) + b"".join(entries)
    out += b"SCEN" + struct.pack("<I", len(scenes))
    for texture, width, height, parts, stretch, cap in scenes:
        out += struct.pack("<H", len(texture)) + texture.encode("ascii")
        out += struct.pack("<IIIII", width, height, len(parts), 1 if stretch else 0, cap)
        for glyph, left, top, w, h in parts:
            out += struct.pack("<H", len(glyph)) + glyph.encode("ascii") + struct.pack("<4i", left, top, w, h)
    return out


def badge_shapes(files: Path = OUT / "files") -> str:
    from build_controller_prompt_textures import fill_inset
    rows, cache = [], {}
    # The glyph and its exact box, as build_prompt_textures placed it (kmrp_badge_boxes.txt).
    boxes = {}
    for line in (files.parent / BADGE_BOXES_NAME).read_text(encoding="utf-8").splitlines():
        resref, glyph, left, top, width, height = line.split()
        boxes[resref] = (glyph, int(left), int(top), int(width), int(height))
    for target in PROMPT_TARGETS:
        gui = files / target.gui
        if not gui.exists():
            gui = VANILLA_GUI / target.gui       # a screen this patch leaves as the game has it
        if target.gui == "mainmenu.gui":
            # The main menu's badges are made from the file the game loads above
            # 640x480 (build(), MAIN_MENU_LOADED), not from mainmenu.gui: there Quit is
            # 210x22 with no corner art, like the other four, where mainmenu.gui has it
            # 210x27 with a 2 px border. Until 2026-10-09 this table read mainmenu.gui,
            # gave Quit's texture, which is the other rows' byte for byte, a made area
            # of 206x23, and the module drew its A in those proportions: 39 wide and
            # 43 tall beside KMRP at 3440x1440 where the other rows' is 39 by 41 (the
            # maintainer saw it, "stretched vertically").
            gui = VANILLA_GUI / MAIN_MENU_LOADED[0]
        if target.size_like or not gui.exists():
            continue                # made for another control's size, or not a screen of the game's
        if target.gui not in cache:
            cache[target.gui] = {c.get_string("TAG"): c for c in read_gff(gui).root.get_list("CONTROLS")}
        control = cache[target.gui].get(target.tag)
        if control is None:
            continue
        extent = control.get_struct("EXTENT")
        inset = fill_inset(control.get_struct("BORDER") if control.exists("BORDER") else None)
        width, height = extent.get_int32("WIDTH") - 2 * inset, extent.get_int32("HEIGHT") - 2 * inset
        if width > 0 and height > 0:
            # Where the glyph stands across that area, in thousandths: the middle of
            # the texture's drawn columns (the texture is stretched over the area).
            from PIL import Image
            art = files.parent / "made" / (target.resref + ".tga")
            box = Image.open(art).convert("RGBA").split()[3].point(lambda v: 255 if v > 40 else 0).getbbox() if art.exists() else None
            if box is None:
                continue
            across = Image.open(art).width
            if target.resref not in boxes:
                raise ValueError(f"{BADGE_BOXES_NAME} has no box for {target.resref}")
            rows.append((target.resref, width, height, round(500 * (box[0] + box[2]) / across),
                         round(1000 * (box[2] - box[0]) / across)) + boxes[target.resref])
    names = [row[0] for row in rows]
    if len(set(names)) != len(names):
        raise ValueError("A badge texture is used on two buttons")
    lines = ["// Generated by tools/build_controller_assets.py --badge-shapes. Do not edit.",
             "// The area, in layout pixels, each badge texture was made for: the button's",
             "// extent less what its border keeps clear; where the glyph's middle stands",
             "// across it, and how wide the glyph is, in thousandths of the area's width",
             "// (Test-ControllerKpatch.py checks this file against the built layouts and",
             "// textures); and which glyph it is and its exact box in that area (left, top,",
             "// width, height in hundred-thousandths of the area), as the build placed it,",
             "// from which the module draws the glyph at the size it shows it (issue 68).",
             "constexpr BadgeShape kBadgeShapes[] = {"]
    lines += ['    {"%s", %d, %d, %d, %d, "%s", %d, %d, %d, %d},' % row for row in sorted(rows)]
    lines.append("};")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if "--badge-shapes" in sys.argv:
        logging.disable(logging.DEBUG)
        BADGE_SHAPES.write_text(badge_shapes(), encoding="utf-8", newline="\n")
        print(f"wrote {BADGE_SHAPES}")
        raise SystemExit(0)
    raise SystemExit(main())
