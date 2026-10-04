#!/usr/bin/env python3
"""What KMRP's .kpatch builders share: the executables KMRP supports, and KOTOR
Patch Manager's manifest and hooks syntax.

Used by tools/build_native_kpatch.py (KMRP's one patch), tools/build_runtime_kpatch.py
(the preview of 2026-10-03) and tools/check_kpm_overlaps.py. Until 2026-10-04 these
functions lived in tools/build_kpatch.py, the builder of the four-patch edition, which
was removed with that edition's last files.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import kmrp_controller                                  # noqa: E402

CD_1_03 = "761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886"
GOG = "9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435"
STEAM = "34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88"
VERSIONS = {"kotor1_cdcrack_103": CD_1_03, "kotor1_gog_103": GOG, "kotor1_steam_103": STEAM}


def toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def toml_list(values) -> str:
    return "[" + ", ".join(toml_string(v) for v in values) + "]"


def render_manifest(patch, version: str, resolutions: int) -> str:
    """A manifest.toml. `resolutions` fills a "{resolutions}" in the description, for
    a patch whose text names a count; pass 0 otherwise."""
    return "\n".join([
        "[patch]",
        f"id = {toml_string(patch['id'])}",
        f"name = {toml_string(patch['name'])}",
        f"version = {toml_string(version)}",
        'author = "RaymanGT"',
        f"description = {toml_string(patch['description'].format(resolutions=resolutions))}",
        f"requires = {toml_list(patch['requires'])}",
        f"conflicts = {toml_list(patch['conflicts'])}",
        "",
        "[patch.supported_versions]",
        *[f'{name} = "{sha}"' for name, sha in VERSIONS.items()],
        "",
    ])


def large_address_hook() -> dict:
    """The large-address flag as a KPM static hook, derived from the unmodified CD
    1.03 executable's own header: IMAGE_FILE_HEADER.Characteristics OR 0x0020, the
    one-bit change the standalone makes (reverse-engineering/large-address-aware.md).
    CD 1.03 and GOG, whose headers differ only in padding: Steam's header is elsewhere (its e_lfanew is 0x110), and Steam's DRM
    refuses to start an executable changed on disk."""
    site = json.loads((ROOT / 'src/engine/windows-sites.json').read_text())["large_address_hook"]
    field = int(site["file"], 16)
    original = list(bytes.fromhex(site["original"]))
    replacement = bytes.fromhex(site["replacement"])
    if (field, original, replacement) != (0x926, [0x0F, 0x01], b'\x2f\x01'):
        raise ValueError("Unexpected documented CD/GOG large-address hook")
    return {"address": 0x00400000 + field, "type": "static", "original_bytes": original,
            "replacement_bytes": list(replacement)}


def render_hooks(hooks, versions=(CD_1_03, GOG, STEAM),
                 source="src/controller-native/kotor1.hooks.toml; edit that file, not this one.") -> str:
    """A hooks file in KPM's syntax: integer addresses, integer byte lists."""
    lines = [
        f"# Generated from {source}",
        "[metadata]",
        "target_versions = [" + ", ".join(f'"{v}"' for v in versions) + "]",
    ]
    for hook in hooks:
        h = kmrp_controller.as_installed(hook)
        lines += ["", "[[hooks]]",
                  f"address = 0x{h['address']:08X}",
                  f"type = {toml_string(h['type'])}"]
        if "function" in h:
            lines.append(f"function = {toml_string(h['function'])}")
        lines.append("original_bytes = [" +
                     ", ".join(f"0x{b:02X}" for b in h["original_bytes"]) + "]")
        if "replacement_bytes" in h:
            lines.append("replacement_bytes = [" +
                         ", ".join(f"0x{b:02X}" for b in h["replacement_bytes"]) + "]")
        if h.get("skip_original_bytes"):
            lines.append("skip_original_bytes = true")
        if h.get("exclude_from_restore"):
            lines.append(f"exclude_from_restore = {toml_list(h['exclude_from_restore'])}")
        if "consumed_exit_address" in h:
            lines.append(f"consumed_exit_address = 0x{h['consumed_exit_address']:08X}")
        for p in h.get("parameters", []):
            lines += ["", "[[hooks.parameters]]",
                      f"source = {toml_string(p['source'])}",
                      f"type = {toml_string(p['type'])}"]
    return "\n".join(lines) + "\n"


def exports_of(dll: bytes) -> set:
    """Exported names of a PE DLL."""
    pe = struct.unpack_from("<I", dll, 0x3C)[0]
    optional = pe + 24
    export_rva = struct.unpack_from("<I", dll, optional + 96)[0]
    count = struct.unpack_from("<H", dll, pe + 6)[0]
    opt_size = struct.unpack_from("<H", dll, pe + 20)[0]
    sections = []
    for i in range(count):
        o = pe + 24 + opt_size + 40 * i
        vsize, va, rsize, raw = struct.unpack_from("<IIII", dll, o + 8)
        sections.append((va, max(vsize, rsize), raw))

    def at(rva):
        for va, size, raw in sections:
            if va <= rva < va + size:
                return raw + rva - va
        raise ValueError(hex(rva))

    base = at(export_rva)
    names = struct.unpack_from("<I", dll, base + 24)[0]
    table = at(struct.unpack_from("<I", dll, base + 32)[0])
    out = set()
    for i in range(names):
        start = at(struct.unpack_from("<I", dll, table + 4 * i)[0])
        end = dll.index(b"\0", start)
        out.add(dll[start:end].decode())
    return out
