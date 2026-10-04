#!/usr/bin/env python3
"""Validate KMRP's packaged patch, KMRP.kpatch, and reject corrupted copies of it.

Run after building the module and the patch (build_kmrp.ps1, or
src/controller-native/build_native_runtime.cmd and tools/build_native_kpatch.py);
no game EXE is required. Until 2026-10-04 this checked the four patches of
tools/build_kpatch.py.

The module is 189 MB and is stored, not compressed, so each corrupted copy is
written with the same entries and the module's bytes untouched.
"""
from pathlib import Path
import sys
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import build_kpatch
import build_native_kpatch as native

source = next((p for p in (ROOT / 'build/kmrp/kpm-patches' / native.NAME, ROOT / 'dist/native' / native.NAME)
               if p.exists()), None)
assert source, 'KMRP.kpatch has not been built'
result = native.validate(source)
assert result['id'] == 'kmrp' and result['options'] == ['controller', 'map-notes'], result
assert result['hooks_by_option']['map-notes'] == 0, 'map notes gate no hook'
print(f"PASS: {source.name} validates ({result['hooks']} hooks, {result['hooks_by_option']['controller']} for the controller option)")

with zipfile.ZipFile(source) as archive:
    files = {name: archive.read(name) for name in archive.namelist()}
hooks_name = native.HOOKS


def corrupted(case):
    changed = dict(files)
    text = files[hooks_name].decode()
    manifest = files['manifest.toml'].decode()
    if case == 'original bytes':
        hook = tomllib.loads(text)['hooks'][0]
        line = 'original_bytes = [' + ', '.join(f'0x{b:02X}' for b in hook['original_bytes']) + ']'
        flipped = hook['original_bytes'].copy()
        flipped[0] ^= 1
        assert line in text
        text = text.replace(line, 'original_bytes = [' + ', '.join(f'0x{b:02X}' for b in flipped) + ']', 1)
    elif case == 'static replacement':
        name = native.LARGE_ADDRESS
        large = files[name].decode()
        assert 'replacement_bytes = [0x2F, 0x01]' in large
        changed[name] = large.replace('replacement_bytes = [0x2F, 0x01]', 'replacement_bytes = [0x0F, 0x01]').encode()
    elif case == 'missing runtime hooks':
        text = text.split('[[hooks]]')[0]
    elif case == 'target versions':
        assert ', "' + build_kpatch.STEAM + '"' in text
        text = text.replace(', "' + build_kpatch.STEAM + '"', '', 1)
    elif case == 'a condition dropped':
        assert 'when = "controller"\n' in text
        text = text.replace('when = "controller"\n', '', 1)
    elif case == 'an undeclared option':
        text = text.replace('when = "controller"', 'when = "rumble"', 1)
    elif case == 'a third option':
        manifest += '\n[[patch.options]]\nid = "movies"\nname = "Movie fixes"\ndescription = "x"\ntype = "toggle"\ndefault = true\n'
    elif case == 'a conflict with itself':
        assert 'conflicts = [' in manifest
        manifest = manifest.replace('conflicts = [', 'conflicts = ["kmrp", ', 1)
    elif case == 'an external dependency':
        assert 'requires = []' in manifest
        manifest = manifest.replace('requires = []', 'requires = ["k1widescreenpatch"]')
    elif case == 'an extra file':
        changed['Override/extra.gui'] = b'x'
    changed[hooks_name] = text.encode()
    changed['manifest.toml'] = manifest.encode()
    return changed


with tempfile.TemporaryDirectory(prefix='kmrp-kpatch-source-') as temporary:
    path = Path(temporary) / native.NAME
    for case in ['original bytes', 'static replacement', 'missing runtime hooks', 'target versions',
                 'a condition dropped', 'an undeclared option', 'a third option', 'a conflict with itself',
                 'an external dependency', 'an extra file']:
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in corrupted(case).items():
                method = zipfile.ZIP_STORED if name == native.MODULE else zipfile.ZIP_DEFLATED
                archive.writestr(zipfile.ZipInfo(name), data, compress_type=method)
        try:
            native.validate(path)
        except (ValueError, KeyError, tomllib.TOMLDecodeError) as error:
            print(f'PASS: rejects {case} ({str(error)[:60]})')
        else:
            raise AssertionError(f'{case}: the corrupted patch was accepted')
print('PASS: KMRP.kpatch source guards')
