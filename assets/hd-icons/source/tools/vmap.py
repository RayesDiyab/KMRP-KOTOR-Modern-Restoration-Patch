"""The vanilla icon as text, pixel for pixel: python vmap.py <icon> ...
Left: what colour each pixel is.  Right: how opaque it is (0 = clear ... 9 = solid).
A 64 x 64 icon is shown at half size (each character one 2 x 2 block: the block's middle colour, its mean alpha).
Colours:  . clear   # black   W white   w pale   g/G light/dark grey
          b light blue   B blue   N navy   c/C light/dark cyan   r pink   R red   D dark red   Y yellow   O orange
Also prints the icon's commonest solid colours."""
import os, sys
import numpy as np
from PIL import Image

IN = r"C:\ComfyUI\kotor\in"


def kind(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 60: return "#"
    if mn > 215: return "W"
    if mx - mn < 40: return "w" if mn > 150 else ("g" if mn > 90 else "G")
    if r > 170 and g > 150 and b < 120: return "Y"
    if r > 170 and g > 90 and b < 90: return "O"
    if b >= r and b >= g:
        if g > r + 50 and g > 0.75 * b: return "c" if mn > 60 or g > 180 else "C"
        if mn > 120: return "b"
        return "B" if b > 150 else "N"
    if r >= g and r >= b:
        if mn > 120: return "r"
        return "R" if r > 150 else "D"
    return "c" if g > 150 else "C"


for name in sys.argv[1:]:
    im = np.asarray(Image.open(os.path.join(IN, name + ".png")).convert("RGBA")).astype(np.float32)
    h, w = im.shape[:2]
    step = 2 if w > 32 else 1
    print("== %s  %dx%d%s" % (name, w, h, "  (shown at half size)" if step == 2 else ""))
    print("    " + "".join(str(x % 10) for x in range(w // step)) + "    " + "".join(str(x % 10) for x in range(w // step)))
    for y in range(0, h, step):
        row_c, row_a = "", ""
        for x in range(0, w, step):
            blk = im[y:y + step, x:x + step].reshape(-1, 4)
            a = blk[:, 3].mean()
            vis = blk[blk[:, 3] >= 32]
            if a < 16 or len(vis) == 0:
                row_c += "."
            else:
                r, g, b = np.median(vis[:, :3], axis=0)
                row_c += kind(r, g, b)
            row_a += str(min(9, int(a / 25.6)))
        print("%2d  %s    %s" % (y // step, row_c, row_a))
    solid = im[im[..., 3] >= 200][:, :3]
    if len(solid):
        q = (solid // 24 * 24 + 12).astype(np.int32)
        keys, counts = np.unique(q, axis=0, return_counts=True)
        top = np.argsort(-counts)[:7]
        print("    colours: " + "  ".join("%d,%d,%d x%d" % (keys[i][0], keys[i][1], keys[i][2], counts[i]) for i in top))
