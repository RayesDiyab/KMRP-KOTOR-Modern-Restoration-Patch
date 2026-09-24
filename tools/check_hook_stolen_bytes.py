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

Only a detour steals bytes at all. A `simple` hook overwrites the site in place
and a `replace` hook overwrites it with a jump to a cave and NOPs, so in neither
case are the original bytes executed again. A `replace` gets the opposite check
instead: its REPLACEMENT runs from a cave the allocator placed anywhere, so a
relative branch there is fine while it stays inside the block and wrong the
moment it leaves it.

It also checks what KPM's wrapper does with the stolen bytes, because the
order is not the obvious one. The wrapper calls the handler, restores every
register except those in `exclude_from_restore`, runs the stolen bytes, and
only THEN tests EAX for a `consumed_exit_address` (Kotor-Patch-Manager,
wrapper_x86.cpp). So:

  * a consumed-exit hook's stolen bytes must not touch EAX -- a write replaces
    the handler's answer before the test reads it -- nor move ESP, or the
    consumed exit is reached with a different stack from the one it expects;
  * no hook's stolen bytes may read a register excluded from restore, which by
    then holds the handler's return value rather than the game's.

Both were real. The Solo Mode hook stole `mov eax,[0x7A39FC]` ahead of its
consumed exit, so every A on that dialog took the close path, OK included; the
resolution hook stole `push 0` ahead of its own.

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
    ROOT / "src" / "controller-native" / "kotor1.hooks.toml",
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


def escaping_branches(raw: bytes):
    """Relative branches in a cave-resident block whose target leaves it.

    Disassembled from 0, so a target inside [0, len) is a branch within the
    block, which moves with it. Anything else was computed against the original
    address and is wrong once the block is somewhere else.
    """
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    found = []
    for instruction in disassembler.disasm(raw, 0):
        if instruction.mnemonic in RELATIVE and instruction.op_str.startswith("0x"):
            if not 0 <= int(instruction.op_str, 16) < len(raw):
                found.append((instruction.mnemonic, instruction.op_str))
    return found


_EAX_FAMILY = {"eax", "ax", "al", "ah"}
_ESP_FAMILY = {"esp", "sp"}
_REGISTER_FAMILIES = {
    "eax": _EAX_FAMILY, "ebx": {"ebx", "bx", "bl", "bh"},
    "ecx": {"ecx", "cx", "cl", "ch"}, "edx": {"edx", "dx", "dl", "dh"},
    "esi": {"esi", "si"}, "edi": {"edi", "di"}, "ebp": {"ebp", "bp"},
}


def register_use(raw: bytes, address: int):
    """(reads, writes) register names over `raw`, implicit operands included."""
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    disassembler.detail = True
    reads, writes = set(), set()
    for instruction in disassembler.disasm(raw, address):
        read, written = instruction.regs_access()
        reads |= {instruction.reg_name(r) for r in read}
        writes |= {instruction.reg_name(r) for r in written}
    return reads, writes


def wrapper_order_problems(hook: dict, raw: bytes, address: int):
    """What the stolen bytes do between the handler and KPM's EAX test."""
    if hook.get("skip_original_bytes", False) or not raw:
        return []
    reads, writes = register_use(raw, address)
    problems = []
    if hook.get("consumed_exit_address"):
        if (reads | writes) & _EAX_FAMILY:
            problems.append("touches EAX before the consumed-exit test reads it")
        if writes & _ESP_FAMILY:
            problems.append("moves ESP before the consumed exit")
    for register in hook.get("exclude_from_restore", []):
        if reads & _REGISTER_FAMILIES.get(register.lower(), {register.lower()}):
            problems.append(f"reads {register}, which then holds the handler's return value")
    return problems


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
            kind = hook.get("type", "detour")
            name = hook.get("function", f"<{kind}>")
            skipped = hook.get("skip_original_bytes", False)

            if kind in ("simple", "replace"):
                # The site is overwritten, so nothing is stolen. For a replace
                # the replacement itself is what has to be position independent.
                replacement = bytes(hook.get("replacement_bytes", []))
                escaping = (escaping_branches(replacement)
                            if kind == "replace" else [])
                if not escaping:
                    print(f"  ok        0x{address:08X}  {name}   "
                          f"nothing stolen ({kind})")
                else:
                    detail = ", ".join(f"{m} {o}" for m, o in escaping)
                    print(f"  FAIL      0x{address:08X}  {name}   "
                          f"replacement branches out of its cave [{detail}]")
                    failures += 1
                continue

            ordering = wrapper_order_problems(hook, raw, address)
            if ordering:
                print(f"  FAIL      0x{address:08X}  {name}   stolen bytes " +
                      "; ".join(ordering))
                failures += 1
                continue

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
        print(f"{failures} hook(s) steal bytes that cannot run where the wrapper runs them.")
        print("For a detour: either set skip_original_bytes = true and reproduce the")
        print("instruction in the handler through an absolute call, or move the hook to a")
        print("site whose bytes are position independent. For a replace: reach outside the")
        print("block through an absolute target (mov reg, imm32 then call/jmp reg, or a")
        print("push imm32 followed by ret) rather than a relative branch.")
        return 1
    print("All hooks steal position-independent bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
