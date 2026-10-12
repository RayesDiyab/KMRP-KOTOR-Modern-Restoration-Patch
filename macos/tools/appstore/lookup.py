"""Look an address of the first build up in a map made by translate.py.

    Map(path).to(address) -> (address in the second build, how) or (None, why not)

how: "code" an anchored instruction; "weak" an instruction mapped by position between two
anchored ones; "inside" a byte inside a mapped instruction, at the same offset; "target" what
an anchored instruction names (data, or a function it calls); "between" data between two
targets that moved by the same amount, within 64 bytes, or 1024 in a __DATA section (tables
of pointers follow one another there); "content" data within 64 bytes of one target, with the
128 bytes around it the same in both files at that target's distance (needs both files).
"""
import bisect, json
from pathlib import Path

class Map:
    def __init__(self, path, from_exe=None, to_exe=None):
        m = json.loads(Path(path).read_text())
        self.a = Path(from_exe).read_bytes() if from_exe else None
        self.b = Path(to_exe).read_bytes() if to_exe else None
        self.code = {int(k, 16): (int(v[0], 16), v[1], v[2]) for k, v in m["code"].items()}
        self.data = {int(k, 16): int(v[0], 16) for k, v in m["data"].items()}
        self.starts = sorted(self.code)
        self.targets = sorted(self.data)
        self.sections = m["from"]["sections"]
        self.to_sections = m["to"]["sections"]

    def section(self, a, which=None):
        for name, (addr, size, _) in (which or self.sections).items():
            if addr <= a < addr + size: return name
        return "?"

    def to(self, a):
        if a in self.code:
            to, _, weak = self.code[a]
            return to, "weak" if weak else "code"
        if a in self.data:
            return self.data[a], "target"
        i = bisect.bisect_right(self.starts, a) - 1
        if i >= 0:
            start = self.starts[i]; to, size, weak = self.code[start]
            if start < a < start + size:
                return to + (a - start), "inside"
        if self.section(a) != "__TEXT,__text":
            i = bisect.bisect_right(self.targets, a)
            lo = self.targets[i - 1] if i > 0 else None
            hi = self.targets[i] if i < len(self.targets) else None
            reach = 1024 if self.section(a).startswith("__DATA,") else 64
            if lo is not None and hi is not None and a - lo <= reach and hi - a <= reach:
                d = self.data[lo] - lo
                if self.data[hi] - hi == d and self.section(lo) == self.section(hi) == self.section(a):
                    return a + d, "between"
            if self.a and self.b:
                for near in (lo, hi):
                    if near is None or abs(a - near) > 64 or self.section(near) != self.section(a):
                        continue
                    d = self.data[near] - near
                    start = a - 64 - 0x100000000
                    if start + d >= 0 and self.a[start:start + 128] == self.b[start + d:start + d + 128]:
                        return a + d, "content"
            return None, "no anchored instruction names it or its neighbours"
        return None, "in code the two builds do not share, or share in a form not recognised"
