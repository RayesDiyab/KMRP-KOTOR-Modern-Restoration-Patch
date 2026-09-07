#!/usr/bin/env python3
"""Raw XInput from the physical controller. No game required.

This answers one question before anything else is tuned: when the stick is
"barely touched", what does the hardware actually report? If a light touch
already reads 40% of full scale, no deadzone in the module is the real problem
and a response curve is the answer. If it reads 2% and the character still runs,
the fault is downstream and the module is where to look.

Usage:
    python testing/controller/raw_stick_monitor.py [--seconds 45]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import math
import time
from ctypes import wintypes


class Gamepad(ctypes.Structure):
    _fields_ = [("wButtons", wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                ("sThumbRY", ctypes.c_short)]


class State(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", Gamepad)]


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
        raise SystemExit("no XInput runtime found")

    state = State()
    slot = None
    for index in range(4):
        if dll.XInputGetState(index, ctypes.byref(state)) == 0:
            slot = index
            break
    if slot is None:
        raise SystemExit("no controller found - plug it in and try again")
    print("reading controller on XInput slot %d for %.0f seconds\n" % (slot, arguments.seconds))
    print("Move the LEFT STICK: rest, then the lightest touch you can manage,")
    print("then roughly 10%, 25%, 50%, and full. Hold each a moment.\n")

    rest_samples = []
    peak = 0.0
    deadline = time.time() + arguments.seconds
    last = 0.0
    while time.time() < deadline:
        if dll.XInputGetState(slot, ctypes.byref(state)) != 0:
            time.sleep(0.05)
            continue
        gp = state.Gamepad
        nx = gp.sThumbLX / 32767.0
        ny = gp.sThumbLY / 32767.0
        magnitude = math.sqrt(nx * nx + ny * ny)
        peak = max(peak, magnitude)
        if magnitude < 0.02:
            rest_samples.append(magnitude)
        now = time.time()
        if now - last > 0.1:
            last = now
            bar = "#" * int(magnitude * 50)
            print("\r  LX=%6d LY=%6d   magnitude=%.4f (%5.1f%%)  %-50s"
                  % (gp.sThumbLX, gp.sThumbLY, magnitude, magnitude * 100, bar),
                  end="", flush=True)
        time.sleep(0.02)

    print("\n")
    if rest_samples:
        print("resting magnitude: max %.4f (%.2f%% of full scale) over %d samples"
              % (max(rest_samples), 100 * max(rest_samples), len(rest_samples)))
    print("peak magnitude seen: %.4f" % peak)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
