#!/usr/bin/env python3
"""Fix the general PC-screen mouse click-offset bug.

Root cause (found via static analysis of the gold-vs-clean byte delta,
`generate_gold_delta.py`'s `changed_ranges()`): two widget-geometry helper
functions shared by essentially every non-main-menu/non-HUD GUI screen
(0x0040B690 and 0x0040BA20 in the vanilla executable) recenter a control's
rect using the formula

    newX = originalX - (liveScreenWidth - DESIGN_WIDTH) / 2
    newY = originalY - (liveScreenHeight - DESIGN_HEIGHT) / 2

where DESIGN_WIDTH/DESIGN_HEIGHT are hardcoded 32-bit immediates baked into
the executable at build time (vanilla: -640/-480; the hand-tuned gold
reference: -3440/-1440, i.e. its own target resolution). `ResolutionPatch`
never touched these 4 addresses, so every resolution we've ever shipped
inherited gold's frozen -3440/-1440 reference. At the exact resolution the
constant matches, `liveWidth - DESIGN_WIDTH == 0` and the recentering is a
no-op (correct). At any other resolution the recentering fires with the
wrong magnitude, shifting every non-main-menu/HUD control's *visual*
position without moving its *clickable* hit-test region (which is computed
elsewhere, unaffected) -- exactly the "click region works only at
3440x1440, and drifts in proportion to distance from it" bug reported
across four independently-patched test installs (1920x1080, 5120x1440,
5120x2160, 3440x1440).

Fix: two identical (width, height) immediate pairs at:
  0x0040B6C6 / 0x0040B6D9   (function 0x0040B690, callers 0x00686B92 /
                              0x00692942)
  0x0040BA6B / 0x0040BA82   (function 0x0040BA20, 6 confirmed direct
                              callers across the PC-screen GUI dispatch:
                              0x004191E3, 0x00419276, 0x0041A520,
                              0x0041A5F6, 0x0041B69F, 0x0041C4D7)
Each is a `05 xx xx xx xx` (ADD EAX, imm32) instruction; only the 4-byte
immediate is replaced, matching the target resolution's negated
width/height, the same way `ResolutionPatch`'s existing 8 fields already
bake in the target resolution as a constant.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


WIDTH_FIELD_VAS = (0x0040B6C6, 0x0040BA6B)
HEIGHT_FIELD_VAS = (0x0040B6D9, 0x0040BA82)

GOLD_WIDTH = 3440
GOLD_HEIGHT = 1440


def patch_field(image: PEImage, data: bytearray, va: int, expected_value: int, new_value: int, label: str) -> None:
    offset, section = image.va_to_file_offset(va)
    actual = struct.unpack_from("<i", data, offset + 1)[0]
    opcode = data[offset]
    if opcode != 0x05:
        raise ValueError(f"{label} @0x{va:08X}: expected opcode 05 (ADD EAX,imm32), found {opcode:02X}")
    if actual != expected_value:
        raise ValueError(
            f"{label} @0x{va:08X}: expected immediate {expected_value}, found {actual} "
            f"(file 0x{offset:08X}, {section}) -- source exe does not match the known baseline"
        )
    struct.pack_into("<i", data, offset + 1, new_value)
    print(f"{label:<45} VA 0x{va:08X}  file 0x{offset:08X}  {expected_value} -> {new_value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="Source executable (already patched for the target resolution)")
    parser.add_argument("output", type=Path, help="Output executable path")
    parser.add_argument("--width", type=int, required=True, help="Target resolution width this exe was patched for")
    parser.add_argument("--height", type=int, required=True, help="Target resolution height this exe was patched for")
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")

    image = PEImage(args.source)
    data = bytearray(image.data)

    for va in WIDTH_FIELD_VAS:
        patch_field(image, data, va, -GOLD_WIDTH, -args.width, "click-fix width reference")
    for va in HEIGHT_FIELD_VAS:
        patch_field(image, data, va, -GOLD_HEIGHT, -args.height, "click-fix height reference")

    args.output.write_bytes(data)
    output = PEImage(args.output)
    for va, expected in list(zip(WIDTH_FIELD_VAS, (-args.width,) * 2)) + list(
        zip(HEIGHT_FIELD_VAS, (-args.height,) * 2)
    ):
        reread, offset, _ = output.read_va(va, 5)
        val = struct.unpack("<i", reread[1:5])[0]
        if val != expected:
            raise ValueError(f"Verification failed at 0x{va:08X}: expected {expected}, found {val}")

    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
