"""Readers for the KotOR file formats the quest database needs.

Origin: cleaned copy of the research scratchpad's kfmt.py (2026-10-22), which read
ERF/MOD, RIM, GFF, KEY and BIF. Added here: TLK reading (from the scratchpad's
ncsscan.py) and a small GFF struct helper. Nothing here writes game files.

All formats are little-endian. Layouts follow the BioWare Aurora format documents
as they apply to KotOR 1.
"""
import os
import struct

# Resource type numbers used by the quest database.
T_ARE, T_IFO, T_GIT = 2012, 2014, 2023
T_UTI, T_UTC, T_DLG = 2025, 2027, 2029
T_UTT, T_UTS, T_UTD, T_UTP = 2032, 2035, 2042, 2044
T_NSS, T_NCS, T_JRL = 2009, 2010, 2056


def erf_entries(data):
    """ERF / MOD: list of (resref, type, bytes)."""
    nent = struct.unpack_from("<I", data, 16)[0]
    off_keys = struct.unpack_from("<I", data, 24)[0]
    off_res = struct.unpack_from("<I", data, 28)[0]
    out = []
    for i in range(nent):
        kb = off_keys + i * 24
        name = data[kb:kb + 16].split(b"\0")[0].decode("latin-1")
        _rid, rtype = struct.unpack_from("<IH", data, kb + 16)
        o, s = struct.unpack_from("<II", data, off_res + i * 8)
        out.append((name, rtype, data[o:o + s]))
    return out


def rim_entries(data):
    """RIM: list of (resref, type, bytes)."""
    n = struct.unpack_from("<I", data, 12)[0]
    off = struct.unpack_from("<I", data, 16)[0]
    out = []
    for i in range(n):
        b = off + i * 32
        name = data[b:b + 16].split(b"\0")[0].decode("latin-1")
        rtype, _rid, o, s = struct.unpack_from("<IIII", data, b + 16)
        out.append((name, rtype, data[o:o + s]))
    return out


def archive_entries(path):
    with open(path, "rb") as f:
        d = f.read()
    return rim_entries(d) if d[:4] == b"RIM " else erf_entries(d)


class S:
    """One GFF struct: id and an ordered list of (label, type name, value)."""

    def __init__(self, sid):
        self.id = sid
        self.f = []

    def get(self, label, default=None):
        for a, _t, v in self.f:
            if a == label:
                return v
        return default

    def __repr__(self):
        return "S(%d)" % self.id


TYPES = {0: "BYTE", 1: "CHAR", 2: "WORD", 3: "SHORT", 4: "DWORD", 5: "INT", 6: "DWORD64", 7: "INT64",
         8: "FLOAT", 9: "DOUBLE", 10: "CExoString", 11: "ResRef", 12: "CExoLocString", 13: "VOID",
         14: "Struct", 15: "List", 16: "Orientation", 17: "Vector", 18: "StrRef"}


def gff(data):
    """Parse a GFF file. Returns (file type, root struct).

    CExoLocString values come back as ("locstr", strref, [(substring id, text), ...]).
    """
    ft = data[:4].decode("latin-1")
    so, sc, fo, fc, lo, lc, fdo, fdc, fio, fic, lio, lic = struct.unpack_from("<12I", data, 8)
    labels = [data[lo + i * 16: lo + i * 16 + 16].split(b"\0")[0].decode("latin-1") for i in range(lc)]

    def field(i):
        t, li, d = struct.unpack_from("<III", data, fo + i * 12)
        fd = fdo + d
        if t == 0:
            v = d & 0xff
        elif t == 1:
            v = struct.unpack("<b", struct.pack("<B", d & 0xff))[0]
        elif t == 2:
            v = d & 0xffff
        elif t == 3:
            v = struct.unpack("<h", struct.pack("<H", d & 0xffff))[0]
        elif t == 4:
            v = d
        elif t == 5:
            v = struct.unpack("<i", struct.pack("<I", d))[0]
        elif t == 8:
            v = struct.unpack("<f", struct.pack("<I", d))[0]
        elif t == 6:
            v = struct.unpack_from("<Q", data, fd)[0]
        elif t == 7:
            v = struct.unpack_from("<q", data, fd)[0]
        elif t == 9:
            v = struct.unpack_from("<d", data, fd)[0]
        elif t == 10:
            n = struct.unpack_from("<I", data, fd)[0]
            v = data[fd + 4: fd + 4 + n].decode("latin-1")
        elif t == 11:
            n = data[fd]
            v = data[fd + 1: fd + 1 + n].decode("latin-1")
        elif t == 12:
            _tot, strref, cnt = struct.unpack_from("<IiI", data, fd)
            p = fd + 12
            subs = []
            for _ in range(cnt):
                sid, n = struct.unpack_from("<II", data, p)
                subs.append((sid, data[p + 8:p + 8 + n].decode("latin-1")))
                p += 8 + n
            v = ("locstr", strref, subs)
        elif t == 13:
            n = struct.unpack_from("<I", data, fd)[0]
            v = ("void", n)
        elif t == 14:
            v = st(d)
        elif t == 15:
            p = lio + d
            n = struct.unpack_from("<I", data, p)[0]
            v = [st(x) for x in struct.unpack_from("<%dI" % n, data, p + 4)]
        elif t == 16:
            v = struct.unpack_from("<4f", data, fd)
        elif t == 17:
            v = struct.unpack_from("<3f", data, fd)
        else:
            v = ("?", d)
        return (labels[li], TYPES.get(t, str(t)), v)

    def st(i):
        sid, d, c = struct.unpack_from("<III", data, so + i * 12)
        s = S(sid)
        if c == 1:
            s.f.append(field(d))
        elif c > 1:
            for k in struct.unpack_from("<%dI" % c, data, fio + d):
                s.f.append(field(k))
        return s

    return ft, st(0)


def key_lookup(root):
    """chitin.key: {(resref lower, type): (bif relative path, index in bif)}."""
    with open(os.path.join(root, "chitin.key"), "rb") as f:
        data = f.read()
    bc, kc, ofb, ofk = struct.unpack_from("<IIII", data, 8)
    bifs = []
    for i in range(bc):
        _size, noff, nlen, _drives = struct.unpack_from("<IIHH", data, ofb + i * 12)
        bifs.append(data[noff:noff + nlen].split(b"\0")[0].decode("latin-1").replace(chr(92), "/"))
    keys = {}
    for i in range(kc):
        b = ofk + i * 22
        name = data[b:b + 16].split(b"\0")[0].decode("latin-1").lower()
        rtype, rid = struct.unpack_from("<HI", data, b + 16)
        keys[(name, rtype)] = (bifs[rid >> 20], rid & 0xfffff)
    return keys


class BifCache:
    def __init__(self, root):
        self.root = root
        self.cache = {}

    def read(self, bif, idx):
        if bif not in self.cache:
            with open(os.path.join(self.root, bif), "rb") as f:
                d = f.read()
            vc, _fc, vo = struct.unpack_from("<III", d, 8)
            m = {}
            for i in range(vc):
                rid, off, size, _typ = struct.unpack_from("<IIII", d, vo + i * 16)
                m[rid & 0xfffff] = (off, size)
            self.cache[bif] = (d, m)
        d, m = self.cache[bif]
        off, size = m[idx]
        return d[off:off + size]


def tlk_reader(root):
    """dialog.tlk: returns get(strref) -> text ("" when out of range)."""
    with open(os.path.join(root, "dialog.tlk"), "rb") as f:
        d = f.read()
    _lang, cnt, off = struct.unpack_from("<III", d, 8)

    def get(i):
        if i is None or i < 0 or i >= cnt:
            return ""
        b = 20 + i * 40
        o, s = struct.unpack_from("<II", d, b + 28)
        return d[off + o: off + o + s].decode("latin-1")
    return get


T_2DA = 2017


def twoda(data):
    """Binary 2DA V2.b: (column names, [(row label, {column: cell text})])."""
    if data[:8] != b"2DA V2.b":
        raise ValueError("not a binary 2DA")
    p = 9
    end = data.index(b"\0", p)
    cols = [c for c in data[p:end].decode("latin-1").split("\t") if c]
    p = end + 1
    nrows = struct.unpack_from("<I", data, p)[0]
    p += 4
    labels = []
    for _ in range(nrows):
        e = data.index(b"\t", p)
        labels.append(data[p:e].decode("latin-1"))
        p = e + 1
    ncell = nrows * len(cols)
    offs = struct.unpack_from("<%dH" % ncell, data, p)
    p += 2 * ncell + 2
    rows = []
    for r in range(nrows):
        cells = {}
        for ci, cn in enumerate(cols):
            o = p + offs[r * len(cols) + ci]
            cells[cn] = data[o:data.index(b"\0", o)].decode("latin-1")
        rows.append((labels[r], cells))
    return cols, rows


def locstr(v, tlk):
    """Text of a CExoLocString: the embedded English substring, else the TLK entry."""
    if isinstance(v, tuple) and v and v[0] == "locstr":
        for sid, text in v[2]:
            if sid in (0, 1) and text:
                return text
        return tlk(v[1])
    return v or ""
