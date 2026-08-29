#!/usr/bin/env python3
"""Fix the HUD minimap's image-draw zoom to use live resolution instead of a
fixed per-"known"-resolution reference table.

The vanilla map/minimap image-draw normalization step (0x00459920) converts an
incoming pixel rect into normalized (0..1) UV coordinates by dividing by a
reference width/height looked up from a small hardcoded table (10-byte stride
entries at 0x007B946C, indexed via a global at 0x007B9460). That table only
has entries for a handful of "known" resolutions (matching
IsKnownResolution's list: 1920x1080, 1024x768, 1280x960, 1280x1024,
1600x1200). At any other resolution (e.g. 3440x1440), the lookup index falls
outside the table's intended entries, producing a wrong reference size and
therefore a wrong zoom — the map image renders zoomed out/tiny relative to
the (correctly, separately, resized) minimap viewport container.

Fix: replace the two table-lookup instructions with direct reads of the live
current-resolution globals (0x0078D1D4 = width, 0x0078D1D8 = height — the
same globals ResolutionPatch keeps correct via swkotor.ini, independently
confirmed via three unrelated code paths this session: the ini-reader
storing them, a KPM tooltip-crash fix reading them, and the WndProc mouse-Y
flip reading the height one). This works for any resolution automatically,
matching how the rest of this patcher generalizes rather than relying on a
fixed table.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from verify_map_patch import PEImage


TABLE_LOOKUP_VA = 0x00459936
TABLE_LOOKUP_ORIGINAL = bytes.fromhex("0F BF 90 6E 94 7B 00 0F BF 80 6C 94 7B 00")
LIVE_HEIGHT_READ = bytes.fromhex("8B 15 D8 D1 78 00")  # mov edx, [0x0078D1D8]
LIVE_WIDTH_READ = bytes.fromhex("A1 D4 D1 78 00")  # mov eax, [0x0078D1D4]
REPLACEMENT = LIVE_HEIGHT_READ + LIVE_WIDTH_READ + b"\x90" * (
    len(TABLE_LOOKUP_ORIGINAL) - len(LIVE_HEIGHT_READ) - len(LIVE_WIDTH_READ)
)


def require_exact(image: PEImage, va: int, expected: bytes, label: str) -> None:
    actual, offset, section = image.read_va(va, len(expected))
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{va:08X} (file 0x{offset:08X}, {section})"
        )
    print(f"{label:<40} VA 0x{va:08X}  file 0x{offset:08X}  verified {actual.hex(' ').upper()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")
    if len(REPLACEMENT) != len(TABLE_LOOKUP_ORIGINAL):
        raise ValueError("Replacement length mismatch")

    image = PEImage(args.source)
    data = bytearray(image.data)

    require_exact(image, TABLE_LOOKUP_VA, TABLE_LOOKUP_ORIGINAL, "minimap zoom table lookup")

    offset, _ = image.va_to_file_offset(TABLE_LOOKUP_VA)
    data[offset : offset + len(TABLE_LOOKUP_ORIGINAL)] = REPLACEMENT
    print(
        f"minimap zoom -> live width/height           VA 0x{TABLE_LOOKUP_VA:08X}  "
        f"{TABLE_LOOKUP_ORIGINAL.hex(' ').upper()} -> {REPLACEMENT.hex(' ').upper()}"
    )

    args.output.write_bytes(data)
    output = PEImage(args.output)
    reread, _, _ = output.read_va(TABLE_LOOKUP_VA, len(REPLACEMENT))
    if reread != REPLACEMENT:
        raise ValueError("Verification failed after write")

    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
