#!/usr/bin/env python3
"""What do L3 and R3 actually do, in every context the controller can reach?

Neither is a retained GUI event. R3 emits the engine's own free-look pair
(0x01 enter / 0x06 exit) and is registered only in the gameplay and free-look
classes; L3 is a bridge that asks the engine to perform a flourish and is gated
to gameplay. So the expectation is "gameplay only" -- but that is the design, not
a measurement, and the point of this file is to press them everywhere and see.

Recorded per context:

    changed   how much of the display differed
    class     input class before -> after (2 -> 0 means the menu closed,
              0 -> 4 means free look was entered)
    front     front panel dispatcher before -> after
    flourish  the module's performed/declined counters
    freelook  the module's free-look binding state

Requires the virtual pad server and a loaded save.

Usage:
    python testing/controller/probe_stick_clicks.py [--tabs 0,1,2,3,4,5,6,7]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import time

import probe_default_buttons as P
import probe_strip_buttons as S
import probe_button_effects as E

LOG = os.path.join(r"C:\Star Wars - KotOR", "kmrp-native-joystick.log")


def flourish_counters():
    """(performed, declined) from the module's diagnostic line."""
    try:
        with open(LOG, "r", errors="replace") as handle:
            found = re.findall(r"\bflour=(\d+)/(\d+)", handle.read())
    except OSError:
        return None
    return tuple(int(v) for v in found[-1]) if found else None


def camera_mode(game):
    """5 while free look is active; the engine's own field."""
    root = game.u32(0x007A39FC)
    app = game.u32(root + 4) if root else None
    internal = game.u32(app + 4) if app else None
    options = game.u32(internal + 4) if internal else None
    raw = game.read(options + 0x6D, 1) if options else None
    return raw[0] if raw else None


def probe(game, label, button):
    before_class = E.input_class(game)
    before_front = game.dispatcher(game.front_panel())
    before_flour = flourish_counters()
    before_cam = camera_mode(game)
    before = E.shot("stick_before")
    P.tap(button, settle=1.8)
    after = E.shot("stick_after")
    delta = E.changed(before, after)
    after_flour = flourish_counters()
    print(f"    {button}: changed {delta:5.1f}%   class {before_class} -> "
          f"{E.input_class(game)}   front {before_front:08X} -> "
          f"{game.dispatcher(game.front_panel()):08X}   "
          f"camera {before_cam} -> {camera_mode(game)}   "
          f"flourish {before_flour} -> {after_flour}")
    return delta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tabs", default="0,1,2,3,4,5,6,7")
    arguments = parser.parse_args()

    game = P.Game()

    # Gameplay first: the one context where both are meant to do something.
    for _ in range(4):
        if E.input_class(game) == 0:
            break
        P.tap("B", settle=1.6)
    print("=== gameplay (ICPC)")
    if E.input_class(game) == 0:
        probe(game, "gameplay", "LS")
        probe(game, "gameplay", "RS")
        # and R3 again, from inside free look, to see the way back out
        print("    -- R3 again, from whatever state that left")
        probe(game, "gameplay", "RS")

    for tab in [int(v) for v in arguments.tabs.split(",")]:
        E.restore(game, tab)
        if S.tab_index(game) != tab:
            print(f"\n=== tab {tab}: could not reach it; skipped")
            continue
        name = S.TAB_NAMES[tab] if 0 <= tab < 8 else str(tab)
        print(f"\n=== {name} (tab {tab})")
        for button in ("LS", "RS"):
            E.restore(game, tab)
            probe(game, name, button)

    E.restore(game, 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
