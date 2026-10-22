"""The save editor icon: the cleaned holocron behind, the datapad (datapad.py's face and
wedge) placed, scaled and turned with the 3D viewer's exact camera and rotation order, at
the settings chosen in it. Then make_icons.py crops, centres and writes the app's files.

    python render_icon.py out.png [size]
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
OUT = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 1024

# The viewer's settings (copied from it, 2026-10-22).
YAW, UPDOWN, TILT, SIZE = -31, 46, 4, 52
POS_ACROSS, POS_UP = 0.17, -0.14

# The face, outline and wedge from datapad.py, run up to its 3D step.
src = (HERE / "datapad.py").read_text(encoding="utf-8")
cut = src.index("# ---------------------------------------------------------------- 3D, as datapad2.py")
ns = {"__name__": "final", "__file__": str(HERE / "datapad.py")}
sys_argv = sys.argv
sys.argv = ["datapad.py", str(HERE / "unused.png"), "1024"]
exec(compile(src[:cut], "datapad.py", "exec"), ns)
sys.argv = sys_argv
face, OUTLINE, FW, FH, TOP = ns["face"], ns["OUTLINE"], ns["FW"], ns["FH"], ns["TOP"]
THICK, THIN = 0.17, 0.045

# The viewer's camera: perspective, 30 degrees, at z = 4, looking down -z; square view.
deg = math.pi / 180
TANH = math.tan(15 * deg)
VIEW_W = 2 * TANH * 4.0
pos = np.array([POS_ACROSS * VIEW_W, POS_UP * VIEW_W, 0.0])
scale = SIZE / 58 * 0.95


def Rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# three.js Euler order ZYX: R = Rz(tilt) Ry(yaw) Rx(-updown).
R = Rz(TILT * deg) @ Ry(YAW * deg) @ Rx(-UPDOWN * deg)
SS = 2
W = N * SS


def model(px, py, z):
    return np.array([(px - FW / 2) / FW, -(py - FH / 2) / FW, z])


def world(p):
    return R @ (p * scale) + pos


def screen(p):
    q = world(p)
    zc = q[2] - 4.0                       # camera space (camera at z = 4)
    x = q[0] / (-zc) / TANH
    y = q[1] / (-zc) / TANH
    return ((x + 1) / 2 * W, (1 - y) / 2 * W)


def thick_at(py):
    t = min(max((py - TOP) / (FH - TOP), 0.0), 1.0)
    return THICK + (THIN - THICK) * t


F = [screen(model(x, y, 0)) for x, y in OUTLINE]
B = [screen(model(x, y, -thick_at(y))) for x, y in OUTLINE]
corners_px = [(0, 0), (FW, 0), (FW, FH), (0, FH)]
Q = [screen(model(x, y, 0)) for x, y in corners_px]

img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
# The holocron, where the viewer puts it: 2% from the left, 5.9% from the top, 84% wide.
holo = Image.open(HERE / "holocron-clean.png").convert("RGBA")
holo = holo.crop(holo.getbbox())
hw = round(0.84 * W)
holo = holo.resize((hw, round(holo.height * hw / holo.width)), Image.LANCZOS)
img.alpha_composite(holo, (round(0.02 * W), round(0.059 * W)))
# The pad's shadow on the holocron, then the pad.
sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
ImageDraw.Draw(sh).polygon([(x + 0.012 * W, y + 0.025 * W) for x, y in B], fill=(0, 0, 0, 150))
img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(0.02 * W)))
pad = Image.new("RGBA", img.size, (0, 0, 0, 0))
dp = ImageDraw.Draw(pad)
light = np.array([-0.4, 0.8, 0.5])
light /= np.linalg.norm(light)
n = len(OUTLINE)
for i in range(n):
    j = (i + 1) % n
    a0, a1 = model(*OUTLINE[i], 0), model(*OUTLINE[j], 0)
    normal = R @ np.cross(a1 - a0, (0, 0, -1))
    normal /= np.linalg.norm(normal) + 1e-9
    quad = [F[i], F[j], B[j], B[i]]
    area = 0.5 * sum(quad[k][0] * quad[(k + 1) % 4][1] - quad[(k + 1) % 4][0] * quad[k][1] for k in range(4))
    if area > 0:
        continue
    lum = 0.3 + 0.7 * max(0.0, float(np.dot(normal, light)))
    for t0, t1, col in ((0, 0.45, np.array((40, 44, 54))), (0.45, 1.0, np.array((16, 18, 24)))):
        qa = [tuple(np.array(quad[0]) + (np.array(quad[3]) - np.array(quad[0])) * t0),
              tuple(np.array(quad[1]) + (np.array(quad[2]) - np.array(quad[1])) * t0),
              tuple(np.array(quad[1]) + (np.array(quad[2]) - np.array(quad[1])) * t1),
              tuple(np.array(quad[0]) + (np.array(quad[3]) - np.array(quad[0])) * t1)]
        dp.polygon(qa, fill=tuple(int(v * lum) for v in col) + (255,))
    dp.line([F[i], F[j]], fill=(61, 127, 208, 255), width=SS * 2)


def coeffs(dst, srcp):
    A, b = [], []
    for (x, y), (u, v) in zip(dst, srcp):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.linalg.solve(np.array(A, float), np.array(b, float)).tolist()


warped = face.transform(img.size, Image.PERSPECTIVE, coeffs(Q, corners_px), Image.BICUBIC)
pad = Image.alpha_composite(pad, warped)
img = Image.alpha_composite(img, pad)
img = img.resize((N, N), Image.LANCZOS)
img.save(OUT)
print(OUT, img.size, "content", img.getbbox())
