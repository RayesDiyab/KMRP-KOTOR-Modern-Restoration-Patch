#!/usr/bin/env python3
"""One place that knows the controller patch's hooks and constants.

Everything here is *derived*. Nothing in this file restates a value that the
implementation already carries, because every time this project has restated one
it has eventually disagreed with itself and reported the disagreement as a bug in
the game:

  * The end-to-end suite hardcoded a 25% deadzone. The module moved to 15%, then
    8%. The suite then reported three NATIVE failures against a module that was
    behaving exactly as designed.
  * The installer and the suite each classified hooks as "native" or "legacy" by
    matching a prefix list. Both lists were wrong when `NativeGuiFrameK1` was
    added, and both were wrong again when `NativeCameraFrameK1` was added, each
    time counting KMRP's own hook as one of the legacy path's.
  * `select_controller_path.py` carried a second copy of the native hook table,
    so adding one hook meant editing the same addresses in three files.

Sources of truth:

  hooks       src/controller-native/kotor1.hooks.toml
  ownership   which .cpp defines the exported function -- the .cpp files in
              src/controller-native/ are KMRP's native path, vendor/ is Saul0097's
  constants   the `constexpr` definitions in K1NativeJoystick.cpp

`tools/check_controller_drift.py` asserts that these derivations still hold.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE_DIR = ROOT / "src" / "controller-native"
HOOKS_TOML = NATIVE_DIR / "kotor1.hooks.toml"
MODULE_SOURCE = NATIVE_DIR / "K1NativeJoystick.cpp"
# Every translation unit of KMRP's own: the joystick path, the layout and prompt
# code, the controller backend and the rumble mixer (K1Rumble.cpp).
KMRP_SOURCES = sorted(NATIVE_DIR.glob("*.cpp"))
VENDOR_DIR = NATIVE_DIR / "vendor"
EXPORTS_DEF = NATIVE_DIR / "exports.def"

# Ownership is decided by which translation unit defines the export, so a new
# hook classifies itself. KMRP is the native path; the vendor sources are
# Saul0097's, modified by KMRP but still his design.
KMRP = "kmrp"
LEGACY = "legacy"

# Legacy-owned hooks the NATIVE path cannot run without. Ownership says who
# wrote a hook; it does not say who depends on it.
#
# ClearActionBarControlsK1 is hooked on CSWGuiMainInterface's destructor and is
# the only code that clears the vendor's g_mainInterface. The native path writes
# that cache every gameplay frame through NativeActionBarK1, so without this
# hook the pointer outlives the interface: loading a save over a loaded game
# freed it, and the next GUI frame walked it. Measured under x32dbg -- a freed
# 0x14D31F38 dereferenced at +0x18, reached from NativeGuiFrameK1.
REQUIRED_LEGACY = frozenset({"ClearActionBarControlsK1"})


def _defining_sources() -> dict:
    """Exported hook name -> owner, from the `extern "C" ... __cdecl` definitions."""
    owners = {}
    for path, owner in [(p, KMRP) for p in KMRP_SOURCES] + [
            (p, LEGACY) for p in sorted(VENDOR_DIR.glob("*.cpp"))]:
        text = path.read_text(encoding="utf-8", errors="replace")
        for name in re.findall(r"__cdecl\s+(\w+)\s*\(", text):
            owners.setdefault(name, owner)
    return owners


def is_byte_patch(hook) -> bool:
    """A hook that writes bytes rather than calling into the module.

    Detour hooks name an exported function; a `replace` or `simple` hook has no
    function at all, because the runtime writes `replacement_bytes` and, for
    `replace`, jumps to a cave. Nothing in the module is involved, so there is no
    export to derive ownership from -- these are KMRP's because KMRP ships them.
    """
    return "function" not in hook


def hooks() -> list:
    """Every hook in kotor1.hooks.toml, in file order, each tagged with an owner.

    A hook whose function is defined in no tracked source gets owner None rather
    than a guess; `check_controller_drift.py` fails on that, which is the point.
    Byte patches carry no function, so they are owned by KMRP directly.
    """
    data = tomllib.loads(HOOKS_TOML.read_text(encoding="utf-8"))
    owners = _defining_sources()
    out = []
    for hook in data.get("hooks", []):
        hook = dict(hook)
        hook["owner"] = KMRP if is_byte_patch(hook) else owners.get(hook["function"])
        out.append(hook)
    return out


def install_of(hook) -> str:
    """Which install a hook belongs to: "always", "controller" or "no-controller".

    From the hook's `install` key in kotor1.hooks.toml, "controller" when absent.
    "always" is the core runtime, installed with or without the controller option;
    "no-controller" is a core stand-in for a controller hook at the same address.
    """
    return hook.get("install", "controller")


def _installable() -> list:
    """KMRP's own hooks plus REQUIRED_LEGACY, whichever install they belong to."""
    return [h for h in hooks()
            if h["owner"] == KMRP
            or (not is_byte_patch(h) and h["function"] in REQUIRED_LEGACY)]


def installed_set(controller: bool) -> list:
    """The hooks the standalone installer must emit, with or without controller
    support. The KPM edition's patches are kpm_patch_hooks' instead."""
    wanted = ("always", "controller") if controller else ("always", "no-controller")
    return [h for h in _installable() if install_of(h) in wanted]


# The KPM edition's patches (tools/build_kpatch.py). Movies and Map Notes also
# select which of KMRP's executable changes the core's applier makes
# (K1KpmApplier.cpp); Map Notes carries no hooks at all.
KPM_PATCHES = ("kmrp", "kmrp-controller", "kmrp-movies", "kmrp-map-notes")


def kpm_patch_of(hook) -> str:
    """Which KPM edition patch carries a hook ("" for none)."""
    if "kpm_patch" in hook:
        return hook["kpm_patch"]
    return "kmrp-controller" if install_of(hook) == "controller" else "kmrp"


def kpm_patch_hooks(patch_id: str) -> list:
    """The hooks one KPM edition patch carries: those whose kpm_patch it is."""
    if patch_id not in KPM_PATCHES:
        raise KeyError(patch_id)
    return [h for h in _installable() if kpm_patch_of(h) == patch_id]


def kpm_same_fix() -> list:
    """The KOTOR Patch Manager patches that make a fix KMRP carries itself
    (`kpm_provided_by`). KPM allows one patch per hook address, so the KPM edition
    conflicts with them; until 2026-09-28 it left those hooks out and required the
    patches instead, which Steam's swkotor.exe could not satisfy."""
    return sorted({h["kpm_provided_by"] for h in _installable()
                   if h.get("kpm_provided_by")})


# Keys in kotor1.hooks.toml that are KMRP's own bookkeeping, and never reach an
# installed patch_config.toml. Comparisons against an install strip these, here in
# one place, so a new key cannot make a correct install compare unequal.
BOOKKEEPING = ("owner", "install", "kpm_provided_by", "kpm_patch")


def as_installed(hook) -> dict:
    """A tracked hook as an install writes it: the bookkeeping keys removed."""
    return {key: value for key, value in hook.items() if key not in BOOKKEEPING}


def installable_hooks() -> list:
    """Every hook either install can emit -- what the patcher's table must cover."""
    return _installable()


def native_hooks() -> list:
    """The hooks the installer must emit with controller support on (the default):
    KMRP's own, plus REQUIRED_LEGACY, minus the no-controller stand-ins."""
    return installed_set(True)


def core_hooks() -> list:
    """The hooks the installer must emit with controller support off."""
    return installed_set(False)


def is_native(function: str) -> bool:
    """Is this exported hook part of KMRP's native path?"""
    return _defining_sources().get(function) == KMRP


def render_patch_hooks(selected: list) -> str:
    """Render hooks as the `[[patches.hooks]]` blocks patch_config.toml wants.

    Key order matches what the installer wrote by hand before this existed, so
    that switching to the generated form changed no installed byte. TOML does not
    care about key order; reviewers reading a diff do.
    """
    lines = []
    for hook in selected:
        lines.append("")
        lines.append("[[patches.hooks]]")
        lines.append(f"address = 0x{hook['address']:08X}")
        lines.append(f'type = "{hook["type"]}"')
        if not is_byte_patch(hook):
            lines.append(f'function = "{hook["function"]}"')
        body = ", ".join(f"0x{b:02X}" for b in hook["original_bytes"])
        lines.append(f"original_bytes = [{body}]")
        if is_byte_patch(hook):
            replacement = ", ".join(
                f"0x{b:02X}" for b in hook["replacement_bytes"])
            lines.append(f"replacement_bytes = [{replacement}]")
        lines.append(f"skip_original_bytes = "
                     f"{'true' if hook.get('skip_original_bytes') else 'false'}")
        excluded = ", ".join(f'"{e}"' for e in hook.get("exclude_from_restore", []))
        lines.append(f"exclude_from_restore = [{excluded}]")
        if "consumed_exit_address" in hook:
            lines.append(f"consumed_exit_address = 0x{hook['consumed_exit_address']:08X}")
        for parameter in hook.get("parameters", []):
            lines.append("[[patches.hooks.parameters]]")
            lines.append(f'source = "{parameter["source"]}"')
            lines.append(f'type = "{parameter["type"]}"')
    return "\n".join(lines) + "\n"


def installed_hooks(config_path) -> list:
    """The hooks actually installed in a patch_config.toml."""
    with open(config_path, "rb") as handle:
        return tomllib.load(handle)["patches"][0]["hooks"]


# ------------------------------------------------------------------ constants

# The value alternation puts the hex form first and keeps the C float suffix
# outside the captured group. Folding the suffix into a character class that also
# contains the hex digits made `0.08f` capture as "0.08f", which float() rejects,
# so every float constant silently vanished from the table.
_CONSTEXPR = re.compile(
    r"constexpr\s+(?:float|int|double|unsigned long|std::size_t|std::uintptr_t)\s+"
    r"(K1_\w+)\s*=\s*"
    r"(-?(?:0[xX][0-9A-Fa-f]+|[0-9]*\.[0-9]+|[0-9]+))[fFuUlL]*\s*;")


def constants() -> dict:
    """The module's `constexpr K1_*` values, parsed from its own source.

    Tests import these rather than restating them. A test that hardcodes a copy
    of a tuning constant does not test the constant -- it tests whether someone
    remembered to edit two files.
    """
    text = MODULE_SOURCE.read_text(encoding="utf-8", errors="replace")
    out = {}
    for name, raw in _CONSTEXPR.findall(text):
        try:
            out[name] = int(raw, 0) if not ("." in raw) else float(raw)
        except ValueError:
            continue
    return out


def constant(name: str):
    """One constant, or a clear failure naming the file that should define it."""
    values = constants()
    if name not in values:
        raise KeyError(f"{name} is not defined in {MODULE_SOURCE}")
    return values[name]
