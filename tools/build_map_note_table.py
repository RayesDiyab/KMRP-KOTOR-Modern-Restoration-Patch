#!/usr/bin/env python3
"""Correct 250 misplaced map-note positions, from Derslok's hand-measured table.

**The bug.** BioWare shipped 250 map notes whose stored world position does not
match where the thing actually is, so the marker on the area map sits off its
subject. It is a 2003 content bug, not a resolution bug, and it is present in
every unmodded install. Derslok measured the corrections by hand for *K1 Area
Map Fixes*; the table is his work, GPL-3.0, used here with his permission and
credited in `THIRD_PARTY_NOTICES.md`.

**What is taken, and what is not.** Only `note_table.bin` -- 250 entries of four
little-endian floats: the note's shipped world X and Y as the lookup key, then
the corrected X and Y. None of his code is used. His own scaling work is not
used either: KMRP already scales the map its own way, and his `hires_patch.py`
would fight it.

**Why this needs no new hook.** His patcher hooks `0x006946EF` and assembles a
match routine into a code cave. KMRP already redirects the very next
instruction, the `call 0x00578E00` at `0x006946F4`, into its own wrapper at
`0x0086D000` (see `map-markers.md` section 5). The world position is built as a
three-float vector on the stack immediately before that call --

    006946DF  sub  esp, 0xC          ; room for the vector
    006946E4  mov  [edx], ecx        ; X, from [esi]
    006946E9  mov  [edx+4], ecx      ; Y, from [esi+4]
    006946EF  mov  [edx+8], ecx      ; Z          <- where his patcher hooks
    006946F4  call 0x00578E00        <- where KMRP already hooks

-- so by the time our wrapper runs, the vector is its own first two arguments,
`[ebp+8]` and `[ebp+0x0C]`. `ret 0x14` on the wrapper confirms the five dwords.
We substitute there. **No vanilla byte outside the wrapper changes, his code
cave at `0x0073C1D0` is never written, and there is no second hook.**

His reserved region at VA `0x0086D000` *is* a genuine collision -- that is
exactly where KMRP's `.kui` lives -- which is why the table goes in a section of
our own instead.

**Registers.** The call site does `mov ecx, eax` at `0x006946F2`, so `ecx` is the
`this` pointer the vanilla routine still needs. The lookup preserves `ecx`, and
`ebx`, `esi` and `edi` besides; only `eax` and `edx` are clobbered, and the
wrapper reloads both.

**Matching** is bitwise on the two key floats. The value being compared was
loaded from the same module field the table was measured from, so equality is
exact and an epsilon would only risk matching a neighbour. A note that is not in
the table is left exactly as it was, so this is inert for everything it does not
correct.

The whole thing is gated on a flag at the start of the section, which
`ResolutionPatch` writes per install from the user's Advanced Settings choice.

Address convention: `FILE = VA - 0x400000` for original sections; the appended
sections use `FILE = VA - 0x492000`.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import capstone

from verify_map_patch import PEImage


SECTION_NAME = b".kmn\0\0\0\0"
# Readable and executable: it holds both the table and the lookup routine.
SECTION_CHARACTERISTICS = 0x60000020

WRAPPER_VA = 0x0086D000
# The wrapper as gold v20 ships it, and the slot it lives in.
WRAPPER_ORIGINAL = bytes.fromhex(
    "5589e556ff7518ff7514ff7510ff750cff7508ba008e5700ffd285c07432508b"
    "75148b060faf430c05dc00000099b9b8010000f7f989068b75188b060faf4310"
    "058000000099b900010000f7f98906585e5dc21400")
WRAPPER_SLOT = 0x80

TABLE_ENTRIES = 250
TABLE_SHA256 = "880a325d982d74df496b02782faefdd3ae3802efbba030b9fbccc967cc0ccaa5"

# Section layout.
FLAG_OFFSET = 0x00       # dword: non-zero to apply the corrections
COUNT_OFFSET = 0x04      # dword: entries, so the routine and the docs cannot drift
MAGIC_OFFSET = 0x08      # 8 bytes
MAGIC = b"KMRPNOTE"
TABLE_OFFSET = 0x10


def build_lookup(section_va: int) -> bytes:
    """The match routine. stdcall, one argument: the address of the vector."""
    flag_va = section_va + FLAG_OFFSET
    table_va = section_va + TABLE_OFFSET

    prologue = bytes.fromhex("5589e5535657518b7508")          # save, esi = &vector
    gate = b"\x83\x3d" + struct.pack("<I", flag_va) + b"\x00"  # cmp [flag], 0
    # je done -- near form, so the offset does not depend on guessing a byte range
    body = (b"\xbf" + struct.pack("<I", table_va)             # mov edi, table
            + b"\xb9" + struct.pack("<I", TABLE_ENTRIES)      # mov ecx, 250
            + bytes.fromhex("8b06")                           # mov eax, [esi]      key X
            + bytes.fromhex("8b5e04"))                        # mov ebx, [esi+4]    key Y
    scan = bytes.fromhex(
        "3b07"        # cmp eax, [edi]
        "7512"        # jne advance
        "3b5f04"      # cmp ebx, [edi+4]
        "750d"        # jne advance
        "8b5708"      # mov edx, [edi+8]
        "8916"        # mov [esi], edx
        "8b570c"      # mov edx, [edi+0Ch]
        "895604"      # mov [esi+4], edx
        "eb0a"        # jmp done
        "83c710"      # advance: add edi, 16
        "49"          # dec ecx
    # Back to the top of the scan block. A displacement is measured from the end
    # of the instruction, and the jnz ends exactly 32 bytes past the block start.
    # An earlier -34 landed two bytes inside `mov ebx, [esi+4]`; the disassembly
    # check at the end of this script is what caught it.
    ) + bytes([0x0F, 0x85]) + struct.pack("<i", -32)          # jnz scan
    epilogue = bytes.fromhex("595f5e5b5dc20400")              # restore, ret 4

    jump_over = len(body) + len(scan)
    gate_jump = b"\x0f\x84" + struct.pack("<i", jump_over)
    return prologue + gate + gate_jump + body + scan + epilogue


def build_wrapper(lookup_va: int) -> bytes:
    """The existing wrapper with a call to the lookup spliced in after its
    prologue. Everything after that is byte-identical to what gold already has."""
    head = WRAPPER_ORIGINAL[:4]          # push ebp; mov ebp,esp; push esi
    call_site = WRAPPER_VA + len(head) + 4
    splice = (bytes.fromhex("8d4508")    # lea eax, [ebp+8]     -> &vector
              + b"\x50"                  # push eax
              + b"\xe8" + struct.pack("<i", lookup_va - (call_site + 5)))
    return head + splice + WRAPPER_ORIGINAL[4:]


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--table", type=Path, required=True,
                        help="note_table.bin from K1 Area Map Fixes")
    parser.add_argument("--default-enabled", type=int, default=1)
    args = parser.parse_args()

    if args.output.resolve() == args.source.resolve():
        raise SystemExit("refusing to patch in place")

    table = args.table.read_bytes()
    if len(table) != TABLE_ENTRIES * 16:
        raise SystemExit(f"expected {TABLE_ENTRIES * 16} bytes of table, got {len(table)}")
    digest = hashlib.sha256(table).hexdigest()
    if digest != TABLE_SHA256:
        raise SystemExit(f"table sha256 {digest} does not match the published "
                         f"{TABLE_SHA256}. Refusing to patch.")

    image = PEImage(args.source)
    if any(s.name == ".kmn" for s in image.sections):
        raise SystemExit("Source already contains a .kmn section")
    if not any(s.name == ".kui" for s in image.sections):
        raise SystemExit("Source has no .kui section: the marker wrappers must exist first")

    actual, wrapper_offset, section = image.read_va(WRAPPER_VA, len(WRAPPER_ORIGINAL))
    if actual != WRAPPER_ORIGINAL:
        raise SystemExit(
            f"0x{WRAPPER_VA:08X}: the coordinate wrapper is not what gold v20 shipped.\n"
            f"expected {WRAPPER_ORIGINAL.hex(' ')}\nfound    {actual.hex(' ')}\n"
            f"(file 0x{wrapper_offset:08X}, {section}). Refusing to patch.")

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
    section_va = image.image_base + new_rva

    payload = bytearray()
    payload += struct.pack("<I", 1 if args.default_enabled else 0)
    payload += struct.pack("<I", TABLE_ENTRIES)
    payload += MAGIC
    assert len(payload) == TABLE_OFFSET
    payload += table
    lookup_va = section_va + len(payload)
    payload += build_lookup(section_va)

    new_wrapper = build_wrapper(lookup_va)
    if len(new_wrapper) > WRAPPER_SLOT:
        raise SystemExit(f"the rewritten wrapper is {len(new_wrapper)} bytes, "
                         f"which does not fit its {WRAPPER_SLOT}-byte slot")
    data[wrapper_offset:wrapper_offset + len(new_wrapper)] = new_wrapper
    # Anything left of the old wrapper inside the slot becomes padding.
    tail = wrapper_offset + len(new_wrapper)
    data[tail:wrapper_offset + WRAPPER_SLOT] = b"\x90" * (WRAPPER_SLOT - len(new_wrapper))

    raw_offset = align(len(data), file_alignment)
    raw_size = align(len(payload), file_alignment)
    struct.pack_into("<H", data, coff + 2, section_count + 1)
    size_of_code = struct.unpack_from("<I", data, optional + 4)[0]
    struct.pack_into("<I", data, optional + 4, size_of_code + raw_size)
    struct.pack_into("<I", data, optional + 56,
                     align(new_rva + len(payload), section_alignment))
    struct.pack_into("<I", data, optional + 64, 0)   # PE checksum, left alone as ever
    header = struct.pack("<8sIIIIIIHHI", SECTION_NAME, len(payload), new_rva,
                         raw_size, raw_offset, 0, 0, 0, 0, SECTION_CHARACTERISTICS)
    data[header_slot:header_slot + 40] = header
    if len(data) < raw_offset:
        data.extend(b"\0" * (raw_offset - len(data)))
    payload_file = len(data)
    data.extend(payload)
    data.extend(b"\0" * (raw_size - len(payload)))

    args.output.write_bytes(bytes(data))

    print(f"  .kmn            VA 0x{section_va:08X}  file 0x{payload_file:08X}  "
          f"{len(payload)} bytes")
    print(f"  enabled flag    VA 0x{section_va + FLAG_OFFSET:08X}  "
          f"FILE 0x{payload_file + FLAG_OFFSET:08X}   <- ResolutionPatch writes this")
    print(f"  table           VA 0x{section_va + TABLE_OFFSET:08X}  "
          f"{TABLE_ENTRIES} entries, sha256 {digest[:16]}...")
    print(f"  lookup          VA 0x{lookup_va:08X}")
    print(f"  wrapper         0x{WRAPPER_VA:08X}  "
          f"{len(WRAPPER_ORIGINAL)} -> {len(new_wrapper)} bytes in a {WRAPPER_SLOT}-byte slot")

    out = PEImage(args.output)
    reread, _, sec = out.read_va(section_va, len(payload))
    if reread != bytes(payload) or sec != ".kmn":
        raise SystemExit("the section did not read back correctly")
    print("\nlookup routine as assembled:")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for insn in md.disasm(build_lookup(section_va), lookup_va):
        print(f"  {insn.address:08X}  {insn.mnemonic:<7} {insn.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
