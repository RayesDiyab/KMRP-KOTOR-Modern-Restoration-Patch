"""Resolve game resources the way KotOR 1 does: Override, then the loaded module, then chitin.

Origin: the lookup order and module handling come from the research scratchpad's
ncsscan.py (collect) and classify.py (effective), 2026-10-22. Rewritten here as one
class with caching. Read only: it never writes into the game folder.

Module rule: when modules/<name>.mod exists the game loads it instead of
<name>.rim and <name>_s.rim (K1 Community Patch ships whole modules as .mod).
"""
import os

import kfmt


class Game:
    def __init__(self, root):
        self.root = root
        self.keys = kfmt.key_lookup(root)
        self.bifs = kfmt.BifCache(root)
        self.tlk = kfmt.tlk_reader(root)
        od = None
        for cand in ("Override", "override"):
            p = os.path.join(root, cand)
            if os.path.isdir(p):
                od = p
                break
        self.override = {}
        ext = {"ncs": kfmt.T_NCS, "dlg": kfmt.T_DLG, "jrl": kfmt.T_JRL, "uti": kfmt.T_UTI,
               "utc": kfmt.T_UTC, "utp": kfmt.T_UTP, "utd": kfmt.T_UTD, "utt": kfmt.T_UTT,
               "nss": kfmt.T_NSS, "git": kfmt.T_GIT, "are": kfmt.T_ARE, "ifo": kfmt.T_IFO,
               "2da": kfmt.T_2DA, "uts": kfmt.T_UTS}
        if od:
            for f in os.listdir(od):
                if "." not in f:
                    continue
                stem, e = f.lower().rsplit(".", 1)
                if e in ext:
                    self.override[(stem, ext[e])] = os.path.join(od, f)
        self.moddir = os.path.join(root, "modules")
        self.modfiles = {f.lower(): os.path.join(self.moddir, f) for f in os.listdir(self.moddir)}
        self._mods = {}
        self._gff = {}

    # ------------------------------------------------------------ modules
    def module_names(self):
        out = set()
        for f in self.modfiles:
            if f.endswith(".mod") or f.endswith(".rim") or f.endswith("_dlg.erf"):
                m = f.rsplit(".", 1)[0]
                if m.endswith("_s"):
                    m = m[:-2]
                if m.endswith("_dlg"):
                    m = m[:-4]
                if m.endswith("_loc"):  # KotOR 2's lip-sync archives, not modules
                    continue
                out.add(m)
        return sorted(out)

    def module_source(self, module):
        """Which archive files the game loads for this module."""
        # KotOR 2 keeps a module's conversations apart in <name>_dlg.erf (added 2026-10-23).
        if module + ".mod" in self.modfiles:
            return [module + ".mod"]
        return [f for f in (module + ".rim", module + "_s.rim", module + "_dlg.erf") if f in self.modfiles]

    def module(self, module):
        """{(resref, type): bytes} for the module as the game loads it."""
        if module not in self._mods:
            res = {}
            for f in self.module_source(module):
                for n, t, d in kfmt.archive_entries(self.modfiles[f]):
                    res.setdefault((n.lower(), t), d)
            self._mods[module] = res
        return self._mods[module]

    # ------------------------------------------------------------ lookup
    def get(self, resref, rtype, module=None):
        """Bytes of a resource and where it came from, or (None, None)."""
        key = (resref.lower(), rtype)
        if key in self.override:
            with open(self.override[key], "rb") as f:
                return f.read(), "Override"
        if module:
            m = self.module(module)
            if key in m:
                return m[key], "modules/" + self.module_source(module)[0]
        if key in self.keys:
            bif, idx = self.keys[key]
            return self.bifs.read(bif, idx), "chitin:" + os.path.basename(bif)
        return None, None

    def gff(self, resref, rtype, module=None):
        """Parsed GFF root struct (cached) or None."""
        data, src = self.get(resref, rtype, module)
        if data is None:
            return None
        ck = (resref.lower(), rtype, src)
        if ck not in self._gff:
            self._gff[ck] = kfmt.gff(data)[1]
        return self._gff[ck]

    def chitin_names(self, rtype):
        return sorted(n for (n, t) in self.keys if t == rtype)

    def text(self, v):
        return kfmt.locstr(v, self.tlk)
