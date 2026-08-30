#!/usr/bin/env python3
"""Fix the word-wrap infinite loop that any enlarged font triggers.

`CAurGUIString`'s line-breaking function (`0x0045A2F0`) breaks an over-long
line that contains no space by backing the cursor up one character and
restarting the line there. Its only termination guard compares the cursor
against the start of the whole *string*:

    0045A5E0  mov eax,[esi+14]     ; eax = start of the STRING
    0045A5E3  dec ebx              ; back up one character
    0045A5E4  cmp ebx,eax
    0045A5EA  je  0045A834         ; bail out only if we are at the string start

That is the wrong reference point. When the cursor lands back on the start of
the current *line* -- not the string -- the guard does not fire, the line
restarts at exactly the position it began at, and the function loops forever,
appending a line-break entry every pass. Each append grows two arrays by
doubling until the allocator cannot satisfy the request; the grow helper at
`0x005E03C0` does not check the returned pointer, so the game dies writing
through NULL. Observed live: 33.5 million entries appended, a 268MB request,
then the crash.

Why an enlarged font sets it off, measured live against the shipped
`inventory.gui`: the item stack-count label is **21 pixels** wide, and its
text is a bare number, so there is never a space to break on. The widest pair
of stock digits is **20px** -- vanilla clears the limit by a single pixel.
Scaling the font at all pushes two digits past 21px (ours: 22px, and 55 of
the 100 digit pairs overflow), so a stack of e.g. "159" hits the loop as soon
as Inventory draws it. The label's own `[esi+0x40]` width multiplier reads
1.0, so nothing is inflating the metrics -- the glyphs are simply, correctly,
bigger. **This is not fixable from the font side**: any universal font
scaling collides with a control sized to vanilla's one-pixel margin.

The replacement keeps the cursor moving forward instead of bailing out:

    dec  ebx
    cmp  ebx,[esp+18]    ; [esp+18] is the current LINE's start
    mov  [esp+10],ecx    ; (preserved from the original)
    ja   +5              ; cursor still past the line start -- fine
    mov  ebx,[esp+18]    ; otherwise snap to lineStart + 1 so the line
    inc  ebx             ;   always consumes at least one character

Every line now advances the cursor by at least one character, so the line
start increases monotonically and the loop always terminates. Unlike the
engine's own bail-out at `0x0045A834` -- which zeroes both entry counts and
therefore draws nothing at all -- the text still renders, merely overflowing
its too-narrow label by a pixel or two.

The replacement is exactly the same 16 bytes it overwrites, so this patches in
place with no new PE section and no trampoline. `eax`, which the original
loaded and this does not, is dead: the fall-through at `0x0045A5F0`
immediately overwrites it with `movzx eax, byte ptr [ebx]`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from verify_map_patch import PEImage


HOOK_VA = 0x0045A5E0

ORIGINAL = bytes.fromhex("8B4614" "4B" "3BD8" "894C2410" "0F84440200 00".replace(" ", ""))

REPLACEMENT = bytes.fromhex(
    "4B"          # dec  ebx
    "3B5C2418"    # cmp  ebx, [esp+0x18]      ; current line's start
    "894C2410"    # mov  [esp+0x10], ecx      ; original side effect, preserved
    "7705"        # ja   +5                   ; past line start -> keep going
    "8B5C2418"    # mov  ebx, [esp+0x18]
    "43"          # inc  ebx                  ; -> lineStart + 1
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")
    if len(REPLACEMENT) != len(ORIGINAL):
        raise ValueError(
            f"Replacement must be exactly {len(ORIGINAL)} bytes, got {len(REPLACEMENT)}"
        )

    image = PEImage(args.source)
    actual, offset, section = image.read_va(HOOK_VA, len(ORIGINAL))
    if actual != ORIGINAL:
        raise ValueError(
            f"Word-wrap guard: expected {ORIGINAL.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{HOOK_VA:08X} (file 0x{offset:08X}, {section})"
        )
    print(f"{'Word-wrap progress guard':<34} VA 0x{HOOK_VA:08X}  file 0x{offset:08X}")
    print(f"{'  original':<34} {ORIGINAL.hex(' ').upper()}")
    print(f"{'  replacement':<34} {REPLACEMENT.hex(' ').upper()}")

    data = bytearray(image.data)
    data[offset : offset + len(ORIGINAL)] = REPLACEMENT
    args.output.write_bytes(data)

    output = PEImage(args.output)
    reread, _, _ = output.read_va(HOOK_VA, len(REPLACEMENT))
    if reread != REPLACEMENT:
        raise ValueError("Verification failed: patched bytes did not read back")

    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
