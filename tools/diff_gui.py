#!/usr/bin/env python3
"""Print field-level differences between two binary KOTOR GUI (GFF) files."""

from __future__ import annotations

import argparse
from pathlib import Path

from pykotor.resource.formats.gff import read_gff
from pykotor.resource.formats.gff.gff_data import GFFList, GFFStruct


def describe(value) -> str:
    if isinstance(value, bytes):
        return value.hex()
    return repr(value)


def item_name(value, index: int) -> str:
    if isinstance(value, GFFStruct):
        tag = value.get_string("TAG")
        if tag:
            return f"[{index}:{tag}]"
    return f"[{index}]"


def compare(left, right, path: str, output: list[str]) -> None:
    if isinstance(left, GFFStruct) and isinstance(right, GFFStruct):
        left_items = dict(left.items())
        right_items = dict(right.items())
        for key in sorted(set(left_items) | set(right_items)):
            child = f"{path}.{key}" if path else key
            if key not in left_items:
                output.append(f"+ {child} = {describe(right_items[key])}")
            elif key not in right_items:
                output.append(f"- {child} = {describe(left_items[key])}")
            else:
                compare(left_items[key], right_items[key], child, output)
        return
    if isinstance(left, GFFList) and isinstance(right, GFFList):
        if len(left) != len(right):
            output.append(f"~ {path}.length: {len(left)} -> {len(right)}")
        for index, (left_value, right_value) in enumerate(zip(left, right)):
            compare(left_value, right_value, path + item_name(right_value, index), output)
        return
    if type(left) is not type(right) or left != right:
        output.append(f"~ {path}: {describe(left)} -> {describe(right)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()

    output: list[str] = []
    compare(read_gff(args.before).root, read_gff(args.after).root, "", output)
    print("\n".join(output) if output else "No semantic field differences.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
