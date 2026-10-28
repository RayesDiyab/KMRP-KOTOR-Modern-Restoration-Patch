#!/usr/bin/env python3
"""Checks the controller button pictures drawn from their outlines (issue 68).

1. assets/controller-glyphs/glyphs.json has every picture every family uses.
2. macos/tools/kmrp-guiblend.c's draw_glyph, which the Mac installer and both games' patch
   DLLs draw badges with, draws every glyph byte for byte as tools/controller_glyphs.py does
   (the build's badges), at small and large sizes, squeezed as a badge texture squeezes them,
   cut off by the texture's edge, and on a backing.
3. Every lettered face button has its letter centred on its disc, measured from the drawn
   pixels: the box of the letter's own colour against the box of the whole button, at 400 px,
   within a quarter of a pixel (the maintainer's rule, 2026-10-27). The check is shown to see
   an offset first: Xelu's own uncentred Xbox B must measure off.

    python testing/regression/Test-ControllerGlyphs.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_controller_prompt_textures as prompts  # noqa: E402
import controller_glyphs as cg  # noqa: E402
import native_helpers  # noqa: E402

# (texture w, texture h, left, top, dw, dh): plain, squeezed like a 512x64 badge, cut off by
# each edge, one pixel, and large.
CASES = [(40, 40, 2, 2, 36, 36), (512, 64, 100, 9, 23, 46), (64, 64, -5, 3, 30, 30),
         (64, 64, 40, -6, 30, 30), (20, 20, 0, 0, 1, 1), (130, 130, 1, 1, 128, 128),
         (512, 64, 30, 2, 61, 60)]
BACKING = (32, 56, 88, 200)
LETTERED = {"xbox": "ABXY", "switch": "ABXY", "steamdeck": "ABXY", "playstation": "A"}


def letter_offset(image: np.ndarray, colour) -> tuple[float, float]:
    alpha = image[..., 3].astype(int)
    ys, xs = np.nonzero(alpha > 127)
    dcx, dcy = (xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2
    near = np.abs(image[..., :3].astype(int) - np.array(colour)).sum(-1) < 12
    ly, lx = np.nonzero(near & (alpha > 250))
    return (lx.min() + lx.max() + 1) / 2 - dcx, (ly.min() + ly.max() + 1) / 2 - dcy


def main() -> int:
    failures = []
    names = [f"{family}/{glyph}" for family, (_, art) in prompts.GLYPH_FAMILIES.items() for glyph in art]
    missing = [n for n in names if n not in cg.glyphs()]
    if missing:
        failures.append(f"glyphs.json lacks {', '.join(missing)}")

    with tempfile.TemporaryDirectory(prefix="kmrp-glyphs-") as tmp:
        tmp = Path(tmp)
        harness = native_helpers.build(Path(__file__).resolve().parent / "glyph_draw_harness.c", tmp, "glyph-draw")
        # Every drawing as one job of one run of the harness (started once per drawing,
        # this took three minutes).
        jobs, expected = [], []
        for name in names:
            if name in missing:
                continue
            family, glyph = name.split("/")
            packed = tmp / f"{family}-{glyph}.bin"
            packed.write_bytes(cg.pack(cg.glyph(family, glyph)))
            for backed in (False, True):
                for tw, th, left, top, dw, dh in CASES[:4] if backed else CASES:
                    sheet = np.zeros((th, tw, 4), np.uint8)
                    extra = []
                    if backed:
                        sheet[...] = BACKING
                        extra = [str(v) for v in BACKING]
                    cg.draw_into(sheet, family, glyph, left, top, dw, dh, BACKING if backed else None)
                    out = tmp / f"out-{len(jobs)}.rgba"
                    jobs.append(" ".join([native_helpers.arg(packed), native_helpers.arg(out), str(tw), str(th),
                                          str(left), str(top), str(dw), str(dh), *extra]))
                    expected.append((name, backed, (tw, th, left, top, dw, dh), out, sheet))
        # One drawing too large to keep (over the drawer's 8 MB): drawn and written four rows
        # at a time, which must come out the same. Drawn whole, the Controller Layout's board
        # took 2 GB and crashed the 32-bit game (2026-10-27).
        packed = tmp / "xbox-DIAGRAM.bin"
        packed.write_bytes(cg.pack(cg.glyph("xbox", "DIAGRAM")))
        big = (960, 640, 3, 5, 950, 615)
        sheet = np.zeros((big[1], big[0], 4), np.uint8)
        cg.draw_into(sheet, "xbox", "DIAGRAM", big[2], big[3], big[4], big[5], None)
        out = tmp / f"out-{len(jobs)}.rgba"
        jobs.append(" ".join([native_helpers.arg(packed), native_helpers.arg(out), *map(str, big)]))
        expected.append(("xbox/DIAGRAM", False, big, out, sheet))
        if any(" " in str(path) for path in (tmp,)):
            raise SystemExit(f"{tmp}: the harness reads job paths without spaces")
        job_file = tmp / "jobs.txt"
        job_file.write_text(chr(10).join(jobs) + chr(10), encoding="ascii")
        compared = 0
        for slice_name, exe in harness.items():
            done = subprocess.run([str(exe), native_helpers.arg(job_file)], check=True,
                                  capture_output=True, text=True).stdout.strip()
            if done != str(len(jobs)):
                failures.append(f"the harness ({slice_name}) drew {done} of {len(jobs)}")
            for name, backed, (tw, th, left, top, dw, dh), out, sheet in expected:
                native = np.frombuffer(out.read_bytes(), np.uint8).reshape(th, tw, 4)
                if not np.array_equal(native, sheet):
                    bad = np.argwhere(np.any(native != sheet, axis=-1))
                    y, x = bad[0]
                    failures.append(f"{name} {dw}x{dh} at ({left}, {top}) in {tw}x{th}"
                                    f"{' on a backing' if backed else ''} ({slice_name}): {len(bad)} pixels differ, "
                                    f"first ({x}, {y}): C {tuple(native[y, x])}, Python {tuple(sheet[y, x])}")
                compared += 1
        print(f"  draw_glyph: {compared} drawings compared with the Python drawer")

    # the measure sees an offset: Xelu's B as he placed it, 2 px right of 81, before centring
    import build_controller_glyph_vectors as vectors  # noqa: E402
    if vectors.FLA.is_file():
        root = vectors.read_fla(vectors.FLA)
        items, box = vectors.plain(root, "xbox", "B")
        cg.glyphs()["xbox/_uncentred"] = vectors.encode(items, box)
        image = np.asarray(cg.picture("xbox", "_uncentred", 400, 400))
        dx, _ = letter_offset(image, cg.glyph("xbox", "_uncentred")["items"][-1]["paint"]["solid"][:3])
        del cg.glyphs()["xbox/_uncentred"]
        if dx < 5:
            failures.append(f"the centring measure did not see Xelu's offset B ({dx:+.2f} px)")
    else:
        print("  (Vector Source.fla not here: the centring measure's own check skipped)")
    for family, letters in LETTERED.items():
        for glyph in letters:
            image = np.asarray(cg.picture(family, glyph, 400, 400))
            g = cg.glyph(family, glyph)
            last = g["items"][-1]["paint"]
            if "solid" not in last:
                failures.append(f"{family}/{glyph}: the letter is not the last item drawn")
                continue
            dx, dy = letter_offset(image, last["solid"][:3])
            if abs(dx) > 0.25 or abs(dy) > 0.25:
                failures.append(f"{family}/{glyph}: letter {dx:+.2f}, {dy:+.2f} px off the disc's centre at 400 px")
    print(f"  letters: {sum(len(v) for v in LETTERED.values())} face buttons measured")

    for failure in failures:
        print(f"FAIL: {failure}")
    print("Test-ControllerGlyphs: " + ("FAILED" if failures else "passed"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
