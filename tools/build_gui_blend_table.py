#!/usr/bin/env python3
"""Pack the finished GUI sets into a table the Mac installer blends any resolution from.

KMRP for macOS installs the built `gui-<W>x<H>.zip` for a listed resolution. For a
display the build has no set for, the installer derives one (macos/tools/kmrp-guiblend.c)
by blending the finished sets around it, the same weighted blend
tools/derive_resolution_gui_set.py uses on upstream: the two aspect-ratio families on
either side, each at the two heights around the target, rounded once. KMRP's layout logic
stays in one place, the build; the installer only interpolates numbers the build made.

That is possible because a finished .gui has the same bytes at every resolution except
the numeric fields held inline in its GFF field entries (checked here for every file and
every anchor: anything else differing stops the build). The table keeps, per file, one
template, the offsets and types of the fields that vary, and each anchor's values.

Anchors are the finished sets of the resolutions High Resolution Menus lays out by hand,
by family. Left out: 3440x1440 (KMRP's hand-tuned gold layout, not on the families'
lines), every derived set (2880x1620 and the macOS group: blends themselves), and sets more
than 2% off their family's aspect ratio (the 21-by-9 folder's 1280x1080).

Accuracy, measured by hiding each finished set with neighbours and predicting it from the
others (2026-09-29): 2,037,074 numeric fields, 97.27% exact, 99.89% within 1 px; see
macos/WINDOWS-PARITY.md, "Resolutions the build has no set for".

Format (little-endian):
    "KGBL" u32 version=1
    u32 families; per family: f64 aspect
    u32 anchors;  per anchor: u32 width, u32 height, u32 family
    u32 files;    per file: u16 name length, name bytes, u32 template size, template,
                  u32 slots; per slot: u32 offset, u32 type (GFF field type);
                  then anchors x slots u32 values (the raw field data dwords)

    python tools/build_gui_blend_table.py RESOURCES_DIR OUTPUT_FILE
"""
from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_universal_resources as pur  # noqa: E402

VERSION = 1
# Field types whose value sits inline in the entry's data dword (GFF V3.2).
INLINE_TYPES = {0: "BYTE", 1: "CHAR", 2: "WORD", 3: "SHORT", 4: "DWORD", 5: "INT", 8: "FLOAT"}
FAMILY_ORDER = ["4:3", "16:10", "16:9", "21:9", "32:9"]
EXCLUDED = {"3440x1440"}


def anchors_by_family(resources: Path) -> tuple[list[float], list[tuple[int, int, int]]]:
    derived = set(pur.DERIVED_GUI_SETS) | set(pur.GROUPS.get("macOS", []))
    families, anchors = [], []
    for index, family in enumerate(FAMILY_ORDER):
        sizes = [tuple(int(v) for v in r.split("x")) for r in pur.GROUPS[family]
                 if r not in EXCLUDED and r not in derived
                 and (resources / f"gui-{r}.zip").is_file()]
        ratios = sorted(w / h for w, h in sizes)
        aspect = ratios[len(ratios) // 2]
        families.append(aspect)
        anchors += [(w, h, index) for w, h in sizes if abs(w / h / aspect - 1) <= 0.02]
    return families, anchors


def field_slots(data: bytes) -> dict[int, int]:
    """Offset of every inline data dword -> its GFF field type."""
    (_, _, _, _, field_offset, field_count) = struct.unpack_from("<4s4sIIII", data, 0)
    slots = {}
    for i in range(field_count):
        entry = field_offset + 12 * i
        ftype = struct.unpack_from("<I", data, entry)[0]
        if ftype in INLINE_TYPES:
            slots[entry + 8] = ftype
    return slots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    families, anchors = anchors_by_family(args.resources)
    archives = [zipfile.ZipFile(args.resources / f"gui-{w}x{h}.zip") for w, h, _ in anchors]
    names = sorted(n for n in archives[0].namelist() if n.lower().endswith(".gui"))

    out = bytearray(b"KGBL" + struct.pack("<I", VERSION))
    out += struct.pack("<I", len(families))
    for aspect in families:
        out += struct.pack("<d", aspect)
    out += struct.pack("<I", len(anchors))
    for w, h, fam in anchors:
        out += struct.pack("<III", w, h, fam)
    out += struct.pack("<I", len(names))

    total_slots = 0
    for name in names:
        blobs = [z.read(name) for z in archives]
        template = blobs[0]
        if any(len(b) != len(template) for b in blobs):
            raise SystemExit(f"{name}: byte length differs between resolutions")
        inline = field_slots(template)
        # Every differing byte must lie inside an inline field's data dword.
        differing = {i for b in blobs[1:] for i in range(len(template)) if b[i] != template[i]}
        slot_of = {}
        for off in inline:
            for i in range(off, off + 4):
                slot_of[i] = off
        stray = sorted(i for i in differing if i not in slot_of)
        if stray:
            raise SystemExit(f"{name}: bytes outside numeric fields differ, first at {stray[0]:#x}")
        varying = sorted({slot_of[i] for i in differing})
        total_slots += len(varying)

        encoded = name.encode("ascii")
        out += struct.pack("<H", len(encoded)) + encoded
        out += struct.pack("<I", len(template)) + template
        out += struct.pack("<I", len(varying))
        for off in varying:
            out += struct.pack("<II", off, inline[off])
        for blob in blobs:
            for off in varying:
                out += blob[off:off + 4]

    args.output.write_bytes(bytes(out))
    print(f"{len(names)} GUI files, {len(anchors)} anchors in {len(families)} families, "
          f"{total_slots} varying fields, {len(out) / 1024 / 1024:.1f} MB -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
