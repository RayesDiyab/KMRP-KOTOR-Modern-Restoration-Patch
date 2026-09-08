#!/usr/bin/env python3
"""Badge textures for the in-game tab screens' action buttons.

The main prompt builder reads each control's extent out of a `.gui` file. These
buttons belong to screens whose panels are built at runtime, and their extents
were measured on the live game instead -- panel byte offset, pixel rect and the
label as it appears on screen, all read from the running process and its
framebuffer rather than guessed.

The glyph on each is measured, not assumed. An earlier version made every one an
`A` on the reasoning that these panels sit behind the tab strip so the retained
`0x28` and `0x29` cannot reach them. That reasoning was wrong: pressing B on the
live Inventory screen changes 95% of the display and takes the input class from
2 to 0, and pressing X changes 3.2% while staying in the menu. B closes, X acts.

Usage:
    python tools/build_tab_screen_prompts.py [--out DIR]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_controller_prompt_textures as textures    # noqa: E402

GAME_OVERRIDE = Path(r"C:\Star Wars - KotOR\override")


TAB_SCREEN_BADGES = (
    # resref, glyph, label as rendered, control width, control height.
    #
    # B and X are measured, not assumed. On the Inventory screen B changed 95%
    # of the display and took the input class from 2 to 0 -- it closes -- while
    # X changed 3.2% and stayed in the menu, so X acts on the screen. Y changed
    # 0.27%, which is noise, and Journal is the only one of these four whose
    # dispatcher implements 0x2A at all.
    ("kmrpb_invclose", "B", "Close", 774, 84),
    ("kmrpa_invuse", "A", "Use Item", 770, 84),
    ("kmrpx_invnew", "X", "Show New Items", 1166, 93),

    ("kmrpb_msgclose", "B", "Close", 785, 84),
    ("kmrpx_msgfeed", "X", "Show Feedback", 1500, 84),

    # Journal, each confirmed by pressing it and looking: X opened the quest
    # items list -- datapads and star maps -- and Y changed the header to
    # "Quests - By Order Received", which is what the Sort button does. Completed
    # Quests showed no dedicated glyph, so it is focus + A.
    ("kmrpx_jrnitems", "X", "Quest Items", 1107, 81),
    ("kmrpa_jrndone", "A", "Completed Quests", 1172, 81),
    ("kmrpy_jrnsort", "Y", "Sort by Name", 1500, 84),
    ("kmrpb_jrnclose", "B", "Close", 785, 84),

    # Map: A opened CSWGuiPartySelect and X opened a message box, which is the
    # Ebon Hawk confirmation. Both measured, both matching what the buttons say.
    ("kmrpx_mapebon", "X", "Return To Ebon Hawk", 1494, 39),
    ("kmrpa_mapparty", "A", "Party Selection", 1494, 39),
    ("kmrpb_mapclose", "B", "Close", 785, 84),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=GAME_OVERRIDE)
    parser.add_argument("--txi", type=Path,
                        default=GAME_OVERRIDE / "dialogfont16x16.txi",
                        help="button font metrics, for placing the glyph")
    arguments = parser.parse_args()

    present, missing = textures.check_glyph_art()
    if missing:
        print(f"glyph art missing, refusing to build: {', '.join(missing)}")
        return 1

    advances, spacing = (None, 0.0)
    if arguments.txi.is_file():
        advances, spacing = textures.parse_font_metrics(arguments.txi)
        print(f"font metrics from {arguments.txi.name}")
    else:
        # Without metrics the badge falls back to a fixed inset from the left
        # edge, which on a 1500px button floats it far from its centred label.
        print(f"WARNING: {arguments.txi} not found; badges will use the fixed "
              f"inset and will not sit against their labels")

    arguments.out.mkdir(parents=True, exist_ok=True)
    for resref, glyph, label, width, height in TAB_SCREEN_BADGES:
        label_width = (textures.measure_label(label, advances, spacing)
                       if advances else 0.0)
        data = textures.build_prompt_tga(width, height, glyph, label_width)
        path = arguments.out / f"{resref}.tga"
        path.write_bytes(data)
        print(f"  {resref:16s} [{glyph}] {label:20s} {width:4d}x{height:<3d} "
              f"label {label_width:6.1f}px -> {path.name}")
    print(f"\n{len(TAB_SCREEN_BADGES)} badges written to {arguments.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
