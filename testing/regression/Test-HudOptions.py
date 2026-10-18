#!/usr/bin/env python3
"""Compile and run the HUD Size page's rules (K1HudOptionsPolicy.h) and the mouse and keyboard
HUD's placing (K1PcHudLayout.h); check that its table is what tools/build_pc_hud.py writes.
No game required; needs pykotor (run with plain `python`)."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    subprocess.run([sys.executable, str(ROOT / 'tools/build_pc_hud.py'), '--check'], cwd=ROOT, check=True)
    out = ROOT / 'build/hud-options-check'
    out.mkdir(parents=True, exist_ok=True)
    vc = re.search(r'^set VC=(.+)$', (ROOT / 'src/controller-native/build_native_runtime.cmd').read_text(), re.M)[1].strip()
    exe = out / 'hud-options.exe'
    args = ['cl', '/nologo', '/O2', '/std:c++17', '/EHsc', '/W4', '/WX',
            str(ROOT / 'testing/regression/hud_options_harness.cpp'),
            '/Fo' + str(out) + '/', '/Fe' + str(exe)]
    cmd = out / 'build.cmd'
    cmd.write_text('@echo off\ncall "' + vc + '" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'
                   + subprocess.list2cmdline(args) + '\nexit /b %errorlevel%\n', newline='\r\n')
    subprocess.run(['cmd', '/d', '/c', str(cmd)], cwd=ROOT, check=True)
    subprocess.run([str(exe)], cwd=out, check=True)


if __name__ == '__main__':
    main()
