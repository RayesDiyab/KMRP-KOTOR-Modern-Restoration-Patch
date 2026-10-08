"""A part of an icon enlarged, with a grid in units:
    python zoom.py <out.png> <icon> [--box x0 y0 x1 y1] [--px 44] [--src vanilla,ref,final] [--back dark|grey|green|black] [--nogrid]
--box in units of the 32-unit frame (default the whole frame); --px: pixels per unit in the picture.
--src: which pictures side by side (vanilla | ref (ChatGPT's redraw laid into the frame) | final | out/trial ...)."""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VANILLA = r"C:\ComfyUI\kotor\in"
BACKS = {"green": (0, 255, 0), "dark": (6, 16, 40), "grey": (128, 128, 128), "black": (0, 0, 0), "white": (255, 255, 255)}
args = sys.argv[1:]
target, name = args.pop(0), args.pop(0)
box, ppu, srcs, back, grid = [0, 0, 32, 32], 24, ["vanilla", "ref", "final"], BACKS["dark"], True
while args:
    a = args.pop(0)
    if a == "--box": box = [float(args.pop(0)) for _ in range(4)]
    elif a == "--px": ppu = int(args.pop(0))
    elif a == "--src": srcs = args.pop(0).split(",")
    elif a == "--back": back = BACKS[args.pop(0)]
    elif a == "--nogrid": grid = False
index = json.load(open(os.path.join(ROOT, "refs", "index.json")))
font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 11)


def load(src):
    if src == "vanilla":
        return Image.open(os.path.join(VANILLA, name + ".png")).convert("RGBA"), Image.NEAREST
    if src == "ref":
        return Image.open(os.path.join(ROOT, "refs", name + ".png")).convert("RGBA"), Image.BICUBIC
    return Image.open(os.path.join(ROOT, src, index[name]["sheet"], name + ".png")).convert("RGBA"), Image.BICUBIC


tiles = []
w, h = int(round((box[2] - box[0]) * ppu)), int(round((box[3] - box[1]) * ppu))
for src in srcs:
    im, how = load(src)
    k = im.width / 32.0
    crop = im.crop((int(round(box[0] * k)), int(round(box[1] * k)), int(round(box[2] * k)), int(round(box[3] * k)))).resize((w, h), how)
    t = Image.new("RGBA", (w, h), back + (255,))
    t.alpha_composite(crop)
    t = t.convert("RGB")
    d = ImageDraw.Draw(t)
    if grid:
        x = np.ceil(box[0])
        while x < box[2]:
            X = int(round((x - box[0]) * ppu))
            d.line([(X, 0), (X, h)], fill=(70, 90, 70) if int(x) % 4 else (120, 160, 120), width=1)
            if int(x) % 2 == 0: d.text((X + 2, 1), str(int(x)), fill=(255, 255, 0), font=font)
            x += 1
        y = np.ceil(box[1])
        while y < box[3]:
            Y = int(round((y - box[1]) * ppu))
            d.line([(0, Y), (w, Y)], fill=(70, 90, 70) if int(y) % 4 else (120, 160, 120), width=1)
            if int(y) % 2 == 0: d.text((1, Y + 1), str(int(y)), fill=(255, 255, 0), font=font)
            y += 1
    d.text((w - 60, h - 14), src, fill=(255, 255, 0), font=font)
    tiles.append(t)
out = Image.new("RGB", (len(tiles) * (w + 4) - 4, h), (30, 30, 30))
for i, t in enumerate(tiles):
    out.paste(t, (i * (w + 4), 0))
out.save(target)
print(target, out.size)
