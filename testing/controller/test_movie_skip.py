#!/usr/bin/env python3
"""Skip the startup movies with the controller, from a cold launch.

Movies own the game loop. While one plays, CExoInput is not polled and no
retained event can be delivered, so there is nothing to register and the skip has
to be a bridge: KMRP hooks the body of CExoMoviePlayerInternal::PlayMovieLoop and
calls the engine's own CancelMovie.

This launches the game and presses the skip button during the logo movies, then
reads the module's own counters out of its diagnostic line:

    mve=<loop frames observed>/<cancels issued>

A cancel that never happens and a movie that was never playing look identical
from outside, so the frame counter is checked as well: it proves the hook ran.

Requires the virtual pad server. The game must NOT already be running.

Usage:
    python testing/controller/test_movie_skip.py [--presses 4]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import time

GAME_DIR = r"C:\Star Wars - KotOR"
GAME_EXE = os.path.join(GAME_DIR, "swkotor.exe")
LOG = os.path.join(GAME_DIR, "kmrp-native-joystick.log")
HOST, PORT = "127.0.0.1", 8787


def pad(command):
    sock = socket.create_connection((HOST, PORT), timeout=5)
    sock.sendall((command + "\n").encode())
    reply = sock.recv(64).decode().strip()
    sock.close()
    if reply.startswith("err"):
        raise RuntimeError(f"{command}: {reply}")
    return reply


def movie_counters():
    """(loop frames, cancels issued) from the module's diagnostic line."""
    try:
        with open(LOG, "r", errors="replace") as handle:
            found = re.findall(r"\bmve=(\d+)/(\d+)", handle.read())
    except OSError:
        return None
    return (int(found[-1][0]), int(found[-1][1])) if found else None


def running():
    out = subprocess.check_output(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process swkotor -ErrorAction SilentlyContinue).Id"]).decode().strip()
    return bool(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--presses", type=int, default=4,
                        help="A presses to make during the logo sequence")
    arguments = parser.parse_args()

    if running():
        print("swkotor is already running; this needs a cold launch")
        return 2
    pad("ping")

    before = movie_counters()
    print(f"counters before launch: {before}")

    # Launched detached and from the game's own directory: it resolves its data
    # relative to the working directory and dies without it.
    subprocess.Popen([GAME_EXE], cwd=GAME_DIR,
                     creationflags=0x00000008 | 0x00000200)
    print("launched; pressing A during the logo movies")

    # A press every second and a half, starting before the first logo appears.
    # Each press is a separate press-and-release: the module arms on a release,
    # so holding the button down would deliberately count once and no more.
    skips_seen = 0
    for index in range(arguments.presses):
        time.sleep(1.5)
        try:
            pad("press A")
            time.sleep(0.25)
            pad("release A")
        except OSError:
            pass
        counters = movie_counters()
        print(f"  press {index + 1}: counters {counters}")
        if counters and counters[1] > (before[1] if before else 0):
            skips_seen = counters[1] - (before[1] if before else 0)

    time.sleep(4.0)
    after = movie_counters()
    print(f"counters after: {after}")

    if not after:
        print("\nFAIL: the module wrote no movie counters at all -- the hook "
              "never ran, so no movie loop was entered")
        return 1
    frames = after[0] - (before[0] if before else 0)
    skips = after[1] - (before[1] if before else 0)
    print(f"\nloop frames observed: {frames}   cancels issued: {skips}")
    if frames == 0:
        print("FAIL: the movie loop never ran; nothing was under test")
        return 1
    if skips == 0:
        print("FAIL: the loop ran but no cancel was issued")
        return 1
    if skips > arguments.presses:
        print(f"FAIL: {skips} cancels from {arguments.presses} presses -- "
              "one press must be one skip")
        return 1
    print("PASS: the movie loop ran and each press produced at most one cancel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
