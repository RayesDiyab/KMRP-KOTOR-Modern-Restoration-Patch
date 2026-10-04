#!/usr/bin/env python3
"""Embed the existing KMRP resource bank in the one native module.

Generated game-derived data stays under ignored build/. Everything the installer
installs is in it, the controller's badges and screen included (the installer
installs those with the controller off too, since the shared layouts name them),
plus the SDL library the controller's non-Xbox pads need, which the module
unpacks to its own folder and loads from there (the installer put it beside the
game until 2026-10-04). Each content object is stored once.
"""
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class Compressor:
    def __init__(self):
        self.api = ctypes.WinDLL('cabinet', use_last_error=True)
        self.api.CreateCompressor.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self.api.Compress.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.api.CloseCompressor.argtypes = [ctypes.c_void_p]
        self.handle = ctypes.c_void_p()
        if not self.api.CreateCompressor(4, None, ctypes.byref(self.handle)):
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


def build(resources, out):
    objects = {}
    groups = []
    compressor = Compressor()
    try:
        archives = [resources / 'override-common.zip'] + sorted(resources.glob('gui-*.zip'))
        if len(archives) != 67:
            raise ValueError('Expected common resources and all 66 resolution sets')
        for number, archive in enumerate(archives):
            entries = []
            with zipfile.ZipFile(archive) as source:
                for name in source.namelist():
                    data = source.read(name)
                    digest = hashlib.sha256(data).digest()
                    if digest not in objects:
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
        table = (resources.parent / 'gui-blend.bin').read_bytes()
        digest = hashlib.sha256(table).digest()
        objects[digest] = (len(table), compressor.compress(table))
        blob = bytearray(b'KNAST001' + struct.pack('<II', len(groups), len(objects)))
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
        print(f'{len(objects)} unique objects, {len(blob)} bytes, SHA256 {build_id}', flush=True)
    finally:
        compressor.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, default=ROOT / 'build/kmrp/resources')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/native-runtime')
    args = parser.parse_args()
    build(args.resources, args.out)
