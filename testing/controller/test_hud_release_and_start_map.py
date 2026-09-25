#!/usr/bin/env python3
"""Issues #17 and #18, checked against the engine's own state.

#17  A used action-bar slot KEEPS focus, so A can be pressed again at once, and
     B lets go of the bar: the focused control on CSWGuiMainInterface (+0x1C)
     must stop being one of the seven action slots. D-pad Right must still
     re-enter. (Until 2026-09-25 A also let go; the user asked for the bar to
     stay focused in combat.)
#18  Start in the world opens the in-game menu ON THE MAP: the input class goes
     to 2 (GUI) and CGuiInGame's open screen, +0x2C, reads 6 -- the Map's tab ID
     in top.gui. Start again closes it: the class returns to 0. The same from
     another tab reached with RT.

Reads memory rather than the module's counters, like probe_action_bar.py, so a
module that counts what it never delivered cannot pass. Requires the virtual pad
server, the game running, and a loaded save in gameplay with at least one usable
action-bar slot. Using a slot spends that action (a stim, a power), so run it on
a throwaway save.

    python testing/controller/test_hud_release_and_start_map.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import time

from probe_action_bar import Game, pad, tap

# CClientExoAppInternal + 0x40 is CGuiInGame (read at 0x00621919 by the menu
# hotkey handler); CGuiInGame + 0x2C is the screen it has open, compared there
# against the requested index.
INTERNAL_GUI_IN_GAME = 0x40
GUI_OPEN_SCREEN = 0x2C
MAP_SCREEN = 6
CLASS_WORLD, CLASS_GUI = 0, 2

failures = 0


def expect(condition: bool, what: str) -> None:
    global failures
    print(("  ok      " if condition else "  FAILED  ") + what)
    if not condition:
        failures += 1


def open_screen(game: Game):
    internal = game.internal()
    gui = game.u32(internal + INTERNAL_GUI_IN_GAME) if internal else None
    return game.u32(gui + GUI_OPEN_SCREEN) if gui else None


def pull_rt(settle: float = 1.2) -> None:
    """RT is an analogue trigger on the pad, not a button."""
    pad("triggers 0 1")
    time.sleep(0.18)
    pad("triggers 0 0")
    time.sleep(settle)


def focus_a_slot(game: Game) -> int | None:
    for _ in range(4):
        if game.active_slot() is not None:
            break
        tap("RIGHT")
    return game.active_slot()


def main() -> int:
    game = Game()
    if game.input_class() != CLASS_WORLD:
        print("not in gameplay; load a save first")
        return 2

    print("-- #17: A on a focused slot")
    slot = focus_a_slot(game)
    expect(slot is not None, f"D-pad Right focuses a slot (slot {slot})")
    tap("A", settle=1.2)
    expect(game.active_slot() == slot, "after A the bar still holds focus, on the same slot")

    print("-- #17: B on a focused slot")
    expect(game.active_slot() is not None, f"a slot holds focus (slot {game.active_slot()})")
    tap("B")
    expect(game.active_slot() is None, "B lets go of the bar")
    expect(game.input_class() == CLASS_WORLD, "and nothing else happened: still in the world")
    slot = focus_a_slot(game)
    expect(slot is not None, f"D-pad Right re-enters the bar (slot {slot})")
    tap("B")

    print("-- #18: Start opens the Map")
    tap("START", settle=1.5)
    expect(game.input_class() == CLASS_GUI, "Start opens the in-game menu")
    screen = open_screen(game)
    expect(screen == MAP_SCREEN, f"on the Map (open screen {screen}, Map is {MAP_SCREEN})")
    tap("START", settle=1.5)
    expect(game.input_class() == CLASS_WORLD, "Start again closes it")

    print("-- #18: Start closes from another tab too")
    tap("START", settle=1.5)
    pull_rt()
    screen = open_screen(game)
    expect(game.input_class() == CLASS_GUI and screen != MAP_SCREEN,
           f"RT moves on from the Map (open screen {screen})")
    tap("START", settle=1.5)
    expect(game.input_class() == CLASS_WORLD, "Start closes it from there")

    time.sleep(0.3)
    print("PASS" if failures == 0 else f"FAIL {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
