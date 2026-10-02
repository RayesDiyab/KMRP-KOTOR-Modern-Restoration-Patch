#!/usr/bin/env python3
"""Exercise uninstall's runtime-ownership decision with isolated KPM records."""
import json
import subprocess
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'macos/kmrp-mac.sh').read_text()
function = source[source.index('kpm_holds_only_kmrp() {'):source.index('\ndo_uninstall()', source.index('kpm_holds_only_kmrp() {'))]
with tempfile.TemporaryDirectory(prefix='kmrp-kpm-ownership-') as folder:
    mac = Path(folder)
    config = mac / 'patch_config.toml'
    state = mac / 'kpm_install_state.json'
    modules = mac / 'patches'
    modules.mkdir()
    (modules / 'kmrp.dylib').write_bytes(b'fixture')
    config.write_text('[[patches]]\nid = "kmrp"\n')
    script = 'MACOS=$1\n' + function + '\nkpm_holds_only_kmrp\n'
    cases = [
        ('legacy absent state', None, True),
        ('only KMRP', json.dumps({'InstalledPatches': ['kmrp']}), True),
        ('empty state list, KMRP config', json.dumps({'InstalledPatches': []}), True),
        ('module-less foreign patch', json.dumps({'InstalledPatches': ['kmrp', 'foreign-byte-patch']}), False),
        ('foreign only', json.dumps({'InstalledPatches': ['foreign']}), False),
        ('missing list', '{}', False),
        ('malformed JSON', '{', False),
        ('string instead of array', '{"InstalledPatches":"kmrp"}', False),
        ('non-string ID', '{"InstalledPatches":[1]}', False),
        ('space inside ID', '{"InstalledPatches":["k mrp"]}', False),
    ]
    def check(name, expected):
        result = subprocess.run(['zsh', '-c', script, 'ownership-test', str(mac)], capture_output=True, text=True)
        assert (result.returncode == 0) == expected, (name, result.returncode, result.stderr)
    for name, text, expected in cases:
        if text is None:
            state.unlink(missing_ok=True)
        else:
            state.write_text(text)
        check(name, expected)
    state.write_text('{"InstalledPatches":["kmrp"]}')
    config.write_text('[[patches]]\nid = "foreign"\n')
    check('foreign config', False)
    config.write_text('')
    check('no config IDs', False)
    config.write_text('[[patches]]\nid = "kmrp"\n')
    (modules / 'foreign.dylib').write_bytes(b'fixture')
    check('foreign module', False)
    (modules / 'foreign.dylib').unlink()
    (modules / 'foreign-directory').mkdir()
    check('foreign directory', False)
print('PASS KPM ownership: module-less foreign patches, invalid state, legacy state, config and modules')
