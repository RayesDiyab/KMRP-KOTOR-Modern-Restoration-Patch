#!/usr/bin/env python3
"""The offscreen frame against a stand-in driver, from K1OffscreenFrame.cpp itself.

testing/regression/offscreen_frame_harness.cpp includes the shipped file, points its OpenGL
functions at fakes, and walks a window through swaps, binds, reads, a new size,
anti-aliasing and every refusal. It says what the module asks of a driver, and what it does
with the answers; it cannot say what a real driver does with them, so AMD, Intel and Proton
stay on the gameplay checklist. The offscreen frame is on for every player, and nothing
tested it before this. The hand-set switch in configs\\kmrp.ini is read from source below,
as it needs a game folder to read at run time.
Run: python testing/regression/Test-OffscreenFrame.py
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"
SOURCE = SRC / "K1OffscreenFrame.cpp"


def main():
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    with tempfile.TemporaryDirectory(dir=ROOT / "build", ignore_cleanup_errors=True) as temporary:
        out = Path(temporary)
        exe = out / "offscreen-frame.exe"
        script = out / "build.cmd"
        args = ["cl", "/nologo", "/O1", "/std:c++17", "/EHsc", "/MT", f"/I{SRC}",
                str(Path(__file__).with_name("offscreen_frame_harness.cpp")), "user32.lib", "gdi32.lib",
                f"/Fo{out}\\", f"/Fe{exe}"]
        script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\n",
                          encoding="utf-8", newline="\r\n")
        built = subprocess.run(["cmd.exe", "/d", "/c", str(script)], capture_output=True, text=True)
        if built.returncode:
            print(built.stdout[-3000:])
            return 1
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    print("\n".join(line for line in result.stdout.splitlines() if not line.startswith("    log:")))
    text = SOURCE.read_text(encoding="utf-8")
    switch = 'GetPrivateProfileIntW(L"Offscreen", L"window-drawn", 0, options)' in text
    print(("ok  " if switch else "FAIL") + "  the module reads the hand-set switch")
    if result.returncode or not switch:
        print(f"FAILED ({result.returncode:#x})")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
