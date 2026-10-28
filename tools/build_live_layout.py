#!/usr/bin/env python3
"""Live Adaptive Layout: lay a screen's .gui out for any screen size at run time.

    python tools/build_live_layout.py            write macos/tools/kmrp-livelayout-table.h
    python tools/build_live_layout.py --check    stop if that file is not what this makes

KMRP's per-size layouts are High Resolution Menus' hand-made sets with KMRP's
corrections on top, made at build time. A GUI mod's file in Override takes the place of
KMRP's whole file, laid out for 640x480, so the screen is drawn small in a corner. Live
Adaptive Layout (the maintainer's name, 2026-10-27) lays out whichever file the game would
load, the game's own or a mod's, for the size in use, at run time: KmrpLiveLayout in
macos/tools/kmrp-guiadapt.c, shared by the Windows module and the Mac. This script makes the
table it reads and holds the same layout in Python (`layout`), which
testing/regression/Test-LiveLayout.py compares with the build's sets and with the C.

The rules (measured 2026-10-28; docs/live-adaptive-layout.md has the figures)
---------------------------------------------------------------------------
Upstream lays each size out by hand, but every control follows one of a few rules applied
to its value in the game's own file, with s = H / BH (BW x BH: the file's own size, which
is its root panel's when that fills the screen from 0,0, else 640x480; mainmenu10x7.gui,
for one, is an 800x600 layout):

    scale    v * s                                 tops and heights; most squares' widths
    stretch  v * W / BW                            lefts and widths of most controls
    aspect   (v + w/2) * W / BW - w * s / 2        a square's left: it keeps its shape and is
                                                   centred where the stretched one would be
    fixed    v                                     list row prototypes (PROTOITEM)
    centre   W/2 + (v - BW/2) * s,  right  W - (BW - v) * s

One rule per field reproduces 92.1% of the fields of upstream's 48 sets exactly in every
set and 99.0% of the values. KMRP's own changes are, per field, the gold 3440x1440 file's
value against the rule's there, and the build carries them to every size as a ratio
(tools/transfer_gold_gui_geometry.py); so does this. Rule and gold together give 95.1% of
the values of KMRP's 66 sets exactly and 99.1% within a pixel, over the screens that are
not the HUD or made by a step of their own; the gold set itself comes out as it is. The
pixel is rounding, accepted by the maintainer on 2026-10-28 for every size but gold.

The table
---------
Per file this moves, per structure of the game's file that has an EXTENT (the root, each
control by TAG, and a list's PROTOITEM and SCROLLBAR): each field's rule, chosen on
upstream's sets (the default where it fits as well), and the gold file's value. The C
applies a structure's gold values only while the file it lays out has the game's own
extent there: a control a mod moved keeps the mod's place, laid out by its rule alone. A
control the table does not know (a mod's own) gets the default rule:

    a list row prototype is fixed; tops and heights scale;
    a square control (width / height 0.8 to 1.25) that is not a list box keeps its shape;
    everything else stretches.

With it go the list gutters (PADDING) the build sets (prepare_universal_resources.py:
DESCRIPTION_LISTBOXES, LIST_LISTBOXES, HAND_TUNED_GUTTERS), at the build's font scale, and
a PADDING the gold file sets by hand, which the build ships at 3440x1440 only, so this does.

The table holds rule numbers and the gold file's values, which are in this repository;
nothing of the game's. The game's own files are read at run time from chitin.key, and here
from build-inputs/vanilla-gui.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from pykotor.resource.formats.gff import GFFList, GFFStruct, read_gff

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from prepare_universal_resources import (DESCRIPTION_LISTBOXES, FONT_HEIGHT_DIVISOR,  # noqa: E402
                                         FONT_SCALE_OFFSET, HAND_TUNED_GUTTERS, LIST_LISTBOXES)
from scale_listbox_padding import GUTTER_AT_UNIT_SCALE, LIST_GUTTER_AT_UNIT_SCALE  # noqa: E402

VANILLA = ROOT / "build-inputs" / "vanilla-gui"
UPSTREAM = ROOT / "third_party" / "Included" / "kotor-high-resolution-menus-1.5"
GOLD = ROOT / "assets" / "override-3440x1440"
TABLE = ROOT / "macos" / "tools" / "kmrp-livelayout-table.h"
GOLD_SIZE = (3440, 1440)

# The screens laid out at run time. The options screens first (2026-10-28): rules and
# gold alone make them, with nothing of KMRP's own added. optgameplay.gui (the Controller
# Layout entry) and optfeedback.gui (its row template) are made by build steps of their
# own and stay with the sets for now.
FILES = (
    "optionsmain.gui", "optionsingame.gui", "optautopause.gui", "optgraphics.gui",
    "optgraphicsadv.gui", "optmouse.gui", "optsound.gui", "optsoundadv.gui",
    "optkeymapping.gui", "optkeyentry.gui", "optresolution.gui",
)

FIELDS = ("LEFT", "TOP", "WIDTH", "HEIGHT")
# Rule numbers, as kmrp-guiadapt.c has them.
RULES = ("scale", "stretch", "fixed", "aspect", "centre", "right")
LISTBOX = 11
SUBS = ("PROTOITEM", "SCROLLBAR")
# Upstream sets more than 2% off their family's shape are no family's (the 21-by-9
# folder's 1280x1080).
OFF_FAMILY = {(1280, 1080)}


def rhalf(x: float) -> int:
    """Round half away from zero, as the C's lround."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def font_scale(height: int) -> float:
    return max(1.0, height / FONT_HEIGHT_DIVISOR - FONT_SCALE_OFFSET)


def gutter(unit: float, height: int) -> int:
    # Python's round, half to even, as scale_listbox_padding.py has it (the C: nearbyint).
    return int(round(unit * font_scale(height)))


def child(struct: GFFStruct, label: str) -> GFFStruct | None:
    """A structure-valued field itself (pykotor's get_struct returns a copy)."""
    return struct.acquire(label, None, GFFStruct)


def extent(struct: GFFStruct) -> list[int] | None:
    e = child(struct, "EXTENT")
    if e is None:
        return None
    return [e.get_int32(f) for f in FIELDS]


def base_of(root: GFFStruct) -> tuple[int, int]:
    e = extent(root)
    if e and e[0] == 0 and e[1] == 0 and e[2] >= 640 and e[3] >= 480:
        return e[2], e[3]
    return 640, 480


def structures(root: GFFStruct):
    """(key, structure, CONTROLTYPE) of every structure with an EXTENT: the root as ("", ""),
    a control as (TAG, ""), its prototype and scroll bar as (TAG, "PROTOITEM"/"SCROLLBAR")."""
    yield ("", ""), root, -1
    if not root.exists("CONTROLS"):
        return
    for index, control in enumerate(root.acquire("CONTROLS", None, GFFList)):
        # An untagged control by its place, never the root's key.
        tag = (control.get_string("TAG") if control.exists("TAG") else "") or f"#{index}"
        ctype = control.get_int32("CONTROLTYPE") if control.exists("CONTROLTYPE") else -1
        if extent(control) is not None:
            yield (tag, ""), control, ctype
        for sub in SUBS:
            inner = child(control, sub)
            if inner is not None and extent(inner) is not None:
                yield (tag, sub), inner, ctype


def value(rule: str, field: int, v: int, w: int, width: int, height: int, base: tuple[int, int]) -> float:
    """A rule's unrounded value for field `field` (0..3) of `v`, `w` the structure's width."""
    bw, bh = base
    s = height / bh
    if rule == "scale":
        return v * s
    if rule == "fixed":
        return float(v)
    if rule == "stretch":
        return v * width / bw
    if rule == "aspect":
        return (v + w / 2) * width / bw - w * s / 2 if field == 0 else v * s
    if rule == "centre":
        return width / 2 + (v - bw / 2) * s if field == 0 else v * s
    if rule == "right":
        return width - (bw - v) * s if field == 0 else v * s
    raise ValueError(rule)


def default_rule(field: int, sub: str, ctype: int, e: list[int]) -> str:
    if sub == "PROTOITEM":
        return "fixed"
    if field in (1, 3):
        return "scale"
    w, h = e[2], e[3]
    if not sub and ctype != LISTBOX and ctype != -1 and h > 0 and 0.8 <= w / h <= 1.25:
        return "aspect" if field == 0 else "scale"
    return "stretch"


def placed(field: int, rule: str, v4: list[int], gold: int | None, width: int, height: int,
           base: tuple[int, int]) -> int:
    """A field on the screen: its rule, carried by gold's ratio where gold differs from it."""
    r = value(rule, field, v4[field], v4[2], width, height, base)
    if gold is None:
        return rhalf(r)
    at_gold = value(rule, field, v4[field], v4[2], *GOLD_SIZE, base)
    if gold == rhalf(at_gold):
        return rhalf(r)
    if at_gold == 0:
        return rhalf(r + gold)
    return rhalf(gold * (r / at_gold))


# ----------------------------------------------------------------------------- the table
def upstream_sets() -> list[tuple[tuple[int, int], Path]]:
    sets = []
    for family in sorted(p for p in UPSTREAM.iterdir() if p.is_dir()):
        for folder in sorted(family.glob("gui.*x*")):
            w, h = (int(x) for x in folder.name[4:].split("x"))
            if (w, h) not in OFF_FAMILY:
                sets.append(((w, h), folder))
    return sets


def choose_rules(name: str, sets) -> dict:
    """Per structure key of the game's file: its four rules, chosen on upstream's sets."""
    vanilla = read_gff(VANILLA / name).root
    base = base_of(vanilla)
    seen = {}
    for (w, h), folder in sets:
        for key, struct, _ in structures(read_gff(folder / name).root):
            seen.setdefault(key, []).append(((w, h), extent(struct)))
    chosen = {}
    for key, struct, ctype in structures(vanilla):
        if key in chosen:
            raise ValueError(f"{name}: two structures are {key}; the table keys by TAG")
        v4 = extent(struct)
        rules = []
        for field in range(4):
            default = default_rule(field, key[1], ctype, v4)
            candidates = ("scale", "fixed") if field in (1, 3) else RULES

            def hits(rule):
                return sum(abs(e[field] - value(rule, field, v4[field], v4[2], w, h, base)) <= 1.5
                           for (w, h), e in seen.get(key, ()))
            best = max(candidates, key=lambda r: (hits(r), r == default))
            rules.append(best)
        chosen[key] = rules
    return chosen


def table_entries() -> list[tuple[str, list]]:
    sets = upstream_sets()
    files = []
    for name in FILES:
        rules = choose_rules(name, sets)
        vanilla = read_gff(VANILLA / name).root
        gold_root = read_gff(GOLD / name).root
        gold = {key: (extent(s), s) for key, s, _ in structures(gold_root)}
        rows = []
        for key, struct, ctype in structures(vanilla):
            g, gs = gold.get(key, (None, None))
            vpad = struct.get_int32("PADDING") if struct.exists("PADDING") else None
            gpad = gs.get_int32("PADDING") if gs is not None and gs.exists("PADDING") else None
            rows.append((key, rules[key], g, gpad if gpad is not None and gpad != vpad else None))
        files.append((name, rows))
    return files


def c_string(text: str) -> str:
    if any(c in text for c in '"\\') or not text.isascii():
        raise ValueError(f"a TAG this table cannot hold: {text!r}")
    return f'"{text}"'


def render() -> str:
    lines = [
        "/* Generated by tools/build_live_layout.py from the gold 3440x1440 layout and High",
        " * Resolution Menus' sets; do not edit. testing/regression/Test-LiveLayout.py fails",
        " * when this is not what the script makes. Read by kmrp-guiadapt.c. */",
        "#ifndef KMRP_LIVELAYOUT_TABLE_H",
        "#define KMRP_LIVELAYOUT_TABLE_H",
        "",
        "/* Rules: " + ", ".join(f"{i} {r}" for i, r in enumerate(RULES)) + ". NO_GOLD: the gold",
        " * file has no such structure. NO_PADDING: the gold file sets no PADDING of its own. */",
        "#define LL_NO_GOLD (-2147483647 - 1)",
        "#define LL_NO_PADDING (-1)",
        "",
        "typedef struct { const char *tag, *sub; unsigned char rule[4]; int gold[4]; int gold_padding; } LLRow;",
        "typedef struct { const char *name; const LLRow *rows; int count; } LLFile;",
        "typedef struct { const char *tag; double unit; int force; } LLGutter;",
        "",
        f"#define LL_GOLD_WIDTH {GOLD_SIZE[0]}",
        f"#define LL_GOLD_HEIGHT {GOLD_SIZE[1]}",
        f"#define LL_FONT_HEIGHT_DIVISOR {FONT_HEIGHT_DIVISOR!r}",
        f"#define LL_FONT_SCALE_OFFSET {FONT_SCALE_OFFSET!r}",
        "",
        "/* The build's list gutters, in its order: description panes, selection lists, then",
        " * the per-file hand-set ones, which may reduce a gutter (force). */",
        "static const LLGutter LL_GUTTERS[] = {",
    ]
    for tag in sorted(DESCRIPTION_LISTBOXES):
        lines.append(f"    {{ {c_string(tag)}, {GUTTER_AT_UNIT_SCALE!r}, 0 }},")
    for tag in sorted(LIST_LISTBOXES):
        lines.append(f"    {{ {c_string(tag)}, {LIST_GUTTER_AT_UNIT_SCALE!r}, 0 }},")
    lines.append("};")
    lines.append("")
    lines.append("typedef struct { const char *file, *tag; double unit; } LLFileGutter;")
    lines.append("static const LLFileGutter LL_FILE_GUTTERS[] = {")
    for file in sorted(HAND_TUNED_GUTTERS):
        for tags, unit in HAND_TUNED_GUTTERS[file]:
            for tag in sorted(tags):
                lines.append(f"    {{ {c_string(file)}, {c_string(tag)}, {unit!r} }},")
    lines.append("};")
    lines.append("")
    entries = table_entries()
    for index, (name, rows) in enumerate(entries):
        lines.append(f"static const LLRow LL_ROWS_{index}[] = {{  /* {name} */")
        for (tag, sub), rules, gold, pad in rows:
            r = ", ".join(str(RULES.index(x)) for x in rules)
            g = ", ".join("LL_NO_GOLD" if gold is None else str(x) for x in (gold or [None] * 4))
            p = "LL_NO_PADDING" if pad is None else str(pad)
            lines.append(f"    {{ {c_string(tag)}, {c_string(sub)}, {{ {r} }}, {{ {g} }}, {p} }},")
        lines.append("};")
    lines.append("")
    lines.append("static const LLFile LL_FILES[] = {")
    for index, (name, rows) in enumerate(entries):
        lines.append(f"    {{ {c_string(name)}, LL_ROWS_{index}, {len(rows)} }},")
    lines.append("};")
    lines.append("")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- the layout
def table_by_file() -> dict:
    return {name: {key: (rules, gold, pad) for key, rules, gold, pad in rows}
            for name, rows in table_entries()}


def game_size(source: GFFStruct, vanilla: GFFStruct) -> bool:
    """Is `source` laid out for the game's size: the game's own base, its root inside it?"""
    base, root = base_of(source), extent(source)
    return (base == base_of(vanilla) and root is not None and root[0] >= 0 and root[1] >= 0
            and root[0] + root[2] <= base[0] and root[1] + root[3] <= base[1])


def layout(name: str, vanilla: GFFStruct, source: GFFStruct, width: int, height: int,
           rows: dict) -> GFFStruct | None:
    """`source` (the game's file or a mod's) laid out for width x height, in place, or None
    when it is not laid out for the game's size (game_size). What KmrpLiveLayout
    (kmrp-guiadapt.c) does, in Python."""
    if not game_size(source, vanilla):
        return None
    base = base_of(source)
    own = {key: extent(s) for key, s, _ in structures(vanilla)}
    for key, struct, ctype in structures(source):
        v4 = extent(struct)
        row = rows.get(key)
        unmoved = row is not None and own.get(key) == v4
        rules = row[0] if row else [default_rule(f, key[1], ctype, v4) for f in range(4)]
        gold = row[1] if unmoved and row[1] is not None else [None] * 4
        e = child(struct, "EXTENT")
        out = [placed(f, rules[f], v4, gold[f], width, height, base) for f in range(4)]
        for f, x in zip(FIELDS, out):
            e.set_int32(f, x)
        if unmoved and row[2] is not None and (width, height) == GOLD_SIZE and struct.exists("PADDING"):
            struct.set_int32("PADDING", row[2])
    # The build's gutters, never reducing one but for the hand-set ones.
    for key, struct, ctype in structures(source):
        if key[1] or ctype != LISTBOX or not struct.exists("PADDING"):
            continue
        tag = key[0].upper()
        for tags, unit, force in ((DESCRIPTION_LISTBOXES, GUTTER_AT_UNIT_SCALE, False),
                                  (LIST_LISTBOXES, LIST_GUTTER_AT_UNIT_SCALE, False),
                                  *((t, u, True) for t, u in HAND_TUNED_GUTTERS.get(name, ()))):
            if tag in tags:
                g = gutter(unit, height)
                if force or struct.get_int32("PADDING") < g:
                    struct.set_int32("PADDING", g)
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="stop if the table is out of date")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not TABLE.is_file() or TABLE.read_text(encoding="ascii") != text:
            print(f"{TABLE} is out of date: run python tools/build_live_layout.py", file=sys.stderr)
            return 1
        print(f"{TABLE} is current")
        return 0
    TABLE.write_bytes(text.encode("ascii"))
    print(f"wrote {TABLE}: {len(FILES)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
