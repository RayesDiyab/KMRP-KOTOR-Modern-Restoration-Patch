#!/usr/bin/env python3
"""The Linux installer's display sizes on recorded displays (issue 72, issue 102).

Runs the AppImage's own `sizes` command in WSL with KMRP_TEST_DRM (a folder read as
/sys/class/drm) and KMRP_TEST_XRANDR (a file read as xrandr's output), so the code under
test is LinuxDisplay.cs exactly as it ships, with the resolution catalogue it carries.
Each case states the size the game starts at and the sizes offered.

The Steam Deck cases record its real panel: the kernel lists it as a portrait 800x1280,
which SteamOS turns to 1280x800. Until issue 102 the recorded "Deck" here had a landscape
panel, and the 1.6.0 AppImage told every Deck owner that the display reports no resolution
KMRP can use.

    python testing/regression/Test-LinuxDisplay.py [path to the AppImage]

With no path it tests dist/KMRP-Linux-<version>-x86_64.AppImage. Needs WSL.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

DECK_PANEL = ['800x1280']   # card0-eDP-1/modes on a Steam Deck (LCD and OLED alike)

# X11 desktop: the output is turned "right"; its header has the turned size, its modes the panel's.
DECK_X11 = """Screen 0: minimum 320 x 200, current 1280 x 800, maximum 16384 x 16384
eDP connected primary 1280x800+0+0 right (normal left inverted right x axis y axis) 0mm x 0mm
   800x1280      60.00*+  50.00
DP-1 disconnected (normal left inverted right x axis y axis)
"""

DECK_XWAYLAND = """Screen 0: minimum 16 x 16, current 1280 x 800, maximum 32767 x 32767
XWAYLAND0 connected primary 1280x800+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
   1280x800      59.81*+
"""

GAMESCOPE_1200 = """Screen 0: minimum 16 x 16, current 1920 x 1200, maximum 32767 x 32767
XWAYLAND0 connected primary 1920x1200+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
   1920x1200     59.95*+
"""

MONITOR_1440 = ['2560x1440', '1920x1080', '1280x720']

DESKTOP_1440 = """Screen 0: minimum 320 x 200, current 2560 x 1440, maximum 16384 x 16384
DP-1 connected primary 2560x1440+0+0 (normal left inverted right x axis y axis) 597mm x 336mm
   2560x1440     143.97*+ 59.95
   1920x1080     60.00
   1280x720      60.00
"""

SCALED_1440 = """Screen 0: minimum 16 x 16, current 2048 x 1152, maximum 32767 x 32767
XWAYLAND0 connected primary 2048x1152+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
   2048x1152     59.96*+
"""

# A monitor stood on its side: the kernel lists its landscape modes, XWayland the turned size.
PORTRAIT_MONITOR = """Screen 0: minimum 16 x 16, current 1440 x 2560, maximum 32767 x 32767
XWAYLAND0 connected primary 1440x2560+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
   1440x2560     59.95*+
"""

GAMESCOPE = {'GAMESCOPE_WAYLAND_DISPLAY': 'gamescope-0'}

#   name, kernel modes (None: no DRM list), xrandr (None: no xrandr), environment,
#   expected start, expected sizes (largest first)
CASES = [
    ('Steam Deck, desktop mode on X11', DECK_PANEL, DECK_X11, {}, '1280x800', ['1280x800']),
    ('Steam Deck, desktop mode through XWayland', DECK_PANEL, DECK_XWAYLAND, {}, '1280x800', ['1280x800']),
    ('Steam Deck, game mode: Gamescope at 1920x1200', DECK_PANEL, GAMESCOPE_1200, GAMESCOPE, '1280x800', ['1280x800']),
    ('Steam Deck, kernel list only', DECK_PANEL, None, {}, '1280x800', ['1280x800']),
    ('2560x1440 monitor, no scaling', MONITOR_1440, DESKTOP_1440, {}, '2560x1440', MONITOR_1440),
    ('2560x1440 monitor, XWayland sees 2048x1152', MONITOR_1440, SCALED_1440, {}, '2560x1440', MONITOR_1440),
    ('2560x1440 monitor stood on its side', MONITOR_1440, PORTRAIT_MONITOR, {}, '2560x1440', MONITOR_1440),
    ('no kernel list: xrandr only', None, DESKTOP_1440, {}, '2560x1440', MONITOR_1440),
]


def wsl_path(path):
    return subprocess.run(['wsl.exe', 'wslpath', '-a', str(path).replace('\\', '/')],
                          capture_output=True, text=True, check=True).stdout.strip()


def default_appimage():
    version = re.search(r'internal const string PatchVersion = "([^"]+)";',
                        (ROOT / 'src/patcher/InstallCore.cs').read_text(encoding='utf-8')).group(1)
    return ROOT / 'dist' / ('KMRP-Linux-' + version + '-x86_64.AppImage')


def write_case(folder, modes, xrandr):
    drm = folder / 'drm'
    (drm / 'card0-HDMI-A-1').mkdir(parents=True)
    (drm / 'card0-HDMI-A-1' / 'status').write_text('disconnected\n', newline='\n')
    (drm / 'card0-HDMI-A-1' / 'modes').write_text('', newline='\n')
    if modes is not None:
        (drm / 'card0-eDP-1').mkdir()
        (drm / 'card0-eDP-1' / 'status').write_text('connected\n', newline='\n')
        (drm / 'card0-eDP-1' / 'modes').write_text(''.join(m + '\n' for m in modes), newline='\n')
    else:
        shutil.rmtree(drm)
    if xrandr is not None:
        (folder / 'xrandr.txt').write_text(xrandr, newline='\n')
    return drm, folder / 'xrandr.txt'


def main():
    appimage = Path(sys.argv[1]) if len(sys.argv) > 1 else default_appimage()
    if not appimage.is_file():
        sys.exit('no AppImage at ' + str(appimage) + ': build it with tools/build_linux_installer.ps1')
    image = wsl_path(appimage)
    failures = 0
    with tempfile.TemporaryDirectory(prefix='kmrp-linux-display-') as temp:
        for index, (name, modes, xrandr, env, start, sizes) in enumerate(CASES):
            folder = Path(temp) / str(index)
            folder.mkdir()
            drm, xrandr_file = write_case(folder, modes, xrandr)
            variables = {'APPIMAGE_EXTRACT_AND_RUN': '1',
                         'KMRP_TEST_DRM': wsl_path(drm) if modes is not None else '/nonexistent',
                         'KMRP_TEST_XRANDR': wsl_path(xrandr_file) if xrandr is not None else 'none'}
            variables.update(env)
            command = ['wsl.exe', '-e', 'env', '-u', 'DISPLAY', '-u', 'WAYLAND_DISPLAY',
                       '-u', 'GAMESCOPE_WAYLAND_DISPLAY', '-u', 'XDG_CURRENT_DESKTOP']
            command += [k + '=' + v for k, v in variables.items()] + [image, 'sizes']
            result = subprocess.run(command, capture_output=True, text=True,
                                    env=dict(os.environ, MSYS_NO_PATHCONV='1'))
            output = result.stdout.replace('\r', '')
            got_start = re.search(r'^start at:\s+(\S+)', output, re.M)
            got_start = got_start.group(1) if got_start else None
            got_sizes = re.findall(r'^\s+(\d+x\d+)\s', output, re.M)
            uncovered = re.findall(r'^\s+(\d+x\d+)\s.*\(not covered\)', output, re.M)
            ok = result.returncode == 0 and got_start == start and got_sizes == sizes and not uncovered
            failures += not ok
            print(('ok   ' if ok else 'FAIL ') + name + ': starts at ' + str(got_start) +
                  ', offers ' + (', '.join(got_sizes) or 'nothing') +
                  (', not covered: ' + ', '.join(uncovered) if uncovered else ''))
            if not ok:
                print('     expected ' + start + ', offering ' + ', '.join(sizes))
                print('     ' + (output + result.stderr).strip().replace('\n', '\n     '))
    print(str(len(CASES) - failures) + ' of ' + str(len(CASES)) + ' cases pass')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
