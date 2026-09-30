#!/usr/bin/env python3
"""Pack the finished GUI sets into a table the installers blend any resolution from.

KMRP's installers install the built `gui-<W>x<H>.zip` for a listed resolution. For a
size the build has no set for, they derive one -- the Mac's with macos/tools/kmrp-guiblend.c,
Windows' with src/patcher/GuiBlend.cs, which match byte for byte -- by blending the
finished sets around it, the same weighted blend
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

Version 3 on master (2026-09-30) made the controller badges for the size as well. Each badge
is a 512x64 texture the engine stretches over its whole button, drawn so that it comes out round
on that button (build_controller_prompt_textures.py, build_prompt_tga). Taken from the
nearest set, a badge was drawn for that set's button, and a blended button of another shape
stretched it: 1.86 times as wide as tall at 3440x1400, whose nearest set by height is
1856x1392 (measured on the blended files). So the table carries what build_prompt_tga needs
-- its constants, the glyph artwork as it loads it (cropped, RGBA), and per badge (per row of
the prompt manifest) the button's extent in its .gui, the glyph, the backing and the
controls whose least height sizes it -- and the installers draw each badge again for the
blended button, with the same arithmetic as Pillow's (Lanczos resample on premultiplied
alpha, fixed-point with 22 bits; the masked paste; alpha_composite), so a set rebuilt from
the table reproduces the build's badges byte for byte (testing/regression/Test-GuiBlendHelper.py).
The same holds for lbl_mileftbot.tga, the HUD's button-row boxes, which the build draws per
set from that set's mipc28x6.gui (build_menubg_texture.py) and which the nearest set's would
draw out of step with the blended buttons: the table carries where LBL_MENUBG and the eight
buttons sit, and the installers draw it from the blended HUD.

Version 3 on the macos branch (2026-09-30) added a third made file: the lists made as tall
as whole rows (scale_listbox_padding.py, fit_list_to_rows: the Container, the granted popup,
the character-generation Feats list and a few full-screen lists at low resolutions). How much
each list changes jumps with the row count, so a blend of fitted sets missed the Mac sets by
up to 41 px (Feats) and put 76 of the Container's 493 fields more than a pixel off. The
table holds each list as it was before the fit -- the manifest's "fitted" lines say by how
much -- and a record of what the rule reads and writes; the helper fits the blend.

Version 4 (2026-09-30, the merge of the two branches the same day) carries both, the
row fits first: the two version 3 tables were different formats with one number, so
the helpers refuse both.

Format (little-endian):
    "KGBL" u32 version=4
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
    u32 row fits; per list: u16 length, name (the .gui), u16 length, tag, u8 popup,
                  f64 loose gap (a full-screen list's largest gap, as a share of a row),
                  u32 gap divisor (the gap is row // divisor), u32 n, n x u32 row bases
                  (row = base x s), u32 list HEIGHT offset, u32 border DIMENSION offset,
                  u32 scrollbar HEIGHT offset (0: none), u32 panel TOP offset, u32 panel
                  HEIGHT offset (both 0 for a full-screen list), u32 n, n x u32 TOP offsets
                  of the controls below the list
    badges:       u32 texture width, u32 texture height, f64 radius, f64 radius below,
                  u32 height they switch at, f64 gap, f64 edge, f64 centre y, f64 centre x
                  without a label (build_controller_prompt_textures.py's BADGE_*),
                  u16 length, the TGA footer;
                  u32 glyphs; per glyph: u32 width, u32 height, width x height x 4 bytes
                  RGBA, top row first (_load_glyph_art's image);
                  u32 prompts; per prompt: u16 length, resref (its manifest row), u16
                  length, the .gui, u32 its control's WIDTH offset, u32 HEIGHT offset,
                  u32 glyph, u8 1 when it stands on a backing and the backing's RGBA
                  (4 bytes, zero without one), u32 n, n x u32 HEIGHT offsets in the same
                  .gui whose least sizes the badge (none: its own height)
    u32 huds;     per HUD texture (one): u16 length, the .gui, u16 length, the texture,
                  u32 width, u32 height, u32 edge alpha (build_menubg_texture.py), u32
                  LBL_MENUBG's LEFT offset, u32 its WIDTH offset, u32 n, n x (u32 LEFT,
                  u32 WIDTH offsets) of the buttons, in the file's order
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
import build_menubg_texture as menubg  # noqa: E402
from fix_hud_menubg import BUTTON_TAGS  # noqa: E402
import scale_listbox_padding as slp  # noqa: E402

LAYOUT_SCREEN = "kmrplayout.gui"
# The HUD every size but 3440x1440 loads, whose buttons lbl_mileftbot.tga's boxes follow
# (prepare_universal_resources.py); a blended size is never 3440x1440.
HUD_SCREEN = "mipc28x6.gui"

VERSION = 4
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


def badge_section(templates: dict[str, bytes], manifest: bytes) -> bytes:
    """The badges' constants, artwork and recipes, one recipe per prompt manifest row, as
    build_prompt_textures makes that row's texture."""
    out = struct.pack("<II", prompts.TEXTURE_WIDTH, prompts.TEXTURE_HEIGHT)
    out += struct.pack("<dd", prompts.BADGE_RADIUS, prompts.BADGE_RADIUS_SHORT)
    out += struct.pack("<I", prompts.BADGE_SHORT_BELOW)
    out += struct.pack("<dddd", prompts.BADGE_GAP, prompts.BADGE_EDGE, prompts.BADGE_CENTER_Y,
                       prompts.BADGE_FALLBACK_X)
    out += struct.pack("<H", len(prompts.TGA_FOOTER)) + prompts.TGA_FOOTER

    glyphs = []                                       # (family, glyph), in table order
    for family in prompts.GLYPH_FAMILIES:
        for glyph in sorted({t.glyph for t in prompts.PROMPT_TARGETS}):
            glyphs.append((family, glyph))
    out += struct.pack("<I", len(glyphs))
    for family, glyph in glyphs:
        art = prompts._load_glyph_art(glyph, family)
        if art is None:
            raise SystemExit(f"no {family} artwork for {glyph}: the installers cannot draw its badges")
        out += struct.pack("<II", art.width, art.height) + art.convert("RGBA").tobytes()

    offsets = {gui: extent_offsets(data)[1] for gui, data in templates.items()}

    def control(gui: str, index: int, tag: str) -> tuple[int, int, int, int]:
        gff = Gff(templates[gui])
        entries = gff.list(gff.fields(0)["CONTROLS"])
        actual = gff.string(gff.fields(entries[index])["TAG"])
        if actual != tag:
            raise SystemExit(f"{gui}[{index}] is {actual}, the badge expects {tag}")
        return offsets[gui][index]

    def index_of(gui: str, tag: str) -> int:
        gff = Gff(templates[gui])
        entries = gff.list(gff.fields(0)["CONTROLS"])
        return next(i for i, e in enumerate(entries) if gff.string(gff.fields(e)["TAG"]) == tag)

    by_resref = {t.resref: t for t in prompts.PROMPT_TARGETS}
    rows = [line.split()[1] for line in manifest.decode("utf-8").splitlines() if line.startswith("prompt ")]
    records = []
    for resref in rows:
        xbox = "kmrp" + resref[4:]
        target, variant = by_resref.get(xbox), False
        if target is None:
            # One texture per caption (PER_CAPTION_TARGETS): the resref and an index.
            base = xbox.rstrip("0123456789")
            target, variant = by_resref.get(base), True
            if target is None or (target.gui, target.tag) not in prompts.PER_CAPTION_TARGETS:
                raise SystemExit(f"the prompt manifest's {resref} is no badge the build makes")
        family = next(f for f, letter in prompts.FAMILY_LETTERS.items() if letter == resref[3])
        extent = control(target.gui, target.control_index, target.tag)
        sizing = []
        backing = None
        if not variant:
            group = prompts.BADGE_GROUPS.get((target.gui, target.tag))
            if group is not None:
                for member in prompts.PROMPT_TARGETS:
                    if prompts.BADGE_GROUPS.get((member.gui, member.tag)) == group:
                        if member.gui != target.gui:
                            raise SystemExit(f"badge group {group} spans two screens")
                        sizing.append(control(member.gui, member.control_index, member.tag)[3])
            elif target.size_like:
                sizing.append(offsets[target.gui][index_of(target.gui, target.size_like)][3])
            if target.backing:
                backing = prompts.BACKINGS[target.backing]
        record = text(resref) + text(target.gui)
        record += struct.pack("<III", extent[2], extent[3], glyphs.index((family, target.glyph)))
        record += struct.pack("<B4B", 1 if backing else 0, *(backing or (0, 0, 0, 0)))
        record += struct.pack("<I", len(sizing)) + struct.pack(f"<{len(sizing)}I", *sizing)
        records.append(record)
    return out + struct.pack("<I", len(records)) + b"".join(records)


def hud_section(templates: dict[str, bytes]) -> bytes:
    """Where build_menubg_texture.geometry_from_gui reads LBL_MENUBG and the eight buttons."""
    gff = Gff(templates[HUD_SCREEN])
    backdrop, buttons = None, []
    for index in gff.list(gff.fields(0)["CONTROLS"]):
        control = gff.fields(index)
        tag = gff.string(control["TAG"])
        extent = gff.fields(gff.dword(control["EXTENT"]))
        if tag in BUTTON_TAGS:
            buttons.append((extent["LEFT"] + 8, extent["WIDTH"] + 8))
        elif tag == "LBL_MENUBG":
            backdrop = (extent["LEFT"] + 8, extent["WIDTH"] + 8)
    if backdrop is None or len(buttons) != len(BUTTON_TAGS):
        raise SystemExit(f"{HUD_SCREEN}: LBL_MENUBG and the {len(BUTTON_TAGS)} buttons were not found")
    if menubg.TGA_FOOTER != prompts.TGA_FOOTER:
        raise SystemExit("build_menubg_texture.py and build_controller_prompt_textures.py end their TGAs "
                         "differently; the table carries one footer")
    out = struct.pack("<I", 1) + text(HUD_SCREEN) + text(pur.MENUBG_TEXTURE_NAME)
    out += struct.pack("<III", *menubg.TEXTURE_SIZE, menubg.EDGE_ALPHA)
    out += struct.pack("<II", *backdrop) + struct.pack("<I", len(buttons))
    for button in buttons:
        out += struct.pack("<II", *button)
    return out


def row_fit(template: bytes, tag: str, popup: bool) -> dict:
    """The data-dword offsets scale_listbox_padding.fit_list_to_rows reads and changes for
    list `tag`, in this file's layout: the list's HEIGHT and its border's DIMENSION, the
    scrollbar's HEIGHT, and, in a popup, the panel's TOP and HEIGHT and the TOP of every
    control below the list (the fit moves those with the list's bottom, so they stay below)."""
    gff = Gff(template)
    root = gff.fields(0)
    panel = gff.fields(gff.dword(root["EXTENT"]))
    target, others = None, []
    for index in gff.list(root["CONTROLS"]):
        control = gff.fields(index)
        extent = gff.fields(gff.dword(control["EXTENT"]))
        if gff.string(control["TAG"]).upper() == tag.upper():
            target = (control, extent)
        else:
            others.append(extent)
    if target is None:
        raise SystemExit(f"no {tag} to fit")
    control, extent = target
    fit = {"height": extent["HEIGHT"] + 8,
           "dimension": gff.fields(gff.dword(control["BORDER"]))["DIMENSION"] + 8,
           "bar": 0, "panel_top": 0, "panel_height": 0, "below": []}
    if "SCROLLBAR" in control:
        bar = gff.fields(gff.dword(control["SCROLLBAR"]))
        fit["bar"] = gff.fields(gff.dword(bar["EXTENT"]))["HEIGHT"] + 8
    if popup:
        bottom = gff.dword(extent["TOP"]) + gff.dword(extent["HEIGHT"])
        fit["panel_top"], fit["panel_height"] = panel["TOP"] + 8, panel["HEIGHT"] + 8
        fit["below"] = [e["TOP"] + 8 for e in others if gff.dword(e["TOP"]) >= bottom]
    return fit


def fitted_by(archive: zipfile.ZipFile, gui: str, tag: str) -> int:
    """What the build changed list `tag` of `gui` by in this set, from its prompt manifest."""
    for line in archive.read(prompts.PROMPT_MANIFEST_NAME).decode("utf-8").splitlines():
        parts = line.split()
        if parts[:3] == ["fitted", gui, tag]:
            return int(parts[3])
    raise SystemExit(f"{archive.filename}: the prompt manifest does not say whether {gui} {tag} was fitted")


def unfit_rows(blob: bytes, fit: dict, change: int) -> bytes:
    """`blob` as it was before fit_list_to_rows changed its list's height by `change`."""
    data = bytearray(blob)
    def add(offset, delta):
        if offset:
            struct.pack_into("<i", data, offset, struct.unpack_from("<i", data, offset)[0] + delta)
    add(fit["height"], -change)
    add(fit["bar"], -change)
    for offset in fit["below"]:
        add(offset, -change)
    add(fit["panel_top"], change // 2)
    add(fit["panel_height"], -change)
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

    # The lists made as tall as whole rows (scale_listbox_padding.ROW_LISTS): held as they
    # were before, from each set's manifest, with what the rule reads and writes, so the
    # installer fits the blend itself. The controls below a popup's list must be the same
    # in every set: the record names them once.
    row_fits = {}
    for (gui, tag), (kind, bases) in slp.ROW_LISTS.items():
        rows = row_fit(archives[0].read(gui), tag, kind == "popup")
        for z in archives[1:]:
            if row_fit(z.read(gui), tag, kind == "popup") != rows:
                raise SystemExit(f"{z.filename}: {gui} {tag} is not laid out as in the first set")
        row_fits[gui, tag] = rows
    out += struct.pack("<I", len(row_fits))
    for (gui, tag), rows in row_fits.items():
        kind, bases = slp.ROW_LISTS[gui, tag]
        out += text(gui) + text(tag)
        out += struct.pack("<BdI", kind == "popup", slp.LOOSE_GAP, slp.ROW_GAP_DIVISOR)
        out += struct.pack(f"<I{len(bases)}I", len(bases), *bases)
        out += struct.pack("<6I", rows["height"], rows["dimension"], rows["bar"], rows["panel_top"],
                           rows["panel_height"], len(rows["below"]))
        out += struct.pack(f"<{len(rows['below'])}I", *rows["below"])

    # The badges. Every set's manifest lists the same rows (checked), and the templates
    # are the files' own layout, the same at every resolution (checked below).
    templates = {name: archives[0].read(name) for name in names}
    templates[pur.CONTAINER_SCREEN] = unfit(templates[pur.CONTAINER_SCREEN], fit,
                                            widened_by(archives[0], pur.CONTAINER_SCREEN))
    manifest = archives[0].read(prompts.PROMPT_MANIFEST_NAME)
    row_names = lambda data: [l.split()[1] for l in data.decode("utf-8").splitlines() if l.startswith("prompt ")]
    for archive in archives[1:]:
        if row_names(archive.read(prompts.PROMPT_MANIFEST_NAME)) != row_names(manifest):
            raise SystemExit(f"{archive.filename}: its prompt manifest lists other badges")
    out += badge_section(templates, manifest)
    out += hud_section(templates)
    out += struct.pack("<I", len(names))

    total_slots = 0
    for name in names:
        blobs = [z.read(name) for z in archives]
        for (gui, tag), rows in row_fits.items():
            if gui == name:
                blobs = [unfit_rows(b, rows, fitted_by(z, gui, tag)) for b, z in zip(blobs, archives)]
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
