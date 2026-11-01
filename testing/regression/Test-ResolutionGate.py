#!/usr/bin/env python3
"""The size gate the game asks when it validates a resolution, from today's module.

KmrpAllowRuntimeResolutionK1 is the module's hook in the game's validator. A size passes when
it fits the viewport's 16-bit fields, KMRP has a layout for it (the pack's listed sizes or
the blend's reach) and the display reports a mode of it. The shipped kmrp-native.dll is
loaded as the installer's art workers load it, with KMRP_PREPARE set, so nothing of the
game's is touched, and it is asked about the sizes this PC's display reports and sizes it
does not.

The answers therefore follow this PC's display, which is why the harness prints what the
display reports. A display reporting a size KMRP has no layout for cannot be set up here, so
the source is read for that half of the rule. The work folder is under build\: a harness
in the system's temp folder that loads the module would not start on this PC, Windows
refusing it with a sharing violation for over 30 seconds (2026-11-01, holder not found).

This replaces Test-RuntimeResolution, which read a preview DLL from 2026-10-04 and expected
32767x32767 to pass: the rule it knew was the range check alone (audit TST-05).
Run: python testing/regression/Test-ResolutionGate.py
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"
MODULE = ROOT / "build/native-runtime/kmrp-native.dll"
PACK = ROOT / "build/native-runtime/kmrp-assets.pack"
CATALOG = ROOT / "build/kmrp/resources/resolutions.tsv"

HARNESS = r'''
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <set>
#include <utility>

int main(int argc, char** argv)
{
    if (argc < 2) return 2;
    HMODULE module = LoadLibraryA(argv[1]);
    if (!module) { std::printf("load failed %lu\n", GetLastError()); return 3; }
    auto allow = reinterpret_cast<int(__cdecl*)(const int*, const int*)>(
        GetProcAddress(module, "KmrpAllowRuntimeResolutionK1"));
    if (!allow) return 4;
    std::set<std::pair<int, int>> sizes;
    DEVMODEA mode{};
    mode.dmSize = sizeof mode;
    for (DWORD index = 0; EnumDisplaySettingsA(nullptr, index, &mode); ++index)
        if (mode.dmBitsPerPel == 32) {
            sizes.insert({static_cast<int>(mode.dmPelsWidth), static_cast<int>(mode.dmPelsHeight)});
            std::printf("reported %lu %lu\n", mode.dmPelsWidth, mode.dmPelsHeight);
        }
    for (int i = 2; i + 1 < argc; i += 2)
        sizes.insert({std::atoi(argv[i]), std::atoi(argv[i + 1])});
    for (const auto& size : sizes) {
        unsigned before, after;
        __asm mov before, esp
        const int result = allow(&size.first, &size.second);
        __asm mov after, esp
        std::printf("size %d %d %d %d\n", size.first, size.second, result, before == after);
    }
    const int width = 1920;
    std::printf("null %d %d\n", allow(nullptr, &width), allow(&width, nullptr));
    return 0;
}
'''

# Never passes, whatever the display: past the viewport's 16-bit fields or the game's minimum,
# or a shape outside the blend's 4:3 to 32:9.
REFUSED = [(639, 480), (640, 479), (32768, 720), (1280, 32768), (-1, 720), (1280, -1), (0, 0),
           (2147483647, 720), (1280, 2147483647), (5000, 1000), (1000, 1000), (32767, 32767)]


def compile_harness(out):
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    source = out / "gate.cpp"
    source.write_text(HARNESS, encoding="utf-8")
    exe = out / "gate.exe"
    script = out / "build.cmd"
    args = ["cl", "/nologo", "/O1", "/std:c++17", "/EHsc", "/MT", str(source), "user32.lib",
            f"/Fo{out}\\", f"/Fe{exe}"]
    script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\n",
                      encoding="utf-8", newline="\r\n")
    subprocess.run(["cmd.exe", "/d", "/c", str(script)], check=True, stdout=subprocess.DEVNULL)
    return exe


def listed_sizes():
    sizes = set()
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            parts = line.split("\t")
            sizes.add((int(parts[1]), int(parts[2])))
    return sizes


def main():
    for needed in (MODULE, PACK, CATALOG):
        if not needed.exists():
            raise SystemExit(f"{needed} is missing: build first")
    failures = 0

    def check(condition, what):
        nonlocal failures
        if not condition:
            failures += 1
            print(f"  FAIL  {what}")

    listed = listed_sizes()
    with tempfile.TemporaryDirectory(dir=ROOT / "build", ignore_cleanup_errors=True) as temporary:
        out = Path(temporary)
        exe = compile_harness(out)
        patches = out / "game/patches"
        patches.mkdir(parents=True)
        shutil.copy2(MODULE, patches / "kmrp.dll")
        shutil.copy2(PACK, patches / "kmrp-assets.pack")
        (out / "local").mkdir()
        environment = dict(os.environ, KMRP_PREPARE="1", LOCALAPPDATA=str(out / "local"))
        asked = [n for size in sorted(listed | set(REFUSED)) for n in size]
        result = subprocess.run([str(exe), str(patches / "kmrp.dll"), *map(str, asked)], env=environment,
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            print(f"  FAIL  the harness ended with {result.returncode:#x}\n{result.stdout}{result.stderr}")
            return 1

    reported, answers = set(), {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts[0] == "reported":
            reported.add((int(parts[1]), int(parts[2])))
        elif parts[0] == "size":
            answers[(int(parts[1]), int(parts[2]))] = int(parts[3])
            check(parts[4] == "1", f"{parts[1]}x{parts[2]}: the call left the stack balanced")
        elif parts[0] == "null":
            check(parts[1:] == ["0", "0"], f"a null slot answers {parts[1:]}")

    both = reported & listed
    print(f"{len(reported)} sizes reported here, {len(both)} of them listed, {len(answers)} asked about")
    check(len(both) > 0, "this display reports a listed size, so the yes half was tried")
    for size in both:
        check(answers.get(size) == 1, f"{size[0]}x{size[1]}: listed and reported passes")
    for size in listed - reported:
        check(answers.get(size) == 0, f"{size[0]}x{size[1]}: listed, not reported, is refused")
    for size in REFUSED:
        check(answers.get(size) == 0, f"{size[0]}x{size[1]}: always refused")

    # The half this display cannot show: each test in the rule, in its place.
    source = (SRC / "K1RuntimeResolution.cpp").read_text(encoding="utf-8")
    body = source[source.index("int __cdecl KmrpAllowRuntimeResolutionK1"):]
    body = body[:body.index("return 1;")]
    tests = [body.find("KmrpRuntimeDimensions(*width, *height)"), body.find("KmrpRuntimeAssetsCovers(*width, *height)"),
             body.find("DisplayReports(*width, *height)")]
    check(min(tests) >= 0 and tests == sorted(tests), "the gate tests range, then layout, then display")

    if failures:
        print(f"FAILED ({failures})")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
