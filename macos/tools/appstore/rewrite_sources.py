#!/usr/bin/env python3
"""Copy a source tree with every address of one build of KOTOR_Exe replaced by the other's.

    rewrite_sources.py <map.json> <from dir> <to dir> [<from KOTOR_Exe> <to KOTOR_Exe>]

Every literal 0x100...... (nine hex digits, with or without UL) in a .cpp, .h, .mm, .c or .inc
file that lies in a section of the first build is looked up (lookup.py). One that cannot be
translated stops the copy, listed with its file and line, unless it stands in a comment line.
Hook tables (.toml) are copied as they are: their addresses and bytes are translated from the
staged patch_config.toml instead (make_runtime.py).
"""
import re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from lookup import Map

PATTERN = re.compile(r"0x(100[0-9a-fA-F]{6})(?![0-9a-fA-F])")
CODE = {".cpp", ".h", ".mm", ".c", ".inc", ".hpp"}

def main():
    m = Map(sys.argv[1], *sys.argv[4:6]); src, dst = Path(sys.argv[2]), Path(sys.argv[3])
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)
    changed = kept = 0; failures = []; how = {}
    for path in sorted(dst.rglob("*")):
        if not path.is_file() or path.suffix not in CODE: continue
        lines = path.read_text(errors="surrogateescape").split("\n")
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
    print(f"{dst}: {changed} addresses translated ({', '.join(f'{k} {v}' for k, v in sorted(how.items()))}), {kept} left as they are (not in the image)")
    for failure in failures: print("  NOT TRANSLATED outside a comment:", failure)
    return 1 if failures else 0

if __name__ == "__main__": sys.exit(main())
