#!/usr/bin/env python3
"""Which KOTOR screens are live right now, read from the game's own memory.

Navigating the game to verify prompts needs a way to know where you are. A
screenshot answers that only for a human, needs the window focused and on top,
and cannot say WHICH panel class drew what is on screen -- which is the thing
that actually matters here, because badges are bound per panel class.

Every live panel is a heap object whose first dword is its vtable, so scanning
committed private memory for each known vtable says exactly which panels exist.
Hits inside the game image (constructors storing the vtable) and inside the
controller module (its own switch statements comparing against it) are excluded.

    python testing/controller/where_am_i.py --pid 11896

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_prompts import Process, MODULE_SOURCE  # noqa: E402

# The game image, and the controller module's own address range.
SKIP = [(0x00400000, 0x00400000 + 0x480000), (0x78C60000, 0x78D00000)]


def panel_vtables() -> dict:
    text = MODULE_SOURCE.read_text(encoding="utf-8")
    return {name: int(value, 0) for name, value in re.findall(
        r"constexpr\s+std::uintptr_t\s+(\w+_PANEL_VTABLE)\s*=\s*(0x[0-9A-Fa-f]+)\s*;", text)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--all", action="store_true",
                        help="also list panels that are not currently instantiated")
    arguments = parser.parse_args()

    process = Process(arguments.pid)
    # One pass over memory for all vtables at once: scanning ~40 times over a
    # few hundred megabytes is minutes; scanning once is seconds.
    vtables = panel_vtables()
    wanted = {value: name for name, value in vtables.items()}
    import struct
    found = {name: [] for name in vtables}
    needles = {struct.pack("<I", value): value for value in wanted}

    for base, size in process.regions():
        if any(low <= base < high for low, high in SKIP):
            continue
        data = process.read(base, min(size, 64 * 1024 * 1024))
        if not data:
            continue
        for needle, value in needles.items():
            start = 0
            while True:
                index = data.find(needle, start)
                if index < 0:
                    break
                if index % 4 == 0:
                    found[wanted[value]].append(base + index)
                start = index + 4

    live = {name: hits for name, hits in found.items() if hits}
    print(f"live panels ({len(live)} of {len(vtables)}):")
    for name in sorted(live):
        print(f"  {name:<46}{', '.join(hex(a) for a in live[name][:4])}")
    if arguments.all:
        print("\nnot instantiated:")
        for name in sorted(set(vtables) - set(live)):
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
