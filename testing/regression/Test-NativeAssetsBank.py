#!/usr/bin/env python3
"""Checks on KMRP's art pack, build/native-runtime/kmrp-assets.pack (KMRPAK01).

The pack (tools/kmrp_pack.py, since 2026-10-19; until then the bank inside the module,
KNAST002) names every file of every resolution's set and stores only the files the
module cannot make: tools/build_native_assets.py leaves out each file the blend helper
writes exactly as the set has it, and the module runs the helper and holds the result
against the index (src/controller-native/K1RuntimeAssets.cpp). What this proves, from
the built pack and the sets it was built from (it starts no game):

  1. The index is complete: 67 groups, each set's group naming exactly its archive's
     files with their SHA-256, but for Live Adaptive Layout's screens, which no set
     names since 2026-10-30 (the module lays them out at run time); the common group and
     SDL included; and the pack is the one the module was built for (KMRP_ASSET_BUILD).
  2. Nothing is missing that the module cannot make: every common file is stored;
     in a set, the two files the helper reads and every font are stored, and a file
     that is not stored is one of the kinds the helper writes.
  3. Every stored file comes back from its block, through its filter, with its
     SHA-256: read by the module's own decoder (K1AssetPack.cpp and the LZMA SDK's,
     testing/regression/asset_pack_harness.cpp, built x86 by Test-AssetPack.cmd).
  4. What was left out can be made: for a sample of sets (every set with --all), the
     helper, built here independently of the build's own, is run on the files the
     pack stores, and every left-out file it writes has the index's SHA-256. A
     listed size outside the blend must have every file stored.

Needs a built pack (src/controller-native/build_native_runtime.cmd), the archives in
build/kmrp/resources, MSVC for the decoder, and a C compiler for the helper (clang or
MSVC).

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_native_assets as builder   # noqa: E402
import kmrp_pack                        # noqa: E402
import native_helpers                   # noqa: E402

PACK = ROOT / "build/native-runtime/kmrp-assets.pack"
GENERATED = ROOT / "build/native-runtime/NativeAssets.generated.h"
CHECKER = ROOT / "build/asset-pack-test/asset-pack-check.exe"
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="rebuild the left-out files of every set, not a sample")
    args = parser.parse_args()

    identity, group_list, objects, blocks, table_key, blob = kmrp_pack.read_pack(PACK)
    built_for = re.search(r'KMRP_ASSET_BUILD L"([0-9a-f]{64})"', GENERATED.read_text())
    check(bool(built_for) and built_for[1] == identity,
          f"the pack is KMRPAK01, {len(blob):,} bytes, the one the module was built for ({identity[:16]})")
    groups = {f"{width}x{height}": dict(entries) for (width, height), entries in group_list}
    check(len(group_list) == 67 and table_key in objects,
          f"{len(group_list)} groups and {len(objects):,} stored files in {len(blocks)} blocks, read to the "
          f"first block, the blend table among them")

    # 1. The index against the archives.
    archives = {"0x0": RESOURCES / "override-common.zip"}
    archives.update({p.stem[4:]: p for p in RESOURCES.glob("gui-*.zip")})
    wrong = []
    for size, archive in archives.items():
        with zipfile.ZipFile(archive) as z:
            # A set names none of Live Adaptive Layout's screens (since 2026-10-30): the
            # module lays them out at run time and takes the helper's out of the set.
            expected = {name: hashlib.sha256(z.read(name)).digest() for name in z.namelist()
                        if name not in builder.FONT_FILES
                        and not (size != "0x0" and name.lower() in builder.LIVE_LAYOUTS)}
        entries = dict(groups.get(size, {}))
        if size == "0x0":
            entries.pop("kmrp-sdl3.dll", None)
            # The two font styles' sources (K1RuntimeAssets.cpp ApplyTextPreferences): the
            # original atlases and HD Original, under private names; and the old HD font's
            # TXI files alone, the size reference (FontSizes; its atlases gone 2026-10-31).
            original = ROOT / 'build/native-runtime/original-fonts'
            for index, name in enumerate(builder.FONT_RESREFS):
                for extension in ('.tga', '.txi'):
                    sources = [('kmrfog', original / f'kmrfog{index:02d}{extension}'),
                               ('kmrfho', builder.hd_original(name, extension))]
                    if extension == '.txi':
                        sources.append(('kmrfhd', ROOT / 'assets/hd-fonts' / (name + extension)))
                    for prefix, source in sources:
                        check(entries.pop(f'{prefix}{index:02d}{extension}', None) == hashlib.sha256(source.read_bytes()).digest(),
                              f"{prefix} font {name}{extension} has its source's hash")
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
        bad += [f"{size} lacks {n}" for n in builder.HELPER_INPUTS
                if n not in builder.FONT_FILES and (n not in entries or entries[n] not in objects)]
    total = sum(len(v) for v in left_out.values())
    check(not bad, f"{total:,} files are left to the module, every one a layout, a badge, the manifest or the HUD box; "
                   f"the helper's non-font inputs are stored, and fonts have shared sources" + (f": {bad[:6]}" if bad else ""))
    # Most, as a share: more than 40,000 until 2026-10-27, when the sets stopped carrying
    # the controller's badges (Windows' controller patch draws its own) and the files left
    # out became the layouts alone, about four in five of the sets' files.
    all_files = sum(len(e) for s, e in groups.items() if s != '0x0')
    check(total > all_files * 0.6, f"the pack leaves out most of the sets' files ({total:,} of "
                         f"{sum(len(e) for s, e in groups.items() if s != '0x0'):,}; {len(whole)} sets are stored whole: "
                         f"{', '.join(sorted(whole)) or 'none'})")

    # 3. Every stored file is what its key says, as the module reads it.
    if sys.platform == "win32":
        subprocess.run(["cmd.exe", "/c", str(ROOT / "testing/regression/Test-AssetPack.cmd")], check=True)
        checker = CHECKER
    else:
        checker = Path(tempfile.mkdtemp()) / "asset-pack-check"
        subprocess.run(["clang", "-O2", "-c", str(ROOT / "third_party/lzma-sdk/LzmaDec.c"), "-o",
                        str(checker) + ".o"], check=True)
        subprocess.run(["clang++", "-O2", "-std=c++17", "-I", str(ROOT / "src/controller-native"), "-I",
                        str(ROOT / "third_party/lzma-sdk"), str(ROOT / "testing/regression/asset_pack_harness.cpp"),
                        str(ROOT / "src/controller-native/K1AssetPack.cpp"), str(checker) + ".o", "-o", str(checker)],
                       check=True)
    done = subprocess.run([str(checker), str(PACK), identity], capture_output=True, text=True)
    lines = done.stdout.strip().splitlines()
    check(done.returncode == 0 and lines[-1:] == ["PASS"],
          f"the module's decoder gives back every stored file with its SHA-256: {lines[0] if lines else done.returncode}")

    # The files section 4 needs (kmrp_prompts.txt and the blend table, never filtered),
    # read here with Python's own LZMA.
    unpacked = {}

    def stored(key: bytes) -> bytes:
        size, block, offset, filter_id = objects[key]
        if filter_id != 0:
            raise ValueError("a filtered file is read by the module's decoder only")
        if block not in unpacked:
            start, length, total, properties = blocks[block]
            unpacked[block] = kmrp_pack._unpack(blob[start:start + length], properties, total)
        data = unpacked[block][offset:offset + size]
        if hashlib.sha256(data).digest() != key:
            raise ValueError("a stored file is not what its key says")
        return data

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
                (inputs / name).write_bytes(builder.shared_font_txi(name[:-4], size.split('x')[1])
                                           if name in builder.FONT_FILES else stored(entries[name]))
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
