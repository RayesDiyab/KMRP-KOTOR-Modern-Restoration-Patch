"""Exercise the actual controller preload callback and worker without KMRP or a renderer."""
from pathlib import Path
import argparse
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=Path('C:/Program Files (x86)/Steam/steamapps/common/swkotor'))
    parser.add_argument('--resources', type=Path, default=ROOT / 'build/kmrp/resources')
    parser.add_argument('--controller-files', type=Path, default=ROOT / 'build/controller-standalone/files')
    options = parser.parse_args()
    out = ROOT / 'build/controller-standalone/preload-check'
    out.mkdir(parents=True, exist_ok=True)
    vendor = (ROOT / 'src/controller-native/vendor/K1XboxControls.cpp').read_text(encoding='utf-8')
    worker = function(vendor, 'void K1BackgroundWorker()')
    queue = function(vendor, 'void KmrpQueueControllerGuiWorkK1(')
    source = (ROOT / 'src/controller-native/K1ControllerPreload.cpp').read_text(encoding='utf-8')
    source = source.replace('0x0078D1D4', 'reinterpret_cast<std::uintptr_t>(&testWidth)')
    source = source.replace('0x0078D1D8', 'reinterpret_cast<std::uintptr_t>(&testHeight)')
    harness = (Path(__file__).parent / 'controller_preload_harness.cpp').read_text(encoding='utf-8')
    hud = (ROOT / 'src/controller-native/K1XboxHud.cpp').read_text(encoding='utf-8')
    sizes = function(hud, 'const HudSizes& Sizes()')
    cpp = out / 'controller-preload.cpp'
    cpp.write_text(harness.replace('// PRODUCTION_WORKER', worker + '\n' + queue)
                   .replace('// PRODUCTION_PRELOAD', source)
                   .replace('// PRODUCTION_HUD_SIZES', sizes), encoding='utf-8')
    build = (ROOT / 'src/controller-native/build_controller_standalone.cmd').read_text(encoding='utf-8')
    vc = re.search(r'^set VC=(.+)$', build, re.M).group(1).strip()
    exe = out / 'controller-preload.exe'
    c_args = ['cl', '/nologo', '/c', '/O2', '/MT', '/TC', '/DKMRP_EMBEDDED', '/D_CRT_SECURE_NO_WARNINGS',
              str(ROOT / 'macos/tools/kmrp-guiadapt.c'), str(ROOT / 'macos/tools/kmrp-gameart.c'), '/Fo' + str(out) + '/']
    args = ['cl', '/nologo', '/O2', '/MT', '/std:c++17', '/EHsc', '/Isrc/controller-native', str(cpp),
            str(out / 'kmrp-guiadapt.obj'), str(out / 'kmrp-gameart.obj'), '/Fo' + str(out) + '/', '/Fe' + str(exe)]
    game = options.game
    fixture = out / 'core-source'
    fixture.mkdir(exist_ok=True)
    for archive, entry in [('gui-3440x1440.zip', 'classsel.gui'), ('override-common.zip', 'lbl_cg_clsssel.tpc')]:
        with zipfile.ZipFile(options.resources / archive) as z:
            (fixture / entry).write_bytes(z.read(entry))
    script = out / 'run.cmd'
    script.write_text('@echo off\ncall "' + vc + '" x86 >nul\n'
                      'if errorlevel 1 exit /b %errorlevel%\n' + subprocess.list2cmdline(c_args)
                      + '\nif errorlevel 1 exit /b %errorlevel%\n' + subprocess.list2cmdline(args)
                      + '\nif errorlevel 1 exit /b %errorlevel%\n'
                      + subprocess.list2cmdline([str(exe), str(game), str(options.controller_files)])
                      + '\nif errorlevel 1 exit /b %errorlevel%\n'
                      + subprocess.list2cmdline([str(exe), str(game), str(options.controller_files), str(fixture)])
                      + '\n', encoding='utf-8')
    return subprocess.run(['cmd.exe', '/d', '/c', str(script)], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
