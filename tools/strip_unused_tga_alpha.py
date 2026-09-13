#!/usr/bin/env python3
"""Rewrite 32-bit override TGAs whose alpha is entirely opaque as 24-bit.

Why: the HD menu backgrounds ship as 2867x1434 uncompressed 32bpp TGAs, 15.7 MB
each, and their alpha channel is 255 everywhere -- measured, not assumed. KOTOR
loads them synchronously when a panel opens, which is the stall (and the grey
frame) seen switching to Inventory or Equipment.

Dropping a channel nothing reads is lossless: every RGB byte is preserved
exactly, and the file gets a quarter smaller.

**It is also mostly useless here, and that is the point of the stride guard.**
The HD backgrounds are 2867 wide, an odd number, so their 24-bit rows can never
be 4-byte aligned -- and KOTOR crashes on them. See `stride_would_be_aligned`.
What remains convertible is a single 1 MB file, so the panel-switch stall these
textures cause is NOT solved by this tool and needs a real answer (TPC/DXT, or
smaller source art).

RLE (TGA type 10) would save far more, but not one of the 1136 override textures
uses it, so there is no evidence this engine's loader accepts it and this tool
does not go there.

Files whose alpha is actually used -- every font atlas, for instance -- and files
whose rows would stop being aligned are both skipped, so running this twice is a
no-op.

Usage:
    python tools/strip_unused_tga_alpha.py DIR [DIR ...] [--apply]
                                           [--min-bytes N] [--manifest PATH]

Without --apply it only reports. With --manifest it rewrites the recorded
SHA-256 for every file it changes, so the installer's ownership check still
matches what is on disk.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import struct
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:                                  # pragma: no cover
    print("Pillow is required; run this from Bash, not PowerShell "
          "(see kmrp-powershell-cannot-see-pil).")
    raise

Image.MAX_IMAGE_PIXELS = None

TGA_FOOTER = b"\x00" * 8 + b"TRUEVISION-XFILE." + b"\x00"


def stride_would_be_aligned(path: Path) -> bool:
    """Would the 24-bit rows still start on a 4-byte boundary?

    This is not a nicety. KOTOR crashed on the Load Game screen after this tool
    converted `lbl_saveload.tga`, which is 2867 pixels wide: at 32bpp the rows
    are 11468 bytes and 4-byte aligned, at 24bpp they are 8601 and are not.

    The evidence that this is the rule: of the 198 24-bit TGAs in a converted
    override, the 165 that shipped that way are ALL aligned and not one is not --
    every unaligned file was one this tool had just written. So "24bpp is proven
    supported, 170 override textures already use it" was true and still missed
    the thing that mattered.

    An odd width can never be aligned at 24bpp, so those files stay 32-bit.
    """
    with Image.open(path) as image:
        return (image.size[0] * 3) % 4 == 0


def alpha_is_unused(path: Path) -> bool:
    """True when every pixel is fully opaque, so the channel carries nothing."""
    with Image.open(path) as image:
        if image.mode != "RGBA":
            return False
        low, high = image.getchannel("A").getextrema()
        return low == 255 and high == 255


def to_24bit(path: Path) -> bytes:
    """The same picture, same orientation, without the alpha channel."""
    header = path.read_bytes()[:18]
    descriptor = header[17]
    # Bits 0-3 are the alpha-channel depth; the origin bits (4-5) must survive,
    # or a bottom-left image would be written as though it were top-left and the
    # texture would appear upside down in game.
    descriptor = (descriptor & 0xF0)

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        # These files declare a bottom-left origin, so their rows are stored
        # bottom-up. Pillow hands them back top-down, and writing that straight
        # out under the same descriptor turns every texture upside down -- which
        # is exactly what the first run of this tool did, caught by comparing
        # pixels against the backups rather than trusting the round trip.
        if not (descriptor & 0x20):                  # bit 5 set == top origin
            rgb = rgb.transpose(Image.FLIP_TOP_BOTTOM)
        red, green, blue = rgb.split()
        body = Image.merge("RGB", (blue, green, red)).tobytes()

    out = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
                      width, height, 24, descriptor)
    return out + body + TGA_FOOTER


def load_manifest(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[0], lines[1:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dirs", nargs="+", type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="write the files; otherwise only report")
    parser.add_argument("--min-bytes", type=int, default=4_000_000,
                        help="ignore files smaller than this (default 4 MB)")
    parser.add_argument("--manifest", type=Path,
                        help="installer manifest whose hashes to refresh")
    arguments = parser.parse_args()

    changed: dict[str, str] = {}
    saved = 0
    skipped_alpha = 0
    skipped_stride = 0

    for directory in arguments.dirs:
        if not directory.is_dir():
            print(f"  {directory}: not a directory; skipped")
            continue
        print(f"\n=== {directory}")
        for path in sorted(directory.glob("*.tga")):
            size = path.stat().st_size
            if size < arguments.min_bytes:
                continue
            if path.read_bytes()[16] != 32:
                continue
            try:
                if not stride_would_be_aligned(path):
                    skipped_stride += 1
                    continue
                if not alpha_is_unused(path):
                    skipped_alpha += 1
                    continue
            except Exception as error:               # unreadable / odd TGA
                print(f"  !! {path.name}: {error}")
                continue

            data = to_24bit(path)
            delta = size - len(data)
            saved += delta
            print(f"  {size/1048576:6.1f} MB -> {len(data)/1048576:6.1f} MB  "
                  f"(-{delta/1048576:4.1f})  {path.name}")
            if arguments.apply:
                path.write_bytes(data)
                changed[path.name.lower()] = hashlib.sha256(data).hexdigest().upper()

    print(f"\nskipped (alpha genuinely used): {skipped_alpha}")
    print(f"total saved: {saved/1048576:.0f} MB"
          f"{'' if arguments.apply else '   (dry run; pass --apply)'}")

    if arguments.apply and arguments.manifest and arguments.manifest.is_file():
        header, rows = load_manifest(arguments.manifest)
        out, updated, dropped = [header], 0, 0
        for row in rows:
            parts = row.split("\t")
            if len(parts) < 4:
                out.append(row)
                continue
            try:
                name = base64.b64decode(parts[0]).decode("utf-8", "replace").lower()
            except Exception:
                out.append(row)
                continue
            # An entry whose file no longer exists would make the uninstaller
            # look for something that is not there.
            target = arguments.manifest.parent / "override" / name
            if not target.exists():
                dropped += 1
                continue
            if name in changed:
                parts[3] = changed[name]
                updated += 1
            out.append("\t".join(parts))
        arguments.manifest.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"manifest: {updated} hashes refreshed, {dropped} stale entries removed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
