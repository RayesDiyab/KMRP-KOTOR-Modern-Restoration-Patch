#!/usr/bin/env python3
"""Verify the source-only Windows engine build and the real installer scaling.

python testing/regression/Test-WindowsEngineSource.py --csc <csc.exe>
On Linux: --mono-root <extracted Mono tree containing usr/bin/mono-sgen>
No game executable, gold snapshot or resource archives are used.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import build_windows_engine as engine
import kpm_data
import kpm_relocations as relocation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    compiler = parser.add_mutually_exclusive_group(required=True)
    compiler.add_argument('--csc', type=Path)
    compiler.add_argument('--mono-root', type=Path)
    args = parser.parse_args()
    template, recipe, fields, checked = engine.build()
    assert template == engine.build()[0], 'engine build is not deterministic'
    assert recipe.lengths == {'.kmn':4094,'.kui':445,'.klb':110,'.kfs':482,'.kwl':17,
                             '.ksc':45,'.kgs':74,'.ktn':42,'.kmz':181,'.kfg':155,'.kmv':81}
    assert len(fields) == 46 and checked == 443

    # Independent historical inventory: all 68 documented original-image edits
    # must remain covered by exact original bytes and the reference replacements.
    document = (ROOT / 'reverse-engineering/binary-inventory.md').read_text()
    section = document.split('## 4. The 68 code and data runs')[1].split('Which document covers')[0]
    inventory = re.findall(r'\| `0x([0-9A-F]+)` \| `0x[0-9A-F]+` \| \d+ \| `([0-9a-f]+)` \| `([0-9a-f]+)`', section)
    assert len(inventory) == 68
    for va, old, new in inventory:
        at = int(va,16)
        assert bytes(recipe.original[at+i] for i in range(len(bytes.fromhex(old)))) == bytes.fromhex(old)
        assert recipe.read(at,len(bytes.fromhex(new))) == bytes.fromhex(new)

    # The relocation proof must detect an omitted field, not only accept a full
    # table. Includes inbound jumps, outbound calls and internal absolute operands.
    md = relocation.disassembler()
    inbound = {field:kind for kind,field in fields if kind == 'IN'}
    instructions, _ = relocation.descend(md, recipe, relocation.entry_points(recipe,inbound))
    runs = [(va,len(old)) for _,va,old,_ in recipe.runs()]
    for drop in fields:
        try:
            relocation.prove(md,recipe,[f for f in fields if f != drop],instructions,runs)
        except SystemExit:
            pass
        else:
            raise AssertionError(f'missing relocation {drop} was not detected')

    environment = os.environ.copy()
    if args.mono_root:
        mono = args.mono_root.resolve()
        runtime = [str(mono / 'usr/bin/mono-sgen')]
        command = runtime + [str(mono / 'usr/lib/mono/4.5/mcs.exe')]
        environment['MONO_PATH'] = str(mono / 'usr/lib/mono/4.5')
        environment['LD_LIBRARY_PATH'] = str(mono / 'usr/lib')
        environment['MONO_CFG_DIR'] = str(mono / 'etc')
    else:
        command, runtime = [str(args.csc.resolve())], []
    with tempfile.TemporaryDirectory(prefix='kmrp-source-') as temporary:
        work = Path(temporary)
        resource = work / 'windows-engine.bin'
        resource.write_bytes(template)
        exe = work / 'WindowsEngineSelfTest.exe'
        sources = sorted((ROOT / 'src/patcher').glob('*.cs'))
        sources.append(ROOT / 'testing/regression/WindowsEngineSelfTest.cs')
        subprocess.run(command + ['/nologo','/target:exe','/main:Kmrp.WindowsEngineSelfTest',
                       '/out:' + str(exe), '/resource:' + str(resource) + ',Kmrp.engine.source',
                       '/reference:System.dll','/reference:System.Drawing.dll',
                       '/reference:System.IO.Compression.dll','/reference:System.IO.Compression.FileSystem.dll',
                       '/reference:System.Windows.Forms.dll'] + [str(s) for s in sources],
                       env=environment, check=True)
        source = ast.parse((ROOT / 'tools/prepare_universal_resources.py').read_text())
        groups = next(ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign)
                      and any(isinstance(t,ast.Name) and t.id == 'GROUPS' for t in n.targets))
        sizes = [tuple(map(int,size.split('x'))) for group in groups.values() for size in group]
        assert len(sizes) == 66
        sizes += [(640,480),(1919,1079),(3457,1453)]
        size_file = work / 'sizes.txt'
        size_file.write_text(''.join(f'{w}x{h}\n' for w,h in sizes))
        subprocess.run(runtime + [str(exe),str(size_file),str(work / 'data')], env=environment,check=True)
        for width,height in sizes:
            dat = kpm_data.parse(work / 'data' / f'{width}x{height}.dat')
            assert len(dat['runs']) == len(recipe.runs())
            assert dat['relocs'] == fields
            expected_originals = {va:bytes(old) for _,va,old,_ in recipe.runs()}
            assert {va:old for _,va,old,_ in dat['runs']} == expected_originals
            movie_bytes = {va+i for va,n in [(0x403D6C,4),(0x403D78,4),(0x5F5B3B,4),
                                            (0x5F5B43,4),(0x4057AC,7)] for i in range(n)}
            for feature,va,old,new in dat['runs']:
                if feature == 2:
                    assert all(va+i in movie_bytes for i,(a,b) in enumerate(zip(old,new)) if a != b)
            applied, _, block = kpm_data.moved(dat,0,1|2|4)
            values = {va+i:b for va,_,new in applied for i,b in enumerate(new)}
            integer = lambda va: struct.unpack('<i',bytes(values[va+i] for i in range(4)))[0]
            for va in (0x40AA65,0x5F0C65,0x403D6C,0x5F5B3B): assert integer(va) == width
            for va in (0x40AA85,0x5F0C6F,0x403D78,0x5F5B43): assert integer(va) == height
            assert integer(0x40B6C7) == integer(0x40BA6C) == -width
            assert integer(0x40B6DA) == integer(0x40BA83) == -height
            assert integer(0x695082) == width // 2
            assert integer(0x695064) == integer(0x69508A) == height // 2
            assert integer(0x6928B3) == width and integer(0x6928C3) == height
            assert abs(struct.unpack_from('<f',block,0x2004)[0] - max(1,height/720)) < 0.000002
            f32 = lambda v: struct.unpack('<f',struct.pack('<f',v))[0]
            assert integer(0x6DE012) == round(f32(25 * max(1,f32(height/720)))), (width,height,integer(0x6DE012))
            assert struct.unpack_from('<I',block,0x9000)[0] == 1
            assert struct.unpack_from('<I',kpm_data.moved(dat,0,1)[2],0x9000)[0] == 0
            applied_core, left, _ = kpm_data.moved(dat,0,1)
            assert all(f == 2 for f,va,_,_ in dat['runs'] if any(va == v for v,_ in left))
            assert len(applied_core) < len(applied)
    print(f'PASS: 68 historical runs, 11 pages, 46 relocations (including omissions), {len(sizes)} resolutions')


if __name__ == '__main__':
    main()
