"""The credits and the alignment a full run of a chapter picks up from its conversations and
scripts, once for a light-side player and once for a dark-side one. rewards.py writes the
result into the chapter's rewards file ("credits"); the editor's Skip Ahead adds the
credits of the side the player picks to PT_GOLD and moves the player's alignment by the
points.

New file (2026-10-23). How a run is modelled, per conversation (only conversations that
something in the chapter speaks: a placed or spawned creature, placeable or door, or a
script's ActionStartConversation):

* Each node's own effect is what its Script does (GiveGoldToCreature / TakeGoldFromCreature
  on the player with a fixed amount, AdjustAlignment on the player), with ExecuteScript
  followed. A script whose branches pay differently counts its largest amount (by size,
  so a payment counts in full); its alignment is the mean of its branches (the game's
  k_act_lightsml and the like scale the points with the player's level).
* A conversation is walked the way the engine runs it: from a line the player picks one
  reply, from a reply the game shows one line. Where the player picks, a reply with a
  condition on its link is a situation the run meets (the bounty handed in, the quest
  reported) and is counted unless it costs credits (an optional purchase) or leans to the
  other side (more dark points than light for the light-side player, and the reverse); of
  the replies without a condition the run takes one: one that costs nothing if there is
  one, then for the light-side player the one with the most light points over dark, then
  the most credits, then the most influence won with the party (KotOR 2); for the dark-side
  player the same with dark points. The payments the
  main story cannot avoid are chapters.py's credits_fixed. Where the game picks, the run takes the
  best line by the same measure (a persuade check passed).
* Every starting line counts (the conversation's first meeting and the later visits), and
  a node reached from several of them counts once.
* Links that jump back into another branch (IsChild) are not followed.

Scripts that pay outside a conversation (a placeable's OnUsed, a trigger) count once each.
SKIP below lists what a run does not count: gambling (pazaak, the swoop bets) and debug
conversations nothing in the game speaks.
"""
import collections
import re

import build
import kfmt
import nodescript

# Conversations and scripts a full run does not count, by game: gambling and test content.
SKIP = {
    "K1": {
        "dialog": re.compile(r"(l33t|pazaak|paz_|_paz|debug|test)", re.I),
        "script": re.compile(r"(paz|bet|gambl|debug|give10000)", re.I),
    },
    "K2": {
        "dialog": re.compile(r"(pazaak|paz_|_paz|debug|test|swoopbet)", re.I),
        "script": re.compile(r"(paz|bet|gambl|debug)", re.I),
    },
}
SLOTS = 12  # KotOR 2's party slots (npc.2da); KotOR 1 has no influence
NO_INFLUENCE = (0,) * SLOTS
ZERO = (0, 0, 0, NO_INFLUENCE)  # (credits, light points, dark points, influence change per slot)
# KotOR 2's ModifyInfluence sits inside a helper of a_influence_inc / dec; following it needs the
# routine among the ones that make a subroutine worth following (ncsvm.RELEVANT)
INFLUENCE_CALLS = {"ModifyInfluence", "SetInfluence"}


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], tuple(x + y for x, y in zip(a[3], b[3])))


class Credits:
    def __init__(self, b, ms):
        self.b = b
        self.ms = ms
        self.light = b.K.get("ALIGNMENT_LIGHT_SIDE", 2)
        self.dark = b.K.get("ALIGNMENT_DARK_SIDE", 3)
        self.cache = {}
        self.skip = SKIP.get(b.game, SKIP["K1"])

    # ------------------------------------------------------------ one script
    def script_value(self, sn, module, depth=0):
        """(credits, light, dark) the script gives the player, by the rule in the docstring."""
        sn = (sn or "").lower()
        if not sn or self.skip["script"].search(sn.split("|")[0]):
            return ZERO
        key = (sn, module)
        if key in self.cache:
            return self.cache[key]
        self.cache[key] = ZERO  # a script that runs itself
        import ncsvm
        saved = ncsvm.RELEVANT
        ncsvm.RELEVANT = set(saved) | INFLUENCE_CALLS
        try:
            paths = self._run(sn, module)
        finally:
            ncsvm.RELEVANT = saved
        per = []
        for p in paths or []:
            g = li = da = 0
            infl = [0] * SLOTS
            for name, a, _d in p.calls:
                if name == "ModifyInfluence" and len(a) >= 2 and isinstance(a[0], int) and isinstance(a[1], int) \
                        and 0 <= a[0] < SLOTS:
                    infl[a[0]] += a[1]
                    continue
                if name == "GiveGoldToCreature" and len(a) == 2 and isinstance(a[1], int) and build.is_pc(a[0]):
                    g += a[1]
                elif name == "TakeGoldFromCreature" and len(a) >= 2 and isinstance(a[0], int) and build.is_pc(a[1]):
                    g -= a[0]
                elif name == "AdjustAlignment" and len(a) >= 3 and isinstance(a[2], int) and build.is_pc(a[0]):
                    if a[1] == self.light:
                        li += a[2]
                    elif a[1] == self.dark:
                        da += a[2]
                elif name == "ExecuteScript" and a and isinstance(a[0], str) and depth < 3:
                    v = self.script_value(a[0], module, depth + 1)
                    g, li, da = g + v[0], li + v[1], da + v[2]
                    infl = [x + y for x, y in zip(infl, v[3])]
            per.append((g, li, da, tuple(infl)))
        if not per:
            out = ZERO
        else:
            gold = max((v[0] for v in per), key=abs)
            # influence: the mean of the branches, like alignment (a_influence_inc's levels)
            infl = tuple(round(sum(v[3][i] for v in per) / len(per)) for i in range(SLOTS))
            out = (gold, round(sum(v[1] for v in per) / len(per)), round(sum(v[2] for v in per) / len(per)), infl)
        self.cache[key] = out
        return out

    def _run(self, sn, module):
        """The script's paths with ModifyInfluence followed (the milestone's own runner with
        INFLUENCE_CALLS added to ncsvm.RELEVANT by the caller)."""
        import kfmt
        import ncsvm
        import nodescript
        name, params, _neg = nodescript.split(sn)
        data, _src = self.ms.g.get(name, kfmt.T_NCS, module)
        if data is None:
            return None
        import milestone
        saved = ncsvm.RELEVANT
        ncsvm.RELEVANT = set(saved) | milestone.EXTRA_RELEVANT
        try:
            return ncsvm.run_script(data, self.ms.b.R, params)[0]
        finally:
            ncsvm.RELEVANT = saved

    # ------------------------------------------------------------ one conversation
    def dialog_nodes(self, d, module, side):
        """The set of nodes a run of this side passes through, over every visit."""
        own = {}

        def node_value(k, i):
            if (k, i) not in own:
                v = ZERO
                for sk in nodescript.node_scripts(d.node(k, i)):
                    v = add(v, self.script_value(sk, module))
                own[(k, i)] = v
            return own[(k, i)]

        def score(v):
            # a branch that costs credits comes last: a run pays only when every way on costs
            mine, other = (v[1], v[2]) if side == "light" else (v[2], v[1])
            # then the most influence won with the party (KotOR 2: the replies a companion likes)
            return (v[0] >= 0, mine - other, v[0], sum(v[3]))

        def takes(v):
            # a situation the run meets, taken unless it leans to the other side or costs credits
            return v[0] >= 0 and score(v)[1] >= 0

        memo, busy = {}, set()

        def value(k, i):
            if (k, i) in memo:
                return memo[(k, i)]
            if (k, i) in busy:
                return ZERO
            busy.add((k, i))
            v = node_value(k, i)
            kids = d.children(k, i, own_only=True)
            if k == "E":
                gated = [c for c in kids if c[2]]
                free = [c for c in kids if not c[2]]
                for k2, j, _act in gated:
                    if takes(value(k2, j)):
                        v = add(v, value(k2, j))
                if free:
                    v = add(v, max((value(k2, j) for k2, j, _a in free), key=score))
            elif kids:
                v = add(v, max((value(k2, j) for k2, j, _a in kids), key=score))
            busy.discard((k, i))
            memo[(k, i)] = v
            return v

        def best(kids):
            return max(kids, key=lambda c: score(value(c[0], c[1])))

        seen = set()
        todo = [("E", idx) for idx, _act in d.starts if idx is not None and idx < len(d.E)]
        while todo:
            k, i = todo.pop()
            if (k, i) in seen:
                continue
            seen.add((k, i))
            kids = [c for c in d.children(k, i, own_only=True) if c[1] is not None and c[1] < len(d.nodes(c[0]))]
            if not kids:
                continue
            if k == "E":
                todo += [(k2, j) for k2, j, act in kids if act and takes(value(k2, j))]
                free = [c for c in kids if not c[2]]
                if free:
                    c = best(free)
                    todo.append((c[0], c[1]))
            else:
                c = best(kids)
                todo.append((c[0], c[1]))
        total = ZERO
        for n in seen:
            total = add(total, node_value(*n))
        return total

    # ------------------------------------------------------------ the chapter
    def spoken_dialogs(self, module, reach):
        """The conversations something in the module speaks."""
        names = set()
        for dn in self.ms.ch.module_dialog_names(module):
            if self.b.dialog_owner(dn, module):
                names.add(dn)
        names |= self.ms.ch.extra_names(module, kfmt.T_DLG, getattr(self.b, "extra_dialogs", None))
        for sn in reach:
            paths, _tr, _src = self.ms.script(sn, module)
            for p in paths or []:
                for name, a, _d in p.calls:
                    if name in ("ActionStartConversation", "BeginConversation") and len(a) > 1 and isinstance(a[1], str) and a[1]:
                        names.add(a[1].lower())
        # placed instances may name a conversation of their own in the area file
        for (n, t) in self.b.g.module(module):
            if t != kfmt.T_GIT:
                continue
            git = self.b.g.gff(n, t, module)
            for lst in ("Creature List", "Placeable List", "Door List"):
                for inst in git.get(lst) or []:
                    c = (inst.get("Conversation") or "").lower()
                    if c:
                        names.add(c)
        return sorted(x for x in names if not self.skip["dialog"].search(x))

    def chapter(self, reach_by_module, side_only=None):
        """{"light": {...}, "dark": {...}, "sources": [...]} for the chapter's modules.
        side_only: {dialog: "light" or "dark"}, conversations only a run of that side has (the
        two sides of a war each paying their own reward: chapters.py credits_side_only)."""
        side_only = {k.lower(): v for k, v in (side_only or {}).items()}
        sides = {"light": ZERO, "dark": ZERO}
        sources = []
        done_dialogs = set()
        in_dialogs = set()
        for module, reach in reach_by_module.items():
            for dn in self.spoken_dialogs(module, reach):
                if dn in done_dialogs:
                    continue
                d = self.ms.ch.dialog(dn, module)
                if d is None:
                    continue
                done_dialogs.add(dn)
                for k in ("E", "R"):
                    for nd in d.nodes(k):
                        in_dialogs.update(nodescript.node_scripts(nd))
                row = {}
                for side in ("light", "dark"):
                    if side_only.get(dn, side) != side:
                        row[side] = ZERO
                        continue
                    v = self.dialog_nodes(d, module, side)
                    sides[side] = add(sides[side], v)
                    row[side] = v
                if any(row[s] != ZERO for s in row):
                    src = {"dialog": dn, "module": module}
                    for side in ("light", "dark"):
                        v = row[side]
                        src[side] = {"credits": v[0], "light_points": v[1], "dark_points": v[2]}
                        if any(v[3]):
                            # per conversation, so the editor can leave out the ones a save played
                            src[side]["influence"] = {str(i): x for i, x in enumerate(v[3]) if x}
                    sources.append(src)
        done_scripts = set()
        for module, reach in reach_by_module.items():
            for sn, where in reach.items():
                if sn in in_dialogs or sn in done_scripts:
                    continue
                # only scripts something outside a conversation runs
                if all(re.search(r" [ER]\d+(>[ER]\d+)? (script|condition)$| start E\d+ condition$", w) for w in where):
                    continue
                if all(w.startswith("ExecuteScript from ") and w[len("ExecuteScript from "):] in in_dialogs for w in where):
                    continue
                v = self.script_value(sn, module)
                if v[0] == 0:
                    continue
                done_scripts.add(sn)
                for side in sides:
                    sides[side] = add(sides[side], (v[0], 0, 0, v[3]))
                sources.append({"script": sn, "module": module, "credits": v[0], "from": where[:2]})
        out = {s: {"credits": v[0], "light_points": v[1], "dark_points": v[2]} for s, v in sides.items()}
        if self.b.game == "K2":
            # influence change per party slot over the chapter (ModifyInfluence; a_influence_inc
            # and _dec move 8 a step), for the editor to add to PT_INFLUENCE
            for side, v in sides.items():
                out[side]["influence"] = {str(i): x for i, x in enumerate(v[3]) if x}
        out["sources"] = sources
        out["note"] = ("tools/questdb/credits.py: the credits and alignment points a full run of the chapter "
                       "picks up from its conversations and scripts, for a light-side and a dark-side player "
                       "(gambling left out). Worked out from the files, not played")
        return out
