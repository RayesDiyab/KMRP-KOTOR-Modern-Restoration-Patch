#!/usr/bin/env python3
"""Enumerate every byte that differs between the clean executable and gold, and
prove each difference is documented somewhere in this repository.

**Why this exists.** KMRP's fixes are documented one subject at a time -- fonts
here, the area map there -- which answers "how does fix X work?" but never
"is there anything in this executable nobody wrote down?". Those are different
questions, and only the second one catches a stray byte. This walks the diff in
the other direction: start from the bytes, and require a document for each.

**What it produces.** A run-level table of every difference, and a coverage
report saying, for each run, whether an address inside it (or within 16 bytes
before it, to catch a document that names an instruction's start while the diff
begins mid-instruction) appears in a Markdown document, in a build script, or
in neither. The output is pasted into
`reverse-engineering/binary-inventory.md`; regenerate it after any change to
gold and the coverage line must still read zero.

**How runs are formed.** Differing bytes separated by fewer than 8 identical
bytes are merged into one run, so a patch site reads as one row rather than as
its individual changed bytes. The threshold is a presentation choice and nothing
depends on it.

**On the "documented in" column.** It records that a document *mentions this
address*, not that the document is correct or that it is the right document.
That is a real limit: it catches an undocumented byte, and it does not catch a
byte documented wrongly. Both address forms are searched -- `VA` and
`FILE = VA - 0x400000` -- because the reverse-engineering documents address
sites by VA while `docs/universal-resolution-math.md` and `KmrpPatcher.cs` use
file offsets.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

MERGE_GAP = 8          # identical bytes tolerated inside one run
LOOKBACK = 16          # bytes before a run whose address still counts as a mention

DOC_GLOBS = ("docs/**/*.md", "reverse-engineering/**/*.md", "*.md")
TOOL_GLOBS = ("tools/*.py", "src/patcher/*.cs")

# Below this file offset is the PE header, whose changes are consequences of
# section injection rather than patch sites. Reported separately.
HEADER_END = 0x1000


def load(root: Path, globs) -> dict:
    out = {}
    for pattern in globs:
        for path in root.glob(pattern):
            name = path.relative_to(root).as_posix()
            if name.startswith("build/"):
                continue
            try:
                out[name] = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                pass
    return out


def runs_of(clean: bytes, gold: bytes) -> list:
    n = min(len(clean), len(gold))
    found, i = [], 0
    while i < n:
        if clean[i] == gold[i]:
            i += 1
            continue
        j = i
        while j < n and clean[j] != gold[j]:
            j += 1
        if found and i - found[-1][1] < MERGE_GAP:
            found[-1] = (found[-1][0], j)
        else:
            found.append((i, j))
        i = j
    return found


def mentions(corpus: dict, start: int, stop: int) -> list:
    """Files naming any address in [start - LOOKBACK, stop), as VA or file offset."""
    hits = set()
    for offset in range(-LOOKBACK, stop - start):
        for base in (0x400000, 0):
            value = start + offset + base
            for width in (8, 6, 5, 4):
                text = format(value, "0%dx" % width)
                for name, body in corpus.items():
                    if text in body:
                        hits.add(name)
    return sorted(hits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("clean", type=Path)
    parser.add_argument("gold", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    clean = args.clean.read_bytes()
    gold = args.gold.read_bytes()
    docs = load(args.root, DOC_GLOBS)
    tools = load(args.root, TOOL_GLOBS)

    print(f"clean {args.clean.name}  {len(clean)} bytes  "
          f"sha256 {hashlib.sha256(clean).hexdigest()}")
    print(f"gold  {args.gold.name}  {len(gold)} bytes  "
          f"sha256 {hashlib.sha256(gold).hexdigest()}")
    print(f"appended beyond the clean image: {len(gold) - min(len(clean), len(gold))} bytes")

    found = runs_of(clean, gold)
    body = [r for r in found if r[0] >= HEADER_END]
    header = [r for r in found if r[0] < HEADER_END]
    print(f"runs: {len(found)}  ({len(header)} PE header, {len(body)} code/data)")
    print(f"bytes changed inside the original image: {sum(b - a for a, b in found)}")
    print()

    print("| VA | FILE | len | clean | gold | documented in |")
    print("| --- | --- | --- | --- | --- | --- |")
    for start, stop in body:
        doc = mentions(docs, start, stop)
        where = ", ".join("`%s`" % d for d in doc) if doc else "**nothing**"
        print(f"| `0x{start + 0x400000:08X}` | `0x{start:06X}` | {stop - start} "
              f"| `{clean[start:stop].hex()}` | `{gold[start:stop].hex()}` | {where} |")

    print()
    undocumented = [r for r in body if not mentions(docs, *r)]
    unowned = [r for r in undocumented if not mentions(tools, *r)]
    print(f"code/data runs with no document: {len(undocumented)}")
    print(f"code/data runs with no document and no build script: {len(unowned)}")
    for start, stop in undocumented:
        print(f"  UNDOCUMENTED 0x{start + 0x400000:08X} FILE 0x{start:06X} len {stop - start}")
    return 1 if undocumented else 0


if __name__ == "__main__":
    raise SystemExit(main())
