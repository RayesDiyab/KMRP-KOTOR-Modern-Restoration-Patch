"""Assemble quest chains from the setters and write the JSON and the review page.

New code for the Save Editor quest database (2026-10-22); called by build.py.
"""
import collections
import json
import os

import chain
import kfmt
from build import plain_need


def load_journal(b):
    root = b.g.gff("global", kfmt.T_JRL)
    _d, src = b.g.get("global", kfmt.T_JRL)
    quests = collections.OrderedDict()
    for c in root.get("Categories") or []:
        tag = (c.get("Tag") or "").lower()
        quests[tag] = {"tag": c.get("Tag") or tag, "name": b.g.text(c.get("Name")),
                       "stages": [{"id": e.get("ID"), "end": bool(e.get("End")), "xp": e.get("XP_Percentage"),
                                   "journal_xp": journal_xp(b, c.get("PlotIndex"), e.get("XP_Percentage")),
                                   "text": b.g.text(e.get("Text"))} for e in c.get("EntryList") or []]}
    return quests, src


def journal_xp(b, plot, pct):
    """XP the game gives when a journal stage is set: the quest's plot.2da row XP times the
    stage's XP_Percentage, rounded (CSWSJournal reading global.jrl at 0x005C5FD5..0x005C6069:
    ftol(base * pct + 0.5f)); AddJournalQuestEntry (0x005483F0) and dialog journal nodes then
    hand it to the party (DistributeExperience). 0 when the quest has no plot row."""
    rows = b.plot_rows()
    if plot is None or plot < 0 or plot >= len(rows) or not pct:
        return 0
    base = int(rows[plot][1].get("xp") or 0)
    return int(base * float(pct) + 0.5)


def build(b):
    ch = chain.Chains(b)
    quests, jsrc = load_journal(b)
    tags = set(quests)
    dsets, ssets = ch.discover(tags)
    refs = ch.script_refs({s for v in ssets.values() for s, _m in v})

    chosen = []
    for tag, q in quests.items():
        if b.owns_tag(tag):
            chosen.append(tag)
            continue
        ids = sorted(s["id"] for s in q["stages"])
        here = {st for (t, st) in list(dsets) + list(ssets) if t == tag}
        ends = {s["id"] for s in q["stages"] if s["end"]}
        if ids and (ids[0] in here or ends & here):
            chosen.append(tag)

    out_quests = []
    report = []
    for tag in chosen:
        q = quests[tag]
        notes, unc = [], []
        local_only = not b.owns_tag(tag)
        if local_only:
            notes.append("This quest is not a %s quest by its tag; only the stages set on %s are listed. "
                         "Other planets also set its stages." % (b.planet, b.planet))
        stages_out = []
        rstages = []
        for s in sorted(q["stages"], key=lambda x: x["id"]):
            sid = s["id"]
            setters = []
            for dn, m, k, i in dsets.get((tag, sid), []):
                st, n, u = ch.dialog_steps(tag, sid, dn, m, k, i)
                setters.append({"kind": "dialog", "name": dn, "module": m, "node": "%s%d" % (k, i),
                                "steps": st, "notes": n, "unc": u})
            for sn, m in ssets.get((tag, sid), []):
                st, n, u, where = ch.script_steps(tag, sid, sn, m, refs)
                setters.append({"kind": "script", "name": sn, "module": m, "steps": st, "notes": n,
                                "unc": u, "where": where})
            merged = merge_copies(setters)
            if not merged:
                if local_only:
                    continue
                unc.append("stage %d has no setter in the %s files (no dialog node or script sets it)"
                           % (sid, b.planet))
            steps = []
            multi = len(merged) > 1
            for n_, se in enumerate(merged):
                if se["also"]:
                    notes.append("stage %d: %s %s gives the same steps in %s"
                                 % (sid, se["kind"], se["name"], ", ".join(se["also"])))
                notes += ["stage %d: %s" % (sid, x) for x in se["notes"] if not x.startswith("UNC:")]
                unc += ["stage %d: %s" % (sid, x[4:]) for x in se["notes"] if x.startswith("UNC:")]
                unc += ["stage %d: %s" % (sid, x) for x in se["unc"]]
                way = None
                if multi:
                    if se["kind"] == "dialog":
                        sp = se["steps"][0]["via"]["speaker"] if se["steps"] else ""
                        way = "way %d: %s, dialog %s %s in %s" % (n_ + 1, sp or "unknown speaker",
                                                                  se["name"], se["node"], se["module"])
                    else:
                        way = "way %d: script %s in %s" % (n_ + 1, se["name"], se["module"])
                for x in se["steps"]:
                    x = dict(x)
                    bad = chain.contradictions(x["needs"])
                    if bad:
                        unc.append("stage %d, %s %s: the needs found contradict each other (%s); "
                                   "the shortest dialog path is probably not the one the game uses"
                                   % (sid, se["kind"], se["name"], "; ".join(bad)))
                    if way:
                        x["branch"] = way + (" / " + x["branch"] if x.get("branch") else "")
                    steps.append(x)
            if multi:
                notes.append("stage %d can be reached in %d ways; each step's branch starts with its way"
                             % (sid, len(merged)))
            st_out = {"stage": sid, "end": s["end"], "steps": steps}
            if s["journal_xp"] > 0:
                # added 2026-10-23: the XP the journal entry itself gives (none on Taris or the Endar Spire)
                st_out["journal_xp"] = s["journal_xp"]
            stages_out.append(st_out)
            rstages.append((s, merged))
        outside = sorted({(m, dn) for (t, _sid), v in dsets.items() if t == tag for dn, m, _k, _i in v
                          if not m.startswith(b.mprefix)})
        if outside:
            notes.append("also set outside %s (not listed): %s"
                         % (b.planet, ", ".join("%s in %s" % (dn, m) for m, dn in outside)))
        globs = b.globals_known()
        bad = sorted({n for st in stages_out for x in st["steps"] for n in global_names(x)
                      if n.lower() not in globs})
        if bad:
            unc.append("globals not listed in globalcat.2da: %s" % ", ".join(bad))
        notes = chain.dedupe(notes)
        unc = chain.dedupe(unc)
        text = " ".join(notes + ["UNCERTAIN: " + u for u in unc])
        rec = {"tag": q["tag"], "stages": stages_out, "notes": text}
        if not local_only:
            # the chapter's own quest, and the ending a full run reaches (the XP scenario's
            # choice: make_path.py ENDINGS, a KotOR 2 chapter's xp endings, else the lowest
            # ending stage with a setter): Skip Ahead closes it there (added 2026-10-23)
            rec["own"] = True
            ends = [st for st in stages_out if st.get("end")]
            want = run_endings(b).get(q["tag"].lower())
            end = next((st for st in ends if st["stage"] == want), None)
            if end is None and ends:
                end = min((st for st in ends if st["steps"]), key=lambda st: st["stage"], default=None) \
                    or min(ends, key=lambda st: st["stage"])
            if end is not None:
                rec["run_ending"] = end["stage"]
        out_quests.append(rec)
        report.append({"tag": q["tag"], "name": q["name"], "stages": rstages, "out": stages_out,
                       "notes": notes, "unc": unc})
    return out_quests, report, jsrc


def merge_copies(setters):
    """Merge copies that give the same steps in several modules; drop unreferenced script copies."""
    merged = []
    for se in setters:
        sig = json.dumps([{k: v for k, v in x.items() if k != "module"} for x in se["steps"]], sort_keys=True)
        for mm in merged:
            if mm["sig"] == sig and mm["kind"] == se["kind"] and mm["name"] == se["name"]:
                mm["also"].append(se["module"])
                break
        else:
            se["sig"] = sig
            se["also"] = []
            merged.append(se)
    referenced = {se["name"] for se in merged if se["kind"] == "script" and se.get("where")}
    return [se for se in merged
            if not (se["kind"] == "script" and not se.get("where") and se["name"] in referenced)]


def global_names(step):
    for n in step.get("needs", []):
        if "global_bool" in n:
            yield n["global_bool"]
        if "global_number" in n:
            yield n["global_number"]
    for d in step.get("does", []):
        for k in ("set_global_bool", "set_global_number"):
            if k in d:
                yield d[k][0]


# ---------------------------------------------------------------- review page
def plain_does(b, d, module, text=False):
    """Plain words for one effect. text=True adds the game's names (local review only: the
    repository holds no text taken from the game, KMRP rule 2026-10-23)."""
    if "set_global_bool" in d:
        return "set %s to %s" % (d["set_global_bool"][0], "TRUE" if d["set_global_bool"][1] else "FALSE")
    if "set_global_number" in d:
        return "set %s to %d" % tuple(d["set_global_number"])
    if "give_item" in d:
        cnt = d["give_item"][1]
        if not text:
            return "give %sitem `%s`" % ("%d x " % cnt if cnt != 1 else "", d["give_item"][0])
        nm = b.item_name(d["give_item"][0])
        return "give %s%s (`%s`)" % ("%d x " % cnt if cnt != 1 else "", nm or "?", d["give_item"][0])
    if "take_item" in d:
        if not text:
            return "take item tag `%s`" % d["take_item"][0]
        nm = b.item_name(d["take_item"][0])
        return "take %s (tag `%s`)" % (nm or "?", d["take_item"][0])
    if "xp" in d:
        return "%d XP" % d["xp"]
    if "light_side" in d:
        return "light side +%d" % d["light_side"]
    if "dark_side" in d:
        return "dark side +%d" % d["dark_side"]
    if "credits" in d:
        return ("%d credits" % d["credits"]) if d["credits"] >= 0 else ("take %d credits" % -d["credits"])
    if "destroy" in d:
        nm = b.creature_name(d["destroy"], module) if text else ""
        return "remove `%s`%s" % (d["destroy"], " (%s)" % nm if nm else "")
    if "door_open" in d:
        return "open door `%s`" % d["door_open"]
    if "door_unlock" in d:
        return "unlock door `%s`" % d["door_unlock"]
    if "journal" in d:
        return "journal %s stage %d" % tuple(d["journal"])
    if "local" in d:
        on, kind, index, value = d["local"]
        return "local %s %d = %d on `%s`" % (kind, index, value, on)
    if "other" in d:
        return d["other"]
    return json.dumps(d)


def run_endings(b):
    """{tag lower: ending stage} a full run takes where the lowest ending is not it."""
    if b.game == "K1":
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "xp"))
        import make_path
        return {k.lower(): v for k, v in make_path.ENDINGS.items()}
    import chapters
    cfg = chapters.CHAPTERS.get((b.game, b.planet), {})
    return {k.lower(): v for k, v in (cfg.get("xp") or {}).get("endings", {}).items()}


def plain_needs(b, needs, text=False):
    out = []
    for n in needs:
        if "item" in n and not text:
            out.append(("has item tag `%s`" if n.get("is", True) else "does not have item tag `%s`") % n["item"])
        elif "item" in n:
            nm = b.item_name(n["item"])
            out.append(("has %s (tag `%s`)" if n.get("is", True) else "does not have %s (tag `%s`)")
                       % (nm or "?", n["item"]))
        else:
            out.append(plain_need(n))
    return "; ".join(out)


def short_text(t, words=14):
    w = " ".join((t or "").split()).split(" ")
    s = " ".join(w[:words])
    return ("Journal: \"" + s + (" ...\"" if len(w) > words else "\"")) if s else ""


def review(b, report, jsrc, out_json, extra_uncertain=None, text=False):
    """The review page. text=False (the committed page) names everything by ID only; text=True
    (written with --review-text to data/quests/local/, which git ignores) adds the quest and
    item names, the speakers' names and the journal text from the player's own game."""
    L = ["# KotOR 1 %s quests: review chain" % b.planet, ""]
    if not text:
        L.append("IDs only: quest tags, stage numbers, dialog and script resrefs with node numbers, item "
                 "resrefs and tags, global names. Run build.py with --review-text for a local copy of this "
                 "page with the game's own names and journal text (data/quests/local/, not committed).")
        L.append("")
    L.append("Generated by `save-editor/tools/questdb/build.py` from the game files (journal from %s). "
             "Each stage lists who sets it, what must be true first, and what happens. "
             "Steps with a branch are alternatives: apply one branch, not all of them. "
             "Steps without a branch always happen. To check a stage, play it and compare the "
             "globals, items and XP." % jsrc)
    L.append("")
    L.append("Data file: `%s`. Its `checked` flag stays false until a person has played these chains."
             % os.path.basename(out_json))
    L.append("")
    L.append("How to read a stage:")
    L.append("")
    L.append("- A step without a branch always happens when the stage is reached that way.")
    L.append("- *way N* names one of several setters of the same stage (another dialog line or script). "
             "Use one way.")
    L.append("- *choice* is a player reply (or the NPC line that follows it) within two lines after the "
             "line that sets the stage. Pick the one the player would have taken.")
    L.append("- *if ...* is a branch inside a script; the game picks it from the save's state "
             "(globals, items, the player's alignment).")
    L.append("- *before this line* is the script on the line just before the one that sets the stage.")
    L.append("- Needs come from the dialog's condition scripts along the shortest path from the start "
             "of the conversation, and from the conditions a script checks before the effect.")
    L.append("- Items in needs and in \"take\" are matched by item tag, as the scripts do; items given "
             "are named by template resref.")
    L.append("- XP on a dialog line is the line's plot XP: plot.2da XP times the line's percentage, "
             "computed with the engine's rounding (two ceilings), so 20% of 500 gives 105.")
    L.append("- In the JSON, a dialog step's `via.list` says whether `node` indexes the entry list or "
             "the reply list; a journal need carries `op` like a global number need.")
    L.append("")
    for q in report:
        L.append(("## %s (`%s`)" % (q["name"] or q["tag"], q["tag"])) if text else ("## `%s`" % q["tag"]))
        L.append("")
        for (s, merged), so in zip(q["stages"], q["out"]):
            L.append("**Stage %d%s%s.** %s" % (s["id"], ", ending" if s["end"] else "",
                                              ", journal XP %d" % s["journal_xp"] if s["journal_xp"] > 0 else "",
                                              short_text(s["text"]) if text else ""))
            L.append("")
            if not so["steps"]:
                L.append("- No setter found.")
            for st in so["steps"]:
                via = st["via"]
                if "dialog" in via:
                    if text:
                        nm = b.creature_name(via["speaker"], st["module"]) if via["speaker"] else ""
                        where = "%s: talk to %s (`%s`), dialog `%s` %s %d" % (
                            st["module"], nm or "?", via["speaker"] or "unknown", via["dialog"],
                            via.get("list", "entry"), via["node"])
                    else:
                        where = "%s: talk to `%s`, dialog `%s` %s %d" % (
                            st["module"], via["speaker"] or "unknown", via["dialog"],
                            via.get("list", "entry"), via["node"])
                else:
                    where = "%s: script `%s`" % (st["module"], via["script"])
                    se = [x for x in merged if x["kind"] == "script" and x["name"] == via["script"]]
                    if se and se[0].get("where"):
                        w = se[0]["where"]
                        where += " (run from %s)" % ", ".join("`%s` %s" % (r[1], r[2]) for r in w[:3])
                L.append("- " + ("*%s*: " % st["branch"] if st.get("branch") else "") + where)
                if st["needs"]:
                    L.append("  - Needs: " + plain_needs(b, st["needs"], text))
                if st["does"]:
                    L.append("  - Does: " + "; ".join(plain_does(b, d, st["module"], text) for d in st["does"]))
                else:
                    L.append("  - Does: nothing found beyond the line itself")
            L.append("")
        if q["notes"]:
            L.append("Notes:")
            L.append("")
            for n in q["notes"]:
                L.append("- " + n)
            L.append("")
    L.append("## Uncertain quests and endings")
    L.append("")
    any_u = False
    for q in report:
        for u in q["unc"]:
            any_u = True
            L.append("- `%s`: %s" % (q["tag"], u))
    for u in extra_uncertain or []:
        any_u = True
        L.append("- " + u)
    if not any_u:
        L.append("- None found by the generator.")
    L.append("")
    return "\n".join(L)


def write(b, a):
    quests, report, jsrc = build(b)
    data = {"game": a.game, "planet": a.planet, "generated_by": "tools/questdb/build.py", "checked": False,
            "quests": quests}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    rp = a.review or os.path.splitext(a.out)[0] + "-review.md"
    with open(rp, "w", encoding="utf-8", newline="\n") as f:
        f.write(review(b, report, jsrc, a.out))
    if getattr(a, "review_text", False):
        # the readable page with the game's text stays on this machine (data/quests/local/)
        lp = os.path.join(os.path.dirname(os.path.abspath(a.out)), "local", os.path.basename(rp))
        os.makedirs(os.path.dirname(lp), exist_ok=True)
        with open(lp, "w", encoding="utf-8", newline="\n") as f:
            f.write(review(b, report, jsrc, a.out, text=True))
        print("wrote", lp)
    nst = sum(len(q["stages"]) for q in quests)
    nend = sum(1 for q in quests for s in q["stages"] if s["end"])
    nsteps = sum(len(s["steps"]) for q in quests for s in q["stages"])
    nneeds = sum(1 for q in quests for s in q["stages"] for x in s["steps"] if x["needs"])
    print("quests %d, stages %d, endings %d, steps %d, steps with needs %d"
          % (len(quests), nst, nend, nsteps, nneeds))
    print("wrote", a.out, "and", rp)
