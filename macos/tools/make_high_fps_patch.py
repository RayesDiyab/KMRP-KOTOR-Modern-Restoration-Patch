#!/usr/bin/env python3
"""Build High FPS Fixes for the Mac game as a KotOR Patch Manager patch of its own.

A port of D3M0's High FPS Fixes 1.0.1 (MIT) to the Steam Aspyr macOS build of KOTOR 1
(macos/patches/high-fps-fixes). The patch needs no other patch and no other patch needs it;
macos/build.sh puts it in KMRP's package, and the installer installs it while High FPS Fix is on.

Before anything is built, every original_bytes of the hook list is held against the unmodified
game, and no two hooks may overlap: a list that does not describe this executable is refused
here rather than by the patcher in the player's game.

    python macos/tools/make_high_fps_patch.py --exe CLEAN_KOTOR_EXE --version 1.0.1 --out FILE.kpatch
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "macos/patches/high-fps-fixes"
HOOKS_FILE = "kotor1-steam-aspyr-macos.hooks.toml"
GAME_SHA = "C1FCB8D37C702849882A17751C63EE0AF7C2B9CBBC3B31B98A5F0EDBC27C6D71"
IMAGE_BASE = 0x100000000   # a thin, non-PIE x86_64 Mach-O: an address is its file offset plus this
ID = "high-fps-fixes"      # D3M0's id: the same patch, for another system
NAME = "High FPS Fixes (macOS)"
DESCRIPTION = ("Fixes high FPS timing and animation issues in KOTOR 1 on the Mac: the game's Steam Aspyr "
               "build. A port of D3M0's High FPS Fixes for Windows; it works on the Mac only.")
# Windows' list, which names the single fixes this patch combines.
CONFLICTS = ["k1-high-fps-fix", "dialogue-letterbox-fix", "post-combat-movement-fix",
             "post-combat-movement-fix-nodelay", "k1-freelook-sensitivity-fix", "k1-animateuv-fix",
             "k1-lightsaber-trail-fix", "k1-danglymesh-high-fps-fix", "k1-water-forcefield-fix"]
FLAGS = ["-arch", "x86_64", "-std=c++17", "-O2", "-mmacosx-version-min=10.13", "-Wall", "-Wextra",
         "-fno-exceptions", "-fno-rtti", "-fvisibility=hidden",
         # libc++'s own note that it no longer supports a system this old; the module uses none of it.
         "-Wno-#warnings"]


def fail(message: str) -> None:
    raise SystemExit(f"make_high_fps_patch: {message}")


def check_hooks(exe: bytes, hooks: list[dict], exported: set[str]) -> None:
    spans = []
    for hook in hooks:
        address, original = hook["address"], bytes(hook["original_bytes"])
        at = address - IMAGE_BASE
        if exe[at:at + len(original)] != original:
            fail(f"{address:#x}: the game has {exe[at:at + len(original)].hex()}, the list {original.hex()}")
        kind = hook["type"]
        if kind == "detour":
            if len(original) < 5:
                fail(f"{address:#x}: a detour needs five bytes")
            if hook["function"] not in exported:
                fail(f"{address:#x}: the module exports no {hook['function']}")
            if "consumed_exit_address" in hook and "eax" not in hook.get("exclude_from_restore", []):
                fail(f"{address:#x}: a consumed exit needs eax kept from the restore (KPM asks for that spelling)")
        elif kind == "simple":
            if len(hook["replacement_bytes"]) != len(original):
                fail(f"{address:#x}: a simple hook replaces as many bytes as it names")
        elif kind == "replace":
            if len(original) < 5:
                fail(f"{address:#x}: a replace needs five bytes")
        else:
            fail(f"{address:#x}: unknown hook type {kind}")
        spans.append((address, address + len(original)))
    spans.sort()
    for (_, end), (start, _) in zip(spans, spans[1:]):
        if start < end:
            fail(f"two hooks overlap at {start:#x}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--exe", type=Path, required=True, help="the unmodified KOTOR_Exe")
    parser.add_argument("--version", default="1.0.1")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    exe = args.exe.read_bytes()
    if hashlib.sha256(exe).hexdigest().upper() != GAME_SHA:
        fail(f"{args.exe} is not the unmodified Steam Aspyr KOTOR_Exe 1.4.0")
    hooks_text = (SOURCE / HOOKS_FILE).read_text()
    hooks = tomllib.loads(hooks_text)["hooks"]

    with tempfile.TemporaryDirectory(prefix="high-fps-fixes-") as tmp:
        tmp = Path(tmp)
        (tmp / "binaries").mkdir()
        module = tmp / "binaries" / "macos_x86_64.dylib"
        build = subprocess.run(["clang++", *FLAGS, "-dynamiclib", "-o", str(module),
                                *map(str, sorted(SOURCE.glob("*.cpp")))], capture_output=True, text=True)
        if build.returncode != 0 or build.stderr.strip():
            fail(f"the module does not build cleanly\n{build.stderr}")
        subprocess.run(["codesign", "--force", "--sign", "-", str(module)], check=True, capture_output=True)
        symbols = subprocess.run(["nm", "-gU", str(module)], check=True, capture_output=True, text=True).stdout
        exported = {line.split()[-1].lstrip("_") for line in symbols.splitlines() if line.strip()}
        check_hooks(exe, hooks, exported)
        unused = {name for name in exported if name.startswith("Hfps")} - {h.get("function") for h in hooks}
        if unused:
            fail(f"handlers no hook uses: {sorted(unused)}")

        (tmp / HOOKS_FILE).write_text(f'[metadata]\ntarget_versions = ["{GAME_SHA}"]\n\n' + hooks_text)
        (tmp / "manifest.toml").write_text(
            "[patch]\n"
            f'id = "{ID}"\n'
            f'name = "{NAME}"\n'
            f'version = "{args.version}"\n'
            'author = "D3M0; macOS port by RaymanGT"\n'
            f'description = "{DESCRIPTION}"\n\n'
            "requires = []\n"
            "conflicts = [" + ", ".join(f'"{c}"' for c in CONFLICTS) + "]\n\n"
            "[patch.supported_versions]\n"
            f'kotor1_steam_aspyr_macos = "{GAME_SHA}"\n')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("manifest.toml", HOOKS_FILE, "binaries/macos_x86_64.dylib"):
                z.write(tmp / name, name)
    kinds = [h["type"] for h in hooks]
    print(f"{args.out.name}: {len(hooks)} hooks ({kinds.count('detour')} detours, {kinds.count('replace')} replaced, "
          f"{kinds.count('simple')} simple), every original byte as the game has it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
