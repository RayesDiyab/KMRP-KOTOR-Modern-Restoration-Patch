"""Write a chapter's full-run XP scenario (data/xp/k1-<chapter>-path.json) for tools/xp/calc.py.

    python tools/xp/make_path.py --chapter dantooine        (or: all)

New tool (2026-10-23). The Endar Spire scenario was written by hand; this one builds the
others from data that already exists, in the order a player meets it:

  kills      every hostile creature of each module in data/xp/k1-enemies.json: placed and
             script-spawned ones marked hostile = true (and the "maybe" ones the chapter's
             entry below includes), and every active encounter, replayed by calc.py's
             spawn-list code (mean of 200 seeded runs for a party of three).
  quest XP   the chapter's quest database (data/quests/k1-<chapter>.json): for each quest the
             route to one ending (ENDINGS below, else the lowest ending stage the database can
             reach), and for every stage on it the journal XP of the stage plus the largest
             XP of one of its steps (dialog plot XP, GivePlotXP, GiveXPToCreature).
  extra      steps the database cannot see, curated below (Dantooine's AddMultiClass level).

What it cannot know, and leaves out: plot XP on dialog lines that set no journal stage,
computer and repair XP that scales with the player's level (k_inc_utility), stealth XP, and
which of several alternative endings a player chooses. The result is an estimate of a full
run, marked checked = false; the editor only raises XP to it, never lowers.

IDs only: no game text in the files (KMRP rule, 2026-10-23).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "data"))
sys.path.insert(0, HERE)
import calc  # noqa: E402

# Story order of the modules in a full run (the order kills and quest XP are met in).
CHAPTER_XP = {
    "taris": {
        "planet": "Taris",
        "modules": ["tar_m02af", "tar_m02aa", "tar_m02ab", "tar_m02ac", "tar_m02ad", "tar_m02ae", "tar_m03aa",
                    "tar_m03ab", "tar_m03ad", "tar_m03ae", "tar_m04aa", "tar_m05aa", "tar_m05ab", "tar_m10aa",
                    "tar_m10ab", "tar_m10ac", "tar_m03af", "tar_m11aa", "tar_m11ab", "tar_m09aa", "tar_m09ab",
                    "tar_m08aa"],
        "maybe": False,
    },
    "dantooine": {
        "planet": "Dantooine",
        "modules": ["danm13", "danm14aa", "danm14ab", "danm14ac", "danm14ad", "danm14ae", "danm16", "danm15"],
        "maybe": False,
        "extra": [
            # k_pdan_makejedi: AddMultiClass, then DistributeExperience(next exptable threshold - XP)
            {"after": "danm13", "position": "after_quests", "step": {
                "do": "next_level", "what": "danm13 k_pdan_makejedi: AddMultiClass raises XP to the next level "
                                            "(0x0052DDC0)"}},
        ],
    },
    "tatooine": {
        "planet": "Tatooine",
        "modules": ["tat_m17ab", "tat_m17aa", "tat_m17ac", "tat_m17ad", "tat_m17ae", "tat_m17af", "tat_m17ag",
                    "tat_m18aa", "tat_m18ab", "tat_m18ac", "tat_m20aa"],
        "maybe": False,
    },
    "kashyyyk": {
        "planet": "Kashyyyk",
        "modules": ["kas_m22aa", "kas_m22ab", "kas_m23aa", "kas_m23ab", "kas_m23ac", "kas_m23ad", "kas_m24aa",
                    "kas_m25aa"],
        "maybe": False,
    },
    "manaan": {
        "planet": "Manaan",
        "modules": ["manm26ad", "manm26aa", "manm26ab", "manm26ac", "manm26ae", "manm27aa", "manm28aa",
                    "manm28ab", "manm28ac", "manm28ad"],
        "maybe": False,
    },
    "korriban": {
        "planet": "Korriban",
        "modules": ["korr_m33aa", "korr_m33ab", "korr_m34aa", "korr_m35aa", "korr_m36aa", "korr_m37aa",
                    "korr_m38aa", "korr_m38ab", "korr_m39aa"],
        "maybe": False,
    },
    "leviathan": {
        "planet": "Leviathan",
        "modules": ["lev_m40aa", "lev_m40ab", "lev_m40ac", "lev_m40ad"],
        "maybe": False,
    },
    "unknown-world": {
        "planet": "Unknown World",
        "modules": ["unk_m41aa", "unk_m41ab", "unk_m41ac", "unk_m41ad", "unk_m42aa", "unk_m43aa", "unk_m44aa",
                    "unk_m44ab", "unk_m44ac"],
        "maybe": False,
    },
    "star-forge": {
        "planet": "Star Forge",
        "modules": ["sta_m45aa", "sta_m45ab", "sta_m45ac", "sta_m45ad"],
        "maybe": False,
    },
    "ebon-hawk": {
        "planet": "Ebon Hawk",
        "modules": ["ebo_m12aa", "m12ab", "ebo_m40aa", "ebo_m40ad", "ebo_m41aa", "ebo_m46ab"],
        "maybe": False,
    },
    "yavin-station": {
        "planet": "Yavin Station",
        "modules": ["liv_m99aa"],
        "maybe": False,
    },
}

# The ending a full run takes, where the lowest reachable ending is not the one the
# chapter's milestone uses (the light-side endings, tools/questdb/chapters.py).
ENDINGS = {
    "kas23_mainwookplot": 150,
    "man_planet": 70,
    "kor35_waysith": 60,
    "kor37_ajuntapall": 60,
    "unk_trapped": 99,
    "k_pebo_stowaway": 40,
    "k_pebo_gizkatrouble": 30,
    "sta_confront": 99,
}


def stage_xp(s):
    """(the largest XP of one of the stage's steps, the module of that step)."""
    best, best_mod = 0, None
    for st in s["steps"]:
        xp = sum(d["xp"] for d in st["does"] if "xp" in d and isinstance(d["xp"], int))
        if xp > best or best_mod is None:
            best, best_mod = xp, st["module"]
    return best, best_mod or (s["steps"][0]["module"] if s["steps"] else None)


def k2_route(route):
    """KotOR 2 (added 2026-10-23): the stages of one way through a quest. Stages in the same
    group of ten below the ending are alternatives (batono 60 / 63 / 66, ghostrest 30 / 31): a run
    sets one of them, so only the best paying counts; the ending is kept as it is."""
    groups = {}
    for s in route[:-1] if route and route[-1]["end"] else route:
        g = s["stage"] // 10
        pay = stage_xp(s)[0] + (s.get("journal_xp") or 0)
        if g not in groups or pay > groups[g][0]:
            groups[g] = (pay, s)
    out = [s for _p, s in sorted(groups.values(), key=lambda x: x[1]["stage"])]
    if route and route[-1]["end"]:
        out.append(route[-1])
    return out


def quest_steps(slug, notes, game="K1", endings=None, last_module=None):
    """{module: [scenario steps]} of quest XP, from the chapter's quest database."""
    path = os.path.join(DATA, "quests", "%s-%s.json" % (game.lower(), slug))
    with open(path, encoding="utf-8") as f:
        qdb = json.load(f)
    sys.path.insert(0, os.path.join(HERE, "..", "questdb"))
    import build
    pcfg = build.PLANETS[build.planet_key(game, qdb["planet"])]
    prefix = pcfg.get("tag_prefix", ())
    exact = {t.lower() for t in pcfg.get("tags", ())}
    endings = ENDINGS if endings is None else endings
    out = {}
    for q in qdb["quests"]:
        tag = q["tag"].lower()
        if not (tag in exact or (prefix and tag.startswith(prefix))):
            # another chapter's quest, listed for the stages set here (k_xor, the party's own quests,
            # k_starforge): counted once, by its own chapter
            continue
        stages = [s for s in q["stages"] if s["steps"] or s.get("journal_xp")]
        if not stages:
            continue
        ends = [s for s in stages if s["end"]]
        want = endings.get(q["tag"], endings.get(q["tag"].lower()))
        end = next((s for s in ends if s["stage"] == want), None) if want is not None else None
        if end is None and ends:
            end = min(ends, key=lambda s: s["stage"])
        route = [s for s in stages if not s["end"] and (end is None or s["stage"] < end["stage"])]
        if end is not None:
            route.append(end)
        if game == "K2":
            route = k2_route(route)
        for i, s in enumerate(route):
            best, mod = stage_xp(s)
            jx = s.get("journal_xp") or 0
            if best <= 0 and jx <= 0:
                continue
            if mod is None and game == "K2":
                # KotOR 2: a stage whose setter the database could not place is met where the
                # quest's next placed stage is, else at the chapter's end
                mod = next((stage_xp(t)[1] for t in route[i + 1:] if stage_xp(t)[1]), None) or last_module
            if mod is None:
                notes.append("%s stage %d: journal XP %d with no module; left out" % (q["tag"], s["stage"], jx))
                continue
            what = "%s stage %d%s%s" % (q["tag"], s["stage"], ": journal %d" % jx if jx else "",
                                       ", step %d" % best if best else "")
            out.setdefault(mod, []).append({"do": "plot_xp", "xp": best + jx, "what": what})
    return out


def kill_steps(doc, module, include_maybe):
    """Scenario steps for the module's kills: one per template, then the encounters."""
    m = doc["modules"].get(module)
    if m is None:
        return []
    steps = []
    encs = {}
    for c in m["creatures"]:
        ok = c["hostile"] is True or (include_maybe and c["hostile"] == "maybe")
        if not ok or c["challenge_rating"] is None:
            continue
        notes = c.get("notes") or ""
        if "Plot flag set" in notes or "Min1HP set" in notes:
            continue
        if c["source"] == "encounter":
            e = c["encounter"]
            if not e.get("active"):
                continue
            key = (e.get("instance"), e["template"])
            d = encs.setdefault(key, {"do": "encounter", "template": e["template"], "rec": e["rec"], "max": e["max"],
                                      "difficulty_index": e["difficulty_index"], "templates": []})
            d["templates"].append([c["resref"], e["encounter_cr"] or 0.0, e["single_spawn"] or 0,
                                   c["challenge_rating"]])
        else:
            n = c["count"] or 0
            if n:
                step = {"do": "kill", "cr": c["challenge_rating"], "count": n,
                        "what": "%s %s (%s)" % (module, c["resref"], c["source"])}
                if c.get("multiplier_set"):
                    step["multiplier_set"] = c["multiplier_set"]
                    # a placed creature spawns when the area loads: its level is fixed then
                    step["spawned_on_entry"] = c["source"] == "placed"
                steps.append(step)
    for e in encs.values():
        e["what"] = "%s encounter %s" % (module, e["template"])
        steps.append(e)
    return steps


def k2_chapters():
    """KotOR 2's CHAPTER_XP, from the "xp" entry of each chapter file (tools/questdb/chapters_k2):
    {"modules": [story order], "maybe": bool, "extra": [...], "endings": {tag: stage}}."""
    sys.path.insert(0, os.path.join(HERE, "..", "questdb"))
    import chapters
    out = {}
    for (game, planet), cfg in chapters.CHAPTERS.items():
        if game == "K2" and cfg.get("xp"):
            out[planet.lower().replace(" ", "-")] = dict(cfg["xp"], planet=planet)
    return out


def make(slug, game="K1"):
    cfg = CHAPTER_XP[slug] if game == "K1" else k2_chapters()[slug]
    with open(os.path.join(DATA, "xp", "%s-enemies.json" % game.lower()), encoding="utf-8") as f:
        doc = json.load(f)
    notes = []
    qs = quest_steps(slug, notes, game, None if game == "K1" else cfg.get("endings", {}), cfg["modules"][-1])
    unplaced = [m for m in qs if m not in cfg["modules"]]
    modules = []
    for mod in cfg["modules"] + unplaced:
        steps = kill_steps(doc, mod, cfg.get("maybe"))
        steps += qs.get(mod, [])
        for ex in cfg.get("extra", []):
            if ex["after"] == mod:
                steps.append(ex["step"])
        modules.append({"module": mod, "steps": steps})
    out = {
        "game": game,
        "what": "A full %s run: kills (hostile creatures and active encounters of each module), then the quest "
                "XP met in that module, in module order. Written by tools/xp/make_path.py; read by "
                "tools/xp/calc.py --scenario." % cfg["planet"],
        "checked": False,
        "assumptions": [
            "Every creature data/xp/%s-enemies.json marks hostile is killed%s; creatures whose template cannot die "
            "(Plot, Min1HP) are left out." % (game.lower(), ", and those a script may turn hostile" if cfg.get("maybe") else
                                              "; creatures a script may turn hostile (hostile = maybe) are left out"),
            "Active encounters spawn as calc.py replays the engine's spawn list for a party of three (mean of "
            "200 seeded runs); encounters that respawn are counted once.",
            "Only the chapter's own quests (build.py PLANETS tag_prefix) count; a quest of another chapter that "
            "this chapter's files also set is counted by its own chapter.",
            "Each quest follows one route to one ending (the lowest ending stage the quest database reaches unless "
            "make_path.py ENDINGS names another); a stage gives its journal XP and the largest XP of one of its "
            "steps.",
            "Not counted: plot XP on dialog lines that set no journal stage, level-scaled computer and repair XP, "
            "stealth XP.",
        ] + notes,
        "modules": modules,
    }
    if game == "K2":
        out["assumptions"].append("KotOR 2's kill XP follows swkotor2.exe 1.0.2 (calc.py use_game): its own tables, "
                                  "and a creature with an autobalance row (MultiplierSet) counted at the player's "
                                  "level when it spawns plus the row's crmod: a placed creature at the player's "
                                  "level on entering the module, a script's at the level of the kill. Encounter "
                                  "creatures are counted at their rating.")
    path = os.path.join(DATA, "xp", "%s-%s-path.json" % (game.lower(), slug))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    rows = calc.run_scenario(path, 0)
    print("%s: %d modules, from 0 XP to %d (level %d) -> %s" % (slug, len(modules), rows[-1][2], rows[-1][3], path))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", required=True, help="a key of CHAPTER_XP, or all")
    ap.add_argument("--game", default="K1")
    a = ap.parse_args(argv)
    known = CHAPTER_XP if a.game == "K1" else k2_chapters()
    for slug in (known if a.chapter == "all" else [a.chapter.lower().replace(" ", "-")]):
        if not os.path.exists(os.path.join(DATA, "quests", "%s-%s.json" % (a.game.lower(), slug))):
            print("%s: no quest database yet, skipped" % slug)
            continue
        make(slug, a.game)


if __name__ == "__main__":
    main(sys.argv[1:])
