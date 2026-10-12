#!/usr/bin/env python3
"""Map addresses of one build of KOTOR_Exe to another build of the same source.

    translate.py <from KOTOR_Exe> <to KOTOR_Exe> <map.json>

Both are thin x86_64 Mach-O files of the same game compiled twice (Steam's 1.4.0 and the App
Store's 1.4.1): the same functions in the same order, some present in only one, and every
reference to data at another distance. Each __text is disassembled; an instruction is reduced
to a token that leaves out what moves (the displacement of a rip-relative operand, the target
of a relative call or jump); runs of K tokens that occur exactly once in each file and are the
same in both anchor the two streams to each other. From the anchored pairs:

  code   every instruction of an anchored run maps to its partner
  data   a rip-relative operand's target in one file maps to its partner's target; an address
         is taken only when every pair that names it agrees

The map is written as JSON: {"code": {from: to}, "data": {from: [to, votes]}, "sections": ...}.
"""
import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import capstone
from capstone import x86_const as x86

K = 6          # tokens in an anchoring run
BASE = 0x100000000


def sections(path):
    out = {}
    text = subprocess.run(["otool", "-l", str(path)], capture_output=True, text=True, check=True).stdout
    for block in text.split("Section")[1:]:
        name = re.search(r"sectname (\S+)", block)
        seg = re.search(r"segname (\S+)", block)
        addr = re.search(r"addr (0x[0-9a-f]+)", block)
        size = re.search(r"size (0x[0-9a-f]+)", block)
        offset = re.search(r"offset (\d+)", block)
        if name and seg and addr and size and offset:
            out[f"{seg.group(1)},{name.group(1)}"] = (int(addr.group(1), 16), int(size.group(1), 16), int(offset.group(1)))
    return out


def disassemble(data, secs):
    """[(address, size, token, target)] for __text: target is the address a rip-relative operand
    or a relative branch names, else None."""
    addr, size, offset = secs["__TEXT,__text"]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    md.skipdata = True
    out = []
    code = data[offset:offset + size]
    for ins in md.disasm(code, addr):
        target = None
        token = ins.mnemonic
        if ins.id == 0:          # skipped data
            out.append((ins.address, ins.size, "?" + ins.bytes.hex(), None))
            continue
        parts = []
        for op in ins.operands:
            if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
                target = ins.address + ins.size + op.mem.disp
                parts.append("[rip]")
            elif op.type == x86.X86_OP_IMM and (x86.X86_GRP_JUMP in ins.groups or x86.X86_GRP_CALL in ins.groups):
                target = op.imm
                parts.append("rel")
            elif op.type == x86.X86_OP_MEM:
                parts.append(f"[{op.mem.base},{op.mem.index},{op.mem.scale},{op.mem.disp}]")
            elif op.type == x86.X86_OP_IMM:
                parts.append(f"#{op.imm}")
            else:
                parts.append(f"r{op.reg}")
        out.append((ins.address, ins.size, token + " " + ",".join(parts), target))
    return out


def grams(stream):
    """hash of each run of K tokens -> index of its first instruction, for runs that occur once."""
    seen, twice = {}, set()
    tokens = [t for _, _, t, _ in stream]
    for i in range(len(tokens) - K + 1):
        h = hashlib.blake2b("\n".join(tokens[i:i + K]).encode(), digest_size=10).digest()
        if h in twice:
            continue
        if h in seen:
            del seen[h]
            twice.add(h)
        else:
            seen[h] = i
    return seen


def main():
    src, dst, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    a_data, b_data = src.read_bytes(), dst.read_bytes()
    a_secs, b_secs = sections(src), sections(dst)
    a, b = disassemble(a_data, a_secs), disassemble(b_data, b_secs)
    print(f"instructions: {len(a):,} and {len(b):,}", file=sys.stderr)
    ga, gb = grams(a), grams(b)
    code = {}
    for h, i in ga.items():
        j = gb.get(h)
        if j is None:
            continue
        for k in range(K):
            code.setdefault(i + k, j + k)
    # Extend each anchored instruction forwards and backwards while the tokens agree: the runs
    # that repeat within a file (prologues, epilogues) are reached from their unique neighbours.
    for direction in (1, -1):
        for i in sorted(code, reverse=direction < 0):
            j = code[i]
            ni, nj = i + direction, j + direction
            while 0 <= ni < len(a) and 0 <= nj < len(b) and ni not in code and a[ni][2] == b[nj][2]:
                code[ni] = nj
                ni += direction
                nj += direction
    # A stretch between two anchored instructions with as many instructions on either side, each
    # pair of the same mnemonic and length: the same code with an operand that differs in a way
    # the token keeps (a constant, an absolute displacement). Mapped as "weak".
    weak = {}
    known = sorted(code)
    for i0, i1 in zip(known, known[1:]):
        if i1 - i0 < 2:
            continue
        j0, j1 = code[i0], code[i1]
        if j1 - j0 != i1 - i0:
            continue
        pairs = [(i0 + n, j0 + n) for n in range(1, i1 - i0)]
        if all(a[i][2].split(" ")[0] == b[j][2].split(" ")[0] and a[i][1] == b[j][1] for i, j in pairs):
            weak.update(pairs)
    code.update(weak)
    code_map = {a[i][0]: (b[j][0], a[i][1], i in weak) for i, j in code.items()}
    votes = collections.defaultdict(collections.Counter)
    for i, j in code.items():
        ta, tb = a[i][3], b[j][3]
        if ta is not None and tb is not None:
            votes[ta][tb] += 1
    data_map, disputed = {}, 0
    for ta, counter in votes.items():
        if len(counter) == 1:
            (tb, n), = counter.items()
            data_map[ta] = (tb, n)
        else:
            disputed += 1
    print(f"code: {len(code_map):,} of {len(a):,} instructions mapped ({len(code_map) / len(a) * 100:.1f}%), "
          f"{len(weak):,} of them weak", file=sys.stderr)
    print(f"targets: {len(data_map):,} agreed, {disputed:,} disputed", file=sys.stderr)
    out.write_text(json.dumps({
        "from": {"sha256": hashlib.sha256(a_data).hexdigest(), "sections": a_secs},
        "to": {"sha256": hashlib.sha256(b_data).hexdigest(), "sections": b_secs},
        "code": {f"{k:#x}": [f"{v[0]:#x}", v[1], int(v[2])] for k, v in sorted(code_map.items())},
        "data": {f"{k:#x}": [f"{v[0]:#x}", v[1]] for k, v in sorted(data_map.items())},
    }))


if __name__ == "__main__":
    main()
