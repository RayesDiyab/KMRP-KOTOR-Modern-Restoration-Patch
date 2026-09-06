#!/usr/bin/env python3
"""Bake KMRP's 3440x1440 reference into both movie display-mode pairs."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


EXPECTED_INPUT_LENGTH = 4_083_712
EXPECTED_INPUT_SHA256 = "7863BCE3BDDAC279B6A14FEB2412D38572CF94D22D6E0D8EC869D491B7EFCDE8"
EXPECTED_OUTPUT_SHA256 = "29BE3C23F53D53F521D98329F996248864834FB3873819DF63CCF1803C65A7E8"
GOLD_WIDTH = 3440
GOLD_HEIGHT = 1440
SITES = (
    (0x00003D6C, 640, GOLD_WIDTH, "entry comparison width"),
    (0x00003D78, 480, GOLD_HEIGHT, "entry comparison height"),
    (0x001F5B3B, 640, GOLD_WIDTH, "temporary mode width"),
    (0x001F5B43, 480, GOLD_HEIGHT, "temporary mode height"),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    data = bytearray(args.source.read_bytes())
    if len(data) != EXPECTED_INPUT_LENGTH or sha256(data) != EXPECTED_INPUT_SHA256:
        raise SystemExit("Refusing an unexpected gold snapshot")

    before_length = len(data)
    for offset, expected, replacement, label in SITES:
        actual = int.from_bytes(data[offset : offset + 4], "little")
        if actual != expected:
            raise SystemExit(
                f"{label} at FILE 0x{offset:X}: expected {expected}, found {actual}"
            )
        data[offset : offset + 4] = replacement.to_bytes(4, "little")
    if len(data) != before_length:
        raise AssertionError("In-place movie-mode edits changed the file length")
    for offset, _expected, replacement, label in SITES:
        actual = int.from_bytes(data[offset : offset + 4], "little")
        if actual != replacement:
            raise AssertionError(f"{label} failed read-back")

    output_hash = sha256(data)
    if output_hash != EXPECTED_OUTPUT_SHA256:
        raise SystemExit(f"Unexpected output SHA-256: {output_hash}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    if sha256(args.output.read_bytes()) != output_hash:
        raise SystemExit("Written output failed verification")

    print(f"Wrote {args.output}")
    print(f"Movie display mode: 640x480 -> {GOLD_WIDTH}x{GOLD_HEIGHT} at two pairs")
    print(f"Length: {len(data)}")
    print(f"SHA-256: {output_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
