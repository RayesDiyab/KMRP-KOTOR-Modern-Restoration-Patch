"""Setter discovery and step building for build.py.

Origin: setter discovery follows the research scratchpad's questmap.py (which scripts
and dialog nodes set each journal stage); the dialog neighbourhood (parent, node, two
levels of children) follows dlgnear.py. Path conditions, branch splitting, owners and
script references are new here.
"""
import collections
import json

import kfmt
import nodescript
import ncsvm

render = ncsvm.render
GFF_TYPES = (kfmt.T_UTC, kfmt.T_UTP, kfmt.T_UTD, kfmt.T_UTT, kfmt.T_UTS, kfmt.T_GIT, kfmt.T_ARE, kfmt.T_IFO)
EXT = {kfmt.T_UTC: "utc", kfmt.T_UTP: "utp", kfmt.T_UTD: "utd", kfmt.T_UTT: "utt", kfmt.T_UTS: "uts",
       kfmt.T_GIT: "git", kfmt.T_ARE: "are", kfmt.T_IFO: "ifo", kfmt.T_DLG: "dlg"}


def short(text, words=12):
    t = " ".join((text or "").split())
    w = t.split(" ")
    return t if len(w) <= words else " ".join(w[:words]) + " ..."


class Dialog:
    def __init__(self, root):
        self.root = root
        self.E = root.get("EntryList") or []
        self.R = root.get("ReplyList") or []
        self.starts = [(x.get("Index"), nodescript.link_condition(x)) for x in root.get("StartingList") or []]
        self.parents = collections.defaultdict(list)
        for k in ("E", "R"):
            for i in range(len(self.nodes(k))):
                for k2, j, act in self.children(k, i):
                    self.parents[(k2, j)].append((k, i, act))

    def nodes(self, k):
        return self.E if k == "E" else self.R

    def node(self, k, i):
        return self.nodes(k)[i]

    def children(self, k, i, own_only=False):
        """Linked nodes. own_only skips IsChild links (pointers to a node that belongs to
        another branch, usually a jump back to the conversation's menu)."""
        n = self.node(k, i)
        lst = n.get("RepliesList" if k == "E" else "EntriesList") or []
        k2 = "R" if k == "E" else "E"
        return [(k2, l.get("Index"), nodescript.link_condition(l)) for l in lst
                if not (own_only and l.get("IsChild"))]

    def path_to(self, k, i):
        """Shortest path from a start: [(kind, index, Active script on the link into it)]."""
        prev = {}
        q = collections.deque()
        for idx, act in self.starts:
            if ("E", idx) not in prev:
                prev[("E", idx)] = (None, act)
                q.append(("E", idx))
        while q:
            cur = q.popleft()
            if cur == (k, i):
                out = []
                while cur is not None:
                    p, act = prev[cur]
                    out.append((cur[0], cur[1], act))
                    cur = p
                return list(reversed(out))
            for k2, j, act in self.children(*cur):
                if (k2, j) not in prev:
                    prev[(k2, j)] = (cur, act)
                    q.append((k2, j))
        return None


class Chains:
    def __init__(self, b):
        self.b = b
        self.g = b.g
        self.dlg_cache = {}
        self.refs = None

    # ------------------------------------------------------------ resources
    def dialog(self, name, module):
        key = (name, module)
        if key not in self.dlg_cache:
            r = self.g.gff(name, kfmt.T_DLG, module)
            self.dlg_cache[key] = Dialog(r) if r is not None else None
        return self.dlg_cache[key]

    def module_dialog_names(self, module):
        names = {n for (n, t) in self.g.module(module) if t == kfmt.T_DLG}
        for (n, t) in list(self.g.module(module)):
            if t in (kfmt.T_UTC, kfmt.T_UTP, kfmt.T_UTD):
                r = self.g.gff(n, t, module)
                c = (r.get("Conversation") or "").lower() if r is not None else ""
                if c:
                    names.add(c)
        names |= self.extra_names(module, kfmt.T_DLG, getattr(self.b, "extra_dialogs", None))
        return sorted(names)

    def module_script_names(self, module):
        names = {n for (n, t) in self.g.module(module) if t == kfmt.T_NCS}
        names |= {n for (n, t) in self.g.override if t == kfmt.T_NCS}
        names |= self.extra_names(module, kfmt.T_NCS, getattr(self.b, "extra_scripts", None))
        return sorted(names)

    def extra_names(self, module, rtype, pattern):
        """Resources outside the module archives that the planet scans with its first module
        (PLANETS extra_dialogs / extra_scripts in build.py)."""
        if not pattern or not self.b.modules or module != self.b.modules[0]:
            return set()
        import re
        rx = re.compile(pattern, re.I)
        names = {n for n in self.g.chitin_names(rtype) if rx.search(n)}
        names |= {n for (n, t) in self.g.override if t == rtype and rx.search(n)}
        return names

    # ------------------------------------------------------------ discovery
    def discover(self, tags):
        """Setters of (tag, stage) in the planet's modules and outside them."""
        dsets = collections.defaultdict(list)   # (tag, stage) -> [(dlg, module, kind, idx)]
        ssets = collections.defaultdict(list)   # (tag, stage) -> [(script, module)]
        tagb = [t.encode("latin-1") for t in tags]
        # A dialog or script that lives outside the module archives (chitin, Override-only)
        # runs anywhere, so it only counts for this planet's own quest tags.
        def counts(tag, src):
            return self.b.owns_tag(tag) or (src or "").startswith("modules/")

        for m in self.b.modules:
            for dn in self.module_dialog_names(m):
                d = self.dialog(dn, m)
                if d is None:
                    continue
                _data, dsrc = self.g.get(dn, kfmt.T_DLG, m)
                if dsrc == "Override" and (dn, kfmt.T_DLG) in self.g.module(m):
                    dsrc = "modules/override-copy"
                for k in ("E", "R"):
                    for i, n in enumerate(d.nodes(k)):
                        q = (n.get("Quest") or "").lower()
                        if q in tags and counts(q, dsrc):
                            dsets[(q, n.get("QuestEntry"))].append((dn, m, k, i))
            for sn in self.module_script_names(m):
                data, ssrc = self.g.get(sn, kfmt.T_NCS, m)
                if data is None:
                    continue
                if ssrc == "Override" and (sn, kfmt.T_NCS) in self.g.module(m):
                    ssrc = "modules/override-copy"
                low = data.lower()
                if not any(t in low for t in tagb):
                    continue
                paths, _tr, _s = self.b.script(sn, m)
                for p in paths or []:
                    for c in p.calls:
                        if c[0] == "AddJournalQuestEntry" and len(c[1]) >= 2 and isinstance(c[1][0], str) \
                                and isinstance(c[1][1], int) and c[1][0].lower() in tags \
                                and counts(c[1][0].lower(), ssrc):
                            key = (c[1][0].lower(), c[1][1])
                            if (sn, m) not in ssets[key]:
                                ssets[key].append((sn, m))
        return dsets, ssets

    def script_refs(self, names):
        """{script: [(module, resource, where, owner tag)]} for the planet's modules."""
        names = set(names)
        refs = collections.defaultdict(list)
        for m in self.b.modules:
            for (n, t) in list(self.g.module(m)):
                if t not in GFF_TYPES:
                    continue
                data, _src = self.g.get(n, t, m)
                low = data.lower()
                if not any(s.encode("latin-1") in low for s in names):
                    continue
                r = kfmt.gff(data)[1]
                owner = r.get("Tag") if t in (kfmt.T_UTC, kfmt.T_UTP, kfmt.T_UTD, kfmt.T_UTT) else None
                for label, val, ctx_owner in walk_strings(r, owner):
                    if isinstance(val, str) and val.lower() in names:
                        refs[val.lower()].append((m, "%s.%s" % (n, EXT[t]), label, ctx_owner))
            for dn in self.module_dialog_names(m):
                d = self.dialog(dn, m)
                if d is None:
                    continue
                for k in ("E", "R"):
                    for i, nd in enumerate(d.nodes(k)):
                        for s in nodescript.node_scripts(nd):
                            if s in names or s.split("|")[0] in names:
                                refs[s.split("|")[0]].append((m, dn + ".dlg", "node %s%d" % (k, i), None))
        return refs

    def scripts_naming(self, name, module):
        """Scripts in the module whose bytes contain the name (for example a dialog they start)."""
        nb = name.encode("latin-1")
        out = []
        for sn in self.module_script_names(module):
            data, _src = self.g.get(sn, kfmt.T_NCS, module)
            if data is not None and nb in data.lower():
                out.append(sn)
        return out

    # ------------------------------------------------------------ owners
    def owner(self, dlg, module):
        own = self.b.dialog_owner(dlg, module)
        tags = sorted({o[0] for o in own})
        # A person speaks a dialog that a door also uses as its "locked" bark (end_trask01 on
        # the Endar Spire belongs to Trask and to end_door02): prefer the creature.
        people = sorted({o[0] for o in own if o[2] == kfmt.T_UTC})
        first = people[0] if people else (tags[0] if tags else None)
        return first, tags

    # ------------------------------------------------------------ node effects
    def node_variants(self, d, k, i, module, owner):
        """[(label, needs, does, leftovers)] for one dialog node: plot XP and its Script."""
        n = d.node(k, i)
        base = []
        xp = self.b.plot_xp_index(n.get("PlotIndex"), n.get("PlotXPPercentage"))
        if xp:
            base.append({"xp": xp})
        keys = nodescript.node_scripts(n)
        if not keys:
            return [(None, [], base, [])], False
        out, trunc = [(None, [], base, [])], False
        # KotOR 2: Script then Script2, each with its own parameters; their variants combine
        for sc in keys:
            vs, tr = self.b.script_variants(sc, module, owner)
            trunc |= tr
            if vs is None:
                out = [(lab, nd, does + [{"other": "runs script %s, which was not found" % sc.split("|")[0]}], left)
                       for lab, nd, does, left in out]
                continue
            if not vs:
                continue
            out = [((" / ".join(x for x in (lab0, lab) if x) or None), nd0 + nd, does0 + does, left0 + left)
                   for lab0, nd0, does0, left0 in out for lab, nd, does, left in vs]
        return out, trunc

    def link_needs(self, act, module, notes):
        if not act:
            return []
        if self.g.get(act, kfmt.T_NCS, module)[0] is None:
            notes.append("UNC:the condition script %s on a dialog link does not exist in the game files; "
                         "whether the engine then offers the line was not measured" % act)
            return []
        needs, left, note = self.b.conditional(act, module)
        if note:
            notes.append(note)
        left = [x for x in clean_left(left) if "helper function" not in x]
        if left:
            notes.append("condition %s also tests: %s" % (act, "; ".join(left[:4])))
        return list(needs)

    def label(self, d, k, i):
        # IDs only, never the game's text (KMRP rule, 2026-10-23): the editor shows the line
        # from the player's own game by its node number.
        n = d.node(k, i)
        empty = not self.g.text(n.get("Text")).strip()
        if k == "R":
            return "reply R%d" % i + (" (empty: [continue])" if empty else "")
        return "line E%d" % i + (" (empty)" if empty else "")

    def dialog_steps(self, tag, stage, dn, module, k, i):
        """Steps for one dialog node that sets (tag, stage): (steps, notes, uncertain)."""
        notes, unc = [], []
        d = self.dialog(dn, module)
        owner, owners = self.owner(dn, module)
        if len(owners) > 1:
            notes.append("dialog %s is used by several objects in %s: %s" % (dn, module, ", ".join(owners)))
        if owner is None:
            starters = self.scripts_naming(dn, module)
            unc.append("no creature, placeable or door template in %s names dialog %s, so its speaker is unknown%s"
                       % (module, dn, ("; scripts that name it: " + ", ".join(starters[:4])) if starters else ""))
        node = d.node(k, i)
        speaker = (node.get("Speaker") or "") if k == "E" else ""
        speaker = speaker or owner or ""
        via = {"dialog": dn, "node": i, "speaker": speaker, "list": "entry" if k == "E" else "reply"}
        path = d.path_to(k, i)
        needs = []
        if path is None:
            unc.append("%s %s%d cannot be reached from the dialog's start in the files" % (dn, k, i))
        else:
            for pk, pi, act in path:
                needs += self.link_needs(act, module, notes)
        main_does = []
        extra = []
        trunc = False
        # parent on the path: its script runs just before this node
        if path and len(path) >= 2:
            pk, pi, _a = path[-2]
            pn = d.node(pk, pi)
            if not (pn.get("Quest") or ""):
                vs, tr = self.node_variants(d, pk, pi, module, owner)
                trunc |= tr
                if len(vs) == 1:
                    main_does += vs[0][2]
                    needs += vs[0][1]
                else:
                    for lab, nd, does, left in vs:
                        extra.append(("before this line: " + (lab or "variant"), nd, does))
        if len(d.parents[(k, i)]) > 1:
            notes.append("%s %s%d can be reached from %d places; needs follow the shortest path"
                         % (dn, k, i, len(d.parents[(k, i)])))
        main_does.append({"journal": [node.get("Quest"), stage]})
        vs, tr = self.node_variants(d, k, i, module, owner)
        trunc |= tr
        if len(vs) == 1:
            main_does += vs[0][2]
            needs += vs[0][1]
        else:
            for lab, nd, does, left in vs:
                extra.append((lab or "variant", nd, does))
        # children, two levels
        options = []
        for k2, j, act in d.children(k, i, own_only=True):
            cn = d.node(k2, j)
            cneeds = self.link_needs(act, module, notes)
            clabel = self.label(d, k2, j)
            if (cn.get("Quest") or ""):
                options.append((clabel + " (goes on to %s stage %s)" % (cn.get("Quest"), cn.get("QuestEntry")), cneeds, []))
                continue
            cvs, tr = self.node_variants(d, k2, j, module, owner)
            trunc |= tr
            grand = d.children(k2, j, own_only=True)
            sub = []
            for k3, h, act3 in grand:
                gn = d.node(k3, h)
                gneeds = self.link_needs(act3, module, notes)
                glabel = self.label(d, k3, h)
                if (gn.get("Quest") or ""):
                    sub.append((glabel + " (goes on to %s stage %s)" % (gn.get("Quest"), gn.get("QuestEntry")), gneeds, [(None, [], [], [])]))
                    continue
                gvs, tr = self.node_variants(d, k3, h, module, owner)
                trunc |= tr
                sub.append((glabel, gneeds, gvs))
            for clab, cnd, cdoes, _l in cvs:
                lab1 = clabel + (" / " + clab if clab else "")
                if not sub:
                    options.append((lab1, cneeds + cnd, cdoes))
                    continue
                combos = []
                for glabel, gneeds, gvs in sub:
                    for glab, gnd, gdoes, _l2 in gvs:
                        combos.append((lab1 + " / " + glabel + (" / " + glab if glab else ""),
                                       cneeds + cnd + gneeds + gnd, cdoes + gdoes))
                if len({json.dumps(state_only(c[2])) for c in combos}) == 1:
                    allx = list(combos[0][2])
                    for c in combos[1:]:
                        allx += [x for x in c[2] if "other" in x and x not in allx]
                    options.append((lab1, cneeds + cnd, allx))
                else:
                    options.extend(combos)
        steps = [{"module": module, "via": via, "needs": dedupe(needs), "does": dedupe_keep(main_does)}]
        for lab, nd, does in extra:
            steps.append({"module": module, "via": via, "needs": dedupe(needs + nd), "does": does, "branch": lab})
        nonempty = [o for o in options if o[2]]
        if nonempty:
            if len(options) > 1 and len({json.dumps(state_only(o[2])) for o in options}) == 1:
                # every choice does the same to the game state: it always happens
                steps[0]["does"] += options[0][2]
                for o in options[1:]:
                    steps[0]["does"] += [x for x in o[2] if "other" in x and x not in steps[0]["does"]]
            elif len(options) == 1:
                steps[0]["does"] += options[0][2]
                steps[0]["needs"] = dedupe(steps[0]["needs"] + options[0][1])
            else:
                # choices that do the same to the game state share one step
                grouped = collections.OrderedDict()
                for lab, nd, does in options:
                    k = json.dumps(state_only(does)) + json.dumps(nd, sort_keys=True)
                    g = grouped.setdefault(k, {"labels": [], "needs": nd, "does": list(does)})
                    g["labels"].append(lab)
                    g["does"] += [x for x in does if "other" in x and x not in g["does"]]
                for g in grouped.values():
                    lab = " or ".join(g["labels"][:3]) + (" (or %d more)" % (len(g["labels"]) - 3)
                                                          if len(g["labels"]) > 3 else "")
                    steps.append({"module": module, "via": via, "needs": dedupe(g["needs"]),
                                  "does": g["does"], "branch": "choice: " + lab})
        if trunc:
            unc.append("a script near %s %s%d was too large to follow completely" % (dn, k, i))
        return steps, notes, unc

    def script_steps(self, tag, stage, sn, module, refs):
        notes, unc = [], []
        where = [r for r in refs.get(sn, []) if r[0] == module]
        owner = None
        dneeds = []
        dl = [r for r in where if r[1].endswith(".dlg")]
        objs = [r for r in where if not r[1].endswith(".dlg")]
        if objs:
            owner = objs[0][3]
        if dl and not objs and len(dl) == 1:
            dn = dl[0][1][:-4]
            nk = dl[0][2].split(" ")[1]
            d = self.dialog(dn, module)
            owner = self.owner(dn, module)[0]
            path = d.path_to(nk[0], int(nk[1:])) if d else None
            if path:
                for pk, pi, act in path:
                    dneeds += self.link_needs(act, module, notes)
        if not where:
            unc.append("script %s is in %s but nothing in the module's files names it (may be started by another script)" % (sn, module))
        vs, tr = self.b.script_variants(sn, module, owner, want=(tag, stage))
        steps = []
        if vs is None:
            unc.append("script %s could not be read in %s" % (sn, module))
            return steps, notes, unc, where
        for lab, nd, does, left in vs:
            st = {"module": module, "via": {"script": sn}, "needs": dedupe(dneeds + nd), "does": does}
            if lab:
                st["branch"] = lab
            if left:
                notes.append("%s (stage %s) also depends on: %s" % (sn, stage, "; ".join(clean_left(left)[:5])))
            steps.append(st)
        if tr:
            unc.append("script %s was too large to follow completely; effects may be missing" % sn)
        return steps, notes, unc, where


def state_only(does):
    return [x for x in does if "other" not in x]


def clean_left(left):
    from build import plain_other
    out = []
    for x in left:
        x = plain_other(x)
        out.append(x if len(x) < 140 else x[:137] + "...")
    return out


def contradictions(needs):
    """Plain descriptions of needs that cannot all hold."""
    bools = collections.defaultdict(set)
    nums = collections.defaultdict(list)
    out = []
    for n in needs:
        if "global_bool" in n:
            bools[n["global_bool"]].add(n["is"])
        elif "global_number" in n:
            nums[n["global_number"]].append((n["op"], n["value"]))
    for g, vals in bools.items():
        if len(vals) > 1:
            out.append("%s must be both TRUE and FALSE" % g)
    for g, tests in nums.items():
        ok = [x for x in range(-50, 1000) if all(ncsvm.CMP[op](x, v) for op, v in tests)]
        if not ok:
            out.append("no value of %s passes %s" % (g, ", ".join("%s %d" % t for t in tests)))
    return out


def walk_strings(s, owner, prefix=""):
    for label, typ, val in s.f:
        if typ in ("ResRef", "CExoString"):
            yield prefix + label, val, owner
        elif typ == "Struct":
            o = val.get("Tag") or owner
            yield from walk_strings(val, o, prefix + label + ".")
        elif typ == "List":
            for x in val:
                o = x.get("Tag") or x.get("TemplateResRef") or owner
                yield from walk_strings(x, o, prefix + label + ".")


def dedupe(xs):
    out, seen = [], set()
    for x in xs:
        k = json.dumps(x, sort_keys=True)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def dedupe_keep(xs):
    """Drop exact repeats of journal entries only; keep other repeats (they are real)."""
    out, seen = [], set()
    for x in xs:
        if "journal" in x:
            k = json.dumps(x)
            if k in seen:
                continue
            seen.add(k)
        out.append(x)
    return out
