#!/usr/bin/env python3
"""Read a kmrp-kpm.dat, and prove it makes the same game as the standalone installer.

The KPM edition's installer writes kmrp-kpm.dat (src/patcher/KpmEdition.cs); the
core patch's module applies it in memory (src/controller-native/K1KpmApplier.cpp),
the Movies and Map Notes parts only when those patches are ticked in KOTOR Patch
Manager. This does what the module does, in Python, on the clean executable's
bytes:

  --equals STANDALONE_EXE   apply with the block left where gold puts it (a delta
                            of zero) and require the result to be the standalone
                            installer's executable for the same resolution --
                            every byte of the original code and data, and the
                            eleven sections -- except where a patch left out
                            leaves the unmodified game's bytes. With all four
                            patches that is no exception at all; without Map
                            Notes it is the standalone with the marker fixes
                            off. The one thing the two editions may differ in is
                            the PE header, which the KPM edition never writes
                            (KPM's 4gb-patch sets its large-address flag).
  --memory                  compare against the RUNNING game instead: find where
                            the module put the block, and require every applied
                            run and every block byte to be exactly the data
                            file's, moved by that delta, and every run left out
                            to be the unmodified game's.

--features names the patches ticked (default: all four). KMRP Controller changes
no data, so it may be named or not.

Checks the file's own checksum and structure either way, as the module does.

Usage:
    python tools/kpm_data.py DAT --clean CLEAN_EXE --equals STANDALONE_EXE [--features IDS]
    python tools/kpm_data.py DAT --memory [--features IDS]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import struct
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

KIND = {1: "IN", 2: "OUT", 3: "ABS"}
# The feature bits K1KpmApplier.cpp gives each patch; KMRP Controller has none.
FEATURE = {"kmrp": 1, "kmrp-movies": 2, "kmrp-map-notes": 4, "kmrp-controller": 0}
NAME = {1: "core", 2: "movies", 4: "map notes"}


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def parse(path: Path):
    data = path.read_bytes()
    if data[:8] != b"KMRPKPM2":
        raise SystemExit(f"{path}: not a version 2 KMRP data file")
    if fnv1a(data[:-4]) != struct.unpack_from("<I", data, len(data) - 4)[0]:
        raise SystemExit(f"{path}: checksum mismatch")
    p = 8
    version, block_va, block_size, pages = struct.unpack_from("<IIII", data, p)
    p += 16
    protect = list(struct.unpack_from(f"<{pages}I", data, p))
    p += 4 * pages
    block = data[p:p + block_size]
    p += block_size
    (count,) = struct.unpack_from("<I", data, p)
    p += 4
    runs = []
    for _ in range(count):
        feature, va, n = struct.unpack_from("<III", data, p)
        p += 12
        runs.append((feature, va, data[p:p + n], data[p + n:p + 2 * n]))
        p += 2 * n
    (count,) = struct.unpack_from("<I", data, p)
    p += 4
    edits = []
    for _ in range(count):
        feature, at, n = struct.unpack_from("<III", data, p)
        p += 12
        edits.append((feature, at, data[p:p + n]))
        p += n
    (count,) = struct.unpack_from("<I", data, p)
    p += 4
    relocs = []
    for _ in range(count):
        kind, field = struct.unpack_from("<II", data, p)
        relocs.append((KIND[kind], field))
        p += 8
    if p != len(data) - 4:
        raise SystemExit(f"{path}: {len(data) - 4 - p} unexplained bytes")
    return {"version": version, "block_va": block_va, "block": block, "protect": protect,
            "runs": runs, "edits": edits, "relocs": relocs}


def sections(image: bytes):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    out = []
    for i in range(count):
        o = pe + 24 + optional + 40 * i
        _, va, rsize, raw = struct.unpack_from("<IIII", image, o + 8)
        out.append((base + va, raw, rsize))
    return out


def offset(secs, va):
    for sva, raw, size in secs:
        if sva <= va < sva + size:
            return raw + va - sva
    raise ValueError(hex(va))


def moved(dat, delta, features):
    """What the module writes for a delta and a set of feature bits:
    (applied runs with IN fields moved, runs left out, block with the chosen edits
    and OUT/ABS fields moved)."""
    applied = [(va, orig, bytearray(fin)) for f, va, orig, fin in dat["runs"] if f & features]
    left = [(va, orig) for f, va, orig, _ in dat["runs"] if not f & features]
    block = bytearray(dat["block"])
    for f, at, data in dat["edits"]:
        if f & features:
            block[at:at + len(data)] = data
    base = dat["block_va"]
    for kind, field in dat["relocs"]:
        if kind == "IN":
            for va, _, fin in applied:
                if va <= field and field + 4 <= va + len(fin):
                    v = struct.unpack_from("<I", fin, field - va)[0]
                    struct.pack_into("<I", fin, field - va, (v + delta) & 0xFFFFFFFF)
                    break
            else:
                if not any(va <= field and field + 4 <= va + len(o) for va, o in left):
                    raise SystemExit(f"IN {field:#010x} is not inside a run")
        else:
            v = struct.unpack_from("<I", block, field - base)[0]
            v = (v - delta if kind == "OUT" else v + delta) & 0xFFFFFFFF
            struct.pack_into("<I", block, field - base, v)
    return applied, left, bytes(block)


def equals(dat, clean_path: Path, standalone_path: Path, features: int) -> int:
    clean = clean_path.read_bytes()
    standalone = standalone_path.read_bytes()
    csec = sections(clean)
    ssec = sections(standalone)
    image = bytearray(clean)
    applied, left, block = moved(dat, 0, features)
    for va, orig, fin in applied:
        o = offset(csec, va)
        if bytes(image[o:o + len(orig)]) != orig:
            raise SystemExit(f"run {va:#010x}: its original bytes are not the clean executable's")
        image[o:o + len(fin)] = fin
    # What the standalone should be, where a patch was left out: the unmodified
    # game's bytes for its runs, and the block as the data file leaves it for its
    # edits.
    expected = bytearray(standalone)
    for va, orig in left:
        o = offset(ssec, va)
        expected[o:o + len(orig)] = orig
    block_off = offset(ssec, dat["block_va"])
    for f, at, data in dat["edits"]:
        if not f & features:
            expected[block_off + at:block_off + at + len(data)] = dat["block"][at:at + len(data)]
    problems = 0
    # every original section, byte for byte
    for sva, raw, size in csec:
        mine = bytes(image[raw:raw + size])
        theirs = bytes(expected[offset(ssec, sva):offset(ssec, sva) + size])
        if mine != theirs:
            first = next(i for i in range(size) if mine[i] != theirs[i])
            print(f"  section at {sva:#010x} differs first at {sva + first:#010x}")
            problems += 1
    # the block
    if bytes(expected[block_off:block_off + len(block)]) != block:
        first = next(i for i in range(len(block)) if expected[block_off + i] != block[i])
        print(f"  the eleven sections differ first at {dat['block_va'] + first:#010x}")
        problems += 1
    if problems:
        print(f"FAIL: kmrp-kpm.dat does not make the standalone executable ({problems})")
        return 1
    changed = sum(len(f) for _, _, f in applied)
    print(f"kmrp-kpm.dat with {describe(features)} makes exactly the standalone executable"
          f"{'' if not left else ' less the parts left out'}: {len(applied)} runs ({changed} bytes) "
          f"applied, {len(left)} left out, and the {len(block) // 4096} sections, every original "
          f"section byte for byte; {len(dat['relocs'])} relocations")
    return 0


def memory(dat, features: int) -> int:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    pid = int(subprocess.check_output(
        ["powershell", "-NoProfile", "-Command", "(Get-Process swkotor).Id"]).split()[0])
    h = k32.OpenProcess(0x0410, False, pid)

    def read(va, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(h, va, buf, n, ctypes.byref(got)):
            raise SystemExit(f"cannot read {va:#010x}")
        return buf.raw

    # the delta, from the first rel32 IN field of an applied run: its target moved
    # by exactly it
    gold = first = None
    for kind, field in dat["relocs"]:
        if kind != "IN" or field >= 0x0073D000:
            continue
        for f, va, _, fin in dat["runs"]:
            if f & features and va <= field < va + len(fin):
                first, gold = field, struct.unpack_from("<I", fin, field - va)[0]
                break
        if first is not None:
            break
    now = struct.unpack("<I", read(first, 4))[0]
    delta = (now - gold) & 0xFFFFFFFF
    base = (dat["block_va"] + delta) & 0xFFFFFFFF
    applied, left, block = moved(dat, delta, features)
    bad = 0
    for va, _, fin in applied:
        if read(va, len(fin)) != bytes(fin):
            print(f"  run {va:#010x} is not as applied")
            bad += 1
    for va, orig in left:
        if read(va, len(orig)) != orig:
            print(f"  run {va:#010x} was left out but is not the unmodified game's")
            bad += 1
    # .kfs is the one writable section because its code keeps state in its own page:
    # a count and a 64-slot table of fonts already scaled, which the game fills as it
    # runs (tools/build_font_scale_wrapper.py). Those bytes are the game's, not the
    # data file's; every other block byte must be exactly as applied.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_font_scale_wrapper as kfs                    # noqa: E402
    kfs_va = 0x0086F000
    live = range(kfs_va + kfs.OFF_DEDUP_COUNT - dat["block_va"],
                 kfs_va + kfs.OFF_SCALE_FN - dat["block_va"])
    memory_block = read(base, len(block))
    wrong = [i for i in range(len(block)) if memory_block[i] != block[i] and i not in live]
    if wrong:
        print(f"  the block at {base:#010x} is not as applied at "
              f"{len(wrong)} bytes, first gold VA {dat['block_va'] + wrong[0]:#010x}")
        bad += 1
    if bad:
        print(f"FAIL: the running game differs from kmrp-kpm.dat in {bad} places")
        return 1
    print(f"the running game carries kmrp-kpm.dat with {describe(features)} exactly: "
          f"{len(applied)} runs applied, {len(left)} left as the game's own, and KMRP's "
          f"code at {base:#010x} (moved by {delta if delta < 0x80000000 else delta - 0x100000000:+#x})")
    return 0


def describe(features: int) -> str:
    return " + ".join(NAME[b] for b in (1, 2, 4) if features & b)


def feature_bits(ids: str) -> int:
    bits = 0
    for name in (i.strip() for i in ids.split(",") if i.strip()):
        if name not in FEATURE:
            raise SystemExit(f"unknown patch id {name!r}; expected {', '.join(FEATURE)}")
        bits |= FEATURE[name]
    if not bits & 1:
        raise SystemExit("the core patch, kmrp, is always installed")
    return bits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dat", type=Path)
    parser.add_argument("--clean", type=Path)
    parser.add_argument("--equals", type=Path)
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--features", default="kmrp,kmrp-movies,kmrp-map-notes",
                        help="comma-separated ids of the patches ticked in KPM")
    parser.add_argument("--list", action="store_true", help="print every run and edit")
    arguments = parser.parse_args()
    dat = parse(arguments.dat)
    features = feature_bits(arguments.features)
    if arguments.memory:
        return memory(dat, features)
    if arguments.equals and arguments.clean:
        return equals(dat, arguments.clean, arguments.equals, features)
    counts = {}
    for f, _, _, fin in dat["runs"]:
        counts[f] = counts.get(f, 0) + 1
    print(f"{arguments.dat}: version {dat['version']}, {len(dat['runs'])} runs "
          f"({', '.join(f'{NAME[f]} {n}' for f, n in sorted(counts.items()))}), "
          f"{len(dat['edits'])} block edits, {len(dat['relocs'])} relocations, "
          f"block {dat['block_va']:#010x}+{len(dat['block']):#x}")
    if arguments.list:
        for f, va, orig, fin in dat["runs"]:
            if f != 1:
                print(f"  {NAME[f]:9} run  {va:#010x}+{len(fin)}  {orig.hex(' ')} -> {fin.hex(' ')}")
        for f, at, data in dat["edits"]:
            print(f"  {NAME[f]:9} edit {dat['block_va'] + at:#010x}+{len(data)}  -> {data.hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
