#!/usr/bin/env python3
"""Install, check and uninstall the macOS package into a stand-in game, five times.

macos/kmrp-mac.sh writes into the game bundle and into swkotor.ini under $HOME. This runs it
against a stand-in: a bundle holding a copy of the unmodified KOTOR_Exe and links to the
game's texture pack, chitin.key and data/, and a temporary $HOME with a swkotor.ini of its
own. Nothing of the real game or the real ini is read or written except those (read).

1. A listed size (--size 3024x1964): the engine files, the module taken out of KMRP-macOS.kpatch,
   the load command, the two ini keys of the size, and nothing in the game's override folder
   (since 2026-10-04 the menu sets, the artwork and what is made from the game are inside the
   module, which Test-MacAssets.py checks; until then this test compared some 1,800 installed
   Override files); status reports nothing changed; uninstall leaves the executable, the bundle
   and the ini exactly as they were.
2. A size the build has no set for (--size 1800x1169), which the module blends when the game
   starts: the installer only checks kmrp-guiblend's table covers it; then the same clean
   uninstall.
3. The listed size again, over the settings round 2 left behind.

The controller's kmrp-controller.ini (beside swkotor.ini, since 2026-09-29), the player's file
as on Windows: round 1 has none, so install writes the defaults and uninstall removes them;
in round 2 the player edits it after installing, and uninstall keeps it and still finishes;
round 3 installs over that edited copy, which install and uninstall leave byte for byte.
4. A listed size with both options off (--no-controller --no-map-notes), as the installer
   app's Advanced Settings pass them: the same patch and module, no SDL, the package's hook
   list without the controller's hooks (patch_config.controller-off.toml), install.info saying
   controller=0, and the player's kmrp-controller.ini untouched by install and uninstall.

The patch's options (since 2026-10-04, as Windows and KOTOR Patch Manager's patch-options pull
request record them): every round finds configs/kmrp.ini beside KOTOR_Exe with a
[Patch Options] section holding the round's choices, and uninstall takes it out. Round 2
installs with --debug-logs; round 3 installs over a configs/kmrp.ini that already holds a
section of the patch's own, which install and uninstall keep byte for byte.
5. FTD's widescreen patch installed through KotOR Patch Manager, laid out as KPM lays it out
   on the Mac: KMRP replaces it (its files deleted, the untouched game put back from KPM's copy
   before KMRP installs) and uninstall leaves the untouched game; with a KPM patch that is not
   FTD's, KMRP installs for KPM, as on Windows: KOTOR_Exe and KPM's files as they were, the
   menus installed and KMRP-macOS.kpatch delivered, and uninstall leaves KPM's install exactly
   (until 2026-10-01 that was refused).
6. KPM's records of KMRP's own install, as Windows writes them (2026-10-01): every round above
   finds kpm_install_state.json and a KPM-format backup of the untouched KOTOR_Exe beside it,
   and KMRP-macOS.kpatch in the patch folder KPM's settings name; and once KPM's Apply has rewritten
   the runtime, uninstall removes KPM's runtime as well when KMRP is its only patch, leaving the
   untouched game, and leaves the runtime, load command and records to KPM beside another patch.

    python testing/regression/Test-MacInstaller.py PACKAGE_KMRP_DIR CLEAN_KOTOR_EXE SWPC_TEX_GUI_ERF

PACKAGE_KMRP_DIR is dist/macos/KMRP-macOS-<version>/KMRP Installer.app/Contents/Resources/kmrp from
macos/build.sh.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# What the installer installs since 2026-10-04: KMRP's patch and the two of FTD's it requires, each
# a .kpatch in the package, with the id KPM names its module by, in KPM's order.
# What an install holds: FTD's two, KMRP's own, and, while Controller Support is on, the
# controller patch (a patch of its own since 2026-10-07).
CORE_PATCHES = (("K1StrayBugFixes.kpatch", "k1-stray-bug-fixes-patch"), ("K1WidescreenPatch.kpatch", "k1widescreenpatch"),
                ("KMRP-macOS.kpatch", "kmrp"))
CONTROLLER_PATCH = ("KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch", "kmrp-controller")
PATCHES = CORE_PATCHES + (CONTROLLER_PATCH,)

INI_BEFORE = "[Graphics Options]\r\nWidth=1024\r\nHeight=768\r\nForceWidth=1600\r\nAnti Aliasing=2\r\n\r\n[Sound Options]\r\nMusic=1\r\n"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    package, clean_exe, erf = (Path(a).resolve() for a in sys.argv[1:])
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="kmrp-installer-test-") as tmp:
        tmp = Path(tmp)
        home = tmp / "home"
        ini = home / "Library/Application Support/Knights of the Old Republic/swkotor.ini"
        ini.parent.mkdir(parents=True)
        game = tmp / "Knights of the Old Republic.app"
        (game / "Contents/MacOS").mkdir(parents=True)
        (game / "Contents/Assets/TexturePacks").mkdir(parents=True)
        (game / "Contents/Assets/TexturePacks/swpc_tex_gui.erf").symlink_to(erf)
        # tutorial.2da is read through chitin.key from data/2da.bif.
        (game / "Contents/Assets/chitin.key").symlink_to(erf.parent.parent / "chitin.key")
        (game / "Contents/Assets/data").symlink_to(erf.parent.parent / "data")
        exe = game / "Contents/MacOS/KOTOR_Exe"
        shutil.copy2(clean_exe, exe)
        vanilla = sha(exe)
        exe_size = exe.stat().st_size
        env = dict(os.environ, HOME=str(home))
        script = package / "kmrp-mac.sh"

        def run(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([str(script), *args, "--game", str(game)], env=env, text=True,
                                  capture_output=True)

        def ini_value(key: str) -> str | None:
            section = False
            for line in ini.read_text().replace("\r", "").splitlines():
                if line.startswith("["):
                    section = line.lower() == "[graphics options]"
                elif section and line.split("=")[0].strip().lower() == key.lower():
                    return line.split("=", 1)[1].strip()
            return None

        settings = ini.parent / "kmrp-controller.ini"
        player_settings = b""
        # KotOR Patch Manager's settings, naming its patch folder, where the install puts
        # KMRP-macOS.kpatch (KPatchLauncher's AppSettings under .NET's ApplicationData, ~/.config).
        kpm_folder = tmp / "kpm-patches"
        kpm_folder.mkdir()
        (home / ".config/KPatchLauncher").mkdir(parents=True)
        (home / ".config/KPatchLauncher/settings.json").write_text(
            '{\n  "PatchesPath": "%s",\n  "GamePath": ""\n}\n' % kpm_folder)
        # "off": the options off (--no-controller --no-map-notes --no-hd-icons), with the player's settings
        # file from the round before still there, which the install must leave alone.
        for size, listed, mode in (("3024x1964", True, "fresh"), ("1800x1169", False, "edit"),
                                   ("3024x1964", True, "kept"), ("1512x982", True, "off")):
            width, height = (int(v) for v in size.split("x"))
            ini.write_bytes(INI_BEFORE.encode())
            if mode in ("kept", "off"):
                player_settings = settings.read_bytes() if settings.is_file() else b""
            if mode == "kept" and player_settings:
                # A settings file from before the Xbox-style HUD: no [Hud] section. Install adds
                # the section and touches nothing else.
                cut = player_settings.find(b"[Hud]")
                if cut < 0:
                    failures.append(f"{size}: the settings file the installer wrote has no [Hud] section")
                else:
                    settings.write_bytes(player_settings[:cut].rstrip(b"\n") + b"\n")
                    player_settings = settings.read_bytes()
            options = {"off": ["--no-controller", "--no-map-notes", "--no-hd-icons"],
                       "edit": ["--debug-logs"]}.get(mode, [])
            # A list of resolutions left beside KOTOR_Exe by an install of 2026-10-07, whose
            # checklist wrote one: removed, and nothing is written for the game's list.
            if mode == "edit":
                (game / "Contents/MacOS/kmrp-resolutions.txt").write_text("1800x1169\n1280x800\n")
            # The patch's own settings, already in its file in configs: kept by install and uninstall.
            options_ini = game / "Contents/MacOS/configs/kmrp.ini"
            own_section = b"[Presets]\r\nlast=enhanced\r\n" if mode == "kept" else b""
            if own_section:
                options_ini.parent.mkdir()
                options_ini.write_bytes(own_section)
            result = run("install", "--size", size, "--yes", *options)
            if result.returncode != 0:
                failures.append(f"{size}: install failed: {result.stderr.strip()[-300:]}")
                continue
            # The controller's settings: Windows' defaults when there are none, else the player's;
            # without the controller, not touched at all.
            if mode == "off":
                if settings.read_bytes() != player_settings:
                    failures.append(f"{size}: install without the controller touched kmrp-controller.ini")
            elif mode == "kept":
                now = settings.read_bytes()
                if not player_settings or not now.startswith(player_settings) or b"[Hud]" in player_settings \
                        or not now.rstrip().endswith(b"Style=Xbox") or now.count(b"[Hud]") != 1:
                    failures.append(f"{size}: the player's kmrp-controller.ini was not kept with the [Hud] section added")
                player_settings = now
                if "Kept your kmrp-controller.ini" not in result.stdout:
                    failures.append(f"{size}: install did not say it kept kmrp-controller.ini")
            else:
                text = settings.read_text() if settings.is_file() else ""
                if not all(line in text.splitlines() for line in ("[Rumble]", "Mode=Enhanced", "Strength=100",
                                                                  "SaberHum=6", "Debug=0")):
                    failures.append(f"{size}: kmrp-controller.ini was not written with the defaults")
            if mode == "edit":
                settings.write_text(settings.read_text().replace("Strength=100", "Strength=40"))
            override = game / "Contents/Assets/override"
            # Engine: KMRP's one patch (FTD's widescreen patch and Stray Bug Fixes with KMRP's code),
            # the same file whatever the options; KPM's hook list for the controller option, the
            # options recorded in configs/kmrp.ini; SDL with the controller only.
            hook_list = "patch_config.controller-off.toml" if mode == "off" else "patch_config.toml"
            installed = CORE_PATCHES if mode == "off" else PATCHES
            macos_dir = game / "Contents/MacOS"
            files = sorted(str(p.relative_to(macos_dir)) for p in macos_dir.rglob("*") if p.is_file())
            backups = [f for f in files if re.fullmatch(r"KOTOR_Exe\.backup\.\d{8}_\d{6}", f)]
            files = [f for f in files if f not in backups and f not in [b + ".json" for b in backups]]
            want = ["KOTOR_Exe", "KotorPatcher.dylib", "kpm_install_state.json", "patch_config.toml",
                    "configs/kmrp.ini"] + [f"patches/{patch_id}.dylib" for _, patch_id in installed]
            if mode != "off":
                want.append("configs/kmrp-controller.ini")
            if (macos_dir / "kmrp-resolutions.txt").exists():
                failures.append(f"{size}: a list of resolutions is beside KOTOR_Exe")
            if files != sorted(want):
                failures.append(f"{size}: MacOS holds {files}, not {sorted(want)}")
            # KPM's records, as Windows writes them: the untouched game in KPM's format, and
            # the install state KPM identifies the modified game by.
            if len(backups) != 1 or sha(macos_dir / backups[0]) != vanilla:
                failures.append(f"{size}: no KPM-format backup of the untouched KOTOR_Exe ({backups})")
            else:
                info = json.loads((macos_dir / f"{backups[0]}.json").read_text())
                if info.get("Hash") != vanilla.upper() or info.get("FileSize") != exe_size:
                    failures.append(f"{size}: {backups[0]}.json does not describe the untouched game")
            try:
                state = json.loads((macos_dir / "kpm_install_state.json").read_text())
                version = state["OriginalVersion"]
                if (state["OriginalHash"] != vanilla.upper() or not state["LinkedDependencyInstalled"]
                        or state["LibraryProxyInstalled"] or state["InstalledPatches"] != [patch_id for _, patch_id in installed]
                        or version["Version"] != "1 1.4.0 (Aspyr macOS)" or version["Platform"] != 1):
                    failures.append(f"{size}: kpm_install_state.json is not KPM's record of this game")
            except (OSError, ValueError, KeyError) as error:
                failures.append(f"{size}: kpm_install_state.json unreadable: {error}")
            for name, _ in installed:
                delivered = kpm_folder / name
                if not delivered.is_file() or delivered.read_bytes() != (package / "engine" / name).read_bytes():
                    failures.append(f"{size}: {name} is not in KPM's patch folder as packaged")
            if mode == "off" and (kpm_folder / CONTROLLER_PATCH[0]).exists():
                failures.append(f"{size}: the controller patch was delivered with Controller Support off")
            chosen = (0, 0) if mode == "off" else (1, 1 if mode == "edit" else 0)
            # hd-icons (since 2026-10-08) is on unless --no-hd-icons, which the "off" round passes.
            section = "[Patch Options]\r\nmap-notes=%d\r\nhd-icons=%d\r\ndebug-logs=%d\r\n" % (chosen[0], chosen[0], chosen[1])
            controller_ini = macos_dir / "configs/kmrp-controller.ini"
            want_controller = ("[Patch Options]\r\ndebug-logs=%d\r\n" % chosen[1]).encode()
            if mode != "off" and (not controller_ini.is_file() or controller_ini.read_bytes() != want_controller):
                failures.append(f"{size}: configs/kmrp-controller.ini is "
                                f"{controller_ini.read_bytes() if controller_ini.is_file() else None!r}, not {want_controller!r}")
            want_ini = section.encode() + (b"\r\n" + own_section if own_section else b"")
            if not options_ini.is_file() or options_ini.read_bytes() != want_ini:
                failures.append(f"{size}: configs/kmrp.ini is "
                                f"{options_ini.read_bytes() if options_ini.is_file() else None!r}, not {want_ini!r}")
            if (macos_dir / "patch_config.toml").read_bytes() != (package / f"engine/{hook_list}").read_bytes():
                failures.append(f"{size}: patch_config.toml is not the package's {hook_list}")
            # Each module is its patch's own, taken out of the .kpatch as KPM takes it.
            for name, patch_id in installed:
                with zipfile.ZipFile(package / "engine" / name) as patch:
                    module = macos_dir / f"patches/{patch_id}.dylib"
                    if not module.is_file() or module.read_bytes() != patch.read("binaries/macos_x86_64.dylib"):
                        failures.append(f"{size}: patches/{patch_id}.dylib is not the module in {name}")
            with zipfile.ZipFile(package / "engine/KMRP-macOS.kpatch") as patch:
                manifest = patch.read("manifest.toml").decode()
                if 'requires = ["k1-stray-bug-fixes-patch", "k1widescreenpatch"]' not in manifest:
                    failures.append(f"{size}: KMRP-macOS.kpatch does not require FTD's two patches")
            if subprocess.run([str(package / "bin/kmrp-macho"), "has-dylib", str(exe), "KotorPatcher.dylib"],
                              capture_output=True).returncode != 0:
                failures.append(f"{size}: KOTOR_Exe has no load command for KotorPatcher")
            # Ini: the size only. UseGuiFileLayouts is the module's to answer since 2026-10-04.
            # The size the game starts at: the game's own Width and Height when this display offers
            # the size (the resolution is then chosen in the game), ForceWidth and ForceHeight for
            # any other. Which it is depends on the display the test runs on.
            if ini_value("UseGuiFileLayouts") is not None:
                failures.append(f"{size}: install wrote UseGuiFileLayouts")
            started = (ini_value("Width"), ini_value("Height")) == (str(width), str(height))
            forced = (ini_value("ForceWidth"), ini_value("ForceHeight")) == (str(width), str(height))
            if not started and not forced:
                failures.append(f"{size}: swkotor.ini holds neither Width/Height nor ForceWidth/ForceHeight {size}")
            # Nothing in the game's override folder: the menu sets, the artwork and what is made
            # from the game are the module's (Test-MacAssets.py checks what it unpacks).
            if override.exists():
                failures.append(f"{size}: install wrote the game's override folder ({len(list(override.iterdir()))} files)")
            for gone in ("override", "layouts.zip", "engine/kmrp.dylib", "engine/kmrp-sdl3.dylib",
                         "bin/kmrp-gameart", "bin/kmrp-abilityicons"):
                if (package / gone).exists():
                    failures.append(f"{size}: the package still carries {gone}")
            status = run("status")
            if "0 changed or missing" not in status.stdout:
                failures.append(f"{size}: status: {status.stdout.strip()[-200:]}")
            want = {"fresh": "the defaults KMRP wrote", "edit": "edited by you"}.get(mode)
            if want and f"kmrp-controller.ini: {want}" not in status.stdout:
                failures.append(f"{size}: status does not say the settings are {want}")
            if "resolutions=" in status.stdout:
                failures.append(f"{size}: status still has a line for chosen resolutions")
            if f"controller={0 if mode == 'off' else 1}" not in status.stdout:
                failures.append(f"{size}: status does not record controller support as {'off' if mode == 'off' else 'on'}")
            # Uninstall.
            result = run("uninstall", "--yes")
            if result.returncode != 0:
                failures.append(f"{size}: uninstall failed: {result.stderr.strip()[-300:]}")
            if mode == "fresh" and settings.exists():
                failures.append(f"{size}: uninstall left the unchanged default kmrp-controller.ini")
            if mode == "edit" and ("Strength=40" not in (settings.read_text() if settings.is_file() else "")
                                   or "Kept your edited kmrp-controller.ini" not in result.stdout):
                failures.append(f"{size}: uninstall did not keep the edited kmrp-controller.ini")
            if mode in ("kept", "off") and (not settings.is_file() or settings.read_bytes() != player_settings):
                failures.append(f"{size}: uninstall touched the player's kmrp-controller.ini")
            if sha(exe) != vanilla:
                failures.append(f"{size}: KOTOR_Exe is not back to the original")
            if own_section:
                if not options_ini.is_file() or options_ini.read_bytes() != own_section:
                    failures.append(f"{size}: uninstall did not leave the patch's own section in configs/kmrp.ini as it was")
                shutil.rmtree(options_ini.parent, ignore_errors=True)
            left = sorted(p.name for p in (game / "Contents/MacOS").iterdir())
            if left != ["KOTOR_Exe"]:
                failures.append(f"{size}: left in MacOS: {left}")
            if override.exists():
                failures.append(f"{size}: override was left behind ({len(list(override.iterdir()))} files)")
            if ini.read_bytes() != INI_BEFORE.encode():
                failures.append(f"{size}: swkotor.ini is not as it was: {ini.read_bytes()!r}")
            if (home / "Library/Application Support/KMRP").exists():
                failures.append(f"{size}: the install state was left behind")
            for name, _ in PATCHES:
                if (kpm_folder / name).exists():
                    failures.append(f"{size}: uninstall left {name} in KPM's patch folder")
            print(f"     {size}: {'a listed size' if listed else 'a size the module blends'}; "
                  f"{'controller and map notes off' if mode == 'off' else f'controller settings {mode}'}")

        # 5. FTD's widescreen patch installed through KotOR Patch Manager, laid out as KPM lays
        #    it out on the Mac (KPatchCore: the patcher named in KOTOR_Exe's load commands, the
        #    patch list, patches/, kpm_install_state.json, and KOTOR_Exe.backup.<time> with its
        #    .json): KMRP deletes it and installs over the untouched game, and uninstall leaves
        #    that game. With any other KPM patch installed, KMRP refuses and changes nothing.
        macos = game / "Contents/MacOS"

        def snapshot() -> dict[str, str]:
            return {str(p.relative_to(macos)): sha(p) for p in sorted(macos.rglob("*")) if p.is_file()}

        def kpm_install(ids: list[str]) -> None:
            shutil.copy2(package / "engine/KotorPatcher.dylib", macos / "KotorPatcher.dylib")
            (macos / "patches").mkdir()
            for i in ids:   # KPM names each module after its patch id; the installer reads only names
                (macos / "patches" / f"{i}.dylib").write_bytes(f"stand-in for {i}\n".encode())
            (macos / "patch_config.toml").write_text(
                "".join(f'[[patches]]\nid = "{i}"\ndll = "patches/{i}.dylib"\n\n' for i in ids))
            (macos / "kpm_install_state.json").write_text('{"deployment": "LinkedDependency"}\n')
            backup = macos / "KOTOR_Exe.backup.20260930_120000"
            shutil.copy2(exe, backup)
            (macos / f"{backup.name}.json").write_text('{"Hash": "%s"}\n' % vanilla.upper())
            subprocess.run([str(package / "bin/kmrp-macho"), "add-dylib", str(exe), "@executable_path/KotorPatcher.dylib"],
                           check=True, capture_output=True)
            subprocess.run(["codesign", "--force", "--sign", "-", "--identifier", "KOTOR_Exe", str(exe)],
                           check=True, capture_output=True)

        ini.write_bytes(INI_BEFORE.encode())
        kpm_install(["k1-stray-bug-fixes-patch", "k1widescreenpatch"])
        before = snapshot()
        status = run("status", "--brief")
        if "(supported: KMRP replaces it)" not in status.stdout:
            failures.append(f"KPM: status does not offer to replace FTD's install: {status.stdout.strip()[-200:]}")
        ftd_install = before
        result = run("install", "--size", "3024x1964", "--yes")
        if result.returncode != 0:
            failures.append(f"KPM: install over FTD's install failed: {result.stderr.strip()[-300:]}")
        else:
            now = snapshot()
            # FTD's install is replaced by KMRP's, which installs his two patches again in the
            # version it was built with: nothing of the old install is left as it was.
            gone = [name for name in ftd_install if name not in ("KOTOR_Exe", "KotorPatcher.dylib", "patch_config.toml",
                                                                "kpm_install_state.json")
                    and now.get(name) == ftd_install[name]]
            if gone:
                failures.append(f"KPM: FTD's install was not removed: {gone}")
            for _, patch_id in PATCHES:
                if f"patches/{patch_id}.dylib" not in now:
                    failures.append(f"KPM: {patch_id} is not installed over FTD's install")
            if "patches/kmrp.dylib" not in now:
                failures.append("KPM: KMRP's patch not installed")
            kept = home / "Library/Application Support/KMRP/macos/backup/KOTOR_Exe"
            if not kept.is_file() or sha(kept) != vanilla:
                failures.append("KPM: KMRP's backup is not the untouched game")
            result = run("uninstall", "--yes")
            if result.returncode != 0:
                failures.append(f"KPM: uninstall failed: {result.stderr.strip()[-300:]}")
            if snapshot() != {"KOTOR_Exe": vanilla}:
                failures.append(f"KPM: uninstall did not leave the untouched game: {sorted(snapshot())[:6]}")
            if (kpm_folder / "KMRP-macOS.kpatch").exists():
                failures.append("KPM: uninstall left KMRP-macOS.kpatch")
            if ini.read_bytes() != INI_BEFORE.encode():
                failures.append("KPM: swkotor.ini is not as it was")
            if (home / "Library/Application Support/KMRP").exists():
                failures.append("KPM: the install state was left behind")
        # With a patch that is not FTD's: installed for KPM, as on Windows. KOTOR_Exe and KPM's
        # files as they were (the controller's SDL added beside the game), the menus in,
        # KMRP-macOS.kpatch where KPM finds it; uninstall leaves KPM's install exactly.
        kpm_install(["k1-stray-bug-fixes-patch", "k1widescreenpatch", "someone-elses-patch"])
        ini.write_bytes(INI_BEFORE.encode())
        before = snapshot()
        status = run("status", "--brief")
        if "supported: KMRP installs for KPM)" not in status.stdout:
            failures.append(f"KPM: status does not offer to install for KPM: {status.stdout.strip()[-200:]}")
        result = run("install", "--size", "3024x1964", "--yes")
        if result.returncode != 0:
            failures.append(f"KPM: install for KPM failed: {result.stderr.strip()[-300:]}")
        else:
            now = snapshot()
            if now != before:
                failures.append("KPM: the install for KPM changed KOTOR_Exe or KPM's files, or added to them")
            if (game / "Contents/Assets/override").exists():
                failures.append("KPM: the install for KPM wrote the game's override folder")
            if not (kpm_folder / "KMRP-macOS.kpatch").is_file():
                failures.append("KPM: KMRP-macOS.kpatch was not delivered")
            if "for_kpm=1" not in run("status").stdout:
                failures.append("KPM: status does not record the install for KPM")
            result = run("uninstall", "--yes")
            if result.returncode != 0:
                failures.append(f"KPM: uninstall of the install for KPM failed: {result.stderr.strip()[-300:]}")
            if snapshot() != before:
                failures.append("KPM: uninstall did not leave KPM's install exactly as it was")
            if (game / "Contents/Assets/override").exists() or (kpm_folder / "KMRP-macOS.kpatch").exists():
                failures.append("KPM: uninstall left KMRP's files")
            if ini.read_bytes() != INI_BEFORE.encode():
                failures.append("KPM: swkotor.ini is not as it was after the install for KPM")
        # The stand-in KPM install cleared: back to the untouched game.
        for name in list(snapshot()):
            if name != "KOTOR_Exe":
                (macos / name).unlink()
        shutil.rmtree(macos / "patches", ignore_errors=True)
        shutil.copy2(clean_exe, exe)

        # 6. KPM takes KMRP's install over (its Apply rewrites the runtime). With KMRP its only
        #    patch, uninstall removes KPM's runtime too, as KPM's Remove would, and leaves the
        #    untouched game (2026-10-01); with another patch beside it, uninstall removes KMRP's
        #    own files and leaves the runtime, the load command and KPM's records to KPM.
        def take_over(other: bool) -> None:
            # KPM 0.7.1's Apply, as seen on 2026-10-01: patch_config.toml and kmrp.dylib written
            # back byte for byte as KMRP wrote them, its own KotorPatcher.dylib and state file,
            # its address database, and patches/ emptied but for the patches' modules; the
            # controller's SDL, beside the game, is out of its way.
            with open(macos / "KotorPatcher.dylib", "ab") as f:
                f.write(b"KPM's own build\n")
            state = macos / "kpm_install_state.json"
            state.write_text(state.read_text().replace('"UpdatedAt"', '"UpdatedAt" ', 1))
            (macos / "addresses.db").write_bytes(b"KPM's address database\n")
            for p in (macos / "patches").iterdir():
                if p.name not in {f"{patch_id}.dylib" for _, patch_id in PATCHES}:
                    p.unlink()
            if other:
                (macos / "patches/someone-elses-patch.dylib").write_bytes(b"stand-in\n")
                config = macos / "patch_config.toml"
                config.write_text(config.read_text() + '\n[[patches]]\nid = "someone-elses-patch"\n'
                                  'dll = "patches/someone-elses-patch.dylib"\n')

        for other in (False, True):
            case = "takeover with another patch" if other else "takeover"
            ini.write_bytes(INI_BEFORE.encode())
            result = run("install", "--size", "3024x1964", "--yes")
            if result.returncode != 0:
                failures.append(f"{case}: install failed: {result.stderr.strip()[-300:]}")
                break
            take_over(other)
            runtime = snapshot()
            result = run("uninstall", "--yes")
            if result.returncode != 0:
                failures.append(f"{case}: uninstall failed: {result.stderr.strip()[-300:]}")
            if other:
                if "taken over the runtime" not in result.stdout:
                    failures.append(f"{case}: uninstall did not say KPM has the runtime")
                if snapshot() != runtime:
                    failures.append(f"{case}: uninstall touched KPM's runtime, load command or records")
            else:
                if "removing it as KPM would" not in result.stdout:
                    failures.append(f"{case}: uninstall did not say it removes KPM's runtime")
                if snapshot() != {"KOTOR_Exe": vanilla}:
                    failures.append(f"{case}: uninstall did not leave the untouched game: {sorted(snapshot())[:8]}")
            if (game / "Contents/Assets/override").exists():
                failures.append(f"{case}: uninstall left KMRP's menus")
            if (kpm_folder / "KMRP-macOS.kpatch").exists():
                failures.append(f"{case}: uninstall left KMRP-macOS.kpatch")
            if (home / "Library/Application Support/KMRP").exists():
                failures.append(f"{case}: the install state was left behind")
        print("     KPM: FTD's install replaced, the untouched game left at uninstall; another KPM patch: "
              "installed for KPM and left exactly; KMRP's install taken over by KPM: removed whole when "
              "KMRP is KPM's only patch, left to KPM beside another")

    for failure in failures:
        print("  " + failure)
    print(f"{'FAIL' if failures else 'ok  '} install, status and uninstall into a stand-in game, listed and "
          f"blended sizes, controller settings, both options off: {len(failures)} problems")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
