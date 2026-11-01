#!/usr/bin/env python3
"""The live controller scripts can find the game (audit TST-07).

testing/controller's scripts need a running game and a pad, so nothing runs them here. What
broke them can be checked without one: each compiles, none names a folder of its own, and
each that reads the game or its logs goes through live_game.py, whose log path is the one
the module writes (KmrpLogPath, KmrpOptions.h).
Run: python testing/regression/Test-LiveSuitePaths.py
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "testing/controller"
OPTIONS = ROOT / "src/controller-native/KmrpOptions.h"


def main():
    failures = []
    scripts = sorted(SUITE.glob("*.py"))
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        try:
            compile(text, str(path), "exec")
        except SyntaxError as error:
            failures.append(f"{path.name} does not compile: {error}")
        if path.name == "live_game.py":
            continue
        if re.search(r"""['"][A-Za-z]:\\[^'"]*(swkotor|KotOR|steamapps)""", text):
            failures.append(f"{path.name} names a game folder of its own")
        if re.search(r"\bGAME_DIR\b|\bGAME_EXE\b|joystick\.log", text) and "live_game" not in text:
            failures.append(f"{path.name} reads the game without live_game.py")
        if re.search(r"""os\.path\.join\(GAME_DIR, ['"]kmrp-[a-z-]+\.log""", text):
            failures.append(f"{path.name} looks for a log in the game's root")
    sys.path.insert(0, str(SUITE))
    import live_game
    if not live_game.JOYSTICK_LOG.endswith(r"KMRP\logs\kmrp-native-joystick.log"):
        failures.append(f"the log is at {live_game.JOYSTICK_LOG}")
    if r"KMRP\\logs" not in OPTIONS.read_text(encoding="utf-8") and "logs" not in OPTIONS.read_text(encoding="utf-8"):
        failures.append("KmrpOptions.h no longer writes to a logs folder")
    print(f"{len(scripts)} scripts")
    for failure in failures:
        print(f"  FAIL  {failure}")
    if failures:
        print(f"FAILED ({len(failures)})")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
