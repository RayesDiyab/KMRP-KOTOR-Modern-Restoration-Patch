#!/usr/bin/env python3
"""Build resolution-matched controller badges for existing KOTOR buttons.

The PC renderer stretches a button's BORDER.FILL across the whole control.  Each
texture is therefore generated from the final control extent for that resolution;
the circle and letter are pre-compensated so they remain round after stretching.
The controller runtime assigns these otherwise-unused fills only while a gamepad
is the last active input device.
"""

from __future__ import annotations

import math
import struct
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

from pykotor.resource.formats.gff import read_gff


TEXTURE_WIDTH = 512
TEXTURE_HEIGHT = 64
TGA_FOOTER = b"\x00" * 8 + b"TRUEVISION-XFILE." + b"\x00"

# Real controller artwork, not drawn here: Xelu's Free Controller & Key Prompts,
# CC0 1.0 (public domain). The licence and the author's own terms are vendored
# beside the images -- "any project you want to (be it commercial or not)".
#
# The Xbox 360 set is used rather than Series X or Xbox One. Those two draw a
# grey disc with a coloured letter, which loses most of its contrast at badge
# size against KOTOR's dark blue panels; the 360 set is a solid coloured disc,
# which is also how the original Xbox build of KOTOR drew its prompts.
#
# Do NOT substitute Microsoft's official glyphs. They are trademarked and
# licensed for Xbox-licensed titles; this repository is public and GPL-3.0.
GLYPH_ART_DIR = (Path(__file__).resolve().parents[1] / "third_party" / "Included"
                 / "Xelu-Free-Controller-Prompts-CC0")
GLYPH_ART = {
    "A": "360_A.png",
    "B": "360_B.png",
    "X": "360_X.png",
    "Y": "360_Y.png",
    "LB": "360_LB.png",
    "RB": "360_RB.png",
    "START": "360_Start.png",
    "BACK": "360_Back.png",
    "DPAD_LEFT": "360_Dpad_Left.png",
    "DPAD_RIGHT": "360_Dpad_Right.png",
}

# Fallback palette for _legacy_drawn_tga only, used if the artwork is missing.
# Measured off original-Xbox KOTOR screenshots (modal colour inside each disc,
# antialiased edges discarded): A (137,210,9)/(134,209,2), B (183,42,0)/(194,45,0),
# Y (236,181,12)/(235,177,0). X could not be sampled cleanly -- its blue overlaps
# KOTOR's own cyan UI in hue -- so that one value is the standard Xbox blue and is
# the single unmeasured entry.
GLYPH_COLORS = {
    "A": (134, 209, 5),
    "B": (190, 44, 0),
    "X": (42, 111, 219),
    "Y": (235, 179, 4),
}
GLYPH_FALLBACK = (77, 215, 255)
GLYPH_INK = (16, 20, 24)


@dataclass(frozen=True)
class PromptTarget:
    gui: str
    tag: str
    control_index: int
    glyph: str
    resref: str


# These are zero-based entries in each GUI GFF control list. The generator
# verifies the tag at every index in every resolution and uses the control's
# rectangle to shape its badge. Runtime lookup uses verified embedded-object
# offsets instead; GUI list order is not an object-layout contract.
PROMPT_TARGETS = (
    PromptTarget("character.gui", "BTN_EXIT", 60, "B", "kmrpb_charexit"),
    PromptTarget("character.gui", "BTN_SCRIPTS", 61, "X", "kmrpx_charscr"),
    PromptTarget("container.gui", "BTN_OK", 2, "A", "kmrpa_contok"),
    PromptTarget("container.gui", "BTN_GIVEITEMS", 3, "X", "kmrpx_contgive"),
    PromptTarget("container.gui", "BTN_CANCEL", 4, "B", "kmrpb_contback"),
    PromptTarget("saveload.gui", "BTN_DELETE", 8, "X", "kmrpx_savdel"),
    PromptTarget("saveload.gui", "BTN_BACK", 9, "B", "kmrpb_savback"),
    PromptTarget("saveload.gui", "BTN_SAVELOAD", 10, "A", "kmrpa_savload"),
    PromptTarget("upgradesel.gui", "BTN_UPGRADEITEMS", 9, "A", "kmrpa_upgitem"),
    PromptTarget("upgradesel.gui", "BTN_BACK", 10, "B", "kmrpb_upgback"),

    # Every remaining screen the controller can navigate, added 2026-09-06.
    #
    # These are all B, and B is the one glyph that can be asserted rather than
    # assumed: the module rewrites B's Delete scancode to Escape whenever a menu
    # panel is open (K1XboxControls.cpp, the DIK_DELETE branch of
    # CaptureActionBarInputK1), and the rewrite is suppressed only for the four
    # transient overlays in IsK1DeleteEscapeSuppressedPanel -- floaty text, bark
    # bubbles, the message box and the controller-loss box. None of these is one.
    #
    # The tags are not trustworthy and were not trusted: `optgraphicsadv.gui`
    # and `optsoundadv.gui` both call their OK button BTN_BACK and their real
    # back button BTN_CANCEL, so each target below was chosen by the STRREF the
    # button actually draws, not by its name.
    PromptTarget("optionsmain.gui", "BTN_BACK", 7, "B", "kmrpb_optmain"),
    PromptTarget("optionsingame.gui", "BTN_EXIT", 10, "B", "kmrpb_optingame"),
    PromptTarget("optgameplay.gui", "BTN_BACK", 10, "B", "kmrpb_optgame"),
    PromptTarget("optautopause.gui", "BTN_BACK", 7, "B", "kmrpb_optpause"),
    PromptTarget("optfeedback.gui", "BTN_BACK", 2, "B", "kmrpb_optfeed"),
    PromptTarget("optmouse.gui", "BTN_BACK", 2, "B", "kmrpb_optmouse"),
    PromptTarget("optgraphics.gui", "BTN_BACK", 5, "B", "kmrpb_optgfx"),
    PromptTarget("optgraphicsadv.gui", "BTN_CANCEL", 3, "B", "kmrpb_optgfxadv"),
    PromptTarget("optsound.gui", "BTN_BACK", 11, "B", "kmrpb_optsnd"),
    PromptTarget("optsoundadv.gui", "BTN_CANCEL", 8, "B", "kmrpb_optsndadv"),
    PromptTarget("optkeymapping.gui", "BTN_Cancel", 3, "B", "kmrpb_optkeys"),
    PromptTarget("upgrade.gui", "BTN_BACK", 28, "B", "kmrpb_upgasm"),
    PromptTarget("upgradeitems.gui", "BTN_BACK", 4, "B", "kmrpb_upgitm"),
    PromptTarget("confirm.gui", "BTN_CANCEL", 2, "B", "kmrpb_confirm"),

    # A on each screen's primary action. Weaker than the B badges above and
    # deliberately marked as such: A is Return, which activates whatever control
    # currently has focus, so this is a CONVENTION -- "A is how you commit on this
    # screen" -- not a guarantee that A hits this particular button from anywhere.
    # It is the same convention the original ten already used for Load, Get Items
    # and Upgrade Items. No badge is put on any "Default" button, because no
    # controller button performs restore-defaults at all.
    PromptTarget("optkeymapping.gui", "BTN_Accept", 2, "A", "kmrpa_optkeys"),
    PromptTarget("optgraphicsadv.gui", "BTN_BACK", 4, "A", "kmrpa_optgfxadv"),
    PromptTarget("optsoundadv.gui", "BTN_BACK", 3, "A", "kmrpa_optsndadv"),
    PromptTarget("upgradeitems.gui", "BTN_UPGRADEITEM", 3, "A", "kmrpa_upgitm"),
    PromptTarget("upgrade.gui", "BTN_ASSEMBLE", 24, "A", "kmrpa_upgasm"),
)


def _distance_to_segment(px: float, py: float, ax: float, ay: float,
                         bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _glyph_distance(glyph: str, x: float, y: float, cx: float, cy: float,
                    radius: float) -> float:
    s = radius * 0.58
    if glyph == "A":
        return min(
            _distance_to_segment(x, y, cx - s * 0.62, cy + s, cx, cy - s),
            _distance_to_segment(x, y, cx, cy - s, cx + s * 0.62, cy + s),
            _distance_to_segment(x, y, cx - s * 0.34, cy + s * 0.20,
                                 cx + s * 0.34, cy + s * 0.20),
        )
    if glyph == "X":
        return min(
            _distance_to_segment(x, y, cx - s * 0.65, cy - s * 0.85,
                                 cx + s * 0.65, cy + s * 0.85),
            _distance_to_segment(x, y, cx + s * 0.65, cy - s * 0.85,
                                 cx - s * 0.65, cy + s * 0.85),
        )
    if glyph == "Y":
        # Two arms meeting just above centre, then a stem to the base. Without
        # this branch "Y" fell through to the B shape below and drew a B on a
        # yellow disc. No current target uses Y, so nothing shipped wrong -- but
        # the original Xbox build puts Y on "Recommended" during character
        # generation, so the first Y target would have hit it.
        return min(
            _distance_to_segment(x, y, cx - s * 0.58, cy - s * 0.85,
                                 cx, cy - s * 0.05),
            _distance_to_segment(x, y, cx + s * 0.58, cy - s * 0.85,
                                 cx, cy - s * 0.05),
            _distance_to_segment(x, y, cx, cy - s * 0.05, cx, cy + s * 0.85),
        )
    # B: a spine plus two rounded bowls.  Trim the left half of each circle so
    # the letter reads as B rather than an 8 next to a line.
    spine = _distance_to_segment(x, y, cx - s * 0.52, cy - s,
                                 cx - s * 0.52, cy + s)
    upper = abs(math.hypot(x - (cx - s * 0.15), y - (cy - s * 0.48)) - s * 0.50)
    lower = abs(math.hypot(x - (cx - s * 0.15), y - (cy + s * 0.48)) - s * 0.50)
    if x < cx - s * 0.48:
        upper = lower = radius
    return min(spine, upper, lower)


def _blend(pixel: tuple[float, float, float, float], color: tuple[int, int, int],
           alpha: float) -> tuple[float, float, float, float]:
    src_a = max(0.0, min(1.0, alpha))
    dst_r, dst_g, dst_b, dst_a = pixel
    out_a = src_a + dst_a * (1.0 - src_a)
    if out_a <= 0:
        return 0.0, 0.0, 0.0, 0.0
    return (
        (color[0] * src_a + dst_r * dst_a * (1.0 - src_a)) / out_a,
        (color[1] * src_a + dst_g * dst_a * (1.0 - src_a)) / out_a,
        (color[2] * src_a + dst_b * dst_a * (1.0 - src_a)) / out_a,
        out_a,
    )


@lru_cache(maxsize=None)
def _load_glyph_art(glyph: str):
    """The CC0 Xbox Series glyph for `glyph`, cropped to its ink, or None."""
    from PIL import Image
    name = GLYPH_ART.get(glyph)
    if name is None:
        return None
    path = GLYPH_ART_DIR / name
    if not path.is_file():
        return None
    art = Image.open(path).convert("RGBA")
    box = art.getbbox()
    return art.crop(box) if box else art


def _composite_glyph_tga(control_width: int, control_height: int, glyph: str,
                         center_x: float, center_y: float, radius: float) -> bytes:
    """Place the real glyph artwork, pre-compensated for the button stretch.

    The engine stretches BORDER.FILL across the whole control, so a square in
    CONTROL space is a rectangle in TEXTURE space. The art is therefore resized
    to that rectangle and comes out round in game.
    """
    art = _load_glyph_art(glyph)
    if art is None:
        return _legacy_drawn_tga(control_width, control_height, glyph)

    from PIL import Image
    diameter = radius * 2.0
    dst_w = max(1, round(diameter * TEXTURE_WIDTH / control_width))
    dst_h = max(1, round(diameter * TEXTURE_HEIGHT / control_height))
    left = round((center_x - radius) * TEXTURE_WIDTH / control_width)
    top = round((center_y - radius) * TEXTURE_HEIGHT / control_height)

    sheet = Image.new("RGBA", (TEXTURE_WIDTH, TEXTURE_HEIGHT), (0, 0, 0, 0))
    resized = art.resize((dst_w, dst_h), Image.LANCZOS)
    # paste() clips anything past the edge instead of raising, and the sheet is
    # empty, so using the art's own alpha as the mask is a correct composite.
    sheet.paste(resized, (left, top), resized)

    # Store bottom-up: the descriptor below declares a bottom-left origin, which
    # is what all 40 sampled shipped KOTOR textures use.
    sheet = sheet.transpose(Image.FLIP_TOP_BOTTOM)
    r, g, b, a = sheet.split()
    header = struct.pack(
        "<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
        TEXTURE_WIDTH, TEXTURE_HEIGHT, 32, 0x08)
    return header + Image.merge("RGBA", (b, g, r, a)).tobytes() + TGA_FOOTER


@lru_cache(maxsize=None)
def build_prompt_tga(control_width: int, control_height: int, glyph: str,
                     label_width: float = 0.0) -> bytes:
    if control_width <= 0 or control_height <= 0:
        raise ValueError(f"Invalid prompt control extent {control_width}x{control_height}")
    center_y = control_height * 0.50
    radius = control_height * 0.29

    # Sit the badge immediately before the label, as the original Xbox build
    # does, instead of at a fixed inset from the button's left edge. KOTOR
    # centres a button's text, so on a 978px-wide button a left-pinned badge
    # floated most of a screen away from the words it belongs to.
    #
    # `label_width` is the measured pixel width of the label for this resolution
    # (font-atlases.md: the engine renders one texel per pixel). When it is
    # unknown -- no metrics, or a label we do not carry -- fall back to the old
    # fixed inset rather than guessing a position.
    if label_width > 0:
        gap = radius * 0.55
        center_x = (control_width - label_width) / 2.0 - gap - radius
        # Never let it leave the button, however long the label.
        center_x = max(radius * 1.15, center_x)
    else:
        center_x = control_height * 0.58
    return _composite_glyph_tga(control_width, control_height, glyph,
                                center_x, center_y, radius)


def _legacy_drawn_tga(control_width: int, control_height: int, glyph: str) -> bytes:
    """The original procedurally drawn badge. Superseded by the CC0 artwork and
    kept only so a build can fall back if the artwork is ever unavailable."""
    center_x = control_height * 0.58
    center_y = control_height * 0.50
    radius = control_height * 0.29
    ring_width = max(1.5, control_height * 0.045)
    glyph_width = max(1.4, control_height * 0.047)
    pixels = bytearray(TEXTURE_WIDTH * TEXTURE_HEIGHT * 4)

    margin = max(ring_width, glyph_width) + 1.0
    source_x_end = min(
        TEXTURE_WIDTH,
        math.ceil((center_x + radius + margin) * TEXTURE_WIDTH / control_width),
    )
    source_y_start = max(
        0,
        math.floor((center_y - radius - margin) * TEXTURE_HEIGHT / control_height),
    )
    source_y_end = min(
        TEXTURE_HEIGHT,
        math.ceil((center_y + radius + margin) * TEXTURE_HEIGHT / control_height),
    )

    for sy in range(source_y_start, source_y_end):
        y = (sy + 0.5) * control_height / TEXTURE_HEIGHT
        for sx in range(source_x_end):
            x = (sx + 0.5) * control_width / TEXTURE_WIDTH
            radial = math.hypot(x - center_x, y - center_y)
            pixel = (0.0, 0.0, 0.0, 0.0)
            face = GLYPH_COLORS.get(glyph, GLYPH_FALLBACK)
            # Solid disc in the button's own colour, letter knocked out dark, as
            # the original Xbox build draws it. See GLYPH_COLORS for the measured
            # values and for why the previous ringed style read as UI decoration.
            fill_coverage = max(0.0, min(1.0, radius + 0.6 - radial))
            if fill_coverage:
                pixel = _blend(pixel, face, fill_coverage)
            letter_distance = _glyph_distance(
                glyph, x, y, center_x, center_y, radius)
            letter_coverage = max(0.0, min(1.0, glyph_width + 0.55 - letter_distance))
            if letter_coverage:
                pixel = _blend(pixel, GLYPH_INK, letter_coverage)

            r, g, b, a = pixel
            # Store bottom-up. The header declares descriptor 0x08 (bottom-left
            # origin), which is what every shipped KOTOR texture uses -- 40 of 40
            # sampled from assets/override-3440x1440 are depth 32, descriptor
            # 0x08 -- but this loop walks `sy` from the TOP of the control down.
            # Writing row `sy` straight to file row `sy` therefore stored every
            # badge mirrored, and the asymmetric glyphs (A, B, Y) rendered upside
            # down in game. X is symmetric about the horizontal axis, which is why
            # it looked correct and hid the fault.
            row = TEXTURE_HEIGHT - 1 - sy
            offset = (row * TEXTURE_WIDTH + sx) * 4
            pixels[offset:offset + 4] = bytes((round(b), round(g), round(r), round(a * 255)))

    header = struct.pack(
        "<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0,
        TEXTURE_WIDTH, TEXTURE_HEIGHT, 32, 0x08)
    return header + pixels + TGA_FOOTER



# Which dialog.tlk string each prompt button draws, so the badge can sit beside
# the TEXT rather than at a fixed inset. The engine centres a button's label, so
# a badge pinned to the left edge of a 978px-wide button floats far from the
# words it belongs to; the original Xbox build puts the glyph immediately before
# them.
#
# These are STRREFs read out of the buttons themselves, not names chosen here.
# Every one of the ten carries TEXT.STRREF and no inline TEXT string, so the
# label is whatever the player's own dialog.tlk holds for that reference -- which
# is why the installer resolves them again against the real file (see
# `kmrp_prompts.txt` below and ControllerPromptGenerator in the patcher). The
# English widths baked here are only the fallback for an install whose dialog.tlk
# cannot be read.
#
# A hand-written table keyed by tag used to live here and was wrong for five of
# the ten: BTN_CANCEL and both BTN_BACKs are STRREF 1582 "Close", not "Cancel" or
# "Back", and BTN_SAVELOAD is 1587 "Save", not "Load". BTN_GIVEITEMS was measured
# as the 20-character "Switch To Give Items" when the strings are 47884
# "Switch To" and 47885 "Give Item".
#
# Two of them are set by code at runtime rather than from a single reference, so
# each target carries a tuple of VARIANTS and is measured against the widest:
#   BTN_SAVELOAD  1587 "Save" on the save screen, 1589 "Load" on the load screen.
#   BTN_GIVEITEMS 47884 + 47885 concatenated. dialog.tlk holds no "Take Item",
#                 so only the give-side wording is known and measured.
PROMPT_STRREFS = {
    ("character.gui", "BTN_EXIT"): ((1582,),),
    ("character.gui", "BTN_SCRIPTS"): ((1067,),),
    ("container.gui", "BTN_OK"): ((38542,),),
    ("container.gui", "BTN_GIVEITEMS"): ((47884, 47885),),
    ("container.gui", "BTN_CANCEL"): ((1582,),),
    ("saveload.gui", "BTN_DELETE"): ((1560,),),
    ("saveload.gui", "BTN_BACK"): ((1581,),),
    ("saveload.gui", "BTN_SAVELOAD"): ((1587,), (1589,)),
    ("upgradesel.gui", "BTN_UPGRADEITEMS"): ((42295,),),
    ("upgradesel.gui", "BTN_BACK"): ((1582,),),

    # The screens added 2026-09-06. 1582 "Close", 1581 "Cancel" -- read from each
    # button's own TEXT.STRREF, which is why two of them are Cancel where the tag
    # says BACK and the other way round.
    ("optionsmain.gui", "BTN_BACK"): ((1582,),),
    ("optionsingame.gui", "BTN_EXIT"): ((1582,),),
    ("optgameplay.gui", "BTN_BACK"): ((1582,),),
    ("optautopause.gui", "BTN_BACK"): ((1582,),),
    ("optfeedback.gui", "BTN_BACK"): ((1582,),),
    ("optmouse.gui", "BTN_BACK"): ((1582,),),
    ("optgraphics.gui", "BTN_BACK"): ((1582,),),
    ("optgraphicsadv.gui", "BTN_CANCEL"): ((1581,),),
    ("optsound.gui", "BTN_BACK"): ((1582,),),
    ("optsoundadv.gui", "BTN_CANCEL"): ((1581,),),
    ("optkeymapping.gui", "BTN_Cancel"): ((1581,),),
    ("upgrade.gui", "BTN_BACK"): ((1581,),),
    ("upgradeitems.gui", "BTN_BACK"): ((1582,),),
    ("confirm.gui", "BTN_CANCEL"): ((1581,),),
    ("optkeymapping.gui", "BTN_Accept"): ((1580,),),
    ("optgraphicsadv.gui", "BTN_BACK"): ((1580,),),
    ("optsoundadv.gui", "BTN_BACK"): ((1580,),),
    ("upgradeitems.gui", "BTN_UPGRADEITEM"): ((42294,),),
    ("upgrade.gui", "BTN_ASSEMBLE"): ((42021,),),
}

# The English text of every STRREF above, as shipped in the retail dialog.tlk.
# Used only to bake the fallback placement into the texture; the installer
# overrides it from the player's own file whenever that file can be read.
PROMPT_FALLBACK_STRINGS = {
    1067: "Scripts",
    1560: "Delete",
    1581: "Cancel",
    1580: "OK",
    1582: "Close",
    1587: "Save",
    1589: "Load",
    38542: "Get Items",
    42295: "Upgrade Items",
    47884: "Switch To",
    42021: "Assemble",
    42294: "Upgrade Item",
    47885: "Give Item",
}

PROMPT_MANIFEST_NAME = "kmrp_prompts.txt"


def variant_strings(variants, strings):
    """Each variant rendered as the single line the button will show."""
    out = []
    for variant in variants:
        parts = [strings.get(ref) for ref in variant]
        if any(part is None for part in parts):
            continue
        out.append(" ".join(parts))
    return out


def parse_font_metrics(txi_path: Path):
    """Per-character pixel advances for a KOTOR font atlas.

    The engine renders one texel per pixel, so a glyph's on-screen width is
    `(lowerright.u - upperleft.u) * texturewidth * 100` -- see
    `reverse-engineering/font-atlases.md`. Returns (advances, spacing_px), both
    already in pixels for the resolution this TXI was generated for.
    """
    text = txi_path.read_text(encoding="ascii", errors="replace").splitlines()
    texture_width = 0.0
    spacing = 0.0
    upper: list[float] = []
    lower: list[float] = []
    mode = None
    for line in text:
        parts = line.split()
        if not parts:
            continue
        head = parts[0].lower()
        if head == "texturewidth" and len(parts) > 1:
            texture_width = float(parts[1]); mode = None
        elif head == "spacingr" and len(parts) > 1:
            spacing = float(parts[1]); mode = None
        elif head == "upperleftcoords":
            mode = "upper"
        elif head == "lowerrightcoords":
            mode = "lower"
        elif mode and len(parts) >= 2:
            try:
                value = float(parts[0])
            except ValueError:
                mode = None
                continue
            (upper if mode == "upper" else lower).append(value)
    if not texture_width or not upper or len(lower) < len(upper):
        return None, 0.0
    advances = [(lower[i] - upper[i]) * texture_width * 100.0
                for i in range(min(len(upper), len(lower)))]
    return advances, spacing * texture_width * 100.0


def measure_label(label: str, advances, spacing_px: float) -> float:
    if not advances:
        return 0.0
    total = 0.0
    for index, ch in enumerate(label):
        code = ord(ch)
        if code < len(advances):
            total += advances[code]
        if index:
            total += spacing_px
    return total


def build_prompt_textures(gui_files: list[Path], output_dir: Path) -> list[Path]:
    by_name = {path.name.lower(): path for path in gui_files}
    output_dir.mkdir(parents=True, exist_ok=True)
    # The button font's metrics for THIS resolution, so the badge can be placed
    # against the real label width rather than a guess.
    txi = by_name.get("dialogfont16x16.txi")
    advances, spacing_px = parse_font_metrics(txi) if txi else (None, 0.0)
    results: list[Path] = []
    manifest = []
    loaded = {}
    for target in PROMPT_TARGETS:
        path = by_name.get(target.gui)
        if path is None:
            raise ValueError(f"Controller prompt source is missing: {target.gui}")
        controls = loaded.get(target.gui)
        if controls is None:
            controls = read_gff(path).root.get_list("CONTROLS")
            loaded[target.gui] = controls
        if controls is None or target.control_index >= len(controls):
            raise ValueError(f"{target.gui}: missing control index {target.control_index}")
        control = controls[target.control_index]
        actual_tag = control.get_string("TAG")
        if actual_tag != target.tag:
            raise ValueError(
                f"{target.gui}[{target.control_index}] is {actual_tag!r}, expected {target.tag!r}")
        extent = control.get_struct("EXTENT")
        border = control.get_struct("BORDER")
        if extent is None or border is None:
            raise ValueError(f"{target.gui}:{target.tag} has no extent or normal border")
        if str(border.get_resref("FILL")):
            raise ValueError(f"{target.gui}:{target.tag} has a non-empty normal fill")
        variants = PROMPT_STRREFS.get((target.gui, target.tag), ())
        labels = variant_strings(variants, PROMPT_FALLBACK_STRINGS)
        # The widest wording the button can show. A badge measured against the
        # narrower one would be overlapped by the wider one; measured against the
        # wider one it merely sits a little further out on the narrow variant.
        label_width = max(
            (measure_label(label, advances, spacing_px) for label in labels),
            default=0.0)
        width = extent.get_int32("WIDTH")
        height = extent.get_int32("HEIGHT")
        output = output_dir / f"{target.resref}.tga"
        output.write_bytes(build_prompt_tga(
            width, height, target.glyph, round(label_width, 2)))
        results.append(output)
        manifest.append((target.resref, width, height, round(label_width, 2),
                         variants))

    # Placement manifest for the installer. The badge artwork does not depend on
    # the label -- only its horizontal position does, and that position moves by
    # exactly half of any change in label width (center_x = (w - label) / 2 - gap
    # - radius). So the installer never re-renders anything: it resolves these
    # STRREFs against the player's real dialog.tlk, measures with the advances
    # carried here, and slides the already-composited badge sideways.
    #
    # The advances are embedded rather than left to the installer to parse out of
    # dialogfont16x16.txi, because that TXI is written by this same build into the
    # same archive and depending on install ORDER for correctness would be a trap.
    if advances and manifest:
        lines = ["# KMRP controller prompt placement. Generated; do not edit.",
                 "version 1",
                 f"texture {TEXTURE_WIDTH} {TEXTURE_HEIGHT}",
                 f"spacing {spacing_px:.6f}",
                 "advances " + " ".join(f"{value:.6f}" for value in advances)]
        for resref, width, height, baked, variants in manifest:
            encoded = ";".join("+".join(str(ref) for ref in variant)
                               for variant in variants) or "-"
            lines.append(f"prompt {resref} {width} {height} {baked:.2f} {encoded}")
        path = output_dir / PROMPT_MANIFEST_NAME
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        results.append(path)
    return results
