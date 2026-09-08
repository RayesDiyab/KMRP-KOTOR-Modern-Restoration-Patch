#!/usr/bin/env python3
"""Every actionable strip button on the in-game tab screens, with its offset.

Physical QA found working buttons with no controller art -- Close, Use Item,
Show New Items, and their equivalents on Map, Journal, Skills and Messages. A
badge is installed by replacing a control's BORDER.FILL, which needs the
control's byte offset within its panel and its pixel extent, so this collects
both for every tab in one pass.

Only controls that register 0x27 are listed: those are the ones A activates when
focused, which is what a badge would be claiming.

Requires the virtual pad server and the game in the in-game menu.

Usage:
    python testing/controller/probe_strip_buttons.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import socket
import time

import probe_default_buttons as P

TAB_NAMES = ["Equipment", "Inventory", "Character", "Abilities",
             "Messages", "Journal", "Map", "Options"]
TUTORIAL_POPUP = 0x006AA8A0
TAB_STRIP = 0x00624970
BARE_PANEL = 0x00409E60


def pad(command):
    sock = socket.create_connection(("127.0.0.1", 8787), timeout=5)
    sock.sendall((command + "\n").encode())
    sock.recv(64)
    sock.close()


def next_tab(settle=1.4):
    pad("triggers 0 1")
    time.sleep(0.25)
    pad("triggers 0 0")
    time.sleep(settle)


def clear_popup(game):
    """The tutorial box opens in front of the strip and swallows navigation."""
    for _ in range(3):
        if game.dispatcher(game.front_panel()) != TUTORIAL_POPUP:
            return
        P.tap("A", settle=1.5)


def tab_index(game):
    root = game.u32(0x007A39FC)
    app = game.u32(root + 4)
    internal = game.u32(app + 4)
    in_game = game.u32(internal + 0x40)
    return game.i32(in_game + 0x2C)


def content_panel(game):
    manager = game.u32(0x007A39F4)
    array = game.u32(manager + 0x88)
    count = game.i32(manager + 0x8C)
    found = None
    for index in range(count):
        panel = game.u32(array + index * 4)
        if not panel:
            continue
        if game.dispatcher(panel) in (TAB_STRIP, BARE_PANEL, TUTORIAL_POPUP):
            continue
        if game.i32(panel + 0x24):
            found = panel
    return found


def main() -> int:
    game = P.Game()
    clear_popup(game)
    for _ in range(8):
        index = tab_index(game)
        panel = content_panel(game)
        if panel is None:
            print(f"tab {index}: no content panel")
            next_tab()
            continue
        name = TAB_NAMES[index] if 0 <= index < 8 else f"tab {index}"
        print(f"\n=== {name} (tab {index})  panel {panel:08X} "
              f"vtable {game.u32(panel):08X} dispatcher {game.dispatcher(panel):08X}")
        array = game.u32(panel + 0x20)
        count = game.i32(panel + 0x24) or 0
        for i in range(min(count, 40)):
            control = game.u32(array + i * 4)
            if not control:
                continue
            events = game.events(control)
            if 0x27 not in events:
                continue
            flags = game.flags(control)
            x = game.i32(control + 4)
            y = game.i32(control + 8)
            w = game.i32(control + 0x0C)
            h = game.i32(control + 0x10)
            print(f"    panel+0x{control - panel:04X}  ({x:5d},{y:5d}) {w:4d}x{h:<4d}"
                  f"  flags {flags:02X}  events {[hex(e) for e in events]}")
        next_tab()
        clear_popup(game)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
