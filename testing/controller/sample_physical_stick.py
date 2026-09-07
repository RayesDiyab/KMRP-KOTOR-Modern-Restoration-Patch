#!/usr/bin/env python3
"""Instrument the whole movement chain while a PHYSICAL controller drives it.

Run this, then push the left stick through the deflections it asks for. It
records, per sample:

  raw LX / LY          straight from XInputGetState, the same call the module makes
  raw magnitude        sqrt(nx^2 + ny^2), 0..1
  after deadzone       what the module's radial deadzone leaves
  after rescale        what the module actually emits, 0..1
  UpDown / LeftRight   the engine's own movement inputs, post-clamp
  velocity             the movement integrator's output
  walking              CSWCreature's walk flag -- walk animation vs run

The point is to separate two different complaints that feel identical: "a small
push moves me too fast" (a magnitude problem) and "a small push looks like a
run" (an animation problem). They have different fixes.

No virtual pad may be running: it would appear as a second XInput device and
this would sample the wrong one.

Usage:
    python testing/controller/sample_physical_stick.py [--seconds 90]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
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

EXOINPUT_GLOBAL = 0x007A39E4
DESCRIPTIONS = 0x128
DESC_ACCUM = 0x24

# player control object fields, as the e2e suite reads them
PC_UPDOWN, PC_LEFTRIGHT, PC_WALKING, PC_VELX, PC_VELY = 0x10, 0x14, 0x18, 0x5C, 0x60

# must match K1NativeJoystick.cpp
K1_STICK_DEADZONE = 0.08
AXIS_FULL_SCALE = 32767.0

# Bins straddle the 25% deadzone edge deliberately: 22-25% must be silent and
# 25-28% must be the gentlest movement there is, and those two claims are the
# whole point of the change.
# Bins straddle the 15% deadzone edge: below it must be silent, just above it
# must be the gentlest movement there is.
BINS = [(0.000, 0.010, "rest"), (0.010, 0.100, "below 10%"),
        (0.100, 0.150, "~10-15% (still dead)"),
        (0.150, 0.200, "~15-20% (first movement)"), (0.200, 0.275, "~20-27%"),
        (0.275, 0.350, "~27-35%"), (0.350, 0.450, "~35-45%"),
        (0.450, 0.550, "~45-55%"), (0.550, 0.700, "~55-70%"),
        (0.700, 0.850, "~70-85%"), (0.850, 1.010, "~85-100%")]


class XInput:
    class _Gamepad(ctypes.Structure):
        _fields_ = [("wButtons", wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte),
                    ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                    ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                    ("sThumbRY", ctypes.c_short)]

    class _State(ctypes.Structure):
        pass

    def __init__(self):
        XInput._State._fields_ = [("dwPacketNumber", wintypes.DWORD),
                                  ("Gamepad", XInput._Gamepad)]
        self.dll = None
        for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                self.dll = ctypes.windll.LoadLibrary(name)
                break
            except Exception:
                continue
        self.slot = None

    def read(self):
        if not self.dll:
            return None
        state = XInput._State()
        slots = [self.slot] if self.slot is not None else range(4)
        for slot in slots:
            if self.dll.XInputGetState(slot, ctypes.byref(state)) == 0:
                self.slot = slot
                return state.Gamepad
        return None


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
        self.internal = self.u32(self.u32(EXOINPUT_GLOBAL) + 4)
        self.descs = self.u32(self.internal + DESCRIPTIONS)

    def read(self, a, n=4):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(a), buf, n,
                                        ctypes.byref(got)):
            return None
        return buf.raw

    def u32(self, a):
        raw = self.read(a)
        return struct.unpack("<I", raw)[0] if raw else None

    def i32(self, a):
        v = self.u32(a)
        return None if v is None else struct.unpack("<i", struct.pack("<I", v))[0]

    def f32(self, a):
        v = self.u32(a)
        return None if v is None else struct.unpack("<f", struct.pack("<I", v))[0]

    def accum(self, event):
        d = self.u32(self.descs + event * 4)
        return self.i32(d + DESC_ACCUM) if d else None


def player_control():
    """Published by the module's diagnostic line as pc=XXXXXXXX."""
    try:
        text = open(LOG, "r", errors="replace").read()
    except OSError:
        return None
    found = re.findall(r"pc=([0-9A-Fa-f]{8})", text)
    return int(found[-1], 16) if found else None


def module_curve(nx, ny):
    """Exactly what K1NativeJoystick.cpp does today, so we can compare."""
    magnitude = math.sqrt(nx * nx + ny * ny)
    if magnitude <= K1_STICK_DEADZONE:
        return 0.0, 0.0
    scaled = (magnitude - K1_STICK_DEADZONE) / (1.0 - K1_STICK_DEADZONE)
    return magnitude, min(scaled, 1.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=120.0)
    arguments = parser.parse_args()

    pads = XInput()
    if not pads.dll:
        raise SystemExit("no XInput DLL")
    game = Game()
    pc = player_control()
    print("player control object: %s" % ("%08X" % pc if pc else "not published yet"))
    print("\nPush the LEFT STICK slowly through: untouched, barely, 10%, 20%, 30%,")
    print("40%, 50%, 75%, 100%. Hold each for about two seconds. Spend most of the")
    print("time between 0 and 40%%. Sampling for %.0f seconds.\n" % arguments.seconds)

    samples = []
    deadline = time.time() + arguments.seconds
    last_print = 0.0
    while time.time() < deadline:
        gp = pads.read()
        if gp is None:
            time.sleep(0.05)
            continue
        nx = gp.sThumbLX / AXIS_FULL_SCALE
        ny = gp.sThumbLY / AXIS_FULL_SCALE
        raw_mag, emitted = module_curve(nx, ny)

        updown = leftright = velx = vely = None
        walking = None
        if pc:
            updown = game.f32(pc + PC_UPDOWN)
            leftright = game.f32(pc + PC_LEFTRIGHT)
            walking = game.i32(pc + PC_WALKING)
            velx = game.f32(pc + PC_VELX)
            vely = game.f32(pc + PC_VELY)
        speed = (math.sqrt(velx * velx + vely * vely)
                 if velx is not None and vely is not None else None)
        engine_mag = (math.sqrt(updown * updown + leftright * leftright)
                      if updown is not None and leftright is not None else None)

        samples.append((raw_mag, emitted, engine_mag, speed, walking,
                        gp.sThumbLX, gp.sThumbLY))

        now = time.time()
        if now - last_print > 0.25:
            last_print = now
            print("\r  raw=%.3f  emitted=%.3f  engine=%s  speed=%s  walking=%s   "
                  % (raw_mag, emitted,
                     "%.3f" % engine_mag if engine_mag is not None else "?",
                     "%.2f" % speed if speed is not None else "?",
                     walking), end="", flush=True)
        time.sleep(0.02)

    print("\n\n%d samples\n" % len(samples))
    print("%-16s %7s %8s %8s %8s %8s %8s" %
          ("stick", "n", "raw", "emitted", "engine", "speed", "walking"))
    for low, high, label in BINS:
        rows = [s for s in samples if low <= s[0] < high]
        if not rows:
            print("%-16s %7s  -- not sampled --" % (label, 0))
            continue
        def med(index):
            vals = sorted(r[index] for r in rows if r[index] is not None)
            return vals[len(vals) // 2] if vals else None
        walk_vals = [r[4] for r in rows if r[4] is not None]
        walking = ("%d%% walk" % (100 * sum(1 for w in walk_vals if w) / len(walk_vals))
                   if walk_vals else "?")
        print("%-16s %7d %8.3f %8.3f %8s %8s %8s" %
              (label, len(rows), med(0) or 0.0, med(1) or 0.0,
               "%.3f" % med(2) if med(2) is not None else "?",
               "%.2f" % med(3) if med(3) is not None else "?",
               walking))

    peak = max((s[3] for s in samples if s[3] is not None), default=None)
    print("\npeak speed observed: %s" % ("%.2f" % peak if peak else "?"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
