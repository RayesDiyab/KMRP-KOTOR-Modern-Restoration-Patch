#!/usr/bin/env python3
"""The relocation table that lets KMRP's appended code run from anywhere.

The standalone installer writes gold's eleven appended sections (.kui ... .kmv,
VA 0x0086D000-0x00877FFF) into swkotor.exe. The KPM edition cannot: KOTOR Patch
Manager keeps the executable unmodified, and in an unmodified process Windows maps
other things into most of that range at start-up (measured 2026-09-28: only the
first three of the eleven pages are free, and those sit below the 64 KB
allocation granularity, so nothing can be reserved there). So the KPM edition's
module copies the sections, as one block with their layout intact, into memory it
allocates wherever it can, and re-points every address that names the block.

This finds those addresses in the gold executable, and every one must be found:

  inbound       fields OUTSIDE the block that name it: `jmp/call rel32` in gold's
                patched code, and absolute pointers in its patched data
  outbound      `jmp/call/jcc rel32` INSIDE the block whose target is outside it
  internal-abs  absolute operands INSIDE the block that name the block

A rel32 from the block to the block needs nothing: the block moves as a whole.

Each is found twice, independently, and the two must agree:
  1. a byte scan of every changed byte (gold vs clean) and of every byte the
     block's decoded code occupies, for rel32 branches by opcode and absolute
     values in range;
  2. disassembly: aligned sweeps over the changed runs, and recursive descent
     through the block from the inbound entry points.
Then the table is proved by moving the block to a test base, relocating with the
table, and disassembling both: every instruction must be the same instruction,
with every operand that named the block moved by exactly the delta and every other
operand unchanged. It found a branch into .ktn that the first ad-hoc scan missed,
which is why neither method is trusted alone.

Output (--out): one line per field, `<kind> <field VA hex>`, sorted, with a
header naming the gold SHA-256 it was computed from. kind is IN (add the delta:
the field is outside the block and its value or target moves), OUT (subtract the
delta: the field moves with the block, its target does not) or ABS (add the delta:
the field moves and so does what it names). The installer embeds the file
(src/patcher/KmrpPatcher.cs, KpmEdition) and hands it to the module's applier.

Usage:
    python tools/kpm_relocations.py [--gold PATH] [--clean PATH] [--out PATH]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

import capstone
from capstone import x86

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "build" / "kmrp" / "swkotor_gold_v24_movieaspect.exe"
DEFAULT_CLEAN = ROOT / "build-inputs" / "swkotornopatch.exe"

BLOCK_LO = 0x0086D000
BLOCK_HI = 0x00878000
SECTION_NAMES = [".kui", ".klb", ".kfs", ".kwl", ".ksc", ".kgs", ".ktn",
                 ".kmz", ".kfg", ".kmn", ".kmv"]
TEXT = (0x00401000, 0x0073D000)


class Image:
    """Gold's sections, by VA."""

    def __init__(self, data: bytes):
        self.data = data
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        count = struct.unpack_from("<H", data, pe + 6)[0]
        optional = struct.unpack_from("<H", data, pe + 20)[0]
        self.base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
        self.sections = []
        for i in range(count):
            o = pe + 24 + optional + 40 * i
            name = data[o:o + 8].rstrip(b"\0").decode()
            vsize, va, rsize, raw = struct.unpack_from("<IIII", data, o + 8)
            chars = struct.unpack_from("<I", data, o + 36)[0]
            self.sections.append((name, self.base + va, vsize, raw, rsize, chars))

    def offset(self, va: int) -> int:
        for _, sva, _, raw, rsize, _ in self.sections:
            if sva <= va < sva + rsize:
                return raw + va - sva
        raise ValueError(f"{va:#010x} is not in a raw section")

    def va(self, offset: int):
        for _, sva, _, raw, rsize, _ in self.sections:
            if raw <= offset < raw + rsize:
                return sva + offset - raw
        return None

    def read(self, va: int, n: int) -> bytes:
        o = self.offset(va)
        return self.data[o:o + n]

    def dword(self, va: int) -> int:
        return struct.unpack_from("<I", self.data, self.offset(va))[0]


def in_block(value: int) -> bool:
    return BLOCK_LO <= value < BLOCK_HI


def disassembler():
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    return md


def is_branch(ins) -> bool:
    return ins.group(x86.X86_GRP_JUMP) or ins.group(x86.X86_GRP_CALL)


def rel32_field(ins):
    """VA of a branch's rel32 field, or None for a short or indirect branch."""
    if not is_branch(ins) or not ins.operands or ins.operands[0].type != x86.X86_OP_IMM:
        return None
    if ins.size < 5:
        return None
    return ins.address + ins.size - 4


def abs_fields(ins):
    """[(field VA, value)] for every 32-bit absolute operand naming the block."""
    out = []
    raw = bytes(ins.bytes)
    for o in ins.operands:
        value = None
        if o.type == x86.X86_OP_IMM and not is_branch(ins):
            value = o.imm & 0xFFFFFFFF
        elif o.type == x86.X86_OP_MEM and o.mem.base == 0:
            value = o.mem.disp & 0xFFFFFFFF
        if value is None or not in_block(value):
            continue
        encoded = struct.pack("<I", value)
        at = raw.find(encoded)
        if at < 0 or raw.find(encoded, at + 1) >= 0:
            raise SystemExit(f"cannot place the operand {value:#x} of "
                             f"{ins.address:#010x} {ins.mnemonic} {ins.op_str}")
        out.append((ins.address + at, value))
    return out


def changed_runs(clean: Image, gold: Image):
    """[(va, length)] of changed bytes inside the original raw sections."""
    runs = []
    end = min(len(clean.data), len(gold.data))
    i = 0x1000
    while i < end:
        if clean.data[i] != gold.data[i]:
            j = i
            while j < end and clean.data[j] != gold.data[j]:
                j += 1
            va = gold.va(i)
            if va is not None and va < BLOCK_LO:
                runs.append((va, j - i))
            i = j
        else:
            i += 1
    return runs


# ------------------------------------------------------------- method 1: bytes

def scan_inbound(gold: Image, runs):
    found = {}
    for va, length in runs:
        for field in range(va - 3, va + length):
            try:
                value = gold.dword(field)
            except ValueError:
                continue
            target = (field + 4 + value) & 0xFFFFFFFF
            opcode = gold.read(field - 1, 1)[0]
            prefix = gold.read(field - 2, 1)[0]
            rel = opcode in (0xE8, 0xE9) or (prefix == 0x0F and 0x80 <= opcode <= 0x8F)
            in_text = TEXT[0] <= field < TEXT[1]
            if in_text and rel and in_block(target):
                found[field] = "IN"
            elif in_block(value) and not (in_text and rel):
                found[field] = "IN"
    return found


def scan_block(gold: Image, covered):
    """Byte scan over the block's decoded instruction bytes."""
    found = {}
    for va in sorted(covered):
        try:
            value = gold.dword(va)
        except ValueError:
            continue
        if not all(v in covered for v in range(va, va + 4)):
            continue
        target = (va + 4 + value) & 0xFFFFFFFF
        opcode = gold.read(va - 1, 1)[0]
        prefix = gold.read(va - 2, 1)[0]
        rel = opcode in (0xE8, 0xE9) or (prefix == 0x0F and 0x80 <= opcode <= 0x8F)
        if rel and (va - 1 in covered) and not in_block(target):
            found[va] = "OUT"
        elif in_block(value):
            found[va] = "ABS"
    return found


# ------------------------------------------------------ method 2: disassembly

def sweep(md, gold: Image, start: int, end: int):
    """A linear sweep that steps over undecodable bytes.

    Capstone's disasm() stops at the first byte it cannot decode, so a sweep that
    met a jump table or padding went silent for the rest of its range -- and two
    silent sweeps "agree" on nothing, which is how the branch into .ktn at
    0x00415E0D was first missed. Resume one byte later instead.
    """
    code = gold.read(start, end - start)
    out = {}
    pos = 0
    while pos < len(code):
        last = None
        for ins in md.disasm(code[pos:], start + pos):
            out[ins.address] = ins
            last = ins
        pos = (last.address + last.size - start) if last else pos
        pos += 0 if last and last.address + last.size - start >= len(code) else 1
        if last is None:
            continue
    return out


def disasm_inbound(md, gold: Image, runs):
    """Aligned sweeps: instructions two sweeps agree on, around every run."""
    found = {}
    decoded = {}
    for va, length in runs:
        if not TEXT[0] <= va < TEXT[1]:
            # data: an absolute pointer is the whole field
            for field in range(va - 3, va + length):
                if in_block(gold.dword(field)):
                    found[field] = "IN"
            continue
        key = va & ~0xFFF
        if key not in decoded:
            a = sweep(md, gold, max(TEXT[0], key - 600), min(key + 0x1100, TEXT[1]))
            b = sweep(md, gold, max(TEXT[0], key - 350), min(key + 0x1100, TEXT[1]))
            decoded[key] = {k: v for k, v in a.items() if k in b and b[k].size == v.size}
        table = decoded[key]
        for ins in table.values():
            if ins.address + ins.size <= va - 3 or ins.address >= va + length:
                continue
            field = rel32_field(ins)
            if field is not None and in_block(ins.operands[0].imm & 0xFFFFFFFF):
                found[field] = "IN"
            for f, _ in abs_fields(ins):
                found[f] = "IN"
    return found


def entry_points(gold: Image, inbound):
    entries = set()
    for field in inbound:
        value = gold.dword(field)
        if TEXT[0] <= field < TEXT[1]:
            target = (field + 4 + value) & 0xFFFFFFFF
            entries.add(target if in_block(target) else value)
        else:
            entries.add(value)
    return {e for e in entries if in_block(e)}


def descend(md, gold: Image, entries):
    """Recursive descent through the block. Returns (instructions, fields)."""
    todo = sorted(entries)
    seen = {}
    found = {}
    while todo:
        pc = todo.pop()
        while in_block(pc) and pc not in seen:
            ins = next(md.disasm(gold.read(pc, 16), pc, count=1), None)
            if ins is None:
                raise SystemExit(f"undecodable instruction in the block at {pc:#010x}")
            seen[pc] = ins
            if is_branch(ins) and ins.operands and ins.operands[0].type == x86.X86_OP_IMM:
                target = ins.operands[0].imm & 0xFFFFFFFF
                field = rel32_field(ins)
                if in_block(target):
                    todo.append(target)
                elif field is not None:
                    found[field] = "OUT"
                else:
                    raise SystemExit(f"a short branch leaves the block at {pc:#010x}")
            for f, _ in abs_fields(ins):
                found[f] = "ABS"
            if ins.mnemonic in ("ret", "jmp"):
                break
            pc = ins.address + ins.size
    return seen, found


# ------------------------------------------------------------------ the proof

def relocate(gold: Image, table, delta: int):
    """Gold's bytes with the block moved by delta: {va: bytes} for changed fields,
    plus the relocated block."""
    block = bytearray(gold.read(BLOCK_LO, BLOCK_HI - BLOCK_LO))
    outside = {}
    for kind, field in table:
        value = gold.dword(field)
        if kind == "IN":
            outside[field] = struct.pack("<I", (value + delta) & 0xFFFFFFFF)
        elif kind == "OUT":
            struct.pack_into("<I", block, field - BLOCK_LO, (value - delta) & 0xFFFFFFFF)
        elif kind == "ABS":
            struct.pack_into("<I", block, field - BLOCK_LO, (value + delta) & 0xFFFFFFFF)
    return bytes(block), outside


def prove(md, gold: Image, table, instructions, runs, delta=0x1F7A3000):
    """Every instruction survives the move: same instruction, block operands
    moved by exactly delta, everything else unchanged."""
    block, outside = relocate(gold, table, delta)
    moved = lambda v: (v + delta) & 0xFFFFFFFF if in_block(v) else v

    def operands(ins):
        out = []
        for o in ins.operands:
            if o.type == x86.X86_OP_IMM:
                out.append(("imm", o.imm & 0xFFFFFFFF))
            elif o.type == x86.X86_OP_MEM:
                out.append(("mem", o.mem.base, o.mem.index, o.mem.scale,
                            o.mem.disp & 0xFFFFFFFF))
            else:
                out.append(("reg", o.reg))
        return out

    checked = 0
    for pc, ins in instructions.items():
        new_pc = pc + delta
        new = next(md.disasm(block[pc - BLOCK_LO:pc - BLOCK_LO + 16], new_pc, count=1))
        if new.mnemonic != ins.mnemonic or new.size != ins.size:
            raise SystemExit(f"{pc:#010x} decodes differently after the move")
        want = []
        for op in operands(ins):
            if op[0] == "imm":
                want.append(("imm", moved(op[1])))
            elif op[0] == "mem" and op[1] == 0:
                want.append(op[:4] + (moved(op[4]),))
            else:
                want.append(op)
        if operands(new) != want:
            raise SystemExit(f"{pc:#010x} {ins.mnemonic} {ins.op_str}: operands "
                             f"after the move are {new.op_str}")
        checked += 1

    # Every reference into the block from outside must be relocated. Found here
    # afresh rather than taken from the table: a table missing one would
    # otherwise pass, because the loop below checks only what it was given.
    missing = sorted(set(scan_inbound(gold, runs)) - set(outside))
    if missing:
        raise SystemExit("inbound references not relocated: "
                         + ", ".join(f"{f:#010x}" for f in missing))

    # every inbound branch still lands on the same instruction, moved
    for field, data in outside.items():
        if TEXT[0] <= field < TEXT[1]:
            old_target = (field + 4 + gold.dword(field)) & 0xFFFFFFFF
            new_target = (field + 4 + struct.unpack("<I", data)[0]) & 0xFFFFFFFF
            expect = old_target + delta if in_block(old_target) else old_target
            if new_target != expect:
                raise SystemExit(f"inbound {field:#010x} lands at {new_target:#x}")
        elif struct.unpack("<I", data)[0] != gold.dword(field) + delta:
            raise SystemExit(f"inbound pointer {field:#010x} did not move")
    return checked


def build(gold_path: Path, clean_path: Path):
    gold = Image(gold_path.read_bytes())
    clean = Image(clean_path.read_bytes())
    md = disassembler()
    runs = changed_runs(clean, gold)

    scanned_in = scan_inbound(gold, runs)
    decoded_in = disasm_inbound(md, gold, runs)
    if scanned_in != decoded_in:
        raise SystemExit("inbound fields disagree between the byte scan and the "
                         f"disassembly: scan only {sorted(set(scanned_in) - set(decoded_in))}, "
                         f"disassembly only {sorted(set(decoded_in) - set(scanned_in))}")

    entries = entry_points(gold, scanned_in)
    instructions, descended = descend(md, gold, entries)
    covered = set()
    for ins in instructions.values():
        covered.update(range(ins.address, ins.address + ins.size))
    scanned_block = scan_block(gold, covered)
    if scanned_block != descended:
        raise SystemExit("block fields disagree between the byte scan and the "
                         f"descent: scan only {sorted(set(scanned_block) - set(descended))}, "
                         f"descent only {sorted(set(descended) - set(scanned_block))}")

    # The block's data -- .kfs's floats and cache, .kmn's table -- is never
    # disassembled, so a pointer stored in it, or a jump table the code indexes,
    # would escape both methods. There are none; keep it that way.
    # An indirect CALL needs nothing: its target is read from game memory -- the
    # import table (.kmv's call [0x0073D484]) or an object's vtable (.kfs's
    # `mov edx,[eax]; mov edx,[edx+0x38]; call edx`, .klb's call [edx+4]) -- and
    # it lands in the block only through a stored pointer. The one such pointer in
    # game data, .rdata's 0x0075477C, is an IN entry, and the check below proves
    # the block's own data holds none. An indirect JUMP not through a fixed game
    # address could be a switch table over the block, so it stops the build.
    for pc, ins in instructions.items():
        if not (is_branch(ins) and ins.operands and ins.operands[0].type != x86.X86_OP_IMM):
            continue
        o = ins.operands[0]
        fixed = (o.type == x86.X86_OP_MEM and o.mem.base == 0 and o.mem.index == 0
                 and not in_block(o.mem.disp & 0xFFFFFFFF))
        if o.type == x86.X86_OP_MEM and in_block(o.mem.disp & 0xFFFFFFFF):
            fixed = False
        elif ins.group(x86.X86_GRP_CALL):
            fixed = True
        if not fixed:
            raise SystemExit(f"indirect branch in the block at {pc:#010x}: "
                             f"{ins.mnemonic} {ins.op_str} -- a table would need relocating")
    for va in range(BLOCK_LO, BLOCK_HI - 3):
        if any(v in covered for v in range(va, va + 4)):
            continue
        if in_block(gold.dword(va)):
            raise SystemExit(f"a value naming the block sits in the block's data at "
                             f"{va:#010x}: a stored pointer would need relocating")

    reached = {(pc - BLOCK_LO) // 0x1000 for pc in instructions}
    missing = [SECTION_NAMES[k] for k in range(11) if k not in reached]
    if missing:
        raise SystemExit(f"no code reached in {missing}: an entry point is missing")

    table = sorted([(k, f) for f, k in scanned_in.items()] +
                   [(k, f) for f, k in descended.items()], key=lambda t: t[1])
    checked = prove(md, gold, table, instructions, runs)
    return gold, table, instructions, checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--clean", type=Path, default=DEFAULT_CLEAN)
    parser.add_argument("--out", type=Path)
    arguments = parser.parse_args()

    gold, table, instructions, checked = build(arguments.gold, arguments.clean)
    digest = hashlib.sha256(gold.data).hexdigest().upper()
    counts = {k: sum(1 for kind, _ in table if kind == k) for k in ("IN", "OUT", "ABS")}
    print(f"gold {digest[:16]}: {counts['IN']} inbound, {counts['OUT']} outbound, "
          f"{counts['ABS']} internal absolute; both methods agree; "
          f"{checked} instructions proved after a move")
    if arguments.out:
        lines = [f"# KMRP KPM-edition relocations. gold {digest}",
                 f"# block {BLOCK_LO:#010x}-{BLOCK_HI:#010x}; IN add, OUT subtract, ABS add"]
        lines += [f"{kind} {field:08X}" for kind, field in table]
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text("\n".join(lines) + "\n", encoding="ascii")
        print(f"wrote {arguments.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
