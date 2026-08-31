#!/usr/bin/env python3
"""Stop message panes reserving a left margin for a scrollbar they rarely show.

A listbox's client rect is built at `0x0041BF80`, read out of the binary:

    0041BF8B  mov  ebx, [esi+0x110]         ; the scrollbar's own EXTENT width
    0041BFC0  test byte [esi+0x2BC], 0x10   ; the GUI's LEFTSCROLLBAR flag
    0041BFCD  add  [esp+0xc], ebx           ; left  += scrollbarWidth  (flag only)
    0041BFD7  sub  ecx, ebx                 ; width -= scrollbarWidth  (always)

Neither line asks whether a scrollbar is currently *shown*. Any listbox with
`LEFTSCROLLBAR` set therefore carries a permanent left margin the width of its
scrollbar, visible even when the content is short enough that no bar is drawn.

Vanilla authored those bars ~16px wide, so the margin went unnoticed. The
upstream HD layout scales them to 64-68px at 3440x1440, which turns it into an
obvious gap down the left of every message pane -- 71px on `computer.gui`'s
LB_MESSAGE, 73px on `messages.gui`'s LB_MESSAGES.

Clearing the flag moves the bar to the right edge, where it only appears when
the pane actually scrolls, and gives the text its full width back. The reserved
width is still subtracted, so nothing overflows.

Applied to message/dialogue panes and plain text lists. Lists whose rows have
an icon column keep their left bar: it sits beside the icons by design, and
several of those were positioned by hand.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


LISTBOX_CONTROLTYPE = 11

# Message and dialogue panes: a wall of text with no icon column, where a
# left-hand bar buys nothing. `confirm.gui`'s LB_MESSAGE already ships with the
# flag clear, which is the pattern followed here.
MESSAGE_LISTBOXES = {
    "LB_MESSAGE", "LB_MESSAGES", "LB_DIALOG", "LB_REPLIES",
}

# Plain text lists with the same wasted margin: a column of labels and nothing
# else, so the bar has no icons to sit beside. LB_OPTIONS covers optfeedback and
# debug, LB_MODULES all five mainmenu aspect variants.
# Tags are matched upper-cased, so these must be too: the GUIs spell them
# LST_EventList and LST_AIState.
TEXT_LISTBOXES = {
    "LB_OPTIONS", "LB_MODULES", "LB_GAMES", "LB_MOVIES",
    "LB_RESOLUTIONS", "LST_EVENTLIST", "LST_AISTATE",
}

# Not included, on purpose: every list whose rows have an icon column keeps its
# left bar, because it sits beside the icons by design and several were placed
# by hand -- LB_ITEMS, LB_ABILITY, LB_FEATS, LB_POWERS, LB_SHOPITEMS,
# LB_INVITEMS, LB_SKILLS, and the HUD action queues LB_ACTIONS0-5. equip.gui's
# LB_DESC is the one description pane with the flag set; it was reviewed in game
# and left as authored.
DEFAULT_LISTBOXES = MESSAGE_LISTBOXES | TEXT_LISTBOXES


def apply(struct, tags: set[str], changed: list) -> None:
    if struct.acquire("CONTROLTYPE", None) == LISTBOX_CONTROLTYPE:
        tag = struct.acquire("TAG", "")
        if tag.upper() in tags and struct.acquire("LEFTSCROLLBAR", 0):
            scrollbar = struct.acquire("SCROLLBAR", None)
            width = 0
            if scrollbar is not None:
                extent = scrollbar.acquire("EXTENT", None)
                width = extent.acquire("WIDTH", 0) if extent is not None else 0
            struct.set_uint8("LEFTSCROLLBAR", 0)
            changed.append((tag, width))
    controls = struct.acquire("CONTROLS", None)
    if controls is not None:
        for child in controls:
            apply(child, tags, changed)


def clear_left_scrollbar(source: Path, dest: Path,
                         tags: set[str] | None = None) -> list:
    gff = read_gff(source)
    changed: list = []
    apply(gff.root, tags if tags is not None else DEFAULT_LISTBOXES, changed)
    write_gff(gff, dest, ResourceType.GUI)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("--tags", default=None,
                        help="comma-separated listbox tags; default is the message and text panes")
    args = parser.parse_args()
    tags = ({t.strip().upper() for t in args.tags.split(",")}
            if args.tags else None)
    for tag, width in clear_left_scrollbar(args.source, args.dest, tags):
        print(f"{tag:<16} LEFTSCROLLBAR 1 -> 0   reclaims {width}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
