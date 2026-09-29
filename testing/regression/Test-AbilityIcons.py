#!/usr/bin/env python3
"""Check macos/tools/kmrp-abilityicons.c against the Windows installer's own generator.

The Mac installer enlarges the feat and Force-power icons with kmrp-abilityicons; the
Windows installer does it with src/patcher/AbilityIconGenerator.cs. This builds both (the
C# source file itself, compiled into a small .NET driver) and requires the same files, byte
for byte, at several screen heights, from the same texture pack. The helper is built for
x86_64 and arm64 and both slices are compared.

    python testing/regression/Test-AbilityIcons.py SWPC_TEX_GUI_ERF

SWPC_TEX_GUI_ERF is the game's TexturePacks/swpc_tex_gui.erf (the Mac build's, under
Contents/Assets). Needs clang and the .NET 8 SDK.
"""
from __future__ import annotations

import io
import os
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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
        (game / "TexturePacks" / "swpc_tex_gui.erf").symlink_to(erf)
        reserved_file = tmp / "reserved.txt"
        reserved_file.write_text("\n".join(RESERVED) + "\n")

        # The helper, both slices.
        helpers = {}
        for arch in ("x86_64", "arm64"):
            helpers[arch] = tmp / f"kmrp-abilityicons-{arch}"
            subprocess.run(["clang", "-O2", "-arch", arch, "-o", str(helpers[arch]), str(HELPER)], check=True)

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
                subprocess.run([str(helper), str(erf), str(height), str(out), str(reserved_file)],
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
            # The skill icons (isk_*, 32 px) grow with the Skills row: round(32s), at most 64,
            # none below s = 1 (checked against the rule itself, not only between the two ports).
            s = max(1.0, struct.unpack("<f", struct.pack("<f", height / 720.0))[0])
            want = min(round(32 * s), 64)
            skills = {n: struct.unpack_from("<HH", data, 12) for n, data in reference.items() if n.startswith("isk_")}
            if want <= 32 and skills:
                failures.append(f"{height}: skill icons generated at scale {s:.3f}")
            if want > 32 and (len(skills) != 8 or set(skills.values()) != {(want, want)}):
                failures.append(f"{height}: skill icons {sorted(set(skills.values()))} x{len(skills)}, want 8 at {want}")
            total += len(reference)
            print(f"     {height}: {len(reference)} icons")

    for failure in failures:
        print("  " + failure)
    print(f"{'FAIL' if failures else 'ok  '} kmrp-abilityicons matches AbilityIconGenerator.cs byte for byte "
          f"({len(HEIGHTS)} heights, {total} icons, x86_64 and arm64)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
