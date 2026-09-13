#!/usr/bin/env python3
"""Catch the grey flash reported when switching to Equipment or Inventory.

A full-screen grab of a 3440x1440 display runs at about 11 fps, which is too
slow to be sure a flash shorter than ~90 ms even happened. Grabbing a small
region instead runs several times faster, and a flash is a whole-screen event so
a sample of it is enough to detect.

Greyness is measured, not eyeballed: the menus are strongly blue (saturation
around 37), gameplay in a corridor is around 22, and a grey frame would be far
lower. The script reports the least saturated frames it saw and when.

Usage:
    python testing/controller/hunt_grey_flash.py [--switches 8]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import pathlib
import tempfile
import time

import numpy as np
from PIL import ImageGrab

EQUIPMENT = (2880, 32)
INVENTORY = (2954, 32)
# A patch of the panel interior, away from the tab strip and the item list, so
# what is sampled is mostly background art.
REGION = (900, 400, 1700, 800)


def click(x: int, y: int) -> None:
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--switches", type=int, default=8)
    parser.add_argument("--hold", type=float, default=0.7)
    arguments = parser.parse_args()

    # How fast can this region actually be sampled?
    probe = time.perf_counter()
    for _ in range(20):
        ImageGrab.grab(bbox=REGION)
    rate = 20 / (time.perf_counter() - probe)
    print(f"sampling {REGION} at {rate:.0f} fps "
          f"({1000/rate:.0f} ms per frame)\n")

    targets = [EQUIPMENT, INVENTORY] * arguments.switches
    samples: list[tuple[float, float, float]] = []
    start = time.perf_counter()
    deadline = start
    index = 0
    clicks: list[float] = []

    while index < len(targets):
        now = time.perf_counter()
        if now >= deadline:
            click(*targets[index])
            clicks.append(now - start)
            index += 1
            deadline = now + arguments.hold
        grabbed = ImageGrab.grab(bbox=REGION).convert("RGB")
        frame = np.asarray(grabbed, dtype=np.int16)
        saturation = float((frame.max(axis=2) - frame.min(axis=2)).mean())
        brightness = float(frame.mean())
        samples.append((now - start, saturation, brightness))
        # Keep the evidence. A dark frame here is the reported flash, and what
        # it actually looks like decides whether it is an unpainted panel or a
        # cleared backbuffer.
        if brightness < 12.0:
            out = pathlib.Path(tempfile.gettempdir()) / f"kmrp_flash_{now-start:06.2f}.png"
            ImageGrab.grab().save(out)
            grabbed.save(str(out).replace(".png", "_region.png"))

    print(f"{len(samples)} samples over {samples[-1][0]:.1f} s, "
          f"{len(clicks)} clicks\n")

    saturations = [s[1] for s in samples]
    baseline = float(np.median(saturations))
    print(f"median saturation (the settled menu): {baseline:.1f}")

    ordered = sorted(samples, key=lambda s: s[1])
    print("\nleast saturated frames -- a grey flash would appear here:")
    for t, sat, bright in ordered[:10]:
        nearest = min((abs(t - c), c) for c in clicks)[1]
        print(f"  t={t:5.2f}s  saturation {sat:5.1f}  brightness {bright:5.1f}"
              f"   ({t - nearest:+.2f}s from a click)")

    flashes = [s for s in samples if s[1] < baseline * 0.5]
    print(f"\nframes below half the settled saturation: {len(flashes)}")
    if not flashes:
        print("  none -- no grey flash occurred at this sampling rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
