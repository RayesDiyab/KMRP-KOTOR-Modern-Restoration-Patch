"""Build data/xp/k1-enemies.json (or k2-enemies.json): the creatures a player can kill,
module by module.

Usage:
    python -I extract_enemies.py <game root> <out.json> [--as-loaded] [--k2]

--k2 (added 2026-10-23) reads KotOR 2: its party members' tags, and the conversations it
keeps in <module>_dlg.erf.

By default the game is read the way the unmodded 1.0.3 game ships it: modules come from
modules/<name>.rim and <name>_s.rim, global resources from chitin.key, and the Override
folder and any modules/*.mod are ignored. With --as-loaded the file lookup matches what
the installed game really loads (Override first, a .mod replaces the module's .rim
pair), which is what a K1 Community Patch install plays.

Read only: nothing in the game folder is written.

Sources per module:
  placed     the area's .git Creature List (one entry per placed creature)
  encounter  the .git Encounter List; the .ute template gives the creature list,
             RecCreatures (minimum spawned) and MaxCreatures (maximum)
  script     CreateObject(OBJECT_TYPE_CREATURE, "<constant resref>", ...) in the
             module's scripts and in the global scripts the module's files name

Hostility follows the engine's kill XP test (CSWSCreature::ApplyDeathExperience,
0x004FB1E0 in swkotor.exe 1.0.3): XP is awarded only when the reputation of the
creature's faction toward the player, repute.2da row "Player", is 10 or less. A
creature whose faction is friendly or neutral but which a script moves to a hostile
faction (ChangeToStandardFaction / ChangeFaction) is reported as "maybe".

Origin: written 2026-10-23 for the Save Editor's "skip to a point in the story" XP
research; reuses tools/questdb (kfmt, gamefiles, nwsig, ncsvm).
"""
import collections
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "questdb"))
import gamefiles  # noqa: E402
import kfmt  # noqa: E402
import ncsvm  # noqa: E402
import nwsig  # noqa: E402

sys.path.insert(0, HERE)
import ncsflat  # noqa: E402

T_UTE = 2040
MAX_PATHS = 300
OBJECT_TYPE_CREATURE = 1
PARTY_TAGS = {"bastila", "cand", "carth", "hk47", "jolee", "juhani", "mission", "t3m4", "zaalbar",
              "canderous"}
# KotOR 2's party (npc.2da) and the tags its templates use
PARTY_TAGS_K2 = {"atton", "baodur", "mand", "mandalore", "g0t0", "handmaiden", "hk47", "kreia", "mira", "t3m4",
                 "visasmarr", "hanharr", "disciple", "remote"}
GFF_TYPES = (kfmt.T_UTC, kfmt.T_UTP, kfmt.T_UTD, kfmt.T_UTT, T_UTE, kfmt.T_DLG, kfmt.T_ARE,
             kfmt.T_IFO, kfmt.T_GIT, kfmt.T_UTS)
WANTED_CALLS = ("CreateObject", "ChangeToStandardFaction", "ChangeFaction")

ncsvm.RELEVANT |= set(WANTED_CALLS)


class VanillaGame(gamefiles.Game):
    """gamefiles.Game without Override and without modules/*.mod."""

    def __init__(self, root):
        super().__init__(root)
        self.override = {}

    def module_source(self, module):
        return [f for f in (module + ".rim", module + "_s.rim", module + "_dlg.erf") if f in self.modfiles]


def render(v):
    return ncsvm.render(v)


def strings_in(s, out):
    """Every string value in a GFF struct tree."""
    for _label, _t, v in s.f:
        if isinstance(v, str):
            if v:
                out.add(v.lower())
        elif isinstance(v, kfmt.S):
            strings_in(v, out)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, kfmt.S):
                    strings_in(x, out)
    return out


class Extractor:
    def __init__(self, root, as_loaded, k2=False):
        self.g = gamefiles.Game(root) if as_loaded else VanillaGame(root)
        self.party = PARTY_TAGS_K2 if k2 else PARTY_TAGS
        self.game = "K2" if k2 else "K1"
        self.as_loaded = as_loaded
        text = self.g.get("nwscript", kfmt.T_NSS)[0].decode("latin-1")
        self.R = nwsig.parse(text)
        self.rid = {name: i for i, (name, _r, _p) in enumerate(self.R)}
        self.needles = [b"\x05\x00" + struct.pack(">H", self.rid[n]) for n in WANTED_CALLS]
        cols, rows = kfmt.twoda(self.g.get("repute", kfmt.T_2DA)[0])
        player = rows[0][1]
        # faction id N is column N (column 0 is the label); the engine reads element N-1
        # of the Player row (CFactionManager::GetNPCReputation(N, 0), 0x0052B420).
        self.rep = {i: int(player[c]) for i, c in enumerate(cols) if i > 0}
        self.faction_name = {i: c for i, c in enumerate(cols) if i > 0}
        self.script_cache = {}
        self.chitin_ncs = set(self.g.chitin_names(kfmt.T_NCS))

    # ------------------------------------------------------------ helpers
    def hostile_faction(self, fid):
        return fid in self.rep and self.rep[fid] <= 10

    def utc(self, resref, module):
        s = self.g.gff(resref, kfmt.T_UTC, module)
        if s is None:
            return None
        levels = sum(c.get("ClassLevel") or 0 for c in (s.get("ClassList") or []))
        return {
            "tag": (s.get("Tag") or "").lower(),
            "cr": float(s.get("ChallengeRating") or 0.0),
            "level": levels,
            "faction": s.get("FactionID"),
            "plot": s.get("Plot") or 0,
            "min1hp": s.get("Min1HP") or 0,
            "is_pc": s.get("IsPC") or 0,
            "conversation": (s.get("Conversation") or "").lower(),
            "scripts": sorted({(v or "").lower() for a, _t, v in s.f if a.startswith("Script") and v}),
            # KotOR 2: the autobalance.2da row; a creature with one is scaled to the player's level
            # when it spawns, and its kill XP follows that level (calc.py kill_award)
            "multiplier_set": s.get("MultiplierSet") or 0,
        }

    def script_calls(self, name, data):
        """Wanted engine calls of one script: (name, args) per call site.

        A flat walk (ncsflat) lists each call site once. When a CreateObject site has a
        creature type but a resref that is not a constant (a helper such as
        UT_CreateObject passes it in), the script is also run path by path (ncsvm,
        limited to MAX_PATHS paths) and the constant resrefs found that way are added.
        """
        if name in self.script_cache:
            return self.script_cache[name]
        out = []
        if data and any(n in data for n in self.needles):
            flat = ncsflat.analyse(data, self.R) or {"calls": []}
            need_paths = False
            for fn, args in flat["calls"]:
                if fn not in WANTED_CALLS:
                    continue
                out.append((fn, tuple(args)))
                if fn == "CreateObject" and len(args) >= 2 and args[0] in (str(OBJECT_TYPE_CREATURE), "?", "var") \
                        and not args[1].startswith('"'):
                    need_paths = True
            if need_paths:
                m = ncsvm.Machine(data, self.R, max_paths=MAX_PATHS)
                paths = m.run(13)
                seen = {(fn, a) for fn, a in out}
                for p in paths:
                    for call in p.calls:
                        if call[0] != "CreateObject":
                            continue
                        key = (call[0], tuple(render(a) for a in call[1]))
                        if key not in seen and len(key[1]) >= 2 and key[1][1].startswith('"'):
                            seen.add(key)
                            out.append(key)
                if m.truncated or any("truncated" in p.flags for p in paths):
                    out.append(("__truncated__", ()))
        self.script_cache[name] = out
        return out

    # ------------------------------------------------------------ one module
    def module(self, mod):
        res = self.g.module(mod)
        gits = [k for k in res if k[1] == kfmt.T_GIT]
        if not gits:
            return None
        git = kfmt.gff(res[gits[0]])[1]
        notes = []

        # names referenced by the module's own files, to pick up global scripts and dialogs
        refs = set()
        for (n, t), d in res.items():
            if t in GFF_TYPES:
                try:
                    strings_in(kfmt.gff(d)[1], refs)
                except Exception:
                    pass
        # one more hop: global dialogs named by module files
        for r in list(refs):
            if (r, kfmt.T_DLG) not in res:
                d, _src = self.g.get(r, kfmt.T_DLG)
                if d:
                    try:
                        strings_in(kfmt.gff(d)[1], refs)
                    except Exception:
                        pass

        scripts = {}
        for (n, t), d in res.items():
            if t == kfmt.T_NCS:
                scripts[n] = (d, "module")
        for r in refs:
            if r not in scripts and r in self.chitin_ncs:
                d, src = self.g.get(r, kfmt.T_NCS)
                scripts[r] = (d, src)

        spawns = collections.Counter()
        spawn_where = collections.defaultdict(set)
        faction_changes = []
        truncated = []
        for name, (data, _src) in sorted(scripts.items()):
            for fn, args in self.script_calls((mod, name) if _src == "module" else name, data):
                if fn == "__truncated__":
                    truncated.append(name)
                elif fn == "CreateObject":
                    if len(args) >= 2 and args[0] == str(OBJECT_TYPE_CREATURE) and args[1].startswith('"'):
                        rr = args[1].strip('"').lower()
                        spawns[rr] += 1
                        spawn_where[rr].add(name)
                elif fn in ("ChangeToStandardFaction", "ChangeFaction"):
                    faction_changes.append((name, fn, args))

        hostile_change_scripts = set()
        hostile_change_text = []
        for name, fn, args in faction_changes:
            if fn == "ChangeToStandardFaction":
                try:
                    fid = int(args[1])
                except (ValueError, IndexError):
                    fid = None
                if fid is None or self.hostile_faction(fid):
                    hostile_change_scripts.add(name)
                    hostile_change_text.append(args[0].lower())
            else:
                hostile_change_scripts.add(name)
                hostile_change_text.append(args[0].lower() if args else "")

        def dialog_scripts(conv):
            if not conv:
                return set()
            d, _s = self.g.get(conv, kfmt.T_DLG, mod)
            if not d:
                return set()
            try:
                return strings_in(kfmt.gff(d)[1], set())
            except Exception:
                return set()

        def hostility(info):
            if info is None:
                return "maybe", "template not found"
            if info["tag"] in self.party or info["is_pc"]:
                return False, "party member"
            if self.hostile_faction(info["faction"]):
                return True, ""
            why = []
            if info["tag"] and any(('"%s"' % info["tag"]) in t for t in hostile_change_text):
                why.append("a script moves its tag to a hostile faction")
            own = set(info["scripts"]) | dialog_scripts(info["conversation"])
            hit = sorted(own & hostile_change_scripts)
            if hit:
                why.append("its own or its dialog's script changes faction: " + ", ".join(hit[:4]))
            if why:
                return "maybe", "; ".join(why)
            return False, ""

        def entry(resref, count, source, extra_notes=""):
            info = self.utc(resref, mod)
            hostile, why = hostility(info)
            n = [x for x in (why, extra_notes) if x]
            if info:
                if info["plot"]:
                    n.append("Plot flag set in the template (cannot die unless a script clears it)")
                if info["min1hp"]:
                    n.append("Min1HP set in the template (cannot die unless a script clears it)")
                fac = info["faction"]
                # IDs only: no names from the game's text (KMRP rule, 2026-10-23)
                n.insert(0, "tag %s, faction %s (%s), level %d" % (
                    info["tag"] or "?", fac, self.faction_name.get(fac, "?"), info["level"]))
            out_entry = {
                "resref": resref,
                "count": count,
                "challenge_rating": info["cr"] if info else None,
                "source": source,
                "hostile": hostile,
                "notes": "; ".join(n),
            }
            if info and info.get("multiplier_set"):
                out_entry["multiplier_set"] = info["multiplier_set"]
            return out_entry

        out = []
        placed = collections.Counter((c.get("TemplateResRef") or "").lower() for c in (git.get("Creature List") or []))
        for rr, cnt in sorted(placed.items()):
            if rr:
                out.append(entry(rr, cnt, "placed"))

        for instance, e in enumerate(git.get("Encounter List") or []):
            tr = (e.get("TemplateResRef") or "").lower()
            ute = self.g.gff(tr, T_UTE, mod)
            if ute is None:
                notes.append("encounter template %s not found" % tr)
                continue
            rec, mx = ute.get("RecCreatures") or 0, ute.get("MaxCreatures") or 0
            active, respawns, reset = ute.get("Active"), ute.get("Respawns"), ute.get("Reset")
            clist = ute.get("CreatureList") or []
            fac = ute.get("Faction")
            for c in clist:
                rr = (c.get("ResRef") or "").lower()
                txt = ("encounter %s (tag %s): spawns %d to %d creatures in all from %d template(s); this "
                       "template's encounter CR %g, single spawn %d; Active %s, Respawns %s, Reset %s, "
                       "encounter faction %s, DifficultyIndex %s" % (
                           tr, e.get("Tag") or ute.get("Tag"), rec, mx, len(clist), c.get("CR") or 0,
                           c.get("SingleSpawn") or 0, active, respawns, reset, fac, ute.get("DifficultyIndex")))
                ent = entry(rr, None, "encounter", txt)
                ent["encounter"] = {
                    "instance": instance, "template": tr, "tag": e.get("Tag") or ute.get("Tag"),
                    "rec": rec, "max": mx,
                    "active": active, "respawns": respawns, "reset": reset,
                    "difficulty_index": ute.get("DifficultyIndex"), "player_only": ute.get("PlayerOnly"),
                    "entries": len(clist), "encounter_cr": c.get("CR"), "single_spawn": c.get("SingleSpawn"),
                }
                if ent["hostile"] is False and self.hostile_faction(fac):
                    ent["notes"] += "; the creature template's faction is not hostile but the encounter's is"
                out.append(ent)

        for rr, cnt in sorted(spawns.items()):
            out.append(entry(rr, cnt, "script", "CreateObject call sites: %d, in %s" % (
                cnt, ", ".join(sorted(spawn_where[rr])[:6]))))

        if truncated:
            notes.append("path limit reached in scripts: " + ", ".join(sorted(set(truncated))[:10]))
        src = self.g.module_source(mod)
        return {"archives": src, "creatures": out, "notes": notes}

    def run(self):
        mods = {}
        for mod in self.g.module_names():
            r = self.module(mod)
            if r is not None:
                mods[mod] = r
            print(mod, len(r["creatures"]) if r else "-", file=sys.stderr)
        return mods


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_loaded = "--as-loaded" in sys.argv
    root, outp = args[0], args[1]
    ex = Extractor(root, as_loaded, "--k2" in sys.argv)
    mods = ex.run()
    doc = {
        "game": ex.game,
        "generated_by": "tools/xp/extract_enemies.py",
        "files": "as the installed game loads them (Override, modules/*.mod)" if as_loaded
                 else "unmodded game files only (chitin.key and modules/*.rim; Override and .mod ignored)",
        "rule": ("Kill XP is awarded by the engine on death (CSWSCreature::ApplyDeathExperience 0x004FB1E0), "
                 "to the PC in full and to every active party member, when the victim is not a party member and "
                 "repute.2da Player row for its faction is <= 10. Amount: xptable.2da row (PC level from XP) - 1, "
                 "column c<trunc(ChallengeRating)>; see tools/xp/calc.py."),
        "hostile_factions": {str(k): ex.faction_name[k] for k in sorted(ex.rep) if ex.hostile_faction(k)},
        "count_meaning": ("placed: creatures in the .git; script: distinct CreateObject call sites (a loop or a "
                          "script that runs more than once can spawn more, a branch can spawn fewer); encounter: "
                          "null, the per-encounter range is in 'encounter' (rec..max for the whole encounter)"),
        "modules": mods,
    }
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    sys.setrecursionlimit(20000)
    main()
