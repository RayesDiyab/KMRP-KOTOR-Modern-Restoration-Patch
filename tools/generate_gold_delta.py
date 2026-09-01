#!/usr/bin/env python3
"""Generate the compact, deterministic source-to-gold patch resource.

The output contains only replacement byte ranges. It never embeds either full
game executable.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


MAGIC = b"KUIPATCH1"
EXPECTED_SOURCE_SHA256 = "761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886"
EXPECTED_GOLD_SHA256 = "A764D82BE5E99CF0CEFE9828E25E24230006E89D34EA0208B6E6CAC73DB0269C"


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def changed_ranges(source: bytes, target: bytes) -> list[tuple[int, bytes]]:
    ranges: list[tuple[int, bytes]] = []
    start: int | None = None

    for offset in range(min(len(source), len(target))):
        differs = source[offset] != target[offset]
        if differs and start is None:
            start = offset
        elif not differs and start is not None:
            ranges.append((start, target[start:offset]))
            start = None

    common_length = min(len(source), len(target))
    if start is not None:
        ranges.append((start, target[start:common_length]))

    if len(target) > common_length:
        ranges.append((common_length, target[common_length:]))

    return ranges


def encode_patch(source: bytes, target: bytes) -> bytes:
    if len(target) < len(source):
        raise ValueError("This patch format does not support shrinking a file")

    ranges = changed_ranges(source, target)
    payload = bytearray(MAGIC)
    payload.extend(sha256(source))
    payload.extend(sha256(target))
    payload.extend(struct.pack("<QQI", len(source), len(target), len(ranges)))

    for offset, replacement in ranges:
        payload.extend(struct.pack("<QI", offset, len(replacement)))
        payload.extend(replacement)

    return bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("gold", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    gold = args.gold.read_bytes()
    source_hash = hashlib.sha256(source).hexdigest().upper()
    gold_hash = hashlib.sha256(gold).hexdigest().upper()
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise SystemExit(f"Unsupported source SHA-256: {source_hash}")
    if gold_hash != EXPECTED_GOLD_SHA256:
        raise SystemExit(f"Gold snapshot changed unexpectedly: {gold_hash}")
    patch = encode_patch(source, gold)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)

    ranges = changed_ranges(source, gold)
    replaced_bytes = sum(len(data) for _, data in ranges)
    print(f"Source SHA-256: {source_hash}")
    print(f"Gold SHA-256:   {gold_hash}")
    print(f"Patch chunks:   {len(ranges)}")
    print(f"Payload bytes:  {replaced_bytes}")
    print(f"Patch size:     {len(patch)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
