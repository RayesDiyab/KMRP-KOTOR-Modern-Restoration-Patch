#!/usr/bin/env python3
"""Adjust the full-map marker hit-test wrapper's vertical screen inset."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from build_map_icon_draw_wrapper import build_hit_test_wrapper
from verify_map_patch import PEImage


HIT_TEST_VTABLE_SLOT = 0x0075477C


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--top-inset", type=int, required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be separate from source")
    if not 0 <= args.top_inset <= 127:
        raise ValueError("Top inset must fit a positive signed imm8")

    image = PEImage(args.source)
    data = bytearray(image.data)
    pointer_bytes, _, _ = image.read_va(HIT_TEST_VTABLE_SLOT, 4)
    wrapper_va = struct.unpack("<I", pointer_bytes)[0]
    expected = build_hit_test_wrapper(wrapper_va)
    actual, wrapper_offset, section = image.read_va(wrapper_va, len(expected))
    if actual != expected:
        raise ValueError(
            f"Unexpected hit-test wrapper at 0x{wrapper_va:08X} in {section}: "
            f"{hashlib.sha256(actual).hexdigest()}"
        )
    marker = b"\x83\xC2\x0E"
    marker_offset = expected.find(marker)
    if marker_offset < 0 or expected.find(marker, marker_offset + 1) >= 0:
        raise ValueError("Expected one add edx,0Eh instruction")

    data[wrapper_offset + marker_offset + 2] = args.top_inset
    args.output.write_bytes(data)
    output = PEImage(args.output)
    patched, _, _ = output.read_va(wrapper_va + marker_offset, 3)
    if patched != b"\x83\xC2" + bytes([args.top_inset]):
        raise ValueError("Patched wrapper verification failed")

    print(f"Hit-test wrapper VA: 0x{wrapper_va:08X} ({section})")
    print(f"Top inset: 14 -> {args.top_inset}")
    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
