"""Story state at the end of a planet, for the Save Editor's "skip to the end" feature.

New code (2026-10-23); called by build.py with --milestone. The Endar Spire is curated below
(CRITICAL, FINALS); every later chapter is curated in chapters.py and built by build_chapter(),
and every milestone gets order, chapter_title and the cleared modules (cleared.py).

What is measured from the game files, and what is curated by hand:

  measured  every script that can run in the planet's modules: module.ifo and area events,
            the templates of the objects placed in each area (.git), creatures that scripts
            spawn (CreateObject), every dialog node script and link condition, and scripts
            started through ExecuteScript. Each one is run through ncsvm, and its global
            writes, party changes, items given to or taken from the player and module
            changes are listed with the branch they sit on.
  measured  which scripts outside the planet's modules read each global (byte scan of every
            other module, chitin and Override, confirmed by running the hits through ncsvm).
  measured  placed container loot (.git placeables with an inventory) and items scripts
            create inside those containers.
  measured  the module the next chapter starts in: StartNewModule from the planet's last
            line, followed through cutscene modules (STUNT_*) by the branch whose global
            tests agree with the final values below; an empty waypoint means the module's
            entry point from its module.ifo.
  curated   the critical path (CRITICAL) and the value each global has at the end (FINALS).
            The order in which a state machine moves cannot be read from the files without
            playing, so each value says how sure it is. The generator checks every curated
            value against the writers it found and reports any that no writer can produce.
"""
import collections
import json
import os
import re

import chain
import kfmt
import ncsvm
import nodescript
from build import branch_label

render = ncsvm.render

# ---------------------------------------------------------------------------- curated
# Scripts and dialog lines every completed run passes through, in story order.
CRITICAL = {
    ("K1", "Endar Spire"): [
        ("end_m01aa", "k_pend_area01", "area m01aa OnEnter: opening movie 01A, K_CURRENT_PLANET = 5, class gear into container end_locker01"),
        ("end_m01aa", "k_pend_traskinc", "end_trask01 E55 (first line): End_TraskTalk + 1"),
        ("end_m01aa", "dialog end_trask01 R92", "journal end_attack 1"),
        ("end_m01aa", "k_pend_traskdl29", "end_trask01 R54 or R59: NPC slot 0 = template end_trask joins, party selection"),
        ("end_m01aa", "k_pend_door01", "first door (end_door01): END_TRASK_DLG = 8"),
        ("end_m01aa", "k_pend_trig02", "trigger end_trig02: END_TRASK_DLG = 10"),
        ("end_m01aa", "dialog end_trask01 R45", "journal end_attack 20, END_TRASK_DLG = 11"),
        ("end_m01aa", "dialog end_trask01 R49", "map loaded: journal end_attack 11"),
        ("end_m01aa", "k_pend_room3_01", "room 3 Sith die: END_ROOM3_DEAD, END_TRASK_DLG = 14, end_door05 unlocked"),
        ("end_m01aa", "k_pend_ud_cut1a", "room 3 Sith die (end_sith3): END_ROOM3_DEAD, END_TRASK_DLG = 14"),
        ("end_m01aa", "k_pend_traskdl50", "end_trask01 E16 after the fight: two items, END_TRASK_DLG = 15"),
        ("end_m01aa", "k_pend_sith2_d", "room 5 Sith die: END_ROOM5_DEAD, end_door16 unlocked"),
        ("end_m01aa", "k_pend_door16", "end_door16 opens: END_TRASK_DLG = -1"),
        ("end_m01aa", "k_pend_room7_01", "room 7 Sith die: END_ROOM7_DEAD"),
        ("end_m01aa", "k_pend_door15", "end_door15 (needs END_ROOM7_DEAD >= 2 and level 2): END_TRASK_DLG = 31"),
        ("end_m01aa", "k_pend_reinfrc03", "cutscene end_cut04 E4: spawns end_reinforce1 and 2"),
        ("end_m01aa", "k_pend_reinfrc08", "reinforcement dies: END_ROOM8_DEAD"),
        ("end_m01aa", "k_pend_reinfrc09", "reinforcement dies: END_ROOM8_DEAD"),
        ("end_m01aa", "k_pend_door20", "bridge door end_door08: bridge fight, END_TRASK_DLG = 31"),
        ("end_m01aa", "cp_end_trasksp_d", "K1CP bridge scene: END_TRASK_DLG = 31, dialog cp_end_traskbrdg"),
        ("end_m01aa", "cp_end_bridgecs", "K1CP: bridge sealed (END_BRIDGE_SEALED = TRUE), journal end_attack 30"),
        ("end_m01aa", "k_pend_traskdie1", "end_door19: slot 0 (end_trask) leaves the party"),
        ("end_m01ab", "k_pend_carth_t02", "trigger end_trig_carth02: END_CARTH_DLG = 1"),
        ("end_m01ab", "k_pend_sith_d", "Sith troopers die: END_SITH_DEAD, end_door04 unlocked"),
        ("end_m01ab", "k_pend_door20", "end_door04 opens: END_CARTH_DLG = 5"),
        ("end_m01ab", "k_pend_carth17", "end_carth001 E1: END_CARTH_DLG + 1"),
        ("end_m01ab", "dialog end_pod R1", "escape pod: journal end_attack 99, 350 XP, k_pend_pod01 StartNewModule STUNT_00"),
    ],
}

# Value at the end of the planet for each global the planet's scripts write.
# certain: the generator found one fixed value every run ends with.
FINALS = {
    ("K1", "Endar Spire"): {
        "K_CURRENT_PLANET": (5, True,
                             "set once by k_pend_area01 on entering m01aa; stunt_00's k_ren_visionland reads 5 "
                             "to send the escape pod to tar_m02af"),
        "END_BRIDGE_COMBAT": (False, True,
                              "only k_pend_door07 (scripts.bif) sets it TRUE and nothing in the end_ modules runs "
                              "k_pend_door07; k_pend_sith_d sets it FALSE. It must stay FALSE: k_ai_master pauses "
                              "the game and shows a hint when the player is hurt while it is TRUE"),
        "END_HURT_WARN": (False, True,
                          "only k_ai_master / k_hen_damage01 set it, and only while END_BRIDGE_COMBAT is TRUE"),
        "END_TRASK_DLG": (31, False,
                          "the state machine of end_trask. 31 is the value the bridge needs (journal stage 30 needs it; "
                          "k_pend_door15, k_pend_door20 and K1CP's cp_end_trasksp_d set it). Opening the end_m01ab "
                          "container adds 1 each time (k_pend_chest01), and the bridge fight's k_pend_sith_d "
                          "may set 28 if it runs after; nothing after the Endar Spire reads it"),
        "END_CARTH_DLG": (6, False,
                          "the state machine of tag Carth in end_m01ab: end_door04 sets 5 (k_pend_door20), the first "
                          "line adds 1 (k_pend_carth17); lines E3/E4 add 1 more if they play (7). Nothing after "
                          "the Endar Spire reads it"),
        "End_TraskTalk": (1, False,
                          "the first conversation with end_trask adds 1 (k_pend_traskinc on end_trask01 E55); stage 1 needs "
                          "it at 0 before. A replay of that line would add again"),
        "END_ROOM3_DEAD": (2, False, "kill counter: two placed Sith carry its scripts (end_sith2, end_sith3)"),
        "END_ROOM5_DEAD": (3, False,
                           "kill counter: three placed Sith carry k_pend_sith2_d (end_cut2_sith1, 2, 4); "
                           "end_door16 opens at 3"),
        "END_ROOM7_DEAD": (2, False, "kill counter: two placed Sith carry k_pend_room7_01; end_door15 needs 2"),
        "END_ROOM8_DEAD": (2, False,
                           "kill counter: the two reinforcements end_reinforce1 and 2, spawned by k_pend_reinfrc03 "
                           "(end_cut04 E4, after the cutscene); the bridge door needs 2"),
        "END_SITH_DEAD": (5, False,
                          "kill counter: five placed troopers in end_m01ab carry k_pend_sith_d (end_sith01 x4, "
                          "end_sith04); the end_m01aa copy of k_pend_sith_d belongs to end_repsol002, which no "
                          "area places or spawns"),
        "END_BRIDGE_SEALED": (True, False,
                              "TRUE when K1CP's bridge scene runs (cp_end_traskbrdg E0, cp_end_bridgecs), which "
                              "K1 Community Patch adds; FALSE on the unpatched route (end_trask01 R1)"),
        "END_PC_ON_BRIDGE": (False, False,
                             "trigger end_sealbridge sets TRUE on entry and FALSE on exit; the player leaves the "
                             "bridge to reach end_door19"),
        "END_TRASK_ON_BRIDGE": (None, False,
                                "trigger end_sealbridge; whether end_trask was last inside depends on where he stood "
                                "when he left the party. Leave unchanged"),
    },
}

# Cutscene modules the StartNewModule chain may pass through before the next chapter.
PASS_THROUGH = ("stunt_",)

PARTY_CALLS = ("AddAvailableNPCByTemplate", "AddAvailableNPCByObject", "AddPartyMember", "RemovePartyMember",
               "RemoveAvailableNPC", "SetNPCSelectability", "SetPartyLeader", "ShowPartySelectionGUI")
EXTRA_RELEVANT = {"CreateObject", "ActionStartConversation", "RemovePartyMember", "RemoveAvailableNPC",
                  "AddAvailableNPCByObject", "SetPartyLeader", "ShowPartySelectionGUI", "SetNPCSelectability"}
SCRIPT_LABEL = re.compile(r"^(Script|On|Mod_On)")
TEXT_TYPES = (kfmt.T_NCS, kfmt.T_DLG, kfmt.T_UTC, kfmt.T_UTP, kfmt.T_UTD, kfmt.T_UTT, kfmt.T_GIT,
              kfmt.T_ARE, kfmt.T_IFO)


class Milestone:
    def __init__(self, b):
        self.b = b
        self.g = b.g
        self.ch = chain.Chains(b)
        self.unc = []
        self.cls = {v: k for k, v in b.K.items() if k.startswith("CLASS_TYPE_")}
        self.skl = {v: k for k, v in b.K.items() if k.startswith("SKILL_")}
        self.npc = {v: k for k, v in b.K.items() if k.startswith("NPC_") and not k.startswith("NPC_AI")}
        self.cache = {}

    def script(self, name, module):
        """Like Builder.script, but subroutines that spawn creatures, start conversations or
        change the party are followed too (ncsvm skips subroutines that touch nothing in
        ncsvm.RELEVANT; the quest chains do not need these calls, a milestone does). Own
        cache, so the quest files are not affected. name may be a nodescript key."""
        name, params, _neg = nodescript.split(name)
        data, src = self.g.get(name, kfmt.T_NCS, module)
        if data is None:
            return None, False, None
        key = (hash(data), params)
        if key not in self.cache:
            saved = ncsvm.RELEVANT
            ncsvm.RELEVANT = set(saved) | EXTRA_RELEVANT
            try:
                self.cache[key] = ncsvm.run_script(data, self.b.R, params)
            finally:
                ncsvm.RELEVANT = saved
        paths, tr = self.cache[key]
        return paths, tr, src

    # ------------------------------------------------------------------ reachability
    def reachable(self, module):
        """{script: [where]} for every script that can run in the module."""
        g = self.g
        found = collections.OrderedDict()
        todo = []

        def add(name, where):
            n = (name or "").lower()
            if ";" in n:  # KotOR 2: two conditions on one link
                for one in n.split(";"):
                    add(one, where)
                return
            n = n.lstrip("!")
            if not n or g.get(nodescript.split(n)[0], kfmt.T_NCS, module)[0] is None:
                return
            if n not in found:
                found[n] = []
                todo.append(n)
            if where not in found[n]:
                found[n].append(where)

        def template(rtype, resref, tag, why):
            r = g.gff(resref, rtype, module)
            if r is None:
                return
            for lab, val, _o in chain.walk_strings(r, None):
                last = lab.split(".")[-1]
                if isinstance(val, str) and SCRIPT_LABEL.match(last):
                    add(val, "%s.%s %s (%s)%s" % (resref, chain.EXT[rtype], last, tag or r.get("Tag") or "",
                                                  why))

        ifo = g.gff("module", kfmt.T_IFO, module)
        for lab, typ, val in ifo.f:
            if typ in ("ResRef", "CExoString") and lab.startswith("Mod_On"):
                add(val, "module.ifo %s" % lab)
        for (n, t) in sorted(g.module(module)):
            if t == kfmt.T_ARE:
                are = g.gff(n, t, module)
                for lab, typ, val in are.f:
                    if typ in ("ResRef", "CExoString") and lab.startswith("On"):
                        add(val, "%s.are %s" % (n, lab))
            if t != kfmt.T_GIT:
                continue
            git = g.gff(n, t, module)
            for lst, rt in (("Creature List", kfmt.T_UTC), ("Placeable List", kfmt.T_UTP),
                            ("Door List", kfmt.T_UTD), ("TriggerList", kfmt.T_UTT)):
                for inst in git.get(lst) or []:
                    tr = (inst.get("TemplateResRef") or "").lower()
                    template(rt, tr, inst.get("Tag"), "")
            for enc in git.get("Encounter List") or []:
                for c in enc.get("CreatureList") or []:
                    template(kfmt.T_UTC, (c.get("ResRef") or "").lower(), None,
                             " in encounter %s" % (enc.get("Tag") or enc.get("TemplateResRef")))
        for dn in self.ch.module_dialog_names(module):
            d = self.ch.dialog(dn, module)
            if d is None:
                continue
            for k in ("E", "R"):
                for i, nd in enumerate(d.nodes(k)):
                    for sk in nodescript.node_scripts(nd):
                        add(sk, "%s %s%d script" % (dn, k, i))
                    for k2, j, act in d.children(k, i):
                        add(act, "%s %s%d>%s%d condition" % (dn, k, i, k2, j))
            for idx, act in d.starts:
                add(act, "%s start E%d condition" % (dn, idx))
        while todo:
            sn = todo.pop(0)
            paths, _tr, _src = self.script(sn, module)
            for p in paths or []:
                for c in p.calls:
                    a = c[1]
                    if c[0] == "ExecuteScript" and a and isinstance(a[0], str):
                        add(a[0], "ExecuteScript from %s" % sn)
                    elif c[0] == "CreateObject" and len(a) >= 2 and isinstance(a[1], str):
                        rt = {1: kfmt.T_UTC, 64: kfmt.T_UTP}.get(a[0])
                        if rt:
                            template(rt, a[1].lower(), None, " spawned by %s" % sn)
        return found

    # ------------------------------------------------------------------ effects
    def label(self, conds):
        lab = branch_label(conds, self.b) if conds else None
        return self.plain(lab) if lab else None

    def plain(self, s):
        s = re.sub(r"GetClassByPosition\(1, (?:GetFirstPC|GetPCSpeaker)\(\)\) (==|!=) (\d+)",
                   lambda m: "class %s %s" % ("is" if m.group(1) == "==" else "is not",
                                              self.cls.get(int(m.group(2)), m.group(2))), s)
        s = re.sub(r"GetHasSkill\((\d+), (?:GetFirstPC|GetPCSpeaker)\(\)\)",
                   lambda m: "has skill %s" % self.skl.get(int(m.group(1)), m.group(1)), s)
        return s

    def scan(self, module, scripts):
        """Global writes, party calls, items and module changes of the reachable scripts."""
        out = {"globals": collections.defaultdict(list), "party": [], "give": [], "take": [],
               "into": [], "modules": []}
        for sn, where in scripts.items():
            paths, tr, src = self.script(sn, module)
            if tr:
                self.unc.append("script %s in %s was too large to follow completely; some of its effects may "
                                "be missing" % (sn, module))
            seen = set()
            for p in paths or []:
                for name, a, deferred in p.calls:
                    ent = None
                    if name in ("SetGlobalNumber", "SetGlobalBoolean") and len(a) == 2 and isinstance(a[0], str):
                        v = a[1]
                        if isinstance(v, int):
                            val = bool(v) if name == "SetGlobalBoolean" else v
                            ent = ("globals", a[0], {"set": val})
                        elif isinstance(v, tuple) and v[0] == "op" and v[1] in ("+", "-") \
                                and isinstance(v[3], int) and v[2] == ("call", "GetGlobalNumber", (a[0],)):
                            ent = ("globals", a[0], {"add": v[3] if v[1] == "+" else -v[3]})
                        else:
                            ent = ("globals", a[0], {"expr": render(v)})
                    elif name in PARTY_CALLS:
                        ent = ("party", None, {"call": "%s(%s)" % (name, ", ".join(render(x) for x in a))})
                    elif name == "CreateItemOnObject" and a and isinstance(a[0], str):
                        tgt = a[1] if len(a) > 1 else ("obj", "OBJECT_SELF")
                        cnt = a[2] if len(a) > 2 else 1
                        if self.b_is_pc(tgt):
                            ent = ("give", None, {"item": a[0].lower(), "count": cnt if isinstance(cnt, int) else 1})
                        else:
                            from build import tag_of
                            t = tag_of(tgt)
                            if t:
                                ent = ("into", None, {"item": a[0].lower(), "container": t})
                    elif name == "DestroyObject" and a:
                        from build import item_of
                        it = item_of(a[0])
                        if it and self.b_is_pc(it[0]):
                            ent = ("take", None, {"item": it[1]})
                    elif name == "StartNewModule" and a and isinstance(a[0], str):
                        ent = ("modules", None, {"target": a[0], "waypoint": a[1] if len(a) > 1 else "",
                                                 "movies": [x for x in a[2:] if isinstance(x, str) and x]})
                    if ent is None:
                        continue
                    lab = self.label(p.conds)
                    if ent[0] == "into":
                        ent[2]["when"] = self.player_tests(p.conds)
                        lab = None
                    key = (ent[0], ent[1], json.dumps(ent[2], sort_keys=True), lab)
                    if key in seen:
                        continue
                    seen.add(key)
                    rec = dict(ent[2])
                    rec.update({"script": sn, "module": module, "from": where[:3]})
                    if lab:
                        rec["branch"] = lab
                    if src and not src.startswith("modules/"):
                        rec["resolves_to"] = src
                    if ent[0] == "globals":
                        out["globals"][ent[1]].append(rec)
                    else:
                        out[ent[0]].append(rec)
        return out

    def player_tests(self, conds):
        """The tests on the player's class and skills along a path, in plain words."""
        out = []
        for v, b in conds:
            r = render(v)
            m = re.match(r"^\(GetClassByPosition\(1, \w+\(\)\) (==|!=) (\d+)\)$", r)
            if m:
                yes = (m.group(1) == "==") == b
                out.append("class is %s%s" % ("" if yes else "not ", self.cls.get(int(m.group(2)), m.group(2))))
                continue
            m = re.match(r"^GetHasSkill\((\d+), \w+\(\)\)$", r)
            if m:
                out.append("%s skill %s" % ("has" if b else "lacks", self.skl.get(int(m.group(1)), m.group(1))))
        # a positive class test makes the negative ones redundant
        if any(x.startswith("class is ") and " not " not in x for x in out):
            out = [x for x in out if not x.startswith("class is not ")]
        return sorted(set(out))

    def b_is_pc(self, v):
        from build import is_pc
        return is_pc(v)

    # ------------------------------------------------------------------ readers outside
    def readers_outside(self, names):
        """{global lower: [(where, script)]} for scripts outside the planet's modules that read it."""
        g = self.g
        pats = {n.lower(): n.lower().encode("latin-1") for n in names}
        res = collections.defaultdict(list)
        planet = set(self.b.modules)

        def check(data, where, sn, module):
            low = data.lower()
            hit = [n for n, pb in pats.items() if pb in low]
            if not hit:
                return
            paths, _tr = ncsvm.run_script(data, self.b.R)
            for n in hit:
                ok = any(c[0] in ("GetGlobalNumber", "GetGlobalBoolean") and c[1] and isinstance(c[1][0], str)
                         and c[1][0].lower() == n for p in paths for c in p.calls)
                if ok:
                    res[n].append((where, sn))

        # Global scripts (chitin, Override) first: they read the global wherever they run, so
        # each one also gets a list of who names it outside the planet's modules.
        glob_data = {}
        for n in g.chitin_names(kfmt.T_NCS):
            if (n, kfmt.T_NCS) not in g.override:
                glob_data[n] = g.get(n, kfmt.T_NCS)
        for (n, t), path in g.override.items():
            if t == kfmt.T_NCS:
                with open(path, "rb") as fh:
                    glob_data[n] = (fh.read(), "Override")
        for n, (d, src) in sorted(glob_data.items()):
            check(d, src, n, None)
        glob_readers = {s for v in res.values() for _w, s in v}
        named = collections.defaultdict(set)
        for n, (d, _src) in glob_data.items():
            low = d.lower()
            for s in glob_readers:
                if s != n and s.encode("latin-1") in low:
                    named[s].add("global script " + n)
        for f in sorted(g.modfiles):
            if not (f.endswith(".mod") or f.endswith(".rim")):
                continue
            m = f.rsplit(".", 1)[0]
            m = m[:-2] if m.endswith("_s") else m
            if m in planet or f not in g.module_source(m):
                continue
            for n, t, d in kfmt.archive_entries(g.modfiles[f]):
                if t == kfmt.T_NCS:
                    check(d, "modules/" + f, n.lower(), m)
                if t in TEXT_TYPES:
                    low = d.lower()
                    for s in glob_readers:
                        if s.encode("latin-1") in low:
                            named[s].add(m)
        out = collections.defaultdict(list)
        for gname, lst in res.items():
            for where, sn in lst:
                ent = {"where": where, "script": sn}
                if not where.startswith("modules/"):
                    nm = sorted(named.get(sn, ()))
                    ent["named_outside_planet"] = len(nm)
                    ent["named_by_examples"] = nm[:4]
                out[gname].append(ent)
        return out

    # ------------------------------------------------------------------ containers
    def containers(self, module, into):
        out = []
        for (n, t) in sorted(self.g.module(module)):
            if t != kfmt.T_GIT:
                continue
            git = self.g.gff(n, t, module)
            for inst in git.get("Placeable List") or []:
                tr = (inst.get("TemplateResRef") or "").lower()
                u = self.g.gff(tr, kfmt.T_UTP, module)
                if u is None or not u.get("HasInventory"):
                    continue
                tag = u.get("Tag") or tr
                items = collections.Counter((i.get("InventoryRes") or "").lower() for i in u.get("ItemList") or [])
                made = [x for x in into if x["module"] == module and x["container"].lower() == tag.lower()]
                if not items and not made:
                    continue
                ent = {"module": module, "area": n, "container": tag, "template": tr,
                       "position": [round(inst.get("X") or 0, 2), round(inst.get("Y") or 0, 2)],
                       "items": [{"resref": r, "count": c} for r, c in items.items()]}
                if made:
                    # one entry per item: the player tests every path that creates it shares
                    per = collections.OrderedDict()
                    for x in made:
                        k = (x["item"], x["script"])
                        per.setdefault(k, []).append(set(x.get("when") or []))
                    ent["created_by_script"] = []
                    for (res, sn), whens in per.items():
                        if not res:
                            self.unc.append("%s in %s calls CreateItemOnObject with an empty template on %s "
                                            "(creates nothing)" % (sn, module, tag))
                            continue
                        rec = {"resref": res, "script": sn,
                               "when": sorted(set.intersection(*whens)) if whens else []}
                        if not rec["when"] and len(whens) > 1:
                            # a test that also appears negated makes no difference to this item
                            alltests = set().union(*whens)
                            moot = {t for t in alltests if opposite(t) in alltests}
                            alts = sorted({tuple(sorted(w - moot)) for w in whens if w - moot})
                            if len(alts) > 1:
                                rec["when_any"] = [list(a) for a in alts]
                        ent["created_by_script"].append(rec)
                out.append(ent)
        return out

    # ------------------------------------------------------------------ next module
    def next_module(self, start_effects, finals):
        hops = []
        moves = [m for m in start_effects if m]
        cur = moves[0] if moves else None
        while cur:
            mod = cur["target"].lower()
            hop = {"module": mod, "waypoint": cur["waypoint"], "movies": cur["movies"], "by": cur["script"],
                   "in": cur["module_from"]}
            hops.append(hop)
            if not mod.startswith(PASS_THROUGH):
                break
            cands = []
            names = {n for (n, t) in self.g.module(mod) if t == kfmt.T_NCS}
            for dn in self.ch.module_dialog_names(mod):
                d = self.ch.dialog(dn, mod)
                if d is None:
                    continue
                for k in ("E", "R"):
                    for nd in d.nodes(k):
                        names.update(nodescript.node_scripts(nd))
                starters = self.ch.scripts_naming(dn, mod)
                if starters:
                    hop.setdefault("dialogs", []).append({"dialog": dn, "started_by": starters})
            for sn in sorted(names):
                paths, _tr, _src = self.script(sn, mod)
                for p in paths or []:
                    for c in p.calls:
                        if c[0] != "StartNewModule" or not c[1] or not isinstance(c[1][0], str):
                            continue
                        needs, _left = self.b.path_needs(p.conds)
                        if all(agrees(n, finals) for n in needs):
                            a = c[1]
                            cands.append({"target": a[0], "waypoint": a[1] if len(a) > 1 else "",
                                          "movies": [x for x in a[2:] if isinstance(x, str) and x],
                                          "script": sn, "module_from": mod,
                                          "needs": needs})
            uniq = {(c["target"].lower(), c["waypoint"]) for c in cands}
            if len(uniq) != 1:
                self.unc.append("the module after %s could not be settled: %d candidates (%s)"
                                % (mod, len(uniq), ", ".join(sorted("%s/%s" % u for u in uniq))))
                break
            cur = cands[0]
            hop["leaves_by"] = {"script": cur["script"], "when": [build_plain(n) for n in cur["needs"]]}
        if not hops:
            return None
        last = hops[-1]
        mod = last["module"]
        ifo = self.g.gff("module", kfmt.T_IFO, mod)
        res = {"module": mod, "waypoint": last["waypoint"], "chain": hops}
        if ifo is not None and not last["waypoint"]:
            res["entry"] = {"area": ifo.get("Mod_Entry_Area"),
                            "x": round(ifo.get("Mod_Entry_X") or 0, 4), "y": round(ifo.get("Mod_Entry_Y") or 0, 4),
                            "z": round(ifo.get("Mod_Entry_Z") or 0, 4),
                            "dir_x": round(ifo.get("Mod_Entry_Dir_X") or 0, 4),
                            "dir_y": round(ifo.get("Mod_Entry_Dir_Y") or 0, 4),
                            "note": "the waypoint is empty, so the game puts the party at the module's entry "
                                    "point from module.ifo"}
            on_load = ifo.get("Mod_OnModLoad")
            if on_load:
                res["on_module_load"] = on_load
        elif ifo is None:
            self.unc.append("module %s of the next chapter was not found in the game files" % mod)
        return res


def opposite(t):
    """The negation of a player test from Milestone.player_tests."""
    for a, b in (("has skill ", "lacks skill "), ("class is not ", "class is ")):
        if t.startswith(a):
            return b + t[len(a):]
        if t.startswith(b):
            return a + t[len(b):]
    return None


def agrees(n, finals):
    """A need (from path_needs) that the final globals do not contradict."""
    if "global_number" in n:
        v = finals.get(n["global_number"].lower())
        if v is None or isinstance(v, bool):
            return True
        return ncsvm.CMP[n["op"]](v, n["value"])
    if "global_bool" in n:
        v = finals.get(n["global_bool"].lower())
        return v is None or bool(v) == n["is"]
    return True


def build_plain(n):
    from build import plain_need
    return plain_need(n)


# ---------------------------------------------------------------------------- assemble
def build(b):
    key = (b.game, b.planet)
    if key not in FINALS:
        raise SystemExit("no milestone is set up for %s %s" % key)
    ms = Milestone(b)
    critical = CRITICAL[key]
    crit_scripts = {(m, n) for m, n, _w in critical if not n.startswith("dialog ")}
    reach = {m: ms.reachable(m) for m in b.modules}
    eff = {m: ms.scan(m, reach[m]) for m in b.modules}
    for m, n, _w in critical:
        if n.startswith("dialog "):
            dn, node = n.split(" ")[1:3]
            d = ms.ch.dialog(dn, m)
            if d is None or int(node[1:]) >= len(d.nodes(node[0])):
                ms.unc.append("critical dialog line %s %s is missing in %s" % (dn, node, m))
        elif n not in (reach[m] if m in reach else reach.setdefault(m, ms.reachable(m))):
            ms.unc.append("critical script %s does not run in %s by any placed object, dialog or script "
                          "the generator could find" % (n, m))

    globs = b.globals_known()
    finals_cfg = FINALS[key]
    writers = collections.defaultdict(list)
    for m in b.modules:
        for gname, recs in eff[m]["globals"].items():
            for r in recs:
                r["critical"] = (m, r["script"]) in crit_scripts
                writers[gname.lower()].append((gname, r))
    byname = {k.lower(): k for k in finals_cfg}
    byname.update({low: v[0][0] for low, v in writers.items()})
    names = sorted(byname.values(), key=str.lower)
    readers = ms.readers_outside(names)
    out_globals = []
    finals_val = {}
    for gname in names:
        low = gname.lower()
        cat = globs.get(low)
        recs = [r for _n, r in writers.get(low, [])]
        cfg = next((v for k, v in finals_cfg.items() if k.lower() == low), None)
        ent = {"name": cat[0] if cat else gname, "type": (cat[1] if cat else "unknown")}
        if cfg is None:
            ent.update({"value": None, "certain": False,
                        "note": "written in the planet's modules but no end value was worked out; leave it unchanged"})
            ms.unc.append("global %s: no end value worked out" % gname)
        else:
            val, certain, why = cfg
            ent.update({"value": val, "certain": certain, "note": why})
            if val is not None:
                finals_val[low] = val
                fixed = {r["set"] for r in recs if "set" in r}
                counts = any("add" in r for r in recs)
                if recs and val not in fixed and not counts and val not in (0, False):
                    ms.unc.append("global %s: the curated value %s is not one any writer sets" % (gname, val))
                    ent["certain"] = False
            if not certain:
                ms.unc.append("global %s = %s: %s" % (ent["name"], json.dumps(val), why))
        if not cat:
            ms.unc.append("global %s is not in globalcat.2da, so a save does not keep it" % gname)
        rl = readers.get(low, [])
        # a global script only matters after the planet if something outside names it
        live = [r for r in rl if r.get("named_outside_planet", 1)]
        ent["read_after_planet"] = live[:12]
        if len(live) > 12:
            ent["read_after_planet_total"] = len(live)
        dead = [r["script"] for r in rl if not r.get("named_outside_planet", 1)]
        if dead:
            ent["read_only_by_planet_scripts"] = dead
        ent["writers"] = recs
        out_globals.append(ent)
    # globals named like the planet's that nothing sets
    pref = b.gprefix
    unset = sorted(v[0] for k, v in globs.items() if v[0].upper().startswith(pref) and k not in writers
                   and not any(n.lower() == k for n in finals_cfg))

    # items
    give, take, into = [], [], []
    for m in b.modules:
        for r in eff[m]["give"]:
            r = dict(r)
            r["critical"] = (m, r["script"]) in crit_scripts
            give.append(r)
        for r in eff[m]["take"]:
            r = dict(r)
            take.append(r)
        into += eff[m]["into"]
    held = [x for x in give if x["critical"]]
    other_given = [x for x in give if not x["critical"]]
    for x in held:
        if x.get("branch"):
            ms.unc.append("item %s from %s sits on a branch (%s)" % (x["item"], x["script"], x["branch"]))
    loot = []
    for m in b.modules:
        loot += ms.containers(m, into)

    # party
    party_calls = []
    for m in b.modules:
        for r in eff[m]["party"]:
            r = dict(r)
            r["critical"] = (m, r["script"]) in crit_scripts
            party_calls.append(r)
    order = {(m, n): i for i, (m, n, _w) in enumerate(critical)}
    party_calls.sort(key=lambda r: order.get((r["module"], r["script"]), len(order)))
    slots = collections.OrderedDict()
    for r in party_calls:
        mm = re.match(r"(AddAvailableNPCByTemplate|RemoveAvailableNPC|AddPartyMember|RemovePartyMember)\((-?\d+)",
                      r["call"])
        if mm and r["critical"]:
            slots.setdefault(int(mm.group(2)), []).append(mm.group(1))
    party = {"recruited_at_end": [], "calls": party_calls, "slots": []}
    for s, ops in slots.items():
        # repeats from several branches of one script collapse to one step
        ops = [o for i, o in enumerate(ops) if i == 0 or ops[i - 1] != o]
        last_add = max([i for i, o in enumerate(ops) if o.startswith("Add")] or [-1])
        last_rem = max([i for i, o in enumerate(ops) if o.startswith("Remove")] or [-1])
        ent = {"slot": s, "constant": ms.npc.get(s, ""), "ops_in_story_order": ops,
               "available_at_end": last_add > last_rem}
        party["slots"].append(ent)
        if ent["available_at_end"]:
            party["recruited_at_end"].append(ent["constant"] or s)

    # journal: the planet quests' stage set by the final line
    final_line = [x for x in critical if x[1].startswith("dialog ")][-1]
    dn, node = final_line[1].split(" ")[1:3]
    d = ms.ch.dialog(dn, final_line[0])
    nd = d.node(node[0], int(node[1:]))
    journal = []
    if nd.get("Quest"):
        journal.append({"tag": nd.get("Quest"), "stage": nd.get("QuestEntry"),
                        "set_by": "dialog %s %s in %s" % (dn, node, final_line[0])})
    final_moves = []
    sc = (nd.get("Script") or "").lower()
    for r in eff[final_line[0]]["modules"]:
        if r["script"] == sc:
            rr = dict(r)
            rr["module_from"] = final_line[0]
            final_moves.append(rr)
    nxt = ms.next_module(final_moves, finals_val)

    # Carth: who joins on this planet, and where the next one joins
    carth = b.K.get("NPC_CARTH")
    if carth is not None and not any(e["slot"] == carth and e["available_at_end"] for e in party["slots"]):
        joins = []
        if nxt:
            nm = nxt["module"]
            for sn in sorted(ms.reachable(nm)):
                paths, _tr, _src = ms.script(sn, nm)
                if any(c[0] in ("AddAvailableNPCByTemplate", "AddPartyMember") and c[1] and c[1][0] == carth
                       for p in paths or [] for c in p.calls):
                    named = sorted("%s.%s" % (n2, chain.EXT.get(t2, t2)) for (n2, t2), data in ms.g.module(nm).items()
                                   if t2 in (kfmt.T_DLG, kfmt.T_UTC, kfmt.T_UTP, kfmt.T_UTT)
                                   and sn.encode("latin-1") in data.lower())
                    joins.append({"module": nm, "script": sn, "named_by": named})
        party["carth"] = {"recruited_on_this_planet": False,
                          "note": "no script or dialog the Endar Spire runs adds NPC_CARTH to the party; the NPC "
                                  "with tag Carth (template p_carth001) is placed in end_m01ab and talks to the player, then "
                                  "escapes in the same pod",
                          "joins_later": joins}
        ms.unc.append("party: NPC_CARTH is not recruited on the Endar Spire (he becomes available in %s); "
                      "the party at the end is the player alone"
                      % (", ".join("%s (%s)" % (j["module"], j["script"]) for j in joins) or "a later module"))

    data = {
        "game": b.game, "planet": b.planet, "generated_by": "tools/questdb/build.py --milestone",
        "checked": False,
        "about": "Story state every completed run of the planet ends with, for a skip-to-the-end feature. "
                 "Values marked certain = false were worked out by reading the scripts, not by playing.",
        "journal": journal,
        "globals": out_globals,
        "globals_never_set": unset,
        "items": {
            "held_at_end": [{"resref": x["item"], "count": x["count"], "script": x["script"],
                             "module": x["module"], "from": x["from"], "branch": x.get("branch"),
                             "certain": False}
                            for x in held],
            "held_note": "Given by scripts on the critical path. Not certain: the line that gives them must play, "
                         "and the player can use them (they are consumables) before the end.",
            "other_script_gifts": other_given,
            "taken_optional": take,
            "container_loot_optional": loot,
            "random_loot": "creature drops from the generic treasure scripts (k_pdan_trask_9, k_pend_bridge01, "
                           "k_pend_reinfrc01/07) are random and not listed",
        },
        "party": party,
        "next_chapter": nxt,
        "critical_path": [{"module": m, "source": n, "what": w} for m, n, w in critical],
        "critical_path_note": "Curated in milestone.py from the scripts, the dialogs and the area layout; the order "
                              "is inferred, not played. Writers marked critical = true belong to these scripts.",
        "uncertain": chain.dedupe(ms.unc),
    }
    return add_chapter_fields(data, b, ms, reach, crit_scripts, loot)


def write(b, path):
    key = (b.game, b.planet)
    data = build(b) if key in FINALS else build_chapter(b)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("milestone: globals %d (certain %d), items held %d, containers %d, party slots %d, uncertain %d, "
          "modules cleared %d"
          % (len(data["globals"]), sum(1 for x in data["globals"] if x["certain"]),
             len(data["items"]["held_at_end"]), len(data["items"]["container_loot_optional"]),
             len(data["party"]["slots"]), len(data["uncertain"]), len(data.get("cleared", []))))
    print("wrote", path)


# ---------------------------------------------------------------------------- every chapter
# Added 2026-10-23: the generic milestone for every chapter after the Endar Spire, driven by
# chapters.py, and the fields every milestone carries (order, title, cleared modules).
PARTY_KEEP = ("AddAvailableNPCByTemplate", "AddAvailableNPCByObject", "RemoveAvailableNPC", "AddPartyMember",
              "RemovePartyMember")


def chapter_cfg(b):
    import chapters
    return chapters.CHAPTERS.get((b.game, b.planet), {})


def add_chapter_fields(data, b, ms, reach, crit_scripts, loot):
    """order, chapter_title and the cleared modules, for a milestone built by build() or
    build_chapter(); the order and title go right after "planet"."""
    import cleared
    cfg = chapter_cfg(b)
    out = {}
    for k, v in data.items():
        out[k] = v
        if k == "planet":
            out["order"] = cfg.get("order")
            out["chapter_title"] = cfg.get("chapter_title")
            for extra in ("side_chapter", "story_position"):
                if extra in cfg:
                    out[extra] = cfg[extra]
    enemies = cleared._enemies(b.game)
    rows = []
    for m in b.modules:
        ret = cfg.get("return_modules", {}).get(m, cfg.get("returnable", True))
        rows.append(cleared.module_cleared(ms, m, reach[m], {s for (_m, s) in crit_scripts}, loot, ret, enemies))
    out["cleared"] = rows
    out["cleared_note"] = ("How each module looks after a full run, for an editor that stores the area as played: "
                           "remove (tag, template), doors (tag: open, unlocked), containers_looted (container tags "
                           "the rewards file empties), locals (the area's, the module's and placed objects' local "
                           "variables their own scripts read to tell a first visit from a return, with the value a "
                           "played area holds; index = the engine's local slot). returnable = false: the player "
                           "never comes back to the module. See tools/questdb/cleared.py.")
    if cfg.get("returnable_note"):
        out["returnable_note"] = cfg["returnable_note"]
    return out


def follow_next(ms, b, eff, nx, finals_val):
    """The next chapter's route from a chapters.py "next" entry: the game's own StartNewModule
    chain, or a fixed door. Split out of build_chapter 2026-10-23 for the dark-side route."""
    if "from" in nx:
        m, sn = nx["from"]
        moves = []
        for r in eff[m]["modules"]:
            if r["script"] == sn and (not nx.get("target") or r["target"].lower() == nx["target"]):
                rr = dict(r)
                rr["module_from"] = m
                moves.append(rr)
        if not moves:
            ms.unc.append("next chapter: %s in %s calls no StartNewModule the generator could read" % (sn, m))
        nxt = ms.next_module(moves, finals_val)
        if nxt and nx.get("last"):
            cut = [h["module"] for h in nxt["chain"]]
            if nx["last"] in cut:
                nxt["chain"] = nxt["chain"][:cut.index(nx["last"]) + 1]
                nxt["module"], nxt["waypoint"] = nx["last"], nxt["chain"][-1]["waypoint"]
                nxt.pop("entry", None)
                ms.unc = [u for u in ms.unc if not u.startswith("the module after %s" % nx["last"])]
        if nxt and nx.get("note"):
            nxt["note"] = nx["note"]
    else:
        f = dict(nx["fixed"])
        nxt = {"module": f["module"], "waypoint": f["waypoint"],
               "chain": [{"module": f["module"], "waypoint": f["waypoint"], "movies": f.get("movies", []),
                          "by": f.get("by"), "in": f.get("in")}]}
        if f.get("note"):
            nxt["note"] = f["note"]
        ok = any(r["script"] == f.get("by") and r["target"].lower() == f["module"] for mm in b.modules
                 for r in eff[mm]["modules"])
        tm = re.match(r"transition (?:trigger|door) (\S+)$", f.get("by") or "")
        if tm and not ok:
            # an area transition placed in the area file (LinkedToModule / LinkedTo)
            for (n, t) in ms.g.module(f["in"]):
                if t != kfmt.T_GIT:
                    continue
                git = ms.g.gff(n, t, f["in"])
                for lst in ("TriggerList", "Door List"):
                    for inst in git.get(lst) or []:
                        same = ((inst.get("Tag") or "").lower() == tm.group(1).lower()
                                and (inst.get("LinkedToModule") or "").lower() == f["module"]
                                and (inst.get("LinkedTo") or "") == f["waypoint"])
                        ok = ok or same
        if not ok and f.get("by"):
            ms.unc.append("next chapter: %s was not found moving the party to %s" % (f.get("by"), f["module"]))

    return nxt


def recruit_entry(ms, row):
    """A party_recruit row of chapters.py as the milestone writes it. A seventh element, "male"
    or "female" (KotOR 2's Handmaiden and Disciple), is the player's gender the recruit needs;
    the editor skips the entry for the other (added 2026-10-23)."""
    slot, tpl, sn, m, certain, why = row[:6]
    ent = {"slot": slot, "constant": ms.npc.get(slot, ""), "template": tpl, "script": sn, "module": m,
           "certain": certain, "note": why}
    if len(row) > 6 and row[6]:
        ent["when"] = row[6]
    return ent


def dark_block(ms, b, eff, dk, finals_val):
    """What a dark-side run of the chapter ends with instead (chapters.py "dark"): the journal
    stages, the story values, the party changes and the route on. The editor applies it in
    place of the light-side values when the player picks the dark side. Added 2026-10-23."""
    out = {"note": dk.get("note", "")}
    if "journal" in dk:
        out["journal"] = [{"tag": t, "stage": s, "set_by": w} for t, s, w in dk["journal"]]
    out["globals"] = [{"name": n, "value": v[0], "certain": v[1], "note": v[2]} for n, v in dk.get("finals", {}).items()]
    for n, v in dk.get("finals", {}).items():
        if v[0] is not None and not v[1]:
            ms.unc.append("dark side: global %s = %s: %s" % (n, json.dumps(v[0]), v[2]))
    calls = [r["call"] for m in b.modules for r in eff[m]["party"]]
    recruit = []
    for row in dk.get("party_recruit", []):
        slot, tpl, sn, m, certain, why = row[:6]
        want = 'AddAvailableNPCByTemplate(%d, "%s")' % (slot, tpl)
        by_object = "AddAvailableNPCByObject(%d," % slot
        if want not in calls and not any(c.startswith(by_object) for c in calls):
            ms.unc.append("dark side: %s by %s in %s was not found in the chapter's scripts" % (want, sn, m))
        recruit.append(recruit_entry(ms, row))
    out["party"] = {
        "recruit": recruit,
        "not_recruited": dk.get("party_not_recruited", []),
        "remove": [{"slot": slot, "constant": ms.npc.get(slot, ""), "script": sn, "module": m, "certain": certain,
                    "note": why} for slot, sn, m, certain, why in dk.get("party_remove", [])],
    }
    if dk.get("next"):
        fv = dict(finals_val)
        fv.update({k.lower(): v[0] for k, v in dk.get("finals", {}).items() if v[0] is not None})
        out["next_chapter"] = follow_next(ms, b, eff, dk["next"], fv)
    return out


def build_chapter(b):
    key = (b.game, b.planet)
    cfg = chapter_cfg(b)
    if not cfg or "critical" not in cfg:
        raise SystemExit("no milestone is set up for %s %s (tools/questdb/chapters.py)" % key)
    ms = Milestone(b)
    critical = cfg["critical"]
    crit_scripts = {(m, n) for m, n, _w in critical if not n.startswith("dialog ")}
    reach = {m: ms.reachable(m) for m in b.modules}
    eff = {m: ms.scan(m, reach[m]) for m in b.modules}
    for m, n, _w in critical:
        if n.startswith("dialog "):
            dn, node = n.split(" ")[1:3]
            d = ms.ch.dialog(dn, m)
            if d is None or int(node[1:]) >= len(d.nodes(node[0])):
                ms.unc.append("critical dialog line %s %s is missing in %s" % (dn, node, m))
        elif n not in (reach[m] if m in reach else reach.setdefault(m, ms.reachable(m))):
            ms.unc.append("critical script %s does not run in %s by any placed object, dialog or script "
                          "the generator could find" % (n, m))

    # ---- globals
    globs = b.globals_known()
    finals_cfg = cfg.get("finals", {})
    writers = collections.defaultdict(list)
    for m in b.modules:
        for gname, recs in eff[m]["globals"].items():
            for r in recs:
                r["critical"] = (m, r["script"]) in crit_scripts
                writers[gname.lower()].append((gname, r))
    byname = {k.lower(): k for k in finals_cfg}
    for low, v in writers.items():
        byname.setdefault(low, v[0][0])
    names = sorted(byname.values(), key=str.lower)
    readers = ms.readers_outside(names)
    curated, rest = [], []
    for gname in names:
        low = gname.lower()
        cat = globs.get(low)
        recs = [r for _n, r in writers.get(low, [])]
        cfgv = next((v for k, v in finals_cfg.items() if k.lower() == low), None)
        ent = {"name": cat[0] if cat else gname, "type": (cat[1] if cat else "unknown")}
        rl = readers.get(low, [])
        live = [r for r in rl if r.get("named_outside_planet", 1)]
        if cfgv is not None:
            val, certain, why = cfgv
            ent.update({"value": val, "certain": certain, "note": why})
            if val is not None and recs:
                fixed = {r["set"] for r in recs if "set" in r}
                counts = any("add" in r or "expr" in r for r in recs)
                if val not in fixed and not counts and val not in (0, False):
                    ms.unc.append("global %s: the curated value %s is not one any script in the chapter sets "
                                  "(set elsewhere, for example by a conversation script in scripts.bif)" % (gname, val))
            if val is not None and not certain:
                ms.unc.append("global %s = %s: %s" % (ent["name"], json.dumps(val), why))
            ent["read_after_planet"] = live[:12]
            if len(live) > 12:
                ent["read_after_planet_total"] = len(live)
            ent["writers"] = recs[:12]
            if len(recs) > 12:
                ent["writers_total"] = len(recs)
            curated.append(ent)
        else:
            vals = sorted({json.dumps(r["set"]) for r in recs if "set" in r})
            ent.update({"value": None, "certain": False,
                        "note": "side content or bookkeeping: no end value is set; the editor leaves it unchanged",
                        "values_written": [json.loads(v) for v in vals][:8],
                        "writers_total": len(recs), "writers": [
                            {k: r[k] for k in ("script", "module", "set", "add", "expr", "branch") if k in r}
                            for r in recs[:3]]})
            if live:
                ent["read_after_planet"] = [{"where": r["where"], "script": r["script"]} for r in live[:6]]
                if len(live) > 6:
                    ent["read_after_planet_total"] = len(live)
            if not cat:
                ent["note"] += "; not in globalcat.2da, so a save does not keep it"
            rest.append(ent)
        if not cat:
            ms.unc.append("global %s is not in globalcat.2da, so a save does not keep it" % gname)
    pref = b.gprefix
    unset = sorted(v[0] for k, v in globs.items() if v[0].upper().startswith(pref) and k not in writers
                   and k not in byname)

    # ---- items
    give, take, into = [], [], []
    for m in b.modules:
        for r in eff[m]["give"]:
            r = dict(r)
            r["critical"] = (m, r["script"]) in crit_scripts
            give.append(r)
        take += [dict(r) for r in eff[m]["take"]]
        into += eff[m]["into"]
    held = []
    for res, cnt, sn, m, why in cfg.get("items", []):
        found = any(g["item"] == res.lower() and g["script"] == sn for g in give)
        if not found:
            ms.unc.append("item %s: %s in %s was not found giving it to the player" % (res, sn, m))
        held.append({"resref": res, "count": cnt, "script": sn, "module": m, "note": why, "certain": False})
    loot = []
    for m in b.modules:
        loot += ms.containers(m, into)

    # ---- party
    calls = []
    for m in b.modules:
        for r in eff[m]["party"]:
            if r["call"].startswith(PARTY_KEEP):
                r = dict(r)
                r["critical"] = (m, r["script"]) in crit_scripts
                calls.append(r)
    recruit = []
    for row in cfg.get("party_recruit", []):
        slot, tpl, sn, m, certain, why = row[:6]
        want = 'AddAvailableNPCByTemplate(%d, "%s")' % (slot, tpl)
        by_object = "AddAvailableNPCByObject(%d," % slot
        ok = any((c["call"] == want or c["call"].startswith(by_object)) and c["script"].split("|")[0] == sn.split("|")[0]
                 and c["module"] == m for c in calls)
        if not ok:
            ms.unc.append("party: %s by %s in %s was not found in the module's scripts" % (want, sn, m))
        recruit.append(recruit_entry(ms, row))
        if not certain:
            ms.unc.append("party: slot %d (%s) joins only on one branch: %s" % (slot, tpl, why))
    remove = [{"slot": slot, "constant": ms.npc.get(slot, ""), "script": sn, "module": m, "certain": certain,
               "note": why} for slot, sn, m, certain, why in cfg.get("party_remove", [])]
    party = {"recruit": recruit, "remove": remove,
             "recruited_at_end": [r["constant"] or r["slot"] for r in recruit],
             "recruit_note": "Apply as the game's own AddAvailableNPCByTemplate(slot, template): the slot's "
                             "AVAILNPC<slot> creature in the save is built from the template (templates.bif, "
                             "Override or the named module)",
             "calls": calls, "slots": [{"slot": r["slot"], "constant": r["constant"],
                                        "available_at_end": True} for r in recruit]}

    # ---- journal
    journal = [{"tag": t, "stage": s, "set_by": w} for t, s, w in cfg.get("journal", [])]

    # ---- next chapter
    nx = cfg.get("next", {})
    finals_val = {k.lower(): v[0] for k, v in finals_cfg.items() if v[0] is not None}
    nxt = follow_next(ms, b, eff, nx, finals_val)

    data = {
        "game": b.game, "planet": b.planet, "generated_by": "tools/questdb/build.py --milestone",
        "checked": False,
        "about": "Story state every completed run of the chapter ends with, for a skip-to-the-end feature. "
                 "Curated in tools/questdb/chapters.py; values marked certain = false were worked out by reading "
                 "the scripts or seen in one real save, not proven for every run.",
        "journal": journal,
        "journal_remove": cfg.get("journal_remove", []),
        "globals": curated + rest,
        "globals_never_set": unset,
        "items": {
            "held_at_end": held,
            "held_note": "Given by scripts on the critical path (tools/questdb/chapters.py).",
            "other_script_gifts": [{k: r[k] for k in ("item", "count", "script", "module", "branch") if k in r}
                                   for r in give if not r["critical"]],
            "taken_optional": take,
            "container_loot_optional": loot,
            "random_loot": "creature drops rolled by the generic treasure scripts at death are random and not listed",
        },
        "party": party,
        "next_chapter": nxt,
        "critical_path": [{"module": m, "source": n, "what": w} for m, n, w in critical],
        "critical_path_note": "Curated in tools/questdb/chapters.py; the order is inferred, not played. Writers "
                              "marked critical = true belong to these scripts.",
        "uncertain": chain.dedupe(ms.unc),
    }
    if cfg.get("journal_remove_note"):
        data["journal_remove_note"] = cfg["journal_remove_note"]
    if cfg.get("star_map"):
        data["star_map"] = cfg["star_map"]
    if cfg.get("jedi_class"):
        data["jedi_class"] = cfg["jedi_class"]
    for k in ("teach_form", "grants", "master_met"):
        # KotOR 2: a master's teaching (a_give_form's rule, applied by the editor) and powers
        # or feats the story grants (added 2026-10-23)
        if cfg.get(k):
            data[k] = cfg[k]
    if cfg.get("increments"):
        # a counter several chapters share, raised by each (KotOR 2's masters found)
        data["increments"] = [{"name": n, "add": a, "note": w} for n, a, w in cfg["increments"]]
    if cfg.get("dark"):
        data["dark"] = dark_block(ms, b, eff, cfg["dark"], finals_val)
    data = add_chapter_fields(data, b, ms, reach, crit_scripts, loot)
    for row in data["cleared"]:
        data["uncertain"] += row["uncertain"]
    data["uncertain"] = chain.dedupe(data["uncertain"])
    return data
