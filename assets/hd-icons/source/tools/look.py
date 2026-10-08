"""A few icons large: python look.py <out.png> [--tile 300] [--back dark|green|grey|white] [--nodiff] [--pair] [--cols N] <icon> ...
--pair: only the vanilla icon and the drawing.  --cols: how many icons side by side.
Per icon: vanilla | ChatGPT's redraw | the JavaScript drawing (final/), and the drawing's difference from the redraw x3."""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VANILLA = r"C:\ComfyUI\kotor\in"
BACKS = {"green": (0, 255, 0), "dark": (6, 16, 40), "grey": (128, 128, 128), "white": (255, 255, 255)}
args = sys.argv[1:]
target = args.pop(0)
tile, back, names, src, pair, ncols = 300, BACKS["dark"], [], "final", False, 0
while args:
    a = args.pop(0)
    if a == "--tile": tile = int(args.pop(0))
    elif a == "--src": src = args.pop(0)
    elif a == "--nodiff": pass
    elif a == "--pair": pair = True
    elif a == "--cols": ncols = int(args.pop(0))
    elif a == "--back": back = BACKS[args.pop(0)]
    else: names.append(a)
index = json.load(open(os.path.join(ROOT, "refs", "index.json")))
font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 11)


def on(im, resample, bk=None):
    im = im.convert("RGBA").resize((tile, tile), resample)
    t = Image.new("RGBA", (tile, tile), (bk or back) + (255,))
    t.alpha_composite(im)
    return t.convert("RGB")


rows = []
for n in names:
    v = Image.open(os.path.join(VANILLA, n + ".png"))
    r = Image.open(os.path.join(ROOT, "refs", n + ".png"))
    m = Image.open(os.path.join(ROOT, src, index[n]["sheet"], n + ".png"))
    A = np.asarray(on(r, Image.LANCZOS, (128, 128, 128))).astype(np.float32)
    Bm = np.asarray(on(m, Image.LANCZOS, (128, 128, 128))).astype(np.float32)
    diff = Image.fromarray(np.clip(np.abs(A - Bm).max(axis=2) * 3, 0, 255).astype(np.uint8)).convert("RGB")
    tiles = [on(v, Image.NEAREST), on(r, Image.LANCZOS), on(m, Image.LANCZOS)] + ([] if "--nodiff" in sys.argv else [diff])
    if pair: tiles = [tiles[0], tiles[2]]
    row = Image.new("RGB", (len(tiles) * (tile + 3), tile + 13), (30, 30, 30))
    for i, t in enumerate(tiles):
        row.paste(t, (i * (tile + 3), 13))
    ImageDraw.Draw(row).text((2, 0), n + ("    game | new" if pair else "    vanilla | ChatGPT redraw | JavaScript drawing"), fill=(255, 255, 0), font=font)
    rows.append(row)
cols = ncols or (2 if len(rows) > 3 else 1)
per = (len(rows) + cols - 1) // cols
out = Image.new("RGB", (cols * (rows[0].width + 8), per * (rows[0].height + 3)), (10, 10, 10))
for i, r_ in enumerate(rows):
    out.paste(r_, ((i // per) * (r_.width + 8), (i % per) * (r_.height + 3)))
out.save(target)
print(target, out.size)
