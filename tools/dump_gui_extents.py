#!/usr/bin/env python3
"""Print GUI control tags, types, parent IDs, and extents."""

from __future__ import annotations

import sys
from pathlib import Path

from pykotor.resource.formats.gff import read_gff


def extent(struct):
    value = struct.get_struct("EXTENT")
    if value is None:
        return None
    return tuple(value.get_int32(name) for name in ("LEFT", "TOP", "WIDTH", "HEIGHT"))


def walk(struct, depth=0):
    print(
        f"{'  ' * depth}{struct.get_string('TAG')!r} "
        f"type={struct.get_int32('CONTROLTYPE')} "
        f"parent={struct.get_int32('Obj_ParentID')} extent={extent(struct)}"
    )
    controls = struct.get_list("CONTROLS")
    if controls is not None:
        for child in controls:
            walk(child, depth + 1)


for arg in sys.argv[1:]:
    path = Path(arg)
    print(f"\n{path}")
    walk(read_gff(path).root)
