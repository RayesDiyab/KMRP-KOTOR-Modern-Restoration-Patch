#!/usr/bin/env python3
"""The unmodified executable's bytes the KPM edition needs, and nothing more.

The KMRP for KPM installer builds kmrp-kpm.dat from the unmodified executable and
the gold delta (src/patcher/KpmEdition.cs). It cannot read that executable from
Steam's swkotor.exe: its code is encrypted on disk and decrypted only when the game
runs, into bytes identical to CD 1.03's (measured 2026-09-28). So both editions
carry the CD 1.03 bytes the data file is built from, as every KOTOR Patch Manager
patch carries the original bytes of the sites it hooks:

  * the PE header, file offsets 0x000-0xFFF, for the section table the data file
    is laid out by;
  * the bytes under every gold-delta chunk in the original sections -- exactly the
    bytes KMRP changes, per tools/generate_gold_delta.py's changed ranges;
  * every inbound relocation field (tools/kpm_relocations.py), whole, since the
    data file carries those four bytes even where some are unchanged;
  * every field ResolutionPatch reads or writes, whole, from the installer's own
    list (`--kpm-sites`, KpmEditionOperations.WriteResolutionSites): it checks
    gold's value across the whole field before writing, and gold changed only some
    bytes of some fields and none of a few. The first version of this tool missed
    them, and the installer refused its own picture ("The stack-count label patch
    did not match the verified gold build") -- loudly, as it should.

Everything else in the installer's picture of the executable is zero, and cannot
matter: the data file records only where the final image differs from the
unmodified executable, and that is only under the chunks and the resolution
fields. The check below proves the coverage before the build embeds the result,
and Test-KpmEdition.ps1 proves the data file the installer builds from it is the
standalone's executable, byte for byte, at every resolution it installs.

Output, little-endian: "KMRPORG1", the unmodified executable's SHA-256 (32 bytes),
u32 range count, per range u32 file offset, u32 length, the bytes; u32 FNV-1a of
everything before it.

Usage:
    python tools/kpm_originals.py --clean CLEAN_EXE --delta GOLD_KUP \\
        --relocations KPM_RELOCATIONS --sites RESOLUTION_SITES --out OUT

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

HEADER = 0x1000
IMAGE_BASE = 0x400000


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def read_delta(path: Path):
    """[(file offset, bytes)] from a KUIPATCH1 gold delta, and its source length."""
    data = path.read_bytes()
    if data[:9] != b"KUIPATCH1":
        raise SystemExit(f"{path}: not a gold delta")
    p = 9 + 32 + 32
    source_length, target_length, count = struct.unpack_from("<QQI", data, p)
    p += 20
    chunks = []
    for _ in range(count):
        offset, length = struct.unpack_from("<QI", data, p)
        p += 12
        chunks.append((offset, data[p:p + length]))
        p += length
    if p != len(data):
        raise SystemExit(f"{path}: trailing bytes")
    return chunks, source_length, data[9:41]


def inbound_fields(path: Path):
    """File offsets of the relocation table's IN fields (FILE = VA - 0x400000 in the
    original sections)."""
    out = []
    for line in path.read_text(encoding="ascii").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "IN":
            out.append(int(parts[1], 16) - IMAGE_BASE)
    return out


def resolution_sites(path: Path):
    """[(file offset, size)] from the installer's --kpm-sites list."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and not line.startswith("#"):
            out.append((int(parts[0], 16), int(parts[1])))
    if not out:
        raise SystemExit(f"{path}: no resolution sites")
    return out


def merge(ranges):
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def build(clean: bytes, delta: Path, relocations: Path, sites: Path):
    chunks, source_length, source_hash = read_delta(delta)
    if hashlib.sha256(clean).digest() != source_hash or len(clean) != source_length:
        raise SystemExit("the gold delta was not made from this unmodified executable")
    ranges = [(0, HEADER)]
    for offset, data in chunks:
        start, end = max(offset, HEADER), min(offset + len(data), source_length)
        if start < end:
            ranges.append((start, end))
    for field in inbound_fields(relocations):
        ranges.append((field, field + 4))
    fields = [(o, o + n) for o, n in resolution_sites(sites) if o < source_length]
    ranges += fields
    ranges = merge(ranges)

    # The proof: the installer's picture of the executable -- zeros, these bytes --
    # with gold's chunks laid over it differs from itself exactly where gold differs
    # from the real unmodified executable, and holds the real bytes wherever it
    # differs.
    picture = bytearray(source_length)
    for start, end in ranges:
        picture[start:end] = clean[start:end]
    covered = bytearray(source_length)
    for start, end in ranges:
        covered[start:end] = b"\x01" * (end - start)
    for offset, data in chunks:
        for i in range(len(data)):
            at = offset + i
            if at >= source_length:
                break
            if not covered[at]:
                raise SystemExit(f"FILE {at:#x} is changed by gold but not carried")
            if picture[at] != clean[at]:
                raise SystemExit(f"FILE {at:#x} is carried wrongly")
    for start, end in fields:
        if picture[start:end] != clean[start:end] or not all(covered[start:end]):
            raise SystemExit(f"resolution field FILE {start:#x}+{end - start} is not carried whole")
    return ranges, source_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--delta", type=Path, required=True)
    parser.add_argument("--relocations", type=Path, required=True)
    parser.add_argument("--sites", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    clean = arguments.clean.read_bytes()
    ranges, source_hash = build(clean, arguments.delta, arguments.relocations, arguments.sites)
    body = bytearray(b"KMRPORG1")
    body += source_hash
    body += struct.pack("<I", len(ranges))
    for start, end in ranges:
        body += struct.pack("<II", start, end - start)
        body += clean[start:end]
    body += struct.pack("<I", fnv1a(bytes(body)))
    arguments.out.write_bytes(bytes(body))
    carried = sum(end - start for start, end in ranges)
    print(f"{len(ranges)} ranges, {carried:,} bytes of the unmodified executable "
          f"({carried - HEADER:,} past the header); proved against the gold delta and "
          f"ResolutionPatch's fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
