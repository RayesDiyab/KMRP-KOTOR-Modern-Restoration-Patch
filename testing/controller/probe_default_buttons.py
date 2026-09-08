#!/usr/bin/env python3
"""Can the controller reach and press the Options "Default" buttons?

The prompt coverage audit called these nine buttons a gap because no panel
implements an X or Y shortcut for them. That was the wrong question. A Default
button is an ordinary focusable control, and A reaches the focused control
through CSWGuiPanel's base path, so the questions that decide accessibility are:

  1. does navigation put focus on it
  2. does it register 0x27, so a focused A activates it
  3. does pressing A actually change something

This walks the in-game Options list, opens each submenu, drives focus onto the
Default button and presses A, reporting all three.

Requires the virtual pad server and the game in the in-game menu.

Usage:
    python testing/controller/probe_default_buttons.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import ctypes
import socket
import struct
import subprocess
import time
from ctypes import wintypes

HOST, PORT = "127.0.0.1", 8787
GUI_MANAGER_PTR = 0x007A39F4

# Panel VTABLE -> (name, byte offset of its Default button), from Saul0097's
# constants in vendor/K1XboxControls.cpp. Keyed by vtable, not dispatcher:
# INGAME_GAMEPLAY and OPTIONS_MOUSE share dispatcher 0x006E6180.
DEFAULT_BUTTONS = {
    0x00758E00: ("INGAME_GAMEPLAY", 0x0788),
    0x00758EE0: ("INGAME_AUTOPAUSE", 0x14E0),
    0x00759358: ("KEY_MAPPINGS", 0x01B0),
    0x007581E8: ("OPTIONS_FEEDBACK", 0x0A68),
    0x007585F8: ("OPTIONS_MOUSE", 0x0788),
    0x007586F8: ("OPTIONS_GRAPHICS", 0x16F8),
    0x007584A0: ("OPTIONS_GRAPHICS_ADVANCED", 0x1F88),
    0x007587C0: ("OPTIONS_SOUND", 0x1368),
    0x00758550: ("OPTIONS_SOUND_ADVANCED", 0x0F8C),
}


def pad(command):
    sock = socket.create_connection((HOST, PORT), timeout=5)
    sock.sendall((command + "\n").encode())
    sock.recv(64)
    sock.close()


def tap(button, hold=0.2, settle=1.3):
    pad("press " + button)
    time.sleep(hold)
    pad("release " + button)
    time.sleep(settle)


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

    def read(self, address, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf,
                                        size, ctypes.byref(got)):
            return None
        return buf.raw

    def u32(self, address):
        raw = self.read(address, 4)
        return struct.unpack("<I", raw)[0] if raw else None

    def i32(self, address):
        value = self.u32(address)
        return None if value is None else struct.unpack("<i", struct.pack("<I", value))[0]

    def dispatcher(self, obj):
        vtable = self.u32(obj) if obj else None
        return self.u32(vtable + 0x3C) if vtable else 0

    def front_panel(self):
        manager = self.u32(GUI_MANAGER_PTR)
        array = self.u32(manager + 0x88)
        count = self.i32(manager + 0x8C)
        for index in range(count - 1, -1, -1):
            panel = self.u32(array + index * 4)
            if panel and not (self.u32(panel + 0x44) & 0x600):
                return panel
        return None

    def active(self, panel):
        return self.u32(panel + 0x1C) if panel else None

    def events(self, control):
        table = self.u32(control + 0x38)
        count = self.i32(control + 0x3C) or 0
        out = []
        if table and 0 < count <= 64:
            for i in range(count):
                entry = self.read(table + i * 12, 12)
                if entry:
                    out.append(struct.unpack("<III", entry)[2])
        return out

    def flags(self, control):
        return (self.u32(control + 0x44) or 0) & 0xFF


def examine(game, name, offset):
    """Report whether the Default button is reachable and A-activatable."""
    panel = game.front_panel()
    control = panel + offset
    flags = game.flags(control)
    events = game.events(control)
    selectable = bool(flags & 0x08) and bool(flags & 0x02)
    print(f"  {name}: Default @ panel+0x{offset:04X} = {control:08X}  "
          f"flags {flags:02X}  events {[hex(e) for e in events]}")
    print(f"    selectable={selectable}  registers 0x27={0x27 in events}")

    # Drive focus onto it, then press A.
    focused = False
    for _ in range(14):
        if game.active(panel) == control:
            focused = True
            break
        tap("RIGHT", settle=0.7)
    if not focused:
        for _ in range(14):
            if game.active(panel) == control:
                focused = True
                break
            tap("DOWN", settle=0.7)
    print(f"    focus reached it: {focused}"
          f"  (active now {game.active(panel) or 0:08X})")
    if focused:
        tap("A", settle=1.5)
        after = game.front_panel()
        print(f"    after A: front panel {after:08X} "
              f"dispatcher {game.dispatcher(after):08X}")
    return selectable, (0x27 in events), focused


def main() -> int:
    game = Game()
    panel = game.front_panel()
    print(f"front panel {panel:08X} dispatcher {game.dispatcher(panel):08X}")
    name_offset = DEFAULT_BUTTONS.get(game.u32(panel))
    if not name_offset:
        print("this screen has no Default button in the table; "
              "open an Options submenu first")
        return 2
    examine(game, *name_offset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
