#!/usr/bin/env python3
"""Turn the hand-supplied step icons in `App icons/` into embeddable resources.

The source art is a silhouette on transparency -- the ink's own colour does not
matter, only its alpha. Each icon is cropped to its ink, squared, resized, and
written out as **white** ink with the original alpha. White is deliberate: the
patcher tints at draw time with a colour matrix, and multiplying white by the
target colour reproduces it exactly, so the icon colour stays a single constant
in the UI code rather than being baked into four PNGs.

Files are matched to steps by keyword, so the names in `App icons/` can be
whatever is convenient:

    folder / directory   -> step 1
    shield / verify      -> step 2
    monitor / display / screen / resolution -> step 3
    tool / wrench / patch / apply           -> step 4

Anything unmatched is reported and skipped; any step without an icon falls back
to the vector glyph drawn in UiTheme.DrawGlyph, so a partial set still builds.

    python tools/prepare_app_icons.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


SIZE = 256          # generous: the badge draws these at ~36px, so downscale only
ALPHA_FLOOR = 8     # ignore near-transparent dust when cropping to the ink

KEYWORDS = (
    ("folder", ("folder", "directory", "game")),
    ("shield", ("shield", "verify", "check")),
    ("monitor", ("monitor", "display", "screen", "resolution")),
    ("tools", ("tool", "wrench", "patch", "apply", "spanner")),
)


def classify(name: str) -> str | None:
    lowered = name.lower()
    for step, words in KEYWORDS:
        for word in words:
            if word in lowered:
                return step
    return None


def convert(source: Path, dest: Path) -> tuple[int, int]:
    image = Image.open(source).convert("RGBA")
    alpha = image.split()[3]

    box = alpha.point(lambda v: 255 if v > ALPHA_FLOOR else 0).getbbox()
    if box is None:
        raise ValueError("the image is fully transparent")
    alpha = alpha.crop(box)

    # Square it on the longer edge so every icon shares one baseline, and the
    # per-glyph aspect stays whatever the artwork says rather than being stretched.
    side = max(alpha.size)
    canvas = Image.new("L", (side, side), 0)
    canvas.paste(alpha, ((side - alpha.width) // 2, (side - alpha.height) // 2))
    canvas = canvas.resize((SIZE, SIZE), Image.LANCZOS)

    out = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    out.putalpha(canvas)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, optimize=True)
    return box[2] - box[0], box[3] - box[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("App icons"))
    parser.add_argument("--dest", type=Path, default=Path("app/patcher/icons"))
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"No icon folder at {args.source}")

    seen = {}
    for path in sorted(args.source.iterdir()):
        if path.suffix.lower() not in (".png", ".webp", ".tif", ".tiff"):
            continue
        step = classify(path.stem)
        if step is None:
            print(f"  {path.name}: no keyword matched, skipped")
            continue
        if step in seen:
            print(f"  {path.name}: '{step}' already supplied by {seen[step]}, skipped")
            continue
        w, h = convert(path, args.dest / (step + ".png"))
        seen[step] = path.name
        print(f"  {path.name:<28} -> {step}.png   (source ink {w}x{h})")

    missing = [step for step, _ in KEYWORDS if step not in seen]
    print(f"\n{len(seen)} of 4 icons supplied.")
    if missing:
        print("still drawn as vectors: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
