#!/usr/bin/env python3
"""Pack everything the Mac installer puts in the game's override folder into one bank, which
make_kmrp_patch.py links into kmrp.dylib, so that kmrp.kpatch alone is the whole of KMRP.

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
    engine/kmrp-sdl3.dylib  SDL, for the controller (optional)

The file, little endian:

    "KMAST001"
    32 bytes   SHA-256 of everything after this field: the build's identity, which names the cache
    u32        groups
    u32        objects
    32 bytes   the object that is gui-blend.bin
    groups     u32 width, u32 height, u32 entries, then per entry: u16 length, name, 32-byte object
               (0, 0) is KMRP's own artwork and SDL; (0, 1) the bundled third-party art;
               every other group is the set for that size
    objects    32-byte SHA-256, u32 size, u32 stored size, then the object, zlib-compressed

Each object is stored once, whatever names it has in however many groups.

    python macos/tools/make_kmrp_assets.py --package DIR --out FILE
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import zipfile
import zlib
from pathlib import Path

MAGIC = b"KMAST001"
COMMON, BUNDLED = (0, 0), (0, 1)


def fail(message: str) -> None:
    raise SystemExit(f"make_kmrp_assets: {message}")


def name_field(name: str) -> bytes:
    data = name.encode("ascii")
    if not data or len(data) > 255 or "/" in name or "\\" in name or ".." in name:
        fail(f"unsafe file name {name!r}")
    return struct.pack("<H", len(data)) + data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--package", type=Path, required=True, help="the installer's payload folder")
    parser.add_argument("--out", type=Path, required=True)
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
    groups: list[tuple[tuple[int, int], list[tuple[str, bytes]]]] = [(COMMON, []), (BUNDLED, [])]
    art = sorted(p for p in (package / "override").iterdir() if p.is_file())
    if not art:
        fail(f"no artwork in {package / 'override'}")
    for path in art:
        groups[1 if path.name.lower() in bundled else 0][1].append((path.name, add(path.read_bytes())))
    missing = bundled - {name.lower() for name, _ in groups[1][1]}
    if missing:
        fail(f"bundled-override.txt names files the package does not carry: {sorted(missing)[:5]}")
    sdl = package / "engine" / "kmrp-sdl3.dylib"
    if sdl.is_file():
        groups[0][1].append((sdl.name, add(sdl.read_bytes())))

    with zipfile.ZipFile(package / "layouts.zip") as layouts:
        pooled: dict[str, bytes] = {}
        sizes = sorted((name[len("index/"):-len(".txt")] for name in layouts.namelist()
                        if name.startswith("index/") and name.endswith(".txt")),
                       key=lambda s: tuple(map(int, s.split("x"))))
        if not sizes:
            fail("layouts.zip holds no set")
        for size in sizes:
            width, height = map(int, size.split("x"))
            entries = []
            for line in layouts.read(f"index/{size}.txt").decode().replace("\r", "").splitlines():
                if not line:
                    continue
                name, short = line.split("\t")
                if short not in pooled:
                    data = layouts.read(f"objects/{short}")
                    key = add(data)
                    if key.hex()[:16].upper() != short.upper():
                        fail(f"layouts.zip: objects/{short} does not match its name")
                    pooled[short] = key
                entries.append((name, pooled[short]))
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
    print(f"{args.out.name}: {len(groups) - 2} sets, {len(groups[0][1])} files of KMRP's and SDL, "
          f"{len(groups[1][1])} bundled, {len(objects)} objects, {len(blob)} bytes, build {build.hex()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
