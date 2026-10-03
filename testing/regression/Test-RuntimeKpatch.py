"""Archive integrity/determinism and byte-guard regressions for the native preview."""
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import build_runtime_kpatch as preview

module = ROOT / 'build/native-preview/kmrp-native-preview.dll'
with tempfile.TemporaryDirectory(prefix='kmrp-native-preview-') as temporary:
    folder = Path(temporary)
    one = preview.build(module, folder / 'one')
    two = preview.build(module, folder / 'two')
    assert one['sha256'] == two['sha256'], 'Same-input archive build is not deterministic'
    source = Path(one['file'])
    with zipfile.ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    cases = {
        'stolen-byte corruption': ('kotor1.hooks.toml', b'0x3D, 0x20, 0x03', b'0x3C, 0x20, 0x03'),
        'missing target': ('kotor1.hooks.toml', preview.build_kpatch.STEAM.encode(), b'unsupported'),
        'external dependency': ('manifest.toml', b'requires = []', b'requires = ["kmrp"]'),
        'wrong callback parameter': ('kotor1.hooks.toml', b'source = "[esp+4]"', b'source = "[esp+12]"'),
    }
    for case, (entry, before, after) in cases.items():
        assert before in files[entry]
        corrupt = dict(files)
        corrupt[entry] = corrupt[entry].replace(before, after, 1)
        target = folder / 'corrupt.kpatch'
        with zipfile.ZipFile(target, 'w') as archive:
            for name, data in corrupt.items():
                archive.writestr(name, data)
        try:
            preview.validate(target)
        except ValueError:
            print(f'PASS: rejects {case}')
        else:
            raise AssertionError(f'Accepted {case}')
    with zipfile.ZipFile(folder / 'extra.kpatch', 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr('kmrp-kpm.dat', b'unwanted external engine payload')
    try:
        preview.validate(folder / 'extra.kpatch')
    except ValueError:
        print('PASS: rejects extra payload')
    else:
        raise AssertionError('Accepted extra payload')
    clean = ROOT / 'build-inputs/swkotornopatch.exe'
    if clean.exists():
        assert preview.verify_clean(clean)['guarded_hook_sites'] == 12
        print('PASS: canonical clean byte guards and native return/branch contracts')
print('PASS: preview archive export/source integrity and deterministic rebuild')
