#!/usr/bin/env python3
"""Do the controller prompts actually appear, and do they leave on keyboard use?

The badge is a texture swap on an existing button's BORDER.FILL, so it is
visible as a pixel change and invisible to any counter. This drives the pad,
screenshots, then types on the keyboard and screenshots again, and reports how
much of the screen changed each way.

This exists because the whole prompt layer was dark in native mode:
UpdateK1ControllerPrompts was reachable only from the legacy DispatchMenuInputK1
hook, and the device-activity flag it consults was raised only from
PollXInputK1, which is also legacy. Tables, textures and mode logic were all
present and all unreachable, and nothing noticed because nothing looked.

Requires the virtual pad server, the game running, and the in-game menu open on
a screen that has badge bindings (the Options tab does).

Usage:
    python testing/controller/probe_prompts.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import ctypes
import os
import re
import socket
import subprocess
import time

HOST, PORT = "127.0.0.1", 8787
LOG = os.path.join(r"C:\Star Wars - KotOR", "kmrp-native-joystick.log")
SHOTS = os.environ.get("TEMP", ".")


def pad(command):
    sock = socket.create_connection((HOST, PORT), timeout=5)
    sock.sendall((command + "\n").encode())
    reply = sock.recv(64).decode().strip()
    sock.close()
    if reply.startswith("err"):
        raise RuntimeError(f"{command}: {reply}")
    return reply


def tap(button, hold=0.2, settle=1.2):
    pad("press " + button)
    time.sleep(hold)
    pad("release " + button)
    time.sleep(settle)


def shot(name):
    path = os.path.join(SHOTS, f"kmrp_prompt_{name}.png")
    subprocess.run(["powershell", "-NoProfile", "-Command",
        "Add-Type -AssemblyName System.Drawing,System.Windows.Forms;"
        "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
        "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($bmp);"
        "$g.CopyFromScreen(0,0,0,0,$bmp.Size);"
        f"$bmp.Save('{path}')"], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path


def changed(before, after):
    """Percentage of pixels that differ, at a coarse stride."""
    from PIL import Image
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    if a.size != b.size:
        return 100.0
    pa, pb = a.load(), b.load()
    step = 4
    total = diff = 0
    for y in range(0, a.size[1], step):
        for x in range(0, a.size[0], step):
            total += 1
            r1, g1, b1 = pa[x, y]
            r2, g2, b2 = pb[x, y]
            if abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2) > 24:
                diff += 1
    return 100.0 * diff / total if total else 0.0


def type_key():
    """A real keyboard press, which must send the prompts away."""
    user32 = ctypes.windll.user32
    for scancode in (0x1F,):          # S: bound to nothing destructive in menus
        user32.keybd_event(0, scancode, 0x0008, 0)
        time.sleep(0.05)
        user32.keybd_event(0, scancode, 0x0008 | 0x0002, 0)
    time.sleep(1.2)


def counters():
    try:
        with open(LOG, "r", errors="replace") as handle:
            text = handle.read()
        pad_active = re.findall(r"\bpad=(\d+)", text)
        prompts = re.findall(r"\bprm=(\d+)", text)
        return (int(pad_active[-1]) if pad_active else None,
                int(prompts[-1]) if prompts else None)
    except OSError:
        return (None, None)


def main() -> int:
    print("counters (pad-active frames, prompt updates):", counters())

    # Pad first: any button marks it the live device.
    tap("RIGHT")
    tap("LEFT")
    time.sleep(0.8)
    with_pad = shot("pad")
    print("after pad activity:", counters())

    # Then the keyboard, which must take the badges away.
    type_key()
    with_keyboard = shot("keyboard")
    print("after keyboard:    ", counters())

    delta = changed(with_pad, with_keyboard)
    print(f"\nscreen changed between pad-active and keyboard-active: {delta:.2f}%")

    # And back again.
    tap("RIGHT")
    time.sleep(0.8)
    back = shot("padagain")
    restored = changed(with_keyboard, back)
    print(f"screen changed going back to the pad:                   {restored:.2f}%")

    if delta > 0.02 and restored > 0.02:
        print("\nPASS: the badges appear with the pad and leave on keyboard use")
        return 0
    print("\nFAIL: no visible difference -- the prompt layer is not drawing")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
