#!/usr/bin/env python3
"""Compile the real direct race/model prompt updater against fake engine objects.

Checks targeting, rebuilt/unloaded objects, input transitions and steady-state
cost counters. Uses MSVC x86; no game files.
Run: python testing/regression/Test-SwoopPrompt.py
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    source = (ROOT / 'src/controller-native/K1NativeJoystick.cpp').read_text(encoding='utf-8')
    start = source.index('namespace {\nconstexpr std::uintptr_t K1_TEXTURE_REF_VTABLE')
    stop = source.index('} // namespace', start) + len('} // namespace')
    helper = source[start:stop]
    assert 'K1_LIVE_MATERIAL' not in source and 'K1_SWOOP_SCAN_BUDGET' not in source
    assert source.count('    UpdateSwoopPromptK1();') == 1
    assert 'swoopPromptActive' not in source
    template = (Path(__file__).parent / 'swoop_prompt_harness.cpp').read_text(encoding='utf-8')
    token = '// KMRP_PRODUCTION_PROMPT_HELPER'
    assert template.count(token) == 1
    out = ROOT / 'build/controller-standalone/swoop-prompt-check'
    out.mkdir(parents=True, exist_ok=True)
    cpp = out / 'prompt-material-regression.cpp'
    cpp.write_text(template.replace(token, helper), encoding='utf-8', newline='\n')
    build = (ROOT / 'src/controller-native/build_controller_standalone.cmd').read_text(encoding='utf-8')
    vc = re.search(r'^set VC=(.+)$', build, re.MULTILINE).group(1).strip()
    if not Path(vc).is_file():
        raise RuntimeError(f'MSVC environment from build_controller_standalone.cmd is missing: {vc}')
    exe = out / 'prompt-material-regression.exe'
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
