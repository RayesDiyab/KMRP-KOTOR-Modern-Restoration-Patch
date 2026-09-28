#!/usr/bin/env python3
"""Does a controller module export every function an installed patch_config.toml hooks?

    python tools/check_module_exports.py <patch_config.toml> <kmrp-controller.module>

The installer compiles its hook table at the end of a build but embeds the module
file as it stands, so a hook added while a build ran shipped naming a function the
module did not have (installer BCA35F28, 2026-09-25). The runtime stopped at that
entry, and every hook after it -- movies, rumble, the keyboard and mouse detection
-- never applied. Test-ControllerSupport.ps1 runs this against its installed fixture.

Standard library only: the PE export table is read with struct, so any Python that
runs the regression suite can run this.
"""
import struct
import sys
import tomllib


def export_names(path):
    data = open(path, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError(f"{path}: not a PE image")
    sections_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    if struct.unpack_from("<H", data, optional)[0] != 0x10B:
        raise ValueError(f"{path}: not a 32-bit image")
    export_rva = struct.unpack_from("<I", data, optional + 96)[0]
    if export_rva == 0:
        return set()
    sections = []
    table = optional + optional_size
    for i in range(sections_count):
        s = table + i * 40
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", data, s + 8)
        sections.append((va, max(vsize, rawsize), rawptr))

    def offset(rva):
        for va, size, rawptr in sections:
            if va <= rva < va + size:
                return rva - va + rawptr
        raise ValueError(f"{path}: RVA 0x{rva:X} is in no section")

    directory = offset(export_rva)
    count = struct.unpack_from("<I", data, directory + 24)[0]   # NumberOfNames
    names = struct.unpack_from("<I", data, directory + 32)[0]   # AddressOfNames
    result = set()
    for i in range(count):
        name_rva = struct.unpack_from("<I", data, offset(names) + i * 4)[0]
        start = offset(name_rva)
        result.add(data[start:data.index(b"\0", start)].decode("ascii"))
    return result


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    config = tomllib.load(open(sys.argv[1], "rb"))
    needed = [hook["function"] for patch in config["patches"]
              for hook in patch.get("hooks", []) if hook.get("function")]
    exported = export_names(sys.argv[2])
    missing = [name for name in needed if name not in exported]
    print(f"hooked functions {len(needed)}, exported {len(exported)}, missing {missing}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
