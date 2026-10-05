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

Measured on the build of 2026-10-05: 248,545,368 bytes with every object (30,848
objects), 128,804,860 bytes like this (3,758 objects; 56,349 of the sets' 62,898
files left to the module). 45 sets are rebuilt whole, 20 in part (32 to 329 files
differ and are stored), and 1280x1080 is outside the blend and stored whole.
testing/regression/Test-NativeAssetsBank.py checks the bank.

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

ROOT = Path(__file__).resolve().parents[1]
# The bank's first eight bytes name its compression: the Windows Compression API's
# XPRESS with Huffman (algorithm 4) or LZMS (5). XPRESS is the one shipped. LZMS,
# --lzms, makes the bank about a fifth smaller and about four times slower to unpack
# (measured 2026-10-05 on the common files: 87.7 MB and 0.64 s against 68.3 MB and
# 2.57 s), and the module unpacks the common files every time the game starts.
MAGIC = b'KNAST002'
MAGIC_LZMS = b'KNASL002'
ALGORITHMS = {MAGIC: 4, MAGIC_LZMS: 5}
HELPER_SOURCE = ROOT / 'macos/tools/kmrp-guiblend.c'
# The module's own flags for this file (build_native_runtime.cmd), without the
# define that drops main(): the same code, as a program.
HELPER_FLAGS = ['/nologo', '/O2', '/fp:strict', '/MT', '/TC']
# What the helper reads from a set (its caption widths and its font's metrics).
HELPER_INPUTS = ('kmrp_prompts.txt', 'dialogfont16x16.txi')


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
            (inputs / name).write_bytes(source.read(name))
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


def build(resources, out, helper=None, every_object=False, lzms=False):
    magic = MAGIC_LZMS if lzms else MAGIC
    objects = {}
    groups = []
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

    compressor = Compressor(ALGORITHMS[magic])
    try:
        left_out = set()
        for number, archive in enumerate(archives):
            entries = []
            made = rebuilt.get(archive.name, set())
            with zipfile.ZipFile(archive) as source:
                for name in source.namelist():
                    data = source.read(name)
                    digest = hashlib.sha256(data).digest()
                    # A helper input is kept even where the helper writes it back unchanged.
                    if name in made and name not in HELPER_INPUTS:
                        left_out.add(digest)
                    elif digest not in objects:
                        objects[digest] = (len(data), compressor.compress(data))
                    entries.append((name, digest))
            if number == 0:
                # Hash-pinned by tools/prepare_sdl3.ps1; loaded from the module's
                # private cache (InitSdl in K1ControllerBackend.cpp).
                data = (resources.parents[1] / 'deps/kmrp-sdl3.dll').read_bytes()
                digest = hashlib.sha256(data).digest()
                objects[digest] = (len(data), compressor.compress(data))
                entries.append(('kmrp-sdl3.dll', digest))
            size = (0, 0) if number == 0 else tuple(map(int, archive.stem[4:].split('x')))
            groups.append((size, entries))
            print(f'[{number + 1}/67] {archive.name}: {len(entries)} files', flush=True)
        table = table_path.read_bytes()
        digest = hashlib.sha256(table).digest()
        objects[digest] = (len(table), compressor.compress(table))
        blob = bytearray(magic + struct.pack('<II', len(groups), len(objects)))
        blob += digest
        for (width, height), entries in groups:
            blob += struct.pack('<III', width, height, len(entries))
            for name, key in entries:
                blob += text(name) + key
        for key, (size, compressed) in objects.items():
            blob += key + struct.pack('<II', size, len(compressed)) + compressed
        out.mkdir(parents=True, exist_ok=True)
        target = out / 'native-assets.bin'
        target.write_bytes(blob)
        build_id = hashlib.sha256(blob).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != build_id:
            raise ValueError('Native asset read-back failed')
        (out / 'NativeAssets.generated.h').write_text(f'#pragma once\n#define KMRP_ASSET_BUILD L"{build_id}"\n')
        (out / 'native-assets.rc').write_text('101 RCDATA "native-assets.bin"\n')
        print(f'{len(objects)} objects stored, {len(left_out - set(objects))} left to the module to make, '
              f'{len(blob)} bytes, SHA256 {build_id}', flush=True)
    finally:
        compressor.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--resources', type=Path, default=ROOT / 'build/kmrp/resources')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/native-runtime')
    parser.add_argument('--helper', type=Path, help='the blend helper, already built (x86, the module\'s flags)')
    parser.add_argument('--every-object', action='store_true',
                        help='store every file of every set, as before 2026-10-05')
    parser.add_argument('--lzms', action='store_true',
                        help='LZMS instead of XPRESS-Huffman: a smaller bank, slower to unpack at every start')
    args = parser.parse_args()
    build(args.resources, args.out, args.helper, args.every_object, args.lzms)
