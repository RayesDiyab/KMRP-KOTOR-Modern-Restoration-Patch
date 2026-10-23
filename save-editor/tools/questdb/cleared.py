"""How a played-through module looks, for the Save Editor's skip ahead: per module, what a
full run removes, which doors end open or unlocked, which containers it empties, and the
local variables the module's own scripts use to remember that a first-visit scene, spawn
or ambush already happened. The editor writes these into the stored area so the player
can come back to a skipped chapter without the area replaying its first visit.

New code (2026-10-23), called by milestone.py for every chapter. IDs only (tags, resrefs,
script names, numbers): nothing taken from the game's text goes into the data files.

What is measured, and how sure each part is:

  remove     placed creatures the enemy data (data/xp/k1-enemies.json) marks hostile and
             that can die (no Plot or Min1HP flag): a full run kills them, certain = true.
             Placed creatures it marks "maybe" (a script turns them hostile): certain = false.
             Objects that scripts reachable in the module destroy by tag (DestroyObject
             (GetObjectByTag)): certain = true when the script is on the chapter's critical
             path, else false. Encounter spawns (.ute) are left alone: the game respawns
             them by design.
  spawned_and_killed
             hostile creatures that scripts create (CreateObject) in the module. They are
             not in the area file, so there is nothing to remove; the locals below are what
             stops their spawn script from running again.
  doors      doors that scripts unlock or open (SetLocked FALSE, ActionOpenDoor), and doors
             whose template is not locked (a full run walks through them; certain = false).
             Locked doors no script opens are listed in uncertain.
  containers_looted
             the chapter's containers (rewards file) in this module, which a full run empties.
  locals     GetLocalBoolean / GetLocalNumber on the area, the module, or a placed trigger,
             placeable or door, read by a script the module runs on its own (module.ifo and
             area events, triggers, placeables, doors), with the values the module's scripts
             set at the same index. A flag that some script sets TRUE is TRUE in a played
             area; a number takes the highest constant written. Indices are the engine's
             local slots (SW_PLOT_BOOLEAN_01 = 0 ... in k_inc_utility).
"""
import collections
import json
import os
import re

import kfmt
import ncsvm

render = ncsvm.render
HERE = os.path.dirname(os.path.abspath(__file__))
ENEMIES = os.path.join(HERE, "..", "..", "data", "xp", "%s-enemies.json")  # k1 / k2

LOCAL_GET = {"GetLocalBoolean": "boolean", "GetLocalNumber": "number"}
LOCAL_SET = {"SetLocalBoolean": "boolean", "SetLocalNumber": "number"}
SELF = ("obj", "OBJECT_SELF")


def _enemies(game="K1"):
    with open(ENEMIES % game.lower(), encoding="utf-8") as f:
        return json.load(f)["modules"]


def _tag_from_notes(notes):
    m = re.match(r"tag (\S+?),", notes or "")
    return m.group(1) if m else None


def owner_of(where):
    """(kind, name) of the object a script runs on, from Milestone.reachable's where text."""
    if where.startswith("module.ifo"):
        return ("module", None)
    m = re.match(r"^(\S+)\.are On", where)
    if m:
        return ("area", m.group(1))
    m = re.match(r"^(\S+)\.(utt|utp|utd|utc) \S+ \(([^)]*)\)", where)
    if m:
        kind = {"utt": "trigger", "utp": "placeable", "utd": "door", "utc": "creature"}[m.group(2)]
        return (kind, m.group(3).lower() or m.group(1))
    return (None, None)


def object_of(v, owner, area):
    """(kind, name) for the object argument of a local call, or None when it is not one
    the stored area keeps (creatures, the player, computed objects)."""
    r = render(v)
    if r.startswith("GetArea("):
        return ("area", area)
    if r == "GetModule()":
        return ("module", None)
    if v == SELF:
        return owner if owner and owner[0] in ("area", "module", "trigger", "placeable", "door") else None
    if isinstance(v, tuple) and v[0] == "call" and v[1] in ("GetObjectByTag", "GetNearestObjectByTag") \
            and v[2] and isinstance(v[2][0], str):
        return ("tag", v[2][0].lower())
    return None


LOCAL_CALLS = set(LOCAL_GET) | set(LOCAL_SET)
_CACHE = {}


def script_locals(ms, name, module):
    """Like Milestone.script, but subroutines that read or write locals are followed too
    (UT_GetPlotBooleanFlag and the like); its own cache, so the milestone's other parts and
    the Endar Spire output are not affected."""
    import nodescript
    name, params, _neg = nodescript.split(name)  # KotOR 2: a script run with parameters
    data, src = ms.g.get(name, kfmt.T_NCS, module)
    if data is None:
        return None, False, None
    key = (hash(data), params)
    if key not in _CACHE:
        import milestone
        saved = ncsvm.RELEVANT
        ncsvm.RELEVANT = set(saved) | milestone.EXTRA_RELEVANT | LOCAL_CALLS | {"DestroyObject", "SetLocked",
                                                                                "ActionOpenDoor"}
        try:
            _CACHE[key] = ncsvm.run_script(data, ms.b.R, params)
        finally:
            ncsvm.RELEVANT = saved
    paths, tr = _CACHE[key]
    return paths, tr, src


def module_cleared(ms, module, reach, crit_scripts, containers, returnable, enemies=None):
    """The cleared section for one module (see the module docstring)."""
    g = ms.g
    enemies = enemies if enemies is not None else _enemies()
    unc = []
    areas = sorted(n for (n, t) in g.module(module) if t == kfmt.T_ARE)
    area = areas[0] if areas else None
    # objects placed in the area
    placed = {}
    for (n, t) in sorted(g.module(module)):
        if t != kfmt.T_GIT:
            continue
        git = g.gff(n, t, module)
        for lst, kind, rt in (("Creature List", "creature", kfmt.T_UTC), ("Placeable List", "placeable", kfmt.T_UTP),
                              ("Door List", "door", kfmt.T_UTD), ("TriggerList", "trigger", kfmt.T_UTT)):
            for inst in git.get(lst) or []:
                tr = (inst.get("TemplateResRef") or "").lower()
                tag = (inst.get("Tag") or "").lower()
                if kind in ("creature", "placeable"):
                    u = g.gff(tr, rt, module)
                    tag = ((u.get("Tag") if u is not None else "") or tag or tr).lower()
                placed.setdefault((kind, tag), []).append(tr)

    # ---- remove
    remove = []
    seen = set()
    mod_en = (enemies.get(module) or {}).get("creatures", [])
    for c in mod_en:
        if c.get("source") != "placed" or c.get("hostile") is False:
            continue
        notes = c.get("notes") or ""
        tag = _tag_from_notes(notes) or ""
        cant_die = "Plot flag set" in notes or "Min1HP set" in notes
        if cant_die:
            unc.append("%s: placed creature %s (template %s) is hostile but its template cannot die (Plot or "
                       "Min1HP); left in place" % (module, tag, c["resref"]))
            continue
        ent = {"tag": tag, "template": c["resref"], "count": c.get("count", 1),
               "why": "placed hostile" if c.get("hostile") is True else "placed, a script turns it hostile",
               "certain": c.get("hostile") is True}
        if c.get("hostile") != True:  # noqa: E712
            ent["evidence"] = notes
        remove.append(ent)
        seen.add(tag)
    destroyed = collections.OrderedDict()
    spawned = collections.OrderedDict()
    for sn in reach:
        paths, _tr, _src = script_locals(ms, sn, module)
        for p in paths or []:
            for name, a, _d in p.calls:
                if name == "DestroyObject" and a:
                    v = a[0]
                    if isinstance(v, tuple) and v[0] == "call" and v[1] in ("GetObjectByTag", "GetNearestObjectByTag") \
                            and v[2] and isinstance(v[2][0], str):
                        destroyed.setdefault(v[2][0].lower(), set()).add(sn)
    for tag, scripts in destroyed.items():
        kinds = [k for (k, t) in placed if t == tag]
        if not kinds:
            continue  # not placed in this area (spawned, an item, or another module's)
        if tag in seen and "creature" in kinds:
            continue
        crit = any(s in crit_scripts for s in scripts)
        remove.append({"tag": tag, "template": placed[(kinds[0], tag)][0], "kind": kinds[0],
                       "why": "destroyed by script", "scripts": sorted(scripts)[:4], "certain": crit})
        if not crit:
            unc.append("%s: %s %s is destroyed by %s, which is not on the curated critical path; it may "
                       "belong to a side quest" % (module, kinds[0], tag, ", ".join(sorted(scripts)[:3])))
    for c in mod_en:
        if c.get("source") == "script" and c.get("hostile") is True:
            spawned[c["resref"]] = _tag_from_notes(c.get("notes")) or ""
    # ---- doors
    script_doors = collections.defaultdict(set)
    for sn in reach:
        paths, _tr, _src = script_locals(ms, sn, module)
        for p in paths or []:
            for name, a, _d in p.calls:
                if name == "SetLocked" and len(a) == 2 and a[1] == 0:
                    t = _tagarg(a[0])
                    if t:
                        script_doors[t].add(("unlock", sn))
                elif name == "ActionOpenDoor" and a:
                    t = _tagarg(a[0])
                    if t:
                        script_doors[t].add(("open", sn))
    doors = []
    for (kind, tag), trs in sorted(placed.items()):
        if kind != "door":
            continue
        u = g.gff(trs[0], kfmt.T_UTD, module)
        locked = bool(u.get("Locked")) if u is not None else False
        key_req = bool(u.get("KeyRequired")) if u is not None else False
        plot = bool(u.get("Plot")) if u is not None else False
        acts = script_doors.get(tag, set())
        if acts:
            scripts = sorted({s for _k, s in acts})
            doors.append({"tag": tag, "template": trs[0], "open": True, "unlocked": True,
                          "why": "a script %s it" % "/".join(sorted({k for k, _s in acts})),
                          "scripts": scripts[:4], "certain": any(s in crit_scripts for s in scripts)})
        elif not locked:
            doors.append({"tag": tag, "template": trs[0], "open": True, "unlocked": True,
                          "why": "not locked; a full run walks through it", "certain": False})
        else:
            unc.append("%s: door %s is locked (%s) and no script here opens it; left as it is" % (
                module, tag, "needs a key" if key_req else ("plot door" if plot else "Security or force")))
    # ---- locals
    locs = collections.OrderedDict()
    for sn, where in reach.items():
        owners = [owner_of(w) for w in where]
        paths, _tr, _src = script_locals(ms, sn, module)
        for p in paths or []:
            for name, a, _d in p.calls:
                if name in LOCAL_GET and len(a) >= 2 and isinstance(a[1], int):
                    for ow in owners:
                        if ow[0] is None or ow[0] == "creature":
                            continue
                        obj = object_of(a[0], ow, area)
                        if obj:
                            e = locs.setdefault((obj, LOCAL_GET[name], a[1]), {"read_by": set(), "set": {}})
                            e["read_by"].add(sn)
                elif name in LOCAL_SET and len(a) == 3 and isinstance(a[1], int):
                    for ow in owners or [(None, None)]:
                        obj = object_of(a[0], ow, area)
                        if obj:
                            e = locs.setdefault((obj, LOCAL_SET[name], a[1]), {"read_by": set(), "set": {}})
                            e["set"].setdefault(render(a[2]), set()).add(sn)
    out_locals = []
    for (obj, kind, idx), e in locs.items():
        if not e["read_by"]:
            continue
        consts = [int(v) for v in e["set"] if re.fullmatch(r"-?\d+", v)]
        exprs = [v for v in e["set"] if not re.fullmatch(r"-?\d+", v)]
        if kind == "boolean":
            value = (1 in consts or any(c != 0 for c in consts)) if consts else None
            if value is True and 0 in consts:
                certain = False
            else:
                certain = value is not None and not exprs
        else:
            value = max(consts) if consts else None
            certain = len(consts) == 1 and not exprs
        objkind, objname = obj
        if objkind == "tag":
            ks = [k for (k, t) in placed if t == objname]
            objkind = ks[0] if ks else "tagged object"
        ent = {"object": objkind, "index": idx, "type": kind, "value": value, "certain": bool(certain),
               "read_by": sorted(e["read_by"])[:6]}
        if objkind not in ("area", "module"):
            ent["tag"] = objname
        elif objkind == "area":
            ent["area"] = objname
        if e["set"]:
            ent["set_by"] = {v: sorted(s)[:4] for v, s in sorted(e["set"].items())}
        else:
            ent["note"] = "read here but no script in the module sets it; leave unchanged"
            ent["value"] = None
            ent["certain"] = False
        if exprs:
            ent["note"] = "also set to values that are not constant: %s" % ", ".join(exprs[:3])
        out_locals.append(ent)
    out_locals.sort(key=lambda x: ({"module": 0, "area": 1}.get(x["object"], 2), x.get("tag", ""), x["type"], x["index"]))
    for ent in out_locals:
        if not ent["certain"] and ent["value"] is not None:
            unc.append("%s: local %s %s %d on %s = %s is not certain (%s)" % (
                module, ent["type"], "index", ent["index"], ent.get("tag") or ent.get("area") or "module",
                json.dumps(ent["value"]), ent.get("note") or "set to more than one value"))
    looted = sorted({c["container"] for c in containers if c["module"] == module})
    return {
        "module": module, "area": area, "returnable": returnable,
        "remove": remove,
        "spawned_and_killed": [{"template": r, "tag": t} for r, t in spawned.items()],
        "doors": doors,
        "containers_looted": looted,
        "locals": out_locals,
        "uncertain": unc,
    }


def _tagarg(v):
    if isinstance(v, tuple) and v[0] == "call" and v[1] in ("GetObjectByTag", "GetNearestObjectByTag") \
            and v[2] and isinstance(v[2][0], str):
        return v[2][0].lower()
    return None
