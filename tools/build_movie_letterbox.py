#!/usr/bin/env python3
"""ABANDONED -- this approach cannot work. Kept as the record of why.

Padding the Bink buffer and centring the picture inside it is defeated by
dirty-rect blitting. The engine calls BinkGetRects and hands those
rectangles to BinkBufferBlit:

    00404D00  call BinkGetRects(bink, flags)
    00404D09  push eax           ; count
    00404D0D  add  edx, 0x34     ; the rect array
    00404D12  call BinkBufferBlit

Those rects are in the MOVIE's coordinate space, 0..movieWidth-1. Offsetting
the copy by destx therefore desyncs the blit from the picture: the blit
still covers buffer columns 0..639 while the picture now lives at
destx..destx+639.

Observed in play, and it matches exactly: for a 640x272 vision padded to 652
with destx=6, the left bar went black (inside 0..639) and the right bar did
not (outside it). For a 640x480 logo padded to 1148 with destx=254, only the
left portion of the frame appeared and the rest of the screen stayed black.

Fixing this would mean also replacing the rect list with a full-buffer rect,
a fourth patch site in the movie path. The window-paint approach fixes the
bars AND the grey before and after playback -- which no amount of buffer work
can reach, since Bink is not drawing then at all -- so that is the route.

Original description follows.

Letterbox KOTOR's movies inside the Bink buffer instead of beside it.

The problem this replaces
------------------------
gold v24 fixed the aspect ratio by scaling each BIK to fit the window. That is
correct geometry and wrong rendering: `BinkBufferOpen` is called with the
MOVIE's dimensions, the blit stretches that buffer to wherever we scale it, and
**Bink never paints anything outside the blit rectangle**. Vanilla scaled to the
full window width and overflowed vertically, so it always covered the screen;
fitting inside it leaves bars nothing draws, showing stale framebuffer --
reported from play as a grey flash before and after every movie.

Measured live, from the BINKBUFFER of an actual vision:

    +00  640   source width      +08  3388  destination width
    +04  272   source height     +0C  1440  destination height
    +24  3440  window width      +28  1440  window height

3388 of 3440 covered: 26px of unpainted screen down each side.

What this does instead
----------------------
Pad the BUFFER to the window's aspect ratio, centre the picture inside it, and
stretch the whole buffer across the window. The bars become part of the image,
so the blit covers every pixel and nothing shows through.

    buffer   650x272   (round4(272 * 3440 / 1440)), picture at destx=5
    blit     3440x1440 at offset 0,0

Frames still copy at their native size, so this costs nothing per frame.

Three sites
-----------
    0x0040572E  the dimensions handed to BinkBufferOpen
    0x00404CD7  the destx/desty handed to BinkCopyToBuffer (hardcoded 0,0)
    0x004057AC  the scale, and the blit offset

The scale stub writes [this+0x84]/[this+0x88] itself and jumps to 0x00405855,
skipping the engine's own offset arithmetic. That is deliberate: those
instructions read stack slots set up in a branchy prologue whose locals Ghidra
leaves unnamed, and `ebx` -- which the original compares against the movie
width -- is written from four places including a literal 1. Jumping past all of
it means the patch depends on nothing but `esi`. Verified by disassembly: from
0x00405855 to the epilogue `esi` is the only register read before being
written, and ebx/ebp/edi/esi are all restored by the pops at 0x004058D3.

Screen size comes from the two 16-bit immediates the resolution patch already
writes, at 0x00403D6C and 0x00403D78 -- the same words Test-MovieResolution
checks -- so this stays correct at every resolution instead of baking one in.

The stubs are assembled with nasm rather than hand-encoded. The predecessor of
this file records an off-by-one in a hand-written jump that resumed "on 7C 24 --
a jl into nothing -- on every movie", found only by disassembling the built
image. This still disassembles the result, but no longer relies on that.

Usage:
    python tools/build_movie_letterbox.py GOLD_V23 OUTPUT_V25

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import subprocess
import tempfile
from pathlib import Path

from verify_map_patch import PEImage

SECTION_NAME = b".kmv\0\0\0\0"
# Writable as well as executable: the open stub stores the centring offsets for
# the copy stub to push.
SECTION_CHARACTERISTICS = 0xE0000020

SCREEN_WIDTH_VA = 0x00403D6C
SCREEN_HEIGHT_VA = 0x00403D78
BINK_SET_SCALE_IAT = 0x0073D484

SITES = {
    "open":  (0x0040572E, bytes.fromhex("8B 50 04 8B 00"),       0x00405733),
    "copy":  (0x00404CD7, bytes.fromhex("6A 00 6A 00 52"),       0x00404CDC),
    "scale": (0x004057AC, bytes.fromhex("8B 4E 48 8B 01 3B D8"), 0x00405855),
}

EXPECTED_INPUT_LENGTH = 4_083_712
EXPECTED_INPUT_SHA256 = "29BE3C23F53D53F521D98329F996248864834FB3873819DF63CCF1803C65A7E8"


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def jmp(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5))


def padded_size(movie_w: int, movie_h: int, screen_w: int, screen_h: int):
    """What the stub should compute, in Python, for cross-checking."""
    if movie_w * screen_h < screen_w * movie_h:
        width = align(movie_h * screen_w // screen_h, 4)
        height = movie_h
    else:
        width = movie_w
        height = align(movie_w * screen_h // screen_w, 4)
    return width, height, (width - movie_w) // 2, (height - movie_h) // 2


def source(base_va: int) -> str:
    open_resume = SITES["open"][2]
    copy_resume = SITES["copy"][2]
    scale_resume = SITES["scale"][2]
    return f"""
bits 32
org 0x{base_va:08X}

; ---- scratch, written by the open stub and read by the copy stub -----------
dest_x:  dd 0
dest_y:  dd 0
         dd 0
         dd 0

    times (0x20 - ($ - $$)) db 0
; ---------------------------------------------------------------- open stub
; in : eax = BINK*, ecx = HWND, esi = this
; out: eax = padded width, edx = padded height, ecx and esi unchanged
;
; ebx/ebp/edi are free: nothing between here and the scale stub reads them, and
; the function epilogue restores all four from the stack.
open_stub:
    push    ebx
    push    ebp
    push    edi
    push    ecx                         ; the HWND, needed by the caller
    mov     ebx, [eax]                  ; movie width
    mov     edi, [eax+4]                ; movie height
    movzx   ebp, word [0x{SCREEN_WIDTH_VA:08X}]
    movzx   ecx, word [0x{SCREEN_HEIGHT_VA:08X}]

    mov     eax, ebx
    imul    eax, ecx                    ; movieW * screenH
    mov     edx, ebp
    imul    edx, edi                    ; screenW * movieH
    cmp     eax, edx
    jge     .pad_height                 ; movie is wider than the window

.pad_width:                             ; width = movieH * screenW / screenH
    mov     eax, edi
    imul    eax, ebp
    cdq
    idiv    ecx
    add     eax, 3
    and     eax, -4                     ; Bink prefers a multiple of four
    mov     edx, edi                    ; height unchanged
    jmp     .store

.pad_height:                            ; height = movieW * screenH / screenW
    mov     eax, ebx
    imul    eax, ecx
    cdq
    idiv    ebp
    add     eax, 3
    and     eax, -4
    mov     edx, eax
    mov     eax, ebx                    ; width unchanged

.store:
    push    eax
    sub     eax, ebx
    shr     eax, 1
    mov     [dest_x], eax
    pop     eax
    push    edx
    sub     edx, edi
    shr     edx, 1
    mov     [dest_y], edx
    pop     edx

    pop     ecx
    pop     edi
    pop     ebp
    pop     ebx
    jmp     0x{open_resume:08X}

    times (0xC0 - ($ - $$)) db 0
; ---------------------------------------------------------------- copy stub
; Replaces `push 0 / push 0 / push edx` -- desty, destx, then destheight.
copy_stub:
    push    dword [dest_y]
    push    dword [dest_x]
    push    edx
    jmp     0x{copy_resume:08X}

    times (0x100 - ($ - $$)) db 0
; --------------------------------------------------------------- scale stub
; in: esi = this. Stretch the padded buffer across the whole window and put it
; at the origin, then rejoin the engine at its BinkBufferSetOffset call.
scale_stub:
    movzx   eax, word [0x{SCREEN_HEIGHT_VA:08X}]
    push    eax
    movzx   eax, word [0x{SCREEN_WIDTH_VA:08X}]
    push    eax
    mov     eax, [esi+0x4C]             ; HBINKBUFFER
    push    eax
    call    [0x{BINK_SET_SCALE_IAT:08X}]
    mov     dword [esi+0x84], 0
    mov     dword [esi+0x88], 0
    jmp     0x{scale_resume:08X}
"""


def assemble(base_va: int) -> tuple[bytes, dict[str, int]]:
    """nasm the stubs; return the blob and each stub's VA."""
    with tempfile.TemporaryDirectory() as work:
        asm = Path(work) / "stubs.asm"
        out = Path(work) / "stubs.bin"
        lst = Path(work) / "stubs.lst"
        asm.write_text(source(base_va), encoding="ascii")
        result = subprocess.run(
            ["nasm", "-f", "bin", "-o", str(out), "-l", str(lst), str(asm)],
            capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"nasm failed:\n{result.stdout}\n{result.stderr}")
        blob = out.read_bytes()
        listing = lst.read_text(encoding="ascii", errors="replace")

    # Fixed slots rather than parsed addresses: the stubs are padded to known
    # offsets, so nothing here depends on their lengths or on nasm's listing
    # format. The padding directives fail the assembly outright if a stub ever
    # outgrows its slot.
    del listing
    offsets = {"open_stub": base_va + 0x20,
               "copy_stub": base_va + 0xC0,
               "scale_stub": base_va + 0x100}
    return blob, offsets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--allow-any-input", action="store_true")
    arguments = parser.parse_args()

    if arguments.source.resolve() == arguments.output.resolve():
        raise SystemExit("Output must be a separate executable")
    original = arguments.source.read_bytes()
    if not arguments.allow_any_input:
        if (len(original) != EXPECTED_INPUT_LENGTH
                or sha256(original) != EXPECTED_INPUT_SHA256):
            raise SystemExit("Refusing an unexpected gold v23 snapshot")

    image = PEImage(arguments.source)
    hooks = {}
    for name, (va, expected, _) in SITES.items():
        actual, offset, section = image.read_va(va, len(expected))
        if actual != expected or section != ".text":
            raise SystemExit(f"{name} site mismatch at 0x{va:08X}: "
                             f"{actual.hex(' ')} != {expected.hex(' ')}")
        hooks[name] = offset

    data = bytearray(original)
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe + 4
    count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    headers = optional + optional_size
    file_align = struct.unpack_from("<I", data, optional + 36)[0]
    section_align = struct.unpack_from("<I", data, optional + 32)[0]
    if headers + count * 40 + 40 > image.size_of_headers:
        raise SystemExit("No room for another PE section header")
    if any(s.name == ".kmv" for s in image.sections):
        raise SystemExit("Source already has a .kmv section")

    last = max(image.sections, key=lambda s: s.virtual_address)
    rva = align(last.virtual_address + max(last.virtual_size, last.raw_size),
                section_align)
    base_va = image.image_base + rva
    payload, stubs = assemble(base_va)

    for name, (va, expected, _) in SITES.items():
        patch = jmp(va, stubs[f"{name}_stub"])
        patch += b"\x90" * (len(expected) - len(patch))
        data[hooks[name] : hooks[name] + len(expected)] = patch

    raw_offset = align(len(data), file_align)
    raw_size = align(len(payload), file_align)
    struct.pack_into("<H", data, coff + 2, count + 1)
    code = struct.unpack_from("<I", data, optional + 4)[0]
    struct.pack_into("<I", data, optional + 4, code + raw_size)
    struct.pack_into("<I", data, optional + 56,
                     align(rva + len(payload), section_align))
    struct.pack_into("<I", data, optional + 64, 0)
    data[headers + count * 40 : headers + count * 40 + 40] = struct.pack(
        "<8sIIIIIIHHI", SECTION_NAME, len(payload), rva, raw_size, raw_offset,
        0, 0, 0, 0, SECTION_CHARACTERISTICS)
    data.extend(b"\0" * (raw_offset - len(data)))
    data.extend(payload)
    data.extend(b"\0" * (raw_size - len(payload)))

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(data)

    written = PEImage(arguments.output)
    back, _, section = written.read_va(base_va, len(payload))
    if back != payload or section != ".kmv":
        raise SystemExit("stub failed read-back")
    for name, (va, expected, _) in SITES.items():
        back, _, _ = written.read_va(va, 5)
        if back != jmp(va, stubs[f"{name}_stub"]):
            raise SystemExit(f"{name} hook failed read-back")

    print(f"stubs at {base_va:#010x}, {len(payload)} bytes")
    for name, (va, _, resume) in SITES.items():
        print(f"  {name:6s} 0x{va:08X} -> 0x{stubs[name + '_stub']:08X}"
              f"  (rejoins 0x{resume:08X})")
    print(f"\nwrote {arguments.output}")
    print(f"length  {len(data)}")
    print(f"SHA-256 {sha256(bytes(data))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
