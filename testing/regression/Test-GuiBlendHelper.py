#!/usr/bin/env python3
"""Check macos/tools/kmrp-guiblend.c against a Python blend and against real sets.

The Mac installer derives the GUI set for a display the build has no set for with
kmrp-guiblend, from the table tools/build_gui_blend_table.py packs (see that file), and the
fonts of the nearest set it installs. This:

1. builds the table and the helper from the resources given;
2. derives several resolutions with the helper and with an independent Python derivation
   over the same table, and requires them to match byte for byte. The Python applies the
   Container's fit itself, fits the lists made as tall as whole rows with the build's own
   scale_listbox_padding.fit_list_to_rows, and makes the Controller Layout screen with the
   build's own generator (build_controller_layout.build_gui) from the blended Gameplay
   panel, so this is also the check that the helper's copies of that rule and that
   generator match them;
3. rebuilds every anchor of the table from the table, with its own fonts, and requires the
   build's set byte for byte;
4. derives every macOS-group resolution (built by the full pipeline, and not anchors of the
   table, so these are held-out cases), with the set's own fonts, and compares every varying
   field with the built set;
5. at every derived size, the Container's Give Items badge sits at its designed gap.

Limits for 4, from the measurement of 2026-09-29: at least 99.5% of fields within 1 px and
none further than 16 px. The misses are list scrollbars, whose positions come from the
3440x1440 geometry the build carries over, which is not linear.

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
import build_controller_prompt_textures as prompts  # noqa: E402
import build_controller_layout as layout  # noqa: E402
import scale_listbox_padding as slp  # noqa: E402
from build_gui_blend_table import LAYOUT_SCREEN  # noqa: E402

RESOURCES = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "kmrp" / "resources"
# Listed and unlisted: the macOS group, and Mac scaled modes the build has no set for.
UNLISTED = ["1800x1169", "3600x2338", "2056x1329", "1352x878", "1710x1112", "1920x1243", "1280x832"]
# The files of a set the helper reads (the installer extracts the whole set there).
SET_FILES = (prompts.PROMPT_MANIFEST_NAME, f"{layout.CAPTION_FONT}.txi")


def read_text(d: bytes, p: int) -> tuple[str, int]:
    n = struct.unpack_from("<H", d, p)[0]
    return d[p + 2:p + 2 + n].decode(), p + 2 + n


def read_table(path: Path):
    d = path.read_bytes()
    assert d[:4] == b"KGBL" and struct.unpack_from("<I", d, 4)[0] == 3
    p = 8
    nf = struct.unpack_from("<I", d, p)[0]; p += 4
    aspects = list(struct.unpack_from(f"<{nf}d", d, p)); p += 8 * nf
    na = struct.unpack_from("<I", d, p)[0]; p += 4
    anchors = [struct.unpack_from("<III", d, p + 12 * i) for i in range(na)]; p += 12 * na
    fits = {}
    nfits = struct.unpack_from("<I", d, p)[0]; p += 4
    for _ in range(nfits):
        name, p = read_text(d, p)
        row, p = read_text(d, p)
        radius_short, radius, short_below, gap, edge = struct.unpack_from("<ddIdd", d, p); p += 36
        left, width, button_width, button_height, count = struct.unpack_from("<5I", d, p); p += 20
        widths = list(struct.unpack_from(f"<{count}I", d, p)); p += 4 * count
        fits[name] = dict(row=row, radius_short=radius_short, radius=radius, short_below=short_below,
                          gap=gap, edge=edge, left=left, width=width, button_width=button_width,
                          button_height=button_height, widths=widths)
    layouts = {}
    nlayouts = struct.unpack_from("<I", d, p)[0]; p += 4
    for _ in range(nlayouts):
        # Read only for its name and font: the Python side makes the screen with build_gui.
        name, p = read_text(d, p)
        font, p = read_text(d, p)
        layouts[name] = font
        constants = struct.unpack_from("<I", d, p)[0]; p += 4
        for _ in range(constants):
            _, p = read_text(d, p)
            p += 8
        rows = struct.unpack_from("<I", d, p)[0]; p += 4
        for _ in range(rows):
            p += 1 + 8 + 8
            _, p = read_text(d, p)
        p += 8                                   # the root's WIDTH and HEIGHT offsets
        controls = struct.unpack_from("<I", d, p)[0]; p += 4 + 16 * controls
    # Skipped: the Python side fits the lists with the build's own rule (ROW_LISTS).
    nrowfits = struct.unpack_from("<I", d, p)[0]; p += 4
    for _ in range(nrowfits):
        _, p = read_text(d, p)
        _, p = read_text(d, p)
        p += 1 + 8 + 4
        bases = struct.unpack_from("<I", d, p)[0]; p += 4 + 4 * bases
        p += 20
        below = struct.unpack_from("<I", d, p)[0]; p += 4 + 4 * below
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
    return aspects, anchors, fits, layouts, files


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


def caption_width(manifest: bytes, row: str) -> float:
    """The baked label width of `row` in a prompt manifest, as kmrp-guiblend reads it."""
    for line in manifest.decode("utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "prompt" and parts[1] == row:
            return float(parts[4])
    raise AssertionError(f"the prompt manifest has no {row}")


def apply_fit(fit: dict, data: bytearray, caption: float) -> None:
    """prepare_universal_resources.fit_container_to_caption, on the blended file."""
    def get(offset):
        return struct.unpack_from("<i", data, offset)[0]

    def add(offset, delta):
        struct.pack_into("<i", data, offset, get(offset) + delta)
    height = get(fit["button_height"])
    radius = height * (fit["radius_short"] if height < fit["short_below"] else fit["radius"])
    extra = math.ceil(caption + 2.0 * radius * (fit["gap"] + 1.0 + fit["edge"]) - get(fit["button_width"]))
    if extra <= 0:
        return
    extra += extra % 2
    add(fit["left"], -(extra // 2))
    add(fit["width"], extra)
    for offset in fit["widths"]:
        add(offset, extra)


def python_derive(table, width, height, set_dir: Path, scratch: Path) -> dict[str, bytes]:
    """What the helper should write: the blend, the lists fitted to whole rows by the
    build's own rule, the Container's fit, and the Controller Layout screen made by the
    build's own generator from the blended Gameplay panel."""
    aspects, anchors, fits, layouts, files = table
    terms = terms_for(aspects, anchors, width, height)
    out = {}
    for name, template, offsets, values in files:
        data = bytearray(template)
        for s, off in enumerate(offsets):
            v = 0.0
            for i, w in terms:
                v += values[i][s] * w
            struct.pack_into("<i", data, off, int(math.copysign(math.floor(abs(v) + 0.5), v)))
        for (screen, tag), (kind, bases) in slp.ROW_LISTS.items():
            if screen == name:
                path = scratch / name
                path.write_bytes(bytes(data))
                if slp.fit_list_to_rows(path, path, height, tag, bases, kind == "popup"):
                    data = bytearray(path.read_bytes())
        if name in fits:
            apply_fit(fits[name], data, caption_width((set_dir / prompts.PROMPT_MANIFEST_NAME).read_bytes(),
                                                      fits[name]["row"]))
        out[name] = bytes(data)
    for name, font in layouts.items():
        source, made = scratch / "optgameplay.gui", scratch / name
        source.write_bytes(out["optgameplay.gui"])
        extent = pur.read_gff(source).root.get_struct("EXTENT")
        layout.build_gui(source, made, extent.get_int32("WIDTH"), extent.get_int32("HEIGHT"),
                         set_dir / f"{font}.txi")
        out[name] = made.read_bytes()
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
        listed = sorted(p.name[4:-4] for p in RESOURCES.glob("gui-*.zip"))
        scratch = tmp / "scratch"
        scratch.mkdir()

        def set_dir(size: str) -> Path:
            """A set's files the helper reads, as the installer extracts them."""
            path = tmp / f"set-{size}"
            if not path.exists():
                path.mkdir()
                with zipfile.ZipFile(RESOURCES / f"gui-{size}.zip") as z:
                    for name in SET_FILES:
                        (path / name).write_bytes(z.read(name))
            return path

        def nearest(res: str) -> str:
            """The set whose fonts and art the installer takes: by height, then shape."""
            w, h = (int(v) for v in res.split("x"))
            return min(listed, key=lambda s: (abs(int(s.split("x")[1]) - h),
                                              abs(int(s.split("x")[0]) / int(s.split("x")[1]) - w / h)))

        def helper_derive(res: str, fonts: str) -> Path:
            w, h = (int(v) for v in res.split("x"))
            out = tmp / f"{res}-{fonts}"
            subprocess.run([str(helper), str(table_path), str(w), str(h), str(out), str(set_dir(fonts))],
                           check=True, stdout=subprocess.DEVNULL)
            return out

        # 2. Helper against the Python derivation, byte for byte, with the installer's fonts.
        mismatches = 0
        for res in mac + UNLISTED:
            w, h = (int(v) for v in res.split("x"))
            out = helper_derive(res, nearest(res))
            for name, data in python_derive(table, w, h, set_dir(nearest(res)), scratch).items():
                if (out / name).read_bytes() != data:
                    mismatches += 1
                    print(f"  differs: {res} {name}")
        ok = mismatches == 0
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} helper matches the Python derivation byte for byte, "
              f"{LAYOUT_SCREEN} made by build_gui ({len(mac) + len(UNLISTED)} resolutions, "
              f"{mismatches} files differ)")

        # 3. Every anchor the blend resolves to itself, rebuilt from the table with its own
        #    fonts. (Not 1360x768: it shares its height and family with 1366x768, and the
        #    blend takes the one nearer the family's aspect ratio. The installer blends no
        #    listed size, so that is the blend's rule, not a miss.)
        anchors = [f"{w}x{h}" for i, (w, h, _) in enumerate(table[1])
                   if terms_for(table[0], table[1], w, h) == [(i, 1.0)]]
        differ = []
        for res in anchors:
            out = helper_derive(res, res)
            with zipfile.ZipFile(RESOURCES / f"gui-{res}.zip") as z:
                differ += [f"{res} {name}" for name, *_ in table[4] if (out / name).read_bytes() != z.read(name)]
        ok = not differ
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} every anchor rebuilt from the table is the build's set, byte "
              f"for byte ({len(anchors)} sets{': ' + ', '.join(differ[:6]) if differ else ''})")

        # 4. Held-out accuracy against the sets the full pipeline built, with their own fonts.
        tally, worst, per_file = Counter(), (0, ""), Counter()
        for res in mac:
            derived = helper_derive(res, res)
            with zipfile.ZipFile(RESOURCES / f"gui-{res}.zip") as z:
                for name, template, offsets, _ in table[4]:
                    real, made = z.read(name), (derived / name).read_bytes()
                    for off in offsets:
                        d = abs(struct.unpack_from("<i", real, off)[0] - struct.unpack_from("<i", made, off)[0])
                        tally["n"] += 1
                        tally["within 1"] += d <= 1
                        if name in (pur.CONTAINER_SCREEN, LAYOUT_SCREEN):
                            per_file[name, "n"] += 1
                            per_file[name, "within 1"] += d <= 1
                        if d > worst[0]:
                            worst = (d, f"{res} {name} @{off:#x}")
        within = tally["within 1"] / tally["n"]
        ok = within >= 0.995 and worst[0] <= 16
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} macOS sets derived from the others: {tally['n']} fields, "
              f"{100 * within:.2f}% within 1 px, worst {worst[0]} px ({worst[1]}); "
              + ", ".join(f"{name} {per_file[name, 'within 1']} of {per_file[name, 'n']}"
                          for name in (pur.CONTAINER_SCREEN, LAYOUT_SCREEN)))

        # 5. The Container at every derived size, as installed: the Give Items badge at its
        #    designed gap from the caption (build_prompt_tga), in the installed set's font.
        target = next(t for t in pur.PROMPT_TARGETS
                      if (t.gui, t.tag) == (pur.CONTAINER_SCREEN, pur.CONTAINER_FIT_TAG))
        closest, short = None, []
        for res in mac + UNLISTED:
            fonts = nearest(res)
            caption = caption_width((set_dir(fonts) / prompts.PROMPT_MANIFEST_NAME).read_bytes(), target.resref)
            button = next(c for c in pur.read_gff((tmp / f"{res}-{fonts}" / pur.CONTAINER_SCREEN).read_bytes())
                          .root.get_list("CONTROLS") if c.get_string("TAG") == pur.CONTAINER_FIT_TAG)
            width, height = (button.get_struct("EXTENT").get_int32(k) for k in ("WIDTH", "HEIGHT"))
            radius = prompts.badge_radius(height)
            badge_right = max(radius * prompts.BADGE_EDGE,
                              (width - caption) / 2 - radius * prompts.BADGE_GAP - radius) + radius
            gap = (width - caption) / 2 - badge_right
            designed = radius * prompts.BADGE_GAP
            if closest is None or gap - designed < closest[0] - closest[1]:
                closest = (gap, designed, res)
            if gap < designed - 0.01:
                short.append(f"{res} ({gap:.1f} of {designed:.1f} px)")
        ok = not short
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} Container's Give Items badge at its designed gap at "
              f"{len(mac) + len(UNLISTED)} derived sizes (tightest {closest[0]:.1f} px of "
              f"{closest[1]:.1f}, {closest[2]}){'; closer at ' + ', '.join(short) if short else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
