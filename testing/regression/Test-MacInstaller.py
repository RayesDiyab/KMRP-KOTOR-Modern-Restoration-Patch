#!/usr/bin/env python3
"""Install, check and uninstall the macOS package into a stand-in game, twice.

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
2. A size the build has no set for (--size 1800x1169): the .gui files are kmrp-guiblend's
   for that size, everything else is the nearest listed set's (by height, then shape); then
   the same clean uninstall.
3. The listed size again, over the settings round 2 left behind.

The controller's kmrp-controller.ini (beside swkotor.ini, since 2026-09-29), the player's file
as on Windows: round 1 has none, so install writes the defaults and uninstall removes them;
in round 2 the player edits it after installing, and uninstall keeps it and still finishes;
round 3 installs over that edited copy, which install and uninstall leave byte for byte.

    python testing/regression/Test-MacInstaller.py PACKAGE_KMRP_DIR CLEAN_KOTOR_EXE SWPC_TEX_GUI_ERF

PACKAGE_KMRP_DIR is dist/macos/KMRP-macOS-<version>/KMRP Installer.app/Contents/Resources/kmrp from
macos/build.sh.
"""
from __future__ import annotations

import hashlib
import os
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
        for size, listed, mode in (("3024x1964", True, "fresh"), ("1800x1169", False, "edit"),
                                   ("3024x1964", True, "kept")):
            width, height = (int(v) for v in size.split("x"))
            ini.write_bytes(INI_BEFORE.encode())
            if mode == "kept":
                player_settings = settings.read_bytes() if settings.is_file() else b""
            result = run("install", "--size", size, "--yes")
            if result.returncode != 0:
                failures.append(f"{size}: install failed: {result.stderr.strip()[-300:]}")
                continue
            # The controller's settings: Windows' defaults when there are none, else the player's.
            if mode == "kept":
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
            # Engine.
            for name in ("KotorPatcher.dylib", "patch_config.toml", "patches/k1widescreenpatch.dylib",
                         "patches/kmrp-layout.dylib", "patches/kmrp-map-notes.dylib",
                         "patches/kmrp-controller.dylib", "patches/kmrp-sdl3.dylib"):
                if not (game / "Contents/MacOS" / name).is_file():
                    failures.append(f"{size}: {name} not installed")
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
                for gui in blend.glob("*.gui"):
                    expected[gui.name] = gui.read_bytes()
            for name, data in expected.items():
                path = override / name
                if not path.is_file() or path.read_bytes() != data:
                    failures.append(f"{size}: override/{name} is not the {'blended' if name.endswith('.gui') and not listed else source} file")
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
            # The eight skill icons, 32 px in the pack, at round(32s), at most 64; both sizes
            # here are past 720, so all eight must be there.
            height = int(size.split("x")[1])
            want = min(round(32 * height / 720), 64)
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
            # Uninstall.
            result = run("uninstall", "--yes")
            if result.returncode != 0:
                failures.append(f"{size}: uninstall failed: {result.stderr.strip()[-300:]}")
            if mode == "fresh" and settings.exists():
                failures.append(f"{size}: uninstall left the unchanged default kmrp-controller.ini")
            if mode == "edit" and ("Strength=40" not in (settings.read_text() if settings.is_file() else "")
                                   or "Kept your edited kmrp-controller.ini" not in result.stdout):
                failures.append(f"{size}: uninstall did not keep the edited kmrp-controller.ini")
            if mode == "kept" and (not settings.is_file() or settings.read_bytes() != player_settings):
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
            print(f"     {size}: {'listed set' if listed else f'blended, fonts and art from {source}'}, "
                  f"{len(expected)} set files, {len(icons)} feat and power icons, {len(skills)} skill icons, "
                  f"{len(art) + 1} made from the game; controller settings {mode}")

    for failure in failures:
        print("  " + failure)
    print(f"{'FAIL' if failures else 'ok  '} install, status and uninstall into a stand-in game, listed and "
          f"blended sizes, controller settings: {len(failures)} problems")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
