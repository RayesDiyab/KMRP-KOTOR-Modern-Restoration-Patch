#!/usr/bin/env python3
"""A virtual Xbox controller that stays alive between commands.

Verifying the controller UI needs a gamepad that KOTOR can see. A physical one
cannot be driven from a script, and a `vgamepad` pad only exists while the Python
object that created it is alive -- so a one-shot script creates a controller,
presses a button and destroys it again before the game has polled. This holds one
pad open and takes commands over a loopback socket instead.

It needs the ViGEmBus driver, which turns the pad into a real XInput device: the
game's own `XInputGetState` sees it on a slot exactly as it would a physical
controller, which is the whole point -- `IsControllerInputActiveK1()` will not go
true for synthesised keystrokes.

Commands, one per line, replying "ok" or "err <reason>":

    tap <BUTTON> [seconds]   press and release
    press <BUTTON>           hold
    release <BUTTON>         let go
    dpad <up|down|left|right> [seconds]
    lstick <x> <y>           floats in [-1, 1]
    rstick <x> <y>
    triggers <l> <r>         floats in [0, 1]
    reset                    everything to neutral
    state                    report what is currently held
    ping                     liveness check
    quit                     drop the pad and exit

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import socket
import sys
import threading
import time

HOST = "127.0.0.1"
PORT = 8787

import vgamepad as vg

BUTTONS = {
    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "LS": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "RS": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    "UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
}

pad = vg.VX360Gamepad()
held = set()
lock = threading.Lock()


def handle(line: str) -> str:
    parts = line.split()
    if not parts:
        return "err empty"
    verb = parts[0].lower()

    if verb == "ping":
        return "ok"
    if verb == "wait":
        # Screen transitions take time the game does not report. Waiting here
        # rather than between connections keeps a navigation sequence inside one
        # command batch, so nothing else can steal focus part-way through it.
        time.sleep(min(10.0, float(parts[1]) if len(parts) > 1 else 1.0))
        return "ok"
    if verb == "quit":
        return "bye"
    if verb == "state":
        return "ok held=" + (",".join(sorted(held)) or "none")

    if verb in ("tap", "press", "release", "dpad"):
        name = parts[1].upper() if len(parts) > 1 else ""
        if verb == "dpad":
            name = {"UP": "UP", "DOWN": "DOWN",
                    "LEFT": "LEFT", "RIGHT": "RIGHT"}.get(name, "")
        if name not in BUTTONS:
            return f"err unknown button {parts[1] if len(parts) > 1 else ''!r}"
        button = BUTTONS[name]
        if verb == "press":
            pad.press_button(button=button); pad.update(); held.add(name)
            return "ok"
        if verb == "release":
            pad.release_button(button=button); pad.update(); held.discard(name)
            return "ok"
        # tap / dpad: a real press has a dwell. The module's own repeat logic
        # keys off held duration, so a zero-length tap is not representative.
        seconds = float(parts[2]) if len(parts) > 2 else 0.08
        pad.press_button(button=button); pad.update()
        time.sleep(seconds)
        pad.release_button(button=button); pad.update()
        time.sleep(0.05)
        return "ok"

    if verb in ("lstick", "rstick"):
        x, y = float(parts[1]), float(parts[2])
        setter = pad.left_joystick_float if verb == "lstick" else pad.right_joystick_float
        setter(x_value_float=max(-1.0, min(1.0, x)),
               y_value_float=max(-1.0, min(1.0, y)))
        pad.update()
        return "ok"

    if verb == "triggers":
        pad.left_trigger_float(value_float=max(0.0, min(1.0, float(parts[1]))))
        pad.right_trigger_float(value_float=max(0.0, min(1.0, float(parts[2]))))
        pad.update()
        return "ok"

    if verb == "reset":
        pad.reset(); pad.update(); held.clear()
        return "ok"

    return f"err unknown command {verb!r}"


def main() -> int:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(4)
    print(f"virtual pad listening on {HOST}:{PORT}", flush=True)
    # Give the driver a moment to enumerate before anything is sent.
    time.sleep(0.5)
    pad.reset()
    pad.update()

    while True:
        connection, _ = server.accept()
        with connection:
            data = connection.recv(4096).decode("utf-8", "replace").strip()
            for line in data.splitlines():
                with lock:
                    try:
                        reply = handle(line)
                    except Exception as error:      # never let one bad command kill the pad
                        reply = f"err {error}"
                print(f"{line!r} -> {reply}", flush=True)
                connection.sendall((reply + "\n").encode())
                if reply == "bye":
                    return 0


if __name__ == "__main__":
    raise SystemExit(main())
