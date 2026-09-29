#!/usr/bin/env python3
"""Check macos/tools/kmrp-abilityicons.c against the Windows installer's own generator.

The Mac installer enlarges the feat and Force-power icons with kmrp-abilityicons; the
Windows installer does it with src/patcher/AbilityIconGenerator.cs. This builds both (the
C# source file itself, compiled into a small .NET driver) and requires the same files, byte
for byte, at several screen heights, from the same texture pack. On macOS the helper is
built for x86_64 and arm64 and both slices are compared; on Windows, one x64 build
(native_helpers.py).

    python testing/regression/Test-AbilityIcons.py SWPC_TEX_GUI_ERF

SWPC_TEX_GUI_ERF is the game's TexturePacks/swpc_tex_gui.erf (the Mac build's, under
Contents/Assets, or the Windows game's). Needs clang and the .NET 8 SDK, on macOS or Windows.
"""
from __future__ import annotations

import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_helpers  # noqa: E402
HELPER = ROOT / "macos" / "tools" / "kmrp-abilityicons.c"
GENERATOR = ROOT / "src" / "patcher" / "AbilityIconGenerator.cs"
# 720: scale 1, where the 32 px icons already grow (box 46); 982 and 1964: the 14-inch
# MacBook Pro; 1440: Windows' reference; 2160, 4320: past the 2x cap for every icon.
HEIGHTS = [600, 720, 900, 982, 1080, 1117, 1440, 1964, 2160, 4320]
RESERVED = ["i_checkbox01.tga", "I_CheckBox02.tga"]  # names KMRP ships, as the installer passes them

DRIVER = r"""
using System;
using System.Collections.Generic;
using System.IO;
namespace Kmrp {
static class Driver {
    // ResolutionPatch.ScaleForHeight (src/patcher/KmrpPatcher.cs).
    static float ScaleForHeight(int height) { float s = height / 720.0f - 0.0f; return s < 1.0f ? 1.0f : s; }
    static int Main(string[] args) {
        // TryBuild finds the pack beside the executable: <dir>/TexturePacks/swpc_tex_gui.erf.
        string executable = args[0];
        var reserved = new HashSet<string>(args[2].Split(','), StringComparer.OrdinalIgnoreCase);
        using (MemoryStream zip = AbilityIconGenerator.TryBuild(executable, ScaleForHeight(int.Parse(args[1])), reserved)) {
            if (zip == null) return 0;
            File.WriteAllBytes(args[3], zip.ToArray());
        }
        return 0;
    }
}
}
"""

PROJECT = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework>
  <Nullable>disable</Nullable><ImplicitUsings>disable</ImplicitUsings><RollForward>Major</RollForward></PropertyGroup>
  <ItemGroup><Compile Include="{generator}" /></ItemGroup>
</Project>
"""


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    erf = Path(sys.argv[1]).resolve()
    failures = []
    with tempfile.TemporaryDirectory(prefix="kmrp-abilityicons-test-") as tmp:
        tmp = Path(tmp)
        # The C# reference.
        project = tmp / "reference"
        project.mkdir()
        (project / "Driver.cs").write_text(DRIVER)
        (project / "reference.csproj").write_text(PROJECT.format(generator=GENERATOR))
        env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
        subprocess.run(["dotnet", "build", str(project), "-c", "Release", "-o", str(project / "out")],
                       check=True, stdout=subprocess.DEVNULL, env=env)
        game = tmp / "game"
        (game / "TexturePacks").mkdir(parents=True)
        # A copy on Windows, where a symbolic link needs extra privileges.
        if native_helpers.WINDOWS:
            shutil.copyfile(erf, game / "TexturePacks" / "swpc_tex_gui.erf")
        else:
            (game / "TexturePacks" / "swpc_tex_gui.erf").symlink_to(erf)
        reserved_file = tmp / "reserved.txt"
        reserved_file.write_text("\n".join(RESERVED) + "\n")

        # The helper: both slices on macOS, x64 on Windows.
        helpers = native_helpers.build(HELPER, tmp, "kmrp-abilityicons")

        total = 0
        for height in HEIGHTS:
            zip_path = tmp / f"reference-{height}.zip"
            subprocess.run(["dotnet", str(project / "out" / "reference.dll"), str(game / "KOTOR_Exe"),
                            str(height), ",".join(RESERVED), str(zip_path)], check=True, env=env)
            reference = {}
            if zip_path.exists():
                with zipfile.ZipFile(zip_path) as z:
                    reference = {n: z.read(n) for n in z.namelist()}
            for arch, helper in helpers.items():
                out = tmp / f"{arch}-{height}"
                subprocess.run([str(helper), native_helpers.arg(erf), str(height), native_helpers.arg(out),
                                native_helpers.arg(reserved_file)],
                               check=True, stdout=subprocess.DEVNULL)
                produced = {p.name: p.read_bytes() for p in out.iterdir()} if out.exists() else {}
                if set(produced) != set(reference):
                    failures.append(f"{height} {arch}: {len(produced)} files, reference {len(reference)} "
                                    f"(only here: {sorted(set(produced) - set(reference))[:3]}, "
                                    f"only in reference: {sorted(set(reference) - set(produced))[:3]})")
                    continue
                differ = [n for n in reference if produced[n] != reference[n]]
                if differ:
                    failures.append(f"{height} {arch}: {len(differ)} files differ, e.g. {differ[:3]}")
            if any(n.lower() in {r.lower() for r in RESERVED} for n in reference):
                failures.append(f"{height}: a reserved name was generated")
            # The skill icons (isk_*, 32 px) grow with the Skills row: a canvas of round(32s),
            # at least 32 and at most 64, with the picture round(0.62 * 42s) in it, centred and
            # moved (round(-0.5s), round(-2s)) to the frame opening's centre, and nothing
            # outside it -- at every height since 2026-09-29, when it moved inside the row's
            # frame (checked against the rule itself, not only between the two ports).
            s = max(1.0, struct.unpack("<f", struct.pack("<f", height / 720.0))[0])
            want = min(max(round(32 * s), 32), 64)
            picture = min(round(42 * s * 0.62), want)
            inset = (want - picture) // 2
            left = min(max(inset + round(-0.5 * s), 0), want - picture)
            top = min(max(inset + round(-2.0 * s), 0), want - picture)
            bottom = want - top - picture          # TGA rows run bottom-up
            skills = {n: data for n, data in reference.items() if n.startswith("isk_")}
            sizes = {struct.unpack_from("<HH", data, 12) for data in skills.values()}
            if len(skills) != 8 or sizes != {(want, want)}:
                failures.append(f"{height}: skill icons {sorted(sizes)} x{len(skills)}, want 8 at {want}")
            for name, data in skills.items():
                outside = [i for i in range(want * want)
                           if not (left <= i % want < left + picture and bottom <= i // want < bottom + picture)
                           and data[18 + i * 4 + 3]]
                if outside:
                    failures.append(f"{height}: {name} has {len(outside)} opaque pixels outside its "
                                    f"{picture} px picture")
                    break
            total += len(reference)
            print(f"     {height}: {len(reference)} icons")

    for failure in failures:
        print("  " + failure)
    print(f"{'FAIL' if failures else 'ok  '} kmrp-abilityicons matches AbilityIconGenerator.cs byte for byte "
          f"({len(HEIGHTS)} heights, {total} icons, {native_helpers.slices(helpers)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
