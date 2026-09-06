#!/usr/bin/env python3
"""Focus the game, then send a sequence of virtual-pad commands.

Two things make this necessary rather than just calling `pad.py`:

  * KOTOR runs fullscreen and minimises itself when it loses focus, and every
    shell command run from the agent's side takes focus for a moment. So the
    window has to be restored and re-fronted immediately before input is sent.
  * The controller module ignores input unless the game is the foreground window
    (`GameHasFocus()` in K1XboxControlsXInput.cpp compares the foreground
    window's process id to its own), so sending to an unfocused game silently
    does nothing -- which looks exactly like the pad not working.

    python testing/controller/drive.py "dpad down" "dpad down" "tap A"

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pad import send  # noqa: E402

SW_RESTORE = 9
GAME_TITLE = "Star Wars: Knights of the Old Republic"

user32 = ctypes.windll.user32


def find_game() -> int:
    """The game's top-level window, by exact title."""
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def each(handle, _):
        length = user32.GetWindowTextLengthW(handle)
        if length:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(handle, buffer, length + 1)
            # The process owns TWO windows with this exact title and only one of
            # them is the visible render window; picking the hidden one made
            # SetForegroundWindow fail silently.
            if buffer.value == GAME_TITLE and user32.IsWindowVisible(handle):
                found.append(handle)
        return True

    user32.EnumWindows(each, 0)
    return found[0] if found else 0


def focus(handle: int, settle: float = 1.2) -> bool:
    if not handle:
        return False
    if user32.IsIconic(handle):
        user32.ShowWindow(handle, SW_RESTORE)
        time.sleep(0.6)
    # AttachThreadInput lets SetForegroundWindow succeed from a background
    # process; without it Windows silently refuses and only flashes the taskbar.
    target = user32.GetWindowThreadProcessId(handle, None)
    current = ctypes.windll.kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(current, target, True)
    # Windows only honours SetForegroundWindow from a process that "owns" recent
    # input. Synthesising a harmless key edge first satisfies that rule; without
    # it the call returns success-ish and merely flashes the taskbar button.
    user32.keybd_event(0x12, 0, 0, 0)          # VK_MENU down
    user32.keybd_event(0x12, 0, 0x0002, 0)     # VK_MENU up
    user32.BringWindowToTop(handle)
    user32.SetForegroundWindow(handle)
    user32.SetActiveWindow(handle)
    user32.AttachThreadInput(current, target, False)
    time.sleep(settle)
    return user32.GetForegroundWindow() == handle


def main() -> int:
    commands = sys.argv[1:]
    handle = find_game()
    if not focus(handle):
        print("could not focus the game window; input would be ignored")
        return 1
    # The module rescans XInput slots at most every two seconds, so give it a
    # beat after focus before expecting it to have found the pad.
    time.sleep(0.5)
    if commands:
        for command, reply in zip(commands, send(commands)):
            print(f"{command:<24}{reply}")
    else:
        print("focused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
