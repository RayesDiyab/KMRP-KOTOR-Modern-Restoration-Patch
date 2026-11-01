#!/usr/bin/env python3
"""A pad badge keeps its shape: every row of the table, at every scale, both ways of drawing it.

K1UniformBadge decides how large a badge is drawn on a label of its own, and K1BadgeKeepsShape
whether its button's fill may show it instead. Both are compiled from the shipped source
and asked about every row of K1ControllerBadgeShapes.inc, for the areas a button takes when a
layout scales it evenly, scales it only one way (1920x540 is the shape that does most of
this), and when its focused border keeps a different inset. The rule is the maintainer's: a
glyph's width and height change together (2026-10-05). The GUI audit stopped checking badges
when the run-time rule took over from fixed art (audit TST-03), so nothing did until this.

K1UniformBadge may leave the area's width, as the three-quarters floor says: a texture is as
wide as its button, the glyph is a small part of it, and the label is placed by its glyph.
Run: python testing/regression/Test-BadgeShape.py
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"
SHAPES = SRC / "K1ControllerBadgeShapes.inc"
CONTROLS = SRC / "vendor/K1XboxControls.cpp"

# Across and down, as a layout scales a button.
EVEN = [1.0, 1.25, 4 / 3, 1.5, 2.0, 3.0, 4.0, 6.0]
UNEVEN = [(1.5, 0.75), (2.0, 1.0), (2.67, 0.75), (1.0, 2.0), (0.75, 1.5), (4.0, 1.0)]
# A button's two borders keep clear this many pixels of it, normal and focused (the game's
# BORDER and HILIGHT dimensions; Options' Close has 0 and 6).
INSETS = [(0, 0), (0, 6), (6, 0), (2, 6)]

HARNESS = r'''
#include <cstdio>
#include <cstdlib>
%s
%s
int main()
{
    long long area[2], made[2];
    int byHeight;
    while (std::scanf("%%lld %%lld %%lld %%lld %%d", &area[0], &area[1], &made[0], &made[1], &byHeight) == 5) {
        int width = 0, height = 0;
        K1UniformBadge(area[0], area[1], made[0], made[1], byHeight != 0, &width, &height);
        std::printf("%%d %%d %%d\n", width, height, K1BadgeKeepsShape(area[0], area[1], made[0], made[1]) ? 1 : 0);
    }
    return 0;
}
'''


def function(source, signature):
    """The function that starts with SIGNATURE, whole."""
    start = source.index(signature)
    depth, at = 0, source.index("{", start)
    for index in range(at, len(source)):
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        if depth == 0:
            return source[start:index + 1]
    raise ValueError(signature)


def compile_harness(out):
    source = CONTROLS.read_text(encoding="utf-8")
    uniform = function(source, "void K1UniformBadge(")
    keeps = function(source, "bool K1BadgeKeepsShape(")
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    path = out / "badge.cpp"
    path.write_text(HARNESS % (uniform, keeps), encoding="utf-8")
    exe = out / "badge.exe"
    script = out / "build.cmd"
    args = ["cl", "/nologo", "/O2", "/std:c++17", "/EHsc", "/MT", "/W4", str(path), f"/Fo{out}\\", f"/Fe{exe}"]
    script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\n",
                      encoding="utf-8", newline="\r\n")
    subprocess.run(["cmd.exe", "/d", "/c", str(script)], check=True, stdout=subprocess.DEVNULL)
    return exe


def rows():
    found = re.findall(r'\{"(kmrp[a-z_0-9]+)",\s*(\d+),\s*(\d+),', SHAPES.read_text(encoding="utf-8"))
    return [(name, int(width), int(height)) for name, width, height in found]


def main():
    table = rows()
    print(f"{len(table)} rows")
    failures = 0

    def check(condition, what):
        nonlocal failures
        if not condition:
            failures += 1
            if failures <= 20:
                print(f"  FAIL  {what}")

    requests = []
    for name, width, height in table:
        for scale in EVEN:
            requests.append((name, "even", round(width * scale), round(height * scale), width, height, 0))
            requests.append((name, "by-height", round(width * scale), round(height * scale), width, height, 1))
        for across, down in UNEVEN:
            requests.append((name, "uneven", round(width * across), round(height * down), width, height, 0))
        # A whole scale with the height a pixel or three off: the shape is then a percent or
        # two out, which 2 per cent let through as a fill until 2026-10-09, when the main
        # menu's Quit was drawn 46 wide and 50 tall.
        for scale in (2, 3, 4, 6):
            for off in (1, 2, 3):
                requests.append((name, "near", width * scale, height * scale + off, width, height, 0))
        for normal, focused in INSETS:
            # The area each border fills once the button is three times the size it was
            # made for, and the area that texture was made for (ShowK1BadgeOverlay).
            step = 2 * (normal - focused)
            made_width, made_height = width + step, height + step
            if made_width > 0 and made_height > 0:
                requests.append((name, "focused", (width + 2 * normal) * 3 - 2 * focused,
                                 (height + 2 * normal) * 3 - 2 * focused, made_width, made_height, 0))

    with tempfile.TemporaryDirectory(dir=ROOT / "build", ignore_cleanup_errors=True) as temporary:
        exe = compile_harness(Path(temporary))
        text = "".join(f"{r[2]} {r[3]} {r[4]} {r[5]} {r[6]}\n" for r in requests)
        result = subprocess.run([str(exe)], input=text, capture_output=True, text=True, timeout=120)
    answers = [tuple(map(int, line.split())) for line in result.stdout.splitlines()]
    check(len(answers) == len(requests), f"{len(answers)} answers to {len(requests)} questions")

    floor_used = whole = 0
    for request, (drawn_width, drawn_height, keeps) in zip(requests, answers):
        name, kind, area_width, area_height, made_width, made_height, by_height = request
        where = f"{name} {kind} area {area_width}x{area_height} made {made_width}x{made_height}"
        check(drawn_width > 0 and drawn_height > 0, f"{where}: drawn {drawn_width}x{drawn_height}")
        # One factor for both: within the half pixel of rounding either one gets.
        exact = drawn_height * made_width / made_height
        check(abs(drawn_width - exact) <= 0.5 + made_width / made_height / 2 + 1e-9,
              f"{where}: drawn {drawn_width}x{drawn_height} is not the made shape")
        check(drawn_height <= area_height, f"{where}: taller than its area, {drawn_height}")
        if by_height:
            check(drawn_height == area_height, f"{where}: by height is the area's height, {drawn_height}")
        else:
            check(drawn_height >= (3 * area_height + 2) // 4, f"{where}: under three quarters of the height, {drawn_height}")
            floor_used += drawn_width > area_width
        # "Exact for the same area at any whole scale": a part scale rounds the area, and
        # then the label draws it, which keeps the shape by the checks above.
        if kind == "even" and area_width % made_width == 0 and area_height % made_height == 0 and \
                area_width // made_width == area_height // made_height:
            whole += 1
            check(keeps == 1, f"{where}: a whole scale keeps the shape")
        if kind == "near" or (kind == "uneven" and made_height >= 10):
            across, down = area_width / made_width, area_height / made_height
            apart = max(across, down) / min(across, down) - 1
            check((keeps == 1) == (apart * area_height < 0.5), f"{where}: the half-pixel test answers {keeps}")
            check(not keeps or apart * area_height < 0.5, f"{where}: an uneven scale passes as a fill")
    print(f"{len(answers)} areas, {whole} at whole scales, {floor_used} past their width by the three-quarters floor")

    source = CONTROLS.read_text(encoding="utf-8")
    check(source.count("K1UniformBadge(width, height, shape->width, shape->height, tall > 0") == 1,
          "the overlay sizes its badge through K1UniformBadge")
    check(source.count("K1BadgeKeepsShape(") >= 3, "the overlay tests both borders")

    if failures:
        print(f"FAILED ({failures})")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
