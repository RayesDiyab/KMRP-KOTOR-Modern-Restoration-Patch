#!/usr/bin/env python3
"""Exercise the actual Mac navigation code against every effective game GUI.

Requires pykotor and clang++. No game files are modified. This is a structural
simulation: resource controls are supplied as visible/enabled, with registered
handlers. Runtime population, visibility and specialized panel dispatch require
live testing; this audit cannot certify those behaviors.
"""
import argparse
import contextlib
import ctypes as C
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
INTERACTIVE = {6, 7, 8, 11}  # button, checkbox, slider, list

def inventory(game):
    from pykotor.extract.installation import Installation
    from pykotor.resource.type import ResourceType
    from pykotor.resource.formats.gff import read_gff
    logging.disable(logging.CRITICAL)
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        inst = Installation(game)
        raw = {r.resname().lower()+'.gui': (r.data(), 'core')
               for r in inst.core_resources() if r.restype() == ResourceType.GUI}
    for directory in (game/'Override', game/'override'):
        if directory.is_dir():
            for path in directory.glob('*.gui'):
                raw[path.name.lower()] = (path.read_bytes(), 'override')
    for name, (data, source) in sorted(raw.items()):
        controls = []
        for c in read_gff(data).root.acquire('CONTROLS', []):
            e, m = c.acquire('EXTENT', None), c.acquire('MOVETO', None)
            controls.append(dict(id=c.acquire('ID', -1), tag=c.acquire('TAG', ''),
                kind=c.acquire('CONTROLTYPE', -1),
                prototype=c.acquire('PROTOITEM',None).acquire('CONTROLTYPE',-1) if c.acquire('PROTOITEM',None) else -1,
                rect=[e.acquire(k, 0) for k in ('LEFT','TOP','WIDTH','HEIGHT')] if e else [0]*4,
                links=[m.acquire(k, -1) for k in ('UP','LEFT','DOWN','RIGHT')] if m else [-1]*4))
        yield name, controls, source, hashlib.sha256(data).hexdigest()

def run(library, controls):
    active = [c for c in controls if c['kind'] in INTERACTIVE
              and (c['kind'] != 11 or c.get('prototype',-1) in INTERACTIVE) and c['id'] >= 0
              and c['rect'][2] > 0 and c['rect'][3] > 0]
    if not active:
        return {'controls': 0, 'result': 'no menu controls'}
    ids = [c['id'] for c in active]
    assert len(ids) == len(set(ids)), 'duplicate control IDs'
    assert max(ids) < 512, 'panel ID outside verified bound'
    def block(): return C.create_string_buffer(0x400)
    def put(p, off, typ, value): typ.from_address(C.addressof(p)+off).value = value
    def pointer(p, off): return C.c_void_p.from_address(C.addressof(p)+off).value
    cast = C.CFUNCTYPE(C.c_void_p, C.c_void_p)(lambda p: p)
    vtables = {}
    for kind in INTERACTIVE:
        vt = (C.c_void_p * 20)()
        vt[0x98//8] = C.cast(cast, C.c_void_p).value
        vt[0x80//8] = {8:0x1004a694c, 11:0x1004a8a38}.get(kind, 0)
        vtables[kind] = vt
    panel, manager = block(), block()
    objects = {c['id']:block() for c in active}
    array = (C.c_void_p * (max(ids)+1))()
    put(panel, 0x20, C.c_void_p, C.addressof(manager))
    put(panel, 0x30, C.c_void_p, C.addressof(array))
    put(panel, 0x38, C.c_int, len(array))
    for c in active:
        obj = objects[c['id']]
        array[c['id']] = C.addressof(obj)
        put(obj, 0, C.c_void_p, C.addressof(vtables[c['kind']]))
        put(obj, 0x50, C.c_void_p, C.addressof(panel))
        put(obj, 0x58, C.c_void_p, C.addressof(obj))
        put(obj, 0x60, C.c_int, 1)
        put(obj, 0x68, C.c_ubyte, 0x0e)
        put(obj, 0x74, C.c_int, c['id'])
        for off, value in zip((8,12,16,20), c['rect']): put(obj, off, C.c_int, value)
        for off, ident in zip((0x88,0x90,0x98,0xa0), c['links']):
            put(obj, off, C.c_void_p, C.addressof(objects[ident]) if ident in objects else None)
    start = objects[ids[0]]
    def reached():
        by_address = {C.addressof(o):o for o in objects.values()}
        seen, todo = set(), [C.addressof(start)]
        while todo:
            address = todo.pop()
            if address in seen: continue
            seen.add(address)
            for off in (0x88,0x90,0x98,0xa0):
                target = pointer(by_address[address], off)
                if target in by_address: todo.append(target)
        return len(seen)
    before = reached()
    library.KmrpNoteArrowNavigation(C.addressof(start), 0x3e, 1)
    after = reached()
    assert after == len(active), f'only {after}/{len(active)} controls reachable'
    if len(active) > 1 and len({c['rect'][1] for c in active}) > 1:
        # Shared horizontal rows must not be linked internally by Up or Down.
        lookup = {C.addressof(objects[c['id']]): c for c in active}
        for c in active:
            if sum(other['rect'][1] == c['rect'][1] for other in active) < 2: continue
            for off in (0x88,0x98):
                target = lookup.get(pointer(objects[c['id']], off))
                assert target and target['rect'][1] != c['rect'][1], 'vertical arrow stayed within a horizontal row'
    return {'controls':len(active), 'reachable_before':before, 'reachable_after':after,
            'lists':sum(c['kind']==11 for c in active), 'result':'PASS'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='kmrp-navigation-audit-') as temp:
        lib = Path(temp)/'navigation.dylib'
        subprocess.run(['clang++','-std=c++17','-dynamiclib',str(ROOT/'macos/patches/kmrp-layout/navigation.cpp'),'-o',str(lib)],check=True)
        library = C.CDLL(str(lib))
        library.KmrpNoteArrowNavigation.argtypes = [C.c_void_p,C.c_int,C.c_int]
        rows = []
        for name, controls, source, sha in inventory(args.game):
            try: result = run(library, controls)
            except AssertionError as e: result = {'result':'FAIL', 'reason':str(e)}
            rows.append(dict(gui=name,source=source,sha256=sha,**result))
    failures = [r for r in rows if r['result']=='FAIL']
    args.report.write_text(json.dumps({'method':__doc__, 'guis':rows},indent=2)+'\n')
    print(f"{len(rows)} GUI resources; {sum(r['result']=='PASS' for r in rows)} menu layouts exercised; {len(failures)} failures")
    for r in failures: print(r['gui'], r['reason'])
    raise SystemExit(bool(failures))
if __name__ == '__main__': main()
