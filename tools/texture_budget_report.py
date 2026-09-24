#!/usr/bin/env python3
"""What KMRP's own textures cost against the engine's texture-memory budget.

The engine does not measure textures in file bytes. It measures them the way
`CAurTextureBasic::GetMemoryUsage` (0x00420710) does, and that is what this
reproduces -- see reverse-engineering/texture-residency.md for how it was read.

    shift = downsample level currently applied
    w = max(width  >> shift, 2)
    h = max(height >> shift, 2)

    compressed    ImageGetS3TCSize(w, h, fmt)      (0x0045E270)
                    blocks = ceil(w/4) * ceil(h/4)
                    bytes  = blocks * (fmt == 4 ? 16 : 8)     DXT5 : DXT1
    uncompressed  bytes = bpp * w * h
                    bpp = 2 when the 16-bit display mode is set,
                          4 when the texture's depth field is 3,
                          otherwise the depth field itself
    mipmapped     bytes = bytes * 4 / 3            the chain's overhead

Why it matters: when the total crosses the budget from `texpacks.2da`,
`AurTextureMemCheck` (0x00421AC0) raises `downsamplemax` and the affected
textures are rebuilt. A texture being rebuilt has no image, and a GUI fill with
no image binds no texture and draws as flat white -- the reported flash.

Shipping art that already fits therefore avoids the rebuild entirely, which is
cheaper than making the engine discover the same thing every time a screen opens.

    python tools/texture_budget_report.py [--resolution 3440x1440]
"""
from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "build" / "kmrp" / "resources"

# texpacks.2da, read from a live installation. `mem` x `dynmemratio`.
BUDGETS = {
    "32MB  (Texture Quality 0)": int(31_457_280 * 0.750),
    "64MB  (Texture Quality 1)": int(62_900_000 * 0.750),
    "128MB (Texture Quality 2)": int(134_217_728 * 0.750),
}

DXT1, DXT5 = 8, 16


def s3tc_size(width: int, height: int, block_bytes: int) -> int:
    """ImageGetS3TCSize, 0x0045E270: whole 4x4 blocks, never fewer than one."""
    width = max(width, 1)
    height = max(height, 1)
    return ((width + 3) // 4) * ((height + 3) // 4) * block_bytes


def resident_bytes(width: int, height: int, *, block_bytes: int | None,
                   bpp: int = 4, mipmapped: bool = False, shift: int = 0) -> int:
    """One texture's cost, by the engine's own arithmetic."""
    w = max(width >> shift, 2)
    h = max(height >> shift, 2)
    total = s3tc_size(w, h, block_bytes) if block_bytes else bpp * w * h
    if mipmapped:
        total = total * 4 // 3
    return total


def measure_tga(blob: bytes) -> tuple[int, int, int] | None:
    """(width, height, bytes-per-pixel) from an uncompressed TGA header."""
    if len(blob) < 18:
        return None
    width, height, depth = struct.unpack_from("<HHB", blob, 12)
    if not width or not height:
        return None
    return width, height, max(depth // 8, 1)


def measure_tpc(blob: bytes) -> tuple[int, int, int | None, bool] | None:
    """(width, height, block bytes or None, mipmapped) from a TPC header.

    128-byte header: dataSize, alphaBlending, width, height, encoding, mips.
    Encoding 2 is DXT1 where dataSize is non-zero, 4 is DXT5; a zero dataSize
    means the payload is uncompressed.
    """
    if len(blob) < 128:
        return None
    data_size, _alpha, width, height, encoding, mips = struct.unpack_from(
        "<IfHHBB", blob, 0)
    if not width or not height:
        return None
    if data_size == 0:
        return width, height, None, mips > 1
    return width, height, (DXT5 if encoding == 4 else DXT1), mips > 1


def measure(name: str, blob: bytes):
    lowered = name.lower()
    if lowered.endswith(".tpc"):
        got = measure_tpc(blob)
        if not got:
            return None
        width, height, block, mips = got
        return width, height, resident_bytes(
            width, height, block_bytes=block, mipmapped=mips), (
                "DXT5" if block == DXT5 else "DXT1" if block else "raw")
    if lowered.endswith(".tga"):
        got = measure_tga(blob)
        if not got:
            return None
        width, height, bpp = got
        return width, height, resident_bytes(
            width, height, block_bytes=None, bpp=bpp), f"{bpp * 8}-bit"
    return None


def survey(archive: Path):
    rows = []
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            if not info.filename.lower().endswith((".tga", ".tpc")):
                continue
            got = measure(info.filename, bundle.read(info.filename))
            if got:
                width, height, cost, kind = got
                rows.append((cost, info.filename, width, height, kind,
                             info.file_size))
    rows.sort(reverse=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", default="3440x1440")
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    archives = [RESOURCES / "override-common.zip",
                RESOURCES / f"gui-{args.resolution}.zip"]
    missing = [a for a in archives if not a.exists()]
    if missing:
        print("Build the resources first; missing: "
              + ", ".join(a.name for a in missing), file=sys.stderr)
        return 1

    grand = 0
    for archive in archives:
        rows = survey(archive)
        total = sum(row[0] for row in rows)
        grand += total
        print(f"\n{archive.name}: {len(rows)} textures, "
              f"{total:,} bytes resident ({total / 1048576:.1f} MB)")
        print(f"  {'texture':<28} {'pixels':>12} {'kind':>8} "
              f"{'resident':>12} {'on disk':>12}")
        for cost, name, width, height, kind, packed in rows[:args.top]:
            print(f"  {name:<28} {width:>5}x{height:<6} {kind:>8} "
                  f"{cost:>12,} {packed:>12,}")

    print(f"\nKMRP art total: {grand:,} bytes ({grand / 1048576:.1f} MB)")
    print("\nAgainst the engine's budget -- shared with everything else "
          "resident, so this is a floor, not a forecast:")
    for label, budget in BUDGETS.items():
        share = grand / budget * 100
        print(f"  {label:<26} {budget:>12,}   KMRP art is {share:6.1f}% of it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
