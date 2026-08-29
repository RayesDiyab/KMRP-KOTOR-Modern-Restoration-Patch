#!/usr/bin/env python3
"""Regenerate lbl_mileftbot.tga, the HUD top-right button-row background art.

The stock texture (1024x128) draws 8 black boxes meant to sit behind the 8
top-right HUD buttons (BTN_EQU/INV/CHAR/ABI/MSG/JOU/MAP/OPT), but its boxes
are drawn at proportions that do not match the buttons' actual layout:

    stock texture:  85px boxes, 43-46px gaps, 16px end margins  (box:gap ~1.9:1)
    actual buttons: 64px boxes, 11px gaps,     4px end margins  (box:gap ~5.8:1)

Because the texture is stretched to fill LBL_MENUBG's extent, no amount of
resizing LBL_MENUBG can make those boxes line up under the buttons -- the
gaps are proportionally far too wide. This is baked into the art asset and is
present at every resolution, including the hand-tuned 3440x1440 gold build.

The proportions are NOT the same at every resolution, so one shared texture
cannot serve them all: the upstream GUI files scale button width and pitch
slightly differently per resolution relative to LBL_MENUBG's span (gold
3440x1440 has button/span = 0.1072, 1920x1080 has 0.0988 -- an ~8.5%
difference, which leaves the drawn boxes visibly wider than the buttons and
drifting out of step across the row). This therefore derives the box
positions from a specific .gui file's own button geometry, using each
button's exact position rather than an averaged pitch, so the result is
correct for that resolution by construction. The build pipeline generates one
per resolution and ships it in that resolution's GUI resource archive.

Output matches the stock asset's format exactly: 1024x128 RGBA TGA, pure
black boxes (0,0,0,255), fully transparent gaps (0,0,0,0), with a 1px
antialiased edge on each box side (alpha ~236), full texture height.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from pykotor.resource.formats.gff import read_gff

from fix_hud_menubg import BUTTON_TAGS


TEXTURE_SIZE = (1024, 128)
EDGE_ALPHA = 236

# The stock asset is an uncompressed 32-bit TGA (image type 2, descriptor 0x08)
# with a TGA 2.0 footer. Written directly rather than via an imaging library so
# the build has no third-party image dependency. Pixels are BGRA, but every
# pixel here is pure black with a varying alpha, so channel order is moot; the
# boxes span the full texture height, so row order is moot as well.
TGA_FOOTER = b"\x00" * 8 + b"TRUEVISION-XFILE." + b"\x00"


def geometry_from_gui(path: Path) -> tuple[int, list[tuple[int, int]]]:
    """Return (menubg_span, [(rel_left, rel_right), ...]) from a mipc*.gui file."""
    gui = read_gff(path)
    controls = gui.root.get_list("CONTROLS")
    if controls is None:
        raise ValueError(f"{path}: no root CONTROLS list")

    buttons: list[tuple[int, int]] = []
    menubg: tuple[int, int] | None = None
    for control in controls:
        tag = control.get_string("TAG")
        extent = control.get_struct("EXTENT")
        if tag in BUTTON_TAGS:
            buttons.append((extent.get_int32("LEFT"), extent.get_int32("WIDTH")))
        elif tag == "LBL_MENUBG":
            menubg = (extent.get_int32("LEFT"), extent.get_int32("WIDTH"))

    if len(buttons) != len(BUTTON_TAGS):
        raise ValueError(f"{path}: found {len(buttons)} of {len(BUTTON_TAGS)} button controls")
    if menubg is None:
        raise ValueError(f"{path}: no LBL_MENUBG control")

    origin, span = menubg
    boxes = sorted((left - origin, left - origin + width) for left, width in buttons)
    if boxes[0][0] < 0 or boxes[-1][1] > span:
        raise ValueError(f"{path}: buttons fall outside LBL_MENUBG (run fix_hud_menubg first)")
    return span, boxes


def build_tga(span: int, boxes: list[tuple[int, int]]) -> bytes:
    width, height = TEXTURE_SIZE
    scale = width / span

    # Alpha per column; every row is identical because the boxes are full height.
    alpha_row = bytearray(width)
    for rel_left, rel_right in boxes:
        start = max(0, int(round(rel_left * scale)))
        end = min(width, int(round(rel_right * scale)))
        for x in range(start, end):
            # 1px antialiased edge on each side, matching the stock asset.
            alpha_row[x] = EDGE_ALPHA if x in (start, end - 1) else 255

    row = bytearray(width * 4)
    for x in range(width):
        row[x * 4 + 3] = alpha_row[x]  # B, G, R stay 0 (pure black)

    header = struct.pack(
        "<BBBHHBHHHHBB",
        0,  # id length
        0,  # colour map type
        2,  # image type: uncompressed true-colour
        0, 0, 0,  # colour map spec
        0, 0,  # x/y origin
        width, height,
        32,  # bits per pixel
        0x08,  # descriptor: 8 alpha bits
    )
    return header + bytes(row) * height + TGA_FOOTER


def build_texture_for_gui(gui_path: Path, output: Path) -> None:
    span, boxes = geometry_from_gui(gui_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_tga(span, boxes))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gui", type=Path, help="mipc*.gui file whose button geometry drives the texture")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    span, boxes = geometry_from_gui(args.gui)
    build_texture_for_gui(args.gui, args.output)
    print(f"Wrote {args.output} ({TEXTURE_SIZE[0]}x{TEXTURE_SIZE[1]} RGBA)")
    print(f"  LBL_MENUBG span {span}, {len(boxes)} boxes, button/span {(boxes[0][1]-boxes[0][0])/span:.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
