#!/usr/bin/env python3
"""Every packaged font atlas is drawn at one texel per pixel.

`texturewidth * 100` in a font's TXI is what turns its normalised glyph
coordinates into texels. When it equals the atlas's real pixel width the engine
draws one texel per pixel; when it does not, the same texels are stretched or
squeezed to a different size.

That is not cosmetic here, because every font TXI also carries `mipmap 0` and
`filter 0`, so the resampling is point sampled -- texels are dropped rather than
blended, which throws away the antialiasing the atlas has. A single atlas baked
at scale 3.0 and reused everywhere was correct only at 3840x2160; 1080p declared
512 px of a 1024 px atlas and 1440p declared 683, and the ragged text that
produced was reported from both (issue #16).

So this asserts the invariant directly, per resolution and per font, rather than
trusting the build to have picked the right set.

Usage:
    python testing/regression/Test-FontAtlasScale.py [--resources DIR]
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Resolutions whose scale has no baked set fall back to the shared atlas and
# cannot satisfy the invariant. Each one listed here is a deliberate exception
# with a reason, not a tolerated failure.
KNOWN_FALLBACKS = {
    # 15360x8640 asks for scale 12.0. dialogfont32x32 at that scale needs an
    # atlas past any sane texture size and the bake does not complete, so this
    # one resolution keeps the shared 3.0 atlas and the resampling with it.
    "15360x8640": "scale 12.0 atlas is larger than the baker can produce",
}


def atlas_width(data: bytes) -> int:
    return struct.unpack_from("<HH", data, 12)[0]


def texture_width(txi: str) -> float | None:
    match = re.search(r"^texturewidth (\S+)$", txi, re.M)
    return float(match.group(1)) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--resources", type=Path,
                        default=ROOT / "build" / "kmrp" / "resources")
    arguments = parser.parse_args()

    archives = sorted(arguments.resources.glob("gui-*.zip"))
    if not archives:
        raise SystemExit(f"no resolution archives in {arguments.resources}")

    common_path = arguments.resources / "override-common.zip"
    shared: dict[str, int] = {}
    if common_path.is_file():
        with zipfile.ZipFile(common_path) as common:
            for name in common.namelist():
                if name.lower().endswith(".tga"):
                    shared[Path(name).stem.lower()] = atlas_width(common.read(name))

    problems: list[str] = []
    matched = fell_back = 0
    for archive_path in archives:
        resolution = archive_path.stem.replace("gui-", "")
        with zipfile.ZipFile(archive_path) as archive:
            names = {n.lower(): n for n in archive.namelist()}
            local = {Path(n).stem.lower(): n for n in archive.namelist()
                     if n.lower().endswith(".tga")}
            for lower, real in sorted(names.items()):
                if not lower.endswith(".txi"):
                    continue
                stem = Path(lower).stem
                declared = texture_width(archive.read(real).decode("ascii", "replace"))
                if declared is None:
                    continue
                if stem in local:
                    width = atlas_width(archive.read(local[stem]))
                    where = "in this archive"
                elif stem in shared:
                    width = shared[stem]
                    where = "shared"
                else:
                    continue            # stock font, no atlas of ours
                if round(declared * 100) == width:
                    matched += 1
                elif resolution in KNOWN_FALLBACKS:
                    fell_back += 1
                else:
                    problems.append(
                        f"{resolution} {stem}: declares {declared * 100:.0f}px "
                        f"but the atlas {where} is {width}px "
                        f"({width / (declared * 100):.2f}x resampled)")

    if problems:
        print(f"FAIL: {len(problems)} font(s) are resampled rather than drawn 1:1")
        for line in problems[:20]:
            print(f"   {line}")
        if len(problems) > 20:
            print(f"   ... and {len(problems) - 20} more")
        return 1

    print(f"PASS: {matched} packaged fonts across {len(archives)} resolutions draw "
          f"one texel per pixel")
    if fell_back:
        for resolution, why in KNOWN_FALLBACKS.items():
            print(f"   known fallback: {resolution} -- {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
