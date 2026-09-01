#!/usr/bin/env python3
"""Make a listbox's `PADDING` a purely horizontal left inset.

`CAurGUIListBox`'s layout function reads the GUI's `PADDING` byte
(`[listbox+0x2C0]`) for **four** different jobs. Read out of the binary:

    0041B44C  movzx edi, byte [esi+0x2C0]   ; edi = PADDING
    0041B46D  mov  [esp+0x20], edi          ; rect.left   = PADDING      (1)
    0041B482  mov  ecx, [esi+0x294]         ; content width
    0041B48C  lea  eax, [edi+edi]           ; 2 * PADDING
    0041B48F  sub  ecx, eax                 ; rect.width -= 2*PADDING    (2)
    0041B4A1  sub  edi, ecx                 ; first row's top starts at
                                            ; PADDING - count*pitch,
                                            ; so row 1 lands at PADDING  (3)

and, in three separate places, as vertical row pitch:

    0041B1C4  add ebp, edi                  ; pitch = rowHeight + PADDING
    0041B26B  add edi, ecx                  ;   "   (also the divisor for
                                            ;        the visible row count)
    0041B553  add ecx, ebp                  ;   "   (advances each row top)

Only (1) is wanted. `PADDING` is the natural field for a gutter beside the
scrollbar -- confirmed in game, a listbox with `PADDING = 25` gets exactly 25px
between its scrollbar and its icons -- but vanilla ties three unwanted effects
to the same byte, so raising it also spaces the rows apart, insets the right
edge and pushes the whole list down.

This patch removes the three unwanted uses, all in place, no size change:

  * the three pitch sites become `mov`, so pitch is `rowHeight` alone;
  * `0x0041B48C` becomes `sub ecx, edi` + `xor edi, edi`, which subtracts
    PADDING once instead of twice (right edge unchanged) and then clears the
    register the row-top chain starts from (no gap above the first row).
    `edi`'s only earlier use, `rect.left`, is already stored by then.

Two further sites (`0x0041B326`, `0x0041B39B`) add `PADDING` to `rowHeight` to
test whether one row fits in the box, deciding scrollbar visibility. They are
deliberately left alone: they do not affect layout.

Side effect: every listbox with a non-zero vanilla `PADDING` loses that many
pixels of row spacing and gains the same left inset -- `LB_FEATS` 4,
`LB_GAMES`/`LB_MESSAGES`/`LB_MODULES`/`LB_OPTIONS` 5, `LB_REPLIES` 3,
`LB_MESSAGE` 2-3, `LB_SKILLS`/`LST_AIState` 2, some `LB_ITEMS` 1-2.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from verify_map_patch import PEImage


# (VA, original bytes, patched bytes, what it does)
PATCH_SITES = (
    (0x0041B1C4, "03ef", "8bef",
     "add ebp,edi -> mov ebp,edi   (pitch #1: initial)"),
    (0x0041B26B, "03f9", "8bf9",
     "add edi,ecx -> mov edi,ecx   (pitch #2: visible-row divisor; overwrites #1)"),
    (0x0041B553, "03cd", "8bcd",
     "add ecx,ebp -> mov ecx,ebp   (pitch #3: advances each row's top)"),
    (0x0041B48C, "8d043f2bc8", "2bcf33ff90",
     "lea eax,[edi+edi]; sub ecx,eax -> sub ecx,edi; xor edi,edi; nop"
     "   (right inset once, not twice; row tops start at 0)"),
    # The two "does the content fit?" tests, which choose between the row
    # layout and the single-item scrolling layout at 0x0041A2D0. Both compute
    # PADDING + rowHeight and compare it against the box height, so a pane whose
    # text fits can still be routed to the scrolling layout -- which then
    # bottom-anchors it and leaves a gap on top. Measured live: an equipped
    # robe's description, rowHeight 320 in a 342-tall box, tested as 72 + 320 =
    # 392 > 342 and came out 22px down the box. PADDING is a horizontal inset
    # now, so it has no business in a vertical fit test.
    (0x0041B339, "03c2", "8bc2",
     "add eax,edx -> mov eax,edx   (fit test: rowHeight alone)"),
    (0x0041B3AE, "03c2", "8bc2",
     "add eax,edx -> mov eax,edx   (fit test: rowHeight alone)"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise SystemExit("Output must be a separate executable")

    image = PEImage(args.source)
    data = bytearray(image.data)

    for va, original, _, _ in PATCH_SITES:
        expected = bytes.fromhex(original)
        actual, offset, section = image.read_va(va, len(expected))
        if actual != expected:
            raise SystemExit(
                f"0x{va:08X}: expected {expected.hex(' ')}, found {actual.hex(' ')} "
                f"(file 0x{offset:08X}, {section}). Refusing to patch.")

    for va, original, patched, what in PATCH_SITES:
        replacement = bytes.fromhex(patched)
        _, offset, _ = image.read_va(va, len(replacement))
        data[offset:offset + len(replacement)] = replacement
        print(f"0x{va:08X}  file 0x{offset:08X}  "
              f"{bytes.fromhex(original).hex(' ')} -> {replacement.hex(' ')}  {what}")

    if len(data) != len(image.data):
        raise SystemExit("Patch changed the file length")
    args.output.write_bytes(bytes(data))

    out = PEImage(args.output)
    for va, _, patched, _ in PATCH_SITES:
        expected = bytes.fromhex(patched)
        actual, _, _ = out.read_va(va, len(expected))
        if actual != expected:
            raise SystemExit(f"Verification failed at 0x{va:08X}")
    print()
    print(f"SHA-256: {out.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
