#!/usr/bin/env python3
"""Add isolated full-map coordinate and hit-test wrappers to KOTOR."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".kui\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read
EMBEDDED_PAYLOAD = bytes.fromhex(
    "5589E556FF7518FF7514FF7510FF750CFF7508BA008E5700FFD285C07432508B"
    "75148B060FAF430C05DC00000099B9B8010000F7F989068B75188B060FAF4310"
    "058000000099B900010000F7F98906585E5DC214009090909090909090909090"
    "9090909090909090909090909090909090909090909090909090909090909090"
    "5589E556FF7510FF750CFF7508BAB0915700FFD285C07432508B750C8B060FAF"
    "430C05DC00000099B9B8010000F7F989068B75108B060FAF4310058000000099"
    "B900010000F7F98906585E5DC20C009090909090909090909090909090909090"
    "9090909090909090909090909090909090909090909090909090909090909090"
)
EMBEDDED_PAYLOAD_SHA256 = "0268b45fdc1da208a2157575f35cd69a6e5a2e4b3cdadf24d7d587b592334a07"


def build_hit_test_wrapper(wrapper_va: int) -> bytes:
    """Translate centered full-map mouse coordinates into overlay-local space.

    The overlay is owned by CUIMap (``this + 0x34``), whose embedded map
    canvas starts at ``+0x1080``.  KOTOR centers that canvas for rendering but
    passes uncentered mouse coordinates to the overlay's custom hit test.
    Deriving the inset from the live rectangles keeps this resolution-neutral.
    """
    code = bytearray.fromhex(
        "8B4134"              # mov eax,[ecx+34h]       ; owning CUIMap
        "85C0"                # test eax,eax
        "7421"                # jz original_hit_test
        "8B500C"              # mov edx,[eax+0Ch]      ; window width
        "2B908C100000"        # sub edx,[eax+108Ch]    ; canvas width
        "D1FA"                # sar edx,1
        "29542404"            # sub [esp+4],edx        ; mouse x
        "8B5010"              # mov edx,[eax+10h]      ; window height
        "2B9090100000"        # sub edx,[eax+1090h]    ; canvas height
        "D1FA"                # sar edx,1
        "83C20E"              # add edx,14             ; render viewport has a 14px top inset
        "29542408"            # sub [esp+8],edx        ; mouse y
        "E900000000"          # jmp 00693300h
    )
    jump_va = wrapper_va + len(code) - 5
    struct.pack_into("<i", code, len(code) - 4, 0x00693300 - (jump_va + 5))
    return bytes(code)


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def patch_exact(image: PEImage, data: bytearray, va: int, expected: bytes, replacement: bytes, label: str) -> None:
    if len(expected) != len(replacement):
        raise ValueError(f"Length mismatch for {label}")
    actual, offset, section = image.read_va(va, len(expected))
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{va:08X} (file 0x{offset:08X}, {section})"
        )
    data[offset : offset + len(replacement)] = replacement
    print(
        f"{label:<32} VA 0x{va:08X}  file 0x{offset:08X}  "
        f"{actual.hex(' ').upper()} -> {replacement.hex(' ').upper()}"
    )


def require_exact(image: PEImage, va: int, expected: bytes, label: str) -> None:
    actual, offset, section = image.read_va(va, len(expected))
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{va:08X} (file 0x{offset:08X}, {section})"
        )
    print(
        f"{label:<32} VA 0x{va:08X}  file 0x{offset:08X}  "
        f"verified {actual.hex(' ').upper()}"
    )


def encode_call(call_va: int, target_va: int) -> bytes:
    displacement = target_va - (call_va + 5)
    return b"\xE8" + struct.pack("<i", displacement)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--payload",
        type=Path,
        help="Optional 256-byte NASM payload; defaults to the verified embedded wrapper",
    )
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument(
        "--icon-width",
        type=int,
        help="Marker-overlay width; defaults to the full map width for legacy candidate 002",
    )
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")
    if not 1 <= args.width <= 16384 or not 1 <= args.height <= 16384:
        raise ValueError("Width and height must be between 1 and 16384")
    icon_width = args.icon_width if args.icon_width is not None else args.width
    if not 1 <= icon_width <= args.width:
        raise ValueError("Icon width must be between 1 and the map width")

    coordinate_payload = args.payload.read_bytes() if args.payload else EMBEDDED_PAYLOAD
    if len(coordinate_payload) != 0x100:
        raise ValueError(f"Expected a 256-byte coordinate-wrapper payload, got {len(coordinate_payload)}")
    coordinate_payload_sha256 = hashlib.sha256(coordinate_payload).hexdigest()
    if not args.payload and coordinate_payload_sha256 != EMBEDDED_PAYLOAD_SHA256:
        raise ValueError("Embedded wrapper payload hash mismatch")

    image = PEImage(args.source)
    data = bytearray(image.data)
    require_exact(
        image,
        0x0069505C,
        struct.pack("<I", args.width),
        "existing map render width",
    )
    require_exact(
        image,
        0x00695064,
        struct.pack("<I", args.height),
        "existing map render height",
    )
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
    if any(section.name == ".kui" for section in image.sections):
        raise ValueError("Source already contains a .kui section")

    last_section = max(image.sections, key=lambda section: section.virtual_address)
    new_rva = align(
        last_section.virtual_address + max(last_section.virtual_size, last_section.raw_size),
        section_alignment,
    )
    new_va = image.image_base + new_rva
    new_raw_offset = align(len(data), file_alignment)
    hit_test_wrapper = new_va + 0x100
    payload = coordinate_payload + build_hit_test_wrapper(hit_test_wrapper)
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    new_raw_size = align(len(payload), file_alignment)
    new_virtual_size = len(payload)

    wrapper_world_to_map = new_va
    wrapper_cached_point = new_va + 0x80
    patch_exact(
        image,
        data,
        0x006946F4,
        bytes.fromhex("E8 07 47 EE FF"),
        encode_call(0x006946F4, wrapper_world_to_map),
        "map object coordinate call",
    )
    patch_exact(
        image,
        data,
        0x00694A39,
        bytes.fromhex("E8 72 47 EE FF"),
        encode_call(0x00694A39, wrapper_cached_point),
        "party marker coordinate call",
    )
    patch_exact(
        image,
        data,
        0x00694AAC,
        bytes.fromhex("E8 FF 46 EE FF"),
        encode_call(0x00694AAC, wrapper_cached_point),
        "player arrow coordinate call",
    )
    patch_exact(
        image,
        data,
        0x00695082,
        bytes.fromhex("B8 01 00 00"),
        struct.pack("<I", icon_width),
        "icon-container width",
    )
    patch_exact(
        image,
        data,
        0x0069508A,
        bytes.fromhex("00 01 00 00"),
        struct.pack("<I", args.height),
        "icon-container height",
    )
    patch_exact(
        image,
        data,
        0x0075477C,
        struct.pack("<I", 0x00693300),
        struct.pack("<I", hit_test_wrapper),
        "map overlay hit-test vfunc",
    )

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
    written, _, section = output.read_va(new_va, len(payload))
    if written != payload or section != ".kui":
        raise ValueError("Wrapper section verification failed")
    print(f"Wrapper section                 VA 0x{new_va:08X}  raw 0x{new_raw_offset:08X}")
    print(f"Coordinate payload SHA-256: {coordinate_payload_sha256}")
    print(f"Combined payload SHA-256: {payload_sha256}")
    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
