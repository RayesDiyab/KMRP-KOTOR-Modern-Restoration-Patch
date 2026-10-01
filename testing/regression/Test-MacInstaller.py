#!/usr/bin/env python3
"""Install, check and uninstall the macOS package into a stand-in game, five times.

macos/kmrp-mac.sh writes into the game bundle and into swkotor.ini under $HOME. This runs it
against a stand-in: a bundle holding a copy of the unmodified KOTOR_Exe and links to the
game's texture pack, chitin.key and data/, and a temporary $HOME with a swkotor.ini of its
own. Nothing of the real game or the real ini is read or written except those (read).

1. A listed size (--size 3024x1964): the engine files, the load command, the three ini keys,
   the size's set from layouts.zip (with KMRP's controller art, kmr*, since the controller
   patch was ported, 2026-09-29), the enlarged feat, power and skill icons, and
   what kmrp-gameart makes from the game (the four hex frames at 56s, the thirteen tut_*
   icons at 64s, tutorial.2da pointing at them); status
   reports nothing changed; uninstall leaves the executable, the bundle and the ini exactly as
   they were.
2. A size the build has no set for (--size 1800x1169): the .gui files, the controller badges,
   the prompt manifest and the HUD's button-row boxes are kmrp-guiblend's for that size (the
   badges and boxes since 2026-09-30), everything else is the nearest listed set's (by
   height, then shape); then the same clean uninstall.
3. The listed size again, over the settings round 2 left behind.

The controller's kmrp-controller.ini (beside swkotor.ini, since 2026-09-29), the player's file
as on Windows: round 1 has none, so install writes the defaults and uninstall removes them;
in round 2 the player edits it after installing, and uninstall keeps it and still finishes;
round 3 installs over that edited copy, which install and uninstall leave byte for byte.
4. A listed size with both options off (--no-controller --no-map-notes), as the installer
   app's Advanced Settings pass them: no controller module, no SDL and no map-notes patch,
   the package's patch_config.no-map-notes.no-controller.toml, install.info saying
   controller=0, and the player's kmrp-controller.ini untouched by install and uninstall.
5. FTD's widescreen patch installed through KotOR Patch Manager, laid out as KPM lays it out
   on the Mac: KMRP replaces it (its files deleted, the untouched game put back from KPM's copy
   before KMRP installs) and uninstall leaves the untouched game; with a KPM patch that is not
   FTD's, KMRP installs for KPM, as on Windows: KOTOR_Exe and KPM's files as they were, the
   menus installed and kmrp.kpatch delivered, and uninstall leaves KPM's install exactly
   (until 2026-10-01 that was refused).
6. KPM's records of KMRP's own install, as Windows writes them (2026-10-01): every round above
   finds kpm_install_state.json and a KPM-format backup of the untouched KOTOR_Exe beside it,
   and kmrp.kpatch in the patch folder KPM's settings name; and once KPM's Apply has rewritten
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

INI_BEFORE = "[Graphics Options]\r\nWidth=1024\r\nHeight=768\r\nForceWidth=1600\r\nAnti Aliasing=2\r\n\r\n[Sound Options]\r\nMusic=1\r\n"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pool_set(package: Path, size: str) -> dict[str, bytes]:
    with zipfile.ZipFile(package / "layouts.zip") as pool:
        index = pool.read(f"index/{size}.txt").decode().replace("\r", "").splitlines()
        return {name: pool.read(f"objects/{obj}") for name, obj in (line.split("\t") for line in index)}


def listed_sizes(package: Path) -> list[tuple[int, int]]:
    with zipfile.ZipFile(package / "layouts.zip") as pool:
        return [tuple(int(v) for v in n[len("index/"):-len(".txt")].split("x"))
                for n in pool.namelist() if n.startswith("index/")]


def nearest(package: Path, width: int, height: int) -> str:
    w, h = min(listed_sizes(package), key=lambda s: (abs(s[1] - height), abs(s[0] / s[1] - width / height)))
    return f"{w}x{h}"


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
        # kmrp.kpatch (KPatchLauncher's AppSettings under .NET's ApplicationData, ~/.config).
        kpm_folder = tmp / "kpm-patches"
        kpm_folder.mkdir()
        (home / ".config/KPatchLauncher").mkdir(parents=True)
        (home / ".config/KPatchLauncher/settings.json").write_text(
            '{\n  "PatchesPath": "%s",\n  "GamePath": ""\n}\n' % kpm_folder)
        # "off": both options off (--no-controller --no-map-notes), with the player's settings
        # file from the round before still there, which the install must leave alone.
        for size, listed, mode in (("3024x1964", True, "fresh"), ("1800x1169", False, "edit"),
                                   ("3024x1964", True, "kept"), ("1512x982", True, "off")):
            width, height = (int(v) for v in size.split("x"))
            ini.write_bytes(INI_BEFORE.encode())
            if mode in ("kept", "off"):
                player_settings = settings.read_bytes() if settings.is_file() else b""
            options = ["--no-controller", "--no-map-notes"] if mode == "off" else []
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
                if not player_settings or settings.read_bytes() != player_settings:
                    failures.append(f"{size}: the player's kmrp-controller.ini was not kept as it was")
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
            # in the version for the options, with KPM's list for it; SDL with the controller only.
            variant = "kmrp.no-map-notes.no-controller" if mode == "off" else "kmrp"
            macos_dir = game / "Contents/MacOS"
            files = sorted(str(p.relative_to(macos_dir)) for p in macos_dir.rglob("*") if p.is_file())
            backups = [f for f in files if re.fullmatch(r"KOTOR_Exe\.backup\.\d{8}_\d{6}", f)]
            files = [f for f in files if f not in backups and f not in [b + ".json" for b in backups]]
            want = ["KOTOR_Exe", "KotorPatcher.dylib", "kpm_install_state.json", "patch_config.toml",
                    "patches/kmrp.dylib"] + ([] if mode == "off" else ["kmrp-sdl3.dylib"])
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
                        or state["LibraryProxyInstalled"] or state["InstalledPatches"] != ["kmrp"]
                        or version["Version"] != "1 1.4.0 (Aspyr macOS)" or version["Platform"] != 1):
                    failures.append(f"{size}: kpm_install_state.json is not KPM's record of this game")
            except (OSError, ValueError, KeyError) as error:
                failures.append(f"{size}: kpm_install_state.json unreadable: {error}")
            delivered = kpm_folder / "kmrp.kpatch"
            if not delivered.is_file() or delivered.read_bytes() != (package / f"engine/{variant}/kmrp.kpatch").read_bytes():
                failures.append(f"{size}: kmrp.kpatch is not in KPM's patch folder as packaged")
            for installed, packaged in (("patch_config.toml", f"engine/{variant}/patch_config.toml"),
                                        ("patches/kmrp.dylib", f"engine/{variant}/kmrp.dylib")):
                if (macos_dir / installed).is_file() and (macos_dir / installed).read_bytes() != (package / packaged).read_bytes():
                    failures.append(f"{size}: {installed} is not the package's {packaged}")
            if subprocess.run([str(package / "bin/kmrp-macho"), "has-dylib", str(exe), "KotorPatcher.dylib"],
                              capture_output=True).returncode != 0:
                failures.append(f"{size}: KOTOR_Exe has no load command for KotorPatcher")
            # Ini.
            for key, want in (("UseGuiFileLayouts", "1"), ("ForceWidth", str(width)), ("ForceHeight", str(height))):
                if ini_value(key) != want:
                    failures.append(f"{size}: ini {key}={ini_value(key)}, want {want}")
            # The menu set.
            source = size if listed else nearest(package, width, height)
            expected = pool_set(package, source)
            if not listed:
                blend = tmp / f"blend-{size}"
                # The set the installer takes fonts from, as it passes it to the helper.
                set_dir = tmp / f"set-{source}"
                set_dir.mkdir(exist_ok=True)
                for name in ("kmrp_prompts.txt", "dialogfont16x16.txi"):
                    (set_dir / name).write_bytes(expected[name])
                subprocess.run([str(package / "bin/kmrp-guiblend"), str(package / "gui-blend.bin"),
                                str(width), str(height), str(blend), str(set_dir)],
                               check=True, capture_output=True)
                # Every file the helper writes replaces the set's: the menus, the badges drawn
                # for the blended buttons, the prompt manifest and the HUD's button-row boxes.
                for made in blend.iterdir():
                    expected[made.name] = made.read_bytes()
            for name, data in expected.items():
                path = override / name
                if not path.is_file() or path.read_bytes() != data:
                    made = not listed and (blend / name).is_file()
                    failures.append(f"{size}: override/{name} is not the {'blended' if made else source} file")
                    break
            # The controller patch's art: the set's badges and Controller Layout screen (checked
            # with the set above) and override-common.zip's cues and layout art.
            if not (override / "kmrplayout.gui").is_file():
                failures.append(f"{size}: the Controller Layout screen (kmrplayout.gui) was not installed")
            for cue in ("kmrpr3_party.tga", "kmrslytdiag.tga"):
                if not any(p.name.lower() == cue for p in override.iterdir()):
                    failures.append(f"{size}: controller art {cue} was not installed")
            icons = [p for p in override.iterdir() if p.name.startswith(("i_", "ip_")) and p.name not in expected]
            if len(icons) < 200:
                failures.append(f"{size}: only {len(icons)} enlarged ability icons")
            # The eight skill icons, 32 px in the pack, on a canvas grown with their row (scaled
            # from 50 where vanilla's is 42): round(32 * s * 50 / 42), at most 64, s as the
            # generator computes it (single precision). The picture inside is smaller;
            # Test-AbilityIcons.py checks it. All eight must be there.
            height = int(size.split("x")[1])
            s = max(1.0, struct.unpack("<f", struct.pack("<f", height / 720.0))[0])
            want = min(round(32 * s * 50 / 42), 64)
            skills = {p.name: struct.unpack_from("<HH", p.read_bytes(), 12)
                      for p in override.iterdir() if p.name.startswith("isk_")}
            if len(skills) != 8 or set(skills.values()) != {(want, want)}:
                failures.append(f"{size}: skill icons {sorted(set(skills.values()))} x{len(skills)}, want 8 at {want}")
            # What kmrp-gameart makes from the game: nothing of it ships in the package.
            scale = max(1.0, height / 720.0)
            art = {}
            for name, native in [(f"lbl_hex{s}.tga", 56) for s in ("", "_3", "_6", "_7")] + \
                                [(f"tut_{n}.tga", 64) for n in ("abi3", "char3", "inv3", "map3", "msg3", "attack",
                                                                "credits", "dside", "lside", "plotxp", "quest",
                                                                "receive", "taken")]:
                path = override / name
                side = round(native * scale)
                if not path.is_file() or struct.unpack_from("<HH", path.read_bytes(), 12) != (side, side):
                    failures.append(f"{size}: override/{name} missing or not {side} px")
                art[name] = path
            table = override / "tutorial.2da"
            if not table.is_file() or b"tut_attack" not in table.read_bytes() or b"lbl_icn_abi3" in table.read_bytes():
                failures.append(f"{size}: tutorial.2da missing or not pointing at the tut_* icons")
            for name in list(art) + ["tutorial.2da"]:
                if (package / "override" / name).exists():
                    failures.append(f"{size}: the package itself carries {name}")
            status = run("status")
            if "0 changed or missing" not in status.stdout:
                failures.append(f"{size}: status: {status.stdout.strip()[-200:]}")
            want = {"fresh": "the defaults KMRP wrote", "edit": "edited by you"}.get(mode)
            if want and f"kmrp-controller.ini: {want}" not in status.stdout:
                failures.append(f"{size}: status does not say the settings are {want}")
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
            left = sorted(p.name for p in (game / "Contents/MacOS").iterdir())
            if left != ["KOTOR_Exe"]:
                failures.append(f"{size}: left in MacOS: {left}")
            if override.exists():
                failures.append(f"{size}: override was left behind ({len(list(override.iterdir()))} files)")
            if ini.read_bytes() != INI_BEFORE.encode():
                failures.append(f"{size}: swkotor.ini is not as it was: {ini.read_bytes()!r}")
            if (home / "Library/Application Support/KMRP").exists():
                failures.append(f"{size}: the install state was left behind")
            if (kpm_folder / "kmrp.kpatch").exists():
                failures.append(f"{size}: uninstall left kmrp.kpatch in KPM's patch folder")
            print(f"     {size}: {'listed set' if listed else f'blended, fonts and art from {source}'}, "
                  f"{len(expected)} set files, {len(icons)} feat and power icons, {len(skills)} skill icons, "
                  f"{len(art) + 1} made from the game; "
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
            gone = [name for name in ftd_install if name not in ("KOTOR_Exe", "KotorPatcher.dylib", "patch_config.toml",
                                                                "kpm_install_state.json") and name in now]
            if gone:
                failures.append(f"KPM: FTD's install was not removed: {gone}")
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
            if (kpm_folder / "kmrp.kpatch").exists():
                failures.append("KPM: uninstall left kmrp.kpatch")
            if ini.read_bytes() != INI_BEFORE.encode():
                failures.append("KPM: swkotor.ini is not as it was")
            if (home / "Library/Application Support/KMRP").exists():
                failures.append("KPM: the install state was left behind")
        # With a patch that is not FTD's: installed for KPM, as on Windows. KOTOR_Exe and KPM's
        # files as they were (the controller's SDL added beside the game), the menus in,
        # kmrp.kpatch where KPM finds it; uninstall leaves KPM's install exactly.
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
            if {k: v for k, v in now.items() if k != "kmrp-sdl3.dylib"} != before:
                failures.append("KPM: the install for KPM changed KOTOR_Exe or KPM's files")
            if "kmrp-sdl3.dylib" not in now:
                failures.append("KPM: the controller's SDL was not put beside the game")
            if not (game / "Contents/Assets/override/kmrplayout.gui").is_file():
                failures.append("KPM: the menus were not installed")
            if not (kpm_folder / "kmrp.kpatch").is_file():
                failures.append("KPM: kmrp.kpatch was not delivered")
            if "for_kpm=1" not in run("status").stdout:
                failures.append("KPM: status does not record the install for KPM")
            result = run("uninstall", "--yes")
            if result.returncode != 0:
                failures.append(f"KPM: uninstall of the install for KPM failed: {result.stderr.strip()[-300:]}")
            if snapshot() != before:
                failures.append("KPM: uninstall did not leave KPM's install exactly as it was")
            if (game / "Contents/Assets/override").exists() or (kpm_folder / "kmrp.kpatch").exists():
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
                if p.name != "kmrp.dylib":
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
            if not (macos / "kmrp-sdl3.dylib").is_file():
                failures.append(f"{case}: the controller's SDL is not beside the game for KPM's install")
            runtime = {k: v for k, v in snapshot().items() if k != "kmrp-sdl3.dylib"}
            result = run("uninstall", "--yes")
            if result.returncode != 0:
                failures.append(f"{case}: uninstall failed: {result.stderr.strip()[-300:]}")
            if other:
                if "taken over the runtime" not in result.stdout:
                    failures.append(f"{case}: uninstall did not say KPM has the runtime")
                if snapshot() != runtime:
                    # SDL is KMRP's and goes, as Windows' Restore removes kmrp-sdl3.dll
                    failures.append(f"{case}: uninstall touched KPM's runtime, load command or records, or left SDL")
            else:
                if "removing it as KPM would" not in result.stdout:
                    failures.append(f"{case}: uninstall did not say it removes KPM's runtime")
                if snapshot() != {"KOTOR_Exe": vanilla}:
                    failures.append(f"{case}: uninstall did not leave the untouched game: {sorted(snapshot())[:8]}")
            if (game / "Contents/Assets/override").exists():
                failures.append(f"{case}: uninstall left KMRP's menus")
            if (kpm_folder / "kmrp.kpatch").exists():
                failures.append(f"{case}: uninstall left kmrp.kpatch")
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
