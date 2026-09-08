#!/usr/bin/env python3
"""Press every face button on every in-game tab screen and record what happens.

Badges must depict what a button really does on the screen it is drawn on, and
that cannot be reasoned out from the retained-event inventory alone: a panel
implementing 0x29 says X is handled, not what X does, and a panel sitting behind
the tab strip may or may not receive it. So this presses A, B, X and Y on each
tab in turn and reports, for each:

    changed   how much of the display differed afterwards
    class     the input class before -> after (2 -> 0 means the menu closed)
    front     the front panel's dispatcher before -> after (a new value means
              something opened on top)

After each press it restores the menu and the tab, so one button's effect cannot
contaminate the next.

Requires the virtual pad server and a loaded save.

Usage:
    python testing/controller/probe_button_effects.py [--tabs 1,4,5,6]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time

import probe_default_buttons as P
import probe_strip_buttons as S

SCRATCH = os.environ.get("TEMP", ".")
TAB_STRIP_VTABLE = 0x00750148


def shot(name):
    out = os.path.join(SCRATCH, f"kmrp_effect_{name}.png")
    subprocess.run(["powershell", "-NoProfile", "-Command",
        "Add-Type -AssemblyName System.Drawing,System.Windows.Forms;"
        "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
        "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($bmp);"
        "$g.CopyFromScreen(0,0,0,0,$bmp.Size);"
        f"$bmp.Save('{out}')"], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def changed(before, after):
    from PIL import Image
    a, b = Image.open(before).convert("RGB"), Image.open(after).convert("RGB")
    if a.size != b.size:
        return 100.0
    pa, pb = a.load(), b.load()
    total = diff = 0
    for y in range(0, a.size[1], 6):
        for x in range(0, a.size[0], 6):
            total += 1
            if sum(abs(p - q) for p, q in zip(pa[x, y], pb[x, y])) > 30:
                diff += 1
    return 100.0 * diff / total if total else 0.0


def input_class(game):
    root = game.u32(0x007A39FC)
    app = game.u32(root + 4) if root else None
    internal = game.u32(app + 4) if app else None
    return game.u32(internal + 0x9C) if internal else None


def restore(game, tab):
    """Back to the in-game menu, on `tab`, with no popup in front."""
    for _ in range(4):
        if input_class(game) == 0:
            break
        if game.u32(game.front_panel()) == TAB_STRIP_VTABLE:
            break
        P.tap("B", settle=1.6)
    if input_class(game) == 0:
        P.tap("START", settle=2.4)
    S.clear_popup(game)
    for _ in range(9):
        if S.tab_index(game) == tab:
            break
        S.next_tab()
        S.clear_popup(game)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tabs", default="1,4,5,6",
                        help="comma-separated tab indices to probe")
    arguments = parser.parse_args()
    tabs = [int(v) for v in arguments.tabs.split(",")]

    game = P.Game()
    for tab in tabs:
        restore(game, tab)
        name = S.TAB_NAMES[tab] if 0 <= tab < 8 else str(tab)
        print(f"\n=== {name} (tab {tab})")
        for button in ("A", "B", "X", "Y"):
            restore(game, tab)
            if S.tab_index(game) != tab:
                print(f"    {button}: could not return to the tab; skipped")
                continue
            before_class = input_class(game)
            before_front = game.dispatcher(game.front_panel())
            before = shot("before")
            P.tap(button, settle=2.0)
            after = shot("after")
            after_class = input_class(game)
            after_front = game.dispatcher(game.front_panel())
            print(f"    {button}: changed {changed(before, after):5.1f}%   "
                  f"class {before_class} -> {after_class}   "
                  f"front {before_front:08X} -> {after_front:08X}"
                  + ("   [MENU CLOSED]" if after_class == 0 else "")
                  + ("   [SOMETHING OPENED]"
                     if after_front != before_front and after_class != 0 else ""))
    restore(game, tabs[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
