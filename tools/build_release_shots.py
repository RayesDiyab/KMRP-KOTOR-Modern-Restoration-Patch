#!/usr/bin/env python3
"""Compose the KMRP 1.5 release images from screenshots: comparisons and controller pages.

The 1.0 set (`build_before_after.py`, `assets/screenshots/1-*.png`) put two equal
panels side by side under BEFORE and AFTER plates. This is the 1.5 set, and it is
meant to look like another release at a glance:

| page | what it shows |
| --- | --- |
| `pair` | the original game small on the left, KMRP large on the right, each frame whole |
| `wide` | the original game small at the top, an ultrawide KMRP frame across the page |
| `solo` | one KMRP frame, for the controller pages |
| `grid` | four KMRP frames, for the controller prompts |
| `card` | an announcement in words: a silver line, a gold line, a few facts, and a frame if there is one |

Every page carries the name in the cover's silver metal with the version in its gold,
the page's subject,
each frame's own resolution under it, and one line saying what to look at.

**Nothing in a frame is retouched or cropped.** A frame is scaled down whole. The
"original game" frames are the unchanged game's interface at the largest size the
unchanged game offers for that display: 1280x960 beside 1920x1080 and 1600x1200
beside 3440x1440. They were taken in a copy of the game that has only the
controller patch, with the pointer moved so that no controller picture is on
screen; the interface in them is the game's own.

**Colours come from `UiTheme`** in `src/patcher/KmrpPatcher.cs`, through
`build_release_cover.read_theme`, as on the cover.

Usage:

    python tools/build_release_shots.py                 # every page of PAGES
    python tools/build_release_shots.py --only 01       # pages whose name begins so

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from build_brand_image import DEFAULT_FONT
from build_release_cover import GOLD, THEME_SOURCE, gold_metal, metal_text, read_theme

VERSION = "1.5"
BOLD_FONT = Path(r"C:\Windows\Fonts\georgiab.ttf")
AMBER = GOLD                    # the version and the controller pages: the cover's gold
SILVER = (198, 206, 218)        # the original game's frames and the plain words
ORIGINAL = "ORIGINAL GAME"
SHOTS = Path("build/controller-standalone/shots")
OUT = Path("releases/v1.5.0/press-kit")      # with 01-cover.png, which build_release_cover.py writes

# (output name, kind, subject, the line under the frames, frames)
# A frame is (screenshot name without .png, label). Screenshot names: k1080 and k1440
# are KMRP at 1920x1080 and 3440x1440, v960 and v1200 the original interface at
# 1280x960 and 1600x1200; "-pad" is the frame as the pad left it.
PAGES = (
    # The maintainer's order of 2026-10-09: 01 is the cover (build_release_cover.py), 02 to 10
    # the pages a post leads with, and the rest follow. A page whose screenshot is not in
    # the folder is skipped and named; nothing stands in for it.
    ("02-new-platform-macos", "card", "NEW PLATFORM",
     "For the Steam version of the game on the Mac. Tested on an Apple Silicon MacBook Pro; Intel Macs are untested.",
     (("mac-installer", "THE INSTALLER ON macOS"),)),
    ("03-macos-character", "solo", "NEW IN 1.5: macOS",
     "The same menus and text on the Mac, with controller support, which the Mac game does not have on its own.",
     (("mac-character", "macOS  1512x982"),)),
    ("04-linux-proton", "card", "LINUX",
     "Tested on Ubuntu with a development build of 1.5. The Steam Deck was not tested on the device.",
     ()),
    ("05-inventory-1080p", "pair", "INVENTORY",
     "Rows, icons and text sized for the screen. HD item icons. Nothing cut off.",
     (("v960-inventory", "1280x960"), ("k1080-inventory", "1920x1080"))),
    ("06-inventory-ultrawide", "wide", "INVENTORY, ULTRAWIDE",
     "21:9 has its own menus: not stretched, not letterboxed.",
     (("v1200-inventory", "1600x1200"), ("k1440-inventory", "3440x1440"))),
    ("07-4k", "solo", "4K",
     "On a 4K television the display and its text are made for 3840x2160, not enlarged.",
     (("k2160-game", "3840x2160"),)),      # the maintainer's frame from a 4K television; it reached the repo reduced to 2000x1125
    ("08-controller-xbox-hud", "solo", "CONTROLLER: XBOX-STYLE HUD",
     "New in 1.5. With a pad the display is laid out like the Xbox game's; touch the mouse and the PC display is back.",
     (("k1080-paused-pad", "1920x1080"),)),
    ("09-controller-menus", "grid", "CONTROLLER: EVERY MENU",
     "Button pictures for Xbox, PlayStation and Switch pads on every screen. They go away when you use the mouse.",
     (("k1080-inventory-pad", "INVENTORY"), ("k1080-character-pad", "CHARACTER"),
      ("k1080-journal-pad", "JOURNAL"), ("k1080-map-pad", "AREA MAP"))),
    ("10-controller-layout", "solo", "CONTROLLER: LAYOUT SCREEN",
     "New in 1.5. Options, Gameplay, Controller Layout shows what every button does, drawn for your pad.",
     (("k1440-layout-pad", "3440x1440"),)),
    ("11-equipment-1080p", "pair", "EQUIPMENT",
     "The whole screen is used. Every slot and every row in its place.",
     (("v960-equip", "1280x960"), ("k1080-equip", "1920x1080"))),
    ("12-area-map-1080p", "pair", "AREA MAP",
     "The map fills its frame, fog covers all of it, and markers are where you click.",
     (("v960-map", "1280x960"), ("k1080-map", "1920x1080"))),
    ("13-abilities-1080p", "pair", "ABILITIES",
     "Skills, powers and feats with icons and descriptions you can read.",
     (("v960-abilities", "1280x960"), ("k1080-abilities", "1920x1080"))),
    ("14-character-1080p", "pair", "CHARACTER",
     "Text drawn sharp for the resolution, not enlarged from a small picture.",
     (("v960-character", "1280x960"), ("k1080-character", "1920x1080"))),
    ("15-journal-1080p", "pair", "JOURNAL",
     "Lists keep their rows, and long text stays inside its box.",
     (("v960-journal", "1280x960"), ("k1080-journal", "1920x1080"))),
    ("16-hud-1080p", "pair", "IN THE GAME",
     "Widescreen without stretching, with the display scaled to the screen.",
     (("v960-hud", "1280x960"), ("k1080-hud", "1920x1080"))),
    ("17-equipment-ultrawide", "wide", "EQUIPMENT, ULTRAWIDE",
     "Every resolution your display has is in the game's own list.",
     (("v1200-equip", "1600x1200"), ("k1440-equip", "3440x1440"))),
    ("18-area-map-ultrawide", "wide", "AREA MAP, ULTRAWIDE",
     "The map and its markers, sized for 3440x1440.",
     (("v1200-map", "1600x1200"), ("k1440-map", "3440x1440"))),
    ("19-abilities-ultrawide", "wide", "ABILITIES, ULTRAWIDE",
     "From 4:3 to 32:9, the menus are made for the shape of the screen.",
     (("v1200-abilities", "1600x1200"), ("k1440-abilities", "3440x1440"))),
    ("20-hud-ultrawide", "wide", "IN THE GAME, ULTRAWIDE",
     "The game starts at your display's resolution. Nothing to set up.",
     (("v1200-hud", "1600x1200"), ("k1440-hud", "3440x1440"))),
    ("21-controller-xbox-hud-ultrawide", "solo", "CONTROLLER: XBOX-STYLE HUD, ULTRAWIDE",
     "Action menu, target, party and minimap in the corners, the pause notice with your pad's trigger.",
     (("k1440-paused-pad", "3440x1440"),)),
    ("22-macos-installer", "solo", "NEW IN 1.5: macOS",
     "The Mac has its own installer, for the Steam version of the game: one click to patch, one click to undo.",
     (("mac-installer", "THE INSTALLER ON macOS"),)),
    ("23-macos-options", "solo", "NEW IN 1.5: macOS",
     "The same options as on Windows. High FPS Fix switches itself on where the display runs above 60 Hz.",
     (("mac-settings", "THE INSTALLER ON macOS"),)),
    ("24-macos-map", "solo", "NEW IN 1.5: macOS",
     "The area map and its fixes on a MacBook Pro, with the buttons of the pad in use.",
     (("mac-map", "macOS  1512x982"),)),
    ("25-macos-screens", "solo", "NEW IN 1.5: macOS",
     "In the game, the map, the options, equipment, inventory and character on a MacBook Pro.",
     (("mac-screens", "macOS  SIX SCREENS AT 1512x982"),)),
    ("26-4k-menu", "solo", "4K",
     "Connect another display and the game offers that display's resolutions.",
     (("k2160-menu", None),)),
)


def font(path: Path, size: int):
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.truetype(str(DEFAULT_FONT), size)


def tracked(draw, x, y, text, face, fill, tracking, centre=None, right=None):
    """Letter-spaced text on a baseline; returns its width."""
    widths = [draw.textlength(ch, font=face) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    if centre is not None:
        x = centre - total / 2
    if right is not None:
        x = right - total
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=face, fill=fill, anchor="ls")
        x += w + tracking
    return total


def ground(size, theme, controller):
    """The page: the app's panel colour, lighter towards the top, with one soft glow."""
    width, height = size
    base = Image.new("RGB", size, theme["Window"])
    glow = Image.new("L", size, 0)
    ImageDraw.Draw(glow).ellipse([width * 0.25, -height * 0.55, width * 1.15, height * 0.75], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(width // 9))
    tint = Image.new("RGB", size, AMBER if controller else theme["Accent"])
    base = Image.composite(tint, base, glow.point(lambda v: v // 3))
    return base.convert("RGBA")


def header(canvas, theme, subject, controller):
    """KMRP in the cover's silver metal, the version in its gold, the subject at the right."""
    width = canvas.width
    draw = ImageDraw.Draw(canvas)
    x, base = 56, 92
    word = metal_text("KMRP", 44, DEFAULT_FONT)
    number = gold_metal(metal_text(VERSION, 44, DEFAULT_FONT))
    wbox, nbox = word.getbbox(), number.getbbox()
    canvas.alpha_composite(word.crop(wbox), (x, base - (wbox[3] - wbox[1]) + 6))
    nx = x + (wbox[2] - wbox[0]) + 26
    canvas.alpha_composite(number.crop(nbox), (nx, base - (nbox[3] - nbox[1]) + 6))
    end = nx + (nbox[2] - nbox[0])
    title = font(BOLD_FONT, 30)
    tracked(draw, 0, base - 8, subject, title, (AMBER if controller else theme["Accent"]) + (255,), 6,
            right=width - 56)
    draw.line([(56, 118), (width - 56, 118)], fill=theme["Border"] + (255,), width=2)
    draw.line([(56, 118), (end + 20, 118)], fill=AMBER + (255,), width=3)


def footer(canvas, theme, line):
    draw = ImageDraw.Draw(canvas)
    face = font(DEFAULT_FONT, 27)
    while draw.textlength(line, font=face) > canvas.width - 140 and face.size > 16:
        face = font(DEFAULT_FONT, face.size - 1)
    draw.text((canvas.width / 2, canvas.height - 40), line, font=face, fill=AMBER + (255,), anchor="ms")


def frame(canvas, theme, shot: Image.Image, box, label, kmrp, controller=False):
    """One screenshot, whole, scaled into `box` (x, y, width), with its label under it."""
    x, y, width = box
    height = round(shot.height * width / shot.width)
    small = shot.resize((width, height), Image.LANCZOS)
    edge = (AMBER if controller else theme["Accent"]) if kmrp else SILVER
    if kmrp:
        halo = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(halo).rectangle([x - 6, y - 6, x + width + 6, y + height + 6], fill=edge + (120,))
        canvas.alpha_composite(halo.filter(ImageFilter.GaussianBlur(18)))
    canvas.paste(small, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([x - 2, y - 2, x + width + 1, y + height + 1], outline=edge + (255,), width=2)
    if label:
        face = font(DEFAULT_FONT, 22)
        tracked(draw, x, y + height + 36, label, face, edge + (255,), 4)
    return height


# A card's words: the silver line, the gold line, and its facts.
CARDS = {
    "02-new-platform-macos": ("NEW PLATFORM", "macOS SUPPORT", (
        "Its own installer: one click to patch, one click to undo",
        "The same menus, text and art, Retina included",
        "Controller support, new to the Mac game",
        "High FPS Fix, ported to the Mac game",
    )),
    "04-linux-proton": ("TESTED ON LINUX", "UBUNTU WITH PROTON", (
        "Installed and played on Ubuntu",
        "With the stable Proton and with Proton Experimental",
        "The Windows installer, run through protontricks",
        "Steam Deck: the same Proton, expected to work the same way",
    )),
}


def card(name, subject, line, frames, theme, shots: Path) -> Image.Image:
    silver, gold, facts = CARDS[name]
    canvas = ground((1920, 1080), theme, False)
    picture = load(shots, frames[0][0]) if frames else None
    left = 96 if picture else None
    cap = 66 if picture else 92
    top = 250 if picture else 270
    for row, (words, metal) in enumerate(((silver, False), (gold, True))):
        image = metal_text(words, cap, DEFAULT_FONT)
        if metal:
            image = gold_metal(image)
        image = image.crop(image.getbbox())
        limit = 820 if picture else 1700
        if image.width > limit:
            image = image.resize((limit, round(image.height * limit / image.width)), Image.LANCZOS)
        x = left if picture else (1920 - image.width) // 2
        canvas.alpha_composite(image, (x, top + row * int(cap * 1.75)))
    draw = ImageDraw.Draw(canvas)
    face = font(DEFAULT_FONT, 30 if picture else 38)
    y = top + int(cap * 3.9)
    step = 58 if picture else 72
    width = max(draw.textlength(fact, font=face) for fact in facts)
    while picture and width + 34 > 800 and face.size > 18:      # clear of the frame beside it
        face = font(DEFAULT_FONT, face.size - 1)
        width = max(draw.textlength(fact, font=face) for fact in facts)
    x = left if picture else (1920 - width) // 2
    for fact in facts:
        draw.rectangle([x, y - 16, x + 12, y - 4], fill=AMBER + (255,))
        draw.text((x + 34, y), fact, font=face, fill=(226, 233, 242, 255), anchor="ls")
        y += step
    if picture:
        width = 860
        height = round(picture.height * width / picture.width)
        frame(canvas, theme, picture, (1920 - 72 - width, 150 + (820 - height) // 2, width), frames[0][1], True)
    header(canvas, theme, subject, False)
    footer(canvas, theme, line)
    return canvas.convert("RGB")


def load(shots: Path, name: str) -> Image.Image:
    path = shots / (name + ".png")
    if not path.exists():
        raise SystemExit(f"Not found: {path}")
    return Image.open(path).convert("RGB")


def compose(kind, subject, line, frames, theme, shots: Path) -> Image.Image:
    controller = subject.startswith("CONTROLLER")
    pictures = [load(shots, name) for name, _ in frames]
    labels = [label or "%dx%d" % picture.size for (_, label), picture in zip(frames, pictures)]
    if kind == "pair":
        canvas = ground((1920, 1080), theme, controller)
        before_w, after_w = 560, 1196
        before_h = round(pictures[0].height * before_w / pictures[0].width)
        after_h = round(pictures[1].height * after_w / pictures[1].width)
        top = 150 + (820 - after_h) // 2
        frame(canvas, theme, pictures[0], (56, top + (after_h - before_h) // 2, before_w),
              ORIGINAL + "  " + labels[0], False)
        frame(canvas, theme, pictures[1], (1920 - 56 - after_w, top, after_w),
              "KMRP " + VERSION + "  " + labels[1], True)
        draw = ImageDraw.Draw(canvas)
        mid = top + after_h // 2
        ax = 56 + before_w + (1920 - 112 - before_w - after_w) // 2
        draw.polygon([(ax - 12, mid - 22), (ax + 14, mid), (ax - 12, mid + 22)], fill=AMBER + (255,))
    elif kind == "wide":
        after_w = 1808
        after_h = round(pictures[1].height * after_w / pictures[1].width)
        before_w = 400
        before_h = round(pictures[0].height * before_w / pictures[0].width)
        canvas = ground((1920, 150 + before_h + 74 + after_h + 150), theme, controller)
        frame(canvas, theme, pictures[0], (56, 150, before_w), ORIGINAL + "  " + labels[0], False)
        draw = ImageDraw.Draw(canvas)
        big = font(BOLD_FONT, 54)
        tx = 56 + before_w + 70
        tracked(draw, tx, 150 + 92, "THE SAME SCREEN,", big, SILVER + (255,), 5)
        tracked(draw, tx, 150 + 168, "MADE FOR YOUR DISPLAY", big, AMBER + (255,), 5)
        note = font(DEFAULT_FONT, 26)
        draw.text((tx, 150 + 228), "Left: all the original game can do on this monitor.", font=note,
                  fill=(170, 182, 198, 255), anchor="ls")
        draw.text((tx, 150 + 266), "Below: KMRP " + VERSION + " at the monitor's own resolution.", font=note,
                  fill=(170, 182, 198, 255), anchor="ls")
        frame(canvas, theme, pictures[1], (56, 150 + before_h + 74, after_w),
              "KMRP " + VERSION + "  " + labels[1], True)
    elif kind == "solo":
        wide = pictures[0].width / pictures[0].height > 2
        width = 1808 if wide else 1500
        if pictures[0].width / pictures[0].height < 1.2:     # a sheet of several screens
            width = 1180
        if pictures[0].width < width:           # a small frame (an installer's window) is not enlarged
            width = pictures[0].width
        height = round(pictures[0].height * width / pictures[0].width)
        canvas = ground((1920, 150 + height + 150), theme, controller)
        frame(canvas, theme, pictures[0], ((1920 - width) // 2, 150, width),
              "KMRP " + VERSION + "  " + labels[0], True, controller)
    else:
        width = 880
        height = round(pictures[0].height * width / pictures[0].width)
        canvas = ground((1920, 150 + 2 * (height + 64) + 86), theme, controller)
        for index, (picture, label) in enumerate(zip(pictures, labels)):
            frame(canvas, theme, picture, (56 + (index % 2) * (width + 48), 150 + (index // 2) * (height + 64), width),
                  label, True, controller)
    header(canvas, theme, subject, controller)
    footer(canvas, theme, line)
    return canvas.convert("RGB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--shots", type=Path, default=None, help="folder of screenshots (default: %s)" % SHOTS)
    parser.add_argument("--out", type=Path, default=None, help="folder for the pages (default: %s)" % OUT)
    parser.add_argument("--only", default="", help="only pages whose name begins with this")
    args = parser.parse_args()
    theme = read_theme(args.root / THEME_SOURCE)
    shots = args.shots or args.root / SHOTS
    out = args.out or args.root / OUT
    out.mkdir(parents=True, exist_ok=True)
    for name, kind, subject, line, frames in PAGES:
        if not name.startswith(args.only):
            continue
        missing = [shot for shot, _ in frames if not (shots / (shot + ".png")).exists()]
        if missing:
            print(f"  {name}: waiting for {', '.join(m + '.png' for m in missing)} in {shots}")
            continue
        page = (card(name, subject, line, frames, theme, shots) if kind == "card"
                else compose(kind, subject, line, frames, theme, shots))
        target = out / (name + ".png")
        page.save(target, optimize=True)
        print(f"  {target.name}  {page.width}x{page.height}  {target.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
