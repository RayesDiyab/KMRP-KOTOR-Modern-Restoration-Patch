#!/usr/bin/env python3
"""KMRP's art pack, kmrp-assets.pack: every file KMRP's module unpacks into its cache, made as
small as it can be without losing a byte, for the installer to carry (2026-10-19).

The pack replaces the bank inside the module (KNAST002, XPRESS, 109 MB of a 113 MB module):
the installer writes it beside the module, in the game's patches folder, and the module and
the installer read it from there (src/controller-native/K1AssetPack.cpp decodes it,
K1RuntimeAssets.cpp reads it). The maintainer's goals for it, 2026-10-19: the smallest
installer, and every resolution ready before the game starts ("smoother user experience
comes priority"), for which the installer unpacks it once. It is meant for the Mac too (the
maintainer, 2026-10-19: "Mac must adapt this new bank and whole process as well"), so
nothing in it is Windows' own: macos/tools/make_kmrp_assets.py can write its groups with
write_pack, and K1AssetPack.cpp is plain C++.

Each file is first made easier to compress, in a way undone exactly (a filter), then
compressed with LZMA (Igor Pavlov's, the 7-Zip format's; written here by Python's liblzma,
read by the LZMA SDK's decoder, third_party/lzma-sdk). Measured on the bank of 2026-10-19
against XPRESS (scratch trials, a sample of each family): the HD portraits, interface art
and panels 48% with filter 1, 59% with plain LZMA; the DXT loading screens and maps 59%
with filters 2 and 3, 62% with plain LZMA. Small files are compressed together, one stream
for each size's own files (3.5 MiB against 6.9 MiB one stream a file, for the sizes' 2,297
stored files): what one size needs then costs one to eight small streams.

The file, little endian:

    "KMRPAK01"
    32 bytes   SHA-256 of every byte after this field: the build's identity, which names
               the module's cache and which the module holds against KMRP_ASSET_BUILD
    u32        bytes from the start of the file to the first block (the index's end)
    u32        groups
    u32        blocks
    u32        objects
    32 bytes   the object that is gui-blend.bin
    groups     u32 width, u32 height, u32 entries; per entry u16 length, name, 32-byte object.
               (0, 0) the common files; every other group the set for that size
    blocks     u32 offset in the file, u32 stored bytes, u32 unpacked bytes, 5 bytes of LZMA
               properties (the lc/lp/pb byte, u32 dictionary size): a raw LZMA stream with an
               end marker, which unpacks to its objects one after another
    objects    32-byte SHA-256 of the file, u32 size, u32 block, u32 offset in the block's
               unpacked bytes, u8 filter
    the blocks

A file is stored once, whatever names it has in however many groups. An object's bytes in its
block are the file after its filter; undoing the filter gives the file, held against its
SHA-256. The filters, each the same size as the file:

    0  none
    1  an uncompressed true-colour TGA (type 2, no colour map, 24 or 32 bits a pixel): its
       width x height x channels pixel bytes after the 18-byte header and the ID field; blue
       and red first less green, modulo 256, then every byte less the MED (LOCO-I)
       prediction from the same channel of the pixels to its left, above, and above-left
       in the file's order (0 outside the image), modulo 256. The rest is unchanged.
    2  DXT1 in a TPC: from byte 128, the whole 8-byte blocks that follow, regrouped: the
       4 colour-endpoint bytes of every block, then the 4 index bytes of every block. The
       rest (a partial block, the TXI after the data) is unchanged.
    3  DXT5 in a TPC, the same with 16-byte blocks: 2 alpha-endpoint bytes, 6 alpha-index
       bytes, 4 colour-endpoint bytes, 4 colour-index bytes.

A filter is used only where it makes that file smaller. Every block is unpacked again here
and compared with what was packed; the module's own decoder reads the whole pack back, every
file against its hash, in testing/regression/asset_pack_harness.cpp (Test-NativeAssetsBank.py
runs it).
"""
from __future__ import annotations

import hashlib
import lzma
import os
import struct
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

MAGIC = b'KMRPAK01'
HEADER = 8 + 32 + 4 * 4 + 32
# Files of at least this size are a block of their own, so each can be read alone (the
# fonts, read one at a time at the size in use) and the blocks unpacked side by side.
OWN_BLOCK = 512 << 10
# Small files share a block up to this many unpacked bytes.
SHARED_BLOCK = 8 << 20
PRESET = 9 | lzma.PRESET_EXTREME
TPC_HEADER = 128


def _med(q: np.ndarray) -> np.ndarray:
    """Each byte less the MED prediction from its left, upper and upper-left neighbours."""
    p = q.astype(np.int16)
    a = np.zeros_like(p); a[:, 1:] = p[:, :-1]
    b = np.zeros_like(p); b[1:, :] = p[:-1, :]
    c = np.zeros_like(p); c[1:, 1:] = p[:-1, :-1]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    pred = np.where(c >= hi, lo, np.where(c <= lo, hi, a + b - c))
    return ((p - pred) & 0xFF).astype(np.uint8)


def _tga_pixels(data: bytes):
    """(start, height, width, channels) of an uncompressed true-colour TGA's pixels, or None."""
    if len(data) < 18 or data[1] != 0 or data[2] != 2:
        return None
    width, height, bits = struct.unpack_from('<HHB', data, 12)
    channels = bits // 8
    start = 18 + data[0]
    if bits not in (24, 32) or not width or not height or start + width * height * channels > len(data):
        return None
    return start, height, width, channels


def _dxt_layout(data: bytes, filter_id: int):
    """(block size, field widths) for filters 2 and 3 where the file can take them, or None."""
    if len(data) < TPC_HEADER + 16:
        return None
    block = 8 if filter_id == 2 else 16
    fields = (4, 4) if filter_id == 2 else (2, 6, 4, 4)
    return block, fields


def apply_filter(data: bytes, filter_id: int) -> bytes | None:
    """The file through a filter, or None where the filter does not apply to it."""
    if filter_id == 0:
        return data
    if filter_id == 1:
        layout = _tga_pixels(data)
        if not layout:
            return None
        start, height, width, channels = layout
        end = start + height * width * channels
        px = np.frombuffer(data, np.uint8, end - start, start).reshape(height, width, channels).astype(np.int16)
        q = px.copy()
        q[..., 0] = (px[..., 0] - px[..., 1]) & 0xFF
        q[..., 2] = (px[..., 2] - px[..., 1]) & 0xFF
        return data[:start] + _med(q.astype(np.uint8)).tobytes() + data[end:]
    if filter_id in (2, 3):
        layout = _dxt_layout(data, filter_id)
        if not layout:
            return None
        block, fields = layout
        count = (len(data) - TPC_HEADER) // block
        records = np.frombuffer(data, np.uint8, count * block, TPC_HEADER).reshape(count, block)
        parts, at = [], 0
        for width in fields:
            parts.append(np.ascontiguousarray(records[:, at:at + width]).tobytes())
            at += width
        end = TPC_HEADER + count * block
        return data[:TPC_HEADER] + b''.join(parts) + data[end:]
    raise ValueError(f'unknown filter {filter_id}')


def candidates(name: str, data: bytes) -> list[int]:
    """The filters worth trying on a file."""
    lower = name.lower()
    if lower.endswith('.tga') and _tga_pixels(data):
        return [0, 1]
    if lower.endswith('.tpc') and len(data) >= TPC_HEADER + 16 and struct.unpack_from('<I', data, 0)[0]:
        # A compressed TPC: encoding 2 is DXT1, 4 is DXT5.
        return [0, 2] if data[12] == 2 else [0, 3] if data[12] == 4 else [0]
    return [0]


def _settings(size: int, filter_id: int, data: bytes) -> list[dict]:
    """LZMA settings to try: the preset's, and for four-byte pixels after filter 1, literal
    and position bits for four-byte steps (lc=0 lp=2 pb=2, measured smaller on most)."""
    dictionary = max(1 << 16, min(64 << 20, 1 << max(0, (size - 1).bit_length())))
    base = {'id': lzma.FILTER_LZMA1, 'preset': PRESET, 'dict_size': dictionary}
    tries = [base]
    if filter_id == 1 and _tga_pixels(data)[3] == 4:
        tries.append({**base, 'lc': 0, 'lp': 2, 'pb': 2})
    return tries


def _properties(settings: dict) -> bytes:
    lc, lp, pb = settings.get('lc', 3), settings.get('lp', 0), settings.get('pb', 2)
    return bytes([(pb * 5 + lp) * 9 + lc]) + struct.pack('<I', settings['dict_size'])


def _compress(data: bytes, settings: dict) -> bytes:
    return lzma.compress(data, format=lzma.FORMAT_RAW, filters=[settings])


def _unpack(stream: bytes, properties: bytes, size: int) -> bytes:
    byte = properties[0]
    settings = {'id': lzma.FILTER_LZMA1, 'lc': byte % 9, 'lp': byte // 9 % 5, 'pb': byte // 45,
                'dict_size': struct.unpack_from('<I', properties, 1)[0]}
    out = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[settings]).decompress(stream, size)
    if len(out) != size:
        raise ValueError('a block unpacked to the wrong size')
    return out


def _best_single(job):
    """A file that is a block of its own: every filter and setting, the smallest kept."""
    name, data = job
    best = None
    for filter_id in candidates(name, data):
        filtered = apply_filter(data, filter_id)
        if filtered is None:
            continue
        for settings in _settings(len(filtered), filter_id, filtered):
            stream = _compress(filtered, settings)
            if _unpack(stream, _properties(settings), len(filtered)) != filtered:
                raise ValueError(f'{name}: LZMA did not give the file back')
            if best is None or len(stream) < len(best[2]):
                best = (filter_id, _properties(settings), stream)
    return best


def _choose_filter(job):
    """A file that shares a block: the filter that makes it smallest on its own."""
    name, data = job
    choices = candidates(name, data)
    if choices == [0]:
        return 0
    sizes = []
    for filter_id in choices:
        filtered = apply_filter(data, filter_id)
        if filtered is not None:
            sizes.append((len(_compress(filtered, _settings(len(filtered), filter_id, filtered)[0])), filter_id))
    return min(sizes)[1]


def _compress_block(data):
    settings = _settings(len(data), 0, data)[0]
    stream = _compress(data, settings)
    if _unpack(stream, _properties(settings), len(data)) != data:
        raise ValueError('LZMA did not give a block back')
    return _properties(settings), stream


def write_pack(path: Path, groups, objects: dict, table_key: bytes, workers: int | None = None) -> str:
    """Writes the pack and returns its identity (hex). `groups`: [((width, height), [(name,
    key)])], the common group (0, 0) first; `objects`: {key: bytes}, every file once, the
    table among them; `table_key`: gui-blend.bin's key."""
    workers = workers or max(1, min(8, (os.cpu_count() or 2) - 1))
    # Each object belongs to the first group that names it, under that name.
    owner = {}
    for number, (_, entries) in enumerate(groups):
        for name, key in entries:
            if key in objects and key not in owner:
                owner[key] = (number, name)
    owner.setdefault(table_key, (len(groups), 'gui-blend.bin'))
    for key in objects:
        if key not in owner:
            raise ValueError('an object no group names')
    singles = [key for key in objects if len(objects[key]) >= OWN_BLOCK]
    shared = [key for key in objects if len(objects[key]) < OWN_BLOCK]
    blocks = []         # (properties, stream, unpacked size)
    placed = {}         # key -> (size, block, offset, filter)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = pool.map(_best_single, [(owner[k][1], objects[k]) for k in singles], chunksize=1)
        filters = dict(zip(shared, pool.map(_choose_filter, [(owner[k][1], objects[k]) for k in shared], chunksize=16)))
        for key, (filter_id, properties, stream) in zip(singles, results):
            placed[key] = (len(objects[key]), len(blocks), 0, filter_id)
            blocks.append((properties, stream, len(objects[key])))
        # The small files by owner, the font metrics (read at every change of size) apart,
        # in name order within a kind, so like follows like.
        bins = {}
        for key in shared:
            number, name = owner[key]
            kind = 'metrics' if name.lower().startswith('kmrf') and name.lower().endswith('.txi') else 'files'
            bins.setdefault((number, kind), []).append(key)
        chunks = []
        for (number, kind), keys in sorted(bins.items()):
            keys.sort(key=lambda k: (owner[k][1].rsplit('.', 1)[-1].lower(), owner[k][1].lower()))
            chunk, size = [], 0
            for key in keys:
                if chunk and size + len(objects[key]) > SHARED_BLOCK:
                    chunks.append(chunk); chunk, size = [], 0
                chunk.append(key); size += len(objects[key])
            if chunk:
                chunks.append(chunk)
        joined = []
        for chunk in chunks:
            parts, offset = [], 0
            for key in chunk:
                filtered = apply_filter(objects[key], filters[key])
                placed[key] = (len(objects[key]), len(blocks) + len(joined), offset, filters[key])
                parts.append(filtered); offset += len(filtered)
            joined.append(b''.join(parts))
        for data, (properties, stream) in zip(joined, pool.map(_compress_block, joined, chunksize=1)):
            blocks.append((properties, stream, len(data)))

    index = bytearray()
    for (width, height), entries in groups:
        index += struct.pack('<III', width, height, len(entries))
        for name, key in entries:
            encoded = name.encode('ascii')
            if not encoded or len(encoded) > 255 or '/' in name or '\\' in name or '..' in name:
                raise ValueError(f'unsafe name {name!r}')
            index += struct.pack('<H', len(encoded)) + encoded + key
    start = HEADER + len(index) + 17 * len(blocks) + 45 * len(placed)
    table = bytearray()
    offset = start
    for properties, stream, unpacked in blocks:
        table += struct.pack('<III', offset, len(stream), unpacked) + properties
        offset += len(stream)
    if offset >= 1 << 32:
        raise ValueError('the pack is over 4 GiB')
    for key, (size, block, at, filter_id) in placed.items():
        table += key + struct.pack('<IIIB', size, block, at, filter_id)
    body = (struct.pack('<IIII', start, len(groups), len(blocks), len(placed)) + table_key + bytes(index) +
            bytes(table) + b''.join(stream for _, stream, _ in blocks))
    identity = hashlib.sha256(body).digest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MAGIC + identity + body)
    return identity.hex()


def read_pack(path: Path):
    """(identity hex, groups, {key: (size, block, offset, filter)}, blocks, table key, bytes)."""
    data = path.read_bytes()
    if data[:8] != MAGIC:
        raise ValueError('not a KMRP art pack')
    identity = data[8:40]
    if hashlib.sha256(data[40:]).digest() != identity:
        raise ValueError('the pack does not match its identity')
    start, group_count, block_count, object_count = struct.unpack_from('<IIII', data, 40)
    table_key = data[56:88]
    at = HEADER
    groups = []
    for _ in range(group_count):
        width, height, count = struct.unpack_from('<III', data, at); at += 12
        entries = []
        for _ in range(count):
            length = struct.unpack_from('<H', data, at)[0]
            name = data[at + 2:at + 2 + length].decode('ascii'); at += 2 + length
            entries.append((name, data[at:at + 32])); at += 32
        groups.append(((width, height), entries))
    blocks = []
    for _ in range(block_count):
        offset, stored, unpacked = struct.unpack_from('<III', data, at)
        blocks.append((offset, stored, unpacked, data[at + 12:at + 17])); at += 17
    objects = {}
    for _ in range(object_count):
        key = data[at:at + 32]
        objects[key] = struct.unpack_from('<IIIB', data, at + 32); at += 45
    if at != start:
        raise ValueError('the index does not end where the blocks start')
    return identity.hex(), groups, objects, blocks, table_key, data


