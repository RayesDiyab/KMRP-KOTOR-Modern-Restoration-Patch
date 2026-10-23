"""What a full run of a chapter leaves the player with besides the story: the XP and the
loot. Writes data/quests/<game>-<chapter>-rewards.json, read by the editor's Skip Ahead
(src/questdb.rs) together with the chapter's milestone file.

  python tools/questdb/rewards.py --chapter "Endar Spire"      (or --chapter all)

* XP: the full-run scenario in data/xp (every kill, plot XP, script XP and SetXP floor in
  the order a player meets them), played by tools/xp/calc.py. "xp_chapter" is the chapter on
  its own from a new character's 0 XP; "xp_at_end" plays it from the previous chapter's
  xp_at_end in story order (STORY below), so it assumes every earlier chapter was done; side
  chapters (the Ebon Hawk, Yavin Station) start from the chapter named in SIDE_AFTER.
  The editor raises the player's XP and the party pool to xp_at_end; it never lowers them.
  (xp_chapter and the cumulative xp_at_end added 2026-10-23; before that xp_at_end was the
  Endar Spire from 0, which is the same number for the first chapter.)
* Enemy drops: every creature a full run kills (data/xp/k1-enemies.json, hostile or made
  hostile by a script, in the chapter's modules), and of each the items its template marks
  Dropable, carried or worn. Random treasure rolled by scripts at death is not knowable and
  is left out (the milestone file lists those scripts).
* Containers: the milestone file's list, as it is (the editor gives what the player's class
  would find).
* Credits and alignment (added 2026-10-23): what the chapter's conversations and scripts pay
  and take, for a light-side and a dark-side run (credits.py), plus the payments the story
  needs that chapters.py lists as "credits_fixed" (a purchase the main path cannot skip).
  --credits-only rewrites just this part of an existing rewards file.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "xp"))
import gamefiles  # noqa: E402
import calc  # noqa: E402

DATA = os.path.join(HERE, "..", "..", "data")
# Story order for the cumulative XP (the four free planets in the game's usual order).
STORY = ["Endar Spire", "Taris", "Dantooine", "Tatooine", "Kashyyyk", "Manaan", "Korriban", "Leviathan",
         "Unknown World", "Star Forge"]
SIDE_AFTER = {"Ebon Hawk": "Korriban", "Yavin Station": "Korriban"}
# The game the run works on (main's --game; added 2026-10-23 for KotOR 2): its story order and
# side chapters come from chapters.py ("order", "side_chapter", "xp_after").
GAME = "K1"


def pre():
    return GAME.lower()


def story():
    """(main chapters in story order, {side chapter: the chapter its XP follows})."""
    if GAME == "K1":
        return STORY, SIDE_AFTER
    import chapters
    k2 = {p: c for (g, p), c in chapters.CHAPTERS.items() if g == GAME}
    main = sorted((p for p, c in k2.items() if not c.get("side_chapter")), key=lambda p: k2[p].get("order", 99))
    side = {p: c.get("xp_after") or main[-1] for p, c in k2.items() if c.get("side_chapter")}
    return main, side


def chapters():
    """{lower name: {"slug", "planet", "modules"}} for every chapter build.py knows."""
    import build
    g = gamefiles.Game(build.STEAM[GAME])
    out = {}
    for (game, planet), cfg in build.PLANETS.items():
        if game != GAME or planet == "All":
            continue
        mods = [m for m in g.module_names() if m.startswith(cfg["module_prefix"])]
        out[planet.lower()] = {"slug": planet.lower().replace(" ", "-"), "planet": planet, "modules": mods}
    return out
UTC = 2027


def field(s, label):
    for lab, _t, v in s.f:
        if lab == label:
            return v
    return None


def drops_of(game, resref, module):
    """The Dropable items of a creature template, carried and worn: (resref, stack)."""
    got = game.gff(resref, UTC, module)
    if got is None:
        return None
    root = got[1] if isinstance(got, tuple) else got
    out = []
    for listname in ("ItemList", "Equip_ItemList"):
        for it in field(root, listname) or []:
            dropable = field(it, "Dropable")
            res = field(it, "InventoryRes") or field(it, "EquippedRes")
            if res and dropable:
                out.append((res.lower(), 1))
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", required=True, help="a chapter name, or all (story order)")
    ap.add_argument("--game", default="K1")
    ap.add_argument("--game-dir", default=None, help="default: the Steam folder of --game")
    ap.add_argument("--credits-only", action="store_true", help="only (re)write the credits of existing files")
    ap.add_argument("--jobs", type=int, default=6, help="chapters whose credits are worked out at once")
    a = ap.parse_args(argv)
    global GAME
    GAME = a.game
    import build
    a.game_dir = a.game_dir or build.STEAM[GAME]
    allch = chapters()
    order, side = story()
    names = order + list(side) if a.chapter.lower() == "all" else [a.chapter]
    game = gamefiles.Game(a.game_dir)
    # The credits of each chapter are independent of the others (only the XP follows story
    # order), so they are worked out in parallel first, each in its own process (added
    # 2026-10-23: the sequential run took 18 minutes for KotOR 2's eleven chapters).
    ready = [allch[n.lower()] for n in names
             if os.path.exists(os.path.join(DATA, "quests", "%s-%s-milestone.json" % (pre(), allch[n.lower()]["slug"])))]
    credits_of = {}
    if len(ready) > 1 and a.jobs > 1:
        import concurrent.futures
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
            futs = {ch["planet"]: pool.submit(_credits_job, GAME, a.game_dir, ch) for ch in ready}
            credits_of = {k: f.result() for k, f in futs.items()}
    for name in names:
        ch = allch[name.lower()]
        if not os.path.exists(os.path.join(DATA, "quests", "%s-%s-milestone.json" % (pre(), ch["slug"]))):
            print("%s: no milestone file yet, skipped" % ch["planet"])
            continue
        if a.credits_only:
            path = os.path.join(DATA, "quests", "%s-%s-rewards.json" % (pre(), ch["slug"]))
            with open(path, encoding="utf-8") as f:
                out = json.load(f)
            out["credits"] = credits_of.get(ch["planet"]) or chapter_credits(a.game_dir, ch)
            write_json(path, out)
            print("%s: credits light %d, dark %d" % (ch["planet"], out["credits"]["light"]["credits"],
                                                     out["credits"]["dark"]["credits"]))
            continue
        one(game, ch, a.game_dir, credits_of.get(ch["planet"]))


def _credits_job(game, game_dir, ch):
    global GAME
    GAME = game
    sys.setrecursionlimit(20000)
    return chapter_credits(game_dir, ch)


def start_xp(planet):
    """xp_at_end of the chapter before this one in story order (0 for the first)."""
    order, side = story()
    prev = side.get(planet)
    if prev is None:
        i = order.index(planet)
        if i == 0:
            return 0, None
        prev = order[i - 1]
    path = os.path.join(DATA, "quests", "%s-%s-rewards.json" % (pre(), prev.lower().replace(" ", "-")))
    if not os.path.exists(path):
        raise SystemExit("%s needs the rewards file of %s first (cumulative XP)" % (planet, prev))
    with open(path, encoding="utf-8") as f:
        return json.load(f)["xp_at_end"], prev


def chapter_credits(game_dir, ch):
    """credits.py's light and dark totals for the chapter, with chapters.py's credits_fixed."""
    import build
    import chapters
    import credits
    import milestone
    b = build.Builder(game_dir, GAME, ch["planet"])
    ms = milestone.Milestone(b)
    reach = {m: ms.reachable(m) for m in b.modules}
    cfg = chapters.CHAPTERS.get((GAME, ch["planet"]), {})
    out = credits.Credits(b, ms).chapter(reach, cfg.get("credits_side_only"))
    fixed = chapters.CHAPTERS.get((GAME, ch["planet"]), {}).get("credits_fixed", [])
    for row in fixed:
        for side in ("light", "dark"):
            out[side]["credits"] += row[0]
    if fixed:
        out["fixed"] = [dict({"credits": row[0], "note": row[1]}, **({"slot": row[2]} if len(row) > 2 else {}))
                        for row in fixed]
    return out


def write_json(path, out):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")


def one(game, ch, game_dir, credits=None):
    scen = os.path.join(DATA, "xp", "%s-%s-path.json" % (pre(), ch["slug"]))
    rows0 = calc.run_scenario(scen, 0)
    xp_chapter = rows0[-1][2]
    start, prev = start_xp(ch["planet"])
    rows = calc.run_scenario(scen, start)
    xp_end = rows[-1][2]

    enemies = json.load(open(os.path.join(DATA, "xp", "%s-enemies.json" % pre()), encoding="utf-8"))
    drops, missing = {}, []
    killed = 0
    # the creatures the XP scenario kills: the Endar Spire's hand-written scenario counts the ones
    # a script turns hostile ("maybe"); make_path.py's scenarios count them only where CHAPTER_XP says
    import make_path
    endar = ch["slug"] == "endar-spire"
    xp_cfg = make_path.CHAPTER_XP if GAME == "K1" else make_path.k2_chapters()
    maybe = endar or xp_cfg.get(ch["slug"], {}).get("maybe", False)
    for module in ch["modules"]:
        for c in (enemies["modules"].get(module) or {}).get("creatures", []):
            if c.get("hostile") is False or c.get("source") == "encounter":
                continue
            if c.get("hostile") == "maybe" and not maybe:
                continue
            notes = c.get("notes") or ""
            if not endar and ("Plot flag set" in notes or "Min1HP set" in notes):
                continue
            items = drops_of(game, c["resref"], module)
            if items is None:
                missing.append(c["resref"])
                continue
            killed += c.get("count", 1)
            for res, n in items:
                d = drops.setdefault(res, {"resref": res, "count": 0, "from": []})
                d["count"] += n * c.get("count", 1)
                if c["resref"] not in d["from"]:
                    d["from"].append(c["resref"])

    milestone = json.load(open(os.path.join(DATA, "quests", "%s-%s-milestone.json" % (pre(), ch["slug"])),
                               encoding="utf-8"))
    out = {
        "game": GAME,
        "planet": milestone["planet"],
        "generated_by": "tools/questdb/rewards.py",
        "checked": False,
        "xp_at_end": xp_end,
        "xp_chapter": xp_chapter,
        "xp_start": start,
        "xp_note": "full-run scenario data/xp/%s-%s-path.json from %s: %s" % (
            pre(), ch["slug"], ("the %s rewards' xp_at_end, %d XP" % (prev, start)) if prev else "0 XP",
            ", ".join("%s %d" % (m, x) for m, _s, x, _l in rows)),
        "xp_chapter_note": "the same scenario from a new character's 0 XP: %d" % xp_chapter,
        "enemies_killed": killed,
        "drops": sorted(drops.values(), key=lambda d: d["resref"]),
        "templates_missing": missing,
        "containers": milestone["items"].get("container_loot_optional", []),
        "credits": credits or chapter_credits(game_dir, ch),
    }
    path = os.path.join(DATA, "quests", "%s-%s-rewards.json" % (pre(), ch["slug"]))
    write_json(path, out)
    print("%s: XP %d (chapter alone %d), %d kills, %d kinds of drops, %d containers, %d templates missing -> %s" % (
        ch["planet"], xp_end, xp_chapter, killed, len(drops), len(out["containers"]), len(missing), path))


if __name__ == "__main__":
    main(sys.argv[1:])
