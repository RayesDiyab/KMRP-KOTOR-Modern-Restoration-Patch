#!/usr/bin/env python3
"""Copy the original PC font atlases out of the user's GUI texture pack (kmrfogNN).

They are the Original Font style, and what tools/build_hd_original_fonts.py measures.
Size is finalized by KMRP at LoadTXI, so they contain no resolution assumptions.
Output is ignored build data. Until 2026-10-18 this also wrote kmrfpcNN, the
"Original Sharpened" style (each atlas enlarged 4x with Lanczos and a steepness-7
coverage curve, after jryantomes/kmdlswap's tools/kmrp_pcfont/build.py at 31bd877);
HD Original replaced it.
"""
from pathlib import Path
import argparse
import hashlib
import re

from PIL import Image
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import read_tpc, TPCTextureFormat
from build_scaled_fonts import FONT_RESREFS, raw_txi, write_tga

# These two stock entries have a regular 16-column alpha sheet but a TXI from
# another packing. Restrict its repair to the measured, identical resources.
GRID_REPAIR_SHA256 = '9e0c0819c16b2a1bb6170e5973ffc4e58740eaaf741d2a3a5fbb8e70e728375b'
GRID_NAMES = {'fnt_d10x10b', 'fnt_d16x16'}


def repair_grid(image, txi):
    """The measured stock alpha atlas uses 32x19 cells, 16 columns, 256 cells.

    Its white glyphs have already been rasterized in these cells. Keep their
    pixels and bearings, derive proportional advances, and preserve a positive
    advance for blank/control characters. No glyphs are synthesized.
    """
    if image.size != (512, 512):
        raise ValueError('Unexpected original-PC grid atlas dimensions')
    alpha = image.getchannel('A')
    upper, lower = [], []
    for index in range(256):
        x, y = index % 16 * 32, index // 16 * 19
        bounds = alpha.crop((x, y, x + 32, y + 19)).getbbox()
        width = min(32, bounds[2] + 1) if bounds else 6
        upper.append(f'{x / 512:.6f} {1 - y / 512:.6f} 0')
        lower.append(f'{(x + width) / 512:.6f} {1 - (y + 19) / 512:.6f} 0')
    head = txi[:txi.lower().index('upperleftcoords')]
    for name, value in [('fontheight', '.190000'), ('baselineheight', '.150000'), ('texturewidth', '5.120000')]:
        head = re.sub(rf'(?im)^{name}\s+[^\r\n]+', f'{name} {value}', head)
    return head + 'upperleftcoords 256\n' + '\n'.join(upper) + '\nlowerrightcoords 256\n' + '\n'.join(lower) + '\n'


def decoded(raw):
    """A stock font's atlas as a top-down RGBA image."""
    texture = read_tpc(raw)
    texture.convert(TPCTextureFormat.RGBA)
    mip = texture.get(0)
    return Image.frombytes('RGBA', (mip.width, mip.height), bytes(mip.data)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def stock_txi(name, raw, image=None):
    """A stock font's TXI, repaired for the two grid atlases (repair_grid) after
    checking they are the measured resource. tools/build_font_from_ttf.py reads its
    reference metrics here too, since 2026-10-18: until then it read the texture pack's
    TXI, so Old HD's fnt_d10x10b and fnt_d16x16 were baked as 10 pixel fonts."""
    txi = raw_txi(raw)
    if name in GRID_NAMES:
        if hashlib.sha256(raw).hexdigest() != GRID_REPAIR_SHA256:
            raise ValueError(f'{name}: unrecognized grid atlas; refusing an unverified repair')
        txi = repair_grid(image if image is not None else decoded(raw), txi)
    return txi


def build(texture_pack, output):
    output.mkdir(parents=True, exist_ok=True)
    for stale in output.glob('kmrfpc*'):     # the retired Original Sharpened set
        stale.unlink()
    resources = {str(r.resref).lower(): bytes(r.data) for r in read_erf(texture_pack)
                 if str(r.resref).lower() in FONT_RESREFS}
    if set(resources) != set(FONT_RESREFS):
        raise ValueError('GUI texture pack must contain all 18 original fonts')
    for index, name in enumerate(FONT_RESREFS):
        raw = resources[name]
        image = decoded(raw)
        txi = stock_txi(name, raw, image)
        stem = f'kmrfog{index:02d}'
        write_tga(output / f'{stem}.tga', *image.size, image.tobytes())
        (output / f'{stem}.txi').write_text(txi, encoding='ascii')
    return len(resources)


def enlarged(originals, resref, output, scale):
    """HD Original's atlas for a font with no vector face (fnt_galahad14): the original's
    own letters from `originals` (the kmrfogNN above), enlarged with Lanczos and their
    edges made steeper. Its TXI's sizes are the original's times the scale, its
    coordinates the same fractions. It is made from the game's files at every build and
    never committed, because it is the game's own art (the maintainer, 2026-10-19).
    Until that day it lived in tools/build_hd_original_fonts.py and its output was in
    assets/hd-original-fonts."""
    import math
    index = FONT_RESREFS.index(resref)
    image = Image.open(originals / f"kmrfog{index:02d}.tga").convert("RGBA")
    size = (round(image.width * scale), round(image.height * scale))
    big = image.resize(size, Image.LANCZOS)
    lo, hi = 1 / (1 + math.exp(14)), 1 / (1 + math.exp(-14))
    curve = [round(max(0.0, min(1.0, (1 / (1 + math.exp(-28 * (a / 255 - 0.5))) - lo) / (hi - lo))) * 255)
             for a in range(256)]
    big.putalpha(big.getchannel("A").point(curve))
    output.mkdir(parents=True, exist_ok=True)
    write_tga(output / f"{resref}.tga", size[0], size[1], big.tobytes())
    lines = []
    for line in (originals / f"kmrfog{index:02d}.txi").read_text().replace("\r\n", "\n").split("\n"):
        parts = line.split()
        if len(parts) == 2 and parts[0] in ("fontheight", "baselineheight", "spacingR", "spacingB"):
            line = f"{parts[0]} {float(parts[1]) * scale:.6f}"
        elif len(parts) == 2 and parts[0] == "texturewidth":
            line = f"texturewidth {size[0] / 100.0:.6f}"
        lines.append(line)
    (output / f"{resref}.txi").write_bytes("\n".join(lines).encode("ascii"))
    return size[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--texture-pack', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(f'Copied {build(args.texture_pack, args.output)} original-PC fonts')
