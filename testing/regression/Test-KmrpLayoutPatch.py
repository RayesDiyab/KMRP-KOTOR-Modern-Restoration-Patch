#!/usr/bin/env python3
"""Check the Mac layout patch (macos/patches/kmrp-layout) against the game binary, the
widescreen patch and KMRP's Windows executable.

The patch writes, when the game starts, the sizes KMRP's Windows installer writes per
resolution and the list-box PADDING fix of Windows gold v11. This builds it with a small
driver that lists every site it would write (KMRP_LayoutGroups) for each screen height KMRP
ships, and checks:

1. every site's expected bytes are what the unmodified KOTOR_Exe 1.4.0 holds there, except
   the sites the widescreen patch owns, which must hold that patch's bytes;
2. no site overlaps a widescreen-patch hook other than those declared below;
3. every value is the Windows installer's (ResolutionPatch.Apply in src/patcher/KmrpPatcher.cs:
   (int)Math.Round(base * max(1, height / 720f)), single precision, half to even);
4. every rewritten instruction disassembles as intended, the two list-box blocks jump to
   the patch's stubs, the stubs disassemble to the listings in listbox_padding.cpp and jump
   back where the blocks end, the Options check boxes' layout (0x1002cecee) is replaced by an
   absolute jump into the patch, and at a height of 720 or less the stack-count block computes
   exactly what vanilla does;
5. the game's module has one load-time initialiser, the patch's constructor. A second one is a
   C++ global that needs initialising, which the constructor may run before: a global
   std::vector of the vanilla bytes was still empty when the constructor read it, and the
   group was left alone in game (2026-09-29). The driver in 1 calls the code after start-up,
   so it cannot see this.

    python testing/regression/Test-KmrpLayoutPatch.py CLEAN_KOTOR_EXE [WIDESCREEN_PATCH_DIR]

CLEAN_KOTOR_EXE must be the unmodified 1.4.0 build (C1FCB8D3...6D71). WIDESCREEN_PATCH_DIR
defaults to the submodule's third_party/Kotor-Patch-Manager/Patches/K1WidescreenPatch.
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_universal_resources as pur  # noqa: E402

PATCH_DIR = ROOT / "macos" / "patches" / "kmrp-layout"
SOURCES = sorted(PATCH_DIR.glob("*.cpp"))
CLEAN_SHA = "c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71"

# Sites the widescreen patch writes that this patch reads or writes after it, by design.
#   0x1002bfb49  its store-row icon hook (icon = row height); checked here, rewritten unchanged
#   0x1002bfbc0  inside its 0x1002bfbbf badge hook, which it restores to vanilla with
#                UseGuiFileLayouts before this patch loads
WIDESCREEN_OWNED = {0x1002bfb49}
DECLARED_OVERLAPS = {0x1002bfb49, 0x1002bfbc0}

# Mac scaled modes the build has no set for (see Test-GuiBlendHelper.py), plus the edges of
# the rule: below 720 everything stays vanilla, and above 5715 the marker scale is capped.
EXTRA_RESOLUTIONS = ["640x480", "800x600", "1280x720", "1281x721", "1280x832", "1352x878", "1710x1112",
                     "1800x1169", "1920x1243", "2056x1329", "3600x2338", "10240x5760"]
# Where the driver says the near page is (any address will do for checking the bytes).
NEAR_PAGE = 0x101000000

# The area-map stubs (area_map.cpp), as they must disassemble, jumps and RIP operands normalised.
MAP_STUB_LISTING = [
    "push rsi", "push rdx", "sub rsp, 8", "call qword ptr [rip + X]", "add rsp, 8", "pop r9", "pop r10",
    "jmp X",
    "push rdx", "push rcx", "sub rsp, 8", "call qword ptr [rip + X]", "add rsp, 8", "pop r9", "pop r10",
    "test eax, eax", "je X", "mov r8d, eax", "mov eax, dword ptr [r10]", "imul eax, dword ptr [rip + X]",
    "add eax, 0xdc", "cdq", "mov ecx, 0x1b8", "idiv ecx", "mov dword ptr [r10], eax",
    "mov eax, dword ptr [r9]", "imul eax, dword ptr [rip + X]", "add eax, 0x80", "cdq",
    "mov ecx, 0x100", "idiv ecx", "mov dword ptr [r9], eax", "mov eax, r8d", "ret",
]


# listbox_padding.cpp's stubs, as they must disassemble, and where each jumps back to.
STUB_LISTINGS = {
    "rows": ([
        "mov r14d, dword ptr [r12 + 0x344]", "movsx edi, word ptr [r12 + 0x378]", "mov eax, edi",
        "mov r8d, dword ptr [rbp - 0x2c]", "imul eax, r8d", "sub r14d, eax", "mov eax, r14d", "cdq",
        "idiv edi", "movzx r15d, byte ptr [r12 + 0x373]", "mov ecx, dword ptr [r12 + 0x340]",
        "mov ebx, dword ptr [r12 + 0x368]", "sub ecx, r15d", "xor edx, edx",
        "test byte ptr [r12 + 0x370], 0x10", "cmovne edx, r15d", "mov dword ptr [rbp - 0x40], edx",
        "mov dword ptr [rbp - 0x3c], r13d", "mov dword ptr [rbp - 0x38], ecx",
        "mov dword ptr [rbp - 0x34], ebx", "movsx esi, word ptr [r12 + 0x37c]", "mov ecx, esi",
        "imul ecx, r8d", "mov r15d, ecx", "neg r15d", "jmp qword ptr [rip]",
    ], 0x1004a889e, 0x1004a8838, 102),
    "scroll": ([
        "movzx r9d, byte ptr [rbx + 0x373]", "mov esi, dword ptr [rbx + 0x340]",
        "mov eax, dword ptr [rbx + 0x368]", "sub esi, r9d", "xor ecx, ecx",
        "test byte ptr [rbx + 0x370], 0x10", "cmovne ecx, r9d", "mov dword ptr [rbp - 0x18], ecx",
        "mov dword ptr [rbp - 0x14], 0", "mov dword ptr [rbp - 0x10], esi",
        "mov dword ptr [rbp - 0xc], eax", "xor r9d, r9d", "jmp qword ptr [rip]",
    ], 0x1004a93a5, 0x1004a937a, 43),
    "button": ([
        "mov rax, qword ptr [rsi]", "mov rdx, qword ptr [rsi + 8]", "mov qword ptr [rbx + 0x10], rdx",
        "mov qword ptr [rbx + 8], rax", "cvtsi2sd xmm0, dword ptr [rbx + 0x14]",
        "cvtss2sd xmm1, dword ptr [rip + X]", "mulsd xmm0, xmm1", "cvtsd2si eax, xmm0",
        "mov dword ptr [rbx + 0x14], eax", "jmp qword ptr [rip]",
    ], 0x1004a5a14, 0x1004a5a05, 15),
}
ROW_SCALES: dict[tuple[int, int], float] = {}
OVERLAYS: dict[tuple[int, int], tuple[int, int]] = {}
PAGES: dict[tuple[int, int], bytes] = {}
STUBS: dict[str, bytes] = {}


def f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def windows_scale(height: int) -> float:
    s = f32(height / 720.0)
    return 1.0 if s < 1.0 else s


def windows_value(base: int, height: int) -> int:
    return round(f32(base * windows_scale(height)))  # Python's round() is half to even


def read_macho(path: Path):
    data = path.read_bytes()
    segments = []
    ncmds = struct.unpack_from("<I", data, 16)[0]
    off = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, off)
        if cmd == 0x19:
            vm, vs, fo, fs = struct.unpack_from("<QQQQ", data, off + 24)
            segments.append((vm, fs, fo))
        off += size

    def at(va: int, n: int) -> bytes:
        for vm, fs, fo in segments:
            if vm <= va and va + n <= vm + fs:
                return data[fo + va - vm: fo + va - vm + n]
        raise ValueError(f"{va:#x} is not in the file")
    return data, at


def widescreen_hooks(patch_dir: Path) -> dict[int, tuple[bytes, bytes]]:
    doc = tomllib.loads((patch_dir / "kotor1-steam-aspyr-macos.hooks.toml").read_text())
    hooks = {}
    for hook in doc.get("hooks", []):
        original = bytes(hook.get("original_bytes", []))
        replacement = bytes(hook.get("replacement_bytes", []))
        hooks[hook["address"]] = (original, replacement)
    return hooks


def disassemble(code: bytes, address: int) -> list[str]:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    out, used = [], 0
    for ins in md.disasm(code, address):
        out.append(f"{ins.mnemonic} {ins.op_str}".strip())
        used += ins.size
    if used != len(code):
        raise ValueError(f"{address:#x}: {len(code) - used} bytes do not disassemble")
    return out


def marker_scale(height: int) -> float:
    """ResolutionPatch.MarkerScaleForHeight: the height rule, capped at 127/16."""
    return min(windows_scale(height), f32(127.0 / 16.0))


def marker_size(vanilla: int, height: int) -> int:
    return max(1, round(f32(vanilla * marker_scale(height))))


def marker_offset(vanilla: int, height: int) -> int:
    return min(-1, -round(f32(-vanilla * marker_scale(height))))


def list_sites(resolutions: list[tuple[int, int]]) -> dict[tuple[int, int], list[tuple[str, int, bytes, bytes]]]:
    with tempfile.TemporaryDirectory(prefix="kmrp-resolution-test-") as tmp:
        tmp = Path(tmp)
        driver = tmp / "driver.cpp"
        driver.write_text(
            "#include <cstdio>\n#include <cstdlib>\n"
            '#include <cstdint>\n'
            'extern "C" void KMRP_LayoutGroups(int, int, uintptr_t, FILE*);\n'
            'extern "C" void KMRP_LayoutStubs(FILE*);\n'
            "int main(int argc, char** argv) {\n"
            "    KMRP_LayoutStubs(stdout);\n"
            "    for (int i = 1; i + 1 < argc; i += 2) {\n"
            '        printf("resolution\\t%s\\t%s\\n", argv[i], argv[i + 1]);\n'
            f"        KMRP_LayoutGroups(atoi(argv[i]), atoi(argv[i + 1]), {NEAR_PAGE:#x}, stdout);\n"
            "    }\n}\n")
        exe = tmp / "driver"
        # x86_64, as the game: the stubs are x86 code (the driver runs under Rosetta on arm64).
        subprocess.run(["clang++", "-arch", "x86_64", "-std=c++17", "-O2", "-w", "-o", str(exe), str(driver),
                        *map(str, SOURCES)], check=True)
        # The patch's constructor reads $HOME's swkotor.ini; an empty HOME keeps it inert.
        env = dict(os.environ, HOME=str(tmp))
        args = [str(v) for resolution in resolutions for v in resolution]
        text = subprocess.run([str(exe), *args], check=True, capture_output=True, text=True, env=env).stdout
    sites: dict[tuple[int, int], list] = {}
    height = None
    for line in text.splitlines():
        parts = line.split("\t")
        if parts[0] == "stub":
            STUBS[parts[1]] = bytes.fromhex(parts[2])
        elif parts[0] == "rowscale":
            ROW_SCALES[height] = float(parts[1])
        elif parts[0] == "overlay":
            OVERLAYS[height] = (int(parts[1]), int(parts[2]))
        elif parts[0] == "page":
            PAGES[height] = bytes.fromhex(parts[1])
        elif parts[0] == "resolution":
            height = (int(parts[1]), int(parts[2]))  # the key: the whole resolution
            sites[height] = []
        else:
            sites[height].append((parts[0], int(parts[1], 16), bytes.fromhex(parts[2]), bytes.fromhex(parts[3])))
    return sites


def initialiser_count() -> int:
    """Entries in the x86_64 module's __mod_init_func (8 bytes each) or __init_offsets (4)."""
    with tempfile.TemporaryDirectory(prefix="kmrp-resolution-module-") as tmp:
        module = Path(tmp) / "module.dylib"
        subprocess.run(["clang++", "-arch", "x86_64", "-std=c++17", "-O2", "-mmacosx-version-min=10.9",
                        "-dynamiclib", "-w", "-o", str(module), *map(str, SOURCES)], check=True)
        load_commands = subprocess.run(["otool", "-l", str(module)], check=True, capture_output=True,
                                       text=True).stdout.splitlines()
    count = 0
    for i, line in enumerate(load_commands):
        name = line.split()[-1] if line.strip().startswith("sectname") else ""
        if name in ("__mod_init_func", "__init_offsets"):
            size = next(int(l.split()[-1], 16) for l in load_commands[i:i + 6] if l.strip().startswith("size"))
            count += size // (8 if name == "__mod_init_func" else 4)
    return count


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    exe_path = Path(sys.argv[1])
    widescreen = Path(sys.argv[2]) if len(sys.argv) > 2 else \
        ROOT / "third_party" / "Kotor-Patch-Manager" / "Patches" / "K1WidescreenPatch"
    data, at = read_macho(exe_path)
    if hashlib.sha256(data).hexdigest() != CLEAN_SHA:
        print(f"FAIL {exe_path} is not the unmodified KOTOR_Exe 1.4.0")
        return 1
    hooks = widescreen_hooks(widescreen)

    resolutions = sorted({tuple(int(v) for v in r.split("x"))
                          for r in [*(r for g in pur.GROUPS.values() for r in g), *EXTRA_RESOLUTIONS]},
                         key=lambda wh: (wh[1], wh[0]))
    by_height = list_sites(resolutions)
    heights = resolutions
    failures: list[str] = []

    # 1 and 2: expected bytes, overlaps (the same sites at every height).
    for group, address, expected, value in by_height[heights[0]]:
        if address in WIDESCREEN_OWNED:
            want = hooks.get(address, (b"", b""))[1]
            source = "the widescreen patch"
        else:
            want = at(address, len(expected))
            source = "KOTOR_Exe"
        if expected != want:
            failures.append(f"{group} {address:#x}: expects {expected.hex()}, {source} has {want.hex()}")
        if len(value) != len(expected):
            # The patch refuses such a site in game (a 100-byte block for 102 did, 2026-09-29).
            failures.append(f"{group} {address:#x}: writes {len(value)} bytes over {len(expected)}")
        for start, (original, _) in hooks.items():
            if start < address + len(expected) and address < start + len(original) \
                    and address not in DECLARED_OVERLAPS:
                failures.append(f"{group} {address:#x}: overlaps widescreen hook {start:#x}")

    # 3 and 4: values and code, at every height.
    for (width, height), sites in by_height.items():
        found = {address: (group, value) for group, address, _, value in sites}
        where = f"{width}x{height}"

        def check(address: int, base: int, what: str) -> None:
            got = struct.unpack("<i", found[address][1])[0]
            if got != windows_value(base, height):
                failures.append(f"{height}: {what} {got}, Windows {windows_value(base, height)}")

        check(0x1002be443, 56, "inventory icon")
        check(0x1002be874, 56, "inventory row height")
        check(0x1002bff71, 56, "store row height")
        check(0x1002bfbc0, 56, "store badge x (icon)")
        check(0x10022f257, 50, "skills icon")
        check(0x10022f60f, 50, "skills row height")
        check(0x100570efc, 50, "chain row height")
        check(0x100306879, 800, "popup width cap")
        check(0x1003065a2, 64, "popup icon offset")
        for address, base, less, what in ((0x10030688d, 800, 1, "popup width cap (>=)"),
                                          (0x100306881, 450, 1, "popup height stop"),
                                          (0x1003068ff, 450, 1, "popup height stop (second)")):
            got = struct.unpack("<i", found[address][1])[0]
            if got != windows_value(base, height) - less:
                failures.append(f"{height}: {what} {got}, Windows {windows_value(base, height) - less}")
        if struct.unpack("<2i", found[0x100571bb8][1]) != (windows_value(64, height),) * 2:
            failures.append(f"{height}: popup icon rect {struct.unpack('<2i', found[0x100571bb8][1])}")

        block = found[0x1002be4a0][1]
        listing = disassemble(block, 0x1002be4a0)
        w, i, t, h = (windows_value(b, height) for b in (21, 56, 37, 19))
        want = ["cmp eax, 2", f"mov ecx, {w:#x}", "jle 0x1002be4ac", "add ecx, ecx",
                "lea rsi, [rbp - 0x68]", "mov dword ptr [rsi + 8], ecx", f"lea eax, [r15 + {i:#x}]",
                "sub eax, ecx", "mov dword ptr [rsi], eax", f"lea eax, [r12 + {t:#x}]",
                "mov dword ptr [rsi + 4], eax", f"mov dword ptr [rsi + 0xc], {h:#x}", "nop", "nop"]
        if listing != want:
            failures.append(f"{height}: stack-count block disassembles as {listing}")
        for address, what in ((0x1002be4da, "add r15d, r13d; nop"), (0x1002be4e1, "sub eax, r13d"),
                              (0x10022f297, "add eax, edx; nop"), (0x10022f29d, "sub esi, edx; nop")):
            listing = "; ".join(disassemble(found[address][1], address))
            if listing != what:
                failures.append(f"{height}: {address:#x} disassembles as {listing}")
        if f32(ROW_SCALES.get((width, height), 0.0)) != windows_scale(height):
            failures.append(f"{height}: text-list row scale {ROW_SCALES.get((width, height))}, "
                            f"Windows {windows_scale(height)}")

        # The area map (resolution geometry: tools/analyze_resolution_guis.py; markers:
        # ResolutionPatch's MarkerSizeSites and MarkerOffsetSites).
        overlay = (width // 2, height // 2)
        canvas = (round(overlay[0] * 512 / 440), height // 2)
        for address, want, what in ((0x100571398, canvas, "canvas"), (0x1005713a8, overlay, "overlay")):
            if struct.unpack("<2i", found[address][1]) != want:
                failures.append(f"{where}: map {what} {struct.unpack('<2i', found[address][1])}, want {want}")
        if OVERLAYS.get((width, height)) != overlay:
            failures.append(f"{where}: map stubs rescale to {OVERLAYS.get((width, height))}, want {overlay}")
        for address, vanilla in ((0x1002b500b, 14), (0x1002b52cb, 20), (0x1002b544f, 16), (0x1002b54ee, 32),
                                 (0x1002b550e, 32), (0x1002b5513, 32)):
            if struct.unpack("<i", found[address][1])[0] != marker_size(vanilla, height):
                failures.append(f"{where}: marker size at {address:#x} {struct.unpack('<i', found[address][1])[0]}")
        for address, vanilla in ((0x1002b4ff4, -7), (0x1002b5003, -7), (0x1002b52b4, -10), (0x1002b52c3, -10),
                                 (0x1002b5438, -8), (0x1002b5447, -8), (0x1002b54d7, -16), (0x1002b54e6, -16)):
            if struct.unpack("<b", found[address][1])[0] != marker_offset(vanilla, height):
                failures.append(f"{where}: marker centring at {address:#x} {struct.unpack('<b', found[address][1])[0]}")
        if struct.unpack("<2i", found[0x1005713c8][1]) != (marker_size(32, height),) * 2:
            failures.append(f"{where}: mm_barrow rect {struct.unpack('<2i', found[0x1005713c8][1])}")
        # The map's two thunks, then (after the circle's rect) the message popup's (popup_fit.cpp)
        # and the granted popup's two (granted_popup.cpp).
        for address, target in ((0x1002b4fca, NEAR_PAGE), (0x1002b541b, NEAR_PAGE + 16), (0x1002b54c2, NEAR_PAGE + 16),
                                (0x100306a88, NEAR_PAGE + 48), (0x10028ea4f, NEAR_PAGE + 64),
                                (0x10022f321, NEAR_PAGE + 80)):
            value = found[address][1]
            if value[0] != 0xE8 or address + 5 + struct.unpack("<i", value[1:])[0] != target:
                failures.append(f"{where}: {address:#x} does not call the near page's thunk at {target:#x}")
        if 0x1002b626e + 7 + struct.unpack("<i", found[0x1002b6271][1])[0] != NEAR_PAGE + 32:
            failures.append(f"{where}: lbl_mapcircle's read does not point at the near page's copy")
        page = PAGES.get((width, height), b"")
        for thunk in (page[0:16], page[16:32], page[48:64], page[64:80], page[80:96]):
            if thunk[:6] != bytes.fromhex("ff2500000000") or thunk[14:] != b"\xcc\xcc":
                failures.append(f"{where}: a near-page thunk is malformed: {thunk.hex()}")
        if struct.unpack("<4i", page[32:48]) != (0, 0, marker_size(16, height), marker_size(16, height)):
            failures.append(f"{where}: lbl_mapcircle copy {struct.unpack('<4i', page[32:48])}")
        if height <= 720 and (w, i, t, h) != (21, 56, 37, 19):
            failures.append(f"{height}: stack-count label is not vanilla at scale 1")

        # The list-box PADDING fix does not depend on the height.
        for address, what in ((0x1004a82fd, "mov bl, 0"), (0x1004a8752, "mov bl, 0"),
                              (0x1004a83de, "xor r13d, r13d"), (0x1004a8697, "xor eax, eax"),
                              (0x1004a895d, "xor eax, eax")):
            listing = [x for x in disassemble(found[address][1], address) if x != "nop"]
            if listing != [what]:
                failures.append(f"{height}: {address:#x} disassembles as {listing}")
        for name, (_, _, site, length) in STUB_LISTINGS.items():
            value = found[site][1]
            if value[:6] != bytes.fromhex("ff2500000000") or value[14:] != b"\xcc" * (length - 14):
                failures.append(f"{height}: {site:#x} is not an absolute jump to the {name} stub")
        # The Options check boxes' SetExtent, replaced whole (resolution_sizes.cpp, AddCheckboxes).
        value = found.get(0x1002cecee, ("", b""))[1]
        if value[:6] != bytes.fromhex("ff2500000000") or value[14:] != b"\xcc" * 3:
            failures.append(f"{height}: 0x1002cecee is not an absolute jump to the check-box layout")

    code = STUBS.get("map", b"")
    listing = [re.sub(r"\[rip \+ 0x[0-9a-f]+\]", "[rip + X]", re.sub(r"^(jmp|je) 0x[0-9a-f]+$", r"\1 X", x))
               for x in disassemble(code[:-16], 0) if not x.startswith("nop")]
    if listing != MAP_STUB_LISTING:
        failures.append(f"map stubs disassemble as {listing}")
    if len(code) < 16 or struct.unpack("<2Q", code[-16:]) != (0x1004400d2, 0x100440300):
        failures.append("map stubs do not call WorldToMapCoords and GetPlayerMapCoords")

    for name, (want, resume, _, _) in STUB_LISTINGS.items():
        code = STUBS.get(name, b"")
        # The row-scale load is RIP-relative to the module's own data; its offset varies.
        listing = [re.sub(r"\[rip \+ 0x[0-9a-f]+\]", "[rip + X]", x) for x in disassemble(code[:-8], 0)]
        if listing != want:
            failures.append(f"{name} stub disassembles as {listing}")
        if len(code) < 8 or struct.unpack("<Q", code[-8:])[0] != resume:
            failures.append(f"{name} stub does not return to {resume:#x}")

    initialisers = initialiser_count()
    if initialisers != 1:
        failures.append(f"the module has {initialisers} load-time initialisers, not 1 (a C++ global?)")

    for failure in failures[:40]:
        print("  " + failure)
    sites = len(by_height[heights[0]])
    print(f"{'FAIL' if failures else 'ok  '} {sites} sites at {len(resolutions)} resolutions "
          f"({resolutions[0][0]}x{resolutions[0][1]}..{resolutions[-1][0]}x{resolutions[-1][1]}): "
          f"{len(failures)} problems")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
