#!/usr/bin/env python3
"""Set IMAGE_FILE_LARGE_ADDRESS_AWARE on the verified KMRP gold snapshot."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


EXPECTED_INPUT_LENGTH = 4_083_712
EXPECTED_INPUT_SHA256 = "9ACE45023EAB9063803136E6C312E5E87DD85E07E33CCB5525C04DCA38C478DC"
EXPECTED_OUTPUT_SHA256 = "7863BCE3BDDAC279B6A14FEB2412D38572CF94D22D6E0D8EC869D491B7EFCDE8"
CHARACTERISTICS_OFFSET = 0x926
EXPECTED_CHARACTERISTICS = 0x010F
LARGE_ADDRESS_AWARE = 0x0020


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
    characteristics = int.from_bytes(
        data[CHARACTERISTICS_OFFSET : CHARACTERISTICS_OFFSET + 2], "little"
    )
    if characteristics != EXPECTED_CHARACTERISTICS:
        raise SystemExit(
            f"Expected PE characteristics 0x{EXPECTED_CHARACTERISTICS:04X}, "
            f"found 0x{characteristics:04X}"
        )

    before_length = len(data)
    patched = characteristics | LARGE_ADDRESS_AWARE
    data[CHARACTERISTICS_OFFSET : CHARACTERISTICS_OFFSET + 2] = patched.to_bytes(2, "little")
    if len(data) != before_length:
        raise AssertionError("In-place PE-header edit changed the file length")
    if int.from_bytes(data[CHARACTERISTICS_OFFSET : CHARACTERISTICS_OFFSET + 2], "little") != 0x012F:
        raise AssertionError("Large Address Aware bit did not survive read-back")
    output_hash = sha256(data)
    if output_hash != EXPECTED_OUTPUT_SHA256:
        raise SystemExit(f"Unexpected output SHA-256: {output_hash}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    if sha256(args.output.read_bytes()) != output_hash:
        raise SystemExit("Written output failed verification")
    print(f"Wrote {args.output}")
    print(f"PE characteristics: 0x{characteristics:04X} -> 0x{patched:04X}")
    print(f"Length: {len(data)}")
    print(f"SHA-256: {output_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
