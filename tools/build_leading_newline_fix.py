#!/usr/bin/env python3
"""Strip leading newlines from GUI text, so descriptions don't open with a blank line.

Item and quest descriptions are composed by prefixing `\\n` to each property
line, so any description that opens with a property block starts with a newline
and renders an empty first line. Read live at 3440x1440, Brejik's Arm Band:

    0A 44 61 6D 61 67 65 ...   "\\nDamage Resistance: Resist 5/- vs. Slashing\\n\\n..."

Everything around it measured correct -- the listbox hands the item a rect of
`{0, 0, width - PADDING, height}` and the proto's alignment is `9` = left+top.
The blank line is in the string, not the layout, which is why it appeared on
some items and not others: an item composed without a leading property block has
no leading newline. Vanilla behaviour; at 800x600 that line is ~16px and passes
unnoticed, at 3440x1440 with the enlarged font it is ~40px.

**Where this hooks.** Traced from a hardware write breakpoint on the text
control's string pointer:

    0055F340  the description builder (properties + prose)
    006B3D80  call 0x415E00        ; hand the built string to the control
    00415E08  call 0x5E5C50        ; CExoString assign -- the write we caught
    00415E0D  mov eax, [esi+0x50]  ; <- patched; esi is the CExoString

`0x00415E00` is the GUI text setter, so trimming here covers **every** GUI text
control in one place, and it happens at set time -- which matters, because the
line-breaker (`0x0045A5C9`) and the renderer (`0x0045A806`) are separate passes
over the same string. Trimming in only one would make them disagree about where
lines start.

`[esi+0]` is the character pointer and `[esi+4]` is the buffer **capacity**, not
a length -- confirmed at `0x005E5C78`, where the assign compares the incoming
length against it to decide whether to reuse the buffer. The string is
NUL-terminated, so the trim is a plain in-place shift with nothing else to
update.

The five bytes at `0x00415E0D` (`mov eax,[esi+0x50]` + `test eax,eax`) are
exactly a `jmp rel32`, so no padding is needed; the stub re-issues both and
returns to `0x00415E12`, whose `je` consumes the `test`'s flags.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".ktn\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read

HOOK_VA = 0x00415E0D
RESUME_VA = 0x00415E12
HOOK_LEN = RESUME_VA - HOOK_VA                  # 5 bytes
ORIGINAL = bytes.fromhex("8b4650" "85c0")       # mov eax,[esi+0x50] ; test eax,eax


def build_stub(stub_va: int) -> bytes:
    stub = bytearray()
    stub += b"\x60"                     # pushad
    stub += b"\x8B\xDE"                 # mov ebx, esi        (ebx = CExoString*)
    check = len(stub)
    stub += b"\x8B\x03"                 # mov eax, [ebx]      (char*)
    stub += b"\x85\xC0"                 # test eax, eax
    je_at = len(stub); stub += b"\x74\x00"
    stub += b"\x80\x38\x0A"             # cmp byte [eax], '\n'
    jne_at = len(stub); stub += b"\x75\x00"
    stub += b"\x8B\xF8"                 # mov edi, eax        (dst)
    stub += b"\x8D\x70\x01"             # lea esi, [eax+1]    (src)
    copy = len(stub)
    stub += b"\x8A\x0E"                 # mov cl, [esi]
    stub += b"\x88\x0F"                 # mov [edi], cl
    stub += b"\x46"                     # inc esi
    stub += b"\x47"                     # inc edi
    stub += b"\x84\xC9"                 # test cl, cl
    stub += b"\x75" + bytes([(copy - (len(stub) + 2)) & 0xFF])   # jne copy
    stub += b"\xEB" + bytes([(check - (len(stub) + 2)) & 0xFF])  # jmp check
    done = len(stub)
    stub[je_at + 1] = done - (je_at + 2)
    stub[jne_at + 1] = done - (jne_at + 2)
    stub += b"\x61"                     # popad
    stub += ORIGINAL                    # mov eax,[esi+0x50] ; test eax,eax
    at = stub_va + len(stub)
    stub += b"\xE9" + struct.pack("<i", RESUME_VA - (at + 5))
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
    actual, offset, section = image.read_va(HOOK_VA, HOOK_LEN)
    if actual != ORIGINAL:
        raise SystemExit(
            f"0x{HOOK_VA:08X}: expected {ORIGINAL.hex(' ')}, found {actual.hex(' ')} "
            f"(file 0x{offset:08X}, {section}). Refusing to patch.")
    if any(s.name == ".ktn" for s in image.sections):
        raise SystemExit("Source already contains a .ktn section")

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

    patch = b"\xE9" + struct.pack("<i", stub_va - (HOOK_VA + 5))
    if len(patch) != HOOK_LEN:
        raise SystemExit("Hook length mismatch")
    data[offset:offset + HOOK_LEN] = patch

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
    reread, _, _ = out.read_va(HOOK_VA, HOOK_LEN)
    if reread != patch:
        raise SystemExit("Verification failed: hook did not read back")
    reread, _, sec = out.read_va(stub_va, len(stub))
    if reread != stub or sec != ".ktn":
        raise SystemExit("Verification failed: stub contents/section")

    print(f"{'hook':<18} VA 0x{HOOK_VA:08X}  file 0x{offset:08X}  {HOOK_LEN} bytes -> jmp 0x{stub_va:08X}")
    print(f"{'stub (.ktn)':<18} VA 0x{stub_va:08X}  file 0x{stub_file_offset:08X}  {len(stub)} bytes")
    print()
    print(f"{'new file length':<18} {len(data)}   <- GoldPatch.TargetLength")
    print(f"{'SHA-256':<18} {out.sha256}   <- GoldPatch.TargetHash / EXPECTED_GOLD_SHA256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
