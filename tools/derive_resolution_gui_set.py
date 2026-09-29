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

Any resolution, across aspect ratios (2026-09-29, for the Mac displays)
-----------------------------------------------------------------------
Every upstream family (4:3, 16:10, 16:9, 21:9, 32:9) has the same 81 files with
the same structure, and the sets turn out to be linear in width as well as in
height. Measured by predicting sets upstream does ship from the families on
either side of their aspect ratio, at the same height, and comparing every
EXTENT field:

  16:10 from 4:3 and 16:9    102,036 fields   91.8% exact, 100% within 1 px
  16:9 from 16:10 and 21:9    46,380 fields   100% within 1 px

(The 21-by-9 folder's 1280x1080 set, 1.19:1, is left out of its family; with it,
the second line was 99.1% within 1 px and 3 px at worst.)

Scaling the nearest family to the new width instead reproduced 70.2% exactly
and missed 5.9% of fields by more than 10 px, so it is not used.

`derive_resolution` therefore computes a set for any WIDTHxHEIGHT between the
4:3 and 32:9 families as one weighted blend of up to four upstream sets (the two
families on either side of its aspect ratio, each at the two heights around its
height), rounded once. `testing/regression/Test-ResolutionDerivation.py`
re-runs the measurement above.

    python tools/derive_resolution_gui_set.py --resolution 3024x1964 UPSTREAM_DIR DEST_DIR
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


#  Any resolution: a weighted blend of up to four upstream sets
# ---------------------------------------------------------------------------------------

# Upstream's folders, in order of aspect ratio.
FAMILY_FOLDERS = {
    (4, 3): "4-by-3",
    (16, 10): "16-by-10",
    (16, 9): "16-by-9",
    (21, 9): "21-by-9",
    (32, 9): "32-by-9",
}


def family_sets(upstream: Path, family: tuple[int, int]) -> dict[tuple[int, int], Path]:
    """Upstream's sets of one family, keyed by (width, height)."""
    sets = {}
    for folder in (upstream / FAMILY_FOLDERS[family]).glob("gui.*x*"):
        width, height = folder.name[len("gui."):].split("x")
        sets[(int(width), int(height))] = folder
    return sets


def family_aspect(upstream: Path, family: tuple[int, int]) -> float:
    """The family's aspect ratio as its sets have it (21:9 is 2560x1080, 3440x1440...)."""
    ratios = sorted(w / h for w, h in family_sets(upstream, family))
    return ratios[len(ratios) // 2]


def family_at_height(upstream: Path, family: tuple[int, int], height: int
                     ) -> tuple[list[tuple[Path, float]], float]:
    """(sets and weights) giving the family at `height`, and the family's width there.

    Only sets within 2% of the family's aspect ratio count: the 21-by-9 folder also
    holds 1280x1080 (1.19:1), and where two sets share a height (1360x768 and
    1366x768) the one nearer the family's ratio is used.
    """
    aspect = family_aspect(upstream, family)
    by_height: dict[int, tuple[tuple[int, int], Path]] = {}
    for (w, h), folder in family_sets(upstream, family).items():
        if abs(w / h / aspect - 1) > 0.02:
            continue
        if h not in by_height or abs(w / h - aspect) < abs(by_height[h][0][0] / h - aspect):
            by_height[h] = ((w, h), folder)
    sets = sorted(by_height.values(), key=lambda item: item[0][1])
    for (width, h), folder in sets:
        if h == height:
            return [(folder, 1.0)], float(width)
    below = [item for item in sets if item[0][1] < height]
    above = [item for item in sets if item[0][1] > height]
    if not below or not above:
        raise ValueError(f"{FAMILY_FOLDERS[family]} has no sets on both sides of height {height}")
    (w1, h1), low = below[-1]
    (w2, h2), high = above[0]
    t = (height - h1) / (h2 - h1)
    return [(low, 1.0 - t), (high, t)], w1 + (w2 - w1) * t


def anchors_for(upstream: Path, width: int, height: int) -> list[tuple[Path, float]]:
    """The upstream sets, with weights, whose blend is the layout for width x height."""
    aspect = width / height
    families = sorted(FAMILY_FOLDERS, key=lambda f: family_aspect(upstream, f))
    for family in families:
        if abs(family_aspect(upstream, family) - aspect) < 0.005:
            return family_at_height(upstream, family, height)[0]
    lower = [f for f in families if family_aspect(upstream, f) < aspect]
    upper = [f for f in families if family_aspect(upstream, f) > aspect]
    if not lower or not upper:
        raise ValueError(f"{width}x{height} lies outside upstream's aspect ratios")
    sets_a, width_a = family_at_height(upstream, lower[-1], height)
    sets_b, width_b = family_at_height(upstream, upper[0], height)
    s = (width - width_a) / (width_b - width_a)
    return [(p, w * (1.0 - s)) for p, w in sets_a] + [(p, w * s) for p, w in sets_b]


def _round(value: float) -> int:
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


def blend(structs: list[tuple[GFFStruct, float]], where: str) -> GFFStruct:
    """The first struct, with every EXTENT field the weighted sum of all of them."""
    base = structs[0][0]
    for label, _ftype, value in list(base):
        path = f"{where}.{label}"
        others = [(s.get_struct(label) if isinstance(value, GFFStruct) else
                   s.get_list(label) if isinstance(value, GFFList) else _field(s, label), w)
                  for s, w in structs]
        if isinstance(value, GFFStruct):
            base.set_struct(label, blend(others, path))
        elif isinstance(value, GFFList):
            if any(o is None or len(o) != len(value) for o, _ in others):
                raise ValueError(f"{path} differs in length between the sets")
            items = GFFList()
            for i in range(len(value)):
                items._structs.append(blend([(o[i], w) for o, w in others], f"{path}[{i}]"))
            base.set_list(label, items)
        elif where.endswith(".EXTENT") and label in EXTENT_FIELDS:
            base.set_int32(label, _round(sum(o * w for o, w in others)))
        elif any(o != value for o, _ in others):
            raise ValueError(f"{path} differs between the sets and is not an extent")
    return base


def derive_resolution(upstream: Path, width: int, height: int, destination: Path) -> list[Path]:
    """Write the layout for width x height, blended from upstream's sets, to `destination`."""
    anchors = [(p, w) for p, w in anchors_for(upstream, width, height) if w > 1e-9]
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for first in sorted(anchors[0][0].glob("*.gui")):
        gffs = [(read_gff(p / first.name), w) for p, w in anchors]
        gff = gffs[0][0]
        gff.root = blend([(g.root, w) for g, w in gffs], first.name)
        out = destination / first.name
        write_gff(gff, out)
        written.append(out)
    return written


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--resolution":
        parser = argparse.ArgumentParser(description="Derive a set for any resolution.")
        parser.add_argument("--resolution", required=True)
        parser.add_argument("upstream", type=Path)
        parser.add_argument("destination", type=Path)
        args = parser.parse_args()
        width, height = (int(v) for v in args.resolution.lower().split("x"))
        files = derive_resolution(args.upstream, width, height, args.destination)
        print(f"derived {len(files)} GUI files for {width}x{height} into {args.destination}")
        return 0
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
