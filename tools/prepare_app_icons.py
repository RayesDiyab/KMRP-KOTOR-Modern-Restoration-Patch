#!/usr/bin/env python3
"""Turn the hand-supplied step icons in `App icons/` into embeddable resources.

The source art is a silhouette on transparency -- the ink's own colour does not
matter, only its alpha. Each icon is cropped to its visible ink, scaled into the
same visual box without changing its aspect ratio, centred on an identical
square canvas, and written out as **white** ink with the original alpha. White
is deliberate: the patcher tints at draw time with a colour matrix, and
multiplying white by the target colour reproduces it exactly, so the icon colour
stays a single constant in the UI code rather than being baked into four PNGs.

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


CANVAS_SIZE = 256   # generous: the badge draws these at ~36px, so downscale only
INK_SIZE = 224      # every icon's longest visible dimension; leaves equal margins
ALPHA_FLOOR = 8     # ignore near-transparent dust when cropping to the ink
CENTER_TOLERANCE = 1.0
LANCZOS = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

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


def visible_box(alpha: Image.Image) -> tuple[int, int, int, int] | None:
    """Return the bounds of meaningful alpha, excluding resampling dust."""
    return alpha.point(lambda value: 255 if value > ALPHA_FLOOR else 0).getbbox()


def convert(
    source: Path, dest: Path
) -> tuple[tuple[int, int], tuple[int, int, int, int]]:
    image = Image.open(source).convert("RGBA")
    alpha = image.split()[3]

    box = visible_box(alpha)
    if box is None:
        raise ValueError("the image is fully transparent")
    alpha = alpha.crop(box)

    # Give every glyph the same longest visible dimension. The other dimension
    # follows the source aspect ratio, so a wide monitor and a tall shield remain
    # recognisably themselves instead of being stretched to the same square.
    scale = INK_SIZE / max(alpha.size)
    resized_size = (
        max(1, round(alpha.width * scale)),
        max(1, round(alpha.height * scale)),
    )
    alpha = alpha.resize(resized_size, LANCZOS)

    canvas = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0)
    paste_at = (
        (CANVAS_SIZE - alpha.width) // 2,
        (CANVAS_SIZE - alpha.height) // 2,
    )
    canvas.paste(alpha, paste_at)

    final_box = visible_box(canvas)
    if final_box is None:
        raise ValueError("the resized image became fully transparent")

    expected_center = (CANVAS_SIZE - 1) / 2
    actual_center = (
        (final_box[0] + final_box[2] - 1) / 2,
        (final_box[1] + final_box[3] - 1) / 2,
    )
    if any(abs(value - expected_center) > CENTER_TOLERANCE for value in actual_center):
        raise ValueError(
            "normalised ink is not centred: "
            f"centre={actual_center}, expected={expected_center}"
        )

    final_size = (final_box[2] - final_box[0], final_box[3] - final_box[1])
    if abs(max(final_size) - INK_SIZE) > 2:
        raise ValueError(
            f"normalised ink is {final_size}, expected a {INK_SIZE}px longest edge"
        )

    out = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 0))
    out.putalpha(canvas)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, optimize=True)
    return (box[2] - box[0], box[3] - box[1]), final_box


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
        source_size, final_box = convert(path, args.dest / (step + ".png"))
        seen[step] = path.name
        final_size = (final_box[2] - final_box[0], final_box[3] - final_box[1])
        print(
            f"  {path.name:<28} -> {step}.png   "
            f"(source ink {source_size[0]}x{source_size[1]}, "
            f"normalised {final_size[0]}x{final_size[1]}, box {final_box})"
        )

    missing = [step for step, _ in KEYWORDS if step not in seen]
    print(f"\n{len(seen)} of 4 icons supplied.")
    if missing:
        print("still drawn as vectors: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
