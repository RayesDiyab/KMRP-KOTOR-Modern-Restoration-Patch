#!/usr/bin/env python3
"""Bake one font atlas set per resolution scale, so text is never resampled.

The shipped atlases are baked once at `HD_FONT_BAKE_SCALE` (3.0) and every
resolution reuses them, with `texturewidth` in the per-resolution TXI rescaled
by `scale / 3.0`. `texturewidth * 100` is what turns normalised coordinates into
texels, so it equals the atlas's real width at 3840x2160 and nowhere else:

    1920x1080  scale 1.5  declares 512 px of a 1024 px atlas  -> 2:1 minified
    2560x1440  scale 2.0  declares 683 px of a 1024 px atlas  -> 1.5:1 minified
    3840x2160  scale 3.0  declares 1024 px of a 1024 px atlas -> 1:1, correct
    7680x4320  scale 6.0  declares 2048 px of a 1024 px atlas -> 2:1 magnified

Every font TXI also carries `mipmap 0` and `filter 0`, so that resampling is
point sampled -- texels are dropped rather than blended, which throws away the
antialiasing the atlas has. Non-integer ratios like 1440p's 1.5:1 drop them
unevenly, which is what makes strokes look ragged. That is the aliasing reported
at 1080p and 1440p in issue #16.

Baking each scale separately makes `texturewidth` the atlas's true width at
every resolution, so one texel lands on one pixel everywhere and nothing is
resampled at all. The typeface does not change: these are the same faces the
shipped atlases already use.

Measured cost, stored (deflate), 17 Old Republic resrefs:

    scale 1.0   166 KB      scale 2.0   381 KB      scale 3.0   729 KB

Stored size grows roughly with scale^1.3 rather than with area, because the art
is thin strokes on mostly empty textures. All 24 distinct scales come to roughly
17 MB rather than the 108 MB an area-based estimate predicts.

Output is a cache keyed by scale, and existing sets are left alone, so a rebuild
only pays for what is missing. Needs Pillow, like the bakers it calls.

Usage:
    python tools/build_font_scale_sets.py ERF OUTPUT_DIR [--scales 1.5 2.0]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import prepare_universal_resources as pur


# The 17 resrefs rendered from Old Republic, and the one rendered from Arimo.
# Split because the two faces need different point sizes to land on the same
# glyph height -- see docs/font-scaling.md for the invocations these mirror.
OLD_REPUBLIC_RESREFS = (
    "dialogfont10x10", "dialogfont10x10a", "dialogfont10x10b",
    "dialogfont12x16", "dialogfont16x16", "dialogfont16x16a",
    "dialogfont16x16b", "dialogfont32x32",
    "fnt_console", "fnt_credits", "fnt_creditsa", "fnt_creditsb",
    "fnt_d10x10b", "fnt_d16x16", "fnt_d16x16a", "fnt_dialog16x16",
    "fnt_galahad14",
)
ARIMO_RESREFS = ("fnt_d16x16b",)

# Arimo's glyphs sit differently in the em, so it was baked at 2.526316 where
# Old Republic was baked at 3.0. Keeping that ratio keeps the two faces the same
# size on screen at every scale.
ARIMO_BAKE_RATIO = 2.526316 / 3.0


def distinct_scales() -> list[float]:
    """Every font scale the shipped resolutions ask for, low to high."""
    scales = set()
    for resolutions in pur.GROUPS.values():
        for resolution in resolutions:
            height = int(resolution.split("x")[1])
            scales.add(round(pur.font_scale_for(height), 6))
    return sorted(scales)


def scale_dir(root: Path, scale: float) -> Path:
    return root / f"{scale:.6f}"


def bake(ttf: Path, erf: Path, out: Path, scale: float, resrefs) -> None:
    command = [sys.executable, str(ROOT / "build_font_from_ttf.py"),
               str(ttf), str(erf), str(out), "--scale", f"{scale:.6f}",
               "--fonts", *resrefs]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("erf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fonts-dir", type=Path,
                        default=ROOT.parent / "assets" / "fonts")
    parser.add_argument("--scales", type=float, nargs="*",
                        help="only these scales (default: every one in use)")
    parser.add_argument("--force", action="store_true",
                        help="re-bake sets that already exist")
    arguments = parser.parse_args()

    scales = arguments.scales or distinct_scales()
    old_republic = arguments.fonts_dir / "OldRepublic.ttf"
    arimo = arguments.fonts_dir / "Arimo-Medium.ttf"
    for path in (old_republic, arimo):
        if not path.is_file():
            raise SystemExit(f"missing typeface: {path}")

    print(f"{len(scales)} scales: "
          + ", ".join(f"{s:g}" for s in scales))
    for index, scale in enumerate(scales, 1):
        out = scale_dir(arguments.output, scale)
        done = out / "dialogfont16x16.tga"
        if done.is_file() and not arguments.force:
            print(f"[{index}/{len(scales)}] {scale:<9.6f} cached")
            continue
        out.mkdir(parents=True, exist_ok=True)
        bake(old_republic, arguments.erf, out, scale, OLD_REPUBLIC_RESREFS)
        bake(arimo, arguments.erf, out, scale * ARIMO_BAKE_RATIO, ARIMO_RESREFS)
        stored = sum(p.stat().st_size for p in out.glob("*.tga"))
        print(f"[{index}/{len(scales)}] {scale:<9.6f} baked "
              f"{len(list(out.glob('*.tga')))} atlases, {stored/1024/1024:.1f} MB raw")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
