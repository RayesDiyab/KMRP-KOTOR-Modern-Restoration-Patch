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

**Gold is not what ships.** With `--installed` and the installer's own outputs
(`--apply` at every resolution), it also inventories the bytes they change that
gold leaves as clean -- the sites the patcher fills in per resolution over a
vanilla value -- and requires a document for those runs too.

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
import re
import subprocess
from pathlib import Path

MERGE_GAP = 8          # identical bytes tolerated inside one run
LOOKBACK = 16          # bytes before a run whose address still counts as a mention

DOC_GLOBS = ("docs/**/*.md", "reverse-engineering/**/*.md", "*.md")
TOOL_GLOBS = ("tools/*.py", "src/patcher/*.cs")

# Below this file offset is the PE header, whose changes are consequences of
# section injection rather than patch sites. Reported separately.
HEADER_END = 0x1000

# This tool's own output document, and the section of it holding the generated run
# table (from its "## 4." heading up to "## 5.").
SELF = "reverse-engineering/binary-inventory.md"
GENERATED_SECTION = re.compile(r"^## 4\..*?(?=^## 5\.)", re.S | re.M)


def tracked(root: Path):
    """The repository's tracked files, or None when git cannot say.

    Only these count as documentation. The globs also match git-ignored local
    notes -- docs/agent-memory/HANDOFF.md and LOCAL.md -- which nobody else can
    read, so a run named only there would pass while no committed document named
    it. Found on 2026-09-24, when HANDOFF.md turned up in the "documented in"
    column.
    """
    try:
        listing = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                                 capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {name for name in listing.decode("utf-8", "replace").split("\0") if name}


def load(root: Path, globs) -> dict:
    out = {}
    only = tracked(root)
    for pattern in globs:
        for path in root.glob(pattern):
            name = path.relative_to(root).as_posix()
            if name.startswith("build/"):
                continue
            if only is not None and name not in only:
                continue
            try:
                body = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if name == SELF:
                # The run table this tool generates names every address in it, so
                # left in, it documents every run the moment it is pasted and the
                # check can never fail again. Only the prose around it counts.
                body = GENERATED_SECTION.sub("", body)
            out[name] = body.lower()
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
    parser.add_argument("--installed", type=Path, nargs="*", default=[],
                        help="executables the installer produced (e.g. `--apply` at "
                             "every resolution); bytes they change that gold leaves "
                             "as clean are inventoried too")
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
    differing = sum(clean[index] != gold[index] for index in range(min(len(clean), len(gold))))
    covered = sum(stop - start for start, stop in found)
    print(f"differing byte positions inside the original image: {differing}")
    print(f"bytes covered by merged presentation runs: {covered}")
    print()

    print("| VA | FILE | len | clean | gold | documented in |")
    print("| --- | --- | --- | --- | --- | --- |")
    for start, stop in body:
        doc = mentions(docs, start, stop)
        where = ", ".join("`%s`" % d for d in doc) if doc else "**nothing**"
        print(f"| `0x{start + 0x400000:08X}` | `0x{start:06X}` | {stop - start} "
              f"| `{clean[start:stop].hex()}` | `{gold[start:stop].hex()}` | {where} |")

    # Gold is not what ships: the installer rewrites some sites per resolution, and
    # a few of them -- the list-row sizes gold leaves at vanilla -- are bytes gold
    # never changes at all. Measured 2026-09-24: 21 such positions across the 48
    # resolutions, 18 of them outside every run above.
    install_only = []
    if args.installed:
        n = min(len(clean), len(gold))
        outputs = [path.read_bytes() for path in args.installed]
        extra = sorted({index for data in outputs for index in range(HEADER_END, n)
                        if data[index] != clean[index] and gold[index] == clean[index]})
        for index in extra:
            if install_only and index - install_only[-1][1] < MERGE_GAP:
                install_only[-1] = (install_only[-1][0], index + 1)
            else:
                install_only.append((index, index + 1))
        print()
        print(f"installed outputs: {len(outputs)}; positions they write that gold leaves "
              f"as clean: {len(extra)}, in {len(install_only)} runs")
        print()
        print("| VA | FILE | len | clean | distinct installed values | documented in |")
        print("| --- | --- | --- | --- | --- | --- |")
        for start, stop in install_only:
            doc = mentions(docs, start, stop)
            where = ", ".join("`%s`" % d for d in doc) if doc else "**nothing**"
            values = {data[start:stop] for data in outputs}
            print(f"| `0x{start + 0x400000:08X}` | `0x{start:06X}` | {stop - start} "
                  f"| `{clean[start:stop].hex()}` | {len(values)} | {where} |")

    print()
    undocumented = [r for r in body + install_only if not mentions(docs, *r)]
    unowned = [r for r in undocumented if not mentions(tools, *r)]
    print(f"code/data runs with no document: {len(undocumented)}")
    print(f"code/data runs with no document and no build script: {len(unowned)}")
    for start, stop in undocumented:
        print(f"  UNDOCUMENTED 0x{start + 0x400000:08X} FILE 0x{start:06X} len {stop - start}")
    return 1 if undocumented else 0


if __name__ == "__main__":
    raise SystemExit(main())
