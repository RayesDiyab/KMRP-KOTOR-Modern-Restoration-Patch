#!/usr/bin/env python3
"""How much of the controller UI actually carries a button badge, and is every
badge truthful?

"Expand the prompts to every screen" needs an answer to "which screens are there,
and which are missing" that is not a person's memory. This reads the controller
module's own tables and reports the gap.

The module holds two independent things:

  `GetK1SettingsStripExit`  every panel it can navigate, and that panel's bottom
                            strip -- the row of action buttons along the base of
                            the screen. This is the set of buttons a badge could
                            belong to.
  `GetK1ControllerPrompts`  every panel that currently assigns badge textures,
                            and which control offset gets which texture.

A screen in the first table and not the second is an uncovered screen. A badge in
the second whose offset is not in the first is worse: it is a badge on a control
the navigation does not treat as a strip button, which means nobody has checked
that the controller button it depicts really activates it.

Both tables are keyed by panel vtable, so the join is exact rather than by name.

The texture side is checked too: every referenced resref must be a real
PROMPT_TARGETS entry, because the badge is installed by replacing that control's
BORDER.FILL and a resref with no texture behind it renders as nothing at all --
silently, which is the failure mode this whole area keeps producing.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

MODULE = ROOT / "src" / "controller-native" / "vendor" / "K1XboxControls.cpp"

CONST = re.compile(
    r"constexpr\s+std::(?:uintptr_t|ptrdiff_t)\s+(\w+)\s*=\s*(-?0x[0-9A-Fa-f]+|-?\d+)\s*;")
BINDING_ARRAY = re.compile(
    r"constexpr\s+ControllerPromptBinding\s+(\w+)\[\]\s*=\s*\{(.*?)\};", re.S)
BINDING_ROW = re.compile(r"\{\s*(\w+)\s*,\s*\"([^\"]+)\"\s*\}")


def parse_constants(text: str) -> dict:
    return {name: int(value, 0) for name, value in CONST.findall(text)}


def parse_prompt_arrays(text: str) -> dict:
    """array name -> [(offset constant, resref)]"""
    out = {}
    for name, body in BINDING_ARRAY.findall(text):
        out[name] = BINDING_ROW.findall(body)
    return out


def parse_switch(text: str, function: str) -> dict:
    """panel vtable constant -> the raw text of its case body."""
    start = text.index(function)
    depth, index, begin = 0, text.index("{", start), None
    for index in range(text.index("{", start), len(text)):
        if text[index] == "{":
            depth += 1
            if begin is None:
                begin = index
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                break
    body = text[begin:index]
    cases = {}
    parts = re.split(r"case\s+(\w+)\s*:", body)
    for position in range(1, len(parts) - 1, 2):
        cases[parts[position]] = parts[position + 1]
    return cases


def strip_offsets(case_body: str, constants: dict):
    """The bottom strip of one panel: the SECOND braced group in its return.

    The struct is {tail...}, tailCount, {strip...}, stripCount, ... so the strip
    is the second group. Entries are constant names; -1 pads the fixed array.
    """
    groups = re.findall(r"\{([^{}]*)\}", case_body)
    if len(groups) < 2:
        return []
    names = [token.strip() for token in groups[1].split(",")]
    return [name for name in names
            if name and name != "-1" and name in constants]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--module", type=Path, default=MODULE)
    parser.add_argument("--strict", action="store_true",
                        help="fail when any strip button lacks a badge")
    args = parser.parse_args()

    text = args.module.read_text(encoding="utf-8")
    constants = parse_constants(text)
    arrays = parse_prompt_arrays(text)

    strips = parse_switch(text, "SettingsStripExit GetK1SettingsStripExit")
    prompts = parse_switch(text, "const ControllerPromptBinding* GetK1ControllerPrompts")

    # panel -> {offset value: resref}
    covered = {}
    for panel, body in prompts.items():
        match = re.search(r"return\s+(\w+);", body)
        if not match or match.group(1) not in arrays:
            continue
        covered[panel] = {constants[name]: resref
                          for name, resref in arrays[match.group(1)]
                          if name in constants}

    from build_controller_prompt_textures import PROMPT_TARGETS
    known_resrefs = {target.resref for target in PROMPT_TARGETS}

    total_strip = covered_strip = 0
    problems = []
    print(f"{'panel':<44}{'strip buttons':>14}{'with badge':>12}")
    for panel in sorted(set(strips) | set(covered)):
        names = strip_offsets(strips.get(panel, ""), constants)
        values = [constants[name] for name in names]
        badges = covered.get(panel, {})
        hit = sum(1 for value in values if value in badges)
        total_strip += len(values)
        covered_strip += hit
        flag = "" if (values and hit == len(values)) else "   <-- gap" if values else ""
        print(f"{panel:<44}{len(values):>14}{hit:>12}{flag}")

        for name, value in zip(names, values):
            if value not in badges:
                problems.append(("uncovered", panel, name, ""))
        for value, resref in badges.items():
            if values and value not in values:
                problems.append(("badge-not-in-strip", panel, hex(value), resref))
            if resref not in known_resrefs:
                problems.append(("no-such-texture", panel, hex(value), resref))

    print()
    print(f"strip buttons: {total_strip}, carrying a badge: {covered_strip} "
          f"({100.0 * covered_strip / total_strip:.0f}%)" if total_strip else "no strips found")

    uncovered = [row for row in problems if row[0] == "uncovered"]
    other = [row for row in problems if row[0] != "uncovered"]
    if uncovered:
        print(f"\nStrip buttons with no badge ({len(uncovered)}):")
        for _, panel, name, _ in uncovered:
            print(f"  {panel:<44}{name}")
    if other:
        print(f"\nProblems ({len(other)}):")
        for kind, panel, where, resref in other:
            print(f"  {kind:<20}{panel:<44}{where} {resref}")

    # Truthfulness, not just coverage.
    #
    # The native path changed what several buttons mean, and a badge depicting a
    # button whose meaning moved is worse than no badge at all. A, B and X are
    # unchanged -- confirm, cancel and the per-panel action -- so every badge
    # that depicts one of those is still accurate by construction. Anything else
    # needs a person to look at the screen and say what it should read.
    UNCHANGED_MEANING = {"a", "b", "x"}
    CURRENT_MAPPING = {
        "a": "confirm", "b": "cancel / back", "x": "per-panel",
        "y": "per-panel", "lb": "description scroll up", "rb": "description scroll down",
        "back": "Black", "lt": "previous screen", "rt": "next screen",
        "start": "open the in-game menu", "l3": "flourish weapons", "r3": "free look",
        "dpad": "focus navigation",
    }
    depicted = {}
    for target in PROMPT_TARGETS:
        button = target.resref.replace("kmrp", "", 1).split("_")[0]
        depicted[button] = depicted.get(button, 0) + 1
    stale = {b: n for b, n in depicted.items() if b not in UNCHANGED_MEANING}
    print()
    print("badges by depicted button: "
          + ", ".join(f"{b.upper()}={n}" for b, n in sorted(depicted.items())))
    if stale:
        print("Badges depicting a button whose meaning the native path changed:")
        for button, number in sorted(stale.items()):
            print(f"  {button.upper():<6}{number} badge(s) -- now {CURRENT_MAPPING.get(button, '?')}")
    else:
        print("No badge depicts a button whose meaning changed; every badge is "
              "still accurate.")
    print("Unbadged bindings, for reference: "
          + ", ".join(f"{b.upper()}={m}" for b, m in CURRENT_MAPPING.items()
                      if b not in depicted))

    if other or stale:
        return 1
    return 1 if (args.strict and uncovered) else 0


if __name__ == "__main__":
    raise SystemExit(main())
