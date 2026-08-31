#!/usr/bin/env python3
"""Put a listbox's gutter on the side its scrollbar is actually on.

Gold v11 made `PADDING` a horizontal inset and dropped the doubled subtraction,
so a row's rect became `left = PADDING`, `width = content - PADDING`. That is
right for a list whose scrollbar is on the left. It is backwards for a
description pane, whose bar is on the **right** (`LEFTSCROLLBAR = 0`): the
gutter lands away from the bar and the text runs up to it with only the 4px
border between. The gutter should follow the scrollbar:

    rect.left = (LEFTSCROLLBAR ? PADDING : 0)

`width = content - PADDING` is already correct in both cases.

**There are two rect builders, not one.** `0x0041B140` handles the case where
the content fits. When it does not, `0x0041B3CB` hands off to a second routine
at `0x0041A2D0` which lays the single item out on its own, carrying its own copy
of the same arithmetic at `[esp+0x1C..0x28]`:

    0041A2EB  movzx edi, byte [esi+0x2C0]   ; PADDING
    0041A2F2  lea   eax, [edi+edi]
    0041A2F5  sub   ecx, eax                ; width = content - 2*PADDING
    0041A2F7  test  ebx, ebx                ; flags consumed by the je at 0x0041A30D
    0041A2F9  mov   [esp+0x1C], edi         ; left  = PADDING
    0041A2FD  mov   [esp+0x24], ecx

Its guard at `0x0041B3B0` compares `PADDING + rowHeight` against the box height,
so this is exactly the "content too tall to fit" case -- which is why patching
only the first builder left the gutter wrong on precisely those descriptions
long enough to need a scrollbar, and right on every shorter one. That symptom
tracking a condition is what located the second builder.

Neither site has slack for a test-and-branch, so both are replaced with jumps
into stubs in a `.kgs` section. `jmp` preserves `esp`, so `[esp+NN]` references
stay valid.

Two constraints the stubs respect:

  * `edi` must survive holding `PADDING` -- `0x0041B48C` still reads it for the
    width and `0x0041B4A1` for the row-top chain -- so the zero is written
    straight to the stack slot rather than by clearing the register.
  * `test ebx, ebx` is re-issued **last** in the second stub. The `je` at
    `0x0041A30D` consumes its flags, and only `mov`s sit in between.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".kgs\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read

FLAGS_OFFSET = 0x2BC        # listbox flags; bit 0x10 is LEFTSCROLLBAR
LEFTSCROLLBAR_BIT = 0x10

# Builder A: the content-fits path. Replaces gold v11's two stores.
FIT_VA = 0x0041B46D
FIT_RESUME = 0x0041B479
FIT_ORIGINAL = bytes.fromhex("897c2420" "c744242400000000")

# Builder B: reached when the content is taller than the box, i.e. whenever the
# pane needs a scrollbar. Untouched by v11, still vanilla.
SCROLL_VA = 0x0041A2F2
SCROLL_RESUME = 0x0041A301
SCROLL_ORIGINAL = bytes.fromhex("8d043f" "2bc8" "85db" "897c241c" "894c2424")


def _gutter(slot: int) -> bytes:
    """left = LEFTSCROLLBAR ? edi : 0, written to [esp+slot]."""
    out = bytearray()
    out += b"\xF6\x86" + struct.pack("<I", FLAGS_OFFSET) + bytes([LEFTSCROLLBAR_BIT])
    out += b"\x75\x0A"                                      # jnz left_gutter
    out += b"\xC7\x44\x24" + bytes([slot]) + struct.pack("<i", 0)
    out += b"\xEB\x04"                                      # jmp past
    out += b"\x89\x7C\x24" + bytes([slot])                  # mov [esp+slot], edi
    return bytes(out)


def build_stubs(stub_va: int) -> tuple[bytes, int]:
    """Both stubs back to back. Returns (bytes, byte offset of the second)."""
    stub = bytearray()

    stub += _gutter(0x20)
    stub += b"\xC7\x44\x24\x24" + struct.pack("<i", 0)       # mov [esp+0x24], 0 (rect.top)
    at = stub_va + len(stub)
    stub += b"\xE9" + struct.pack("<i", FIT_RESUME - (at + 5))

    second = len(stub)
    stub += b"\x2B\xCF"                                      # sub ecx, edi
    stub += _gutter(0x1C)
    stub += b"\x89\x4C\x24\x24"                              # mov [esp+0x24], ecx
    # Builder B derives rect.top from edi as well: `sub ebx, edi` at 0x0041A35D
    # on the bottom-anchored branch, and `sub edi, eax` at 0x0041A381 otherwise,
    # which leaves top = PADDING when unscrolled. Builder A writes top = 0, so a
    # pane long enough to scroll gained a PADDING-tall gap above its first line
    # while a short one did not. Clearing edi here fixes both branches at once --
    # those two subtractions are its only remaining readers. It must come before
    # the `test`, which sets the flags 0x0041A30D consumes.
    stub += b"\x33\xFF"                                      # xor edi, edi
    stub += b"\x85\xDB"                                      # test ebx, ebx  (flags for 0x41A30D)
    at = stub_va + len(stub)
    stub += b"\xE9" + struct.pack("<i", SCROLL_RESUME - (at + 5))
    return bytes(stub), second


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
    sites = ((FIT_VA, FIT_ORIGINAL, FIT_RESUME), (SCROLL_VA, SCROLL_ORIGINAL, SCROLL_RESUME))
    for va, original, _ in sites:
        actual, offset, section = image.read_va(va, len(original))
        if actual != original:
            raise SystemExit(
                f"0x{va:08X}: expected\n  {original.hex(' ')}\nfound\n  {actual.hex(' ')}\n"
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
    stub, second = build_stubs(stub_va)

    for (va, original, _), target in zip(sites, (stub_va, stub_va + second)):
        _, offset, _ = image.read_va(va, len(original))
        patch = b"\xE9" + struct.pack("<i", target - (va + 5))
        patch += b"\x90" * (len(original) - len(patch))
        data[offset:offset + len(original)] = patch
        print(f"0x{va:08X}  file 0x{offset:08X}  {len(original)} bytes -> jmp 0x{target:08X}")

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
    reread, _, sec = out.read_va(stub_va, len(stub))
    if reread != stub or sec != ".kgs":
        raise SystemExit("Verification failed: stub contents/section")

    print(f"{'stub (.kgs)':<20} VA 0x{stub_va:08X}  file 0x{stub_file_offset:08X}  {len(stub)} bytes")
    print()
    print(f"{'new file length':<20} {len(data)}   <- GoldPatch.TargetLength")
    print(f"{'SHA-256':<20} {out.sha256}   <- GoldPatch.TargetHash / EXPECTED_GOLD_SHA256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
