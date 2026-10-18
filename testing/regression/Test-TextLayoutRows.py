#!/usr/bin/env python3
"""Compile and run the combined production native text layout and rows services; no game required."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = ROOT / 'build/text-layout-rows-check'
    out.mkdir(parents=True, exist_ok=True)
    vc = re.search(r'^set VC=(.+)$', (ROOT / 'src/controller-native/build_native_runtime.cmd').read_text(), re.M)[1].strip()
    exe = out / 'text-layout-rows.exe'
    args = ['cl', '/nologo', '/O2', '/std:c++17', '/EHsc', '/W4', '/WX', '/DKMRP_TEXT_LAYOUT_TEST',
            str(ROOT / 'testing/regression/native_text_layout_rows_harness.cpp'),
            str(ROOT / 'src/controller-native/K1TextRows.cpp'),
            '/Fo' + str(out) + '/', '/Fe' + str(exe)]
    cmd = out / 'build.cmd'
    cmd.write_text('@echo off\ncall "' + vc + '" x86 >nul\nif errorlevel 1 exit /b %errorlevel%\n'
                   + subprocess.list2cmdline(args) + '\nexit /b %errorlevel%\n', newline='\r\n')
    subprocess.run(['cmd', '/d', '/c', str(cmd)], cwd=ROOT, check=True)
    subprocess.run([str(exe)], cwd=out, check=True)


if __name__ == '__main__':
    main()

