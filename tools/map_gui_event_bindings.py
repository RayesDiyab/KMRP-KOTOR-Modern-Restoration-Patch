#!/usr/bin/env python3
"""Every GUI event binding KOTOR registers at runtime, read out of the image.

`map_retained_gui_events.py` reads the *other* half of this system: the
`HandleInputEvent` dispatchers compiled into each class's vtable. That survey was
incomplete in a way that mattered, because a control can also have handlers
**registered onto it** at construction time:

    CSWGuiControl::AddEvent(eventCode, receiver, handler)      0x0041AB20

appends a 12-byte `{receiver, handler, eventCode}` entry to the control's table
at `+0x38`, with the count at `+0x3C`. `CSWGuiControl::HandleInputEvent`
(`0x00418750`) walks that table for any event its class did not handle itself:

    00418790  cmp  dword ptr [eax+8], edi    ; entry's code == this event?
    00418795  mov  ebp, [eax+4]              ; entry's handler
    0041879D  add  eax, 0xC                  ; next entry

So "which panel implements event X" has two answers, and the dispatcher survey
only ever gave one of them. The 515 `AddEvent` call sites give the other, and
they are static: arguments are pushed in reverse, so the three pushes before each
call read handler, receiver, eventCode from the top down.

The practical payoff is knowing which buttons are *bound to nothing anywhere*.
B (`0x28`), Black (`0x2B`) and the scroll pair (`0x31`/`0x32`) have zero
registrations in the whole executable; X (`0x29`) has exactly one. Those are free
for KMRP to drive without colliding with retained behaviour.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import bisect
import sqlite3
import struct
import sys
from collections import Counter
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "build" / "research" / "Kotor-Patch-Manager" / "AddressDatabases" / "kotor1_0_3.db"
IMAGE_BASE = 0x00400000
ADD_EVENT = 0x0041AB20

# Only the codes with evidence behind them are named. The rest are printed as
# bare numbers on purpose: a guessed name in a reference document is worse than
# no name, because the next reader cannot tell which is which.
EVENT_NAMES = {
    0x00: "MouseEnter?", 0x01: "MouseLeave?",
    0x27: "A", 0x28: "B", 0x29: "X", 0x2A: "Y", 0x2B: "Black",
    0x2F: "DpadLeft", 0x30: "DpadRight", 0x31: "ScrollUp", 0x32: "ScrollDown",
    0x39: "DescUp", 0x3A: "DescDown",
    0x3D: "ScrollUp'", 0x3E: "ScrollDown'", 0x3F: "DpadLeft'", 0x40: "DpadRight'",
}


def symbols():
    """(sorted addresses, "Class::Function" by index) from the KPM database."""
    connection = sqlite3.connect(DATABASE)
    rows = connection.execute(
        "SELECT class_name, function_name, address FROM functions ORDER BY address").fetchall()
    connection.close()
    return [r[2] for r in rows], [f"{r[0]}::{r[1]}" for r in rows]


def call_sites(data: bytes, target: int) -> list[int]:
    """Direct `call rel32` sites, which encode target - (site + 5)."""
    sites = []
    for offset in range(len(data) - 5):
        if data[offset] == 0xE8:
            site = offset + IMAGE_BASE
            if site + 5 + struct.unpack_from("<i", data, offset + 1)[0] == target:
                sites.append(site)
    return sites


def bindings(data: bytes):
    """(owner, event code, handler, call site) for every resolvable AddEvent call."""
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    addresses, names = symbols()
    resolved, skipped = [], []
    for site in call_sites(data, ADD_EVENT):
        pushes = []
        # Widening windows: most sites push three literals back to back, but a
        # few compute an argument first and need more room to reach all three.
        for window in (48, 64, 96, 128):
            pushes = []
            for instruction in disassembler.disasm(
                    data[site - window - IMAGE_BASE: site - IMAGE_BASE], site - window):
                if instruction.mnemonic == "push":
                    pushes.append(instruction.op_str)
            if len(pushes) >= 3:
                break
        if len(pushes) < 3:
            skipped.append(site)
            continue
        handler, _receiver, code = pushes[-3], pushes[-2], pushes[-1]
        try:
            value = int(code, 0)
        except ValueError:
            skipped.append(site)
            continue
        # An event code is a small integer. Anything image-sized means the window
        # picked up an unrelated push and the site is reported, not guessed at.
        if not 0 <= value <= 0xFFFF:
            skipped.append(site)
            continue
        index = bisect.bisect_right(addresses, site) - 1
        resolved.append((names[index] if index >= 0 else "?", value, handler, site))
    return resolved, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("executable", type=Path, nargs="?",
                        default=Path(r"C:\Star Wars - KotOR\swkotor.exe"))
    parser.add_argument("--code", type=lambda v: int(v, 0), action="append",
                        help="list every binding for this event code (repeatable)")
    arguments = parser.parse_args()

    resolved, skipped = bindings(arguments.executable.read_bytes())
    counts = Counter(code for _, code, _, _ in resolved)

    print(f"{len(resolved)} bindings resolved from {len(resolved) + len(skipped)} "
          f"AddEvent call sites")
    if skipped:
        print("not resolved (arguments were not three literals in the window): " +
              ", ".join(f"0x{s:08X}" for s in skipped))
    print()
    print("event".ljust(8) + "name".ljust(14) + "bindings")
    print("-" * 32)
    for code in sorted(counts):
        print(f"0x{code:03X}".ljust(8) + EVENT_NAMES.get(code, "").ljust(14) + str(counts[code]))

    print()
    for code in (0x28, 0x2B, 0x31, 0x32):
        if code not in counts:
            print(f"0x{code:02X} {EVENT_NAMES[code]}: no bindings anywhere in the image.")

    for code in arguments.code or []:
        print(f"\n=== 0x{code:02X} {EVENT_NAMES.get(code, '')}")
        for panel, value, handler, site in resolved:
            if value == code:
                print(f"    {panel:<50} handler {handler:<12} at 0x{site:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
