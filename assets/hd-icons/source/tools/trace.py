"""Measure a reference: the outlines of one kind of area, in units of the 32-unit frame.

    python trace.py <icon> [--src ref|vanilla] [--mask solid|any|black|white|light|blue|red|yellow|dark|clear] [--eps 0.3] [--min 1.5]

For each outline found (largest first; holes marked): its area and bounding box, the circle that fits it (centre,
radius, how far the outline strays from it), and the outline simplified to a few points (within eps units).
Measurements are the input for an exact construction; they are not pasted in as drawings.
    solid  alpha >= 0.5      any  alpha >= 0.1      clear  alpha < 0.5 (the holes)
    black  dark and solid    white  near white       light  light (any hue)      dark  dark blue/red/black
    blue / red / yellow      by hue, solid
"""
import os, sys
import numpy as np
import cv2
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
name = args.pop(0)
src, mask_kind, eps, least = "ref", "solid", 0.3, 1.5
while args:
    a = args.pop(0)
    if a == "--src": src = args.pop(0)
    elif a == "--mask": mask_kind = args.pop(0)
    elif a == "--eps": eps = float(args.pop(0))
    elif a == "--min": least = float(args.pop(0))
p = os.path.join(ROOT, "refs", name + ".png") if src == "ref" else os.path.join(r"C:\ComfyUI\kotor\in", name + ".png")
im = Image.open(p).convert("RGBA")
if src == "vanilla":
    im = im.resize((512, 512), Image.NEAREST)
a = np.asarray(im).astype(np.float32)
k = a.shape[0] / 32.0
r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3] / 255.0
mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
solid = al >= 0.5
masks = {
    "solid": solid, "any": al >= 0.1, "clear": ~solid,
    "black": solid & (mx < 70), "white": solid & (mn > 205), "light": solid & (mx > 200) & (mn > 120),
    "dark": solid & (mx < 130),
    "blue": solid & (b > r + 40) & (b > 90), "red": solid & (r > b + 40) & (r > 90) & (g < 0.75 * r),
    "yellow": solid & (r > 170) & (g > 150) & (b < 130),
}
m = masks[mask_kind].astype(np.uint8)
found, tree = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
items = []
for i, c in enumerate(found):
    area = cv2.contourArea(c) / (k * k)
    if area < least:
        continue
    items.append((area, i, c))
print("%s  %s  mask %s: %d outlines of %.1f square units or more" % (name, src, mask_kind, len(items), least))
for area, i, c in sorted(items, key=lambda t: -t[0])[:14]:
    hole = tree[0][i][3] >= 0
    pts = c[:, 0, :].astype(np.float64)
    x0, y0, x1, y1 = pts[:, 0].min() / k, pts[:, 1].min() / k, (pts[:, 0].max() + 1) / k, (pts[:, 1].max() + 1) / k
    A = np.c_[2 * pts, np.ones(len(pts))]
    (cx, cy, kk), *_ = np.linalg.lstsq(A, (pts ** 2).sum(axis=1), rcond=None)
    rad = np.sqrt(max(kk + cx * cx + cy * cy, 0))
    stray = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - rad)
    simp = cv2.approxPolyDP(c, eps * k, True)[:, 0, :] / k
    print(" %s area %6.1f  box x %.1f..%.1f y %.1f..%.1f   circle c %.2f,%.2f r %.2f (stray mean %.2f max %.2f)"
          % ("HOLE " if hole else "shape", area, x0, x1, y0, y1, (cx + 0.5) / k, (cy + 0.5) / k, rad / k, stray.mean() / k, stray.max() / k))
    print("      %d pts: %s" % (len(simp), " ".join("%.1f,%.1f" % (px + 0.5 / k, py + 0.5 / k) for px, py in simp)))
