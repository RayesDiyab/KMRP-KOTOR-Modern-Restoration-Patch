"""The game the live controller scripts drive, in one place (audit TST-07).

Every script here named C:\\Star Wars - KotOR, which the maintainer's play-test folder stopped
being on 2026-10-20, and read logs from the game's root, which they left the same day
(KmrpFolder, src/patcher/InstallCore.cs). None of them could run. They take the folder from
KMRP_TEST_GAME, or else Steam's usual one.

These scripts start the game and send it input. They are for a game nobody is playing, in a
folder meant for testing, and only with the maintainer's say-so at the PC.
"""
from __future__ import annotations

import os

GAME_DIR = os.environ.get("KMRP_TEST_GAME", r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
GAME_EXE = os.path.join(GAME_DIR, "swkotor.exe")
LOGS = os.path.join(GAME_DIR, "KMRP", "logs")
JOYSTICK_LOG = os.path.join(LOGS, "kmrp-native-joystick.log")
