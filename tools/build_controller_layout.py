#!/usr/bin/env python3
"""Author the Controller Layout screen: a real controller diagram with callouts.

The screen is built from the game's own GUI controls, so it scales, focuses and
closes like any other KOTOR panel. What it draws:

  * a controller diagram in the middle of a 760x380 board, from Xelu's CC0 pack,
    with each family's own face-button glyphs composited onto it;
  * leader lines, baked into the same texture, from every button to its row;
  * one row per button: an engine-drawn glyph and an engine-drawn caption, so the
    text is crisp in-game type rather than pixels in a bitmap, and the glyph still
    follows the controller family at run time.

The row positions are solved once, in `rows()`, and used by BOTH the texture and
the GUI. That is the whole alignment contract: the texture is stretched across
the board control, the board shares the design space with the rows, and so the
line ends land on the glyphs at every one of the 48 resolutions.

Captions describe the NATIVE controller path as it ships, read from
`K1_GAMEPLAY_ACTIONS`, `K1_BUTTONS` and `K1_STICK_CLICKS` in
`src/controller-native/K1NativeJoystick.cpp` -- not from the legacy key table in
`docs/controller-support.md`, which describes a different path and disagrees
with it (LB/RB cycle targets here, View is solo mode, Start opens the Map).
The captions are plain ASCII because the menu face, Old Republic, has 95
printable-ASCII glyphs and nothing else.
"""
from __future__ import annotations

import copy
import struct
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from pykotor.common.misc import ResRef
from utility.common.geometry import Vector3
from pykotor.resource.formats.gff import GFFList, read_gff, write_gff

import controller_layout_backdrop as backdrop
from build_controller_prompt_textures import (
    FAMILY_LETTERS, GLYPH_FAMILIES, GLYPH_PACK, TGA_FOOTER, _load_glyph_art,
    build_square_glyph_tga, measure_label, parse_font_metrics)


# ---------------------------------------------------------------- the content

# (glyph, caption, side, anchor). Side is L or R for the two callout columns, or
# T for the centre pair above the controller. View and Menu sit between the
# sticks, so a line from either column to them has to cross a stick; measured
# across every row order, the left column could not get below one line through
# a foreign button until they were moved out of it.
#
# Glyph names are the prompt vocabulary shared
# with the HUD badges; the anchor names a point on the silhouette below. Order is
# the order of the GLYPH_nn / TEXT_nn controls, which the runtime binds by tag.
LAYOUT = [
    ("LT",     "Switch ally / Prev tab",    "L", "LT"),
    ("LB",     "Previous target",           "L", "LB"),
    ("BACK",   "Solo mode",                 "T", "BACK"),
    ("LSTICK", "Move / Click: flourish",    "L", "LSTICK"),
    ("DPAD",   "Action bar / Navigate",     "L", "DPAD"),
    ("RT",     "Pause / Next tab",          "R", "RT"),
    ("RB",     "Next target",               "R", "RB"),
    ("START",  "Map / Close menu",          "T", "START"),
    # In combat, Y removes the last queued action and X disengages (the HUD's
    # own clear buttons); in menus each screen gives them its own meaning.
    ("Y",      "Undo action / Menu action", "R", "Y"),
    ("X",      "Disengage / Menu action",   "R", "X"),
    ("B",      "Back / Release bar",        "R", "B"),
    ("A",      "Interact / Select",         "R", "A"),
    ("RSTICK", "Camera / Click: free look", "R", "RSTICK"),
]

# Kept under this name: the regression and the prompt builder import it.
MAPPINGS = [(glyph, caption) for glyph, caption, _, _ in LAYOUT]

# The runtime binds GLYPH_nn and TEXT_nn by tag and must know how many there
# are: K1_LAYOUT_ROWS in src/controller-native/K1ControllerLayout.cpp.
# Test-ControllerPromptAssets.py fails the build if the two disagree.
ROWS = len(LAYOUT)


# ---------------------------------------------------------------- the art

# Two silhouettes ship with a plain, unlabelled variant: Xbox Series X and PS5,
# 1452x940 each. Switch and Steam Deck have no diagram in the pack at all, so
# they use the Xbox silhouette with their own glyphs on the face buttons. A Deck
# is physically a handheld with trackpads; this is the honest nearest drawing,
# not a picture of one.
SILHOUETTES = {
    "xbox":        ("Xbox/XboxSeriesX_Diagram_Simple.png", "xbox"),
    "playstation": ("PS5/PS5_Diagram_Simple.png",          "ps5"),
    "switch":      ("Xbox/XboxSeriesX_Diagram_Simple.png", "xbox"),
    "steamdeck":   ("Xbox/XboxSeriesX_Diagram_Simple.png", "xbox"),
}
SOURCE_SIZE = (1452, 940)

# Button positions in the 1452x940 source, read off a gridded render of each
# silhouette. `glyph` entries also say how large a glyph to composite there.
ANCHORS = {
    "xbox": {
        "LT": (360, 70),   "LB": (300, 150),  "RT": (1095, 70),  "RB": (1150, 150),
        "BACK": (630, 410), "START": (832, 410),
        "LSTICK": (318, 400), "L3": (375, 425), "RSTICK": (915, 622),
        "DPAD": (550, 615),
        "Y": (1093, 318), "X": (995, 408), "B": (1186, 402), "A": (1088, 492),
    },
    "ps5": {
        "LT": (320, 95),   "LB": (300, 205),  "RT": (1130, 95),  "RB": (1150, 205),
        "BACK": (410, 310), "START": (1045, 310),
        "LSTICK": (470, 630), "L3": (525, 640), "RSTICK": (930, 630),
        "DPAD": (310, 445),
        "Y": (1155, 355), "X": (1052, 450), "B": (1255, 448), "A": (1152, 530),
    },
}
# Glyphs composited onto the silhouette, and their size in source pixels.
# View and Menu are too small on the silhouette for their glyphs to read; the
# row glyph beside the caption shows them instead.
FACE_GLYPHS = {"A": 88, "B": 88, "X": 88, "Y": 88}

# Where a leader stops short of its anchor, in source pixels. A line to a face
# button ends at its rim rather than its centre, or the dot covers the letter.
STOP = {"A": 48, "B": 48, "X": 48, "Y": 48}

# How close another control's line may pass, in source pixels: roughly each
# control's drawn radius. A line through a button that is not its own reads as
# pointing at that button, which is worse than two lines crossing.
KEEPOUT = {"A": 45, "B": 45, "X": 45, "Y": 45, "BACK": 34, "START": 34,
           "LSTICK": 72, "L3": 72, "RSTICK": 72, "DPAD": 78,
           "LT": 40, "RT": 40, "LB": 40, "RB": 40}
# Controls that share a physical part and so may carry lines to the same place.
# Empty since the left stick became one row, "Move / Click: flourish", like the
# right stick's "Camera / Click: free look": two rows on one stick put three
# lines into the same small region beside the inboard D-pad, and no row order
# on the Xbox silhouette could keep them from crossing.
SAME_CONTROL: set = set()

# The design space every layout coordinate lives in, and the board inside it.
DESIGN_W = 760
BOARD = (0, 84, 760, 380)                 # left, top, width, height
DIAGRAM_W = 340                           # source 1452 wide -> 340 design units
DIAGRAM_X = (DESIGN_W - DIAGRAM_W) / 2
DIAGRAM_Y = 110                           # leaves the top band for the centre row
SCALE = DIAGRAM_W / SOURCE_SIZE[0]        # design units per source pixel

GLYPH = 30                                # glyph control, design units
LEFT_GLYPH_X = 172                        # left column glyph box
RIGHT_GLYPH_X = 558                       # right column glyph box
CAPTION_W = 166                           # the least a caption box is given
BEND_INSET = 12                           # how far past the glyph the line runs flat
ROW_TOP, ROW_BOTTOM = 30, 350             # each column spreads over this band
EDGE_GAP = 14                             # captions stop this far from the screen edge
TOP_ROW_Y = 52                            # the centre pair, above the triggers
TOP_GLYPH_X = {"BACK": 300, "START": 430} # either side of the board's centre
TOP_CAPTION_W = 150                       # centred ABOVE the glyph, so it stays
                                          # clear of the columns' trigger lines

# Vertical spacing. The 540-unit layout is the compact form, the one short
# displays such as 1024x576 get. Where the screen has room, up to SPREAD more
# units open the layout out: the title and heading rise by SPREAD_UP of it and
# the help line and Back sink to the bottom by the rest, framing the board --
# the arrangement the author sketched on 2026-09-24.
SPREAD = 78
SPREAD_UP = 18

# The rest of build_gui's layout, in design units unless marked. Named, not written
# inline, because the Mac installer does this same arithmetic for a resolution with
# no set (macos/tools/kmrp-guiblend.c) and takes every number from gui-blend.bin
# (layout_constants), so there is one copy of each.
SCALE_HEIGHT = 720                        # screen pixels per 720 design units' scale step
COMPACT_H = 540                           # the compact layout's height
SCREEN_MARGIN = 40                        # kept free when the layout opens out
TOP_MIN_PX = 8                            # screen pixels above the title, at least
TITLE_H = 32
FAMILY_Y, FAMILY_H = 34, 22               # the heading naming the pad
HELP_Y, HELP_H = 466, 22                  # the help line, compact form
BACK_X, BACK_Y, BACK_W, BACK_H = 280, 494, 200, 40
BACK_GLYPH_X, BACK_GLYPH_Y, BACK_GLYPH_TRIM = 8, 6, 12   # the B inside Back
CAPTION_GAP = 6                           # between a glyph and its caption box
LINE_BOX_H = 28                           # a one-line caption box
TWO_LINES = 2.3                           # a two-line box, in the font's lines
TOP_CAPTION_H, TOP_CAPTION_RISE = 26, 28  # the centre pair's captions, above their glyphs
HEADING_BOTTOM, HAIR_BELOW_HEADING = 56, 12
HAIR_ABOVE_HELP, HAIR_OPEN_DOWN, HAIR_COMPACT_Y = 18, 40, 546
TEXTURE = (2048, 1024)                    # the board's aspect exactly: 760x380
INK = (0, 168, 250)                       # KOTOR's own cyan
BODY = (165, 214, 240)                    # the silhouette, a paler cyan


def anchor(family: str, key: str) -> tuple[float, float]:
    """A button's position on the board, in design units, board-relative."""
    ax, ay = ANCHORS[SILHOUETTES[family][1]][key]
    return DIAGRAM_X + ax * SCALE, DIAGRAM_Y + ay * SCALE


def _line(i: int, y: float, family: str):
    """The last leg of entry i's leader, from its bend to where it stops."""
    side, key = LAYOUT[i][2], LAYOUT[i][3]
    ax, ay = anchor(family, key)
    if side == "T":
        # Straight down from under the glyph: nothing else sits in that band.
        return (TOP_GLYPH_X[key] + GLYPH / 2, y + GLYPH / 2 + 3), (ax, ay)
    bend = (LEFT_GLYPH_X + GLYPH + 4 + BEND_INSET if side == "L"
            else RIGHT_GLYPH_X - 4 - BEND_INSET)
    stop = STOP.get(key, 0) * SCALE
    if stop:
        dx, dy = bend - ax, y - ay
        length = (dx * dx + dy * dy) ** 0.5
        ax, ay = ax + dx / length * stop, ay + dy / length * stop
    return (bend, y), (ax, ay)


def _crosses(a, b) -> bool:
    """Do two segments properly intersect?"""
    (p1, p2), (p3, p4) = a, b

    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def _near(segment, point, radius: float) -> bool:
    """Does the segment pass within `radius` of a point?"""
    (x1, y1), (x2, y2) = segment
    dx, dy = x2 - x1, y2 - y1
    length2 = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((point[0] - x1) * dx + (point[1] - y1) * dy) / length2))
    px, py = x1 + t * dx, y1 + t * dy
    return (px - point[0]) ** 2 + (py - point[1]) ** 2 < radius * radius


@lru_cache(maxsize=None)
def rows() -> tuple[float, ...]:
    """The row centre of each LAYOUT entry, board-relative.

    ONE answer for every family, because there is one kmrplayout.gui: the
    captions and glyph boxes cannot move per family, only the texture behind
    them can. So the order is chosen against both silhouettes at once.

    Each column's rows are evenly spaced over the same band; a sweep of row
    placements, bend depths and keep-out radii measured this as the only
    variant that reaches zero lines through a foreign button. Which order the
    rows take is searched exhaustively (8! on the right is 40,320 orders) for
    the fewest lines passing through a button that is not theirs, then the
    fewest crossings, then the shortest total line. A line through another
    button ranks worst because it reads as pointing at that button. Sorting by button height
    alone was tried first and crossed three pairs: buttons sit at different
    depths, so a line to an inner button fans past the outer ones.
    """
    import itertools

    silhouettes = ("xbox", "playstation")
    # Xbox, Switch and Steam Deck are all drawn on the Xbox silhouette, so a
    # crossing there is seen by three families and one on PS5 by one.
    weight = {f: sum(1 for s in SILHOUETTES.values()
                     if s[1] == SILHOUETTES[f][1]) for f in silhouettes}
    centres = [0.0] * len(LAYOUT)

    for i, entry in enumerate(LAYOUT):
        if entry[2] == "T":
            centres[i] = TOP_ROW_Y

    for side in ("L", "R"):
        members = [i for i, e in enumerate(LAYOUT) if e[2] == side]
        n = len(members)
        slots = [ROW_TOP + k * (ROW_BOTTOM - ROW_TOP) / (n - 1) for k in range(n)]
        # Every control on this side, with the radius a foreign line must clear.
        keepouts = {f: [(LAYOUT[j][3], anchor(f, LAYOUT[j][3]),
                         KEEPOUT[LAYOUT[j][3]] * SCALE) for j in members]
                    for f in silhouettes}
        best = None
        for order in itertools.permutations(members):
            crossings = grazes = 0
            length = 0.0
            for f in silhouettes:
                segs = [_line(i, y, f) for i, y in zip(order, slots)]
                for a, i in enumerate(order):
                    (bx, by), (ax, ay) = segs[a]
                    length += ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                    for b in range(a + 1, n):
                        if _crosses(segs[a], segs[b]):
                            crossings += weight[f]
                    own = LAYOUT[i][3]
                    for key, point, radius in keepouts[f]:
                        if key == own or frozenset((key, own)) in SAME_CONTROL:
                            continue
                        if _near(segs[a], point, radius):
                            grazes += weight[f]
                if best is not None and (grazes, crossings) > best[:2]:
                    break
            key = (grazes, crossings, length, order, tuple(slots))
            if best is None or key < best:
                best = key
        for i, y in zip(best[3], best[4]):
            centres[i] = y
    return tuple(centres)


def _tga(image) -> bytes:
    """32-bit bottom-up TGA, the encoding every shipped KOTOR texture uses."""
    from PIL import Image
    sheet = image.transpose(Image.FLIP_TOP_BOTTOM)
    r, g, b, a = sheet.split()
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
                         sheet.width, sheet.height, 32, 0x08)
    return header + Image.merge("RGBA", (b, g, r, a)).tobytes() + TGA_FOOTER


def _glow(size, centre, radii, colour, alpha):
    """A soft elliptical glow, strongest at the centre, fading to nothing."""
    import numpy as np
    from PIL import Image
    y, x = np.mgrid[0:size[1], 0:size[0]].astype(np.float32)
    d = np.sqrt(((x - centre[0]) / radii[0]) ** 2 + ((y - centre[1]) / radii[1]) ** 2)
    a = (np.clip(1 - d, 0, 1) ** 2 * alpha).astype(np.uint8)
    rgb = np.broadcast_to(np.array(colour, np.uint8), (size[1], size[0], 3))
    return Image.fromarray(np.dstack([rgb, a[..., None]]), "RGBA")


def build_diagram(family: str):
    """The board texture for one family: silhouette, glyphs and leader lines."""
    from PIL import Image, ImageDraw

    source, silhouette = SILHOUETTES[family]
    art = Image.open(GLYPH_PACK / source).convert("RGBA")
    # Tint the white line art to KOTOR's palette, keeping its own alpha.
    tint = Image.new("RGBA", art.size, BODY + (0,))
    tint.putalpha(art.getchannel("A"))
    art = tint

    # This family's own buttons, where the silhouette only has empty circles.
    for key, size in FACE_GLYPHS.items():
        glyph = _load_glyph_art(key, family)
        if glyph is None:
            raise ValueError(f"{family}: no {key} glyph to put on the diagram")
        glyph = glyph.convert("RGBA")
        scale = size / max(glyph.size)
        glyph = glyph.resize((max(1, round(glyph.width * scale)),
                              max(1, round(glyph.height * scale))), Image.LANCZOS)
        cx, cy = ANCHORS[silhouette][key]
        art.alpha_composite(glyph, (round(cx - glyph.width / 2),
                                    round(cy - glyph.height / 2)))

    k = TEXTURE[0] / BOARD[2]                     # texture px per design unit
    board = Image.new("RGBA", TEXTURE, (0, 0, 0, 0))
    # A soft holo-glow seats the controller on the backdrop. This texture keeps
    # its aspect on screen, so the glow is a true ellipse, not a stretched one.
    cx = (DIAGRAM_X + DIAGRAM_W / 2) * k
    cy = (DIAGRAM_Y + DIAGRAM_W * SOURCE_SIZE[1] / SOURCE_SIZE[0] / 2) * k
    board.alpha_composite(_glow(TEXTURE, (cx, cy),
                                (DIAGRAM_W * 0.62 * k, DIAGRAM_W * 0.42 * k),
                                INK, 70))
    placed = art.resize((round(DIAGRAM_W * k),
                         round(DIAGRAM_W * k * art.height / art.width)),
                        Image.LANCZOS)
    board.alpha_composite(placed, (round(DIAGRAM_X * k), round(DIAGRAM_Y * k)))

    # Lines on a separate layer at 4x, then downsampled: PIL's line drawing is
    # not antialiased, and a stair-stepped diagonal reads as a rendering fault.
    ss = 4
    lines = Image.new("RGBA", (TEXTURE[0] * ss, TEXTURE[1] * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(lines)
    width = round(2.2 * ss)
    for i, cy in enumerate(rows()):
        side = LAYOUT[i][2]
        (bend, by), (ax, ay) = _line(i, cy, family)
        if side == "T":
            points = [(bend, by), (ax, ay)]
        else:
            start = (LEFT_GLYPH_X + GLYPH + 4) if side == "L" else (RIGHT_GLYPH_X - 4)
            points = [(start, cy), (bend, cy), (ax, ay)]
        draw.line([(x * k * ss, y * k * ss) for x, y in points],
                  fill=INK + (235,), width=width, joint="curve")
        r = 2.6 * k * ss
        draw.ellipse((ax * k * ss - r, ay * k * ss - r,
                      ax * k * ss + r, ay * k * ss + r), fill=INK + (255,))
    lines = lines.resize(TEXTURE, Image.LANCZOS)
    board.alpha_composite(lines)
    return board


def build_art(output: Path):
    """Every texture the screen uses, for every family."""
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for family in GLYPH_FAMILIES:
        letter = FAMILY_LETTERS[family]
        for i, (glyph, _) in enumerate(MAPPINGS):
            p = output / f"kmr{letter}lyt{i:02d}.tga"
            p.write_bytes(build_square_glyph_tga(glyph, family=family))
            paths.append(p)
        p = output / f"kmr{letter}lytdiag.tga"
        p.write_bytes(_tga(build_diagram(family)))
        paths.append(p)
        # The B inside the layout screen's own Back button.
        p = output / f"kmr{letter}lytbk.tga"
        p.write_bytes(build_square_glyph_tga("B", family=family))
        paths.append(p)
        # The A that sits beside the focused button of a confirmation box.
        p = output / f"kmr{letter}{CONFIRM_BADGE_STEM}.tga"
        p.write_bytes(build_square_glyph_tga("A", family=family))
        paths.append(p)
    # The backdrop and edge art do not change with the controller.
    for name, image in backdrop.build_all().items():
        p = output / f"{name}.tga"
        p.write_bytes(_tga(image))
        paths.append(p)
    return paths


# ---------------------------------------------------------------- the GUI

# get_struct() returns a copy holding its own field dict, so a mutation made
# through it is discarded unless the struct is stored back — the same trap as
# get_list() below. Without this the whole screen was written with one shared
# extent, no captions and no title, and only the menu entry's text was checked.
@contextmanager
def edit(control, label):
    struct_ = control.get_struct(label)
    yield struct_
    control.set_struct(label, struct_)


def text(control, value):
    with edit(control, 'TEXT') as t:
        t.set_uint32('STRREF', 0xffffffff)
        t.set_string('TEXT', value)


def style(control, font=None, align=None, color=None):
    with edit(control, 'TEXT') as t:
        if font is not None: t.set_resref('FONT', ResRef(font))
        if align is not None: t.set_int32('ALIGNMENT', align)
        if color is not None: t.set_vector3('COLOR', color)


def fill(control, resref):
    with edit(control, 'BORDER') as b:
        b.set_resref('FILL', ResRef(resref))


def extent(c, x, y, w, h):
    with edit(c, 'EXTENT') as e:
        for k, v in zip(('LEFT', 'TOP', 'WIDTH', 'HEIGHT'), (x, y, w, h)):
            e.set_int32(k, round(v))


# KOTOR text alignment is a bitfield: 1/2/4 left/centre/right, 16 vertical centre.
ALIGN_LEFT, ALIGN_CENTRE, ALIGN_RIGHT = 17, 18, 20
CYAN, YELLOW = Vector3(0, 0.66, 0.98), Vector3(0.98, 1, 0)


# The font every label on this screen is drawn in, and how wide it draws.
#
# Measured in game on 2026-09-24 at 3440x1440: captions authored in
# dialogfont10x10 rendered at exactly the size of dialogfont16x16 text -- the
# title, the heading and the captions all came out alike -- so the game draws
# this panel's labels in 16x16 whatever the .gui asks for. Captions sized for
# 10x10 therefore wrapped, and a wrapped label too short for two lines shows
# only its last: "Camera / Click: free look" read "Free look", "Switch ally /
# Prev tab" read "Tab". The labels now ask for the font they get, and the boxes
# are sized from that font's own metrics at each resolution.
#
# RENDER_FACTOR is a margin over measure_label(), since the engine wraps against
# its own slightly different sum (reverse-engineering/font-atlases.md, "spacingR
# controls word wrap"): each glyph's advance rounded, plus spacingR.
# *Corrected 2026-09-30:* this was 0.92, below 1, because measure_label()
# over-read the font -- vanilla 16x16 text on the Gameplay screen and these
# captions rendered at 0.88 of it at 3440x1440. The over-read was
# parse_font_metrics scaling spacingR by texturewidth, and it grew with the
# resolution (the text drew at about 0.84 of it at 3024x1964). With the measure
# corrected, 1.04 gives every resolution the same 4% margin: the boxes played at
# 3440x1440 grow by 7 to 9 px, and the over-wide ones at 3024x1964 lose 18 to 32
# (read from the resource builds before and after).
CAPTION_FONT = 'dialogfont16x16'
RENDER_FACTOR = 1.04
CAPTION_PAD = 4                           # design units beyond the text


def caption_width(text_value: str, metrics, scale: float) -> float:
    """Design units a caption needs in CAPTION_FONT, or 0 without metrics."""
    if not metrics:
        return 0.0
    return measure_label(text_value, *metrics) * RENDER_FACTOR / scale + CAPTION_PAD


def layout_constants() -> dict[str, float]:
    """Every number build_gui's geometry uses, by name, for gui-blend.bin: the Mac
    installer redoes that geometry for a resolution with no set (kmrp-guiblend.c) and
    looks each one up here by name rather than carrying a copy."""
    return {name: float(value) for name, value in (
        ("DESIGN_W", DESIGN_W), ("BOARD_X", BOARD[0]), ("BOARD_Y", BOARD[1]),
        ("BOARD_W", BOARD[2]), ("BOARD_H", BOARD[3]), ("GLYPH", GLYPH),
        ("LEFT_GLYPH_X", LEFT_GLYPH_X), ("RIGHT_GLYPH_X", RIGHT_GLYPH_X),
        ("CAPTION_W", CAPTION_W), ("EDGE_GAP", EDGE_GAP), ("TOP_CAPTION_W", TOP_CAPTION_W),
        ("SPREAD", SPREAD), ("SPREAD_UP", SPREAD_UP), ("RENDER_FACTOR", RENDER_FACTOR),
        ("CAPTION_PAD", CAPTION_PAD), ("SCALE_HEIGHT", SCALE_HEIGHT), ("COMPACT_H", COMPACT_H),
        ("SCREEN_MARGIN", SCREEN_MARGIN), ("TOP_MIN_PX", TOP_MIN_PX), ("TITLE_H", TITLE_H),
        ("FAMILY_Y", FAMILY_Y), ("FAMILY_H", FAMILY_H), ("HELP_Y", HELP_Y), ("HELP_H", HELP_H),
        ("BACK_X", BACK_X), ("BACK_Y", BACK_Y), ("BACK_W", BACK_W), ("BACK_H", BACK_H),
        ("BACK_GLYPH_X", BACK_GLYPH_X), ("BACK_GLYPH_Y", BACK_GLYPH_Y),
        ("BACK_GLYPH_TRIM", BACK_GLYPH_TRIM), ("CAPTION_GAP", CAPTION_GAP),
        ("LINE_BOX_H", LINE_BOX_H), ("TWO_LINES", TWO_LINES), ("TOP_CAPTION_H", TOP_CAPTION_H),
        ("TOP_CAPTION_RISE", TOP_CAPTION_RISE), ("HEADING_BOTTOM", HEADING_BOTTOM),
        ("HAIR_BELOW_HEADING", HAIR_BELOW_HEADING), ("HAIR_ABOVE_HELP", HAIR_ABOVE_HELP),
        ("HAIR_OPEN_DOWN", HAIR_OPEN_DOWN), ("HAIR_COMPACT_Y", HAIR_COMPACT_Y),
        ("DECOR_CORNER", backdrop.CORNER), ("DECOR_EDGE_GAP", backdrop.EDGE_GAP),
        ("READOUT_W", backdrop.READOUT[0]), ("READOUT_H", backdrop.READOUT[1]),
        ("HAIR_H", backdrop.HAIR_H), ("ART_MAX_W", backdrop.ART_MAX_W),
        ("ART_MIN_W", backdrop.ART_MIN_W), ("ART_MARGIN", backdrop.ART_MARGIN),
        ("READOUT_INSET", backdrop.READOUT_INSET), ("HAIR_OVERLAP", backdrop.HAIR_OVERLAP),
        ("DECOR_COUNT", len(backdrop.DECOR)), ("ROWS", ROWS))}


def layout_rows() -> list[tuple[str, float, float, str]]:
    """Per LAYOUT entry: its side, its glyph's x, its row centre on the board (rows(),
    the same for every resolution), and its caption, for gui-blend.bin."""
    return [(side, float({'L': LEFT_GLYPH_X, 'R': RIGHT_GLYPH_X}.get(side) or TOP_GLYPH_X[key]),
             float(cy), caption)
            for (_, caption, side, key), cy in zip(LAYOUT, rows())]


def build_gui(source: Path, output: Path, width: int, height: int,
              font_txi: Path | None = None):
    """kmrplayout.gui: every tag the runtime binds, laid out for one screen.

    `font_txi` is this resolution's CAPTION_FONT TXI; without it the caption
    boxes keep their minimum widths.
    """
    metrics = parse_font_metrics(font_txi) if font_txi else None
    line_h = 0.0
    if font_txi:
        import re
        found = re.search(r'^fontheight (\S+)', font_txi.read_text(
            encoding='ascii', errors='replace'), re.M | re.I)
        line_h = float(found.group(1)) * 100 if found else 0.0
    g = read_gff(source)
    controls = {c.get_string('TAG'): c for c in g.root.get_list('CONTROLS')}
    label, button = controls['LBL_TITLE'], controls['BTN_BACK']
    out = GFFList()
    scale = max(1, height / SCALE_HEIGHT)
    # Keep the same shared text scale even on 540/576/600-pixel displays.
    left = width / 2 - DESIGN_W / 2 * scale
    # Open the layout out by as much of SPREAD as the screen allows, keeping
    # 40 units of margin; design y=0 stays the board's frame of reference.
    spread = min(SPREAD, max(0.0, height / scale - COMPACT_H - SCREEN_MARGIN))
    up = round(spread * SPREAD_UP / SPREAD)
    down = spread - up
    top = max(TOP_MIN_PX + up * scale, (height - (COMPACT_H + spread) * scale) / 2 + up * scale)

    def add(i, tag, value, x, y, w, h, btn=False):
        c = copy.deepcopy(button if btn else label)
        c.set_int32('ID', i); c.set_string('TAG', tag)
        extent(c, left + x * scale, top + y * scale, w * scale, h * scale)
        text(c, value)
        if not btn:
            style(c, font=CAPTION_FONT, align=ALIGN_LEFT, color=CYAN)
        out.append(c)
        return c

    title = add(0, 'LBL_TITLE', 'Controller Layout', 0, -up, DESIGN_W, TITLE_H)
    style(title, font='dialogfont16x16', align=ALIGN_CENTRE, color=YELLOW)
    add(1, 'BTN_BACK', 'Back', BACK_X, BACK_Y + down, BACK_W, BACK_H, True)
    names = ('Xbox / compatible controller', 'PlayStation controller',
             'Nintendo Switch controller', 'Steam controller')
    tags = ('LBL_XBOX', 'LBL_PS', 'LBL_SWITCH', 'LBL_DECK')
    for i, name in enumerate(names):
        style(add(2 + i, tags[i], name, 0, FAMILY_Y - up, DESIGN_W, FAMILY_H),
              align=ALIGN_CENTRE)
    # The active-device line is gone from the screen (2026-09-24): the heading
    # already names the pad. The two labels stay, empty and sizeless, because
    # the runtime binds IDs 6 and 7 by tag and toggles them with the device;
    # removing them would renumber every control after them.
    for i in range(2):
        add(6 + i, ('LBL_KBM', 'LBL_PAD')[i], '', 0, 0, 0, 0)

    # The board: one label the size of the whole callout area, its fill the
    # diagram texture. The runtime swaps the fill's family letter with the pad.
    fill(add(8, 'LBL_DIAGRAM', '', *BOARD), 'kmrplytdiag')
    style(add(9, 'LBL_HELP',
              'Buttons are shown by position. Menu actions vary by screen.',
              0, HELP_Y + down, DESIGN_W, HELP_H), align=ALIGN_CENTRE)

    # Each column's box is as wide as its longest caption needs, growing
    # outward, away from the diagram; the glyphs and leader lines stay put.
    need = {side: max([caption_width(e[1], metrics, scale)
                       for e in LAYOUT if e[2] == side] + [0.0])
            for side in 'LRT'}
    # On the narrowest screens (1280x1080, 800x600) the longest captions would
    # run off the edge, so a column stops EDGE_GAP short of it and its box is
    # made two lines tall: a caption that wraps then shows both lines, where a
    # one-line box shows only the last.
    screen_left = -left / scale + EDGE_GAP
    screen_right = (width - left) / scale - EDGE_GAP
    left_w = min(max(CAPTION_W, need['L']), LEFT_GLYPH_X - CAPTION_GAP - screen_left)
    right_w = min(max(CAPTION_W, need['R']),
                  screen_right - (RIGHT_GLYPH_X + GLYPH + CAPTION_GAP))
    top_w = max(TOP_CAPTION_W, need['T'])
    overhang = max(left_w, right_w) - CAPTION_W
    two_lines = max(float(LINE_BOX_H), TWO_LINES * line_h / scale)

    def box_height(caption, box_w):
        return two_lines if caption_width(caption, metrics, scale) > box_w else LINE_BOX_H

    # The rows sit where the texture's lines end, in the same design space.
    for i, ((glyph, caption, side, _), cy) in enumerate(zip(LAYOUT, rows())):
        y = BOARD[1] + cy
        key = LAYOUT[i][3]
        gx = {'L': LEFT_GLYPH_X, 'R': RIGHT_GLYPH_X}.get(side) or TOP_GLYPH_X[key]
        # The runtime rewrites this fill per controller family; the file still
        # carries a valid resref so the screen is never blank on the first frame.
        fill(add(10 + i, f'GLYPH_{i:02d}', '', gx, y - GLYPH / 2, GLYPH, GLYPH),
             f'kmrplyt{i:02d}')
        if side == 'L':
            tw = left_w
            tx, align = LEFT_GLYPH_X - CAPTION_GAP - tw, ALIGN_RIGHT
        elif side == 'R':
            tw = right_w
            tx, align = RIGHT_GLYPH_X + GLYPH + CAPTION_GAP, ALIGN_LEFT
        else:
            # Centred above its glyph. Beside it, "Map / Close menu" reached
            # into the right column and the RT line ran through the word menu.
            tw = top_w
            tx, align = gx + GLYPH / 2 - tw / 2, ALIGN_CENTRE
            style(add(10 + ROWS + i, f'TEXT_{i:02d}', caption, tx,
                      y - GLYPH / 2 - TOP_CAPTION_RISE, tw, TOP_CAPTION_H), align=align)
            continue
        th = box_height(caption, tw)
        style(add(10 + ROWS + i, f'TEXT_{i:02d}', caption, tx, y - th / 2, tw, th),
              align=align)

    # Full screen, not a box: the panel root is the backdrop, and the edge art
    # is anchored to the screen's own edges rather than the design space, so
    # it reaches the corners at every aspect. Drawn after the rows, which it
    # never overlaps.
    with edit(g.root, 'BORDER') as b:
        b.set_resref('FILL', ResRef('kmrlytbg'))
        b.set_resref('EDGE', ResRef('')); b.set_resref('CORNER', ResRef(''))
        b.set_int32('DIMENSION', 0)
    deco_base = 10 + 2 * ROWS
    # Upper hairline just under the heading; lower one above the help line when
    # the layout is opened out, else under Back, where the compact form has room.
    hair_upper = HEADING_BOTTOM - up + HAIR_BELOW_HEADING
    hair_lower = HELP_Y + down - HAIR_ABOVE_HELP if down >= HAIR_OPEN_DOWN else HAIR_COMPACT_Y
    for i, (resref, (x, y, w, h)) in enumerate(zip(
            backdrop.DECOR,
            # The side art makes room for captions that reach past the board.
            backdrop.placements(width, height, scale, top, DESIGN_W + 2 * overhang,
                                hair_upper, hair_lower))):
        c = copy.deepcopy(label)
        c.set_int32('ID', deco_base + i); c.set_string('TAG', f'DECO_{i:02d}')
        extent(c, x, y, w, h)
        text(c, '')
        fill(c, resref)
        out.append(c)

    # The B inside Back, at its left end: Back is what B does on this screen.
    # Last, so no earlier ID moves; the runtime binds it as GLYPH_BACK, sets
    # the pad's glyph and shows it only while a pad is in use.
    back_x, back_y, back_h = BACK_X, BACK_Y + down, BACK_H
    size = back_h - BACK_GLYPH_TRIM
    c = copy.deepcopy(label)
    c.set_int32('ID', deco_base + len(backdrop.DECOR))
    c.set_string('TAG', 'GLYPH_BACK')
    extent(c, left + (back_x + BACK_GLYPH_X) * scale, top + (back_y + BACK_GLYPH_Y) * scale,
           size * scale, size * scale)
    text(c, '')
    fill(c, 'kmrplytbk')
    out.append(c)

    g.root.set_list('CONTROLS', out)
    write_gff(g, output)


# The confirmation box, confirm.gui, which every Yes/No prompt uses: Exit Game,
# Solo Mode, overwrite and delete save. CSWGuiMessageBox::FixMessageLabel
# (0x006253A0) resizes both buttons to fit their captions before drawing, so a
# badge painted inside a button is stretched by a factor nobody can know at
# build time -- which is how the Solo Mode Cancel badge came out as a smear.
# The A goes BESIDE the focused button instead, in a label of its own: the
# runtime (K1ControllerLayout.cpp) binds LBL_KMRPA by tag, then each frame
# places it left of whichever button has focus and gives it the pad's glyph,
# kmr?cnfa -- the main menu's travelling A, for these boxes.
CONFIRM_BADGE_TAG = 'LBL_KMRPA'
CONFIRM_BADGE_STEM = 'cnfa'
# The A left of the highlighted dialogue reply (issue #21). The same A art as the
# confirm boxes; the runtime moves it and swaps the family letter.
DIALOG_BADGE_TAG = 'LBL_KMRPDLG'


def add_confirm_badge(source: Path, output: Path, label_source: Path,
                      tag: str = CONFIRM_BADGE_TAG):
    """Add the travelling-A label to confirm.gui, or with `tag` to another file.

    confirm.gui has no plain label to copy -- LB_MESSAGE is a list box -- so the
    struct comes from `label_source`'s LBL_TITLE, the same one the layout screen
    is built from. Its extent is irrelevant: the runtime sets it every frame.
    dialog.gui gets the same label as DIALOG_BADGE_TAG.
    """
    g = read_gff(source); cs = g.root.get_list('CONTROLS')
    if any(c.get_string('TAG') == tag for c in cs):
        write_gff(g, output)
        return
    labels = {c.get_string('TAG'): c
              for c in read_gff(label_source).root.get_list('CONTROLS')}
    c = copy.deepcopy(labels['LBL_TITLE'])
    c.set_string('TAG', tag)
    c.set_int32('ID', max(x.get_int32('ID') for x in cs) + 1)
    text(c, '')
    fill(c, f'kmrp{CONFIRM_BADGE_STEM}')
    extent(c, 0, 0, 0, 0)
    cs.append(c)
    g.root.set_list('CONTROLS', cs)
    write_gff(g, output)


def add_entry(source: Path, output: Path):
    """Add Controller Layout to the Gameplay screen, under Keymapping.

    It lives beside Keymapping and Mouse rather than inside Mouse, because that
    is the column a player looks down for this kind of screen, and because
    Options does not list Mouse at all -- the route is Options -> Gameplay ->
    Mouse, so an entry buried there is two clicks from where it reads.

    The button is a copy of Keymapping, and its position is derived from the
    step between Mouse and Keymapping rather than a constant, so it stays in
    the column at every one of the 48 resolutions.
    """
    g = read_gff(source); cs = g.root.get_list('CONTROLS')
    if any(c.get_string('TAG') == 'BTN_KMRPLAY' for c in cs): return
    by = {c.get_string('TAG'): c for c in cs}
    if 'BTN_KEYMAP' not in by:
        raise ValueError(f"{source.name} has no BTN_KEYMAP to sit under")
    c = copy.deepcopy(by['BTN_KEYMAP'])
    c.set_string('TAG', 'BTN_KMRPLAY')
    c.set_int32('ID', max(x.get_int32('ID') for x in cs) + 1)
    text(c, 'Controller Layout')

    keymap = by['BTN_KEYMAP'].get_struct('EXTENT')
    top = keymap.get_int32('TOP')
    height = keymap.get_int32('HEIGHT')
    if 'BTN_MOUSE' in by:
        # The column's own spacing, whatever this resolution scaled it to.
        step = top - by['BTN_MOUSE'].get_struct('EXTENT').get_int32('TOP')
    else:
        step = round(height * 1.175)
    with edit(c, 'EXTENT') as e:
        e.set_int32('TOP', top + step)

    # Lift the three stacked buttons -- Mouse, Keymapping and this one -- by
    # half their own spacing. Below Keymapping the new button reached the
    # bottom bar (6px above Default at 3440x1440); lifted, the gap under the
    # last checkbox roughly matches the step between the buttons, and the stack
    # clears the bottom bar.
    lift = step // 2
    for control in [by[t] for t in ('BTN_MOUSE', 'BTN_KEYMAP') if t in by] + [c]:
        with edit(control, 'EXTENT') as e:
            e.set_int32('TOP', e.get_int32('TOP') - lift)

    # get_list() returns a copy. Store it back or the new control is silently
    # absent from the file even though append() succeeded.
    # Generic KMRP spatial navigation discovers the new ID automatically.
    cs.append(c)
    g.root.set_list('CONTROLS', cs)
    write_gff(g, output)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('override', type=Path)
    a = p.parse_args()
    root = read_gff(a.override / 'optmouse.gui').root.get_struct('EXTENT')
    build_gui(a.override / 'optmouse.gui', a.override / 'kmrplayout.gui',
              root.get_int32('WIDTH'), root.get_int32('HEIGHT'))
    add_entry(a.override / 'optgameplay.gui', a.override / 'optgameplay.gui')
    build_art(a.override)
