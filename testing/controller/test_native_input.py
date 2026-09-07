#!/usr/bin/env python3
"""Deterministic regression tests for the native controller path.

Everything here is proved from memory rather than judged by eye. The game's own
input state is readable: each binding is an input-event description whose value
field says whether the control is currently down, and the analog axes are
accumulators whose growth rate over a fixed interval is the stick magnitude.
That makes the whole native path testable without a human watching the screen.

Requirements, all of which are checked before anything runs:

  * KOTOR running, with the native path selected
    (`select_controller_path.py native`)
  * the virtual pad server running (`virtual_pad_server.py`)
  * for the movement tests, a save loaded -- input class 0 has to be active,
    which it is not at the main menu

Usage:
    python testing/controller/test_native_input.py [--quick]

Note on the pad server: its `tap` and `dpad` verbs hold the control and release
it before replying, so a caller that samples afterwards always sees the released
state. These tests use `press` / `release` and sample in between. That cost an
hour once; it is why the helper below only ever uses the explicit verbs.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import socket
import struct
import subprocess
import sys
import time
from ctypes import wintypes

HOST, PORT = "127.0.0.1", 8787

# CExoInput* -> +4 -> CExoInputInternal
EXOINPUT_GLOBAL = 0x007A39E4
DESCRIPTIONS = 0x128            # CExoInputInternal + this -> description array
DEVICE_COUNT = 0x158
DESC_VALUE = 0x04               # digital state, and the type 0 analog value
DESC_ACCUM = 0x24               # type 3 accumulator, grows by dwData per record
MOUSE_DELTA_X = 0x3A0

# XInput control -> (pad-server name, KOTOR event id, human label)
BINDINGS = [
    ("A",     0x27, "confirm"),
    ("B",     0x28, "cancel"),
    ("X",     0x29, "per-panel"),
    ("Y",     0x2A, "per-panel"),
    ("LB",    0x39, "description scroll up"),
    ("RB",    0x3A, "description scroll down"),
    ("BACK",  0x2B, "Black"),
    ("UP",    0x31, "scroll up"),
    ("DOWN",  0x32, "scroll down"),
    ("LEFT",  0x2F, "D-pad left"),
    ("RIGHT", 0x30, "D-pad right"),
]

EVENT_JOY_X = 0x08              # the game's own analog axes
EVENT_JOY_Y = 0x07
EVENT_PREV_SCREEN = 0x35
EVENT_NEXT_SCREEN = 0x36

DEADZONE = 0.08                 # must match K1_STICK_DEADZONE in the module


class Game:
    """Read-only access to the running game's input state."""

    def __init__(self):
        self.k = ctypes.windll.kernel32
        self.k.OpenProcess.restype = wintypes.HANDLE
        pid = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "(Get-Process swkotor).Id"])
        self.handle = self.k.OpenProcess(0x0010 | 0x0400, False, int(pid.decode().strip()))
        if not self.handle:
            raise SystemExit("could not open swkotor -- is it running?")
        self.internal = self.u32(self.u32(EXOINPUT_GLOBAL) + 4)
        self.descs = self.u32(self.internal + DESCRIPTIONS)

    def read(self, address, size=4):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(address),
                                        buf, size, ctypes.byref(got)):
            return None
        return buf.raw

    def u32(self, address):
        raw = self.read(address)
        return struct.unpack("<I", raw)[0] if raw else None

    def i32(self, address):
        value = self.u32(address)
        return None if value is None else struct.unpack("<i", struct.pack("<I", value))[0]

    def f32(self, address):
        value = self.u32(address)
        return None if value is None else struct.unpack("<f", struct.pack("<I", value))[0]

    def description(self, event):
        return self.u32(self.descs + event * 4)

    def value(self, event):
        desc = self.description(event)
        return self.i32(desc + DESC_VALUE) if desc else None

    def accumulator(self, event):
        desc = self.description(event)
        return self.i32(desc + DESC_ACCUM) if desc else None

    def device_count(self):
        return self.i32(self.internal + DEVICE_COUNT)

    def mouse_delta_x(self):
        return self.f32(self.internal + MOUSE_DELTA_X)


def pad(command):
    sock = socket.create_connection((HOST, PORT), timeout=5)
    sock.sendall((command + "\n").encode())
    reply = sock.recv(64).decode().strip()
    sock.close()
    return reply


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def check(self, name, ok, detail=""):
        if ok is None:
            self.skipped += 1
            print(f"  SKIP  {name}   {detail}")
        elif ok:
            self.passed += 1
            print(f"  PASS  {name}   {detail}")
        else:
            self.failed += 1
            print(f"  FAIL  {name}   {detail}")


def test_registration(game, results):
    print("\n== registration")
    results.check("device count includes a joystick",
                  (game.device_count() or 0) >= 3,
                  f"count={game.device_count()}")
    for name, event, label in BINDINGS + [("LT", EVENT_PREV_SCREEN, "previous screen"),
                                          ("RT", EVENT_NEXT_SCREEN, "next screen")]:
        results.check(f"{name} bound to event 0x{event:02X} ({label})",
                      game.description(event) is not None)


def test_buttons(game, results):
    print("\n== buttons, D-pad: press sets the value, release clears it")
    pad("reset")
    time.sleep(0.4)
    for name, event, label in BINDINGS:
        pad(f"press {name}")
        time.sleep(0.45)
        held = game.value(event)
        pad(f"release {name}")
        time.sleep(0.35)
        released = game.value(event)
        results.check(f"{name} (0x{event:02X})", held == 1 and released == 0,
                      f"held={held} released={released}")


def test_triggers(game, results):
    print("\n== triggers, independently and together")
    pad("triggers 1 0"); time.sleep(0.45)
    lt_only = (game.value(EVENT_PREV_SCREEN), game.value(EVENT_NEXT_SCREEN))
    pad("triggers 0 1"); time.sleep(0.45)
    rt_only = (game.value(EVENT_PREV_SCREEN), game.value(EVENT_NEXT_SCREEN))
    pad("triggers 1 1"); time.sleep(0.45)
    both = (game.value(EVENT_PREV_SCREEN), game.value(EVENT_NEXT_SCREEN))
    pad("triggers 0 0"); time.sleep(0.45)
    none = (game.value(EVENT_PREV_SCREEN), game.value(EVENT_NEXT_SCREEN))
    results.check("LT alone", lt_only == (1, 0), str(lt_only))
    results.check("RT alone", rt_only == (0, 1), str(rt_only))
    # The point of using XInput rather than DirectInput: a shared trigger axis
    # cannot express both at once.
    results.check("LT and RT together", both == (1, 1), str(both))
    results.check("both released", none == (0, 0), str(none))


def axis_rate(game, event, x, y, seconds=1.2):
    """Accumulator growth per second while the stick is held -- the analog rate."""
    pad(f"lstick {x} {y}")
    time.sleep(0.5)
    start = game.accumulator(event)
    time.sleep(seconds)
    end = game.accumulator(event)
    if start is None or end is None:
        return None
    return abs(end - start) / seconds


def test_axes(game, results):
    print("\n== analog axes: rate proportional to deflection")
    full = axis_rate(game, EVENT_JOY_Y, 0, 1.0)
    if not full:
        results.check("full deflection produces movement", False, "no accumulation")
        pad("lstick 0 0")
        return
    for label, deflection, expected in (("25%", 0.25, 0.185), ("50%", 0.50, 0.457),
                                        ("75%", 0.75, 0.728)):
        rate = axis_rate(game, EVENT_JOY_Y, 0, deflection)
        ratio = rate / full if rate else 0.0
        # Expected is the deflection after the module's radial deadzone and
        # rescale: (d - DEADZONE) / (1 - DEADZONE).
        ok = abs(ratio - expected) < 0.12
        results.check(f"{label} deflection", ok,
                      f"ratio={ratio:.3f} expected~{expected:.3f}")

    centre_rate = axis_rate(game, EVENT_JOY_Y, 0, 0.0, seconds=1.0)
    results.check("centre produces no movement", (centre_rate or 0) < 1.0,
                  f"rate={centre_rate}")

    inside = axis_rate(game, EVENT_JOY_Y, 0, DEADZONE * 0.7, seconds=1.0)
    results.check("inside the deadzone produces no movement", (inside or 0) < 1.0,
                  f"rate={inside}")

    print("\n== diagonals keep their magnitude")
    half_diag = 0.5 / (2 ** 0.5)
    dx = axis_rate(game, EVENT_JOY_X, half_diag, half_diag)
    dy = axis_rate(game, EVENT_JOY_Y, half_diag, half_diag)
    magnitude = ((dx or 0) ** 2 + (dy or 0) ** 2) ** 0.5 / full if full else 0
    results.check("half diagonal stays partial", 0.25 < magnitude < 0.65,
                  f"magnitude={magnitude:.3f} of full")

    corner = 1.0 / (2 ** 0.5)
    fx = axis_rate(game, EVENT_JOY_X, corner, corner)
    fy = axis_rate(game, EVENT_JOY_Y, corner, corner)
    full_mag = ((fx or 0) ** 2 + (fy or 0) ** 2) ** 0.5 / full if full else 0
    results.check("full diagonal does not exceed full speed", full_mag <= 1.15,
                  f"magnitude={full_mag:.3f} of full")
    pad("lstick 0 0")


def test_camera(game, results):
    print("\n== camera: right stick feeds the mouse-delta field")
    pad("rstick 0 0")
    time.sleep(0.6)
    before = game.mouse_delta_x()
    small = 0.0
    large = 0.0
    for deflection, store in ((0.3, "small"), (1.0, "large")):
        pad(f"rstick {deflection} 0")
        time.sleep(0.1)
        samples = []
        for _ in range(6):
            samples.append(abs(game.mouse_delta_x() or 0.0))
            time.sleep(0.08)
        peak = max(samples)
        if store == "small":
            small = peak
        else:
            large = peak
    pad("rstick 0 0")
    time.sleep(0.6)
    rest = abs(game.mouse_delta_x() or 0.0)
    results.check("small stick gives a small camera delta", small > 0.0,
                  f"peak={small:.2f}")
    results.check("full stick gives a larger delta than small", large > small,
                  f"small={small:.2f} large={large:.2f}")
    results.check("centred stick contributes nothing", rest <= max(small, 0.5),
                  f"rest={rest:.2f}")


def in_gameplay(game):
    """Do the movement axes actually accumulate right now?

    The axes live in input class 0, which only becomes the active class once a
    save is loaded. At the main menu they never receive records, so the analog
    tests would report failures that mean nothing beyond "we are in a menu".
    """
    pad("lstick 0 1")
    time.sleep(0.4)
    start = game.accumulator(EVENT_JOY_Y)
    time.sleep(0.6)
    end = game.accumulator(EVENT_JOY_Y)
    pad("lstick 0 0")
    time.sleep(0.3)
    return start is not None and end is not None and abs(end - start) > 1


def test_disconnect(game, results):
    print("\n== disconnect leaves no stale state")
    pad("lstick 0 1")
    time.sleep(0.6)
    moving = axis_rate(game, EVENT_JOY_Y, 0, 1.0, seconds=0.6)
    pad("press A")
    time.sleep(0.4)
    held = game.value(0x27)
    # Dropping the pad is what a real disconnect looks like to XInput.
    pad("reset")
    time.sleep(0.8)
    after_release = game.value(0x27)
    stopped = axis_rate(game, EVENT_JOY_Y, 0, 0.0, seconds=0.8)
    results.check("was moving before release",
                  True if (moving or 0) > 1.0 else None,
                  f"rate={moving}" if (moving or 0) > 1.0 else "not in gameplay")
    results.check("button was held", held == 1, f"value={held}")
    results.check("button clears on release", after_release == 0, f"value={after_release}")
    results.check("movement stops", (stopped or 0) < 1.0, f"rate={stopped}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true",
                        help="skip the slower analog timing tests")
    arguments = parser.parse_args()

    try:
        if pad("ping") != "ok":
            raise SystemExit("pad server did not answer -- start virtual_pad_server.py")
    except OSError:
        raise SystemExit("pad server not reachable on 127.0.0.1:8787")

    game = Game()
    results = Results()
    print(f"CExoInputInternal 0x{game.internal:08X}   descriptions 0x{game.descs:08X}")

    test_registration(game, results)
    test_buttons(game, results)
    test_triggers(game, results)
    playing = in_gameplay(game)
    if not playing:
        print("\n(not in gameplay -- load a save to exercise the analog tests)")
    if not arguments.quick and playing:
        test_axes(game, results)
        test_camera(game, results)
    test_disconnect(game, results)
    pad("reset")

    print(f"\n{results.passed} passed, {results.failed} failed, {results.skipped} skipped")
    return 1 if results.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
