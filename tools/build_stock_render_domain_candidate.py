#!/usr/bin/env python3
"""Restore stock shared map domains while retaining marker wrappers.

This diagnostic candidate starts from the verified marker-coordinate/hit-test
build and removes every shared map-size edit.  The widescreen map GUI remains
installed, so this isolates whether the EXE size constants are responsible for
the HUD minimap's vertical texture wrap.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from verify_map_patch import PEImage


SOURCE_SHA256 = "3C73627AEEE967BD780AFEA108A6AB2EC4EA6EAF345E15727E081F945506DBD2"


def va_to_offset(image: PEImage, va: int) -> int:
    _, offset, _ = image.read_va(va, 1)
    return offset


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

    for va, value in (
        (0x006928B3, 640),
        (0x006928C3, 480),
        (0x0069505C, 512),
        (0x00695064, 256),
        (0x00695082, 440),
        (0x0069508A, 256),
    ):
        struct.pack_into("<I", data, va_to_offset(image, va), value)

    args.output.write_bytes(data)
    output = PEImage(args.output)
    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
