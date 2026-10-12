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
3. The player's override comes first (2026-10-12, as Windows' 1.5.1): a file the game's override
   folder has is left out of both folders the game is given, KMRP's own files as well as the
   bundled art; a texture counts as a .tga or a .tpc and takes KMRP's .txi with it; the cache
   keeps the set whole.
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

        # 3. The player's override comes first (2026-10-12, as Windows' 1.5.1): a file there is
        #    left out of both folders the game is given, KMRP's own as well as the bundled art.
        #    A texture counts in either format and takes KMRP's .tga, .tpc and .txi of its name;
        #    a layout takes the set's; nothing else goes missing, and the cache keeps the set
        #    whole.
        bundled = [line.strip() for line in (source / "bundled-override.txt").read_text().splitlines() if line.strip()]
        lower_bundled = {b.lower() for b in bundled}
        clean = prepare(*SIZES[0])
        made = {}
        if clean:
            art_before = {p.name.lower() for p in Path(clean["art"]).iterdir()}
            set_before = {p.name.lower() for p in Path(clean["set"]).iterdir()}
            same, other = bundled[0], bundled[1]
            other_kind = Path(other).with_suffix(".tga" if other.lower().endswith(".tpc") else ".tpc").name
            own = next(n for n in sorted(art_before) if n not in lower_bundled and n.endswith((".tga", ".tpc")))
            layout = next(n for n in sorted(set_before) if n.endswith(".gui"))
            font = next(n for n in sorted(set_before) if n.endswith(".txi") and (n[:-4] + ".tga") in set_before)
            font_texture = font[:-4] + ".tpc"       # the other format than the set's .tga
            for name in (same, other_kind, own, layout, font_texture):
                (assets / "override" / name).write_bytes(b"the player's")
            made = prepare(*SIZES[0])
        if made:
            art_after = {p.name.lower() for p in Path(made["art"]).iterdir()}
            set_after = {p.name.lower() for p in Path(made["set"]).iterdir()}
            stem = lambda n: n.rsplit(".", 1)[0]
            gone_art = {n for n in art_before if n in (same.lower(), own) or
                        (stem(n) in (stem(other.lower()), stem(own)) and n.endswith((".tga", ".tpc", ".txi")))}
            gone_set = {layout} | {n for n in set_before if stem(n) == stem(font) and n.endswith((".tga", ".tpc", ".txi"))}
            if art_before - art_after != gone_art:
                failures.append(f"override first, artwork: left out {sorted(art_before - art_after)[:6]}, "
                                f"expected {sorted(gone_art)[:6]}")
            if set_before - set_after != gone_set:
                failures.append(f"override first, set: left out {sorted(set_before - set_after)[:6]}, "
                                f"expected {sorted(gone_set)[:6]}")
            if art_after - art_before or set_after - set_before:
                failures.append("override first: files appeared that were not there before")
            whole = Path(made["set"]).parent / "sets" / f"{SIZES[0][0]}x{SIZES[0][1]}"
            if not (whole / layout).is_file() or not (whole / font).is_file():
                failures.append("override first: the set in the cache lost the files left to the override")
            print(f"     override first: {len(gone_art)} of the artwork and {len(gone_set)} of the set left to the "
                  f"player's files ({own}, {layout}, {font} with its texture, two of the bundled art)")
            for name in (same, other_kind, own, layout, font_texture):
                (assets / "override" / name).unlink()

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
