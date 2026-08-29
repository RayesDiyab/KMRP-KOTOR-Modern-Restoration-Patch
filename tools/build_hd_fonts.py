#!/usr/bin/env python3
"""Render higher-resolution versions of KOTOR's font atlases.

The stock atlases are tiny -- `dialogfont16x16` and `fnt_galahad14` are 256x256
with a 32x32 glyph grid (8px cells), `fnt_d16x16` is 512x512 (16px cells) -- so
once the TXI metrics scale text up (tools/build_scaled_fonts.py) the glyphs are
magnified well past their native detail and look soft and jagged.

Two properties of the source art decide how they must be upscaled:

  * The glyph shape lives entirely in the ALPHA channel, at a genuine 256
    levels (the art is already antialiased, not a 1-bit mask).
  * RGB is white wherever the glyph is drawn, but holds junk in the fully
    transparent areas -- `dialogfont16x16` has bright green (0,255,0) sitting
    in its empty space. Upscaling RGB would bleed that green into every glyph
    edge, so RGB is discarded and rewritten as flat white.

So only alpha is resampled. Lanczos recovers smooth curves from the staircased
original, but leaves edges spread over roughly `factor` pixels; a smoothstep
remap centred on 50% then pulls them back to a ~1px transition. Centring the
curve on 50% keeps the half-coverage contour where it was, so glyph weight and
shape are preserved rather than fattened or thinned.

The atlas is scaled uniformly, so the normalised glyph UVs in the TXI stay
exactly valid -- no coordinate rework, and no executable change.

Output goes to a directory of `.tga` files intended to be committed as assets
and shipped by prepare_universal_resources.py, which pairs them with the
per-resolution TXI metrics. This tool needs Pillow, which is why it is kept out
of the build pipeline itself (the pipeline's interpreter has no Pillow).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc

from build_scaled_fonts import FONT_RESREFS, write_tga


DEFAULT_FACTOR = 4
DEFAULT_EDGE = 0.16


def edge_lut(edge: float) -> list[int]:
    """Smoothstep centred on 50% coverage, tightening resampled edges."""
    lut = []
    low, high = 0.5 - edge, 0.5 + edge
    for value in range(256):
        alpha = value / 255.0
        t = (alpha - low) / (high - low)
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        lut.append(round(t * t * (3.0 - 2.0 * t) * 255.0))
    return lut


def upscale_atlas(rgba: bytes, width: int, height: int, factor: int, edge: float) -> Image.Image:
    source = Image.frombytes("RGBA", (width, height), rgba)
    alpha = source.getchannel("A").resize((width * factor, height * factor), Image.LANCZOS)
    alpha = alpha.point(edge_lut(edge))
    # Flat white everywhere: the source's RGB is meaningless where alpha is 0
    # and would otherwise bleed into the glyph edges.
    output = Image.new("RGBA", alpha.size, (255, 255, 255, 0))
    output.putalpha(alpha)
    return output


def build(erf_path: Path, output_dir: Path, factor: int, edge: float) -> list[tuple[str, tuple[int, int]]]:
    erf = read_erf(erf_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    wanted = {name.lower() for name in FONT_RESREFS}
    built: list[tuple[str, tuple[int, int]]] = []

    for resource in erf:
        name = str(resource.resref).lower()
        if name not in wanted:
            continue
        tpc = read_tpc(bytes(resource.data))
        tpc.convert(TPCTextureFormat.RGBA)
        mipmap = tpc.get(0)
        image = upscale_atlas(bytes(mipmap.data), mipmap.width, mipmap.height, factor, edge)
        write_tga(output_dir / f"{name}.tga", image.width, image.height, image.tobytes())
        built.append((name, image.size))

    missing = sorted(wanted - {name for name, _ in built})
    if missing:
        raise ValueError(f"Font atlases not found in {erf_path}: {', '.join(missing)}")
    return built


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("erf", type=Path, help="TexturePacks/swpc_tex_gui.erf")
    parser.add_argument("output", type=Path)
    parser.add_argument("--factor", type=int, default=DEFAULT_FACTOR, help="Texture upscale factor")
    parser.add_argument("--edge", type=float, default=DEFAULT_EDGE,
                        help="Edge transition half-width in coverage units; smaller is crisper")
    args = parser.parse_args()

    if not 1 <= args.factor <= 8:
        raise ValueError("Factor must be between 1 and 8")
    if not 0.01 <= args.edge <= 0.5:
        raise ValueError("Edge must be between 0.01 and 0.5")

    built = build(args.erf, args.output, args.factor, args.edge)
    total = sum((args.output / f"{name}.tga").stat().st_size for name, _ in built)
    print(f"Wrote {len(built)} atlases at {args.factor}x to {args.output} ({total / 1024 / 1024:.1f} MB)")
    for name, size in sorted(built):
        print(f"  {name:<20} {size[0]}x{size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
