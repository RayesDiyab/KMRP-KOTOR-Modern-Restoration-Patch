#!/usr/bin/env python3
"""Stop the word-wrap loop that hangs, and keep unfittable text visible.

`CAurGUIString`'s line-breaker (`0x0045A2F0`) breaks an over-long line that
holds no space by backing the cursor up one character and restarting the line
there, guarded only against the start of the whole *string*:

    0045A5E0  mov eax,[esi+14]     ; start of the STRING
    0045A5E3  dec ebx              ; back up one character
    0045A5E4  cmp ebx,eax
    0045A5EA  je  0045A834         ; bail out only if we are at the string start

Wrong reference point. When the cursor lands back on the start of the current
*line*, the guard does not fire, the line restarts where it began, and the
function loops forever appending a line-break entry every pass. Each append
grows two arrays by doubling until the allocator fails; the grow helper at
`0x005E03C0` never checks its result, so the game dies writing through NULL.
Observed live: 33.5 million entries, a 268MB request, then the crash.

What reaches it: the item stack-count label is **21px wide** and its text is a
bare number, so there is never a space to break on. The widest pair of stock
digits is 20px -- vanilla clears that label by a single pixel, so any font
enlargement trips it.

**Why guaranteeing progress is not enough.** An earlier version snapped the
cursor to `lineStart + 1`, which terminates but emits one character per line.
`Draw` centres text vertically by `(height - lines * lineHeight) / 2`
(`0x0045A932`), so wrapping "159" to three 24px lines inside a 19px label gives
`(19 - 72) / 2 = -26.5px` -- the digits land far above the icon and vanish.
Unwrapped it is `(19 - 24) / 2 = -2.5px`, which stays visible. So when a line
cannot progress this consumes the rest of the string as ONE line: the stub
walks the cursor to the closing NUL and rejoins the engine's own end-of-line
path at `0x0045A785`, which appends that line and drops out of the loop at
`0x0045A821` because the cursor now sits on the terminator.

**And that alone was still not enough**, because two guards run *before* the
loop and blank short strings outright rather than trying to lay them out:

    0x0045A3B7   strlen == 1 : bail if maxWidth <     width('o')
    0x0045A3DC   strlen <= 2 : bail if maxWidth < 2 * width('o')

Both jump to `0x0045A83C`, which zeroes the entry counts so `Draw` renders
nothing. Reasonable in vanilla, where they fire only for a hopeless box -- but
the stack-count label is a fixed 21px while an enlarged font takes width('o')
to 12px at 1080p and 16px at 1440p, so **every two-digit stack count silently
disappears** (and single digits too at 2160p). This happens before the loop is
reached, which is why patching the loop alone did not bring the numbers back.

The three changes are a set. Removing the guards is only safe *because* of the
loop patch: a box too narrow for one character used to spin forever, and now
degrades to a single overflowing line. Do not NOP the guards without it.

Normal text reaches none of this: a line that fits even one character always
progresses, and strings of three or more characters skip both guards.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".kwl\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read

HOOK_VA = 0x0045A5E0
RESUME_VA = 0x0045A5F0      # the original fall-through, when the line progressed
ENDLINE_VA = 0x0045A785     # the engine's own "append this line and continue"

ORIGINAL = bytes.fromhex("8B4614" "4B" "3BD8" "894C2410" "0F8444020000")

# The two early "give up and draw nothing" guards described above.
GUARD_SITES = (
    (0x0045A3B7, bytes.fromhex("0F8C7F040000")),   # strlen == 1
    (0x0045A3DC, bytes.fromhex("0F8C5A040000")),   # strlen <= 2
)
NOP = 0x90


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def encode_jmp(jmp_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (jmp_va + 5))


def build_patch(stub_va: int) -> bytes:
    """The 16 bytes replacing the original guard, same length, patched in place."""
    patch = bytearray()
    patch += b"\x4B"                    # dec  ebx
    patch += b"\x3B\x5C\x24\x18"        # cmp  ebx,[esp+0x18]   ; the LINE's start
    patch += b"\x89\x4C\x24\x10"        # mov  [esp+0x10],ecx   ; original side effect
    patch += b"\x77\x05"                # ja   RESUME_VA        ; progressed -> carry on
    patch += encode_jmp(HOOK_VA + len(patch), stub_va)
    assert len(patch) == len(ORIGINAL), len(patch)
    return bytes(patch)


def build_stub(stub_va: int) -> bytes:
    """Consume the rest of the string as one line, then rejoin the engine."""
    stub = bytearray()
    stub += b"\x8B\x5C\x24\x18"         # mov  ebx,[esp+0x18]   ; back to line start
    stub += b"\x80\x3B\x00"             # scan: cmp byte [ebx],0
    stub += b"\x74\x03"                 #       je   done
    stub += b"\x43"                     #       inc  ebx
    stub += b"\xEB\xF8"                 #       jmp  scan
    stub += encode_jmp(stub_va + len(stub), ENDLINE_VA)   # done: jmp 0x0045A785
    return bytes(stub)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")

    image = PEImage(args.source)
    actual, offset, section = image.read_va(HOOK_VA, len(ORIGINAL))
    if actual != ORIGINAL:
        raise ValueError(
            f"Word-wrap guard: expected {ORIGINAL.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{HOOK_VA:08X} (file 0x{offset:08X}, {section}). "
            f"This patches the ORIGINAL bytes -- do not run it on an exe that "
            f"already carries a wrap fix.")
    for guard_va, guard_bytes in GUARD_SITES:
        found, _, _ = image.read_va(guard_va, len(guard_bytes))
        if found != guard_bytes:
            raise ValueError(
                f"Short-string guard at 0x{guard_va:08X}: expected "
                f"{guard_bytes.hex(' ')}, found {found.hex(' ')}")

    data = bytearray(image.data)

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    coff_offset = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff_offset + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff_offset + 16)[0]
    optional_offset = coff_offset + 20
    section_offset = optional_offset + optional_size
    file_alignment = struct.unpack_from("<I", data, optional_offset + 36)[0]
    section_alignment = struct.unpack_from("<I", data, optional_offset + 32)[0]

    new_header_offset = section_offset + section_count * 40
    if new_header_offset + 40 > image.size_of_headers:
        raise ValueError("No room for another PE section header")
    if any(s.name == ".kwl" for s in image.sections):
        raise ValueError("Source already contains a .kwl section")

    last = max(image.sections, key=lambda s: s.virtual_address)
    new_rva = align(last.virtual_address + max(last.virtual_size, last.raw_size),
                    section_alignment)
    stub_va = image.image_base + new_rva

    stub = build_stub(stub_va)
    patch = build_patch(stub_va)

    print(f"{'Word-wrap guard':<28} VA 0x{HOOK_VA:08X}  file 0x{offset:08X}")
    print(f"{'  original':<28} {ORIGINAL.hex(' ').upper()}")
    print(f"{'  replacement':<28} {patch.hex(' ').upper()}")
    print(f"{'  stub (.kwl)':<28} VA 0x{stub_va:08X}  {stub.hex(' ').upper()}")

    data[offset:offset + len(ORIGINAL)] = patch

    for guard_va, guard_bytes in GUARD_SITES:
        guard_offset, _ = image.va_to_file_offset(guard_va)
        data[guard_offset:guard_offset + len(guard_bytes)] = bytes([NOP]) * len(guard_bytes)
        print(f"{'  short-string guard':<28} VA 0x{guard_va:08X}  "
              f"{guard_bytes.hex(' ').upper()} -> {len(guard_bytes)}x NOP")

    raw_offset = align(len(data), file_alignment)
    raw_size = align(len(stub), file_alignment)
    struct.pack_into("<H", data, coff_offset + 2, section_count + 1)
    size_of_code = struct.unpack_from("<I", data, optional_offset + 4)[0]
    struct.pack_into("<I", data, optional_offset + 4, size_of_code + raw_size)
    struct.pack_into("<I", data, optional_offset + 56,
                     align(new_rva + len(stub), section_alignment))
    struct.pack_into("<I", data, optional_offset + 64, 0)
    header = struct.pack("<8sIIIIIIHHI", SECTION_NAME, len(stub), new_rva,
                         raw_size, raw_offset, 0, 0, 0, 0, SECTION_CHARACTERISTICS)
    data[new_header_offset:new_header_offset + 40] = header
    if len(data) < raw_offset:
        data.extend(b"\0" * (raw_offset - len(data)))
    data.extend(stub)
    data.extend(b"\0" * (raw_size - len(stub)))

    args.output.write_bytes(data)
    output = PEImage(args.output)

    reread, _, _ = output.read_va(HOOK_VA, len(patch))
    if reread != patch:
        raise ValueError("Verification failed: patched bytes did not read back")
    reread, _, sect = output.read_va(stub_va, len(stub))
    if reread != stub or sect != ".kwl":
        raise ValueError("Verification failed: stub contents/section")
    for guard_va, guard_bytes in GUARD_SITES:
        reread, _, _ = output.read_va(guard_va, len(guard_bytes))
        if reread != bytes([NOP]) * len(guard_bytes):
            raise ValueError(f"Verification failed: guard 0x{guard_va:08X}")

    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
