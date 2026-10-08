#!/usr/bin/env python3
"""Checks on KMRP's resource bank, build/native-runtime/native-assets.bin (KNAST002).

Since 2026-10-05 the bank names every file of every resolution's set and stores only
the objects the module cannot make: tools/build_native_assets.py leaves out each file
the blend helper writes exactly as the set has it, and the module runs the helper and
holds the result against the index (src/controller-native/K1RuntimeAssets.cpp). What
this proves, from the built bank and the sets it was built from (it starts no game):

  1. The index is complete: 67 groups, each set's group naming exactly its archive's
     files with their SHA-256, the common group and SDL included.
  2. Nothing is missing that the module cannot make: every common file is stored;
     in a set, the two files the helper reads and every font are stored, and a file
     that is not stored is one of the kinds the helper writes.
  3. Every stored object decompresses to its key.
  4. What was left out can be made: for a sample of sets (every set with --all), the
     helper, built here independently of the build's own, is run on the files the
     bank stores, and every left-out file it writes has the index's SHA-256. A
     listed size outside the blend must have every file stored.

Needs a built bank (src/controller-native/build_native_runtime.cmd), the archives in
build/kmrp/resources, and a C compiler for the helper (clang or MSVC).

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import struct
import subprocess
import sys
import tempfile
import zipfile
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_native_assets as builder   # noqa: E402
import native_helpers                   # noqa: E402

BANK = ROOT / "build/native-runtime/native-assets.bin"
RESOURCES = ROOT / "build/kmrp/resources"
# Checked every run: two anchors, the maintainer's own size (a listed size that is not
# an anchor), the listed size nearest another of its height, the smallest and the largest.
SAMPLE = ("1920x1080", "2560x1440", "3440x1440", "1360x768", "1280x720", "5120x2880")
failures = []


def check(condition: bool, text: str) -> None:
    print(("ok    " if condition else "FAIL  ") + text)
    if not condition:
        failures.append(text)


def helper_made(name: str) -> bool:
    """A file of the kinds the blend helper writes: layouts, badges, the prompt
    manifest and the HUD box."""
    return name.endswith(".gui") or (name.startswith(("kmr", "kmf")) and name.endswith(".tga")) \
        or name in ("kmrp_prompts.txt", "lbl_mileftbot.tga")


def decompress(api, handle, data: bytes, size: int) -> bytes:
    out = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if not api.Decompress(handle, data, len(data), out, size, ctypes.byref(got)):
        raise ctypes.WinError(ctypes.get_last_error())
    return out.raw[:got.value]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="rebuild the left-out files of every set, not a sample")
    args = parser.parse_args()

    blob = BANK.read_bytes()
    check(blob[:8] in builder.ALGORITHMS, f"the bank is {blob[:8].decode('ascii', 'replace')}, {len(blob):,} bytes")
    group_count, object_count = struct.unpack_from("<II", blob, 8)
    table_key = blob[16:48]
    at = 48
    groups = {}
    for _ in range(group_count):
        width, height, count = struct.unpack_from("<III", blob, at)
        at += 12
        entries = {}
        for _ in range(count):
            n = struct.unpack_from("<H", blob, at)[0]
            entries[blob[at + 2:at + 2 + n].decode()] = blob[at + 2 + n:at + 34 + n]
            at += 34 + n
        groups[f"{width}x{height}"] = entries
    objects = {}
    for _ in range(object_count):
        key = blob[at:at + 32]
        size, packed = struct.unpack_from("<II", blob, at + 32)
        objects[key] = (size, at + 40, packed)
        at += 40 + packed
    check(at == len(blob) and group_count == 67 and table_key in objects,
          f"{group_count} groups and {object_count:,} stored objects, read to the last byte, the blend table among them")

    # 1. The index against the archives.
    archives = {"0x0": RESOURCES / "override-common.zip"}
    archives.update({p.stem[4:]: p for p in RESOURCES.glob("gui-*.zip")})
    wrong = []
    for size, archive in archives.items():
        with zipfile.ZipFile(archive) as z:
            expected = {name: hashlib.sha256(z.read(name)).digest() for name in z.namelist()}
        entries = dict(groups.get(size, {}))
        if size == "0x0":
            entries.pop("kmrp-sdl3.dll", None)
        if entries != expected:
            wrong.append(size)
    check(not wrong and set(archives) == set(groups),
          "every group names exactly its archive's files with their SHA-256" + (f": {wrong[:6]}" if wrong else ""))

    # 2. What is stored and what is not.
    missing_common = [n for n, key in groups["0x0"].items() if key not in objects]
    check(not missing_common, f"all {len(groups['0x0'])} common files are stored")
    # The module's rule for the hd-icons option (HdIcon, K1RuntimeAssets.cpp) against
    # the pack itself: the same 351 names, and no other common file.
    pack = ROOT / "third_party/Included/KOTOR1 HD ICON PACK ver1.0 1.0.0 by JackInTheBox/Override"
    pack_names = {p.stem.lower() + ".tpc" for p in pack.glob("*.tga")}
    by_rule = {n.lower() for n in groups["0x0"]
               if n.lower().endswith(".tpc") and len(n) >= 8 and n[0] in "iI" and n[1] in "aiwAIW" and n[2] == "_"}
    check(by_rule == pack_names and len(pack_names) == 351,
          f"the hd-icons option's name rule picks the HD Icon Pack's {len(pack_names)} icons and nothing else")
    bad, left_out, whole = [], {}, []
    for size, entries in groups.items():
        if size == "0x0":
            continue
        absent = [n for n, key in entries.items() if key not in objects]
        left_out[size] = absent
        if not absent:
            whole.append(size)
        bad += [f"{size} {n}" for n in absent if not helper_made(n) or n in builder.HELPER_INPUTS]
        bad += [f"{size} lacks {n}" for n in builder.HELPER_INPUTS if n not in entries or entries[n] not in objects]
    total = sum(len(v) for v in left_out.values())
    check(not bad, f"{total:,} files are left to the module, every one a layout, a badge, the manifest or the HUD box; "
                   f"the helper's inputs and every font are stored" + (f": {bad[:6]}" if bad else ""))
    check(total > 40000, f"the bank leaves out most of the sets' files ({total:,} of "
                         f"{sum(len(e) for s, e in groups.items() if s != '0x0'):,}; {len(whole)} sets are stored whole: "
                         f"{', '.join(sorted(whole)) or 'none'})")

    # 3. Every stored object is what its key says.
    api = ctypes.WinDLL("cabinet", use_last_error=True)
    api.CreateDecompressor.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    api.Decompress.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t,
                               ctypes.POINTER(ctypes.c_size_t)]
    handle = ctypes.c_void_p()
    if not api.CreateDecompressor(builder.ALGORITHMS.get(blob[:8], 4), None, ctypes.byref(handle)):
        raise ctypes.WinError(ctypes.get_last_error())

    def stored(key: bytes) -> bytes:
        size, start, packed = objects[key]
        return decompress(api, handle, blob[start:start + packed], size)

    corrupt = sum(1 for key in objects if hashlib.sha256(stored(key)).digest() != key)
    check(corrupt == 0, f"all {len(objects):,} stored objects decompress to their keys")

    # 4. The left-out files, made again.
    sizes = sorted(s for s in groups if s != "0x0") if args.all else list(SAMPLE)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        built = native_helpers.build(ROOT / "macos" / "tools" / "kmrp-guiblend.c", tmp, "kmrp-guiblend")
        helper = next(iter(built.values()))
        table = tmp / "gui-blend.bin"
        table.write_bytes(stored(table_key))
        unmade = []
        for size in sizes:
            entries = groups[size]
            inputs, out = tmp / f"in-{size}", tmp / f"out-{size}"
            inputs.mkdir()
            for name in builder.HELPER_INPUTS:
                (inputs / name).write_bytes(stored(entries[name]))
            width, height = size.split("x")
            done = subprocess.run([str(helper), native_helpers.arg(table), width, height, native_helpers.arg(out),
                                   native_helpers.arg(inputs)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if done.returncode == 2:
                if left_out[size]:
                    unmade.append(f"{size}: outside the blend, with {len(left_out[size])} files left out")
                continue
            if done.returncode:
                unmade.append(f"{size}: the helper failed: {done.stderr.strip()[:80]}")
                continue
            for name in left_out[size]:
                path = out / name
                if not path.exists() or hashlib.sha256(path.read_bytes()).digest() != entries[name]:
                    unmade.append(f"{size} {name}")
        check(not unmade, f"the helper ({native_helpers.slices(built)}, built here) makes every left-out file of "
                          f"{len(sizes)} sets exactly: {sum(len(left_out[s]) for s in sizes):,} files"
                          + (f"; NOT {unmade[:6]}" if unmade else ""))

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
