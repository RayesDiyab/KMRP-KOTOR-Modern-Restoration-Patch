#!/usr/bin/env python3
"""Check that both installers make the same files from the player's game.

Since 2026-09-29 neither release ships the files KMRP makes from the game's own art and
data. The installers make them at install instead: src/patcher/GameArtGenerator.cs on
Windows, macos/tools/kmrp-gameart.c on the Mac. They are the four hex row frames
(lbl_hex*), the tutorial popup's thirteen tut_* icons and tutorial.2da. This builds both
(the C# source itself, in a small .NET driver; the helper for x86_64 and arm64) and
requires:

1. the same files, byte for byte, at every set height of RESOURCES_DIR and at a few
   heights no set has;
2. the same bytes as an independent Python reference at a subset of those heights: the
   standard DXT5 formulas, and the build's own resize_rgba, nearest_rgba and write_tga,
   and pykotor for tutorial.2da;
3. the texture sizes each set shipped before 2026-09-29, where RESOURCES_DIR still holds
   them (a build from before that date);
4. tutorial.2da differing from the game's own table in the icon column only, each cell
   renamed as export_tutorial_icons.ICON_RENAMES says.

It also reports how far the textures differ from the ones the build shipped (the build
decoded DXT5 with pykotor, whose eight-level alpha is off by one code).

    python testing/regression/Test-GameArt.py GAME_DIR [RESOURCES_DIR]

GAME_DIR holds chitin.key, data/ and TexturePacks/swpc_tex_gui.erf (the Mac build's
Contents/Assets, or the Windows game folder). Needs clang and the .NET 8 SDK.
"""
from __future__ import annotations

import io
import os
import re
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build_scaled_fonts import write_tga  # noqa: E402
from export_tutorial_icons import ICON_RENAMES, nearest_rgba  # noqa: E402
from scale_row_icon_frames import FRAME_RESREFS, resize_rgba  # noqa: E402

HELPER = ROOT / "macos" / "tools" / "kmrp-gameart.c"
SOURCES = [ROOT / "src" / "patcher" / "GameArtGenerator.cs", ROOT / "src" / "patcher" / "AbilityIconGenerator.cs"]
EXTRA_HEIGHTS = [600, 720, 878, 1169, 4320]      # below the scale floor, and sizes no set has
REFERENCE_HEIGHTS = [720, 982, 1080, 1440, 1964]  # pure Python is slow; these cover both code paths

DRIVER = r"""
using System;
using System.Collections.Generic;
using System.IO;
namespace Kmrp {
static class Driver {
    // Driver EXECUTABLE OUTROOT HEIGHT...: GameArtGenerator.Build for each height into OUTROOT/HEIGHT.
    static int Main(string[] args) {
        for (int i = 2; i < args.Length; i++) {
            int height = int.Parse(args[i]);
            List<KeyValuePair<string, byte[]>> files = GameArtGenerator.Build(args[0], height);
            if (files == null) { Console.Error.WriteLine("Build returned null at " + height); return 3; }
            string dir = Path.Combine(args[1], args[i]);
            Directory.CreateDirectory(dir);
            foreach (KeyValuePair<string, byte[]> file in files) File.WriteAllBytes(Path.Combine(dir, file.Key), file.Value);
            using (MemoryStream zip = GameArtGenerator.TryBuild(args[0], height, null))
                if (zip == null) { Console.Error.WriteLine("TryBuild returned null at " + height); return 4; }
        }
        return 0;
    }
}
}
"""

PROJECT = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework>
  <Nullable>disable</Nullable><ImplicitUsings>disable</ImplicitUsings><RollForward>Major</RollForward></PropertyGroup>
  <ItemGroup>{compile}</ItemGroup>
</Project>
"""


# ------------------------------------------------------------------ the Python reference

def erf_tpc(pack: bytes, resref: str) -> bytes:
    entries, keys, resources = (struct.unpack_from("<I", pack, o)[0] for o in (16, 24, 28))
    for i in range(entries):
        k, r = keys + 24 * i, resources + 8 * i
        if struct.unpack_from("<H", pack, k + 20)[0] != 3007:
            continue
        if pack[k:k + 16].split(b"\0")[0].decode().lower() == resref:
            offset, size = struct.unpack_from("<ii", pack, r)
            return pack[offset:offset + size]
    raise KeyError(resref)


def decode_tpc(tpc: bytes) -> tuple[int, int, bytes]:
    """Top mip as RGBA in stored (bottom-up) order: the standard DXT5 formulas."""
    data_size, _, width, height, encoding = struct.unpack_from("<IfHHB", tpc, 0)
    body = tpc[128:]
    if data_size == 0:
        channels = {2: 3, 4: 4}[encoding]
        out = bytearray()
        for i in range(width * height):
            px = body[i * channels:(i + 1) * channels]
            out += px if channels == 4 else px + b"\xff"
        return width, height, bytes(out)
    assert encoding == 4
    out = bytearray(width * height * 4)
    bw = (width + 3) // 4
    for block in range(bw * ((height + 3) // 4)):
        b = body[block * 16:(block + 1) * 16]
        a = [b[0], b[1]]
        if a[0] > a[1]:
            a += [((8 - i) * a[0] + (i - 1) * a[1]) // 7 for i in range(2, 8)]
        else:
            a += [((6 - i) * a[0] + (i - 1) * a[1]) // 5 for i in range(2, 6)] + [0, 255]
        abits = int.from_bytes(b[2:8], "little")

        def c565(v):
            r, g, bl = (v >> 11) & 31, (v >> 5) & 63, v & 31
            return [(r << 3) | (r >> 2), (g << 2) | (g >> 4), (bl << 3) | (bl >> 2)]
        c0, c1 = c565(int.from_bytes(b[8:10], "little")), c565(int.from_bytes(b[10:12], "little"))
        colors = [c0, c1, [(2 * x + y) // 3 for x, y in zip(c0, c1)], [(x + 2 * y) // 3 for x, y in zip(c0, c1)]]
        cbits = int.from_bytes(b[12:16], "little")
        left, top = (block % bw) * 4, (block // bw) * 4
        for t in range(16):
            x, y = left + t % 4, top + t // 4
            if x < width and y < height:
                o = (y * width + x) * 4
                out[o:o + 3] = bytes(colors[(cbits >> (2 * t)) & 3])
                out[o + 3] = a[(abits >> (3 * t)) & 7]
    return width, height, bytes(out)


def flip(pixels: bytes, width: int, height: int) -> bytes:
    stride = width * 4
    return b"".join(pixels[y * stride:(y + 1) * stride] for y in range(height - 1, -1, -1))


def reference_textures(pack: bytes, height: int) -> dict[str, bytes]:
    scale = max(1.0, height / 720.0)
    files = {}
    for resref, native, name in ([(r, 56, r) for r in FRAME_RESREFS] +
                                 [(r, 64, n) for r, n in ICON_RENAMES.items()]):
        size = max(1, int(round(native * scale)))
        w, h, bottom_up = decode_tpc(erf_tpc(pack, resref))
        top_down = flip(bottom_up, w, h)
        if native == 64 and w == h and size % w == 0:
            scaled = nearest_rgba(top_down, w, h, size // w)
        else:
            scaled = resize_rgba(top_down, w, h, size, size)
        with tempfile.NamedTemporaryFile(suffix=".tga") as f:
            write_tga(Path(f.name), size, size, scaled)
            files[f"{name}.tga"] = Path(f.name).read_bytes()
    return files


def keyed_resource(game: Path, resref: str, restype: int) -> bytes:
    key = (game / "chitin.key").read_bytes()
    bif_count, key_count, file_table, key_table = struct.unpack_from("<IIII", key, 8)
    for i in range(key_count):
        k = key_table + 22 * i
        if key[k:k + 16].split(b"\0")[0].decode().lower() != resref:
            continue
        rtype, rid = struct.unpack_from("<HI", key, k + 16)
        if rtype != restype:
            continue
        _, name_offset, name_length, _ = struct.unpack_from("<IIHH", key, file_table + 12 * (rid >> 20))
        bif = (game / key[name_offset:name_offset + name_length].split(b"\0")[0].decode().replace("\\", "/")).read_bytes()
        _, _, var_table = struct.unpack_from("<III", bif, 8)
        _, offset, size, _ = struct.unpack_from("<IIII", bif, var_table + 16 * (rid & 0xFFFFF))
        return bif[offset:offset + size]
    raise KeyError(resref)


def reference_table(game: Path) -> tuple[bytes, bytes]:
    from pykotor.resource.formats.twoda import bytes_2da, read_2da
    from pykotor.resource.type import ResourceType
    original = keyed_resource(game, "tutorial", 2017)
    table = read_2da(original)
    for row in range(table.get_height()):
        icon = table.get_cell(row, "icon")
        if icon.lower() in ICON_RENAMES:
            table.set_cell(row, "icon", ICON_RENAMES[icon.lower()])
    return original, bytes(bytes_2da(table, ResourceType.TwoDA))


# ------------------------------------------------------------------ the test

def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2
    game = Path(sys.argv[1]).resolve()
    resources = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else None
    pack = (game / "TexturePacks" / "swpc_tex_gui.erf").read_bytes()
    failures: list[str] = []

    set_heights: dict[int, list[Path]] = {}
    if resources:
        for archive in sorted(resources.glob("gui-*.zip")):
            height = int(re.match(r"gui-\d+x(\d+)\.zip", archive.name).group(1))
            set_heights.setdefault(height, []).append(archive)
    heights = sorted(set(set_heights) | set(EXTRA_HEIGHTS) | set(REFERENCE_HEIGHTS))

    with tempfile.TemporaryDirectory(prefix="kmrp-gameart-test-") as tmp:
        tmp = Path(tmp)
        project = tmp / "reference"
        project.mkdir()
        (project / "Driver.cs").write_text(DRIVER)
        compile_items = "".join(f'<Compile Include="{s}" />' for s in SOURCES)
        (project / "reference.csproj").write_text(PROJECT.format(compile=compile_items))
        env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
        subprocess.run(["dotnet", "build", str(project), "-c", "Release", "-o", str(project / "out")],
                       check=True, stdout=subprocess.DEVNULL, env=env)
        # The C# reads the pack and chitin.key beside the executable, as it does in a game folder.
        subprocess.run(["dotnet", str(project / "out" / "reference.dll"), str(game / "swkotor.exe"),
                        str(tmp / "cs")] + [str(h) for h in heights], check=True, env=env)

        helpers = {}
        for arch in ("x86_64", "arm64"):
            helpers[arch] = tmp / f"kmrp-gameart-{arch}"
            subprocess.run(["clang", "-O2", "-Wall", "-Wextra", "-Werror", "-arch", arch, "-o",
                            str(helpers[arch]), str(HELPER)], check=True)

        original_table, expected_table = reference_table(game)
        compared = 0
        for height in heights:
            cs = {p.name: p.read_bytes() for p in (tmp / "cs" / str(height)).iterdir()}
            if len(cs) != 18:
                failures.append(f"{height}: C# made {len(cs)} files")
            for arch, helper in helpers.items():
                out = tmp / f"{arch}-{height}"
                subprocess.run([str(helper), str(game / "TexturePacks" / "swpc_tex_gui.erf"),
                                str(game / "chitin.key"), str(height), str(out)], check=True, stdout=subprocess.DEVNULL)
                made = {p.name: p.read_bytes() for p in out.iterdir()}
                if made != cs:
                    differ = sorted(n for n in set(made) | set(cs) if made.get(n) != cs.get(n))
                    failures.append(f"{height} {arch}: differs from the C# in {differ[:4]}")
            if cs.get("tutorial.2da") != expected_table:
                failures.append(f"{height}: tutorial.2da differs from the pykotor reference")
            if height in REFERENCE_HEIGHTS:
                expected = reference_textures(pack, height)
                differ = sorted(n for n in expected if cs.get(n) != expected[n])
                if differ:
                    failures.append(f"{height}: differs from the Python reference in {differ[:4]}")
            for archive in set_heights.get(height, []):
                with zipfile.ZipFile(archive) as z:
                    for name in z.namelist():
                        if name.lower() in cs and name.lower().endswith(".tga"):
                            shipped = struct.unpack_from("<HH", z.read(name), 12)
                            made_size = struct.unpack_from("<HH", cs[name.lower()], 12)
                            if shipped != made_size:
                                failures.append(f"{archive.name} {name}: shipped {shipped}, made {made_size}")
                            compared += 1
        print(f"     {len(heights)} heights, 18 files each; {compared} shipped textures compared for size")

        # 4. The table: only the icon column, only by the rename table.
        from pykotor.resource.formats.twoda import read_2da
        a, b = read_2da(original_table), read_2da(expected_table)
        for row in range(a.get_height()):
            for header in a.get_headers():
                before, after = a.get_cell(row, header), b.get_cell(row, header)
                wanted = ICON_RENAMES.get(before.lower(), before) if header == "icon" else before
                if after != wanted:
                    failures.append(f"tutorial.2da row {row} {header}: {before!r} -> {after!r}")

        # How far the new textures are from what the build shipped (information only).
        if resources and 1964 in set_heights:
            from PIL import Image
            with zipfile.ZipFile(set_heights[1964][0]) as z:
                worst_rgb = worst_alpha = 0
                for name in sorted(n for n in z.namelist() if n.lower().rsplit(".", 1)[0] in
                                   set(FRAME_RESREFS) | set(ICON_RENAMES.values())):
                    old = Image.open(io.BytesIO(z.read(name))).convert("RGBA").tobytes()
                    new = Image.open(io.BytesIO((tmp / "cs" / "1964" / name.lower()).read_bytes())).convert("RGBA").tobytes()
                    rgb = max((abs(old[i] - new[i]) for i in range(len(old)) if i % 4 != 3), default=0)
                    alpha = max((abs(old[i] - new[i]) for i in range(3, len(old), 4)), default=0)
                    worst_rgb, worst_alpha = max(worst_rgb, rgb), max(worst_alpha, alpha)
                print(f"     against the textures the build shipped at 1964: colour within {worst_rgb}, alpha within {worst_alpha}")

    for failure in failures[:40]:
        print("  " + failure)
    print(f"{'FAIL' if failures else 'ok  '} kmrp-gameart matches GameArtGenerator.cs byte for byte "
          f"({len(heights)} heights, x86_64 and arm64), the Python reference, and the shipped sizes")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
