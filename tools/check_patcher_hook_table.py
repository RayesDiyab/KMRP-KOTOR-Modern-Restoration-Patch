#!/usr/bin/env python3
"""Assert the patcher's hardcoded hook table matches `kotor1.hooks.toml`.

The shipped patcher writes `patch_config.toml` from a table written out by hand
in `KmrpPatcher.cs`, because it is a single-file C# build with no TOML reader.
That hand-copying is exactly where a wrong address, a wrong stolen byte or a
wrong consumed-exit address gets in, and every one of those is a jump into the
wrong place at run time rather than a build error.

This existed because one did: the consumed exit for
`NativeJoystickSkipNormalizeK1` was transcribed as 0x00679BB6 where the tracked
table says 0x00679B76.

Usage:
    python tools/check_patcher_hook_table.py

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import kmrp_controller                                  # noqa: E402

PATCHER = ROOT / "src" / "patcher" / "KmrpPatcher.cs"

CALL = re.compile(
    r'AppendHook\(text,\s*"(0x[0-9A-Fa-f]+)",\s*"([^"]*)",\s*'
    r'\n?\s*"(\w+)"(.*?)\);',
    re.DOTALL,
)


def parse_patcher():
    text = PATCHER.read_text(encoding="utf-8")
    found = {}
    for match in CALL.finditer(text):
        address = int(match.group(1), 16)
        stolen = [int(b, 16) for b in match.group(2).split(", ")]
        function = match.group(3)
        tail = match.group(4)
        exit_match = re.search(r'"(0x[0-9A-Fa-f]{6,8})"', tail)
        found[function] = {
            "address": address,
            "original_bytes": stolen,
            "consumed": int(exit_match.group(1), 16) if exit_match else None,
            "skip": tail.rstrip().endswith("true"),
        }
    return found


def main() -> int:
    patcher = parse_patcher()
    tracked = {h["function"]: h for h in kmrp_controller.native_hooks()}

    problems = []
    missing = sorted(set(tracked) - set(patcher))
    if missing:
        problems.append(f"the patcher does not emit: {', '.join(missing)}")
    extra = sorted(set(patcher) - set(tracked))
    if extra:
        problems.append(f"the patcher emits hooks not in the tracked table: "
                        f"{', '.join(extra)}")

    for name in sorted(set(patcher) & set(tracked)):
        got, want = patcher[name], tracked[name]
        if got["address"] != want["address"]:
            problems.append(f"{name}: address {got['address']:#010x} != "
                            f"{want['address']:#010x}")
        if got["original_bytes"] != list(want["original_bytes"]):
            problems.append(f"{name}: stolen bytes differ")
        if bool(got["skip"]) != bool(want.get("skip_original_bytes")):
            problems.append(f"{name}: skip_original_bytes "
                            f"{got['skip']} != {want.get('skip_original_bytes')}")
        wanted_exit = want.get("consumed_exit_address")
        if got["consumed"] != wanted_exit:
            shown = f"{got['consumed']:#010x}" if got["consumed"] else "none"
            expect = f"{wanted_exit:#010x}" if wanted_exit else "none"
            problems.append(f"{name}: consumed exit {shown} != {expect}")

    if problems:
        print("Patcher hook table does NOT match kotor1.hooks.toml:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print(f"Patcher hook table matches the tracked table "
          f"({len(tracked)} native hooks, addresses, stolen bytes, skip flags "
          f"and consumed exits all agree).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
