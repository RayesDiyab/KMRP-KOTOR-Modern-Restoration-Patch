"""KMRP's mod compatibility, shown to be generic by format (docs/mod-file-inventory.md).

What it checks, each with files made here, under names no KMRP code knows:

1. 2DA (macos/tools/kmrp-merge.c with kmrp-2da.h), on six table schemas:
   - rows told apart by a "label" column, by another column of unique values, by row
     labels that are names, and by row number;
   - a mod that puts rows in between, appends rows, reorders columns, adds a column in
     between, changes a cell KMRP changes (the mod's value stays and is noted), removes a
     column KMRP changes (noted as lost), repeats a key (left alone and noted);
   - a table read by number whose rows the mod pushed down (KMRP's change not applied to
     the rows that moved), a text "2DA V2.0" mod with a DEFAULT line (kept as text, with
     its DEFAULT), a malformed file (not merged), a mod table equal to vanilla (gives
     KMRP's), a mod table without the key column (not merged);
   - every merged table keeps the mod's rows at the mod's numbers;
   - the merge code names no table: it holds no ".2da" file name at all.
2. Pictures (kmrp-gameart.c, KmrpDeriveImage): a mod's TGA (24 and 32 bit, RLE, either
   origin) and TPC (uncompressed RGB and RGBA) drawn as a kmrp_derive.txt line says, its
   size, place and transparency checked pixel for pixel; a TPC out when asked; a file that
   is not a picture refused.
3. The record (kmrp_derive.txt) the generators write, when the game's files are present:
   every line names a file that was written and a source.
4. Models (kmrp-swoophud.c, KmrpSwoopHudModel): the game's model changed, a model whose
   part is not the game's refused.
5. Layouts (kmrp-guiadapt.c, Live Adaptive Layout), C and Python field for field:
   - a mod's moved control keeps its move through KMRP's placing (the key mapping list
     moved 20 px: 740 at 3440x1440, as docs/mod-file-inventory.md computes it);
   - an already-scaled file (every full-screen screen laid out for 1920x1080 first): at
     its own size exactly as it went in (never scaled twice); at 3440x1440 converted from
     its canvas, each control where it was as a share of the screen; a file scaled by the
     rules alone gets KMRP's calibration once at another size (the key list's LEFT 632),
     and KMRP's own calibrated layout given back has the skipped calibration reported;
   - a file whose root alone was resized is refused, as before;
   - two controls the mod moved together stay lined up.
6. Every file given as a mod's input is byte for byte the same after each call.

Run: python testing/regression/Test-ModCompatibility.py  (exit 0 when everything passes).
"""
from __future__ import annotations

import hashlib
import io
import os
import random
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_live_layout as ll  # noqa: E402
import native_helpers  # noqa: E402
from pykotor.resource.formats.gff import GFFList, read_gff, write_gff  # noqa: E402
from pykotor.resource.formats.twoda import TwoDA, read_2da, write_2da  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402

TOOLS = ROOT / "macos" / "tools"
GAME = Path(os.environ.get("KMRP_GAME", r"C:/Program Files (x86)/Steam/steamapps/common/swkotor"))
failures: list[str] = []
checks = 0


def fail(message: str) -> None:
    failures.append(message)
    print("FAIL " + message)


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        fail(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------- 2DA
def table(headers: list[str], rows: list[tuple[str, dict]]) -> TwoDA:
    t = TwoDA(headers)
    for label, cells in rows:
        t.add_row(label, {h: cells.get(h, "") for h in headers})
    return t


def binary(t: TwoDA) -> bytes:
    data = bytearray()
    write_2da(t, data, ResourceType.TwoDA)
    return bytes(data)


def text_2da(headers: list[str], rows: list[tuple[str, dict]], default: str | None) -> bytes:
    lines = ["2DA V2.0", f"DEFAULT: {default}" if default is not None else "", "  " + " ".join(headers)]
    for label, cells in rows:
        values = [cells.get(h, "") for h in headers]
        lines.append(label + " " + " ".join(f'"{v}"' if " " in v else (v or "****") for v in values))
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def rows_of(data: bytes) -> list[tuple[str, dict]]:
    """A 2DA's rows as (label, {column: value}), read by PyKotor (binary) or by hand (text)."""
    if data.startswith(b"2DA V2.0"):
        lines = [l for l in data.decode("ascii").splitlines()]
        headers = lines[2].split()
        out = []
        for line in lines[3:]:
            if not line.strip():
                continue
            parts, token, quoted = [], "", False
            for ch in line:
                if ch == '"':
                    quoted = not quoted
                elif ch in " \t" and not quoted:
                    if token:
                        parts.append(token)
                    token = ""
                else:
                    token += ch
            if token:
                parts.append(token)
            out.append((parts[0], {h: ("" if v == "****" else v) for h, v in zip(headers, parts[1:])}))
        return out
    t = read_2da(data)
    return [(t.get_label(i), {h: t.get_cell(i, h) for h in t.get_headers()}) for i in range(t.get_height())]


class Merge:
    def __init__(self, helper: Path, tmp: Path):
        self.helper, self.tmp, self.count = helper, tmp, 0

    def __call__(self, base: bytes, ours: bytes, theirs: bytes) -> tuple[int, bytes | None, str]:
        self.count += 1
        name = f"zz_never_seen_{self.count:02d}.2da"   # a name no KMRP code knows
        paths = [self.tmp / f"{self.count}-{k}.2da" for k in ("base", "ours", "theirs", "out")]
        for p, data in zip(paths, (base, ours, theirs)):
            p.write_bytes(data)
        before = [digest(p) for p in paths[:3]]
        r = subprocess.run([str(self.helper), "2da", name, *(native_helpers.arg(p) for p in paths)],
                           capture_output=True, text=True)
        check([digest(p) for p in paths[:3]] == before, f"{name}: an input file changed")
        out = paths[3].read_bytes() if paths[3].exists() else None
        return r.returncode, out, r.stdout


def test_2da(helper: Path, tmp: Path) -> None:
    merge = Merge(helper, tmp)

    # A. Rows named by a "label" column; KMRP changes one column of some rows.
    headers = ["label", "strref", "icon", "flag"]
    vanilla = [(str(i), {"label": f"Row_{i:02d}", "strref": str(100 + i), "icon": f"ico_{i % 4}", "flag": "1"})
               for i in range(12)]
    kmrp = [(l, {**c, "icon": c["icon"].replace("ico_", "kmr_")}) for l, c in vanilla]
    # The mod: a row in between, a row at the end, the icon column moved first and a column
    # put in between, one icon KMRP changes set to its own, one row's flag changed.
    mod_rows = [(l, dict(c)) for l, c in vanilla]
    mod_rows.insert(4, ("x", {"label": "Mod_Inserted", "strref": "999", "icon": "mod_new", "flag": "0"}))
    mod_rows.append(("x", {"label": "Mod_Appended", "strref": "998", "icon": "ico_1", "flag": "1"}))
    mod_rows[8][1]["icon"] = "mod_own"         # vanilla Row_07
    mod_rows[2][1]["flag"] = "0"               # vanilla Row_02
    mod_rows = [(str(i), c) for i, (_, c) in enumerate(mod_rows)]
    mod_headers = ["icon", "label", "extra", "strref", "flag"]
    for _, c in mod_rows:
        c["extra"] = "x"
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)),
                             binary(table(mod_headers, mod_rows)))
    check(code == 0 and out is not None, f"A: merged ({code}): {notes}")
    if out:
        got = rows_of(out)
        check([l for l, _ in got] == [l for l, _ in mod_rows], "A: the mod's row numbers are not kept")
        check(read_2da(out).get_headers() == mod_headers, "A: the mod's columns or their order are not kept")
        by = {c["label"]: c for _, c in got}
        check(by["Row_00"]["icon"] == "kmr_0" and by["Row_11"]["icon"] == "kmr_3", "A: KMRP's change not applied by name")
        check(by["Row_07"]["icon"] == "mod_own", "A: the mod's own change to a field KMRP changes was not kept")
        check(by["Row_02"]["flag"] == "0" and by["Row_02"]["icon"] == "kmr_2", "A: independent changes not both kept")
        check(by["Mod_Inserted"]["icon"] == "mod_new" and by["Mod_Appended"]["icon"] == "ico_1",
              "A: the mod's own rows were changed")
        check(all(c["extra"] == "x" for _, c in got), "A: the mod's added column lost a value")
        check("Row_07" in notes and "kept" in notes, "A: the conflict was not noted")
        check("is row" in notes, "A: vanilla rows the mod moved were not noted")

    # B. No label column: the first column of unique values names the rows; the mod reorders.
    headers = ["resref", "cost", "group"]
    vanilla = [(str(i), {"resref": f"itm_{i}", "cost": str(i * 10), "group": str(i % 2)}) for i in range(6)]
    kmrp = [(l, {**c, "cost": str(int(c["cost"]) + 1)}) for l, c in vanilla]
    mod_rows = [(str(i), dict(c)) for i, (_, c) in enumerate(reversed(vanilla))]
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)), binary(table(headers, mod_rows)))
    check(code == 0 and out is not None, f"B: merged ({code}): {notes}")
    if out:
        got = {c["resref"]: c for _, c in rows_of(out)}
        check(all(got[f"itm_{i}"]["cost"] == str(i * 10 + 1) for i in range(6)), "B: not matched by the unique column")
        check([c["resref"] for _, c in rows_of(out)] == [c["resref"] for _, c in mod_rows], "B: the mod's order not kept")

    # C. No unique column; the row labels are names.
    headers = ["a", "b"]
    vanilla = [(name, {"a": "1", "b": "same"}) for name in ("Alpha", "Beta", "Gamma")]
    kmrp = [(l, {**c, "b": "kmrp"}) if l == "Beta" else (l, c) for l, c in vanilla]
    mod_rows = [vanilla[2], vanilla[0], vanilla[1]]
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)), binary(table(headers, mod_rows)))
    check(code == 0 and out is not None, f"C: merged ({code}): {notes}")
    if out:
        got = dict(rows_of(out))
        check(got["Beta"]["b"] == "kmrp" and got["Alpha"]["b"] == "same", "C: not matched by the row labels")

    # D. Read by number (labels 0, 1, ..., no unique column): rows appended by the mod keep
    # KMRP's change on the rows still vanilla's; a row put first pushes the others down,
    # and KMRP's change is then not applied to the moved rows.
    headers = ["x", "y", "z"]
    vanilla = [(str(i), {"x": str(i % 3), "y": "a", "z": "q"}) for i in range(8)]
    kmrp = [(l, {**c, "y": "b"}) if int(l) in (2, 5) else (l, c) for l, c in vanilla]
    appended = vanilla + [("8", {"x": "9", "y": "m", "z": "m"})]
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)), binary(table(headers, appended)))
    check(code == 0 and out is not None, f"D: appended merged ({code}): {notes}")
    if out:
        got = rows_of(out)
        check(got[2][1]["y"] == "b" and got[5][1]["y"] == "b" and got[8][1]["y"] == "m", "D: not applied by number")
    pushed = [("0", {"x": "7", "y": "zz", "z": "zz"})] + [(str(i + 1), c) for i, (_, c) in enumerate(vanilla)]
    pushed = [(l, {**c, "z": "p"} if l != "0" else c) for l, c in pushed]  # the mod's own column change
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)), binary(table(headers, pushed)))
    if out:
        got = rows_of(out)
        check(all(c["y"] != "b" for _, c in got), "D: KMRP's change landed on a row the mod pushed down")
        check("not vanilla's row" in notes, "D: the rows the mod pushed down were not noted")

    # E. A key the mod's table repeats: those rows are left alone.
    headers = ["label", "v"]
    vanilla = [(str(i), {"label": f"K{i}", "v": "0"}) for i in range(4)]
    kmrp = [(l, {**c, "v": "1"}) for l, c in vanilla]
    mod_rows = vanilla + [("4", {"label": "K2", "v": "0"})]
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)), binary(table(headers, mod_rows)))
    check(code == 0 and out is not None, f"E: merged ({code})")
    if out:
        got = rows_of(out)
        check(got[2][1]["v"] == "0" and got[4][1]["v"] == "0" and got[0][1]["v"] == "1", "E: an ambiguous row was changed")
        check("more than one row K2" in notes, "E: the repeated key was not noted")

    # F. The mod removed the column KMRP changes: noted as lost, the rest merged.
    headers = ["label", "keep", "gone"]
    vanilla = [(str(i), {"label": f"N{i}", "keep": "k", "gone": "g"}) for i in range(3)]
    kmrp = [(l, {**c, "gone": "kmrp", "keep": "kk"}) for l, c in vanilla]
    mod_rows = [(l, {"label": c["label"], "keep": c["keep"]}) for l, c in vanilla]
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)),
                             binary(table(["label", "keep"], mod_rows)))
    check(code == 0 and out is not None and all(c["keep"] == "kk" for _, c in rows_of(out or b"2DA V2.b\n")),
          "F: the column still there was not merged")
    check("no column gone" in notes, "F: the lost column was not noted")

    # G. A malformed mod file, and a mod table without the key column: not merged.
    good = binary(table(["label", "v"], vanilla[:2] if False else [("0", {"label": "A", "v": "1"})]))
    code, out, notes = merge(good, good, good[: len(good) // 2])
    check(code == 3 and out is None, f"G: a truncated mod table was merged ({code})")
    code, out, notes = merge(good, binary(table(["label", "v"], [("0", {"label": "A", "v": "2"})])),
                             binary(table(["name", "v"], [("0", {"name": "A", "v": "1"})])))
    check(code == 3 and out is None, f"G: a table without the key column was merged ({code})")

    # H. A text 2DA mod with a DEFAULT line: merged, kept as text, its DEFAULT kept.
    headers = ["label", "text"]
    vanilla = [(str(i), {"label": f"T{i}", "text": "old"}) for i in range(3)]
    kmrp = [(l, {**c, "text": "new"}) if c["label"] == "T1" else (l, c) for l, c in vanilla]
    mod = text_2da(headers, vanilla + [("3", {"label": "T3", "text": "two words"})], "fallback")
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)), mod)
    check(code == 0 and out is not None and out.startswith(b"2DA V2.0"), f"H: a text mod not merged as text ({code})")
    if out:
        check(b"DEFAULT: fallback" in out, "H: the DEFAULT line was lost")
        got = {c["label"]: c for _, c in rows_of(out)}
        check(got["T1"]["text"] == "new" and got["T3"]["text"] == "two words", "H: text cells wrong")

    # I. A mod table equal to vanilla gives KMRP's table.
    headers = ["label", "v"]
    vanilla = [(str(i), {"label": f"Q{i}", "v": str(i)}) for i in range(5)]
    kmrp = [(l, {**c, "v": c["v"] + "k"}) for l, c in vanilla]
    code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)), binary(table(headers, vanilla)))
    check(code == 0 and out is not None and rows_of(out) == kmrp, "I: an unchanged mod table did not give KMRP's")

    # J. Random schemas: whatever the mod does, its rows keep their numbers and labels.
    rng = random.Random(20261031)
    for case in range(40):
        columns = [f"c{rng.randint(0, 999)}_{k}" for k in range(rng.randint(1, 6))]
        headers = ["label"] + columns
        n = rng.randint(1, 30)
        vanilla = [(str(i), {"label": f"r{i}", **{c: rng.choice(["", "1", "2", "x y"]) for c in columns}}) for i in range(n)]
        kmrp = [(l, {**c, **{k: "K" for k in columns if rng.random() < 0.2}}) for l, c in vanilla]
        mod_rows = [(l, dict(c)) for l, c in vanilla]
        for _ in range(rng.randint(0, 5)):
            mod_rows.insert(rng.randint(0, len(mod_rows)), ("x", {"label": f"m{rng.randint(0, 99999)}",
                                                                   **{c: "M" for c in columns}}))
        mod_rows = [(str(i), c) for i, (_, c) in enumerate(mod_rows)]
        code, out, notes = merge(binary(table(headers, vanilla)), binary(table(headers, kmrp)),
                                 binary(table(headers, mod_rows)))
        if code != 0 or out is None:
            fail(f"J{case}: not merged ({code})")
            continue
        got = rows_of(out)
        check([l for l, _ in got] == [l for l, _ in mod_rows] and [c["label"] for _, c in got] == [c["label"] for _, c in mod_rows],
              f"J{case}: rows moved or renumbered")
        want = {c["label"]: c for _, c in kmrp}
        check(all(c == want[c["label"]] for _, c in got if c["label"] in want), f"J{case}: KMRP's change not applied")

    # K. The merge names no table.
    for source in (TOOLS / "kmrp-2da.h", TOOLS / "kmrp-merge.c"):
        text = source.read_text(encoding="utf-8")
        check(".2da\"" not in text and "tutorial" not in text.lower(), f"{source.name} names a table")


# ----------------------------------------------------------------------------- pictures
def tga(width: int, height: int, pixels: list[tuple[int, int, int, int]], bits: int = 32, rle: bool = False,
        top: bool = False) -> bytes:
    """A TGA of `pixels` (RGBA, rows from the top)."""
    rows = [pixels[y * width:(y + 1) * width] for y in range(height)]
    if not top:
        rows = rows[::-1]
    head = struct.pack("<BBBHHBHHHHBB", 0, 0, 10 if rle else 2, 0, 0, 0, 0, 0, width, height, bits,
                       (8 if bits == 32 else 0) | (32 if top else 0))
    out = bytearray(head)
    for row in rows:
        for r, g, b, a in row:
            px = bytes((b, g, r, a)) if bits == 32 else bytes((b, g, r))
            out += (b"\x00" + px) if rle else px
    return bytes(out)


def tpc(width: int, height: int, pixels: list[tuple[int, int, int, int]], alpha: bool) -> bytes:
    """An uncompressed TPC of `pixels` (RGBA, rows from the top), stored bottom row first
    as the game's TPCs are read (kmrp-gameart.c)."""
    head = struct.pack("<IfHHBB", 0, 0.0, width, height, 4 if alpha else 2, 1) + bytes(114)
    data = bytearray()
    for y in reversed(range(height)):
        for r, g, b, a in pixels[y * width:(y + 1) * width]:
            data += bytes((r, g, b, a)) if alpha else bytes((r, g, b))
    return head + bytes(data)


def read_out(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """A TGA or TPC KmrpDeriveImage wrote: (width, height, RGBA rows from the top)."""
    d = path.read_bytes()
    if path.suffix == ".tpc":
        w, h = struct.unpack("<HH", d[8:12])
        check(d[12] == 4 and struct.unpack("<I", d[:4])[0] == 0, "picture: the TPC is not uncompressed RGBA")
        raw = d[128:]
        rows = [[tuple(raw[(y * w + x) * 4:(y * w + x) * 4 + 4]) for x in range(w)] for y in range(h)]
        rows = rows[::-1]
    else:
        w, h = struct.unpack("<HH", d[12:16])
        raw = d[18:]
        rows = [[(raw[i + 2], raw[i + 1], raw[i], raw[i + 3]) for i in ((y * w + x) * 4 for x in range(w))] for y in range(h)]
        rows = rows[::-1]
    return w, h, [p for row in rows for p in row]


def test_pictures(gameart: Path, tmp: Path) -> None:
    # A 2x2 picture of four colours, opaque.
    four = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 255, 255)]
    sources = {
        "32-bit.tga": tga(2, 2, four), "24-bit.tga": tga(2, 2, four, bits=24), "rle.tga": tga(2, 2, four, rle=True),
        "top-origin.tga": tga(2, 2, four, top=True), "rgba.tpc": tpc(2, 2, four, True), "rgb.tpc": tpc(2, 2, four, False),
    }
    for name, data in sources.items():
        source = tmp / f"mod-{name}"
        source.write_bytes(data)
        before = digest(source)
        # Drawn 4x4, nearest, at left 1, bottom 2 on a 7x7 canvas; as a TPC for the TPCs.
        out = tmp / f"derived-{name}"
        out = out.with_suffix(".tpc" if name.endswith(".tpc") else ".tga")
        code = subprocess.run([str(gameart), "derive", native_helpers.arg(source), "7", "4", "1", "2", "nearest",
                               native_helpers.arg(out)]).returncode
        check(digest(source) == before, f"picture {name}: the mod's file changed")
        if code != 0 or not out.exists():
            fail(f"picture {name}: not derived ({code})")
            continue
        w, h, pixels = read_out(out)
        check((w, h) == (7, 7), f"picture {name}: canvas {w}x{h}")
        top = 7 - 2 - 4   # rows from the top above the picture
        for y in range(7):
            for x in range(7):
                inside = 1 <= x < 5 and top <= y < top + 4
                want = four[((y - top) // 2) * 2 + (x - 1) // 2] if inside else (0, 0, 0, 0)
                if pixels[y * 7 + x] != want:
                    fail(f"picture {name}: pixel {x},{y} is {pixels[y * 7 + x]}, wanted {want}")
                    break
            else:
                continue
            break
        global checks
        checks += 1
    # Linear at another size, and a file that is not a picture.
    src = tmp / "mod-linear.tga"
    src.write_bytes(tga(2, 2, four))
    out = tmp / "derived-linear.tga"
    code = subprocess.run([str(gameart), "derive", native_helpers.arg(src), "5", "5", "0", "0", "linear",
                           native_helpers.arg(out)]).returncode
    check(code == 0 and read_out(out)[:2] == (5, 5), "picture: a linear resize was not made")
    bad = tmp / "mod-bad.tga"
    bad.write_bytes(b"not a picture at all")
    out = tmp / "derived-bad.tga"
    code = subprocess.run([str(gameart), "derive", native_helpers.arg(bad), "5", "5", "0", "0", "linear",
                           native_helpers.arg(out)]).returncode
    check(code == 1 and not out.exists(), f"picture: a file that is not a picture was used ({code})")


def test_record(gameart: Path, icons: Path, tmp: Path) -> None:
    erf, key = GAME / "TexturePacks" / "swpc_tex_gui.erf", GAME / "chitin.key"
    if not erf.is_file() or not key.is_file():
        print(f"note: the record is not checked: no game at {GAME} (set KMRP_GAME)")
        return
    out = tmp / "set"
    out.mkdir()
    for args in ([str(icons), native_helpers.arg(erf), "1440", native_helpers.arg(out)],
                 [str(gameart), native_helpers.arg(erf), native_helpers.arg(key), "1440", native_helpers.arg(out)]):
        check(subprocess.run(args, stdout=subprocess.DEVNULL).returncode == 0, f"record: {Path(args[0]).name} failed")
    lines = (out / "kmrp_derive.txt").read_text(encoding="ascii").splitlines()
    check(len(lines) > 300, f"record: only {len(lines)} lines")
    for line in lines:
        f = line.split("\t")
        if len(f) not in (2, 7) or not (out / f[0]).is_file() or not f[1]:
            fail(f"record: bad line {line!r}")
            break
    check(any(l.startswith("tutorial.2da\ttutorial") for l in lines), "record: the table's line is missing")


def test_model(swoop: Path, tmp: Path) -> None:
    key = GAME / "chitin.key"
    if not key.is_file():
        print(f"note: models are not checked: no game at {GAME}")
        return
    from pykotor.extract.installation import Installation, SearchLocation
    inst = Installation(str(GAME))
    files = {}
    for kind in (ResourceType.MDL, ResourceType.MDX):
        res = inst.resource("m17mg_camera", kind, [SearchLocation.CHITIN])
        files[kind] = tmp / f"mod-m17mg_camera.{kind.extension}"
        files[kind].write_bytes(res.data)
    before = [digest(p) for p in files.values()]
    out = tmp / "model"
    out.mkdir()
    code = subprocess.run([str(swoop), "--model", *(native_helpers.arg(p) for p in files.values()),
                           native_helpers.arg(out), "3440", "1440"], stdout=subprocess.DEVNULL).returncode
    check(code == 0 and (out / "m17mg_camera.mdl").is_file(), f"model: the game's model was not changed ({code})")
    check([digest(p) for p in files.values()] == before, "model: the mod's files changed")
    # A model whose part is no longer the game's (the one just made) is refused.
    again = tmp / "model-again"
    again.mkdir()
    code = subprocess.run([str(swoop), "--model", native_helpers.arg(out / "m17mg_camera.mdl"),
                           native_helpers.arg(files[ResourceType.MDX]), native_helpers.arg(again), "3440", "1440"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    check(code == 1 and not (again / "m17mg_camera.mdl").exists(), f"model: a changed model was changed again ({code})")


# ----------------------------------------------------------------------------- layouts
def extents(root) -> dict:
    return {key: ll.extent(s) for key, s, _ in ll.structures(root)}


def live(helper: Path, name: str, source: Path | None, w: int, h: int, out: Path) -> tuple[int, str]:
    out.unlink(missing_ok=True)
    before = digest(source) if source else None
    r = subprocess.run([str(helper), "live", native_helpers.arg(ll.VANILLA / name), name, str(w), str(h),
                        native_helpers.arg(out), native_helpers.arg(source) if source else "-"],
                       capture_output=True, text=True)
    if source:
        check(digest(source) == before, f"{name}: the mod's file changed")
    return r.returncode, r.stdout


def test_layouts(helper: Path, tmp: Path) -> None:
    rows = ll.table_by_file()
    out = tmp / "out.gui"

    # The moved key list: 740 at 3440x1440 (docs/mod-file-inventory.md).
    name = "optkeymapping.gui"
    g = read_gff((ll.VANILLA / name).read_bytes())
    for c in g.root.acquire("CONTROLS", None, GFFList):
        if c.get_string("TAG") == "LST_EventList":
            e = ll.child(c, "EXTENT")
            e.set_int32("LEFT", e.get_int32("LEFT") + 20)
    moved = tmp / f"moved-{name}"
    write_gff(g, moved, ResourceType.GUI)
    code, notes = live(helper, name, moved, 3440, 1440, out)
    check(code == 0 and out.exists(), f"{name}: not laid out ({code})")
    if out.exists():
        got = extents(read_gff(out.read_bytes()).root)[("LST_EventList", "")]
        check(got[0] == 740, f"{name}: the moved list's LEFT is {got[0]}, not 740")
        python = ll.layout(name, read_gff((ll.VANILLA / name).read_bytes()).root, read_gff(moved.read_bytes()).root,
                           3440, 1440, rows[name])
        check(extents(python)[("LST_EventList", "")] == got, f"{name}: C and Python differ for the moved list")
        check("moved or resized" in notes, f"{name}: the carried move was not noted")

    # Already-scaled files: every full-screen screen, laid out for 1920x1080 by Live Adaptive
    # Layout itself, then given as a mod's file.
    tested = 0
    for name in sorted(rows):
        vanilla = read_gff((ll.VANILLA / name).read_bytes()).root
        if ll.extent(vanilla) != [0, 0, *ll.base_of(vanilla)]:
            continue
        code, _ = live(helper, name, None, 1920, 1080, out)
        if code != 0 or not out.exists():
            continue
        scaled = tmp / f"scaled-{name}"
        scaled.write_bytes(out.read_bytes())
        if ll.canvas(read_gff(scaled.read_bytes()).root, vanilla) != 2:
            continue
        tested += 1
        for w, h in ((1920, 1080), (3440, 1440)):
            code, notes = live(helper, name, scaled, w, h, out)
            if code != 0 or not out.exists():
                fail(f"{name}: the already-scaled file was refused at {w}x{h}")
                continue
            got = extents(read_gff(out.read_bytes()).root)
            given = extents(read_gff(scaled.read_bytes()).root)
            if (w, h) == (1920, 1080):
                # At its own size exactly as it went in: never scaled twice.
                off = [(k, got[k], given[k]) for k in given if got.get(k) != given[k]]
                check(not off, f"{name} at {w}x{h} from 1920x1080: it was scaled twice: {off[:2]}")
            else:
                # Each top-level control either converted from the file's canvas (its centre
                # where it was, as a share of the screen, within 2%: the file's own placing
                # kept) or, where it was only scaled from the game's, KMRP's own placing of
                # the game's control there (its calibration applied once), within 3 px.
                live(helper, name, None, w, h, tmp / "direct.gui")
                direct = extents(read_gff((tmp / "direct.gui").read_bytes()).root)
                off = []
                for k, e in given.items():
                    if k == ("", "") or k[1] or not e or e[2] <= 0 or e[3] <= 0 or k not in got:
                        continue
                    g = got[k]
                    converted = (abs((g[0] + g[2] / 2) / w - (e[0] + e[2] / 2) / 1920) <= 0.02 and
                                 abs((g[1] + g[3] / 2) / h - (e[1] + e[3] / 2) / 1080) <= 0.02)
                    kmrp = direct.get(k) is not None and max(abs(a - b) for a, b in zip(g, direct[k])) <= 3
                    if not (converted or kmrp):
                        off.append((k, e, g))
                check(not off, f"{name} at {w}x{h} from 1920x1080: not converted from its canvas: {off[:2]}")
            python = ll.layout(name, vanilla, read_gff(scaled.read_bytes()).root, w, h, rows[name])
            check(python is not None and extents(python) == got, f"{name} at {w}x{h}: C and Python differ (scaled)")
            check("not scaled twice" in notes, f"{name}: the canvas was not noted")
    check(tested >= 5, f"only {tested} screens tested already scaled")

    # A file scaled by the rules alone, nothing calibrated or moved: at another size each
    # control only scaled gets KMRP's calibration once (rule 2), so the key list stands
    # where KMRP puts the game's: LEFT 632 at 3440x1440, not the rule's 328.
    name = "optkeymapping.gui"
    vanilla = read_gff((ll.VANILLA / name).read_bytes()).root
    plain_rows = {k: (r[0], None, None, *r[3:]) for k, r in rows[name].items()}
    plain = ll.layout(name, vanilla, read_gff((ll.VANILLA / name).read_bytes()).root, 1920, 1080, plain_rows)
    g = read_gff((ll.VANILLA / name).read_bytes())
    g.root = plain
    scaled = tmp / f"plain-{name}"
    write_gff(g, scaled, ResourceType.GUI)
    code, notes = live(helper, name, scaled, 3440, 1440, out)
    got = extents(read_gff(out.read_bytes()).root) if code == 0 and out.exists() else {}
    live(helper, name, None, 3440, 1440, tmp / "direct.gui")
    direct = extents(read_gff((tmp / "direct.gui").read_bytes()).root)
    check(got.get(("LST_EventList", "")) == direct[("LST_EventList", "")],
          f"{name}: a file only scaled did not get KMRP's calibration: {got.get(('LST_EventList', ''))}, "
          f"KMRP's {direct[('LST_EventList', '')]}")
    check("calibration applied once" in notes, f"{name}: the calibration applied was not noted")
    python = ll.layout(name, vanilla, read_gff(scaled.read_bytes()).root, 3440, 1440, rows[name])
    check(extents(python) == got, f"{name}: C and Python differ (plain scaled)")
    # KMRP's own 1920x1080 layout given back: its calibrated controls are ambiguous, kept
    # as the file has them, and the skipped calibration reported (rule 3).
    code, _ = live(helper, name, None, 1920, 1080, out)
    calibrated = tmp / f"calibrated-{name}"
    calibrated.write_bytes(out.read_bytes())
    code, notes = live(helper, name, calibrated, 3440, 1440, out)
    check("calibration of them is skipped" in notes, f"{name}: a skipped calibration was not reported")

    # A root resized alone (its controls the game's): refused, as before.
    name = "optionsmain.gui"
    g = read_gff((ll.VANILLA / name).read_bytes())
    root = ll.child(g.root, "EXTENT")
    for field, factor in zip(ll.FIELDS, (3, 2.25, 3, 2.25)):
        root.set_int32(field, int(root.get_int32(field) * factor))
    hires = tmp / f"hires-{name}"
    write_gff(g, hires, ResourceType.GUI)
    code, notes = live(helper, name, hires, 1920, 1080, out)
    check(code == 0 and not out.exists(), f"{name}: a root resized alone was laid out")
    check("cannot identify" in notes, f"{name}: the refusal was not noted")

    # Two controls the mod moved together stay lined up, wherever gold placed them apart.
    found = False
    for name in sorted(rows):
        vanilla = read_gff((ll.VANILLA / name).read_bytes()).root
        game = extents(vanilla)
        code, _ = live(helper, name, None, 3440, 1440, out)
        if code != 0 or not out.exists():
            continue
        placed = extents(read_gff(out.read_bytes()).root)
        keys = [k for k in game if k != ("", "") and not k[1] and k in rows[name] and rows[name][k][1]]
        pair = next(((a, b) for a in keys for b in keys if a < b and game[a] and game[b] and game[a][1] == game[b][1]
                     and placed[a][1] != placed[b][1]), None)
        if not pair:
            continue
        g = read_gff((ll.VANILLA / name).read_bytes())
        for c in g.root.acquire("CONTROLS", None, GFFList):
            if (c.get_string("TAG"), "") in pair:
                e = ll.child(c, "EXTENT")
                e.set_int32("TOP", e.get_int32("TOP") + 10)
        mod = tmp / f"lined-{name}"
        write_gff(g, mod, ResourceType.GUI)
        code, notes = live(helper, name, mod, 3440, 1440, out)
        got = extents(read_gff(out.read_bytes()).root) if out.exists() else {}
        check(code == 0 and got and got[pair[0]][1] == got[pair[1]][1], f"{name}: {pair} moved together came apart")
        python = ll.layout(name, vanilla, read_gff(mod.read_bytes()).root, 3440, 1440, rows[name])
        check(got and extents(python) == got, f"{name}: C and Python differ (line-up)")
        check("line-up" in notes, f"{name}: the kept line-up was not noted")
        found = True
        break
    if not found:
        print("note: no screen has two controls at one top that gold places apart; line-up not exercised")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="kmrp-modcompat-") as name:
        tmp = Path(name)
        merge = native_helpers.build(TOOLS / "kmrp-merge.c", tmp, "kmrp-merge")
        gameart = native_helpers.build(TOOLS / "kmrp-gameart.c", tmp, "kmrp-gameart")
        icons = native_helpers.build(TOOLS / "kmrp-abilityicons.c", tmp, "kmrp-abilityicons")
        swoop = native_helpers.build(TOOLS / "kmrp-swoophud.c", tmp, "kmrp-swoophud")
        guiadapt = native_helpers.build(TOOLS / "kmrp-guiadapt.c", tmp, "kmrp-guiadapt")
        first = lambda helpers: next(iter(helpers.values()))  # noqa: E731
        for part, run in (("2da", lambda: test_2da(first(merge), tmp)),
                          ("pictures", lambda: test_pictures(first(gameart), tmp)),
                          ("record", lambda: test_record(first(gameart), first(icons), tmp)),
                          ("models", lambda: test_model(first(swoop), tmp)),
                          ("layouts", lambda: test_layouts(first(guiadapt), tmp))):
            before = len(failures)
            run()
            print(f"{part}: {'ok' if len(failures) == before else f'{len(failures) - before} failed'}")
    print(f"{checks} checks, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
