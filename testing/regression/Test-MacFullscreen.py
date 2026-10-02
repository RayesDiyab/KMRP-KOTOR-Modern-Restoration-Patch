#!/usr/bin/env python3
"""Test install/restore of Aspyr fullscreen using a temporary plist only."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
s = (root / "macos/kmrp-mac.sh").read_text()
functions = s[s.index("fullscreen_value()"):s.index("do_install()")]
setup = 'set -euo pipefail\ntask_dir=$(mktemp -d)\ntrap \'rm -rf "$task_dir"\' EXIT\nASPYR_PREFS="$task_dir/test.plist"\nrecord() { recorded=$3; backup=$4; }\ndie() { exit 1; }\n'
checks = '\nset_fullscreen\n[[ $(fullscreen_value "$ASPYR_PREFS") == 1 && $backup == - ]]\nrestore_fullscreen "$ASPYR_PREFS" "$recorded" "$backup"\n[[ -z $(fullscreen_value "$ASPYR_PREFS") ]]\ndefaults write "$ASPYR_PREFS" DisplayFullScreen -bool false\ndefaults write "$ASPYR_PREFS" Unrelated -string keep\nset_fullscreen\n[[ $backup == 0 ]]\nrestore_fullscreen "$ASPYR_PREFS" "$recorded" "$backup"\n[[ $(fullscreen_value "$ASPYR_PREFS") == 0 ]]\nset_fullscreen\ndefaults write "$ASPYR_PREFS" DisplayFullScreen -bool false\nrestore_fullscreen "$ASPYR_PREFS" "$recorded" "$backup"\n[[ $(fullscreen_value "$ASPYR_PREFS") == 0 ]]\n[[ $(defaults read "$ASPYR_PREFS" Unrelated) == keep ]]\necho \'Fullscreen install/restore/user-change checks pass\'\n'
with tempfile.TemporaryDirectory(prefix="kmrp-fullscreen-test-") as folder:
    script = Path(folder) / "test.zsh"
    script.write_text(setup + functions + checks)
    subprocess.run(["zsh", str(script)], check=True)
