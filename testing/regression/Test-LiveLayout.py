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

    python testing/regression/Test-LiveLayout.py [RESOURCES_DIR]
"""
from __future__ import annotations

import io
import copy
import argparse
import logging
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
                  caption: float | None = None) -> GFFStruct | None:
    vanilla = read_gff(ll.VANILLA / name).root
    return ll.layout(name, vanilla, read_gff(source).root, width, height, rows, caption)


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


def main() -> int:
    global RESOURCES
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path, nargs="?", default=RESOURCES)
    parser.add_argument("--screens", nargs="+", choices=ll.FILES, default=ll.FILES,
                        help="check selected screens; table and cue/options mod checks still run")
    args = parser.parse_args()
    RESOURCES = args.resources
    files = args.screens
    logging.disable(logging.DEBUG)
    failed = False

    def fail(message: str) -> None:
        nonlocal failed
        failed = True
        print("FAIL", message)

    # 1. The table.
    if ll.TABLE.read_text(encoding="ascii") != ll.render():
        fail(f"{ll.TABLE} is out of date: run python tools/build_live_layout.py")
    rows = ll.table_by_file()

    # 2. The Python against KMRP's sets.
    sizes = sorted(p.name[4:-4] for p in RESOURCES.glob("gui-*.zip"))
    if len(sizes) < 66:
        fail(f"{RESOURCES} has {len(sizes)} sets, expected 66")
    diffs = Counter()
    for name in files:
        for size in sizes:
            w, h = (int(x) for x in size.split("x"))
            caption = ll.manifest_caption(built_manifest(size))
            ours = python_layout(name, ll.VANILLA / name, w, h, rows[name], caption)
            theirs = built_file(size, name)
            a, b = numbers(ours), numbers(theirs)
            if a.keys() != b.keys():
                fail(f"{name} {size}: the structures differ from the set's")
                continue
            for k in a:
                d = abs(a[k] - b[k])
                if k[1] == "PADDING":
                    if d and size != "3440x1440" and centred_padding(name, size, k, ours, theirs):
                        print(f"note {name} {size} {k}: PADDING {a[k]}, the set has {b[k]} (its own list centred)")
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
                    print(f"note {name} {size} {k}: {a[k]}, the set has {b[k]} (gold moved it)")
                    continue
                if (d > limit(w) and size != "3440x1440"
                        and row_threshold(name, size, k, rows[name], caption)):
                    print(f"note {name} {size} {k}: {a[k]}, the set has {b[k]} (a row count crossed by the rounding pixel)")
                    continue
                if (size == "3440x1440" and d) or (d > limit(w) and not engine_placed):
                    fail(f"{name} {size} {k}: {a[k]}, the set has {b[k]}")
                elif d > 1:
                    print(f"note {name} {size} {k}: {a[k]}, the set has {b[k]}")
            # Every other field at every size (until 2026-10-28 at 3440x1440 only, which
            # hid that Character's LBL_LEVEL alignment, gold's at every size, was not carried).
            fa, fb = flat(ours), flat(theirs)
            for k in fa.keys() | fb.keys():
                if ".EXTENT." in k or k.endswith(".PADDING"):
                    continue
                x, y = fa.get(k), fb.get(k)
                if x == y:
                    continue
                if hasattr(x, "x") and hasattr(y, "x") and all(
                        abs(getattr(x, c) - getattr(y, c)) <= COLOUR_TOLERANCE for c in "xyz"):
                    continue
                fail(f"{name} {size} {k}: {x!r}, the set has {y!r}")
    total = sum(diffs.values())
    print(f"against KMRP's {len(sizes)} sets, {len(files)} screens: {total} EXTENT fields, "
          f"{100 * diffs['exact'] / total:.2f}% exact, {100 * diffs['1 px'] / total:.2f}% 1 px off, "
          f"{diffs['more']} further; 3440x1440 identical, every other field the set's at every "
          f"size, but for colour precision")

    # 3 and 4. The C against the Python.
    with tempfile.TemporaryDirectory(prefix="kmrp-livelayout-test-") as tmp:
        tmp = Path(tmp)
        if native_helpers.WINDOWS:
            helper = native_helpers.build(ROOT / "macos" / "tools" / "kmrp-guiadapt.c", tmp, "kmrp-guiadapt")["x64"]
        else:
            helper = tmp / "kmrp-guiadapt"
            subprocess.run(["clang", "-O2", "-o", str(helper), str(ROOT / "macos" / "tools" / "kmrp-guiadapt.c"),
                           "-lm"], check=True)
        rng = random.Random(20261028)
        extra = [(rng.randint(640, 15360), 0) for _ in range(200)]
        extra = [(w, rng.randint(max(480, w // 4), min(8640, w * 3 // 4 + 1))) for w, _ in extra]
        checked = 0
        for name in files:
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
                prompts = tmp / "kmrp_prompts.txt"
                prompts.write_text(manifest, encoding="utf-8")
                args = [str(helper), "live", native_helpers.arg(ll.VANILLA / name), name, str(w), str(h),
                        native_helpers.arg(out), native_helpers.arg(source) if source else "-",
                        native_helpers.arg(prompts)]
                code = subprocess.run(args, stdout=subprocess.DEVNULL).returncode
                ours = python_layout(name, source or ll.VANILLA / name, w, h, rows[name],
                                     ll.manifest_caption(manifest))
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
                if ours[(key, "LEFT")] == gold[(key, "LEFT")] or ours[(key, "TOP")] == gold[(key, "TOP")]:
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
            code = subprocess.run([str(helper), "live", native_helpers.arg(ll.VANILLA / name), name, "1920", "1080",
                                   native_helpers.arg(out), native_helpers.arg(hires)],
                                  stdout=subprocess.DEVNULL).returncode
            if code != 0 or out.exists() or python_layout(name, hires, 1920, 1080, rows[name]) is not None:
                fail(f"{name}: a file laid out for 1920x1080 was not refused")
        print(f"C against Python: {checked} layouts, {len(files)} refused mods' files")
        print(f"Cue mods: {check_cue_mods(helper, tmp, rows, fail)} layouts")
        print(f"Options mods: {check_options_mods(helper, tmp, rows, fail)} layouts")

    print("FAILED" if failed else "PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
