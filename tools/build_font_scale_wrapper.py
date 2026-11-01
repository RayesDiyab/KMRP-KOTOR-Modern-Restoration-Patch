#!/usr/bin/env python3
"""The list-row height stub of the engine's .kfs page.

What is left of a tool that added a font-size wrapper to KOTOR, after the "2x Font" Kotor
Patch Manager patch (https://github.com/J0-o/KotorUniResPatch). Until 2026-11-01 it also
emitted stubs at the entries of CAurFont::TextOutA (0x004A1770) and CAurGUIStringInternal::Draw
(0x0045A850) that multiplied each font's five metrics by a constant, with a 64-slot list of the
fonts done. Font sizing moved to the atlases' own TXI metrics long before (build_scaled_fonts.py):
scaled at run time, the first line was measured at the old size. So that constant was 1.0, and
nothing wrote it, and they went (audit E-1). Their record is in
reverse-engineering/font.md and reverse-engineering/patch-records/font_patch.

List rows still scale here: this hook rewrites a row's height as the row is built, before
anything has measured it, so it has no such ordering problem.
"""

from __future__ import annotations

import struct


# Generic composite list-row setup (CSWGuiInGameItemEntry-style row init), used by
# the save/load list, journal quest list, and the graphics resolution popup rows
# (per Kotor Patch Manager's "2x List Item Height" research). The row height read
# from [eax+0x0C] is copied verbatim into the new row's rect at [ecx+0x0C]; without
# scaling it, rows stay their original (small-font) height while the text drawn
# into them is now bigger, so adjacent rows overlap.
LIST_ROW_VA = 0x00417992
LIST_ROW_ORIGINAL = bytes.fromhex("8B 40 0C 89 41 0C 8B 4C 24 6C")
LIST_ROW_RESUME_VA = LIST_ROW_VA + len(LIST_ROW_ORIGINAL)


def encode_jmp(jmp_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (jmp_va + 5))


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
