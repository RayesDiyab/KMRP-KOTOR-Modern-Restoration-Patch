#!/usr/bin/env python3
"""Copy a source tree with every address of one build of KOTOR_Exe replaced by the other's.

    rewrite_sources.py <map.json> <from dir> <to dir> [<from KOTOR_Exe> <to KOTOR_Exe>]

Every literal 0x100...... (nine hex digits, with or without UL) in a .cpp, .h, .mm, .c or .inc
file that lies in a section of the first build is looked up (lookup.py). One that cannot be
translated stops the copy, listed with its file and line, unless it stands in a comment line.
Hook tables (.toml) are copied as they are: their addresses and bytes are translated from the
staged patch_config.toml instead (make_runtime.py).

Machine code written out as bytes holds addresses no literal shows: FTD's widescreen patch
writes stubs and 5-byte calls as arrays (`uint8_t callFit[5] = { 0xe8, 0x2b, 0xe5, 0xde, 0xff };
writeMemBytes(0x100306a88, callFit, 5);`), where the four bytes are the distance from that
site to a stub in Steam's build. The site and the stub do not move by the same amount in the
other build (0x5600 and 0x5640 here), so the call as written landed 0x40 short of its stub, in
the padding before a routine of OpenSSL's, and ran into it: the App Store's game ended at the
first message box (Load Game with no saves) and would have at the first dialogue (found
2026-10-12, docs/macos-app-store.md, section 7.6). So, before the literals: in every byte
array that is written to a literal address (`writeMem...(0x100......, <name>`), a call or jump
(e8, e9, 0f 8x) whose target is in the first build's image is given the distance between the
translated site and the translated target, and eight bytes that are an address of the image
are given the translated address. One that cannot be translated stops the copy. An array with
a call or jump in it and no literal address to be written to is listed, not changed: its
distance is worked out when it runs, or it is compared and not written.
"""
import re, shutil, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from lookup import Map

PATTERN = re.compile(r"0x(100[0-9a-fA-F]{6})(?![0-9a-fA-F])")
CODE = {".cpp", ".h", ".mm", ".c", ".inc", ".hpp"}

ARRAY = re.compile(r"(\w+)\s*\[\s*\d*\s*\]\s*=\s*\{([^{};]*)\}")
NUMBER = re.compile(r"0[xX][0-9a-fA-F]+|\d+")

def blank_comments(text):
    """The text with // and /* */ comments turned to spaces: the same length, the same lines."""
    keep = lambda match: re.sub(r"[^\n]", " ", match.group(0))
    return re.sub(r"//[^\n]*|/\*.*?\*/", keep, text, flags=re.S)

def rewrite_byte_arrays(m, text, where, failures, notes):
    """Calls, jumps and addresses inside byte arrays written to literal addresses, translated."""
    bare = blank_comments(text); edits = []; count = 0
    for array in ARRAY.finditer(bare):
        name = array.group(1); tokens = list(NUMBER.finditer(array.group(2)))
        if len(tokens) < 5 or NUMBER.sub("", array.group(2)).strip(" ,\n\t\r"): continue   # not a plain list of numbers
        values = [int(token.group(0), 0) for token in tokens]
        if any(value > 0xff for value in values): continue
        data = bytes(values); line = bare.count("\n", 0, array.start()) + 1
        written = re.search(r"writeMem\w*\(\s*0x(100[0-9a-fA-F]{6})\s*,\s*" + re.escape(name) + r"\b", bare[array.end():array.end() + 1200])
        new = bytearray(data)
        for i in range(len(data) - 7):
            value = struct.unpack_from("<Q", data, i)[0]
            if m.section(value) == "?": continue
            to, kind = m.to(value)
            if to is None: failures.append(f"{where}:{line}: {name}[{i}], the address {value:#x} in bytes ({kind})"); continue
            struct.pack_into("<Q", new, i, to); count += 1
        branches = [i for i in range(len(data) - 4) if data[i] in (0xe8, 0xe9) or (i and data[i - 1] == 0x0f and 0x80 <= data[i] <= 0x8f)]
        if not written:
            if any(struct.unpack_from("<i", data, i + 1)[0] for i in branches):
                notes.append(f"{where}:{line}: {name} has a call or jump and is not written to a literal address: left as it is")
        else:
            site = int(written.group(1), 16); site_to, kind = m.to(site)
            for i in branches:
                target = site + i + 5 + struct.unpack_from("<i", data, i + 1)[0]
                if m.section(target) == "?": continue
                target_to, kind = m.to(target)
                if site_to is None or target_to is None:
                    failures.append(f"{where}:{line}: {name}[{i}], the branch from {site + i:#x} to {target:#x} ({kind})"); continue
                struct.pack_into("<i", new, i + 1, target_to - (site_to + i + 5)); count += 1
        base = array.start(2)
        for i, token in enumerate(tokens):
            if new[i] != data[i]: edits.append((base + token.start(), base + token.end(), f"0x{new[i]:02x}"))
    for start, end, replacement in sorted(edits, reverse=True): text = text[:start] + replacement + text[end:]
    return text, count

def main():
    m = Map(sys.argv[1], *sys.argv[4:6]); src, dst = Path(sys.argv[2]), Path(sys.argv[3])
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)
    changed = kept = encoded = 0; failures = []; how = {}; notes = []
    for path in sorted(dst.rglob("*")):
        if not path.is_file() or path.suffix not in CODE: continue
        text, count = rewrite_byte_arrays(m, path.read_text(errors="surrogateescape"), path.relative_to(dst), failures, notes)
        encoded += count
        lines = text.split("\n")
        for n, line in enumerate(lines):
            comment = line.lstrip().startswith(("//", "*", "/*", "#"))
            def replace(match):
                nonlocal changed, kept
                a = int(match.group(1), 16)
                if m.section(a) == "?":
                    kept += 1; return match.group(0)       # not an address of the image (a base, a mask)
                to, kind = m.to(a)
                if to is None:
                    if not comment: failures.append(f"{path.relative_to(dst)}:{n + 1}: {a:#x} ({kind})")
                    return match.group(0)
                changed += 1; how[kind] = how.get(kind, 0) + 1
                digits = match.group(1)
                return "0x" + (f"{to:x}" if digits.islower() or not any(c.isalpha() for c in digits) else f"{to:X}")
            lines[n] = PATTERN.sub(replace, line)
        path.write_text("\n".join(lines), errors="surrogateescape")
    print(f"{dst}: {changed} addresses translated ({', '.join(f'{k} {v}' for k, v in sorted(how.items()))}), {kept} left as they are (not in the image), {encoded} calls, jumps and addresses inside byte arrays")
    for note in notes: print("  note:", note)
    for failure in failures: print("  NOT TRANSLATED outside a comment:", failure)
    return 1 if failures else 0

if __name__ == "__main__": sys.exit(main())
