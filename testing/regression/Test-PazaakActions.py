"""Run the production Pazaak handlers against native-layout mock objects."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    source = (ROOT / 'src/controller-native/K1NativeJoystick.cpp').read_text(encoding='utf-8')
    names = ['PazaakFocusedHandCardK1', 'PazaakPlayFocusedCardK1', 'PazaakActionFlashK1',
             'PazaakMouseOnlyDrawK1', 'PazaakFlipFocusedCardK1', 'SetPazaakActionEnabledK1',
             'PazaakHandSlotK1', 'RememberPazaakHandSlotK1', 'EnsurePazaakHandFocusK1',
             'NavigatePazaakHandK1', 'PazaakHandActionEnabledK1']
    functions = []
    for name in names:
        match = re.search(r'^(?:void\*|void|int|bool)(?: __fastcall)? ' + name + r'\([^;]*?\)\n\{', source, re.M)
        assert match, name
        begin = match.start()
        end = source.index('\n}', match.end()) + 2
        functions.append(source[begin:end])
    badges = (ROOT / 'src/controller-native/vendor/K1XboxControls.cpp').read_text(encoding='utf-8')
    begin = badges.index('void KmrpPromptDimK1(')
    functions.append(badges[begin:badges.index('\n}', begin) + 2])
    production = '\n\n'.join(functions)
    # Replace only engine entry points; handler logic, field offsets and guards stay intact.
    production = production.replace('(K1_PAZAAK_CLICK_CARD)', '(&MockPlay)')
    production = production.replace('(0x0067CA50)', '(&MockFlash)')
    production = production.replace('(0x0067DD80)', '(&MockFlip)')
    production = production.replace('(0x00414E10)', '(&MockTextColor)')
    production = production.replace('(K1_SET_ACTIVE_CONTROL)', '(&MockFocus)')
    production = production.replace('reinterpret_cast<const float*>(0x007A23CC)', 'flashColour')
    template = (Path(__file__).parent / 'pazaak_actions_harness.cpp').read_text(encoding='utf-8')
    out = ROOT / 'build/controller-standalone/pazaak-actions-check'
    out.mkdir(parents=True, exist_ok=True)
    cpp = out / 'pazaak-actions.cpp'
    cpp.write_text(template.replace('// PRODUCTION_HANDLERS', production), encoding='utf-8')
    build = (ROOT / 'src/controller-native/build_controller_standalone.cmd').read_text(encoding='utf-8')
    vc = re.search(r'^set VC=(.+)$', build, re.M).group(1).strip()
    exe = out / 'pazaak-actions.exe'
    args = ['cl', '/nologo', '/std:c++17', '/EHsc', '/W4', '/DKMRP_CONTROLLER_STANDALONE',
            str(cpp), '/Fo' + str(out) + '/', '/Fe' + str(exe)]
    script = out / 'run.cmd'
    script.write_text('@echo off\ncall "' + vc + '" x86 >nul\n'
                      'if errorlevel 1 exit /b %errorlevel%\n' + subprocess.list2cmdline(args)
                      + '\nif errorlevel 1 exit /b %errorlevel%\n"' + str(exe) + '"\n', encoding='utf-8')
    return subprocess.run(['cmd.exe', '/d', '/c', str(script)], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
