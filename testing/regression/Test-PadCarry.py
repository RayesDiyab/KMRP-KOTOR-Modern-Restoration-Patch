#!/usr/bin/env python3
"""A button held across a movie's end is not a press on the next screen (PAD-9).

pad_carry_harness.cpp runs K1PadCarry.h on the sequences a movie's end can give, and this holds
K1NativeJoystick.cpp to using it: the movie frame marks it, and the buffer filters the word before
the remap, so the press never reaches anything downstream. The real game's case is
`testing/controller/trial_movie_skip.py`. No game runs here.
Run: python testing/regression/Test-PadCarry.py
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"


def main():
    failed = False
    native = (SRC / "K1NativeJoystick.cpp").read_text(encoding="utf-8")
    start = native.index('extern "C" void __cdecl NativeMovieFrameK1(void* moviePlayer)')
    if "g_padCarry.MovieFrame();" not in native[start:native.index("\n}\n", start)]:
        print("FAIL the movie frame no longer marks the carry")
        failed = True
    if "KmrpRemapButtonsK1(g_padCarry.Filter(word), world)" not in native:
        print("FAIL the buffer no longer filters the word ahead of the remap")
        failed = True
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    with tempfile.TemporaryDirectory(dir=ROOT / "build", ignore_cleanup_errors=True) as temporary:
        out = Path(temporary)
        exe = out / "pad-carry.exe"
        script = out / "build.cmd"
        args = ["cl", "/nologo", "/O1", "/std:c++17", "/EHsc", "/MT", f"/I{SRC}",
                str(Path(__file__).with_name("pad_carry_harness.cpp")), f"/Fo{out}\\", f"/Fe{exe}"]
        script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\nexit /b %errorlevel%\n",
                          encoding="utf-8", newline="\r\n")
        built = subprocess.run(["cmd", "/d", "/c", str(script)], cwd=ROOT, capture_output=True, text=True, errors="replace")
        if built.returncode:
            print(built.stdout[-2000:])
            print("FAIL the harness did not build")
            return 1
        run = subprocess.run([str(exe)], capture_output=True, text=True, errors="replace")
        print(run.stdout)
        failed = failed or run.returncode != 0
    print("FAILED" if failed else "PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
