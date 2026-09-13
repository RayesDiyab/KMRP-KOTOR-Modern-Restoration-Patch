#!/usr/bin/env python3
"""Record rapid Equipment <-> Inventory switching as an animated GIF.

The reported symptom is a stall with a grey flash when switching to these two
screens. Timing it only says how long the screen took to settle; it does not
show what is on screen while it settles, which is the part being complained
about. So this captures frames as fast as the display can be grabbed while
clicking between the two tabs, and writes them out to look at.

Clicks here are deliberately NOT the shared `click` helper: that one sleeps
400 ms before pressing, which is slower than the switching being investigated.

Usage:
    python testing/controller/record_tab_switch.py [--switches 6] [--scale 4]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageGrab

GAME_DIR = Path(r"C:\Star Wars - KotOR")
EQUIPMENT = (2880, 32)
INVENTORY = (2954, 32)

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def click(x: int, y: int) -> None:
    """A press with no settling sleep, so the switch is as fast as a player's."""
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--switches", type=int, default=6)
    parser.add_argument("--scale", type=int, default=4,
                        help="downscale factor for the recording")
    parser.add_argument("--out", type=Path,
                        default=Path(os.environ.get("TEMP", ".")) / "kmrp-tab-switch.gif")
    parser.add_argument("--hold", type=float, default=0.9,
                        help="seconds to dwell on each screen")
    arguments = parser.parse_args()

    size = (3440 // arguments.scale, 1440 // arguments.scale)
    frames: list[tuple[float, Image.Image]] = []
    start = time.perf_counter()
    targets = [EQUIPMENT, INVENTORY] * arguments.switches
    deadline = start
    index = 0

    while index < len(targets):
        now = time.perf_counter()
        if now >= deadline:
            click(*targets[index])
            index += 1
            deadline = now + arguments.hold
        frames.append((now - start, ImageGrab.grab().convert("RGB").resize(size)))

    rate = len(frames) / (time.perf_counter() - start)
    print(f"captured {len(frames)} frames at {rate:.0f} fps, "
          f"{arguments.switches} switches each way")

    durations = []
    for i in range(len(frames)):
        nxt = frames[i + 1][0] if i + 1 < len(frames) else frames[i][0] + 0.04
        durations.append(max(20, int((nxt - frames[i][0]) * 1000)))
    frames[0][1].save(arguments.out, save_all=True,
                      append_images=[f[1] for f in frames[1:]],
                      duration=durations, loop=0, optimize=True)
    print(f"wrote {arguments.out}  "
          f"({arguments.out.stat().st_size/1048576:.1f} MB)")

    # Also report, per frame, how grey it is -- the flash is the thing being
    # looked for, and a number makes it checkable rather than a matter of
    # opinion.
    import numpy as np
    print("\n  t(s)   saturation  brightness")
    for t, image in frames[::max(1, len(frames)//40)]:
        a = np.asarray(image, dtype=np.float64)
        sat = (a.max(axis=2) - a.min(axis=2)).mean()
        print(f"  {t:5.2f}   {sat:8.1f}   {a.mean():9.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
