#!/usr/bin/env python3
"""Check macos/tools/kmrp-guiblend.c against a Python blend and against real sets.

The Mac installer derives the GUI set for a display the build has no set for with
kmrp-guiblend, from the table tools/build_gui_blend_table.py packs (see that file). This:

1. builds the table and the helper from the resources given;
2. derives several resolutions with the helper and with an independent Python blend over
   the same table, and requires them to match byte for byte;
3. derives every macOS-group resolution (built by the full pipeline, and not anchors of the
   table, so these are held-out cases) and compares every varying field with the built set.

Limits for 3, from the measurement of 2026-09-29: at least 99.5% of fields within 1 px and
none further than 16 px, in every file the Mac loads (kmrplayout.gui, the Windows
controller-layout screen, is left out). The misses are list scrollbars, whose positions come
from the 3440x1440 geometry the build carries over, which is not linear.

    python testing/regression/Test-GuiBlendHelper.py [RESOURCES_DIR]
"""
from __future__ import annotations

import math
import struct
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_universal_resources as pur  # noqa: E402

RESOURCES = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "kmrp" / "resources"
# Listed and unlisted: the macOS group, and Mac scaled modes the build has no set for.
UNLISTED = ["1800x1169", "3600x2338", "2056x1329", "1352x878", "1710x1112", "1920x1243", "1280x832"]
# KMRP's Controller Layout screen, part of the Windows controller layer: built at every
# resolution, never loaded on the Mac (the Aspyr port has its own controller support). Its
# layout is generated, not interpolated, and misses by up to 62 px (measured 2026-09-29).
NOT_LOADED_ON_MAC = {"kmrplayout.gui"}


def read_table(path: Path):
    d = path.read_bytes()
    assert d[:4] == b"KGBL" and struct.unpack_from("<I", d, 4)[0] == 1
    p = 8
    nf = struct.unpack_from("<I", d, p)[0]; p += 4
    aspects = list(struct.unpack_from(f"<{nf}d", d, p)); p += 8 * nf
    na = struct.unpack_from("<I", d, p)[0]; p += 4
    anchors = [struct.unpack_from("<III", d, p + 12 * i) for i in range(na)]; p += 12 * na
    nfiles = struct.unpack_from("<I", d, p)[0]; p += 4
    files = []
    for _ in range(nfiles):
        n = struct.unpack_from("<H", d, p)[0]; p += 2
        name = d[p:p + n].decode(); p += n
        size = struct.unpack_from("<I", d, p)[0]; p += 4
        template = d[p:p + size]; p += size
        s = struct.unpack_from("<I", d, p)[0]; p += 4
        offsets = [struct.unpack_from("<II", d, p + 8 * i)[0] for i in range(s)]; p += 8 * s
        values = [list(struct.unpack_from(f"<{s}i", d, p + 4 * s * a)) for a in range(na)]
        p += 4 * s * na
        files.append((name, template, offsets, values))
    return aspects, anchors, files


def family_at_height(anchors, family, aspect, height):
    by_height = {}
    for i, (w, h, f) in enumerate(anchors):
        if f != family:
            continue
        if h not in by_height or abs(w / h - aspect) < abs(anchors[by_height[h]][0] / h - aspect):
            by_height[h] = i
    if height in by_height:
        i = by_height[height]
        return [(i, 1.0)], float(anchors[i][0])
    below = [h for h in by_height if h < height]
    above = [h for h in by_height if h > height]
    if not below or not above:
        return None, 0.0
    lo, hi = by_height[max(below)], by_height[min(above)]
    t = (height - anchors[lo][1]) / (anchors[hi][1] - anchors[lo][1])
    return [(lo, 1.0 - t), (hi, t)], anchors[lo][0] + (anchors[hi][0] - anchors[lo][0]) * t


def terms_for(aspects, anchors, width, height):
    aspect = width / height
    order = sorted(range(len(aspects)), key=lambda i: aspects[i])
    for f in order:
        if abs(aspects[f] - aspect) < 0.005:
            return [t for t in family_at_height(anchors, f, aspects[f], height)[0] if t[1] > 1e-9]
    lower = [f for f in order if aspects[f] < aspect]
    upper = [f for f in order if aspects[f] > aspect]
    a, wa = family_at_height(anchors, lower[-1], aspects[lower[-1]], height)
    b, wb = family_at_height(anchors, upper[0], aspects[upper[0]], height)
    s = (width - wa) / (wb - wa)
    return [t for t in [(i, w * (1 - s)) for i, w in a] + [(i, w * s) for i, w in b] if t[1] > 1e-9]


def python_blend(table, width, height) -> dict[str, bytes]:
    aspects, anchors, files = table
    terms = terms_for(aspects, anchors, width, height)
    out = {}
    for name, template, offsets, values in files:
        data = bytearray(template)
        for s, off in enumerate(offsets):
            v = 0.0
            for i, w in terms:
                v += values[i][s] * w
            struct.pack_into("<i", data, off, int(math.copysign(math.floor(abs(v) + 0.5), v)))
        out[name] = bytes(data)
    return out


def main() -> int:
    failed = False
    with tempfile.TemporaryDirectory(prefix="kmrp-guiblend-test-") as tmp:
        tmp = Path(tmp)
        table_path, helper = tmp / "gui-blend.bin", tmp / "kmrp-guiblend"
        subprocess.run([sys.executable, str(ROOT / "tools" / "build_gui_blend_table.py"),
                        str(RESOURCES), str(table_path)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["clang", "-O2", "-o", str(helper), str(ROOT / "macos" / "tools" / "kmrp-guiblend.c")],
                       check=True)
        table = read_table(table_path)
        mac = pur.GROUPS["macOS"]

        # 1. Helper against the Python blend, byte for byte.
        mismatches = 0
        for res in mac + UNLISTED:
            w, h = (int(v) for v in res.split("x"))
            out = tmp / res
            subprocess.run([str(helper), str(table_path), str(w), str(h), str(out)],
                           check=True, stdout=subprocess.DEVNULL)
            for name, data in python_blend(table, w, h).items():
                if (out / name).read_bytes() != data:
                    mismatches += 1
                    print(f"  differs: {res} {name}")
        ok = mismatches == 0
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} helper matches the Python blend byte for byte "
              f"({len(mac) + len(UNLISTED)} resolutions, {mismatches} files differ)")

        # 2. Held-out accuracy against the sets the full pipeline built.
        tally, worst = Counter(), (0, "")
        for res in mac:
            with zipfile.ZipFile(RESOURCES / f"gui-{res}.zip") as z:
                for name, template, offsets, _ in table[2]:
                    if name in NOT_LOADED_ON_MAC:
                        continue
                    real, derived = z.read(name), (tmp / res / name).read_bytes()
                    for off in offsets:
                        d = abs(struct.unpack_from("<i", real, off)[0] - struct.unpack_from("<i", derived, off)[0])
                        tally["n"] += 1
                        tally["within 1"] += d <= 1
                        if d > worst[0]:
                            worst = (d, f"{res} {name} @{off:#x}")
        within = tally["within 1"] / tally["n"]
        ok = within >= 0.995 and worst[0] <= 16
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} macOS sets derived from the others: {tally['n']} fields, "
              f"{100 * within:.2f}% within 1 px, worst {worst[0]} px ({worst[1]})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
