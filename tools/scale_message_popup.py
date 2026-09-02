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


def scale_popup(source: Path, dest: Path, factor: float,
                height_factor: float | None = None, button_gap: int = 0) -> list:
    fy = factor if height_factor is None else height_factor
    gui = read_gff(source)
    root = gui.root
    extent = root.acquire("EXTENT", None)
    if extent is None:
        raise ValueError(f"{source}: root has no EXTENT")

    left, top = extent.get_int32("LEFT"), extent.get_int32("TOP")
    width, height = extent.get_int32("WIDTH"), extent.get_int32("HEIGHT")
    new_w, new_h = round_half_up(width * factor), round_half_up(height * fy) + button_gap
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
                after = (round_half_up(before[0] * factor),
                         round_half_up(before[1] * fy),
                         round_half_up(before[2] * factor),
                         round_half_up(before[3] * fy))
                # Buttons sit below the message; pushing them down opens the gap
                # between the text and the OK button. The panel grew by the same
                # amount above, so nothing falls off the bottom.
                if button_gap and child.acquire("CONTROLTYPE", None) == 6:
                    after = (after[0], after[1] + button_gap, after[2], after[3])
                for field, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), after):
                    child_extent.set_int32(field, value)
                child.set_struct("EXTENT", child_extent)
                changed.append((child.acquire("TAG", ""), before, after))
            walk(child)

    walk(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gui, dest, ResourceType.GUI)
    return changed


# A layout tuned in play at 3440x1440 rather than derived by scaling. Scaling
# alone cannot work here: the message text renders far taller than LB_MESSAGE's
# authored height (a four-line tutorial is ~180px in a box authored at 104), so
# a proportionally-placed button ends up almost touching the last line. These
# values give the text room for five lines and still clear the buttons.
#
# The icon stays 32: its texture is 32x32 and the control TILES rather than
# scales, so a 64px icon draws as four copies. Confirmed in play.
TUNED = {
    # Measured in play at 3440x1440 rather than derived by scaling.
    #
    # OK sits at LB_MESSAGE's bottom edge and the text starts at its top, so
    #     gap above OK = LB_MESSAGE height - text height
    # A 4-line message is ~116px, so 150 leaves ~34px. The box must stay taller
    # than the text: if it overflows, the engine's auto-fit loop switches back on
    # and the horizontal clipping returns with it.
    #
    # Panel height is then set to just clear the button. The engine ADDS the icon
    # size to the panel height (panel.height += icon), so the authored value is
    # the height without the icon: 300 renders as ~428 with a 128px icon.
    # Measured at 420 the button ended 114px above the bottom edge. 300 was
    # too far (the button was clipped by the panel edge) and 340 put the
    # button flush against it, so 375, which leaves ~35px below. The confirm box has no icon, so it renders at the authored
    # 300 and its two buttons sit 128px higher, still inside.
    "TGuiPanel":  (900, 375),
    "LB_MESSAGE": (60, 24, 780, 150),
    "BTN_OK":     (60, 320, 780, 80),
    "BTN_CANCEL": (60, 410, 780, 80),
}

# The listbox lays text out inside `width - scrollbar - 2*border - PADDING`, so
# PADDING pulls the WRAP edge in while the text is still CLIPPED at the control
# edge. That difference is the slack the engine's own line measurement needs:
# it truncates each glyph's advance and runs ~3% short, so a line it believes
# fits renders wider and loses its last character. 30px covers ~3% of this
# box's 780px width.
MESSAGE_PADDING = 30


def apply_tuned(source: Path, dest: Path) -> list:
    """Write the tuned layout, keeping the panel's centre where it was."""
    gui = read_gff(source)
    root = gui.root
    extent = root.acquire("EXTENT", None)
    left, top = extent.get_int32("LEFT"), extent.get_int32("TOP")
    width, height = extent.get_int32("WIDTH"), extent.get_int32("HEIGHT")
    new_w, new_h = TUNED["TGuiPanel"]
    new_l = round_half_up(left + (width - new_w) / 2)
    new_t = round_half_up(top + (height - new_h) / 2)
    changed = [("TGuiPanel", (left, top, width, height), (new_l, new_t, new_w, new_h))]
    for field, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), (new_l, new_t, new_w, new_h)):
        extent.set_int32(field, value)
    root.set_struct("EXTENT", extent)

    def walk(struct):
        controls = struct.acquire("CONTROLS", None)
        if controls is None:
            return
        for child in controls:
            tag = child.acquire("TAG", "")
            child_extent = child.acquire("EXTENT", None)
            if tag == "LB_MESSAGE":
                was = child.acquire("PADDING", 0)
                child.set_int32("PADDING", MESSAGE_PADDING)
                changed.append(("LB_MESSAGE.PADDING", was, MESSAGE_PADDING))
            if child_extent is not None and tag in TUNED and tag != "TGuiPanel":
                before = tuple(child_extent.get_int32(f)
                               for f in ("LEFT", "TOP", "WIDTH", "HEIGHT"))
                after = TUNED[tag]
                for field, value in zip(("LEFT", "TOP", "WIDTH", "HEIGHT"), after):
                    child_extent.set_int32(field, value)
                child.set_struct("EXTENT", child_extent)
                changed.append((tag, before, after))
            walk(child)

    walk(root)
    # The listbox's client rect always subtracts the scrollbar's width
    # (0x0041BF80, unconditionally), and that is what clips the text -- but the
    # wrap is computed on the full box width. The mismatch is exactly the
    # scrollbar's authored width, 15, which is why long lines lose their last
    # character or two no matter how wide the box is. Zeroing it makes wrap and
    # clip agree. The box is sized to hold the message, so nothing needs to
    # scroll.
    def zero_scrollbar(struct):
        controls = struct.acquire("CONTROLS", None)
        if controls is None:
            return
        for child in controls:
            if child.acquire("TAG", "") == "LB_MESSAGE":
                bar = child.acquire("SCROLLBAR", None)
                if bar is not None:
                    bar_extent = bar.acquire("EXTENT", None)
                    if bar_extent is not None:
                        was = bar_extent.get_int32("WIDTH")
                        bar_extent.set_int32("WIDTH", 0)
                        bar.set_struct("EXTENT", bar_extent)
                        child.set_struct("SCROLLBAR", bar)
                        changed.append(("LB_MESSAGE.SCROLLBAR width", was, 0))
            zero_scrollbar(child)

    zero_scrollbar(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_gff(gui, dest, ResourceType.GUI)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--factor", type=float, default=1.5,
                        help="horizontal scale for the panel and every child (default 1.5)")
    parser.add_argument("--height-factor", type=float, default=None,
                        help="vertical scale; defaults to --factor")
    parser.add_argument("--tuned", action="store_true",
                        help="use the play-tested layout instead of scaling factors")
    parser.add_argument("--button-gap", type=int, default=0,
                        help="extra space between the message and the buttons, in panel "
                             "units; the panel grows by the same amount")
    args = parser.parse_args()

    if not 1.0 <= args.factor <= 4.0:
        raise SystemExit("--factor must be between 1.0 and 4.0")
    if args.height_factor is not None and not 1.0 <= args.height_factor <= 6.0:
        raise SystemExit("--height-factor must be between 1.0 and 6.0")

    if args.tuned:
        changed = apply_tuned(args.source, args.output)
    else:
        changed = scale_popup(args.source, args.output, args.factor, args.height_factor,
                              args.button_gap)
    fy = args.factor if args.height_factor is None else args.height_factor
    print(f"scaled {args.source.name} by {args.factor}x wide, {fy}x tall -> {args.output}")
    for tag, before, after in changed:
        print(f"  {tag:14s} {before} -> {after}")
    print()
    print("The popup GUI is read once when the message-popup class is constructed,")
    print("so the game must be restarted for this to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
