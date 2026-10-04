#!/usr/bin/env python3
"""Build/check the first standalone native KMRP vertical slice (experimental).

No installer data, generated GUI archives, controller module or game executable
is a build input. Existing production package builds are deliberately separate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tomllib
import zipfile
from pathlib import Path
import build_kpatch
import kmrp_controller

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'src/controller-native/kotor1-runtime-preview.hooks.toml'
ID = 'kmrp-native-preview'
NAME = 'KMRP Native Preview.kpatch'
# Keyboard repairs and the existing memory-safety hooks are independent of the
# old engine payload and resolution-specific GUI resources.
REUSED = {0x41A9D0, 0x41CE20, 0x40C24E, 0x41FEB5, 0x46BE64,
          0x4A847C, 0x4A8380, 0x5DDE32}
PREVIEW_PARAMETERS = {
    'KmrpAllowRuntimeResolutionK1': [('esp+4', 'pointer'), ('esp+8', 'pointer')],
    'KmrpResolutionRequestedK1': [('ecx', 'pointer'), ('esp+4', 'pointer'), ('esp+8', 'pointer')],
    'KmrpResolutionObservedK1': [('ecx', 'pointer')],
}

def hooks():
    source = [kmrp_controller.as_installed(h) for h in kmrp_controller.kpm_patch_hooks('kmrp')
              if h['address'] in REUSED]
    if {h['address'] for h in source} != REUSED:
        raise ValueError('Existing core hooks changed; review the preview explicitly')
    table = tomllib.loads(TABLE.read_text())
    if set(table['metadata']['target_versions']) != set(build_kpatch.VERSIONS.values()):
        raise ValueError('Preview table target builds changed')
    for h in table['hooks']:
        parameters = [(p['source'], p['type']) for p in h.get('parameters', [])]
        if h['type'] == 'simple' and parameters:
            raise ValueError('Simple patches cannot carry callback parameters')
        if h.get('function') in PREVIEW_PARAMETERS and parameters != PREVIEW_PARAMETERS[h['function']]:
            raise ValueError(f"Callback parameter contract changed: {h['function']}")
    source += table['hooks']
    return sorted(source, key=lambda h: h['address'])

def validate(path: Path):
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) != 3 or set(z.namelist()) != {'manifest.toml', 'kotor1.hooks.toml', 'binaries/windows_x86.dll'}:
            raise ValueError('Unexpected files or external payload dependency')
        manifest = tomllib.loads(z.read('manifest.toml').decode())['patch']
        for key in ('id', 'name', 'version', 'author', 'description'):
            if not isinstance(manifest.get(key), str) or not manifest[key].strip():
                raise ValueError(f'Invalid manifest {key}')
        if manifest['id'] != ID or manifest['requires']:
            raise ValueError('Preview must be independent')
        if manifest['supported_versions'] != build_kpatch.VERSIONS:
            raise ValueError('Unexpected target builds')
        actual = tomllib.loads(z.read('kotor1.hooks.toml').decode())
        if set(actual['metadata']['target_versions']) != set(build_kpatch.VERSIONS.values()):
            raise ValueError('Packaged target builds differ from source')
        if ([kmrp_controller.normalised(h) for h in actual['hooks']] !=
                [kmrp_controller.normalised(h) for h in hooks()]):
            raise ValueError('Packaged hooks differ from source')
        exports = build_kpatch.exports_of(z.read('binaries/windows_x86.dll'))
        requested = {h['function'] for h in hooks() if h.get('function')}
        if exports != requested:
            raise ValueError(f'Module exports differ: {exports ^ requested}')
        addresses = set()
        for h in hooks():
            span = set(range(h['address'], h['address'] + len(h['original_bytes'])))
            if span & addresses or not span or (h['type'] in ('detour', 'replace') and len(span) < 5):
                raise ValueError('Hook ranges overlap or are too short')
            addresses |= span
            if h['type'] == 'simple' and len(h['replacement_bytes']) != len(span):
                raise ValueError('Simple patch changes length')
            if 'consumed_exit_address' in h and 'eax' not in h.get('exclude_from_restore', []):
                raise ValueError('Consumed exit loses EAX')
    return {'file': str(path), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            'hooks': len(hooks()), 'installer_dependencies': [], 'controller_exports': []}

def verify_clean(clean: Path):
    """Optional verification input, never an input to the shipped module/archive."""
    data = clean.read_bytes()
    sha = hashlib.sha256(data).hexdigest().upper()
    if sha not in (build_kpatch.CD_1_03, build_kpatch.GOG):
        raise ValueError('Byte verification requires canonical clean CD 1.03 or GOG')
    for h in hooks():
        at = h['address'] - 0x400000
        if data[at:at + len(h['original_bytes'])] != bytes(h['original_bytes']):
            raise ValueError(f"Clean bytes disagree at {h['address']:#010x}")
    if data[0x1f0cd2:0x1f0cd5] != bytes.fromhex('C2 08 00'):
        raise ValueError('Resolution consumed exit no longer returns/pops two arguments')
    if 0x627861 + int.from_bytes(data[0x227860:0x227861], signed=True) != 0x6278ba:
        raise ValueError('Original tooltip branch target changed')
    return {'sha256': sha, 'bytes': len(data), 'guarded_hook_sites': len(hooks())}

def build(module: Path, out: Path):
    patch = {
        'id': ID, 'name': 'KMRP Native Runtime Preview (experimental)',
        'description': 'First standalone KMRP runtime prototype: exposes dimension-valid '
            'driver display modes in Graphics/Resolution, preserves native mode switching, '
            'and includes core keyboard and memory-safety repairs. No controller or KMRP '
            'installer required. Full KMRP layout, font, map and movie migration is unfinished; '
            'this is not the complete restoration patch.',
        'requires': [],
        'conflicts': ['kmrp', 'kmrp-controller', 'kmrp-movies', 'kmrp-map-notes',
                      'scaled-kotor', 'k1widescreenpatch', 'expanded-keyboard-control']
                      + kmrp_controller.kpm_same_fix(),
    }
    out.mkdir(parents=True, exist_ok=True)
    target = out / NAME
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in [
            ('manifest.toml', build_kpatch.render_manifest(patch, '0.0.1', 0).encode()),
            ('kotor1.hooks.toml', build_kpatch.render_hooks(hooks(), source=str(TABLE.name)).encode()),
            ('binaries/windows_x86.dll', module.read_bytes()),
        ]:
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    result = validate(target)
    (out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--module', type=Path, default=ROOT / 'build/native-preview/kmrp-native-preview.dll')
    p.add_argument('--out', type=Path, default=ROOT / 'dist/native-preview')
    p.add_argument('--check', type=Path)
    p.add_argument('--verify-clean', type=Path, help='Optional clean CD/GOG byte guard verification')
    args = p.parse_args()
    result = validate(args.check) if args.check else build(args.module, args.out)
    if args.verify_clean:
        result['clean_verification'] = verify_clean(args.verify_clean)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
