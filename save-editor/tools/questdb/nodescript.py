"""The scripts a conversation node runs and the condition scripts a link tests, as keys the
script runners take (added 2026-10-23 for KotOR 2).

KotOR 1: a node has one Script and a link one Active, both plain resrefs.
KotOR 2: a node has Script (ActionParam1..5, ActionParamStrA) and Script2 (ActionParam1b..5b,
ActionParamStrB); a link has Active (Param1..5, ParamStrA, Not) and Active2 (Param1b..5b,
ParamStrB, Not2), joined by Logic. The same resref (a_global_set, c_global_eq) does
different things for different parameters, so the key carries them:

    "a_global_set|5,0,0,0,0,000_Atton_Leave"      a script with parameters
    "!c_global_eq|1,0,0,0,0,203tel_bao"            a condition that must be FALSE (Not)

A key without "|" is the plain resref. Builder.script and Milestone.script split keys with
split() and run the script with GetScriptParameter / GetScriptStringParameter bound.
"""


def key(name, params=None, negate=False):
    name = (name or "").lower()
    if not name:
        return ""
    out = ("!" if negate else "") + name
    if params is not None:
        out += "|" + ",".join(str(int(x or 0)) for x in params[:5]) + "," + (params[5] or "")
    return out


def split(k):
    """(resref, params or None, negate) of a key."""
    negate = k.startswith("!")
    if negate:
        k = k[1:]
    if "|" not in k:
        return k, None, negate
    name, rest = k.split("|", 1)
    parts = rest.split(",", 5)
    nums = tuple(int(x) for x in parts[:5])
    return name, nums + (parts[5] if len(parts) > 5 else "",), negate


def is_k2(nd):
    return any(lab == "Script2" for lab, _t, _v in nd.f)


def node_scripts(nd):
    """The keys of the scripts a node runs, in order (empty ones left out)."""
    if not is_k2(nd):
        s = (nd.get("Script") or "").lower()
        return [s] if s else []
    out = []
    for script, suffix, strp in (("Script", "", "ActionParamStrA"), ("Script2", "b", "ActionParamStrB")):
        name = (nd.get(script) or "").lower()
        if name:
            params = tuple(nd.get("ActionParam%d%s" % (i, suffix)) or 0 for i in range(1, 6)) + (nd.get(strp) or "",)
            out.append(key(name, params))
    return out


def link_condition(l):
    """The condition key of a link or a starting-list entry: "" for none. KotOR 2's two
    conditions joined with AND come back as "a;b", with OR as the first alone (the run
    meets the line when either passes)."""
    if not any(lab == "Active2" for lab, _t, _v in l.f):
        return (l.get("Active") or "").lower()
    keys = []
    for active, suffix, strp, notf in (("Active", "", "ParamStrA", "Not"), ("Active2", "b", "ParamStrB", "Not2")):
        name = (l.get(active) or "").lower()
        if name:
            params = tuple(l.get("Param%d%s" % (i, suffix)) or 0 for i in range(1, 6)) + (l.get(strp) or "",)
            keys.append(key(name, params, bool(l.get(notf))))
    # Logic: 0 joins the two with AND, 1 with OR, as the community DLG editors read the
    # field (not checked against the engine)
    if len(keys) == 2 and l.get("Logic") == 1:
        return keys[0]
    return ";".join(keys)
