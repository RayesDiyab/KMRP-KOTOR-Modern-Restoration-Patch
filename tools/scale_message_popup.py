#!/usr/bin/env python3
"""Scale the shared message popup (`confirm.gui`) up from its authored size.

**What uses it.** `confirm.gui` is not only the Yes/No confirm box. It is the
GUI behind the engine's shared message-popup class, whose constructor at
`0x00626DF0` loads it:

    00626EB0  push 0x0074FDA4        ; "confirm"
    00626EBE  call 0x00406D80        ; CExoString
    00626ECA  call 0x0040A680        ; load GUI by name

The **tutorial popups** derive from that class -- their constructor at
`0x006AA100` calls it -- so the little "The attributes of your character apply
bonuses..." box that appears on entering a chargen step is `confirm.gui` wearing
different text. Its body comes from `tutorial.2da` (`Message%i`, `Icon`, one row
per trigger, read at `0x006AA724` via the table the manager holds at
`[manager+0x118]`), which is why nothing in the `.gui` mentions that text.

**Why it looks small.** It was authored for 640x480 and the upstream HD mod
never grew it, so at 3440x1440 it keeps roughly its original pixel size while
the font around it doubled. `LB_MESSAGE` is 46px tall -- about one line -- so a
four-line tutorial message scrolls inside a sliver.

**A restart is required to see a change.** The class is constructed once per
session, so the GUI is read at startup and reused for every popup afterwards.
Editing the file mid-session does nothing.

**Children are panel-relative.** `TGuiPanel` sits at (935, 630) while its
children start at (32, 30), so the offsets are relative to the panel, not the
screen. Scaling therefore means multiplying every extent -- panel and children
alike -- by the same factor, and moving the panel to keep its centre where it
was.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.type import ResourceType


def round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def scale_popup(source: Path, dest: Path, factor: float) -> list:
    gui = read_gff(source)
    root = gui.root
    extent = root.acquire("EXTENT", None)
    if extent is None:
        raise ValueError(f"{source}: root has no EXTENT")

    left, top = extent.get_int32("LEFT"), extent.get_int32("TOP")
    width, height = extent.get_int32("WIDTH"), extent.get_int32("HEIGHT")
    new_w, new_h = round_half_up(width * factor), round_half_up(height * factor)
    # Keep the panel's centre where it was, so the popup does not drift.
    new_l = round_half_up(left + (width - new_w) / 2)
    new_t = round_half_up(top + (height - new_h) / 2)

    changed = [("TGuiPanel", (left, top, width, height), (new_l, new_t, new_w, new_h))]
    extent.set_int32("LEFT", new_l)
    extent.set_int32("TOP", new_t)
    extent.set_int32("WIDTH", new_w)
    extent.set_int32("HEIGHT", new_h)
    root.set_struct("EXTENT", extent)

    def walk(struct):
        controls = struct.acquire("CONTROLS", None)
        if controls is None:
            return
        for child in controls:
            child_extent = child.acquire("EXTENT", None)
            if child_extent is not None:
                before = tuple(child_extent.get_int32(f)
                               for f in ("LEFT", "TOP", "WIDTH", "HEIGHT"))
                after = tuple(round_half_up(v * factor) for v in before)
                for field, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), after):
                    child_extent.set_int32(field, value)
                child.set_struct("EXTENT", child_extent)
                changed.append((child.acquire("TAG", ""), before, after))
            walk(child)

    walk(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gui, dest, ResourceType.GUI)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--factor", type=float, default=1.5,
                        help="uniform scale for the panel and every child (default 1.5)")
    args = parser.parse_args()

    if not 1.0 <= args.factor <= 4.0:
        raise SystemExit("--factor must be between 1.0 and 4.0")

    changed = scale_popup(args.source, args.output, args.factor)
    print(f"scaled {args.source.name} by {args.factor}x -> {args.output}")
    for tag, before, after in changed:
        print(f"  {tag:14s} {before} -> {after}")
    print()
    print("The popup GUI is read once when the message-popup class is constructed,")
    print("so the game must be restarted for this to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
