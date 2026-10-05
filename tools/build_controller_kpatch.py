#!/usr/bin/env python3
"""Build and check the standalone controller patch for KOTOR Patch Manager:
"KOTOR 1 Native Controller Mod + Xbox HUD.kpatch", id "kmrp-controller".

KMRP's native controller support for a game WITHOUT KMRP: the pad in the game and in
every menu, the button prompts of four controller families, rumble and the Controller
Layout screen, on the game's original interface. It carries none of KMRP's other
work (no interface scaling, no memory, movie or map fixes) and needs nothing else
installed. KMRP's own patch already contains controller support as an option, so
the two conflict.

One module (src/controller-native/build_controller_standalone.cmd) with its files
embedded (tools/build_controller_assets.py). Its hooks are the controller's own in
src/controller-native/kotor1.hooks.toml (`install = "controller"`, which includes the
two frame hooks the full patch reaches through its core's stand-ins) and the one
site in kotor1-native-runtime.hooks.toml where the module registers its files.

The id was the controller add-on of KMRP's four-patch edition (2026-09-28 to
2026-10-04), which needed KMRP's core. This patch replaces it and needs nothing, and
every KMRP patch since already lists the id as a conflict.

Usage:
    python tools/build_controller_kpatch.py [--module PATH] [--version X.Y.Z]
    python tools/build_controller_kpatch.py --check FILE [--verify-clean EXE]
    python tools/build_controller_kpatch.py --write-def FILE

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
import zipfile
from pathlib import Path

import kpatch_common
import kmrp_controller

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_TABLE = ROOT / 'src/controller-native/kotor1-native-runtime.hooks.toml'
ID = 'kmrp-controller'
# The patch was "KMRP Controller" until 2026-10-05, when the maintainer renamed it: it
# is for the game without KMRP, and the name now says what it is. Its id, its
# settings file (kmrp-controller.ini) and its log keep their names, since KMRP's own
# patch lists the id as a conflict and players have the files.
NAME = 'KOTOR 1 Native Controller Mod + Xbox HUD.kpatch'
MODULE = 'binaries/windows_x86.dll'
HOOKS = 'kotor1.hooks.toml'
# The module's one site outside the controller's table: where its files are
# registered, before the game's first resource lookup.
RESOURCE_HOOK = 'KmrpPrepareResourcesK1'
# KMRP's own patch hooks that function's entry for its own files (0x00407230,
# CExoResMan::GetKeyEntry: mov eax, [esp+4] / push ebx), and since 2026-10-05 the two
# patches are installed together, so this one takes the next two instructions of the
# same function: mov ebx, [esp+0x10] / push ebp, five bytes with nothing for a
# trampoline to relocate, ecx still the resource manager. Neither is a branch target.
RESOURCE_SITE_KMRP = 0x00407230
RESOURCE_OWN_HOOK = {
    'address': 0x00407235, 'type': 'detour', 'function': RESOURCE_HOOK,
    'original_bytes': [0x8B, 0x5C, 0x24, 0x10, 0x55],
    'skip_original_bytes': False, 'exclude_from_restore': [],
    'parameters': [{'source': 'ecx', 'type': 'pointer'}],
}
# The Xbox-style HUD's site, this patch's own: the entry of
# CSWGuiMainInterface::DrawMap, ecx = the HUD (mov eax, [0x007A39FC], an absolute
# address, nothing for a trampoline to relocate), which the HUD's Draw calls after
# its updating and before it draws anything. The handler returns at once unless the
# option is on (K1XboxHud.cpp).
XBOX_HUD_HOOK = {
    'address': 0x0068AB10, 'type': 'detour', 'function': 'KmrpXboxHudK1',
    'original_bytes': [0xA1, 0xFC, 0x39, 0x7A, 0x00],
    'skip_original_bytes': False, 'exclude_from_restore': [],
    'parameters': [{'source': 'ecx', 'type': 'pointer'}],
}
# What travels with the file. The module carries SDL whole (zlib), Saul0097's
# controller sources as modified by KMRP (MIT) and Xelu's prompt art (CC0); the
# notices file says which is which.
LICENSES = {
    'licenses/LICENSE.txt': ROOT / 'LICENSE',
    'licenses/THIRD_PARTY_NOTICES.md': ROOT / 'THIRD_PARTY_NOTICES.md',
    'licenses/SDL3-LICENSE.txt': ROOT / 'build/deps/SDL3-3.4.16/LICENSE.txt',
}
# KMRP's patches, every one of which either is or contains controller support.
KMRP_PATCHES = ['kmrp-movies', 'kmrp-map-notes', 'kmrp-native', 'kmrp-native-options',
                'kmrp-native-map-notes', 'kmrp-native-preview']
# Other authors' patches that hook this patch's sites (tools/check_kpm_overlaps.py).
OTHERS = ['expanded-keyboard-control', 'xbox-controls-k1']
PATCH = {
    'id': ID,
    'name': 'KOTOR 1 Native Controller Mod + Xbox HUD',
    'description': (
        "Native controller support for KOTOR's original interface: play with an Xbox, "
        'PlayStation, Switch or Steam Deck controller in the game and in every menu, with '
        'matching button prompts, rumble, a Controller Layout screen in Options and an '
        "optional HUD laid out like the original Xbox version's. "
        'Needs no other patch and writes nothing to Override. KMRP installs it as its '
        'controller support; it works the same on the game without KMRP.'),
    'requires': [],
    'conflicts': KMRP_PATCHES + OTHERS,
}
# Its second site: the entry of CSWGuiTargetActionMenu::Draw, ecx = the menu (push esi
# / mov esi, ecx / test byte ptr [esi+0x1AEC], 1; the jump after it reads the test's
# flags, and the three instructions run after the handler). The HUD calls it right
# after drawing its panel, which is when the party bars' filled parts are drawn.
XBOX_HUD_BARS_HOOK = {
    'address': 0x00685ED0, 'type': 'detour', 'function': 'KmrpXboxHudBarsK1',
    'original_bytes': [0x56, 0x8B, 0xF1, 0xF6, 0x86, 0xEC, 0x1A, 0x00, 0x00, 0x01],
    'skip_original_bytes': False, 'exclude_from_restore': [],
    'parameters': [{'source': 'ecx', 'type': 'pointer'}],
}
# Where a panel is told to the module, in this patch only. KMRP's own patch hooks the
# entry of CSWGuiPanel::StopLoadFromLayout (0x0040B8F0), which every panel calls as
# its constructor ends and again from the base destructor. Scaled Kotor 1.3.1, a
# widescreen patch for KOTOR Patch Manager, hooks that same entry, and the manager
# refuses two patches on one address (tried 2026-10-05: "Hook conflicts detected:
# 0x0040B8F0"). So this patch reaches the same two moments from sites of its own:
#
# - as a panel finishes loading: the entry of CRes::Release (0x00409B80: push ecx /
#   mov ecx, [0x007A39E8], an absolute address), which StopLoadFromLayout calls on
#   the panel's parsed layout at 0x0040B8FC with the panel in esi. The handler acts
#   only on that one call, known by its return address, 0x0040B901;
# - as a panel is destroyed: 0x0040CFAB in CSWGuiPanel::~CSWGuiPanel (mov dword ptr
#   [esi+0x5C], 0), the instruction before the destructor's own call of
#   StopLoadFromLayout, with the base vtable already back and the panel in esi.
PANEL_SITE = 0x0040B8F0
PANEL_FUNCTION = 'NativePanelReleaseGffK1'
PANEL_LOADED_HOOK = {
    'address': 0x00409B80, 'type': 'detour', 'function': 'NativePanelLoadedK1',
    'original_bytes': [0x51, 0x8B, 0x0D, 0xE8, 0x39, 0x7A, 0x00],
    'skip_original_bytes': False, 'exclude_from_restore': [],
    'parameters': [{'source': 'ecx', 'type': 'pointer'}, {'source': 'esi', 'type': 'pointer'},
                   {'source': 'esp+0', 'type': 'pointer'}],
}
PANEL_DESTROYED_HOOK = {
    'address': 0x0040CFAB, 'type': 'detour', 'function': 'NativePanelDestroyedK1',
    'original_bytes': [0xC7, 0x46, 0x5C, 0x00, 0x00, 0x00, 0x00],
    'skip_original_bytes': False, 'exclude_from_restore': [],
    'parameters': [{'source': 'esi', 'type': 'pointer'}],
}
OPTIONS = [
    {'id': 'xbox-hud', 'name': 'Xbox-style HUD', 'default': False,
     'description': "Lays the in-game HUD out like the original Xbox version's: the action "
                    'slots in a box at the bottom left, the target\'s name at the top left, '
                    'the party at the bottom right. Without a manager that offers options, '
                    'set Style=Xbox under [Hud] in kmrp-controller.ini.'},
    {'id': 'debug-logs', 'name': 'Debug logs', 'default': False,
     'description': 'Writes diagnostic log files beside the game. Leave off unless you are '
                    'reporting a problem.'},
]


def hooks():
    """The patch's hooks, by address."""
    selected = [kmrp_controller.as_installed(h) for h in kmrp_controller.installable_hooks()
                if kmrp_controller.install_of(h) == 'controller']
    table = tomllib.loads(RUNTIME_TABLE.read_text())
    if set(table['metadata']['target_versions']) != set(kpatch_common.VERSIONS.values()):
        raise ValueError('Native table target builds changed')
    resource = [h for h in table['hooks'] if h.get('function') == RESOURCE_HOOK]
    if len(resource) != 1 or resource[0]['address'] != RESOURCE_SITE_KMRP:
        raise ValueError(f'Expected one {RESOURCE_HOOK} site, at {RESOURCE_SITE_KMRP:#010x}')
    selected.append(dict(RESOURCE_OWN_HOOK))
    shared = [h for h in selected if h['address'] == PANEL_SITE and h['function'] == PANEL_FUNCTION]
    if len(shared) != 1:
        raise ValueError(f'Expected one {PANEL_FUNCTION} site at {PANEL_SITE:#010x}')
    selected.remove(shared[0])
    selected.append(dict(PANEL_LOADED_HOOK))
    selected.append(dict(PANEL_DESTROYED_HOOK))
    selected.append(dict(XBOX_HUD_HOOK))
    selected.append(dict(XBOX_HUD_BARS_HOOK))
    for index, h in enumerate(selected):
        span = range(h['address'], h['address'] + len(h['original_bytes']))
        if h['type'] != 'detour' or len(span) < 5:
            raise ValueError(f"Not a detour of five bytes or more at {h['address']:#010x}")
        if 'consumed_exit_address' in h and 'eax' not in h.get('exclude_from_restore', []):
            raise ValueError('Consumed exit loses EAX')
        for other in selected[:index]:
            if other['address'] < span.stop and span.start < other['address'] + len(other['original_bytes']):
                raise ValueError(f"Hooks overlap at {h['address']:#010x}")
    return sorted(selected, key=lambda h: h['address'])


def functions():
    return {h['function'] for h in hooks()}


def render_manifest(version: str) -> str:
    text = kpatch_common.render_manifest(PATCH, version, 0)
    for option in OPTIONS:
        text += '\n'.join([
            '', '[[patch.options]]',
            f"id = {kpatch_common.toml_string(option['id'])}",
            f"name = {kpatch_common.toml_string(option['name'])}",
            f"description = {kpatch_common.toml_string(option['description'])}",
            'type = "toggle"', f"default = {'true' if option.get('default', True) else 'false'}", ''])
    return text


def render_hooks() -> str:
    return kpatch_common.render_hooks(
        hooks(), source='kotor1.hooks.toml and kotor1-native-runtime.hooks.toml; edit those files, not this one.')


def validate(path: Path):
    with zipfile.ZipFile(path) as z:
        if sorted(z.namelist()) != sorted(['manifest.toml', HOOKS, MODULE, *LICENSES]):
            raise ValueError('Unexpected files or external payload dependency')
        manifest = tomllib.loads(z.read('manifest.toml').decode())['patch']
        for key in ('id', 'name', 'version', 'author', 'description'):
            if not isinstance(manifest.get(key), str) or not manifest[key].strip():
                raise ValueError(f'Invalid manifest {key}')
        if manifest['id'] != ID or manifest['requires']:
            raise ValueError(f'The patch must be "{ID}" and require nothing')
        if 'kmrp' in manifest['conflicts'] or ID in manifest['conflicts']:
            raise ValueError('Must conflict neither with KMRP, which requires it, nor with itself')
        if manifest['supported_versions'] != kpatch_common.VERSIONS:
            raise ValueError('Unexpected target builds')
        actual = tomllib.loads(z.read(HOOKS).decode())
        if set(actual['metadata']['target_versions']) != set(kpatch_common.VERSIONS.values()):
            raise ValueError('Packaged target builds differ from source')
        expected = hooks()
        if [kmrp_controller.normalised(h) for h in actual['hooks']] != \
                [kmrp_controller.normalised(h) for h in expected]:
            raise ValueError('Packaged hooks differ from source')
        for name, source in LICENSES.items():
            if z.read(name) != source.read_bytes():
                raise ValueError(f'{name} differs from its source')
        module = z.read(MODULE)
        missing = functions() - kpatch_common.exports_of(module)
        if missing:
            raise ValueError(f'Module does not export: {sorted(missing)}')
    return {'file': str(path), 'id': manifest['id'], 'version': manifest['version'],
            'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            'module_bytes': len(module), 'module_sha256': hashlib.sha256(module).hexdigest().upper(),
            'hooks': len(expected), 'options': [o['id'] for o in manifest.get('options', [])]}


def verify_clean(clean: Path):
    """Optional: every hook's original bytes against an unmodified CD 1.03 or GOG executable."""
    data = clean.read_bytes()
    sha = hashlib.sha256(data).hexdigest().upper()
    if sha not in (kpatch_common.CD_1_03, kpatch_common.GOG):
        raise ValueError('Byte verification requires canonical clean CD 1.03 or GOG')
    for h in hooks():
        at = h['address'] - 0x400000
        if data[at:at + len(h['original_bytes'])] != bytes(h['original_bytes']):
            raise ValueError(f"Clean bytes disagree at {h['address']:#010x}")
    return {'sha256': sha, 'bytes': len(data), 'guarded_hook_sites': len(hooks())}


def build(module: Path, out: Path, version: str):
    target = out / NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data, method in [
            ('manifest.toml', render_manifest(version).encode(), zipfile.ZIP_DEFLATED),
            (HOOKS, render_hooks().encode(), zipfile.ZIP_DEFLATED),
            # The module's file bank is already compressed.
            (MODULE, module.read_bytes(), zipfile.ZIP_STORED),
            *[(name, source.read_bytes(), zipfile.ZIP_DEFLATED) for name, source in LICENSES.items()],
        ]:
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = method
            z.writestr(info, data)
    result = validate(target)
    (out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def write_def(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('EXPORTS\n' + ''.join(f'    {name}\n' for name in sorted(functions())))
    return {'exports': len(functions()), 'file': str(path)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--module', type=Path, default=ROOT / 'build/controller-standalone/kmrp-controller.dll')
    p.add_argument('--out', type=Path, default=ROOT / 'dist/controller')
    p.add_argument('--version', default='1.0.0')
    p.add_argument('--check', type=Path)
    p.add_argument('--write-def', type=Path, help="Write the module's export list and stop")
    p.add_argument('--verify-clean', type=Path, help='Optional clean CD/GOG byte guard verification')
    args = p.parse_args()
    if args.write_def:
        print(json.dumps(write_def(args.write_def), indent=2))
        return
    result = validate(args.check) if args.check else build(args.module, args.out, args.version)
    if args.verify_clean:
        result['clean_verification'] = verify_clean(args.verify_clean)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
