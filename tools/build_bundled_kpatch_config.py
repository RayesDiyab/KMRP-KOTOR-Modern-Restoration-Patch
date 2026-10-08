#!/usr/bin/env python3
"""A bundled KOTOR Patch Manager patch of another author's, for KMRP's installer.

KMRP's installer installs KOTOR Patch Manager's runtime itself and writes
patch_config.toml as KPM's applier would. For its own two patches the hooks come from
their builders (--config-dir). For a patch KMRP only carries, unchanged, as its author
released it, this script makes the same thing from the .kpatch file:

  <id>.hooks.toml    every hook of the patch for KOTOR 1 as a [[patches.hooks]] block

The blocks carry each hook's fields as the patch's own hooks file has them, which are
the fields KPM's ConfigGenerator writes (third_party/Kotor-Patch-Manager,
src/KPatchCore/Applicators/ConfigGenerator.cs: address, original_bytes, type,
function, replacement_bytes, preserve_registers, preserve_flags, exclude_from_restore,
skip_original_bytes, consumed_exit_address, parameters); a field the file does not
give is left out, and the runtime takes its default, as with KPM.

Checked before anything is written, since the installer installs the patch beside
KMRP's two without KPM's own checks:

  * the patch declares the three executables KMRP accepts;
  * its module is where the installer takes it from (binaries/windows_x86.dll) and
    exports every function a hook names;
  * no hook is a static one (those are written to the executable when a patch is
    applied, which this installer does not do);
  * no hook overlaps a hook of KMRP's patch or of the controller patch, or a byte
    the engine recipe writes.

The one patch so far: D3M0's High FPS Fixes (MIT), 2026-10-09, an option of the
installer that is off by default.

Documentation standard: see `docs/documentation-standard.md`.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import kpatch_common                       # noqa: E402
import build_native_kpatch                 # noqa: E402
import build_controller_kpatch             # noqa: E402
import build_windows_engine as engine      # noqa: E402

MODULE = 'binaries/windows_x86.dll'
KOTOR1_HOOKS = 'kotor1.hooks.toml'
# The order KPM's ConfigGenerator writes a hook's fields in.
FIELDS = ('address', 'original_bytes', 'type', 'function', 'replacement_bytes', 'preserve_registers',
          'preserve_flags', 'exclude_from_restore', 'skip_original_bytes', 'consumed_exit_address')


def value(key, item):
    if isinstance(item, bool):
        return 'true' if item else 'false'
    if isinstance(item, int):
        return f'0x{item:08X}' if key.endswith('address') else str(item)
    if isinstance(item, str):
        return kpatch_common.toml_string(item)
    if isinstance(item, list) and all(isinstance(b, int) and not isinstance(b, bool) for b in item):
        return '[' + ', '.join(f'0x{b:02X}' for b in item) + ']'
    if isinstance(item, list) and all(isinstance(s, str) for s in item):
        return '[' + ', '.join(kpatch_common.toml_string(s) for s in item) + ']'
    raise ValueError(f'{key}: a value this script does not write: {item!r}')


def render(hooks):
    lines = []
    for hook in hooks:
        unknown = set(hook) - set(FIELDS) - {'parameters'}
        if unknown:
            raise ValueError(f"hook at {hook['address']:#010x}: fields KPM's config does not have: {sorted(unknown)}")
        lines += ['', '[[patches.hooks]]']
        lines += [f'{key} = {value(key, hook[key])}' for key in FIELDS if key in hook]
        for parameter in hook.get('parameters', []):
            if set(parameter) != {'source', 'type'}:
                raise ValueError(f"hook at {hook['address']:#010x}: a parameter with other fields")
            lines += ['[[patches.hooks.parameters]]', f"source = {kpatch_common.toml_string(parameter['source'])}",
                      f"type = {kpatch_common.toml_string(parameter['type'].lower())}"]
    return '\n'.join(lines) + '\n'


def spans_of_kmrp():
    """Every byte KMRP's two patches hook, and every byte the engine recipe writes."""
    spans = [(h['address'], len(h['original_bytes']), "KMRP's patch") for h in build_native_kpatch.all_hooks()]
    spans += [(h['address'], len(h['original_bytes']), 'the controller patch') for h in build_controller_kpatch.hooks()]
    _, recipe, _, _ = engine.build()
    spans += [(va, len(old), "KMRP's engine recipe") for _feature, va, old, _new in recipe.runs()]
    return spans


def read(kpatch: Path):
    with zipfile.ZipFile(kpatch) as z:
        names = set(z.namelist())
        if MODULE not in names or KOTOR1_HOOKS not in names or 'manifest.toml' not in names:
            raise ValueError(f'{kpatch.name}: not a KOTOR 1 patch with a module ({sorted(names)})')
        manifest = tomllib.loads(z.read('manifest.toml').decode('utf-8'))['patch']
        table = tomllib.loads(z.read(KOTOR1_HOOKS).decode('utf-8'))
        module = z.read(MODULE)
    return manifest, table, module


def check(kpatch: Path):
    manifest, table, module = read(kpatch)
    wanted = set(kpatch_common.VERSIONS.values())
    declared = {v.upper() for v in manifest['supported_versions'].values()}
    targets = {v.upper() for v in table['metadata']['target_versions']}
    if not wanted <= declared or not wanted <= targets:
        raise ValueError(f"{kpatch.name}: does not declare the three executables KMRP accepts")
    hooks = table['hooks']
    exports = kpatch_common.exports_of(module)
    for hook in hooks:
        if hook['type'] not in ('detour', 'simple', 'replace'):
            raise ValueError(f"hook at {hook['address']:#010x}: type {hook['type']!r} is not one the installer installs")
        if hook['type'] == 'detour' and hook['function'] not in exports:
            raise ValueError(f"the module does not export {hook['function']}")
    overlaps = []
    for hook in hooks:
        a, n = hook['address'], len(hook['original_bytes'])
        for b, m, owner in spans_of_kmrp_cached():
            if a < b + m and b < a + n:
                overlaps.append(f"{a:#010x}+{n} overlaps {owner} at {b:#010x}+{m}")
    if overlaps:
        raise ValueError(f'{kpatch.name} cannot be installed beside KMRP:\n  ' + '\n  '.join(overlaps))
    return manifest, hooks, module


_spans = None


def spans_of_kmrp_cached():
    global _spans
    if _spans is None:
        _spans = spans_of_kmrp()
    return _spans


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('kpatch', type=Path)
    p.add_argument('--config-dir', type=Path, required=True)
    p.add_argument('--id', help='The patch id the installer installs it as: must be the manifest\'s')
    args = p.parse_args()
    manifest, hooks, module = check(args.kpatch)
    if args.id and manifest['id'] != args.id:
        raise ValueError(f"{args.kpatch.name}: its id is {manifest['id']!r}, not {args.id!r}")
    args.config_dir.mkdir(parents=True, exist_ok=True)
    target = args.config_dir / f"{manifest['id']}.hooks.toml"
    target.write_text(render(hooks), newline='\n')
    # Read back as KPM's runtime would see it.
    written = tomllib.loads('[[patches]]\n' + target.read_text())['patches'][0]['hooks']
    if len(written) != len(hooks) or any(w['address'] != h['address'] or w['original_bytes'] != h['original_bytes']
                                         for w, h in zip(written, hooks)):
        raise ValueError('The written hooks do not read back as the patch\'s')
    print(json.dumps({
        'file': str(args.kpatch), 'id': manifest['id'], 'name': manifest['name'], 'version': manifest['version'],
        'author': manifest['author'], 'sha256': hashlib.sha256(args.kpatch.read_bytes()).hexdigest().upper(),
        'module_sha256': hashlib.sha256(module).hexdigest().upper(),
        'hooks': len(hooks), 'by_type': {t: sum(1 for h in hooks if h['type'] == t) for t in sorted({h['type'] for h in hooks})},
        'config_file': str(target),
    }, indent=2))


if __name__ == '__main__':
    main()
