#!/usr/bin/env python3
"""Trace the right-stick camera path end to end on a PHYSICAL controller.

Six stages, so the report can name the one that is silent rather than guessing:

  1 XInput RX/RY        read here, from the same API the module calls
  2 module's rightX/rY  what the buffer hook last stored (from the dump)
  3 bridge ran/wrote    how often FeedNativeCameraK1 ran, wrote, or bailed
  4 turn amount        the value it handed to CSWCModule::RotateCamera
  5 engine accepted    whether RotateCamera was reached, with its receiver live
  6 input class        the camera only turns in gameplay (class 0 or 4)

Also reports which XInput slot is live and whether the counters are advancing,
because a bridge that never runs and a bridge that runs and writes zero look
identical from the outside.

Usage:
    python testing/controller/trace_camera_chain.py [--seconds 45]

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
APP_MANAGER_PTR = 0x007A39FC
MOUSE_DELTA_X = 0x3A0           # written by the engine, discarded by UpdateCamera
CAMERA_DEADZONE = 0.12          # must match K1_CAMERA_DEADZONE


class Gamepad(ctypes.Structure):
    _fields_ = [("wButtons", wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                ("sThumbRY", ctypes.c_short)]


class State(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", Gamepad)]


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

    def f32(self, a):
        raw = self.read(a)
        return struct.unpack("<f", raw)[0] if raw else None

    def camera_owner(self):
        """[CClientExoAppInternal+0x18] -- RotateCamera's receiver.

        The facing itself is deliberately NOT read. RotateCamera reaches it
        through a virtual call on a camera object fetched from [owner+0x40],
        and guessing that offset from outside the process is how the previous
        round of this investigation went wrong: +0x3A0 was read, agreed with
        itself, and the camera was not moving. Visible rotation is the pass
        condition, and a human has to supply it.
        """
        root = self.u32(APP_MANAGER_PTR)
        app = self.u32(root + 4) if root else None
        internal = self.u32(app + 4) if app else None
        return self.u32(internal + 0x18) if internal else None

    def input_class(self):
        root = self.u32(APP_MANAGER_PTR)
        app = self.u32(root + 4) if root else None
        internal = self.u32(app + 4) if app else None
        return self.u32(internal + 0x9C) if internal else None


FIELDS = ("rx", "ry", "camrun", "camwr", "camdz", "camapp", "camcls", "camown",
          "buf", "count")


def dump():
    """The module's own view, from its diagnostic line."""
    try:
        text = open(LOG, "r", errors="replace").read()
    except OSError:
        return {}
    out = {}
    for name in FIELDS:
        found = re.findall(r"\b%s=(-?\d+)" % name, text)
        if found:
            out[name] = int(found[-1])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=45.0)
    arguments = parser.parse_args()

    dll = None
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.windll.LoadLibrary(name)
            break
        except Exception:
            continue
    if not dll:
        raise SystemExit("no XInput runtime")
    state = State()
    slot = None
    for index in range(4):
        if dll.XInputGetState(index, ctypes.byref(state)) == 0:
            slot = index
            break
    if slot is None:
        raise SystemExit("no controller connected")

    game = Game()
    print("XInput slot %d, CExoInputInternal %08X, input class %s\n"
          % (slot, game.internal, game.input_class()))
    print("Move the RIGHT STICK left and right. Recording %.0fs.\n" % arguments.seconds)

    start = dump()
    samples = []
    deadline = time.time() + arguments.seconds
    last = 0.0
    while time.time() < deadline:
        if dll.XInputGetState(slot, ctypes.byref(state)) != 0:
            time.sleep(0.05)
            continue
        gp = state.Gamepad
        rx = gp.sThumbRX / 32767.0
        ry = gp.sThumbRY / 32767.0
        magnitude = math.sqrt(rx * rx + ry * ry)
        d = dump()
        samples.append((magnitude, rx, game.camera_owner(), d.get("rx"), d.get("camapp"),
                        d.get("camwr"), game.input_class()))
        now = time.time()
        if now - last > 0.25:
            last = now
            print("\r  XInput RX=%6d mag=%.3f | module rx=%-7s | camapp=%-7s "
                  "camwr=%-8s | owner=%-8s cls=%s      "
                  % (gp.sThumbRX, magnitude, d.get("rx"), d.get("camapp"),
                     d.get("camwr"), ("%08X" % game.camera_owner()) if game.camera_owner() else "none",
                     game.input_class()), end="", flush=True)
        time.sleep(0.02)

    end = dump()
    print("\n\n--- stage by stage ---")
    pushed = [s for s in samples if s[0] > CAMERA_DEADZONE]
    print("1 XInput          : peak |RX| magnitude %.3f over %d samples, %d past the %.0f%% deadzone"
          % (max((s[0] for s in samples), default=0), len(samples), len(pushed), CAMERA_DEADZONE * 100))
    print("2 module rightX   : values seen %s"
          % sorted({s[3] for s in samples if s[3] is not None})[:8])
    print("3 bridge ran      : camrun %s -> %s   wrote %s -> %s   below-deadzone %s -> %s"
          % (start.get("camrun"), end.get("camrun"), start.get("camwr"), end.get("camwr"),
             start.get("camdz"), end.get("camdz")))
    print("4 turn amount     : values seen %s (x100)"
          % sorted({s[4] for s in samples if s[4] is not None})[:8])
    owners = {s[2] for s in samples if s[2]}
    print("5 engine accepted : receiver %s"
          % (", ".join("%08X" % o for o in sorted(owners)) if owners else "NEVER LIVE"))
    print("6 input class     : %s" % sorted({s[6] for s in samples if s[6] is not None}))
    print("  buffer calls    : buf %s -> %s   device count %s"
          % (start.get("buf"), end.get("buf"), end.get("count")))
    print("  bridge refusals : wrong class %s -> %s   no module %s -> %s"
          % (start.get("camcls"), end.get("camcls"),
             start.get("camown"), end.get("camown")))
    print()
    if end.get("camwr", 0) != start.get("camwr", 0):
        print("VERDICT: the bridge reached RotateCamera %s times with a live receiver."
              % (end.get("camwr", 0) - start.get("camwr", 0)))
        print("         Whether the view rotated is a question only your eyes answer.")
    else:
        print("VERDICT: the bridge never called RotateCamera -- see the counters above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
