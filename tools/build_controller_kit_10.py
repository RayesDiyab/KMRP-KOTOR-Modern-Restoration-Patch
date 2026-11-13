"""Press kit for KOTOR 1 Native Controller Mod + Xbox HUD 1.0.0 (the standalone .kpatch).

Eight 1920x1080 pages in releases/controller-v1.0.0/press-kit, in the look of the KMRP 1.6
kit (tools/build_release_kit_16.py, whose page builders and palette this uses): the night
sky, the crest, polished silver KOTOR, the mod's name in gold and its version in cyan.

The mod is the same code as KMRP's controller support, so the frames are KMRP's (the
maintainer, 2026-11-13: "use controller screenshots from kmrp not only standalone version").
Each frame's label names the KMRP version it was taken with: the 1.6 frames are the
maintainer's screenshots of 2026-11-13 in releases/v1.6.0, the 1.5 frames are the 1.5 kit's
sources in build/controller-standalone/shots and show the controller as it was then.

    python tools/build_controller_kit_10.py          # every page
    python tools/build_controller_kit_10.py 03       # pages whose name begins so

Documentation standard: see docs/documentation-standard.md.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_release_kit_16 as kit  # noqa: E402
from build_brand_image import DEFAULT_FONT  # noqa: E402

OUT = kit.ROOT / "releases" / "controller-v1.0.0" / "press-kit"
NAME_GOLD, VERSION = "NATIVE CONTROLLER MOD", "1.0"
W, H, P = kit.W, kit.H, kit.P

# the page header: the mod's short name in gold, its version in cyan, no "new in" tag
kit.HEADER_WORD, kit.HEADER_VERSION, kit.NEW_TAG = "CONTROLLER MOD", VERSION, None


def build_cover():
    canvas = kit.dusk(grid=False)
    lockup = Image.open(kit.ROOT / kit.cover.LOCKUP).convert("RGBA")
    lockup = lockup.crop(lockup.getbbox())
    tw = int(W * 0.50)
    lockup = lockup.resize((tw, int(lockup.height * tw / lockup.width)), Image.LANCZOS)
    lockup = kit.polish_silver(lockup)
    shine = np.asarray(lockup).astype(np.float32)
    grey = (shine[..., :3].max(axis=2) - shine[..., :3].min(axis=2)) < 40
    solid = grey & (shine[..., 3] > 128)
    solid = solid & (solid.sum(axis=1) > solid.shape[1] * 0.06)[:, None]
    halo = Image.fromarray((solid * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(14))
    glow = Image.new("RGBA", lockup.size, (220, 236, 255, 0))
    glow.putalpha(halo.point(lambda v: int(v * 0.22)))
    y = int(H * 0.03)
    canvas.alpha_composite(glow, ((W - tw) // 2, y))
    canvas.alpha_composite(lockup, ((W - tw) // 2, y))
    cursor = y + lockup.height

    # NATIVE CONTROLLER MOD in gold and 1.0 in cyan metal, one line, fitted to the page
    cap = int(H * 0.070)
    word = kit.shiny_gold(kit.cover.metal_text(NAME_GOLD, cap, DEFAULT_FONT))
    num = kit.cover.metal_text(VERSION, cap, DEFAULT_FONT)
    word, num = word.crop(word.getbbox()), num.crop(num.getbbox())
    gap = int(H * 0.04)
    total = word.width + gap + num.width
    limit = int(W * 0.86)
    if total > limit:
        k = limit / total
        word = word.resize((round(word.width * k), round(word.height * k)), Image.LANCZOS)
        num = num.resize((round(num.width * k), round(num.height * k)), Image.LANCZOS)
        gap = round(gap * k)
        total = word.width + gap + num.width
    tall = max(word.height, num.height)
    ky = cursor + int(H * 0.018)
    x0 = (W - total) // 2
    kit.gold_pop(canvas, word, (x0, ky + tall - word.height), sparkles=False)
    blade, (px, py) = kit.saber(num)
    canvas.alpha_composite(blade, (x0 + word.width + gap - px, ky + tall - num.height - py))

    draw = ImageDraw.Draw(canvas)
    sub = kit.font(DEFAULT_FONT, int(H * 0.033))
    sy = ky + tall + int(H * 0.055)
    kit.tracked(draw, sy, "+  XBOX HUD", sub, P["Holo"] + (255,), sub.size * 0.42, centre=W / 2)
    face = kit.font(kit.BOLD, int(H * 0.029))
    lines = ("XBOX  ·  PLAYSTATION  ·  SWITCH  ·  STEAM DECK",
             "ORIGINAL XBOX CONTROLS  ·  REMAPPING  ·  RUMBLE",
             "PAZAAK  ·  SWOOP RACING",
             "ONE KPATCH  ·  NO OTHER PATCH NEEDED")
    fy = sy + int(H * 0.066)
    rows = [(fy + r * int(face.size * 1.75), line, face.size * 0.3) for r, line in enumerate(lines)]
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for yy, line, track in rows:
        kit.tracked(sd, yy + 2, line, face, (2, 4, 12, 210), track, centre=W / 2)
    canvas.alpha_composite(shade.filter(ImageFilter.GaussianBlur(2)))
    draw = ImageDraw.Draw(canvas)
    for yy, line, track in rows:
        kit.tracked(draw, yy, line, face, P["Text"] + (255,), track, centre=W / 2)
    kit.footer(canvas, "* Already included in KMRP 1.6")     # the maintainer's wording, 2026-11-13
    return canvas


def solo(subject, picture, label, line):
    canvas = kit.page_ground()
    kit.header(canvas, subject, False)
    width = 1420
    kit.frame(canvas, picture, (W - width) // 2, 160, width, label)
    kit.footer(canvas, line)
    return canvas


PAGES = (
    ("01-cover", build_cover),
    ("02-controls-remapping", lambda: kit.card_with_picture(
        "CONTROLS", "THE ORIGINAL", "XBOX CONTROLS", (
            "LB pauses, RB switches party member",
            "The triggers change target",
            "X queues, Y flourishes, B disengages",
            "Start opens the menus where you left them",
            "Every button can be remapped",
        ), kit.shot("remap"), "CONTROLLER LAYOUT: REMAPPING  WITH KMRP 1.6",
        "PlayStation, Switch, Steam Deck and other controllers show their own button icons too.",
        new=False)),
    ("03-xbox-hud", lambda: solo(
        "XBOX-STYLE HUD", kit.old_shot("k1080-paused-pad"), "WITH KMRP 1.5  1920x1080",
        "With a pad the HUD is laid out like the Xbox game's; touch the mouse and the PC HUD is back.")),
    ("04-every-menu", lambda: kit.three_page(
        "EVERY MENU WITH A PAD", kit.old_shot("k1080-inventory-pad"), kit.old_shot("k1080-character-pad"),
        kit.old_shot("k1080-journal-pad"), ("INVENTORY  WITH KMRP 1.5", "CHARACTER", "JOURNAL"),
        "Button prompts on every screen, for the controller in your hands.", new=False)),
    ("05-pazaak", lambda: kit.three_page(
        "PAZAAK WITH A PAD", kit.shot("pazaak-table"), kit.shot("pazaak-sidedeck"), kit.shot("pazaak-wager"),
        ("THE TABLE  WITH KMRP 1.6", "SIDE DECK", "THE WAGER"),
        "X plays the card you picked, LB flips it, A ends the turn and Y stands, as on the Xbox.", new=False)),
    ("06-swoop-racing", lambda: solo(
        "SWOOP RACING WITH A PAD", kit.shot("swoop"), "WITH KMRP 1.6  1920x1080",
        "Swoop racing and the gun turret, played with a controller.")),
    ("07-any-interface", lambda: kit.card_page(
        "ANY INTERFACE", "THE GAME'S OWN,", "A MOD'S OR KMRP'S", (
            "Works on the game's own interface, a widescreen mod's or KMRP's",
            "Adds its button prompts to a GUI mod's screens",
            "Needs no other patch and writes nothing to Override",
            "For the Steam and GOG games",
        ), "", new=False)),
    ("08-installing", lambda: kit.card_page(
        "INSTALLING", "ONE KPATCH FOR", "KOTOR PATCH MANAGER", (
            "Install it with KOTOR Patch Manager like any other patch",
            "The Xbox-style HUD is an option, on by default",
            "Rumble and your button layout kept in one settings file",
            "Already included in KMRP 1.6",
        ), "", new=False)),
)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in PAGES:
        if only and not name.startswith(only):
            continue
        img = fn().convert("RGB")
        assert img.size == (W, H), img.size
        path = OUT / f"{name}.png"
        img.save(path)
        print(path, img.size)


if __name__ == "__main__":
    main()
