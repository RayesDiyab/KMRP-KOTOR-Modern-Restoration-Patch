#!/usr/bin/env python3
"""Check that `derive_resolution` reproduces layouts upstream made by hand.

KMRP derives GUI sets for resolutions KOTOR High Resolution Menus does not ship
(the Mac displays among them) as a blend of the upstream sets around them
(tools/derive_resolution_gui_set.py). This test hides one family at a time and
predicts each of its sets from the families on either side, at the same height,
then compares every EXTENT field with the real set:

  16:10 sets from 4:3 and 16:9     (every one with both neighbours in range)
  16:9 sets from 16:10 and 21:9

It passes when at least 99% of fields land within 1 px and none is further than
3 px off. Measured 2026-09-29: 100% within 1 px in both cases (102,036 and 46,380
fields).

It also checks that the general blend agrees within 1 px with 2880x1620, the one
set the build derived before, by the two-set interpolation.

    python testing/regression/Test-ResolutionDerivation.py [UPSTREAM_DIR]
"""
from __future__ import annotations

import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from derive_resolution_gui_set import (  # noqa: E402
    EXTENT_FIELDS,
    blend,
    derive_gui_set,
    derive_resolution,
    family_at_height,
    family_sets,
)
from pykotor.resource.formats.gff import GFFList, GFFStruct, read_gff  # noqa: E402

UPSTREAM = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    ROOT / "third_party" / "Included" / "kotor-high-resolution-menus-1.5")

# (hidden family, family below it, family above it)
CASES = [((16, 10), (4, 3), (16, 9)), ((16, 9), (16, 10), (21, 9))]


def extents(struct: GFFStruct, out: list[int]) -> list[int]:
    for label, _ftype, value in struct:
        if isinstance(value, GFFStruct):
            if label == "EXTENT":
                out.extend(value.get_int32(name) for name in EXTENT_FIELDS)
            else:
                extents(value, out)
        elif isinstance(value, GFFList):
            for item in value:
                extents(item, out)
    return out


def predict(width: int, height: int, lower, upper) -> dict[str, list[int]]:
    sets_a, width_a = family_at_height(UPSTREAM, lower, height)
    sets_b, width_b = family_at_height(UPSTREAM, upper, height)
    s = (width - width_a) / (width_b - width_a)
    anchors = [(p, w * (1 - s)) for p, w in sets_a] + [(p, w * s) for p, w in sets_b]
    anchors = [(p, w) for p, w in anchors if w > 1e-9]
    result = {}
    for gui in sorted(anchors[0][0].glob("*.gui")):
        roots = [(read_gff(p / gui.name).root, w) for p, w in anchors]
        result[gui.name] = extents(blend(roots, gui.name), [])
    return result


def main() -> int:
    failed = False
    for hidden, lower, upper in CASES:
        tally = Counter()
        for (width, height), folder in sorted(family_sets(UPSTREAM, hidden).items()):
            try:
                predicted = predict(width, height, lower, upper)
            except ValueError:
                continue  # a neighbour family has no sets around this height
            tally["sets"] += 1
            for gui in sorted(folder.glob("*.gui")):
                real = extents(read_gff(gui).root, [])
                for p, r in zip(predicted[gui.name], real):
                    d = abs(p - r)
                    tally["fields"] += 1
                    tally["within 1"] += d <= 1
                    tally["over 3"] += d > 3
        within = tally["within 1"] / tally["fields"]
        ok = within >= 0.99 and tally["over 3"] == 0
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} {hidden[0]}:{hidden[1]} from {lower[0]}:{lower[1]} and "
              f"{upper[0]}:{upper[1]}: {tally['sets']} sets, {tally['fields']} fields, "
              f"{100 * within:.1f}% within 1 px, {tally['over 3']} over 3 px")

    # The shipped 2880x1620 blends 1920x1080 and 3840x2160 at the midpoint; the general
    # blend uses the nearest heights, 2560x1440 and 3840x2160. Both interpolate the same
    # linear layouts, so they must agree within 1 px (measured 2026-09-29: 86.1% of the
    # 9,276 fields identical, the rest 1 px apart).
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nine = UPSTREAM / "16-by-9"
        derive_gui_set(nine / "gui.1920x1080", nine / "gui.3840x2160", tmp / "pair", 0.5)
        derive_resolution(UPSTREAM, 2880, 1620, tmp / "blend")
        worst = 0
        for f in sorted((tmp / "blend").glob("*.gui")):
            a = extents(read_gff(f).root, [])
            b = extents(read_gff(tmp / "pair" / f.name).root, [])
            worst = max([worst] + [abs(x - y) for x, y in zip(a, b)])
        ok = worst <= 1
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} 2880x1620: the blend agrees with the shipped two-set "
              f"derivation within {worst} px")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
