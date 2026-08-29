#!/usr/bin/env python3
"""Render the installed 800x600 UI backgrounds as a labeled contact sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("override", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    files = sorted(args.override.glob("800x600*.tga"))
    files += sorted(args.override.glob("800x600*.tga.disabled*.bak"))
    cells = []
    for path in files:
        image = Image.open(path).convert("RGB")
        image.thumbnail((700, 260))
        cell = Image.new("RGB", (720, 300), "white")
        cell.paste(image, ((720 - image.width) // 2, 25))
        ImageDraw.Draw(cell).text((10, 5), path.name, fill="black")
        cells.append(cell)

    sheet = Image.new("RGB", (1440, ((len(cells) + 1) // 2) * 300), (80, 80, 80))
    for index, cell in enumerate(cells):
        sheet.paste(cell, ((index % 2) * 720, (index // 2) * 300))
    sheet.save(args.output, quality=92)
    print(f"Wrote {args.output} with {len(cells)} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
