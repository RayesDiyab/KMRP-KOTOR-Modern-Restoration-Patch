#!/usr/bin/env python3
"""Drive the gameplay HUD's bottom-right action bar with the D-pad.

Reads the ENGINE's state, not the module's counters: the active control on
CSWGuiMainInterface, and which of the seven action buttons it is. A module that
counts presses it never delivered looks identical to a working one from its own
diagnostics, which is the failure this avoids.

Layout, from Saul0097's K1_CONFIG in vendor/K1XboxControls.cpp:

    mainInterface + 0x1C     the active (focused) control
    mainInterface + 0xBC     the target-action menu, 3 lists
    mainInterface + 0x772C   the personal/ability actions, 4 slots
    action group size        0x71C, with control offsets 0, 0x1C4, 0x388, 0x54C

Requires the virtual pad server, the game running, and a loaded save in
gameplay.

Usage:
    python testing/controller/probe_action_bar.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import ctypes
import os
import re
import socket
import struct
import subprocess
import time
from ctypes import wintypes

APP_MANAGER_PTR = 0x007A39FC
LOG = os.path.join(r"C:\Star Wars - KotOR", "kmrp-native-joystick.log")
HOST, PORT = "127.0.0.1", 8787

PANEL_ACTIVE_CONTROL = 0x1C
TARGET_ACTION_MENU = 0xBC
PERSONAL_ACTIONS = 0x772C
ACTION_GROUP_SIZE = 0x71C
ACTION_CONTROL_OFFSETS = (0x000, 0x1C4, 0x388, 0x54C)
TARGET_ACTION_COUNT = 3
PERSONAL_ACTION_COUNT = 4


def pad(command):
    sock = socket.create_connection((HOST, PORT), timeout=5)
    sock.sendall((command + "\n").encode())
    reply = sock.recv(64).decode().strip()
    sock.close()
    if reply.startswith("err"):
        raise RuntimeError(f"{command}: {reply}")
    return reply


def tap(button, hold=0.18, settle=0.85):
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

    def u32(self, address):
        buf = ctypes.create_string_buffer(4)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf, 4,
                                        ctypes.byref(got)):
            return None
        return struct.unpack("<I", buf.raw)[0]

    def internal(self):
        root = self.u32(APP_MANAGER_PTR)
        app = self.u32(root + 4) if root else None
        return self.u32(app + 4) if app else None

    def input_class(self):
        internal = self.internal()
        return self.u32(internal + 0x9C) if internal else None

    def main_interface(self):
        """The pointer the HUD hook is actually handed, from the module's dump.

        Derived from CGuiInGame+0x18 at first, which produced a different and
        plausible-looking object -- a manager pointer at +0x18 and all -- and
        every reading taken through it was of the wrong thing. The module
        publishes what the engine hands it, so ask that instead of guessing.
        """
        try:
            with open(LOG, "r", errors="replace") as handle:
                found = re.findall(r"hud=\d+/\d+/\d+/([0-9A-Fa-f]{8})/", handle.read())
        except OSError:
            return None
        return int(found[-1], 16) if found else None

    def action_buttons(self):
        """The seven slots, in the order Saul's GetActionButtons builds them."""
        base = self.main_interface()
        if not base:
            return []
        out = []
        target = base + TARGET_ACTION_MENU
        for i in range(TARGET_ACTION_COUNT):
            out.append(target + i * 0x1C4)
        personal = base + PERSONAL_ACTIONS
        for i in range(PERSONAL_ACTION_COUNT):
            out.append(personal + i * ACTION_GROUP_SIZE)
        return out

    def active_control(self):
        base = self.main_interface()
        return self.u32(base + PANEL_ACTIVE_CONTROL) if base else None

    def active_slot(self):
        """Which slot holds focus, by matching the control offsets."""
        active = self.active_control()
        if not active:
            return None
        for index, button in enumerate(self.action_buttons()):
            for offset in ACTION_CONTROL_OFFSETS:
                if button + offset == active:
                    return index
        return None


def main() -> int:
    game = Game()
    print(f"input class {game.input_class()}   "
          f"main interface {game.main_interface():08X}")
    if game.input_class() != 0:
        print("not in gameplay; nothing to drive")
        return 2

    print(f"\nactive slot at rest: {game.active_slot()}  "
          f"(control {game.active_control() or 0:08X})")

    print("\n-- RIGHT x5")
    seen = []
    for _ in range(5):
        tap("RIGHT")
        seen.append(game.active_slot())
        print(f"   slot={seen[-1]}  control={game.active_control() or 0:08X}")

    print("\n-- LEFT x3")
    for _ in range(3):
        tap("LEFT")
        print(f"   slot={game.active_slot()}  control={game.active_control() or 0:08X}")

    print("\n-- DOWN x3 (cycle the action in this slot)")
    for _ in range(3):
        before = game.active_control()
        tap("DOWN")
        print(f"   slot={game.active_slot()}  control "
              f"{before or 0:08X} -> {game.active_control() or 0:08X}")

    print("\n-- UP x3")
    for _ in range(3):
        tap("UP")
        print(f"   slot={game.active_slot()}  control={game.active_control() or 0:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
