#!/usr/bin/env python3
"""The keyboard must keep vanilla movement after the analog Normalize bypass.

The bypass at 0x00679B71 skips Vector::Normalize so the stick's magnitude
survives. Nothing about that may reach the keyboard, where each axis is exactly
+/-1: without the normalize a keyboard diagonal would travel sqrt(2) -- about
41% -- faster than a cardinal, which is the classic bug this proves absent.

Measured from the engine's own state: the movement vector at
playerControl+0x10/+0x14 and the resulting velocity at +0x5C/+0x60.

No controller may be connected -- the module reads the first connected XInput
slot, and a pad at rest would still count as "connected".

Usage:
    python testing/controller/test_keyboard_normalize.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import ctypes
import math
import os
import re
import struct
import subprocess
import time
from ctypes import wintypes

GAME_DIR = r"C:\Star Wars - KotOR"
LOG = os.path.join(GAME_DIR, "kmrp-native-joystick.log")
PC_UPDOWN, PC_LEFTRIGHT, PC_VELX, PC_VELY = 0x10, 0x14, 0x5C, 0x60

# swkotor.ini binds movement to the arrow keys / WASD; these are the scancodes
# the game's DirectInput keyboard path sees.
SC_W, SC_S, SC_A, SC_D = 0x11, 0x1F, 0x1E, 0x20

user32 = ctypes.windll.user32


class KeyInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class InputUnion(ctypes.Union):
    _fields_ = [("ki", KeyInput), ("padding", ctypes.c_ubyte * 32)]


class Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", InputUnion)]


def key(scancode, down):
    flags = 0x0008 | (0 if down else 0x0002)          # SCANCODE | KEYUP
    item = Input(type=1, u=InputUnion(ki=KeyInput(0, scancode, flags, 0, None)))
    user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(Input))


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

    def f32(self, a):
        buf = ctypes.create_string_buffer(4)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(a), buf, 4,
                                        ctypes.byref(got)):
            return None
        return struct.unpack("<f", buf.raw)[0]


def player_control():
    try:
        text = open(LOG, "r", errors="replace").read()
    except OSError:
        return None
    found = re.findall(r"pc=([0-9A-Fa-f]{8})", text)
    return int(found[-1], 16) if found else None


def hold(game, pc, scancodes, seconds=1.4):
    """Hold keys, then sample the steady-state vector and speed."""
    for sc in scancodes:
        key(sc, True)
    time.sleep(seconds)
    samples = []
    for _ in range(12):
        ud = game.f32(pc + PC_UPDOWN)
        lr = game.f32(pc + PC_LEFTRIGHT)
        vx = game.f32(pc + PC_VELX)
        vy = game.f32(pc + PC_VELY)
        if None not in (ud, lr, vx, vy):
            samples.append((math.sqrt(ud * ud + lr * lr), math.sqrt(vx * vx + vy * vy)))
        time.sleep(0.05)
    for sc in scancodes:
        key(sc, False)
    time.sleep(1.0)
    if not samples:
        return None, None
    samples.sort(key=lambda s: s[1])
    return samples[len(samples) // 2]


def main() -> int:
    # A connected pad would be read in preference to the keyboard path.
    dll = None
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.windll.LoadLibrary(name)
            break
        except Exception:
            continue
    if dll:
        class GP(ctypes.Structure):
            _fields_ = [("b", wintypes.WORD), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte),
                        ("lx", ctypes.c_short), ("ly", ctypes.c_short),
                        ("rx", ctypes.c_short), ("ry", ctypes.c_short)]

        class ST(ctypes.Structure):
            _fields_ = [("p", wintypes.DWORD), ("g", GP)]
        st = ST()
        connected = [i for i in range(4) if dll.XInputGetState(i, ctypes.byref(st)) == 0]
        if connected:
            print("REFUSING: a controller is connected on slot(s) %s." % connected)
            print("Unplug it: the module reads the first connected pad, so this")
            print("would not be measuring the keyboard path at all.")
            return 2

    game = Game()
    pc = player_control()
    if not pc:
        raise SystemExit("player control object not published; is a save loaded?")
    print("player control = %08X\n" % pc)

    cardinal_vec, cardinal_speed = hold(game, pc, [SC_W])
    diagonal_vec, diagonal_speed = hold(game, pc, [SC_W, SC_D])

    print("%-22s %10s %10s" % ("keyboard", "vector", "speed"))
    print("%-22s %10s %10s" % ("forward (W)",
                               "%.3f" % cardinal_vec if cardinal_vec else "?",
                               "%.2f" % cardinal_speed if cardinal_speed else "?"))
    print("%-22s %10s %10s" % ("diagonal (W+D)",
                               "%.3f" % diagonal_vec if diagonal_vec else "?",
                               "%.2f" % diagonal_speed if diagonal_speed else "?"))

    if cardinal_speed and diagonal_speed:
        ratio = diagonal_speed / cardinal_speed
        print("\ndiagonal / cardinal speed = %.3f" % ratio)
        if ratio > 1.2:
            print("FAIL: the keyboard diagonal is faster than the cardinal.")
            print("      Normalize is being skipped on the keyboard path.")
            return 1
        print("PASS: no sqrt(2) boost; Normalize still runs for the keyboard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
