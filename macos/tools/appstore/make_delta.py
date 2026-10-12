#!/usr/bin/env python3
"""What turns one file into another of the same length, as a list of the stretches that differ.

    make_delta.py <base> <new> <out.delta>

KMRP's module for the Mac App Store's game is the module for Steam's compiled with other
addresses: the same length, the menu sets inside it the same 100 MB, and a few thousand bytes
of code and signature that differ. The package carries those instead of a second copy, and the
installer makes the App Store's module from Steam's (kmrp-mac.sh, apply_delta).

The file, all text but the bytes:

    KMRP-DELTA 1
    base <sha256 of the base>
    new <sha256 of the result>
    size <length of both>
    runs <count>
    <offset> <length>      one line per run, decimal, in order
    data
    <the runs' bytes, one after another>

Stretches less than 16 bytes apart are one run. Exit code 3, and no file, when the lengths
differ: the caller then packages the whole file.
"""
import hashlib
import sys
from pathlib import Path

GAP = 16


def main() -> int:
    base, new, out = (Path(a) for a in sys.argv[1:4])
    a, b = base.read_bytes(), new.read_bytes()
    if len(a) != len(b):
        print(f"{new.name}: {len(b)} bytes, the base {len(a)}: no delta")
        return 3
    runs = []
    step = 1 << 16
    for start in range(0, len(a), step):
        if a[start:start + step] == b[start:start + step]:
            continue
        for i in range(start, min(start + step, len(a))):
            if a[i] != b[i]:
                if runs and i - (runs[-1][0] + runs[-1][1]) < GAP:
                    runs[-1][1] = i + 1 - runs[-1][0]
                else:
                    runs.append([i, 1])
    head = ["KMRP-DELTA 1", f"base {hashlib.sha256(a).hexdigest()}", f"new {hashlib.sha256(b).hexdigest()}",
            f"size {len(a)}", f"runs {len(runs)}", *(f"{offset} {length}" for offset, length in runs), "data", ""]
    out.write_bytes("\n".join(head).encode() + b"".join(b[offset:offset + length] for offset, length in runs))
    print(f"{out.name}: {len(runs)} runs, {sum(length for _, length in runs)} bytes of {len(a)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
