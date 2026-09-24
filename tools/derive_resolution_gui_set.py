#!/usr/bin/env python3
"""Derive a KOTOR High Resolution Menus GUI set that upstream does not ship.

High Resolution Menus lays out each resolution by hand, and it has no set for
2880x1620 (issue #16). That preset is exactly halfway between two sets it does
ship, 1920x1080 and 3840x2160, in width and in height, so every field of the
derived set is interpolated halfway between the two.

Interpolation rather than scaling one set, because upstream does not scale
everything. Measured 2026-09-25 by deriving its 3840x2160 set from 1920x1080 at
2x: every non-EXTENT field matched, but 3,524 EXTENT fields did not -- list
prototypes, for one, stay at vanilla values at every resolution, and a
prototype rewrite once broke Character Scripts. Interpolating between two real
sets keeps each of upstream's choices: a field it doubles comes out 1.5x, a field
it holds fixed stays fixed, and a hand adjustment lands between its two values.

The method was checked against a set upstream does ship: 2560x1440 is a third of
the way from 1920x1080 to 3840x2160, and interpolating at 1/3 reproduces it (the
figures are in docs/universal-resolution-math.md, *Adding another resolution*).

Only numeric fields that differ between the two sets are interpolated; every
other field is copied from the lower set. The two sets must have the same
structure, file by file, or the derivation stops.

    python tools/derive_resolution_gui_set.py LOW_DIR HIGH_DIR DEST_DIR T
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from pykotor.resource.formats.gff import GFFList, GFFStruct, read_gff, write_gff

EXTENT_FIELDS = ("LEFT", "TOP", "WIDTH", "HEIGHT")

# resolution: (lower upstream set, upper upstream set, position between them)
DERIVED_GUI_SETS = {
    "2880x1620": ("1920x1080", "3840x2160", 0.5),
}


def between(low: int, high: int, t: float) -> int:
    """Interpolate, rounding half away from zero."""
    value = low + (high - low) * t
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


def interpolate(low: GFFStruct, high: GFFStruct, t: float, where: str) -> GFFStruct:
    """`low`, with every integer field that differs from `high` interpolated."""
    for label, _ftype, value in list(low):
        path = f"{where}.{label}"
        if not high.exists(label):
            raise ValueError(f"{path} is missing from the upper set")
        other = high.get_struct(label) if isinstance(value, GFFStruct) else None
        if isinstance(value, GFFStruct):
            low.set_struct(label, interpolate(value, other, t, path))
        elif isinstance(value, GFFList):
            upper = high.get_list(label)
            if len(upper) != len(value):
                raise ValueError(f"{path} has {len(value)} entries below, {len(upper)} above")
            items = GFFList()
            for i, (a, b) in enumerate(zip(value, upper)):
                items._structs.append(interpolate(a, b, t, f"{path}[{i}]"))
            low.set_list(label, items)
        elif where.endswith(".EXTENT") and label in EXTENT_FIELDS:
            upper = high.get_int32(label)
            if upper != value:
                low.set_int32(label, between(value, upper, t))
        elif value != _field(high, label):
            # Upstream changes nothing but extents between resolutions; anything
            # else differing means the two sets are not what this assumes.
            raise ValueError(f"{path} differs between the sets and is not an extent")
    return low


def _field(struct: GFFStruct, label: str):
    for name, _ftype, value in struct:
        if name == label:
            return value
    return None


def derive_gui_set(low_dir: Path, high_dir: Path, destination: Path, t: float) -> list[Path]:
    """Write every .gui of `low_dir` to `destination`, interpolated toward `high_dir`."""
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for low in sorted(low_dir.glob("*.gui")):
        high = high_dir / low.name
        if not high.is_file():
            raise ValueError(f"{low.name} has no counterpart in {high_dir}")
        gff = read_gff(low)
        gff.root = interpolate(gff.root, read_gff(high).root, t, low.name)
        out = destination / low.name
        write_gff(gff, out)
        written.append(out)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("low", type=Path)
    parser.add_argument("high", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("t", type=float)
    args = parser.parse_args()
    files = derive_gui_set(args.low, args.high, args.destination, args.t)
    print(f"derived {len(files)} GUI files at t={args.t} into {args.destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
