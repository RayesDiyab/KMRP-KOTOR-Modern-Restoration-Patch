#!/usr/bin/env python3
"""From a Pazaak player's dialogue to a played hand, by pad, on the running game (checklist 7, 12).

Same start as `trial_dialogue.py`: the newest save must stand beside a Pazaak player, whose first A
replies lead to the wager. Then A takes the wager, Y adds ten cards, A plays, and A and the D-pad
play a hand. What the screens look like is read by a person from the frames.

Writes `build/verify/paz-*.png` and `build/verify/paz-<label>.json`.
Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import json
import time

from live_harness import VERIFY, wait_for
from live_session import Session

SETUP = 0x007532E8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    session = Session()
    game = session.game
    rows: list = []

    def step(name: str, command: str, settle: float = 1.2):
        game.press(command)
        time.sleep(settle)
        row = {"step": name, "panels": game.panel_names()[-3:], "alive": game.alive()}
        rows.append(row)
        print(json.dumps(row), flush=True)
        game.shot(VERIFY / f"paz-{len(rows):02d}.png")

    try:
        session.boot()
        session.load_newest_save()
        time.sleep(3)
        game.press("tap A 0.1")
        for _ in range(14):
            time.sleep(2.0)
            if any(game.u32(panel) == SETUP for panel in game.panels()):
                break
            game.press("tap A 0.1")
        step("wager", "tap A 0.1", 2.0)
        # Each card has two copies, so ten take five places in the list.
        for number in range(1, 6):
            step(f"Y adds card {number}", "tap Y 0.1", 0.5)
            step(f"Y adds card {number}", "tap Y 0.1", 0.5)
            step("next card", "dpad down 0.1", 0.5)
        step("A plays", "tap A 0.1", 1.5)
        step("the box opens on Cancel: Up to OK", "dpad up 0.1", 0.8)
        step("A on OK", "tap A 0.1", 4.0)
        for number in range(1, 5):
            step(f"end turn {number}", "tap A 0.1", 3.5)
            step(f"X side {number}", "tap X 0.1", 2.0)
        step("B", "tap B 0.1", 2.0)
    finally:
        (VERIFY / f"paz-{args.label}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
