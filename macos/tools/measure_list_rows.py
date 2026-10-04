#!/usr/bin/env python3
"""Measure, for every resolution's menu set, how far off centre each list's rows are in their box.

A list's box is drawn by its panel's artwork (the panel's FILL texture, stretched over the
panel), not by the list. This finds the box's left and right border in that artwork beside the
rows' rectangle, as the game lays it out (left = the list's left + the scrollbar's width +
PADDING; right = the list's right; macos/patches/kmrp-layout/listbox_padding.cpp), and writes
for every set and list

    offset = (rows' left - the left border's inner edge) - (the right border's inner edge - rows' right)

into macos/patches/kmrp-assets/list_rows.inc, which the module is compiled with
(macos/patches/kmrp-assets/layout.cpp, "List rows"). The border is the lit run nearest the rows
in the median brightness of the columns over the middle three fifths of the list's height: lit
is 30% of the way from the box's inside to the run's peak. Checked against the game's own picture
at 1512x982 (2026-10-04): inventory 5, quests 5, abilities 5, quest items 10 or 9, the same
columns to within one.

    python macos/tools/measure_list_rows.py LAYOUTS_ZIP ARTWORK_DIR [--check | --out FILE]

LAYOUTS_ZIP and ARTWORK_DIR are build/macos/assets-src/layouts.zip and .../override, which
macos/build.sh makes. --check compares with the committed file and fails when they differ: run
without it after the layouts or the panels' artwork change.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from pykotor.resource.formats.gff import read_gff
from pykotor.resource.formats.tpc import TPCTextureFormat, read_tpc

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "macos/patches/kmrp-assets/list_rows.inc"

# The lists whose box is in their panel's artwork. The order is the table's.
LISTS = (
    ("inventory", "LB_ITEMS"),
    ("abilities", "LB_ABILITY"),
    ("journal", "LB_ITEMS"),
    ("questitem", "LB_ITEMS"),
    ("store", "LB_INVITEMS"),
    ("store", "LB_SHOPITEMS"),
    ("upgradeitems", "LB_ITEMS"),
    ("ftchrgen", "LB_FEATS"),
    ("pwrlvlup", "LB_POWERS"),
    ("scriptselect", "LST_AIState"),
)
NONE = -128   # no border found on one side


def extent(struct) -> tuple[int, int, int, int]:
    e = struct.get_struct("EXTENT")
    return tuple(e.acquire(k, 0) for k in ("LEFT", "TOP", "WIDTH", "HEIGHT"))


def fill(struct) -> str:
    return str(struct.get_struct("BORDER").acquire("FILL", "")).lower() if struct.exists("BORDER") else ""


class Artwork:
    def __init__(self, directory: Path) -> None:
        self.files = {p.stem.lower(): p for p in directory.iterdir() if p.suffix.lower() in (".tga", ".tpc")}
        self.images: dict[str, Image.Image | None] = {}

    def get(self, name: str) -> Image.Image | None:
        if name not in self.images:
            path = self.files.get(name)
            image = None
            if path and path.suffix.lower() == ".tga":
                image = Image.open(path).convert("RGBA")
            elif path:
                tpc = read_tpc(path.read_bytes())
                tpc.convert(TPCTextureFormat.RGBA)
                mip = tpc.layers[0].mipmaps[0]
                # A .tpc's first row is the picture's bottom.
                image = Image.frombytes("RGBA", (mip.width, mip.height), bytes(mip.data)).transpose(Image.FLIP_TOP_BOTTOM)
            self.images[name] = image
        return self.images[name]


def offset(root, tag: str, scale: float, artwork: Artwork) -> int:
    """One list's offset in one layout, or NONE."""
    _, _, panel_width, panel_height = extent(root)
    controls = list(root.get_list("CONTROLS"))
    box = next((c for c in controls if c.acquire("TAG", "") == tag), None)
    if box is None or not box.acquire("LEFTSCROLLBAR", 0):
        return NONE
    x, y, w, h = extent(box)
    top, bottom = y + h // 5, y + 4 * h // 5
    if bottom <= top or top < 0 or bottom > panel_height:
        return NONE
    # The rows of the panel's picture the list's middle covers: the panel's own fill, and the
    # fills of the labels over it.
    strip = Image.new("RGBA", (panel_width, bottom - top), (0, 0, 0, 255))
    layers = [(root, (0, 0, panel_width, panel_height))]
    layers += [(c, extent(c)) for c in controls if c.acquire("CONTROLTYPE", 0) == 4]
    for control, (cx, cy, cw, ch) in layers:
        image = artwork.get(fill(control)) if fill(control) else None
        if image is None or cw <= 0 or ch <= 0 or cx < 0:
            continue
        first, last = max(top, cy), min(bottom, cy + ch)
        if last <= first:
            continue
        source = (0, (first - cy) * image.height / ch, image.width, (last - cy) * image.height / ch)
        strip.alpha_composite(image.resize((cw, last - first), Image.BILINEAR, box=source), (cx, first - top))
    light = np.median(np.asarray(strip.convert("RGB")).astype(int).sum(axis=2), axis=0)
    bar = extent(box.get_struct("SCROLLBAR"))[2] if box.exists("SCROLLBAR") else 0
    left, right = x + bar + box.acquire("PADDING", 0), x + w
    if right - left < 80 * scale or right > panel_width:
        return NONE
    inside = float(np.median(light[left + int(20 * scale): left + int(60 * scale)]))

    def lit(first: int, last: int) -> list[int]:
        window = light[first:last]
        if not len(window) or window.max() < inside + 40:
            return []
        level = inside + 0.3 * (window.max() - inside)
        return [first + i for i, value in enumerate(window) if value >= level]

    reach = int(30 * scale)
    on_left, on_right = lit(max(0, left - reach), left + 3), lit(right - 3, min(panel_width, right + reach))
    if not on_left or not on_right:
        return NONE
    result = (left - (on_left[-1] + 1)) - (on_right[0] - right)
    return max(-127, min(127, result))


def measure(layouts: Path, artwork_dir: Path) -> str:
    artwork = Artwork(artwork_dir)
    rows = []
    with zipfile.ZipFile(layouts) as archive:
        sizes = sorted((n[len("index/"):-len(".txt")] for n in archive.namelist() if n.startswith("index/")),
                       key=lambda s: (int(s.split("x")[1]), int(s.split("x")[0])))
        for size in sizes:
            width, height = map(int, size.split("x"))
            index = dict(line.split("\t") for line in archive.read(f"index/{size}.txt").decode().replace("\r", "").splitlines() if line)
            index = {name.lower(): obj for name, obj in index.items()}
            values = []
            guis: dict[str, object] = {}
            for gui, tag in LISTS:
                obj = index.get(f"{gui}.gui")
                if obj is None:
                    values.append(NONE)
                    continue
                if gui not in guis:
                    guis[gui] = read_gff(archive.read(f"objects/{obj}")).root
                values.append(offset(guis[gui], tag, max(1.0, height / 720), artwork))
            rows.append((width, height, values))
    text = ["// Made by macos/tools/measure_list_rows.py from the menu sets and the panels' artwork: not to be",
            "// edited. Per set, per list: (the rows' left - the box's left border) - (the box's right border -",
            "// the rows' right), in that set's pixels; kNoBox where the artwork has no border on a side.",
            "const char* const kMeasuredLists[] = {"]
    text += [f'    "{gui}.{tag}",' for gui, tag in LISTS]
    text += ["};", "const int kNoBox = -128;",
             f"struct MeasuredSet {{ short width, height; signed char offset[{len(LISTS)}]; }};",
             "const MeasuredSet kMeasuredSets[] = {"]
    text += [f"    {{{w}, {h}, {{{', '.join(str(v) for v in values)}}}}}," for w, h, values in rows]
    text += ["};", ""]
    return "\n".join(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("layouts", type=Path)
    parser.add_argument("artwork", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", type=Path, default=TABLE)
    args = parser.parse_args()
    text = measure(args.layouts, args.artwork)
    if args.check:
        same = args.out.is_file() and args.out.read_text() == text
        print(f"{'ok  ' if same else 'FAIL'} {args.out.name} is what the menu sets and the artwork measure to")
        return 0 if same else 1
    args.out.write_text(text)
    print(f"{args.out}: {len(text.splitlines()) - 9 - len(LISTS)} sets, {len(LISTS)} lists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
