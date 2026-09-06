#!/usr/bin/env python3
"""The retained console input path, from physical button down to GUI event.

Two other tools read the receiving end: `map_retained_gui_events.py` reads the
`HandleInputEvent` dispatchers, and `map_gui_event_bindings.py` reads the
handlers registered by `AddEvent`. Both answer "what would happen if this event
arrived". Neither answers the question that actually matters, which is **what
ever sends one**.

This tool reads the sending end, and finds two layers of it.

**Layer 1 -- the panel button thunks.** Five four-instruction functions sit
consecutively at `0x0040B640`:

    0040B640  mov eax,[ecx] / push 1 / push 0x27 / call [eax+0x3C] / ret 4

one per Xbox face button (A `0x27`, B `0x28`, X `0x29`, Y `0x2A`, Black `0x2B`),
each occupying vtable slots `+0x50`, `+0x54`, `+0x58`, `+0x5C`, `+0x60` on 76
panel classes. **Nothing in the executable calls any of them.** They are the
console entry points, still present in every panel's vtable, wired to nothing.

**Layer 2 -- the client action router.** `CClientExoAppInternal::HandleInputEvent`
(`0x00621210`) dispatches game actions through a small direct table at
`0x00622128` (ids `0x01`..`0x0C`) and an indexed table at `0x006221FC` /
`0x00622154` (ids `0x19`..`0x108`). Handlers there come in **pairs**: a low id and
a high one share a body, e.g. `0x09` and `0xCE` both reach the handler that calls
`ChangeCharacterToNextLivingPartyMember`. The low ids are the surviving input
source; the high `0xCC`..`0xE0` block is the second one, and several high ids
(`0xD1`..`0xDA`) have no low-id partner at all.

Nothing here is proof of intent, and the tool does not claim any. What it
establishes is reachability: which entry points exist, and which have no caller.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import bisect
import sqlite3
import struct
import sys
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "build" / "research" / "Kotor-Patch-Manager" / "AddressDatabases" / "kotor1_0_3.db"
IMAGE_BASE = 0x00400000

ACTION_ROUTER = 0x00621210
ACTION_SMALL_TABLE = 0x00622128        # ids 0x01..0x0C, direct
ACTION_INDEX = 0x006221FC              # ids 0x19..0x108, id -> case
ACTION_TABLE = 0x00622154              # case -> handler
ACTION_DEFAULT = 0x0062211C

BUTTON_NAMES = {0x27: "A", 0x28: "B", 0x29: "X", 0x2A: "Y", 0x2B: "Black"}


def symbols():
    connection = sqlite3.connect(DATABASE)
    rows = connection.execute(
        "SELECT class_name, function_name, address FROM functions ORDER BY address").fetchall()
    connection.close()
    return [r[2] for r in rows], [f"{r[0]}::{r[1]}" for r in rows], \
           {r[2]: f"{r[0]}::{r[1]}" for r in rows}


def thunks(data: bytes):
    """`mov eax,[ecx]; push flag; push code; call [eax+0x3C]` -- an event raise."""
    found = []
    for offset in range(len(data) - 12):
        if data[offset] != 0x8B or data[offset + 1] != 0x01 or data[offset + 2] != 0x6A:
            continue
        flag = data[offset + 3]
        cursor = offset + 4
        if data[cursor] == 0x6A:
            code, cursor = data[cursor + 1], cursor + 2
        elif data[cursor] == 0x68:
            code, cursor = struct.unpack_from("<I", data, cursor + 1)[0], cursor + 5
        else:
            continue
        if data[cursor:cursor + 3] == b"\xff\x50\x3c":
            found.append((offset + IMAGE_BASE, code, flag))
    return found


def callers(data: bytes, target: int):
    return [offset + IMAGE_BASE for offset in range(len(data) - 5)
            if data[offset] == 0xE8
            and offset + IMAGE_BASE + 5 + struct.unpack_from("<i", data, offset + 1)[0] == target]


def actions(data: bytes):
    """action id -> handler, from both of the router's tables."""
    def dword(va):
        return struct.unpack_from("<I", data, va - IMAGE_BASE)[0]

    mapping = {}
    for index in range(0x0C):
        target = dword(ACTION_SMALL_TABLE + index * 4)
        if target != ACTION_DEFAULT:
            mapping[1 + index] = target
    for index in range(0xF0):
        case = data[ACTION_INDEX - IMAGE_BASE + index]
        target = dword(ACTION_TABLE + case * 4)
        if target != ACTION_DEFAULT:
            mapping[0x19 + index] = target
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("executable", type=Path, nargs="?",
                        default=Path(r"C:\Star Wars - KotOR\swkotor.exe"))
    arguments = parser.parse_args()
    data = arguments.executable.read_bytes()
    addresses, names, by_address = symbols()

    def owner(address):
        index = bisect.bisect_right(addresses, address) - 1
        return names[index] if index >= 0 else "?"

    print("=== layer 1: event-raising thunks")
    for address, code, flag in thunks(data):
        name = by_address.get(address) or f"(inside {owner(address)})"
        note = ""
        if code in BUTTON_NAMES and address < 0x0040C000:
            note = f"   <-- {BUTTON_NAMES[code]} button, {len(callers(data, address))} callers"
        print(f"    0x{address:08X}  raises 0x{code:03X} flag {flag}   {name}{note}")

    print("\n=== layer 2: client action router, paired ids")
    mapping = actions(data)
    grouped = {}
    for identifier, handler in mapping.items():
        grouped.setdefault(handler, []).append(identifier)
    for handler in sorted(grouped):
        identifiers = sorted(grouped[handler])
        low = [i for i in identifiers if i < 0x40]
        high = [i for i in identifiers if i >= 0xC0]
        flag = ""
        if high and not low:
            flag = "   <-- high id with no low-id partner"
        print(f"    0x{handler:08X}  " +
              ", ".join(f"0x{i:02X}" for i in identifiers) + flag)
    print(f"\n{len(mapping)} action ids, {len(grouped)} handlers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
