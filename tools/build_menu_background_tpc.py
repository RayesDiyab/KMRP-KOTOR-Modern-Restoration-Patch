#!/usr/bin/env python3
"""Rebuild the oversized menu backgrounds as power-of-two DXT TPC.

The problem, measured rather than assumed:

  * Stock KOTOR ships `lbl_invent` as a 512x512 DXT5 TPC of 256 KB, with a
    trailing TXI of `mipmap 0`. All 1570 textures in `swpc_tex_gui.erf` are TPC,
    and every common dimension in it is a power of two.
  * KMRP replaced it with a 2867x1434 uncompressed 32-bit TGA of 15.7 MB -- 61x
    the stock asset, non-power-of-two, and needing a full decode plus a
    per-pixel conversion before any of it reaches the GPU.
  * The file read is not the cost. On an NVMe the 15.7 MB arrives in about 5 ms.
    Decoding it takes ~22 ms, and rounding a non-power-of-two texture up to
    4096x2048 costs ~107 ms more.

DXT blocks need no decode at all -- they go to the GPU compressed -- and a
power-of-two texture needs no rescale. 4096x2048 DXT5 is 8 MB against 15.7, and
is *sharper* than the source on a 3440-wide screen.

Every output matches the stock structure: single mipmap level, `mipmap 0` in the
TXI, `alphaBlending` 1.0.

Usage:
    python tools/build_menu_background_tpc.py SRC_DIR [--out DIR] [--apply]
                                              [--size 4096x2048] [--format dxt5]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import io
import struct
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:                                      # pragma: no cover
    print("Pillow is required; run this from Bash, not the PowerShell tool "
          "(see kmrp-powershell-cannot-see-pil).")
    raise

Image.MAX_IMAGE_PIXELS = None

# TPC encoding values, read off the stock files: 2 is DXT1 (half a byte per
# pixel), 4 is DXT5 (one byte). `dataSize` of zero would mean uncompressed.
ENCODING = {"dxt1": 2, "dxt5": 4}
# Stock GUI textures carry this and it matters: without it the engine mips a
# texture that is only ever drawn at 1:1, for no benefit and 33% more bytes.
TXI = b"mipmap 0\n"


def compress(image: Image.Image, fmt: str) -> bytes:
    """DXT payload only -- Pillow writes a DDS, whose header is 128 bytes.

    Flipped first: TPC rows run bottom-up and Pillow returns them top-down. The
    backgrounds hid this because the panel frame is close to vertically
    symmetric; the item icons did not.
    """
    buffer = io.BytesIO()
    (image.convert("RGBA")
          .transpose(Image.FLIP_TOP_BOTTOM)
          .save(buffer, format="DDS", pixel_format=fmt.upper()))
    return buffer.getvalue()[128:]


def build(image: Image.Image, fmt: str) -> bytes:
    payload = compress(image, fmt)
    width, height = image.size
    header = struct.pack("<IfHHBB", len(payload), 1.0, width, height,
                         ENCODING[fmt], 1)
    return header + b"\x00" * (128 - len(header)) + payload + TXI


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("src", type=Path, help="directory holding the TGAs")
    parser.add_argument("--out", type=Path, help="where to write (default: beside src)")
    parser.add_argument("--size", default="4096x2048")
    parser.add_argument("--format", default="dxt5", choices=sorted(ENCODING))
    parser.add_argument("--min-bytes", type=int, default=4_000_000)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()

    width, height = (int(v) for v in arguments.size.split("x"))
    # DXT is the only hard constraint: it encodes 4x4 blocks.
    if width % 4 or height % 4:
        print(f"{width}x{height} is not a multiple of 4, which DXT requires")
        return 1
    # Power-of-two is conventional here -- every stock GUI texture is one -- but
    # not required: the art being replaced is 2867x1434 and has always worked.
    # Storing at exactly the display size beats a larger power-of-two, because
    # no resampling happens at all: measured 38.3 dB at 2.36 MB for 3440x1440
    # against 36.2 dB at 4.00 MB for 4096x2048.
    if (width & (width - 1)) or (height & (height - 1)):
        print(f"note: {width}x{height} is not a power of two (fine, but "
              f"unlike the stock assets)")

    out = arguments.out or arguments.src
    if arguments.apply:
        out.mkdir(parents=True, exist_ok=True)

    total_before = total_after = 0
    count = 0
    for path in sorted(arguments.src.glob("*.tga")):
        size = path.stat().st_size
        if size < arguments.min_bytes:
            continue
        with Image.open(path) as source:
            resized = source.convert("RGBA").resize((width, height), Image.LANCZOS)
        blob = build(resized, arguments.format)
        total_before += size
        total_after += len(blob)
        count += 1
        print(f"  {size/1048576:6.1f} MB -> {len(blob)/1048576:5.2f} MB  "
              f"{path.stem}.tpc")
        if arguments.apply:
            (out / f"{path.stem}.tpc").write_bytes(blob)

    if not count:
        print("nothing over the size threshold")
        return 0
    print(f"\n{count} textures: {total_before/1048576:.0f} MB -> "
          f"{total_after/1048576:.0f} MB "
          f"({total_before/total_after:.1f}x smaller)"
          f"{'' if arguments.apply else '   (dry run; pass --apply)'}")
    print("NOTE: the .tga files stay in place; TPC takes priority in override.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
