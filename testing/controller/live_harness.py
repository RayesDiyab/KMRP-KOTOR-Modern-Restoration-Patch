#!/usr/bin/env python3
"""A running game, read from outside and driven by the virtual pad.

The pieces the live trials share: start a game folder, bring it forward, read the GUI manager's
panels and the movie player out of its memory, press the pad, and take a frame. Nothing here writes
to the game's memory. Run from Git Bash: PowerShell's Python has no vgamepad, and the pad is held
open by `virtual_pad_server.py`, which `Pad.ensure_server` starts.

Pad input reaches only a game that holds the foreground, so every press checks that first and
refuses otherwise. Keyboard and mouse are never sent from here.

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import ctypes
import os
import socket
import struct
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
VERIFY = ROOT / "build" / "verify"
DEFAULT_GAME = VERIFY / "steam"

GUI_MANAGER = 0x007A39F4
CLIENT_ROOT = 0x007A39FC
MOVIE_PLAYER = 0x007A3CF4
MANAGER_PANELS, MANAGER_COUNT = 0x88, 0x8C
PANEL_ACTIVE = 0x1C

# K1EngineAddresses.h and K1XboxControls.cpp, by the names the trials ask for.
PANEL_NAMES = {
    0x00752F70: "main-menu",
    0x00758020: "class-select",
    0x00759710: "quick-or-custom",
    0x00753F50: "hud",
    0x00750148: "ingame-menu-strip",
    0x0074FDB0: "message-box",
    0x00755C60: "bark-bubble",
    0x00757940: "skill-info",
}

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(ctypes.c_size_t)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]


class Pad:
    """The virtual pad, through `virtual_pad_server.py`."""

    HOST, PORT = "127.0.0.1", 8787
    server: subprocess.Popen | None = None

    @classmethod
    def ensure_server(cls):
        try:
            cls.send("ping")
            return
        except OSError:
            pass
        log = open(VERIFY / "pad-server.log", "a", encoding="utf-8")
        cls.server = subprocess.Popen([sys.executable, str(HERE / "virtual_pad_server.py")], stdout=log, stderr=log)
        for _ in range(50):
            time.sleep(0.1)
            try:
                cls.send("ping")
                time.sleep(1.0)      # the bus takes a moment to show the pad to XInput
                return
            except OSError:
                continue
        raise RuntimeError("the virtual pad server did not start")

    @classmethod
    def send(cls, *commands: str) -> list[str]:
        with socket.create_connection((cls.HOST, cls.PORT), timeout=20) as connection:
            connection.sendall(("\n".join(commands) + "\n").encode())
            replies = b""
            while replies.count(b"\n") < len(commands):
                chunk = connection.recv(4096)
                if not chunk:
                    break
                replies += chunk
        return replies.decode("utf-8", "replace").strip().splitlines()


class Game:
    def __init__(self, folder: Path = DEFAULT_GAME):
        self.folder = Path(folder)
        self.process: subprocess.Popen | None = None
        self.handle = None
        self.pid = 0

    # ------------------------------------------------------------------ the process

    def start(self, wait_seconds: float = 60.0):
        if self.running_elsewhere():
            raise RuntimeError("a swkotor.exe is already running")
        self.process = subprocess.Popen([str(self.folder / "swkotor.exe")], cwd=self.folder)
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            self.pid = self.find_pid()
            if self.pid:
                self.handle = kernel32.OpenProcess(0x0010 | 0x0400, False, self.pid)
                if self.handle and self.read(GUI_MANAGER, 4) is not None:
                    return self
            time.sleep(0.05)
        raise RuntimeError("the game did not start")

    @staticmethod
    def running_elsewhere() -> bool:
        return Game.find_pid() != 0

    @staticmethod
    def find_pid() -> int:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq swkotor.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, errors="replace").stdout
        for line in out.splitlines():
            parts = line.strip().strip('"').split('","')
            if len(parts) > 1 and parts[0].lower() == "swkotor.exe":
                return int(parts[1])
        return 0

    def alive(self) -> bool:
        return self.pid != 0 and self.find_pid() == self.pid

    def stop(self):
        if self.pid:
            subprocess.run(["taskkill", "/PID", str(self.pid), "/F"], capture_output=True)
            for _ in range(100):
                if not self.find_pid():
                    break
                time.sleep(0.05)
        if self.handle:
            kernel32.CloseHandle(self.handle)
        self.handle = None
        self.pid = 0

    # ------------------------------------------------------------------ the foreground

    def windows(self) -> list[int]:
        found: list[int] = []

        def visit(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        user32.EnumWindows(EnumWindowsProc(visit), 0)
        return found

    def in_front(self) -> bool:
        hwnd = user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == self.pid

    def bring_forward(self) -> bool:
        if self.in_front():
            return True
        for hwnd in self.windows():
            # A lone Alt lets a background process take the foreground. It is a key press, but no
            # window acts on it: Alt alone only arms the menu bar of a window that has one.
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x12, 0, 2, 0)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.1)
            if self.in_front():
                return True
        return False

    # ------------------------------------------------------------------ memory

    def read(self, address: int, size: int) -> bytes | None:
        buffer = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(self.handle, address, buffer, size, ctypes.byref(got)) or got.value != size:
            return None
        return buffer.raw

    def u32(self, address: int) -> int | None:
        raw = self.read(address, 4)
        return struct.unpack("<I", raw)[0] if raw else None

    def manager(self) -> int:
        return self.u32(GUI_MANAGER) or 0

    def panels(self) -> list[int]:
        """Every panel's address, bottom first."""
        manager = self.manager()
        if not manager:
            return []
        array, count = self.u32(manager + MANAGER_PANELS), self.u32(manager + MANAGER_COUNT)
        if not array or not count or count > 64:
            return []
        raw = self.read(array, count * 4)
        return list(struct.unpack(f"<{count}I", raw)) if raw else []

    def panel_names(self) -> list[str]:
        names = []
        for panel in self.panels():
            table = self.u32(panel) or 0
            names.append(PANEL_NAMES.get(table, f"{table:08X}"))
        return names

    def top(self) -> str:
        names = self.panel_names()
        return names[-1] if names else ""

    def movie_player(self) -> int:
        return self.u32(MOVIE_PLAYER) or 0

    # ------------------------------------------------------------------ frames

    def shot(self, path: Path) -> bool:
        """One frame of the desktop with ddagrab: GDI capture is stale in fullscreen."""
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "ddagrab=framerate=30,hwdownload,format=bgra", "-frames:v", "1", str(path)],
                       capture_output=True, timeout=30)
        return path.exists()

    # ------------------------------------------------------------------ the pad

    def press(self, *commands: str) -> list[str]:
        if not self.bring_forward():
            raise RuntimeError("the game is not in front: no input sent")
        return Pad.send(*commands)


def wait_for(test, seconds: float, step: float = 0.01):
    deadline = time.time() + seconds
    while time.time() < deadline:
        value = test()
        if value:
            return value
        time.sleep(step)
    return None


def game_folder() -> Path:
    return Path(os.environ.get("KMRP_TEST_GAME", str(DEFAULT_GAME)))
