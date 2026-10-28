#!/usr/bin/env python3
"""The in-game menu's bottom row on every screen: Close, and the button beside it, at
the Character screen's own rectangles.

**Why.** Every in-game screen has Close at the bottom right, and most have a second
button beside it (Scripts, Equip, Use Item; Select and Done on the two party-choice
screens). The game's own files put them in one place on all of them: Close at
393,410 146x28 and its neighbour at 247,410 146x28 in 640x480 units, the two
party-choice screens' Close one unit to the right (394). The high-resolution sets the
layouts start from did not keep that: at 3440x1440 Equip's Close was 2117,1230 779x84,
Inventory's 2122,1230 774x84 and Script Selection's 2118, where Character's is
2112,1230 785x84, so Close and its glyph moved as the player went through the tabs
(the maintainer, 2026-10-28: "make all of these have the same exact location and size
... so when I scroll through the tabs, the close is all the same").

**The rule.** At each size, from that size's own `character.gui` as it is built:
every screen's Close takes Character's `BTN_EXIT` rectangle, and its neighbour
Character's `BTN_SCRIPTS`. Computed from the layout, not tuned, so it holds at every
size and stays true if Character's own layout changes. Only `EXTENT` is written: a
button's text and art are its own, and Script Selection's art box is the same as
Character's.

The wide buttons left of Close on Journal, Messages and Map (Sort, Show, Party
Selection over Return) are not the neighbour and keep their own rectangles; Close
still moves to Character's there.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.formats.gff.gff_data import GFFList, GFFStruct
from pykotor.resource.type import ResourceType

REFERENCE = "character.gui"
REFERENCE_CLOSE = "BTN_EXIT"
REFERENCE_NEIGHBOUR = "BTN_SCRIPTS"

# screen: (its Close, its neighbour or None)
SCREENS: dict[str, tuple[str, str | None]] = {
    "character.gui": ("BTN_EXIT", "BTN_SCRIPTS"),
    "equip.gui": ("BTN_BACK", "BTN_EQUIP"),
    "inventory.gui": ("BTN_EXIT", "BTN_USEITEM"),
    "abilities.gui": ("BTN_EXIT", None),
    "messages.gui": ("BTN_EXIT", None),
    "journal.gui": ("BTN_EXIT", None),
    "map.gui": ("BTN_EXIT", None),
    "optionsingame.gui": ("BTN_EXIT", None),
    "scriptselect.gui": ("BTN_Back", "BTN_Accept"),
    "partyselection.gui": ("BTN_BACK", "BTN_DONE"),
}

FIELDS = ("LEFT", "TOP", "WIDTH", "HEIGHT")


def _control(root, tag: str):
    for control in root.acquire("CONTROLS", None, GFFList) or ():
        if control.get_string("TAG") == tag:
            return control
    return None


def extent_of(path: Path, tag: str) -> tuple[int, int, int, int] | None:
    control = _control(read_gff(path).root, tag)
    if control is None:
        return None
    extent = control.get_struct("EXTENT")
    return tuple(extent.get_int32(field) for field in FIELDS)


def reference(character: Path) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Character's Close and neighbour rectangles."""
    close = extent_of(character, REFERENCE_CLOSE)
    neighbour = extent_of(character, REFERENCE_NEIGHBOUR)
    if close is None or neighbour is None:
        raise ValueError(f"{character}: no {REFERENCE_CLOSE} or {REFERENCE_NEIGHBOUR}")
    # The neighbour ends where Close starts: Character's own layout has them overlap by a
    # pixel at 3440x1440 (Scripts to 2113, Close from 2112; in the game's file they
    # touch), and on Party Selection, whose Done sits beside Back the same way, KMRP's
    # roster layout refuses overlapping actions (Test-PartyRosterGui).
    left, top, width, height = neighbour
    if left < close[0] < left + width:
        neighbour = (left, top, close[0] - left, height)
    return close, neighbour


def match(source: Path, destination: Path, close, neighbour) -> int:
    """Writes `source` to `destination` with its Close and neighbour at the given
    rectangles; returns how many fields changed. A screen not in SCREENS is copied."""
    gff = read_gff(source)
    changed = 0
    wanted = SCREENS.get(source.name.lower())
    if wanted:
        for tag, rect in zip(wanted, (close, neighbour)):
            if tag is None:
                continue
            control = _control(gff.root, tag)
            if control is None:
                raise ValueError(f"{source}: no {tag}")
            extent = control.acquire("EXTENT", None, GFFStruct)
            for field, value in zip(FIELDS, rect):
                if extent.get_int32(field) != value:
                    extent.set_int32(field, value)
                    changed += 1
    if changed or Path(destination).resolve() != Path(source).resolve():
        write_gff(gff, destination, ResourceType.GUI)
    return changed


def match_folder(folder: Path, out: Path | None = None) -> dict[str, int]:
    """Every screen of SCREENS in `folder` matched to that folder's character.gui."""
    out = out or folder
    close, neighbour = reference(folder / REFERENCE)
    result = {}
    for name in SCREENS:
        path = folder / name
        if path.is_file():
            result[name] = match(path, out / name, close, neighbour)
    return result


if __name__ == "__main__":
    for folder in sys.argv[1:]:
        print(folder, match_folder(Path(folder)))
