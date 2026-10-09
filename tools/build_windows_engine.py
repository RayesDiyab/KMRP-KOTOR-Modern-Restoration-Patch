#!/usr/bin/env python3
"""Assemble Windows KPM engine patches from source, without a game executable.

windows-sites.json names the small, documented original-image edits. Injected
code comes from the existing assembly emitters, not a gold PE snapshot. The
installer specializes this template through ResolutionPatch; KPM's module still
verifies the original bytes before applying any run to the decrypted game.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import build_font_scale_wrapper as fonts
import build_gutter_side_fix as gutter
import build_hit_test_center_fix as hit_test
import build_leading_newline_fix as newline
import build_letterbox_scale_wrapper as letterbox
import build_map_icon_draw_wrapper as icons
import build_map_note_table as notes
import build_minimap_fog_fix as fog
import build_minimap_split_candidate as minimap
import build_minimap_zoom_fix as zoom
import build_movie_aspect_fit as movies
import build_stack_count_fix as stacks
import build_wrap_progress_fix as wrap
import kpm_relocations as reloc

ROOT = Path(__file__).resolve().parents[1]
BLOCK_VA = 0x86D000
BLOCK_SIZE = 0xB000
CORE, MOVIES = 1, 2


def u32(value):
    return struct.pack('<I', value & 0xFFFFFFFF)


def checksum(data):
    value = 2166136261
    for b in data:
        value = ((value ^ b) * 16777619) & 0xFFFFFFFF
    return u32(value)


class Recipe:
    def __init__(self):
        self.original = {}
        self.final = {}
        self.features = {}
        self.block = bytearray(BLOCK_SIZE)
        self.lengths = {}

    def site(self, va, old, new, feature=CORE):
        if len(old) != len(new) or not old or not 0x401000 <= va < BLOCK_VA:
            raise ValueError(f'invalid patch at {va:08X}')
        for i, (a, b) in enumerate(zip(old, new)):
            at = va + i
            if at in self.original and (self.original[at], self.final[at], self.features[at]) != (a, b, feature):
                raise ValueError(f'conflicting source patches at {at:08X}')
            self.original[at], self.final[at], self.features[at] = a, b, feature

    def integer(self, va, old, new, feature=CORE):
        self.site(va, u32(old), u32(new), feature)

    def hook(self, va, old, target, call=False, feature=CORE):
        instruction = icons.encode_call(va, target) if call else letterbox.encode_jmp(va, target)
        self.site(va, old, instruction + b'\x90' * (len(old) - 5), feature)

    def page(self, index, name, data):
        if len(data) > 0x1000:
            raise ValueError(f'{name} exceeds its page')
        self.block[index * 0x1000:index * 0x1000 + len(data)] = data
        self.lengths[name] = len(data)

    def runs(self):
        result = []
        for at in sorted(self.original):
            if not result or at != result[-1][1] + len(result[-1][2]) or self.features[at] != result[-1][0]:
                result.append((self.features[at], at, bytearray(), bytearray()))
            result[-1][2].append(self.original[at])
            result[-1][3].append(self.final[at])
        return result

    def read(self, va, n):
        # Unknown original-image bytes are zero for the relocation scan only;
        # they never become guards or writes in the generated recipe.
        return bytes(self.block[v - BLOCK_VA] if BLOCK_VA <= v < BLOCK_VA + BLOCK_SIZE
                     else self.final.get(v, 0) for v in range(va, va + n))

    def dword(self, va):
        return struct.unpack('<I', self.read(va, 4))[0]


def assemble():
    recipe = Recipe()
    sites = json.loads((ROOT / 'src/engine/windows-sites.json').read_text())
    if sites['format'] != 1:
        raise ValueError('unsupported Windows sites format')
    movie_sites = {0x403D6C, 0x403D78, 0x4057AC, 0x5F5B3B}
    for site in sites['sites']:
        va = int(site['va'], 16)
        recipe.site(va, bytes.fromhex(site['original']), bytes.fromhex(site['replacement']),
                    MOVIES if va in movie_sites else CORE)

    # Whole imm32 guards, including bytes unchanged in the old gold delta.
    for va, old, new, feature in [
        (0x403D6C,640,3440,MOVIES), (0x403D78,480,1440,MOVIES),
        (0x5F5B3B,640,3440,MOVIES), (0x5F5B43,480,1440,MOVIES),
        (0x40AA65,640,3440,CORE), (0x40AA85,480,1440,CORE),
        (0x5F0C65,800,3440,CORE), (0x5F0C6F,600,1440,CORE),
        (0x40B6C7,-640,-3440,CORE), (0x40BA6C,-640,-3440,CORE),
        (0x40B6DA,-480,-1440,CORE), (0x40BA83,-480,-1440,CORE),
        (0x6256DC,440,1600,CORE), (0x6256F6,440,1600,CORE),
        (0x6256E3,280,900,CORE), (0x625759,280,900,CORE),
        (0x62540D,32,128,CORE), (0x626F95,32,128,CORE),
        (0x6928B3,640,2750,CORE), (0x6928C3,480,1400,CORE),
        (0x69505C,512,1720,CORE), (0x695064,256,720,CORE),
        (0x695082,440,1478,CORE), (0x69508A,256,720,CORE),
        (0x694720,20,40,CORE), (0x694763,14,28,CORE),
        (0x694A13,16,32,CORE), (0x694AC4,32,64,CORE),
        (0x69405B,32,64,CORE), (0x6940DC,16,32,CORE),
        (0x68C4E3,1024,3440,CORE),
    ]:
        recipe.integer(va, old, new, feature)
    for old, addresses in [(56,[0x6B527F,0x6B4FA9,0x6B55E3,0x6C265F,0x6C2A23]),
                           (42,[0x6AB8EF,0x6ACB20]), (40,[0x6CD8D9,0x6CDB79]),
                           (19,[0x6B5332]), (25,[0x6DE012])]:
        for va in addresses:
            recipe.integer(va, old, old)
    recipe.site(0x6DE031, b'\x02', b'\x02')
    label = bytes.fromhex('83e91e83c01e')
    recipe.site(0x6DE08E, label, label)
    recipe.site(0x6DE0D1, b'\x90' * 13, b'\x90' * 13)
    # The message popup's widening step and the store row's stack-count label
    # (docs/windows-changes-from-macos.md, items 24 and 26): guarded here as the
    # game has them; rewritten with 32-bit operands by the installer's
    # ResolutionPatch and by tools/build_native_engine.py.
    popup_step = bytes.fromhex('83442438288b44242083c128894c242883e8148d4c243089442420')
    recipe.site(0x6256FC, popup_step, popup_step)
    store_count = bytes.fromhex('33c983f8020f9ec18bd7897c242c4983e11583c1158bc12bd0894424288b44242003c28d8e340300008d54242089442420')
    recipe.site(0x6C2704, store_count, store_count)

    table_path = ROOT / 'third_party/Included/K1-Area-Map-Fixes-1.0.0 by derslok/More info/source/data/note_table.bin'
    table = table_path.read_bytes()
    if len(table) != notes.TABLE_ENTRIES * 16 or hashlib.sha256(table).hexdigest() != notes.TABLE_SHA256:
        raise ValueError('map-note table does not match the approved source')
    note_page = u32(1) + u32(notes.TABLE_ENTRIES) + notes.MAGIC + table + notes.build_lookup(0x876000)
    recipe.page(9, '.kmn', note_page)

    icon_page = bytearray(icons.EMBEDDED_PAYLOAD + icons.build_hit_test_wrapper(BLOCK_VA + 0x100))
    wrapper = notes.build_wrapper(0x876000 + notes.TABLE_OFFSET + len(table))
    icon_page[:notes.WRAPPER_SLOT] = wrapper + b'\x90' * (notes.WRAPPER_SLOT - len(wrapper))
    at = hit_test.HIT_TEST_X_BLOCK_VA - BLOCK_VA
    if icon_page[at:at + len(hit_test.EXPECTED)] != hit_test.EXPECTED:
        raise ValueError('hit-test source guard differs')
    icon_page[at:at + len(hit_test.REPLACEMENT)] = hit_test.REPLACEMENT
    icon_page += bytes(0x130 - len(icon_page))
    icon_page += minimap.build_wrapper(BLOCK_VA + 0x130, 0x694D50)
    recipe.page(0, '.kui', icon_page)
    recipe.hook(0x62B39B, minimap.CALLERS[0x62B39B], BLOCK_VA + 0x130, call=True)
    for va, old, target in [(0x6946F4,'e80747eeff',BLOCK_VA),
                            (0x694A39,'e87247eeff',BLOCK_VA+0x80),
                            (0x694AAC,'e8ff46eeff',BLOCK_VA+0x80)]:
        recipe.hook(va, bytes.fromhex(old), target, call=True)
    recipe.integer(0x75477C, 0x693300, BLOCK_VA + 0x100)

    lb = bytearray()
    for va, old, new, _ in letterbox.HOOKS:
        if len(new) <= len(old):
            recipe.site(va, old, new + b'\x90' * (len(old)-len(new)))
        else:
            target = 0x86E000 + len(lb)
            lb += new + letterbox.encode_jmp(target + len(new), va + len(old))
            recipe.hook(va, old, target)
    recipe.page(1, '.klb', lb)

    font_page = bytearray(struct.pack('<ffI',1.0,1.75,0) + bytes(fonts.MAX_TRACKED_FONTS * 4))
    scale_va = 0x86F000 + len(font_page)
    font_page += fonts.build_scale_fontinfo(scale_va, 0x86F000)
    for va, old, emit in [(fonts.TEXTOUTA_VA, fonts.TEXTOUTA_ORIGINAL, fonts.build_textout_stub),
                          (fonts.DRAW_VA, fonts.DRAW_ORIGINAL, fonts.build_draw_stub),
                          (fonts.LIST_ROW_VA, fonts.LIST_ROW_ORIGINAL, fonts.build_list_row_stub)]:
        target = 0x86F000 + len(font_page)
        font_page += emit(target, 0x86F004 if va == fonts.LIST_ROW_VA else scale_va)
        recipe.hook(va, old, target)
    recipe.page(2, '.kfs', font_page)
    recipe.page(3, '.kwl', wrap.build_stub(0x870000))
    recipe.site(wrap.HOOK_VA, wrap.ORIGINAL, wrap.build_patch(0x870000))
    recipe.page(4, '.ksc', stacks.build_stub(0x871000)[0])
    recipe.hook(stacks.BLOCK_VA, stacks.ORIGINAL, 0x871000)
    gutter_page, scroll_offset = gutter.build_stubs(0x872000)
    recipe.page(5, '.kgs', gutter_page)
    recipe.hook(gutter.FIT_VA, gutter.FIT_ORIGINAL, 0x872000)
    recipe.hook(gutter.SCROLL_VA, gutter.SCROLL_ORIGINAL, 0x872000 + scroll_offset)
    recipe.page(6, '.ktn', newline.build_stub(0x873000))
    recipe.hook(newline.HOOK_VA, newline.ORIGINAL, 0x873000)
    recipe.page(7, '.kmz', zoom.build_stub(0x874000))
    recipe.hook(zoom.SITE_VA, zoom.ORIGINAL, 0x874000)
    recipe.page(8, '.kfg', fog.build_stub(0x875000, fog.BASE_VIEWPORT))
    recipe.hook(fog.SITE_VA, fog.ORIGINAL, 0x875000, call=True)
    recipe.page(10, '.kmv', movies.build_stub(0x877000))
    recipe.hook(movies.HOOK_VA, movies.HOOK_ORIGINAL, 0x877000, feature=MOVIES)
    return recipe


def relocations(recipe):
    md = reloc.disassembler()
    runs = [(va, len(old)) for _, va, old, _ in recipe.runs()]
    inbound = reloc.scan_inbound(recipe, runs)
    for field in inbound:
        if not all(field + b in recipe.original for b in range(4)):
            raise ValueError(f'inbound field {field:08X} lacks a whole original guard')
    entries = reloc.entry_points(recipe, inbound)
    instructions, decoded = reloc.descend(md, recipe, entries)
    covered = {at for ins in instructions.values() for at in range(ins.address, ins.address+ins.size)}
    scanned = reloc.scan_block(recipe, covered)
    if scanned != decoded:
        raise ValueError('source relocation byte scan and disassembly disagree')
    fields = sorted([(kind,field) for field,kind in {**inbound, **decoded}.items()], key=lambda x:x[1])
    for delta in (0x1F7A3000, -0x500000):
        reloc.prove(md, recipe, fields, instructions, runs, delta=delta)
    return fields, len(instructions)


def build():
    recipe = assemble()
    fields, checked = relocations(recipe)
    data = bytearray(b'KMRPSRC1' + u32(1) + u32(BLOCK_VA) + u32(BLOCK_SIZE) + u32(11))
    for index in range(11):
        data += u32(0x40 if index == 2 else 0x20)
    data += recipe.block
    runs = recipe.runs()
    data += u32(len(runs))
    for feature, va, old, new in runs:
        data += u32(feature) + u32(va) + u32(len(old)) + old + new
    data += u32(len(fields))
    for kind, field in fields:
        data += u32({'IN':1,'OUT':2,'ABS':3}[kind]) + u32(field)
    data += checksum(data)
    return bytes(data), recipe, fields, checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data, recipe, fields, checked = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    if args.out.read_bytes() != data:
        raise ValueError('source patch template read-back failed')
    print(f'{len(recipe.runs())} guarded sites, {len(fields)} relocations, {checked} instructions proved at two bases')
    print('pages: ' + ', '.join(f'{name}={length}' for name,length in recipe.lengths.items()))
    print(f'{args.out}: {len(data)} bytes, SHA-256 {hashlib.sha256(data).hexdigest()}')


if __name__ == '__main__':
    main()
