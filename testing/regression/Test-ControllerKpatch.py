#!/usr/bin/env python3
"""Checks on the standalone controller patch, dist/controller/KMRP Controller.kpatch.

What it proves, from the built files and the sources (it starts no game):

  1. The package is what tools/build_controller_kpatch.py would write from the
     sources: its hooks, its manifest, its licences, and a module that exports every
     callback a hook names.
  2. It is a controller patch and nothing else: no hook of KMRP's core (the engine
     recipe's sites, the keyboard navigation, the memory and movie fixes), no static
     hook, and KMRP's own patch among its conflicts.
  3. No hook of it overlaps a hook of KMRP's own patch at a different address span:
     every site it holds, KMRP holds identically or not at all.
  4. The file bank holds exactly the layout files the controller changes and the
     art, in all four controller families, and nothing a controller does not need.
  5. Badge shape: for every badged button of the game's own layouts, the badge
     texture maps to a round badge in the area that button's border really fills,
     normal and focused, and a focused-state texture exists exactly where the two
     borders fill different areas (docs/controller-standalone.md, section 3).
  6. The Xbox-style HUD: a twin of every HUD layout the game loads, holding the
     same controls, with what the module's half (K1XboxHud.cpp) relies on: the seven
     slots in one row at one pitch, the first personal slot's frame at the size the
     module recognises the layout by, the action box drawn before the description
     and everything either on the screen or parked far off it.

Needs the built package (src/controller-native/build_controller_standalone.cmd and
tools/build_controller_kpatch.py) and build-inputs/vanilla-gui.

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import logging
import struct
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
logging.disable(logging.DEBUG)

from pykotor.resource.formats.gff import read_gff          # noqa: E402

import build_controller_assets as assets                    # noqa: E402
import build_controller_kpatch as package                   # noqa: E402
import build_controller_prompt_textures as prompts          # noqa: E402
import build_native_kpatch as kmrp                          # noqa: E402
import build_xbox_hud as xbox_hud                           # noqa: E402
import kmrp_controller                                      # noqa: E402

PACKAGE = ROOT / "dist/controller" / package.NAME
FILES = ROOT / "build/controller-standalone/files"
FAMILIES = "psnd"
failures = []


def check(condition: bool, text: str) -> None:
    print(("ok    " if condition else "FAIL  ") + text)
    if not condition:
        failures.append(text)


def alpha_box(tga: bytes):
    """Bounding box of the non-transparent pixels of a bottom-up 32-bit TGA, in
    texture pixels from the top left: (left, top, width, height), or None."""
    width, height = struct.unpack_from("<HH", tga, 12)
    pixels = tga[18:18 + width * height * 4]
    xs, ys = [], []
    for y in range(height):
        row = pixels[y * width * 4:(y + 1) * width * 4]
        hit = [x for x in range(width) if row[x * 4 + 3] > 96]
        if hit:
            xs += (hit[0], hit[-1])
            ys.append(height - 1 - y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def main() -> int:
    # 1. The package against its sources.
    result = package.validate(PACKAGE)
    check(result["hooks"] == len(package.hooks()) == 33, f"the package carries {result['hooks']} hooks, all from the sources")
    with zipfile.ZipFile(PACKAGE) as z:
        manifest = tomllib.loads(z.read("manifest.toml").decode())["patch"]
        packed = tomllib.loads(z.read(package.HOOKS).decode())["hooks"]

    # 2. A controller patch and nothing else.
    mine = {h["address"]: h for h in package.hooks()}
    # By what a hook does, not where: the core's two frame stand-ins sit at the
    # controller's frame sites, and this patch holds those sites with the
    # controller's own frames.
    core = [h for h in kmrp_controller.installable_hooks() if kmrp_controller.install_of(h) != "controller"]
    core_functions = {h["function"] for h in core if "function" in h}
    core_bytes = {h["address"] for h in core if "function" not in h}
    check(not (core_functions & package.functions()) and not (core_bytes & set(mine)),
          f"none of the {len(core)} core hooks (keyboard, memory, popups, movies) is in it")
    engine = [h for h in kmrp._table() if h.get("function") != package.RESOURCE_HOOK]
    check(not any(h["address"] in mine for h in engine),
          f"none of the {len(engine)} resolution and layout hooks of KMRP's module is in it")
    check(all(h.get("type", "detour") == "detour" for h in packed), "every hook is a detour: nothing is written to the file on disk")
    check("kmrp" in manifest["conflicts"] and not manifest["requires"], "it conflicts with KMRP and requires nothing")
    check(package.ID in kmrp.PATCH["conflicts"], "KMRP's own patch lists it as a conflict")

    # 3. Its sites against KMRP's.
    theirs = {h["address"]: h for h in kmrp.all_hooks()}
    stand_ins = {0x0040CE70, 0x00404D96}        # held by KMRP's core frames, which run the controller's
    # the Xbox-style HUD's two, which KMRP's patch does not have
    own = {package.XBOX_HUD_HOOK["address"], package.XBOX_HUD_BARS_HOOK["address"]}
    same = [a for a in mine if a in theirs and a not in stand_ins
            and kmrp_controller.normalised(mine[a]) == kmrp_controller.normalised(theirs[a])]
    check(len(same) == len(mine) - len(stand_ins) - len(own) and stand_ins <= set(theirs) and not (own & set(theirs)),
          f"{len(same)} sites are KMRP's own hooks unchanged, {len(stand_ins)} are the frame sites KMRP holds, "
          f"and {len(own)} are the Xbox-style HUD's own, which KMRP's patch leaves alone")

    # 4. The file bank.
    names = sorted(p.name for p in FILES.iterdir())
    guis = [n for n in names if n.endswith(".gui")]
    expected = sorted(list(assets.R3_CUE_SCREENS) + [assets.TAB_CUE_SCREEN, "optgameplay.gui", "confirm.gui",
                                                      "dialog.gui", "kmrplayout.gui"]
                      + [p.name for p in assets.VANILLA_GUI.glob("mipc*.gui")]
                      + [assets.XBOX_HUD_PREFIX + p.name[4:] for p in assets.VANILLA_GUI.glob("mipc2*.gui")])
    check(guis == expected,
          f"{len(guis)} layout files: the ones the controller changes, its own screen and the Xbox-style HUD's twins")
    check(all(n.endswith((".gui", ".tga")) for n in names), "nothing but layout files and textures")
    check(not any("font" in n or n.startswith(("fnt_", "kmxf")) for n in names), "no font: the game's own text is untouched")
    targets = prompts.PROMPT_TARGETS
    missing = [prompts.family_resref(t.resref, family) for t in targets for family in prompts.GLYPH_FAMILIES
               if prompts.family_resref(t.resref, family) + ".tga" not in names]
    check(not missing, f"all {len(targets)} badges in all {len(prompts.GLYPH_FAMILIES)} families")

    # 5. Badge shape, from the layouts the game loads and the textures in the bank.
    worst = 0.0
    wrong_focus = []
    measured = 0
    loaded = {}
    for target in targets:
        source = "mainmenu8x6.gui" if target.gui == "mainmenu.gui" else target.gui
        path = FILES / source if (FILES / source).exists() else assets.VANILLA_GUI / source
        controls = loaded.setdefault(source, {c.get_string("TAG"): c for c in read_gff(path).root.get_list("CONTROLS")})
        control = controls[target.tag]
        extent = control.get_struct("EXTENT")
        width, height = extent.get_int32("WIDTH"), extent.get_int32("HEIGHT")
        normal = prompts.fill_inset(control.get_struct("BORDER"))
        focused = prompts.fill_inset(control.get_struct("HILIGHT")) if control.exists("HILIGHT") else normal
        resref = prompts.family_resref(target.resref, "xbox")
        has_focus = (FILES / (prompts.focus_resref(resref) + ".tga")).exists()
        if has_focus != (normal != focused):
            wrong_focus.append(target.resref)
        for name, inset in ((resref, normal), (prompts.focus_resref(resref) if has_focus else None, focused)):
            if name is None or target.glyph not in "ABXY" or target.backing:
                continue
            box = alpha_box((FILES / (name + ".tga")).read_bytes())
            area_w, area_h = width - 2 * inset, height - 2 * inset
            if box is None:
                if area_h >= prompts.MIN_BADGE_AREA:
                    wrong_focus.append(name + " is empty")
                continue
            drawn_w = box[2] * area_w / prompts.TEXTURE_WIDTH
            drawn_h = box[3] * area_h / prompts.TEXTURE_HEIGHT
            worst = max(worst, abs(drawn_w / drawn_h - 1.0))
            if box[1] == 0 or box[1] + box[3] >= prompts.TEXTURE_HEIGHT:
                wrong_focus.append(name + " touches the texture's edge")
            measured += 1
    check(not wrong_focus, "a focused-state texture exactly where the two borders fill different areas, none empty or cut"
          + ("" if not wrong_focus else f": {wrong_focus[:6]}"))
    check(measured > 150 and worst <= 0.08,
          f"{measured} face-button badges map to round ones in their fill area (worst {worst * 100:.1f}% off square)")

    # 6. The Xbox-style HUD's layouts.
    twins = sorted(FILES.glob(assets.XBOX_HUD_PREFIX + "*.gui"))
    problems = []
    for twin in twins:
        original = FILES / ("mipc" + twin.name[len(assets.XBOX_HUD_PREFIX):])
        mine_gui, theirs_gui = read_gff(twin).root, read_gff(original).root
        controls = {c.get_string("TAG"): c for c in mine_gui.get_list("CONTROLS")}
        order = [c.get_string("TAG") for c in mine_gui.get_list("CONTROLS")]
        if order != [c.get_string("TAG") for c in theirs_gui.get_list("CONTROLS")]:
            problems.append(f"{twin.name}: not the original's controls in the original's order")
            continue
        screen = mine_gui.get_struct("EXTENT")
        width, height = screen.get_int32("WIDTH"), screen.get_int32("HEIGHT")

        def box(tag):
            e = controls[tag].get_struct("EXTENT")
            return [e.get_int32(k) for k in ("LEFT", "TOP", "WIDTH", "HEIGHT")]

        frames = [box(f"BTN_TARGET{i}") for i in range(3)] + [box(f"BTN_ACTION{i}") for i in range(4)]
        row = [frames[i] for i in (3, 1, 2, 4, 5)]        # the second to sixth places, left to right
        pitches = {b[0] - a[0] for a, b in zip(row, row[1:])}
        if len(pitches) != 1 or min(pitches) <= 0 or len({(f[1], f[2], f[3]) for f in frames}) != 1:
            problems.append(f"{twin.name}: the six places are not one row at one pitch")
        if frames[6] != frames[2] or frames[0] != frames[3]:
            problems.append(f"{twin.name}: the mines' and skills' slots are not on the places they share")
        if row[0][0] - min(pitches) < 0:
            problems.append(f"{twin.name}: no room for the first place")
        if frames[3][2] != xbox_hud.scale_value(xbox_hud.SLOT_BORDER[2], height):
            problems.append(f"{twin.name}: the first personal slot is not the size the module looks for")
        if not order.index("LBL_MOULDING1") < order.index("LBL_ACTIONDESC"):
            problems.append(f"{twin.name}: the action box would be drawn over its description")
        for tag in order:
            left, top, w, h = box(tag)
            parked = left == xbox_hud.OFFSCREEN and top == xbox_hud.OFFSCREEN
            # LBL_MAP is the map picture, larger than its window by design.
            inside = 0 <= left and 0 <= top and left + w <= width and top + h <= height
            if not (parked or inside or tag in ("LBL_MAP", "LBL_ARROW_MARGIN", "LBL_CMBTMODEMSG", "LBL_CMBTMSGBG")):
                problems.append(f"{twin.name}: {tag} at {left},{top} {w}x{h} is partly off the {width}x{height} screen")
    check(len(twins) == 4 and not problems,
          f"{len(twins)} Xbox-style HUD layouts: the originals' controls, six places in a row, all on screen"
          + ("" if not problems else f": {problems[:4]}"))

    print()
    print(f"{PACKAGE.name}: {result['bytes']} bytes, SHA-256 {result['sha256']}")
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
