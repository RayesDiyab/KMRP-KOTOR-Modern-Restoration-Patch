#!/usr/bin/env python3
"""Resize the shared map surface only while the full-screen map is active.

KOTOR's full-screen map and HUD minimap share the CUIMap render surface.  A
constructor-time resize therefore leaks into the HUD and makes the map texture
wrap vertically.  This builder restores the retail constructor dimensions and
hooks CUIMap's activation/deactivation vtable methods so the surface is large
only for the full-screen map.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from verify_map_patch import PEImage


SOURCE_SHA256 = "3C73627AEEE967BD780AFEA108A6AB2EC4EA6EAF345E15727E081F945506DBD2"

ACTIVATE_SLOT_VA = 0x00754878
DEACTIVATE_SLOT_VA = 0x0075487C
ORIGINAL_ACTIVATE_VA = 0x00693650
ORIGINAL_DEACTIVATE_VA = 0x00693BA0


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def va_to_offset(image: PEImage, va: int) -> int:
    _, offset, _ = image.read_va(va, 1)
    return offset


def build_surface_wrapper(
    wrapper_va: int,
    original_va: int,
    canvas_width: int,
    canvas_height: int,
    overlay_width: int,
    overlay_height: int,
    *,
    resize_before_original: bool,
) -> bytes:
    prologue = "55 8B EC 56 83 EC 10 89 CE"
    resize = (
        "C7 45 F0 00 00 00 00"       # rect.x = 0
        "C7 45 F4 00 00 00 00"       # rect.y = 0
        "C7 45 F8 11 11 11 11"       # canvas width
        "C7 45 FC 22 22 22 22"       # canvas height
        "8B 96 80 10 00 00"          # mov edx,[esi+1080h]
        "8D 8E 80 10 00 00"          # lea ecx,[esi+1080h]
        "8D 45 F0 50 FF 52 04"        # set canvas rect
        "C7 45 F8 33 33 33 33"       # overlay width
        "C7 45 FC 44 44 44 44"       # overlay height
        "8B 96 38 0E 00 00"          # mov edx,[esi+0E38h]
        "8D 8E 38 0E 00 00"          # lea ecx,[esi+0E38h]
        "8D 45 F0 50 FF 52 04"        # set overlay rect
    )
    original_call = "89 F1 E8 00 00 00 00"  # mov ecx,esi; call original
    epilogue = "83 C4 10 5E 5D C3"
    if resize_before_original:
        code = bytearray.fromhex(prologue + resize + original_call + epilogue)
    else:
        # Deactivation must clear the live marker/control list before changing
        # its rectangle.  Candidate 010 resized first, which let the rectangle
        # setter traverse live controls immediately before 00692E30 freed them
        # and caused the M-to-close crash.
        code = bytearray.fromhex(prologue + original_call + resize + epilogue)

    for sentinel, value in (
        (b"\x11" * 4, canvas_width),
        (b"\x22" * 4, canvas_height),
        (b"\x33" * 4, overlay_width),
        (b"\x44" * 4, overlay_height),
    ):
        offset = code.find(sentinel)
        if offset < 0 or code.find(sentinel, offset + 1) >= 0:
            raise ValueError(f"Wrapper sentinel {sentinel.hex()} is not unique")
        struct.pack_into("<I", code, offset, value)

    call_pattern = b"\xE8\0\0\0\0"
    call_offset = code.find(call_pattern)
    if call_offset < 0 or code.find(call_pattern, call_offset + 1) >= 0:
        raise ValueError("Original-method call placeholder is not unique")
    call_va = wrapper_va + call_offset
    struct.pack_into("<i", code, call_offset + 1, original_va - (call_va + 5))
    return bytes(code)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")
    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest().upper()
    if source_hash != SOURCE_SHA256:
        raise ValueError(f"Unexpected source SHA-256: {source_hash}")

    image = PEImage(args.source)
    data = bytearray(image.data)
    kui = next((section for section in image.sections if section.name == ".kui"), None)
    if kui is None:
        raise ValueError("Source must contain the existing .kui section")

    # Undo the constructor-time enlargement that leaks into the HUD minimap.
    for va, value in (
        (0x0069505C, 512),
        (0x00695064, 256),
        (0x00695082, 440),
        (0x0069508A, 256),
    ):
        struct.pack_into("<I", data, va_to_offset(image, va), value)

    append_offset = align(kui.virtual_size, 0x10)
    activate_va = image.image_base + kui.virtual_address + append_offset
    activate = build_surface_wrapper(
        activate_va,
        ORIGINAL_ACTIVATE_VA,
        1720,
        720,
        1478,
        720,
        resize_before_original=True,
    )
    deactivate_offset = align(append_offset + len(activate), 0x10)
    deactivate_va = image.image_base + kui.virtual_address + deactivate_offset
    deactivate = build_surface_wrapper(
        deactivate_va,
        ORIGINAL_DEACTIVATE_VA,
        512,
        256,
        440,
        256,
        resize_before_original=False,
    )

    if deactivate_offset + len(deactivate) > kui.raw_size:
        raise ValueError("Existing .kui raw section has no room for wrappers")

    struct.pack_into("<I", data, va_to_offset(image, ACTIVATE_SLOT_VA), activate_va)
    struct.pack_into("<I", data, va_to_offset(image, DEACTIVATE_SLOT_VA), deactivate_va)
    activate_raw = kui.raw_offset + append_offset
    deactivate_raw = kui.raw_offset + deactivate_offset
    data[activate_raw : activate_raw + len(activate)] = activate
    data[deactivate_raw : deactivate_raw + len(deactivate)] = deactivate

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    coff_offset = pe_offset + 4
    optional_size = struct.unpack_from("<H", data, coff_offset + 16)[0]
    section_table = coff_offset + 20 + optional_size
    kui_index = image.sections.index(kui)
    kui_header_offset = section_table + kui_index * 40
    new_virtual_size = max(kui.virtual_size, deactivate_offset + len(deactivate))
    struct.pack_into("<I", data, kui_header_offset + 8, new_virtual_size)

    args.output.write_bytes(data)
    output = PEImage(args.output)
    for va, wrapper in ((activate_va, activate), (deactivate_va, deactivate)):
        written, _, section = output.read_va(va, len(wrapper))
        if written != wrapper or section != ".kui":
            raise ValueError(f"Wrapper verification failed at 0x{va:08X}")

    print(f"Full-map activate slot -> 0x{activate_va:08X}")
    print(f"Full-map deactivate slot -> 0x{deactivate_va:08X}")
    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
