#!/usr/bin/env python3
"""A dialogue from first line to last, by pad, on the running game (checklist 9a, E-1, E-2).

Loads the newest save, which must stand beside someone to talk to, with no enemy near. A starts the
conversation, A moves through the lines and picks the first reply, until the HUD has the player
again or the limit is reached. Each step records the panels and a frame: what the bars and the
replies look like is read by a person.

Writes `build/verify/talk-*.png` and `build/verify/talk-<label>.json`.
Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import json
import time

from live_harness import VERIFY
from live_session import Session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="run")
    parser.add_argument("--presses", type=int, default=24)
    args = parser.parse_args()
    session = Session()
    game = session.game
    rows: list = []
    try:
        session.boot()
        session.load_newest_save()
        time.sleep(3)
        game.press("tap A 0.1")
        for number in range(1, args.presses + 1):
            time.sleep(2.5)
            row = {"step": number, "panels": game.panel_names()[-3:], "class": session.input_class(),
                   "alive": game.alive()}
            rows.append(row)
            print(json.dumps(row), flush=True)
            game.shot(VERIFY / f"talk-{number:02d}.png")
            game.press("tap A 0.1")
    finally:
        (VERIFY / f"talk-{args.label}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
