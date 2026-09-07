#!/usr/bin/env python3
"""Prove, from the running game's own memory, which buttons carry a badge.

Why this exists rather than a screenshot: a screenshot shows that *something*
was drawn. This shows that a specific control, on a specific panel class, has a
specific texture assigned as its fill -- which is the actual claim being made.

Why it does everything in one process: KOTOR runs fullscreen and minimises the
moment it loses focus, and the controller module ignores input unless the game is
the foreground window. Any tool call between "focus" and "read" hands focus to
something else and the run is void. So focusing, driving the pad and reading
memory all happen here, without yielding.

How a control is found:

  panel object   scan the process's committed private memory for a pointer to the
                 panel's vtable. Live panels are heap objects whose first dword is
                 that vtable, so a hit outside the image and outside the module is
                 the object itself.
  control        `panel + offset`. Controls are embedded objects, not pointers --
                 the module's own GetControl-free addressing relies on this.
  fill resref    `control + 0x80` is the normal border params (`+ 0xF4` is the
                 highlighted set), and the fill CExoString sits at `+ 0x40`
                 within those, read out of CSWGuiBorderParams::SetFillImage at
                 VA 0x00414C00: `lea edi,[esi+0x40]` then an assignment call.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import json
import re
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pad import send  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MODULE_SOURCE = ROOT / "src" / "controller-native" / "vendor" / "K1XboxControls.cpp"

BORDER_NORMAL = 0x80
BORDER_HILIGHT = 0xF4
FILL_IN_BORDER = 0x40

# GameConfig::panelActiveControlOffset in K1XboxControls.cpp -- the panel holds a
# POINTER to the control that currently has focus.
#
# Reading this is a safety requirement, not a nicety. Pressing A without knowing
# what is selected activates whatever happens to be focused: an early run of this
# harness sent a blind "tap A" on the main menu and quit the game. On Save/Load
# the same mistake would press Delete.
PANEL_ACTIVE_CONTROL = 0x1C

PROCESS_QUERY = 0x0400
PROCESS_READ = 0x0010
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_READABLE = 0x04 | 0x02 | 0x20 | 0x40      # RW, RO, EXEC_READ, EXEC_RW

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", wintypes.DWORD), ("Protect", wintypes.DWORD),
                ("Type", wintypes.DWORD)]


class Process:
    def __init__(self, pid: int):
        self.handle = kernel32.OpenProcess(PROCESS_QUERY | PROCESS_READ, False, pid)
        if not self.handle:
            raise OSError(f"could not open process {pid}")

    def read(self, address: int, size: int) -> bytes | None:
        buffer = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address),
                                        buffer, size, ctypes.byref(got))
        return buffer.raw[:got.value] if ok and got.value else None

    def regions(self):
        info = MEMORY_BASIC_INFORMATION()
        address = 0
        while address < 0x7FFF0000:
            if not kernel32.VirtualQueryEx(self.handle, ctypes.c_void_p(address),
                                           ctypes.byref(info),
                                           ctypes.sizeof(info)):
                break
            base = info.BaseAddress or 0
            size = info.RegionSize or 0
            if size == 0:
                break
            # MEM_PRIVATE only. Panel objects are heap allocations; the same dword
            # occurs by chance inside other modules' mapped data (opengl32,
            # kernelbase and ntdll all produced false "live panel" hits), and an
            # image or mapped region can never hold one.
            if (info.State == MEM_COMMIT and (info.Protect & PAGE_READABLE)
                    and info.Type == MEM_PRIVATE):
                yield base, size
            address = base + size

    def find_pointer(self, value: int, skip: list[tuple[int, int]]) -> list[int]:
        """Every address holding `value` as a little-endian dword, outside the
        ranges in `skip` (the game image and the controller module, whose hits are
        constructors and the module's own vtable comparisons)."""
        needle = struct.pack("<I", value)
        hits = []
        for base, size in self.regions():
            if any(low <= base < high for low, high in skip):
                continue
            data = self.read(base, min(size, 64 * 1024 * 1024))
            if not data:
                continue
            start = 0
            while True:
                index = data.find(needle, start)
                if index < 0:
                    break
                if index % 4 == 0:                 # objects are dword aligned
                    hits.append(base + index)
                start = index + 4
        return hits

    def fill_resref(self, address: int) -> str | None:
        """The fill is an INLINE 16-byte ResRef, not a heap CExoString.

        This was read as {char* text; int length} at first, which made every
        fill decode as empty -- and that false negative was very nearly reported
        as "the badges do not work", when a screenshot showed them rendering
        correctly all along. Verified against a live badge: the bytes at
        control+0xC0 (normal) and control+0x134 (highlighted) are
        the literal text "kmrpb_optgame" then NUL padding to 16 bytes.
        """
        raw = self.read(address, 16)
        if raw is None:
            return None
        return raw.split(b"\x00")[0].decode("ascii", "replace")


def parse_module():
    """Panel vtables, control offsets, and the badge bindings, from the source of
    truth rather than a copy kept here."""
    text = MODULE_SOURCE.read_text(encoding="utf-8")
    constants = {name: int(value, 0) for name, value in re.findall(
        r"constexpr\s+std::(?:uintptr_t|ptrdiff_t)\s+(\w+)\s*=\s*(-?0x[0-9A-Fa-f]+|-?\d+)\s*;", text)}
    arrays = {name: re.findall(r"\{\s*(\w+)\s*,\s*\"([^\"]+)\"\s*\}", body)
              for name, body in re.findall(
                  r"constexpr\s+ControllerPromptBinding\s+(\w+)\[\]\s*=\s*\{(.*?)\};", text, re.S)}
    return constants, arrays


def find_game_window() -> int:
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def each(handle, _):
        length = user32.GetWindowTextLengthW(handle)
        if length:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(handle, buffer, length + 1)
            if (buffer.value == "Star Wars: Knights of the Old Republic"
                    and user32.IsWindowVisible(handle)):
                found.append(handle)
        return True

    user32.EnumWindows(each, 0)
    return found[0] if found else 0


def clear_foreground_thief():
    """Windows Input Experience (TextInputHost.exe) repeatedly grabs the
    foreground on this machine, which makes the module's GameHasFocus() false and
    silently discards every controller input. It is a per-user UI host that
    Windows restarts on demand, so ending it is harmless and immediate."""
    import subprocess
    handle = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    listing = subprocess.run(["tasklist", "/FI", f"PID eq {pid.value}", "/NH"],
                             capture_output=True, text=True).stdout.split()
    if listing and listing[0].lower().startswith("textinputhost"):
        subprocess.run(["taskkill", "/PID", str(pid.value), "/F"],
                       capture_output=True, text=True)
        time.sleep(0.8)
        return True
    return False


def focus(handle: int) -> bool:
    clear_foreground_thief()
    user32.ShowWindow(handle, 5)
    if user32.IsIconic(handle):
        user32.ShowWindow(handle, 9)
        time.sleep(0.6)
    target = user32.GetWindowThreadProcessId(handle, None)
    current = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(current, target, True)
    user32.BringWindowToTop(handle)
    user32.SetForegroundWindow(handle)
    user32.SetActiveWindow(handle)
    user32.SetFocus(handle)
    user32.AttachThreadInput(current, target, False)
    time.sleep(1.2)
    if user32.GetForegroundWindow() != handle and clear_foreground_thief():
        user32.AttachThreadInput(current, target, True)
        user32.BringWindowToTop(handle)
        user32.SetForegroundWindow(handle)
        user32.AttachThreadInput(current, target, False)
        time.sleep(1.0)
    return user32.GetForegroundWindow() == handle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--panel", required=True,
                        help="panel vtable constant, e.g. K1_SAVELOAD_PANEL_VTABLE")
    parser.add_argument("--bindings", default="",
                        help="ControllerPromptBinding array name to check")
    parser.add_argument("--offsets", default="",
                        help="comma-separated offset constants to dump instead")
    parser.add_argument("--drive", default="",
                        help="semicolon-separated pad commands to send first")
    parser.add_argument("--buttons", action="store_true",
                        help="enumerate the panel's buttons with their screen rects")
    parser.add_argument("--out", type=Path)
    arguments = parser.parse_args()

    constants, arrays = parse_module()
    vtable = constants[arguments.panel]

    process = Process(arguments.pid)
    window = find_game_window()
    focused = focus(window) if window else False
    report = {"panel": arguments.panel, "vtable": hex(vtable), "focused": focused}

    if arguments.drive:
        commands = [c.strip() for c in arguments.drive.split(";") if c.strip()]
        # Controller mode only engages on real controller input, and the module
        # rescans XInput slots at most every two seconds.
        time.sleep(2.5)
        report["drive"] = list(zip(commands, send(commands)))
        time.sleep(1.0)

    # The game image and the controller module both legitimately contain this
    # value -- constructors and the module's own switch -- and are not objects.
    skip = [(0x00400000, 0x00400000 + 0x480000), (0x78C60000, 0x78D00000)]
    candidates = process.find_pointer(vtable, skip)
    report["panel_objects"] = [hex(a) for a in candidates]

    wanted = []
    if arguments.bindings:
        wanted = [(resref, constants[name]) for name, resref in arguments.bindings and
                  arrays.get(arguments.bindings, []) if name in constants]
    elif arguments.offsets:
        wanted = [(name, constants[name]) for name in arguments.offsets.split(",")
                  if name in constants]

    # What is focused right now, named by the offset constant it matches. This is
    # what makes a subsequent "tap A" safe to send.
    report["active"] = []
    for panel in candidates:
        head = process.read(panel + PANEL_ACTIVE_CONTROL, 4)
        active = struct.unpack("<I", head)[0] if head else 0
        entry = {"panel": hex(panel), "active": hex(active)}
        if active and active > panel:
            delta = active - panel
            entry["offset"] = hex(delta)
            entry["name"] = next((name for name, value in constants.items()
                                  if value == delta and name.endswith("_OFFSET")),
                                 "unnamed")
        report["active"].append(entry)

    # Every button on the panel, with the rectangle it occupies. Buttons are
    # embedded objects sharing one vtable, so scanning the panel for that vtable
    # finds them all; the rect lives at control + 0x04. This is how a screen's
    # layout is learned without guessing offsets, and how a press is aimed at a
    # known control rather than whatever happens to be focused.
    if arguments.buttons:
        report["buttons"] = []
        for panel in candidates:
            head = process.read(panel + PANEL_ACTIVE_CONTROL, 4)
            active = struct.unpack("<I", head)[0] if head else 0
            blob = process.read(panel, 0x8000) or b""
            rows = []
            for position in range(0, len(blob) - 4, 4):
                # Any embedded control, not just the class the focused one happens
                # to be: keying off the active control's vtable found only the save
                # listbox on Save/Load. A control starts with a vtable pointing
                # into the game's read-only data, followed by its screen rect.
                candidate = struct.unpack_from("<I", blob, position)[0]
                if not (0x00700000 <= candidate <= 0x00780000):
                    continue
                rect = process.read(panel + position + 4, 16)
                if not rect or len(rect) < 16:
                    continue
                left, top, width, height = struct.unpack("<iiii", rect)
                if 0 <= left <= 8192 and 0 <= top <= 8192 and 0 < width <= 8192 and 0 < height <= 1024:
                    rows.append({"offset": hex(position),
                                 "vtable": hex(candidate),
                                 "rect": [left, top, width, height],
                                 "active": panel + position == active,
                                 "name": next((n for n, v in constants.items()
                                               if v == position and n.endswith("_OFFSET")),
                                              "")})
            rows.sort(key=lambda row: (row["rect"][1], row["rect"][0]))
            report["buttons"].append({"panel": hex(panel), "items": rows})

    report["controls"] = []
    for panel in candidates:
        for label, offset in wanted:
            control = panel + offset
            row = {
                "panel": hex(panel), "control": label, "offset": hex(offset),
                "normal_fill": process.fill_resref(control + BORDER_NORMAL + FILL_IN_BORDER),
                "hilight_fill": process.fill_resref(control + BORDER_HILIGHT + FILL_IN_BORDER),
            }
            report["controls"].append(row)

    text = json.dumps(report, indent=2)
    print(text)
    if arguments.out:
        arguments.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
