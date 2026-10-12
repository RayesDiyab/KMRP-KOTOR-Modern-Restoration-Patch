#!/usr/bin/env python3
"""KMRP for the Mac App Store's game: the package's second set, and the installer's way with it.

The App Store's game is not changed by KMRP (docs/macos-app-store.md): the installer makes an
app beside it, "KOTOR with KMRP", holding the patcher, a hook list translated for that build of
KOTOR_Exe and modules compiled with its addresses, which the package carries as what turns
Steam's modules into them.

1. The hook lists (appstore/patch_config*.toml): each names the App Store's KOTOR_Exe by its
   SHA-256; every hook's original bytes are what that file has at the hook's address; no two
   hooks of a list overlap; and each list has the hooks its Steam counterpart has, patch by
   patch, in the same order.
2. install --game <a stand-in of the App Store's game> with every choice of controller support
   and High FPS Fix: the app appears beside the game, signed, with the hook list of the choice,
   the options written, each module the file its delta names (by SHA-256), SDL beside the
   controller's module and only with it; the stand-in game is byte for byte what it was;
   status reports the install; a second install is refused; uninstall removes the app and the
   state and nothing else; an app of that name that is not KMRP's is left alone and refused.
3. A game that is the App Store's by its bundle id but another KOTOR_Exe is refused.

    python testing/regression/Test-MacAppStore.py PACKAGE_KMRP_DIR APPSTORE_KOTOR_EXE

PACKAGE_KMRP_DIR is dist/macos/KMRP-macOS-<version>/KMRP Installer.app/Contents/Resources/kmrp
from macos/build.sh, built with the App Store's KOTOR_Exe at hand. The executable is read and
copied into a temporary stand-in; the real game is not touched.
"""
from __future__ import annotations

import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

APPSTORE_SHA = "d03315aace822908d6b7ca936d47c644ffe6ebf79822c8c62225bfaaf79ad7ca"
BASE = 0x100000000
LISTS = {(1, 0): "patch_config.toml", (0, 0): "patch_config.controller-off.toml",
         (1, 1): "patch_config.high-fps.toml", (0, 1): "patch_config.controller-off.high-fps.toml"}
KPATCH = {"k1-stray-bug-fixes-patch": "K1StrayBugFixes.kpatch", "k1widescreenpatch": "K1WidescreenPatch.kpatch",
          "kmrp": "KMRP-macOS.kpatch", "kmrp-controller": "KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch",
          "high-fps-fixes": "High FPS Fixes (macOS).kpatch"}
APP = "KOTOR with KMRP.app"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    package, exe_path = (Path(a).resolve() for a in sys.argv[1:])
    store = package / "appstore"
    if not (store / "loader.dylib").is_file():
        print(f"FAIL {store} has no App Store set: the package was built without the App Store's KOTOR_Exe")
        return 1
    exe = exe_path.read_bytes()
    if hashlib.sha256(exe).hexdigest() != APPSTORE_SHA:
        print(f"FAIL {exe_path} is not the App Store's KOTOR_Exe 1.4.1")
        return 1
    failures: list[str] = []

    # 1. the hook lists
    for (controller, high_fps), name in LISTS.items():
        listed = tomllib.loads((store / name).read_text())
        steam = tomllib.loads((package / "engine" / name).read_text())
        if listed["target_version_sha"].lower() != APPSTORE_SHA:
            failures.append(f"{name}: names another executable")
        if [p["id"] for p in listed["patches"]] != [p["id"] for p in steam["patches"]]:
            failures.append(f"{name}: not the patches of Steam's list")
        spans = []
        for patch, steam_patch in zip(listed["patches"], steam["patches"]):
            hooks, steam_hooks = patch.get("hooks", []), steam_patch.get("hooks", [])
            if [(h["type"], len(h["original_bytes"]), h.get("function")) for h in hooks] != \
               [(h["type"], len(h["original_bytes"]), h.get("function")) for h in steam_hooks]:
                failures.append(f"{name}: {patch['id']} has other hooks than Steam's list")
            for hook in hooks:
                at, original = hook["address"] - BASE, bytes(hook["original_bytes"])
                if exe[at:at + len(original)] != original:
                    failures.append(f"{name}: {patch['id']} {hook['address']:#x}: the game has other bytes there")
                spans.append((at, at + len(original)))
        spans.sort()
        if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
            failures.append(f"{name}: two hooks overlap")
    print(f"     hook lists: {len(LISTS)}, {len(spans)} hooks in the last, every original byte as the App Store's game has it")

    with tempfile.TemporaryDirectory(prefix="kmrp-appstore-") as tmp:
        tmp = Path(tmp)
        home = tmp / "home"
        home.mkdir()
        folder = tmp / "Applications"
        game = folder / "Knights of the Old Republic.app"
        (game / "Contents/MacOS").mkdir(parents=True)
        (game / "Contents/_MASReceipt").mkdir()
        (game / "Contents/_MASReceipt/receipt").write_bytes(b"stand-in")
        (game / "Contents/MacOS/KOTOR_Exe").write_bytes(exe)
        (game / "Contents/MacOS/KOTOR_Exe").chmod(0o755)
        (game / "Contents/MacOS/AppBundleExe").write_bytes(b"#!/bin/sh\n")
        (game / "Contents/MacOS/AppBundleExe").chmod(0o755)
        with open(game / "Contents/Info.plist", "wb") as f:
            plistlib.dump({"CFBundleIdentifier": "com.aspyr.kotor", "CFBundleExecutable": "AppBundleExe"}, f)
        before = tree(game)
        env = dict(os.environ, HOME=str(home))
        script = str(package / "kmrp-mac.sh")
        state = home / "Library/Application Support/KMRP/macos-appstore"

        def run(*args):
            return subprocess.run(["/bin/zsh", script, *args, "--game", str(game)], env=env, capture_output=True, text=True)

        # 2. every choice
        for (controller, high_fps), name in LISTS.items():
            label = f"controller {controller}, high fps {high_fps}"
            args = ["install", "--yes", "--high-fps" if high_fps else "--no-high-fps"]
            if not controller:
                args.append("--no-controller")
            result = run(*args)
            app = folder / APP
            kmrp = app / "Contents/Resources/kmrp"
            if result.returncode != 0 or not app.is_dir():
                failures.append(f"{label}: install failed: {result.stdout[-300:]}{result.stderr[-300:]}")
                continue
            if subprocess.run(["codesign", "--verify", "--strict", str(app)], capture_output=True).returncode != 0:
                failures.append(f"{label}: the app is not signed whole")
            if (kmrp / "patch_config.toml").read_bytes() != (store / name).read_bytes():
                failures.append(f"{label}: not the hook list of the choice")
            if (kmrp / "game-path.txt").read_text().strip() != str(game):
                failures.append(f"{label}: game-path.txt does not name the game")
            ids = [p["id"] for p in tomllib.loads((store / name).read_text())["patches"]]
            for patch in ids:
                module = kmrp / "patches" / f"{patch}.dylib"
                delta = store / f"{patch}.dylib.delta"
                if delta.is_file():
                    want = next(line.split()[1] for line in delta.read_bytes().split(b"\ndata\n", 1)[0].decode().split("\n")
                                if line.startswith("new "))
                    with zipfile.ZipFile(package / "engine" / KPATCH[patch]) as z:
                        base = hashlib.sha256(z.read("binaries/macos_x86_64.dylib")).hexdigest()
                    named = next(line.split()[1] for line in delta.read_bytes().split(b"\ndata\n", 1)[0].decode().split("\n")
                                 if line.startswith("base "))
                    if base != named:
                        failures.append(f"{label}: {patch}'s delta is not against the module in its .kpatch")
                else:
                    want = sha(store / f"{patch}.dylib")
                if not module.is_file() or sha(module) != want:
                    failures.append(f"{label}: {patch}.dylib is not the App Store module")
            others = {p.name for p in (kmrp / "patches").iterdir()} - {f"{i}.dylib" for i in ids}
            if others != ({"kmrp-sdl3.dylib"} if controller else set()):
                failures.append(f"{label}: beside the modules: {sorted(others)}")
            options = (kmrp / "configs/kmrp.ini").read_bytes()
            if options != b"[Patch Options]\r\nmap-notes=1\r\nhd-icons=1\r\ndebug-logs=0\r\n":
                failures.append(f"{label}: configs/kmrp.ini is {options!r}")
            if (kmrp / "configs/kmrp-controller.ini").is_file() != bool(controller):
                failures.append(f"{label}: configs/kmrp-controller.ini does not follow the choice")
            if tree(game) != before:
                failures.append(f"{label}: the game was changed by install")
            status = run("status")
            if "store=mac-app-store" not in status.stdout or "as installed" not in status.stdout:
                failures.append(f"{label}: status does not report the install: {status.stdout[-200:]}")
            again = run("install", "--yes")
            if again.returncode == 0 or "already installed" not in again.stderr:
                failures.append(f"{label}: a second install was not refused")
            removed = run("uninstall", "--yes")
            if removed.returncode != 0 or app.exists() or state.exists():
                failures.append(f"{label}: uninstall left the app or the state: {removed.stdout[-200:]}{removed.stderr[-200:]}")
            if tree(game) != before or sorted(p.name for p in folder.iterdir()) != [game.name]:
                failures.append(f"{label}: uninstall changed the game or left something beside it")
        print("     install, status, second install refused, uninstall: every choice of controller support and High FPS Fix")

        # an app of that name that is not KMRP's
        foreign = folder / APP
        (foreign / "Contents").mkdir(parents=True)
        with open(foreign / "Contents/Info.plist", "wb") as f:
            plistlib.dump({"CFBundleIdentifier": "com.example.other"}, f)
        refused = run("install", "--yes")
        if refused.returncode == 0 or "not KMRP's" not in refused.stderr or not (foreign / "Contents/Info.plist").is_file():
            failures.append(f"an app of KMRP's name that is not KMRP's was not refused: {refused.stderr[-200:]}")
        shutil.rmtree(foreign)
        print("     an app of that name that is not KMRP's: refused and left alone")

        # 3. another KOTOR_Exe in the App Store's bundle
        (game / "Contents/MacOS/KOTOR_Exe").write_bytes(exe[:-1] + bytes([exe[-1] ^ 1]))
        other = run("install", "--yes")
        if other.returncode == 0 or "not the Mac App Store version" not in other.stderr or (folder / APP).exists():
            failures.append(f"another version of the App Store's game was not refused: {other.stderr[-200:]}")
        print("     another version of the App Store's game: refused")

    for failure in failures:
        print("FAIL", failure)
    print(f"{'ok  ' if not failures else 'FAIL'} KMRP for the Mac App Store's game: {len(failures)} problems")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
