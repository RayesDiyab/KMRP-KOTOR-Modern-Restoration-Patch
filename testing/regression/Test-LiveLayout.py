#!/usr/bin/env python3
"""Check Live Adaptive Layout: the table, the Python layout against KMRP's sets, the C against the Python.

tools/build_live_layout.py makes macos/tools/kmrp-livelayout-table.h and holds the layout in
Python; KmrpLiveLayout in macos/tools/kmrp-guiadapt.c is what the Windows module and the Mac
run. This:

1. requires the table to be what the script makes now;
2. lays out the game's own file of every screen the table has (build-inputs/vanilla-gui) in
   Python at every size KMRP has a set for, and compares it with that set's file
   (build/kmrp/resources/gui-<W>x<H>.zip): at 3440x1440, the gold layout, every EXTENT and
   PADDING must be the set's and every other field too, but for colours within 1e-5 (the
   gold files' colours were written back with less precision); at every other size every
   PADDING must be the set's and no EXTENT field more than limit(width) px off (the
   maintainer accepted the rounding pixel on 2026-10-28; fields further than a pixel are
   printed), with the share within a pixel printed. KMRP's own controls count: the R3 cue
   Inventory, Equipment and Character carry must be there and where the set has it;
3. builds the C helper (native_helpers.py) and requires its file to have every field of
   the Python's, the cue's included, at every set's size and at 200 random sizes from
   640x480 to 15360x8640;
4. the same for mods' files: each screen's game file with one control moved (it keeps its
   place, without gold's correction) and one control added under a new TAG (the default
   rule), and a file laid out for 1920x1080, which both must refuse.

    python testing/regression/Test-LiveLayout.py [RESOURCES_DIR] [--screens NAME...] [--no-cache]

Each screen that passed is kept in build/test-cache/live-layout under a fingerprint of what
it reads, and skipped while that still matches (see "the cache" below); --no-cache checks
everything. The screens left to check run in worker processes, one a core (--jobs N).
"""
from __future__ import annotations

import io
import ast
import copy
import argparse
import hashlib
import importlib.metadata
import json
import logging
import os
import re
from concurrent.futures import ProcessPoolExecutor
import random
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_live_layout as ll  # noqa: E402
import native_helpers  # noqa: E402
import source_fingerprint  # noqa: E402
from pykotor.resource.formats.gff import GFFList, GFFStruct, read_gff, write_gff  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402
from pykotor.common.misc import ResRef  # noqa: E402

RESOURCES = ROOT / "build" / "kmrp" / "resources"
# The rounding pixel was accepted (2026-10-28); a few fields carry upstream's own rounding
# through gold's ratio to 2 or 3 px at very large or blended sizes (9 of 35,640 on
# 2026-10-28), and are printed. On the widest screens that rounding is up to a 3072th of
# the width: the party portraits' second button and the R3 cue beside it, 5 px at
# 15360x8640 and 2 or 3 px from 3008 px wide (2026-10-28).
def limit(width: int) -> int:
    return max(3, width // 3072)
COLOUR_TOLERANCE = 1e-5
UPSTREAM_GOLD = ll.UPSTREAM / "21-by-9" / "gui.3440x1440"
_moved: dict = {}


def moved_ratio(name: str, k) -> float:
    """How far gold moved a field from upstream's 3440x1440 set, as a ratio (at least 1)."""
    if name not in _moved:
        up = numbers(read_gff(UPSTREAM_GOLD / name).root) if (UPSTREAM_GOLD / name).is_file() else {}
        _moved[name] = (up, numbers(read_gff(ll.GOLD / name).root))
    up, gold = _moved[name]
    u, g = up.get(k), gold.get(k)
    if not u or g is None or k[1] == "PADDING":
        return 1.0
    return max(1.0, abs(g / u), abs(u / g) if g else 1.0)


def flat(struct: GFFStruct, path: str = "") -> dict:
    """Every field of a structure, nested ones by path."""
    out = {}
    for label, _ftype, value in struct:
        here = f"{path}.{label}"
        if isinstance(value, GFFStruct):
            out.update(flat(value, here))
        elif isinstance(value, GFFList):
            for i, item in enumerate(value):
                out.update(flat(item, f"{here}[{i}]"))
        else:
            out[here] = value
    return out


def numbers(root: GFFStruct) -> dict:
    """(key, field) -> value for every EXTENT field and PADDING, keyed as the layout keys."""
    out = {}
    for key, struct, _ in ll.structures(root):
        for name, value in zip(ll.FIELDS, ll.extent(struct)):
            out[(key, name)] = value
        if struct.exists("PADDING"):
            out[(key, "PADDING")] = struct.get_int32("PADDING")
    return out


def built_file(size: str, name: str) -> GFFStruct:
    with zipfile.ZipFile(RESOURCES / f"gui-{size}.zip") as z:
        entry = next(i for i in z.infolist() if i.filename.rsplit("/", 1)[-1].lower() == name)
        return read_gff(z.read(entry)).root


def built_manifest(size: str) -> str:
    """The set's prompt manifest (kmrp_prompts.txt), which the run time reads beside its files."""
    with zipfile.ZipFile(RESOURCES / f"gui-{size}.zip") as z:
        return z.read("kmrp_prompts.txt").decode("utf-8")


def python_layout(name: str, source: Path, width: int, height: int, rows: dict,
                  caption: float | None = None, donor: Path | None = None) -> GFFStruct | None:
    vanilla = read_gff(ll.VANILLA / name).root
    return ll.layout(name, vanilla, read_gff(source).root, width, height, rows, caption, donor)


def set_folder(folder: Path, size: str, manifest: str) -> Path:
    """A size's set folder as the run time reads it: the prompt manifest and the badge
    labels' donor, kmrplayout.gui (a set's own at its size, else the 3440x1440 set's)."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "kmrp_prompts.txt").write_text(manifest, encoding="utf-8")
    donor_size = size if (RESOURCES / f"gui-{size}.zip").is_file() else "3440x1440"
    with zipfile.ZipFile(RESOURCES / f"gui-{donor_size}.zip") as z:
        entry = next(i for i in z.infolist() if i.filename.rsplit("/", 1)[-1].lower() == ll.BADGE_DONOR)
        (folder / ll.BADGE_DONOR).write_bytes(z.read(entry))
    return folder


def centred_padding(name: str, size: str, k, ours: GFFStruct, theirs: GFFStruct) -> bool:
    """Is Script Selection's PADDING off only because the list it centres is? Each must be
    centre_rows_in_frame of its own list, and the two no further apart than that list's
    rounding: its left edge twice, its width and its scroll bar's width, and a pixel for the
    rounding of the result. At 3440x1440 they are the same; elsewhere up to 3 px
    (2026-10-30), the run time's rows centred in the art's frame for the list as it lays it."""
    if name != "scriptselect.gui" or k != (("LST_AIState", ""), "PADDING"):
        return False
    w = int(size.split("x")[0])

    def geometry(root: GFFStruct) -> tuple[int, int, int, int]:
        s = {key: struct for key, struct, _ in ll.structures(root)}
        e = ll.extent(s[("LST_AIState", "")])
        return e[0], e[2], ll.extent(s[("LST_AIState", "SCROLLBAR")])[2], s[("LST_AIState", "")].get_int32("PADDING")

    def centred(left: int, width: int, bar: int) -> int:
        frame_left, frame_right = (f * w for f in ll.SCRIPTSELECT_FRAME)
        padding = int(round(frame_left + frame_right - (left + width) - left - bar))
        return max(0, min(padding, 255, (width - bar) // 2 - 1))

    a, b = geometry(ours), geometry(theirs)
    bound = 2 * abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) + 1
    return centred(*a[:3]) == a[3] and centred(*b[:3]) == b[3] and abs(a[3] - b[3]) <= bound


def row_threshold(name: str, size: str, k, rows: dict, caption) -> bool:
    """Is a row list's height off only because the accepted rounding pixel put the list before
    fitting on the other side of a row count? Then the build's own fit_list_to_rows, given the
    run time's height, makes the run time's list, and given the set's, the set's.
    ftchrgen.gui at 2880x1864: 1035 px fits 7 rows loosely and shrinks to 984, 1036 fits 8
    rows exactly and stays (2026-10-30)."""
    (tag, sub), field = k
    if field != "HEIGHT" or sub not in ("", "SCROLLBAR") or (name, tag) not in ll.ROW_LISTS:
        return False
    w, h = (int(x) for x in size.split("x"))
    fitted = next((int(line.split()[-1]) for line in built_manifest(size).splitlines()
                   if line.split()[:3] == ["fitted", name, tag]), None)
    saved = dict(ll.ROW_LISTS)
    ll.ROW_LISTS.clear()
    try:
        unfitted = python_layout(name, ll.VANILLA / name, w, h, rows, caption)
    finally:
        ll.ROW_LISTS.update(saved)
    before = numbers(unfitted)[((tag, ""), "HEIGHT")]
    theirs_list = numbers(built_file(size, name))[((tag, ""), "HEIGHT")]
    if fitted is None or abs(before - (theirs_list - fitted)) > 1:
        return False
    kind, bases = ll.ROW_LISTS[(name, tag)]
    with tempfile.TemporaryDirectory(prefix="kmrp-rowthreshold-") as tmp:
        path = Path(tmp) / name
        gff = read_gff(ll.VANILLA / name)
        gff.root = unfitted
        write_gff(gff, path, ResourceType.GUI)
        change = ll.fit_list_to_rows(path, path, h, tag, bases, popup=kind == "popup")
    return before + change == numbers(python_layout(name, ll.VANILLA / name, w, h, rows, caption))[((tag, ""), "HEIGHT")]


def mod_files(name: str, out: Path) -> tuple[Path | None, Path, str | None]:
    """The game's file with its last control moved and a label added under a new TAG
    (None for a screen with no controls, which has neither to test); and the game's file
    scaled to 1920x1080."""
    big = read_gff(ll.VANILLA / name)
    root = ll.child(big.root, "EXTENT")
    for field, factor in zip(ll.FIELDS, (3, 2.25, 3, 2.25)):
        root.set_int32(field, int(root.get_int32(field) * factor))
    hires = out / f"hires-{name}"
    write_gff(big, hires, ResourceType.GUI)
    gff = read_gff(ll.VANILLA / name)
    controls = gff.root.acquire("CONTROLS", None, GFFList)
    if controls is None or len(controls) == 0:
        return None, hires, None
    moved = controls.at(len(controls) - 1)
    e = ll.child(moved, "EXTENT")
    e.set_int32("LEFT", e.get_int32("LEFT") + 7)
    e.set_int32("TOP", e.get_int32("TOP") + 5)
    if name == "classsel.gui":
        by_tag = {c.get_string("TAG"): c for c in controls}
        # Exercise both affine axes without gold's correction, and preserve a
        # mod's own frame instead of clearing it with the game's border art.
        selected = by_tag["BTN_SEL1"]
        box = ll.child(selected, "EXTENT")
        box.set_int32("WIDTH", box.get_int32("WIDTH") + 8)
        box.set_int32("HEIGHT", box.get_int32("HEIGHT") + 6)
        ll.child(selected, "BORDER").set_resref("CORNER", ResRef("mod_frame"))
        model = ll.child(by_tag["3D_MODEL1"], "EXTENT")
        model.set_int32("TOP", model.get_int32("TOP") + 4)
    added = controls.add(0)
    added.set_string("TAG", "LBL_MOD_ADDED")
    added.set_int32("CONTROLTYPE", 4)
    ext = GFFStruct()
    for field, v in zip(ll.FIELDS, (101, 37, 40, 40)):
        ext.set_int32(field, v)
    added.set_struct("EXTENT", ext)
    mod = out / f"mod-{name}"
    write_gff(gff, mod, ResourceType.GUI)
    return mod, hires, moved.get_string("TAG")


def check_cue_mods(helper: Path, tmp: Path, rows: dict, fail) -> int:
    """Exercise cue placement from mod geometry, refusal, duplicate tags and template fallback."""
    checked = 0
    for name, variants in (("abilities.gui", ("moved", "missing", "blocked", "existing", "template")),
                           ("top.gui", ("moved", "missing", "existing", "template"))):
        for variant in variants:
            gff = read_gff(ll.VANILLA / name)
            controls = gff.root.acquire("CONTROLS", None, GFFList)
            by_tag = {c.get_string("TAG"): c for c in controls}
            if variant == "moved":
                tags = ll.SUBTAB_TAGS if name == "abilities.gui" else ll.TAB_TAGS
                for index, tag in enumerate(tags):
                    box = ll.child(by_tag[tag], "EXTENT")
                    box.set_int32("LEFT", box.get_int32("LEFT") + 3 * (index + 1))
                    box.set_int32("HEIGHT", box.get_int32("HEIGHT") + 1)
                # New IDs must follow the highest, even if the template has a lower ID.
                controls.at(0).set_int32("ID", 900)
            elif variant == "missing":
                by_tag[ll.SUBTAB_TAGS[1] if name == "abilities.gui" else ll.TAB_TAGS[1]].set_string("TAG", "MOD_RENAMED")
            elif variant == "blocked":
                ll.child(by_tag[ll.SWAP_CUE_BESIDE], "EXTENT").set_int32("LEFT", 1)
            elif variant == "existing":
                cue = copy.deepcopy(by_tag[ll.SUBTAB_TAGS[0] if name == "abilities.gui" else ll.TAB_TAGS[0]])
                cue.set_string("TAG", ll.SWAP_CUE_TAG if name == "abilities.gui" else ll.TAB_CUES[0][0])
                cue.set_int32("ID", 901)
                ll.child(cue, "BORDER").set_resref("FILL", ResRef("mod_cue"))
                controls.append(cue)
            elif variant == "template":
                template = ll.extra_cue_template(gff.root, name)
                # A mod with no label still uses the first tab button on top.gui.
                if name == "top.gui":
                    for c in controls:
                        if c.acquire("CONTROLTYPE", -1) == 4:
                            c.set_int32("CONTROLTYPE", 5)
                else:
                    template._fields.pop("ID")
            source = tmp / f"{variant}-{name}"
            write_gff(gff, source, ResourceType.GUI)
            original = source.read_bytes()
            for w, h in ((800, 600), (1920, 1080), (3440, 1440), (2560, 1600)):
                out = tmp / "cue-mod.gui"
                out.unlink(missing_ok=True)
                code = subprocess.run([str(helper), "live", native_helpers.arg(ll.VANILLA / name), name,
                                       str(w), str(h), native_helpers.arg(out), native_helpers.arg(source)],
                                      stdout=subprocess.DEVNULL).returncode
                expected = python_layout(name, source, w, h, rows[name])
                if code or not out.exists() or flat(read_gff(out).root) != flat(expected):
                    fail(f"{name} {variant} {w}x{h}: cue mod differs between C and Python (code {code})")
                    continue
                actual = read_gff(out).root.acquire("CONTROLS", None, GFFList)
                tags = [c.get_string("TAG") for c in actual]
                cue_tag = ll.SWAP_CUE_TAG if name == "abilities.gui" else ll.TAB_CUES[0][0]
                if variant in ("missing", "blocked") or (variant == "template" and name == "abilities.gui"):
                    if cue_tag in tags:
                        fail(f"{name} {variant}: unsupported cue was added")
                elif variant == "existing":
                    cue = next(c for c in actual if c.get_string("TAG") == cue_tag)
                    if tags.count(cue_tag) != 1 or str(ll.child(cue, "BORDER").get_resref("FILL")) != "mod_cue":
                        fail(f"{name}: existing mod cue was replaced or duplicated")
                    if name == "top.gui" and ll.TAB_CUES[1][0] in tags:
                        fail("top.gui: an existing partial cue pair was changed")
                elif name == "top.gui" and any(t not in tags for t, _, _ in ll.TAB_CUES):
                    fail(f"top.gui {variant}: tab cues were not added")
                if variant == "moved":
                    new_ids = [c.get_int32("ID") for c in actual if c.get_string("TAG").startswith("LBL_KMRP")]
                    if not new_ids or min(new_ids) <= 900 or len(new_ids) != len(set(new_ids)):
                        fail(f"{name}: cue IDs do not follow the mod's highest ID")
                checked += 1
            if source.read_bytes() != original:
                fail(f"{name} {variant}: source mod was modified on disk")
    return checked


def check_options_mods(helper: Path, tmp: Path, rows: dict, fail) -> int:
    """Check entry cloning/lifting and checkbox rows against independently run build steps."""
    checked = 0
    for name, variants in ((ll.ENTRY_SCREEN, ("style", "missing-key", "missing-mouse", "existing", "reverse-step", "missing-text")),
                           (ll.FEEDBACK_LIST[0], ("row57", "missing-proto", "missing-list"))):
        for variant in variants:
            gff = read_gff(ll.VANILLA / name)
            controls = gff.root.acquire("CONTROLS", None, GFFList)
            by_tag = {c.get_string("TAG"): c for c in controls}
            if name == ll.ENTRY_SCREEN:
                key, mouse = by_tag[ll.ENTRY_TEMPLATE], by_tag[ll.ENTRY_PREVIOUS]
                if variant == "style":
                    key.set_int32("ID", 903)
                    ll.child(key, "BORDER").set_resref("FILL", ResRef("mod_fill"))
                    ll.child(key, "BORDER").set_resref("CORNER", ResRef("mod_corner"))
                    ll.child(key, "TEXT").set_resref("FONT", ResRef("mod_font"))
                    ll.child(key, "TEXT").set_int32("ALIGNMENT", 18)
                    ll.child(key, "EXTENT").set_int32("TOP", 361)
                elif variant == "missing-key":
                    key.set_string("TAG", "MOD_KEYMAP")
                elif variant == "missing-mouse":
                    mouse.set_string("TAG", "MOD_MOUSE")
                elif variant == "reverse-step":
                    ll.child(mouse, "EXTENT").set_int32("TOP", 373)
                elif variant == "missing-text":
                    ll.child(key, "TEXT")._fields.pop("STRREF")
                elif variant == "existing":
                    entry = copy.deepcopy(key)
                    entry.set_string("TAG", ll.ENTRY_TAG)
                    entry.set_int32("ID", 904)
                    ll.child(entry, "TEXT").set_string("TEXT", "Mod layout")
                    controls.append(entry)
            else:
                target = by_tag[ll.FEEDBACK_LIST[1]]
                if variant == "row57":
                    proto = ll.child(target, "PROTOITEM")
                    e = ll.child(proto, "EXTENT")
                    e.set_int32("HEIGHT", 57)
                    e.set_int32("WIDTH", 251)
                elif variant == "missing-proto":
                    target._fields.pop("PROTOITEM")
                elif variant == "missing-list":
                    target.set_string("TAG", "MOD_OPTIONS")
            source = tmp / f"options-{variant}-{name}"
            write_gff(gff, source, ResourceType.GUI)
            original = source.read_bytes()
            for w, h in ((800, 600), (1920, 1080), (3440, 1440), (3840, 2160)):
                out = tmp / "options-mod.gui"
                out.unlink(missing_ok=True)
                code = subprocess.run([str(helper), "live", native_helpers.arg(ll.VANILLA / name), name,
                                       str(w), str(h), native_helpers.arg(out), native_helpers.arg(source)],
                                      stdout=subprocess.DEVNULL).returncode
                expected = python_layout(name, source, w, h, rows[name])
                if code or not out.exists() or flat(read_gff(out).root) != flat(expected):
                    fail(f"{name} {variant} {w}x{h}: option mod differs between C and Python (code {code})")
                    continue
                actual = read_gff(out).root.acquire("CONTROLS", None, GFFList)
                entries = [c for c in actual if c.get_string("TAG") == ll.ENTRY_TAG]
                if name == ll.ENTRY_SCREEN:
                    if variant in ("missing-key", "missing-text"):
                        if entries:
                            fail(f"{variant}: unsupported entry was added")
                    elif len(entries) != 1:
                        fail(f"{variant}: Controller Layout entry missing or duplicated")
                    elif variant == "style":
                        entry = entries[0]
                        if (entry.get_int32("ID") != 904 or
                            str(ll.child(entry, "BORDER").get_resref("CORNER")) != "mod_corner" or
                            str(ll.child(entry, "BORDER").get_resref("FILL")) != "mod_fill" or
                            str(ll.child(entry, "TEXT").get_resref("FONT")) != "mod_font"):
                            fail("entry clone lost the mod's border, fill, font or next ID")
                    elif variant == "existing" and ll.child(entries[0], "TEXT").get_string("TEXT") != "Mod layout":
                        fail("existing mod entry was overwritten")
                elif variant == "row57":
                    row = next(c for c in actual if c.get_string("TAG") == ll.FEEDBACK_LIST[1])
                    box = ll.extent(ll.child(row, "PROTOITEM"))
                    if box[2] != 251 or box[3] != {600: 57, 1080: 86, 1440: 114, 2160: 171}[h]:
                        fail("Feedback lost mod row dimensions or single-precision half-even scaling")
                checked += 1
            if source.read_bytes() != original:
                fail(f"{name} {variant}: source mod was modified on disk")
    return checked


def check_hud_cue_mods(helper: Path, tmp: Path, fail) -> int:
    """The combat cues given to a mod's HUD file (KmrpHudCues) against the build's own
    add_combat_cues (build_live_layout.hud_cues), on the game's eight HUD files and on
    variants a mod could have: buttons moved, a cue already there, the template gone, a cue
    that would leave the panel, a template label without a picture field."""
    checked = 0
    for name in ll.HUD_FILES:
        for variant in ("plain", "moved", "existing", "no-template", "offscreen", "no-fill"):
            gff = read_gff(ll.VANILLA / name)
            controls = gff.root.acquire("CONTROLS", None, GFFList)
            by_tag = {c.get_string("TAG"): c for c in controls}
            if variant == "moved":
                for tag, shift in (("BTN_CLEARONE", 37), ("BTN_CLEARALL", -11)):
                    box = ll.child(by_tag[tag], "EXTENT")
                    box.set_int32("LEFT", box.get_int32("LEFT") + shift)
                    box.set_int32("HEIGHT", box.get_int32("HEIGHT") + 3)
            elif variant == "existing":
                cue = copy.deepcopy(by_tag[ll.COMBAT_CUE_TEMPLATE])
                cue.set_string("TAG", ll.COMBAT_CUES[1][0])
                controls.append(cue)
            elif variant == "no-template":
                by_tag[ll.COMBAT_CUE_TEMPLATE].set_string("TAG", "MOD_QUEUE")
            elif variant == "offscreen":
                ll.child(by_tag["BTN_CLEARALL"], "EXTENT").set_int32("LEFT", 3)
            elif variant == "no-fill":
                ll.child(by_tag[ll.COMBAT_CUE_TEMPLATE], "BORDER")._fields.pop("FILL", None)
            source = tmp / f"hud-{variant}-{name}"
            write_gff(gff, source, ResourceType.GUI)
            out = tmp / "hud-out.gui"
            out.unlink(missing_ok=True)
            code = subprocess.run([str(helper), "hudcues", native_helpers.arg(source), native_helpers.arg(out)],
                                  stdout=subprocess.DEVNULL).returncode
            expected = ll.hud_cues(read_gff(source).root)
            if expected is None:
                if code != 0 or out.exists():
                    fail(f"{name} {variant}: the build adds no cues, the helper wrote a file (code {code})")
            elif code != 0 or not out.exists() or flat(read_gff(out).root) != flat(expected):
                fail(f"{name} {variant}: the combat cues differ between C and Python (code {code})")
            elif variant == "plain":
                tags = [c.get_string("TAG") for c in read_gff(out).root.acquire("CONTROLS", None, GFFList)]
                if any(tags.count(tag) != 1 for tag, *_ in ll.COMBAT_CUES):
                    fail(f"{name}: the combat cues were not each added once")
            if variant in ("existing", "no-template", "no-fill") and expected is not None:
                fail(f"{name} {variant}: the build was expected to add nothing")
            checked += 1
    return checked


# ----------------------------------------------------------------------------- the cache
# Each screen's checks (the Python against the 66 sets, the C against the Python) and each
# mod suite are skipped while a fingerprint of everything they read still matches the one
# kept from their last pass (2026-10-30, the maintainer: "cache each one screen being
# tested ... with a fingerprint"). A full run had grown past ten minutes with 65 screens,
# almost all of it checking screens nothing had touched. The fingerprint holds the code
# (Python by its parsed code, comments and docstrings out, as build_kmrp.ps1's step cache
# counts it, tools/source_fingerprint.py; build_live_layout.py without its FILES list, so
# adding a screen leaves the others cached), the C, the table's shared part and the
# screen's own rows, the screen's files (the game's, gold's, upstream's 48, each set's copy
# and prompt manifest by CRC), and the Python and pykotor versions. Written only for a
# screen that passed. --no-cache runs everything.
CACHE = ROOT / "build" / "test-cache" / "live-layout"
CACHE_FORMAT = "1"
SHARED_CODE = [ROOT / "tools" / f for f in ("scale_listbox_padding.py", "prepare_universal_resources.py",
                                             "build_controller_layout.py", "build_controller_prompt_textures.py")]
SHARED_CODE += [Path(__file__).resolve(), Path(native_helpers.__file__).resolve()]
GUIADAPT = ROOT / "macos" / "tools" / "kmrp-guiadapt.c"
ROWS_BLOCK = re.compile(r"static const LLRow LL_ROWS_\d+\[\] = \{  /\* (\S+) \*/\n(.*?)\n\};\n", re.S)
FILES_LIST = re.compile(r"static const LLFile LL_FILES\[\] = \{.*?\};\n", re.S)


def sha(*parts) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part if isinstance(part, bytes) else str(part).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def layout_code() -> str:
    """build_live_layout.py's code without its FILES list (source_fingerprint's rule)."""
    tree = ast.parse(Path(ll.__file__).read_bytes())
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "FILES" for t in n.targets))]
    return sha(ast.dump(source_fingerprint.without_docstrings(tree)))


class Fingerprints:
    def __init__(self, resources: Path, sizes: list[str]):
        table = ll.TABLE.read_text(encoding="ascii")
        self.rows = {m.group(1): m.group(2) for m in ROWS_BLOCK.finditer(table)}
        shared_table = FILES_LIST.sub("", ROWS_BLOCK.sub("", table))
        try:
            pykotor = importlib.metadata.version("pykotor")
        except importlib.metadata.PackageNotFoundError:
            pykotor = "unknown"
        self.code = sha(CACHE_FORMAT, sys.version, pykotor, layout_code(),
                        *(source_fingerprint.code_hash(p) for p in SHARED_CODE), GUIADAPT.read_bytes(), shared_table)
        self.table = table
        self.upstream = ll.upstream_sets()
        self.sets = {}
        for size in sizes:
            with zipfile.ZipFile(resources / f"gui-{size}.zip") as z:
                self.sets[size] = {i.filename.rsplit("/", 1)[-1].lower(): (i.CRC, i.file_size) for i in z.infolist()}

    def files(self, name: str) -> str:
        """The screen's own inputs: the game's file, gold's, upstream's."""
        def read(path: Path) -> bytes:
            return path.read_bytes() if path.is_file() else b"missing"
        return sha(read(ll.VANILLA / name), read(ll.GOLD / name),
                   *(read(folder / name) for _, folder in self.upstream))

    def screen(self, name: str) -> str:
        built = [(size, entries.get(name), entries.get("kmrp_prompts.txt")) for size, entries in sorted(self.sets.items())]
        return sha(self.code, self.rows.get(name, "none"), self.files(name), built)

    def rules(self, name: str) -> str:
        return sha(CACHE_FORMAT, layout_code(), self.files(name))

    def suites(self) -> str:
        return sha(self.code, self.table, *(self.files(n) for n in ll.FILES), *(self.files(n) for n in ll.HUD_FILES))


def cached(kind: str, name: str, fingerprint: str) -> dict | None:
    path = CACHE / kind / f"{name}.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if record.get("fingerprint") == fingerprint else None


def keep(kind: str, name: str, fingerprint: str, record: dict) -> None:
    path = CACHE / kind / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**record, "fingerprint": fingerprint}), encoding="utf-8")


def cache_rules(prints: Fingerprints) -> None:
    """build_live_layout.choose_rules, kept per screen: the table check and table_by_file
    otherwise choose every screen's rules from upstream's 48 sets twice a run."""
    choose = ll.choose_rules

    def rules(name, sets):
        fingerprint = prints.rules(name)
        record = cached("rules", name, fingerprint)
        if record is not None:
            return {tuple(key): value for key, value in record["rules"]}
        chosen = choose(name, sets)
        keep("rules", name, fingerprint, {"rules": [[list(key), value] for key, value in chosen.items()]})
        return chosen
    ll.choose_rules = rules


def main() -> int:
    global RESOURCES
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path, nargs="?", default=RESOURCES)
    parser.add_argument("--screens", nargs="+", choices=ll.FILES, default=ll.FILES,
                        help="check selected screens; table and cue/options mod checks still run")
    parser.add_argument("--no-cache", action="store_true", help="check every screen, whatever passed before")
    parser.add_argument("--jobs", type=int, default=0,
                        help="worker processes for the screens to check (default: one a core; 1: none)")
    args = parser.parse_args()
    RESOURCES = args.resources
    files = args.screens
    logging.disable(logging.DEBUG)
    failed = False
    failures = 0

    def fail(message: str) -> None:
        nonlocal failed, failures
        failed = True
        failures += 1
        print("FAIL", message)

    sizes = sorted(p.name[4:-4] for p in RESOURCES.glob("gui-*.zip"))
    if len(sizes) < 66:
        fail(f"{RESOURCES} has {len(sizes)} sets, expected 66")
    prints = Fingerprints(RESOURCES, sizes)
    if not args.no_cache:
        cache_rules(prints)

    # 1. The table.
    if ll.TABLE.read_text(encoding="ascii") != ll.render():
        fail(f"{ll.TABLE} is out of date: run python tools/build_live_layout.py")
    rows = ll.table_by_file()

    tmp_dir = tempfile.TemporaryDirectory(prefix="kmrp-livelayout-test-")
    tmp = Path(tmp_dir.name)
    helper_path: list[Path] = []

    def helper() -> Path:
        """The C helper, built the first time something is not taken from the cache."""
        if not helper_path:
            if native_helpers.WINDOWS:
                helper_path.append(native_helpers.build(GUIADAPT, tmp, "kmrp-guiadapt")["x64"])
            else:
                helper_path.append(tmp / "kmrp-guiadapt")
                subprocess.run(["clang", "-O2", "-o", str(helper_path[0]), str(GUIADAPT), "-lm"], check=True)
        return helper_path[0]

    diffs = Counter()
    checked = 0
    reused = 0
    rng = random.Random(20261028)
    extra = [(rng.randint(640, 15360), 0) for _ in range(200)]
    extra = [(w, rng.randint(max(480, w // 4), min(8640, w * 3 // 4 + 1))) for w, _ in extra]
    fingerprints = {name: prints.screen(name) for name in files}
    records = {} if args.no_cache else {name: cached("screens", name, fingerprints[name]) for name in files}
    to_check = [name for name in files if records.get(name) is None]
    # The screens not taken from the cache, in parallel: one worker process a screen at a time,
    # as many as the machine has cores (2026-10-30, the maintainer: a run that has to check
    # every screen took about 18 minutes on one core). Each works in a folder of its own and
    # returns its failures and notes, printed here in the screens' order.
    if to_check:
        built_helper = helper()
        jobs = [(name, sizes, rows[name], extra, str(built_helper), str(RESOURCES)) for name in to_check]
        workers = min(len(jobs), os.cpu_count() or 1, args.jobs or os.cpu_count() or 1)
        if workers > 1:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results = dict(zip(to_check, pool.map(check_screen_job, jobs)))
        else:
            results = {name: check_screen_job(job) for name, job in zip(to_check, jobs)}
    for name in files:
        record = records.get(name)
        if record is not None:
            for line in record["notes"]:
                print(line)
            diffs.update(record["diffs"])
            checked += record["checked"]
            reused += 1
            continue
        fails, notes, screen_diffs, screen_checked = results[name]
        for line in notes:
            print(line)
        for message in fails:
            fail(message)
        diffs.update(screen_diffs)
        checked += screen_checked
        if not fails:
            keep("screens", name, fingerprints[name], {"notes": notes, "diffs": dict(screen_diffs), "checked": screen_checked})
    total = sum(diffs.values())
    print(f"against KMRP's {len(sizes)} sets, {len(files)} screens: {total} EXTENT fields, "
          f"{100 * diffs['exact'] / total:.2f}% exact, {100 * diffs['1 px'] / total:.2f}% 1 px off, "
          f"{diffs['more']} further; 3440x1440 identical, every other field the set's at every "
          f"size, but for colour precision")
    print(f"C against Python: {checked} layouts, {len(files)} refused mods' files")

    # The mod suites, kept together.
    fingerprint = prints.suites()
    record = None if args.no_cache else cached("suites", "mods", fingerprint)
    if record is None:
        before = failures
        record = {"cue": check_cue_mods(helper(), tmp, rows, fail),
                  "options": check_options_mods(helper(), tmp, rows, fail),
                  "hud": check_hud_cue_mods(helper(), tmp, fail)}
        if failures == before:
            keep("suites", "mods", fingerprint, record)
    else:
        reused += 1
    print(f"Cue mods: {record['cue']} layouts")
    print(f"Options mods: {record['options']} layouts")
    print(f"HUD cue mods: {record['hud']} files")
    tmp_dir.cleanup()
    if reused:
        print(f"from the cache ({CACHE.relative_to(ROOT)}): {reused} of {len(files) + 1} checks unchanged since they passed")

    print("FAILED" if failed else "PASSED")
    return 1 if failed else 0


def check_screen_job(job) -> tuple[list[str], list[str], Counter, int]:
    """check_screen in a worker process: its failures and notes collected, not printed."""
    global RESOURCES
    name, sizes, screen_rows, extra, helper_path, resources = job
    RESOURCES = Path(resources)
    logging.disable(logging.DEBUG)
    fails: list[str] = []
    notes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="kmrp-livelayout-screen-") as tmp:
        screen_diffs, screen_checked = check_screen(name, sizes, {name: screen_rows}, extra,
                                                    lambda: Path(helper_path), Path(tmp), fails.append, notes)
    return fails, notes, screen_diffs, screen_checked


def check_screen(name, sizes, rows, extra, helper, tmp, fail, notes) -> tuple[Counter, int]:
    """One screen's checks: the Python against KMRP's sets (2), the C against the Python (3),
    a mod's file (4). Returns the EXTENT field counts and the C layouts checked; its notes go
    into `notes` (printed by the caller)."""
    def note(line: str) -> None:
        notes.append(line)

    # 2. The Python against KMRP's sets.
    diffs = Counter()
    for size in sizes:
        w, h = (int(x) for x in size.split("x"))
        caption = ll.manifest_caption(built_manifest(size))
        donor = set_folder(tmp / f"donor-{size}", size, built_manifest(size)) / ll.BADGE_DONOR
        ours = python_layout(name, ll.VANILLA / name, w, h, rows[name], caption, donor)
        theirs = built_file(size, name)
        a, b = numbers(ours), numbers(theirs)
        if a.keys() != b.keys():
            fail(f"{name} {size}: the structures differ from the set's")
            continue
        for k in a:
            d = abs(a[k] - b[k])
            if k[1] == "PADDING":
                if d and size != "3440x1440" and centred_padding(name, size, k, ours, theirs):
                    note(f"note {name} {size} {k}: PADDING {a[k]}, the set has {b[k]} (its own list centred)")
                elif d:
                    fail(f"{name} {size} {k}: PADDING {a[k]}, the set has {b[k]}")
                continue
            diffs["exact" if d == 0 else "1 px" if d <= 1 else "more"] += 1
            # A list's scroll bar takes only its WIDTH from the file: the list puts it on
            # its own edge as it loads (docs/live-adaptive-layout.md, section 1), so its
            # other three are noted, not held (Equipment's LB_ITEMS, 2026-10-28).
            engine_placed = k[0][1] == "SCROLLBAR" and k[1] in ("LEFT", "TOP", "HEIGHT")
            # A value gold moved far is carried to each size by gold's ratio, and so is
            # the rounding of the place it is carried from: the Galaxy Map's LBL_Live01,
            # 760 in upstream's 3440x1440 set and 2039 in gold, 2.7 times, is 6 px from
            # the set at 15360x8640 (2026-10-28). Its allowance grows by that ratio.
            if (d > limit(w) and not engine_placed and size != "3440x1440"
                    and d <= limit(w) * moved_ratio(name, k)):
                note(f"note {name} {size} {k}: {a[k]}, the set has {b[k]} (gold moved it)")
                continue
            if (d > limit(w) and size != "3440x1440"
                    and row_threshold(name, size, k, rows[name], caption)):
                note(f"note {name} {size} {k}: {a[k]}, the set has {b[k]} (a row count crossed by the rounding pixel)")
                continue
            if (size == "3440x1440" and d) or (d > limit(w) and not engine_placed):
                fail(f"{name} {size} {k}: {a[k]}, the set has {b[k]}")
            elif d > 1:
                note(f"note {name} {size} {k}: {a[k]}, the set has {b[k]}")
        # Every other field at every size (until 2026-10-28 at 3440x1440 only, which
        # hid that Character's LBL_LEVEL alignment, gold's at every size, was not carried).
        fa, fb = flat(ours), flat(theirs)
        # A controller badge label's text colour: it has no text, so the colour is never drawn.
        # The build cloned it from kmrplayout.gui's title before a later step coloured that
        # title 0.98 (it had 250/255 then); the run time clones the finished file (2026-10-30).
        controls = ours.acquire("CONTROLS", GFFList(), GFFList)
        silent = {f".CONTROLS[{i}].TEXT.COLOR" for i, c in enumerate(controls)
                  if c.acquire("TAG", "") in ll.BADGE_SCREENS.values() and not fa.get(f".CONTROLS[{i}].TEXT.TEXT")}
        for k in fa.keys() | fb.keys():
            if ".EXTENT." in k or k.endswith(".PADDING") or k in silent:
                continue
            x, y = fa.get(k), fb.get(k)
            if x == y:
                continue
            if hasattr(x, "x") and hasattr(y, "x") and all(
                    abs(getattr(x, c) - getattr(y, c)) <= COLOUR_TOLERANCE for c in "xyz"):
                continue
            fail(f"{name} {size} {k}: {x!r}, the set has {y!r}")

    # 3 and 4. The C against the Python, at every set's size, 200 random sizes and for a
    # mod's file. The random captions come from the screen's own stream, so a screen's
    # cases are the same whether or not the screens before it ran.
    rng = random.Random(f"captions {name}")
    checked = 0
    mod, hires, moved_tag = mod_files(name, tmp)
    cases = [(int(s.split("x")[0]), int(s.split("x")[1]), None) for s in sizes]
    cases += [(w, h, None) for w, h in extra]
    if mod:
        cases += [(w, h, mod) for w, h in ((1920, 1080), (3440, 1440), (2560, 1600), (1024, 768))]
    for w, h, source in cases:
        out = tmp / "out.gui"
        out.unlink(missing_ok=True)
        # The size's prompt manifest, as the run time reads it from the set: the set's
        # own at a set's size, else one giving a caption that may or may not need the
        # Container widened.
        size = f"{w}x{h}"
        manifest = (built_manifest(size) if size in sizes else
                    f"prompt {ll.CAPTION_ROW} 1 1 {rng.uniform(100, 900):.2f} -\n")
        folder = set_folder(tmp / "set", size, manifest)
        args = [str(helper()), "live", native_helpers.arg(ll.VANILLA / name), name, str(w), str(h),
                native_helpers.arg(out), native_helpers.arg(source) if source else "-",
                native_helpers.arg(folder)]
        code = subprocess.run(args, stdout=subprocess.DEVNULL).returncode
        ours = python_layout(name, source or ll.VANILLA / name, w, h, rows[name],
                             ll.manifest_caption(manifest), folder / ll.BADGE_DONOR)
        if code != 0 or not out.is_file():
            fail(f"{name} {w}x{h}{' (mod)' if source else ''}: the helper returned {code}")
            continue
        a, b = flat(read_gff(out.read_bytes()).root), flat(ours)
        if a != b:
            bad = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))[:5]
            fail(f"{name} {w}x{h}{' (mod)' if source else ''}: C and Python differ at "
                 + ", ".join(f"{k} {a.get(k)} / {b.get(k)}" for k in bad))
        checked += 1
    # The mod's moved control keeps the mod's place: no gold correction on it.
    if mod:
        ours = numbers(python_layout(name, mod, 3440, 1440, rows[name]))
        gold = numbers(read_gff(ll.GOLD / name).root)
        key = (moved_tag, "")
        # The popup's own controls are placed by its measured table whatever the file says,
        # as the build places them (scale_message_popup.apply_tuned).
        owned = name == ll.POPUP_SCREEN and moved_tag in ll.TUNED
        if not owned and (ours[(key, "LEFT")] == gold[(key, "LEFT")] or ours[(key, "TOP")] == gold[(key, "TOP")]):
            fail(f"{name}: {moved_tag}, moved by the mod, took gold's place")
        if ((("LBL_MOD_ADDED", ""), "LEFT")) not in ours:
            fail(f"{name}: the mod's own control was not laid out")
        if name == "classsel.gui":
            root = python_layout(name, mod, 1920, 1080, rows[name])
            controls = {c.get_string("TAG"): c for c in root.acquire("CONTROLS", None, GFFList)}
            if ll.extent(controls["BTN_SEL1"])[2] != 269:
                fail("classsel.gui: the mod's widened button did not retain its 20 px frame")
            if str(ll.child(controls["BTN_SEL1"], "BORDER").get_resref("CORNER")) != "mod_frame":
                fail("classsel.gui: the mod's own corner art was cleared")
            if str(ll.child(controls["BTN_SEL1"], "BORDER").get_resref("EDGE")):
                fail("classsel.gui: the game's original edge art was not cleared")
    # A file laid out for another size: refused by both.
    out = tmp / "refused.gui"
    out.unlink(missing_ok=True)
    code = subprocess.run([str(helper()), "live", native_helpers.arg(ll.VANILLA / name), name, "1920", "1080",
                           native_helpers.arg(out), native_helpers.arg(hires)],
                          stdout=subprocess.DEVNULL).returncode
    if code != 0 or out.exists() or python_layout(name, hires, 1920, 1080, rows[name]) is not None:
        fail(f"{name}: a file laid out for 1920x1080 was not refused")
    return diffs, checked


if __name__ == "__main__":
    sys.exit(main())
