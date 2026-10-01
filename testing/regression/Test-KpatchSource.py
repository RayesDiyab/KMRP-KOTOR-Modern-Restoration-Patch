#!/usr/bin/env python3
"""Validate packaged source-only KPM patches and reject corrupted guarded hooks.

Run after building the native module and .kpatch files; no game EXE is required.
"""
import contextlib
import io
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import build_kpatch

source = ROOT / 'build/kmrp/kpm-patches'
assert build_kpatch.check(source) == 0
with tempfile.TemporaryDirectory(prefix='kmrp-kpatch-source-') as temporary:
    folder = Path(temporary)
    cases = ['original bytes', 'static replacement', 'missing runtime hooks', 'target versions']
    for case in cases:
        for path in source.glob('*.kpatch'):
            shutil.copy2(path, folder / path.name)
        path = folder / 'KMRP.kpatch'
        with zipfile.ZipFile(path) as archive:
            files = {name:archive.read(name) for name in archive.namelist()}
        if case == 'static replacement':
            name = 'kotor1-cd-large-address.hooks.toml'
            text = files[name].decode()
            assert 'replacement_bytes = [0x2F, 0x01]' in text
            files[name] = text.replace('replacement_bytes = [0x2F, 0x01]',
                                       'replacement_bytes = [0x0F, 0x01]').encode()
        else:
            name = 'kotor1.hooks.toml'
            text = files[name].decode()
            if case == 'original bytes':
                hook = tomllib.loads(text)['hooks'][0]
                line = 'original_bytes = [' + ', '.join(f'0x{b:02X}' for b in hook['original_bytes']) + ']'
                changed = hook['original_bytes'].copy()
                changed[0] ^= 1
                replacement = 'original_bytes = [' + ', '.join(f'0x{b:02X}' for b in changed) + ']'
                text = text.replace(line, replacement, 1)
            elif case == 'missing runtime hooks':
                text = text.split('[[hooks]]')[0]
            elif case == 'target versions':
                text = text.replace(', "' + build_kpatch.STEAM + '"', '', 1)
            files[name] = text.encode()
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name,data in files.items():
                archive.writestr(name,data)
        with contextlib.redirect_stdout(io.StringIO()):
            status = build_kpatch.check(folder)
        assert status == 1, f'{case} corruption was accepted'
        print(f'PASS: rejects corrupted {case}')
print('PASS: source-only KPM package guards')
