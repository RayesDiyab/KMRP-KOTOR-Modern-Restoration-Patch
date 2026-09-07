#!/usr/bin/env python3
"""Which retained Xbox GUI events does each menu panel still implement?

KOTOR's PC build kept the console UI's event model. A panel's dispatcher lives at
vtable + 0x3C and is compiled as a jump table over the event code:

    mov  esi, [esp+0xC]              ; the event
    lea  eax, [esi - BIAS]           ; bias to the table's first event
    cmp  eax, RANGE
    ja   default
    movzx eax, byte ptr [eax + INDEX]   ; event -> case index
    jmp  dword ptr [eax*4 + TABLE]      ; case index -> handler

Both tables are plain data in the image, so the whole mapping can be read out
without running the game: for each event, look up its case index, then its
handler address, and anything landing on the `ja` target is not handled *by this
class* -- the default case forwards down to the focused control, so "unimplemented
here" is not "ignored".

This exists because the Abilities screen turned out to cycle its Skills / Powers
/ Feats tabs on event 0x29 -- the Xbox X button -- with the tab index still kept
in a live variable. Nothing was missing; the event simply was not being sent. The
question this answers is how much more of that is sitting there unreached.

Known event codes, from the controller module's own constants and from what the
handlers do:

    0x27 A          0x28 B          0x29 X          0x2A Y
    0x2B Black      0x2F D-pad L    0x30 D-pad R    0x31/0x32 scroll a listbox
    0x39/0x3A       panel-level scroll of its description box

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "controller-native" / "vendor" / "K1XboxControls.cpp"

IMAGE_BASE = 0x00400000
EVENT_NAMES = {
    0x27: "A", 0x28: "B", 0x29: "X", 0x2A: "Y", 0x2B: "Black",
    0x2F: "DpadLeft", 0x30: "DpadRight", 0x31: "ScrollUp", 0x32: "ScrollDown",
    0x39: "DescUp", 0x3A: "DescDown",
}


def panel_vtables() -> dict:
    text = MODULE.read_text(encoding="utf-8")
    return {name.replace("K1_", "").replace("_PANEL_VTABLE", ""): int(value, 0)
            for name, value in re.findall(
                r"constexpr\s+std::uintptr_t\s+(\w+_PANEL_VTABLE)\s*=\s*(0x[0-9A-Fa-f]+)\s*;", text)}


class Image:
    def __init__(self, path: Path):
        self.data = path.read_bytes()

    def inside(self, va: int, width: int = 4) -> bool:
        offset = va - IMAGE_BASE
        return 0 <= offset and offset + width <= len(self.data)

    def dword(self, va: int):
        # Some vtable constants in the module are K2's, or sit in sections this
        # executable does not have. Those are skipped rather than crashed on.
        return struct.unpack_from("<I", self.data, va - IMAGE_BASE)[0] if self.inside(va) else None

    def byte(self, va: int):
        return self.data[va - IMAGE_BASE] if self.inside(va, 1) else None

    def code(self, va: int, length: int) -> bytes:
        return self.data[va - IMAGE_BASE: va - IMAGE_BASE + length]


def decode_dispatcher(image: Image, handler: int):
    """(bias, range, index table, jump table, default) or None when the handler
    is not a jump table -- some panels use if/else chains and are read by hand."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    bias = span = index = table = default = None
    for instruction in md.disasm(image.code(handler, 320), handler):
        text = instruction.mnemonic + " " + instruction.op_str
        if instruction.mnemonic == "lea" and " - 0x" in text:
            match = re.search(r"- (0x[0-9a-f]+)\]", text)
            if match and bias is None:
                bias = int(match.group(1), 16)
        elif instruction.mnemonic == "add" and bias is None:
            # The same bias written as a subtraction. The Journal's dispatcher
            # uses `add eax, -0x28` where others use `lea eax, [esi-0x28]`, and
            # missing this form silently reported the panel as having no
            # dispatcher at all -- which reads as "handles nothing".
            match = re.search(r", -(0x[0-9a-f]+)$", text)
            if match:
                bias = int(match.group(1), 16)
        elif instruction.mnemonic == "cmp" and span is None and bias is not None:
            # Capstone prints small immediates in decimal, so Container's
            # `cmp eax, 7` was not matched by a hex-only pattern and the panel
            # read as undecodable. Both forms are accepted.
            match = re.search(r", (0x[0-9a-f]+|\d+)$", text)
            if match:
                span = int(match.group(1), 0)
        elif instruction.mnemonic == "ja" and default is None:
            default = int(instruction.op_str, 16)
        elif instruction.mnemonic == "movzx" and "byte ptr [" in text:
            match = re.search(r"\+ (0x[0-9a-f]+)\]", text)
            if match:
                index = int(match.group(1), 16)
        elif instruction.mnemonic == "jmp" and "*4 +" in text:
            match = re.search(r"\*4 \+ (0x[0-9a-f]+)\]", text)
            if match:
                table = int(match.group(1), 16)
                break
    if None in (bias, span, table, default):
        return None
    # `index is None` is the Container shape: a direct jump table with no
    # event-to-case indirection, `jmp [eax*4 + TABLE]` straight after the range
    # check. Signalled to the caller as index 0, meaning "case index == offset".
    return bias, span, index, table, default


def decode_chain(image: Image, handler: int) -> dict:
    """Panels that compare the event code directly instead of using a jump table.

    Two shapes appear: a run of `cmp <reg>, <event>` / `je <handler>`, and a
    subtract-and-test chain (`sub eax, N` / `je`), which the compiler emits for
    codes that are close together. Both are walked here; anything not matched is
    reported rather than silently dropped, because a missed handler reads as
    "the panel ignores that event" and that is the one wrong answer this whole
    exercise must not give.
    """
    # Operands print in decimal when they are small: `sub eax, 5`, not
    # `sub eax, 0x5`. A hex-only pattern had already cost this project the
    # Container panel once; it was costing the Main Menu's 0x2D here too, and a
    # dropped handler reads as "the panel ignores that event".
    operand = re.compile(r", (0x[0-9a-f]+|\d+)$")

    def immediate(text):
        match = operand.search(text)
        if not match:
            return None
        return int(match.group(1), 16 if match.group(1).startswith("0x") else 10)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    found, pending, running = {}, None, None
    for instruction in md.disasm(image.code(handler, 768), handler):
        text = instruction.mnemonic + " " + instruction.op_str
        if instruction.mnemonic == "cmp":
            pending = immediate(text)
        elif instruction.mnemonic == "sub" and running is None:
            # Chains that open `sub eax, 0x28` with no preceding cmp -- Main Menu
            # and Level Up. Without seeding from this the first `je` was dropped
            # and the whole panel read as undecodable.
            seed = immediate(text)
            if seed is not None:
                running = seed
                pending = running
        elif instruction.mnemonic == "sub":
            step = immediate(text)
            if step is not None and running is not None:
                running += step
                pending = running
        elif instruction.mnemonic == "dec" and running is not None:
            running += 1
            pending = running
        elif instruction.mnemonic in ("je", "jz") and pending is not None:
            found[pending] = int(instruction.op_str, 16)
            if running is None:
                running = pending
            pending = None
        elif instruction.mnemonic in ("ret", "jmp"):
            if instruction.mnemonic == "ret":
                break
    return found


def full_report(image, first_only=None):
    """Every event each panel implements, across the WHOLE range its dispatcher
    accepts -- not a chosen slice of it.

    The slice mattered: the party-change code on the Character screen is reached
    by event 0xCE, and a survey that stopped at 0x3F reported that panel as
    having no such handler at all. The dispatchers accept 0x28..0xDF, so that is
    what gets walked.
    """
    vtables = panel_vtables()
    decoded, chained, opaque = {}, {}, []
    for name, vtable in sorted(vtables.items()):
        handler = image.dword(vtable + 0x3C)
        if handler is None or not image.inside(handler, 16):
            continue
        shape = decode_dispatcher(image, handler)
        if shape is not None:
            bias, span, index, table, default = shape
            groups = {}
            for event in range(bias, bias + span + 1):
                case = (event - bias) if index is None else image.byte(index + (event - bias))
                if case is None:
                    continue
                target = image.dword(table + case * 4)
                if target is not None and target != default:
                    groups.setdefault(target, []).append(event)
            decoded[name] = (handler, bias, bias + span, groups)
            continue
        chain = decode_chain(image, handler)
        if chain:
            groups = {}
            for event, target in chain.items():
                groups.setdefault(target, []).append(event)
            chained[name] = (handler, groups)
        else:
            opaque.append((name, handler))
    return decoded, chained, opaque


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("executable", type=Path, nargs="?",
                        default=Path(r"C:\Star Wars - KotOR\swkotor.exe"))
    parser.add_argument("--first", type=lambda v: int(v, 0), default=0x27)
    parser.add_argument("--last", type=lambda v: int(v, 0), default=0x3F)
    parser.add_argument("--full", action="store_true",
                        help="every implemented event per panel, whole accepted range")
    arguments = parser.parse_args()

    image = Image(arguments.executable)

    if arguments.full:
        decoded, chained, opaque = full_report(image)
        total = 0
        for name, (handler, low, high, groups) in decoded.items():
            count = sum(len(v) for v in groups.values())
            total += count
            print(f"{name}   dispatcher 0x{handler:08X}  accepts 0x{low:02X}..0x{high:02X}  "
                  f"implements {count} events")
            for target in sorted(groups):
                codes = ", ".join(f"0x{e:02X}" for e in groups[target])
                print(f"    0x{target:08X}  <- {codes}")
        for name, (handler, groups) in chained.items():
            count = sum(len(v) for v in groups.values())
            total += count
            print(f"{name}   dispatcher 0x{handler:08X}  [cmp/je chain]  implements {count} events")
            for target in sorted(groups):
                codes = ", ".join(f"0x{e:02X}" for e in groups[target])
                print(f"    0x{target:08X}  <- {codes}")
        print()
        print(f"panels decoded: {len(decoded) + len(chained)}   "
              f"events implemented in total: {total}")
        if opaque:
            print(f"NOT decoded ({len(opaque)}):")
            for name, handler in opaque:
                print(f"    {name:<30}0x{handler:08X}")
        return 0

    events = list(range(arguments.first, arguments.last + 1))

    header = "panel".ljust(30) + "".join(
        f"{EVENT_NAMES.get(e, hex(e)[2:]):>10}" for e in events)
    print(header)
    print("-" * len(header))

    unreadable = []
    for name, vtable in sorted(panel_vtables().items()):
        handler = image.dword(vtable + 0x3C)
        if handler is None or not image.inside(handler, 16):
            continue                       # not this executable's panel
        decoded = decode_dispatcher(image, handler)
        row = name[:29].ljust(30)
        if decoded is None:
            chain = decode_chain(image, handler)
            if not chain:
                unreadable.append((name, handler))
                continue
            for event in events:
                row += f"{hex(chain[event])[2:]:>10}" if event in chain else f"{'.':>10}"
            print(row + "   [chain]")
            continue
        bias, span, index, table, default = decoded
        for event in events:
            offset = event - bias
            if offset < 0 or offset > span:
                row += f"{'.':>10}"
                continue
            case = image.byte(index + offset)
            target = image.dword(table + case * 4) if case is not None else None
            if target is None:
                row += f"{'?':>10}"
                continue
            row += f"{'.':>10}" if target == default else f"{hex(target)[2:]:>10}"
        print(row)

    print()
    print("'.' = dispatched to the default case. That does NOT mean nothing happens:")
    print("      the default forwards the event to the focused control and then to")
    print("      CSWGuiControl::HandleInputEvent (0x00418750), so it may still be")
    print("      handled a layer down. This is how A reaches every button.")
    print("Anything else is the address of the handler this class runs itself.")
    if unreadable:
        print("\nNot a jump table, read these by hand:")
        for name, handler in unreadable:
            print(f"  {name:<30}dispatcher 0x{handler:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
