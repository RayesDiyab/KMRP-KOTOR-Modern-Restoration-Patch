#!/usr/bin/env python3
"""Every size field the module writes, at every size KMRP lists, against the reference.

KmrpEngineFieldValue (K1EngineFields.h) is what the game runs on: it fills the recipe's 59
fields at each size. Nothing checked it until this test (audit TST-06): the values that were
checked were its C# twin's, ResolutionPatch, which only `--apply` reaches. Here the header
is compiled with the module's own compiler flags and asked for every field, and the installer's
`--apply` writes the reference executable for the same size, read back byte for byte. This is
also what stands in for `--apply` once it goes (approved decision 3): its values are then
held in this test's baseline instead.

Then the rest of the rule, which the reference does not have: the Icon Size slider's rows at
every percent, and the marker clamp where the height passes 5,715 lines.
Run: python testing/regression/Test-EngineFields.py
"""
from pathlib import Path
import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/controller-native"
GENERATED = ROOT / "build/native-runtime/NativeEngine.generated.h"
INSTALLER = ROOT / "dist/KMRP - KOTOR Modern Restoration Patch.exe"
SOURCE_EXE = ROOT / "build-inputs/swkotornopatch.exe"
BASELINE = Path(__file__).with_name("engine-fields-baseline.json")
CATALOG = ROOT / "build/kmrp/resources/resolutions.tsv"

HARNESS = r'''
#include "K1EngineFields.h"
#include "NativeEngine.generated.h"
#include <cstdio>
#include <cstdlib>
int main(int argc, char** argv)
{
    for (int i = 1; i + 2 < argc; i += 3) {
        const int width = std::atoi(argv[i]), height = std::atoi(argv[i + 1]), percent = std::atoi(argv[i + 2]);
        for (const auto& f : kNativeFields) {
            const auto value = KmrpEngineFieldValue(f.va, f.size, f.kind, f.base, width, height, percent);
            std::printf("%d %d %d %X %u %u %d %02X%02X%02X%02X\n", width, height, percent, f.va, f.size, f.kind,
                        f.base, value[0], value[1], value[2], value[3]);
        }
    }
    return 0;
}
'''

# Sizes not listed, which the blend reaches (ResolutionCatalog.Find), one of each shape.
DERIVED = [(1500, 1000), (2000, 1200), (3600, 1500)]


def exact_tie(kind, base, height):
    """base x height / 720 is exactly half way between two integers. The module gives the
    even one, as its rule says. The reference gives the lower: its scale is the
    single-precision value below the true one, and the 32-bit CLR multiplies it in double.
    Arithmetic decides this, not a list of addresses, so any other difference still fails."""
    return kind in (3, 10, 11) and (2 * abs(base) * height) % 1440 == 720


def compile_harness(out):
    build = (SRC / "build_controller_standalone.cmd").read_text(encoding="utf-8")
    vc = re.search(r"^set VC=(.+)$", build, re.MULTILINE).group(1).strip()
    source = out / "fields.cpp"
    source.write_text(HARNESS, encoding="utf-8")
    exe = out / "fields.exe"
    script = out / "build.cmd"
    args = ["cl", "/nologo", "/O2", "/fp:strict", "/std:c++17", "/EHsc", "/MT", "/W4", f"/I{SRC}",
            f"/I{GENERATED.parent}", str(source), f"/Fo{out}\\", f"/Fe{exe}"]
    script.write_text(f'@echo off\ncall "{vc}" x86 >nul\n' + subprocess.list2cmdline(args) + "\n",
                      encoding="utf-8", newline="\r\n")
    subprocess.run(["cmd.exe", "/d", "/c", str(script)], check=True, stdout=subprocess.DEVNULL)
    return exe


def ask(exe, requests):
    """{(width, height, percent): {va: (size, kind, bytes)}}"""
    values = {}
    for start in range(0, len(requests), 40):
        arguments = [str(n) for request in requests[start:start + 40] for n in request]
        output = subprocess.run([str(exe), *arguments], check=True, capture_output=True, text=True).stdout
        for line in output.splitlines():
            width, height, percent, va, size, kind, base, value = line.split()
            size = int(size)
            values.setdefault((int(width), int(height), int(percent)), {})[int(va, 16)] = (
                size, int(kind), bytes.fromhex(value)[:size], int(base))
    return values


def sections(image):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional = struct.unpack_from("<H", image, pe + 20)[0]
    table = pe + 24 + optional
    rows = []
    for index in range(count):
        at = table + index * 40
        virtual_size, rva, raw_size, raw = struct.unpack_from("<IIII", image, at + 8)
        rows.append((0x400000 + rva, max(virtual_size, raw_size), raw))
    return rows


def read_va(image, rows, va, size):
    for start, length, raw in rows:
        if start <= va and va + size <= start + length:
            return bytes(image[raw + va - start:raw + va - start + size])
    raise ValueError(f"{va:08X} is in no section")


def reference(sizes, out):
    """The installer's bytes at every field, at every size."""
    fields = {}
    for width, height in sizes:
        target = out / f"{width}x{height}.exe"
        result = subprocess.run([str(INSTALLER), "--apply", str(SOURCE_EXE), str(target), f"{width}x{height}"])
        if result.returncode:
            raise SystemExit(f"--apply failed at {width}x{height}")
        fields[(width, height)] = target.read_bytes()
        target.unlink()
    return fields


def catalog_sizes():
    sizes = []
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            parts = line.split("\t")
            sizes.append((int(parts[1]), int(parts[2])))
    return sizes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline", action="store_true")
    options = parser.parse_args()
    for needed in (GENERATED, INSTALLER, SOURCE_EXE, CATALOG):
        if not needed.exists():
            raise SystemExit(f"{needed} is missing: build first")
    sizes = sorted(set(catalog_sizes()) | set(DERIVED))
    failures = 0

    def check(condition, what):
        nonlocal failures
        if not condition:
            failures += 1
            print(f"  FAIL  {what}")

    with tempfile.TemporaryDirectory() as temporary:
        out = Path(temporary)
        exe = compile_harness(out)
        values = ask(exe, [(w, h, 50) for w, h in sizes])
        print(f"{len(sizes)} sizes, {len(next(iter(values.values())))} fields")

        images = reference(sizes, out)
        differing = {}
        compared = ties = 0
        for (width, height), image in images.items():
            rows = sections(image)
            for va, (size, kind, value, base) in values[(width, height, 50)].items():
                compared += 1
                expected = read_va(image, rows, va, size)
                number = int.from_bytes(value, "little", signed=True)
                other = int.from_bytes(expected, "little", signed=True)
                if expected != value and exact_tie(kind, base, height) and number % 2 == 0 and abs(number - other) == 1:
                    ties += 1
                elif expected != value:
                    differing.setdefault(va, []).append(
                        f"{width}x{height} kind {kind}: module {value.hex()} reference {expected.hex()}")
        print(f"{compared} fields compared with --apply, {ties} exact ties")
        for va, rows in sorted(differing.items()):
            check(False, f"{va:08X} differs at {len(rows)} sizes, first {rows[0]}")

        snapshot = {f"{w}x{h}": {f"{va:X}": row[2].hex() for va, row in sorted(values[(w, h, 50)].items())}
                    for w, h in sizes}
        if options.write_baseline:
            BASELINE.write_text(json.dumps(snapshot, indent=0, sort_keys=True) + "\n", encoding="utf-8")
            print(f"wrote {BASELINE.name}")
        else:
            check(BASELINE.exists() and json.loads(BASELINE.read_text(encoding="utf-8")) == snapshot,
                  "the values are the baseline's")

        # The slider: nothing changes at or below 50%, rows never shrink, they grow with
        # the percent, and only the four fields it owns move.
        rows = {0x6CD8D9, 0x6CDB79, 0x6AB8EF, 0x6ACB20}
        for width, height in [(1280, 720), (1920, 1080), (3440, 1440), (3840, 2160)]:
            slider = ask(exe, [(width, height, p) for p in (25, 40, 50, 60, 75, 100)])
            at = lambda p, va: int.from_bytes(slider[(width, height, p)][va][2], "little", signed=True)
            default = slider[(width, height, 50)]
            for percent in (25, 40):
                check(slider[(width, height, percent)] == default, f"{height}p {percent}%: as at the default")
            for percent in (60, 75, 100):
                moved = {va for va, row in slider[(width, height, percent)].items() if row != default[va]}
                check(moved <= rows, f"{height}p {percent}%: only the row fields move, {moved - rows}")
            for va in rows:
                check(at(60, va) >= at(50, va) and at(75, va) >= at(60, va) and at(100, va) >= at(75, va),
                      f"{height}p {va:08X}: rows grow with the slider")
                check(at(100, va) > at(50, va), f"{height}p {va:08X}: the largest icons outgrow the default row")

        # The markers' byte operands stay signed bytes past the clamp, and small screens
        # never reach zero. Not sizes KMRP lists, so the reference has no say.
        clamp = ask(exe, [(320, 200, 50), (7680, 4320, 50), (15360, 8640, 50)])
        for request, fields in clamp.items():
            for va, (size, kind, value, base) in fields.items():
                number = int.from_bytes(value, "little", signed=True)
                if kind == 11:
                    check(-127 <= number <= -1, f"{request} {va:08X}: a marker offset is a signed byte, {number}")
                if kind == 10:
                    check(1 <= number <= 254, f"{request} {va:08X}: a marker size is positive, {number}")

    if failures:
        print(f"FAILED ({failures})")
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
