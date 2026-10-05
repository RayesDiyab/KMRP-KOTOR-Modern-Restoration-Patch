#!/usr/bin/env python3
"""The Xbox-style HUD's frames, drawn from scratch at four times the game's size.

The Xbox-style HUD (tools/build_xbox_hud.py, K1XboxHud.cpp) was dressed in the game's
own HUD textures, which are 16 to 256 pixels across and are stretched over a modern
screen: soft lines, stair-stepped curves. The maintainer asked for a crisp HUD
(2026-10-05), looked at upscalers and rejected them, and chose redrawing.

So every frame here is a DRAWING, not a copy: each of the game's textures was measured
row by row and is described below as geometry (lines, arcs, polygons) in the game
texture's own pixel units, in the game's colours, and rendered at 4x with each pixel
from 4x4 samples. Nothing is read from the game when this runs and no game art is
shipped, so the patch may carry the result.

The drawings have names of their own (`NAMES`: lbl_mibox01 -> kmrx_mibox01), so the
game's textures stay what they are for the PC HUD and for any other mod, and the
Xbox HUD's table and module ask for the new names.

Icons are not here, by the maintainer's decision the same day: every action, feat and
power icon stays the game's own (i_noaction included). Nor is lbl_miscroll_f / _h, the
round box the engine gives a target's slots: the Xbox HUD puts the slot box there instead.

Usage:
    python tools/build_xbox_hud_art.py OUT_DIR      write the drawings as PNG, to look at

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

SCALE, SAMPLES = 4, 4          # drawn at 4x, each output pixel from 4x4 samples
BLACK = (0, 0, 0)
# The game's colours, read from its textures (medians of their opaque bright pixels).
BLUE = (82, 118, 255)
YELLOW = (255, 255, 0)
ARROW_BLUE, ARROW_YELLOW = (82, 117, 251), (251, 251, 0)
RED, GREEN, FORCE = (255, 0, 0), (0, 212, 0), (148, 186, 255)
COMBAT = (189, 28, 0)
CURVE = (82, 117, 247)

PREFIX = "kmrx_"
TXI = b"clamp 3\r\n"      # what the engine reads beside each texture (see build())


def hd_name(game_name: str) -> str:
    """The drawing's name for one of the game's textures, or the name itself when it has none."""
    return NAMES.get(game_name, game_name)


class Canvas:
    """A texture being drawn, `width` x `height` in the game texture's pixels."""

    def __init__(self, width: int, height: int):
        import numpy as np

        self.np = np
        self.w, self.h = width, height
        n = SCALE * SAMPLES
        self.ys, self.xs = (np.mgrid[0:height * n, 0:width * n] + 0.5) / n
        self.rgb = np.zeros((height * SCALE, width * SCALE, 3), np.float32)
        self.alpha = np.zeros((height * SCALE, width * SCALE), np.float32)

    def polygon(self, points, grow: float = 0.0):
        """A polygon as a yes/no shape; `grow` widens it all round, corners rounded."""
        from PIL import Image, ImageDraw

        n = SCALE * SAMPLES
        image = Image.new("L", (self.w * n, self.h * n), 0)
        scaled = [(x * n, y * n) for x, y in points]
        draw = ImageDraw.Draw(image)
        draw.polygon(scaled, fill=255)
        if grow > 0:
            draw.line(scaled + [scaled[0]], fill=255, width=int(round(2 * grow * n)), joint="curve")
            r = grow * n
            for x, y in scaled:
                draw.ellipse((x - r, y - r, x + r, y + r), fill=255)
        return self.np.asarray(image) > 127

    def paint(self, shape, colour, opacity: float = 1.0) -> None:
        np = self.np
        cover = shape.reshape(self.h * SCALE, SAMPLES, self.w * SCALE, SAMPLES).mean(axis=(1, 3)).astype(np.float32) * opacity
        self.rgb = self.rgb * (1 - cover[..., None]) + np.asarray(colour, np.float32) * cover[..., None]
        self.alpha = self.alpha + cover * (1 - self.alpha)

    def image(self):
        from PIL import Image

        np = self.np
        return Image.fromarray(np.dstack([self.rgb, self.alpha * 255]).round().astype(np.uint8), "RGBA")


# ---- the action slot's box (lbl_mibox01; lbl_mibox02 when the slot is chosen)
# A barrel: a straight line across the top and the bottom, one pixel thick, and sides
# that bow outwards. Measured: the lines at y 12..13 and 46..47; the side's outer edge
# at x 10.0 in the middle and 14.3 where it meets the lines, on 10.0 + 0.00105 *
# |y - 29.5| ** 3. The game's sides are 2.1 thick; at full sharpness that looked heavy
# beside the one-pixel lines, so they are 1.8. The game's yellow box sits a pixel lower
# than its blue one and is a little thinner; both are this one shape here, so that a
# slot does not jump when it is chosen.
def slot_box(colour):
    c = Canvas(64, 64)
    np = c.np
    dy = c.ys - 29.5
    bow = 10.0 + 0.00105 * np.abs(dy) ** 3
    lean = np.sqrt(1 + (3 * 0.00105 * dy ** 2) ** 2)       # the thickness is across the side, not along the row
    mirror = np.minimum(c.xs, 63.0 - c.xs)
    outer = (np.abs(dy) <= 17.5) & (mirror >= bow)
    inner = (np.abs(dy) <= 16.5) & (mirror >= bow + 1.8 * lean)
    c.paint(outer & ~inner, colour)
    return c.image()


# ---- the two arrows beside a slot (lbl_miarrow01, lbl_miarrow02): one pointing up at
# the top of the strip, one pointing down at the bottom. An arrowhead on a short stem,
# in a black outline two pixels wide around the head and one under it.
def slot_arrows(colour):
    c = Canvas(16, 64)
    head = [(8.15, 3.9), (13.3, 9.05), (13.3, 10.0), (3.0, 10.0), (3.0, 9.05)]
    stem = [(6.3, 9.9), (10.0, 9.9), (10.0, 12.0), (6.3, 12.0)]
    for down in (False, True):
        place = (lambda points: [(x, 61.0 - y) for x, y in points]) if down else (lambda points: points)
        outline = c.polygon(place(head), grow=1.9)
        limit = (c.ys >= 49.9) if down else (c.ys <= 11.1)     # the outline stops a pixel past the wings
        c.paint((outline & limit) | c.polygon(place(stem), grow=0.4), BLACK)
        c.paint(c.polygon(place(head)) | c.polygon(place(stem)), colour)
    return c.image()


# ---- the minimap's frame (lbl_minimap): a square line 1.4 thick, from 2.6 to 61.4
def minimap_frame():
    c = Canvas(64, 64)
    np = c.np
    far = np.maximum(np.abs(c.xs - 32.0), np.abs(c.ys - 32.0))
    c.paint((far <= 29.4) & (far >= 28.0), BLUE)
    return c.image()


# ---- a portrait's frame (lbl_miport): a black panel between two bright sides shaped
# like lenses, a line across the top and the bottom, all in a black outline. The
# lens's outer edge runs from x 7.3 at the corners out to 3.3 in the middle, on
# 3.3 + 0.00213 * |y - 32| ** 2.3.
#
# The game's two lines are one pixel thick, and its layout puts each portrait a
# fraction of a unit off the panel, differently for each of the three: one portrait
# had a black strip under it, another beside it, the leader's none (the maintainer saw
# it, 2026-10-05). Here the lines are three pixels thick, reaching inwards, and the
# module puts each frame around its portrait itself (K1XboxHud.cpp, FramePortraits, by
# PORTRAIT_INSET below): above and below, the portrait's edge falls in the middle of
# the line, so it is edged in blue whatever the screen's size rounds to. At the sides
# a black hairline stands between the picture and each lens, as on the Xbox (the
# maintainer's direction, the same day, from a picture of the Xbox game: with the
# portrait reaching into the lenses the arcs sat on the picture). The hairline is
# drawn here, HAIRLINE wide, from the frame's outline at the top to its outline at the
# bottom, so that it joins the lens's own black edge at both ends (he asked for that
# too): the two blue lines run only between the hairlines, over the picture's width.
HAIRLINE = 0.7
PORTRAIT_INSET = (8.25 + HAIRLINE, 3.5)   # where a portrait's side edge goes; the middle of the top line. Of the texture's 64.


def portrait_frame():
    c = Canvas(64, 64)
    np = c.np
    dy = np.abs(c.ys - 32.0)
    lens = np.minimum(3.3 + 0.00213 * dy ** 2.3, 7.3)
    mirror = np.minimum(c.xs, 64.0 - c.xs)
    c.paint((dy <= 31.0) & (mirror >= lens - 1.1), BLACK)
    sides = (dy <= 30.0) & (mirror >= lens) & (mirror <= 8.25)
    lines = (dy <= 30.0) & (dy >= 27.0) & (mirror >= 8.25 + HAIRLINE)
    c.paint(sides | lines, (82, 121, 255))
    return c.image()


# ---- a bar beside a portrait (lbl_health, lbl_healthp, lbl_force; lbl_health2 and
# lbl_force2 the same shape, empty): a band seven pixels wide, bowed like the
# portrait's lens, outlined. In the game's art its left edge runs on 1.0 + 0.00384 *
# |y - 32| ** 2.25, which leaves the outline at the arc's widest cut by the texture's
# side; the module used to draw that edge a second time to mend it. Here the arc is
# half a pixel further in, so its outline is whole. The force bar is its mirror image.
# The empty bar is the same outline around a half-opaque band.
def bar(colour, mirrored: bool):
    c = Canvas(16, 64)
    np = c.np
    x = (16.0 - c.xs) if mirrored else c.xs
    dy = np.abs(c.ys - 32.0)
    left = 1.5 + 0.00384 * dy ** 2.25
    outline = (dy <= 31.0) & (x >= left - 1.45) & (x <= left + 8.45)
    band = (dy <= 30.0) & (x >= left) & (x <= left + 7.0)
    # The empty bar has the black outline too, around a half-opaque band. The filling is
    # drawn over it only as high as the bar is full, so an empty bar that was the bare
    # shade lost its outline from the top down as a character was hurt (the maintainer
    # saw it, 2026-10-05).
    c.paint(outline & ~band, BLACK)
    c.paint(band, BLACK, 0.5) if colour is None else c.paint(band, colour)
    return c.image()


# ---- the description box's two ends (lbl_mitextbox its top, lbl_mitextbox2 its
# bottom): a dark panel, four fifths opaque, in a thin bright line with two soft
# corners, outlined in black. The corners are not quarter circles: they follow
# |dx / rx| ** 1.35 + |dy / ry| ** 1.35 = 1.
def _cap(c, y, left, top, rx, ry):
    np = c.np
    m = np.abs(c.xs - 116.5)
    half = 116.5 - left
    dx = np.clip(m - (half - rx), 0, None) / rx
    dy = np.clip((top + ry) - y, 0, None) / ry
    return (y >= top) & (m <= half) & (dx ** 1.35 + dy ** 1.35 <= 1.0)


def text_box(bottom: bool):
    c = Canvas(256, 32 if bottom else 64)
    y = (18.0 - c.ys) if bottom else c.ys                  # the bottom end is the top end, upside down
    outer = _cap(c, y, 3.0, 1.0 if bottom else 2.0, 5.5, 10.5)
    line_out = _cap(c, y, 5.0, 3.0, 5.0, 9.5)
    line_in = _cap(c, y, 6.0, 4.5, 5.7, 10.5)
    c.paint(outer & ~line_out, BLACK)
    c.paint(line_in, BLACK, 0.8)
    c.paint(line_out & ~line_in, (82, 117, 255))
    return c.image()


# ---- the target's name bar (lbl_miindic01f, and lbl_miindic01e for an enemy): a long
# box, half opaque inside, a thin line above and below, thick sides that bulge a
# little, a second thin line across near the bottom, outlined.
def target_bar(colour):
    c = Canvas(256, 64)
    np = c.np
    xm = 126.7 - np.abs(c.xs - 126.7)                      # folded: the right half is the left's mirror
    dy = np.abs(c.ys - 31.5)
    left = 6.7 + 0.115 * np.clip(dy - 11.0, 0, None) ** 1.6
    box = (dy <= 18.5) & (xm >= left)
    inside = (dy <= 17.5) & (xm >= 10.2)
    line = box & ((xm <= 10.2) | (dy >= 17.5) | ((c.ys >= 39.0) & (c.ys <= 40.0)))
    c.paint((dy <= 19.5) & (xm >= left - 1.0) & ~inside, BLACK)
    c.paint(inside, BLACK, 0.5)
    c.paint(line, colour)
    return c.image()


# ---- the combat queue's frame (lbl_micombat): a bar that points, with a chevron, into
# a barrel-shaped box.
def combat_frame():
    c = Canvas(128, 64)
    np = c.np
    dy = c.ys - 30.5
    reach = np.abs(dy) / 17.0
    bow = 4.7 * reach ** 2.7
    m = np.abs(c.xs - 100.5)
    box_out = (np.abs(dy) <= 17.5) & (m <= 21.5 - bow)
    box_in = (np.abs(dy) <= 16.5) & (m <= 21.5 - bow - 1.6 * np.sqrt(1 + (4.7 * 2.7 / 17.0 * reach ** 1.7) ** 2))
    box_dark = (np.abs(dy) <= 18.6) & (m <= 21.5 - bow + 1.5)
    bar_out = (c.xs >= 7.0) & (c.xs <= 76.0) & (np.abs(dy) <= 10.5)
    bar_in = (c.xs >= 8.1) & (c.xs <= 76.0) & (np.abs(dy) <= 9.5)
    bar_dark = (c.xs >= 6.0) & (c.xs <= 77.0) & (np.abs(dy) <= 11.5)
    # the chevron: a band ten wide, bent to point right, its tip at x 73; and the small triangle in its notch
    bend = 73.0 - 7.0 * np.abs(dy) / 8.5
    chevron = (np.abs(dy) <= 9.5) & (c.xs >= bend) & (c.xs <= bend + 10.0) & (c.xs <= 100.5 - (21.5 - bow) + 1.0)
    thick = ((np.abs(dy) <= 10.5) & (np.abs(dy) >= 9.5 - np.clip((c.xs - 55.0) / 11.0, 0, 1))
             & (c.xs >= 55.0) & (c.xs <= bend + 10.0))
    small = c.polygon([(66.0, 25.8), (71.2, 30.5), (66.0, 35.2)])
    c.paint((box_dark & ~box_in) | (bar_dark & ~bar_in), BLACK)
    c.paint(box_in | bar_in, BLACK, 0.5)
    c.paint((box_out & ~box_in) | (bar_out & ~bar_in & (c.xs <= 74.5)) | chevron | thick | small, COMBAT)
    return c.image()


# ---- the curve that joins the party's portraits (lbl_micurve): a blade with a small
# hook, outlined. Its edge is given as points between the game's pixels (True: a
# corner), joined by a smooth curve through the others.
CURVE_EDGE = [
    (22.0, 3.0, True), (23.0, 4.5, False), (24.0, 7.5, False), (24.8, 10.5, False), (25.3, 13.5, False),
    (25.7, 16.5, False), (26.1, 19.5, False), (26.35, 24.5, False), (26.5, 28.0, False), (26.5, 31.0, False),
    (26.2, 34.0, False), (25.6, 36.5, False), (24.8, 39.5, False), (24.2, 42.0, True),
    (26.3, 44.0, True), (26.3, 46.4, True),
    (25.3, 47.6, False), (23.7, 49.6, False), (21.7, 51.6, False), (18.3, 54.5, False), (14.3, 57.4, False),
    (11.2, 59.4, False), (8.1, 60.6, False), (5.3, 61.6, False), (3.5, 62.5, True),
    (3.9, 60.6, False), (5.7, 59.4, False), (7.6, 57.5, False), (10.3, 54.5, False), (12.6, 51.0, False),
    (14.3, 48.4, False), (15.8, 45.4, False), (17.4, 42.4, False), (18.7, 39.5, False), (19.7, 36.5, False),
    (20.5, 33.5, False), (21.2, 30.0, False), (21.7, 26.0, False), (22.0, 22.0, False), (22.2, 18.0, False),
    (22.1, 14.0, False), (21.7, 10.0, False), (21.2, 6.5, False), (21.3, 4.2, False),
]


def _smooth(points):
    """Catmull-Rom through the smooth points, straight into and out of the corners."""
    import numpy as np

    start = next(i for i, p in enumerate(points) if p[2])
    ordered = points[start:] + points[:start] + [points[start]]
    out, run = [], [ordered[0]]
    for p in ordered[1:]:
        run.append(p)
        if not p[2]:
            continue
        xy = np.array([(q[0], q[1]) for q in run], np.float64)
        if len(xy) == 2:
            out.append(tuple(xy[0]))
        else:
            ext = np.vstack([2 * xy[0] - xy[1], xy, 2 * xy[-1] - xy[-2]])
            for i in range(1, len(ext) - 2):
                p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
                for t in np.linspace(0, 1, 24, endpoint=False):
                    out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                            + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)))
        run = [p]
    return out


def curve():
    c = Canvas(32, 64)
    blade = _smooth(CURVE_EDGE)
    c.paint(c.polygon(blade, grow=2.0), BLACK)
    c.paint(c.polygon(blade), CURVE)
    return c.image()


# The game's texture -> how its drawing is made.
DRAWN = {
    "lbl_mibox01": lambda: slot_box(BLUE),
    "lbl_mibox02": lambda: slot_box(YELLOW),
    "lbl_miarrow01": lambda: slot_arrows(ARROW_BLUE),
    "lbl_miarrow02": lambda: slot_arrows(ARROW_YELLOW),
    "lbl_minimap": minimap_frame,
    "lbl_miport": portrait_frame,
    "lbl_health": lambda: bar(RED, False),
    "lbl_healthp": lambda: bar(GREEN, False),
    "lbl_health2": lambda: bar(None, False),
    "lbl_force": lambda: bar(FORCE, True),
    "lbl_force2": lambda: bar(None, True),
    "lbl_mitextbox": lambda: text_box(False),
    "lbl_mitextbox2": lambda: text_box(True),
    "lbl_miindic01f": lambda: target_bar((82, 117, 255)),
    "lbl_miindic01e": lambda: target_bar(RED),
    "lbl_micombat": combat_frame,
    "lbl_micurve": curve,
}
NAMES = {name: PREFIX + name[len("lbl_"):] for name in DRAWN}


def tga(game_name: str) -> bytes:
    """A drawing as the patch's other textures are: 32-bit, uncompressed, rows from the bottom."""
    image = DRAWN[game_name]()
    width, height = image.size
    b, g, r, a = (image.getchannel(ch).transpose(1) for ch in "BGRA")      # 1: FLIP_TOP_BOTTOM
    from PIL import Image

    rows = Image.merge("RGBA", (b, g, r, a)).tobytes()                       # the bytes in B, G, R, A order
    return struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 8) + rows


def build(out: Path) -> list[Path]:
    """Write every drawing into `out` under its own name. Returns the paths."""
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for game_name in DRAWN:
        path = out / (NAMES[game_name] + ".tga")
        path.write_bytes(tga(game_name))
        paths.append(path)
        # The engine repeats a texture past its edge, and it makes smaller copies of a
        # TGA for drawing it small: in those, a frame's last row was mixed with its
        # first, and the description box showed a dark seam where its two ends meet
        # (seen in the scratch game, 2026-10-05). "clamp 3" stops the repeat both ways.
        info = out / (NAMES[game_name] + ".txi")
        info.write_bytes(TXI)
        paths.append(info)
    return paths


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    for game_name, make in DRAWN.items():
        make().save(target / (NAMES[game_name] + ".png"))
    print(f"{len(DRAWN)} drawings in {target}")
