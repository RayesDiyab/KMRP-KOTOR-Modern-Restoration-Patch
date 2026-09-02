#!/usr/bin/env python3
"""Pad the area map atlases so the HUD minimap never runs off into black.

**The problem.** The gameplay minimap pins the player marker to the centre of
`LBL_MAPVIEW` and pans the map underneath it -- `x = viewportCentre - player *
factor`, with no clamping anywhere (confirmed in the disassembly at `0x0068ABB0`
and independently in xoreos, which reimplements the same engine). The window
onto the map is therefore always *player +/- 60 map units*. The atlases are
512x256. So whenever the player stands within 60 map units of an area's edge,
the window extends past the atlas and there is nothing left to draw.

Vanilla hides that by declaring `LBL_MAP` at 512x512 over a 512x256 texture: the
engine then emits a second draw one texture-height down, filling the gap with a
copy of the map. That is the vertical duplication bug. KMRP closed it by
declaring 512x256 instead, which trades the duplicate for black.

(Corrected 2026-09-02: this was recorded as a sampler wrap. Measured under
x64dbg it is two separate draw calls -- see `reverse-engineering/map.md`. This
tool is research, not shipped: the atlas route was dropped.)

**The fix.** Neither. Give the atlas a real margin: paint a 632x632 canvas, drop
the original content in at (60, 60), and fill the surround. `LBL_MAP` becomes
632x632, so the source rect matches the texture exactly -- no overrun, no wrap --
and the margin occupies precisely the region that was black. 60 map units is
exactly half the 120-unit window, so the margin covers every edge of every area.

The map content does not move: `build_minimap_zoom_fix.py --padded-atlas`
subtracts the same 60 units before scaling, which works out to exactly half the
viewport width, so the content lands on the identical screen pixels it does
today. That matters because the engine keeps the player arrow pinned to the
viewport centre and never moves it -- the reason clamping the pan (candidate
006) failed.

**Measured facts this relies on**, from `swpc_tex_gui.erf`:

  * 97 `lbl_map*` resources; 92 are area atlases (512 wide), the other 5 are HUD
    icons (`lbl_mapcircle`, `lbl_mapnorth`, `lbl_mapup`, `lbl_mapdown`,
    `lbl_mapnotearr`) and are left alone;
  * 90 are 512x256, plus `lbl_map` (the generic fallback) and `lbl_mapm25ab` at
    512x512;
  * 91 of the 92 are **fully opaque** -- alpha 255 everywhere. An earlier note
    claiming the maps are mostly transparent was measuring `lbl_minimap.tga`,
    the border ring, and was wrong. Because the maps are opaque, a margin cannot
    bleed through them; it is visible only where the map is not;
  * the sole exception, `lbl_mapm25ab`, carries its content in rows 242..511, so
    KMRP's 512x256 extent currently crops it away almost entirely. A 632x632
    canvas restores it.

Content is anchored at (60, 60) for both source sizes, so a 512x512 atlas gets
60 units of margin on every side and a 512x256 atlas gets 60 at the top and left
with the remainder below and right -- more than the window can ever reach.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np

from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc
from pykotor.resource.formats.erf import read_erf


DEFAULT_ERF = Path(r"C:\Star Wars - KotOR\TexturePacks\swpc_tex_gui.erf")

# 512 of content plus 60 of margin on each side. 60 is half the engine's
# 120-unit minimap window, which is the furthest the view can ever reach past
# the content.
CANVAS = 632
MARGIN = 60

# The five lbl_map* resources that are HUD icons rather than area atlases.
ICONS = {"lbl_mapcircle", "lbl_mapnorth", "lbl_mapup", "lbl_mapdown", "lbl_mapnotearr"}

# Dark navy with a faint grid: legible as "off the map" without competing with
# the map itself. Unlike the LBL_MAPBORDER experiment this cannot bleed over the
# map, because the atlases are opaque.
BASE_RGB = (10, 18, 38)
LINE_RGB = (20, 34, 68)
GRID_SPACING = 16


def parse_rgb(text):
    parts = [int(p) for p in text.replace(",", " ").split()]
    if len(parts) != 3 or not all(0 <= p <= 255 for p in parts):
        raise argparse.ArgumentTypeError("expected R,G,B in 0..255, got " + repr(text))
    return tuple(parts)


def make_margin(canvas: int, base, line, spacing: int, style: str) -> np.ndarray:
    """The whole canvas filled with the margin treatment, RGBA."""
    out = np.empty((canvas, canvas, 4), np.uint8)
    out[:, :, :3] = base
    out[:, :, 3] = 255
    if style == "grid" and spacing > 0:
        out[::spacing, :, :3] = line
        out[:, ::spacing, :3] = line
    return out


def pad(content: np.ndarray, canvas: int, margin: int, margin_fill: np.ndarray) -> np.ndarray:
    h, w = content.shape[:2]
    if margin + h > canvas or margin + w > canvas:
        raise ValueError(
            f"{w}x{h} content does not fit at margin {margin} in {canvas}x{canvas}")
    out = margin_fill.copy()
    out[margin:margin + h, margin:margin + w] = content
    return out


def load_atlases(erf_path: Path):
    erf = read_erf(erf_path)
    atlases = []
    for res in erf:
        name = res.resref.get().lower()
        if not name.startswith("lbl_map") or name in ICONS:
            continue
        tpc = read_tpc(res.data)
        width, height = tpc.dimensions()
        if width != 512:
            print(f"  skip {name}: {width}x{height} is not an area atlas")
            continue
        tpc.convert(TPCTextureFormat.RGBA)
        mip = tpc.get()
        pixels = np.frombuffer(mip.data, np.uint8).reshape(mip.height, mip.width, 4).copy()
        atlases.append((name, pixels))
    atlases.sort(key=lambda item: item[0])
    return atlases


def write_tga(path: Path, pixels: np.ndarray) -> None:
    """Uncompressed 32-bit TGA, bottom-up, exactly as the game's own assets are.

    pykotor writes descriptor 0x28 -- top-left origin. Every TGA the game ships,
    and every one KMRP ships, is 0x08: bottom-left, the TGA default. A loader
    that ignores the origin bit reads a 0x28 file upside down, which for a padded
    atlas displaces the content by 256 texels and hides the map completely. So
    emit the convention the rest of the game uses rather than rely on the bit
    being honoured.
    """
    height, width = pixels.shape[:2]
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 0x08)
    bgra = pixels[..., [2, 1, 0, 3]]
    path.write_bytes(header + bgra[::-1].tobytes())


def verify(path: Path, expected: np.ndarray) -> None:
    tpc = read_tpc(path)
    tpc.convert(TPCTextureFormat.RGBA)
    mip = tpc.get()
    got = np.frombuffer(mip.data, np.uint8).reshape(mip.height, mip.width, 4)
    if got.shape != expected.shape or not np.array_equal(got, expected):
        raise SystemExit(f"{path}: round-trip mismatch, refusing to ship it")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path,
                        help="directory to write the padded .tga files into")
    parser.add_argument("--erf", type=Path, default=DEFAULT_ERF)
    parser.add_argument("--canvas", type=int, default=CANVAS)
    parser.add_argument("--margin", type=int, default=MARGIN)
    parser.add_argument("--style", choices=("grid", "flat"), default="grid")
    parser.add_argument("--base", type=parse_rgb, default=BASE_RGB)
    parser.add_argument("--line", type=parse_rgb, default=LINE_RGB)
    parser.add_argument("--spacing", type=int, default=GRID_SPACING)
    parser.add_argument("--only", action="append", default=None,
                        help="build just these resrefs (repeatable), for a cheap first playtest")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()

    if not args.erf.is_file():
        raise SystemExit(f"{args.erf}: not found. Pass --erf with the game's swpc_tex_gui.erf")

    print(f"Reading {args.erf}")
    atlases = load_atlases(args.erf)
    if args.only:
        wanted = {name.lower() for name in args.only}
        atlases = [item for item in atlases if item[0] in wanted]
        missing = wanted - {name for name, _ in atlases}
        if missing:
            raise SystemExit(f"no such area atlas: {sorted(missing)}")
    print(f"{len(atlases)} area atlases\n")

    margin_fill = make_margin(args.canvas, args.base, args.line, args.spacing, args.style)
    args.output.mkdir(parents=True, exist_ok=True)

    total = 0
    sizes = {}
    for name, pixels in atlases:
        padded = pad(pixels, args.canvas, args.margin, margin_fill)
        path = args.output / (name + ".tga")
        write_tga(path, padded)
        if not args.no_verify:
            verify(path, padded)
        total += path.stat().st_size
        key = (pixels.shape[1], pixels.shape[0])
        sizes[key] = sizes.get(key, 0) + 1

    print("source sizes : " + ", ".join(f"{w}x{h} x{n}" for (w, h), n in sorted(sizes.items())))
    print(f"canvas       : {args.canvas}x{args.canvas}, content at ({args.margin}, {args.margin})")
    detail = f", lines {args.line} every {args.spacing}px" if args.style == "grid" else ""
    print(f"margin       : {args.style}, base {args.base}{detail}")
    print(f"written      : {len(atlases)} files, {total / 1048576:.1f} MiB -> {args.output}")
    print()
    print(f"Now set LBL_MAP's extent to {args.canvas}x{args.canvas} and build the exe with")
    print("  build_minimap_zoom_fix.py --padded-atlas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
