"""Removes the white fringe under the holocron's base (left from cutting out its
background): near-white, unsaturated pixels below the base line made transparent, with
a two-pixel soft edge. Nothing else is touched.

    python clean_holocron.py in.png out.png
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

src, dst = sys.argv[1], sys.argv[2]
rgba = np.asarray(Image.open(src).convert("RGBA")).astype(np.float32)
rgb, a = rgba[..., :3], rgba[..., 3]
lum = rgb.mean(2)
sat = rgb.max(2) - rgb.min(2)
BASE_TOP = 3300                      # the base starts here; the glass above keeps its white lines
white = (lum > 150) & (sat < 110) & (a > 8)
white[:BASE_TOP] = False
# Grow it by two pixels so the light rim around the fringe goes with it, then soften.
grown = ndimage.binary_dilation(white, iterations=2)
soft = ndimage.gaussian_filter(grown.astype(np.float32), 1.0)
rgba[..., 3] = a * (1 - np.clip(soft * 1.4, 0, 1))
Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA").save(dst)
print(dst, "fringe pixels removed:", int(white.sum()))
