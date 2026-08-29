#!/usr/bin/env python3
"""Transfer the user's 3440x1440 GUI geometry corrections to another GUI.

The reference pair is the untouched 3440x1440 upstream layout and the final
play-tested 3440x1440 gold layout.  Only changed EXTENT integers are
transferred.  Texture references, strings, colors, IDs, and event wiring from
the target resolution remain intact.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from pykotor.resource.formats.gff import read_gff, write_gff
from pykotor.resource.formats.gff.gff_data import GFFList, GFFStruct
from pykotor.resource.type import ResourceType


EXTENT_FIELDS = ("LEFT", "TOP", "WIDTH", "HEIGHT")


def round_ratio(target: int, before: int, after: int) -> int:
    if before == 0:
        return after if target == 0 else target + after
    value = Decimal(target) * Decimal(after) / Decimal(before)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def keyed_items(values: GFFList) -> dict[str, GFFStruct] | None:
    result: dict[str, GFFStruct] = {}
    for value in values:
        if not isinstance(value, GFFStruct):
            return None
        tag = value.get_string("TAG")
        if not tag or tag in result:
            return None
        result[tag] = value
    return result


def transfer_struct(before: GFFStruct, after: GFFStruct, target: GFFStruct) -> int:
    changed = 0
    before_extent = before.get_struct("EXTENT")
    after_extent = after.get_struct("EXTENT")
    target_extent = target.get_struct("EXTENT")
    if before_extent is not None and after_extent is not None and target_extent is not None:
        for field in EXTENT_FIELDS:
            old = before_extent.get_int32(field)
            new = after_extent.get_int32(field)
            if old == new:
                continue
            current = target_extent.get_int32(field)
            target_extent.set_int32(field, round_ratio(current, old, new))
            changed += 1
        target.set_struct("EXTENT", target_extent)

    before_fields = dict(before.items())
    after_fields = dict(after.items())
    target_fields = dict(target.items())
    for field in sorted(set(before_fields) & set(after_fields) & set(target_fields)):
        if field == "EXTENT":
            continue
        left = before_fields[field]
        right = after_fields[field]
        destination = target_fields[field]
        if isinstance(left, GFFStruct) and isinstance(right, GFFStruct) and isinstance(destination, GFFStruct):
            changed += transfer_struct(left, right, destination)
        elif isinstance(left, GFFList) and isinstance(right, GFFList) and isinstance(destination, GFFList):
            left_by_tag = keyed_items(left)
            right_by_tag = keyed_items(right)
            target_by_tag = keyed_items(destination)
            if left_by_tag is not None and right_by_tag is not None and target_by_tag is not None:
                for tag in sorted(set(left_by_tag) & set(right_by_tag) & set(target_by_tag)):
                    changed += transfer_struct(left_by_tag[tag], right_by_tag[tag], target_by_tag[tag])
            else:
                for left_item, right_item, target_item in zip(left, right, destination):
                    if all(isinstance(item, GFFStruct) for item in (left_item, right_item, target_item)):
                        changed += transfer_struct(left_item, right_item, target_item)
    return changed


def transfer_geometry(before_path: Path, after_path: Path, target_path: Path, output_path: Path) -> int:
    before = read_gff(before_path)
    after = read_gff(after_path)
    target = read_gff(target_path)
    changed = transfer_struct(before.root, after.root, target.root)
    if changed == 0:
        raise ValueError(f"No changed extents found in reference pair for {before_path.name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_gff(target, output_path, ResourceType.GUI)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_before", type=Path)
    parser.add_argument("reference_after", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    count = transfer_geometry(
        args.reference_before, args.reference_after, args.target, args.output
    )
    print(f"Wrote {args.output}; transferred {count} changed EXTENT fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
