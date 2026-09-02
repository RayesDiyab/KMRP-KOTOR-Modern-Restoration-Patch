#!/usr/bin/env python3
"""Raise the message popup's height cap and icon size.

**What this fixes.** `confirm.gui` backs the engine's shared message popup, and
the tutorial popups derive from it (see `reverse-engineering/text-padding.md`).
Scaling that `.gui` makes the box wider but **not taller**, because the popup
does not use its authored height: it re-lays itself out every time it is shown,
growing to fit the text and clamping against constants compiled into the layout
function at `0x006253A0`.

    006256DA  cmp ecx, 0x1B8      ; width  cap 440
    006256E2  cmp eax, 0x118      ; height cap 280   <- what pins the height
    006256ED  cmp eax, 0xA0       ; only grow past 160
    006256F4  cmp ecx, 0x1B8      ; width cap again
    006256FC  add [esp+0x38], 40  ; grow height a step
    00625705  add ecx, 40         ; grow width a step
    00625758  cmp eax, 0x118      ; height cap, SECOND site

The height cap has **two** sites. Patching only the first leaves the second
clamping, which is the "there is always a second copy" pattern this codebase has
hit repeatedly -- three row-pitch sites in gold v11, two rect builders in v12.

**The icon** is not in `confirm.gui` at all: the base constructor creates it and
gives it a 32x32 rect,

    00626F94  mov eax, 0x20       ; icon width and height
    00626FB5  mov [esp+0x1c], 10  ; icon top; left is 0

and the layout function insets the message text by the same 32 when an icon is
present,

    0062540C  mov edx, 0x20

so both must move together or the text runs under the icon.

All five patches are in-place `imm32` rewrites -- no size change, no new
section. See `reverse-engineering/exe-patching.md` for why that matters.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


HEIGHT_CAP_SITES = (0x006256E2, 0x00625758)      # cmp eax, imm32   (3D xx xx xx xx)
HEIGHT_CAP_ORIGINAL = 0x118                      # 280

ICON_RECT_SITE = 0x00626F94                      # mov eax, imm32   (B8 ...)
ICON_INSET_SITE = 0x0062540C                     # mov edx, imm32   (BA ...)
ICON_ORIGINAL = 0x20                             # 32


def patch_imm32(data: bytearray, image: PEImage, va: int, opcode: bytes,
                expect: int, value: int, label: str) -> None:
    actual, offset, section = image.read_va(va, len(opcode) + 4)
    if actual[:len(opcode)] != opcode or struct.unpack("<I", actual[len(opcode):])[0] != expect:
        raise SystemExit(
            f"0x{va:08X}: expected {opcode.hex(' ')} {expect:#x}, found {actual.hex(' ')} "
            f"in {section}. Refusing to patch.")
    struct.pack_into("<I", data, offset + len(opcode), value)
    print(f"  0x{va:08X}  {label:24s} {expect} -> {value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--height-cap", type=int, default=420,
                        help="max popup height in authored units (vanilla 280)")
    parser.add_argument("--icon-size", type=int, default=48,
                        help="icon edge in authored units (vanilla 32)")
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise SystemExit("Output must be a separate executable")
    if not 280 <= args.height_cap <= 1200:
        raise SystemExit("--height-cap must be 280..1200")
    if not 32 <= args.icon_size <= 256:
        raise SystemExit("--icon-size must be 32..256")

    image = PEImage(args.source)
    data = bytearray(image.data)
    before = len(data)

    for va in HEIGHT_CAP_SITES:
        patch_imm32(data, image, va, b"\x3D", HEIGHT_CAP_ORIGINAL, args.height_cap,
                    "height cap")
    patch_imm32(data, image, ICON_RECT_SITE, b"\xB8", ICON_ORIGINAL, args.icon_size,
                "icon rect (w and h)")
    patch_imm32(data, image, ICON_INSET_SITE, b"\xBA", ICON_ORIGINAL, args.icon_size,
                "icon inset for text")

    if len(data) != before:
        raise SystemExit(f"Patch changed the file length ({before} -> {len(data)})")
    args.output.write_bytes(data)

    out = PEImage(args.output)
    for va, opcode, value in (
            [(v, b"\x3D", args.height_cap) for v in HEIGHT_CAP_SITES]
            + [(ICON_RECT_SITE, b"\xB8", args.icon_size),
               (ICON_INSET_SITE, b"\xBA", args.icon_size)]):
        check, _, _ = out.read_va(va, len(opcode) + 4)
        if check[:len(opcode)] != opcode or struct.unpack("<I", check[len(opcode):])[0] != value:
            raise SystemExit(f"Verification failed at 0x{va:08X}")
    # Every pre-existing stub section must still read back, per exe-patching.md.
    for section in out.sections:
        if section.name.startswith(".k"):
            probe, _, name = out.read_va(out.image_base + section.virtual_address, 8)
            if name != section.name or len(probe) != 8:
                raise SystemExit(f"Section {section.name} no longer reads correctly")

    print()
    print(f"{'sections intact':<20} {[s.name for s in out.sections if s.name.startswith('.k')]}")
    print(f"{'file length':<20} {len(data)} (unchanged)")
    print(f"{'SHA-256':<20} {out.sha256}")
    print()
    print("confirm.gui is read once when the popup class is constructed, so the")
    print("game must be restarted for this to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
