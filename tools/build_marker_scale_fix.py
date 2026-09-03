#!/usr/bin/env python3
"""Scale the area map's marker icons with the map they sit on.

**The problem.** KMRP enlarges the marker overlay from vanilla's 440x256 to
`canvasWidth x 440/512` by `canvasHeight` -- 1478x720 at 3440x1440. The marker
rectangles are built from immediates in the icon loop and were never scaled with
it, so relative to the map they shrink by exactly the same factor the overlay
grew:

    vanilla      20 px on a  440-wide overlay = 4.5%  of map width
    3440x1440    20 px on a 1478-wide overlay = 1.4%  (3.4x smaller)
    15360x8640   20 px on a 6600-wide overlay = 0.3%  (a speck)

Only one of the four sizes was ever touched: `0x0069405A`, 32 -> 40, a 1.25x bump
against a 3.36x overlay.

**The sites.** Three markers, each a size plus the two centring offsets that
place the rectangle's top-left. The relationship is always `offset = -size / 2`,
so they must move together or the icon drifts off the point it marks.

    map note     0x0069471F  mov eax, 0x14   size 20
                 0x00694718  add eax, -0x0A  centre X
                 0x00694724  add ecx, -0x0A  centre Y
    party        0x00694A12  mov edi, 0x10   size 16
                 0x00694A51  add eax, -0x08  centre X
                 0x00694A54  add edx, -0x08  centre Y
    player arrow 0x00694AC3  mov edx, 0x20   size 32
                 0x00694ACE  add ecx, -0x10  centre Y
                 0x00694AD2  add eax, -0x10  centre X
    arrow extent 0x0069405A  mov eax, 0x20   the arrow control's own width and
                                             height, no paired offset

**The factor.** `overlayWidth / 440`, which reduces exactly to
`canvasWidth / 512` and so to `screenWidth / 1024`. Using the overlay's own
derivation keeps markers at vanilla's proportion of the map at every resolution.

**The imm8 ceiling.** The sizes are `imm32` and take any value, but every
centring offset is an `add r32, imm8` -- three bytes, range -128..127. The
largest offset is the arrow's `size / 2`, so the factor is clamped at
`127 / 16 = 7.9375`. That binds only above ~8130 px wide: of the 48 shipped
resolutions, 8192x4608 and 15360x8640 get slightly under-scaled markers, still
correctly centred. Growing those adds into `imm32` would need a stub, the same
way the stack-count label did in gold v10.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


# (VA, opcode bytes, vanilla value, encoding) for every marker geometry site.
# "imm32" is a mov with a 4-byte operand; "imm8" is `add r32, imm8`.
SIZE_SITES = (
    (0x0069471F, bytes.fromhex("b8"), 20, "map note size"),
    (0x00694A12, bytes.fromhex("bf"), 16, "party marker size"),
    (0x00694AC3, bytes.fromhex("ba"), 32, "player arrow size"),
    (0x0069405A, bytes.fromhex("b8"), 32, "player arrow control extent"),
)
OFFSET_SITES = (
    (0x00694718, bytes.fromhex("83c0"), -10, "map note centre X"),
    (0x00694724, bytes.fromhex("83c1"), -10, "map note centre Y"),
    (0x00694A51, bytes.fromhex("83c0"), -8, "party marker centre X"),
    (0x00694A54, bytes.fromhex("83c2"), -8, "party marker centre Y"),
    (0x00694ACE, bytes.fromhex("83c1"), -16, "player arrow centre Y"),
    (0x00694AD2, bytes.fromhex("83c0"), -16, "player arrow centre X"),
)

# The arrow control extent at 0x0069405A is 40 in gold v15, not the vanilla 32:
# an earlier partial attempt at this same problem. It is superseded here.
GOLD_V15_ARROW_EXTENT = 40

MAX_OFFSET = 127            # add r32, imm8
MAX_FACTOR = MAX_OFFSET / 16.0


def factor_for(width: int) -> float:
    """Marker scale for a screen width: overlayWidth / 440, clamped."""
    canvas = width // 2
    overlay = round(canvas * 440 / 512)
    return min(overlay / 440.0, MAX_FACTOR)


def patch(data: bytearray, image: PEImage, factor: float, verbose: bool = True) -> None:
    for va, opcode, expected, label in SIZE_SITES:
        actual, offset, section = image.read_va(va, len(opcode) + 4)
        found = struct.unpack("<I", actual[len(opcode):])[0]
        allowed = {expected}
        if va == 0x0069405A:
            allowed.add(GOLD_V15_ARROW_EXTENT)
        if actual[:len(opcode)] != opcode or found not in allowed:
            raise SystemExit(
                f"0x{va:08X}: expected {opcode.hex(' ')} with one of "
                f"{sorted(allowed)}, found {actual.hex(' ')} in {section}")
        value = max(1, round(expected * factor))
        struct.pack_into("<I", data, offset + len(opcode), value)
        if verbose:
            print(f"  0x{va:08X}  {label:28} {found:>4} -> {value}")

    for va, opcode, expected, label in OFFSET_SITES:
        actual, offset, section = image.read_va(va, len(opcode) + 1)
        found = struct.unpack("<b", actual[len(opcode):])[0]
        if actual[:len(opcode)] != opcode or found != expected:
            raise SystemExit(
                f"0x{va:08X}: expected {opcode.hex(' ')} {expected}, "
                f"found {actual.hex(' ')} in {section}")
        value = -max(1, round(-expected * factor))
        if not -128 <= value <= 127:
            raise SystemExit(f"0x{va:08X}: {value} does not fit in imm8")
        struct.pack_into("<b", data, offset + len(opcode), value)
        if verbose:
            print(f"  0x{va:08X}  {label:28} {found:>4} -> {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=3440,
                        help="screen width the baked values are for (default 3440)")
    args = parser.parse_args()

    if args.output.resolve() == args.source.resolve():
        raise SystemExit("refusing to patch in place")

    image = PEImage(args.source)
    data = bytearray(image.data)
    before = len(data)
    factor = factor_for(args.width)
    print(f"marker scale for {args.width}px wide: {factor:.4f}"
          f"{'  (clamped by the imm8 ceiling)' if factor >= MAX_FACTOR else ''}\n")
    patch(data, image, factor)

    assert len(data) == before, "in-place patch changed the file length"
    args.output.write_bytes(bytes(data))
    print(f"\nfile length {len(data)} (unchanged)")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
