#!/usr/bin/env python3
"""Give the item stack-count label 32-bit geometry so it can scale without limit.

The label is built inside the inventory row's `SetRect` (`0x006B5270`) and
appears in no `.gui` file. It is bottom-right-aligned *inside the icon box*:

    006B5326  cmp eax, 2             ; strlen of the count text
    006B532E  mov [esp+2C], 0x13     ; height 19          (already imm32)
    006B5337  and ecx, 0x15          ; width 21  (<= 2 digits)
    006B533A  add ecx, 0x15          ;    or 42  (3+ digits)
    006B5343  sub edx, eax           ; left += iconSize - width
    006B534F  add eax, 0x25          ; top  += 37
    006B5352  mov [esp+20], ecx

`37 + 19 = 56`, the vanilla icon size, so the label sits in the icon's
bottom-right corner. Once the icon is scaled these must scale with it.

**Why this needs a trampoline.** Three of the four are **imm8** operands
(`83 /r ib`), sign-extended, so anything above 127 encodes as negative. Clamping
keeps them legal but at 7680x4320 the icon is 336px while the top offset stops
at 127 -- the label floats partway up the icon instead of sitting in its corner.
The imm32 forms (`81 /r id`, `05 id`) are three bytes longer each and there is
no slack to grow into, so the arithmetic has to move somewhere it can be
encoded properly.

This replaces the whole 32-byte run at `0x006B5336`-`0x006B5355` with a jump to
a stub that performs **exactly the same instructions** with imm32 operands, then
jumps back. `jmp` preserves `esp`, so the stub's `[esp+NN]` references stay
valid. The three constants sit at fixed offsets in the stub so the per-resolution
patcher can write them as full 32-bit values (`StackCountSites` in
`KotorUniversalPatcher.cs`), with no clamp.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".ksc\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read

BLOCK_VA = 0x006B5336
RESUME_VA = 0x006B5356
BLOCK_LEN = RESUME_VA - BLOCK_VA          # 32 bytes

ORIGINAL = bytes.fromhex(
    "49"            # dec ecx
    "83E115"        # and ecx, 0x15
    "83C115"        # add ecx, 0x15
    "8BC1"          # mov eax, ecx
    "8B4C2420"      # mov ecx, [esp+0x20]
    "2BD0"          # sub edx, eax
    "894424 28".replace(" ", "")
    + "8B442424"    # mov eax, [esp+0x24]
    "03CA"          # add ecx, edx
    "83C025"        # add eax, 0x25
    "894C2420"      # mov [esp+0x20], ecx
)

VANILLA_WIDTH = 21
VANILLA_TOP = 37

# Byte offsets of the three imm32 operands within the stub, filled in below.
OFF_WIDTH_AND = 2       # after `dec ecx` (1) + `81 E1` (2)
OFF_WIDTH_ADD = 2 + 4 + 2
OFF_TOP = None          # computed


def build_stub(stub_va: int) -> tuple[bytes, dict[str, int]]:
    """Same instruction sequence, imm32 operands. Returns (bytes, operand offsets)."""
    stub = bytearray()
    offsets: dict[str, int] = {}

    stub += b"\x49"                                     # dec ecx
    stub += b"\x81\xE1"; offsets["width_and"] = len(stub)
    stub += struct.pack("<i", VANILLA_WIDTH)            # and ecx, imm32
    stub += b"\x81\xC1"; offsets["width_add"] = len(stub)
    stub += struct.pack("<i", VANILLA_WIDTH)            # add ecx, imm32
    stub += b"\x8B\xC1"                                 # mov eax, ecx
    stub += b"\x8B\x4C\x24\x20"                         # mov ecx, [esp+0x20]
    stub += b"\x2B\xD0"                                 # sub edx, eax
    stub += b"\x89\x44\x24\x28"                         # mov [esp+0x28], eax
    stub += b"\x8B\x44\x24\x24"                         # mov eax, [esp+0x24]
    stub += b"\x03\xCA"                                 # add ecx, edx
    stub += b"\x05"; offsets["top"] = len(stub)
    stub += struct.pack("<i", VANILLA_TOP)              # add eax, imm32
    stub += b"\x89\x4C\x24\x20"                         # mov [esp+0x20], ecx
    jmp_at = stub_va + len(stub)
    stub += b"\xE9" + struct.pack("<i", RESUME_VA - (jmp_at + 5))
    return bytes(stub), offsets


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
    if any(s.name == ".ksc" for s in image.sections):
        raise SystemExit("Source already contains a .ksc section")

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
    stub, operand_offsets = build_stub(stub_va)

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
    if reread != stub or sec != ".ksc":
        raise SystemExit("Verification failed: stub contents/section")

    print(f"{'block replaced':<22} VA 0x{BLOCK_VA:08X}  file 0x{offset:08X}  {BLOCK_LEN} bytes")
    print(f"{'stub (.ksc)':<22} VA 0x{stub_va:08X}  file 0x{stub_file_offset:08X}  {len(stub)} bytes")
    print()
    print("StackCountSites file offsets for KotorUniversalPatcher.cs (all imm32):")
    print(f"    new[] {{ 0x{0x002B5332:08X}, 4, 19 }},   // label height (unchanged, already imm32)")
    for name, vanilla in (("width_and", VANILLA_WIDTH), ("width_add", VANILLA_WIDTH),
                          ("top", VANILLA_TOP)):
        print(f"    new[] {{ 0x{stub_file_offset + operand_offsets[name]:08X}, 4, {vanilla} }},"
              f"   // {name}")
    print()
    print(f"SHA-256: {out.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
