#!/usr/bin/env python3
"""An engine address named by more than one file is named once (audit S-8).

K1EngineAddresses.h holds them. This fails on a number of its written anywhere else, and on any
other address in the code of two files, which belongs there too. Comments do not count: they
cite addresses for the reader. No game runs.
Run: python testing/regression/Test-EngineAddresses.py
"""
from collections import defaultdict
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"
HOME = "K1EngineAddresses.h"
# Inside the game's image: .text from 0x00401000 to the data's end, written with leading zeros.
ADDRESS = re.compile(r"\b0x0{1,2}([4-7][0-9A-Fa-f]{5})\b")


def addresses_in(path):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for match in ADDRESS.finditer(line.split("//")[0]):
            yield int(match.group(1), 16), number


def main():
    home = {value for value, _ in addresses_in(SRC / HOME)}
    if len(home) < 60:
        print(f"FAIL only {len(home)} addresses read from {HOME}: the pattern has stopped matching")
        return 1
    used = defaultdict(set)
    failed = False
    for path in sorted(SRC.glob("*.cpp")) + sorted(SRC.glob("*.h")):
        if path.name == HOME:
            continue
        for value, number in addresses_in(path):
            used[value].add(path.name)
            if value in home:
                print(f"FAIL {path.name}:{number} writes 0x{value:08X}, which {HOME} names")
                failed = True
    for value, files in sorted(used.items()):
        if len(files) > 1:
            print(f"FAIL 0x{value:08X} is written in {', '.join(sorted(files))}: it belongs in {HOME}")
            failed = True
    if failed:
        return 1
    print(f"PASS {len(home)} addresses named once; {len(used)} others each in one file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
