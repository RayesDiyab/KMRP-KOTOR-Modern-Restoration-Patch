#!/usr/bin/env python3
"""Check what the Mac module unpacks for the game against what the installer used to install.

Since 2026-10-04 kmrp.dylib carries every resolution's menu set and KMRP's artwork
(macos/tools/make_kmrp_assets.py packs them; macos/patches/kmrp-assets/assets.cpp unpacks them
to ~/Library/Caches/KMRP and registers the cache with the game). Until then KMRP Installer wrote
the same files into the game's override folder. This builds the part with a small driver, with
the bank linked in as the module links it, runs it without a game, and checks:

1. For a size the build has a set for and one it has none for: the files the game is given (this
   run's artwork folder, then the size's set, which is searched first) are, name for name and
   byte for byte, what the installer's procedure makes for that size: the artwork, the set (the
   nearest by height, then shape, with kmrp-guiblend's files over it for a size without one),
   what kmrp-gameart makes from the game, and kmrp-abilityicons' icons.
2. A second run for the same size rewrites nothing.
3. Bundled third-party art is left out of the artwork folder when the game's override folder
   already has that texture, as a .tga or as a .tpc, and KMRP's own files are not.
4. The part's load-time initialisers are exactly its two constructors (UseKmrpIni in
   layouts_ini.cpp, WatchFrames in layout.cpp): a C++ global needing construction would be
   another, run in an order nothing can rely on.

    python testing/regression/Test-MacAssets.py ASSETS_SOURCE_DIR BANK SWPC_TEX_GUI_ERF

ASSETS_SOURCE_DIR is build/macos/assets-src (override/, bundled-override.txt, layouts.zip,
gui-blend.bin), BANK build/macos/assets/kmrp-assets.bin, both made by
macos/build.sh. The texture pack, chitin.key and data/ beside it are only read.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PART = ROOT / "macos/patches/kmrp-assets"
TOOLS = ROOT / "macos/tools"
# A set the module rebuilds in part (the bank holds what the blend makes differently); one it
# rebuilds whole; one outside the blend, stored whole; and a size with no set, blended from the
# nearest. Since 2026-10-08 the bank leaves out what the module's blend helper writes exactly.
SIZES = ((1512, 982), (1920, 1080), (1280, 1080), (1800, 1169))

DRIVER = r"""
#include "assets.h"
#include <cstdio>
#include <cstdlib>
int g_targetWidth, g_targetHeight;
void InitTargetResolution() {}
namespace kmrp { FILE* (*g_iniOpen)(const char*, const char*) = nullptr; }
int main(int argc, char** argv) {
    std::string art, set;
    const bool ok = kmrp::assets::Prepare(atoi(argv[1]), atoi(argv[2]), &art, &set);
    printf("art\t%s\nset\t%s\n", art.c_str(), set.c_str());
    return ok ? 0 : 1;
}
"""


def run(*command: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, capture_output=True, text=True, **kwargs)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(source: Path, tools: Path, assets: Path, out: Path, width: int, height: int) -> tuple[dict[str, str], str]:
    """The override folder kmrp-mac.sh made for a size until 2026-10-04, as name -> SHA-256."""
    files: dict[str, str] = {p.name: digest(p) for p in (source / "override").iterdir() if p.is_file()}
    with zipfile.ZipFile(source / "layouts.zip") as layouts:
        sizes = [n[len("index/"):-len(".txt")] for n in layouts.namelist() if n.startswith("index/")]
        size = f"{width}x{height}"
        if size in sizes:
            chosen = size
        else:
            def distance(candidate: str) -> tuple[int, float]:
                w, h = map(int, candidate.split("x"))
                return abs(h - height), abs(w / h - width / height)
            chosen = min(sizes, key=distance)
        set_dir = out / "set"
        set_dir.mkdir(parents=True)
        for line in layouts.read(f"index/{chosen}.txt").decode().replace("\r", "").splitlines():
            if line:
                name, obj = line.split("\t")
                (set_dir / name).write_bytes(layouts.read(f"objects/{obj}"))
    if chosen != size:
        run(str(tools / "kmrp-guiblend"), str(source / "gui-blend.bin"), str(width), str(height),
            str(out / "blend"), str(set_dir))
        for made in (out / "blend").iterdir():
            shutil.copy2(made, set_dir / made.name)
    reserved = out / "reserved.txt"
    reserved.write_text("".join(f"{name}\n" for name in [*files, *(p.name for p in set_dir.iterdir())]))
    files.update({p.name: digest(p) for p in set_dir.iterdir()})
    pack = assets / "TexturePacks/swpc_tex_gui.erf"
    run(str(tools / "kmrp-gameart"), str(pack), str(assets / "chitin.key"), str(height), str(out / "gameart"))
    files.update({p.name: digest(p) for p in (out / "gameart").iterdir()})
    run(str(tools / "kmrp-abilityicons"), str(pack), str(height), str(out / "icons"), str(reserved))
    files.update({p.name: digest(p) for p in (out / "icons").glob("*.tga")})
    return files, chosen


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    source, bank, erf = (Path(a).resolve() for a in sys.argv[1:])
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="kmrp-assets-test-") as tmp:
        tmp = Path(tmp)
        tools = tmp / "tools"
        tools.mkdir()
        for name in ("kmrp-guiblend", "kmrp-abilityicons", "kmrp-gameart"):
            run("clang", "-O2", "-w", "-o", str(tools / name), str(TOOLS / f"{name}.c"))
        # The stand-in game: the driver where KOTOR_Exe is, the game's assets beside it.
        contents = tmp / "Game.app/Contents"
        assets = contents / "Assets"
        (contents / "MacOS").mkdir(parents=True)
        (assets / "TexturePacks").mkdir(parents=True)
        (assets / "TexturePacks/swpc_tex_gui.erf").symlink_to(erf)
        (assets / "chitin.key").symlink_to(erf.parent.parent / "chitin.key")
        (assets / "data").symlink_to(erf.parent.parent / "data")
        (assets / "override").mkdir()
        objects = tmp / "objects"
        objects.mkdir()
        (tmp / "driver.cpp").write_text(DRIVER)
        for name, define in (("kmrp-guiblend", "-DKMRP_GUI_EMBEDDED"), ("kmrp-abilityicons", "-DKMRP_EMBEDDED"),
                             ("kmrp-gameart", "-DKMRP_EMBEDDED")):
            run("clang", "-arch", "x86_64", "-std=c11", "-O2", "-w", define, "-c", str(TOOLS / f"{name}.c"),
                "-o", str(objects / f"{name}.o"))
        driver = contents / "MacOS/driver"
        part = [str(PART / "assets.cpp"), str(PART / "widescreen.cpp"), str(ROOT / "macos/patches/kmrp-layout/options.cpp")]
        run("clang++", "-arch", "x86_64", "-std=c++17", "-O2", "-w", "-I", str(PART), str(tmp / "driver.cpp"), *part,
            *(str(p) for p in sorted(objects.glob("*.o"))), "-lz", f"-Wl,-sectcreate,__KMRP,__assets,{bank}",
            "-o", str(driver))
        home = tmp / "home"
        home.mkdir()
        env = dict(os.environ, HOME=str(home))

        def prepare(width: int, height: int) -> dict[str, str]:
            result = subprocess.run([str(driver), str(width), str(height)], env=env, capture_output=True, text=True)
            if result.returncode != 0:
                failures.append(f"{width}x{height}: the part could not prepare it: {result.stderr.strip()[-300:]}")
                return {}
            return dict(line.split("\t", 1) for line in result.stdout.splitlines() if line.count("\t") == 1)

        # KMRP_ALL_SETS=1 in the environment: every set the build has, which takes some minutes.
        sizes = SIZES
        if os.environ.get("KMRP_ALL_SETS"):
            with zipfile.ZipFile(source / "layouts.zip") as layouts:
                sizes = tuple(sorted(tuple(map(int, n[len("index/"):-len(".txt")].split("x")))
                                     for n in layouts.namelist() if n.startswith("index/") and n.endswith(".txt")))
        for width, height in sizes:
            size = f"{width}x{height}"
            made = prepare(width, height)
            if not made:
                continue
            art, set_dir = Path(made["art"]), Path(made["set"])
            got = {p.name: digest(p) for p in art.iterdir()}
            got.update({p.name: digest(p) for p in set_dir.iterdir()})   # the set is searched first
            want, chosen = reference(source, tools, assets, tmp / f"reference-{size}", width, height)
            missing, extra = sorted(set(want) - set(got)), sorted(set(got) - set(want))
            different = sorted(n for n in want if n in got and want[n] != got[n])
            if missing or extra or different:
                failures.append(f"{size}: missing {missing[:5]}, not the installer's {extra[:5]}, different {different[:5]} "
                                f"({len(missing)}, {len(extra)}, {len(different)})")
            # 2. A second run leaves the set as it is.
            before = {p.name: p.stat().st_mtime_ns for p in set_dir.iterdir()}
            again = prepare(width, height)
            if again and {p.name: p.stat().st_mtime_ns for p in Path(again["set"]).iterdir()} != before:
                failures.append(f"{size}: a second run rewrote the set")
            print(f"     {size}: {len(got)} files, as the installer made them (set from {chosen})")

        # 3. Bundled art yields to the player's own texture of that name, of either kind.
        bundled = [line.strip() for line in (source / "bundled-override.txt").read_text().splitlines() if line.strip()]
        own = next(p.name for p in (source / "override").iterdir() if p.name.lower() not in {b.lower() for b in bundled})
        same, other = bundled[0], bundled[1]
        other_kind = Path(other).with_suffix(".tga" if other.lower().endswith(".tpc") else ".tpc").name
        for name in (same, other_kind, own):
            (assets / "override" / name).write_bytes(b"the player's")
        made = prepare(*SIZES[0])
        if made:
            linked = {p.name.lower() for p in Path(made["art"]).iterdir()}
            if same.lower() in linked or other.lower() in linked:
                failures.append("bundled art was given to the game over the player's own texture")
            if own.lower() not in linked:
                failures.append("KMRP's own file was left out because the player's override has one of that name")
            if len(linked) != len(list((source / "override").iterdir())) - 2:
                failures.append("more than the two shadowed files are missing from the artwork folder")

        # 4. Two load-time initialisers, the part's own constructors.
        check = tmp / "part.dylib"
        run("clang++", "-arch", "x86_64", "-std=c++17", "-O2", "-w", "-dynamiclib", "-undefined", "dynamic_lookup",
            "-I", str(PART), *(str(p) for p in sorted(PART.glob("*.cpp"))), "-o", str(check))
        sections = subprocess.run(["otool", "-l", str(check)], capture_output=True, text=True).stdout
        count = 0
        for block in sections.split("Section")[1:]:
            if "sectname __mod_init_func" in block or "sectname __init_offsets" in block:
                size_hex = block.split("size ")[1].split()[0]
                count += int(size_hex, 16) // (8 if "__mod_init_func" in block else 4)
        if count != 2:
            failures.append(f"the part has {count} load-time initialisers, not its two constructors")

    for failure in failures:
        print(f"  {failure}")
    print(f"{'FAIL' if failures else 'ok  '} the module's menu sets and artwork, against the installer's own procedure: "
          f"{len(failures)} problems")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
