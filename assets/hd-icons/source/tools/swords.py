"""Measure the swords of an icon: python swords.py <icon> <mask> [--src ref|vanilla] [--min 3]
mask: red | blue | light | paint (solid and not dark) | solid
Every connected part of the mask is taken as one elongated object. Its axis is fitted (principal axis), its width is
measured along that axis, and from the width profile: where the cross-guard sits (the widest place), the blade's
width (median of the blade's middle), where the tip starts to taper, the grip's width.
All in units of the 32-unit frame. One line per object, as the arguments of sword() in drawn/flat_sharp.js:
    tip x,y   end x,y (pommel end)   guard at (distance from the pommel end)   blade (width)   taper (length of the point)
    guard (length across) x (thickness)   grip (width)   angle (degrees; y runs down)"""
import os, sys, math
import numpy as np
import cv2
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
name, kind = args[0], args[1]
src = args[args.index("--src") + 1] if "--src" in args else "ref"
least = float(args[args.index("--min") + 1]) if "--min" in args else 3.0
if src == "vanilla":
    im = Image.open(os.path.join(r"C:\ComfyUI\kotor\in", name + ".png")).convert("RGBA")
    im = im.resize((512, 512), Image.NEAREST)
else:
    im = Image.open(os.path.join(ROOT, "refs", name + ".png")).convert("RGBA")
a = np.asarray(im).astype(np.float32)
K = a.shape[0] / 32.0
r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3] / 255.0
mx = np.maximum(np.maximum(r, g), b)
solid = al >= 0.5
masks = {"solid": solid, "paint": solid & (mx >= 90), "red": solid & (r > 120) & (r > b + 50), "blue": solid & (b > 120) & (b > r + 30),
         "light": solid & (np.minimum(np.minimum(r, g), b) > 190)}
m = cv2.morphologyEx(masks[kind].astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
for k in sorted(range(1, n), key=lambda i: -stats[i, cv2.CC_STAT_AREA]):
    if stats[k, cv2.CC_STAT_AREA] < least * K * K:
        continue
    ys, xs = np.nonzero(lab == k)
    p = np.c_[(xs + 0.5) / K, (ys + 0.5) / K]
    c = p.mean(axis=0)
    _, _, vt = np.linalg.svd(p - c, full_matrices=False)
    u, nv = vt[0], vt[1]
    t, s = (p - c) @ u, (p - c) @ nv
    step = 0.25
    bins = np.floor((t - t.min()) / step).astype(int)
    nb = bins.max() + 1
    lo = np.full(nb, np.inf); hi = np.full(nb, -np.inf)
    np.minimum.at(lo, bins, s); np.maximum.at(hi, bins, s)
    w = np.where(np.isfinite(lo), hi - lo, 0.0) + 1.0 / K
    mid = np.where(np.isfinite(lo), (hi + lo) / 2, 0.0)
    ig = int(np.argmax(w))
    wide = w > 0.62 * w[ig]
    g0 = ig
    while g0 > 0 and wide[g0 - 1]: g0 -= 1
    g1 = ig
    while g1 < nb - 1 and wide[g1 + 1]: g1 += 1
    if (nb - g1) < g0:                                             # the blade is the longer side: put it at the high end
        u, nv = -u, -nv
        t, s = -t, -s
        w, mid, wide = w[::-1], -mid[::-1], wide[::-1]
        g0, g1, ig = nb - 1 - g1, nb - 1 - g0, nb - 1 - ig
    blade = w[g1 + 1:]
    grip = w[:g0]
    bw = float(np.median(blade[int(0.15 * len(blade)):int(0.7 * len(blade)) or None])) if len(blade) > 4 else 0.0
    taper = 0
    for v in blade[::-1]:
        if v >= 0.92 * bw: break
        taper += 1
    gw = float(np.median(grip)) if len(grip) else 0.0
    off = float(np.median(mid[g1 + 1:][int(0.15 * len(blade)):int(0.7 * len(blade)) or None])) if len(blade) > 4 else 0.0
    axis0 = c + nv * off                                           # the blade's own centre line
    tmin, tmax = t.min(), t.max()
    E, T = axis0 + u * tmin, axis0 + u * tmax
    ang = math.degrees(math.atan2(u[1], u[0]))
    print("%s part of %.1f sq units: tip %.2f,%.2f  end %.2f,%.2f  guard at %.2f  blade %.2f  taper %.2f  guard %.2f x %.2f  grip %.2f  angle %.1f"
          % (name, stats[k, cv2.CC_STAT_AREA] / K / K, T[0], T[1], E[0], E[1], (g0 + g1 + 1) / 2 * step, bw, taper * step, w[ig], (g1 - g0 + 1) * step, gw, ang))
    if "--profile" in args:
        # the outline as offsets from the blade's centre line, every 0.25 along it from the pommel end: low side, high side
        lo2 = np.where(np.isfinite(lo), lo, 0.0); hi2 = np.where(np.isfinite(hi), hi, 0.0)
        if (u @ vt[0]) < 0:
            lo2, hi2 = -hi2[::-1], -lo2[::-1]
        lo2, hi2 = lo2 - off - 0.5 / K, hi2 - off + 0.5 / K
        print("   t: " + " ".join("%5.2f" % (i * step) for i in range(nb)))
        print("  lo: " + " ".join("%5.2f" % v for v in lo2))
        print("  hi: " + " ".join("%5.2f" % v for v in hi2))
    if "--fit" in args:
        # the half-width along the object as a few straight stretches (Douglas-Peucker, 0.1 units): the outline's corners
        lo2 = np.where(np.isfinite(lo), lo, 0.0); hi2 = np.where(np.isfinite(hi), hi, 0.0)
        if (u @ vt[0]) < 0:
            lo2, hi2 = -hi2[::-1], -lo2[::-1]
        half = (hi2 - lo2) / 2 + 0.5 / K
        ctr = (hi2 + lo2) / 2 - off
        tt = np.arange(nb) * step + step / 2
        pts = np.c_[tt, half]
        eps = float(args[args.index("--fit") + 1]) if args.index("--fit") + 1 < len(args) and args[args.index("--fit") + 1][0].isdigit() else 0.1
        keep = [0, nb - 1]
        stack = [(0, nb - 1)]
        while stack:
            i0, i1 = stack.pop()
            if i1 <= i0 + 1: continue
            seg = pts[i0:i1 + 1]; ch = pts[i1] - pts[i0]; Lc = math.hypot(*ch)
            dd = np.abs((seg[:, 0] - pts[i0, 0]) * ch[1] - (seg[:, 1] - pts[i0, 1]) * ch[0]) / max(Lc, 1e-9)
            j = int(np.argmax(dd))
            if dd[j] > eps:
                keep.append(i0 + j); stack += [(i0, i0 + j), (i0 + j, i1)]
        keep = sorted(set(keep))
        print("  half-width knots (t: half, centre offset): " + "  ".join("%.2f: %.2f (%+.2f)" % (tt[i], half[i], ctr[i]) for i in keep))
    if "--colour" in args:
        # the colours across the object at places along it (t), from the low side to the high side every 0.2 units
        for tt in [float(v) for v in args[args.index("--colour") + 1].split(",")]:
            row = []
            for ss in np.arange(-5.0, 5.01, 0.2):
                pt = axis0 + u * (tmin + tt) + nv * ss
                x, y = int(pt[0] * K), int(pt[1] * K)
                if 0 <= x < a.shape[1] and 0 <= y < a.shape[0] and a[y, x, 3] > 127:
                    row.append("%+.1f:%02x%02x%02x" % (ss, int(a[y, x, 0]), int(a[y, x, 1]), int(a[y, x, 2])))
            print("  t %5.2f: %s" % (tt, " ".join(row)))
