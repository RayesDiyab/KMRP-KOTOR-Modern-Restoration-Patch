#!/usr/bin/env python3
"""Build and check KMRP's patch for KOTOR Patch Manager: one .kpatch, id "kmrp".

One module (src/controller-native/build_native_runtime.cmd) with the engine recipe
and the resource bank embedded (tools/build_native_engine.py,
tools/build_native_assets.py). It needs no data file and no Override file, and
handles any resolution KMRP has a layout for at run time.

  dist/native/KMRP.kpatch                       id "kmrp"
  (build_kmrp.ps1 writes it to build/kmrp/kpm-patches instead, with --out)

Controller support and map notes are options of the patch, both on by default. The
movie fixes are not an option: they are part of KMRP (the maintainer, 2026-10-04,
after a day on which they were a third). A hook that belongs to an option carries `when`. No address has two
hooks, so a KOTOR Patch Manager without patch options (0.7.1), which ignores `when`
and the options, installs every hook: every option at its default. The module reads
what was chosen from the patch's [patches.options] table in patch_config.toml and
takes a missing table, or a missing value, as on.

KMRP's installer installs the same patch itself. For it, --config-dir writes the
patch's hooks as patch_config.toml blocks, in one file per condition:

  kmrp.hooks.toml                 the hooks that are always installed
  kmrp.hooks.<option>.toml        the hooks of one option, installed when it is on

The installer writes the patch's header, the hooks of the options the player kept,
and the [patches.options] table (KpmEditionOperations.InstallEngine).

The hooks are those of kotor1.hooks.toml (its "kmrp", "kmrp-movies" and
"kmrp-controller" groups) plus the module's own sites in
kotor1-native-runtime.hooks.toml.

Until 2026-10-04 this built two experimental packages, "kmrp-native" without
options (and a map-notes add-on beside it) and "kmrp-native-options". The
maintainer made the options package the final patch that day and gave it the id
"kmrp"; the others are retired and listed as conflicts.

Usage:
    python tools/build_native_kpatch.py [--module PATH] [--version X.Y.Z] [--config-dir DIR]
    python tools/build_native_kpatch.py --check FILE [--verify-clean EXE]
    python tools/build_native_kpatch.py --write-def FILE

Documentation standard: see `docs/documentation-standard.md`.
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
TABLE = ROOT / 'src/controller-native/kotor1-native-runtime.hooks.toml'
ID = 'kmrp'
NAME = 'KMRP.kpatch'
MODULE = 'binaries/windows_x86.dll'
HOOKS = 'kotor1.hooks.toml'
LARGE_ADDRESS = 'kotor1-cd-large-address.hooks.toml'
# The module embeds KOTOR High Resolution Menus' art (GPL-3.0) and the other bundled
# work THIRD_PARTY_NOTICES.md lists (SDL among it), so the archive carries the texts
# the installer carries. KPM reads only the entries it knows; these travel with the file.
LICENSES = {
    'licenses/LICENSE.txt': ROOT / 'LICENSE',
    'licenses/THIRD_PARTY_NOTICES.md': ROOT / 'THIRD_PARTY_NOTICES.md',
    'licenses/GPL-3.0-KOTOR-High-Resolution-Menus.txt':
        ROOT / 'build/kmrp/resources/GPL-3.0-KOTOR-High-Resolution-Menus.txt',
    # MIT: KOTOR Patch Manager's three memory-safety fixes and Saul0097's controller
    # sources are part of the module. zlib: SDL, which the module carries whole.
    'licenses/LICENSE-KOTOR-PATCH-MANAGER.txt': ROOT / 'third_party/Kotor-Patch-Manager/LICENSE',
    'licenses/SDL3-LICENSE.txt': ROOT / 'build/deps/SDL3-3.4.16/LICENSE.txt',
}
# The module's own callbacks and what each is handed.
PARAMETERS = {
    'KmrpAllowRuntimeResolutionK1': [('esp+4', 'pointer'), ('esp+8', 'pointer')],
    'KmrpResolutionRequestedK1': [('ecx', 'pointer'), ('esp+4', 'pointer'), ('esp+8', 'pointer')],
    'KmrpModeSwitchK1': [],
    'KmrpPrepareResourcesK1': [('ecx', 'pointer')],
    'KmrpPanelLayoutStartK1': [('ecx', 'pointer'), ('esp+4', 'pointer')],
    'KmrpPanelControlK1': [('ecx', 'pointer'), ('esp+4', 'pointer'), ('esp+8', 'pointer')],
    'KmrpPanelDestroyedK1': [('ecx', 'pointer')],
    'KmrpControlDestroyedK1': [('ecx', 'pointer')],
}
# KMRP's earlier patches, which this one replaces: the add-ons of the four-patch
# edition (whose core had this id), and the experimental packages of 2026-10.
RETIRED = ['kmrp-controller', 'kmrp-movies', 'kmrp-map-notes', 'kmrp-native',
           'kmrp-native-options', 'kmrp-native-map-notes', 'kmrp-native-preview']
# Other authors' patches that make a change this one makes too, or hook its sites.
OTHERS = (['hud-minimap-map-size-fix-v1', 'scaled-kotor', '4gb-patch', 'better-movie-playback-v1']
          + kmrp_controller.kpm_same_fix() + ['expanded-keyboard-control', 'xbox-controls-k1'])
PATCH = {
    'id': ID,
    'name': 'KMRP - KOTOR Modern Restoration Patch',
    'description': (
        'KMRP in one patch: the widescreen and high-resolution interface at the '
        'resolution chosen in Options, with the 4 GB, texture, grass and save-game '
        'memory fixes and the movie fixes. Controller support and map notes are options '
        'you can turn off. Needs no installer and writes nothing to Override.'),
    'requires': [],
    'conflicts': RETIRED + OTHERS,
}
# What the player can turn off, in the order the launcher lists it. Both on by default.
# The descriptions are the launcher's, so they say what the player gets.
OPTIONS = [
    {'id': 'controller', 'name': 'Controller support',
     'description': 'Play with an Xbox, PlayStation, Switch or Steam Deck controller, in the '
                    'game and in every menu, with matching button prompts and rumble.'},
    {'id': 'map-notes', 'name': 'Map notes',
     'description': "Shows the area map's notes where they belong (Derslok's map marker "
                    'corrections).'},
]


def _table():
    table = tomllib.loads(TABLE.read_text())
    if set(table['metadata']['target_versions']) != set(build_kpatch.VERSIONS.values()):
        raise ValueError('Native table target builds changed')
    for h in table['hooks']:
        parameters = [(p['source'], p['type']) for p in h.get('parameters', [])]
        if h['type'] == 'simple':
            if parameters or 'function' in h:
                raise ValueError('Simple patches carry no callback')
        elif parameters != PARAMETERS.get(h.get('function')):
            raise ValueError(f"Callback parameter contract changed: {h.get('function')}")
    return table['hooks']


def option_hooks():
    """Every runtime hook of the patch with its condition, by address: (hook, None)
    for one always installed, else (hook, option id) for one installed while that
    option is on."""
    # The core's hooks, always. The GUI and movie frame sites are among them and stay
    # one hook each: CoreGuiFrameK1 and CoreMovieFrameK1 run the controller's frame
    # themselves when the option is on. A variant per state would be two hooks at
    # one address, which a manager without options installs both of and refuses.
    conditioned = [(kmrp_controller.as_installed(h), None)
                   for h in kmrp_controller.kpm_patch_hooks('kmrp')]
    for h in kmrp_controller.kpm_patch_hooks('kmrp-controller'):
        conditioned.append((kmrp_controller.as_installed(h), 'controller'))
    for h in kmrp_controller.kpm_patch_hooks('kmrp-movies'):
        conditioned.append((kmrp_controller.as_installed(h), None))
    conditioned += [(h, None) for h in _table()]
    for index, (h, _) in enumerate(conditioned):
        span = range(h['address'], h['address'] + len(h['original_bytes']))
        if not span or (h['type'] in ('detour', 'replace') and len(span) < 5):
            raise ValueError(f"Hook too short at {h['address']:#010x}")
        if h['type'] == 'simple' and len(h['replacement_bytes']) != len(span):
            raise ValueError('Simple patch changes length')
        if 'consumed_exit_address' in h and 'eax' not in h.get('exclude_from_restore', []):
            raise ValueError('Consumed exit loses EAX')
        # Whatever their conditions: a manager without options installs them all.
        for other, _ in conditioned[:index]:
            if other['address'] < span.stop and span.start < other['address'] + len(other['original_bytes']):
                raise ValueError(f"Hooks overlap at {h['address']:#010x}")
    return sorted(conditioned, key=lambda pair: pair[0]['address'])


def all_hooks():
    """Every hook the patch can install: what the engine recipe must not touch."""
    return [h for h, _ in option_hooks()]


def functions():
    """Every callback a hook names: what the module exports."""
    return {h['function'] for h in all_hooks() if h.get('function')}


def render_hooks():
    """The patch's hooks file: build_kpatch's rendering, each conditional hook with
    its `when` after its address."""
    source = 'kotor1.hooks.toml and kotor1-native-runtime.hooks.toml; edit those files, not this one.'
    header = build_kpatch.render_hooks([], source=source)
    parts = [header.rstrip('\n')]
    for h, when in option_hooks():
        lines = build_kpatch.render_hooks([h], source=source)[len(header):].strip('\n').split('\n')
        if when:
            at = next(i for i, line in enumerate(lines) if line.startswith('address = '))
            lines.insert(at + 1, f'when = "{when}"')
        parts.append('\n'.join(lines))
    return '\n\n'.join(parts) + '\n'


def render_manifest(version: str) -> str:
    text = build_kpatch.render_manifest(PATCH, version, 0)
    for option in OPTIONS:
        text += '\n'.join([
            '', '[[patch.options]]',
            f"id = {build_kpatch.toml_string(option['id'])}",
            f"name = {build_kpatch.toml_string(option['name'])}",
            f"description = {build_kpatch.toml_string(option['description'])}",
            'type = "toggle"', 'default = true', ''])
    return text


def config_files():
    """The installer's pieces of patch_config.toml: the hooks as [[patches.hooks]]
    blocks, by condition. Name to text."""
    files = {}
    for condition in [None] + [o['id'] for o in OPTIONS]:
        selected = [h for h, when in option_hooks() if when == condition]
        if selected or condition is None:
            name = f'{ID}.hooks.toml' if condition is None else f'{ID}.hooks.{condition}.toml'
            files[name] = kmrp_controller.render_patch_hooks(selected)
    return files


def validate(path: Path):
    with zipfile.ZipFile(path) as z:
        if sorted(z.namelist()) != sorted(['manifest.toml', HOOKS, LARGE_ADDRESS, MODULE, *LICENSES]):
            raise ValueError('Unexpected files or external payload dependency')
        manifest = tomllib.loads(z.read('manifest.toml').decode())['patch']
        for key in ('id', 'name', 'version', 'author', 'description'):
            if not isinstance(manifest.get(key), str) or not manifest[key].strip():
                raise ValueError(f'Invalid manifest {key}')
        if manifest['id'] != ID or manifest['requires']:
            raise ValueError('The patch must be "kmrp" and require nothing')
        if not set(RETIRED) <= set(manifest['conflicts']) or ID in manifest['conflicts']:
            raise ValueError("Must conflict with KMRP's retired patches, and not with itself")
        if manifest['supported_versions'] != build_kpatch.VERSIONS:
            raise ValueError('Unexpected target builds')
        declared = manifest.get('options', [])
        if [(o['id'], o['name'], o['description'], o['type'], o['default']) for o in declared] != \
                [(o['id'], o['name'], o['description'], 'toggle', True) for o in OPTIONS]:
            raise ValueError('Packaged options differ from source')
        actual = tomllib.loads(z.read(HOOKS).decode())
        if set(actual['metadata']['target_versions']) != set(build_kpatch.VERSIONS.values()):
            raise ValueError('Packaged target builds differ from source')
        expected = option_hooks()
        if ([(kmrp_controller.normalised(h), h.get('when')) for h in actual['hooks']] !=
                [(kmrp_controller.normalised(h), when) for h, when in expected]):
            raise ValueError('Packaged hooks differ from source')
        addresses = [h['address'] for h in actual['hooks']]
        if len(set(addresses)) != len(addresses):
            raise ValueError('Two hooks share an address: a manager without options would refuse the patch')
        for _, when in expected:
            if when and when not in {o['id'] for o in OPTIONS}:
                raise ValueError(f'A hook depends on an undeclared option: {when}')
        large = tomllib.loads(z.read(LARGE_ADDRESS).decode())
        if (set(large['metadata']['target_versions']) != {build_kpatch.CD_1_03, build_kpatch.GOG}
                or [kmrp_controller.normalised(h) for h in large['hooks']] !=
                [kmrp_controller.normalised(build_kpatch.large_address_hook())]):
            raise ValueError('Packaged large-address hook differs from the documented one')
        for name, source in LICENSES.items():
            if z.read(name) != source.read_bytes():
                raise ValueError(f'{name} differs from its source')
        module = z.read(MODULE)
        exports = build_kpatch.exports_of(module)
        missing = {h['function'] for h, _ in expected if h.get('function')} - exports
        if missing:
            raise ValueError(f'Module does not export: {sorted(missing)}')
        size = z.getinfo(MODULE).file_size
    return {'file': str(path), 'id': manifest['id'], 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            'module_bytes': size, 'module_sha256': hashlib.sha256(module).hexdigest().upper(),
            'hooks': len(expected),
            'hooks_by_option': {o['id']: sum(1 for _, when in expected if when == o['id']) for o in OPTIONS},
            'options': [o['id'] for o in declared], 'installer_dependencies': []}


def verify_clean(clean: Path):
    """Optional verification input, never an input to the shipped module/archive."""
    data = clean.read_bytes()
    sha = hashlib.sha256(data).hexdigest().upper()
    if sha not in (build_kpatch.CD_1_03, build_kpatch.GOG):
        raise ValueError('Byte verification requires canonical clean CD 1.03 or GOG')
    for h in all_hooks():
        at = h['address'] - 0x400000
        if data[at:at + len(h['original_bytes'])] != bytes(h['original_bytes']):
            raise ValueError(f"Clean bytes disagree at {h['address']:#010x}")
    if data[0x1f0cd2:0x1f0cd5] != bytes.fromhex('C2 08 00'):
        raise ValueError('Resolution consumed exit no longer returns/pops two arguments')
    if 0x627861 + int.from_bytes(data[0x227860:0x227861], signed=True) != 0x6278ba:
        raise ValueError('Original tooltip branch target changed')
    return {'sha256': sha, 'bytes': len(data), 'guarded_hook_sites': len(all_hooks())}


def build(module: Path, out: Path, version: str, config_dir: Path = None):
    target = out / NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data, method in [
            ('manifest.toml', render_manifest(version).encode(), zipfile.ZIP_DEFLATED),
            (HOOKS, render_hooks().encode(), zipfile.ZIP_DEFLATED),
            (LARGE_ADDRESS, build_kpatch.render_hooks(
                [build_kpatch.large_address_hook()],
                versions=(build_kpatch.CD_1_03, build_kpatch.GOG),
                source='the unmodified CD 1.03 and GOG header: the large-address flag.').encode(),
             zipfile.ZIP_DEFLATED),
            # The module's resource bank is already compressed; deflating it again
            # costs minutes and saves nothing.
            (MODULE, module.read_bytes(), zipfile.ZIP_STORED),
            *[(name, source.read_bytes(), zipfile.ZIP_DEFLATED) for name, source in LICENSES.items()],
        ]:
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = method
            z.writestr(info, data)
    result = validate(target)
    (out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    if config_dir:
        config_dir.mkdir(parents=True, exist_ok=True)
        for name, text in config_files().items():
            (config_dir / name).write_text(text, newline='\n')
        result['config_files'] = sorted(config_files())
    return result


def write_def(path: Path):
    """The module's export list: every callback a hook names."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('EXPORTS\n' + ''.join(f'    {name}\n' for name in sorted(functions())))
    return {'exports': len(functions()), 'file': str(path)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--module', type=Path, default=ROOT / 'build/native-runtime/kmrp-native.dll')
    p.add_argument('--out', type=Path, default=ROOT / 'dist/native')
    p.add_argument('--version', default='0.1.0')
    p.add_argument('--config-dir', type=Path, help="Also write the installer's patch_config.toml pieces")
    p.add_argument('--check', type=Path)
    p.add_argument('--write-def', type=Path, help="Write the module's export list and stop")
    p.add_argument('--verify-clean', type=Path, help='Optional clean CD/GOG byte guard verification')
    args = p.parse_args()
    if args.write_def:
        print(json.dumps(write_def(args.write_def), indent=2))
        return
    result = validate(args.check) if args.check else build(args.module, args.out, args.version, args.config_dir)
    if args.verify_clean:
        result['clean_verification'] = verify_clean(args.verify_clean)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
