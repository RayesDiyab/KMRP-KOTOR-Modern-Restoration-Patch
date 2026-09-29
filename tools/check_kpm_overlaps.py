#!/usr/bin/env python3
"""Which KOTOR Patch Manager patches touch the bytes KMRP's KPM edition changes.

KPM itself catches only two patches hooking the SAME start address; overlapping
ranges pass its checks and fail at run time, where the first failure stops every
hook after it. So KMRP's manifest has to name its conflicts itself, and this
measures them rather than guessing: KMRP's footprint -- every byte the gold delta
changes in the original image, and every run-time hook site of the KPM edition's
hook sets -- against every hook of every .kpatch in a directory, for the
unmodified 1.03 executable. Hooks that only NEIGHBOUR KMRP's bytes are listed too
(within --near bytes), because a hook next to a change in the same routine can
still disagree with it in behaviour; those are for a reviewer, not automatic
conflicts.

Since KMRP carries its own memory fixes and large-address flag (2026-09-28), it
overlaps KPM's 4GB, Texture Bucket, Grass Memory and Save Game patches by design;
those are reported as declared, from tools/build_kpatch.py's conflicts. An overlap
with a patch no KMRP patch declares fails the check.

Usage:
    python tools/check_kpm_overlaps.py <folder of .kpatch files> [--near 32]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_kpatch                                     # noqa: E402
import kmrp_controller                                  # noqa: E402
import kpm_relocations                                  # noqa: E402

CD_1_03 = "761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886"


def kmrp_footprint():
    """[(start, end, what)] of everything KMRP's KPM edition changes or hooks."""
    gold = kpm_relocations.Image(kpm_relocations.DEFAULT_GOLD.read_bytes())
    clean = kpm_relocations.Image(kpm_relocations.DEFAULT_CLEAN.read_bytes())
    spans = [(va, va + n, "gold delta") for va, n in kpm_relocations.changed_runs(clean, gold)]
    seen = set()
    laa = build_kpatch.large_address_hook()
    spans.append((laa["address"], laa["address"] + len(laa["original_bytes"]), "large-address flag"))
    for patch_id in kmrp_controller.KPM_PATCHES:
        for hook in kmrp_controller.kpm_patch_hooks(patch_id):
            if hook["address"] in seen:
                continue
            seen.add(hook["address"])
            spans.append((hook["address"], hook["address"] + len(hook["original_bytes"]),
                          hook.get("function", "byte patch")))
    return spans


def patch_hooks(path: Path):
    """(manifest, [(start, end, type)]) for the CD 1.03 executable."""
    with zipfile.ZipFile(path) as archive:
        manifest = tomllib.loads(archive.read("manifest.toml").decode("utf-8"))["patch"]
        if CD_1_03 not in [v.upper() for v in manifest.get("supported_versions", {}).values()]:
            return manifest, None
        hooks = []
        for name in archive.namelist():
            if not name.lower().endswith("hooks.toml"):
                continue
            data = tomllib.loads(archive.read(name).decode("utf-8"))
            targets = [t.upper() for t in data.get("metadata", {}).get("target_versions", [])]
            if targets and CD_1_03 not in targets:
                continue
            for hook in data.get("hooks", []):
                start = hook["address"]
                hooks.append((start, start + len(hook["original_bytes"]),
                              hook.get("type", "detour")))
        return manifest, hooks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--near", type=int, default=32)
    arguments = parser.parse_args()

    footprint = kmrp_footprint()
    print(f"KMRP's footprint: {len(footprint)} spans, "
          f"{sum(e - s for s, e, _ in footprint)} bytes")
    overlapping, neighbouring = [], []
    for path in sorted(arguments.folder.glob("*.kpatch")):
        manifest, hooks = patch_hooks(path)
        if hooks is None:
            continue
        hits, near = [], []
        for hs, he, htype in hooks:
            for ks, ke, what in footprint:
                gap = max(ks - he, hs - ke)
                if gap < 0:
                    hits.append(f"{hs:#010x}+{he - hs} {htype} overlaps {what} {ks:#010x}+{ke - ks}")
                elif gap < arguments.near:
                    near.append(f"{hs:#010x}+{he - hs} {htype} {gap} bytes from {what} {ks:#010x}")
        label = f"{manifest['id']} ({path.stem})"
        if hits:
            overlapping.append((label, hits))
        elif near:
            neighbouring.append((label, near))
    declared = {c for p in build_kpatch.PATCHES for c in p["conflicts"]}
    undeclared = [(label, hits) for label, hits in overlapping if label.split()[0] not in declared]
    print(f"\nOVERLAP, declared as conflicts ({len(overlapping) - len(undeclared)}):")
    for label, hits in overlapping:
        if label.split()[0] in declared:
            print(f"  {label}")
            for h in hits[:6]:
                print(f"      {h}")
    print(f"\nOVERLAP, NOT declared -- declare as conflicts ({len(undeclared)}):")
    for label, hits in undeclared:
        print(f"  {label}")
        for h in hits[:6]:
            print(f"      {h}")
    print(f"\nNEAR (within {arguments.near} bytes) -- review ({len(neighbouring)}):")
    for label, near in neighbouring:
        print(f"  {label}")
        for n in near[:6]:
            print(f"      {n}")
    return 1 if undeclared else 0


if __name__ == "__main__":
    raise SystemExit(main())
