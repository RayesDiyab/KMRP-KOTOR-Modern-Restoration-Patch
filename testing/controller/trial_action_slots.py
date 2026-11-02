#!/usr/bin/env python3
"""What pad A does on each action slot, on the running game (PAD-2, PAD-3).

Loads the save `build_combat_fixture.py` made, held by the game's own pause on sighting an enemy:
`Enemy Sighted=1` under `[Autopause Options]` in its `swkotor.ini`. Fresh launch, pad only. Each step
presses once and reads `queue N actions M` from the module's level 2 lines. A press on a slot that
adds nothing, or adds two, is the defect. The queue can show a slot's action only while combat runs:
an item used on oneself leaves the queue alone, so its frame is saved as well.

Needs `debug-logs=2` in the game's `configs\\kmrp-controller.ini`. Writes `build/verify/slots-*.png`
and `build/verify/slots-<label>.json`. Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import json
import re
import time

from live_harness import VERIFY
from live_session import Session


def numbers(session: Session, mark: int) -> list[tuple[int, int]]:
    found = (re.search(r"queue (\d+) actions (-?\d+)", line) for line in session.events(mark, " queue "))
    return [(int(m.group(1)), int(m.group(2))) for m in found if m]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    session = Session()
    game = session.game
    rows: list = []

    def step(name: str, command: str):
        mark = session.mark()
        game.press(command)
        time.sleep(0.9)
        row = {"step": name, "queue": numbers(session, mark), "top": game.top()}
        rows.append(row)
        print(json.dumps(row), flush=True)
        game.shot(VERIFY / f"slots-{len(rows):02d}.png")

    try:
        session.boot()
        session.load_newest_save()
        time.sleep(5)
        step("default A", "tap A 0.1")
        step("Right: feats", "dpad right 0.1")
        step("A on feats", "tap A 0.1")
        # PAD-2: Force Push's slot has one entry and no arrows, so this is the slot that can show it.
        step("Down straight after A", "dpad down 0.1")
        step("Up straight after A", "dpad up 0.1")
        step("Right: Force power", "dpad right 0.1")
        step("A on Force power, 1", "tap A 0.1")
        step("A on Force power, 2", "tap A 0.1")
        # The queue holds four, so a slot further along is only measured with room left.
        for number in range(1, 4):
            step(f"Y makes room, {number}", "tap Y 0.1")
        step("X on the slot", "tap X 0.1")
        step("Y makes room", "tap Y 0.1")
        step("Right: grenade", "dpad right 0.1")
        step("A on grenade", "tap A 0.1")
        step("Y makes room", "tap Y 0.1")
        step("Right: own power", "dpad right 0.1")
        step("A on own power", "tap A 0.1")
        step("Y makes room", "tap Y 0.1")
        step("Right: defensive item", "dpad right 0.1")
        step("A on defensive item", "tap A 0.1")
        for number in range(1, 5):
            step(f"Y removes, {number}", "tap Y 0.1")
    finally:
        (VERIFY / f"slots-{args.label}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
