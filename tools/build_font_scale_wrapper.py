#!/usr/bin/env python3
"""Add a font-size scaling wrapper to KOTOR (KPM-style detour, static patch).

This reproduces the mechanism of the third-party "2x Font" Kotor Patch Manager
patch (https://github.com/J0-o/KotorUniResPatch), verified independently
against our own copy of the same clean editable exe, but as a static on-disk
patch (matching this project's existing `.kui` map-wrapper approach) instead
of a runtime DLL-injected detour, and with a build-time-configurable scale
factor instead of a hardcoded 2.0x.

Two engine functions are hooked:

  - CAurFont::TextOutA at 0x004A1770 (ecx = CAurFont*). Reads a CAurFontInfo*
    directly from [ecx+0x18].
  - CAurGUIStringInternal::Draw at 0x0045A850 (ecx = the GUI-string object).
    [ecx+0x18] holds a "safe pointer" whose vtable slot +0x38 is a getter that
    resolves to the same CAurFontInfo* used by TextOutA.

CAurFontInfo stores five relevant fields as normalized (not raw-pixel)
32-bit floats, confirmed live against a real instance (main-menu label font:
fontHeight = baselineHeight ~= 0.16, textureWidth ~= 2.56, spacingR =
spacingB = 0.0), and confirmed proportional via CAurFont::GetFontPixelHeight
(0x00459610), which computes `fontHeight * 100.0 + 0.5` to get an on-screen
pixel height:

  +0x04 fontHeight
  +0x08 baselineHeight
  +0x0C textureWidth
  +0x10 spacingR
  +0x14 spacingB

Because both hooked functions run every rendered frame and CAurFontInfo
objects are persistent/shared (the same instance is reused across many draw
calls), naively multiplying these fields on every hook call would compound
without bound. A small in-section, write-enabled dedup table (mirroring the
64-slot "already scaled" pointer cache in KPM's own implementation) ensures
each distinct CAurFontInfo instance is scaled exactly once.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from verify_map_patch import PEImage


SECTION_NAME = b".kfs\0\0\0\0"
SECTION_CHARACTERISTICS = 0xE0000020  # code | execute | read | write

MAX_TRACKED_FONTS = 64
# Two independent scale constants. The font-metric scale is normally left at 1.0
# now that font sizing is done in the atlases' own TXI metrics instead
# (tools/build_scaled_fonts.py) -- scaling CAurFontInfo at runtime happened one
# frame too late, after the engine had already measured and centred the text,
# which shifted the first screen drawn each session. List-row heights have no
# such ordering problem (the hook rewrites a row's height as the row is built,
# and nothing has measured it beforehand), so that scaling stays here and needs
# its own constant rather than sharing the font one.
OFF_SCALE_CONST = 0x000
OFF_ROW_SCALE_CONST = 0x004
OFF_DEDUP_COUNT = 0x008
OFF_DEDUP_ARRAY = 0x00C
OFF_SCALE_FN = OFF_DEDUP_ARRAY + MAX_TRACKED_FONTS * 4  # 0x10C

TEXTOUTA_VA = 0x004A1770
TEXTOUTA_ORIGINAL = bytes.fromhex("6A FF 68 5C 7E 71 00 64 A1 00 00 00 00")
TEXTOUTA_RESUME_VA = TEXTOUTA_VA + len(TEXTOUTA_ORIGINAL)

DRAW_VA = 0x0045A850
DRAW_ORIGINAL = bytes.fromhex("83 EC 4C 89 4C 24 04")
DRAW_RESUME_VA = DRAW_VA + len(DRAW_ORIGINAL)

# Generic composite list-row setup (CSWGuiInGameItemEntry-style row init), used by
# the save/load list, journal quest list, and the graphics resolution popup rows
# (per Kotor Patch Manager's "2x List Item Height" research). The row height read
# from [eax+0x0C] is copied verbatim into the new row's rect at [ecx+0x0C]; without
# scaling it, rows stay their original (small-font) height while the text drawn
# into them is now bigger, so adjacent rows overlap.
LIST_ROW_VA = 0x00417992
LIST_ROW_ORIGINAL = bytes.fromhex("8B 40 0C 89 41 0C 8B 4C 24 6C")
LIST_ROW_RESUME_VA = LIST_ROW_VA + len(LIST_ROW_ORIGINAL)

FONT_HEIGHT_OFF = 0x04
BASELINE_HEIGHT_OFF = 0x08
TEXTURE_WIDTH_OFF = 0x0C
SPACING_R_OFF = 0x10
SPACING_B_OFF = 0x14
FONT_INFO_PTR_OFF = 0x18  # on CAurFont, and the "safe pointer" on the GUI string
SAFE_PTR_GETTER_VTABLE_OFF = 0x38


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def patch_exact(image: PEImage, data: bytearray, va: int, expected: bytes, replacement: bytes, label: str) -> None:
    if len(expected) != len(replacement):
        raise ValueError(f"Length mismatch for {label}")
    actual, offset, section = image.read_va(va, len(expected))
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{va:08X} (file 0x{offset:08X}, {section})"
        )
    data[offset : offset + len(replacement)] = replacement
    print(
        f"{label:<32} VA 0x{va:08X}  file 0x{offset:08X}  "
        f"{actual.hex(' ').upper()} -> {replacement.hex(' ').upper()}"
    )


def require_exact(image: PEImage, va: int, expected: bytes, label: str) -> None:
    actual, offset, section = image.read_va(va, len(expected))
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex(' ')}, found {actual.hex(' ')} "
            f"at VA 0x{va:08X} (file 0x{offset:08X}, {section})"
        )
    print(f"{label:<32} VA 0x{va:08X}  file 0x{offset:08X}  verified {actual.hex(' ').upper()}")


def encode_call(call_va: int, target_va: int) -> bytes:
    return b"\xE8" + struct.pack("<i", target_va - (call_va + 5))


def encode_jmp(jmp_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (jmp_va + 5))


def build_scale_fontinfo(fn_va: int, new_va: int) -> bytes:
    """void __fastcall-ish scale_fontinfo(eax=CAurFontInfo*); clobbers eax/ecx/edx/FPU-balanced; ret."""
    scale_const_va = new_va + OFF_SCALE_CONST
    dedup_count_va = new_va + OFF_DEDUP_COUNT
    dedup_array_va = new_va + OFF_DEDUP_ARRAY

    code = bytearray()
    code += bytes.fromhex("51")  # push ecx
    code += bytes.fromhex("52")  # push edx
    code += b"\x8B\x0D" + struct.pack("<I", dedup_count_va)  # mov ecx, [dedup_count]
    code += bytes.fromhex("31D2")  # xor edx, edx

    scan_off = len(code)
    code += bytes.fromhex("3BD1")  # cmp edx, ecx
    jge_not_found_patch_off = len(code) + 1
    code += bytes.fromhex("7D00")  # jge not_found (patched below)
    code += b"\x3B\x04\x95" + struct.pack("<I", dedup_array_va)  # cmp eax, [dedup_array + edx*4]
    je_already_1_patch_off = len(code) + 1
    code += bytes.fromhex("7400")  # je already (patched below)
    code += bytes.fromhex("42")  # inc edx
    jmp_scan_patch_off = len(code) + 1
    code += bytes.fromhex("EB00")  # jmp scan (patched below)

    not_found_off = len(code)
    code[jge_not_found_patch_off] = (not_found_off - (jge_not_found_patch_off + 1)) & 0xFF
    code[jmp_scan_patch_off] = (scan_off - (jmp_scan_patch_off + 1)) & 0xFF

    code += bytes.fromhex("83F940")  # cmp ecx, 64
    jge_already_2_patch_off = len(code) + 1
    code += bytes.fromhex("7D00")  # jge already (patched below)
    code += b"\x89\x04\x8D" + struct.pack("<I", dedup_array_va)  # mov [dedup_array + ecx*4], eax
    code += bytes.fromhex("41")  # inc ecx
    code += b"\x89\x0D" + struct.pack("<I", dedup_count_va)  # mov [dedup_count], ecx

    for field_off in (FONT_HEIGHT_OFF, BASELINE_HEIGHT_OFF, TEXTURE_WIDTH_OFF, SPACING_R_OFF, SPACING_B_OFF):
        code += bytes([0xD9, 0x40, field_off])  # fld dword [eax+field_off]
        code += b"\xD8\x0D" + struct.pack("<I", scale_const_va)  # fmul dword [scale_const]
        code += bytes([0xD9, 0x58, field_off])  # fstp dword [eax+field_off]

    already_off = len(code)
    code[je_already_1_patch_off] = (already_off - (je_already_1_patch_off + 1)) & 0xFF
    code[jge_already_2_patch_off] = (already_off - (jge_already_2_patch_off + 1)) & 0xFF

    code += bytes.fromhex("5A")  # pop edx
    code += bytes.fromhex("59")  # pop ecx
    code += bytes.fromhex("C3")  # ret

    for patch_off in (jge_not_found_patch_off, je_already_1_patch_off, jmp_scan_patch_off, jge_already_2_patch_off):
        if not (0 <= code[patch_off] <= 0x7F) and not (0x80 <= code[patch_off] <= 0xFF):
            raise ValueError("scale_fontinfo: rel8 displacement out of range")
    return bytes(code)


def build_textout_stub(stub_va: int, scale_fn_va: int) -> bytes:
    code = bytearray()
    code += bytes.fromhex("50")  # push eax
    code += bytes.fromhex("52")  # push edx
    code += bytes.fromhex("8B4118")  # mov eax, [ecx+0x18]
    code += bytes.fromhex("85C0")  # test eax, eax
    jz_skip_patch_off = len(code) + 1
    code += bytes.fromhex("7400")  # jz skip (patched below)
    call_off = len(code)
    code += encode_call(stub_va + call_off, scale_fn_va)  # call scale_fontinfo

    skip_off = len(code)
    code[jz_skip_patch_off] = (skip_off - (jz_skip_patch_off + 1)) & 0xFF

    code += bytes.fromhex("5A")  # pop edx
    code += bytes.fromhex("58")  # pop eax
    code += TEXTOUTA_ORIGINAL
    jmp_off = len(code)
    code += encode_jmp(stub_va + jmp_off, TEXTOUTA_RESUME_VA)
    return bytes(code)


def build_draw_stub(stub_va: int, scale_fn_va: int) -> bytes:
    code = bytearray()
    code += bytes.fromhex("50")  # push eax
    code += bytes.fromhex("51")  # push ecx
    code += bytes.fromhex("52")  # push edx
    code += bytes.fromhex("8B4118")  # mov eax, [ecx+0x18]        ; "safe pointer"
    code += bytes.fromhex("85C0")  # test eax, eax
    jz_done_1_patch_off = len(code) + 1
    code += bytes.fromhex("7400")  # jz done (patched below)
    code += bytes.fromhex("8B10")  # mov edx, [eax]              ; vtable
    code += bytes.fromhex("8B5238")  # mov edx, [edx+0x38]       ; getter fn ptr
    code += bytes.fromhex("8BC8")  # mov ecx, eax                ; thiscall arg = safe pointer
    code += bytes.fromhex("FFD2")  # call edx                    ; eax = CAurFontInfo* (or null)
    code += bytes.fromhex("85C0")  # test eax, eax
    jz_done_2_patch_off = len(code) + 1
    code += bytes.fromhex("7400")  # jz done (patched below)
    call_off = len(code)
    code += encode_call(stub_va + call_off, scale_fn_va)  # call scale_fontinfo

    done_off = len(code)
    code[jz_done_1_patch_off] = (done_off - (jz_done_1_patch_off + 1)) & 0xFF
    code[jz_done_2_patch_off] = (done_off - (jz_done_2_patch_off + 1)) & 0xFF

    code += bytes.fromhex("5A")  # pop edx
    code += bytes.fromhex("59")  # pop ecx
    code += bytes.fromhex("58")  # pop eax
    code += DRAW_ORIGINAL
    jmp_off = len(code)
    code += encode_jmp(stub_va + jmp_off, DRAW_RESUME_VA)
    return bytes(code)


def build_list_row_stub(stub_va: int, scale_const_va: int) -> bytes:
    code = bytearray()
    code += bytes.fromhex("8B400C")  # mov eax, [eax+0x0C]        ; original row-height read
    code += bytes.fromhex("50")  # push eax
    code += bytes.fromhex("DB0424")  # fild dword [esp]
    code += b"\xD8\x0D" + struct.pack("<I", scale_const_va)  # fmul dword [scale_const]
    code += bytes.fromhex("DB1C24")  # fistp dword [esp]
    code += bytes.fromhex("58")  # pop eax
    code += bytes.fromhex("89410C")  # mov [ecx+0x0C], eax         ; original store
    code += bytes.fromhex("8B4C246C")  # mov ecx, [esp+0x6C]      ; original next instruction
    jmp_off = len(code)
    code += encode_jmp(stub_va + jmp_off, LIST_ROW_RESUME_VA)
    return bytes(code)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, required=True, help="Uniform font-metric scale factor, e.g. 2.0")
    parser.add_argument("--row-scale", type=float, default=None,
                        help="List-row height scale factor (defaults to --scale)")
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a separate executable")
    if args.row_scale is None:
        args.row_scale = args.scale
    if not 0.1 <= args.scale <= 8.0:
        raise ValueError("Scale must be between 0.1 and 8.0")
    if not 0.1 <= args.row_scale <= 8.0:
        raise ValueError("Row scale must be between 0.1 and 8.0")

    image = PEImage(args.source)
    data = bytearray(image.data)

    require_exact(image, TEXTOUTA_VA, TEXTOUTA_ORIGINAL, "CAurFont::TextOutA prologue")
    require_exact(image, DRAW_VA, DRAW_ORIGINAL, "CAurGUIStringInternal::Draw prologue")
    require_exact(image, LIST_ROW_VA, LIST_ROW_ORIGINAL, "generic list-row height setup")

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    coff_offset = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff_offset + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff_offset + 16)[0]
    optional_offset = coff_offset + 20
    section_offset = optional_offset + optional_size
    file_alignment = struct.unpack_from("<I", data, optional_offset + 36)[0]
    section_alignment = struct.unpack_from("<I", data, optional_offset + 32)[0]

    new_header_offset = section_offset + section_count * 40
    if new_header_offset + 40 > image.size_of_headers:
        raise ValueError("No room for another PE section header")
    if any(section.name == ".kfs" for section in image.sections):
        raise ValueError("Source already contains a .kfs section")

    last_section = max(image.sections, key=lambda section: section.virtual_address)
    new_rva = align(
        last_section.virtual_address + max(last_section.virtual_size, last_section.raw_size),
        section_alignment,
    )
    new_va = image.image_base + new_rva

    scale_fn_va = new_va + OFF_SCALE_FN
    scale_fn = build_scale_fontinfo(scale_fn_va, new_va)
    textout_stub_va = scale_fn_va + len(scale_fn)
    textout_stub = build_textout_stub(textout_stub_va, scale_fn_va)
    draw_stub_va = textout_stub_va + len(textout_stub)
    draw_stub = build_draw_stub(draw_stub_va, scale_fn_va)
    list_row_stub_va = draw_stub_va + len(draw_stub)
    list_row_stub = build_list_row_stub(list_row_stub_va, new_va + OFF_ROW_SCALE_CONST)

    header = (
        struct.pack("<f", args.scale)
        + struct.pack("<f", args.row_scale)
        + struct.pack("<I", 0)
        + b"\0" * (MAX_TRACKED_FONTS * 4)
    )
    assert len(header) == OFF_SCALE_FN
    payload = header + scale_fn + textout_stub + draw_stub + list_row_stub

    new_raw_offset = align(len(data), file_alignment)
    new_raw_size = align(len(payload), file_alignment)
    new_virtual_size = len(payload)

    patch_exact(
        image,
        data,
        TEXTOUTA_VA,
        TEXTOUTA_ORIGINAL,
        encode_jmp(TEXTOUTA_VA, textout_stub_va) + b"\x90" * (len(TEXTOUTA_ORIGINAL) - 5),
        "CAurFont::TextOutA hook",
    )
    patch_exact(
        image,
        data,
        DRAW_VA,
        DRAW_ORIGINAL,
        encode_jmp(DRAW_VA, draw_stub_va) + b"\x90" * (len(DRAW_ORIGINAL) - 5),
        "CAurGUIStringInternal::Draw hook",
    )
    patch_exact(
        image,
        data,
        LIST_ROW_VA,
        LIST_ROW_ORIGINAL,
        encode_jmp(LIST_ROW_VA, list_row_stub_va) + b"\x90" * (len(LIST_ROW_ORIGINAL) - 5),
        "generic list-row height hook",
    )

    struct.pack_into("<H", data, coff_offset + 2, section_count + 1)
    size_of_code = struct.unpack_from("<I", data, optional_offset + 4)[0]
    struct.pack_into("<I", data, optional_offset + 4, size_of_code + new_raw_size)
    struct.pack_into("<I", data, optional_offset + 56, align(new_rva + new_virtual_size, section_alignment))
    struct.pack_into("<I", data, optional_offset + 64, 0)  # clear checksum

    section_header = struct.pack(
        "<8sIIIIIIHHI",
        SECTION_NAME,
        new_virtual_size,
        new_rva,
        new_raw_size,
        new_raw_offset,
        0,
        0,
        0,
        0,
        SECTION_CHARACTERISTICS,
    )
    data[new_header_offset : new_header_offset + 40] = section_header
    if len(data) < new_raw_offset:
        data.extend(b"\0" * (new_raw_offset - len(data)))
    data.extend(payload)
    data.extend(b"\0" * (new_raw_size - len(payload)))

    args.output.write_bytes(data)
    output = PEImage(args.output)
    written, _, section = output.read_va(new_va, len(payload))
    if written != payload or section != ".kfs":
        raise ValueError("Font-scale section verification failed")

    reread, _, _ = output.read_va(TEXTOUTA_VA, 5)
    if reread != encode_jmp(TEXTOUTA_VA, textout_stub_va):
        raise ValueError("TextOutA hook verification failed")
    reread, _, _ = output.read_va(DRAW_VA, 5)
    if reread != encode_jmp(DRAW_VA, draw_stub_va):
        raise ValueError("Draw hook verification failed")
    reread, _, _ = output.read_va(LIST_ROW_VA, 5)
    if reread != encode_jmp(LIST_ROW_VA, list_row_stub_va):
        raise ValueError("List-row hook verification failed")

    print(f"Font-scale section              VA 0x{new_va:08X}  raw 0x{new_raw_offset:08X}  size {len(payload)}")
    print(f"scale_fontinfo                  VA 0x{scale_fn_va:08X}")
    print(f"TextOutA stub                   VA 0x{textout_stub_va:08X}")
    print(f"Draw stub                       VA 0x{draw_stub_va:08X}")
    print(f"List-row stub                   VA 0x{list_row_stub_va:08X}")
    print(f"Font scale factor: {args.scale}   list-row scale factor: {args.row_scale}")
    print(f"Wrote {args.output}")
    print(f"SHA-256: {output.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
