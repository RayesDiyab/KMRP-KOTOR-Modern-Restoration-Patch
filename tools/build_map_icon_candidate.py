#!/usr/bin/env python3
"""Build an isolated KOTOR executable with candidate map-icon scaling patches."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path

from verify_map_patch import PEImage


def parse_va(value: str) -> int:
    return int(value, 0)


def expected_bytes(value: str) -> bytes:
    return bytes.fromhex(value)


def patch_va(image: PEImage, data: bytearray, va: int, expected: bytes, replacement: bytes, label: str) -> None:
    if len(expected) != len(replacement):
        raise ValueError(f"Length mismatch for {label}")
    actual, file_offset, section = image.read_va(va, len(expected))
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{va:08X} (file 0x{file_offset:08X}, {section})"
        )
    data[file_offset : file_offset + len(replacement)] = replacement
    print(
        f"{label:<34} VA 0x{va:08X}  file 0x{file_offset:08X}  "
        f"{actual.hex(' ').upper()} -> {replacement.hex(' ').upper()}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    args = parser.parse_args()

    if not 1 <= args.width <= 16384 or not 1 <= args.height <= 16384:
        raise ValueError("Width and height must be between 1 and 16384")
    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    image = PEImage(args.source)
    if image.image_base != parse_va(spec["image_base"]):
        raise ValueError(f"Unexpected image base 0x{image.image_base:08X}")

    data = bytearray(image.data)
    width_bytes = struct.pack("<I", args.width)
    height_bytes = struct.pack("<I", args.height)

    storage = spec["float_storage"]
    storage_va = parse_va(storage["va"])
    patch_va(
        image,
        data,
        storage_va,
        expected_bytes(storage["expected"]),
        struct.pack("<ff", float(args.width), float(args.height)),
        "coordinate float storage",
    )

    width_pointer = struct.pack("<I", storage_va)
    height_pointer = struct.pack("<I", storage_va + 4)
    for record in spec["width_float_references"]:
        patch_va(
            image,
            data,
            parse_va(record["va"]),
            expected_bytes(record["expected"]),
            width_pointer,
            record["purpose"],
        )
    for record in spec["height_float_references"]:
        patch_va(
            image,
            data,
            parse_va(record["va"]),
            expected_bytes(record["expected"]),
            height_pointer,
            record["purpose"],
        )
    for record in spec["width_integer_immediates"]:
        patch_va(
            image,
            data,
            parse_va(record["va"]),
            expected_bytes(record["expected"]),
            width_bytes,
            record["purpose"],
        )
    for record in spec["height_integer_immediates"]:
        patch_va(
            image,
            data,
            parse_va(record["va"]),
            expected_bytes(record["expected"]),
            height_bytes,
            record["purpose"],
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.source, args.output)
    args.output.write_bytes(data)
    output_image = PEImage(args.output)
    print(f"Wrote {args.output}")
    print(f"SHA-256: {output_image.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
