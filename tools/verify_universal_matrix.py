#!/usr/bin/env python3
"""Verify every generated universal executable against the resolution catalog."""

from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path


FIELDS = {
    0x0000AA65: "width",
    0x001F0C65: "width",
    0x0028C4E3: "width",
    0x0000AA85: "height",
    0x001F0C6F: "height",
    0x002928B3: "center_width",
    0x002928C3: "center_height",
    0x0029505C: "canvas_width",
    0x00295064: "canvas_height",
    0x00295082: "overlay_width",
    0x0029508A: "canvas_height",
}


def read_catalog(path: Path) -> list[dict[str, int | str]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        lines = (line for line in stream if line.strip() and not line.startswith("#"))
        for fields in csv.reader(lines, delimiter="\t"):
            rows.append({
                "category": fields[0],
                "width": int(fields[1]),
                "height": int(fields[2]),
                "canvas_width": int(fields[3]),
                "canvas_height": int(fields[4]),
                "overlay_width": int(fields[5]),
                "center_width": int(fields[6]),
                "center_height": int(fields[7]),
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("matrix_directory", type=Path)
    args = parser.parse_args()

    rows = read_catalog(args.catalog)
    if len(rows) != 48:
        raise ValueError(f"Expected 48 catalog entries, found {len(rows)}")
    for row in rows:
        key = f"{row['width']}x{row['height']}"
        executable = args.matrix_directory / f"swkotor-{key}.exe"
        data = executable.read_bytes()
        if len(data) != 4_046_848:
            raise ValueError(f"{key}: unexpected executable length {len(data)}")
        for offset, field in FIELDS.items():
            actual = struct.unpack_from("<I", data, offset)[0]
            expected = row[field]
            if actual != expected:
                raise ValueError(f"{key}: {field} at 0x{offset:X} is {actual}, expected {expected}")
    print(f"Verified {len(rows)} resolution executables and {len(FIELDS)} fields per executable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
