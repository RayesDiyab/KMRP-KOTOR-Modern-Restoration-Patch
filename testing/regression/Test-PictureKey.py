#!/usr/bin/env python3
"""The key the controller patch finds its pictures by, on awkward names (audit THR-5).

The per-frame lookups in K1XboxControls.cpp went from walking lists to hash tables, so each is
exactly as good as K1PictureKey: picture_key_harness.cpp compares it with the _strnicmp test it
replaced, and this also holds the file to using it. No game runs.
Run: python testing/regression/Test-PictureKey.py
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"


def main():
    controls = (SRC / "K1XboxControls.cpp").read_text(encoding="utf-8")
    failed = False
    for gone in ("g_k1SceneFills", "std::vector<std::string> g_k1DrawnBadges"):
        if gone in controls:
            print(f"FAIL {gone} is back: every border walks it every frame")
            failed = True
    start = controls.index("const K1Scene* FindK1Scene(const char* fill)")
    if "for (const K1Scene&" in controls[start:controls.index("\n}\n", start)]:
        print("FAIL FindK1Scene walks the scenes again")
        failed = True
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    with tempfile.TemporaryDirectory(dir=ROOT / "build", ignore_cleanup_errors=True) as temporary:
        out = Path(temporary)
        exe = out / "picture-key.exe"
        script = out / "build.cmd"
        args = ["cl", "/nologo", "/O1", "/std:c++17", "/EHsc", "/MT", f"/I{SRC}",
                str(Path(__file__).with_name("picture_key_harness.cpp")), f"/Fo{out}\\", f"/Fe{exe}"]
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
