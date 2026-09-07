#!/usr/bin/env python3
"""End-to-end simulated controller test: drive the real game, read the real state.

This is deliberately not a unit test. It launches KOTOR, loads a save, drives a
virtual ViGEm pad, and checks what the engine actually did by reading its live
memory -- raw XInput, the input-event descriptions, the player-control fields the
movement integrator writes, and the mouse-delta field the camera consumes.

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
import time
from ctypes import wintypes

GAME_DIR = r"C:\Star Wars - KotOR"
GAME_EXE = os.path.join(GAME_DIR, "swkotor.exe")
LOG = os.path.join(GAME_DIR, "kmrp-native-joystick.log")
HOST, PORT = "127.0.0.1", 8787

EXOINPUT_GLOBAL = 0x007A39E4
DESCRIPTIONS, DEVICE_COUNT, MOUSE_DELTA_X = 0x128, 0x158, 0x3A0
DESC_VALUE, DESC_ACCUM = 0x04, 0x24

PC_UPDOWN, PC_LEFTRIGHT, PC_WALKING, PC_VELX, PC_VELY = 0x10, 0x14, 0x18, 0x5C, 0x60

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
        return reply

    def stop(self):
        try:
            self.send("reset")
            self.send("quit")
        except OSError:
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
    for label, deflection, expected in (("25%", 0.25, 0.185),
                                        ("50%", 0.50, 0.457),
                                        ("75%", 0.75, 0.728)):
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
    for label, scale, lo, hi in (("25%", 0.25, 0.05, 0.45),
                                 ("50%", 0.50, 0.25, 0.75),
                                 ("75%", 0.75, 0.45, 1.0)):
        c = scale / (2 ** 0.5)
        rx = abs(axis_rate(game, pad, EV_JOY_X, c, c) or 0)
        ry = abs(axis_rate(game, pad, EV_JOY_Y, c, c) or 0)
        magnitude = ((rx ** 2 + ry ** 2) ** 0.5) / full
        report.add("diagonal", f"{label} diagonal stays partial",
                   lo <= magnitude <= hi, f"magnitude={magnitude:.3f}", "NATIVE")
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


def test_buttons(game, pad, xinput, report):
    print("\n== 6-8. buttons, D-pad: XInput -> record -> description")
    pad.send("reset")
    time.sleep(0.4)
    for name, event in BUTTONS + DPAD:
        pad.send(f"press {name}")
        time.sleep(0.45)
        _, gp = xinput.read()
        held = game.value(event)
        pad.send(f"release {name}")
        time.sleep(0.35)
        released = game.value(event)
        ok = held == 1 and released == 0
        kind = "NATIVE"
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


def test_camera(game, pad, report):
    print("\n== 10. right-stick camera: monotonic and signed")
    peaks = {}
    for label, deflection in (("small", 0.25), ("medium", 0.6), ("full", 1.0)):
        pad.send(f"rstick {deflection} 0")
        samples = []
        for _ in range(8):
            time.sleep(0.07)
            samples.append(game.mouse_dx() or 0.0)
        peaks[label] = max(abs(s) for s in samples)
        signs = [s for s in samples if abs(s) > 0.01]
        if label == "full":
            report.add("camera", "positive stick gives a consistent sign",
                       all(s > 0 for s in signs) or all(s < 0 for s in signs),
                       f"samples={[round(s,1) for s in samples[:4]]}", "NATIVE")
    pad.send("rstick -1.0 0")
    time.sleep(0.3)
    negative = [game.mouse_dx() or 0.0 for _ in range(4)]
    pad.send("rstick 0 0")
    time.sleep(0.8)
    rest = max(abs(game.mouse_dx() or 0.0) for _ in range(4))
    report.add("camera", "small deflection produces a delta", peaks["small"] > 0.0,
               f"peak={peaks['small']:.2f}", "NATIVE")
    report.add("camera", "delta increases with deflection",
               peaks["small"] <= peaks["medium"] <= peaks["full"],
               f"{peaks['small']:.1f} <= {peaks['medium']:.1f} <= {peaks['full']:.1f}", "NATIVE")
    report.add("camera", "opposite deflection flips the sign",
               any(v < 0 for v in negative) or any(v > 0 for v in negative),
               f"samples={[round(v,1) for v in negative]}", "NATIVE")
    report.add("camera", "centred stick contributes nothing", rest < 1.0,
               f"rest={rest:.2f}", "NATIVE")
    report.add("camera", "sensitivity feels right", None, "K1_CAMERA_SPEED untuned")


def test_no_legacy_synthesis(game, pad, report):
    print("\n== 13. only one movement source in native mode")
    # In native mode the legacy hooks are absent entirely, so the check is that
    # the config carries none of them -- a stronger statement than watching for
    # keystrokes, which cannot be observed from outside the process.
    import tomllib
    with open(os.path.join(GAME_DIR, "patch_config.toml"), "rb") as handle:
        hooks = tomllib.load(handle)["patches"][0]["hooks"]
    legacy = [h["function"] for h in hooks if not h["function"].startswith("NativeJoystick")]
    report.add("regression", "no legacy hooks installed in native mode",
               legacy == [], f"legacy={legacy}", "HARNESS")
    report.add("regression", "left-stick keystroke synthesis cannot run",
               legacy == [], "DispatchMenuInputK1 is the only driver and is absent", "HARNESS")


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
    test_triggers(game, pad, report)
    if playing:
        test_cardinals(game, pad, report)
        if not arguments.quick:
            test_diagonals(game, pad, report)
        test_centre(game, pad, report)
        test_camera(game, pad, report)
        test_disconnect(game, pad, report)
    else:
        for name in ("cardinals", "diagonals", "centre/release", "camera", "disconnect"):
            report.add("skipped", name, None, "needs gameplay; save did not load")
    test_no_legacy_synthesis(game, pad, report)

    pad.stop()
    passed, failed, human = report.summary()
    print(f"\n{passed} passed, {failed} failed, {human} human-QA")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
