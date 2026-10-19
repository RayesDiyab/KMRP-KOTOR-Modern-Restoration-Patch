#!/usr/bin/env python3
"""Modern Driver Compatibility is left out where it would keep the game from starting.

K1DC's dinput8.dll and .asi import functions Windows 7 does not have. Windows will not
load a DLL whose imports it cannot find, and the game loads dinput8.dll as it starts,
so on Windows 7 an installed K1DC stops the game (the reporter of issue 41 met this with
1.0). Since 2026-10-19 the installer asks the PC for each of those functions first
(DriverCompatOperations.NewerImports in src/patcher/KmrpPatcher.cs) and installs K1DC
only where all are present. This checks, from the vendored files themselves:

  1. the two files are the ones whose import tables were read for that list (their
     SHA-256s). A new K1DC fails here on purpose: read its imports again against
     Windows 7, then update NewerImports and these hashes;
  2. every function in NewerImports is imported by one of the two files, so the list
     holds nothing stale;
  3. every import from a DLL Windows 7 lacks altogether (the api-ms-win-* API sets)
     and from bcryptprimitives.dll is in the list;
  4. the installer asks before it writes either file, and the Advanced Settings tile
     is disabled where K1DC cannot run.

Reads files only; it starts no game and no installer, and runs on any system.

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import hashlib
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENDORED = ROOT / "third_party/Included/k1-modern-driver-compatibility-2.0.0 by Synchro"
SOURCE = ROOT / "src/patcher/KmrpPatcher.cs"

# The files NewerImports was read from (2.0.0, 2026-10-19).
REVIEWED = {
    "dinput8.dll": "EC2F4824ECA58DD40F425756A4A7CEC77B8E381F21D11D7C846EC4B339B617AB",
    "k1-modern-driver-compatibility.asi": "BB58F426D5C3EC5D52C21D99F089F5979E4C30934C246F7C740AB269C932735E",
}


def imports(path: Path) -> set[tuple[str, str]]:
    """(dll in lower case, function) for each import by name of a PE32 file."""
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise SystemExit(f"{path.name} is not a PE file")
    sections, optional_size = struct.unpack_from("<H", data, pe + 6)[0], struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    if struct.unpack_from("<H", data, optional)[0] != 0x10B:
        raise SystemExit(f"{path.name} is not 32-bit")
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
        raise SystemExit(f"{path.name}: RVA 0x{rva:X} is in no section")

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

    for name, expected in REVIEWED.items():
        actual = hashlib.sha256((VENDORED / name).read_bytes()).hexdigest().upper()
        check(actual == expected, f"{name} is the file NewerImports was read from"
              + ("" if actual == expected else f" (now {actual}: read its imports again)"))

    source = SOURCE.read_text(encoding="utf-8")
    block = re.search(r"NewerImports =\s*\{(.*?)\};", source, re.S)
    listed = {(dll.lower(), fn) for dll, fn in re.findall(r'\{ "([^"]+)", "([^"]+)" \}', block.group(1))} if block else set()
    check(len(listed) == 6, f"NewerImports lists {len(listed)} functions")

    imported = set()
    for name in REVIEWED:
        found = imports(VENDORED / name)
        print(f"      {name}: {len(found)} functions imported by name")
        imported |= found
    stale = sorted(listed - imported)
    check(not stale, "every function in NewerImports is imported" + (f"; not imported: {stale}" if stale else ""))
    newer = {(dll, fn) for dll, fn in imported if dll.startswith("api-ms-win-") or dll == "bcryptprimitives.dll"}
    unlisted = sorted(newer - listed)
    check(not unlisted, "every API-set and bcryptprimitives import is in NewerImports"
          + (f"; missing: {unlisted}" if unlisted else ""))

    install = re.search(r"internal static void Install\(string executablePath, Action<string> report\)(.*?)\n        \}",
                        source, re.S)
    body = install.group(1) if install else ""
    asks, writes = body.find("if (!CanRunHere)"), body.find("File.Create(target)")
    check(0 <= asks < writes, "Install asks CanRunHere before it writes a file")
    tile = re.search(r"if \(!DriverCompatOperations\.CanRunHere\)\s*\{(.*?)\}", source, re.S)
    check(bool(tile) and "driverToggle.Enabled = false;" in tile.group(1),
          "the Advanced Settings tile is disabled where K1DC cannot run")

    print()
    print("a check failed" if failed else "all checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
