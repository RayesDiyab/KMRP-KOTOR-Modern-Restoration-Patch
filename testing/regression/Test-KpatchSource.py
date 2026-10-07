#!/usr/bin/env python3
"""Validate KMRP's packaged patch, KMRP.kpatch, and reject corrupted copies of it.

Run after building the module and the patch (build_kmrp.ps1, or
src/controller-native/build_native_runtime.cmd and tools/build_native_kpatch.py);
no game EXE is required. Until 2026-10-04 this checked the four patches of
tools/build_kpatch.py, which was removed that day.

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
import kpatch_common
import build_native_kpatch as native

source = next((p for p in (ROOT / 'build/kmrp/kpm-patches' / native.NAME, ROOT / 'dist/native' / native.NAME)
               if p.exists()), None)
assert source, 'KMRP.kpatch has not been built'
result = native.validate(source)
# No controller option since 2026-10-05: controller support is a patch of its own.
assert result['id'] == 'kmrp' and result['options'] == ['map-notes', 'hd-icons', 'debug-logs'], result
assert result['hooks_by_option']['map-notes'] == 0, 'map notes gate no hook'
assert result['hooks_by_option']['debug-logs'] == 0, 'debug logs gate no hook'
print(f"PASS: {source.name} validates ({result['hooks']} hooks, none an option's)")

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
        assert ', "' + kpatch_common.STEAM + '"' in text
        text = text.replace(', "' + kpatch_common.STEAM + '"', '', 1)
    elif case in ('a condition added', 'an undeclared option'):
        # No hook has a condition now, so one is put on the first hook: a declared
        # option's, which the source does not give it, and an option that does not exist.
        assert 'when = ' not in text
        at = text.index('\n', text.index('address = ')) + 1
        text = text[:at] + ('when = "map-notes"\n' if case == 'a condition added' else 'when = "rumble"\n') + text[at:]
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
                 'a condition added', 'an undeclared option', 'a third option', 'a conflict with itself',
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

# The list rows' measured table is a copy of the Mac's (K1RuntimeLayout.cpp, "List rows"):
# from its first declaration on the two files are the same, once the Mac's is in the tree.
ROOT = Path(__file__).resolve().parents[2]


def table_of(path):
    text = path.read_text(encoding='utf-8').replace(chr(13) + chr(10), chr(10))
    start = 'const char* const kMeasuredLists[] = {'
    assert start in text, f'{path.name} has no table'
    return text[text.index(start):].strip()


ours = table_of(ROOT / 'src/controller-native/K1ListRows.inc')
mac = ROOT / 'macos/patches/kmrp-assets/list_rows.inc'
if mac.is_file():
    assert ours == table_of(mac), 'K1ListRows.inc differs from macos/patches/kmrp-assets/list_rows.inc'
    print('PASS: K1ListRows.inc is the Mac table')
else:
    print('PASS: K1ListRows.inc has its table (the Mac file is not in this tree to compare with)')
print('PASS: KMRP.kpatch source guards')
