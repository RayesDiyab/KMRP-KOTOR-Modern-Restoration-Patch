#!/usr/bin/env python3
"""Compare read-only Mac runtime navigation probes with the GUI's parsed MOVETO IDs.

Usage: python Test-MacNavigationTrace.py before.log after.log
Probe format and capture procedure: reverse-engineering/macos-keyboard-navigation.md.
This checks actual loader/resolver state, not screenshots or synthesized input.
"""
import re
import sys
from pathlib import Path

LOAD = re.compile(r'load control=(\w+) ID=(-?\d+) found=\d+ MOVETO L=(-?\d+) R=(-?\d+) U=(-?\d+) D=(-?\d+)')
RESOLVE = re.compile(r'resolve control=(\w+) id=(-?\d+) nav=\w+ raw=([\w,]+)')
NAV = re.compile(r'nav control=(\w+) id=(-?\d+) event=(\w+) value=(\w+)')
FOCUS = re.compile(r'focus panel=(\w+) vt=\w+ old=(\w+) new=(\w+) id=(-?\d+)')
DIRECTIONS = {0x3d: 0, 0x3f: 1, 0x3e: 2, 0x40: 3}  # UP LEFT DOWN RIGHT


def inspect(path):
    controls = {}
    mismatches, checked, moves = [], 0, []
    pending = None
    for line in Path(path).read_text().splitlines():
        m = LOAD.match(line)
        if m:
            ptr, ident, left, right, up, down = m.groups()
            controls[ptr] = (int(ident), tuple(map(int, (up, left, down, right))))
        m = RESOLVE.match(line)
        if m and m[1] in controls:
            actual = tuple(-1 if int(v, 16) == 0xffffffffffffffff else int(v, 16) for v in m[3].split(','))
            expected = controls[m[1]][1]
            checked += 1
            if actual != expected:
                mismatches.append((m[1], expected, actual))
        m = FOCUS.match(line)
        if m and pending:
            ptr, expected = pending
            if m[2] == ptr:
                moves.append((m[1], expected, int(m[4])))
        m = NAV.match(line)
        if m:
            pending = None
            event, value = int(m[3], 16), int(m[4], 16)
            if event in DIRECTIONS and value == 1 and m[1] in controls:
                target = controls[m[1]][1][DIRECTIONS[event]]
                if target >= 0:
                    pending = (m[1], target)
    return checked, mismatches, moves


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    before = inspect(sys.argv[1])
    after = inspect(sys.argv[2])
    assert before[0] >= 5 and before[1], 'baseline must capture the broken loader'
    assert any(expected != actual for _, expected, actual in before[2]), 'baseline must capture a wrong keyboard target'
    assert after[0] >= 5, 'fixed capture lacks resolver coverage'
    assert not after[1], f'fixed resolver mismatch: {after[1][:5]}'
    assert len(after[2]) >= 2, 'fixed capture needs at least two keyboard focus moves'
    assert not [(p, e, a) for p, e, a in after[2] if e != a], 'fixed keyboard focus differs from MOVETO target'
    print(f'PASS: baseline {len(before[1])}/{before[0]} incorrect links; fixed {after[0]} controls correct; '
          f'{len(after[2])} keyboard moves across {len(set(p for p, _, _ in after[2]))} panels matched GUI targets.')


if __name__ == '__main__':
    main()
