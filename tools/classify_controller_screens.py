#!/usr/bin/env python3
"""Classify every GUI screen by how a controller navigates it.

Three answers, and the point of the exercise is that the first one wins wherever
it applies -- KMRP must not take over navigation the engine already does well.

  NATIVE  the panel's own dispatcher implements the direction events
          (0x2F / 0x30 / 0x31 / 0x32, or their 0x3D..0x40 aliases), so the
          retained console path navigates the screen unaided.

  HYBRID  the panel does not, but it is built around a control that does -- a
          list box, a navigable or a slider consumes the directions itself.
          Navigation *within* that control is native; moving focus on to it, or
          off it to the surrounding buttons, is KMRP's job.

  KMRP    neither. The screen is a set of buttons and nothing in the engine
          moves focus between them sensibly, so the spatial layer drives it.

The NATIVE set is read out of the retained-event inventory rather than typed in,
so it cannot drift away from what the binary actually implements. The HYBRID
call needs to know which controls a screen carries, which is a runtime fact; the
table below records it from live probing and is marked as such.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "reverse-engineering" / "retained-gui-event-inventory.txt"

DIRECTION_EVENTS = {0x2F, 0x30, 0x31, 0x32, 0x3D, 0x3E, 0x3F, 0x40}

# Screens the request named, mapped to the inventory's panel names. A screen
# that is not a panel in its own right says so.
REQUESTED = {
    "Main Menu": "MAIN_MENU",
    "Inventory": "INVENTORY",
    "Character": "CHARACTER",
    "Skills": "SKILLS",
    "Feats": "FEATS",
    "Powers": "POWERS",
    "Equipment": "EQUIP",
    "Journal": "JOURNAL",
    "Map": "MAP",
    "Options": "OPTIONS_MAIN",
    "Save": "SAVELOAD",
    "Load": "SAVELOAD",
    "Dialogue": None,
    "Merchant": "STORE",
    "Containers": "CONTAINER",
    "Level-up": "LEVEL_UP",
    "Party select": "PARTY_SELECT",
}

# Screens observed live to be built around a control that consumes the
# directions itself. Probed with testing/controller/, not inferred: a list box's
# dispatcher is CSWGuiListBox::HandleInputEvent at 0x0041CE20.
KNOWN_LIST_SCREENS = {
    "INVENTORY", "JOURNAL", "STORE", "CONTAINER", "SAVELOAD", "EQUIP",
    "UPGRADE", "UPGRADE_ITEM_SELECT", "MESSAGES", "KEY_MAPPINGS",
}

# Screens with no panel of their own.
NOT_A_PANEL = {
    "Dialogue": "runs on the in-game GUI, not a panel of its own; entries are a "
                "list box on CGuiInGame and the retained events reach it",
}


def read_inventory(path: Path) -> dict:
    panels = {}
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        header = re.match(r"^(\S+)\s+dispatcher (0x[0-9A-Fa-f]+)", line)
        if header:
            current = header.group(1)
            panels[current] = {"dispatcher": int(header.group(2), 16), "events": set()}
            continue
        body = re.search(r"<- (.+)$", line)
        if body and current:
            for token in body.group(1).split(","):
                token = token.strip()
                if token.startswith("0x"):
                    panels[current]["events"].add(int(token, 16))
    return panels


def classify(name: str, info: dict) -> tuple:
    directions = sorted(info["events"] & DIRECTION_EVENTS)
    if directions:
        return "NATIVE", "panel implements " + ", ".join(hex(d) for d in directions)
    if name in KNOWN_LIST_SCREENS:
        return "HYBRID", "built around a list box; KMRP moves focus on and off it"
    return "KMRP", "buttons only; spatial navigation drives it"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true",
                        help="every panel, not just the ones the survey named")
    arguments = parser.parse_args()

    if not INVENTORY.exists():
        print(f"missing {INVENTORY}; run tools/map_retained_gui_events.py --full")
        return 1
    panels = read_inventory(INVENTORY)

    rows = []
    if arguments.all:
        for name in sorted(panels):
            kind, why = classify(name, panels[name])
            rows.append((name, name, kind, why))
    else:
        for label, panel in REQUESTED.items():
            if panel is None:
                rows.append((label, "-", "NATIVE", NOT_A_PANEL[label]))
            elif panel not in panels:
                rows.append((label, panel, "?", "no such panel in the inventory"))
            else:
                kind, why = classify(panel, panels[panel])
                rows.append((label, panel, kind, why))

    width = max(len(r[0]) for r in rows)
    counts = {}
    for label, panel, kind, why in rows:
        counts[kind] = counts.get(kind, 0) + 1
        print(f"  {label:<{width}}  {kind:<7}  {panel:<22} {why}")
    print()
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
