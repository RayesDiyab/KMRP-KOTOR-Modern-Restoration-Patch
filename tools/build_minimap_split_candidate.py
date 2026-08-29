#!/usr/bin/env python3
"""Restore stock dimensions for the gameplay minimap constructor call.

The universal map patch enlarges the shared CUIMap canvas.  The game creates
the same CUIMap class for the full map and the HUD minimap, so this candidate
wraps one constructor call and restores the stock canvas/overlay extents only
for that instance.  The caller is selectable because the two retail GUI
factories use different type-dispatch sites.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


CALLERS = {
    0x0062B39B: bytes.fromhex("E8 B0 99 06 00"),
    0x00633102: bytes.fromhex("E8 49 1C 06 00"),
}


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def va_to_offset(image: PEImage, va: int) -> int:
    _, offset, _ = image.read_va(va, 1)
    return offset


def call_bytes(call_va: int, target_va: int) -> bytes:
    return b"\xE8" + struct.pack("<i", target_va - (call_va + 5))


def build_wrapper(wrapper_va: int, constructor_va: int) -> bytes:
    code = bytearray.fromhex(
        "55"                         # push ebp
        "8BEC"                       # mov ebp,esp
        "56"                         # push esi
        "83EC10"                     # sub esp,10h (x,y,w,h rect)
        "FF7508"                     # push original parent argument
        "E800000000"                 # call constructor (patched below)
        "89C6"                       # mov esi,eax
        # The executable-wide resize also changes the map object's own
        # normalization/render domains.  Restore those stock fields for the
        # gameplay minimap instance before touching its child controls.
        "C7460C00020000"             # this->width domain = 512
        "C7461000010000"             # this->height domain = 256
        "C7867000000000020000"       # this->render width = 512
        "C7867400000000010000"       # this->render height = 256
        "C745F000000000"             # rect.x = 0
        "C745F400000000"             # rect.y = 0
        "C745F800020000"             # canvas width = 512
        "C745FC00010000"             # canvas height = 256
        "8B9680100000"               # mov edx,[esi+1080h]
        "8D8E80100000"               # lea ecx,[esi+1080h]
        "8D45F0"                     # lea eax,[ebp-10h]
        "50"                         # push rect
        "FF5204"                     # call [edx+4]
        "C745F8B8010000"             # overlay width = 440
        "C745FC00010000"             # overlay height = 256
        "8B96380E0000"               # mov edx,[esi+0E38h]
        "8D8E380E0000"               # lea ecx,[esi+0E38h]
        "8D45F0"                     # lea eax,[ebp-10h]
        "50"                         # push rect
        "FF5204"                     # call [edx+4]
        "89F0"                       # mov eax,esi (constructor result)
        "83C410"                     # add esp,10h
        "5E"                         # pop esi
        "5D"                         # pop ebp
        "C20400"                     # ret 4 (constructor call also consumed one parent arg)
    )
    call_va = wrapper_va + 10
    struct.pack_into("<i", code, 11, constructor_va - (call_va + 5))
    return bytes(code)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--caller", required=True, type=lambda value: int(value, 0), choices=CALLERS)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")
    image = PEImage(args.source)
    data = bytearray(image.data)
    kui = next((section for section in image.sections if section.name == ".kui"), None)
    if kui is None:
        raise ValueError("Source must contain the existing .kui section")

    append_offset = align(kui.virtual_size, 0x10)
    wrapper_va = image.image_base + kui.virtual_address + append_offset
    wrapper = build_wrapper(wrapper_va, 0x00694D50)
    if append_offset + len(wrapper) > kui.raw_size:
        raise ValueError("Existing .kui raw section has no room for wrapper")

    call_va = args.caller
    actual, call_offset, _ = image.read_va(call_va, 5)
    expected = CALLERS[call_va]
    if actual != expected:
        raise ValueError(f"caller bytes mismatch at 0x{call_va:08X}: {actual.hex(' ')}")
    replacement = call_bytes(call_va, wrapper_va)
    data[call_offset : call_offset + 5] = replacement

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    coff_offset = pe_offset + 4
    optional_size = struct.unpack_from("<H", data, coff_offset + 16)[0]
    section_table = coff_offset + 20 + optional_size
    kui_index = image.sections.index(kui)
    kui_header_offset = section_table + kui_index * 40
    new_virtual_size = max(kui.virtual_size, append_offset + len(wrapper))
    struct.pack_into("<I", data, kui_header_offset + 8, new_virtual_size)
    raw_offset = kui.raw_offset + append_offset
    data[raw_offset : raw_offset + len(wrapper)] = wrapper
    args.output.write_bytes(data)

    output = PEImage(args.output)
    written, _, section = output.read_va(wrapper_va, len(wrapper))
    if written != wrapper or section != ".kui":
        raise ValueError("minimap wrapper verification failed")
    print(f"Caller 0x{call_va:08X}: {actual.hex(' ').upper()} -> {replacement.hex(' ').upper()}")
    print(f"Minimap wrapper VA 0x{wrapper_va:08X}, length {len(wrapper)}")
    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
