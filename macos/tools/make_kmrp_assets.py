#!/usr/bin/env python3
"""Pack everything the Mac installer puts in the game's override folder into one bank, which
make_kmrp_patch.py links into kmrp.dylib, so that KMRP-macOS.kpatch alone is the whole of KMRP.

The Mac counterpart of tools/build_native_assets.py, which does this for Windows' module. The
module unpacks the bank to a cache of its own and registers it with the game's resource manager
(macos/patches/kmrp-layout/assets.cpp); nothing is written to the game's override folder.

What goes in, from the package macos/build.sh has already laid out:

    override/             KMRP's artwork, and the third-party art it bundles
    bundled-override.txt  which of those files are the third-party art, which yields to a file
                          the player already has
    layouts.zip           every resolution's menu set, pooled (index/<W>x<H>.txt names each
                          file's object, objects/<first 16 hex digits of its SHA-256>)
    gui-blend.bin         the table kmrp-guiblend blends any other size from

The file, little endian:

    "KMAST002"   (001 until 2026-10-08, when every entry's object was in the bank)
    32 bytes   SHA-256 of everything after this field: the build's identity, which names the cache
    u32        groups
    u32        objects
    32 bytes   the object that is gui-blend.bin
    groups     u32 width, u32 height, u32 entries, then per entry: u16 length, name, 32-byte object
               (0, 0) is KMRP's own artwork; (0, 1) the bundled third-party art; (0, 2), since
               2026-10-08, the part of that art that is the HD icon pack (--hd-icons), which the
               module leaves out when the patch's hd-icons option is off;
               every other group is the set for that size
    objects    32-byte SHA-256, u32 size, u32 stored size, then the object, zlib-compressed

Each object is stored once, whatever names it has in however many groups.

Since 2026-10-08, with --helper (macos/build.sh passes the kmrp-guiblend it has just built), the
bank leaves out what the module can make itself, as Windows' bank does since 2026-10-05
(tools/build_native_assets.py, whose rule this is): the module carries the blend helper, which
writes a size's layouts, badges, prompt manifest and HUD box from gui-blend.bin, and for most
listed sizes what it writes is the build's own set, byte for byte. The helper is run here for
every set, as x86_64 code like the module's copy, and an object is stored only when some file
that needs it is not what the helper writes: a font, a file of a set outside the blend, a file
the blend makes differently than the build did, or one of the two files the helper reads. A
set's entries still name every file with its SHA-256; an entry whose object the bank does not
hold is the module's to make and to hold against that hash (assets.cpp, BuildSet). Measured on
the build of 2026-10-08: 216,600,987 bytes with every object (32,135 objects), 104,605,483
like this (3,865 objects; 59,285 of the sets' 64,482 files left to the module); 45 sets are
rebuilt whole, 20 in part and 1280x1080, outside the blend, is stored whole.

    python macos/tools/make_kmrp_assets.py --package DIR --out FILE [--helper KMRP-GUIBLEND]
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAGIC = b"KMAST002"
# What the blend helper reads from a set (its caption widths and its font's metrics): kept in the
# bank even where the helper writes them back unchanged.
HELPER_INPUTS = ("kmrp_prompts.txt", "dialogfont16x16.txi")
COMMON, BUNDLED, ICONS = (0, 0), (0, 1), (0, 2)


def fail(message: str) -> None:
    raise SystemExit(f"make_kmrp_assets: {message}")


def name_field(name: str) -> bytes:
    data = name.encode("ascii")
    if not data or len(data) > 255 or "/" in name or "\\" in name or ".." in name:
        fail(f"unsafe file name {name!r}")
    return struct.pack("<H", len(data)) + data


def rebuilt_names(helper: Path, table: Path, size: str, files: dict[str, bytes], work: Path) -> tuple[set, int]:
    """The names of the set's files that the helper writes exactly as the set has them, and how
    many it writes differently (-1: the size is outside the blend, and the set keeps every file).
    The helper is run as the module runs its copy of it: the x86_64 code, which the game is."""
    width, height = size.split("x")
    inputs, out = work / f"in-{size}", work / f"out-{size}"
    inputs.mkdir()
    for name in HELPER_INPUTS:
        (inputs / name).write_bytes(files[name])
    done = subprocess.run(["arch", "-x86_64", str(helper), str(table), width, height, str(out), str(inputs)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    shutil.rmtree(inputs)
    if done.returncode == 2:
        return set(), -1
    if done.returncode:
        fail(f"{size}: the helper failed: {done.stderr.strip()}")
    same, different = set(), 0
    for path in out.iterdir():
        if path.name not in files:
            fail(f"{size}: the helper wrote {path.name}, which the set does not have")
        if path.read_bytes() == files[path.name]:
            same.add(path.name)
        else:
            different += 1
    shutil.rmtree(out)
    return same, different


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--package", type=Path, required=True, help="the installer's payload folder")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--hd-icons", type=Path, required=True,
                        help="the HD icon pack's folder: the bundled files of these names are a group of their own")
    parser.add_argument("--helper", type=Path,
                        help="kmrp-guiblend, built: what it writes for a set exactly as the set has it is left out")
    args = parser.parse_args()
    package: Path = args.package

    objects: dict[bytes, tuple[int, bytes]] = {}

    def add(data: bytes) -> bytes:
        key = hashlib.sha256(data).digest()
        if key not in objects:
            if not data:
                fail("an empty file cannot be stored")
            objects[key] = (len(data), zlib.compress(data, 9))
        return key

    bundled = {line.strip().lower() for line in (package / "bundled-override.txt").read_text().splitlines() if line.strip()}
    groups: list[tuple[tuple[int, int], list[tuple[str, bytes]]]] = [(COMMON, []), (BUNDLED, []), (ICONS, [])]
    # By name without its kind: the pack's .tga files are bundled as .tpc.
    pack = {p.stem.lower() for p in args.hd_icons.iterdir() if p.is_file()}
    icons = {name for name in bundled if name.rsplit(".", 1)[0] in pack}
    if not pack or {name.rsplit(".", 1)[0] for name in icons} != pack:
        fail(f"{args.hd_icons} is not the icon pack the package bundles")
    art = sorted(p for p in (package / "override").iterdir() if p.is_file())
    if not art:
        fail(f"no artwork in {package / 'override'}")
    for path in art:
        lower = path.name.lower()
        groups[2 if lower in icons else 1 if lower in bundled else 0][1].append((path.name, add(path.read_bytes())))
    missing = bundled - {name.lower() for name, _ in groups[1][1] + groups[2][1]}
    if missing:
        fail(f"bundled-override.txt names files the package does not carry: {sorted(missing)[:5]}")

    # Every set's files first, then what the module can make of them itself (--helper), and only
    # then the objects: one is stored when some file that needs it is not what the helper writes.
    sets: list[tuple[str, dict[str, bytes]]] = []
    with zipfile.ZipFile(package / "layouts.zip") as layouts:
        pooled: dict[str, bytes] = {}
        sizes = sorted((name[len("index/"):-len(".txt")] for name in layouts.namelist()
                        if name.startswith("index/") and name.endswith(".txt")),
                       key=lambda s: tuple(map(int, s.split("x"))))
        if not sizes:
            fail("layouts.zip holds no set")
        for size in sizes:
            files: dict[str, bytes] = {}
            for line in layouts.read(f"index/{size}.txt").decode().replace("\r", "").splitlines():
                if not line:
                    continue
                name, short = line.split("\t")
                if short not in pooled:
                    data = layouts.read(f"objects/{short}")
                    if hashlib.sha256(data).hexdigest()[:16].upper() != short.upper():
                        fail(f"layouts.zip: objects/{short} does not match its name")
                    pooled[short] = data
                files[name] = pooled[short]
            sets.append((size, files))

    made: dict[str, set] = {}
    if args.helper:
        with tempfile.TemporaryDirectory() as work:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(
                    lambda item: rebuilt_names(args.helper, package / "gui-blend.bin", item[0], item[1], Path(work)), sets))
        whole = part = outside = 0
        for (size, files), (same, different) in zip(sets, results):
            made[size] = same - set(HELPER_INPUTS)
            whole, part, outside = whole + (different == 0), part + (different > 0), outside + (different < 0)
            if different:
                print(f"  {size}: " + ("outside the blend, every file stored" if different < 0 else
                                       f"the helper rebuilds {len(same)} files, {different} differ and are stored"))
        print(f"{whole} sets rebuilt whole by the module, {part} in part, {outside} stored whole")

    left_out: set[bytes] = set()
    files_left = files_all = 0
    for size, files in sets:
        width, height = map(int, size.split("x"))
        entries = []
        for name, data in files.items():
            files_all += 1
            if name in made.get(size, ()):
                key = hashlib.sha256(data).digest()
                left_out.add(key)
                files_left += 1
            else:
                key = add(data)
            entries.append((name, key))
        groups.append(((width, height), entries))

    table = add((package / "gui-blend.bin").read_bytes())

    body = bytearray(struct.pack("<II", len(groups), len(objects)) + table)
    for (width, height), entries in groups:
        body += struct.pack("<III", width, height, len(entries))
        for name, key in entries:
            body += name_field(name) + key
    for key, (size, stored) in objects.items():
        body += key + struct.pack("<II", size, len(stored)) + stored
    build = hashlib.sha256(body).digest()
    blob = MAGIC + build + bytes(body)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(blob)
    if args.out.read_bytes() != blob:
        fail("the bank does not read back")
    if args.helper:
        print(f"{len(left_out - set(objects))} objects left to the module to make "
              f"({files_left} of the sets' {files_all} files)")
    print(f"{args.out.name}: {len(groups) - 3} sets, {len(groups[0][1])} files of KMRP's, "
          f"{len(groups[1][1])} bundled and {len(groups[2][1])} of the HD icon pack, {len(objects)} objects, {len(blob)} bytes, build {build.hex()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
