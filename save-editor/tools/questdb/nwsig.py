"""Read nwscript.nss into the ordered engine routine table (index = ACTION routine number).

Origin: the research scratchpad's nwsig.py (2026-10-22). Changed here: parameters are
split only on top-level commas, so a default such as [0.0,0.0,0.0] stays one parameter,
and integer constants are read as well.
"""
import re

TYPES = r"(?:void|int|float|string|object|location|vector|effect|event|talent|action|itemproperty)"


def _strip(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _split_args(args):
    out, depth, cur = [], 0, ""
    for ch in args:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [a.strip() for a in out if a.strip()]


def parse(text):
    """List of (name, return type, [(param type, param name)])."""
    src = _strip(text)
    out = []
    pat = re.compile(r"^\s*(" + TYPES + r")\s+(\w+)\s*\(([^;{]*)\)\s*;", re.M)
    for m in pat.finditer(src):
        ret, name, args = m.groups()
        params = []
        for a in _split_args(args):
            a = a.split("=")[0].strip()
            parts = a.split()
            params.append((parts[0], parts[-1]))
        out.append((name, ret, params))
    return out


def constants(text):
    """{name: int value} for the integer constants."""
    src = _strip(text)
    out = {}
    for m in re.finditer(r"^\s*int\s+(\w+)\s*=\s*(-?(?:0x[0-9A-Fa-f]+|\d+))\s*;", src, re.M):
        out[m.group(1)] = int(m.group(2), 0)
    return out
