#!/usr/bin/env python3
"""What each combat button does to the player's queue, on the running game (PAD-1, 2, 3, issues 88, 90).

Loads the save `build_combat_fixture.py` made, in the game's own pause on sighting an enemy, so the
queue holds still and can be counted. Fresh launch, pad only: no mouse click, which is what hid
PAD-1. Each step presses once and reads `queue N` from the module's level 2 lines, and the button
edges it sent. A press that adds or removes two is the defect.

Needs `debug-logs=2` in the game's `configs\\kmrp-controller.ini`, tutorials off in its `swkotor.ini`,
and that save the only one in its `Saves`. Writes `build/verify/combat-<label>.json`.
Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import argparse
import json
import re
import time

from live_harness import VERIFY, Pad
from live_session import Session


def queue(session: Session, mark: int, known: int | None) -> int | None:
    values = [int(m.group(1)) for line in session.events(mark, " queue ") for m in [re.search(r"queue (\d+)", line)] if m]
    return values[-1] if values else known


def step(session: Session, name: str, command: str, known: int | None, rows: list, settle: float = 0.7) -> int | None:
    mark = session.mark()
    session.game.press(command)
    time.sleep(settle)
    now = queue(session, mark, known)
    edges = [line.split(" ", 1)[1] for line in session.events(mark, " press class", " release class")]
    row = {"step": name, "before": known, "after": now, "edges": edges, "top": session.game.top(),
           "class": session.input_class()}
    rows.append(row)
    print(json.dumps(row), flush=True)
    return now


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="run")
    parser.add_argument("--wait", type=float, default=5.0, help="seconds after loading")
    args = parser.parse_args()
    session = Session()
    game = session.game
    rows: list = []
    try:
        session.boot()
        session.load_newest_save()
        time.sleep(args.wait)
        game.shot(VERIFY / f"combat-{args.label}-start.png")
        known = queue(session, 0, None)
        print("start", game.panel_names(), "queue", known)
        known = step(session, "focus a slot: D-pad Right", "dpad right 0.1", known, rows)
        for number in range(1, 3):
            known = step(session, f"A on the slot, {number}", "tap A 0.1", known, rows)
        game.shot(VERIFY / f"combat-{args.label}-queued.png")
        known = step(session, "D-pad Down after A", "dpad down 0.1", known, rows)
        known = step(session, "D-pad Up after A", "dpad up 0.1", known, rows)
        known = step(session, "X uses the slot", "tap X 0.1", known, rows)
        known = step(session, "Y removes the last", "tap Y 0.1", known, rows)
        known = step(session, "Y removes the next", "tap Y 0.1", known, rows)
        known = step(session, "B lets go of the slot", "tap B 0.1", known, rows)
        known = step(session, "A, the default action", "tap A 0.1", known, rows)
        known = step(session, "B disengages", "tap B 0.1", known, rows)
        game.shot(VERIFY / f"combat-{args.label}-end.png")
    finally:
        (VERIFY / f"combat-{args.label}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
