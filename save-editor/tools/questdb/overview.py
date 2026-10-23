"""Write data/quests/k1-overview.md: every KotOR 1 chapter the Save Editor carries, its counts,
what is uncertain and what must be checked in play.

    python tools/questdb/overview.py

New tool (2026-10-23). It reads only the data files (data/quests, data/xp), so it can run
without the game. IDs only: no game text (KMRP rule, 2026-10-23).
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "data"))

CHAPTERS = ["endar-spire", "taris", "dantooine", "tatooine", "kashyyyk", "manaan", "korriban", "leviathan",
            "unknown-world", "star-forge", "ebon-hawk", "yavin-station"]

# What must be seen in play, per chapter, beyond the generic checks below. Plain words, IDs only.
PLAY_CHECKS = {
    "endar-spire": ["Checked in play on 2026-10-23: the skip plays the vision (stunt_00), lands on Taris "
                    "with 3085 XP and the loot."],
    "taris": ["The first hop is STUNT_06 with movie 05 (k_ptar_tarisover): check that the escape, the turret "
              "scene (m12ab) and the destruction movie play and that the party lands on Dantooine.",
              "All six Taris recruits come from AddAvailableNPCByTemplate: check that slots 0, 1, 2, 6, 7 and 8 "
              "are on the party selection screen after the skip."],
    "dantooine": ["The jedi_class block needs the editor to add a Jedi class level and the matching lightsaber: "
                  "check the class, the level-up and the lightsaber after the skip.",
                  "Return to Dantooine after the skip: the enclave, grove and ruins must not replay their first "
                  "visit (the cleared locals) and the council must not restart the trials.",
                  "The first take-off from the galaxy map must play the Dantooine take-off scene (K_KOTOR_MASTER "
                  "15, K_KALO_BANDON 0)."],
    "tatooine": ["The star map counter (star_map rule): after skipping one, two, three and four free planets "
                 "the next take-off must play the right scene (the Leviathan capture after the third)."],
    "kashyyyk": ["As Tatooine; slot 4 (p_jolee) must be on the party screen."],
    "manaan": ["As Tatooine; man_questend closes several Manaan side quests if the player is banned: check "
               "the journal after the skip."],
    "korriban": ["As Tatooine; the light-side ending of kor35_waysith (stage 60) is assumed."],
    "leviathan": ["The skip leaves slot 0 unavailable (RemoveAvailableNPC 0) and K_KOTOR_MASTER 20: Dantooine "
                  "must turn unselectable on the galaxy map.",
                  "The game plays the Leviathan after the third free planet; skipping it before the fourth must "
                  "still leave the fourth planet playable."],
    "unknown-world": ["The light-side ending (G_FinalChoice 2) is assumed: no party changes. A dark-side run "
                      "changes the party (k_punk_bastjoin) and is not covered."],
    "star-forge": ["The first hop is STUNT_56a with movie 56 (light-side ending): check that the ending plays "
                   "to the end."],
    "ebon-hawk": ["A side chapter: it sets the ship's own quest endings only; its XP counts after Korriban."],
    "yavin-station": ["A side chapter with no quests of its own in the journal; its XP counts after Korriban."],
}


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    rows = []
    sections = []
    for slug in CHAPTERS:
        q = load(os.path.join(DATA, "quests", "k1-%s.json" % slug))
        m = load(os.path.join(DATA, "quests", "k1-%s-milestone.json" % slug))
        r = load(os.path.join(DATA, "quests", "k1-%s-rewards.json" % slug))
        p = load(os.path.join(DATA, "xp", "k1-%s-path.json" % slug))
        planet = (m or q or {}).get("planet", slug)
        nq = len(q["quests"]) if q else 0
        nst = sum(len(x["stages"]) for x in q["quests"]) if q else 0
        nend = sum(1 for x in q["quests"] for s in x["stages"] if s["end"]) if q else 0
        nsteps = sum(len(s["steps"]) for x in q["quests"] for s in x["stages"]) if q else 0
        unc_q = sum(1 for x in q["quests"] if "UNCERTAIN" in (x.get("notes") or "")) if q else 0
        glob_c = [g for g in (m or {}).get("globals", []) if g.get("value") is not None]
        sure = sum(1 for g in glob_c if g.get("certain"))
        cleared = (m or {}).get("cleared", [])
        rem = sum(len(c["remove"]) for c in cleared)
        doors = sum(len(c["doors"]) for c in cleared)
        locs = sum(len(c["locals"]) for c in cleared)
        recruits = [str(x.get("constant") or x.get("slot")) for x in (m or {}).get("party", {}).get("recruit", [])]
        rows.append("| %s | %s | %d | %d | %d | %d | %d | %d (%d certain) | %s | %d / %d / %d | %s | %s |" % (
            (m or {}).get("order", "") if m else "", planet, nq, nst, nend, nsteps, unc_q, len(glob_c), sure,
            ", ".join(recruits) or "none", rem, doors, locs,
            r["xp_chapter"] if r and "xp_chapter" in r else (r["xp_at_end"] if r else "not built"),
            r["xp_at_end"] if r else "not built"))
        S = ["## %s" % planet, ""]
        if m:
            S.append("- Milestone: order %s, %s. Next hop: `%s`%s%s." % (
                m.get("order"), "side chapter" if m.get("side_chapter") else "story chapter",
                (m.get("next_chapter") or {}).get("chain", [{}])[0].get("module"),
                " waypoint `%s`" % m["next_chapter"]["chain"][0]["waypoint"]
                if (m.get("next_chapter") or {}).get("chain", [{}])[0].get("waypoint") else "",
                " with movies %s" % ", ".join("`%s`" % x for x in m["next_chapter"]["chain"][0].get("movies", []))
                if (m.get("next_chapter") or {}).get("chain", [{}])[0].get("movies") else ""))
            S.append("- Journal set: %s%s." % (
                ", ".join("`%s` %d" % (j["tag"], j["stage"]) for j in m.get("journal", [])) or "none",
                ("; removed: " + ", ".join("`%s`" % t for t in m.get("journal_remove", [])))
                if m.get("journal_remove") else ""))
            if m.get("star_map"):
                S.append("- star map: sets `%s`; `K_STAR_MAP` follows the counting rule in the file (the editor "
                         "must count the planet flags, not copy a number)." % m["star_map"]["planet_flag"])
            if m.get("jedi_class"):
                S.append("- Jedi class: the editor must offer the three choices in `jedi_class`.")
            back = sorted({c["module"] for c in cleared if c["returnable"]})
            S.append("- Modules the player can come back to: %s." % (", ".join("`%s`" % x for x in back) or "none"))
        else:
            S.append("- No milestone file yet.")
        if r:
            S.append("- XP: %d for the chapter alone, %d cumulative (`xp_at_end`, from %d)." % (
                r.get("xp_chapter", r["xp_at_end"]), r["xp_at_end"], r.get("xp_start", 0)))
        unc = []
        if m:
            kinds = collections.Counter()
            for u in m.get("uncertain", []):
                if "too large to follow" in u:
                    kinds["large"] += 1
                elif u.startswith("global ") and " = " in u:
                    kinds["value"] += 1
                else:
                    unc.append(u)
            if kinds["large"]:
                S.append("- %d scripts were too large for the analyser to follow completely (listed in the "
                         "milestone file)." % kinds["large"])
            if kinds["value"]:
                S.append("- %d story values are marked certain = false (worked out or seen in one save)."
                         % kinds["value"])
        if unc:
            S.append("")
            S.append("Uncertain (from the milestone file):")
            S.append("")
            for u in unc[:40]:
                S.append("- " + u)
            if len(unc) > 40:
                S.append("- ... and %d more in the milestone file." % (len(unc) - 40))
        S.append("")
        S.append("Check in play:")
        S.append("")
        for c in PLAY_CHECKS.get(slug, []):
            S.append("- " + c)
        S.append("")
        sections.append("\n".join(S))
    L = ["# KotOR 1 chapters in the Save Editor", "",
         "Generated by `save-editor/tools/questdb/overview.py` from the data files. IDs only: quest tags, stage "
         "numbers, resrefs, tags, global names and module names; nothing taken from the game's text.", "",
         "Per chapter: the quest database (`k1-<chapter>.json`, its ID-only review page), the milestone "
         "(`-milestone.json`: the story state a finished chapter leaves, the next hop and the cleared modules), "
         "the rewards (`-rewards.json`: XP and loot) and the XP scenario (`data/xp/k1-<chapter>-path.json`).", "",
         "| Order | Chapter | Quests | Stages | Endings | Steps | Quests with uncertain notes | Story values set "
         "| Recruits | Cleared: remove / doors / locals | XP alone | XP cumulative |",
         "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | ---: |"]
    L += rows
    L += ["", "## What is uncertain everywhere", "",
          "- Every file has `checked`: false. Only the Endar Spire skip has been played.",
          "- Story values come from reading the scripts; where the maintainer's saves cover a chapter (GalaxyMap "
          "after Dantooine, Game224 on Tatooine, Game22 on Manaan, Game133 late on Taris) the values were "
          "compared with them, and the Endar Spire milestone matched the GalaxyMap save except END_BRIDGE_SEALED "
          "(the save predates K1 Community Patch) and END_TRASK_DLG (32: the footlocker was opened once).",
          "- Side quests are not completed by a milestone: their globals stay unchanged (value null) and the "
          "quest database can finish them one by one.",
          "- The XP scenarios are estimates (tools/xp/make_path.py): they count kills, journal XP and the plot "
          "XP of journal steps on one route per quest, and miss plot XP on dialog lines that set no journal "
          "stage, level-scaled computer XP and stealth XP. The editor only raises XP to xp_at_end.",
          "- The cleared sections: certain = false entries (removed by a script off the critical path, unlocked "
          "doors assumed walked through, locals set to more than one value) need a choice by the editor; locals "
          "on creatures are not listed.",
          "- The four free planets and the Leviathan: in the game the Leviathan comes after the third star map, "
          "so the chapter order 4 to 8 is the list's order, not a fixed story order.",
          ""]
    L += sections
    out = os.path.join(DATA, "quests", "k1-overview.md")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    print("wrote", out)


if __name__ == "__main__":
    main()
