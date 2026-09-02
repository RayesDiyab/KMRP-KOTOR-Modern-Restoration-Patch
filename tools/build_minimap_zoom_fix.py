#!/usr/bin/env python3
"""Zoom the HUD minimap's map content to match its enlarged viewport.

**The symptom.** At 3440x1440 the minimap frame is the right size -- KMRP's
`scale_hud_minimap.py` grows `LBL_MAPVIEW` to 270x270 in `mipc210x7.gui` -- but
the map drawn inside it is not zoomed to the player. You see the whole area with
a tiny player marker instead of the vanilla close-up.

**The function.** `0x00459920` turns a pixel rect into 0..1 UV coordinates and
hands it to a virtual draw. Disassembled from our own editable exe:

    00459920  push  ecx
    00459921  mov   eax, [0x7BB4D0]      ; early bypass flag
    00459926  test  eax, eax
    00459928  jne   0x004599A5           ; -> pop ecx / ret 0x20
    0045992A  movsx eax, word [0x7B9460] ; active render viewport index
    00459931  lea   eax, [eax+eax*4]     ; * 5
    00459934  shl   eax, 1               ; * 10 = entry stride
    00459936  movsx edx, word [eax+0x7B946E]  ; viewport height
    0045993D  movsx eax, word [eax+0x7B946C]  ; viewport width
    ...
    004599A2  call  [edx+0x14]

The four stack arguments are normalised as `arg1/W`, `arg2/H`, `arg3/W`,
`arg4/H`, i.e. `(x, y, width, height)` over the active viewport. The zoom is
therefore decided by how large that destination rect is *relative to the
viewport*. Vanilla sizes it on a 120-pixel basis; enlarging the viewport to 270
without enlarging the rect is exactly "zoomed out".

**The fix.** Scale the destination rect by `viewportWidth / 120`, about the
viewport centre, before the normalisation:

    c    = W / 2
    arg1 = c + (arg1 - c) * W / 120
    arg2 = c + (arg2 - c) * W / 120
    arg3 = arg3 * W / 120
    arg4 = arg4 * W / 120

At a vanilla 120 viewport this is the identity, so the patch cannot change
anything the vanilla game already draws correctly.

**Why it is gated, and gated tightly.** `0x00459920` is *not* minimap-specific --
an earlier attempt (candidate 004) rewrote the viewport lookup unconditionally
for every caller and broke unrelated screens. KPM solves this in a DLL with a
flag set around the minimap draw. With no DLL, the stub instead tests facts
available at the call:

  * the active viewport is square and between 121 and 2048 -- the minimap is
    square, a full-screen viewport is not;
  * the source rect is exactly the map atlas: width 512, height 256 or 512,
    which is what `LBL_MAP` is in every shipped GUI variant.

If any test fails the stub restores `eax`/`edx` and falls through to the
untouched vanilla path. The worst case is that the patch does nothing, which is
the failure mode this fix is required to have: it cannot repeat candidate 004.

Everything the vanilla code needs afterwards is preserved: `ecx` still holds
`this` for `mov edx,[ecx]`, and `eax`/`edx` still hold the viewport width and
height for `mov [esp],edx`. `jmp` is used rather than `call`, so `esp` is
unchanged and the `[esp+NN]` argument references stay valid.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".kmz\0\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read

SITE_VA = 0x0045992A
RESUME_VA = 0x00459944
ORIGINAL = bytes.fromhex(
    "0fbf0560947b00"    # movsx eax, word [0x7B9460]
    "8d0480"            # lea   eax, [eax+eax*4]
    "d1e0"              # shl   eax, 1
    "0fbf906e947b00"    # movsx edx, word [eax+0x7B946E]
    "0fbf806c947b00"    # movsx eax, word [eax+0x7B946C]
)

VIEWPORT_INDEX = 0x007B9460
VIEWPORT_WIDTH = 0x007B946C
VIEWPORT_HEIGHT = 0x007B946E

BASE_VIEWPORT = 120     # the vanilla minimap viewport the map maths assumes
MIN_VIEWPORT = 121      # below this the scale is 1 and there is nothing to do
MAX_VIEWPORT = 2048
ATLAS_WIDTH = 512
ATLAS_HEIGHTS = (256, 512)

# Argument slots, relative to esp after the stub's three pushes. The site is
# entered by jmp, so esp is still the value the original `push ecx` left: arg1
# sits at [esp+8] there, and 12 bytes of pushes move it to [esp+0x14].
ARG1 = 0x14
ARG2 = 0x18
ARG3 = 0x1C
ARG4 = 0x20


def _scale_slot(slot: int, centred: bool) -> bytes:
    """eax = slot; (optionally about the centre) * W / 120; store back."""
    out = bytearray()
    out += b"\x8B\x44\x24" + bytes([slot])          # mov  eax, [esp+slot]
    if centred:
        out += b"\x2B\xC6"                          # sub  eax, esi
    out += b"\xF7\xEB"                              # imul ebx            edx:eax = eax*W
    out += b"\xF7\xF9"                              # idiv ecx            eax = /120
    if centred:
        out += b"\x03\xC6"                          # add  eax, esi
    out += b"\x89\x44\x24" + bytes([slot])          # mov  [esp+slot], eax
    return bytes(out)


def build_stub(stub_va: int) -> bytes:
    body = bytearray()

    def here() -> int:
        return stub_va + len(body)

    # Recompute the viewport entry exactly as the replaced bytes did.
    body += b"\x0F\xBF\x05" + struct.pack("<I", VIEWPORT_INDEX)
    body += b"\x8D\x04\x80"
    body += b"\xD1\xE0"
    body += b"\x0F\xBF\x90" + struct.pack("<I", VIEWPORT_HEIGHT)   # edx = H
    body += b"\x0F\xBF\x80" + struct.pack("<I", VIEWPORT_WIDTH)    # eax = W

    out_fixups: list[int] = []
    restore_fixups: list[int] = []

    def jcc_out(opcode: bytes) -> None:
        body.extend(opcode)
        out_fixups.append(len(body))
        body.extend(b"\x00\x00\x00\x00")

    def jcc_restore(opcode: bytes) -> None:
        body.extend(opcode)
        restore_fixups.append(len(body))
        body.extend(b"\x00\x00\x00\x00")

    # Gate 1: a square viewport in the minimap's size range.
    body += b"\x3B\xC2"                                            # cmp eax, edx
    jcc_out(b"\x0F\x85")                                           # jne out
    body += b"\x83\xF8" + bytes([MIN_VIEWPORT])                    # cmp eax, 121
    jcc_out(b"\x0F\x8C")                                           # jl  out
    body += b"\x3D" + struct.pack("<I", MAX_VIEWPORT)              # cmp eax, 2048
    jcc_out(b"\x0F\x8F")                                           # jg  out

    body += b"\x53\x51\x56"                                        # push ebx, ecx, esi
    body += b"\x8B\xD8"                                            # mov  ebx, eax   (W)
    body += b"\xB9" + struct.pack("<I", BASE_VIEWPORT)             # mov  ecx, 120
    body += b"\x8B\xF3"                                            # mov  esi, ebx
    body += b"\xD1\xEE"                                            # shr  esi, 1     (c)

    # Gate 2: the source rect is exactly the map atlas.
    body += b"\x8B\x44\x24" + bytes([ARG3])                        # mov eax, [esp+arg3]
    body += b"\x3D" + struct.pack("<I", ATLAS_WIDTH)               # cmp eax, 512
    jcc_restore(b"\x0F\x85")                                       # jne restore
    body += b"\x8B\x44\x24" + bytes([ARG4])                        # mov eax, [esp+arg4]
    body += b"\x3D" + struct.pack("<I", ATLAS_HEIGHTS[0])          # cmp eax, 256
    ok_at = None
    body += b"\x0F\x84"                                            # je  ok
    ok_fixup = len(body)
    body += b"\x00\x00\x00\x00"
    body += b"\x3D" + struct.pack("<I", ATLAS_HEIGHTS[1])          # cmp eax, 512
    jcc_restore(b"\x0F\x85")                                       # jne restore

    ok_at = len(body)
    struct.pack_into("<i", body, ok_fixup, ok_at - (ok_fixup + 4))

    body += _scale_slot(ARG1, centred=True)
    body += _scale_slot(ARG2, centred=True)
    body += _scale_slot(ARG3, centred=False)
    body += _scale_slot(ARG4, centred=False)

    restore_at = len(body)
    body += b"\x8B\xC3"                                            # mov eax, ebx  (W)
    body += b"\x8B\xD3"                                            # mov edx, ebx  (H == W)
    body += b"\x5E\x59\x5B"                                        # pop esi, ecx, ebx

    out_at = len(body)
    body += b"\xE9" + struct.pack("<i", RESUME_VA - (here() + 5))

    for fixup in restore_fixups:
        struct.pack_into("<i", body, fixup, restore_at - (fixup + 4))
    for fixup in out_fixups:
        struct.pack_into("<i", body, fixup, out_at - (fixup + 4))
    return bytes(body)


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise SystemExit("Output must be a separate executable")

    image = PEImage(args.source)
    actual, offset, section = image.read_va(SITE_VA, len(ORIGINAL))
    if actual != ORIGINAL:
        raise SystemExit(
            f"0x{SITE_VA:08X}: expected\n  {ORIGINAL.hex(' ')}\nfound\n  {actual.hex(' ')}\n"
            f"(file 0x{offset:08X}, {section}). Refusing to patch.")
    if any(s.name == ".kmz" for s in image.sections):
        raise SystemExit("Source already contains a .kmz section")

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
    stub = build_stub(stub_va)

    patch = b"\xE9" + struct.pack("<i", stub_va - (SITE_VA + 5))
    patch += b"\x90" * (len(ORIGINAL) - len(patch))
    data[offset:offset + len(ORIGINAL)] = patch
    print(f"0x{SITE_VA:08X}  file 0x{offset:08X}  {len(ORIGINAL)} bytes -> jmp 0x{stub_va:08X}")

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
    if reread != stub or sec != ".kmz":
        raise SystemExit("Verification failed: stub contents/section")

    print(f"{'stub (.kmz)':<20} VA 0x{stub_va:08X}  file 0x{stub_file_offset:08X}  {len(stub)} bytes")
    print()
    print(f"{'new file length':<20} {len(data)}")
    print(f"{'SHA-256':<20} {out.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
