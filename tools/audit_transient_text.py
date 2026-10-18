#!/usr/bin/env python3
"""Passively sample native K1 posted strings and GUI floaty labels.

Reads query/VM_READ process memory only. Does not invoke native code, inject,
change game state, or export game strings. Registration is not draw execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct
import time

from audit_live_text import Memory, module_info, font_metrics

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = '761f9466f456a83909036baebb5c43167d722387be66e54617ba20a8c49e9886'
# Exact native instructions establish allocation, ownership, fields and draw path.
# Addresses are preferred VA; FILE=VA-0x400000 in the inspected clean sections.
GUARDS = {
    0x44D4A6: '68 34 04 00 00',                 # PostedString allocation 0x434
    0x44D340: '89 96 04 04 00 00',              # remaining duration +404
    0x44D34A: '89 8E 08 04 00 00',              # initial duration +408
    0x44D354: '89 96 30 04 00 00',              # screen-grid y +430
    0x44D35B: '89 8E 2C 04 00 00',              # screen-grid x +42C
    0x44D37B: '89 86 00 04 00 00',              # character count +400
    0x44D41C: '8B 0D FC 90 7B 00',              # posted registry pointer
    0x44D425: 'FF 05 00 91 7B 00',              # registry count
    0x44D155: '8B 8E 30 04 00 00',
    0x44D15B: '8B 96 2C 04 00 00',
    0x44D164: 'E8 E7 FC FF FF',                 # AurPrintString
    0x44D18A: 'D8 25 74 E5 78 00',              # subtract frame delta
    0x44D6C0: 'E8 4B F9 FF FF',                 # AurRenderStrings -> Post
    0x44CF62: 'C6 05 5C E3 78 00 00',           # first-print bitmap branch selection
    0x68B7D9: '68 54 01 00 00',                 # floaty label allocation 0x154
    0x68B7FA: 'E8 D1 F4 D8 FF',                 # base CSWGuiLabel constructor
    0x68B7FF: 'C7 07 A8 3E 75 00',              # floaty vtable
    0x68B934: '8B 86 B8 5C 00 00',              # floaty registry count
    0x68B93A: '8B 8E B4 5C 00 00',              # floaty registry pointer
    0x68B940: '89 2C 81',                        # append floaty pointer
    0x68C4D8: '89 35 B4 3B 83 00',              # global MainInterface owner
    0x688EDA: '8D 8E D0 00 00 00',              # inherited label text wrapper
    0x688EE0: 'C7 46 0C C8 00 00 00',           # native width 200
    0x688FF8: 'D9 86 40 01 00 00',              # fld remaining +140
    0x689016: '8B 0D B4 3B 83 00',
    0x68B6F0: '8B 87 B4 5C 00 00',              # draw private array
    0x68B700: 'FF 52 38',                        # label virtual draw
}


def digest(path):
    p = Path(path)
    return {'path': str(p), 'bytes': p.stat().st_size,
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}


def finite(value, limit=1e9):
    if not math.isfinite(value) or abs(value) > limit:
        raise ValueError('Invalid finite native field')
    return value


def registry(mem, address, limit=4096):
    raw = mem.read(address, 12)
    pointer, count, capacity = struct.unpack('<III', raw)
    if count > capacity or capacity > limit or (count and not pointer):
        raise ValueError('Invalid registry count/capacity/pointer')
    pointers = list(struct.unpack('<' + str(count) + 'I', mem.read(pointer, count * 4))) if count else []
    if len(set(pointers)) != count or any(not p or p % 4 for p in pointers):
        raise ValueError('Null, duplicate or unaligned registered pointer')
    if mem.read(address, 12) != raw:
        raise ValueError('Registry changed while reading')
    return {'address': hex(address), 'pointer': hex(pointer), 'count': count,
            'capacity': capacity}, pointers, raw


def posted(mem, address):
    raw = mem.read(address, 0x434)
    length = struct.unpack_from('<I', raw, 0x400)[0]
    terminator = raw[:0x400].find(b'\0')
    if terminator < 0 or length != terminator:
        raise ValueError('Posted inline text/length mismatch')
    remaining, duration = struct.unpack_from('<2f', raw, 0x404)
    finite(remaining); finite(duration)
    colors = struct.unpack_from('<8f', raw, 0x40C)
    if any(not math.isfinite(x) or abs(x) > 1000 for x in colors):
        raise ValueError('Invalid posted color interpolation fields')
    x, y = struct.unpack_from('<2i', raw, 0x42C)
    return {'address': hex(address), 'family': 'posted-screen-string',
            'text_present': bool(length), 'character_count': length,
            'remaining_seconds': remaining, 'initial_seconds': duration,
            'position_grid': [x, y], 'content_rect': None,
            'font_metrics_status': 'screen-print-font-contract-not-gui-text',
            'observed_state': 'registered-native-object-not-draw-execution'}


def floaty(mem, address):
    raw = mem.read(address, 0x154)
    if struct.unpack_from('<I', raw)[0] != 0x753EA8:
        raise ValueError('Registered floaty vtable mismatch')
    wrapper = address + 0xD0
    if mem.u(wrapper) != 0x73E3A4 or mem.u(wrapper + 0x68) != wrapper:
        raise ValueError('Floaty CSWGuiText wrapper mismatch')
    internal = mem.u(wrapper + 0x14)
    text = mem.read(internal, 0x48)
    if struct.unpack_from('<I', text)[0] != 0x741878:
        raise ValueError('Floaty native string vtable mismatch')
    rect = list(struct.unpack_from('<4i', text, 4))
    if any(abs(v) > 32767 for v in rect) or rect[2] < 0 or rect[3] < 0:
        raise ValueError('Invalid floaty content rectangle')
    scale = finite(struct.unpack_from('<f', text, 0x40)[0])
    if not 0 < scale <= 128: raise ValueError('Invalid floaty local scale')
    for offset in (0x28, 0x34):
        ptr, count, cap = struct.unpack_from('<III', text, offset)
        if count > cap or cap > 1000000 or (count and not ptr):
            raise ValueError('Invalid floaty line array')
    remaining, duration = struct.unpack_from('<2f', raw, 0x140)
    finite(remaining); finite(duration)
    font = struct.unpack_from('<I', text, 0x18)[0]
    font_name = mem.read(wrapper + 0x24, 16).split(b'\0')[0].decode('ascii')
    if any(not (c.isalnum() or c == '_') for c in font_name):
        raise ValueError('Invalid font resource identifier')
    result = {'address': hex(address), 'family': 'gui-floaty-label',
              'text_present': bool(mem.read(struct.unpack_from('<I', text, 0x14)[0], 1)[0]),
              'wrapper': hex(wrapper), 'internal': hex(internal),
              'control_rect': list(struct.unpack_from('<4i', raw, 4)),
              'content_rect': rect, 'scale': scale, 'font': font_name,
              'font_object': hex(font), 'line_count': struct.unpack_from('<I', text, 0x38)[0],
              'remaining_seconds': remaining, 'initial_seconds': duration,
              'opacity': finite(struct.unpack_from('<f', raw, 0x110)[0]),
              'raw_owner_flags': hex(struct.unpack_from('<I', raw, 0x44)[0]),
              'observed_state': 'registered-native-object-not-draw-execution'}
    result.update(font_metrics(mem, font, scale))
    return result


COMBAT_BANNER_GUARDS = {
    0x5EDE70: '8B 41 04 8B 80 20 03 00 00 C3',  # wrapper -> internal combat-mode flag
    0x68CFC9: 'C7 86 28 77 00 00 50 BC 00 00',  # constructor's default message ID
    0x6877F5: '89 9E 28 77 00 00',               # SetCombatMessage stores message ID
}


def combat_banner(mem):
    """Snapshot actual combat mode and the ordinary top HUD label, without text."""
    app = mem.u(0x7A39FC)
    client = mem.u(app + 4) if app else 0
    native = mem.u(client + 4) if client else 0
    result = {'combat_mode': mem.u(native + 0x320) if native else None,
              'observed_state': 'non-atomic-control-state-not-draw-execution'}
    owner = mem.u(0x833BB4)
    if not owner:
        return dict(result, owner=None)
    if mem.u(owner) != 0x753F50:
        raise ValueError('Combat banner MainInterface vtable mismatch')
    label = owner + 0x735C
    wrapper = label + 0xD0
    if mem.u(label) != 0x73E5B8 or mem.u(wrapper) != 0x73E3A4:
        raise ValueError('Combat banner label/wrapper vtable mismatch')
    if mem.u(wrapper + 0x68) != wrapper:
        raise ValueError('Combat banner wrapper back-pointer mismatch')
    internal = mem.u(wrapper + 0x14)
    raw = mem.read(internal, 0x48)
    if struct.unpack_from('<I', raw)[0] != 0x741878:
        raise ValueError('Combat banner internal string vtable mismatch')
    pointer = struct.unpack_from('<I', raw, 0x14)[0]
    rect = list(struct.unpack_from('<4i', raw, 4))
    if any(abs(v) > 32767 for v in rect) or min(rect[2:]) < 0:
        raise ValueError('Invalid combat banner content rectangle')
    scale = finite(struct.unpack_from('<f', raw, 0x40)[0])
    if not 0 < scale <= 128:
        raise ValueError('Invalid combat banner scale')
    params_pointer = mem.u(label + 0xE8)
    font = struct.unpack_from('<I', raw, 0x18)[0]
    result.update({
        'owner': hex(owner), 'label': hex(label),
        'message_id': mem.u(owner + 0x7728),
        'message_id_limit': '48208 is also the constructor default, not proof of combat',
        'initial_timer': finite(struct.unpack('<f', mem.read(owner + 0x7720, 4))[0]),
        'remaining_timer': finite(struct.unpack('<f', mem.read(owner + 0x7724, 4))[0]),
        'params_text_present': bool(params_pointer and mem.read(params_pointer, 1)[0]),
        'params_character_count': mem.u(label + 0xEC),
        'internal_text_present': bool(pointer and mem.read(pointer, 1)[0]),
        'content_rect': rect,
        'line_count': struct.unpack_from('<I', raw, 0x38)[0],
        'alignment': struct.unpack_from('<H', raw, 0x46)[0],
        'scale': scale,
        'control_visible_bit': bool(mem.u(label + 0x44) & 2),
        'opacity': finite(struct.unpack('<f', mem.read(label + 0x110, 4))[0]),
    })
    result.update(font_metrics(mem, font, scale))
    if mem.u(0x833BB4) != owner or mem.u(wrapper + 0x14) != internal:
        raise ValueError('Combat banner owner/string changed during read')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--seconds', type=float, default=20)
    p.add_argument('--interval-ms', type=float, default=25)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--clean-exe', type=Path, default=ROOT / 'build-inputs/swkotornopatch.exe')
    p.add_argument('--combat-banner', action='store_true',
                   help='Also snapshot actual combat mode and top HUD message state')
    args = p.parse_args()
    if not 0 < args.seconds <= 120: p.error('--seconds must be in (0,120]')
    if not 20 <= args.interval_ms <= 50: p.error('--interval-ms must be 20..50')
    if args.out.exists() and any(args.out.iterdir()): p.error('--out must be empty/new')
    clean_identity = digest(args.clean_exe)
    if clean_identity['sha256'] != EXPECTED: raise ValueError('Unexpected clean native build')
    clean = args.clean_exe.read_bytes()
    guards = dict(GUARDS)
    if args.combat_banner:
        guards.update(COMBAT_BANNER_GUARDS)
    for address, expected in guards.items():
        if clean[address-0x400000:address-0x400000+len(bytes.fromhex(expected))] != bytes.fromhex(expected):
            raise ValueError('Static guard mismatch at ' + hex(address))
    modules = module_info(args.pid)
    exe = modules.get('swkotor.exe')
    if not exe or exe['base'] != 0x400000: raise ValueError('Expected native K1 at 0x400000')
    identities = {n: digest(v['path']) for n, v in modules.items() if n in ('swkotor.exe','kmrp.dll','kmrp-controller.dll')}
    mem = Memory(args.pid)
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {'started_utc': datetime.now(timezone.utc).isoformat(), 'pid': args.pid,
                'requested_seconds': args.seconds, 'requested_interval_ms': args.interval_ms,
                'clean_exe': clean_identity, 'identities': identities, 'modules': modules,
                'tool': digest(__file__), 'helper': digest(ROOT/'tools/audit_live_text.py'),
                'guards': {hex(a): v for a,v in guards.items()},
                'combat_banner_enabled': args.combat_banner,
                'limits': ['Read-only non-atomic polling. Objects can appear/disappear between samples.',
                           'Registered/nonempty objects do not establish actual draw execution or visibility.',
                           'Observed pointer epochs are not allocation identities; reuse can be missed.',
                           'Raw screen print has no verified GUI content rectangle and a separate font contract.',
                           'No injected hooks, native method calls, heap scan, or process suspension.'],
                'warnings': []}
    samples = []; epochs = []; active = {}; start = time.perf_counter(); deadline = start + args.seconds
    previous_tick = None; intervals = []; peak = {'posted-screen-string':0, 'gui-floaty-label':0}
    try:
        for address, expected in guards.items():
            if mem.read(address,len(bytes.fromhex(expected))) != bytes.fromhex(expected):
                raise ValueError('Live ABI guard mismatch at ' + hex(address))
        if mem.u(0x753EA8+0xA0) != 0x688FF0:
            raise ValueError('Floaty update vtable slot mismatch')
        while True:
            tick = time.perf_counter()
            if samples and tick >= deadline: break
            elapsed = tick-start
            if previous_tick is not None: intervals.append((tick-previous_tick)*1000)
            previous_tick = tick
            sample = {'index':len(samples),'elapsed_seconds':elapsed,'objects':[], 'warnings':[], 'registries':{}}
            sample['raw_screen_renderer'] = {
                'initialized': bool(mem.u(0x7B90F0)),
                'texture_branch_selected': bool(mem.read(0x78E35C, 1)[0]),
                'texture_font_index': struct.unpack('<i', mem.read(0x78E358, 4))[0],
                'interpretation': 'native selector state; not a draw-call trace'}
            if args.combat_banner:
                try:
                    sample['combat_banner'] = combat_banner(mem)
                except (OSError, ValueError, struct.error) as exc:
                    sample['warnings'].append({'family': 'combat-banner', 'error': str(exc)})
            successful = set()
            for family in ('posted-screen-string','gui-floaty-label'):
                try:
                    owner = mem.u(0x833BB4) if family == 'gui-floaty-label' else None
                    if owner and mem.u(owner) != 0x753F50:
                        raise ValueError('MainInterface owner vtable mismatch')
                    address = 0x7B90FC if family == 'posted-screen-string' else owner + 0x5CB4 if owner else None
                    if address is None:
                        sample['registries'][family] = {'owner':None,'count':0,'state':'owner-null'}
                        successful.add(family); continue
                    reg, pointers, initial = registry(mem,address)
                    if owner: reg['owner'] = hex(owner)
                    sample['registries'][family] = reg
                    objects = []
                    for pointer in pointers:
                        try: objects.append(posted(mem,pointer) if family == 'posted-screen-string' else floaty(mem,pointer))
                        except (OSError,ValueError,struct.error,UnicodeError) as exc:
                            sample['warnings'].append({'family':family,'address':hex(pointer),'error':str(exc)})
                    if mem.read(address,12) != initial or (owner and mem.u(0x833BB4) != owner):
                        raise ValueError('Owner/registry changed across object reads')
                    sample['objects'].extend(objects)
                    peak[family] = max(peak[family],reg['count'])
                    if len(objects) == reg['count']:
                        successful.add(family)
                except (OSError,ValueError,struct.error) as exc:
                    sample['warnings'].append({'family':family,'error':str(exc)})
            now_keys = {(o['family'],o['address']) for o in sample['objects']}
            for key in list(active):
                if key[0] in successful and key not in now_keys:
                    epochs[active.pop(key)]['first_absent_seconds'] = elapsed
            for obj in sample['objects']:
                key = (obj['family'],obj['address'])
                if key not in active:
                    active[key] = len(epochs)
                    epochs.append({'family':key[0],'address':key[1],'first_seen_seconds':elapsed,
                                   'last_seen_seconds':elapsed,'observed_samples':0})
                epoch = epochs[active[key]]; epoch['last_seen_seconds'] = elapsed; epoch['observed_samples'] += 1
                obj['observed_epoch'] = active[key]
            samples.append(sample)
            sample['read_duration_ms'] = (time.perf_counter()-tick)*1000
            target = start + len(samples)*args.interval_ms/1000
            time.sleep(max(0,min(target,deadline)-time.perf_counter()))
        manifest.update({'finished_utc':datetime.now(timezone.utc).isoformat(),
                         'elapsed_seconds':time.perf_counter()-start,'sample_count':len(samples),
                         'warning_count':sum(len(s['warnings']) for s in samples),'peak_registry_counts':peak,
                         'object_epoch_count':len(epochs),
                         'measured_intervals_ms':{'min':min(intervals) if intervals else None,
                                                  'max':max(intervals) if intervals else None,
                                                  'mean':sum(intervals)/len(intervals) if intervals else None}})
    except (OSError,ValueError,struct.error) as exc:
        manifest['fatal_error'] = str(exc)
        raise
    finally:
        mem.close()
        (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        (args.out/'samples.json').write_text(json.dumps(samples,indent=2)+'\n')
        (args.out/'observed-epochs.json').write_text(json.dumps(epochs,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ('sample_count','warning_count','peak_registry_counts','object_epoch_count','measured_intervals_ms')},indent=2))


if __name__ == '__main__': main()
