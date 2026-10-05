#!/usr/bin/env python3
"""Checks on the standalone controller patch, dist/controller/KOTOR 1 Native Controller Mod + Xbox HUD.kpatch.

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
  6. The Xbox-style HUD: the table the module lays the live HUD out from
     (K1XboxHudLayout.inc) is what tools/build_xbox_hud.py writes; every piece is a
     control of the game's own HUD layouts, of the class the table says; and on
     screens of several sizes and shapes, the game's own and others, the six places
     are one row at one pitch, the groups do not run into each other and every
     piece is on the screen. No layout file of the HUD's is in the bank for it.

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
import build_xbox_hud_art                                   # noqa: E402
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
    check(result["hooks"] == len(package.hooks()) == 34, f"the package carries {result['hooks']} hooks, all from the sources")
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
    engine = kmrp._table()      # its resource hook included: this patch has a site of its own for that
    check(not any(h["address"] in mine for h in engine),
          f"none of the {len(engine)} resolution and layout hooks of KMRP's module is in it")
    check(all(h.get("type", "detour") == "detour" for h in packed), "every hook is a detour: nothing is written to the file on disk")
    check("kmrp" not in manifest["conflicts"] and not manifest["requires"], "it requires nothing, and does not conflict with KMRP")
    check(kmrp.PATCH["requires"] == [package.ID] and package.ID not in kmrp.PATCH["conflicts"],
          "KMRP's own patch requires it")
    shared = sorted(a for a in mine if any(h["address"] < a + len(mine[a]["original_bytes"])
                                           and a < h["address"] + len(h["original_bytes"]) for h in kmrp.all_hooks()))
    check(not shared, "no site of it overlaps a site of KMRP's patch: the two install together"
          + ("" if not shared else f": {[hex(a) for a in shared]}"))

    # 3. Its sites against KMRP's.
    # KMRP's controller hooks, as its sources define them. Its patch no longer
    # installs them (the controller is this patch, since 2026-10-05); they are what
    # this patch's sites are held against.
    theirs = {h["address"]: kmrp_controller.as_installed(h) for h in kmrp_controller.kpm_patch_hooks("kmrp-controller")}
    theirs.update({h["address"]: kmrp_controller.as_installed(h) for h in kmrp_controller.installable_hooks()
                   if h.get("function") in ("NativeGuiFrameK1", "NativeMovieFrameK1")})
    stand_ins = set()
    # the Xbox-style HUD's two, which KMRP's patch does not have, and the two that
    # stand in for KMRP's hook at StopLoadFromLayout's entry, left to other patches
    own = {package.XBOX_HUD_HOOK["address"], package.XBOX_HUD_BARS_HOOK["address"],
           package.PANEL_LOADED_HOOK["address"], package.PANEL_DESTROYED_HOOK["address"],
           package.RESOURCE_OWN_HOOK["address"]}
    check(package.PANEL_SITE not in mine and package.PANEL_SITE in theirs,
          "StopLoadFromLayout's entry, which KMRP's patch hooks, is left free for another patch")
    same = [a for a in mine if a in theirs and a not in stand_ins
            and kmrp_controller.normalised(mine[a]) == kmrp_controller.normalised(theirs[a])]
    check(len(same) == len(mine) - len(stand_ins) - len(own) and stand_ins <= set(theirs) and not (own & set(theirs)),
          f"{len(same)} sites are KMRP's own hooks unchanged, {len(stand_ins)} are the frame sites KMRP holds, "
          f"and {len(own)} are this patch's own (the Xbox-style HUD's two and the two panel sites), "
          "which KMRP's patch leaves alone")

    # 4. The file bank.
    names = sorted(p.name for p in FILES.iterdir())
    guis = [n for n in names if n.endswith(".gui")]
    expected = sorted(list(assets.R3_CUE_SCREENS) + [assets.TAB_CUE_SCREEN, "optgameplay.gui", "confirm.gui",
                                                      "dialog.gui", "kmrplayout.gui"]
                      + [p.name for p in assets.VANILLA_GUI.glob("mipc*.gui")])
    check(guis == expected,
          f"{len(guis)} layout files: the ones the controller changes and its own screen")
    hud_art = sorted(n for n in names if n.startswith(build_xbox_hud_art.PREFIX))
    check(hud_art == sorted(f"{v}.{kind}" for v in build_xbox_hud_art.NAMES.values() for kind in ("tga", "txi")),
          f"{len(build_xbox_hud_art.NAMES)} drawn Xbox HUD frames, each with its clamp setting")
    check(all(n.endswith((".gui", ".tga")) or n in hud_art for n in names), "nothing but layout files and textures")
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

    # The shapes the badges were made for, which the module keeps them to.
    shapes = assets.BADGE_SHAPES.read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10)) if assets.BADGE_SHAPES.exists() else ""
    check(shapes == assets.badge_shapes() and shapes.count("{") > 100,
          f"{assets.BADGE_SHAPES.name} is what tools/build_controller_assets.py --badge-shapes writes "
          f"({shapes.count('{') - 1} badges)")

    # The tab strip's two cues are the drawn arrows, for every family.
    import build_tab_arrows
    wrong = [f"{family}/{fill}" for family in prompts.GLYPH_FAMILIES for index, (_, fill, _) in enumerate(assets.TAB_CUES)
             if (FILES / (prompts.family_resref(fill, family) + ".tga")).read_bytes()
             != build_tab_arrows.arrow_tga(family, index == 1)]
    check(not wrong, "LT and RT beside the tab strip are tools/build_tab_arrows.py's arrows, in all 4 families"
          + ("" if not wrong else f": {wrong}"))

    # 6. The Xbox-style HUD's table.
    table = xbox_hud.TABLE.read_text(encoding="utf-8").replace("\r\n", "\n") if xbox_hud.TABLE.exists() else ""
    check(table == xbox_hud.table(), f"{xbox_hud.TABLE.name} is what tools/build_xbox_hud.py writes")
    pieces = xbox_hud.pieces()
    by_tag = {piece["tag"]: piece for piece in pieces}
    problems = []
    for hud in sorted(FILES.glob("mipc2*.gui")):
        kinds = {c.get_string("TAG"): c.get_int32("CONTROLTYPE") for c in read_gff(hud).root.get_list("CONTROLS")}
        problems += [f"{hud.name}: {p['tag']}" for p in pieces if kinds.get(p["tag"]) != p["kind"]]
        order = [c.get_string("TAG") for c in read_gff(hud).root.get_list("CONTROLS")]
        if not order.index("LBL_MOULDING1") < order.index("LBL_ACTIONDESC") < order.index("LBL_MOULDING3"):
            problems.append(f"{hud.name}: the action box would be drawn over its description")
    offsets = [piece["offset"] for piece in pieces]
    check(not problems and len(set(offsets)) == len(offsets),
          f"{len(pieces)} pieces, each a control of the game's four HUD layouts, of the class the table says"
          + ("" if not problems else f": {problems[:4]}"))

    problems = []
    screens = [(800, 600), (1024, 768), (1280, 960), (1600, 1200), (1280, 1024), (1280, 720), (1920, 1080),
               (2560, 1080), (3440, 1440), (3840, 2160)]
    for width, height in screens:
        at = {tag: xbox_hud.rectangle(piece, width, height) for tag, piece in by_tag.items()}
        frames = [at[f"BTN_TARGET{i}"] for i in range(3)] + [at[f"BTN_ACTION{i}"] for i in range(4)]
        row = [frames[i] for i in (3, 1, 2, 4, 5)]        # the second to sixth places, left to right
        pitches = {b[0] - a[0] for a, b in zip(row, row[1:])}
        name = f"{width}x{height}"
        if len(pitches) != 1 or min(pitches) <= 0 or len({(f[1], f[2], f[3]) for f in frames}) != 1:
            problems.append(f"{name}: the six places are not one row at one pitch")
        if frames[6] != frames[2] or frames[0] != frames[3]:
            problems.append(f"{name}: the mines' and skills' slots are not on the places they share")
        if row[0][0] - min(pitches) < 0:
            problems.append(f"{name}: no room for the first place")
        box, queue, party = at["LBL_MOULDING1"], at["LBL_COMBATBG1"], at["PB_VIT1"]
        if not box[0] + box[2] <= queue[0] or not queue[0] + queue[2] <= party[0]:
            problems.append(f"{name}: the action box, the queue and the party run into each other")
        if not at["LBL_NAMEBG"][0] + at["LBL_NAMEBG"][2] <= at["LBL_MAPBORDER"][0]:
            problems.append(f"{name}: the target's bar reaches the minimap")
        for tag, piece in by_tag.items():
            if at[tag] is None or piece["side"] == xbox_hud.RELATIVE:
                continue          # parked, or placed from its portrait's corner
            left, top, w, h = at[tag]
            if not (0 <= left and 0 <= top and left + w <= width and top + h <= height):
                problems.append(f"{name}: {tag} at {left},{top} {w}x{h} is partly off the screen")
    check(not problems,
          f"the Xbox-style HUD laid out for {len(screens)} screens from 800x600 to 3840x2160, 5:4 to 21:9: "
          "six places in a row, nothing overlapping, all on screen" + ("" if not problems else f": {problems[:4]}"))

    print()
    print(f"{PACKAGE.name}: {result['bytes']} bytes, SHA-256 {result['sha256']}")
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
