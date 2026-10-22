"""The save editor icon's datapad: a KOTOR-style wedge slab in the holocron's colours
(obsidian, glowing blue cracks, an Aurebesh holo-screen), drawn from geometry, lit from a
height map and built in 3D. render_icon.py runs this up to its 3D step and places the
face with the angles chosen in the 3D viewer.

    python datapad.py out.png [size]      the datapad alone, at its own default angle
"""

import math
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = sys.argv[1]
SIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
from pathlib import Path as _Path
# Aurebesh AF Canon Tech by AurekFonts, CC0 public domain (its name table says so).
AUREBESH = str(_Path(__file__).resolve().parent / "AurebeshAF-CanonTech.otf")
rng = np.random.default_rng(11)

FW, FH = 2000, 1560                 # the face, landscape
TAB_W, TAB_H = 560, 170             # the handle tab on top, its slot cut through
TOP = TAB_H                         # the slab's top edge, below the tab
R = 120                             # corner radius


def arc(cx, cy, r, a0, a1, n=10):
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
            for a in np.linspace(a0, a1, n)]


def outline():
    """The slab with rounded corners and the handle tab, clockwise from the tab's left."""
    x0, y0, x1, y1 = 0, TOP, FW, FH
    tx0, tx1 = FW / 2 - TAB_W / 2, FW / 2 + TAB_W / 2
    pts = []
    pts += [(tx0 - 60, y0), (tx0, y0 - TAB_H + 50)] + arc(tx0 + 50, y0 - TAB_H + 50, 50, 180, 270, 6)
    pts += arc(tx1 - 50, y0 - TAB_H + 50, 50, 270, 360, 6) + [(tx1, y0 - TAB_H + 50), (tx1 + 60, y0)]
    pts += arc(x1 - R, y0 + R, R, 270, 360)
    pts += arc(x1 - R, y1 - R, R, 0, 90)
    pts += arc(x0 + R, y1 - R, R, 90, 180)
    pts += arc(x0 + R, y0 + R, R, 180, 270)
    return pts


OUTLINE = outline()
SLOT = (FW / 2 - TAB_W / 2 + 90, 45, FW / 2 + TAB_W / 2 - 90, 110)


def mask_of(poly):
    m = Image.new("L", (FW, FH), 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    return m


def brushed(base, spread, streak=70):
    n = rng.normal(0, 1, (FH, FW)).astype(np.float32)
    k = np.ones(streak, np.float32) / streak
    n = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, n)
    n /= n.std() + 1e-6
    n += rng.normal(0, 1, (FH, FW)).astype(np.float32) * 0.25
    rgb = np.clip(np.array(base, np.float32)[None, None, :] + n[..., None] * spread, 0, 255)
    return Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")


body_mask = mask_of(OUTLINE)
ImageDraw.Draw(body_mask).rounded_rectangle(SLOT, radius=30, fill=0)       # the slot is a hole
face = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
# Worn steel frame, lighter at the top.
steel = brushed((26, 28, 34), 4)
shade = Image.linear_gradient("L").resize((FW, FH))
steel = Image.composite(Image.new("RGBA", (FW, FH), (8, 9, 12, 255)), steel, shade.point(lambda v: int(v * 0.5)))
face.paste(steel, (0, 0), body_mask)
d = ImageDraw.Draw(face)
BRASS, BRASS_HI, BRASS_LO = (24, 70, 140, 255), (110, 190, 255, 255), (8, 22, 48, 255)
# Highlight along the top edges, shadow along the bottom (a rounded frame catching light).
d.line(OUTLINE[:len(OUTLINE) // 2 - 6], fill=(90, 150, 220, 200), width=6)
d.line(OUTLINE[len(OUTLINE) // 2 + 6:], fill=(4, 5, 8, 230), width=8)
d.rounded_rectangle(SLOT, radius=30, outline=(40, 38, 34, 255), width=8)

# The hinge bar: a cylinder along the top, left of the tab (the third reference).
hx0, hx1, hy = 130, FW / 2 - TAB_W / 2 - 110, TOP + 70
for k, col in enumerate(((8, 9, 12), (26, 30, 38), (52, 64, 82), (28, 32, 40), (10, 11, 14))):
    d.rounded_rectangle((hx0, hy - 38 + k * 15, hx1, hy - 38 + (k + 1) * 15 + 2), radius=6, fill=col + (255,))
for x in (hx0 + 40, hx1 - 40):
    d.ellipse((x - 22, hy - 22, x + 22, hy + 22), fill=BRASS)
    d.ellipse((x - 12, hy - 12, x + 12, hy + 12), fill=BRASS_LO)

# Side rails on the right edge (the game's datapad).
for k in range(3):
    y = 520 + k * 240
    d.rounded_rectangle((FW - 46, y, FW - 6, y + 150), radius=14, fill=(14, 16, 20, 255))
    d.line((FW - 46, y + 6, FW - 46, y + 144), fill=(80, 150, 230, 220), width=4)

# The screen bezel (dark, recessed) and the screen.
SX0, SY0, SX1, SY1 = 170, TOP + 180, FW - 170, FH - 150
d.rounded_rectangle((SX0 - 40, SY0 - 40, SX1 + 40, SY1 + 40), radius=60, fill=(16, 15, 14, 255))
d.rounded_rectangle((SX0 - 40, SY0 - 40, SX1 + 40, SY1 + 40), radius=60, outline=(40, 90, 170, 255), width=5)
smask = Image.new("L", (FW, FH), 0)
ImageDraw.Draw(smask).rounded_rectangle((SX0, SY0, SX1, SY1), radius=30, fill=255)
g = np.linspace(0, 1, SY1 - SY0)[:, None, None]
grad = (np.array((4, 16, 34))[None, None, :] * (1 - g) + np.array((10, 70, 140))[None, None, :] * g)
gl = Image.fromarray(np.broadcast_to(grad, (SY1 - SY0, SX1 - SX0, 3)).astype(np.uint8), "RGB").convert("RGBA")
screen = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
screen.paste(gl, (SX0, SY0))

content = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
c = ImageDraw.Draw(content)
CYAN, DIM, WHITE = (120, 220, 255, 255), (60, 150, 220, 220), (225, 245, 255, 255)
AMBER, GREEN = (90, 180, 255, 255), (200, 236, 255, 255)
# A cyan border box round the whole screen and a title rule (the game's datapad).
c.rounded_rectangle((SX0 + 30, SY0 + 30, SX1 - 30, SY1 - 30), radius=16, outline=CYAN, width=7)
tf = ImageFont.truetype(AUREBESH, 74)
c.text((SX0 + 80, SY0 + 55), "KOTOR SAVE", font=tf, fill=CYAN)
c.line((SX0 + 60, SY0 + 160, SX1 - 60, SY0 + 160), fill=DIM, width=5)
# Left: a circular gauge with tick marks, echoing the holocron's rings.
cx, cy, r = SX0 + 330, SY0 + 470, 220
c.ellipse((cx - r, cy - r, cx + r, cy + r), outline=CYAN, width=8)
c.ellipse((cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62), outline=DIM, width=6)
for k in range(36):
    a = 2 * math.pi * k / 36
    r0 = r * (1.08 if k % 3 else 1.04)
    c.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r * 1.16 * math.cos(a), cy + r * 1.16 * math.sin(a)),
           fill=DIM, width=5)
c.arc((cx - r * 0.82, cy - r * 0.82, cx + r * 0.82, cy + r * 0.82), 200, 330, fill=AMBER, width=14)
c.line((cx - r * 1.05, cy + r * 0.3, cx + r * 1.05, cy - r * 0.3), fill=DIM, width=5)
for a, rad, s in ((-0.3, r, 20), (2.6, r, 16), (1.0, r * 0.62, 13), (0, 0, 22)):
    px, py = cx + rad * math.cos(a), cy + rad * math.sin(a)
    c.ellipse((px - s, py - s, px + s, py + s), fill=WHITE)
# Right: an amber panel with a notched corner, green Aurebesh inside (the concept art).
px0, py0, px1, py1 = SX0 + 660, SY0 + 220, SX1 - 70, SY1 - 70
panel = [(px0 + 60, py0), (px1, py0), (px1, py1), (px0, py1), (px0, py0 + 60)]
c.line(panel + [panel[0]], fill=AMBER, width=7)
c.rectangle((px0 + 90, py0 - 10, px0 + 330, py0 + 10), fill=AMBER)
sf = ImageFont.truetype(AUREBESH, 48)
y = py0 + 60
for t in ("REVAN", "LEVEL 20 JEDI", "EBON HAWK", "DANTOOINE", "TARIS", "KASHYYYK", "MANAAN", "KORRIBAN"):
    c.text((px0 + 50, y), t, font=sf, fill=GREEN)
    y += 70
# Glow, scanlines, glass sheen.
lit = Image.alpha_composite(content.filter(ImageFilter.GaussianBlur(9)), content)
screen = Image.alpha_composite(screen, lit)
scan = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
sd = ImageDraw.Draw(scan)
for yy in range(SY0, SY1, 9):
    sd.line((SX0, yy, SX1, yy), fill=(0, 0, 0, 40), width=3)
screen = Image.alpha_composite(screen, scan)
sheen = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
ImageDraw.Draw(sheen).polygon([(SX0, SY0), (SX0 + 900, SY0), (SX0, SY0 + 620)], fill=(255, 255, 255, 20))
screen = Image.alpha_composite(screen, sheen.filter(ImageFilter.GaussianBlur(8)))
face.paste(screen, (0, 0), smask)

# Bottom deck: three brass-ringed keys and an amber light below the screen.
for x in (FW / 2 - 200, FW / 2, FW / 2 + 200):
    y = FH - 75
    d.ellipse((x - 46, y - 46, x + 46, y + 46), fill=BRASS)
    d.ellipse((x - 36, y - 36, x + 36, y + 36), fill=(26, 25, 23, 255))
    d.arc((x - 36, y - 36, x + 36, y + 36), 200, 330, fill=(70, 120, 190, 255), width=5)
d.ellipse((FW - 260, FH - 98, FW - 214, FH - 52), fill=BRASS)
d.ellipse((FW - 252, FH - 90, FW - 222, FH - 60), fill=(140, 210, 255, 255))

# Wear: scuffs and scratches on the frame, grime in the corners.
wear = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
wd = ImageDraw.Draw(wear)
for _ in range(420):
    x, y = rng.uniform(20, FW - 20), rng.uniform(20, FH - 20)
    a, L = rng.uniform(0, math.pi), rng.uniform(15, 120)
    col = (120, 150, 190, int(rng.uniform(15, 45))) if rng.random() < 0.5 else (0, 0, 0, int(rng.uniform(50, 110)))
    wd.line((x, y, x + L * math.cos(a), y + L * math.sin(a)), fill=col, width=int(rng.choice((2, 3, 4))))
frame_only = ImageChops.subtract(body_mask, smask.filter(ImageFilter.MaxFilter(91)))
face.paste(Image.alpha_composite(face, wear), (0, 0), frame_only)
edge = body_mask.filter(ImageFilter.GaussianBlur(45))
grime = np.clip((255 - np.asarray(edge, np.float32)) * 1.5, 0, 150) * (np.asarray(body_mask, np.float32) / 255)
gl2 = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
gl2.putalpha(Image.fromarray(grime.astype(np.uint8)))
face = Image.alpha_composite(face, gl2)
# The holocron's cracks: polygon cells over the frame, thin blue lines that glow.
from scipy.spatial import Voronoi
pts = np.column_stack([rng.uniform(-200, FW + 200, 70), rng.uniform(-200, FH + 200, 70)])
vor = Voronoi(pts)
cracks = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
cd = ImageDraw.Draw(cracks)
for a, b in vor.ridge_vertices:
    if a < 0 or b < 0:
        continue
    (x0, y0), (x1, y1) = vor.vertices[a], vor.vertices[b]
    cd.line((x0, y0, x1, y1), fill=(70, 160, 255, int(rng.uniform(110, 220))), width=int(rng.choice((3, 4, 5))))
cracks = Image.alpha_composite(cracks.filter(ImageFilter.GaussianBlur(7)), cracks)
face.paste(Image.alpha_composite(face, cracks), (0, 0), frame_only)
# The holocron's under-glow: blue light rising from the bottom of the frame.
glow = np.clip((np.arange(FH)[:, None] - FH * 0.62) / (FH * 0.38), 0, 1) ** 2
gl3 = Image.new("RGBA", (FW, FH), (60, 140, 255, 0))
gl3.putalpha(Image.fromarray((np.broadcast_to(glow, (FH, FW)) * 120).astype(np.uint8)))
face.paste(Image.alpha_composite(face, gl3), (0, 0), frame_only)
face.putalpha(ImageChops.multiply(face.getchannel("A"), body_mask))

# ---------------------------------------------------------------- relief and light
# A height map of the face (units are pixels of height), its normals, and light from the
# upper left: the frame a rounded rim, the screen sunk in its bezel, keys as domes, the
# hinge a cylinder, the rails raised. The screen glows by itself (only a glass highlight).
from scipy.ndimage import distance_transform_edt, gaussian_filter


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


bm = np.asarray(body_mask) > 127
h = 34 * smooth(distance_transform_edt(bm) / 80.0)                   # rounded outer edge
bez = np.zeros((FH, FW), bool)
bez[SY0 - 40:SY1 + 40, SX0 - 40:SX1 + 40] = True
h -= 22 * smooth(distance_transform_edt(bez) / 30.0)                 # the bezel sinks
scr = np.asarray(smask) > 127
h -= 8 * smooth(distance_transform_edt(scr) / 12.0)                  # the glass a little lower
yy, xx = np.mgrid[0:FH, 0:FW]
for x in (FW / 2 - 200, FW / 2, FW / 2 + 200):                       # the keys: brass ring, dome
    r = np.hypot(xx - x, yy - (FH - 75))
    h += np.where(r < 46, 6, 0) + np.where(r < 36, 10 * np.sqrt(np.clip(1 - (r / 36) ** 2, 0, 1)), 0)
r = np.hypot(xx - (FW - 237), yy - (FH - 75))
h += np.where(r < 23, 8 * np.sqrt(np.clip(1 - (r / 23) ** 2, 0, 1)) + 4, 0)
band = (xx >= hx0) & (xx <= hx1) & (np.abs(yy - hy) <= 38)             # the hinge: a cylinder
h += np.where(band, 18 * np.sqrt(np.clip(1 - ((yy - hy) / 38.0) ** 2, 0, 1)), 0)
for k in range(3):                                                    # the rails
    y = 520 + k * 240
    rail = (xx >= FW - 46) & (yy >= y) & (yy <= y + 150)
    h += np.where(rail, 12, 0)
h += np.asarray(ImageChops.subtract(body_mask, smask), np.float32) / 255 * rng.normal(0, 0.25, (FH, FW))  # brushed grain
h = gaussian_filter(h, 1.5)
gy, gx = np.gradient(h)
n = np.dstack([-gx * 1.6, -gy * 1.6, np.ones_like(h)])
n /= np.linalg.norm(n, axis=2, keepdims=True)
L = np.array([-0.45, -0.62, 0.64]); L /= np.linalg.norm(L)
Hv = L + np.array([0, 0, 1.0]); Hv /= np.linalg.norm(Hv)
diff = np.clip((n * L).sum(2), 0, 1)
spec = np.clip((n * Hv).sum(2), 0, 1) ** 48
ao = 1 - np.clip((gaussian_filter(h, 22) - h) / 18.0, 0, 0.55)
rgba = np.asarray(face, np.float32)
lit_rgb = rgba[..., :3] * ((0.45 + 0.8 * diff) * ao)[..., None] + spec[..., None] * np.array((150, 190, 255))
glass = rgba[..., :3] + (spec * 70)[..., None]
inside = (np.asarray(smask, np.float32) / 255)[..., None]
rgba[..., :3] = np.clip(lit_rgb * (1 - inside) + glass * inside, 0, 255)
face = Image.fromarray(rgba.astype(np.uint8), "RGBA")

# ---------------------------------------------------------------- 3D, as datapad2.py
THICK = 0.17
YAW, PITCH, ROLL = math.radians(-20), math.radians(-46), math.radians(4)
CAM = 4.0
U = FW


def rot(p):
    x, y, z = p
    x, z = x * math.cos(YAW) + z * math.sin(YAW), -x * math.sin(YAW) + z * math.cos(YAW)
    y, z = y * math.cos(PITCH) - z * math.sin(PITCH), y * math.sin(PITCH) + z * math.cos(PITCH)
    x, y = x * math.cos(ROLL) - y * math.sin(ROLL), x * math.sin(ROLL) + y * math.cos(ROLL)
    return x, y, z


def proj(p):
    x, y, z = rot(p)
    f = CAM / (CAM - z)
    return x * f, y * f


def to3d(px, py, z):
    return ((px - FW / 2) / U, -(py - FH / 2) / U, z)


THIN = 0.045


def thick_at(py):
    """Thickness at face row py: THICK at the top edge, THIN at the bottom (a wedge)."""
    t = min(max((py - TOP) / (FH - TOP), 0.0), 1.0)
    return THICK + (THIN - THICK) * t


front = [proj(to3d(x, y, 0)) for x, y in OUTLINE]
back = [proj(to3d(x, y, -thick_at(y))) for x, y in OUTLINE]
corners_px = [(0, 0), (FW, 0), (FW, FH), (0, FH)]
corners = [proj(to3d(x, y, 0)) for x, y in corners_px]
allp = np.array(front + back)
lo, hi = allp.min(0), allp.max(0)
span = (hi - lo).max()
scale = SIZE * 0.86 / span
off = np.array([SIZE, SIZE]) / 2 - (lo + hi) / 2 * scale


def fixy(pts):
    return [(p[0] * scale + off[0], SIZE - (p[1] * scale + off[1])) for p in pts]


SS = 2
F, B, Q = ([(x * SS, y * SS) for x, y in fixy(v)] for v in (front, back, corners))
img = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
ImageDraw.Draw(sh).polygon([(x + 0.02 * SIZE * SS, y + 0.05 * SIZE * SS) for x, y in B], fill=(0, 0, 0, 160))
img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(0.03 * SIZE * SS)))
dimg = ImageDraw.Draw(img)
light = np.array([-0.4, 0.8, 0.5])
light /= np.linalg.norm(light)
n = len(OUTLINE)
for i in range(n):
    j = (i + 1) % n
    a0, a1 = np.array(to3d(*OUTLINE[i], 0)), np.array(to3d(*OUTLINE[j], 0))
    normal = np.array(rot(tuple(np.cross(a1 - a0, (0, 0, -1)))))
    normal /= np.linalg.norm(normal) + 1e-9
    quad = [F[i], F[j], B[j], B[i]]
    area = 0.5 * sum(quad[k][0] * quad[(k + 1) % 4][1] - quad[(k + 1) % 4][0] * quad[k][1] for k in range(4))
    if area > 0:
        continue
    lum = 0.3 + 0.7 * max(0.0, float(np.dot(normal, light)))
    # The sides: steel above, a bronze-brown base below (the concept art's body).
    top_col, base_col = np.array((40, 44, 54)), np.array((16, 18, 24))
    for t0, t1, col in ((0, 0.45, top_col), (0.45, 1.0, base_col)):
        qa = [tuple(np.array(quad[0]) + (np.array(quad[3]) - np.array(quad[0])) * t0),
              tuple(np.array(quad[1]) + (np.array(quad[2]) - np.array(quad[1])) * t0),
              tuple(np.array(quad[1]) + (np.array(quad[2]) - np.array(quad[1])) * t1),
              tuple(np.array(quad[0]) + (np.array(quad[3]) - np.array(quad[0])) * t1)]
        dimg.polygon(qa, fill=tuple(int(v * lum) for v in col) + (255,))


def coeffs(dst, src):
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.linalg.solve(np.array(A, float), np.array(b, float)).tolist()


warped = face.transform(img.size, Image.PERSPECTIVE, coeffs(Q, corners_px), Image.BICUBIC)
img = Image.alpha_composite(img, warped)
img = img.resize((SIZE, SIZE), Image.LANCZOS)
img = img.crop(img.getbbox())
canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
k = SIZE * 0.96 / max(img.size)
img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
canvas.alpha_composite(img, ((SIZE - img.width) // 2, (SIZE - img.height) // 2))
canvas.save(OUT)
print(OUT, canvas.size)
