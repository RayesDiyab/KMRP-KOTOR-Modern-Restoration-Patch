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

Two layouts are not numbers to interpolate, and the table carries them as rules instead
(version 2, 2026-09-30), which kmrp-guiblend applies to the blend with the fonts of the set
it installs:
  * the Container is widened, in some sets and not others, until "Switch To Give Item" and
    its badge fit (prepare_universal_resources.py, fit_container_to_caption). A blend of
    widened and unwidened sets missed by up to 21 px, so the table holds the Container as
    it was before the widening -- each set's prompt manifest records by how much -- and a
    fit record;
  * the Controller Layout screen, kmrplayout.gui, is generated from its panel's size and the
    caption font (build_controller_layout.py, build_gui), and a blend missed it by up to
    62 px. The table carries that generator's constants by name, its rows, and where each
    control's extent sits, and the helper does build_gui's arithmetic, step for step.

Format (little-endian):
    "KGBL" u32 version=2
    u32 families; per family: f64 aspect
    u32 anchors;  per anchor: u32 width, u32 height, u32 family
    u32 fits;     per fit: u16 name length, name (the .gui), u16 length, resref (the
                  prompt manifest row whose baked width is the caption),
                  f64 radius below, f64 radius from, u32 height they switch at,
                  f64 gap, f64 edge (the badge's geometry, build_controller_prompt_textures),
                  u32 panel LEFT offset, u32 panel WIDTH offset, u32 button WIDTH offset,
                  u32 button HEIGHT offset, u32 n, n x u32 WIDTH offsets to widen
    u32 layouts;  per layout: u16 length, name (the .gui), u16 length, font (the TXI's
                  resref), u32 constants; per constant: u16 length, name, f64 value;
                  u32 rows; per row: u8 side ('L', 'R' or 'T'), f64 glyph x, f64 row y,
                  u16 length, caption; u32 root WIDTH offset, u32 root HEIGHT offset,
                  u32 controls; per control, in the file's order: u32 LEFT, TOP, WIDTH,
                  HEIGHT offsets
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
import build_controller_prompt_textures as prompts  # noqa: E402
import build_controller_layout as layout  # noqa: E402

LAYOUT_SCREEN = "kmrplayout.gui"

VERSION = 2
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


class Gff:
    """Just enough of GFF V3.2 to find a named field's inline data dword."""

    def __init__(self, data: bytes):
        self.data = data
        (self.structs, _, self.fields_at, _, self.labels, _, self.field_data, _,
         self.indices, _, self.lists, _) = struct.unpack_from("<12I", data, 8)

    def fields(self, index: int) -> dict[str, int]:
        """A struct's fields: label -> the field entry's offset."""
        _, first, count = struct.unpack_from("<III", self.data, self.structs + 12 * index)
        numbers = [first] if count == 1 else struct.unpack_from(f"<{count}I", self.data, self.indices + first)
        out = {}
        for number in numbers:
            entry = self.fields_at + 12 * number
            label = struct.unpack_from("<I", self.data, entry + 4)[0]
            name = self.data[self.labels + 16 * label:self.labels + 16 * label + 16].rstrip(b"\0")
            out[name.decode("ascii")] = entry
        return out

    def dword(self, entry: int) -> int:
        return struct.unpack_from("<I", self.data, entry + 8)[0]

    def string(self, entry: int) -> str:
        at = self.field_data + self.dword(entry)
        return self.data[at + 4:at + 4 + struct.unpack_from("<I", self.data, at)[0]].decode("latin-1")

    def list(self, entry: int) -> tuple[int, ...]:
        at = self.lists + self.dword(entry)
        return struct.unpack_from(f"<{struct.unpack_from('<I', self.data, at)[0]}I", self.data, at + 4)


def container_fit(template: bytes) -> dict:
    """The data-dword offsets fit_container_to_caption changes, in this file's layout."""
    gff = Gff(template)
    root = gff.fields(0)
    panel = gff.fields(gff.dword(root["EXTENT"]))
    fit = {"left": panel["LEFT"] + 8, "width": panel["WIDTH"] + 8, "widths": []}
    for index in gff.list(root["CONTROLS"]):
        control = gff.fields(index)
        tag = gff.string(control["TAG"])
        if tag not in pur.CONTAINER_WIDENED:
            continue
        extent = gff.fields(gff.dword(control["EXTENT"]))
        fit["widths"].append(extent["WIDTH"] + 8)
        if tag == pur.CONTAINER_FIT_TAG:
            fit["button_width"], fit["button_height"] = extent["WIDTH"] + 8, extent["HEIGHT"] + 8
    if len(fit["widths"]) != len(pur.CONTAINER_WIDENED) or "button_width" not in fit:
        raise SystemExit(f"{pur.CONTAINER_SCREEN}: not every widened control was found")
    return fit


def extent_offsets(template: bytes) -> tuple[tuple[int, int], list[tuple[int, int, int, int]]]:
    """The root's WIDTH and HEIGHT data dwords, and each control's LEFT, TOP, WIDTH and
    HEIGHT, in the order the file lists its controls."""
    gff = Gff(template)
    root = gff.fields(0)
    panel = gff.fields(gff.dword(root["EXTENT"]))
    controls = []
    for index in gff.list(root["CONTROLS"]):
        extent = gff.fields(gff.dword(gff.fields(index)["EXTENT"]))
        controls.append(tuple(extent[k] + 8 for k in ("LEFT", "TOP", "WIDTH", "HEIGHT")))
    return (panel["WIDTH"] + 8, panel["HEIGHT"] + 8), controls


def text(value: str) -> bytes:
    encoded = value.encode("ascii")
    return struct.pack("<H", len(encoded)) + encoded


def widened_by(archive: zipfile.ZipFile, gui: str) -> int:
    """What the build widened `gui` by in this set, from its prompt manifest."""
    for line in archive.read(prompts.PROMPT_MANIFEST_NAME).decode("utf-8").splitlines():
        parts = line.split()
        if parts[:2] == ["widened", gui]:
            return int(parts[2])
    raise SystemExit(f"{archive.filename}: the prompt manifest does not say whether {gui} was widened")


def unfit(blob: bytes, fit: dict, pixels: int) -> bytes:
    """`blob` as it was before fit_container_to_caption widened it by `pixels`."""
    data = bytearray(blob)
    def add(offset, delta):
        struct.pack_into("<i", data, offset, struct.unpack_from("<i", data, offset)[0] + delta)
    add(fit["left"], pixels // 2)
    add(fit["width"], -pixels)
    for offset in fit["widths"]:
        add(offset, -pixels)
    return bytes(data)


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

    # The one fit: the Container, whose caption is the Give Items prompt's baked width.
    fit = container_fit(archives[0].read(pur.CONTAINER_SCREEN))
    caption_row = next(t.resref for t in prompts.PROMPT_TARGETS
                       if (t.gui, t.tag) == (pur.CONTAINER_SCREEN, pur.CONTAINER_FIT_TAG))
    out += struct.pack("<I", 1) + text(pur.CONTAINER_SCREEN) + text(caption_row)
    out += struct.pack("<ddIdd", prompts.BADGE_RADIUS_SHORT, prompts.BADGE_RADIUS,
                       prompts.BADGE_SHORT_BELOW, prompts.BADGE_GAP, prompts.BADGE_EDGE)
    out += struct.pack("<IIIII", fit["left"], fit["width"], fit["button_width"],
                       fit["button_height"], len(fit["widths"]))
    out += struct.pack(f"<{len(fit['widths'])}I", *fit["widths"])

    # The one generated layout: the Controller Layout screen.
    root, controls = extent_offsets(archives[0].read(LAYOUT_SCREEN))
    constants = layout.layout_constants()
    expected = 10 + 2 * int(constants["ROWS"]) + int(constants["DECOR_COUNT"]) + 1
    if len(controls) != expected:
        raise SystemExit(f"{LAYOUT_SCREEN}: {len(controls)} controls, build_gui makes {expected}")
    out += struct.pack("<I", 1) + text(LAYOUT_SCREEN) + text(layout.CAPTION_FONT)
    out += struct.pack("<I", len(constants))
    for name, value in constants.items():
        out += text(name) + struct.pack("<d", value)
    rows = layout.layout_rows()
    out += struct.pack("<I", len(rows))
    for side, glyph_x, row_y, caption in rows:
        out += struct.pack("<Bdd", ord(side), glyph_x, row_y) + text(caption)
    out += struct.pack("<III", root[0], root[1], len(controls))
    for offsets in controls:
        out += struct.pack("<4I", *offsets)
    out += struct.pack("<I", len(names))

    total_slots = 0
    for name in names:
        blobs = [z.read(name) for z in archives]
        if name == pur.CONTAINER_SCREEN:
            blobs = [unfit(b, fit, widened_by(z, name)) for b, z in zip(blobs, archives)]
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
