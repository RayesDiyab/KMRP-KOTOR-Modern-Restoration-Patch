#!/usr/bin/env python3
"""The installer's preparation of KMRP's art, as the installer does it (2026-10-19).

KMRP's installer makes the art of every size the display offers before the game first
starts: worker copies of itself load the module with KMRP_PREPARE in their environment,
so its DllMain leaves the process alone, and call its export KmrpPrepareAssets with the
game's folder and a share of the work (ArtPreparation, src/patcher/KpmEdition.cs;
KmrpRuntimeAssetsPrepare, src/controller-native/K1RuntimeAssets.cpp). This runs the same
calls from testing/regression/asset_prepare_harness.cpp, an x86 program as the installer
is (Test-AssetPack.cmd builds it), with %LOCALAPPDATA% pointed at a folder of its own,
on a stand-in game folder (a swkotor.ini; no texture pack, so the icons and art KMRP
makes from the player's own game are left out, which is not an error). It checks:

  1. one worker makes the common files and every size of this PC's display that KMRP
     covers, each set marked complete, and lets go of the pack when it is done;
  2. a set of a listed size holds every file its group in the pack names, each with the
     index's SHA-256;
  3. a second run finds everything made, and makes nothing;
  4. three workers side by side make the same sets as one, the common files once;
  5. without the pack the module makes nothing and says why in kmrp-kpm.log;
  6. a pack cut short, one with its header or its identity damaged: the same, and no crash;
  7. a byte wrong in a pack's stored data: no set is marked complete with wrong files;
  8. a set a stopped run left without its marker, and one whose file went missing under its
     marker: the next run makes them again;
  9. a cache folder that cannot be made: nothing is made, and no crash;
 10. a game whose files the art helpers cannot read: the set is used, not sealed, the next two
     runs try again, and the third seals it.

It starts no game. Windows only (the module is Windows'). It takes about two minutes on
the maintainer's PC.

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import kmrp_pack  # noqa: E402

MODULE = ROOT / "build/native-runtime/kmrp-native.dll"
PACK = ROOT / "build/native-runtime/kmrp-assets.pack"
HARNESS = ROOT / "build/asset-pack-test/asset-prepare-check.exe"
failures = []


def check(condition: bool, text: str) -> None:
    print(("ok    " if condition else "FAIL  ") + text)
    if not condition:
        failures.append(text)


def run(module: Path, game: Path, local: Path, share: int = 0, shares: int = 1) -> subprocess.Popen:
    environment = dict(os.environ, LOCALAPPDATA=str(local))
    return subprocess.Popen([str(HARNESS), str(module), str(game), str(share), str(shares)], env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)


def finish(process: subprocess.Popen) -> tuple[int, int]:
    """(exit code, sizes made) of a harness run."""
    out, _ = process.communicate()
    made = -1
    for line in out.splitlines():
        if line.startswith("sizes made: "):
            made = int(line.split()[2])
    return process.returncode, made


def cache_state(local: Path):
    """(the build folders, the common files made, the sets made) of a cache."""
    cache = local / "KMRP" / "cache"
    builds = [p for p in cache.iterdir() if p.is_dir()] if cache.exists() else []
    if len(builds) != 1:
        return builds, False, set()
    sets = {p.name[:-len(".complete")] for p in (builds[0] / "sets").glob("*.complete")}
    return builds, (builds[0] / "store.complete").exists(), sets


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    for needed in (MODULE, PACK):
        if not needed.exists():
            raise SystemExit(f"{needed} is missing: run src/controller-native/build_native_runtime.cmd first")
    subprocess.run(["cmd.exe", "/c", str(ROOT / "testing/regression/Test-AssetPack.cmd")], check=True,
                   stdout=subprocess.DEVNULL)
    identity, groups, objects, _, _, _ = kmrp_pack.read_pack(PACK)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        game = tmp / "game"
        game.mkdir()
        (game / "swkotor.ini").write_text("[Graphics Options]\nFullScreen=1\nWidth=1920\nHeight=1080\n")

        # 1. One worker.
        local = tmp / "one"
        local.mkdir()
        started = time.time()
        code, made = finish(run(MODULE, game, local))
        seconds = time.time() - started
        builds, common, sets = cache_state(local)
        check(code == 0 and made >= 1, f"one worker makes {made} sizes in {seconds:.0f} s and lets go of the pack")
        check(len(builds) == 1 and builds[0].name == identity[:16] and common and len(sets) == made,
              f"the cache is the pack's build's ({identity[:16]}), with the common files and {len(sets)} sets marked complete")

        # 2. A listed size's set against the pack's index.
        listed = {f"{w}x{h}": entries for (w, h), entries in groups if w}
        sample = next((s for s in ("1920x1080", "2560x1440", "1280x720") if s in sets and s in listed),
                      next((s for s in sets if s in listed), None))
        if sample:
            folder = builds[0] / "sets" / sample
            wrong = [name for name, key in listed[sample]
                     if not (folder / name).exists() or hashlib.sha256((folder / name).read_bytes()).digest() != key]
            check(not wrong, f"the {sample} set holds all {len(listed[sample])} files its group names, each with "
                             f"the index's SHA-256" + (f": NOT {wrong[:5]}" if wrong else ""))
        else:
            check(False, "a listed size among the sizes made")

        # 3. Again: everything is there.
        started = time.time()
        code, again = finish(run(MODULE, game, local))
        seconds = time.time() - started
        check(code == 0 and again == made and seconds < 15 and cache_state(local)[2] == sets,
              f"a second run finds the {again} sizes made, in {seconds:.1f} s")

        # 4. Three workers side by side.
        local3 = tmp / "three"
        local3.mkdir()
        started = time.time()
        results = [finish(p) for p in [run(MODULE, game, local3, i, 3) for i in range(3)]]
        seconds = time.time() - started
        builds3, common3, sets3 = cache_state(local3)
        check(all(code == 0 for code, _ in results) and sum(m for _, m in results) == made and common3 and sets3 == sets,
              f"three workers make the same {len(sets3)} sets and the common files once, in {seconds:.0f} s")

        # 5. No pack: a module alone, as KOTOR Patch Manager installs it without the installer.
        lone = tmp / "lone"
        lone.mkdir()
        shutil.copy2(MODULE, lone / "kmrp.dll")
        local5 = tmp / "none"
        local5.mkdir()
        code, none = finish(run(lone / "kmrp.dll", game, local5))
        # KMRP's logs are in KMRP\logs since 2026-10-20 (KmrpLogPath, KmrpOptions.h); this
        # read the game folder's root until 2026-10-30 and failed from the move on.
        path = game / "KMRP" / "logs" / "kmrp-kpm.log"
        log = path.read_text(errors="replace") if path.exists() else ""
        check(code != 0 and none == -1 and "kmrp-assets.pack is not in the patches folder" in log,
              "without the pack nothing is made, and kmrp-kpm.log says the pack is missing")

        # 6. A damaged pack: nothing is made, the log says so, the process lives (audit TST).
        def with_pack(name, change):
            folder = tmp / name
            folder.mkdir()
            shutil.copy2(MODULE, folder / "kmrp.dll")
            bytes_ = bytearray(PACK.read_bytes())
            change(bytes_)
            (folder / "kmrp-assets.pack").write_bytes(bytes_)
            cache = tmp / (name + "-cache")
            cache.mkdir()
            if path.exists():
                path.unlink()
            code, count = finish(run(folder / "kmrp.dll", game, cache))
            text = path.read_text(errors="replace") if path.exists() else ""
            return code, count, text, cache

        def cut(pack):
            del pack[len(pack) // 2:]

        def first_byte(pack):
            pack[0] ^= 0xFF

        def identity_byte(pack):
            pack[20] ^= 0xFF

        for name, change, says in (("cut", cut, "cannot be read"), ("header", first_byte, "cannot be read"),
                                   ("identity", identity_byte, "kmrp-assets.pack")):
            code, count, text, _ = with_pack(name, change)
            check(code != 0 and count == -1 and says in text and code & 0xC0000000 != 0xC0000000,
                  f"a pack damaged ({name}): nothing is made, the log says so, no crash (exit {code:#x}, made {count})")

        # 7. A byte wrong in the stored data, a third of the way through every block's bytes.
        def stored_byte(pack):
            for at in range(len(pack) // 2, len(pack), 4 << 20):
                pack[at] ^= 0xFF

        code, count, text, cache = with_pack("stored", stored_byte)
        crashed = code & 0xC0000000 == 0xC0000000
        check(not crashed, f"wrong bytes in the stored data do not crash it (exit {code:#x}, made {count})")
        builds7, _, sets7 = cache_state(cache)
        wrong = []
        for size in sets7:
            for name, key in dict(listed).get(size, []):
                file = builds7[0] / "sets" / size / name
                if file.exists() and hashlib.sha256(file.read_bytes()).digest() != key:
                    wrong.append(f"{size}/{name}")
        check(not wrong, f"no set marked complete holds a wrong file ({len(sets7)} sets marked)" +
              (f": NOT {wrong[:5]}" if wrong else ""))

        # 8. A stopped run, and a file gone from a set that says it is complete.
        target = builds[0] / "sets" / sample
        marker = target.parent / (sample + ".complete")
        check(marker.exists(), f"the {sample} set has its marker beside it")
        marker.unlink()
        one = next(file for file in target.iterdir() if file.is_file())
        one.unlink()
        code, again = finish(run(MODULE, game, local))
        check(code == 0 and again == made and marker.exists() and one.exists(),
              "a set without its marker is made again")
        one.unlink()
        code, again = finish(run(MODULE, game, local))
        check(code == 0 and one.exists(), "a file gone from a set with its marker is made again")

        # 9. No cache folder can be made: %LOCALAPPDATA% is a file.
        blocked = tmp / "blocked"
        blocked.write_text("not a folder")
        code, count = finish(run(MODULE, game, blocked))
        check(code != 0 and count == -1 and code & 0xC0000000 != 0xC0000000,
              f"a cache that cannot be made: nothing is made, no crash (exit {code:#x}, made {count})")

        # 10. Art helpers that fail on files that are there.
        broken = tmp / "broken-game"
        (broken / "TexturePacks").mkdir(parents=True)
        (broken / "swkotor.ini").write_text("[Graphics Options]\nWidth=1920\nHeight=1080\n")
        (broken / "TexturePacks" / "swpc_tex_gui.erf").write_bytes(b"not a texture pack")
        (broken / "chitin.key").write_bytes(b"not a key")
        local10 = tmp / "broken"
        local10.mkdir()
        code, first = finish(run(MODULE, broken, local10))
        check(code == 0 and first >= 1, f"helpers that fail do not stop the sets ({first} made)")
        sealed = [len(cache_state(local10)[2])]
        finish(run(MODULE, broken, local10))
        sealed.append(len(cache_state(local10)[2]))
        finish(run(MODULE, broken, local10))
        sealed.append(len(cache_state(local10)[2]))
        check(sealed[0] == 0 and sealed[1] == 0 and sealed[2] == first,
              f"not sealed at the first two runs, sealed at the third (sets marked: {sealed})")
    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
