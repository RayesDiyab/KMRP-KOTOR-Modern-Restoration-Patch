#!/usr/bin/env python3
"""Time each menu tab by when it reaches its FINAL appearance.

An earlier version of this measurement called a screen "settled" as soon as two
consecutive frames matched, sampled at 160x68. That is wrong for a screen which
fills in progressively: each item and icon appearing is a small change at that
scale, so the very first plateau reads as finished while the list is still
populating. It reported Inventory and Map as equally fast, which contradicts
what the screen actually does.

This instead captures the whole transition, takes the LAST frame as the
reference, and reports the first moment the screen is within a threshold of what
it ends up looking like. A screen that finishes in one step and a screen that
dribbles in over a second are then distinguishable.

Usage:
    python testing/controller/bench_tab_convergence.py [--tabs Map,Inventory]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import time

import numpy as np
from PIL import ImageGrab

ICONS = {
    "Equipment": (2880, 32),
    "Inventory": (2954, 32),
    "Character": (3030, 32),
    "Abilities": (3104, 32),
    "Messages":  (3178, 32),
    "Journal":   (3251, 32),
    "Map":       (3324, 32),
    "Options":   (3397, 32),
}

# The panel interior including the list column, which is where progressive
# population would show. Kept modest so sampling stays fast.
REGION = (300, 200, 1900, 1100)


def click(x: int, y: int) -> None:
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)


def grab() -> np.ndarray:
    return np.asarray(ImageGrab.grab(bbox=REGION).convert("RGB").resize((400, 225)),
                      dtype=np.int16)


def difference(a: np.ndarray, b: np.ndarray) -> float:
    return float((np.abs(a - b).sum(axis=2) > 24).mean() * 100.0)


def time_tab(name: str, seconds: float, threshold: float):
    # Sample BEFORE clicking. Clicking first meant the very first grab was
    # already the finished screen, and every tab "converged" at 0.00s -- a
    # measurement with no resolution at all rather than a fast game.
    frames = []
    start = time.perf_counter()
    while time.perf_counter() - start < 0.25:
        frames.append((time.perf_counter() - start, grab()))
    clicked = time.perf_counter() - start
    click(*ICONS[name])
    while time.perf_counter() - start < seconds:
        frames.append((time.perf_counter() - start, grab()))
    frames = [(t - clicked, f) for t, f in frames]
    final = frames[-1][1]
    converged = None
    for when, frame in frames:
        if when < 0:
            continue
        if difference(frame, final) <= threshold:
            converged = when
            break
    # How much of the transition happened after the first plateau -- the number
    # the old measurement was blind to.
    plateau = None
    for i in range(1, len(frames)):
        if frames[i][0] < 0:
            continue
        if difference(frames[i - 1][1], frames[i][1]) < 1.0:
            plateau = frames[i][0]
            break
    return converged, plateau, len(frames)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tabs", default="Map,Inventory,Equipment,Journal")
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--threshold", type=float, default=1.5)
    parser.add_argument("--repeats", type=int, default=2)
    arguments = parser.parse_args()

    print(f"region {REGION}, converged = within {arguments.threshold}% of the "
          f"final frame\n")
    print(f"  {'tab':11s} {'converged':>10s} {'first plateau':>14s}  frames")
    for _ in range(arguments.repeats):
        for name in arguments.tabs.split(","):
            converged, plateau, count = time_tab(name, arguments.seconds,
                                                 arguments.threshold)
            c = f"{converged:.2f}s" if converged is not None else "  n/a"
            p = f"{plateau:.2f}s" if plateau is not None else "  n/a"
            print(f"  {name:11s} {c:>10s} {p:>14s}  {count}")
            time.sleep(0.5)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
