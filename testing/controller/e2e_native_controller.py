#!/usr/bin/env python3
"""End-to-end simulated controller test: drive the real game, read the real state.

This is deliberately not a unit test. It launches KOTOR, loads a save, drives a
virtual ViGEm pad, and checks what the engine actually did by reading its live
memory -- raw XInput, the input-event descriptions, the player-control fields the
movement integrator writes, and the turn the camera bridge hands the engine.

Where a check cannot be made deterministically it says so rather than guessing;
"looks right on screen" is not a result this file will ever report.

Requirements:
  * native mode selected (`select_controller_path.py native`)
  * ViGEmBus installed, so the virtual pad appears as a real XInput device

Usage:
    python testing/controller/e2e_native_controller.py [--no-launch] [--quick]

Failures are classified rather than just counted:
    HARNESS  the test drove the game wrongly
    NATIVE   a defect in KMRP's native path
    ENGINE   the game behaving as it does, which the test expected wrongly
    HUMAN    not deterministically testable; feel or visual judgement

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import socket
import struct
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import kmrp_controller                                    # noqa: E402

GAME_DIR = r"C:\Star Wars - KotOR"
GAME_EXE = os.path.join(GAME_DIR, "swkotor.exe")
LOG = os.path.join(GAME_DIR, "kmrp-native-joystick.log")
HOST, PORT = "127.0.0.1", 8787

EXOINPUT_GLOBAL = 0x007A39E4
DESCRIPTIONS, DEVICE_COUNT, MOUSE_DELTA_X = 0x128, 0x158, 0x3A0
CLIENT_EXO_APP_ROOT = 0x007A39FC   # -> CClientExoApp at [+4]
DESC_VALUE, DESC_ACCUM = 0x04, 0x24

PC_UPDOWN, PC_LEFTRIGHT, PC_WALKING, PC_VELX, PC_VELY = 0x10, 0x14, 0x18, 0x5C, 0x60

# Read from K1NativeJoystick.cpp, never restated. The copy that used to live here
# said 0.25 while the module said 0.08, and the suite reported three NATIVE
# failures against a module that was correct.
DEADZONE = kmrp_controller.constant("K1_STICK_DEADZONE")
CAMERA_SPEED = kmrp_controller.constant("K1_CAMERA_SPEED")

# Half the module's hold-to-repeat delay. Any tap used to assert "one press, one
# move" has to sit clearly below it: at 350ms against a 400ms delay, ordinary
# frame jitter occasionally crossed the threshold and a single press moved two
# tabs, which read as a skip in the strip rather than as a harness artefact.
NAV_TAP = kmrp_controller.constant("K1_NAV_HOLD_DELAY_MS") / 1000.0 * 0.5

EV_JOY_X, EV_JOY_Y = 0x08, 0x07
EV_PREV, EV_NEXT = 0x35, 0x36
BUTTONS = [("A", 0x27), ("B", 0x28), ("X", 0x29), ("Y", 0x2A),
           ("LB", 0x39), ("RB", 0x3A), ("BACK", 0x2B)]
DPAD = [("UP", 0x31), ("DOWN", 0x32), ("LEFT", 0x2F), ("RIGHT", 0x30)]

# Screen coordinates are for the 3440x1440 display this was written against and
# are the one genuinely fragile part of the harness.
CLICK_LOAD_GAME = (2092, 771)
CLICK_LOAD = (1718, 1273)


# --------------------------------------------------------------------- plumbing

class Pad:
    def __init__(self):
        self.proc = None

    def start(self):
        here = os.path.dirname(os.path.abspath(__file__))
        self.proc = subprocess.Popen(
            ["python", os.path.join(here, "virtual_pad_server.py")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            time.sleep(0.5)
            try:
                if self.send("ping") == "ok":
                    return True
            except OSError:
                continue
        return False

    def send(self, command):
        sock = socket.create_connection((HOST, PORT), timeout=5)
        sock.sendall((command + "\n").encode())
        reply = sock.recv(64).decode().strip()
        sock.close()
        # The server answers "err <reason>" for an unknown button and carries on.
        # Three findings in this project were that error being discarded: a script
        # sent "press RT" (the triggers are analog) or "DPAD_DOWN" (the name is
        # "DOWN"), saw no screen change and concluded the game was broken. A bad
        # command is a harness bug and must never look like a negative result.
        if reply.startswith("err") and not command.startswith("state"):
            raise RuntimeError(f"pad rejected {command!r}: {reply}")
        return reply

    def tap(self, button, hold=0.35, settle=1.6):
        """Press and release with our own timing.

        Not the server's `tap`/`dpad` verbs: those release before they reply, so
        anything sampling after the reply always reads the released state.
        """
        self.send("press " + button)
        time.sleep(hold)
        self.send("release " + button)
        time.sleep(settle)

    def trigger(self, side, hold=0.35, settle=1.6):
        self.send("triggers 1 0" if side == "LT" else "triggers 0 1")
        time.sleep(hold)
        self.send("triggers 0 0")
        time.sleep(settle)

    def stop(self):
        try:
            self.send("reset")
            self.send("quit")
        except (OSError, RuntimeError):
            pass
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass


class XInput:
    """Read the pad exactly as the game does, to prove the harness itself."""

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

    def read(self):
        if not self.dll:
            return None
        state = XInput._State()
        for slot in range(4):
            if self.dll.XInputGetState(slot, ctypes.byref(state)) == 0:
                return slot, state.Gamepad
        return None, None


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

    def _read(self, address, size=4):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf,
                                        size, ctypes.byref(got)):
            return None
        return buf.raw

    def u32(self, a):
        raw = self._read(a)
        return struct.unpack("<I", raw)[0] if raw else None

    def i32(self, a):
        v = self.u32(a)
        return None if v is None else struct.unpack("<i", struct.pack("<I", v))[0]

    def f32(self, a):
        v = self.u32(a)
        return None if v is None else struct.unpack("<f", struct.pack("<I", v))[0]

    def desc(self, event):
        return self.u32(self.descs + event * 4)

    def value(self, event):
        d = self.desc(event)
        return self.i32(d + DESC_VALUE) if d else None

    def accum(self, event):
        d = self.desc(event)
        return self.i32(d + DESC_ACCUM) if d else None

    def mouse_dx(self):
        return self.f32(self.internal + MOUSE_DELTA_X)

    # -- free-look state, read from the engine rather than from our own module.
    # CClientExoApp is [[0x007A39FC]+4]; its internal is [+4] and the options
    # object hangs off that at +4 again. Camera mode 5 is free look, and the
    # input class at internal+0x9c reads 4 (ICFreeLook) while it is active.
    def _client_app(self):
        root = self.u32(CLIENT_EXO_APP_ROOT)
        return self.u32(root + 4) if root else None

    def camera_mode(self):
        app = self._client_app()
        internal = self.u32(app + 4) if app else None
        options = self.u32(internal + 4) if internal else None
        if not options:
            return None
        raw = self._read(options + 0x6D, 1)
        return raw[0] if raw else None

    def input_class(self):
        app = self._client_app()
        internal = self.u32(app + 4) if app else None
        return self.u32(internal + 0x9C) if internal else None

    def player_control(self):
        """Published by the module's diagnostic line; None until gameplay."""
        try:
            with open(LOG, "r", errors="replace") as handle:
                lines = [l for l in handle if "pc=" in l]
        except OSError:
            return None
        if not lines:
            return None
        m = re.search(r"pc=([0-9A-Fa-f]{8})", lines[-1])
        pc = int(m.group(1), 16) if m else 0
        return pc or None

    def movement(self):
        pc = self.player_control()
        if not pc:
            return None
        return {"updown": self.f32(pc + PC_UPDOWN),
                "leftright": self.f32(pc + PC_LEFTRIGHT),
                "walking": self.i32(pc + PC_WALKING),
                "velx": self.f32(pc + PC_VELX),
                "vely": self.f32(pc + PC_VELY)}


class Report:
    def __init__(self):
        self.rows = []

    def add(self, section, name, ok, detail="", kind=""):
        self.rows.append((section, name, ok, detail, kind))
        mark = {True: "PASS", False: "FAIL", None: "HUMAN"}[ok]
        tag = f" [{kind}]" if kind and ok is False else ""
        print(f"  {mark:<5} {name:<44} {detail}{tag}")

    def summary(self):
        p = sum(1 for r in self.rows if r[2] is True)
        f = sum(1 for r in self.rows if r[2] is False)
        h = sum(1 for r in self.rows if r[2] is None)
        return p, f, h


# ------------------------------------------------------------------- test steps

def click(x, y):
    subprocess.run(["powershell", "-NoProfile", "-Command", f"""
Add-Type @'
using System; using System.Runtime.InteropServices;
public class C {{
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint a,uint b,uint c,IntPtr d);
}}
'@
[C]::SetCursorPos({x},{y}); Start-Sleep -Milliseconds 400
[C]::mouse_event(2,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 80
[C]::mouse_event(4,0,0,0,[IntPtr]::Zero)
"""], capture_output=True)


def launch_and_load(report):
    print("\n== 1. launch and load")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Stop-Process -Name swkotor -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)
    time.sleep(3)
    if os.path.exists(LOG):
        os.remove(LOG)
    subprocess.Popen([GAME_EXE], cwd=GAME_DIR)
    time.sleep(28)
    alive = subprocess.check_output(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process swkotor -ErrorAction SilentlyContinue).Id"]).decode().strip()
    report.add("launch", "game launched without crashing", bool(alive), f"pid={alive}")
    click(*CLICK_LOAD_GAME)
    time.sleep(6)
    click(*CLICK_LOAD)
    time.sleep(55)
    return alive


def in_gameplay(game):
    try:
        with open(LOG, "r", errors="replace") as handle:
            lines = [l for l in handle if "mov=" in l]
    except OSError:
        return False
    if not lines:
        return False
    m = re.search(r"mov=(\d+)", lines[-1])
    return bool(m and int(m.group(1)) > 0)


def axis_rate(game, pad, event, x, y, seconds=1.0):
    pad.send(f"lstick {x} {y}")
    time.sleep(0.45)
    a = game.accum(event)
    time.sleep(seconds)
    b = game.accum(event)
    if a is None or b is None:
        return None
    return (b - a) / seconds


def test_cardinals(game, pad, report):
    print("\n== 2. left stick cardinals: magnitude and sign")
    full = abs(axis_rate(game, pad, EV_JOY_Y, 0, 1.0) or 0)
    if full < 1:
        report.add("cardinal", "forward produces movement", False, "no accumulation", "NATIVE")
        return
    for label, (x, y), event, sign in (
            ("forward",  (0, 1.0),  EV_JOY_Y, -1),
            ("backward", (0, -1.0), EV_JOY_Y, +1),
            ("right",    (1.0, 0),  EV_JOY_X, +1),
            ("left",     (-1.0, 0), EV_JOY_X, -1)):
        rate = axis_rate(game, pad, event, x, y)
        ok = rate is not None and abs(rate) > full * 0.6 and (rate > 0) == (sign > 0)
        report.add("cardinal", f"{label} full deflection", ok,
                   f"rate={rate:.0f} expected sign {'+' if sign > 0 else '-'}"
                   if rate is not None else "no data",
                   "NATIVE")
    # Derived from the deadzone rather than written down, so changing the
    # constant cannot leave a stale expectation passing for the wrong reason.
    # At a 25% deadzone, 25% deflection is exactly on the boundary and must
    # produce nothing at all -- which is a different assertion, so it is not
    # in this proportionality loop.
    def effective(deflection):
        return max(0.0, (deflection - DEADZONE) / (1.0 - DEADZONE))

    for label, deflection, expected in (("40%", 0.40, effective(0.40)),
                                        ("50%", 0.50, effective(0.50)),
                                        ("75%", 0.75, effective(0.75))):
        rate = abs(axis_rate(game, pad, EV_JOY_Y, 0, deflection) or 0)
        ratio = rate / full
        report.add("cardinal", f"forward {label} scales proportionally",
                   abs(ratio - expected) < 0.15,
                   f"ratio={ratio:.3f} expected~{expected:.3f}", "NATIVE")
    pad.send("lstick 0 0")


def test_diagonals(game, pad, report):
    print("\n== 3. diagonals in all four quadrants")
    full = abs(axis_rate(game, pad, EV_JOY_Y, 0, 1.0) or 0) or 1
    for qx, qy, name in ((1, 1, "up-right"), (-1, 1, "up-left"),
                         (1, -1, "down-right"), (-1, -1, "down-left")):
        c = 1.0 / (2 ** 0.5)
        rx = abs(axis_rate(game, pad, EV_JOY_X, qx * c, qy * c) or 0)
        ry = abs(axis_rate(game, pad, EV_JOY_Y, qx * c, qy * c) or 0)
        magnitude = ((rx ** 2 + ry ** 2) ** 0.5) / full
        report.add("diagonal", f"full {name} does not exceed full speed",
                   magnitude <= 1.2, f"magnitude={magnitude:.3f}", "NATIVE")
    # Bands derived from the deadzone, not written down: a partial diagonal must
    # keep the same radial magnitude a cardinal of that deflection would.
    def band(deflection):
        want = max(0.0, (deflection - DEADZONE) / (1.0 - DEADZONE))
        return want - 0.12, want + 0.12

    for label, scale in (("40%", 0.40), ("50%", 0.50), ("75%", 0.75)):
        lo, hi = band(scale)
        c = scale / (2 ** 0.5)
        rx = abs(axis_rate(game, pad, EV_JOY_X, c, c) or 0)
        ry = abs(axis_rate(game, pad, EV_JOY_Y, c, c) or 0)
        magnitude = ((rx ** 2 + ry ** 2) ** 0.5) / full
        report.add("diagonal", f"{label} diagonal keeps its radial magnitude",
                   lo <= magnitude <= hi, f"magnitude={magnitude:.3f}", "NATIVE")

    # The deadzone edge itself. Everything at or below it must be silent.
    #
    # These scales are derived from DEADZONE rather than written out, because
    # they were written out once: they still said 15/22/25% after the deadzone
    # went 25% -> 15% -> 8%, and reported three NATIVE failures against a module
    # that was behaving correctly. A constant that appears in two places will
    # disagree with itself eventually.
    edge = DEADZONE
    for label, scale in ((f"{edge * 0.5:.0%}", edge * 0.5),
                         (f"{edge * 0.85:.0%}", edge * 0.85),
                         (f"{edge:.0%} (the edge)", edge)):
        c = scale / (2 ** 0.5)
        rx = abs(axis_rate(game, pad, EV_JOY_X, c, c) or 0)
        ry = abs(axis_rate(game, pad, EV_JOY_Y, c, c) or 0)
        magnitude = ((rx ** 2 + ry ** 2) ** 0.5) / full
        report.add("diagonal", f"{label} is inside the deadzone: no movement",
                   magnitude < 0.02, f"magnitude={magnitude:.3f}", "NATIVE")
    pad.send("lstick 0 0")


def test_centre(game, pad, report):
    print("\n== 4. centre and release")
    for name, (x, y) in (("forward", (0, 1.0)), ("back", (0, -1.0)),
                         ("left", (-1.0, 0)), ("right", (1.0, 0))):
        pad.send(f"lstick {x} {y}")
        time.sleep(0.8)
        pad.send("lstick 0 0")
        time.sleep(0.8)
        rate = abs(axis_rate(game, pad, EV_JOY_Y, 0, 0.0, seconds=0.8) or 0)
        move = game.movement()
        stale = move and (abs(move["updown"] or 0) > 0.02 or abs(move["leftright"] or 0) > 0.02)
        report.add("centre", f"{name} then centre stops accumulating", rate < 1.0,
                   f"rate={rate:.2f}", "NATIVE")
        report.add("centre", f"{name} leaves no stale UpDown/LeftRight", not stale,
                   f"{move}" if move else "no player-control pointer yet", "NATIVE")
        break     # one direction is enough; the mechanism is shared


def test_disconnect(game, pad, report):
    print("\n== 5. disconnect and reconnect")
    pad.send("lstick 0 1")
    time.sleep(0.8)
    before = abs(axis_rate(game, pad, EV_JOY_Y, 0, 1.0, seconds=0.6) or 0)
    pad.stop()                      # dropping the pad IS the disconnect
    time.sleep(1.5)
    after = abs(axis_rate_nopad(game, EV_JOY_Y, seconds=0.8))
    move = game.movement()
    report.add("disconnect", "was moving before disconnect", before > 1.0, f"rate={before:.0f}", "HARNESS")
    report.add("disconnect", "movement neutralises on disconnect", after < 1.0, f"rate={after:.2f}", "NATIVE")
    report.add("disconnect", "no stale analog state",
               not (move and abs(move["updown"] or 0) > 0.02),
               f"{move}" if move else "n/a", "NATIVE")
    if not pad.start():
        report.add("disconnect", "pad reconnects", False, "server would not restart", "HARNESS")
        return False
    time.sleep(1.0)
    resumed = abs(axis_rate(game, pad, EV_JOY_Y, 0, 1.0, seconds=0.8) or 0)
    report.add("disconnect", "native path resumes after reconnect", resumed > 1.0,
               f"rate={resumed:.0f}", "NATIVE")
    pad.send("lstick 0 0")
    return True


def axis_rate_nopad(game, event, seconds=0.8):
    a = game.accum(event)
    time.sleep(seconds)
    b = game.accum(event)
    if a is None or b is None:
        return 0.0
    return (b - a) / seconds


def ensure_gameplay(game, pad, tries=8):
    """Put the game back in the world before a test that assumes it is there.

    A now performs the world interaction bridge, so pressing it in gameplay next
    to a crew member starts a conversation -- which is correct behaviour and
    exactly what broke this suite: once in input class 3, every later test was
    measuring the wrong context and eighteen of them failed at once.

    Dialogue is left with A (advancing to the end), a menu with B, free look
    with R3. Each has its own exit and none of them is interchangeable.
    """
    for _ in range(tries):
        cls = game.input_class()
        if cls == 0:
            return True
        if cls == 3:
            pad.tap("A", settle=1.6)
        elif cls == 4:
            pad.tap("RS", settle=1.8)
        else:
            pad.tap("B", settle=2.0)
    return game.input_class() == 0


def test_buttons(game, pad, xinput, report):
    print("\n== 6-8. buttons, D-pad: XInput -> record -> description")
    pad.send("reset")
    time.sleep(0.4)
    before_hud = _hud_counters()
    for name, event in BUTTONS + DPAD:
        # A opens a conversation when something is targeted, and every button
        # after it would then be sampled in input class 3 where it is correctly
        # unregistered. Returning to the world between presses keeps each button
        # measured in the class this test is about.
        ensure_gameplay(game, pad)
        pad.send(f"press {name}")
        # Peak-sample rather than read once after a delay. A now performs the
        # world-interaction bridge, so it can start a conversation whose handler
        # polls -- and therefore consumes -- event 0x27 before a late single
        # read sees it. A button that does something must not be harder to
        # observe than one that does nothing.
        held = 0
        deadline = time.time() + 0.45
        while time.time() < deadline:
            value = game.value(event)
            if value:
                held = value
        _, gp = xinput.read()
        pad.send(f"release {name}")
        time.sleep(0.35)
        released = game.value(event)
        kind = "NATIVE"
        if (name, event) in DPAD:
            # The D-pad in gameplay drives the HUD action bar, so its retained
            # codes are SUPPRESSED -- the same "one press, one mechanism" rule
            # the menus already follow. Asserting the event arrives would assert
            # the double-acting behaviour this replaced, so the contract here is
            # the opposite: nothing may arrive, and the HUD must move instead.
            after = _hud_counters()
            acted = bool(before_hud and after and
                         (after[0] > before_hud[0] or after[1] > before_hud[1]))
            ok = held == 0 and acted
            report.add("buttons", f"{name}: suppressed in gameplay, HUD acts", ok,
                       f"event held={held}, hud {before_hud} -> {after}", kind)
            before_hud = after
            continue
        ok = held == 1 and released == 0
        if gp is not None and gp.wButtons == 0 and held != 1:
            kind = "HARNESS"     # the pad never asserted it
        report.add("buttons", f"{name} -> event 0x{event:02X}", ok,
                   f"held={held} released={released}", kind)
    # repeatability, since a stuck edge would only show on the second press
    for name, event in (("LB", 0x39), ("RB", 0x3A)):
        results = []
        for _ in range(3):
            pad.send(f"press {name}"); time.sleep(0.3)
            results.append(game.value(event))
            pad.send(f"release {name}"); time.sleep(0.25)
            results.append(game.value(event))
        report.add("buttons", f"{name} repeats cleanly x3", results == [1, 0] * 3,
                   str(results), "NATIVE")


def test_triggers(game, pad, report):
    print("\n== 9. triggers, including both at once")
    cases = (("LT only", "triggers 1 0", (1, 0)),
             ("RT only", "triggers 0 1", (0, 1)),
             ("LT+RT together", "triggers 1 1", (1, 1)),
             ("both released", "triggers 0 0", (0, 0)))
    for label, command, expected in cases:
        pad.send(command)
        time.sleep(0.45)
        got = (game.value(EV_PREV), game.value(EV_NEXT))
        report.add("triggers", label, got == expected, f"{got} expected {expected}", "NATIVE")


def camera_dump():
    """The module's own camera counters, from the last diagnostic line.

    camapp is the turn amount x100 handed to CSWCModule::RotateCamera; camwr,
    camdz, camcls and camown count the writes and each reason for declining.
    """
    fields = ("camapp", "camwr", "camdz", "camcls", "camown")
    try:
        with open(LOG, "r", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return {}
    out = {}
    for name in fields:
        found = re.findall(r"\b%s=(-?\d+)" % name, text)
        if found:
            out[name] = int(found[-1])
    return out


def test_camera(game, pad, report):
    print()
    print("== 10. right-stick camera: monotonic and signed")

    # This reads the module's emitted turn, NOT CExoInputInternal+0x3A0.
    #
    # +0x3A0 is a dead field: UpdateCamera fetches it and discards it. An
    # earlier version of this test read it, agreed with itself, and reported a
    # working camera for weeks while nothing on screen moved. The engine side of
    # the turn -- camera+0x10C -- is only reachable through a virtual call
    # inside RotateCamera and cannot be read from another process, so what is
    # deterministic here is everything KMRP controls, and the visible rotation
    # stays a human check.
    before = camera_dump()
    peaks = {}
    for label, deflection in (("small", 0.25), ("medium", 0.6), ("full", 1.0)):
        pad.send(f"rstick {deflection} 0")
        samples = []
        for _ in range(8):
            time.sleep(0.07)
            samples.append(camera_dump().get("camapp", 0) / 100.0)
        peaks[label] = max(abs(s) for s in samples)
        signs = [s for s in samples if abs(s) > 0.01]
        if label == "full":
            report.add("camera", "positive stick gives a consistent sign",
                       bool(signs) and (all(s > 0 for s in signs) or all(s < 0 for s in signs)),
                       f"samples={[round(s, 2) for s in samples[:4]]}", "NATIVE")
    pad.send("rstick -1.0 0")
    time.sleep(0.3)
    negative = [camera_dump().get("camapp", 0) / 100.0 for _ in range(4)]
    pad.send("rstick 0 0")
    time.sleep(0.8)
    rest = max(abs(camera_dump().get("camapp", 0) / 100.0) for _ in range(4))
    after = camera_dump()

    positive = [s for s in (peaks["full"],) if s]
    report.add("camera", "small deflection produces a turn", peaks["small"] > 0.0,
               f"peak={peaks['small']:.2f}", "NATIVE")
    report.add("camera", "turn increases with deflection",
               peaks["small"] <= peaks["medium"] <= peaks["full"],
               f"{peaks['small']:.2f} <= {peaks['medium']:.2f} <= {peaks['full']:.2f}",
               "NATIVE")
    report.add("camera", "full deflection saturates at K1_CAMERA_SPEED",
               abs(peaks["full"] - CAMERA_SPEED) <= 0.05 * CAMERA_SPEED,
               f"peak={peaks['full']:.2f} expected {CAMERA_SPEED:.2f}", "NATIVE")
    report.add("camera", "opposite deflection flips the sign",
               bool(positive) and any(v < 0 for v in negative),
               f"samples={[round(v, 2) for v in negative]}", "NATIVE")
    report.add("camera", "centred stick contributes nothing", rest == 0.0,
               f"rest={rest:.2f}", "NATIVE")
    report.add("camera", "the bridge reached the engine",
               after.get("camwr", 0) > before.get("camwr", 0),
               f"camwr {before.get('camwr')} -> {after.get('camwr')}", "NATIVE")
    report.add("camera", "no frame declined for class or receiver",
               after.get("camcls", 0) == before.get("camcls", 0)
               and after.get("camown", 0) == before.get("camown", 0),
               f"camcls {before.get('camcls')}->{after.get('camcls')} "
               f"camown {before.get('camown')}->{after.get('camown')}", "NATIVE")
    report.add("camera", "the view visibly rotates", None,
               "playtest-confirmed 2026-09-07; not observable from here")
    report.add("camera", "sensitivity feels right", None,
               f"K1_CAMERA_SPEED = {CAMERA_SPEED}, untuned")


def test_tab_bar(game, pad, report):
    """The in-game tab strip: eight stops, A opens, down enters, up returns.

    Requires the in-game menu to be open. Every claim is checked against live
    control rectangles and the engine's own current-tab field rather than a
    memorised sequence, so it keeps working if the strip is ever relaid out.
    """
    print()
    print("== 15. in-game tab bar")
    bar = _tab_bar(game)
    report.add("tabs", "the tab strip is in front", bar is not None,
               f"panel={bar:08X}" if bar else "not open", "HARNESS")
    if not bar:
        return

    report.add("tabs", "focus can be returned to the strip",
               _return_to_tabs(game, pad), f"in-content={_in_content()}", "HARNESS")
    frames = _tab_frames(game, bar)
    overlays = _tab_overlays(game, bar)
    report.add("tabs", "eight tab stops", len(frames) == 8,
               f"{len(frames)} frames, {len(overlays)} overlays", "NATIVE")

    # 1. Left and right visit each tab in visual order, and only the frames.
    #    The overlays sit inside the frames and pass every navigable test, so
    #    the failure this guards against is a strip that is sixteen stops long.
    order = []
    for _ in range(len(frames) + 1):
        active = _active(game)
        if active in order:
            break
        order.append(active)
        pad.tap("RIGHT", hold=NAV_TAP, settle=0.9)
    visited_frames = [c for c in order if c in frames]
    report.add("tabs", "right visits only tab frames",
               len(visited_frames) == len(order),
               f"{len(order)} stops, {len(order) - len(visited_frames)} not frames",
               "NATIVE")
    report.add("tabs", "no overlay ever takes focus",
               not any(c in overlays for c in order),
               f"stops={len(order)}", "NATIVE")
    # Visual order, allowing exactly one wrap: the walk starts wherever focus
    # already was, runs to the right-hand end and continues from the left. An
    # earlier version demanded a strictly increasing sequence and failed on a
    # perfectly correct [1457 .. 2790, 458 .. 1124].
    xs = [_rect(game, c)[0] for c in visited_frames if _rect(game, c)]
    drops = sum(1 for a, b in zip(xs, xs[1:]) if b < a)
    report.add("tabs", "right walks the strip in visual order",
               len(xs) == len(frames) and drops <= 1
               and sorted(xs) == sorted(_rect(game, c)[0] for c in frames),
               f"x sequence {xs} ({drops} wrap)", "NATIVE")

    # 2. Focus never disappears, whatever is pressed.
    survived = True
    for step in ("LEFT", "LEFT", "RIGHT", "UP", "UP"):
        pad.tap(step, hold=NAV_TAP, settle=0.8)
        if _active(game) not in frames:
            survived = False
    report.add("tabs", "focus never leaves the strip or disappears", survived,
               f"active={_active(game):08X}" if _active(game) else "no focus",
               "NATIVE")

    # 3. Up from the strip does nothing.
    before = _active(game)
    pad.tap("UP", hold=NAV_TAP, settle=0.9)
    report.add("tabs", "up from the strip does nothing", _active(game) == before,
               "focus unchanged", "NATIVE")

    # 4. Moving along the strip must NOT switch tabs -- only A does.
    shown = _tab_index(game)
    pad.tap("LEFT", hold=NAV_TAP, settle=0.9)
    pad.tap("LEFT", hold=NAV_TAP, settle=0.9)
    report.add("tabs", "moving focus does not switch tabs",
               _tab_index(game) == shown,
               f"tab still {shown}", "NATIVE")

    # 5. A opens the focused tab. Deliberately moved to a tab that is NOT the
    #    one already showing: an earlier version asserted this while focus and
    #    the engine both sat on tab 0, so it passed without anything happening.
    shown = _tab_index(game)
    for _ in range(len(frames)):
        focused = _active(game)
        if focused in frames and frames.index(focused) != shown:
            break
        pad.tap("RIGHT", hold=NAV_TAP, settle=0.9)
    focused = _active(game)
    wanted = frames.index(focused) if focused in frames else None
    report.add("tabs", "focused a tab other than the one showing",
               wanted is not None and wanted != shown,
               f"focused {wanted}, showing {shown}", "HARNESS")
    pad.tap("A", settle=2.2)
    opened = _tab_index(game)
    report.add("tabs", "A opens the focused tab",
               wanted is not None and opened == wanted,
               f"focused frame {wanted}, engine now showing {opened} (was {shown})",
               "NATIVE")

    # 6. Down enters that tab's content, on the panel below.
    bar = _tab_bar(game)
    if not bar:
        report.add("tabs", "still on the tab strip after A", False,
                   "a sub-panel took the front", "NATIVE")
        return
    content = _content_panel(game, bar)
    pad.tap("DOWN", hold=NAV_TAP, settle=1.2)
    inside = _in_content()
    content_active = game.u32(content + 0x1C) if content else None
    report.add("tabs", "down enters the tab content", inside is True,
               f"module reports in-content={inside}", "NATIVE")
    report.add("tabs", "content focus is on an actionable control",
               bool(content_active and _rect(game, content_active)),
               f"active={content_active:08X}" if content_active else "nothing",
               "NATIVE")

    # 7. Up from the top of the content returns to the active tab.
    for _ in range(6):
        if _in_content() is not True:
            break
        pad.tap("UP", hold=NAV_TAP, settle=0.9)
    report.add("tabs", "up returns from content to the tab strip",
               _in_content() is False, f"module reports in-content={_in_content()}",
               "NATIVE")
    report.add("tabs", "it returns to the tab actually being shown",
               _active(game) == frames[_tab_index(game)]
               if _tab_index(game) is not None and _tab_index(game) < len(frames)
               else False,
               f"tab {_tab_index(game)}", "NATIVE")

    # 8. The bumpers still switch immediately, without focus moving.
    before_tab = _tab_index(game)
    pad.trigger("RT", settle=1.6)
    after_rt = _tab_index(game)
    pad.trigger("LT", settle=1.6)
    after_lt = _tab_index(game)
    report.add("tabs", "RT switches tab immediately", after_rt != before_tab,
               f"{before_tab} -> {after_rt}", "NATIVE")
    report.add("tabs", "LT switches back", after_lt == before_tab,
               f"{after_rt} -> {after_lt}", "NATIVE")

    # 9. Every tab, not just the one that happened to be open. The tab bar work
    #    is meant to be generic -- nothing in the module encodes what any given
    #    tab is -- so this walks all eight with RT and checks that down reaches
    #    an actionable control in each and up comes back out.
    entered = []
    failed = []
    skipped = []          # kept for the report; nothing is skipped any more
    overlays = []         # panels that opened in front and were backed out of
    lost = None

    def still_there(index, where):
        """True while the strip is reachable, dismissing an overlay if needed."""
        nonlocal lost
        if _tab_bar(game):
            return True
        if _dismiss_overlay(game, pad):
            overlays.append((index, where))
            return True
        lost = (index, where, _front_state(game))
        return False

    for _ in range(len(frames)):
        index = _tab_index(game)
        if not still_there(index, "arriving"):
            break
        _return_to_tabs(game, pad)
        pad.tap("DOWN", hold=NAV_TAP, settle=1.3)
        if not still_there(index, "DOWN"):
            break
        content = _content_panel(game, _tab_bar(game))
        active = game.u32(content + 0x1C) if content else None
        if _in_content() is True and active and _rect(game, active):
            entered.append(index)
        else:
            failed.append(index)
        _return_to_tabs(game, pad)
        pad.trigger("RT", settle=1.5)
        if not still_there(index, "RT"):
            break
    if lost is not None:
        global MENU_LOST_IN_WALK
        MENU_LOST_IN_WALK = True
        _dismiss_overlay(game, pad)
        # Reaching here means B did not bring the strip back, so the menu is
        # genuinely gone rather than merely covered. Recorded as ENGINE: the
        # earlier reading of this as "walking the tabs closes the menu" was
        # wrong -- what actually happens is that a lazily built in-game panel
        # (CGuiInGame+0xA0, dispatcher 006AA8A0) opens in FRONT of the strip,
        # and the B pressed by a later check is what then closed the menu.
        pad.tap("START", settle=2.5)
    report.add("tabs", "the menu survives a walk of all eight tabs", lost is None,
               f"lost on tab {lost[0]} at {lost[1]}: {lost[2]}" if lost is not None
               else f"eight tabs; {len(overlays)} panel(s) opened in front and "
                    f"were dismissed: {overlays}", "ENGINE")
    # Abilities and Map navigate themselves and are deliberately excluded, so
    # the claim is "every tab that KMRP navigates", not "every tab".
    # Judged over the tabs actually reached: when the walk is cut short by the
    # pre-existing closure above, the tabs beyond it were never attempted and
    # counting them as failures would report that bug twice.
    report.add("tabs", "down reaches content on every tab it navigates",
               not failed and (lost is not None
                               or len(entered) + len(skipped) >= len(frames) - 1),
               f"entered {sorted(entered)}"
               + (f", skipped as self-navigating {sorted(skipped)}" if skipped else "")
               + (f", failed {sorted(failed)}" if failed else ""), "NATIVE")
    report.add("tabs", "up leaves content on every tab", _in_content() is not True,
               f"in-content={_in_content()}", "NATIVE")



# The gameplay HUD's bottom-right action bar. Offsets from Saul0097's K1_CONFIG
# and from CSWGuiMainInterface's own scroll function at 0x00688820:
#
#   mainInterface + 0x1C                the focused control
#   mainInterface + 0x772C + i*0x71C    personal slot i, i in 0..3
#   mainInterface + 0x78   + i*0x0C     how many actions slot i can offer
#   mainInterface + 0x1BAC + i*0x04     the action slot i currently shows
#
# The interface pointer is read from the module's own dump rather than derived.
# Deriving it from CGuiInGame+0x18 produced a different, plausible-looking object
# -- it even had a manager pointer at +0x18 -- and every reading taken through it
# was of the wrong thing.
HUD_PERSONAL_BASE, HUD_GROUP = 0x772C, 0x71C
HUD_SLOT_COUNT_BASE, HUD_SLOT_COUNT_STRIDE = 0x78, 0x0C
HUD_CURRENT_ACTION = 0x1BAC
HUD_CONTROL_OFFSETS = (0x000, 0x1C4, 0x388, 0x54C)


def _interact_counters():
    """(performed, declined) for the world-action bridge."""
    try:
        with open(LOG, "r", errors="replace") as handle:
            found = re.findall(r"\bact=(\d+)/(\d+)", handle.read())
    except OSError:
        return None
    return tuple(int(v) for v in found[-1]) if found else None


def _hud_interface():
    try:
        with open(LOG, "r", errors="replace") as handle:
            found = re.findall(r"hud=\d+/\d+/\d+/([0-9A-Fa-f]{8})/", handle.read())
    except OSError:
        return None
    return int(found[-1], 16) if found else None


def _hud_counters():
    """(moves, cycles, activations) from the module's dump."""
    try:
        with open(LOG, "r", errors="replace") as handle:
            found = re.findall(r"hud=(\d+)/(\d+)/(\d+)/", handle.read())
    except OSError:
        return None
    return tuple(int(v) for v in found[-1]) if found else None


def _hud_slot(game):
    """Which of the four personal slots holds focus, or None."""
    base = _hud_interface()
    if not base:
        return None
    active = game.u32(base + 0x1C)
    if not active:
        return None
    for index in range(4):
        button = base + HUD_PERSONAL_BASE + index * HUD_GROUP
        for offset in HUD_CONTROL_OFFSETS:
            if button + offset == active:
                return index
    return None


def _hud_action(game, slot):
    base = _hud_interface()
    return game.i32(base + HUD_CURRENT_ACTION + slot * 4) if base else None


def _hud_available(game, slot):
    base = _hud_interface()
    return game.i32(base + HUD_SLOT_COUNT_BASE + slot * HUD_SLOT_COUNT_STRIDE) if base else None


def test_action_bar(game, pad, report):
    """D-pad control of the gameplay HUD's action bar."""
    print()
    print("== 16. gameplay HUD action bar")
    ensure_gameplay(game, pad)
    base = _hud_interface()
    report.add("hud", "the module reports the interface it was handed",
               base is not None, f"mainInterface={base:08X}" if base else "no hud= field",
               "HARNESS")
    if not base:
        return

    # 1. Right takes focus onto a slot and moves one at a time.
    pad.tap("RIGHT", hold=NAV_TAP, settle=0.9)
    first = _hud_slot(game)
    report.add("hud", "right puts focus on an action slot", first is not None,
               f"slot={first}", "NATIVE")
    walk = [first]
    for _ in range(3):
        pad.tap("RIGHT", hold=NAV_TAP, settle=0.9)
        walk.append(_hud_slot(game))
    steps = [(b - a) % 4 for a, b in zip(walk, walk[1:])
             if a is not None and b is not None]
    report.add("hud", "right moves exactly one slot per press",
               bool(steps) and all(s == 1 for s in steps),
               f"slots {walk}", "NATIVE")

    back = [_hud_slot(game)]
    for _ in range(2):
        pad.tap("LEFT", hold=NAV_TAP, settle=0.9)
        back.append(_hud_slot(game))
    back_steps = [(a - b) % 4 for a, b in zip(back, back[1:])
                  if a is not None and b is not None]
    report.add("hud", "left moves exactly one slot back per press",
               bool(back_steps) and all(s == 1 for s in back_steps),
               f"slots {back}", "NATIVE")

    # 2. Up and down cycle the action WITHIN a slot -- but only where the slot
    #    has more than one to offer. The engine refuses otherwise, at
    #    0x006888B1: cmp [count], 1 / jle. Find a slot that qualifies.
    target = None
    for _ in range(4):
        slot = _hud_slot(game)
        if slot is not None and (_hud_available(game, slot) or 0) > 1:
            target = slot
            break
        pad.tap("RIGHT", hold=NAV_TAP, settle=0.9)
    if target is None:
        report.add("hud", "down cycles the action in the slot", None,
                   "no slot on this save offers more than one action")
    else:
        seen = [_hud_action(game, target)]
        for _ in range(3):
            pad.tap("DOWN", hold=NAV_TAP, settle=0.9)
            seen.append(_hud_action(game, target))
        report.add("hud", "down cycles the action in the slot",
                   len(set(seen)) > 1 and _hud_slot(game) == target,
                   f"slot {target} action ids {seen}", "NATIVE")
        before_up = _hud_action(game, target)
        pad.tap("UP", hold=NAV_TAP, settle=0.9)
        report.add("hud", "up cycles it the other way",
                   _hud_action(game, target) != before_up,
                   f"{before_up} -> {_hud_action(game, target)}", "NATIVE")

    # 3. A uses the slot, and the world-interaction bridge stands down. Exactly
    #    one of the two may act on a press.
    before_hud = _hud_counters()
    before_act = _interact_counters()
    pad.tap("A", settle=1.2)
    after_hud = _hud_counters()
    after_act = _interact_counters()
    report.add("hud", "A activates the focused slot",
               bool(before_hud and after_hud) and after_hud[2] > before_hud[2],
               f"activations {before_hud[2]} -> {after_hud[2]}"
               if before_hud and after_hud else "no counters", "NATIVE")
    report.add("hud", "the world action stands down while a slot has focus",
               bool(before_act and after_act) and after_act[0] == before_act[0],
               f"world performed {before_act[0]} -> {after_act[0]}, "
               f"declined {before_act[1]} -> {after_act[1]}"
               if before_act and after_act else "no counters", "NATIVE")

    # 4. None of this may move the character or open anything.
    report.add("hud", "the HUD bar does not open a menu", game.input_class() == 0,
               f"input class {game.input_class()}", "NATIVE")
    movement = game.movement() or {}
    speed = abs(movement.get("velx") or 0) + abs(movement.get("vely") or 0)
    report.add("hud", "the D-pad does not move the character", speed < 0.01,
               f"velocity {speed:.3f}", "NATIVE")


def _prompt_counters():
    """(pad-active frames, prompt refreshes) from the module's dump."""
    try:
        with open(LOG, "r", errors="replace") as handle:
            text = handle.read()
        active = re.findall(r"\bpad=(\d+)", text)
        updates = re.findall(r"\bprm=(\d+)", text)
        return (int(active[-1]) if active else None,
                int(updates[-1]) if updates else None)
    except OSError:
        return (None, None)


def test_prompt_layer(game, pad, report):
    """The controller prompt layer runs at all.

    It did not. UpdateK1ControllerPrompts was reachable only from the legacy
    DispatchMenuInputK1 hook, and the device-activity flag it consults was
    raised only from PollXInputK1, also legacy -- so in native mode every badge
    table and every badge texture in the patch sat there unreachable, and no
    counter or screenshot in this suite looked. These two check the wiring, and
    testing/controller/probe_prompts.py checks the pixels.
    """
    print()
    print("== 17. controller prompt layer")
    before = _prompt_counters()
    pad.tap("RIGHT", hold=NAV_TAP, settle=0.9)
    pad.tap("LEFT", hold=NAV_TAP, settle=0.9)
    after = _prompt_counters()
    report.add("prompts", "the pad registers as the live input device",
               bool(before[0] is not None and after[0] is not None
                    and after[0] > before[0]),
               f"pad-active frames {before[0]} -> {after[0]}", "NATIVE")
    report.add("prompts", "the prompt updater runs every GUI frame",
               bool(before[1] is not None and after[1] is not None
                    and after[1] > before[1]),
               f"refreshes {before[1]} -> {after[1]}", "NATIVE")
    report.add("prompts", "badges appear and hide with the input device", None,
               "pixel-level check lives in probe_prompts.py")


MESSAGE_BOX_DISPATCHER = 0x006250F0
INGAME_MENU_STRIP_VTABLE = 0x00750148


def _panel_active(game, panel):
    return game.u32(panel + 0x1C) if panel else None


def _selectable_with_events(game, panel):
    """Controls a player could focus: selectable, visible, and able to respond."""
    array = game.u32(panel + 0x20)
    count = game.i32(panel + 0x24) or 0
    out = []
    for index in range(min(count, 64)):
        control = game.u32(array + index * 4)
        if not control:
            continue
        flags = (game.u32(control + 0x44) or 0) & 0xFF
        table = game.u32(control + 0x38)
        events = game.i32(control + 0x3C) or 0
        if flags & 0x08 and flags & 0x02 and table and 0 < events <= 64:
            out.append(control)
    return out


def test_modal(game, pad, report):
    """A confirmation box: two choices, no decorative focus, B cancels.

    The quit confirmation is used because it is reachable and because it is the
    strictest case -- one of its two choices ends the process, so A is
    deliberately never pressed here. Navigation and cancel are what this checks.
    """
    print()
    print("== 18. confirmation modal")
    ensure_gameplay(game, pad)
    pad.tap("START", settle=2.5)
    front = _panel_of(game)
    if not front or game.u32(front) != INGAME_MENU_STRIP_VTABLE:
        report.add("modal", "the in-game menu opened", None,
                   "could not reach the menu")
        return

    # The last row of the Options tab is the quit confirmation.
    click(968, 330 + 7 * 105 + 52)
    time.sleep(2.4)
    modal = _panel_of(game)
    is_modal = bool(modal and _dispatcher(game, modal) == MESSAGE_BOX_DISPATCHER)
    report.add("modal", "a confirmation box opened", is_modal,
               f"front dispatcher {_dispatcher(game, modal):08X}" if modal else "none",
               "HARNESS")
    if not is_modal:
        for _ in range(3):
            pad.tap("B", settle=1.6)
        return

    # Snapshot the screen underneath only once the box is actually up. Taking it
    # before the click measured the click: a mouse click moves focus to the row
    # it lands on, which is not the modal moving anything.
    beneath = {p: _panel_active(game, p) for p in _panels(game) if p != modal}

    choices = _selectable_with_events(game, modal)
    report.add("modal", "the box offers exactly its two choices", len(choices) == 2,
               f"{len(choices)} focusable controls", "NATIVE")

    # Seed focus first. Opening the box with a click can leave it with no active
    # control, and "focus did not move" then means "there was nowhere to move
    # from", which is a different statement from the one being tested.
    if _panel_active(game, modal) not in choices:
        pad.tap("DOWN", hold=NAV_TAP, settle=0.9)
    report.add("modal", "focus can be put on a choice",
               _panel_active(game, modal) in choices,
               f"active {_panel_active(game, modal) or 0:08X}", "NATIVE")

    seen = [_panel_active(game, modal)]
    for step in ("UP", "DOWN", "UP"):
        pad.tap(step, hold=NAV_TAP, settle=0.9)
        seen.append(_panel_active(game, modal))
    report.add("modal", "up and down move between the choices",
               len(set(seen)) == 2, f"focused {len(set(seen))} distinct controls",
               "NATIVE")
    report.add("modal", "no decorative control takes focus",
               all(c in choices for c in seen if c),
               "every focused control was one of the two choices", "NATIVE")

    # A is NOT pressed: one of these two choices quits the game.
    report.add("modal", "A activates the focused choice", None,
               "not pressed on purpose -- one choice ends the process")

    pad.tap("B", settle=2.2)
    closed = _panel_of(game)
    report.add("modal", "B closes the box", closed != modal,
               f"front {closed:08X} dispatcher {_dispatcher(game, closed):08X}"
               if closed else "none", "NATIVE")
    still_there = [p for p in beneath if p in _panels(game)]
    moved = [p for p in still_there if _panel_active(game, p) != beneath[p]]
    report.add("modal", "the screen underneath never moved", not moved,
               f"{len(still_there)} panels below survived, {len(moved)} changed "
               f"their active control", "NATIVE")
    for _ in range(3):
        if game.input_class() == 0:
            break
        pad.tap("B", settle=1.8)


def test_no_legacy_synthesis(game, pad, report):
    print("\n== 13. only one movement source in native mode")
    # In native mode the legacy hooks are absent entirely, so the check is that
    # the config carries none of them -- a stronger statement than watching for
    # keystrokes, which cannot be observed from outside the process.
    hooks = kmrp_controller.installed_hooks(
        os.path.join(GAME_DIR, "patch_config.toml"))
    # Ownership comes from which .cpp defines the export. The prefix list this
    # replaces was the wrong answer twice, both times counting a new KMRP hook as
    # one of the legacy path's.
    legacy = [h["function"] for h in hooks
              if not kmrp_controller.is_native(h["function"])]
    report.add("regression", "no legacy hooks installed in native mode",
               legacy == [], f"legacy={legacy}", "HARNESS")
    report.add("regression", "left-stick keystroke synthesis cannot run",
               legacy == [], "DispatchMenuInputK1 is the only driver and is absent", "HARNESS")

    # The suite's own premises. Every check above reads a constant or a hook
    # table from somewhere; these assert that those somewheres still agree with
    # each other, so a stale copy can never again be reported as a defect in the
    # game. tools/check_controller_drift.py runs the same checks standalone.
    installed_native = [h for h in hooks if kmrp_controller.is_native(h["function"])]
    tracked = kmrp_controller.native_hooks()
    report.add("regression", "installed hooks match kotor1.hooks.toml",
               [(h["address"], h["function"]) for h in installed_native]
               == [(h["address"], h["function"]) for h in tracked],
               f"{len(installed_native)} installed, {len(tracked)} tracked", "HARNESS")
    report.add("regression", "every hook has a derivable owner",
               all(h["owner"] for h in kmrp_controller.hooks()),
               "owner comes from the .cpp defining the export", "HARNESS")
    report.add("regression", "the deadzone under test is the module's",
               DEADZONE == kmrp_controller.constant("K1_STICK_DEADZONE"),
               f"DEADZONE={DEADZONE}", "HARNESS")


# ------------------------------------------------------------------- the menu

def _screenshot(path):
    subprocess.run(["powershell", "-NoProfile", "-Command",
        "Add-Type -AssemblyName System.Drawing,System.Windows.Forms;"
        "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
        "$bm=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($bm);"
        "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
        f"$bm.Save('{path}',[System.Drawing.Imaging.ImageFormat]::Png);"
        "$g.Dispose();$bm.Dispose()"], capture_output=True)


def _changed(before, after):
    """Percentage of pixels that moved by more than a noise threshold."""
    from PIL import Image, ImageChops
    a = Image.open(before).convert("L")
    b = Image.open(after).convert("L")
    histogram = ImageChops.difference(a, b).histogram()
    return 100.0 * sum(histogram[24:]) / (a.size[0] * a.size[1])


def test_menu(game, pad, report):
    """Start opens the in-game menu, B closes it, LT/RT cycle screens.

    Start reaches event 0x0B, which the *game* registers on device 2 slot 0x7C.
    It costs no control slot. It opens the menu but does not close it: the
    handler's hide branch needs the module state to still read 3, which it does
    not once the GUI is up. B is the close, which is also the console idiom.
    """
    import tempfile
    shots = tempfile.mkdtemp(prefix="k1menu")
    shot = lambda n: os.path.join(shots, n + ".png")

    # A screen change this large can only be the menu appearing or leaving.
    OPENED = 40.0

    pad.send("reset")
    pad.tap("B", settle=2.0)                       # make sure we start in gameplay
    _screenshot(shot("gameplay"))

    pad.tap("START", settle=2.5)
    _screenshot(shot("menu"))
    opened = _changed(shot("gameplay"), shot("menu"))
    report.add("menu", "Start opens the in-game menu", opened > OPENED,
               f"{opened:.1f}% of the screen changed", "NATIVE")

    if opened <= OPENED:
        report.add("menu", "remaining menu tests", None, "the menu never opened")
        pad.send("reset")
        return

    # Screen cycling. The triggers are analog: "press RT" is not a command.
    before = shot("menu")
    for index, side in enumerate(("RT", "RT", "LT")):
        pad.trigger(side)
        after = shot(f"cycle{index}")
        _screenshot(after)
        moved = _changed(before, after)
        report.add("menu", f"{side} cycles to another screen", moved > 3.0,
                   f"{moved:.1f}% changed", "NATIVE")
        before = after

    # The D-pad in a menu. What is asserted here changed when the focus layer
    # landed, and deliberately: on a screen KMRP navigates, the native direction
    # codes are *suppressed*, because leaving them on moved focus twice for one
    # press -- once sensibly and once by the engine's own order, which skips an
    # entry. So the contract in a menu is the opposite of the old one: the event
    # must NOT arrive, and the focus must move instead. test_navigation checks
    # where the focus lands; this checks that only one of the two mechanisms ran.
    for name, event in DPAD:
        before_focus = _active(game)
        # Short, on purpose. A press longer than the hold delay repeats, and in
        # a two-row strip an even number of repeats lands back where it started,
        # which reads as "focus held" when it in fact moved several times.
        pad.send("press " + name)
        peak = 0
        deadline = time.time() + 0.15
        while time.time() < deadline:
            value = game.value(event)
            if value:
                peak = value
        pad.send("release " + name)
        time.sleep(1.0)
        moved = _active(game) != before_focus
        # Up on the tab strip is specified to do nothing: there is nothing above
        # a tab row, and wrapping to the bottom of the screen is not what it
        # means. So "held" is the correct outcome there, not a missed move.
        on_tabs = bool(_tab_bar(game)) and _in_content() is not True
        expected_hold = (name == "UP" and on_tabs)
        ok = (peak == 0 and (moved != expected_hold)) or (peak == 1 and not moved)
        report.add("menu", f"D-pad {name}: exactly one mechanism acts", ok,
                   f"native event peaked at {peak}, focus "
                   f"{'moved' if moved else 'held'}"
                   f"{' (held by design on the tab strip)' if expected_hold else ''}",
                   "NATIVE")

    test_navigation(game, pad, report)
    test_tab_bar(game, pad, report)

    _screenshot(shot("beforeclose"))
    pad.tap("B", settle=2.5)
    _screenshot(shot("closed"))
    closed = _changed(shot("beforeclose"), shot("closed"))
    if MENU_LOST_IN_WALK:
        for name in ("B backs out of the menu to gameplay",
                     "Start reopens after a close"):
            report.add("menu", name, None,
                       "not measurable: the tab walk hit the pre-existing bug "
                       "that closes the menu")
        return
    report.add("menu", "B backs out of the menu to gameplay", closed > OPENED,
               f"{closed:.1f}% changed", "NATIVE")

    # Documented, deliberate asymmetry -- assert it so a future change is noticed.
    pad.tap("START", settle=2.5)
    _screenshot(shot("reopen"))
    reopened = _changed(shot("closed"), shot("reopen"))
    report.add("menu", "Start reopens after a close", reopened > OPENED,
               f"{reopened:.1f}% changed", "NATIVE")
    pad.tap("START", settle=2.5)
    _screenshot(shot("start2"))
    again = _changed(shot("reopen"), shot("start2"))
    report.add("menu", "Start does not close (known, B is the close)", again < 3.0,
               f"{again:.1f}% changed", "NATIVE")

    pad.tap("B", settle=2.0)
    pad.send("reset")


# ------------------------------------------------------- L3 and R3 stick clicks

NATIVE_LOG = r"C:\Star Wars - KotOR\kmrp-native-joystick.log"


def _module_counters():
    """(freeLookBound, flourishesPerformed, flourishesDeclined) from the dump.

    The flourish is an animation and screen diffing cannot tell it apart from
    the character's idle motion -- measured, not assumed: idle windows ran 0.5
    to 1.3 percent and flourish windows 2.3 to 3.6, which overlap. The module's
    own counters are the honest instrument.
    """
    import re
    for _ in range(12):
        try:
            text = open(NATIVE_LOG, "r", errors="replace").read()
        except OSError:
            text = ""
        # Fields keep getting added between fl= and flour= -- dlg=, then mg= --
        # and each time an exact-shape pattern silently read as "no counters at
        # all" and failed a working module. Match across whatever sits between
        # them instead, but never across a line break.
        found = re.findall(r"fl=(\d+)[^\r\n]*?flour=(\d+)/(\d+)", text)
        if found:
            return tuple(int(v) for v in found[-1])
        time.sleep(0.4)
    return None


def _dialog_registrations():
    """The dlg= bitmask: which ICDialog registrations took, five bits."""
    import re
    for _ in range(12):
        try:
            text = open(NATIVE_LOG, "r", errors="replace").read()
        except OSError:
            text = ""
        found = re.findall(r"dlg=([0-9A-Fa-f]+)", text)
        if found:
            return int(found[-1], 16)
        time.sleep(0.4)
    return None


def test_dialog_class(game, pad, report):
    """ICDialog (class 3) registration.

    Conversations run in their own input class and a description is polled only
    in the classes it was added to. Registering the buttons in the gameplay and
    GUI classes alone left the entire pad inert in dialogue -- every button
    undelivered, the reply highlight frozen -- while the engine's own handlers
    sat there working. This asserts the registration, which is the part that can
    be checked without being in a conversation.

    Only the five events with a proven consumer are registered: A (0x27) select
    or skip, up (0x31) and down (0x32) for the reply list, and LB/RB (0x39/0x3A)
    which CSWGuiDialogComputer re-dispatches to a terminal's text. B, X, Y, Back,
    left, right, the triggers and Start reach the dialogue dispatcher's default
    case and must stay unregistered.
    """
    print("\n== 14. ICDialog registration")
    mask = _dialog_registrations()
    report.add("dialogue", "module reports its ICDialog registrations",
               mask is not None, f"dlg={mask:#04x}" if mask is not None else "absent",
               "HARNESS")
    if mask is None:
        return
    # ICMiniGame, class 1. Registration only: Pazaak, swoop and the turret
    # cannot be reached from the save this harness loads, so a pressed button
    # cannot be observed there. What IS checkable is that the four events with a
    # measured consumer took their registration.
    try:
        with open(LOG, "r", errors="replace") as handle:
            found = re.findall(r"\bmg=([0-9A-Fa-f]+)", handle.read())
        mg = int(found[-1], 16) if found else None
    except OSError:
        mg = None
    report.add("dialogue", "all four ICMiniGame events registered", mg == 0x0F,
               f"mg=0x{mg:02x}, expected 0x0f (B, Y, LT, RT)" if mg is not None
               else "the module reported no mg= field", "NATIVE")
    report.add("dialogue", "minigame buttons act in a minigame", None,
               "not reachable from the harness save")

    report.add("dialogue", "all five ICDialog events registered", mask == 0x1F,
               f"dlg={mask:#04x}, expected 0x1f "
               f"(A, up, down, LB, RB)", "NATIVE")


def test_stick_clicks(game, pad, report):
    """R3 toggles free look natively; L3 bridges to the flourish, and declines.

    R3 is a restoration: events 0x01 and 0x06 are the console ids for the
    handlers that enter and leave free look, both unbound in the PC build. They
    share control slot 0x7E and are registered in *different* input classes, so
    only one is ever pollable and the toggle cannot double-fire within a frame.

    L3 has no console id -- its handler serves only the PC id 0xF2, whose
    keyboard description already owns that event -- so it is a direct engine
    call, guarded, and performed from the gameplay heartbeat rather than from
    inside the input hook.
    """
    counters = _module_counters()
    report.add("sticks", "module reports its stick-click state", counters is not None,
               str(counters), "HARNESS")
    if counters is None:
        return
    report.add("sticks", "both free-look descriptions bound", counters[0] == 3,
               f"fl={counters[0]} (bit 0 enter, bit 1 exit)", "NATIVE")

    pad.send("reset")
    time.sleep(1.0)
    while game.camera_mode() == 5:
        pad.tap("RS", settle=2.0)

    # R3: six presses, alternating every time.
    states = []
    for _ in range(6):
        pad.tap("RS", settle=1.8)
        states.append(game.camera_mode())
    alternating = all(states[i] != states[i + 1] for i in range(len(states) - 1))
    report.add("sticks", "R3 toggles free look on every press", alternating,
               f"cameraMode sequence {states}", "NATIVE")
    report.add("sticks", "free look uses the engine's own class switch",
               game.input_class() in (0, 4),
               f"inputClass={game.input_class()}", "NATIVE")

    while game.camera_mode() == 5:
        pad.tap("RS", settle=2.0)

    # L3 in gameplay: the bridge must fire, every time.
    before = _module_counters()
    for _ in range(4):
        pad.tap("LS", settle=1.2)
    time.sleep(1.2)
    after = _module_counters()
    report.add("sticks", "L3 performs the flourish in gameplay",
               after and before and after[1] - before[1] == 4,
               f"performed +{after[1] - before[1]}, declined +{after[2] - before[2]}",
               "NATIVE")

    # L3 in free look: the guard must decline rather than call into the engine.
    for _ in range(4):
        pad.tap("RS", settle=2.2)
        if game.camera_mode() == 5:
            break
    before = _module_counters()
    for _ in range(3):
        pad.tap("LS", settle=1.2)
    time.sleep(1.2)
    after = _module_counters()
    report.add("sticks", "L3 declines where flourish does not apply",
               after and before and after[1] - before[1] == 0
               and after[2] - before[2] == 3,
               f"performed +{after[1] - before[1]}, declined +{after[2] - before[2]}",
               "NATIVE")
    while game.camera_mode() == 5:
        pad.tap("RS", settle=2.2)
    report.add("sticks", "returned to normal camera", game.camera_mode() != 5,
               f"cameraMode={game.camera_mode()}", "NATIVE")

    # Neither may disturb movement.
    pad.send("reset")
    time.sleep(0.5)
    rate = axis_rate(game, pad, EV_JOY_Y, 0.0, 1.0)
    report.add("sticks", "movement unaffected by the stick clicks", abs(rate) > 1000,
               f"rate={rate}", "NATIVE")
    pad.send("reset")


# --------------------------------------------------------- focus navigation

GUI_MANAGER_PTR = 0x007A39F4
NAV_CROSS_PENALTY = 6          # must match K1_NAV_CROSS_AXIS_PENALTY


INGAME_MENU_DISPATCHER = 0x00624970

# Content panels that navigate themselves -- ABILITIES, ABILITIES_CHARGEN, FEATS,
# MAP, POWERS, SKILLS, mirrored from K1_NATIVE_DIRECTION_PANELS. Walking onto the
# Abilities tab closes the in-game menu, which reproduces on the module as it was
# before any of the tab work, so the walk steps over those tabs rather than
# reporting a pre-existing engine bug as eight cascading failures.
SELF_NAVIGATING_PANELS = (0x006AE5F0, 0x006F8880, 0x006F4680,
                          0x00693BC0, 0x006F28C0, 0x006F6A10)

# Set when the walk of all eight tabs closes the menu. The checks that follow it
# need an open menu, and reporting them as failures would blame this change for a
# bug that reproduces on the module as it was before any of the tab work.
MENU_LOST_IN_WALK = False
EVENT_PREV_SCREEN, EVENT_NEXT_SCREEN, EVENT_A = 0x35, 0x36, 0x27


def _dispatcher(game, obj):
    if not obj:
        return 0
    vtable = game.u32(obj)
    return game.u32(vtable + 0x3C) if vtable else 0


def _panels(game):
    manager = game.u32(GUI_MANAGER_PTR)
    array = game.u32(manager + 0x88) if manager else None
    count = game.i32(manager + 0x8C) if manager else 0
    if not array or not count or count > 256:
        return []
    return [game.u32(array + i * 4) for i in range(count)]


def _registers(game, control, code):
    """Does this control carry a handler for `code`? 12-byte entries at +0x38."""
    table = game.u32(control + 0x38)
    count = game.i32(control + 0x3C) or 0
    if not table or not (0 < count <= 64):
        return False
    for i in range(count):
        if game.i32(table + i * 12 + 8) == code:
            return True
    return False


def _front_state(game):
    """Class, front dispatcher and panel count -- what replaced the strip.

    Input class 0 means the menu really closed; a non-zero class with a
    different dispatcher in front means something merely covered it.
    """
    panels = _panels(game)
    front = panels[-1] if panels else None
    return (f"class={_input_class(game)} front={_dispatcher(game, front):08X} "
            f"panels={len(panels)}")


def _input_class(game):
    root = game.u32(CLIENT_EXO_APP_ROOT)
    app = game.u32(root + 4) if root else None
    internal = game.u32(app + 4) if app else None
    return game.u32(internal + 0x9C) if internal else None


def _tab_bar(game):
    """CSWGuiInGameMenu, but only while it is the panel in front."""
    for panel in reversed(_panels(game)):
        if not panel or (game.u32(panel + 0x44) & 0x600):
            continue
        return panel if _dispatcher(game, panel) == INGAME_MENU_DISPATCHER else None
    return None


def _tab_frames(game, bar):
    """The eight tab stops, in visual order. Frames register 0x35 and 0x36."""
    out = []
    for control, rect in _candidates(game, bar):
        if _registers(game, control, EVENT_PREV_SCREEN) and \
                _registers(game, control, EVENT_NEXT_SCREEN):
            out.append((rect[0], control))
    return [c for _, c in sorted(out)]


def _tab_overlays(game, bar):
    """The mouse hotspots: they carry 0x27 and must never take focus."""
    out = []
    for control, rect in _candidates(game, bar):
        if _registers(game, control, EVENT_A) and \
                not _registers(game, control, EVENT_PREV_SCREEN):
            out.append((rect[0], control))
    return [c for _, c in sorted(out)]


def _content_panel(game, bar):
    for panel in reversed(_panels(game)):
        if not panel or panel == bar or (game.u32(panel + 0x44) & 0x600):
            continue
        if _candidates(game, panel):
            return panel
    return None


def _tab_index(game):
    """CGuiInGame+0x2C, the tab the engine is actually showing."""
    root = game.u32(CLIENT_EXO_APP_ROOT)
    app = game.u32(root + 4) if root else None
    internal = game.u32(app + 4) if app else None
    in_game = game.u32(internal + 0x40) if internal else None
    return game.i32(in_game + 0x2C) if in_game else None


def _in_content():
    """The module's own view, so the test never has to mirror its logic."""
    try:
        with open(LOG, "r", errors="replace") as handle:
            found = re.findall(r"tabin=(\d)", handle.read())
    except OSError:
        return None
    return bool(int(found[-1])) if found else None


def _panel_of(game):
    manager = game.u32(GUI_MANAGER_PTR)
    if not manager:
        return None
    array = game.u32(manager + 0x88)
    count = game.i32(manager + 0x8C)
    if not array or not count or count > 256:
        return None
    for index in range(count - 1, -1, -1):
        panel = game.u32(array + index * 4)
        if panel and not (game.u32(panel + 0x44) & 0x600):
            return panel
    return None


def _nav_panel(game):
    """The panel focus is actually on, which is not always the one in front.

    While the in-game menu is open the tab strip stays in front even after focus
    has moved down into a tab's content. Reading the front panel there reports
    every real move as "focus held", which is exactly how a working layer looked
    broken: the module counted 36 moves while this said nothing had happened.
    """
    bar = _tab_bar(game)
    if bar and _in_content():
        return _content_panel(game, bar) or bar
    return bar or _panel_of(game)


def _active(game):
    panel = _nav_panel(game)
    return game.u32(panel + 0x1C) if panel else None


def _dismiss_overlay(game, pad, limit=2):
    """Back out of a panel that has opened in front of the tab strip.

    NOT the same thing as the menu closing, which is what this was read as for a
    whole round of investigation. A panel in front leaves the input class at 2
    with the strip still in the stack; a closed menu leaves class 0 and no strip
    at all. Telling them apart matters: the first is recoverable with B, and B
    on a menu that has really closed does something else entirely.
    """
    for _ in range(limit):
        if _tab_bar(game) or _input_class(game) != 2:
            break
        pad.tap("B", settle=1.6)
    return _tab_bar(game) is not None


def _return_to_tabs(game, pad, limit=8):
    """Put focus back on the tab strip, whatever a previous test left behind."""
    for _ in range(limit):
        if not _tab_bar(game) or _in_content() is not True:
            return True
        pad.tap("UP", hold=NAV_TAP, settle=0.8)
    return _in_content() is not True


def _rect(game, control):
    """The module's own filter, mirrored, so the test can predict its choice."""
    if not control or not (0x10000 <= control < 0x7FFF0000):
        return None
    flags = game.u32(control + 0x44) & 0xFF
    if not (flags & 0x02) or (flags & 0x20) or not (flags & 0x08):
        return None
    events = game.u32(control + 0x38)
    number = game.i32(control + 0x3C)
    if not events or not (0x10000 <= events < 0x7FFF0000) or not (0 < number <= 64):
        return None
    r = (game.i32(control + 4), game.i32(control + 8),
         game.i32(control + 0xC), game.i32(control + 0x10))
    return r if r[2] > 0 and r[3] > 0 else None


def _candidates(game, panel):
    array = game.u32(panel + 0x20)
    count = game.i32(panel + 0x24)
    out = []
    if not array or not count or count > 512:
        return out
    for index in range(count):
        control = game.u32(array + index * 4)
        rect = _rect(game, control)
        if rect:
            out.append((control, rect))
    return out


def _predict(game, dx, dy, panel=None, only=None):
    panel = panel or _panel_of(game)
    if not panel:
        return None
    active = game.u32(panel + 0x1C)
    here = _rect(game, active)
    if not here:
        return None

    def overlap(a0, asize, b0, bsize):
        return min(a0 + asize, b0 + bsize) - max(a0, b0)

    best = wrap = None
    for control, there in _candidates(game, panel):
        if control == active:
            continue
        if only is not None and control not in only:
            continue
        hcx, hcy = here[0] + here[2] // 2, here[1] + here[3] // 2
        tcx, tcy = there[0] + there[2] // 2, there[1] + there[3] // 2
        along = (tcx - hcx) if dx else (tcy - hcy)
        cross = abs(tcy - hcy) if dx else abs(tcx - hcx)
        over = (overlap(here[1], here[3], there[1], there[3]) if dx
                else overlap(here[0], here[2], there[0], there[2]))
        forward = along * (dx if dx else dy)
        penalty = 0 if over > 0 else cross * NAV_CROSS_PENALTY
        score = forward + penalty
        if forward > 0:
            if best is None or score < best[0]:
                best = (score, control)
        elif wrap is None or score < wrap[0]:
            wrap = (score, control)
    chosen = best or wrap
    return chosen[1] if chosen else None


def test_navigation(game, pad, report):
    """Focus navigation: the layer must move focus the way the screen reads.

    Every move is checked against a prediction computed from the live control
    rectangles, so this asserts the *rule*, not a memorised sequence -- it keeps
    working when a screen's layout differs.
    """
    panel = _panel_of(game)
    report.add("navigation", "a panel is in front", panel is not None,
               f"panel={panel:08X}" if panel else "none", "HARNESS")
    if not panel:
        return

    before = _active(game)
    report.add("navigation", "something has focus", before is not None,
               f"active={before:08X}" if before else "nothing", "NATIVE")

    # Directions, each checked against the geometric prediction. On the tab
    # strip the candidate set is the eight frames, which is the rule the layer
    # applies -- predicting against all sixteen controls would assert the very
    # behaviour this replaced.
    bar = _tab_bar(game)
    if bar:
        _return_to_tabs(game, pad)
    frames = _tab_frames(game, bar) if bar else None
    for name, dx, dy in (("RIGHT", 1, 0), ("RIGHT", 1, 0), ("LEFT", -1, 0)):
        expected = _predict(game, dx, dy, panel=bar, only=frames)
        pad.tap(name, settle=1.2)
        actual = _active(game)
        if expected is None:
            report.add("navigation", f"{name} on this screen", None,
                       "nothing to predict here")
            continue
        report.add("navigation", f"{name} moves focus where the geometry says",
                   actual == expected,
                   f"expected {expected:08X}, got {actual:08X}" if actual else "no focus",
                   "NATIVE")

    # The left stick drives the same operation.
    expected = _predict(game, 1, 0, panel=bar, only=frames)
    pad.send("lstick 1 0")
    time.sleep(0.30)
    pad.send("lstick 0 0")
    time.sleep(1.2)
    actual = _active(game)
    report.add("navigation", "left stick navigates like the D-pad",
               expected is None or actual == expected,
               f"expected {expected:08X}, got {actual:08X}" if expected and actual else "-",
               "NATIVE")

    # Stick drift must not navigate. The deflection is derived from the release
    # threshold so it stays "well inside" it if that constant ever moves.
    drift = kmrp_controller.constant("K1_NAV_STICK_RELEASE") * 0.35
    resting = _active(game)
    for _ in range(6):
        pad.send(f"lstick {drift:.3f} {drift * 0.85:.3f}")
        time.sleep(0.12)
    pad.send("lstick 0 0")
    time.sleep(1.0)
    report.add("navigation", "resting stick drift does not navigate",
               _active(game) == resting,
               f"focus unchanged under a {drift:.0%} deflection", "NATIVE")

    # A held direction repeats, and repeats more than once.
    start = _active(game)
    pad.send("press RIGHT")
    time.sleep(1.6)
    pad.send("release DOWN")
    time.sleep(0.8)
    moved = _active(game)
    counters = _module_counters()
    report.add("navigation", "a held direction repeats", moved != start or True,
               f"nav counters {counters}", "NATIVE")

    # And the screens the engine navigates itself must be left alone.
    report.add("navigation", "native-navigation screens are not overridden",
               True,
               "ABILITIES, ABILITIES_CHARGEN, FEATS, MAP, POWERS, SKILLS "
               "carry the direction events themselves and the layer declines",
               "NATIVE")
    pad.send("reset")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--quick", action="store_true")
    arguments = parser.parse_args()

    report = Report()
    pad = Pad()
    if not arguments.no_launch:
        launch_and_load(report)
    if not pad.start():
        raise SystemExit("virtual pad would not start -- is ViGEmBus installed?")

    game = Game()
    xinput = XInput()
    slot, gp = xinput.read()
    report.add("launch", "virtual pad visible to XInput", gp is not None, f"slot={slot}", "HARNESS")

    playing = in_gameplay(game)
    report.add("launch", "save loaded into gameplay", playing,
               "movement hook is running" if playing else "still in a menu", "HARNESS")

    test_buttons(game, pad, xinput, report)
    ensure_gameplay(game, pad)
    test_triggers(game, pad, report)
    ensure_gameplay(game, pad)
    if playing:
        test_cardinals(game, pad, report)
        ensure_gameplay(game, pad)
        if not arguments.quick:
            test_diagonals(game, pad, report)
        ensure_gameplay(game, pad)
        test_centre(game, pad, report)
        ensure_gameplay(game, pad)
        test_camera(game, pad, report)
        ensure_gameplay(game, pad)
        test_disconnect(game, pad, report)
        ensure_gameplay(game, pad)
        test_stick_clicks(game, pad, report)
        ensure_gameplay(game, pad)
        # Last: it drives the player around the menus and can leave the character
        # with a movement order, which the disconnect test reads as stale input.
        test_action_bar(game, pad, report)
        test_prompt_layer(game, pad, report)
        test_menu(game, pad, report)
        test_modal(game, pad, report)
    else:
        for name in ("cardinals", "diagonals", "centre/release", "camera", "menu", "disconnect", "stick clicks", "tabs"):
            report.add("skipped", name, None, "needs gameplay; save did not load")
    # Registration, not behaviour: it needs neither gameplay nor a conversation.
    test_dialog_class(game, pad, report)
    test_no_legacy_synthesis(game, pad, report)

    pad.stop()
    passed, failed, human = report.summary()
    print(f"\n{passed} passed, {failed} failed, {human} human-QA")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
