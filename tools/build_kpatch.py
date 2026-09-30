#!/usr/bin/env python3
"""Build the KPM edition's four .kpatch files, and check them as KPM would.

KMRP ships two ways from one source. The standalone installer writes the gold
delta into swkotor.exe and installs its own copy of the KOTOR Patch Manager
runtime with patch_config.toml. The KPM edition leaves the executable unmodified
and hands the same work to KOTOR Patch Manager, as one patch per fix:

  KMRP.kpatch             id "kmrp", required: the widescreen interface and
                          everything else KMRP always does, including the memory
                          fixes. Its module applies the executable changes in
                          memory (K1KpmApplier.cpp) from kmrp-kpm.dat, which
                          KMRP's installer writes with the Override files.
  KMRP Controller.kpatch  id "kmrp-controller": controller support
  KMRP Movies.kpatch      id "kmrp-movies": the movie fixes -- the movie window's
                          two hooks, and the movie changes the core's applier
                          makes only when this is ticked
  KMRP Map Notes.kpatch   id "kmrp-map-notes": Derslok's map-note corrections. No
                          hooks and no module: the core's applier sets the flag
                          when this is ticked. KPM writes such a patch into
                          patch_config.toml with an empty dll, and its runtime
                          skips it (KotorPatcher config_reader.cpp).

Each hook's patch is `kpm_patch` in kotor1.hooks.toml, derived by
tools/kmrp_controller.kpm_patch_hooks. KMRP requires no KPM patch: it carries the
memory fixes KPM's patches also make, and conflicts with those patches
(kmrp_controller.kpm_same_fix), because Texture Bucket Safety and Grass Memory
Safety do not support Steam's swkotor.exe and KPM has one `requires` list for
every game version. On CD 1.03 it also sets the large-address flag, as the
standalone does, with a static hook in a hooks file for CD 1.03 and GOG, and so
conflicts with 4gb-patch; Steam's DRM refuses to start an executable changed on
disk, so there it runs without the flag. The three add-ons require KMRP; KPM adds nothing
by itself, so the player ticks it.

Every patch supports CD 1.03, GOG's swkotor.exe (kotor1_gog_103) and Steam's
(kotor1_steam_103). GOG's is CD 1.03 without the 16 bytes of "Hellspawn Reborn"
in its header padding: zeroing them in CD 1.03 gives GOG's SHA-256 exactly
(checked 2026-09-30), so every byte KMRP reads or writes is the same. Steam's is
CD 1.03's program behind SteamStub: decrypted, its code is byte for byte CD
1.03's (measured 2026-09-28). On Steam, KPM must use its binkw32.dll proxy,
since the executable hands its launch to Steam and an injected process exits.

The check replays KPM 0.7.1's install-time rules on the output, as read from its
source (KPatchCore ManifestParser, HooksParser, Hook.IsValid, HookValidator,
HookTargetValidator, PatchRepository):
  * manifest: [patch] with non-empty id, name, version, author, description;
    requires/conflicts string arrays; supported_versions string values;
  * hooks: integer addresses 0x00400000..0x7FFFFFFF, byte lists 0..255, one
    hook per start address -- across all four, since a player may tick them
    all; detour with a function, 5+ stolen bytes, and "eax" excluded when it has
    a consumed exit; simple equal length; replace 5+ bytes;
  * a module (binaries/windows_x86.dll) exactly when there are detours, and it
    exports every function named;
  * every hook's original bytes are the unmodified executable's (the pre-install
    check); a static hook's are the file's own, in the header.

Conflicts are declared from measurement, not guesswork: tools/check_kpm_overlaps.py
finds no byte overlap with any K1 patch KPM 0.7.1 ships once the three
memory-safety patches are required. Map Texture Patch changes the minimap the
core's interface changes, and Scaled Kotor is a competing widescreen patch;
Movie Patch changes what KMRP Movies does; Expanded Keyboard Control and Xbox
Controls K1 hook the controller's input sites.

Usage:
    python tools/build_kpatch.py --module PATH --out DIR [--version 1.5.0]
    python tools/build_kpatch.py --check DIR

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import struct
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import kmrp_controller                                  # noqa: E402

CD_1_03 = "761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886"
GOG = "9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435"
STEAM = "34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88"
VERSIONS = {"kotor1_cdcrack_103": CD_1_03, "kotor1_gog_103": GOG, "kotor1_steam_103": STEAM}
CLEAN_EXE = ROOT / "build-inputs" / "swkotornopatch.exe"

PATCHES = [
    {
        "file": "KMRP.kpatch",
        "id": "kmrp",
        "name": "KMRP - KOTOR Modern Restoration Patch",
        "description": (
            "Widescreen and high-resolution interface for KOTOR 1 at {resolutions} "
            "resolutions, with the 4 GB, texture, grass and save-game memory fixes built in. Needs "
            "KMRP's installer, which picks the resolution and installs KMRP's interface "
            "files (it installs for KOTOR Patch Manager when KPM manages the game). Add "
            "KMRP Controller, KMRP Movies and KMRP Map Notes for the rest of KMRP."),
        "requires": [],
        "conflicts": (["hud-minimap-map-size-fix-v1", "scaled-kotor", "4gb-patch"]
                      + kmrp_controller.kpm_same_fix()),
    },
    {
        "file": "KMRP Controller.kpatch",
        "id": "kmrp-controller",
        "name": "KMRP Controller",
        "description": (
            "KMRP's controller support: Xbox, PlayStation, Switch and Steam Deck pads "
            "for play and menus, with matching button prompts. Requires KMRP."),
        "requires": ["kmrp"],
        "conflicts": ["expanded-keyboard-control", "xbox-controls-k1"],
    },
    {
        "file": "KMRP Movies.kpatch",
        "id": "kmrp-movies",
        "name": "KMRP Movies",
        "description": (
            "KMRP's movie fixes: movies play at your resolution without a display-mode "
            "switch, fitted at their own aspect, with black instead of grey around "
            "them. Requires KMRP."),
        "requires": ["kmrp"],
        "conflicts": ["better-movie-playback-v1"],
    },
    {
        "file": "KMRP Map Notes.kpatch",
        "id": "kmrp-map-notes",
        "name": "KMRP Map Notes",
        "description": (
            "Derslok's area-map marker corrections: map notes shown where they belong. "
            "Requires KMRP."),
        "requires": ["kmrp"],
        "conflicts": [],
    },
]
assert [p["id"] for p in PATCHES] == list(kmrp_controller.KPM_PATCHES)


def toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def toml_list(values) -> str:
    return "[" + ", ".join(toml_string(v) for v in values) + "]"


def resolution_count(catalog: Path) -> int:
    """How many resolutions the build made: the rows of its resolutions.tsv, the
    catalog the installer lists (ResolutionCatalog in KmrpPatcher.cs)."""
    rows = [line for line in catalog.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]
    if not rows:
        raise SystemExit(f"{catalog} lists no resolutions")
    return len(rows)


def render_manifest(patch, version: str, resolutions: int) -> str:
    return "\n".join([
        "[patch]",
        f"id = {toml_string(patch['id'])}",
        f"name = {toml_string(patch['name'])}",
        f"version = {toml_string(version)}",
        'author = "Rayes Diyab (KMRP)"',
        f"description = {toml_string(patch['description'].format(resolutions=resolutions))}",
        f"requires = {toml_list(patch['requires'])}",
        f"conflicts = {toml_list(patch['conflicts'])}",
        "",
        "[patch.supported_versions]",
        *[f'{name} = "{sha}"' for name, sha in VERSIONS.items()],
        "",
    ])


def large_address_hook() -> dict:
    """The large-address flag as a KPM static hook, derived from the unmodified CD
    1.03 executable's own header: IMAGE_FILE_HEADER.Characteristics OR 0x0020, the
    one-bit change the standalone makes (reverse-engineering/large-address-aware.md).
    CD 1.03 and GOG, whose headers differ only in padding: Steam's header is elsewhere (its e_lfanew is 0x110), and Steam's DRM
    refuses to start an executable changed on disk."""
    clean = CLEAN_EXE.read_bytes()
    field = struct.unpack_from("<I", clean, 0x3C)[0] + 22
    original = list(clean[field:field + 2])
    value = struct.unpack_from("<H", clean, field)[0] | 0x0020
    return {"address": 0x00400000 + field, "type": "static", "original_bytes": original,
            "replacement_bytes": list(struct.pack("<H", value))}


def render_hooks(hooks, versions=(CD_1_03, GOG, STEAM),
                 source="src/controller-native/kotor1.hooks.toml; edit that file, not this one.") -> str:
    """A hooks file in KPM's syntax: integer addresses, integer byte lists."""
    lines = [
        f"# Generated by tools/build_kpatch.py from {source}",
        "[metadata]",
        "target_versions = [" + ", ".join(f'"{v}"' for v in versions) + "]",
    ]
    for hook in hooks:
        h = kmrp_controller.as_installed(hook)
        lines += ["", "[[hooks]]",
                  f"address = 0x{h['address']:08X}",
                  f"type = {toml_string(h['type'])}"]
        if "function" in h:
            lines.append(f"function = {toml_string(h['function'])}")
        lines.append("original_bytes = [" +
                     ", ".join(f"0x{b:02X}" for b in h["original_bytes"]) + "]")
        if "replacement_bytes" in h:
            lines.append("replacement_bytes = [" +
                         ", ".join(f"0x{b:02X}" for b in h["replacement_bytes"]) + "]")
        if h.get("skip_original_bytes"):
            lines.append("skip_original_bytes = true")
        if h.get("exclude_from_restore"):
            lines.append(f"exclude_from_restore = {toml_list(h['exclude_from_restore'])}")
        if "consumed_exit_address" in h:
            lines.append(f"consumed_exit_address = 0x{h['consumed_exit_address']:08X}")
        for p in h.get("parameters", []):
            lines += ["", "[[hooks.parameters]]",
                      f"source = {toml_string(p['source'])}",
                      f"type = {toml_string(p['type'])}"]
    return "\n".join(lines) + "\n"


def module_path(patch_id: str) -> str:
    """Where KMRP's installer puts a patch's module, relative to the game folder:
    patches/<id>.dll, as KPM extracts it (PatchApplicator), or "" for a patch
    without detours, which loads no module."""
    detours = any(h.get("type", "detour") == "detour"
                  for h in kmrp_controller.kpm_patch_hooks(patch_id))
    return f"patches/{patch_id}.dll" if detours else ""


def render_config_section(patch_id: str) -> str:
    """One patch's part of patch_config.toml, as KMRP's installer writes it when it
    installs KPM's runtime itself: what KPM's ConfigGenerator would write for this
    patch -- id, module, and the runtime hooks (a static hook is written to the
    file at install time and is never in the config) -- in the [[patches.hooks]]
    form the standalone installer wrote. The installer puts target_version_sha
    first and joins the chosen patches' sections, kmrp's first."""
    hooks = [kmrp_controller.as_installed(h) for h in kmrp_controller.kpm_patch_hooks(patch_id)]
    text = (f"[[patches]]\nid = {toml_string(patch_id)}\n"
            f"dll = {toml_string(module_path(patch_id))}\n")
    return text + (kmrp_controller.render_patch_hooks(hooks) if hooks else "")


def build(module: Path, out: Path, version: str, resolutions: int, config_dir: Path = None):
    out.mkdir(parents=True, exist_ok=True)
    dll = module.read_bytes()
    written = []
    if config_dir:
        config_dir.mkdir(parents=True, exist_ok=True)
        for stale in config_dir.glob("*.toml"):
            stale.unlink()
        for patch in PATCHES:
            (config_dir / f"{patch['id']}.toml").write_bytes(
                render_config_section(patch["id"]).encode())
    for patch in PATCHES:
        hooks = kmrp_controller.kpm_patch_hooks(patch["id"])
        entries = [("manifest.toml", render_manifest(patch, version, resolutions).encode())]
        # A patch without hooks carries neither a hooks file nor a module: KPM then
        # lists it, records it in patch_config.toml, and loads nothing for it.
        if hooks:
            entries.append(("kotor1.hooks.toml", render_hooks(hooks).encode()))
            entries.append(("binaries/windows_x86.dll", dll))
        if patch["id"] == "kmrp":
            entries.append(("kotor1-cd-large-address.hooks.toml", render_hooks(
                [large_address_hook()], versions=(CD_1_03, GOG),
                source="the unmodified CD 1.03 and GOG header: the large-address flag.").encode()))
        target = out / patch["file"]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            # Fixed timestamps, so the same inputs give the same bytes.
            for name, data in entries:
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
        target.write_bytes(buffer.getvalue())
        written.append((target, len(hooks)))
    return written


# ------------------------------------------------------------------ the check

def exports_of(dll: bytes) -> set:
    """Exported names of a PE DLL."""
    pe = struct.unpack_from("<I", dll, 0x3C)[0]
    optional = pe + 24
    export_rva = struct.unpack_from("<I", dll, optional + 96)[0]
    count = struct.unpack_from("<H", dll, pe + 6)[0]
    opt_size = struct.unpack_from("<H", dll, pe + 20)[0]
    sections = []
    for i in range(count):
        o = pe + 24 + opt_size + 40 * i
        vsize, va, rsize, raw = struct.unpack_from("<IIII", dll, o + 8)
        sections.append((va, max(vsize, rsize), raw))

    def at(rva):
        for va, size, raw in sections:
            if va <= rva < va + size:
                return raw + rva - va
        raise ValueError(hex(rva))

    base = at(export_rva)
    names = struct.unpack_from("<I", dll, base + 24)[0]
    table = at(struct.unpack_from("<I", dll, base + 32)[0])
    out = set()
    for i in range(names):
        start = at(struct.unpack_from("<I", dll, table + 4 * i)[0])
        end = dll.index(b"\0", start)
        out.add(dll[start:end].decode())
    return out


def clean_bytes(va: int, n: int) -> bytes:
    data = CLEAN_EXE.read_bytes()
    for sva, raw, size in [(0x401000, 0x1000, 0x33C000), (0x73D000, 0x33D000, 0x50000),
                           (0x78D000, 0x38D000, 0x17000)]:
        if sva <= va < sva + size:
            return data[raw + va - sva: raw + va - sva + n]
    raise ValueError(f"{va:#x} is not file-backed in the unmodified executable")


GOLD_EXE = ROOT / "build" / "kmrp" / "swkotor_gold_v24_movieaspect.exe"


def gold_bytes(va: int, n: int) -> bytes:
    data = GOLD_EXE.read_bytes()
    for sva, raw, size in [(0x401000, 0x1000, 0x33C000), (0x73D000, 0x33D000, 0x50000),
                           (0x78D000, 0x38D000, 0x17000)]:
        if sva <= va < sva + size:
            return data[raw + va - sva: raw + va - sva + n]
    raise ValueError(f"{va:#x} is not file-backed in gold")


def check(folder: Path) -> int:
    problems = []
    ids = {}
    manifests = {}
    everywhere = {}      # start address -> patch file, across every patch
    for path in sorted(folder.glob("*.kpatch")):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            manifest = tomllib.loads(archive.read("manifest.toml").decode())["patch"]
            for key in ("id", "name", "version", "author", "description"):
                if not isinstance(manifest.get(key), str) or not manifest[key].strip():
                    problems.append(f"{path.name}: manifest needs a non-empty {key}")
            for key in ("requires", "conflicts"):
                if not all(isinstance(v, str) for v in manifest.get(key, [])):
                    problems.append(f"{path.name}: {key} must be strings")
            supported = set(manifest.get("supported_versions", {}).values())
            for name, sha in VERSIONS.items():
                if sha not in supported:
                    problems.append(f"{path.name}: does not support {name}")
            ids[manifest["id"]] = path.name
            manifests[manifest["id"]] = manifest
            hook_files = [n for n in names if n.lower().endswith("hooks.toml")]
            hooks = []
            for name in hook_files:
                data = tomllib.loads(archive.read(name).decode())
                targets = data.get("metadata", {}).get("target_versions", [])
                if not targets or not set(targets) <= supported:
                    problems.append(f"{path.name} {name}: target_versions must be supported versions")
                for hook in data.get("hooks", []):
                    hook = dict(hook)
                    hook["_targets"] = targets
                    hooks.append(hook)
            detours = [h for h in hooks if h.get("type", "detour") == "detour"]
            has_module = "binaries/windows_x86.dll" in names
            if detours and not has_module:
                problems.append(f"{path.name}: detours without binaries/windows_x86.dll")
            if has_module and not hooks:
                problems.append(f"{path.name}: a module but no hooks -- KPM would load it "
                                "as a DLL-only patch")
            exported = exports_of(archive.read("binaries/windows_x86.dll")) if has_module else set()
            for hook in hooks:
                a = hook.get("address")
                where = f"{path.name} {a:#010x}" if isinstance(a, int) else path.name
                if not isinstance(a, int) or not 0x00400000 <= a <= 0x7FFFFFFF:
                    problems.append(f"{where}: address must be an integer in range")
                    continue
                if a in everywhere:
                    problems.append(f"{where}: {everywhere[a]} hooks this address too")
                everywhere[a] = path.name
                kind = hook.get("type", "detour")
                ob = hook.get("original_bytes", [])
                rb = hook.get("replacement_bytes")
                if not ob or not all(isinstance(b, int) and 0 <= b <= 255 for b in ob):
                    problems.append(f"{where}: original_bytes")
                if kind == "detour":
                    if not hook.get("function"):
                        problems.append(f"{where}: detour without a function")
                    elif hook["function"] not in exported:
                        problems.append(f"{where}: {hook['function']} is not exported")
                    if len(ob) < 5:
                        problems.append(f"{where}: detour needs 5+ bytes")
                    if "consumed_exit_address" in hook and "eax" not in hook.get("exclude_from_restore", []):
                        problems.append(f"{where}: a consumed exit needs eax excluded")
                    for p in hook.get("parameters", []):
                        if p.get("type") not in ("int", "uint", "pointer", "float", "byte", "short"):
                            problems.append(f"{where}: parameter type {p.get('type')}")
                elif kind == "simple":
                    if rb is None or len(rb) != len(ob):
                        problems.append(f"{where}: simple needs equal lengths")
                elif kind == "replace":
                    if rb is None or len(ob) < 5:
                        problems.append(f"{where}: replace needs 5+ bytes and a replacement")
                elif kind == "static":
                    # Written to the file at install time: the header only, CD 1.03
                    # and GOG only. Steam's DRM refuses to start an executable changed
                    # on disk.
                    if rb is None or len(rb) != len(ob):
                        problems.append(f"{where}: static needs equal lengths")
                    if a + len(ob) > 0x00401000:
                        problems.append(f"{where}: a static hook outside the header")
                    if sorted(hook["_targets"]) != sorted([CD_1_03, GOG]):
                        problems.append(f"{where}: a static hook must target CD 1.03 and GOG alone")
                    header = CLEAN_EXE.read_bytes()[a - 0x00400000:a - 0x00400000 + len(ob)]
                    if header != bytes(ob):
                        problems.append(f"{where}: original bytes are not the unmodified header's")
                    continue
                else:
                    problems.append(f"{where}: unexpected type {kind}")
                try:
                    if clean_bytes(a, len(ob)) != bytes(ob):
                        problems.append(f"{where}: original bytes are not the unmodified "
                                        "executable's (KPM refuses the install)")
                    # KPM checks a detour's bytes again as it writes it, which may be
                    # AFTER the applier (running in the core module's DllMain, at its
                    # first detour) has written the gold delta. So no hook may sit on a
                    # byte the delta changes.
                    if gold_bytes(a, len(ob)) != bytes(ob):
                        problems.append(f"{where}: the gold delta changes these bytes, "
                                        "so the hook would fail after the applier ran")
                except ValueError as error:
                    problems.append(f"{where}: {error}")
    for patch_id, manifest in manifests.items():
        for other in manifest.get("conflicts", []):
            if other in manifests and patch_id not in manifests[other].get("conflicts", []):
                problems.append(f"{ids[patch_id]}: conflicts with {other}, but not the other way")
        for needed in manifest.get("requires", []):
            if needed.startswith("kmrp") and needed not in manifests:
                problems.append(f"{ids[patch_id]}: requires {needed}, which is not built")
            if needed in manifest.get("conflicts", []):
                problems.append(f"{ids[patch_id]}: requires and conflicts with {needed}")
    if sorted(manifests) != sorted(kmrp_controller.KPM_PATCHES):
        problems.append(f"expected the patches {', '.join(kmrp_controller.KPM_PATCHES)}, "
                        f"found {', '.join(sorted(manifests))}")
    if problems:
        print("KPM edition patches FAIL:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"KPM edition patches pass KPM 0.7.1's install rules: {', '.join(sorted(ids))}")
    return 0


normalised = kmrp_controller.normalised


def check_config(config_dir: Path, kpatch_dir: Path) -> int:
    """Each config section, parsed as KotorPatcher parses the joined file, carries
    exactly its .kpatch's runtime hooks, and names patches/<id>.dll exactly when
    those hooks include a detour; and the four sections joined load as one
    patch_config.toml with no address hooked twice."""
    problems = []
    joined = 'target_version_sha = "' + CD_1_03 + '"\n'
    for patch in PATCHES:
        section = (config_dir / f"{patch['id']}.toml").read_text(encoding="utf-8")
        joined += "\n" + section
        parsed = tomllib.loads(section)["patches"]
        if len(parsed) != 1 or parsed[0].get("id") != patch["id"]:
            problems.append(f"{patch['id']}.toml: not one [[patches]] with id {patch['id']}")
            continue
        with zipfile.ZipFile(kpatch_dir / patch["file"]) as archive:
            shipped = [h for name in archive.namelist() if name.lower().endswith("hooks.toml")
                       for h in tomllib.loads(archive.read(name).decode()).get("hooks", [])
                       if h.get("type", "detour") != "static"]
        got = sorted((normalised(h) for h in parsed[0].get("hooks", [])), key=lambda h: h["address"])
        want = sorted((normalised(h) for h in shipped), key=lambda h: h["address"])
        if got != want:
            problems.append(f"{patch['id']}.toml: its hooks differ from {patch['file']}'s")
        detours = any(h["type"] == "detour" for h in want)
        expected_dll = f"patches/{patch['id']}.dll" if detours else ""
        if parsed[0].get("dll") != expected_dll:
            problems.append(f"{patch['id']}.toml: dll {parsed[0].get('dll')!r}, expected {expected_dll!r}")
    addresses = [h["address"] for p in tomllib.loads(joined)["patches"] for h in p.get("hooks", [])]
    if len(addresses) != len(set(addresses)):
        problems.append("the joined config hooks an address twice")
    if problems:
        print("KMRP installer config sections FAIL:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"KMRP installer config sections match the .kpatch files: {len(addresses)} hooks in all four")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--module", type=Path,
                        default=ROOT / "src" / "controller-native" / "kmrp-controller.module")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--config-dir", type=Path,
                        help="also write each patch's patch_config.toml section here, "
                             "for KMRP's installer")
    parser.add_argument("--resolutions", type=Path,
                        default=ROOT / "build" / "kmrp" / "resources" / "resolutions.tsv",
                        help="the build's resolution catalog, for KMRP's description")
    parser.add_argument("--version", default="1.5.0")
    parser.add_argument("--check", type=Path)
    arguments = parser.parse_args()
    if arguments.check:
        return check(arguments.check)
    if not arguments.out:
        parser.error("--out or --check is required")
    for target, count in build(arguments.module, arguments.out, arguments.version,
                               resolution_count(arguments.resolutions), arguments.config_dir):
        digest = hashlib.sha256(target.read_bytes()).hexdigest().upper()
        print(f"{target.name}: {count} hooks, {target.stat().st_size:,} bytes, {digest[:16]}")
    status = check(arguments.out)
    if arguments.config_dir:
        status |= check_config(arguments.config_dir, arguments.out)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
