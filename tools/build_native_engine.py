#!/usr/bin/env python3
"""Compile the tracked engine recipe into the native module (no game file input).

Resolution operands are described separately so startup and later mode changes
use the same arithmetic. Output is generated under build/, never game bytes.
"""
from pathlib import Path
import argparse
import struct
import build_windows_engine as engine
import build_native_kpatch

ROOT = Path(__file__).resolve().parents[1]


# The message popup's widening step (CSWGuiMessageBox::FixMessageLabel, 0x006253A0).
# The game adds 40 to the width and takes 20 off the left per pass, both as signed
# bytes; the same 27 bytes with one 32-bit step, which follows the screen:
#   mov eax, step ; add [esp+38], eax ; add ecx, eax ; mov [esp+28], ecx ;
#   sar eax, 1 ; sub [esp+20], eax ; lea ecx, [esp+30] ; nop ; nop
POPUP_STEP = bytes.fromhex('B8 28 00 00 00  01 44 24 38  01 C1  89 4C 24 28  D1 F8  29 44 24 20  8D 4C 24 30  90 90')
# The store row's stack-count label (CSWGuiStoreItemEntry::SetExtent, 0x006C2650).
# The game makes it 21 wide (42 for three digits or more) and as tall as the icon,
# at the row's top; the same 49 bytes by the inventory's rule: 21s or 42s wide,
# 19s tall, right-aligned in the icon and its top at the icon less its height:
#   cmp eax, 2 ; mov ecx, 21s ; jle +2 ; add ecx, ecx ; mov [esp+28], ecx ;
#   add [esp+20], edi ; sub [esp+20], ecx ; mov eax, 19s ; mov [esp+2c], eax ;
#   sub eax, edi ; sub [esp+24], eax ; lea ecx, [esi+334] ; lea edx, [esp+20]
STORE_COUNT = bytes.fromhex('83 F8 02  B9 15 00 00 00  7E 02  03 C9  89 4C 24 28  01 7C 24 20  29 4C 24 20'
                            '  B8 13 00 00 00  89 44 24 2C  2B C7  29 44 24 24  8D 8E 34 03 00 00  8D 54 24 20')


def resolution_fields():
    # kind: width, height, scaled integer, negative width/height, map canvas,
    # half width/height, scaled float, clamped marker integer/byte.
    fields = []
    def add(kind, base, addresses, size=4):
        fields.extend((va, size, kind, base) for va in addresses)
    add(1, 0, [0x40AA65, 0x403D6C, 0x5F5B3B, 0x6928B3])
    add(2, 0, [0x40AA85, 0x403D78, 0x5F5B43, 0x6928C3])
    add(4, 0, [0x40B6C7, 0x40BA6C])
    add(5, 0, [0x40B6DA, 0x40BA83])
    add(6, 0, [0x69505C])
    add(7, 0, [0x695082])
    add(8, 0, [0x695064, 0x69508A])
    add(9, 0, [0x86F004])
    for base, addresses in [
        (19, [0x6B5332]), (21, [0x871003, 0x871009]), (37, [0x871020]),
        (56, [0x6B527F, 0x6B4FA9, 0x6B55E3, 0x6C265F, 0x6C2A23]),
        (50, [0x6AB8EF, 0x6ACB20, 0x6CD8D9, 0x6CDB79]),
        (450, [0x6256E3, 0x625759]), (800, [0x6256DC, 0x6256F6]),
        (64, [0x626F95, 0x62540D]), (25, [0x6DE012]),
        (30, [0x6DE0D3, 0x6DE0D8]),
        # the popup's widening step; the store row's count label: width, height
        (40, [0x6256FD]), (21, [0x6C2708]), (19, [0x6C271D]),
    ]:
        add(3, base, addresses)
    add(3, 2, [0x6DE031], 1)
    for base, addresses in [(20, [0x694720]), (14, [0x694763]),
                            (16, [0x694A13, 0x6940DC]), (32, [0x694AC4, 0x69405B])]:
        add(10, base, addresses)
    for base, addresses in [(-10, [0x69471A, 0x694726]), (-7, [0x694777, 0x69477A]),
                            (-8, [0x694A53, 0x694A56]), (-16, [0x694AD0, 0x694AD4])]:
        add(11, base, addresses, 1)
    return sorted(fields)


def build():
    _, recipe, relocations, _ = engine.build()
    # The native validator owns this function; its operands must stay vanilla
    # until KPM installs the declared detour. It supersedes both fixed checks.
    omit = {0x5F0C65, 0x5F0C6F}
    runs = [r for r in recipe.runs() if r[1] not in omit]
    for feature, va, old, new in runs:
        for hook in build_native_kpatch.all_hooks():
            if va < hook['address'] + len(hook['original_bytes']) and hook['address'] < va + len(old):
                raise ValueError(f'Engine overlaps native hook at {va:08X}')
    data = bytearray(b'KMRPKPM2' + struct.pack('<IIII', 2, engine.BLOCK_VA, engine.BLOCK_SIZE, 11))
    data += b''.join(struct.pack('<I', 0x40 if p == 2 else 0x20) for p in range(11))
    block_at = len(data)
    block = bytearray(recipe.block)
    # The .kmn page's first word (VA 0x876000) enables Derslok's map-note table. It is
    # cleared here and set by a block edit of the map-notes feature (4), exactly as
    # kmrp-kpm.dat carried it: map notes are an option of the patch.
    if struct.unpack_from('<I', block, 0x9000)[0] != 1:
        raise ValueError('Unexpected map-note flag in the engine block')
    struct.pack_into('<I', block, 0x9000, 0)
    data += block
    data += struct.pack('<I', len(runs))
    regions = [(engine.BLOCK_VA, engine.BLOCK_SIZE, block_at)]
    for feature, va, old, new in runs:
        if va == 0x6DE08E:
            new = bytes.fromhex('E9 3E 00 00 00 90')
        elif va == 0x6DE0D1:
            new = bytes.fromhex('81 E9 1E 00 00 00 05 1E 00 00 00 EB B6')
        elif va == 0x6256FC:
            new = POPUP_STEP
        elif va == 0x6C2704:
            new = STORE_COUNT
        data += struct.pack('<III', feature, va, len(old)) + old
        regions.append((va, len(new), len(data)))
        data += new
    data += struct.pack('<I', 1) + struct.pack('<III', 4, 0x9000, 4) + struct.pack('<I', 1)
    data += struct.pack('<I', len(relocations))
    for kind, va in relocations:
        if not any(begin <= va and va + 4 <= begin + length for begin, length, _ in regions):
            raise ValueError(f'Relocation without retained owner {va:08X}')
        data += struct.pack('<II', {'IN': 1, 'OUT': 2, 'ABS': 3}[kind], va)
    data += engine.checksum(data)
    descriptors = []
    for va, size, kind, base in resolution_fields():
        owners = [(at + va - begin) for begin, length, at in regions
                  if begin <= va and va + size <= begin + length]
        if len(owners) != 1:
            raise ValueError(f'Resolution field lacks one complete guard: {va:08X}')
        if any(field < va + size and va < field + 4 for _, field in relocations):
            raise ValueError(f'Resolution field overlaps relocation: {va:08X}')
        descriptors.append((va, owners[0], size, kind, base))
    return bytes(data), descriptors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/native-runtime/NativeEngine.generated.h')
    args = parser.parse_args()
    data, fields = build()
    lines = ['// Generated by tools/build_native_engine.py. Do not edit.',
             '#pragma once', 'static const unsigned char kNativeEngine[] = {']
    lines += [','.join(f'0x{b:02X}' for b in data[i:i+24]) + ',' for i in range(0, len(data), 24)]
    lines += ['};', 'struct NativeField { unsigned va, payload, size, kind; int base; };',
              'static const NativeField kNativeFields[] = {']
    lines += [f'{{0x{va:X},{at},{size},{kind},{base}}},' for va, at, size, kind, base in fields]
    lines += ['};', '']
    args.out.parent.mkdir(parents=True, exist_ok=True)
    source = '\n'.join(lines)
    args.out.write_text(source)
    if args.out.read_text() != source:
        raise ValueError('Native engine header read-back failed')
    print(f'{len(data)} embedded engine bytes, {len(fields)} guarded runtime fields')


if __name__ == '__main__':
    main()
