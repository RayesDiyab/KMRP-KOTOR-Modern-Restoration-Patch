#!/usr/bin/env python3
"""SUPERSEDED by build_movie_letterbox.py -- kept for the v23->v24 record.

This produced gold v24. It fixed the aspect ratio but left the bars it
created unpainted: BinkBufferOpen is called with the MOVIE's size, and Bink
draws nothing outside the blit rectangle, so fitting inside the window
exposed stale framebuffer down both sides -- a grey flash around every
movie, reported from play. v25 pads the BUFFER to the window aspect instead,
so the bars are part of the image. The build no longer uses this file.

Original description follows.

Replace KOTOR's width-only Bink scaling with true aspect-fit scaling.

The retail movie loop scales every BIK from the client width. On an ultrawide
display that enlarges a 4:3 640x480 logo to 3440x2580 and crops 1140 vertical
pixels. The injected integer routine selects the smaller of the width and
height ratios for the live BIK dimensions, so vanilla and high-resolution movie
replacements share one policy and are never stretched or cropped.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from verify_map_patch import PEImage


EXPECTED_INPUT_LENGTH = 4_083_712
EXPECTED_INPUT_SHA256 = "29BE3C23F53D53F521D98329F996248864834FB3873819DF63CCF1803C65A7E8"
EXPECTED_OUTPUT_LENGTH = 4_087_808
EXPECTED_OUTPUT_SHA256 = "9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A"

SECTION_NAME = b".kmv\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read
HOOK_VA = 0x004057AC
RESUME_VA = 0x00405808
HOOK_ORIGINAL = bytes.fromhex("8B 4E 48 8B 01 3B D8")
BINK_BUFFER_SET_SCALE_IAT = 0x0073D484


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def encode_jmp(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5))


def build_stub(stub_va: int) -> bytes:
    # Entry state at 0x004057AC:
    #   ESI = CExoMoviePlayerInternal*, EBX = client width,
    #   EBP = client bottom, [ESP+0x24] = client top.
    # Save EDI because the original continuation uses it as client right. The
    # saved value shifts the original locals by four bytes while this runs.
    code = bytearray.fromhex(
        "57 "                    # push edi
        "8B 46 48 "              # mov eax,[esi+48]       ; BINK*
        "8B 08 "                 # mov ecx,[eax]          ; movie width
        "8B 50 04 "              # mov edx,[eax+4]        ; movie height
        "8B FB "                 # mov edi,ebx            ; client width
        "0F AF FA "              # imul edi,edx           ; cw * mh
        "8B C5 "                 # mov eax,ebp
        "2B 44 24 28 "           # sub eax,[esp+28]       ; client height
        "0F AF C1 "              # imul eax,ecx           ; ch * mw
        "3B F8 "                 # cmp edi,eax
        "7E 16 "                 # jle width_limited
        # Height-limited: sh=client height, sw=mw*sh/mh.
        "8B C5 "                 # mov eax,ebp
        "2B 44 24 28 "           # sub eax,[esp+28]
        "8B F8 "                 # mov edi,eax            ; scaled height
        "0F AF C1 "              # imul eax,ecx
        "99 "                    # cdq
        "8B 4E 48 "              # mov ecx,[esi+48]
        "F7 79 04 "              # idiv dword ptr [ecx+4]
        "8B D8 "                 # mov ebx,eax            ; scaled width
        # 0x0A, not 0x0B. The width-limited block below is exactly ten bytes
        # (2+3+1+2+2), so 0x0B landed one byte inside the shared
        # `mov [esp+14],edi` that follows it, resuming on `7C 24` -- a `jl` into
        # nothing -- on every movie. Found by disassembling the built image, not
        # the intended assembly; verify_stub() below now enforces it.
        "EB 0A "                 # jmp apply
        # Width-limited: sw=client width, sh=mh*sw/mw.
        "8B C2 "                 # width_limited: mov eax,edx
        "0F AF C3 "              # imul eax,ebx
        "99 "                    # cdq
        "F7 F9 "                 # idiv ecx
        "8B F8 "                 # mov edi,eax            ; scaled height
        # Apply both dimensions and leave the original centring inputs intact.
        "89 7C 24 14 "           # apply: mov [esp+14],edi ; original [esp+10]
        "8B 46 4C "              # mov eax,[esi+4c]       ; Bink buffer
        "57 "                    # push scaled height
        "53 "                    # push scaled width
        "50 "                    # push buffer
        "FF 15 84 D4 73 00 "     # call [BinkBufferSetScale]
        "5F"                     # pop edi
    )
    if BINK_BUFFER_SET_SCALE_IAT != 0x0073D484:
        raise AssertionError("Update the encoded BinkBufferSetScale IAT operand")
    code += encode_jmp(stub_va + len(code), RESUME_VA)
    return bytes(code)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")
    source = args.source.read_bytes()
    if len(source) != EXPECTED_INPUT_LENGTH or sha256(source) != EXPECTED_INPUT_SHA256:
        raise SystemExit("Refusing an unexpected gold v23 snapshot")

    image = PEImage(args.source)
    actual, hook_offset, hook_section = image.read_va(HOOK_VA, len(HOOK_ORIGINAL))
    if actual != HOOK_ORIGINAL or hook_section != ".text":
        raise ValueError(
            f"movie scale hook mismatch at VA 0x{HOOK_VA:08X}: {actual.hex(' ')}"
        )

    data = bytearray(source)
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
    if any(section.name == ".kmv" for section in image.sections):
        raise ValueError("Source already contains a .kmv section")

    last = max(image.sections, key=lambda section: section.virtual_address)
    new_rva = align(
        last.virtual_address + max(last.virtual_size, last.raw_size),
        section_alignment,
    )
    new_va = image.image_base + new_rva
    payload = build_stub(new_va)
    new_raw_offset = align(len(data), file_alignment)
    new_raw_size = align(len(payload), file_alignment)

    hook = encode_jmp(HOOK_VA, new_va) + b"\x90" * (len(HOOK_ORIGINAL) - 5)
    data[hook_offset : hook_offset + len(HOOK_ORIGINAL)] = hook

    struct.pack_into("<H", data, coff_offset + 2, section_count + 1)
    size_of_code = struct.unpack_from("<I", data, optional_offset + 4)[0]
    struct.pack_into("<I", data, optional_offset + 4, size_of_code + new_raw_size)
    struct.pack_into(
        "<I", data, optional_offset + 56,
        align(new_rva + len(payload), section_alignment),
    )
    struct.pack_into("<I", data, optional_offset + 64, 0)  # checksum
    header = struct.pack(
        "<8sIIIIIIHHI",
        SECTION_NAME,
        len(payload),
        new_rva,
        new_raw_size,
        new_raw_offset,
        0, 0, 0, 0,
        SECTION_CHARACTERISTICS,
    )
    data[new_header_offset : new_header_offset + 40] = header
    data.extend(b"\0" * (new_raw_offset - len(data)))
    data.extend(payload)
    data.extend(b"\0" * (new_raw_size - len(payload)))

    if len(data) != EXPECTED_OUTPUT_LENGTH:
        raise AssertionError(f"Unexpected output length {len(data)}")
    output_hash = sha256(data)
    if EXPECTED_OUTPUT_SHA256 and output_hash != EXPECTED_OUTPUT_SHA256:
        raise AssertionError(f"Unexpected output SHA-256 {output_hash}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    output = PEImage(args.output)
    reread, _, section = output.read_va(new_va, len(payload))
    if reread != payload or section != ".kmv":
        raise AssertionError("Injected movie aspect-fit routine failed read-back")
    reread, _, _ = output.read_va(HOOK_VA, len(HOOK_ORIGINAL))
    if reread != hook:
        raise AssertionError("Movie aspect-fit hook failed read-back")
    if sha256(args.output.read_bytes()) != output_hash:
        raise AssertionError("Written output failed SHA-256 verification")

    print(f"Movie aspect-fit hook: VA 0x{HOOK_VA:08X} -> 0x{new_va:08X}")
    print(f"Payload: {len(payload)} bytes in .kmv")
    print(f"Wrote {args.output}")
    print(f"Length: {len(data)}")
    print(f"SHA-256: {output_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
