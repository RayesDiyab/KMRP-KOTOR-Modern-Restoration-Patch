#!/usr/bin/env python3
"""Find geometry KMRP introduced into a generated GUI that upstream did not have.

Written after the Character Scripts screen shipped blank. Every existing check
passed it: the file parsed, its controls sat inside the screen, and it matched the
play-tested 3440x1440 gold field for field. It was still broken, because gold had
never been play-tested on that screen and the fault was copied into it.

So this audit does not ask "is this file self-consistent". It asks **what did KMRP
change, and is the changed value less sane than what upstream shipped**. Upstream's
own defects are reported separately and never as ours: `scriptselect.gui` ships
both listbox scrollbars at the same x, which puts the left list's scrollbar outside
its own parent, and no KMRP pass created that.

The checks are deliberately about *relationships* rather than absolute numbers,
because absolute numbers are exactly what legitimately changes per resolution:

  scrollbar-in-content  a listbox scrollbar overlapping the list's content instead
                        of sitting against one edge. This is the shape of the
                        Character Scripts fault: the transfer moved `LST_AIState`'s
                        scrollbar from x=3064 to x=261, its parent's left edge.
  scrollbar-outside     a scrollbar with no overlap with its parent at all.
  offscreen             a control leaving the screen rectangle.
  degenerate            a width or height of zero or less.
  panel-origin          a root panel not at (0, 0); every working screen is.
  proto-wider           a row prototype wider than the listbox holding it.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

from pykotor.resource.formats.gff import read_gff

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "Included" / "kotor-high-resolution-menus-1.5"

LISTBOX = 11


def extent(struct):
    e = struct.get_struct("EXTENT") if struct is not None else None
    if e is None:
        return None
    return (e.get_int32("LEFT"), e.get_int32("TOP"),
            e.get_int32("WIDTH"), e.get_int32("HEIGHT"))


def findings(data: bytes, width: int, height: int) -> dict:
    """Every anomaly in one GUI, keyed so two files can be compared."""
    out = {}
    root = read_gff(data).root
    panel = extent(root)
    if panel and (panel[0], panel[1]) != (0, 0):
        out["panel-origin"] = panel

    for control in root.get_list("CONTROLS") or []:
        tag = control.get_string("TAG")
        rect = extent(control)
        if rect is None:
            continue
        left, top, wide, high = rect
        if wide <= 0 or high <= 0:
            out[f"degenerate:{tag}"] = rect
        if left < 0 or top < 0 or left + wide > width or top + high > height:
            out[f"offscreen:{tag}"] = rect

        scroll = extent(control.get_struct("SCROLLBAR"))
        if scroll is not None:
            sl, _, sw, _ = scroll
            sr, pr = sl + sw, left + wide
            if sr <= left or sl >= pr:
                out[f"scrollbar-outside:{tag}"] = scroll
            else:
                # Against an edge is correct; anywhere else covers the content.
                # A quarter of the parent's width is generous -- a real scrollbar
                # is a small fraction of it.
                margin = max(4, wide // 4)
                if sl > left + margin and sr < pr - margin:
                    out[f"scrollbar-in-content:{tag}"] = scroll

        proto = extent(control.get_struct("PROTOITEM"))
        if proto is not None and control.get_int32("CONTROLTYPE") == LISTBOX:
            if proto[2] > wide:
                out[f"proto-wider:{tag}"] = (proto, rect)
    return out


def upstream_for(resolution: str, name: str):
    matches = list(UPSTREAM.glob(f"*/gui.{resolution}/{name}"))
    return matches[0] if matches else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("resources", type=Path, nargs="?",
                        default=ROOT / "build" / "kmrp" / "resources")
    parser.add_argument("--all", action="store_true",
                        help="every resolution; default is a representative five")
    args = parser.parse_args()

    archives = sorted(args.resources.glob("gui-*.zip"))
    if not args.all:
        keep = {"gui-800x600.zip", "gui-1920x1080.zip", "gui-3440x1440.zip",
                "gui-3840x2160.zip", "gui-5120x1440.zip"}
        chosen = [a for a in archives if a.name in keep] or archives[:5]
        archives = chosen

    ours, theirs = 0, 0
    for archive_path in archives:
        resolution = re.sub(r"^gui-|\.zip$", "", archive_path.name)
        w, h = (int(v) for v in resolution.split("x"))
        with zipfile.ZipFile(archive_path) as archive:
            for name in sorted(archive.namelist()):
                if not name.lower().endswith(".gui"):
                    continue
                try:
                    mine = findings(archive.read(name), w, h)
                except Exception as error:
                    print(f"  {resolution:>10}  {name:<22} UNREADABLE: {error}")
                    continue
                if not mine:
                    continue
                source = upstream_for(resolution, name)
                base = {}
                if source is not None:
                    try:
                        base = findings(source.read_bytes(), w, h)
                    except Exception:
                        base = {}
                for key, value in sorted(mine.items()):
                    if key in base:
                        theirs += 1
                        continue
                    ours += 1
                    print(f"  {resolution:>10}  {name:<22} {key:<34} {value}")

    print()
    print(f"KMRP-introduced anomalies: {ours}")
    print(f"upstream anomalies carried through (not ours): {theirs}")
    return 1 if ours else 0


if __name__ == "__main__":
    raise SystemExit(main())
