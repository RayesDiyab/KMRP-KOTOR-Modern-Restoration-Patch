#!/usr/bin/env python3
"""The two pictures of a hotfix release: the cover with HOTFIX on it, and what was fixed.

Both are the 1.5 press kit's own pages with other words: the cover is
`build_release_cover.py`'s composition (the patcher's lockup, KMRP in its metal, the
version in gold) with a green HOTFIX between the name and the lines, and the second
page is `build_release_shots.py`'s card (two metal lines, a list, a foot line) with
room for a longer list. Nothing is drawn that those two do not already draw; their
functions are imported, not copied.

    python tools/build_hotfix_art.py            # releases/v1.5.1/press-kit/

What the pictures say is in HOTFIX_LINES and FIXED below. Every line of FIXED is an
entry of CHANGELOG.md's [1.5.1]; one that was not tried where it matters says so.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

import numpy as np

import build_release_cover as cover
import build_release_shots as shots
from build_brand_image import DEFAULT_FONT

VERSION = "1.5.1"
OUT = Path("releases/v1.5.1/press-kit")

# The cover has HOTFIX and nothing under it: what it fixes and where it runs are the
# second page's to say (the maintainer, 2026-10-12: "just the hotfix").
HOTFIX_LINES = ()

# The second page, in the changelog's order of what a player notices.
FIXED = (
    "SteamOS: tested and working",
    "Linux with Proton: the game starts again",
    "The installer finds the game under Proton, and Restore Original completes",
    "Mods in Override always win: load screens, textures, icons, fonts",
    "Translations: their fonts are drawn at the right size (Polish tested)",
    "Changing resolution with a controller no longer ends the game",
    "Pazaak with a controller: A plays the selected card",
    "PadForge, DS4Windows and the like: no more stuttering movement",
    "Xbox pad on Bluetooth under Linux: Back no longer flashes the keyboard HUD",
    "No more 177 MB left in the temp folder at every start",
    "Windows 7: the start-up error is removed (not yet tested there)",
)
# HOTFIX is green (the maintainer, 2026-10-12: "hotfix in a green that fits"): the
# green of a fix, taken towards the cover's blue so that it sits with the silver, the
# gold and the accent. Dark, middle and highlight, as cover.GOLD_RAMP is for the gold.
GREEN = (74, 204, 132)
GREEN_RAMP = ((8, 66, 44), (58, 190, 118), (206, 255, 226))


def green_metal(metal: Image.Image) -> Image.Image:
    """A silver `metal_text` image with the same shading in green (as cover.gold_metal)."""
    arr = np.asarray(metal).astype(np.float32)
    lum = arr[..., :3].max(axis=2) / 255.0
    low, mid, high = (np.array(c, dtype=np.float32) for c in GREEN_RAMP)
    lower = low + (mid - low) * np.clip(lum / 0.6, 0, 1)[..., None]
    upper = mid + (high - mid) * np.clip((lum - 0.6) / 0.4, 0, 1)[..., None]
    rgb = np.where((lum < 0.6)[..., None], lower, upper)
    out = np.dstack([rgb, arr[..., 3:4]])
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


FOOT = "Tested on Windows 11 and on SteamOS with Proton 11. The macOS release stays 1.5.0."


def build_cover(out: Path, root: Path) -> None:
    """build_release_cover.build, with HOTFIX in gold metal between the name and the lines."""
    theme = cover.read_theme(root / cover.THEME_SOURCE)
    width, height = 1920, 1080
    canvas = cover.ground((width, height), theme)

    lockup = Image.open(root / cover.LOCKUP).convert("RGBA")
    lockup = lockup.crop(lockup.getbbox())
    target_w = int(width * 0.58)
    lockup = lockup.resize((target_w, int(lockup.height * target_w / lockup.width)), Image.LANCZOS)
    lockup_y = int(height * 0.06)
    canvas.alpha_composite(lockup, ((width - lockup.width) // 2, lockup_y))

    cap = int(height * 0.082)
    word = cover.metal_text("KMRP", cap, DEFAULT_FONT)
    number = cover.gold_metal(cover.metal_text(VERSION, cap, DEFAULT_FONT))
    word = word.crop((word.getbbox()[0], 0, word.getbbox()[2], word.height))
    number = number.crop((number.getbbox()[0], 0, number.getbbox()[2], number.height))
    gap = int(height * 0.045)
    name = Image.new("RGBA", (word.width + gap + number.width, max(word.height, number.height)), (0, 0, 0, 0))
    name.alpha_composite(word, (0, 0))
    name.alpha_composite(number, (word.width + gap, 0))
    name_y = lockup_y + lockup.height + int(height * 0.008)
    canvas.alpha_composite(name, ((width - name.width) // 2, name_y))

    draw = ImageDraw.Draw(canvas)
    mid = name_y + name.height // 2
    reach = name.width // 2 + int(width * 0.045)
    rule = int(width * 0.075)
    for direction in (-1, 1):
        x0 = width // 2 + direction * reach
        x1 = x0 + direction * rule
        draw.line([(min(x0, x1), mid), (max(x0, x1), mid)], fill=theme["Border"] + (215,), width=2)

    sub_size = int(height * 0.03)
    sub_y = name_y + name.height + int(height * 0.045)
    cover.tracked(draw, (0, sub_y), "MODERN RESTORATION PATCH", shots.font(DEFAULT_FONT, sub_size),
                  theme["Accent"] + (255,), sub_size * 0.42, anchor_centre_x=width / 2)

    # HOTFIX: the lockup's metal in green, between two green rules, the one thing on
    # the page the 1.5 cover does not have.
    hot = green_metal(cover.metal_text("HOTFIX", int(height * 0.064), DEFAULT_FONT))
    hot = hot.crop(hot.getbbox())
    hot_y = sub_y + int(height * 0.05)
    canvas.alpha_composite(hot, ((width - hot.width) // 2, hot_y))
    hot_mid = hot_y + hot.height // 2
    for direction in (-1, 1):
        x0 = width // 2 + direction * (hot.width // 2 + 36)
        x1 = x0 + direction * 220
        draw.line([(min(x0, x1), hot_mid), (max(x0, x1), hot_mid)], fill=GREEN + (255,), width=3)

    foot_size = int(height * 0.029)
    foot_font = shots.font(cover.BOLD_FONT, foot_size)
    foot_y = hot_y + hot.height + int(height * 0.062)
    for row, line in enumerate(HOTFIX_LINES):
        last = row == len(HOTFIX_LINES) - 1
        cover.tracked(draw, (0, foot_y + row * int(foot_size * 1.7)), line, foot_font,
                      (theme["Text"] if last else cover.GOLD) + (255,), foot_size * 0.22,
                      anchor_centre_x=width / 2)

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, optimize=True)
    print(f"  {out}  {width}x{height}  {out.stat().st_size} bytes")


def build_fixed(out: Path, root: Path) -> None:
    """build_release_shots.card's page, with a list of eleven in place of four."""
    theme = cover.read_theme(root / cover.THEME_SOURCE)
    shots.VERSION = VERSION                     # the header's number
    canvas = shots.ground((1920, 1080), theme, False)
    top, cap = 168, 64
    for row, (words, green) in enumerate((("WHAT WAS FIXED", False), ("HOTFIX FOR KMRP 1.5", True))):
        image = cover.metal_text(words, cap, DEFAULT_FONT)
        if green:
            image = green_metal(image)
        image = image.crop(image.getbbox())
        canvas.alpha_composite(image, ((1920 - image.width) // 2, top + row * int(cap * 1.6)))
    draw = ImageDraw.Draw(canvas)
    face = shots.font(DEFAULT_FONT, 33)
    widest = max(draw.textlength(line, font=face) for line in FIXED)
    x = (1920 - widest - 34) // 2
    y = top + int(cap * 3.75)
    for line in FIXED:
        draw.rectangle([x, y - 15, x + 12, y - 3], fill=shots.AMBER + (255,))
        draw.text((x + 34, y), line, font=face, fill=(226, 233, 242, 255), anchor="ls")
        y += 54
    shots.header(canvas, theme, "HOTFIX", False)
    shots.footer(canvas, theme, FOOT)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, optimize=True)
    print(f"  {out}  1920x1080  {out.stat().st_size} bytes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out", type=Path, default=None, help="folder for the two pictures (default: %s)" % OUT)
    args = parser.parse_args()
    out = args.out or args.root / OUT
    build_cover(out / "01-cover-hotfix.png", args.root)
    build_fixed(out / "02-what-was-fixed.png", args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
