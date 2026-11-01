#!/usr/bin/env python3
"""The rumble mixer's rules, run from K1Rumble.cpp itself (audit coverage list, item 6).

testing/regression/rumble_mixer_harness.cpp includes the shipped file and drives what its
anonymous namespace holds: the evaluator, the maximum per motor, the modes, merging, keys,
held loops, a full table, the saber hum's pulse and BioWare's table. No game runs, so which
events start which pattern is not covered: those come from engine hooks.
Run: python testing/regression/Test-RumbleMixer.py
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"


def main():
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    with tempfile.TemporaryDirectory(dir=ROOT / "build", ignore_cleanup_errors=True) as temporary:
        out = Path(temporary)
        exe = out / "rumble-mixer.exe"
        script = out / "build.cmd"
        args = ["cl", "/nologo", "/O1", "/std:c++17", "/EHsc", "/MT", f"/I{SRC}",
                str(Path(__file__).with_name("rumble_mixer_harness.cpp")), "user32.lib", f"/Fo{out}\\", f"/Fe{exe}"]
        script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\n",
                          encoding="utf-8", newline="\r\n")
        built = subprocess.run(["cmd.exe", "/d", "/c", str(script)], capture_output=True, text=True)
        if built.returncode:
            print(built.stdout[-3000:])
            return 1
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    print(result.stdout, end="")
    if result.returncode:
        print(f"FAILED ({result.returncode:#x})")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
