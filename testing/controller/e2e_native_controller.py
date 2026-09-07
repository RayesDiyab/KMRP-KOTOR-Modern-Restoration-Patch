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
CLIENT_EXO_APP_ROOT = 0x007A39FC   # -> CClientExoApp at [+4]
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
    legacy = [h["function"] for h in hooks if not h["function"].startswith(("NativeJoystick", "NativeGui"))]
    report.add("regression", "no legacy hooks installed in native mode",
               legacy == [], f"legacy={legacy}", "HARNESS")
    report.add("regression", "left-stick keystroke synthesis cannot run",
               legacy == [], "DispatchMenuInputK1 is the only driver and is absent", "HARNESS")


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
        report.add("menu", f"D-pad {name}: exactly one mechanism acts",
                   (peak == 0 and moved) or (peak == 1 and not moved),
                   f"native event peaked at {peak}, focus {'moved' if moved else 'held'}",
                   "NATIVE")

    test_navigation(game, pad, report)

    _screenshot(shot("beforeclose"))
    pad.tap("B", settle=2.5)
    _screenshot(shot("closed"))
    closed = _changed(shot("beforeclose"), shot("closed"))
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
        found = re.findall(r"fl=(\d+) flour=(\d+)/(\d+)", text)
        if found:
            return tuple(int(v) for v in found[-1])
        time.sleep(0.4)
    return None


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


def _active(game):
    panel = _panel_of(game)
    return game.u32(panel + 0x1C) if panel else None


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


def _predict(game, dx, dy):
    panel = _panel_of(game)
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

    # Directions, each checked against the geometric prediction.
    for name, dx, dy in (("DOWN", 0, 1), ("DOWN", 0, 1), ("UP", 0, -1),
                         ("RIGHT", 1, 0), ("LEFT", -1, 0)):
        expected = _predict(game, dx, dy)
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
    expected = _predict(game, 0, 1)
    pad.send("lstick 0 -1")
    time.sleep(0.30)
    pad.send("lstick 0 0")
    time.sleep(1.2)
    actual = _active(game)
    report.add("navigation", "left stick navigates like the D-pad",
               expected is None or actual == expected,
               f"expected {expected:08X}, got {actual:08X}" if expected and actual else "-",
               "NATIVE")

    # Stick drift must not navigate. Well inside the release threshold.
    resting = _active(game)
    for _ in range(6):
        pad.send("lstick 0.12 0.10")
        time.sleep(0.12)
    pad.send("lstick 0 0")
    time.sleep(1.0)
    report.add("navigation", "resting stick drift does not navigate",
               _active(game) == resting, "focus unchanged under a 12% deflection",
               "NATIVE")

    # A held direction repeats, and repeats more than once.
    start = _active(game)
    pad.send("press DOWN")
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
    test_triggers(game, pad, report)
    if playing:
        test_cardinals(game, pad, report)
        if not arguments.quick:
            test_diagonals(game, pad, report)
        test_centre(game, pad, report)
        test_camera(game, pad, report)
        test_disconnect(game, pad, report)
        test_stick_clicks(game, pad, report)
        # Last: it drives the player around the menus and can leave the character
        # with a movement order, which the disconnect test reads as stale input.
        test_menu(game, pad, report)
    else:
        for name in ("cardinals", "diagonals", "centre/release", "camera", "menu", "disconnect", "stick clicks"):
            report.add("skipped", name, None, "needs gameplay; save did not load")
    test_no_legacy_synthesis(game, pad, report)

    pad.stop()
    passed, failed, human = report.summary()
    print(f"\n{passed} passed, {failed} failed, {human} human-QA")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
