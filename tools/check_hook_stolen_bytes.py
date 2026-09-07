#!/usr/bin/env python3
"""Reject hooks whose stolen bytes contain a relative branch.

A detour copies a hook's `original_bytes` into a trampoline and executes them
there. A relative branch computes its target from where it executes, so a stolen
`call rel32` or `jcc rel8` runs correctly at its original address and jumps into
nothing from the trampoline.

This exists because that is exactly what happened. A hook at 0x00679B71 stole
`E8 BA 15 E3 FF` -- `call Vector::Normalize` -- with `skip_original_bytes =
false`. It installed fine, the main menu was fine, and the game crashed on
entering gameplay, because the stolen call only runs once movement code does.
Every one of the module's pre-existing hooks steals position-independent
instructions only; the pattern was there to be read beforehand and was not.

A relative branch is tolerated when `skip_original_bytes` is true, because then
the bytes are never re-executed -- the handler is expected to reproduce whatever
they did.

Usage:
    python tools/check_hook_stolen_bytes.py [patch_config.toml ...]

Defaults to the installed config and the module's own hook tables. Exits
non-zero if any hook would re-execute a relative branch.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = [
    Path(r"C:\Star Wars - KotOR\patch_config.toml"),
    ROOT / "build" / "research" / "KPM-Xbox-Controls-K1" / "kotor1.hooks.toml",
]

# Every x86 branch whose operand is an offset from the instruction's own address.
RELATIVE = {
    "call", "jmp", "loop", "loope", "loopne", "jecxz", "jcxz",
    "ja", "jae", "jb", "jbe", "jc", "je", "jg", "jge", "jl", "jle",
    "jna", "jnae", "jnb", "jnbe", "jnc", "jne", "jng", "jnge", "jnl", "jnle",
    "jno", "jnp", "jns", "jnz", "jo", "jp", "jpe", "jpo", "js", "jz",
}


def relative_branches(address: int, raw: bytes):
    """(mnemonic, operand) for each position-dependent branch in `raw`."""
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    found = []
    for instruction in disassembler.disasm(raw, address):
        # A register or memory operand is absolute; only an immediate target is
        # computed relative to the instruction pointer.
        if instruction.mnemonic in RELATIVE and instruction.op_str.startswith("0x"):
            found.append((instruction.mnemonic, instruction.op_str))
    return found


def hooks_in(document: dict):
    """Both layouts: the installed `[[patches.hooks]]` and the module's `[[hooks]]`."""
    for patch in document.get("patches", []):
        yield from patch.get("hooks", [])
    yield from document.get("hooks", [])


def main() -> int:
    paths = [Path(a) for a in sys.argv[1:]] or DEFAULTS
    failures = 0
    for path in paths:
        if not path.exists():
            print(f"skipped (not present): {path}")
            continue
        print(f"\n=== {path}")
        with path.open("rb") as handle:
            document = tomllib.load(handle)
        for hook in hooks_in(document):
            raw = bytes(hook.get("original_bytes", []))
            address = hook.get("address", 0)
            name = hook.get("function", "?")
            skipped = hook.get("skip_original_bytes", False)
            branches = relative_branches(address, raw)
            if not branches:
                print(f"  ok        0x{address:08X}  {name}")
            elif skipped:
                detail = ", ".join(f"{m} {o}" for m, o in branches)
                print(f"  ok (skip) 0x{address:08X}  {name}   [{detail}] never re-executed")
            else:
                detail = ", ".join(f"{m} {o}" for m, o in branches)
                print(f"  FAIL      0x{address:08X}  {name}   re-executes [{detail}]")
                failures += 1

    print()
    if failures:
        print(f"{failures} hook(s) would re-execute a relative branch from a trampoline.")
        print("Either set skip_original_bytes = true and reproduce the instruction in the")
        print("handler through an absolute call, or move the hook to a site whose bytes are")
        print("position independent.")
        return 1
    print("All hooks steal position-independent bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
