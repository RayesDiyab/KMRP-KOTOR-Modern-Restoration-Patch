#!/usr/bin/env python3
"""Send commands to the virtual pad held open by `virtual_pad_server.py`.

    python testing/controller/pad.py tap A
    python testing/controller/pad.py dpad down 0.5
    python testing/controller/pad.py "tap START" "dpad down" "tap A"

Several commands in one call are sent down one connection in order, which keeps
menu sequences tight enough that the game does not settle in between.
"""

from __future__ import annotations

import socket
import sys

HOST, PORT = "127.0.0.1", 8787


def send(commands: list[str]) -> list[str]:
    with socket.create_connection((HOST, PORT), timeout=15) as connection:
        connection.sendall(("\n".join(commands) + "\n").encode())
        replies = b""
        while replies.count(b"\n") < len(commands):
            chunk = connection.recv(4096)
            if not chunk:
                break
            replies += chunk
    return replies.decode("utf-8", "replace").strip().splitlines()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    # Either one command as separate words, or several quoted commands.
    arguments = sys.argv[1:]
    commands = arguments if len(arguments) > 1 and " " in arguments[0] else [" ".join(arguments)]
    for command, reply in zip(commands, send(commands)):
        print(f"{command:<24}{reply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
