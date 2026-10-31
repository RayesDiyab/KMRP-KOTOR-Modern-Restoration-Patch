#!/usr/bin/env python3
"""Modern Driver Compatibility goes in by a route that lets the game start.

K1DC's module imports functions Windows 7 does not have. Windows will not load a DLL
whose imports it cannot find, and KOTOR Patch Manager's runtime loads the module as the
game starts, so on Windows 7 that K1DC stops the game (the reporter of issue 41 met this
with 1.0). Since 2026-10-19 the installer asks the PC for each of those functions first
(DriverCompatOperations.NewerImports in src/patcher/KmrpPatcher.cs). Since 2026-10-31
(issue 44) K1DC is installed as its .kpatch, the module binaries/windows_x86.dll inside
it, where all are present, and as its author's standalone build for Windows 7 and 8
where one is missing (until then Windows 7 had no K1DC). This checks, from the vendored
files themselves:

  1. the module is the one whose import table was read for that list (its SHA-256). A
     new K1DC fails here on purpose: read its imports again against Windows 7, then
     update NewerImports and this hash;
  2. every function in NewerImports is imported by the module, so the list holds
     nothing stale;
  3. every import from a DLL Windows 7 lacks altogether (the api-ms-win-* API sets)
     and from bcryptprimitives.dll is in the list;
  4. the Windows 7 and 8 build's two files are the ones read (their SHA-256s) and
     import none of those: no function in NewerImports, no API set, nothing from
     bcryptprimitives.dll;
  5. the installer asks the PC before it picks the route (KpmEdition.cs,
     DriverCompatRoute), and the Advanced Settings tile stays enabled where the .kpatch
     cannot run.

Reads files only; it starts no game and no installer, and runs on any system.

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import hashlib
import re
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KPATCH = ROOT / "third_party/Included/k1-modern-driver-compatibility-2.0.1 by Synchro/k1-modern-driver-compatibility.kpatch"
MODULE = "binaries/windows_x86.dll"
SOURCE = ROOT / "src/patcher/KmrpPatcher.cs"
CHOOSER = ROOT / "src/patcher/KpmEdition.cs"

# The module NewerImports was read from (2.0.1, 2026-10-31).
REVIEWED = "5AA8D31DF06E01D9C540068F1DC7E923404D958EC020BB38A3A5F7810A500C55"

# The Windows 7 and 8 build (2.0.1's -standalone-win7 download), read 2026-10-31.
WINDOWS7 = KPATCH.parent / "standalone-win7"
WINDOWS7_REVIEWED = {
    "dinput8.dll": "AD5D8D449CE305CAF62CB17D8698EBF17E94F9120EE993D0DD85211DFE14F8DD",
    "k1-modern-driver-compatibility.asi": "ABA0D9DF267FB4E87D22D13F780AC5F559AFD4302FC2D67468463FEE8F38B507",
}


def imports(name: str, data: bytes) -> set[tuple[str, str]]:
    """(dll in lower case, function) for each import by name of a PE32 file."""
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise SystemExit(f"{name} is not a PE file")
    sections, optional_size = struct.unpack_from("<H", data, pe + 6)[0], struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    if struct.unpack_from("<H", data, optional)[0] != 0x10B:
        raise SystemExit(f"{name} is not 32-bit")
    import_rva = struct.unpack_from("<I", data, optional + 96 + 8)[0]   # data directory 1
    table = optional + optional_size
    spans = []
    for i in range(sections):
        virtual_size, address, raw_size, raw = struct.unpack_from("<IIII", data, table + 40 * i + 8)
        spans.append((address, max(virtual_size, raw_size), raw))

    def at(rva: int) -> int:
        for address, size, raw in spans:
            if address <= rva < address + size:
                return rva - address + raw
        raise SystemExit(f"{name}: RVA 0x{rva:X} is in no section")

    def text(offset: int) -> str:
        return data[offset:data.index(b"\0", offset)].decode("ascii")

    found = set()
    descriptor = at(import_rva)
    while True:
        lookup, _, _, name, first = struct.unpack_from("<IIIII", data, descriptor)
        if not (lookup or name or first):
            return found
        library = text(at(name)).lower()
        thunk = at(lookup or first)
        while (entry := struct.unpack_from("<I", data, thunk)[0]):
            if not entry & 0x80000000:                     # by name, not by ordinal
                found.add((library, text(at(entry) + 2)))  # after the two-byte hint
            thunk += 4
        descriptor += 20


def main() -> int:
    failed = False

    def check(ok: bool, what: str) -> None:
        nonlocal failed
        failed |= not ok
        print(("ok    " if ok else "FAIL  ") + what)

    with zipfile.ZipFile(KPATCH) as kpatch:
        module = kpatch.read(MODULE)
    actual = hashlib.sha256(module).hexdigest().upper()
    check(actual == REVIEWED, f"{MODULE} is the module NewerImports was read from"
          + ("" if actual == REVIEWED else f" (now {actual}: read its imports again)"))

    source = SOURCE.read_text(encoding="utf-8")
    block = re.search(r"NewerImports =\s*\{(.*?)\};", source, re.S)
    listed = {(dll.lower(), fn) for dll, fn in re.findall(r'\{ "([^"]+)", "([^"]+)" \}', block.group(1))} if block else set()
    check(len(listed) == 4, f"NewerImports lists {len(listed)} functions")

    imported = imports(MODULE, module)
    print(f"      {MODULE}: {len(imported)} functions imported by name")
    stale = sorted(listed - imported)
    check(not stale, "every function in NewerImports is imported" + (f"; not imported: {stale}" if stale else ""))
    newer = {(dll, fn) for dll, fn in imported if dll.startswith("api-ms-win-") or dll == "bcryptprimitives.dll"}
    unlisted = sorted(newer - listed)
    check(not unlisted, "every API-set and bcryptprimitives import is in NewerImports"
          + (f"; missing: {unlisted}" if unlisted else ""))

    for name, expected in WINDOWS7_REVIEWED.items():
        data = (WINDOWS7 / name).read_bytes()
        actual = hashlib.sha256(data).hexdigest().upper()
        check(actual == expected, f"standalone-win7/{name} is the file read"
              + ("" if actual == expected else f" (now {actual}: read its imports again)"))
        found = imports(name, data)
        newer = sorted(f"{dll}!{fn}" for dll, fn in found
                       if (dll, fn) in listed or dll.startswith("api-ms-win-") or dll == "bcryptprimitives.dll")
        check(not newer, f"standalone-win7/{name} imports nothing Windows 7 lacks ({len(found)} functions)"
              + (f"; it imports {newer}" if newer else ""))

    chooser = CHOOSER.read_text(encoding="utf-8")
    route = re.search(r"private static int DriverCompatRoute\(.*?\n        \}", chooser, re.S)
    body = route.group(0) if route else ""
    check("InstallPlatform.DriverCompatMissing() == null ? DriverCompatKpatch : DriverCompatWindows7" in body,
          "DriverCompatRoute asks the PC, the .kpatch where it can run, the Windows 7 build where not")
    check("DriverCompatStandalone.Install(" in chooser, "the install writes the Windows 7 build on that route")
    check("driverToggle.Enabled = false;" not in source, "the Advanced Settings tile stays enabled on Windows 7")

    print()
    print("a check failed" if failed else "all checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
