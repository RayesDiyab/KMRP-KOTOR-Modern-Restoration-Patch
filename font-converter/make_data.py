#!/usr/bin/env python3
"""The data the KMRP Font Converter carries, made from KMRP's (New) Original HD Font.

The converter (this folder) turns any font file into the game's font atlases. Two
things it needs come from KMRP's `assets/hd-original-fonts`, so they are made here
rather than written by hand into the program, and kept in `data/` so the converter
builds on its own (`build.ps1 -Refresh` runs this again):

  * `references.txt`: for each of the 17 fonts it writes, the HD Original atlas's TXI
    header (the fields the converter keeps: fontheight, baselineheight, spacing and the
    rest), its atlas width, and each slot's width in pixels. A slot the chosen font has
    no letter for keeps this width, so no glyph is ever zero wide (a zero-wide glyph
    crashes the game's word wrap, see build_font_from_ttf.measure).
  * The examples on the converter's tiles: each line drawn in the HD Original font at
    three times the size it is shown, as a PNG, and `examples.txt`, which says what each
    tile shows and how, so the converter can draw the same lines in the player's font.

The HD Original atlases are 6x bakes (docs/hd-original-font.md); the converter writes
its atlases at the same size, so KMRP sizes both the same way.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
# The KMRP checkout this folder sits in.
HD = HERE.parent / "assets" / "hd-original-fonts"

# The 17 fonts the converter writes: the game's 18 less fnt_galahad14, which is game art
# made at build time and never a text font the player sees in menus.
FONTS = ("dialogfont10x10", "dialogfont10x10a", "dialogfont10x10b", "dialogfont12x16",
         "dialogfont16x16", "dialogfont16x16a", "dialogfont16x16b", "dialogfont32x32",
         "fnt_console", "fnt_credits", "fnt_creditsa", "fnt_creditsb", "fnt_d10x10b",
         "fnt_d16x16", "fnt_d16x16a", "fnt_d16x16b", "fnt_dialog16x16")

GOLD, CYAN, PALE = (236, 214, 64), (52, 172, 236), (200, 226, 250)

# What each tile shows: lines, each a list of pieces side by side. A piece is the font
# it is drawn in, its text, its colour and the height it is shown at, in pixels at
# 1600x900. These are what the game uses each font for, in its own words.
EXAMPLES = {
    "menu": [[("dialogfont16x16", "Options", GOLD, 24)],
             [("dialogfont16x16", "Gameplay", CYAN, 18), ("dialogfont16x16", "Close", CYAN, 18)]],
    "menusmall": [[("dialogfont10x10", "Combat Movement", CYAN, 17)],
                  [("dialogfont10x10", "Auto Level Up", CYAN, 17)]],
    "menusmallb": [[("dialogfont10x10b", "Feats", CYAN, 16), ("dialogfont10x10b", "Skills", CYAN, 16),
                    ("dialogfont10x10b", "Powers", CYAN, 16)]],
    "menumedium": [[("dialogfont12x16", "Taris: Upper City", CYAN, 18)],
                   [("dialogfont12x16", "Endar Spire", CYAN, 18)]],
    "menularge": [[("dialogfont32x32", "Character", GOLD, 36)]],
    "dialogue": [[("fnt_d16x16", "Carth: We need a ship", PALE, 19)],
                 [("fnt_d16x16", "before the Sith find us.", PALE, 19)]],
    "descriptions": [[("fnt_d16x16b", "1. Who are you?", CYAN, 21)],
                     [("fnt_d16x16b", "2. I have to go.", CYAN, 21)]],
    "light": [[("fnt_d16x16a", "Find Bastila, then", PALE, 19)],
              [("fnt_d16x16a", "a way off Taris.", PALE, 19)]],
    "console": [[("fnt_console", "1,250", CYAN, 24)], [("fnt_console", "XP 4,500", CYAN, 24)]],
    "credits": [[("fnt_credits", "Lead Designer", PALE, 21)], [("fnt_credits", "Art Director", PALE, 21)]],
    "creditsb": [[("fnt_creditsb", "BioWare Corp.", PALE, 21)], [("fnt_creditsb", "LucasArts", PALE, 21)]],
}
DRAWN_AT = 3   # the examples are drawn at three times the size they are shown


class Atlas:
    """An HD Original atlas and its TXI."""

    def __init__(self, resref: str):
        text = (HD / f"{resref}.txi").read_text(encoding="ascii").replace("\r", "")
        self.lines = [line.strip() for line in text.splitlines() if line.strip()]
        self.header = []
        for line in self.lines:
            if line.startswith("upperleftcoords"):
                break
            self.header.append(line)
        self.fields = {line.split()[0]: line.split()[1] for line in self.header if len(line.split()) > 1}
        self.numchars = int(float(self.fields["numchars"]))
        self.width = round(float(self.fields["texturewidth"]) * 100)
        self.height = round(float(self.fields["fontheight"]) * 100)
        upper = next(i for i, line in enumerate(self.lines) if line.startswith("upperleftcoords"))
        lower = next(i for i, line in enumerate(self.lines) if line.startswith("lowerrightcoords"))
        self.cells = []
        for c in range(self.numchars):
            x0, y0 = map(float, self.lines[upper + 1 + c].split()[:2])
            x1, y1 = map(float, self.lines[lower + 1 + c].split()[:2])
            self.cells.append((x0, y0, x1, y1))
        self.image = Image.open(HD / f"{resref}.tga").convert("RGBA")

    def slot_widths(self) -> list[int]:
        return [max(1, round((x1 - x0) * self.width)) for x0, _, x1, _ in self.cells]

    def draw(self, text: str, height: float, colour: tuple[int, int, int]) -> Image.Image:
        """`text` at a glyph box `height` pixels high, as the game draws it: each glyph its
        cell, one texel to one pixel at the atlas's own size, scaled as a whole."""
        iw, ih = self.image.size
        spacing = float(self.fields.get("spacingR", 0)) * 100
        pieces, pen = [], 0.0
        for byte in text.encode("cp1252"):
            x0, y0, x1, y1 = self.cells[byte]
            box = (round(x0 * iw), round((1 - y0) * ih), round(x1 * iw), round((1 - y1) * ih))
            if box[2] > box[0] and box[3] > box[1]:
                pieces.append((self.image.crop(box), pen))
            pen += (x1 - x0) * iw + spacing
        line = Image.new("RGBA", (max(1, round(pen)), self.height), (0, 0, 0, 0))
        for cell, x in pieces:
            line.alpha_composite(cell, (round(x), 0))
        factor = height / self.height
        line = line.resize((max(1, round(line.width * factor)), max(1, round(height))), Image.LANCZOS)
        # The text colour times the atlas's own: white letters take the colour, the HUD
        # font's black outline stays black.
        r, g, b, a = line.split()
        tinted = [ch.point(lambda v, k=k: v * k // 255) for ch, k in zip((r, g, b), colour)]
        return Image.merge("RGBA", (*tinted, a))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, nargs="?", default=HERE / "data")
    args = parser.parse_args()
    out: Path = args.out
    (out / "examples").mkdir(parents=True, exist_ok=True)
    for old in (out / "examples").glob("*.png"):
        old.unlink()

    atlases = {resref: Atlas(resref) for resref in FONTS}
    with open(out / "references.txt", "w", encoding="ascii", newline="\n") as file:
        for resref in FONTS:
            atlas = atlases[resref]
            file.write(f"font {resref} {atlas.width}\n")
            for line in atlas.header:
                file.write(f"  {line}\n")
            file.write("  widths " + " ".join(map(str, atlas.slot_widths())) + "\n")

    with open(out / "examples.txt", "w", encoding="utf-8", newline="\n") as file:
        for tile, lines in EXAMPLES.items():
            file.write(f"tile {tile}\n")
            for n, line in enumerate(lines):
                file.write("  line\n")
                for p, (resref, text, colour, height) in enumerate(line):
                    name = f"{tile}-{n}-{p}"
                    atlases[resref].draw(text, height * DRAWN_AT, colour).save(out / "examples" / f"{name}.png")
                    file.write(f"    piece {name} {resref} {height} {colour[0]} {colour[1]} {colour[2]} {text}\n")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
