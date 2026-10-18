#!/usr/bin/env python3
"""Read-only K1 text-object census rooted in native GUI registries.

No injection, memory writes or game strings are exported. Windows/x86 K1 only.
Database names/sizes are discovery hints; observed vtables and pointers are checked.
See docs/text-layout-inventory.md for coverage limits.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import struct
import time

ROOT = Path(__file__).resolve().parents[1]
K = C.WinDLL('kernel32', use_last_error=True)
K.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
K.OpenProcess.restype = W.HANDLE
K.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
K.ReadProcessMemory.restype = W.BOOL
K.CloseHandle.argtypes = [W.HANDLE]


class Memory:
    def __init__(self, pid):
        self.handle = K.OpenProcess(0x410, False, pid)  # query + VM_READ only
        if not self.handle: raise OSError(C.get_last_error(), 'OpenProcess')
    def read(self, address, size):
        if not address or size < 0 or size > (4 << 20): raise ValueError('Invalid bounded read')
        buf = C.create_string_buffer(size)
        got = C.c_size_t()
        if not K.ReadProcessMemory(self.handle, address, buf, size, C.byref(got)) or got.value != size:
            raise OSError(C.get_last_error(), hex(address))
        return buf.raw
    def u(self, address): return struct.unpack('<I', self.read(address, 4))[0]
    def array(self, address, limit=4096):
        ptr, count, capacity = struct.unpack('<III', self.read(address, 12))
        if count > capacity or capacity > limit: raise ValueError('Invalid native array')
        return list(struct.unpack('<' + str(count) + 'I', self.read(ptr, count * 4))) if count else []
    def string(self, address):
        data = self.read(address, 24)
        count, cap = struct.unpack_from('<II', data, 16)
        if count > 256 or cap < count: raise ValueError('Invalid MSVC string')
        value = data[:count] if cap < 16 else self.read(struct.unpack_from('<I', data)[0], count)
        return value.decode('ascii')
    def tree(self, address):
        head, size = struct.unpack('<II', self.read(address, 8))
        if size > 4096: raise ValueError('Invalid MSVC tree')
        todo = [self.u(head + 4)] if size else []
        seen = set()
        while todo:
            node = todo.pop()
            if node == head: continue
            if node in seen or len(seen) >= size: raise ValueError('Invalid/cyclic MSVC tree')
            data = self.read(node, 16)
            if data[13]: raise ValueError('Unexpected sentinel')
            seen.add(node)
            yield node + 16
            todo.extend([struct.unpack_from('<I', data)[0], struct.unpack_from('<I', data, 8)[0]])
        if len(seen) != size: raise ValueError('Changed/incomplete MSVC tree snapshot')
    def close(self): K.CloseHandle(self.handle)


def heap_strings(mem, owned):
    # Factory allocations are 0x48-byte private-heap objects. Signature matches
    # without a rooted owner remain candidates: freed memory can retain a vtable.
    class Region(C.Structure):
        _fields_ = [('base', C.c_void_p), ('allocation', C.c_void_p), ('allocation_protect', W.DWORD),
                    ('alignment', W.DWORD), ('size', C.c_size_t), ('state', W.DWORD),
                    ('protect', W.DWORD), ('kind', W.DWORD)]
    K.VirtualQueryEx.argtypes = [W.HANDLE, C.c_void_p, C.POINTER(Region), C.c_size_t]
    K.VirtualQueryEx.restype = C.c_size_t
    address = 0x10000; signature = struct.pack('<I', 0x741878)
    seen = set(); candidates = []; wrapper_candidates = {}; scanned = errors = regions = 0
    unreadable_ranges = []
    while address < 0x100000000:
        info = Region()
        if not K.VirtualQueryEx(mem.handle, address, C.byref(info), C.sizeof(info)): break
        start = info.base or 0; end = start + info.size
        if end <= address: break
        address = end
        if info.state != 0x1000 or info.kind != 0x20000 or info.protect & 0x100 or info.protect & 0xFF not in (2, 4, 8, 0x20, 0x40, 0x80): continue
        regions += 1; carry = b''
        for at in range(start, end, 1 << 20):
            try: block = mem.read(at, min(1 << 20, end - at))
            except (OSError, ValueError) as exc:
                errors += 1; carry = b''
                unreadable_ranges.append({'address':hex(at), 'bytes':min(1 << 20, end-at),
                                          'region_protection':hex(info.protect), 'error':str(exc)})
                continue
            scanned += len(block); data = carry + block; base = at - len(carry); pos = 0
            while True:
                pos = data.find(signature, pos)
                if pos < 0: break
                obj = base + pos; pos += 1
                if obj % 4 or obj in seen: continue
                seen.add(obj)
                try:
                    raw = mem.read(obj, 0x48)
                    scale = struct.unpack_from('<f', raw, 0x40)[0]
                    rect = struct.unpack_from('<4i', raw, 4)
                    if not math.isfinite(scale) or not 0 < scale <= 128: continue
                    if any(abs(v) > 32767 for v in rect) or rect[2] < 0 or rect[3] < 0: continue
                    font = struct.unpack_from('<I', raw, 0x18)[0]
                    if not 0x400000 <= mem.u(font) < 0x800000: continue
                    text = struct.unpack_from('<I', raw, 0x14)[0]; present = bool(mem.read(text, 1)[0])
                    for a in (0x28, 0x34):
                        ptr, count, cap = struct.unpack_from('<III', raw, a)
                        if count > cap or cap > 1000000 or (count and not ptr): raise ValueError('Invalid line array')
                    candidates.append({'address':hex(obj),'status':'rooted-owner' if obj in owned else 'unowned-shape-candidate',
                                       'owners':owned.get(obj,[]),'content_rect':rect,'scale':scale,
                                       'line_count':struct.unpack_from('<I',raw,0x38)[0], 'text_present':present})
                except (OSError, ValueError): continue
            for table in (0x73E3A4, 0x73E444):
                pos = 0; marker = struct.pack('<I', table)
                while True:
                    pos = data.find(marker, pos)
                    if pos < 0: break
                    wrapper = base + pos; pos += 1
                    if wrapper % 4 or wrapper in wrapper_candidates: continue
                    try:
                        if mem.u(wrapper + 0x68) != wrapper: continue
                        internal = mem.u(wrapper + 0x14)
                        if not internal or mem.u(internal) != 0x741878: continue
                        wrapper_candidates[wrapper] = {'wrapper':hex(wrapper),'internal':hex(internal),
                                                       'rooted':internal in owned,
                                                       'font':mem.read(wrapper+0x24,16).split(b'\0')[0].decode('ascii','replace')}
                    except (OSError,ValueError): continue
            carry = data[-0x6F:]
    return {'read_bytes':scanned,'private_regions':regions,'unreadable_chunks':errors,
            'unreadable_ranges':unreadable_ranges,
            'vtable_signature_hits':len(seen),'validated_shapes':len(candidates),
            'unowned_candidates':sum(r['status']=='unowned-shape-candidate' for r in candidates),
            'validated_wrapper_shapes':len(wrapper_candidates),'unrooted_wrapper_shapes':sum(not r['rooted'] for r in wrapper_candidates.values()),
            'objects':candidates,'wrapper_candidates':list(wrapper_candidates.values()),'limits':['Unowned shapes may be stale/freed allocations, not confirmed active text.',
                                          'Only committed readable private memory in the 32-bit address space is scanned.',
                                          'The snapshot is not atomic and is not an allocation history.']}


def module_info(pid):
    class Module(C.Structure):
        _fields_ = [('size', W.DWORD), ('id', W.DWORD), ('pid', W.DWORD), ('guse', W.DWORD),
                    ('puse', W.DWORD), ('base', C.c_void_p), ('length', W.DWORD), ('module', W.HMODULE),
                    ('name', W.WCHAR * 256), ('path', W.WCHAR * 260)]
    K.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
    K.CreateToolhelp32Snapshot.restype = W.HANDLE
    K.Module32FirstW.argtypes = [W.HANDLE, C.POINTER(Module)]
    K.Module32NextW.argtypes = [W.HANDLE, C.POINTER(Module)]
    snap = K.CreateToolhelp32Snapshot(0x18, pid)
    mod = Module(); mod.size = C.sizeof(mod)
    found = {}; ok = K.Module32FirstW(snap, C.byref(mod))
    while ok:
        found[mod.name.lower()] = {'base': mod.base, 'length': mod.length, 'path': mod.path}
        ok = K.Module32NextW(snap, C.byref(mod))
    K.CloseHandle(snap)
    return found


def font_metrics(mem, font, scale):
    """Read the verified texture-font getter chain; never invoke native methods."""
    vt = mem.u(font)
    if mem.u(vt + 0x38) != 0x41EFA0 or mem.u(vt + 8) != 0x4205C0:
        return {'font_metrics_status': 'unreviewed-font-getters'}
    if mem.read(0x4205C0, 3) != bytes.fromhex('8B 41 10'):
        return {'font_metrics_status': 'font-getter-abi-mismatch'}
    texture = mem.u(font + 0x10) or font
    if mem.u(mem.u(texture) + 4) != 0x641DB0 or mem.read(0x641DB0, 3) != bytes.fromhex('8B C1 C3'):
        return {'font_metrics_status': 'unreviewed-texture-getter'}
    info = mem.u(texture + 0x38)
    if not info: return {'font_metrics_status': 'missing-font-info'}
    height = struct.unpack('<f', mem.read(info + 4, 4))[0] * 100
    if not math.isfinite(height) or not 0 < height <= 10000:
        return {'font_metrics_status': 'invalid-font-height'}
    return {'font_metrics_status': 'verified-native-getter-chain', 'font_info': hex(info),
            'font_height_px': height, 'draw_line_height_px': height * scale}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--database', type=Path, default=ROOT / 'build/party-roster-kpm-check/game/addresses.db')
    p.add_argument('--map', type=Path, default=ROOT / 'build/native-runtime/kmrp-native.map')
    p.add_argument('--catalog', type=Path, default=ROOT / 'build/text-layout-inventory/controls.csv')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--heap-scan', action='store_true', help='Also compare private-heap internal-string shapes with rooted owners')
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    mem = Memory(args.pid); modules = module_info(args.pid)
    exe = next((v for n, v in modules.items() if n == 'swkotor.exe'), None)
    if not exe or exe['base'] != 0x400000: raise ValueError('Expected 32-bit K1 at preferred base')
    db = sqlite3.connect('file:' + args.database.as_posix() + '?mode=ro', uri=True)
    classes = {v: (n, s) for n, s, v in db.execute('select class_name,size,vtable from classes') if v}
    text_tables = {0x73E3A4, 0x73E444}
    bounded_overrides = {}
    # TutorialBox's database size is a placeholder. Its constructor calls the
    # message-box base and writes its last observed byte at +0x995. This is a
    # verified minimum readable span, not a claim about full sizeof.
    if mem.read(0x6AA124,5) == b'\xE8' + struct.pack('<i',0x626DF0-0x6AA129):
        classes[0x755CD0] = ('CSWGuiTutorialBox',0x996)
        bounded_overrides['CSWGuiTutorialBox'] = 'constructor-derived minimum 0x996; full sizeof unknown'
    if (mem.read(0x6CAED3, 5) == b'\xE8' + struct.pack('<i', 0x41C6B0-0x6CAED8) and
            mem.read(0x6CAED8, 6) == bytes.fromhex('C7 03 B0 75 75 00')):
        classes[0x7575B0] = ('CSWGuiSaveGameEditBox', 0x160)
        bounded_overrides['CSWGuiSaveGameEditBox'] = (
            'constructor verifies base edit-box call/vtable; embedded span 0x550-0x3F0=0x160')
    if mem.u(0x741878 + 0x4C) != 0x45A2F0: raise ValueError('Native text ABI mismatch')
    if mem.read(0x417280, 2) != bytes.fromhex('6A FF'): raise ValueError('Native text constructor ABI mismatch')
    # These allocations are owned outside the generic control/row arrays.
    message_pools_verified = (
        mem.read(0x62663D, 6) == bytes.fromhex('89 86 64 07 00 00') and
        mem.read(0x6266F8, 6) == bytes.fromhex('89 AE 68 07 00 00') and
        mem.read(0x626616, 2) == bytes.fromhex('6A 40') and
        mem.read(0x626621, 5) == bytes.fromhex('68 B4 01 00 00'))
    dialog_top_verified = mem.read(0x6A8D9F, 6) == bytes.fromhex('89 86 FC 1D 00 00')
    floaty_registry_verified = (mem.read(0x68B93A, 6) == bytes.fromhex('8B 8E B4 5C 00 00') and
                               mem.read(0x68B940, 3) == bytes.fromhex('89 2C 81'))
    warnings = []; tagged = {}; registered = {}; custom = set()
    if 'kmrp.dll' in modules:
        kmrp = modules['kmrp.dll']; maptext = args.map.read_text()
        match = next(x for x in maptext.splitlines() if '?panels@' in x and 'K1RuntimeLayout.obj' in x)
        address = kmrp['base'] + int(match.split()[2], 16) - 0x10000000
        try:
            for pair in mem.tree(address):
                panel = mem.u(pair); resource = mem.string(pair + 4)
                registered[panel] = resource + '.gui'
                if kmrp['base'] <= mem.u(panel) < kmrp['base'] + kmrp['length']:
                    custom.add(panel)
                    current_line = next(x for x in maptext.splitlines() if '?current@' in x and 'K1TextOptions.obj' in x)
                    current_address = kmrp['base'] + int(current_line.split()[2],16) - 0x10000000
                    if mem.u(current_address) == panel:
                        classes[mem.u(panel)] = ('KmrpTextOptionsPanel',0x64)
                        bounded_overrides['KmrpTextOptionsPanel'] = 'local source panel allocation 0x64; private current pointer matched'
                for control_pair in mem.tree(pair + 4 + 24):
                    tag = mem.string(control_pair); control = mem.u(control_pair + 24)
                    expected = mem.u(control_pair + 28)
                    if mem.u(control) != expected: raise ValueError('Stale tracked control')
                    tagged[control] = (panel, tag)
        except (OSError, ValueError, StopIteration) as e: warnings.append('Tracked-map snapshot incomplete: ' + str(e))
    catalog = list(csv.DictReader(args.catalog.open(encoding='utf-8-sig')))
    direct = {}; prototypes = {}
    for r in catalog:
        if r['prototype_owner']: prototypes.setdefault((r['gui'],r['owner_tag']),[]).append(r)
        if not r['prototype_owner'] and r['path'].count('/CONTROLS[') == 1 and '/SCROLLBAR/' not in r['path']:
            direct.setdefault((r['gui'], r['tag']), []).append(r)
    manager = mem.u(0x7A39F4)
    roots = set(mem.array(manager + 0x88)) | set(mem.array(manager + 0x94)) | set(registered)
    tooltip = mem.u(manager+0x3C)
    if tooltip: roots.add(tooltip)
    # All bounded, checked control trees and embedded CSWGuiText subobjects.
    queue = [(a, a, 'panel', '') for a in sorted(roots) if a]
    background = mem.u(manager+0x7C)
    if background: queue.append((background,0,'manager-background',hex(manager)))
    objects = {}; wrappers = {}; panels = []
    while queue:
        obj, panel, origin, parent = queue.pop()
        if obj in objects: continue
        if len(objects) > 20000: raise ValueError('Census object limit exceeded')
        try:
            vt = mem.u(obj); name, size = classes.get(vt, ('unmapped-vtable', 0))
            objects[obj] = {'panel': panel, 'class': name, 'vtable': hex(vt), 'origin': origin, 'parent': parent,
                            'size_hint':size,'bounded_scan_supported':bool(24 <= (size or 0) <= 0x20000)}
            if name == 'CSWGuiMainInterface':
                if not floaty_registry_verified: raise ValueError('Floaty registry ABI mismatch')
                queue.extend((a, panel, 'native-floaty-array', hex(obj))
                             for a in mem.array(obj + 0x5CB4) if a)
            if name == 'CSWGuiInGameMessages':
                if not message_pools_verified: raise ValueError('Message pool constructor ABI mismatch')
                for field in (0x764, 0x768):
                    pool = mem.u(obj + field)
                    if not pool: continue
                    if mem.u(pool - 4) != 64: raise ValueError('Unexpected message label array cookie')
                    # Constructor allocates two fixed arrays of 64 labels, stride 0x1B4.
                    for index in range(64):
                        label = pool + index * 0x1B4
                        if classes.get(mem.u(label), ('', 0))[0] != 'CSWGuiLabelHilight':
                            raise ValueError('Unexpected message pool label vtable')
                        queue.append((label, panel, 'message-label-pool-' + hex(field), hex(obj)))
            if name == 'CSWGuiDialogCinematic':
                if not dialog_top_verified: raise ValueError('Nested dialogue panel ABI mismatch')
                nested = mem.u(obj + 0x1DFC)
                if nested:
                    if classes.get(mem.u(nested), ('', 0))[0] != 'CSWGuiDialogTop':
                        raise ValueError('Unexpected nested dialogue panel vtable')
                    queue.append((nested, panel, 'owned-dialogue-panel', hex(obj)))
            if name == 'CSWGuiListBox':
                raw_flags = mem.u(obj+0x2BC)
                row_count = len(mem.array(obj + 0x29C))
                objects[obj]['list_layout'] = {'raw_flags':hex(raw_flags),
                    'observed_row_count':row_count,
                    'layout_state_status':'populated-cache-requires-behavior-review' if row_count else 'unpopulated-cache-unverified',
                    'unequal_layout_bit_0x100':bool(raw_flags&0x100),
                    'cached_row_height':mem.u(obj+0x2B4),
                    'padding':mem.read(obj+0x2C0,1)[0],
                    'viewport_width':mem.u(obj+0x294),'viewport_height':mem.u(obj+0x298),
                    'visible_rows':struct.unpack('<h',mem.read(obj+0x2C4,2))[0],
                    'selection':struct.unpack('<h',mem.read(obj+0x2C6,2))[0],
                    'top_visible':struct.unpack('<h',mem.read(obj+0x2C8,2))[0],
                    'bottom_visible':struct.unpack('<h',mem.read(obj+0x2CA,2))[0]}
            if origin == 'panel':
                panels.append({'address': hex(obj), 'resource': registered.get(obj, 'unmapped'),
                               'class': name, 'vtable': hex(vt), 'runtime_custom_panel': obj in custom})
                queue.extend((a, panel, 'panel-array', hex(obj)) for a in mem.array(obj + 0x20) if a)
            else:
                try: queue.extend((a, panel, 'child-array', hex(obj)) for a in mem.array(obj + 0x18) if a)
                except (OSError, ValueError): pass
                if name == 'CSWGuiListBox':
                    queue.extend((a, panel, 'list-row-array', hex(obj)) for a in mem.array(obj + 0x29C) if a)
                    prototype = mem.u(obj + 0x2CC)
                    if prototype: queue.append((prototype, panel, 'list-prototype', hex(obj)))
            if not 24 <= (size or 0) <= 0x20000: continue
            data = mem.read(obj, size)
            for off in range(0, len(data) - 0x70 + 1, 4):
                if struct.unpack_from('<I', data, off)[0] not in text_tables: continue
                wrapper = obj + off
                if mem.u(wrapper + 0x68) != wrapper: continue  # text_params.text_object back-pointer
                internal = mem.u(wrapper + 0x14)
                if internal and mem.u(internal) != 0x741878: continue
                # Prefer the smallest containing widget over a whole containing panel.
                old = wrappers.get(wrapper)
                if old and old['owner_size'] <= size: continue
                tag_info = tagged.get(obj)
                tag = tag_info[1] if tag_info else ''
                resource = registered.get(panel, '')
                matches = direct.get((resource, tag), []) if tag and panel not in custom else []
                expected = matches[0] if len(matches) == 1 else None
                association = 'exact-tracked-template' if expected else ''
                if not expected and origin in ('list-prototype','list-row-array') and parent:
                    parent_obj = int(parent,16)
                    parent_tag = tagged.get(parent_obj)
                    related = prototypes.get((resource,parent_tag[1]),[]) if parent_tag else []
                    if len(related)==1:
                        expected = related[0]
                        association = 'list-prototype-related' if origin=='list-prototype' else 'list-row-related'
                additional_member = (name in ('CSWGuiInGameItemEntry', 'CSWGuiStoreItemEntry') and off == 0x324 or
                                     name == 'CSWUpgradeItemEntry' and off == 0x334)
                if expected and additional_member:
                    association += '-additional-member'
                row = {'panel': hex(panel), 'gui': resource, 'owner': hex(obj), 'owner_class': name,
                       'owner_vtable': hex(vt), 'owner_size': size, 'tag': tag, 'origin': origin,
                       'wrapper': hex(wrapper), 'wrapper_offset': hex(off), 'internal': hex(internal), 'raw_owner_flags':hex(mem.u(obj+0x44)),
                       'catalog_path': expected['path'] if expected else '',
                       'match_status': association if expected else 'runtime-custom-panel' if panel in custom else 'manager-owned-no-gui-slot' if origin=='manager-background' else 'unmatched-review',
                       'requested_font': mem.read(wrapper + 0x24, 16).split(b'\0')[0].decode('ascii', 'replace'),
                       'template_font': expected['font'] if expected else '', 'template_font_matches': '', 'effective_scale': '',
                       'template_font_scope': ('different-native-text-member' if additional_member else 'matched-text-member') if expected else 'unresolved',
                       'content_x': '', 'content_y': '', 'content_width': '', 'content_height': '',
                       'wrapped_lines': '', 'alignment': '', 'font_object': '', 'text_present': False,
                       'font_metrics_status': 'no-internal-string', 'font_info': '',
                       'font_height_px': '', 'draw_line_height_px': ''}
                if expected and not additional_member:
                    row['template_font_matches'] = row['requested_font'].lower() in (expected['font'],expected['font']+'a',expected['font']+'b')
                if internal:
                    raw = mem.read(internal, 0x48)
                    scale = struct.unpack_from('<f', raw, 0x40)[0]
                    if not math.isfinite(scale) or not 0 < scale <= 128: continue
                    xywh = struct.unpack_from('<4i', raw, 4)
                    row.update(dict(zip(('content_x', 'content_y', 'content_width', 'content_height'), xywh)))
                    row.update(effective_scale=scale, wrapped_lines=struct.unpack_from('<I', raw, 0x38)[0],
                               alignment=raw[0x46], font_object=hex(struct.unpack_from('<I', raw, 0x18)[0]),
                               text_present=bool(mem.read(struct.unpack_from('<I', raw, 0x14)[0], 1)[0]))
                    try: row.update(font_metrics(mem, int(row['font_object'], 16), scale))
                    except (OSError, ValueError): row['font_metrics_status'] = 'unreadable-font-metrics'
                wrappers[wrapper] = row
        except (OSError, ValueError) as e: warnings.append(hex(obj) + ': ' + str(e))
    rows = sorted(wrappers.values(), key=lambda r: (r['gui'], r['panel'], r['owner'], r['wrapper']))
    if rows:
        with (args.out / 'text-objects.csv').open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    owned = {}
    for r in rows:
        if r['internal'] != '0x0': owned.setdefault(int(r['internal'],16),[]).append(r['wrapper'])
    heap = heap_strings(mem, owned) if args.heap_scan else None
    if heap is not None: (args.out / 'heap-comparison.json').write_text(json.dumps(heap,indent=2)+'\n')
    object_rows = [{'address':hex(a),**r} for a,r in sorted(objects.items())]
    (args.out / 'object-tree.json').write_text(json.dumps(object_rows,indent=2)+'\n')
    manifest = {'pid': args.pid, 'captured_unix': time.time(), 'access': 'PROCESS_QUERY_INFORMATION | PROCESS_VM_READ',
                'manager': hex(manager), 'bounded_size_overrides':bounded_overrides, 'panels': panels, 'tracked_panels': len(registered),
                'walked_objects': len(objects), 'unscanned_object_sizes':sum(not r['bounded_scan_supported'] for r in objects.values()),
                'unknown_vtable_objects':sum(r['class']=='unmapped-vtable' for r in objects.values()),
                'heap_comparison':{k:v for k,v in heap.items() if k not in ('objects','limits','wrapper_candidates')} if heap else None,
                'text_wrappers': len(rows),
                'instantiated_strings': sum(r['internal'] != '0x0' for r in rows),
                'nonempty_strings': sum(r['text_present'] for r in rows),
                'match_counts': dict(Counter(r['match_status'] for r in rows)),
                'related_template_font_mismatches':sum(r['template_font_matches'] is False for r in rows),
                'classes': dict(Counter(r['owner_class'] for r in rows)),
                'warnings': warnings, 'modules': modules,
                'catalog_sha256': hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
                'database_sha256': hashlib.sha256(args.database.read_bytes()).hexdigest(),
                'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'map_sha256': hashlib.sha256(args.map.read_bytes()).hexdigest(),
                'limits': ['Not an allocation/event trace; transient or unopened-screen objects are not observed.',
                           'Only rooted GUI objects with known bounded class sizes are searched.',
                           'Database class sizes/names are hints; unknown classes remain coverage gaps.',
                           'Direct font rendering and objects outside GUI registries require separate coverage.',
                           'An exact template match records binding, not proof that geometry/font stayed unchanged.',
                           'Snapshot is not atomic; a changing screen can invalidate reads.']}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    mem.close()
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('modules', 'limits', 'database_sha256', 'map_sha256', 'catalog_sha256')}, indent=2))


if __name__ == '__main__': main()
