"""Colours along a line, or at points: for measuring a gradient before writing it as a formula.

    python probe.py <icon> x0 y0 x1 y1 [--n 16] [--src ref|vanilla|final]      n samples from (x0, y0) to (x1, y1)
    python probe.py <icon> --at x,y x,y ...        [--src ...]                 the colour at each point

Coordinates in units of the 32-unit frame. Each sample: distance along the line, colour as rrggbb, opacity 0..9
(each sample is the mean of a 3 x 3 patch of the 512 px picture, so one stray pixel does not decide it).
src final reads the JavaScript drawing (final/<sheet>/<icon>.png), for checking a formula against its reference."""
import os, sys, json
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
name = args.pop(0)
src, n, pts, line = "ref", 16, [], []
while args:
    a = args.pop(0)
    if a == "--src": src = args.pop(0)
    elif a == "--n": n = int(args.pop(0))
    elif a == "--at":
        while args and not args[0].startswith("--"):
            pts.append(tuple(float(v) for v in args.pop(0).split(",")))
    else: line.append(float(a))
if src == "vanilla":
    im = Image.open(os.path.join(r"C:\ComfyUI\kotor\in", name + ".png")).convert("RGBA")
elif src == "ref":
    im = Image.open(os.path.join(ROOT, "refs", name + ".png")).convert("RGBA")
else:
    index = json.load(open(os.path.join(ROOT, "refs", "index.json")))
    im = Image.open(os.path.join(ROOT, src, index[name]["sheet"], name + ".png")).convert("RGBA")
a = np.asarray(im).astype(np.float64)
K = a.shape[0] / 32.0
rad = 1 if K >= 8 else 0


def at(x, y):
    px, py = int(x * K), int(y * K)
    if not (0 <= px < a.shape[1] and 0 <= py < a.shape[0]):
        return "------ ."
    p = a[max(py - rad, 0):py + rad + 1, max(px - rad, 0):px + rad + 1].reshape(-1, 4)
    w = p[:, 3:4] / 255.0
    al = float(w.mean())
    c = (p[:, :3] * w).sum(axis=0) / max(w.sum(), 1e-6)
    return "%02x%02x%02x %d" % (int(round(c[0])), int(round(c[1])), int(round(c[2])), int(round(al * 9)))


if pts:
    for x, y in pts:
        print("%6.2f,%6.2f  %s" % (x, y, at(x, y)))
else:
    x0, y0, x1, y1 = line
    L = float(np.hypot(x1 - x0, y1 - y0))
    print("%s %s from %.2f,%.2f to %.2f,%.2f (%.2f units)" % (name, src, x0, y0, x1, y1, L))
    for i in range(n):
        t = i / (n - 1)
        print("%6.2f  %s" % (t * L, at(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)))
