#!/usr/bin/env python3
"""Make the files the Mac's controller patch embeds, and pack them into its bank.

The controller patch (macos/patches/kmrp-controller, "KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch") runs on a game
without KMRP, on the layouts the game ships, so it carries its own: the game's layout files
with the controller's cues added, the Controller Layout screen, the badge and cue art of the
four controller families, the Xbox-style HUD's art and SDL. They are made by the same steps
Windows' patch uses, tools/build_controller_assets.py's make(), run here on the Mac game's own
files; only the packing differs, since that tool's bank is compressed with a Windows API.

Inputs, game-derived and never committed (build-inputs/README.md):

    build-inputs/vanilla-gui/*.gui   written by --extract from the game's chitin.key
    build-inputs/swpc_tex_gui.erf    the game's texture pack, for its font metrics (--erf
                                     copies it there when it is missing)

The bank, little endian, zlib throughout:

    "KMCAS001"
    32 bytes   SHA-256 of everything after this field: the build's identity, which names the cache
    u32        files
    per file   u16 name length, name (ASCII, no path), 32-byte SHA-256, u32 size, u32 stored
               size, the file compressed

    python macos/tools/make_controller_assets.py --extract GAME_ASSETS_DIR
    python macos/tools/make_controller_assets.py --sdl FILE --out BANK [--files DIR] [--erf FILE]

--files also leaves the files loose in DIR, for inspection and tests.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

MAGIC = b"KMCAS001"
SDL_NAME = "kmrp-sdl3.dylib"


def fail(message: str) -> None:
    raise SystemExit(f"make_controller_assets: {message}")


def pack(files: dict[str, Path], out: Path) -> tuple[int, str]:
    body = bytearray(struct.pack("<I", len(files)))
    for name in sorted(files):
        encoded = name.encode("ascii")
        if not encoded or len(encoded) > 255 or "/" in name or "\\" in name or ".." in name:
            fail(f"unsafe file name {name!r}")
        data = files[name].read_bytes()
        stored = zlib.compress(data, 9)
        body += struct.pack("<H", len(encoded)) + encoded + hashlib.sha256(data).digest()
        body += struct.pack("<II", len(data), len(stored)) + stored
    identity = hashlib.sha256(body).digest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(MAGIC + identity + body)
    return len(files), identity.hex()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--extract", type=Path, metavar="GAME_ASSETS",
                        help="write the game's layout files to build-inputs/vanilla-gui and stop")
    parser.add_argument("--erf", type=Path, help="the game's TexturePacks/swpc_tex_gui.erf")
    parser.add_argument("--sdl", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--files", type=Path)
    args = parser.parse_args()
    logging.disable(logging.DEBUG)   # pykotor and PIL narrate every struct and chunk
    import build_controller_assets as shared

    if args.extract:
        print(f"{shared.extract(args.extract)} layout files written to {shared.VANILLA_GUI}")
        return 0
    if not (args.sdl and args.out):
        fail("--sdl and --out are needed")
    if not args.sdl.is_file():
        fail(f"no SDL at {args.sdl}")
    if not shared.TEXTURE_PACK.is_file():
        if not (args.erf and args.erf.is_file()):
            fail(f"{shared.TEXTURE_PACK} is missing: pass --erf with the game's swpc_tex_gui.erf")
        shutil.copyfile(args.erf, shared.TEXTURE_PACK)
    if not any(shared.VANILLA_GUI.glob("*.gui")):
        fail(f"{shared.VANILLA_GUI} is empty: run --extract with the game's Assets folder first")
    with tempfile.TemporaryDirectory(prefix="kmrp-controller-assets-") as temp:
        files = dict(shared.make(Path(temp)))
        if SDL_NAME in files:
            fail(f"the shared steps already made a file called {SDL_NAME}")
        files[SDL_NAME] = args.sdl
        count, identity = pack(files, args.out)
        if args.files:
            shutil.rmtree(args.files, ignore_errors=True)
            args.files.mkdir(parents=True)
            for name, path in files.items():
                shutil.copyfile(path, args.files / name)
    kinds: dict[str, int] = {}
    for name in files:
        kinds[name.rsplit(".", 1)[-1]] = kinds.get(name.rsplit(".", 1)[-1], 0) + 1
    print(f"{args.out.name}: {count} files {kinds}, {args.out.stat().st_size} bytes, build {identity[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
