#!/usr/bin/env python3
"""The engine's font record, read in one place (audit S-8).

font_info_harness.cpp holds K1FontInfo.h and the widths built on it to numbers worked out by hand
on a made-up font, and this holds the files to using it: only K1CaptionInk::Letters and
K1TextLayout's Font, which ask more of the font, call its virtual themselves. No game runs.
Run: python testing/regression/Test-FontInfo.py
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"
ALLOWED = {"K1CaptionInk.h": 1, "K1TextLayout.cpp": 1, "K1FontInfo.h": 1}


def main():
    failed = False
    # The virtual at +0x38 of a font, called: a pointer to it is followed by the font itself.
    call = re.compile(r"\[0x38\s*/\s*4\]\)\(\s*(?:\w+\.)?(?:font|ownFont)\b")
    for path in sorted(SRC.glob("*.cpp")) + sorted(SRC.glob("*.h")):
        text = "\n".join(line.split("//")[0] for line in path.read_text(encoding="utf-8").splitlines())
        count = len(call.findall(text))
        if count != ALLOWED.get(path.name, 0):
            print(f"FAIL {path.name} calls the font's information {count} times, {ALLOWED.get(path.name, 0)} allowed")
            failed = True
    for name, count in ALLOWED.items():
        if not call.search((SRC / name).read_text(encoding="utf-8")):
            print(f"FAIL {name} no longer matches: the pattern above has stopped working")
            failed = True
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    with tempfile.TemporaryDirectory(dir=ROOT / "build", ignore_cleanup_errors=True) as temporary:
        out = Path(temporary)
        exe = out / "font-info.exe"
        script = out / "build.cmd"
        args = ["cl", "/nologo", "/O1", "/std:c++17", "/EHsc", "/MT", "/DWIN32_LEAN_AND_MEAN", f"/I{SRC}",
                str(Path(__file__).with_name("font_info_harness.cpp")), f"/Fo{out}\\", f"/Fe{exe}", "user32.lib"]
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
