#!/usr/bin/env python3
"""Dump the live GUI panel stack, with every control's geometry and flags.

Written for the in-game tab bar work. The navigation layer only ever looked at
the topmost panel, and with the in-game menu open that is `CSWGuiInGameMenu` --
the tab bar -- while the screen's actual content is on a panel below it. Any
cross-panel navigation has to start from knowing exactly what is on each.

Prints, per panel: its dispatcher (which identifies the screen), its active
control, and for each control the rect, the flag bits the navigation layer
tests, its registered event count and its own dispatcher.

Usage:
    python testing/controller/dump_panel_stack.py [--all]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import struct
import subprocess
from ctypes import wintypes

GUI_MANAGER_PTR = 0x007A39F4
APP_MANAGER_PTR = 0x007A39FC

MGR_PANEL_ARRAY, MGR_PANEL_COUNT = 0x88, 0x8C
PANEL_ACTIVE, PANEL_CONTROL_ARRAY, PANEL_CONTROL_COUNT, PANEL_FLAGS = 0x1C, 0x20, 0x24, 0x44
CTL_X, CTL_Y, CTL_W, CTL_H = 0x04, 0x08, 0x0C, 0x10
CTL_FLAGS, CTL_EVENT_TABLE, CTL_EVENT_COUNT = 0x44, 0x38, 0x3C
VTABLE_HANDLE_INPUT = 0x3C

PANEL_FLAG_SKIP = 0x600
FLAG_VISIBLE, FLAG_SELECTABLE, FLAG_DISABLED = 0x02, 0x08, 0x20


class Game:
    def __init__(self):
        self.k = ctypes.windll.kernel32
        self.k.OpenProcess.restype = wintypes.HANDLE
        pid = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process swkotor -ErrorAction SilentlyContinue).Id"]).decode().strip()
        if not pid:
            raise SystemExit("swkotor is not running")
        self.handle = self.k.OpenProcess(0x0010 | 0x0400, False, int(pid.splitlines()[0]))

    def read(self, address, size=4):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf,
                                        size, ctypes.byref(got)):
            return None
        return buf.raw

    def u32(self, a):
        raw = self.read(a)
        return struct.unpack("<I", raw)[0] if raw else None

    def i32(self, a):
        v = self.u32(a)
        return None if v is None else struct.unpack("<i", struct.pack("<I", v))[0]

    def dispatcher(self, obj):
        if not obj:
            return 0
        vtable = self.u32(obj)
        return self.u32(vtable + VTABLE_HANDLE_INPUT) if vtable else 0

    def input_class(self):
        root = self.u32(APP_MANAGER_PTR)
        app = self.u32(root + 4) if root else None
        internal = self.u32(app + 4) if app else None
        return self.u32(internal + 0x9C) if internal else None


def navigable(game, control):
    """The navigation layer's own test, repeated here so the dump agrees with it."""
    flags = (game.u32(control + CTL_FLAGS) or 0) & 0xFF
    events = game.u32(control + CTL_EVENT_TABLE) or 0
    count = game.i32(control + CTL_EVENT_COUNT) or 0
    return (flags & FLAG_VISIBLE and not flags & FLAG_DISABLED
            and flags & FLAG_SELECTABLE and 0 < count <= 64 and events > 0x10000)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true",
                        help="include controls the navigation layer rejects")
    arguments = parser.parse_args()

    game = Game()
    manager = game.u32(GUI_MANAGER_PTR)
    panels = game.u32(manager + MGR_PANEL_ARRAY)
    count = game.i32(manager + MGR_PANEL_COUNT)
    print(f"input class {game.input_class()}   {count} panels\n")

    for index in range(count):
        panel = game.u32(panels + index * 4)
        if not panel:
            continue
        flags = game.u32(panel + PANEL_FLAGS) or 0
        skipped = "SKIPPED" if flags & PANEL_FLAG_SKIP else "in front" \
            if index == count - 1 else ""
        active = game.u32(panel + PANEL_ACTIVE)
        controls = game.u32(panel + PANEL_CONTROL_ARRAY)
        n = game.i32(panel + PANEL_CONTROL_COUNT) or 0
        print(f"[{index}] panel {panel:08X}  dispatcher {game.dispatcher(panel):08X}  "
              f"flags {flags:08X} {skipped}")
        print(f"     active {active:08X}   {n} controls" if active
              else f"     active none   {n} controls")
        for i in range(min(n, 512)):
            control = game.u32(controls + i * 4)
            if not control:
                continue
            ok = navigable(game, control)
            if not ok and not arguments.all:
                continue
            x = game.i32(control + CTL_X)
            y = game.i32(control + CTL_Y)
            w = game.i32(control + CTL_W)
            h = game.i32(control + CTL_H)
            cflags = (game.u32(control + CTL_FLAGS) or 0) & 0xFF
            events = game.i32(control + CTL_EVENT_COUNT) or 0
            mark = "*" if control == active else " "
            print(f"    {mark}{i:3d} {control:08X} "
                  f"({x:5d},{y:5d}) {w:4d}x{h:<4d} flags {cflags:02X} "
                  f"events {events:2d} disp {game.dispatcher(control):08X} "
                  f"{'nav' if ok else '---'}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
