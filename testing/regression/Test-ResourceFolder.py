#!/usr/bin/env python3
"""A folder's name for the game, and preparation that stops when it fails (audit THR-2).

Compiles K1ResourceFolder.h's path code with the real Windows calls and asks it about real
folders: a plain path stays as it is, and a folder with a character the system's code page
lacks comes back in its short form, or empty where the drive keeps no short names, and never
with a substituted character. Then the source: both modules share the header, and each
preparation has one try per size.
Run: python testing/regression/Test-ResourceFolder.py
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"

HARNESS = r'''
#define KMRP_RESOURCE_FOLDER_TEST
#include "K1ResourceFolder.h"
#include <cstdio>
int wmain(int argc, wchar_t** argv)
{
    for (int i = 1; i < argc; ++i) {
        const std::string text = KmrpNarrowPathK1(argv[i]);
        std::printf("%s\n", text.empty() ? "<empty>" : text.c_str());
    }
    return 0;
}
'''


def compile_harness(out):
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    source = out / "resource-folder.cpp"
    source.write_text(HARNESS, encoding="utf-8")
    exe = out / "resource-folder.exe"
    script = out / "build.cmd"
    args = ["cl", "/nologo", "/O2", "/std:c++17", "/EHsc", "/W4", f"/I{SRC}", str(source),
            f"/Fo{out}\\", f"/Fe{exe}"]
    script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\n",
                      encoding="utf-8", newline="\r\n")
    subprocess.run(["cmd.exe", "/d", "/c", str(script)], check=True, stdout=subprocess.DEVNULL)
    return exe


def main():
    out = ROOT / "build/resource-folder-check"
    out.mkdir(parents=True, exist_ok=True)
    exe = compile_harness(out)
    checks = 0
    with tempfile.TemporaryDirectory(prefix="kmrp-folder-") as temporary:
        plain = Path(temporary) / "plain"
        plain.mkdir()
        odd = Path(temporary) / "Привет世界"
        odd.mkdir()
        answers = subprocess.run([str(exe), str(plain), str(odd), str(odd / "not-yet")],
                                 capture_output=True, text=True, encoding="mbcs").stdout.split("\n")
        assert answers[0] == str(plain), f"a plain path is kept: {answers[0]}"
        checks += 1
        for answer in answers[1:3]:
            assert "?" not in answer, f"a character was substituted: {answer}"
            assert answer == "<empty>" or "~" in answer or answer.isascii(), answer
            checks += 1
        assert answers[2] == "<empty>" or answers[2].endswith("\\not-yet"), "the part that does not exist stays"
        checks += 1

    assets = (SRC / "K1RuntimeAssets.cpp").read_text(encoding="utf-8")
    standalone = (SRC / "K1ControllerStandalone.cpp").read_text(encoding="utf-8")
    pictures = (SRC / "vendor/K1XboxControls.cpp").read_text(encoding="utf-8")
    for source in (assets, standalone):
        assert '#include "K1ResourceFolder.h"' in source
        assert "0x5E6880" not in source and "0x408800" not in source, "a second copy of registration"
    assert "tried = true" in assets and "busy || tried || registered" in assets
    hook = standalone[standalone.index("extern \"C\" void __cdecl ControllerPrepareResourcesK1"):]
    assert "failed = true;" in hook[hook.index("registered = RegisterDirectory()"):], "a failed folder stops the hook"
    assert "if (failed) return false;" in standalone, "Unpack remembers a failure"
    assert "K1PictureFailed(out)" in pictures and "g_k1FailedPictures.push_back" in pictures
    checks += 7
    shutil.rmtree(out, ignore_errors=True)
    print(f"PASS: {checks} checks: folders named for the game, one try per size.")


if __name__ == "__main__":
    main()
