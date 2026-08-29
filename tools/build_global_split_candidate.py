#!/usr/bin/env python3
"""Split stock HUD-map dimensions from the enlarged full-screen map.

The map-size immediates are shared by every CUIMap instance.  This candidate
restores those immediates to retail values, then wraps the full-map factory
call so only that instance receives the enlarged canvas and overlay.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def call_bytes(call_va: int, target_va: int) -> bytes:
    return b"\xE8" + struct.pack("<i", target_va - (call_va + 5))


def build_wrapper(wrapper_va: int) -> bytes:
    # Forward the constructor's parent argument, then restore the enlarged
    # map-control domains and child rectangles for the full-screen instance.
    code = bytearray.fromhex(
        "55 8B EC 56 83 EC 10"
        "FF 75 08"
        "E8 00 00 00 00"
        "89 C6"
        "C7 46 0C B8 06 00 00"  # map-control width domain = 1720
        "C7 46 10 D0 02 00 00"  # map-control height domain = 720
        "C7 86 70 00 00 00 B8 06 00 00"
        "C7 86 74 00 00 00 D0 02 00 00"
        "C7 45 F0 00 00 00 00"
        "C7 45 F4 00 00 00 00"
        "C7 45 F8 B8 06 00 00"
        "C7 45 FC D0 02 00 00"
        "8B 96 80 10 00 00 8D 8E 80 10 00 00 8D 45 F0 50 FF 52 04"
        "C7 45 F8 C6 05 00 00"
        "C7 45 FC D0 02 00 00"
        "8B 96 38 0E 00 00 8D 8E 38 0E 00 00 8D 45 F0 50 FF 52 04"
        "89 F0 83 C4 10 5E 5D C2 04 00"
    )
    call_va = wrapper_va + 10
    struct.pack_into("<i", code, 11, 0x00694D50 - (call_va + 5))
    return bytes(code)


def va_to_offset(image: PEImage, va: int) -> int:
    _, offset, _ = image.read_va(va, 1)
    return offset


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be separate")
    image = PEImage(args.source)
    data = bytearray(image.data)
    for va, value in ((0x0069505C, 512), (0x00695064, 256),
                      (0x00695082, 440), (0x0069508A, 256)):
        off = va_to_offset(image, va)
        struct.pack_into("<I", data, off, value)
    call_va = 0x00633102
    actual, call_off, _ = image.read_va(call_va, 5)
    expected = bytes.fromhex("E8 49 1C 06 00")
    if actual != expected:
        raise ValueError(f"unexpected full-map caller bytes: {actual.hex(' ')}")
    kui = next(s for s in image.sections if s.name == ".kui")
    append_offset = align(kui.virtual_size, 0x10)
    wrapper_va = image.image_base + kui.virtual_address + append_offset
    wrapper = build_wrapper(wrapper_va)
    if append_offset + len(wrapper) > kui.raw_size:
        raise ValueError("no .kui room")
    data[call_off:call_off+5] = call_bytes(call_va, wrapper_va)
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe_offset + 4
    opt = struct.unpack_from("<H", data, coff + 16)[0]
    table = coff + 20 + opt
    idx = image.sections.index(kui)
    hdr = table + idx * 40
    struct.pack_into("<I", data, hdr + 8, max(kui.virtual_size, append_offset + len(wrapper)))
    raw = kui.raw_offset + append_offset
    data[raw:raw+len(wrapper)] = wrapper
    args.output.write_bytes(data)
    out = PEImage(args.output)
    print(f"Wrote {args.output}")
    print(f"Wrapper VA 0x{wrapper_va:08X}, length {len(wrapper)}")
    print(f"SHA-256: {out.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
