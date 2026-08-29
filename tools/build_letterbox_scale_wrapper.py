#!/usr/bin/env python3
"""Fix the dialogue letterbox/reply-box sizing at ultrawide resolutions.

Vanilla KOTOR derives the dialogue letterbox bar height from screen WIDTH:

    barHeight = round((screenHeight - round(screenWidth * scale)) * 0.5)

At ultrawide resolutions `round(screenWidth * scale)` approaches or exceeds
screenHeight, so the computed bar becomes tiny — this is why, after the font
scale patch made dialogue text bigger, subtitle text clips at the bottom
(descenders like the tail of 'y' get cut off) and sometimes fails to display
at all (when the required text height exceeds the undersized bar entirely).

This reproduces (independently re-verified against our own exe copy) the
"Scaled Letterbox" Kotor Patch Manager patch's fix
(https://github.com/J0-o/KotorUniResPatch): replace the width-derived formula
with a HEIGHT-derived one at 9 call sites across the dialogue GUI code:

    barHeight = round(screenHeight / 6)

Two of the nine replacements are longer than the bytes they replace and need
a small trampoline (jmp out, run the replacement, jmp back) placed in a new
`.klb` PE section; the other seven are the same length or shorter than the
original and are patched in place with trailing NOPs, exactly like this
project's existing simple byte-constant patches.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".klb\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def h(hexstr: str) -> bytes:
    return bytes.fromhex(hexstr.replace(" ", "").replace("\n", ""))


def encode_jmp(jmp_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (jmp_va + 5))


# (address, original_bytes, replacement_bytes, label)
HOOKS = [
    (
        0x006A74D2,
        h("0FBF4F6C 894C240C DB44240C D80D88577500 E8A3390500 0FBF576E 2BD0 8954240C DB44240C D80DACE97300 E88A390500"),
        h("0FBF476E 83C003 51 99 B906000000 F7F9 59"),
        "SetTop constructor path",
    ),
    (
        0x006A7560,
        h("0FBF4F6C 0FBF5F6E 894C240C DB44240C D80D88577500 E8113905 00 8BD3 2BD0 8954240C DB44240C D80DACE97300 E8FA380500"),
        h("0FBF5F6E 8BC3 83C003 51 99 B906000000 F7F9 59"),
        "SetBottom constructor path",
    ),
    (
        0x006A7943,
        h("0FBF556C 8954240F".replace("240F", "2410") + "DB442410 D80D88577500 E8323505 00 0FBF4D6E 2BC8 8BC1 99 2BC2 D1F8 2BC3 83E805"),
        h("0FBF456E 83C003 51 99 B906000000 F7F9 59 2BC3 83E805"),
        "Nested message/dialog owner root height",
    ),
    (
        0x006A7B59,
        h("8B7E18 0FBF576C 8954 2424 DB442424 D80D88577500 E8193305 00 0FBF4F6E 2BC8 8BC1 8B4C2408 99 2BC2 D1F8 2BC1 83C0FB"),
        h("8B7E18 0FBF476E 83C003 51 99 B906000000 F7F9 59 2B442408 83C0FB"),
        "Later message refresh path",
    ),
    (
        0x006A7F3D,
        h("0FBF436C 0FBF7B6E 8944 2414 DB442414 D80D88577500 E8342F0500 8BCF 2BC8 8BC1 99 2BC2 8B542410 D1F8 2BF8 897C2428"),
        h("0FBF7B6E 8BC7 83C003 51 99 B906000000 F7F9 59 2BF8 8B542410 897C2428"),
        "CSWGuiDialogCinematic bottom root top",
    ),
    (
        0x006A8C4C,
        h("0FBF476C 8944 2410 DB442410 D80DE45A7500 E8292205 00 0FBF4F6E 2BC8 8BC1 99 2BC2 8B542464 D1F8 8944 2428"),
        h("0FBF476E 50 83C003 99 B906000000 F7F9 59 2BC8 894C2428 8B542464"),
        "Dialogue owner constructor bottom root placement",
    ),
    (
        0x006A7CD0,
        h("8B96C4190000 8944 2410 894C240C 8D8EC4190000 8D442404 50 FF5204"),
        h("8B4618 0FBF406E 83C003 51 99 B906000000 F7F9 59 2B442408 8986D4190000 8B96C4190000 8944 2410 894C240C 8D8EC4190000 8D442404 50 FF5204"),
        "CSWGuiDialog::SetRect LB_REPLIES height",
    ),
    (
        0x006A8E1D,
        h("F686081A000002 744F"),
        h("85DB 7417 8B4618 0FBF406E 83C003 51 99 B906000000 F7F9 59 894610 F686081A000002 7506 6875 8E6A00 C3"),
        "CSWGuiDialogCinematic::SetReplies",
    ),
    (
        0x006A7F71,
        h("8B7E10"),
        h("6A64 5F"),
        "CSWGuiDialogCinematic old-height baseline",
    ),
]


def require_exact(image: PEImage, va: int, expected: bytes, label: str) -> None:
    actual, offset, section = image.read_va(va, len(expected))
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{va:08X} (file 0x{offset:08X}, {section})"
        )
    print(f"{label:<46} VA 0x{va:08X}  file 0x{offset:08X}  verified {actual.hex(' ').upper()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")

    image = PEImage(args.source)
    data = bytearray(image.data)

    for va, original, replacement, label in HOOKS:
        require_exact(image, va, original, label)

    trampoline_hooks = [(va, o, r, l) for va, o, r, l in HOOKS if len(r) > len(o)]
    inline_hooks = [(va, o, r, l) for va, o, r, l in HOOKS if len(r) <= len(o)]

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
    if any(section.name == ".klb" for section in image.sections):
        raise ValueError("Source already contains a .klb section")

    last_section = max(image.sections, key=lambda section: section.virtual_address)
    new_rva = align(
        last_section.virtual_address + max(last_section.virtual_size, last_section.raw_size),
        section_alignment,
    )
    new_va = image.image_base + new_rva

    # Lay out trampoline stubs for the two hooks whose replacement is longer
    # than the bytes it replaces.
    stubs: dict[int, tuple[int, bytes]] = {}
    cursor = new_va
    for va, original, replacement, label in trampoline_hooks:
        resume_va = va + len(original)
        stub = replacement + encode_jmp(cursor + len(replacement), resume_va)
        stubs[va] = (cursor, stub)
        cursor += len(stub)
    payload = b"".join(stub for _, stub in stubs.values())
    new_raw_offset = align(len(data), file_alignment)
    new_raw_size = align(len(payload), file_alignment) if payload else 0
    new_virtual_size = len(payload)

    for va, original, replacement, label in inline_hooks:
        offset, _ = image.va_to_file_offset(va)
        padded = replacement + b"\x90" * (len(original) - len(replacement))
        data[offset : offset + len(original)] = padded
        print(f"{label:<46} VA 0x{va:08X}  patched in place ({len(replacement)}/{len(original)} bytes + NOP)")

    for va, original, replacement, label in trampoline_hooks:
        stub_va, _ = stubs[va]
        offset, _ = image.va_to_file_offset(va)
        jump = encode_jmp(va, stub_va) + b"\x90" * (len(original) - 5)
        data[offset : offset + len(original)] = jump
        print(f"{label:<46} VA 0x{va:08X}  -> trampoline VA 0x{stub_va:08X} ({len(replacement)} bytes)")

    if payload:
        struct.pack_into("<H", data, coff_offset + 2, section_count + 1)
        size_of_code = struct.unpack_from("<I", data, optional_offset + 4)[0]
        struct.pack_into("<I", data, optional_offset + 4, size_of_code + new_raw_size)
        struct.pack_into("<I", data, optional_offset + 56, align(new_rva + new_virtual_size, section_alignment))
        struct.pack_into("<I", data, optional_offset + 64, 0)

        section_header = struct.pack(
            "<8sIIIIIIHHI",
            SECTION_NAME,
            new_virtual_size,
            new_rva,
            new_raw_size,
            new_raw_offset,
            0,
            0,
            0,
            0,
            SECTION_CHARACTERISTICS,
        )
        data[new_header_offset : new_header_offset + 40] = section_header
        if len(data) < new_raw_offset:
            data.extend(b"\0" * (new_raw_offset - len(data)))
        data.extend(payload)
        data.extend(b"\0" * (new_raw_size - len(payload)))

    args.output.write_bytes(data)
    output = PEImage(args.output)

    for va, original, replacement, label in inline_hooks:
        reread, _, _ = output.read_va(va, len(original))
        expected = replacement + b"\x90" * (len(original) - len(replacement))
        if reread != expected:
            raise ValueError(f"Verification failed for inline hook: {label}")
    for va, original, replacement, label in trampoline_hooks:
        stub_va, stub_bytes = stubs[va]
        reread, _, _ = output.read_va(va, 5)
        if reread != encode_jmp(va, stub_va):
            raise ValueError(f"Verification failed for trampoline jump: {label}")
        reread, _, section = output.read_va(stub_va, len(stub_bytes))
        if reread != stub_bytes or section != ".klb":
            raise ValueError(f"Verification failed for trampoline stub: {label}")

    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
