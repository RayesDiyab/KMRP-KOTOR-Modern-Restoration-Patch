#!/usr/bin/env python3
"""Compile the production minigame fire block and check all 512 input transitions.

Covers A/LT/RT overlap, simultaneous presses, holds, swoop trigger exclusion,
pause consumption and missing client. Uses MSVC x86; no game files.
Run: python testing/regression/Test-MiniGameFire.py
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    source = (ROOT / 'src/controller-native/K1NativeJoystick.cpp').read_text(encoding='utf-8')
    start = source.index('    const std::uint8_t held =', source.index('extern "C" void __cdecl NativeMiniGameAxisK1('))
    tail = '    g_miniGameFireHeld = held;'
    stop = source.index(tail, start) + len(tail)
    helper = source[start:stop]
    template = (Path(__file__).parent / 'mini_game_fire_harness.cpp').read_text(encoding='utf-8')
    token = '// KMRP_PRODUCTION_FIRE_BLOCK'
    assert template.count(token) == 1
    out = ROOT / 'build/controller-standalone/minigame-fire-check'
    out.mkdir(parents=True, exist_ok=True)
    cpp = out / 'minigame-fire-regression.cpp'
    cpp.write_text(template.replace(token, helper), encoding='utf-8', newline='\n')
    build = (ROOT / 'src/controller-native/build_controller_standalone.cmd').read_text(encoding='utf-8')
    vc = re.search(r'^set VC=(.+)$', build, re.MULTILINE).group(1).strip()
    if not Path(vc).is_file():
        raise RuntimeError(f'MSVC environment from build_controller_standalone.cmd is missing: {vc}')
    exe = out / 'minigame-fire-regression.exe'
    script = out / 'run-regression.cmd'
    compile_args = ['cl', '/nologo', '/O2', '/std:c++17', '/EHsc', '/W4',
                    '/D_CRT_SECURE_NO_WARNINGS', str(cpp), '/Fo' + str(out) + '\\', '/Fe' + str(exe)]
    script.write_text('@echo off\ncall "' + vc + '" x86 >nul\n'
                      'if errorlevel 1 exit /b %errorlevel%\n'
                      + subprocess.list2cmdline(compile_args) + '\n'
                      'if errorlevel 1 exit /b %errorlevel%\n"' + str(exe) + '"\n'
                      'exit /b %errorlevel%\n', encoding='utf-8', newline='\r\n')
    return subprocess.run(['cmd.exe', '/d', '/c', str(script)], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
