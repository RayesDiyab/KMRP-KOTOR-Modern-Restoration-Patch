#!/usr/bin/env python3
"""Fail loudly when the controller patch's sources of truth disagree.

Every check here exists because the disagreement it looks for actually happened
and was reported as a defect in the game rather than in the tooling:

  1. A hook in kotor1.hooks.toml whose export no source defines. Ownership is
     derived from the defining .cpp, so an unresolvable hook would silently
     become "not KMRP's" -- the same failure mode as the prefix list this
     replaced, which mis-classified NativeGuiFrameK1 and then
     NativeCameraFrameK1.
  2. A hook missing from exports.def, which links but cannot be resolved at
     patch time.
  3. Installed native hooks that differ from the tracked table. The installer
     used to carry its own copy of that table, so the game could be running hooks
     no tracked file described.
  4. A constant the tests import that the module no longer defines. The tests
     used to hardcode copies; a copy that outlives its original reports a
     correct module as broken.

Exit status is 0 when everything agrees, 1 otherwise.

Usage:
    python tools/check_controller_drift.py [--config PATH]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kmrp_controller as kc                              # noqa: E402

DEFAULT_CONFIG = Path(r"C:\Star Wars - KotOR\patch_config.toml")

# Constants the test scripts and diagnostics import by name. Listed here so that
# deleting or renaming one in the module is caught by this check rather than by a
# traceback in the middle of a 20-minute end-to-end run.
REQUIRED_CONSTANTS = [
    "K1_STICK_DEADZONE",
    "K1_CAMERA_DEADZONE",
    "K1_CAMERA_SPEED",
    "K1_NAV_STICK_ENGAGE",
    "K1_NAV_STICK_RELEASE",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="installed patch_config.toml (skipped when absent)")
    arguments = parser.parse_args()

    problems = []
    hooks = kc.hooks()
    print(f"{len(hooks)} hooks in {kc.HOOKS_TOML.name}")

    # 1. every hook classifiable
    unowned = [h["function"] for h in hooks if h["owner"] is None]
    if unowned:
        problems.append(
            "no tracked source defines these hook exports, so their owner cannot "
            f"be derived: {', '.join(unowned)}")
    native = [h for h in hooks if h["owner"] == kc.KMRP]
    legacy = [h for h in hooks if h["owner"] == kc.LEGACY]
    print(f"  {len(native)} KMRP native, {len(legacy)} legacy, {len(unowned)} unowned")

    # 2. every hook exported
    exported = {line.strip() for line in
                kc.EXPORTS_DEF.read_text(encoding="utf-8").splitlines()}
    missing = [h["function"] for h in hooks if h["function"] not in exported]
    if missing:
        problems.append(f"hooks missing from exports.def: {', '.join(missing)}")

    # 3. installed native hooks match the tracked table
    if arguments.config.exists():
        installed = kc.installed_hooks(arguments.config)
        installed_native = [h for h in installed if kc.is_native(h["function"])]
        want = [(h["address"], h["function"], list(h["original_bytes"]))
                for h in native]
        got = [(h["address"], h["function"], list(h["original_bytes"]))
               for h in installed_native]
        if got and got != want:
            only_tracked = [n for _, n, _ in want]
            only_installed = [n for _, n, _ in got]
            problems.append(
                "installed native hooks differ from kotor1.hooks.toml\n"
                f"    tracked:   {only_tracked}\n"
                f"    installed: {only_installed}")
        elif got:
            print(f"  installed config matches the tracked table "
                  f"({len(got)} native hooks)")
    else:
        print(f"  {arguments.config} not present; install check skipped")

    # 4. the installer can actually render a config
    #
    # This checks the code path that WRITES the config, not just the table it
    # reads. select_controller_path.apply() referred to a NATIVE_HOOKS constant
    # that the single-source refactor had deleted, so both "native" and "both"
    # raised NameError -- and nothing noticed, because the suite only ever calls
    # report(). A renderer nothing exercises is a renderer nothing tests.
    sys.path.insert(0, str(kc.ROOT / "testing" / "controller"))
    try:
        import select_controller_path as installer
        rendered = installer.native_hooks_toml()
        names = re.findall(r'function\s*=\s*"(\w+)"', rendered)
        want = [h["function"] for h in native]
        if names != want:
            problems.append(f"the installer renders {names}, tracked table is {want}")
        else:
            print(f"  installer renders all {len(names)} native hooks")
    except Exception as error:                       # noqa: BLE001 - report it
        problems.append(f"the installer cannot render a config: {error!r}")

    # 5. constants the tooling imports still exist
    values = kc.constants()
    absent = [name for name in REQUIRED_CONSTANTS if name not in values]
    if absent:
        problems.append(
            f"constants imported by the tests are not defined in "
            f"{kc.MODULE_SOURCE.name}: {', '.join(absent)}")
    else:
        print("  constants: " + ", ".join(
            f"{name}={values[name]}" for name in REQUIRED_CONSTANTS))

    print()
    if problems:
        for problem in problems:
            print("DRIFT: " + problem)
        return 1
    print("No drift: hooks, ownership, exports and constants all agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
