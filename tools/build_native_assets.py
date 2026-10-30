#!/usr/bin/env python3
"""Embed the existing KMRP resource bank in the one native module.

Generated game-derived data stays under ignored build/. Everything the installer
installs is in it, the controller's badges and screen included (the installer
installs those with the controller off too, since the shared layouts name them),
plus the SDL library the controller's non-Xbox pads need, which the module
unpacks to its own folder and loads from there (the installer put it beside the
game until 2026-10-04). Each content object is stored once.

Since 2026-10-05 the bank leaves out what the module can make itself. The module
carries the blend helper (macos/tools/kmrp-guiblend.c, KmrpGuiBlend), which writes a
resolution's layouts, badges, prompt manifest and HUD box from gui-blend.bin; for
most listed sizes what it writes is the build's own set, byte for byte
(testing/regression/Test-GuiBlendHelper.py has checked that for the anchors since
the table existed). So this script runs that helper for every set, built with the
module's own compiler flags, and an object is stored only if some file that needs it
is NOT what the helper writes: a font, a file of a set outside the blend, or a file
the blend makes differently than the build did. A set's index still names every one
of its files with its SHA-256: the module writes the files it has, runs the helper,
puts the stored files back over the helper's where both exist, and holds every file
against the index (K1RuntimeAssets.cpp). The result is the build's set at every
listed size, as before.

Since 2026-10-30 a set's index leaves out the layouts Live Adaptive Layout makes at run
time (the 73 screens of macos/tools/kmrp-livelayout-table.h, LIVE_LAYOUTS below): the
module lays each out from the game's own file or a mod's, and deletes what the helper
writes of them from the set. The build's gui-*.zip still hold them, for
testing/regression/Test-LiveLayout.py and for the Mac, whose installer copies sets.

Measured on the build of 2026-10-05: 248,545,368 bytes with every object (30,848
objects), 128,804,860 bytes like this (3,758 objects; 56,349 of the sets' 62,898
files left to the module). 45 sets are rebuilt whole, 20 in part (32 to 329 files
differ and are stored), and 1280x1080 is outside the blend and stored whole.
testing/regression/Test-NativeAssetsBank.py checks the bank.

The fonts are one set per style, in the common group under private names, and the
module writes the chosen style's at the drawn size (K1RuntimeAssets.cpp
ApplyTextPreferences): kmrfogNN the original atlases (tools/build_original_fonts.py),
kmrfhoNN HD Original (assets/hd-original-fonts, the default since 2026-10-18; its
fnt_galahad14 is made here from the game's files, see hd_original), kmrfhdNN
Old HD (assets/hd-fonts). Until 2026-10-18 kmrfpcNN held an "Original Sharpened" set,
the original atlases enlarged; HD Original replaced it.

Run from src/controller-native/build_native_runtime.cmd, where the x86 compiler is on
the path; --helper names a helper already built.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import shutil
import struct
import subprocess
import tempfile
import zipfile
import os
import re
import build_original_fonts
import kmrp_pack
from build_scaled_fonts import FONT_RESREFS

ROOT = Path(__file__).resolve().parents[1]
# The art pack (tools/kmrp_pack.py), which the installer writes beside the module.
PACK = 'kmrp-assets.pack'
# build_native_runtime.cmd makes the pack again when this differs from the
# font-style-assets.version it wrote: 8 the sets without Live Adaptive Layout's screens
# (2026-10-30), 7 HD Original's atlases drawn from the KMRP Original HD
# fonts (fonts/otf, 2026-10-22), 6 the round o in HD Original's body and light fonts
# (2026-10-21), 5 the pack (2026-10-19), 4 the last bank.
ASSETS_VERSION = 8
# What the bank, KNAST002, used until 2026-10-19 (still the controller patch's,
# tools/build_controller_assets.py): the Windows Compression API's XPRESS with Huffman.
MAGIC = b'KNAST002'
ALGORITHMS = {MAGIC: 4}
HELPER_SOURCE = ROOT / 'macos/tools/kmrp-guiblend.c'
# The module's own flags for this file (build_native_runtime.cmd), without the
# define that drops main(): the same code, as a program.
HELPER_FLAGS = ['/nologo', '/O2', '/fp:strict', '/MT', '/TC']
# What the helper reads from a set (its caption widths and its font's metrics).
HELPER_INPUTS = ('kmrp_prompts.txt', 'dialogfont16x16.txi')
FONT_FILES = {name + extension for name in FONT_RESREFS for extension in ('.tga', '.txi')}
LIVE_TABLE = ROOT / 'macos/tools/kmrp-livelayout-table.h'


def live_layouts(table: Path = LIVE_TABLE) -> frozenset:
    """The screens the module lays out at run time, read from the table it is compiled
    with (LL_FILES), lower case."""
    text = table.read_text(encoding='utf-8')
    block = text[text.index('static const LLFile LL_FILES[] = {'):]
    block = block[:block.index('\n};')]
    names = frozenset(name.lower() for name in re.findall(r'\{ "([^"]+\.gui)"', block))
    if len(names) < 70:
        raise ValueError(f'{table}: only {len(names)} screens found in LL_FILES')
    return names


LIVE_LAYOUTS = live_layouts()


# The size the HD styles are baked at, and the one the runtime's text sizes are reckoned
# from (K1RuntimeAssets.cpp, kHdBakeScale and kSizeReferenceScale).
HD_BAKE_SCALE = 6.0
SIZE_REFERENCE_SCALE = 3.0

# HD Original's atlases. 17 are drawn from fonts and kept in assets/hd-original-fonts.
# fnt_galahad14 has no font to draw it from, so it is the game's own letters enlarged
# (build_original_fonts.enlarged). That is the game's art, so it is never committed:
# it is made from the game's files at every build, into build/ (the maintainer,
# 2026-10-19).
MADE_AT_BUILD = ('fnt_galahad14',)
ORIGINAL_FONTS = ROOT / 'build/native-runtime/original-fonts'
HD_ORIGINAL_MADE = ROOT / 'build/native-runtime/hd-original-fonts'


def make_hd_original(original_fonts=ORIGINAL_FONTS):
    for name in MADE_AT_BUILD:
        build_original_fonts.enlarged(original_fonts, name, HD_ORIGINAL_MADE, HD_BAKE_SCALE)


def hd_original(name, extension):
    """Where HD Original's atlas or TXI for `name` is; made first if it is one of ours
    and missing."""
    if name not in MADE_AT_BUILD:
        return ROOT / 'assets/hd-original-fonts' / (name + extension)
    path = HD_ORIGINAL_MADE / (name + extension)
    if not path.is_file():
        make_hd_original()
    return path


def fontheight(text):
    return float(re.search(r'(?im)^fontheight\s+([\d.]+)', text)[1])


def shared_font_txi(name, height):
    """The TXI the module writes for the default style, HD Original, at the default
    size, which the blend helper measures captions with: K1RuntimeAssets.cpp
    ApplyTextPreferences (the height from Old HD's TXI, FontTargetHeight; the
    dimensions scaled to it, FontTxiAtHeight; the atlas fitted to it, FitAtlas), in
    the same single precision."""
    f32 = lambda v: struct.unpack('<f', struct.pack('<f', v))[0]
    reference = f32(f32(f32(fontheight((ROOT / 'assets/hd-fonts' / (name + '.txi')).read_text())) *
                        SIZE_REFERENCE_SCALE) / HD_BAKE_SCALE)
    scale_micros = (max(720, int(height)) * 1000000 + 360) // 720
    numerator, denominator = int(f32(reference * 100.0) + 0.5) * scale_micros, 3000000
    rounded, remainder = divmod(numerator, denominator)
    if remainder * 2 > denominator or (remainder * 2 == denominator and rounded & 1):
        rounded += 1
    target = f32(f32(rounded) / f32(100.0))
    text = hd_original(name, '.txi').read_text()
    own = f32(fontheight(text))
    factor = target / own
    atlas = hd_original(name, '.tga').read_bytes()
    width = atlas[12] | atlas[13] << 8
    fitted = int(f32(width * f32(target / own)) + 0.5)
    keys = {'fontheight', 'baselineheight', 'texturewidth', 'spacingR', 'spacingB'}
    out = []
    for line in text.splitlines():
        p = line.split()
        if len(p) == 2 and p[0] in keys:
            value = (target if p[0] == 'fontheight' else fitted / 100.0 if p[0] == 'texturewidth'
                     else float(p[1]) * factor)
            line = f'{p[0]} {value:.6f}'
        out.append(line)
    return ('\n'.join(out) + '\n').encode('ascii')


class Compressor:
    def __init__(self, algorithm=4):
        self.api = ctypes.WinDLL('cabinet', use_last_error=True)
        self.api.CreateCompressor.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self.api.Compress.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.api.CloseCompressor.argtypes = [ctypes.c_void_p]
        self.handle = ctypes.c_void_p()
        if not self.api.CreateCompressor(algorithm, None, ctypes.byref(self.handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def compress(self, data):
        size = ctypes.c_size_t()
        self.api.Compress(self.handle, data, len(data), None, 0, ctypes.byref(size))
        out = ctypes.create_string_buffer(size.value)
        if not self.api.Compress(self.handle, data, len(data), out, len(out), ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return out.raw[:size.value]

    def close(self):
        self.api.CloseCompressor(self.handle)


def text(value):
    data = value.encode('ascii')
    if not data or len(data) > 255 or '/' in value or '\\' in value or '..' in value:
        raise ValueError(f'Unsafe embedded asset name {value!r}')
    return struct.pack('<H', len(data)) + data


def build_helper(out: Path) -> Path:
    """The blend helper as an x86 program, compiled as the module compiles it."""
    if shutil.which('cl') is None:
        raise RuntimeError('cl is not on the path: run this from build_native_runtime.cmd, or pass --helper')
    work = out / 'bank-helper'
    work.mkdir(parents=True, exist_ok=True)
    target = work / 'kmrp-guiblend.exe'
    subprocess.run(['cl', *HELPER_FLAGS, str(HELPER_SOURCE), f'/Fo{work}\\', f'/Fe{target}'],
                   check=True, stdout=subprocess.DEVNULL)
    return target


def rebuilt_names(helper: Path, table: Path, archive: Path, work: Path) -> tuple[set, int]:
    """The names of the set's files that the helper writes exactly as the set has them,
    and how many it writes differently."""
    width, height = archive.stem[4:].split('x')
    inputs, out = work / f'in-{archive.stem}', work / f'out-{archive.stem}'
    inputs.mkdir()
    with zipfile.ZipFile(archive) as source:
        digests = {name: hashlib.sha256(source.read(name)).digest() for name in source.namelist()}
        for name in HELPER_INPUTS:
            (inputs / name).write_bytes(shared_font_txi(name[:-4], height) if name in FONT_FILES else source.read(name))
    done = subprocess.run([str(helper), str(table), width, height, str(out), str(inputs)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    shutil.rmtree(inputs)
    if done.returncode == 2:
        # A listed size the blend does not cover (the helper's own answer, the one
        # KmrpGuiBlendCovers gives the module): the set keeps all its files.
        return set(), -1
    if done.returncode:
        raise RuntimeError(f'{archive.name}: the helper failed: {done.stderr.strip()}')
    same, different = set(), 0
    for path in out.iterdir():
        if path.name not in digests:
            raise ValueError(f'{archive.name}: the helper wrote {path.name}, which the set does not have')
        if hashlib.sha256(path.read_bytes()).digest() == digests[path.name]:
            same.add(path.name)
        else:
            different += 1
    shutil.rmtree(out)
    return same, different


def build(resources, out, helper=None, every_object=False):
    objects = {}
    groups = []
    original_fonts = out / 'original-fonts'
    texture_pack = Path(os.environ.get('KMRP_TEXTURE_PACK', str(ROOT / 'build-inputs/swpc_tex_gui.erf')))
    build_original_fonts.build(texture_pack, original_fonts)
    make_hd_original(original_fonts)
    table_path = resources.parent / 'gui-blend.bin'
    archives = [resources / 'override-common.zip'] + sorted(resources.glob('gui-*.zip'))
    if len(archives) != 67:
        raise ValueError('Expected common resources and all 66 resolution sets')

    # What the module will make for itself, per set.
    rebuilt = {}
    if not every_object:
        helper = helper or build_helper(out)
        with tempfile.TemporaryDirectory() as work:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda a: rebuilt_names(helper, table_path, a, Path(work)), archives[1:]))
        for archive, (same, different) in zip(archives[1:], results):
            rebuilt[archive.name] = same
            print(f'{archive.name}: ' + ('outside the blend, every file stored' if different < 0 else
                                         f'the helper rebuilds {len(same)} files, {different} differ'), flush=True)

    left_out = set()
    for number, archive in enumerate(archives):
        entries = []
        made = rebuilt.get(archive.name, set())
        with zipfile.ZipFile(archive) as source:
            for name in source.namelist():
                # Fonts have one shared source per style, below. Live sizing
                # changes native font metrics, never rasterizes another atlas.
                if name in FONT_FILES or (number and name.lower() in LIVE_LAYOUTS):
                    continue
                data = source.read(name)
                digest = hashlib.sha256(data).digest()
                # A helper input is kept even where the helper writes it back unchanged.
                if name in made and name not in HELPER_INPUTS:
                    left_out.add(digest)
                elif digest not in objects:
                    objects[digest] = data
                entries.append((name, digest))
        if number == 0:
            # Each font style is resolution independent: its sources under
            # private names, which K1RuntimeAssets selects from at runtime.
            for index, name in enumerate(FONT_RESREFS):
                for extension in ('.tga', '.txi'):
                    for prefix, path in (('kmrfog', original_fonts / f'kmrfog{index:02d}{extension}'),
                                         ('kmrfho', hd_original(name, extension)),
                                         ('kmrfhd', ROOT / 'assets/hd-fonts' / (name + extension))):
                        data = path.read_bytes()
                        digest = hashlib.sha256(data).digest()
                        objects.setdefault(digest, data)
                        entries.append((f'{prefix}{index:02d}{extension}', digest))
            # Hash-pinned by tools/prepare_sdl3.ps1; loaded from the module's
            # private cache (InitSdl in K1ControllerBackend.cpp).
            data = (resources.parents[1] / 'deps/kmrp-sdl3.dll').read_bytes()
            digest = hashlib.sha256(data).digest()
            objects.setdefault(digest, data)
            entries.append(('kmrp-sdl3.dll', digest))
        size = (0, 0) if number == 0 else tuple(map(int, archive.stem[4:].split('x')))
        groups.append((size, entries))
        print(f'[{number + 1}/67] {archive.name}: {len(entries)} files', flush=True)
    table = table_path.read_bytes()
    table_key = hashlib.sha256(table).digest()
    objects.setdefault(table_key, table)
    out.mkdir(parents=True, exist_ok=True)
    target = out / PACK
    print(f'packing {len(objects)} files, {sum(map(len, objects.values())) / 2**20:.1f} MiB (filters and LZMA, '
          f'about a minute and a half)', flush=True)
    build_id = kmrp_pack.write_pack(target, groups, objects, table_key)
    if kmrp_pack.read_pack(target)[0] != build_id:
        raise ValueError('Art pack read-back failed')
    (out / 'NativeAssets.generated.h').write_text(f'#pragma once\n#define KMRP_ASSET_BUILD L"{build_id}"\n')
    for retired in ('native-assets.bin', 'native-assets.rc', 'native-assets.res'):
        (out / retired).unlink(missing_ok=True)
    (out / 'font-style-assets.version').write_text(f'{ASSETS_VERSION}\n')
    print(f'{len(objects)} objects stored, {len(left_out - set(objects))} left to the module to make, '
          f'{target.stat().st_size} bytes, SHA256 {build_id}', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--resources', type=Path, default=ROOT / 'build/kmrp/resources')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/native-runtime')
    parser.add_argument('--helper', type=Path, help='the blend helper, already built (x86, the module\'s flags)')
    parser.add_argument('--every-object', action='store_true',
                        help='store every file of every set, as before 2026-10-05')
    args = parser.parse_args()
    build(args.resources, args.out, args.helper, args.every_object)
