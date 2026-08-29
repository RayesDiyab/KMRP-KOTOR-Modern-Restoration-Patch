#!/usr/bin/env python3
"""Verify known KOTOR map patch bytes without modifying an executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_offset: int
    raw_size: int


class PEImage:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ValueError(f"{path} is not an MZ executable")

        pe_offset = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise ValueError(f"{path} has no PE signature")

        coff_offset = pe_offset + 4
        section_count = struct.unpack_from("<H", self.data, coff_offset + 2)[0]
        optional_size = struct.unpack_from("<H", self.data, coff_offset + 16)[0]
        optional_offset = coff_offset + 20
        magic = struct.unpack_from("<H", self.data, optional_offset)[0]
        if magic != 0x10B:
            raise ValueError(f"{path} is not a 32-bit PE image")

        self.image_base = struct.unpack_from("<I", self.data, optional_offset + 28)[0]
        self.size_of_headers = struct.unpack_from("<I", self.data, optional_offset + 60)[0]
        section_offset = optional_offset + optional_size
        sections: list[Section] = []
        for index in range(section_count):
            offset = section_offset + index * 40
            raw_name = self.data[offset : offset + 8].split(b"\0", 1)[0]
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
                "<IIII", self.data, offset + 8
            )
            sections.append(
                Section(
                    name=raw_name.decode("ascii", errors="replace"),
                    virtual_address=virtual_address,
                    virtual_size=virtual_size,
                    raw_offset=raw_offset,
                    raw_size=raw_size,
                )
            )
        self.sections = sections

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest().upper()

    def va_to_file_offset(self, va: int) -> tuple[int, str]:
        rva = va - self.image_base
        if rva < 0:
            raise ValueError(f"VA 0x{va:08X} is below the PE image base")
        if rva < self.size_of_headers:
            return rva, "headers"
        for section in self.sections:
            extent = max(section.virtual_size, section.raw_size)
            if section.virtual_address <= rva < section.virtual_address + extent:
                delta = rva - section.virtual_address
                if delta >= section.raw_size:
                    raise ValueError(
                        f"VA 0x{va:08X} lies in the zero-filled tail of {section.name}"
                    )
                return section.raw_offset + delta, section.name
        raise ValueError(f"VA 0x{va:08X} is not mapped by a PE section")

    def read_va(self, va: int, size: int) -> tuple[bytes, int, str]:
        offset, section = self.va_to_file_offset(va)
        end = offset + size
        if end > len(self.data):
            raise ValueError(f"Read at VA 0x{va:08X} exceeds the file")
        return self.data[offset:end], offset, section


def parse_hex_bytes(value: str) -> bytes:
    return bytes.fromhex(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path, help="Known map patch JSON")
    parser.add_argument("executables", nargs="+", type=Path)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    expected_base = int(spec["image_base"], 0)
    failures = 0

    for executable in args.executables:
        image = PEImage(executable)
        print(f"\n{executable}")
        print(f"  SHA-256:   {image.sha256}")
        print(f"  ImageBase: 0x{image.image_base:08X}")
        if image.image_base != expected_base:
            print(f"  ERROR: expected image base 0x{expected_base:08X}")
            failures += 1

        for patch in spec["verified_patches"]:
            va = int(patch["va"], 0)
            original = parse_hex_bytes(patch["original"])
            patched = parse_hex_bytes(patch["patched"])
            if len(original) != len(patched):
                raise ValueError(f"Length mismatch in patch {patch['name']}")
            actual, file_offset, section = image.read_va(va, len(original))
            if actual == original:
                status = "ORIGINAL"
            elif actual == patched:
                status = "PATCHED"
            else:
                status = "UNEXPECTED"
                failures += 1
            print(
                f"  {patch['name']:<22} VA {patch['va']}  "
                f"file 0x{file_offset:08X}  {section:<8}  "
                f"{actual.hex(' ').upper():<11}  {status}"
            )

        print("  Investigation probes:")
        for probe in spec.get("investigation_probes", []):
            va = int(probe["va"], 0)
            actual, file_offset, section = image.read_va(va, 8)
            print(
                f"    {probe['name']:<30} VA {probe['va']}  "
                f"file 0x{file_offset:08X}  {section:<8}  "
                f"{actual.hex(' ').upper()}"
            )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
