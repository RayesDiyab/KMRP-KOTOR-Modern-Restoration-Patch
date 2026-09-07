#!/usr/bin/env python3
"""Walk the in-game tab strip one press at a time, reporting state after each.

Written to find why a scripted walk of all eight tabs ended with the menu shut
and the harness reading a stale tab index in gameplay. Prints, after every
press: the input class, whether the tab strip is still in front, the engine's
current tab, the module's in-content flag, and what has focus -- so the exact
press that closes the menu is visible rather than inferred.

Requires the virtual pad server and the game at a loaded save.

Usage:
    python testing/controller/probe_tab_walk.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import ctypes
import re
import socket
import struct
import subprocess
import time
from ctypes import wintypes

GAME_DIR = r"C:\Star Wars - KotOR"
LOG = GAME_DIR + r"\kmrp-native-joystick.log"
GUI_MANAGER_PTR = 0x007A39F4
APP_MANAGER_PTR = 0x007A39FC
INGAME_MENU_DISPATCHER = 0x00624970


def pad(command):
    sock = socket.create_connection(("127.0.0.1", 8787), timeout=5)
    sock.sendall((command + "\n").encode())
    reply = sock.recv(64).decode().strip()
    sock.close()
    if reply.startswith("err"):
        raise RuntimeError(f"{command}: {reply}")
    return reply


def tap(button, hold=0.2, settle=1.2):
    pad("press " + button)
    time.sleep(hold)
    pad("release " + button)
    time.sleep(settle)


def trigger(side, hold=0.25, settle=1.5):
    pad("triggers 1 0" if side == "LT" else "triggers 0 1")
    time.sleep(hold)
    pad("triggers 0 0")
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

    def u32(self, a):
        buf = ctypes.create_string_buffer(4)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(a), buf, 4,
                                        ctypes.byref(got)):
            return None
        return struct.unpack("<I", buf.raw)[0]

    def i32(self, a):
        v = self.u32(a)
        return None if v is None else struct.unpack("<i", struct.pack("<I", v))[0]

    def dispatcher(self, obj):
        vtable = self.u32(obj) if obj else None
        return self.u32(vtable + 0x3C) if vtable else 0

    def input_class(self):
        root = self.u32(APP_MANAGER_PTR)
        app = self.u32(root + 4) if root else None
        internal = self.u32(app + 4) if app else None
        return self.u32(internal + 0x9C) if internal else None

    def tab_index(self):
        root = self.u32(APP_MANAGER_PTR)
        app = self.u32(root + 4) if root else None
        internal = self.u32(app + 4) if app else None
        in_game = self.u32(internal + 0x40) if internal else None
        return self.i32(in_game + 0x2C) if in_game else None

    def panels(self):
        manager = self.u32(GUI_MANAGER_PTR)
        array = self.u32(manager + 0x88) if manager else None
        count = self.i32(manager + 0x8C) if manager else 0
        if not array or not count or count > 256:
            return []
        return [self.u32(array + i * 4) for i in range(count)]

    def tab_bar(self):
        for panel in reversed(self.panels()):
            if not panel or (self.u32(panel + 0x44) & 0x600):
                continue
            return panel if self.dispatcher(panel) == INGAME_MENU_DISPATCHER else None
        return None


def in_content():
    try:
        found = re.findall(r"tabin=(\d)", open(LOG, "r", errors="replace").read())
    except OSError:
        return None
    return bool(int(found[-1])) if found else None


def report(game, label):
    bar = game.tab_bar()
    front = game.panels()[-1] if game.panels() else None
    print(f"{label:<22} class={game.input_class()} tab={game.tab_index()} "
          f"strip={'yes' if bar else 'NO'} in_content={in_content()} "
          f"panels={len(game.panels())} front_disp={game.dispatcher(front):08X}")


def main() -> int:
    game = Game()
    if game.input_class() == 0:
        tap("START", settle=2.0)
    report(game, "menu open")
    for step in range(8):
        report(game, f"-- tab {game.tab_index()}")
        tap("DOWN", settle=1.3)
        report(game, "   after DOWN")
        for _ in range(6):
            if in_content() is not True:
                break
            tap("UP", settle=0.9)
        report(game, "   after UP(s)")
        trigger("RT")
        report(game, "   after RT")
        if not game.tab_bar():
            print("\nthe strip is gone -- stopping here")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
