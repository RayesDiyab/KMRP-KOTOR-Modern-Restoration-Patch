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

RESOURCES = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "kmrp" / "resources"
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


def python_layout(name: str, source: Path, width: int, height: int, rows: dict) -> GFFStruct | None:
    vanilla = read_gff(ll.VANILLA / name).root
    return ll.layout(name, vanilla, read_gff(source).root, width, height, rows)


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


def main() -> int:
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
    for name in ll.FILES:
        for size in sizes:
            w, h = (int(x) for x in size.split("x"))
            ours = python_layout(name, ll.VANILLA / name, w, h, rows[name])
            theirs = built_file(size, name)
            a, b = numbers(ours), numbers(theirs)
            if a.keys() != b.keys():
                fail(f"{name} {size}: the structures differ from the set's")
                continue
            for k in a:
                d = abs(a[k] - b[k])
                if k[1] == "PADDING":
                    if d:
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
    print(f"against KMRP's {len(sizes)} sets, {len(ll.FILES)} screens: {total} EXTENT fields, "
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
        for name in ll.FILES:
            mod, hires, moved_tag = mod_files(name, tmp)
            cases = [(int(s.split("x")[0]), int(s.split("x")[1]), None) for s in sizes]
            cases += [(w, h, None) for w, h in extra]
            if mod:
                cases += [(w, h, mod) for w, h in ((1920, 1080), (3440, 1440), (2560, 1600), (1024, 768))]
            for w, h, source in cases:
                out = tmp / "out.gui"
                out.unlink(missing_ok=True)
                args = [str(helper), "live", native_helpers.arg(ll.VANILLA / name), name, str(w), str(h),
                        native_helpers.arg(out)] + ([native_helpers.arg(source)] if source else [])
                code = subprocess.run(args, stdout=subprocess.DEVNULL).returncode
                ours = python_layout(name, source or ll.VANILLA / name, w, h, rows[name])
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
            # A file laid out for another size: refused by both.
            out = tmp / "refused.gui"
            out.unlink(missing_ok=True)
            code = subprocess.run([str(helper), "live", native_helpers.arg(ll.VANILLA / name), name, "1920", "1080",
                                   native_helpers.arg(out), native_helpers.arg(hires)],
                                  stdout=subprocess.DEVNULL).returncode
            if code != 0 or out.exists() or python_layout(name, hires, 1920, 1080, rows[name]) is not None:
                fail(f"{name}: a file laid out for 1920x1080 was not refused")
        print(f"C against Python: {checked} layouts, {len(ll.FILES)} refused mods' files")

    print("FAILED" if failed else "PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
