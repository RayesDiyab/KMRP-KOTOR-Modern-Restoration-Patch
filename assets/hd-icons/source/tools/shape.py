"""The outline of one area of a reference as straight lines and circular arcs only (a measurement for a construction).

    python shape.py <icon> --mask <kind> [--src ref|vanilla] [--min 1.5] [--pick N]
    python shape.py <icon> --seed x,y [--tol 40] [--src ...]     the area of like colour round the point (x, y)

mask kinds as in trace.py: solid any clear black white light dark blue red yellow.
For each outline (largest first; --pick N prints only the Nth): its area, box, and its pieces in order:
    M x y            start
    L x y            a straight line to (x, y), with its direction in degrees (y down) and its length
    A cx cy r a0 a1  a circular arc about (cx, cy) with radius r from angle a0 to a1 (degrees)
    C ...            a stretch that fitted neither (rare: treat as a hint to look closer)
and how far the fitted outline strays from the measured one (mean, max; units of the 32-unit frame).
The pieces are a measurement: read the lengths, angles, radii and symmetries off them and construct the shape
with exact primitives (do not paste them in as a drawing)."""
import os, sys, math
import numpy as np
import cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outline as OL

OL.STRICT = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
name = args.pop(0)
src, mask_kind, least, seed, tol, pick = "ref", "solid", 1.5, None, 40.0, None
while args:
    a = args.pop(0)
    if a == "--src": src = args.pop(0)
    elif a == "--mask": mask_kind = args.pop(0)
    elif a == "--min": least = float(args.pop(0))
    elif a == "--seed": seed = tuple(float(v) for v in args.pop(0).split(","))
    elif a == "--tol": tol = float(args.pop(0))
    elif a == "--pick": pick = int(args.pop(0))
p = os.path.join(ROOT, "refs", name + ".png") if src == "ref" else os.path.join(r"C:\ComfyUI\kotor\in", name + ".png")
im = Image.open(p).convert("RGBA")
if im.width != 512:
    im = im.resize((512, 512), Image.NEAREST)
a = np.asarray(im).astype(np.float32)
k = a.shape[0] / 32.0
r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3] / 255.0
mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
solid = al >= 0.5
if seed is not None:
    sx, sy = int(seed[0] * k), int(seed[1] * k)
    ref = a[sy, sx, :3]
    like = (np.abs(a[..., :3] - ref).max(axis=2) <= tol) & (solid if al[sy, sx] >= 0.5 else ~solid)
    n, lab = cv2.connectedComponents(like.astype(np.uint8), connectivity=4)
    m = (lab == lab[sy, sx]).astype(np.uint8)
    print("%s %s: the area like %02x%02x%02x (within %d) round %.2f,%.2f" % (name, src, int(ref[0]), int(ref[1]), int(ref[2]), tol, seed[0], seed[1]))
else:
    masks = {
        "solid": solid, "any": al >= 0.1, "clear": ~solid,
        "black": solid & (mx < 70), "white": solid & (mn > 205), "light": solid & (mx > 200) & (mn > 120),
        "dark": solid & (mx < 130),
        "blue": solid & (b > r + 40) & (b > 90), "red": solid & (r > b + 40) & (r > 90) & (g < 0.75 * r),
        "yellow": solid & (r > 170) & (g > 150) & (b < 130),
    }
    m = masks[mask_kind].astype(np.uint8)
    print("%s %s mask %s" % (name, src, mask_kind))
m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
found, tree = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
items = sorted(((cv2.contourArea(c) / (k * k), i, c) for i, c in enumerate(found)), key=lambda t: -t[0])
items = [t for t in items if t[0] >= least]
for rank, (area, i, c) in enumerate(items[:12]):
    if pick is not None and rank != pick:
        continue
    pts = c[:, 0, :]
    hole = tree[0][i][3] >= 0
    x0, y0, x1, y1 = pts[:, 0].min() / k, pts[:, 1].min() / k, (pts[:, 0].max() + 1) / k, (pts[:, 1].max() + 1) / k
    shape, stray, made = OL.regularize(pts)
    print("#%d %s area %.1f  box x %.2f..%.2f y %.2f..%.2f  stray mean %.3f max %.2f" % (rank, "HOLE " if hole else "shape", area, x0, x1, y0, y1, stray[0], stray[1]))
    if shape[0] == "circle":
        print("   circle  centre %.2f,%.2f  radius %.2f" % (shape[1], shape[2], shape[3]))
    elif shape[0] == "ellipse":
        print("   ellipse centre %.2f,%.2f  radii %.2f x %.2f  turned %.1f deg" % tuple(shape[1:6]))
    else:
        x = y = 0.0
        for q in shape[1]:
            if q[0] == "M":
                x, y = q[1], q[2]
                print("   M %6.2f %6.2f" % (x, y))
            elif q[0] == "L":
                d = math.hypot(q[1] - x, q[2] - y)
                if d > 0.05:
                    print("   L %6.2f %6.2f     %7.1f deg  %5.2f long" % (q[1], q[2], math.degrees(math.atan2(q[2] - y, q[1] - x)), d))
                x, y = q[1], q[2]
            elif q[0] == "A":
                _, cx, cy, rr, a0, a1 = q
                x, y = cx + rr * math.cos(a1), cy + rr * math.sin(a1)
                print("   A centre %6.2f %6.2f r %5.2f from %6.1f to %6.1f deg   ends at %.2f %.2f" % (cx, cy, rr, math.degrees(a0), math.degrees(a1), x, y))
            elif q[0] == "C":
                x, y = q[5], q[6]
                print("   C (free curve) to %6.2f %6.2f" % (x, y))
