#!/usr/bin/env python3
"""Targets, menus, party and pause in a fight, by pad, on the running game (PAD-5, checklist 1 and 9a).

Loads the save `build_combat_fixture.py` made, and walks what a player does around a fight: the next
and previous target, the in-game menu with every tab, D-pad presses in a menu, party switching,
solo mode and pause. Each step records the panels on top, the HUD's active control and a frame, and
the game must still be running at the end. What a frame shows is read by a person: this says what
happened, not that it looked right.

Needs `debug-logs=2` in the game's `configs\\kmrp-controller.ini`. Writes `build/verify/play-*.png`
and `build/verify/play-<label>.json`. Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import json
import time

from live_harness import VERIFY
from live_session import Session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    session = Session()
    game = session.game
    rows: list = []

    def active() -> int:
        hud = session.hud()
        return (game.u32(hud + 0x1C) or 0) if hud else 0

    def step(name: str, *commands: str, settle: float = 1.0):
        game.press(*commands)
        time.sleep(settle)
        row = {"step": name, "panels": game.panel_names()[-3:], "active": f"{active():08X}",
               "class": session.input_class(), "alive": game.alive()}
        rows.append(row)
        print(json.dumps(row), flush=True)
        game.shot(VERIFY / f"play-{len(rows):02d}.png")

    def trigger(left: float, right: float) -> tuple:
        return (f"triggers {left} {right}", "wait 0.12", "triggers 0 0")

    try:
        session.boot()
        session.load_newest_save()
        time.sleep(5)
        step("next target", *trigger(0, 1))
        step("next target", *trigger(0, 1))
        step("previous target", *trigger(1, 0))
        step("slot focus", "dpad right 0.1")
        step("Start opens the menu", "tap START 0.1", settle=1.5)
        for name in ("next tab 1", "next tab 2", "next tab 3", "next tab 4", "next tab 5", "next tab 6"):
            step(name, *trigger(0, 1), settle=1.5)
        step("previous tab", *trigger(1, 0), settle=1.5)
        for name in ("D-pad down", "D-pad down", "D-pad right", "D-pad up"):
            step(f"menu {name}", f"dpad {name.split()[-1]} 0.1")
        step("Start closes the menu", "tap START 0.1", settle=1.5)
        step("slot after the menu: A", "tap A 0.1")
        step("RB switches ally", "tap RB 0.1")
        step("RB switches ally", "tap RB 0.1")
        step("RB back to the leader", "tap RB 0.1")
        step("View: solo mode on", "tap BACK 0.1")
        step("View: solo mode off", "tap BACK 0.1")
        step("LB: pause off", "tap LB 0.1")
        step("LB: pause on", "tap LB 0.1")
    finally:
        (VERIFY / f"play-{args.label}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
