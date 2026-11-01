#!/usr/bin/env python3
"""kmrp-gameart.c with no memory left and with a chitin.key that lies (audit GUI-7, GUI-11).

gameart_failure_harness.c includes the shipped file, built for x86 as the module is, makes each
allocation of a picture's making fail in turn, and gives the key reader good and bad keys. A
crash here would end the game or the installer's preparation of a size. The game's own files
are not used. add_texture's own failure path is not run: it needs a texture pack.
Run: python testing/regression/Test-GameArtFailure.py
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
        exe = out / "gameart-failure.exe"
        script = out / "build.cmd"
        args = ["cl", "/nologo", "/O1", "/MT", "/D_CRT_SECURE_NO_WARNINGS", "/D_CRT_NONSTDC_NO_WARNINGS",
                str(Path(__file__).with_name("gameart_failure_harness.c")), f"/Fo{out}\\", f"/Fe{exe}"]
        script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\nexit /b %errorlevel%\n",
                          encoding="utf-8", newline="\r\n")
        built = subprocess.run(["cmd", "/d", "/c", str(script)], cwd=ROOT, capture_output=True, text=True, errors="replace")
        if built.returncode:
            print(built.stdout[-3000:])
            print("FAIL the harness did not build")
            return 1
        run = subprocess.run([str(exe), str(out)], capture_output=True, text=True, errors="replace")
        print(run.stdout)
        if run.returncode not in (0, 1):
            print(f"FAIL the harness ended with 0x{run.returncode & 0xFFFFFFFF:08X}: a crash")
        print("PASSED" if run.returncode == 0 else "FAILED")
        return 0 if run.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
