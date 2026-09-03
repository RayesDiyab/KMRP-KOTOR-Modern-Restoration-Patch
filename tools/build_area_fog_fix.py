#!/usr/bin/env python3
"""Make the AREA MAP's fog grid span the enlarged map surface.

**The symptom.** With the map enlarged, the full-screen map's fog only covers
the top-left corner of the map surface; the rest of the map is drawn unfogged
whether or not it has been explored. The HUD minimap is unaffected -- that path
is handled separately by `build_minimap_fog_fix.py`.

**The cause.** The fog walker at `0x0069449B` steps a grid across the map
surface. It derives the step from a *constant* viewport size, but normalises the
resulting coordinates by the *live* surface size held on the map object:

    0069449B  fild  dword ptr [esp+0x44]   ; columns
    006944A8  fdivr dword ptr [0x747748]   ; 440.0 / columns   <- constant width
    006944C0  fild  dword ptr [esp+0x50]   ; rows
    006944C4  fdivr dword ptr [0x7455D4]   ; 256.0 / rows      <- constant height
    006944D4  fmul  dword ptr [0x73F404]   ; x 4.0, the tile edge
    ...
    00694536  fild  dword ptr [ebx+0x10]   ; live surface height
    0069453E  fild  dword ptr [ebx+0x0C]   ; live surface width
    0069454A  fdiv  st(2)                  ; normalise the horizontal accumulator
    00694576  fdiv  st(1)                  ; ... and the vertical one

The horizontal accumulator runs 0 -> 440 in `columns` steps and is then divided
by `[ebx+0x0C]`, so the grid covers `440 / width` of the surface; likewise
`256 / height` vertically. In vanilla the map surface *is* 440x256, so the two
agree and the grid covers exactly 1.0 of it. Enlarge the surface and the grid
keeps its 440x256 reach -- at 1478x720 that is 29.8% x 35.6%, the top-left
corner.

**The fix.** Divide by the live fields instead of the constants. `FIDIVR
m32int` takes the same reversed-divide form as `FDIVR m32fp` and reads an
integer operand, which is exactly what `[ebx+0x0C]` and `[ebx+0x10]` hold:

    D8 3D 48 77 74 00   fdivr  dword ptr [0x747748]    (6 bytes)
    DA 7B 0C 90 90 90   fidivr dword ptr [ebx+0x0C]    (3 bytes + 3 NOP)

The grid then covers `width / width` = 1.0 at every resolution, by
construction. Nothing is tuned per resolution, so `ResolutionPatch` has no work
to do here and no private floats are needed.

`ebx` is the map object throughout: nothing between `0x006944A8` and the loop's
own `fild [ebx+0x10]` writes to it, which this script re-verifies before
patching.

The **shared** constants at `0x00747748` and `0x007455D4` are left alone -- the
HUD fog walker at `0x00688153` / `0x00688161` still reads them, which is why
this project never rewrites them in place.

Only whole instructions inside one basic block are rewritten, byte-for-byte in
place, so nothing moves and the file length is unchanged.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import capstone

from verify_map_patch import PEImage


IMAGE_BASE = 0x00400000

# (VA, expected bytes, replacement bytes, description)
FOG_SITES = (
    (0x006944A8,
     bytes.fromhex("d8 3d 48 77 74 00".replace(" ", "")),
     bytes.fromhex("da 7b 0c 90 90 90".replace(" ", "")),
     "fdivr [440.0] -> fidivr [ebx+0x0C] (live surface width)"),
    (0x006944C4,
     bytes.fromhex("d8 3d d4 55 74 00".replace(" ", "")),
     bytes.fromhex("da 7b 10 90 90 90".replace(" ", "")),
     "fdivr [256.0] -> fidivr [ebx+0x10] (live surface height)"),
)

# The loop body that must keep ebx pointing at the map object.
EBX_LIVE_RANGE = (0x006944A8, 0x006945E3)


def check_ebx_untouched(data: bytes) -> None:
    """Refuse to patch if anything in the loop writes to ebx."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    start, end = EBX_LIVE_RANGE
    offenders = []
    for insn in md.disasm(data[start - IMAGE_BASE:end - IMAGE_BASE], start):
        destination = insn.op_str.split(",")[0].strip()
        if destination == "ebx" and insn.mnemonic not in ("cmp", "test", "push"):
            offenders.append(f"0x{insn.address:08X}  {insn.mnemonic} {insn.op_str}")
    if offenders:
        raise SystemExit(
            "ebx is not stable across the fog loop; refusing to patch:\n  "
            + "\n  ".join(offenders))
    print(f"  ebx verified stable across 0x{start:08X}-0x{end:08X}")


def patch(data: bytearray) -> None:
    check_ebx_untouched(bytes(data))
    for va, expected, replacement, description in FOG_SITES:
        offset = va - IMAGE_BASE
        found = bytes(data[offset:offset + len(expected)])
        if found != expected:
            raise SystemExit(
                f"0x{va:08X}: expected {expected.hex(' ')}, found {found.hex(' ')}. "
                "Refusing to patch.")
        data[offset:offset + len(replacement)] = replacement
        print(f"  0x{va:08X}  {description}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.output.resolve() == args.source.resolve():
        raise SystemExit("refusing to patch in place")

    image = PEImage(args.source)
    data = bytearray(image.data)
    before = len(data)
    patch(data)
    assert len(data) == before, "in-place patch changed the file length"
    args.output.write_bytes(bytes(data))
    print(f"\nfile length {len(data)} (unchanged)")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
