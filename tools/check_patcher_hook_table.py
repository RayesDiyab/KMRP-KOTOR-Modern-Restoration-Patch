#!/usr/bin/env python3
"""Assert the installer's hook table matches `kotor1.hooks.toml`.

Until 2026-09-29 the shipped patcher wrote `patch_config.toml` from a table
written out by hand in `KmrpPatcher.cs` (`ControllerOperations.BuildConfig`),
because it is a single-file C# build with no TOML reader, and this parsed that
C# and compared it with the tracked table. That hand-copying is exactly where a
wrong address, a wrong stolen byte or a wrong consumed-exit address gets in, and
every one of those is a jump into the wrong place at run time rather than a build
error. It existed because one did: the consumed exit for
`NativeJoystickSkipNormalizeK1` was transcribed as 0x00679BB6 where the tracked
table says 0x00679B76.

Since 2026-09-29 the installer has no hand-written table. It embeds one section
of `patch_config.toml` per KMRP patch, which `tools/build_kpatch.py
--config-dir` generates from the tracked table into `build/kmrp/kpm-config/`
(`Kmrp.engine.config.<id>` in `build_kmrp.ps1`). This checks those files -- the
ones the last build embedded -- against `kotor1.hooks.toml` on its own terms:
each patch's hooks, every runtime field (`kmrp_controller.normalised`), and its
module. `build_kpatch.py` also checks them against the `.kpatch` files as it
writes them.

Usage:
    python tools/check_patcher_hook_table.py [--config-dir DIR]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import kmrp_controller                                  # noqa: E402

CONFIG_DIR = ROOT / "build" / "kmrp" / "kpm-config"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    arguments = parser.parse_args()

    problems = []
    counts = {}
    for patch_id in kmrp_controller.KPM_PATCHES:
        path = arguments.config_dir / f"{patch_id}.toml"
        if not path.exists():
            problems.append(f"{path} is missing: run build_kmrp.ps1")
            continue
        sections = tomllib.loads(path.read_text(encoding="utf-8")).get("patches", [])
        if len(sections) != 1 or sections[0].get("id") != patch_id:
            problems.append(f"{path.name}: not one [[patches]] with id {patch_id}")
            continue
        want = sorted((kmrp_controller.normalised(h) for h in kmrp_controller.engine_hooks([patch_id])),
                      key=lambda h: h["address"])
        have = sorted((kmrp_controller.normalised(h) for h in sections[0].get("hooks", [])),
                      key=lambda h: h["address"])
        if have != want:
            wanted = {h["address"]: h for h in want}
            found = {h["address"]: h for h in have}
            for address in sorted(set(wanted) | set(found)):
                if wanted.get(address) != found.get(address):
                    name = (wanted.get(address) or found.get(address)).get("function") or "byte patch"
                    problems.append(f"{patch_id}: {name} at {address:#010x} "
                                    f"{'missing' if address not in found else 'extra' if address not in wanted else 'differs'}")
        dll = f"patches/{patch_id}.dll" if any(h["type"] == "detour" for h in want) else ""
        if sections[0].get("dll") != dll:
            problems.append(f"{patch_id}: dll {sections[0].get('dll')!r}, expected {dll!r}")
        counts[patch_id] = len(want)

    if problems:
        print("The installer's hook table does NOT match kotor1.hooks.toml:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"The installer's hook table matches kotor1.hooks.toml: "
          + ", ".join(f"{patch_id} {count}" for patch_id, count in counts.items())
          + f" -- {sum(counts.values())} hooks, every runtime field, and each patch's module.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
