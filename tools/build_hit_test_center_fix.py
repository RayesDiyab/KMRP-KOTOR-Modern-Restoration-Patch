#!/usr/bin/env python3
"""Re-centre the area map's hit test on the overlay instead of the canvas.

**The symptom.** After the Option D surface change (see
`reverse-engineering/area-map-surface.md`), the map draws in the right place but
clicks land 141 px to the right of where you point at 3440x1440. Map notes are
selected by pointing to their left.

**The cause.** The hit-test wrapper at `0x0086D100` converts window mouse
coordinates into map-local ones by assuming the map canvas is *centred in the
window*:

    0086D107  mov edx, [eax+0x0C]      ; window width   3440
    0086D10A  sub edx, [eax+0x108C]    ; - canvas width 2001
    0086D110  sar edx, 1               ; = 719
    0086D112  sub [esp+4], edx         ; mouse x

Measured live with x64dbg, a click at screen (1445, 913) reaches the wrapper as
(1651, 766) and leaves as (932, 392), confirming the 719.

That assumption held while the canvas *was* centred. Option D sets
`centringX = screenWidth`, which puts the canvas origin at `LBL_Map.left`, and
`LBL_Map` is placed by the **overlay** width, not the canvas width -- the canvas
is wider and overhangs to the right, where `LBL_Map` crops it. The correct inset
is therefore

    LBL_Map.left = (windowWidth - overlayWidth) / 2 = (3440 - 1720) / 2 = 860

against the 719 the wrapper computes: **141 px of error**, which is exactly
`(canvas - overlay) / 2 = (2001 - 1720) / 2`.

**The fix.** Option D's rule is `overlay = screenWidth // 2`, and `[eax+0x0C]`
holds the window width, so the inset collapses to a constant-free shift:

    (W - W/2) / 2  ==  W / 4  ==  sar edx,1 ; sar edx,1

No field lookup, no multiply, and correct at every resolution by construction --
including odd widths, where integer division and `sar` agree (1366 -> 683 -> 341,
and `(1366 - 683) / 2 = 341`).

    8B 50 0C  2B 90 8C 10 00 00  D1 FA        mov edx,[eax+0Ch]; sub edx,[eax+108Ch]; sar edx,1
    8B 50 0C  D1 FA  D1 FA  90 90 90 90       mov edx,[eax+0Ch]; sar edx,1; sar edx,1

Eleven bytes replaced by eleven, so the wrapper does not move and neither the
section nor the vtable slot at `0x0075477C` needs touching.

**The Y half is left alone.** It computes `(1440 - 720) / 2 + 14 = 374`, which is
exactly `LBL_Map.top`, and was measured correct in the same breakpoint session.
It is already right because the overlay and canvas heights are equal
(`screenHeight // 2`), so centring on either gives the same answer. Only the
widths differ, which is why only X was wrong.

Address convention: `FILE = VA - 0x492000` for the appended `.kui` section.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

KUI_FILE_DELTA = 0x492000
HIT_TEST_X_BLOCK_VA = 0x0086D107

EXPECTED = bytes.fromhex("8b500c" "2b908c100000" "d1fa")
REPLACEMENT = bytes.fromhex("8b500c" "d1fa" "d1fa" "90909090")

assert len(EXPECTED) == len(REPLACEMENT) == 11


def patch(data: bytearray) -> None:
    offset = HIT_TEST_X_BLOCK_VA - KUI_FILE_DELTA
    found = bytes(data[offset:offset + len(EXPECTED)])
    if found != EXPECTED:
        raise SystemExit(
            f"0x{HIT_TEST_X_BLOCK_VA:08X}: expected {EXPECTED.hex(' ')}, "
            f"found {found.hex(' ')}. Refusing to patch.")
    data[offset:offset + len(REPLACEMENT)] = REPLACEMENT
    print(f"  0x{HIT_TEST_X_BLOCK_VA:08X}  hit-test X inset: "
          f"(window - canvas)/2  ->  window/4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.output.resolve() == args.source.resolve():
        raise SystemExit("refusing to patch in place")

    data = bytearray(args.source.read_bytes())
    before = len(data)
    patch(data)
    assert len(data) == before, "in-place patch changed the file length"
    args.output.write_bytes(bytes(data))
    print(f"\nfile length {len(data)} (unchanged)")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
