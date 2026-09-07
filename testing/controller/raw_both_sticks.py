#!/usr/bin/env python3
"""Both thumbsticks, straight from XInput. No game, no module, no hooks.

If the right stick moves here and not in the game, the fault is in KMRP. If it
does not move here either, the controller or its driver is not reporting that
axis and nothing in KMRP can fix it.

Usage:
    python testing/controller/raw_both_sticks.py [--seconds 40]

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
    parser.add_argument("--seconds", type=float, default=40.0)
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
    print("controller on XInput slot %d\n" % slot)
    print("Move the RIGHT stick fully left and right, then the LEFT stick, then")
    print("press a few buttons. %.0f seconds.\n" % arguments.seconds)

    # Wait for the controller to be touched before measuring.
    #
    # An earlier version started its window immediately and reported "the right
    # stick is not reaching XInput" from a run in which the pad reported zero
    # state changes of any kind -- one distinct packet number, no buttons, both
    # sticks at rest. That is a harness bug producing a hardware verdict, which
    # is the worst kind of wrong answer. Now nothing is measured until the pad
    # actually moves.
    print("waiting for you to touch the controller...", flush=True)
    idle_packet = state.dwPacketNumber
    wait_until = time.time() + 120.0
    while time.time() < wait_until:
        if dll.XInputGetState(slot, ctypes.byref(state)) == 0:
            if state.dwPacketNumber != idle_packet:
                break
        time.sleep(0.02)
    else:
        print("\nno controller activity in 120s -- nothing was measured.")
        return 2
    print("movement detected, recording for %.0f seconds\n" % arguments.seconds)

    peak_l = peak_r = 0.0
    rx_lo = rx_hi = ry_lo = ry_hi = 0
    buttons_seen = 0
    packets = set()
    deadline = time.time() + arguments.seconds
    last = 0.0
    while time.time() < deadline:
        if dll.XInputGetState(slot, ctypes.byref(state)) != 0:
            time.sleep(0.05)
            continue
        gp = state.Gamepad
        packets.add(state.dwPacketNumber)
        buttons_seen |= gp.wButtons
        peak_l = max(peak_l, math.hypot(gp.sThumbLX / 32767.0, gp.sThumbLY / 32767.0))
        peak_r = max(peak_r, math.hypot(gp.sThumbRX / 32767.0, gp.sThumbRY / 32767.0))
        rx_lo, rx_hi = min(rx_lo, gp.sThumbRX), max(rx_hi, gp.sThumbRX)
        ry_lo, ry_hi = min(ry_lo, gp.sThumbRY), max(ry_hi, gp.sThumbRY)
        now = time.time()
        if now - last > 0.1:
            last = now
            print("\r  L(%6d,%6d) %5.1f%%   R(%6d,%6d) %5.1f%%   buttons %04X    "
                  % (gp.sThumbLX, gp.sThumbLY, peak_l * 100,
                     gp.sThumbRX, gp.sThumbRY, math.hypot(
                         gp.sThumbRX / 32767.0, gp.sThumbRY / 32767.0) * 100,
                     gp.wButtons), end="", flush=True)
        time.sleep(0.02)

    print("\n")
    print("left  stick peak magnitude : %.3f" % peak_l)
    print("right stick peak magnitude : %.3f" % peak_r)
    print("right X range              : %d .. %d" % (rx_lo, rx_hi))
    print("right Y range              : %d .. %d" % (ry_lo, ry_hi))
    print("buttons seen (mask)        : %04X" % buttons_seen)
    print("distinct packet numbers    : %d" % len(packets))
    print()
    # Three outcomes, and the middle one must never be reported as the first.
    if len(packets) <= 1:
        print("VERDICT: the controller reported no state changes at all, so nothing")
        print("         was measured. This says nothing about the right stick.")
    elif peak_l < 0.10 and peak_r < 0.10:
        print("VERDICT: the pad changed state but neither stick moved far. Try again")
        print("         and push both sticks fully.")
    elif peak_r < 0.10:
        print("VERDICT: the LEFT stick reports (%.2f) and the RIGHT stick does not"
              % peak_l)
        print("         (%.3f). The right stick is not reaching XInput, which is" % peak_r)
        print("         upstream of KMRP -- driver, controller mode, or a remapper.")
    else:
        print("VERDICT: the right stick reports fine here (%.2f), so the fault is in"
              % peak_r)
        print("         the game-side path and KMRP is where to look.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
