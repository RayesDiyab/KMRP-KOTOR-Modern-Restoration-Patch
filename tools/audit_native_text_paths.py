#!/usr/bin/env python3
"""Read clean K1 executable text paths, checked direct references and virtual slots.

Symbol names are local database hints. Direct references are decoded from their
nearest known function entry; this does not independently prove function bounds.
No game binaries or instructions are written. See docs/text-layout-inventory.md.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = '761f9466f456a83909036baebb5c43167d722387be66e54617ba20a8c49e9886'
TARGETS = {
    0x45B990: 'CAurGUIStringInternal::Constructor', 0x45BDF0: 'NewCAurGUIString',
    0x417280: 'CSWGuiText::Constructor', 0x417310: 'CSWGuiText::Initialize',
    0x416050: 'CSWGuiText::Load', 0x415F70: 'CSWGuiTextParams::SetTextObject',
    0x45A2F0: 'CAurGUIStringInternal::WrapStrings', 0x45A850: 'CAurGUIStringInternal::Draw',
    0x4A1770: 'CAurFont::TextOutA', 0x44CCA0: 'PrintStringScreenPos_UseTextureFont',
    0x44CB90: 'GLRender::PrintStringAtScreenPos', 0x44CE50: 'AurPrintString'}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--exe', type=Path, default=ROOT / 'build-inputs/swkotornopatch.exe')
    p.add_argument('--database', type=Path, default=ROOT / 'build/party-roster-kpm-check/game/addresses.db')
    p.add_argument('--out', type=Path, default=ROOT / 'build/text-layout-inventory/native-paths')
    args = p.parse_args(); b = args.exe.read_bytes()
    if hashlib.sha256(b).hexdigest() != EXPECTED: raise ValueError('Only canonical clean CD K1 1.03 is supported')
    db = sqlite3.connect('file:' + args.database.as_posix() + '?mode=ro', uri=True)
    symbols = sorted((a, c + '::' + n) for a, c, n in db.execute('select address,class_name,function_name from functions'))
    starts = [a for a, _ in symbols]
    pe = struct.unpack_from('<I', b, 0x3C)[0]
    count = struct.unpack_from('<H', b, pe + 6)[0]; optional = struct.unpack_from('<H', b, pe + 20)[0]
    sections = []
    for i in range(count):
        s = pe + 24 + optional + 40 * i
        name = b[s:s + 8].rstrip(b'\0').decode('ascii')
        vsize, rva, size, raw = struct.unpack_from('<4I', b, s + 8)
        flags = struct.unpack_from('<I', b, s + 36)[0]
        sections.append((name, 0x400000 + rva, raw, size, flags))
    def file_at(va):
        for name, base, raw, size, _ in sections:
            if base <= va < base + size: return raw + va - base
        raise ValueError('VA outside file sections')
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    @lru_cache(maxsize=None)
    def decoded(start, end):
        off = file_at(start)
        return {address: (mnemonic, operands) for address, _, mnemonic, operands in md.disasm_lite(b[off:off + end - start], start)}
    calls = []
    for name, base, raw, size, flags in sections:
        if not flags & 0x20000000: continue
        for off in range(raw, raw + size - 4):
            if b[off] not in (0xE8, 0xE9): continue
            site = base + off - raw; target = site + 5 + struct.unpack_from('<i', b, off + 1)[0]
            if target not in TARGETS: continue
            idx = bisect_right(starts, site) - 1
            nearest, label = symbols[idx] if idx >= 0 else (0, 'unknown')
            valid = False
            if nearest and 0 <= site - nearest < 0x10000:
                ins = decoded(nearest, site + 5).get(site)
                valid = ins == ('call' if b[off] == 0xE8 else 'jmp', hex(target))
            calls.append({'site_va': hex(site), 'site_file': hex(off), 'instruction': 'call' if b[off] == 0xE8 else 'jmp',
                          'target_va': hex(target), 'target': TARGETS[target],
                          'nearest_symbol': label, 'symbol_entry': hex(nearest),
                          'decoded_from_symbol_entry': valid})
    slots = []
    for table, entries in [(0x741878, {0:'draw', 4:'destruct', 0x18:'set-string', 0x48:'font-height', 0x4C:'wrap', 0x50:'ideal-height', 0x64:'position', 0x74:'size', 0x7C:'draw-with-opacity'}),
                            (0x73E3A4, {0:'destruct', 4:'extent', 8:'ideal-height', 0xC:'draw', 0x10:'load'})]:
        for offset, label in entries.items():
            site = table + offset; fn = struct.unpack_from('<I', b, file_at(site))[0]
            slots.append({'table_va':hex(table),'slot':hex(offset),'file':hex(file_at(site)), 'operation':label,'target_va':hex(fn)})
    args.out.mkdir(parents=True, exist_ok=True)
    report = {'exe': {'bytes':len(b),'sha256':EXPECTED}, 'address_convention':'preferred VA; FILE=VA-0x400000 for these clean sections',
              'database_sha256':hashlib.sha256(args.database.read_bytes()).hexdigest(),
              'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'direct_references':calls,'virtual_slots':slots,
              'counts': dict(Counter(r['target'] for r in calls)),
              'limits':['Direct references exclude unobserved indirect calls and dynamically loaded module code.',
                        'Nearest database symbols are naming/boundary hints, not independent function recovery.',
                        'Static reachability is not evidence that a path executed in a captured game session.']}
    (args.out / 'paths.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'counts':report['counts'],'direct_reference_count':len(calls),
                      'decoded_references':sum(r['decoded_from_symbol_entry'] for r in calls),
                      'virtual_slots':len(slots)},indent=2))


if __name__ == '__main__': main()
