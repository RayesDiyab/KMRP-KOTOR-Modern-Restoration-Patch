#!/usr/bin/env python3
"""Give every listbox a top inset, so text doesn't start hard against the box.

Gold v11 (`build_listbox_padding_fix.py`) made `PADDING` a purely horizontal
inset. One of the three things it removed was the *vertical* one: vanilla
started the first row `PADDING` pixels down, but since the same byte also set
row pitch, raising it to open a top gap also spaced every row apart. v11 forced
the row-top chain's seed to zero instead, which is correct but leaves the first
line flush with the top of the content rect.

This restores a top inset as an **independent constant**, so it cannot bring the
row spacing back. Two sites, because there are two rect builders:

**Builder A** -- the content-fits path, patched in place, no size change:

    0041B48C  sub ecx, edi          ; right inset, once   (left alone)
    0041B48E  xor edi, edi   90     ; v11's zero seed
              ->  6A KK 5F          ; push KK / pop edi

Three bytes for three. `push imm8` sign-extends, so the range is 0..127, and
neither instruction touches flags. `edi` then flows to `0x0041B4A1`'s
`sub edi, ecx`, which seeds the row-top chain, so row 1 lands at `KK`.

**Builder B** -- the scrolling path, whose equivalent zero lives inside the
`.kgs` stub that `build_gutter_side_fix.py` writes:

    xor edi, edi ; test ebx, ebx ; jmp 0x0041A301
    ->  push KK ; pop edi ; test ebx, ebx ; jmp 0x0041A301

One byte longer, taken from the section's padding, with the jump displacement
recomputed. `edi` is read there by `sub ebx, edi` at `0x0041A35D` and
`sub edi, eax` at `0x0041A381`, the bottom-anchored and normal branches, so both
pick the inset up. The `test` stays last: `0x0041A30D`'s `je` consumes its
flags, and push/pop do not disturb them.

Patching only Builder A would inset short panes and not scrolling ones -- which
is exactly the asymmetry that located Builder B in the first place.

Requires an executable that already carries the v11 padding fix and the `.kgs`
gutter fix; it refuses otherwise rather than guessing.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


# Builder A: v11 leaves `xor edi, edi` + `nop` here.
FIT_VA = 0x0041B48E
FIT_ORIGINAL = bytes.fromhex("33ff90")

# Builder B: the tail of the second .kgs stub.
SCROLL_TAIL = bytes.fromhex("33ff85dbe9")     # xor edi,edi; test ebx,ebx; jmp rel32
SCROLL_RESUME = 0x0041A301


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--top-inset", type=int, required=True,
                        help="pixels of gap above the first row, 0..127")
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise SystemExit("Output must be a separate executable")
    if not 0 <= args.top_inset <= 127:
        raise SystemExit("--top-inset must be 0..127 (it is encoded as push imm8)")

    image = PEImage(args.source)
    data = bytearray(image.data)

    # --- Builder A -------------------------------------------------------
    actual, offset, section = image.read_va(FIT_VA, len(FIT_ORIGINAL))
    if actual != FIT_ORIGINAL:
        raise SystemExit(
            f"0x{FIT_VA:08X}: expected {FIT_ORIGINAL.hex(' ')} (gold v11's zero seed), "
            f"found {actual.hex(' ')} in {section}. Refusing to patch.")
    data[offset:offset + 3] = b"\x6A" + bytes([args.top_inset]) + b"\x5F"
    print(f"builder A  0x{FIT_VA:08X}  file 0x{offset:08X}  "
          f"xor edi,edi -> push {args.top_inset} / pop edi")

    # --- Builder B -------------------------------------------------------
    kgs = next((s for s in image.sections if s.name == ".kgs"), None)
    if kgs is None:
        raise SystemExit("Source has no .kgs section: apply build_gutter_side_fix.py first")
    kgs_va = image.image_base + kgs.virtual_address
    stub, kgs_offset, _ = image.read_va(kgs_va, kgs.virtual_size)
    at = stub.find(SCROLL_TAIL)
    if at < 0 or stub.find(SCROLL_TAIL, at + 1) >= 0:
        raise SystemExit("Expected exactly one 'xor edi,edi; test ebx,ebx; jmp' tail in .kgs")
    if kgs.virtual_size + 1 > kgs.raw_size:
        raise SystemExit("No padding left in .kgs to grow the stub by one byte")

    jmp_va = kgs_va + at + 5                       # push(2) + pop(1) + test(2)
    tail = (b"\x6A" + bytes([args.top_inset]) + b"\x5F"     # push KK ; pop edi
            + b"\x85\xDB"                                    # test ebx, ebx
            + b"\xE9" + struct.pack("<i", SCROLL_RESUME - (jmp_va + 5)))
    data[kgs_offset + at:kgs_offset + at + len(SCROLL_TAIL) + 4] = tail
    print(f"builder B  0x{kgs_va + at:08X}  file 0x{kgs_offset + at:08X}  "
          f"same, +1 byte, jmp 0x{SCROLL_RESUME:08X} rebased")

    # Grow .kgs's VirtualSize by the one byte the stub gained.
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    headers = coff + 20 + optional_size
    for index in range(section_count):
        slot = headers + index * 40
        if data[slot:slot + 4] == b".kgs":
            struct.pack_into("<I", data, slot + 8, kgs.virtual_size + 1)
            break
    else:
        raise SystemExit("Could not find the .kgs section header to update")

    args.output.write_bytes(data)

    out = PEImage(args.output)
    check, _, sec = out.read_va(FIT_VA, 3)
    if check != b"\x6A" + bytes([args.top_inset]) + b"\x5F" or sec != ".text":
        raise SystemExit("Verification failed: builder A")
    check, _, sec = out.read_va(kgs_va + at, len(tail))
    if check != tail or sec != ".kgs":
        raise SystemExit("Verification failed: builder B")

    print()
    print(f"{'top inset':<20} {args.top_inset} px")
    print(f"{'new file length':<20} {len(data)}")
    print(f"{'SHA-256':<20} {out.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
