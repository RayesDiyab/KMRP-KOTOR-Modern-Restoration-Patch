#!/usr/bin/env python3
"""Time the first Inventory open after a cold load, with and without the TPC.

Why this shape:

  * It must be the FIRST open. The engine keeps the texture once loaded, so any
    later open measures nothing but a cache hit.
  * It must sample fast. A PowerShell screenshot costs ~680 ms per frame, which
    cannot resolve the ~100 ms effect being measured; `ImageGrab` in-process is
    around 40 ms.
  * It must relaunch between arms, because a cold load is the whole point.

Reports the interval from the click to the first pair of consecutive frames that
match, which is when the screen has finished appearing.

Usage:
    python testing/controller/bench_menu_textures.py --arms tpc,tga --repeats 2

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_native_controller as E                      # noqa: E402

from PIL import ImageGrab                              # noqa: E402

GAME_DIR = Path(r"C:\Star Wars - KotOR")
GAME_EXE = GAME_DIR / "swkotor.exe"
OVERRIDE = GAME_DIR / "override"
CANDIDATE = Path(r"C:\Users\diyab\Desktop\KMRP-tpc-test\lbl_invent_4096x2048_dxt5.tpc")
INVENTORY_ICON = (2954, 32)


def kill_game() -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Stop-Process -Name swkotor -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)
    time.sleep(3)


def launch_and_load() -> bool:
    subprocess.Popen([str(GAME_EXE)], cwd=str(GAME_DIR))
    time.sleep(28)
    E.click(*E.CLICK_LOAD_GAME)
    time.sleep(6)
    E.click(*E.CLICK_LOAD)
    time.sleep(9)
    alive = subprocess.check_output(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process swkotor -ErrorAction SilentlyContinue).Id"]).decode().strip()
    return bool(alive)


def frame():
    return ImageGrab.grab().convert("RGB").resize((172, 72))


def changed(a, b) -> float:
    pa, pb = a.load(), b.load()
    total = diff = 0
    for y in range(a.size[1]):
        for x in range(a.size[0]):
            total += 1
            if sum(abs(p - q) for p, q in zip(pa[x, y], pb[x, y])) > 24:
                diff += 1
    return 100.0 * diff / total


def measure_open(seconds: float = 6.0) -> tuple[float, float]:
    """(seconds until the screen stopped changing, total change from gameplay)."""
    first = frame()
    start = time.perf_counter()
    E.click(*INVENTORY_ICON)
    samples = []
    while time.perf_counter() - start < seconds:
        samples.append((time.perf_counter() - start, frame()))
    settled = float("nan")
    # Skip the click helper's own ~0.5s sleep before looking for stability.
    for i in range(1, len(samples)):
        if samples[i][0] < 0.7:
            continue
        if changed(samples[i - 1][1], samples[i][1]) < 1.0:
            settled = samples[i][0]
            break
    return settled, changed(first, samples[-1][1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arms", default="tpc,tga")
    parser.add_argument("--repeats", type=int, default=2)
    arguments = parser.parse_args()

    installed = OVERRIDE / "lbl_invent.tpc"
    results: dict[str, list[float]] = {}

    for arm in arguments.arms.split(","):
        if arm == "tpc":
            shutil.copy2(CANDIDATE, installed)
        else:
            installed.unlink(missing_ok=True)
        size = installed.stat().st_size / 1048576 if installed.exists() else 0
        print(f"\n=== arm '{arm}'  (lbl_invent.tpc "
              f"{'present %.1f MB' % size if size else 'absent, TGA used'})")

        for run in range(arguments.repeats):
            kill_game()
            if not launch_and_load():
                print(f"  run {run + 1}: game did not reach gameplay; skipped")
                continue
            settled, delta = measure_open()
            results.setdefault(arm, []).append(settled)
            print(f"  run {run + 1}: settled {settled:5.2f} s   "
                  f"screen changed {delta:5.1f}%")

    print("\n--- summary")
    for arm, values in results.items():
        good = [v for v in values if v == v]
        if good:
            print(f"  {arm:4s} median {statistics.median(good):5.2f} s  "
                  f"from {len(good)} run(s): "
                  + ", ".join(f"{v:.2f}" for v in good))
        else:
            print(f"  {arm:4s} no usable samples")
    kill_game()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
