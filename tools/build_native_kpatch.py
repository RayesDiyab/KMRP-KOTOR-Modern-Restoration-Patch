#!/usr/bin/env python3
"""Build and check the standalone KMRP packages (experimental).

One module (src/controller-native/build_native_runtime.cmd) with the engine
recipe and the resource bank embedded (tools/build_native_engine.py,
tools/build_native_assets.py), in two packages. Neither needs a KMRP installer,
kmrp-kpm.dat or an Override file.

  dist/native/KMRP Standalone.kpatch            id "kmrp-native"
      For KOTOR Patch Manager 0.7.1, which has no patch options. The interface,
      the movie fixes and the memory fixes; no controller support. Map notes are
      the add-on beside it, "KMRP Standalone Map Notes.kpatch", which the module
      finds in patch_config.toml.

  dist/native-options/KMRP.kpatch               id "kmrp-native-options"
      For a KOTOR Patch Manager with patch options (upstream issue 13; the local
      prototype is build/research/kpm-options-fork). Controller support, map notes
      and the movie fixes are options of the one patch, all on by default. An
      option's hooks carry `when`. No address has two hooks, so KPM 0.7.1, which
      ignores `when` and the options, installs every hook: every option at its
      default. The module reads what was chosen, or the defaults, from
      patch_config.toml.

The hooks are those of kotor1.hooks.toml (the installer edition's "kmrp",
"kmrp-movies" and "kmrp-controller" patches) plus the standalone module's own
sites in kotor1-native-runtime.hooks.toml. The installer edition's four patches
are built separately by tools/build_kpatch.py and are unchanged.

Usage:
    python tools/build_native_kpatch.py [--module PATH] [--version X.Y.Z]
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
ID = 'kmrp-native'
NAME = 'KMRP Standalone.kpatch'
OPTIONS_ID = 'kmrp-native-options'
OPTIONS_NAME = 'KMRP.kpatch'
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
}
# The standalone module's own callbacks and what each is handed.
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
MAP_NOTES_ID = 'kmrp-native-map-notes'
MAP_NOTES_NAME = 'KMRP Standalone Map Notes.kpatch'
OTHERS = (['kmrp', 'kmrp-controller', 'kmrp-movies', 'kmrp-map-notes', 'kmrp-native-preview',
           'hud-minimap-map-size-fix-v1', 'scaled-kotor', '4gb-patch', 'better-movie-playback-v1']
          + kmrp_controller.kpm_same_fix())
MAP_NOTES = {
    'id': MAP_NOTES_ID,
    'name': 'KMRP Standalone Map Notes',
    'description': (
        "Derslok's area-map marker corrections for KMRP Standalone: map notes shown "
        'where they belong. Requires KMRP Standalone.'),
    'requires': [ID],
    'conflicts': [OPTIONS_ID],
}
PATCH = {
    'id': ID,
    'name': 'KMRP Standalone (experimental)',
    'description': (
        'KMRP in one patch: the widescreen and high-resolution interface at the '
        'resolution chosen in Options, the movie fixes, and the 4 GB, texture, grass '
        'and save-game memory fixes. Needs no KMRP installer and writes nothing to '
        'Override. Map notes are a separate patch; no controller support. '
        'Experimental.'),
    'requires': [],
    'conflicts': OTHERS + [OPTIONS_ID],
}
OPTIONS_PATCH = {
    'id': OPTIONS_ID,
    'name': 'KMRP - KOTOR Modern Restoration Patch (experimental)',
    'description': (
        'KMRP in one patch: the widescreen and high-resolution interface at the '
        'resolution chosen in Options, with the 4 GB, texture, grass and save-game '
        'memory fixes. Controller support, map notes and the movie fixes are options '
        'you can turn off. Needs no KMRP installer and writes nothing to Override. '
        'Experimental.'),
    'requires': [],
    'conflicts': OTHERS + [ID, MAP_NOTES_ID, 'expanded-keyboard-control', 'xbox-controls-k1'],
}
# What the player can turn off, in the order the launcher lists it. All on by default.
# The descriptions are the launcher's, so they say what the player gets.
OPTIONS = [
    {'id': 'controller', 'name': 'Controller support',
     'description': 'Play with an Xbox, PlayStation, Switch or Steam Deck controller, in the '
                    'game and in every menu, with matching button prompts and rumble.'},
    {'id': 'map-notes', 'name': 'Map notes',
     'description': "Shows the area map's notes where they belong (Derslok's map marker "
                    'corrections).'},
    {'id': 'movies', 'name': 'Movie fixes',
     'description': 'Plays movies at your resolution without switching the display mode, at '
                    'their own shape, with black around them instead of grey.'},
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


def _checked(conditioned):
    """(hook, when) pairs in address order, refused unless every pair of hooks that
    share bytes can never be installed together."""
    for index, (h, when) in enumerate(conditioned):
        span = range(h['address'], h['address'] + len(h['original_bytes']))
        if not span or (h['type'] in ('detour', 'replace') and len(span) < 5):
            raise ValueError(f"Hook too short at {h['address']:#010x}")
        if h['type'] == 'simple' and len(h['replacement_bytes']) != len(span):
            raise ValueError('Simple patch changes length')
        if 'consumed_exit_address' in h and 'eax' not in h.get('exclude_from_restore', []):
            raise ValueError('Consumed exit loses EAX')
        for other, other_when in conditioned[:index]:
            if (other['address'] < span.stop and span.start < other['address'] + len(other['original_bytes'])
                    and not (when and other_when and when[0] == other_when[0] and when[1] != other_when[1])):
                raise ValueError(f"Hooks overlap at {h['address']:#010x}")
    return sorted(conditioned, key=lambda pair: pair[0]['address'])


def hooks():
    """Every runtime hook of the 0.7.1 package, by address."""
    source = [kmrp_controller.as_installed(h) for patch in ('kmrp', 'kmrp-movies')
              for h in kmrp_controller.kpm_patch_hooks(patch)]
    return [h for h, _ in _checked([(h, None) for h in source + _table()])]


def option_hooks():
    """Every runtime hook of the options package with its condition, by address:
    (hook, None) for one always installed, else (hook, (option id, value))."""
    # The core's hooks, always. The GUI and movie frame sites are among them and stay
    # one hook each: CoreGuiFrameK1 and CoreMovieFrameK1 run the controller's frame
    # themselves when the option is on. A variant per state would be two hooks at
    # one address, which a manager without options installs both of and refuses.
    conditioned = [(kmrp_controller.as_installed(h), None)
                   for h in kmrp_controller.kpm_patch_hooks('kmrp')]
    for h in kmrp_controller.kpm_patch_hooks('kmrp-controller'):
        conditioned.append((kmrp_controller.as_installed(h), ('controller', True)))
    for h in kmrp_controller.kpm_patch_hooks('kmrp-movies'):
        conditioned.append((kmrp_controller.as_installed(h), ('movies', True)))
    conditioned += [(h, None) for h in _table()]
    conditioned = _checked(conditioned)
    addresses = [h['address'] for h, _ in conditioned]
    if len(set(addresses)) != len(addresses):
        raise ValueError('Two hooks share an address: a manager without options would refuse the package')
    return conditioned


def all_hooks():
    """Every hook either package can install: what the engine recipe must not touch."""
    seen, out = set(), []
    for h in hooks() + [h for h, _ in option_hooks()]:
        key = (h['address'], h.get('function'))
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


def functions():
    """Every callback a hook of either package names: what the module exports."""
    return {h['function'] for h in all_hooks() if h.get('function')}


def render_when(when):
    option, value = when
    return f'when = "{option}"' if value is True else \
        f'when = {{ option = "{option}", is = {"true" if value else "false"} }}'


def render_option_hooks():
    """The options package's hooks file: build_kpatch's rendering, each conditional
    hook with its `when` after its address."""
    source = 'kotor1.hooks.toml and kotor1-native-runtime.hooks.toml; edit those files, not this one.'
    header = build_kpatch.render_hooks([], source=source)
    parts = [header.rstrip('\n')]
    for h, when in option_hooks():
        lines = build_kpatch.render_hooks([h], source=source)[len(header):].strip('\n').split('\n')
        if when:
            at = next(i for i, line in enumerate(lines) if line.startswith('address = '))
            lines.insert(at + 1, render_when(when))
        parts.append('\n'.join(lines))
    return '\n\n'.join(parts) + '\n'


def render_options_manifest(version: str) -> str:
    text = build_kpatch.render_manifest(OPTIONS_PATCH, version, 0)
    for option in OPTIONS:
        text += '\n'.join([
            '', '[[patch.options]]',
            f"id = {build_kpatch.toml_string(option['id'])}",
            f"name = {build_kpatch.toml_string(option['name'])}",
            f"description = {build_kpatch.toml_string(option['description'])}",
            'type = "toggle"', 'default = true', ''])
    return text


def _condition(hook):
    when = hook.get('when')
    if when is None:
        return None
    return (when, True) if isinstance(when, str) else (when['option'], when.get('is', True))


def validate(path: Path):
    with zipfile.ZipFile(path) as z:
        if sorted(z.namelist()) != sorted(['manifest.toml', HOOKS, LARGE_ADDRESS, MODULE, *LICENSES]):
            raise ValueError('Unexpected files or external payload dependency')
        manifest = tomllib.loads(z.read('manifest.toml').decode())['patch']
        for key in ('id', 'name', 'version', 'author', 'description'):
            if not isinstance(manifest.get(key), str) or not manifest[key].strip():
                raise ValueError(f'Invalid manifest {key}')
        if manifest['id'] not in (ID, OPTIONS_ID) or manifest['requires']:
            raise ValueError('A standalone patch must require nothing')
        with_options = manifest['id'] == OPTIONS_ID
        if not {p['id'] for p in build_kpatch.PATCHES} <= set(manifest['conflicts']):
            raise ValueError("Must conflict with the installer edition's patches")
        if (OPTIONS_ID if not with_options else ID) not in manifest['conflicts']:
            raise ValueError('The two standalone packages must conflict with each other')
        if manifest['supported_versions'] != build_kpatch.VERSIONS:
            raise ValueError('Unexpected target builds')
        declared = manifest.get('options', [])
        if with_options:
            if [(o['id'], o['name'], o['description'], o['type'], o['default']) for o in declared] != \
                    [(o['id'], o['name'], o['description'], 'toggle', True) for o in OPTIONS]:
                raise ValueError('Packaged options differ from source')
        elif declared:
            raise ValueError('The 0.7.1 package cannot carry options')
        actual = tomllib.loads(z.read(HOOKS).decode())
        if set(actual['metadata']['target_versions']) != set(build_kpatch.VERSIONS.values()):
            raise ValueError('Packaged target builds differ from source')
        expected = option_hooks() if with_options else [(h, None) for h in hooks()]
        if ([(kmrp_controller.normalised(h), _condition(h)) for h in actual['hooks']] !=
                [(kmrp_controller.normalised(h), when) for h, when in expected]):
            raise ValueError('Packaged hooks differ from source')
        for _, when in expected:
            if when and when[0] not in {o['id'] for o in OPTIONS}:
                raise ValueError(f'A hook depends on an undeclared option: {when[0]}')
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
            'hooks': len(expected), 'conditional_hooks': sum(1 for _, when in expected if when),
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


def _archive(target: Path, manifest: str, hooks_text: str, module: bytes):
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data, method in [
            ('manifest.toml', manifest.encode(), zipfile.ZIP_DEFLATED),
            (HOOKS, hooks_text.encode(), zipfile.ZIP_DEFLATED),
            (LARGE_ADDRESS, build_kpatch.render_hooks(
                [build_kpatch.large_address_hook()],
                versions=(build_kpatch.CD_1_03, build_kpatch.GOG),
                source='the unmodified CD 1.03 and GOG header: the large-address flag.').encode(),
             zipfile.ZIP_DEFLATED),
            # The module's resource bank is already compressed; deflating it again
            # costs minutes and saves nothing.
            (MODULE, module, zipfile.ZIP_STORED),
            *[(name, source.read_bytes(), zipfile.ZIP_DEFLATED) for name, source in LICENSES.items()],
        ]:
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = method
            z.writestr(info, data)
    return validate(target)


def build(module: Path, out: Path, options_out: Path, version: str):
    dll = module.read_bytes()
    source = 'kotor1.hooks.toml and kotor1-native-runtime.hooks.toml; edit those files, not this one.'
    result = _archive(out / NAME, build_kpatch.render_manifest(PATCH, version, 0),
                      build_kpatch.render_hooks(hooks(), source=source), dll)
    # The add-on: a manifest and nothing else. KPM lists it and records its id in
    # patch_config.toml, where the standalone module looks for it
    # (OptionalFeatures in K1RuntimeEngine.cpp).
    notes = out / MAP_NOTES_NAME
    with zipfile.ZipFile(notes, 'w', zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo('manifest.toml', (2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, build_kpatch.render_manifest(MAP_NOTES, version, 0).encode())
    with zipfile.ZipFile(notes) as z:
        manifest = tomllib.loads(z.read('manifest.toml').decode())['patch']
        if z.namelist() != ['manifest.toml'] or manifest['id'] != MAP_NOTES_ID or manifest['requires'] != [ID]:
            raise ValueError('Unexpected map-notes add-on')
    result['map_notes'] = {'file': str(notes), 'bytes': notes.stat().st_size,
                           'sha256': hashlib.sha256(notes.read_bytes()).hexdigest().upper()}
    (out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')

    with_options = _archive(options_out / OPTIONS_NAME, render_options_manifest(version),
                            render_option_hooks(), dll)
    (options_out / 'verification.json').write_text(json.dumps(with_options, indent=2) + '\n')
    return {'standalone': result, 'with_options': with_options}


def write_def(path: Path):
    """The module's export list: every callback a hook of either package names."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('EXPORTS\n' + ''.join(f'    {name}\n' for name in sorted(functions())))
    return {'exports': len(functions()), 'file': str(path)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--module', type=Path, default=ROOT / 'build/native-runtime/kmrp-native.dll')
    p.add_argument('--out', type=Path, default=ROOT / 'dist/native')
    p.add_argument('--options-out', type=Path, default=ROOT / 'dist/native-options')
    p.add_argument('--version', default='0.1.0')
    p.add_argument('--check', type=Path)
    p.add_argument('--write-def', type=Path, help="Write the module's export list and stop")
    p.add_argument('--verify-clean', type=Path, help='Optional clean CD/GOG byte guard verification')
    args = p.parse_args()
    if args.write_def:
        print(json.dumps(write_def(args.write_def), indent=2))
        return
    result = validate(args.check) if args.check else build(args.module, args.out, args.options_out, args.version)
    if args.verify_clean:
        result['clean_verification'] = verify_clean(args.verify_clean)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
