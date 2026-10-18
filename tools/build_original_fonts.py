#!/usr/bin/env python3
"""Build untouched and sharpened original-PC font atlases from the user's GUI texture pack.

The 4x Lanczos / steepness-7 coverage curve follows jryantomes/kmdlswap's
tools/kmrp_pcfont/build.py at 31bd877. Size is finalized by KMRP at LoadTXI,
so these assets contain no resolution assumptions. Output is ignored build data.
"""
from pathlib import Path
import argparse
import hashlib
import math
import re

from PIL import Image
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.tpc import read_tpc, TPCTextureFormat
from build_scaled_fonts import FONT_RESREFS, raw_txi, write_tga

# These two stock entries have a regular 16-column alpha sheet but a TXI from
# another packing. Restrict its repair to the measured, identical resources.
GRID_REPAIR_SHA256 = '9e0c0819c16b2a1bb6170e5973ffc4e58740eaaf741d2a3a5fbb8e70e728375b'
GRID_NAMES = {'fnt_d10x10b', 'fnt_d16x16'}


def sharpen(image):
    alpha = image.getchannel('A').resize((image.width * 4, image.height * 4), Image.Resampling.LANCZOS)
    lo, hi = 1 / (1 + math.exp(14)), 1 / (1 + math.exp(-14))
    curve = [round(max(0., min(1., (1 / (1 + math.exp(-28 * (a / 255 - .5))) - lo) / (hi - lo))) * 255) for a in range(256)]
    result = Image.new('RGBA', alpha.size, (255, 255, 255, 0))
    result.putalpha(alpha.point(curve))
    return result


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


def build(texture_pack, output):
    output.mkdir(parents=True, exist_ok=True)
    resources = {str(r.resref).lower(): bytes(r.data) for r in read_erf(texture_pack)
                 if str(r.resref).lower() in FONT_RESREFS}
    if set(resources) != set(FONT_RESREFS):
        raise ValueError('GUI texture pack must contain all 18 original fonts')
    for index, name in enumerate(FONT_RESREFS):
        raw = resources[name]
        texture = read_tpc(raw)
        texture.convert(TPCTextureFormat.RGBA)
        mip = texture.get(0)
        image = Image.frombytes('RGBA', (mip.width, mip.height), bytes(mip.data)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        txi = raw_txi(raw)
        if name in GRID_NAMES:
            if hashlib.sha256(raw).hexdigest() != GRID_REPAIR_SHA256:
                raise ValueError(f'{name}: unrecognized grid atlas; refusing an unverified repair')
            txi = repair_grid(image, txi)
        for prefix, atlas in [('kmrfog', image), ('kmrfpc', sharpen(image))]:
            stem = f'{prefix}{index:02d}'
            write_tga(output / f'{stem}.tga', *atlas.size, atlas.tobytes())
            (output / f'{stem}.txi').write_text(txi, encoding='ascii')
    return len(resources)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--texture-pack', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(f'Built {build(args.texture_pack, args.output)} sharpened original-PC fonts')
