#!/usr/bin/env python3
"""Put a listbox's gutter on the side its scrollbar is actually on.

Gold v11 made `PADDING` a horizontal inset and dropped the doubled subtraction,
so a row's rect became:

    0041B46D  mov [esp+0x20], edi   ; rect.left  = PADDING      (unconditional)
    0041B48C  sub ecx, edi          ; rect.width = content - PADDING

That is right for a list whose scrollbar is on the left. It is backwards for a
description pane, whose scrollbar is on the **right** (`LEFTSCROLLBAR = 0`): the
gutter lands on the left, away from the bar, and the text runs up to the bar
with only the 4px border between them. Measured on the shipped 3440x1440 build,
every description pane in the game -- inventory, journal, questitem, store --
had a 4px gap where 72 was intended.

The gutter should follow the scrollbar. `rect.width` is already correct in both
cases; only the left edge differs:

    rect.left = (LEFTSCROLLBAR ? PADDING : 0)

`0x0041B46D` has no slack for a test-and-branch -- the instructions around it
are packed -- so the run is replaced with a jump to a stub that does the same
two stores with the flag test in front, then jumps back. `jmp` preserves `esp`,
so the stub's `[esp+NN]` references stay valid.

`edi` must survive as `PADDING`: `0x0041B48C` still reads it for the width, and
`0x0041B4A1` for the row-top chain. The stub therefore never touches it, and
writes the zero straight to the stack slot instead.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".kgs\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read

BLOCK_VA = 0x0041B46D
RESUME_VA = 0x0041B479
BLOCK_LEN = RESUME_VA - BLOCK_VA        # 12 bytes

# gold v11's two stores: rect.left = edi (PADDING), rect.top = 0
ORIGINAL = bytes.fromhex("897c2420" "c744242400000000")

FLAGS_OFFSET = 0x2BC        # listbox flags; bit 0x10 is LEFTSCROLLBAR
LEFTSCROLLBAR_BIT = 0x10


def build_stub(stub_va: int) -> bytes:
    stub = bytearray()
    stub += b"\xF6\x86" + struct.pack("<I", FLAGS_OFFSET) + bytes([LEFTSCROLLBAR_BIT])
    #        test byte [esi+0x2BC], 0x10
    stub += b"\x75\x0A"                                  # jnz  left_gutter
    stub += b"\xC7\x44\x24\x20" + struct.pack("<i", 0)   # mov [esp+0x20], 0
    stub += b"\xEB\x04"                                  # jmp  set_top
    # left_gutter:
    stub += b"\x89\x7C\x24\x20"                          # mov [esp+0x20], edi
    # set_top:
    stub += b"\xC7\x44\x24\x24" + struct.pack("<i", 0)   # mov [esp+0x24], 0
    jmp_at = stub_va + len(stub)
    stub += b"\xE9" + struct.pack("<i", RESUME_VA - (jmp_at + 5))
    return bytes(stub)


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise SystemExit("Output must be a separate executable")

    image = PEImage(args.source)
    actual, offset, section = image.read_va(BLOCK_VA, BLOCK_LEN)
    if actual != ORIGINAL:
        raise SystemExit(
            f"0x{BLOCK_VA:08X}: expected\n  {ORIGINAL.hex(' ')}\nfound\n  {actual.hex(' ')}\n"
            f"(file 0x{offset:08X}, {section}). Refusing to patch.")
    if any(s.name == ".kgs" for s in image.sections):
        raise SystemExit("Source already contains a .kgs section")

    data = bytearray(image.data)

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    header_slot = optional + optional_size + section_count * 40
    file_alignment = struct.unpack_from("<I", data, optional + 36)[0]
    section_alignment = struct.unpack_from("<I", data, optional + 32)[0]

    if header_slot + 40 > image.size_of_headers:
        raise SystemExit("No room for another PE section header")

    last = max(image.sections, key=lambda s: s.virtual_address)
    new_rva = align(last.virtual_address + max(last.virtual_size, last.raw_size),
                    section_alignment)
    stub_va = image.image_base + new_rva
    stub = build_stub(stub_va)

    patch = b"\xE9" + struct.pack("<i", stub_va - (BLOCK_VA + 5))
    patch += b"\x90" * (BLOCK_LEN - len(patch))
    data[offset:offset + BLOCK_LEN] = patch

    raw_offset = align(len(data), file_alignment)
    raw_size = align(len(stub), file_alignment)
    struct.pack_into("<H", data, coff + 2, section_count + 1)
    size_of_code = struct.unpack_from("<I", data, optional + 4)[0]
    struct.pack_into("<I", data, optional + 4, size_of_code + raw_size)
    struct.pack_into("<I", data, optional + 56,
                     align(new_rva + len(stub), section_alignment))
    struct.pack_into("<I", data, optional + 64, 0)
    header = struct.pack("<8sIIIIIIHHI", SECTION_NAME, len(stub), new_rva,
                         raw_size, raw_offset, 0, 0, 0, 0, SECTION_CHARACTERISTICS)
    data[header_slot:header_slot + 40] = header
    if len(data) < raw_offset:
        data.extend(b"\0" * (raw_offset - len(data)))
    stub_file_offset = len(data)
    data.extend(stub)
    data.extend(b"\0" * (raw_size - len(stub)))

    args.output.write_bytes(data)

    out = PEImage(args.output)
    reread, _, _ = out.read_va(BLOCK_VA, BLOCK_LEN)
    if reread != patch:
        raise SystemExit("Verification failed: trampoline did not read back")
    reread, _, sec = out.read_va(stub_va, len(stub))
    if reread != stub or sec != ".kgs":
        raise SystemExit("Verification failed: stub contents/section")

    print(f"{'block replaced':<20} VA 0x{BLOCK_VA:08X}  file 0x{offset:08X}  {BLOCK_LEN} bytes")
    print(f"{'stub (.kgs)':<20} VA 0x{stub_va:08X}  file 0x{stub_file_offset:08X}  {len(stub)} bytes")
    print()
    print(f"{'new file length':<20} {len(data)}   <- GoldPatch.TargetLength")
    print(f"{'SHA-256':<20} {out.sha256}   <- GoldPatch.TargetHash / EXPECTED_GOLD_SHA256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
