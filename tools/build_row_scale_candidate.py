#!/usr/bin/env python3
"""Write a candidate copy of an installed exe with a different list-row scale.

The `.kfs` section holds a 32-bit float at file offset 0x003DD004 that the
row-init hook at `0x00417992` multiplies a list row's height by. The Universal
Patcher writes `max(1.0, height/720)` there -- 2.0 at 3440x1440 -- deliberately
tied to the font scale so rows grow exactly as much as the text in them.

This tool decouples it, to answer one question: **do inventory item rows and
their icons come from that hook at all?** The hook is documented (from Kotor
Patch Manager's research) as the generic composite row init used by the
save/load list, the journal quest list and the resolution popup; its comment
also names `CSWGuiInGameItemEntry`, which would be the inventory item row. That
has never been verified here.

Ruled out already: `PROTOITEM`'s own EXTENT in the GUI file. Upstream ships it
at a hardcoded 245x50 for every single resolution, and editing it to 245x100 at
3440x1440 changed nothing on screen -- 15 rows still fit an 868px list, where a
100px row would give 8.

Reads an installed, already-resolution-patched executable and writes a SEPARATE
candidate file. It never modifies its input.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


ROW_SCALE_OFFSET = 0x003DD004


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="an installed, patched swkotor.exe")
    parser.add_argument("output", type=Path, help="candidate to write (must not exist)")
    parser.add_argument("--scale", type=float, required=True)
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise SystemExit("Refusing to write over the source executable")
    if args.output.exists():
        raise SystemExit(f"{args.output} already exists")

    data = bytearray(args.source.read_bytes())
    current = struct.unpack_from("<f", data, ROW_SCALE_OFFSET)[0]
    if not 0.5 <= current <= 8.0:
        raise SystemExit(
            f"Found {current!r} at 0x{ROW_SCALE_OFFSET:08X}, which is not a plausible "
            f"row scale. This is not a patched executable of the expected build -- "
            f"nothing was written.")

    struct.pack_into("<f", data, ROW_SCALE_OFFSET, args.scale)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)

    print(f"source     {args.source}")
    print(f"row scale  {current:g} -> {args.scale:g}  (file 0x{ROW_SCALE_OFFSET:08X})")
    print(f"wrote      {args.output}")
    print(f"SHA-256    {hashlib.sha256(data).hexdigest().upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
