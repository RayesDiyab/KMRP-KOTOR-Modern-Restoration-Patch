#!/usr/bin/env python3
"""Pack the per-resolution GUI archives into one pool that stores each file once.

    python tools/pack_resolution_layouts.py <resource dir> <output zip>

The installer embedded all 49 `gui-<W>x<H>.zip` archives, 121.0 MB, and installs
one. Most of their files are the same bytes at several resolutions: a prompt badge
is drawn for its button's size, and many buttons are the same size at many
resolutions. On 2026-09-25 the archives held 20,580 prompt textures, of which
6,852 differed.

The pool is one zip:

    index/<W>x<H>.txt   that resolution's files, in its archive's own order, one
                        line each: "<Override name><TAB><object>"
    objects/<object>    each distinct file once, named by the first 16 hex digits
                        of its SHA-256, upper case

The installer (`GuiPool` in src/patcher/KmrpPatcher.cs) reads one index and
installs the objects it names under their Override names. It checks every file it
writes against its object name.

The per-resolution archives stay in the build: the regression checks read them.
So this verifies the pool before it returns. Every resolution rebuilt from the
pool must have its archive's names, in its archive's order, with its archive's
SHA-256 for each, or the build stops.

Standard library only. Deterministic: the same archives give the same bytes.
"""
import hashlib
import sys
import zipfile
from pathlib import Path

OBJECT_DIGITS = 16
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
TAB = chr(9)
NEWLINE = chr(10)


def entry(name):
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def archive_files(path):
    """(name, SHA-256, bytes) for every file in one resolution archive, in order."""
    files = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = info.filename
            if name.endswith("/") or TAB in name or NEWLINE in name or chr(13) in name:
                raise ValueError(f"{path.name}: cannot index the entry {name!r}")
            data = archive.read(info)
            files.append((name, hashlib.sha256(data).hexdigest().upper(), data))
    return files


def pack(archives, output):
    objects = {}        # object name -> full SHA-256
    expected = {}       # resolution -> [(name, full SHA-256)]
    total_files = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9,
                         allowZip64=True) as pool:
        for number, path in enumerate(archives, 1):
            resolution = path.stem[len("gui-"):]
            lines = []
            listed = []
            for name, digest, data in archive_files(path):
                key = digest[:OBJECT_DIGITS]
                known = objects.get(key)
                if known is None:
                    objects[key] = digest
                    pool.writestr(entry("objects/" + key), data, compresslevel=9)
                elif known != digest:
                    raise ValueError(f"two files share the object name {key}; "
                                     f"raise OBJECT_DIGITS")
                lines.append(name + TAB + key)
                listed.append((name, digest))
            expected[resolution] = listed
            total_files += len(listed)
            pool.writestr(entry(f"index/{resolution}.txt"),
                          (NEWLINE.join(lines) + NEWLINE).encode("utf-8"), compresslevel=9)
            print(f"[{number}/{len(archives)}] {resolution}", flush=True)
    return objects, expected, total_files


def verify(output, objects, expected):
    """Rebuild every resolution from the pool and compare it with its archive."""
    with zipfile.ZipFile(output) as pool:
        names = [info.filename for info in pool.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("the pool holds a name twice")
        stored = {}
        for name in names:
            if not name.startswith("objects/"):
                continue
            key = name[len("objects/"):]
            digest = hashlib.sha256(pool.read(name)).hexdigest().upper()
            if not digest.startswith(key) or objects.get(key) != digest:
                raise ValueError(f"object {key} does not hold the file it names")
            stored[key] = digest
        if set(stored) != set(objects):
            raise ValueError("the pool's objects are not the objects packed")
        indexes = sorted(name for name in names if name.startswith("index/"))
        if len(indexes) != len(expected):
            raise ValueError(f"{len(indexes)} indexes for {len(expected)} archives")
        for resolution, listed in expected.items():
            text = pool.read(f"index/{resolution}.txt").decode("utf-8")
            rebuilt = []
            for line in text.split(NEWLINE)[:-1]:
                name, key = line.split(TAB)
                rebuilt.append((name, stored[key]))
            if rebuilt != listed:
                raise ValueError(f"{resolution} rebuilt from the pool differs from "
                                 f"gui-{resolution}.zip")


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    resources = Path(sys.argv[1])
    output = Path(sys.argv[2])
    archives = sorted(resources.glob("gui-*.zip"))
    if not archives:
        print(f"no gui-*.zip in {resources}")
        return 1
    temporary = output.with_name(output.name + ".tmp")
    objects, expected, total_files = pack(archives, temporary)
    verify(temporary, objects, expected)
    temporary.replace(output)
    before = sum(path.stat().st_size for path in archives)
    after = output.stat().st_size
    # Two short lines: the build prints each as one detail line, cut to its width.
    print(f"{len(archives)} archives, {total_files:,} files, {len(objects):,} distinct: "
          f"{before / 1048576:.1f} MB -> {after / 1048576:.1f} MB")
    print(f"all {len(expected)} rebuilt from the pool match their archives")
    return 0


if __name__ == "__main__":
    sys.exit(main())
