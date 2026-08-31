#!/usr/bin/env python3
"""Stop list rows growing every time a listbox is re-populated.

`CAurGUIListBox`'s variable-height layout inflates its own row height on every
layout pass, so re-populating a list makes its rows taller without bound until
they hit the box-height clamp. Two sites do it, and both are patched here.

**Site 1 -- a row COUNT added to a row HEIGHT.**

    0041B465  idiv ecx                ; eax = how many rows fit in the box
    0041B488  mov [esp+18], eax       ; ...stashed
    ...
    0041B4FD  mov ebp,[esi+2B4]       ; ebp = the listbox's row height, in PIXELS
    0041B507  add ebp, edx            ; + that COUNT          <-- type confusion
    0041B522  mov [esp+2C], ebp       ; and that becomes the row's rect height

**Site 2 -- the remainder distribution.**

    0041B52C  lea edx,[ebp+1]         ; +1px on the first `ebx` rows

Either alone would be harmless if the result were discarded, but the layout
writes the inflated rect back into the row controls, and the *next* pass
recomputes `[listbox+0x2B4] = max(item->height)` (`0x0041B20D`) over those same,
now-taller, reused rows. That closes a feedback loop: every populate ratchets
the height up again.

`[+0x2B4]` *is* reset to 0 at `0x0041B1D6` each populate, which is why this was
so hard to see -- the reset is real, but the max immediately re-reads it back
out of row objects that were never rebuilt.

**This is a vanilla BioWare bug, not a mod bug.** Reproduced with an
`abilities.gui` byte-identical to the packed original. It is invisible at low
resolution only because growth is clamped by the box height, and a small box
clamps on the first pass; give the same list a 1324x510 box at 3440x1440 and it
ratchets visibly. Measured live on the Abilities screen's Powers tab, clicking
the tab repeatedly: `[listbox+0x2B4]` went 42 -> 56 -> 126. With this patch it
holds at 40, the rows' natural height.

The fix is deliberately minimal -- it removes the two inflations and nothing
else. Row *positions* still advance normally (that uses a separate accumulator
in `edi`), so lists lay out as before; they simply stop growing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from verify_map_patch import PEImage


# (virtual address, original bytes, replacement bytes, description)
PATCH_SITES = (
    (0x0041B507, "03 ea",    "90 90",    "add ebp,edx -> nop nop (row count added to row height)"),
    (0x0041B52C, "8d 55 01", "8d 55 00", "lea edx,[ebp+1] -> [ebp+0] (remainder distribution)"),
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

    for va, original, replacement, description in PATCH_SITES:
        want = bytes.fromhex(original.replace(" ", ""))
        new = bytes.fromhex(replacement.replace(" ", ""))
        if len(want) != len(new):
            raise SystemExit(f"Length mismatch at 0x{va:08X}")
        actual, offset, section = image.read_va(va, len(want))
        if actual != want:
            raise SystemExit(
                f"0x{va:08X}: expected {want.hex(' ')}, found {actual.hex(' ')} "
                f"(file 0x{offset:08X}, {section}). Refusing to patch -- this is "
                f"not the expected build, or the fix is already applied.")
        data[offset:offset + len(new)] = new
        print(f"{description}")
        print(f"    VA 0x{va:08X}  file 0x{offset:08X}  "
              f"{actual.hex(' ').upper()} -> {new.hex(' ').upper()}")

    args.output.write_bytes(data)

    output = PEImage(args.output)
    for va, _, replacement, _ in PATCH_SITES:
        new = bytes.fromhex(replacement.replace(" ", ""))
        reread, _, _ = output.read_va(va, len(new))
        if reread != new:
            raise SystemExit(f"Verification failed at 0x{va:08X}")
    if len(data) != len(image.data):
        raise SystemExit("Patch changed the file length; it must not")

    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
