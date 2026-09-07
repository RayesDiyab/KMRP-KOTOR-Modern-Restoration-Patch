#!/usr/bin/env python3
"""The Normalize bypass must never survive into keyboard movement.

Three ways the analog override could plausibly get stuck on, each of which would
show up as a keyboard diagonal running sqrt(2) too fast:

  controller -> centre -> keyboard
  controller -> disconnect -> keyboard
  GUI -> gameplay -> keyboard

Each is driven with the virtual pad, then the pad is silenced and the keyboard
is measured. A ratio near 1.0 means Normalize still runs for the keyboard.

Requires the virtual pad server and no physical controller.

Usage:
    python testing/controller/test_override_handoff.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import ctypes
import math
import os
import re
import socket
import struct
import subprocess
import time
from ctypes import wintypes

GAME_DIR = r"C:\Star Wars - KotOR"
LOG = os.path.join(GAME_DIR, "kmrp-native-joystick.log")
HOST, PORT = "127.0.0.1", 8787
PC_UPDOWN, PC_LEFTRIGHT, PC_VELX, PC_VELY = 0x10, 0x14, 0x5C, 0x60
SC_W, SC_D = 0x11, 0x20

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
    flags = 0x0008 | (0 if down else 0x0002)
    item = Input(type=1, u=InputUnion(ki=KeyInput(0, scancode, flags, 0, None)))
    user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(Input))


def pad(command):
    s = socket.create_connection((HOST, PORT), timeout=5)
    s.sendall((command + "\n").encode())
    reply = s.recv(64).decode().strip()
    s.close()
    if reply.startswith("err"):
        raise RuntimeError(reply)
    return reply


class Game:
    def __init__(self):
        self.k = ctypes.windll.kernel32
        self.k.OpenProcess.restype = wintypes.HANDLE
        pid = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process swkotor -ErrorAction SilentlyContinue).Id"]).decode().strip()
        self.handle = self.k.OpenProcess(0x0010 | 0x0400, False, int(pid.splitlines()[0]))

    def f32(self, a):
        buf = ctypes.create_string_buffer(4)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(a), buf, 4,
                                        ctypes.byref(got)):
            return None
        return struct.unpack("<f", buf.raw)[0]


def player_control():
    text = open(LOG, "r", errors="replace").read()
    return int(re.findall(r"pc=([0-9A-Fa-f]{8})", text)[-1], 16)


def override_flag():
    text = open(LOG, "r", errors="replace").read()
    found = re.findall(r"ovr=(\d)", text)
    return int(found[-1]) if found else None


def keyboard_speed(game, pc, keys, seconds=1.3):
    for sc in keys:
        key(sc, True)
    time.sleep(seconds)
    speeds = []
    for _ in range(10):
        vx, vy = game.f32(pc + PC_VELX), game.f32(pc + PC_VELY)
        if vx is not None and vy is not None:
            speeds.append(math.sqrt(vx * vx + vy * vy))
        time.sleep(0.05)
    for sc in keys:
        key(sc, False)
    time.sleep(1.0)
    speeds.sort()
    return speeds[len(speeds) // 2] if speeds else None


def main() -> int:
    game = Game()
    pc = player_control()
    print("player control = %08X\n" % pc)
    failures = 0

    baseline_cardinal = keyboard_speed(game, pc, [SC_W])
    baseline_diagonal = keyboard_speed(game, pc, [SC_W, SC_D])
    print("baseline keyboard: cardinal %.2f  diagonal %.2f  ratio %.3f"
          % (baseline_cardinal, baseline_diagonal, baseline_diagonal / baseline_cardinal))

    scenarios = []

    # 1. controller -> centre -> keyboard
    pad("lstick 0 1")
    time.sleep(1.2)
    pad("lstick 0 0")
    time.sleep(0.8)
    scenarios.append(("controller -> centre -> keyboard", None))

    # 2. controller -> disconnect -> keyboard
    def scenario_two():
        pad("lstick 0 1")
        time.sleep(1.0)
        pad("quit")            # the pad vanishes mid-push
        time.sleep(2.0)
    scenarios.append(("controller -> disconnect -> keyboard", scenario_two))

    results = []
    for name, setup in scenarios:
        if setup:
            try:
                setup()
            except (OSError, RuntimeError):
                pass
        diagonal = keyboard_speed(game, pc, [SC_W, SC_D])
        cardinal = keyboard_speed(game, pc, [SC_W])
        ratio = diagonal / cardinal if cardinal else 0
        ok = ratio < 1.2
        failures += 0 if ok else 1
        print("  %-38s cardinal %.2f diagonal %.2f ratio %.3f  %s"
              % (name, cardinal, diagonal, ratio, "PASS" if ok else "FAIL"))
        results.append((name, ratio))

    print("\noverride flag now: %s (expected 0 with no pad driving)" % override_flag())
    if failures:
        print("\n%d handoff scenario(s) FAILED - the bypass leaked to the keyboard" % failures)
        return 1
    print("\nall handoff scenarios pass: the bypass never reaches the keyboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
