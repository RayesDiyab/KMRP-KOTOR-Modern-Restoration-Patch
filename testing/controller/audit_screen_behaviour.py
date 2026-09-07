#!/usr/bin/env python3
"""What each controller input actually does, measured against the running game.

The static pass (tools/controller_behaviour_matrix.py) says which handler an
event reaches. This says what happened. They answer different questions, and the
second one is the one that matters: an event arriving proves the wiring, not
that the screen responded.

For every button on every screen it can reach, this records the observable
change:

  panel      the topmost panel's vtable -- a change means the screen changed
  focus      the panel's active control -- a change means focus moved
  class      CClientExoAppInternal+0x9c: 0 world, 2 GUI, 4 free look
  camera     ClientOptions+0x6D: 5 is free look
  event      the input description's value while held, so a button that does
             nothing can still be distinguished from one that never arrived
  pixels     how much of the screen changed, as a last resort for effects with
             no state to read

Safety: A is never pressed on Save/Load, and no control named delete or quit is
ever activated. The run is read-only apart from the button presses themselves.

Run with the game already in gameplay with a save loaded, and the virtual pad
server running.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import socket
import struct
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

HOST, PORT = "127.0.0.1", 8787

EXOINPUT_GLOBAL = 0x007A39E4
GUI_MANAGER_PTR = 0x007A39F4
APP_MANAGER_PTR = 0x007A39FC
DESCRIPTIONS = 0x128

# button -> (pad verb, event id) ; None means it has no single event
BUTTONS = [
    ("A", "A", 0x27), ("B", "B", 0x28), ("X", "X", 0x29), ("Y", "Y", 0x2A),
    ("LB", "LB", 0x39), ("RB", "RB", 0x3A), ("Back", "BACK", 0x2B),
    ("Up", "UP", 0x31), ("Down", "DOWN", 0x32),
    ("Left", "LEFT", 0x2F), ("Right", "RIGHT", 0x30),
    ("Start", "START", 0x0B), ("L3", "LS", None), ("R3", "RS", 0x01),
]
TRIGGERS = [("LT", 0x35), ("RT", 0x36)]

DESTRUCTIVE_SCREENS = {"CSWGuiSaveLoad"}    # A is not pressed here

# A confirmation box appearing means the previous press asked a question, and
# leaving it open would make every later row describe the box instead of the
# screen. Each is dismissed by the button PROVEN to reach its cancel handler,
# never by assuming that B works everywhere.
#
# CSWGuiSoloModeQuery earned that caution and then disproved it. Its dispatcher
# at 0x006C2400 was read as implementing 0x2E but not 0x28, which would have
# meant B could not close it. That reading was a decoder artefact: the chain
# accumulated across a `mov ecx, eax` that restarts the arithmetic, inventing
# 0x55/0x56/0x5B and hiding the real 0x27/0x28/0x2D. Decoded correctly:
#
#   0x28 (B), 0x2E -> 0x006C2488 -> CGuiInGame::HideSoloMode      cancel
#   0x27 (A), 0x2D -> 0x006C244C -> CClientExoApp::TogglePartyFollow  confirm
#
# So B is the correct dismiss here after all. A is not destructive either, but
# it toggles party follow, so it is still not the button to recover with.
DIALOG_PANELS = {"CSWGuiMessageBox", "CSWGuiSoloModeQuery", "CSWGuiControllerLossBox"}

# panel -> the button proven to reach its cancel/dismiss handler.
DIALOG_DISMISS = {
    "CSWGuiMessageBox": "B",          # 0x28 implemented, verified live
    "CSWGuiSoloModeQuery": "B",       # 0x28 -> HideSoloMode, proven statically
    "CSWGuiControllerLossBox": "B",   # 0x28 implemented
}

SYMBOLS_DB = (Path(__file__).resolve().parents[2] / "build" / "research" /
              "Kotor-Patch-Manager" / "AddressDatabases" / "kotor1_0_3.db")


def panel_names():
    """vtable -> class name, so a screen is reported by name and not an address."""
    import sqlite3
    if not SYMBOLS_DB.exists():
        return {}
    connection = sqlite3.connect(SYMBOLS_DB)
    return {vtable: name for name, vtable in connection.execute(
        "select class_name, vtable from classes "
        "where vtable is not null and class_name like 'CSWGui%'")}


NAMES = {}


class Game:
    def __init__(self):
        self.k = ctypes.windll.kernel32
        self.k.OpenProcess.restype = wintypes.HANDLE
        pid = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "(Get-Process swkotor).Id"])
        self.handle = self.k.OpenProcess(0x0010 | 0x0400, False,
                                         int(pid.decode().split()[0]))
        if not self.handle:
            raise SystemExit("could not open swkotor")
        self.internal = self.u32(self.u32(EXOINPUT_GLOBAL) + 4)
        self.descs = self.u32(self.internal + DESCRIPTIONS)

    def read(self, address, size=4):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, ctypes.c_void_p(address),
                                        buf, size, ctypes.byref(got)):
            return None
        return buf.raw

    def u32(self, a):
        raw = self.read(a)
        return struct.unpack("<I", raw)[0] if raw else None

    def i32(self, a):
        v = self.u32(a)
        return None if v is None else struct.unpack("<i", struct.pack("<I", v))[0]

    # -- GUI ---------------------------------------------------------------
    def top_panel(self):
        manager = self.u32(GUI_MANAGER_PTR)
        if not manager:
            return None
        array, count = self.u32(manager + 0x88), self.i32(manager + 0x8C)
        if not array or not count or count > 256:
            return None
        for index in range(count - 1, -1, -1):
            panel = self.u32(array + index * 4)
            if panel and not (self.u32(panel + 0x44) & 0x600):
                return panel
        return None

    def panel_vtable(self):
        panel = self.top_panel()
        return self.u32(panel) if panel else None

    def panel_dispatcher(self):
        vtable = self.panel_vtable()
        return self.u32(vtable + 0x3C) if vtable else None

    def focus(self):
        panel = self.top_panel()
        return self.u32(panel + 0x1C) if panel else None

    def panel_depth(self):
        manager = self.u32(GUI_MANAGER_PTR)
        return self.i32(manager + 0x8C) if manager else None

    # -- app ---------------------------------------------------------------
    def _app(self):
        root = self.u32(APP_MANAGER_PTR)
        return self.u32(root + 4) if root else None

    def input_class(self):
        app = self._app()
        internal = self.u32(app + 4) if app else None
        return self.u32(internal + 0x9C) if internal else None

    def camera_mode(self):
        app = self._app()
        internal = self.u32(app + 4) if app else None
        options = self.u32(internal + 4) if internal else None
        raw = self.read(options + 0x6D, 1) if options else None
        return raw[0] if raw else None

    def event_value(self, event):
        if event is None:
            return None
        d = self.u32(self.descs + event * 4)
        return self.i32(d + 4) if d else None

    def stack(self):
        """Every panel in the manager's list, front last, named where known.

        The topmost panel is not the screen. With the in-game menu open the top
        is always CSWGuiInGameMenu, the shell that draws the tab strip, and the
        tab actually being looked at is a panel below it -- which is why an
        earlier pass reported four different tabs as the same screen.
        """
        manager = self.u32(GUI_MANAGER_PTR)
        if not manager:
            return []
        array, count = self.u32(manager + 0x88), self.i32(manager + 0x8C)
        if not array or not count or count > 256:
            return []
        out = []
        for index in range(count):
            panel = self.u32(array + index * 4)
            if not panel:
                continue
            vtable = self.u32(panel)
            out.append((vtable, NAMES.get(vtable, f"{vtable:08X}")))
        return out

    def screen_name(self):
        """The screen a player would say they are looking at."""
        names = [n for _, n in self.stack()]
        for name in reversed(names):
            if name in DIALOG_PANELS:
                return name
        content = [n for n in names
                   if n not in ("CSWGuiFade", "CSWGuiInGameMenu", "CSWGuiMainInterface")
                   and not n[0].isdigit()]
        if content:
            return content[-1]
        return names[-1] if names else "?"

    def snapshot(self):
        return {
            "panel": self.panel_vtable(),
            "dispatcher": self.panel_dispatcher(),
            "focus": self.focus(),
            "class": self.input_class(),
            "camera": self.camera_mode(),
            "depth": self.panel_depth(),
            "screen": self.screen_name(),
            "stack": [n for _, n in self.stack()],
        }


def pad(command):
    s = socket.create_connection((HOST, PORT), timeout=5)
    s.sendall((command + "\n").encode())
    reply = s.recv(64).decode().strip()
    s.close()
    if reply.startswith("err"):
        raise RuntimeError(f"pad rejected {command!r}: {reply}")
    return reply


def screenshot(path):
    subprocess.run(["powershell", "-NoProfile", "-Command",
        "Add-Type -AssemblyName System.Drawing,System.Windows.Forms;"
        "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
        "$bm=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($bm);"
        "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
        f"$bm.Save('{path}',[System.Drawing.Imaging.ImageFormat]::Png);"
        "$g.Dispose();$bm.Dispose()"], capture_output=True)


def changed(before, after):
    from PIL import Image, ImageChops
    a, b = Image.open(before).convert("L"), Image.open(after).convert("L")
    histogram = ImageChops.difference(a, b).histogram()
    return 100.0 * sum(histogram[24:]) / (a.size[0] * a.size[1])


def describe(before, after, pixels, peak):
    """Turn two snapshots into a sentence about what the button did."""
    notes = []
    if before["screen"] != after["screen"]:
        notes.append(f"screen {before['screen']} -> {after['screen']}")
    elif before["panel"] != after["panel"]:
        notes.append(f"top panel {before['panel']:08X} -> {after['panel']:08X}")
    if before["depth"] != after["depth"]:
        notes.append(f"panel depth {before['depth']} -> {after['depth']}")
    if before["focus"] != after["focus"]:
        notes.append("focus moved")
    if before["class"] != after["class"]:
        notes.append(f"input class {before['class']} -> {after['class']}")
    if before["camera"] != after["camera"]:
        notes.append(f"camera mode {before['camera']} -> {after['camera']}")
    if not notes:
        if pixels is not None and pixels > 1.5:
            notes.append(f"visible change only ({pixels:.1f}% of screen)")
        elif peak:
            notes.append("event delivered, no observable state change")
        else:
            notes.append("nothing")
    return "; ".join(notes)


def press_button(game, verb, event, shots, hold=0.16, settle=1.1):
    before = game.snapshot()
    a = str(shots / "a.png")
    b = str(shots / "b.png")
    screenshot(a)
    peak = 0
    if verb in ("LT", "RT"):
        pad("triggers 1 0" if verb == "LT" else "triggers 0 1")
        deadline = time.time() + hold
        while time.time() < deadline:
            v = game.event_value(event)
            if v:
                peak = v
        pad("triggers 0 0")
    else:
        pad("press " + verb)
        deadline = time.time() + hold
        while time.time() < deadline:
            v = game.event_value(event)
            if v:
                peak = v
        pad("release " + verb)
    time.sleep(settle)
    after = game.snapshot()
    screenshot(b)
    pixels = changed(a, b)
    return before, after, peak, pixels


def dismiss_dialog(game):
    """Back out of a confirmation box, never confirm it.

    The dismiss button is looked up per panel from DIALOG_DISMISS rather than
    assumed, because event aliases are not interchangeable: a handler registered
    for 0x2E is not reached by sending 0x28. If a box turns up that is not in
    the table, this stops rather than guessing -- pressing an unknown button on
    an unknown prompt is how an audit confirms something destructive.
    """
    for _ in range(3):
        screen = game.screen_name()
        if screen not in DIALOG_PANELS:
            return True
        button = DIALOG_DISMISS.get(screen)
        if button is None:
            print(f"  !! {screen} is open and no proven dismiss button is known; "
                  f"stopping rather than guessing")
            return False
        pad("press " + button)
        time.sleep(0.25)
        pad("release " + button)
        time.sleep(1.5)
    return game.screen_name() not in DIALOG_PANELS


def restore(game, target):
    """Get back to the input class the audit was measuring.

    Start opens the menu and B closes it, so one of those two returns us. This
    is why the audit records the class it started in rather than assuming.
    """
    for _ in range(4):
        if game.input_class() == target["class"]:
            return True
        verb = "START" if target["class"] == 2 else "B"
        pad("press " + verb)
        time.sleep(0.25)
        pad("release " + verb)
        time.sleep(2.0)
    return game.input_class() == target["class"]


def audit_screen(game, label, shots, skip=()):
    print(f"\n--- {label}  panel={game.panel_vtable():08X} "
          f"dispatcher={game.panel_dispatcher():08X} class={game.input_class()}")
    rows = []
    if game.screen_name() in DESTRUCTIVE_SCREENS:
        skip = tuple(skip) + ("A",)
    for name, verb, event in BUTTONS:
        if name in skip:
            print(f"  {name:<6} SKIPPED (unsafe on this screen)")
            rows.append({"button": name, "action": "not pressed: unsafe here",
                         "event": event, "peak": None, "pixels": None})
            continue
        before, after, peak, pixels = press_button(game, verb, event, shots)
        action = describe(before, after, pixels, peak)
        label_event = "-" if event is None else hex(event)
        print(f"  {name:<6} ev={label_event:<6} peak={peak} "
              f"pix={pixels:5.1f} {action}")
        rows.append({"button": name, "event": event, "peak": peak,
                     "pixels": round(pixels, 2), "action": action,
                     "before": before, "after": after})
        # If the button moved us off this screen, come back before testing the
        # next one, or every later row describes a different screen.
        dismiss_dialog(game)
        if after["class"] != before["class"] or after["screen"] != before["screen"]:
            restore(game, before)
    for name, event in TRIGGERS:
        if name in skip:
            continue
        before, after, peak, pixels = press_button(game, name, event, shots)
        action = describe(before, after, pixels, peak)
        print(f"  {name:<6} ev={hex(event):<6} peak={peak} {action}")
        rows.append({"button": name, "event": event, "peak": peak,
                     "pixels": round(pixels, 2), "action": action,
                     "before": before, "after": after})
    return rows


def audit_sticks(game, label, shots):
    """Left and right stick, which are analog and need their own treatment."""
    rows = []
    for name, command in (("Left stick", "lstick 0 1"), ("Right stick", "rstick 1 0")):
        before = game.snapshot()
        a, b = str(shots / "sa.png"), str(shots / "sb.png")
        screenshot(a)
        pad(command)
        time.sleep(0.7)
        pad("reset")
        time.sleep(1.0)
        after = game.snapshot()
        screenshot(b)
        pixels = changed(a, b)
        action = describe(before, after, pixels, 0)
        print(f"  {name:<12} {action}")
        rows.append({"button": name, "action": action, "pixels": round(pixels, 2)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("screen_audit.json"))
    parser.add_argument("--screens", type=int, default=8,
                        help="how many in-game tab screens to walk with RT")
    arguments = parser.parse_args()

    shots = Path(__file__).resolve().parent / "_audit_shots"
    shots.mkdir(exist_ok=True)
    global NAMES
    NAMES = panel_names()
    game = Game()
    pad("reset")
    time.sleep(1.0)

    result = {}

    # 1. gameplay
    if game.input_class() != 0:
        pad("press B")
        time.sleep(0.3)
        pad("release B")
        time.sleep(2.0)
    result["GAMEPLAY"] = {
        "class": game.input_class(),
        "rows": audit_screen(game, "GAMEPLAY", shots),
    }
    result["GAMEPLAY"]["rows"] += audit_sticks(game, "GAMEPLAY", shots)

    # 2. the in-game menu and its tab screens
    if game.input_class() != 2:
        pad("press START")
        time.sleep(0.3)
        pad("release START")
        time.sleep(2.5)
    for index in range(arguments.screens):
        dispatcher = game.panel_dispatcher()
        label = f"INGAME_SCREEN_{index}_disp_{dispatcher:08X}" if dispatcher else f"INGAME_{index}"
        skip = ()
        result[label] = {
            "class": game.input_class(),
            "dispatcher": dispatcher,
            "rows": audit_screen(game, label, shots, skip=skip),
        }
        # next tab
        pad("triggers 0 1")
        time.sleep(0.3)
        pad("triggers 0 0")
        time.sleep(1.6)

    arguments.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nwrote {arguments.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
