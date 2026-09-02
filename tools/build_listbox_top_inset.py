#!/usr/bin/env python3
"""Give every listbox a top inset, so text doesn't start hard against the frame.

Gold v11 made `PADDING` purely horizontal; one of the things it dropped was
vanilla's top inset, because the same byte also set row pitch, so opening a top
gap also spaced every row apart. Gold v12 then moved each builder's `rect.top`
into its `.kgs` stub. That is where a top inset belongs, and this patch sets it
there -- as a constant independent of `PADDING`, so the row spacing cannot come
back with it.

**Both stubs, because there are two rect builders** (see
`reverse-engineering/listbox-geometry.md`): `0x0041B140` lays out rows when the
content fits, `0x0041A2D0` lays out a single item when it does not. Patching one
insets short panes and not scrolling ones -- the same asymmetry that originally
exposed builder B.

The rects sit at different stack offsets in the two builders:

    builder A   [esp+0x20 .. 0x2C] = {left, top, width, height}
    builder B   [esp+0x1C .. 0x28] = {left, top, width, height}

**Builder A** writes its top directly, so the inset is just its immediate:

    00872017  mov dword [esp+0x24], 0    ->  mov dword [esp+0x24], KK

An imm32 already, so no size change and no register touched.

**Builder B** never writes `[esp+0x20]`. Its top is derived from `edi` by
`sub ebx, edi` at `0x0041A35D` (bottom-anchored branch) and `sub edi, eax` at
`0x0041A381` (otherwise), which is why v12's stub clears `edi` there. Seeding it
with the inset instead reaches both branches:

    00872041  xor edi, edi   ->  push KK ; pop edi

One byte longer, taken from the section's padding, jump displacement recomputed.
`test ebx, ebx` stays last -- `0x0041A30D`'s `je` consumes its flags, and
push/pop do not disturb them. This runs after `sub ecx, edi` and the gutter
store, `edi`'s last two readers as `PADDING`.

**Do not do this in `.text` instead.** An earlier attempt replaced v11's
`xor edi, edi` at `0x0041B48E` with the same push/pop. That register is not
spare: `0x0041B48C` reads it for the width and `0x0041B4A1` seeds the row-top
chain from it, which is precisely why v12 wrote the zero to the stack slot
rather than clearing the register. The game crashed on launch. Both levers are
in `.kgs`; `.text` is left alone, and this tool verifies it is still v11's.

Requires an executable carrying gold v11 and v12; it refuses otherwise.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


# v11's zero seed. Must still be intact: this patch does NOT touch it.
V11_SEED_VA = 0x0041B48E
V11_SEED = bytes.fromhex("33ff90")

# Builder A's `mov dword [esp+0x24], imm32` inside the .kgs fit stub.
FIT_TOP = bytes.fromhex("c744242400000000")

# Builder B's seed, and where its stub returns to.
SCROLL_TAIL = bytes.fromhex("33ff85dbe9")     # xor edi,edi ; test ebx,ebx ; jmp rel32
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
        raise SystemExit("--top-inset must be 0..127 (builder B encodes it as push imm8)")

    image = PEImage(args.source)
    data = bytearray(image.data)

    seed, _, _ = image.read_va(V11_SEED_VA, len(V11_SEED))
    if seed != V11_SEED:
        raise SystemExit(
            f"0x{V11_SEED_VA:08X}: expected gold v11's {V11_SEED.hex(' ')}, found "
            f"{seed.hex(' ')}. That register must stay zero -- see this module's docstring.")

    kgs = next((s for s in image.sections if s.name == ".kgs"), None)
    if kgs is None:
        raise SystemExit("Source has no .kgs section: apply build_gutter_side_fix.py (v12) first")
    kgs_va = image.image_base + kgs.virtual_address
    stub, kgs_offset, _ = image.read_va(kgs_va, kgs.virtual_size)

    # --- Builder A: the fit stub's rect.top immediate ---------------------
    at = stub.find(FIT_TOP)
    if at < 0 or stub.find(FIT_TOP, at + 1) >= 0:
        raise SystemExit("Expected exactly one 'mov [esp+0x24], 0' in .kgs")
    struct.pack_into("<i", data, kgs_offset + at + 4, args.top_inset)
    print(f"builder A  0x{kgs_va + at:08X}  mov [esp+0x24], 0 -> {args.top_inset}")

    # --- Builder B: seed edi with the inset -------------------------------
    at = stub.find(SCROLL_TAIL)
    if at < 0 or stub.find(SCROLL_TAIL, at + 1) >= 0:
        raise SystemExit("Expected exactly one 'xor edi,edi; test ebx,ebx; jmp' tail in .kgs")
    if kgs.virtual_size + 1 > kgs.raw_size:
        raise SystemExit("No padding left in .kgs to grow the stub by one byte")
    jmp_va = kgs_va + at + 5                       # push(2) + pop(1) + test(2)
    tail = (b"\x6A" + bytes([args.top_inset]) + b"\x5F"
            + b"\x85\xDB"
            + b"\xE9" + struct.pack("<i", SCROLL_RESUME - (jmp_va + 5)))
    # The new tail is one byte longer than the old, and that byte comes from the
    # section's zero padding -- so OVERWRITE ten bytes rather than replacing the
    # old nine. Assigning a longer bytes to a shorter bytearray slice inserts,
    # which slides every following section's raw data by a byte and silently
    # wrecks .ktn, .kmz and .kfg. That crashed the game on launch, faulting
    # inside the displaced .ktn hook, and the length assert below is what would
    # have caught it.
    if data[kgs_offset + at + len(SCROLL_TAIL) + 4] != 0:
        raise SystemExit("The byte after the stub is not padding; refusing to grow into it")
    before = len(data)
    data[kgs_offset + at:kgs_offset + at + len(tail)] = tail
    if len(data) != before:
        raise SystemExit(f"Patch changed the file length ({before} -> {len(data)}); "
                         "section raw offsets would all be wrong")
    print(f"builder B  0x{kgs_va + at:08X}  xor edi,edi -> push {args.top_inset} / pop edi"
          f"  (+1 byte, jmp rebased)")

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
    check, _, sec = out.read_va(V11_SEED_VA, len(V11_SEED))
    if check != V11_SEED or sec != ".text":
        raise SystemExit("Verification failed: v11's seed in .text must be untouched")
    check, _, sec = out.read_va(kgs_va + at, len(tail))
    if check != tail or sec != ".kgs":
        raise SystemExit("Verification failed: builder B")

    print()
    print(f"{'top inset':<20} {args.top_inset} px")
    print(f"{'.text':<20} untouched")
    print(f"{'SHA-256':<20} {out.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
