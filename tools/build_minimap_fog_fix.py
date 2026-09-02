#!/usr/bin/env python3
"""Zoom the HUD minimap's fog grid to match the zoomed map.

**The symptom.** With `build_minimap_zoom_fix.py` applied, explored ground
re-fogs as soon as it leaves the middle of the minimap: the cleared area behaves
like a fixed window travelling with the player instead of the ground you have
actually walked.

**Why.** The fog is a separate draw with a scale basis of its own.
`0x0068AC9F` calls `0x00688100`, which walks the explored bitset --

    006882B7  and ecx, 0x8000001F
    006882D9  sar eax, 5
    006882DC  test dword ptr [edx + eax*4], ecx

-- and emits one quad per unexplored 4-unit tile. Its coordinates come from

    [0x00747748] = 440.0     the area map's viewport width
    [0x007455D4] = 256.0     ... and height

divided by `[edi+0x6088]` / `[edi+0x608C]`, the live minimap viewport. Both
constants are exactly KPM's `AreaMapViewportWidth` / `AreaMapViewportHeight`.

The map, meanwhile, is sized by `LBL_MAP`'s extent against the same viewport over
at `0x00459920`. In vanilla, at a 120 viewport, the two agree. Enlarging
`LBL_MAPVIEW` to 270 shrinks both by 2.25, so they still agree -- an unpatched
KMRP build looks consistent, merely zoomed out. The `.kmz` patch then restores
the *map* to vanilla's ratio and leaves the fog at 1/2.25 of it.

**The correction**, derived rather than guessed. Writing `s = W / B` for the
zoom the `.kmz` stub applies, `c = W / 2` for the viewport centre, `x` for the
pan and `u` for a map unit, the map puts unit `u` at normalised

    X_map(u) = [c + (x - c) * s + u * s] / W  =  1/2 + (x - c) / B + u / B

and the fog, dividing by `D` from an origin `px`, puts it at `(px + u) / D`.
Equating for all `u` gives

    D  = B                    so write B into hud+0x6088 / hud+0x608C
    px = x - (W - B) / 2      so shift the pan point by half the excess

At W = 270, B = 120 that shift is 75, which is what KPM's
`beginHudMinimapGridZoom` uses -- two independent routes to the same number.

**How.** `0x0068AC9F` is replaced by a call to a wrapper in a new `.kfg`
section. The call is `thiscall` with `ecx` = the HUD and one stack argument, a
pointer to the two pan ints (`0x00688100` reads them as `fild [ebp]` and
`fild [ebp+4]`); the callee cleans it with `ret 4`, so the wrapper does too. The
wrapper shifts the point, swaps the two viewport fields, calls the original,
then puts all four values back, so nothing downstream sees the substitution --
`0x0068ACA4` draws the player arrow from `esi+0x5F40` immediately afterwards and
must still see the real viewport.

Gated the same way as the zoom stub: the viewport must be square and larger than
the basis. Failing that it calls straight through, so the worst case is vanilla
behaviour.

**The basis must match the exe's zoom basis.** Pass the same `--zoom-basis` you
gave `build_minimap_zoom_fix.py`, or the fog will be corrected to the wrong
scale.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".kfg\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read

SITE_VA = 0x0068AC9F                  # call 0x688100, the fog grid draw
FOG_DRAW_VA = 0x00688100
ORIGINAL = bytes.fromhex("e85cd4ffff")  # call 0x688100

HUD_VIEW_W = 0x6088                   # hud+0x6088 / +0x608C: the live minimap viewport
HUD_VIEW_H = 0x608C

BASE_VIEWPORT = 120
MAX_VIEWPORT = 2048


def build_stub(stub_va: int, basis: int) -> bytes:
    body = bytearray()
    plain_fixups: list[int] = []
    done_fixups: list[int] = []

    def jcc_plain(opcode: bytes) -> None:
        body.extend(opcode)
        plain_fixups.append(len(body))
        body.extend(b"\x00\x00\x00\x00")

    def call_original() -> None:
        body.extend(b"\xFF\x75\x08")                                # push [ebp+8]
        body.extend(b"\x8B\xCE")                                    # mov  ecx, esi
        body.extend(b"\xE8")
        body.extend(struct.pack("<i", FOG_DRAW_VA - (stub_va + len(body) + 4)))

    body += b"\x55"                                                 # push ebp
    body += b"\x8B\xEC"                                             # mov  ebp, esp
    body += b"\x53\x56\x57"                                         # push ebx, esi, edi
    body += b"\x8B\xF1"                                             # mov  esi, ecx   (hud)
    body += b"\x8B\x7D\x08"                                         # mov  edi, [ebp+8] (point)

    body += b"\x8B\x86" + struct.pack("<I", HUD_VIEW_W)             # mov  eax, [esi+6088]
    body += b"\x8B\xD8"                                             # mov  ebx, eax   (W)
    body += b"\x3B\x86" + struct.pack("<I", HUD_VIEW_H)             # cmp  eax, [esi+608C]
    jcc_plain(b"\x0F\x85")                                          # jne  plain
    body += b"\x83\xF8" + bytes([basis + 1])                        # cmp  eax, basis+1
    jcc_plain(b"\x0F\x8C")                                          # jl   plain
    body += b"\x3D" + struct.pack("<I", MAX_VIEWPORT)               # cmp  eax, 2048
    jcc_plain(b"\x0F\x8F")                                          # jg   plain

    # ecx = (W - basis) / 2, the amount the pan must move
    body += b"\x8B\xC8"                                             # mov  ecx, eax
    body += b"\x81\xE9" + struct.pack("<I", basis)                  # sub  ecx, basis
    body += b"\xD1\xF9"                                             # sar  ecx, 1
    body += b"\x29\x0F"                                             # sub  [edi], ecx
    body += b"\x29\x4F\x04"                                         # sub  [edi+4], ecx

    body += b"\x8B\x96" + struct.pack("<I", HUD_VIEW_H)             # mov  edx, [esi+608C]
    body += b"\x52"                                                 # push edx   (H)
    body += b"\x53"                                                 # push ebx   (W)
    body += b"\xC7\x86" + struct.pack("<I", HUD_VIEW_W) + struct.pack("<I", basis)
    body += b"\xC7\x86" + struct.pack("<I", HUD_VIEW_H) + struct.pack("<I", basis)

    call_original()

    body += b"\x58"                                                 # pop eax  (W)
    body += b"\x89\x86" + struct.pack("<I", HUD_VIEW_W)             # mov [esi+6088], eax
    body += b"\x58"                                                 # pop eax  (H)
    body += b"\x89\x86" + struct.pack("<I", HUD_VIEW_H)             # mov [esi+608C], eax
    body += b"\x8B\xCB"                                             # mov ecx, ebx
    body += b"\x81\xE9" + struct.pack("<I", basis)                  # sub ecx, basis
    body += b"\xD1\xF9"                                             # sar ecx, 1
    body += b"\x01\x0F"                                             # add [edi], ecx
    body += b"\x01\x4F\x04"                                         # add [edi+4], ecx
    body += b"\xE9"
    done_fixups.append(len(body))
    body += b"\x00\x00\x00\x00"                                     # jmp done

    plain_at = len(body)
    call_original()

    done_at = len(body)
    body += b"\x5F\x5E\x5B"                                         # pop edi, esi, ebx
    body += b"\x5D"                                                 # pop ebp
    body += b"\xC2\x04\x00"                                         # ret 4

    for fixup in plain_fixups:
        struct.pack_into("<i", body, fixup, plain_at - (fixup + 4))
    for fixup in done_fixups:
        struct.pack_into("<i", body, fixup, done_at - (fixup + 4))
    return bytes(body)


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--zoom-basis", type=int, default=BASE_VIEWPORT,
                        help="must match the basis the .kmz zoom stub was built with")
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise SystemExit("Output must be a separate executable")
    if not 16 <= args.zoom_basis <= 126:
        raise SystemExit("--zoom-basis must be 16..126 (the gate compares against an imm8)")

    image = PEImage(args.source)
    actual, offset, section = image.read_va(SITE_VA, len(ORIGINAL))
    if actual != ORIGINAL:
        raise SystemExit(
            f"0x{SITE_VA:08X}: expected\n  {ORIGINAL.hex(' ')}\nfound\n  {actual.hex(' ')}\n"
            f"(file 0x{offset:08X}, {section}). Refusing to patch.")
    if any(s.name == ".kfg" for s in image.sections):
        raise SystemExit("Source already contains a .kfg section")
    if not any(s.name == ".kmz" for s in image.sections):
        raise SystemExit("Source has no .kmz section: the fog only desynchronises "
                         "once the map is zoomed, so apply build_minimap_zoom_fix.py first")

    data = bytearray(image.data)

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    header_slot = optional + optional_size + section_count * 40
    file_alignment = struct.unpack_from("<I", data, optional + 36)[0]
    section_alignment = struct.unpack_from("<I", data, optional + 32)[0]

    if header_slot + 40 > image.size_of_headers:
        raise SystemExit("No room for another PE section header")

    last = max(image.sections, key=lambda s: s.virtual_address)
    new_rva = align(last.virtual_address + max(last.virtual_size, last.raw_size),
                    section_alignment)
    stub_va = image.image_base + new_rva
    stub = build_stub(stub_va, args.zoom_basis)

    patch = b"\xE8" + struct.pack("<i", stub_va - (SITE_VA + 5))
    data[offset:offset + len(ORIGINAL)] = patch
    print(f"0x{SITE_VA:08X}  file 0x{offset:08X}  call 0x{FOG_DRAW_VA:08X} "
          f"-> call 0x{stub_va:08X}")

    raw_offset = align(len(data), file_alignment)
    raw_size = align(len(stub), file_alignment)
    struct.pack_into("<H", data, coff + 2, section_count + 1)
    size_of_code = struct.unpack_from("<I", data, optional + 4)[0]
    struct.pack_into("<I", data, optional + 4, size_of_code + raw_size)
    struct.pack_into("<I", data, optional + 56,
                     align(new_rva + len(stub), section_alignment))
    struct.pack_into("<I", data, optional + 64, 0)
    header = struct.pack("<8sIIIIIIHHI", SECTION_NAME, len(stub), new_rva,
                         raw_size, raw_offset, 0, 0, 0, 0, SECTION_CHARACTERISTICS)
    data[header_slot:header_slot + 40] = header
    if len(data) < raw_offset:
        data.extend(b"\0" * (raw_offset - len(data)))
    stub_file_offset = len(data)
    data.extend(stub)
    data.extend(b"\0" * (raw_size - len(stub)))

    args.output.write_bytes(data)

    out = PEImage(args.output)
    reread, _, sec = out.read_va(stub_va, len(stub))
    if reread != stub or sec != ".kfg":
        raise SystemExit("Verification failed: stub contents/section")

    print(f"{'stub (.kfg)':<20} VA 0x{stub_va:08X}  file 0x{stub_file_offset:08X}  "
          f"{len(stub)} bytes")
    print()
    print(f"{'zoom basis':<20} {args.zoom_basis} map units")
    print(f"{'new file length':<20} {len(data)}")
    print(f"{'SHA-256':<20} {out.sha256}   <- GoldPatch.TargetHash / EXPECTED_GOLD_SHA256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
