#!/usr/bin/env python3
"""A on a focused action slot goes to the slot's icon (PAD-3).

The focus sits on the slot's frame, at offset 0, which has no handler for 0x27. The engine registers
that event on the icon alone, so A sent to the frame did nothing. This holds K1XboxControls.cpp to
the icon, and to the offset the Xbox-style HUD has no other way to check. The real game's case is
`testing/controller/trial_action_slots.py`. No game runs here.
Run: python testing/regression/Test-ActionSlotEvent.py
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    text = (ROOT / "src/controller-native/K1XboxControls.cpp").read_text(encoding="utf-8")
    failed = False
    if not re.search(r"ACTION_SLOT_ICON_OFFSET = 0x0*1C4;", text):
        print("FAIL the icon's offset in a slot is not 0x1C4")
        failed = True
    if "SendControlEventK1(OffsetPointer(buttons[activeIndex], ACTION_SLOT_ICON_OFFSET), 0x27);" not in text:
        print("FAIL A no longer goes to the slot's icon")
        failed = True
    if "SendControlEventK1(buttons[activeIndex], 0x27)" in text:
        print("FAIL A goes to the slot's frame, which has no handler for it")
        failed = True
    if failed:
        return 1
    print("OK A on a slot goes to its icon")
    return 0


if __name__ == "__main__":
    sys.exit(main())
