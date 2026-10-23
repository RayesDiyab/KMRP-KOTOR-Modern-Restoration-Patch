"""Build the Save Editor's quest database for one planet from the game files.

Usage:
    python save-editor/tools/questdb/build.py --game K1 --planet Taris \
        --out save-editor/data/quests/k1-taris.json [--game-dir <KotOR folder>] [--review <md path>]
    python save-editor/tools/questdb/build.py --game K1 --planet "Endar Spire" \
        --out save-editor/data/quests/k1-endar-spire.json \
        --milestone save-editor/data/quests/k1-endar-spire-milestone.json

Reads the game read-only (default: the Steam folder). Writes the JSON chain described
in the editor's schema and a review page (default: <out stem>-review.md). The planets
that are set up are in PLANETS below. --milestone also writes the story state at the
end of the planet (milestone.py; every K1 chapter, curated in chapters.py). --review-text also
writes the review page with the game's own names and text to data/quests/local/ (not committed).

Where the pieces came from (research scratchpad, 2026-10-22):
  kfmt.py      the scratchpad's kfmt.py (ERF/RIM/GFF/KEY/BIF), plus TLK and 2DA readers
  gamefiles.py lookup order from ncsscan.py collect() and classify.py effective()
  nwsig.py     the scratchpad's nwsig.py, with nested-comma and constant parsing
  ncsvm.py     instruction decoding from ncsscan.py, rewritten to run each path apart
  build.py     setter discovery from questmap.py, dialog neighbourhood from dlgnear.py
               (parent, node, two levels of children); everything else is new here.

Engine facts used (from github.com/mattlgroff/swkotor1-reconstruction, GOG 1.03):
  - dialog nodes grant plot XP: CSWSDialog::GiveDialogPlotXP (0x0059F3C0) with the
    node's PlotIndex and PlotXPPercentage; CSWPartyTable::GivePlotXP (0x005666E0):
    xp = ceil(plot.2da XP * ceil(percent * 100) * 0.01)
  - GivePlotXP(name, percent) in scripts (0x00566600): xp = ceil(plot.2da XP(row name) * percent * 0.01)
  - AddJournalQuestEntry only raises a quest's stage (unless bAllowOverrideHigher).
"""
import argparse
import collections
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gamefiles  # noqa: E402
import kfmt  # noqa: E402
import ncsvm  # noqa: E402
import nwsig  # noqa: E402
import nodescript  # noqa: E402

STEAM_K1 = r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"
# KotOR 2 (added 2026-10-23): the maintainer's Steam copy, Aspyr's current release, no mods.
STEAM_K2 = r"D:\SteamLibrary\steamapps\common\Knights of the Old Republic II"
STEAM = {"K1": STEAM_K1, "K2": STEAM_K2}
# A planet is the set of modules whose names start with one of module_prefix, and the
# journal quests whose tags start with one of tag_prefix (those count as the planet's own
# quests; other quests are listed only for the stages these modules set). Both are tuples
# so a planet can span several naming schemes. Names match case-insensitively on --planet.
#
# extra_dialogs / extra_scripts (regular expressions on resref, optional): dialogs and scripts
# that live outside every module archive (chitin, Override) and are scanned as if they
# belonged to the planet's first module. Only the Ebon Hawk uses them, for the party
# members' own conversations (k_h*_dialog in templates.bif) and their scripts.
PLANETS = {
    ("K1", "Taris"): {"module_prefix": ("tar_m",), "tag_prefix": ("tar_",)},
    # end_m01aa (the ship up to the bridge) and end_m01ab (Carth and the escape pods)
    ("K1", "Endar Spire"): {"module_prefix": ("end_m",), "tag_prefix": ("end_",)},
    # danm13 the Enclave, danm14aa-ae the courtyard, grove, Matale and Sandral grounds,
    # danm15 the ruins, danm16 the Mandalorian camp
    ("K1", "Dantooine"): {"module_prefix": ("danm",), "tag_prefix": ("dan_",)},
    ("K1", "Tatooine"): {"module_prefix": ("tat_m",), "tag_prefix": ("tat",)},
    ("K1", "Kashyyyk"): {"module_prefix": ("kas_m",), "tag_prefix": ("kas",)},
    # the Genoharadan quests start with Hulas in manm26ae
    ("K1", "Manaan"): {"module_prefix": ("manm",), "tag_prefix": ("man", "geno")},
    # "Category000" is the journal tag of The Code of the Sith (Uthar and Yuthura, korr_m35aa)
    ("K1", "Korriban"): {"module_prefix": ("korr_m",), "tag_prefix": ("kor", "category000")},
    ("K1", "Leviathan"): {"module_prefix": ("lev_m",), "tag_prefix": ("lev_",)},
    ("K1", "Unknown World"): {"module_prefix": ("unk_m",), "tag_prefix": ("unk_",)},
    ("K1", "Star Forge"): {"module_prefix": ("sta_m",), "tag_prefix": ("sta_",)},
    # ebo_m12aa the Ebon Hawk between planets, m12ab its interior during the Sith boarding,
    # ebo_m40aa / ebo_m40ad on the Leviathan, ebo_m41aa at the Unknown World, ebo_m46ab the
    # Unfinished Business fight. Party members' quests are set in their own conversations.
    ("K1", "Ebon Hawk"): {"module_prefix": ("ebo_m", "m12ab"),
                          "tag_prefix": ("ebo", "k_pebo_", "k_ebonhawk", "k_swg_", "k_missbroth", "k_jagi",
                                         "k_xor"),
                          "extra_dialogs": r"^k_h\w+_dialog\w*$",
                          "extra_scripts": r"^k_(swg|hbas|hcan|hcar|hhk|hjol|hjuh|hmis|hzaa|ht3m|hjagi|hxor|hlena|pebo|pebn)"},
    ("K1", "Yavin Station"): {"module_prefix": ("liv_m",), "tag_prefix": ("liv", "yav")},
    # every KotOR 2 module, for surveys
    ("K2", "All"): {"module_prefix": tuple("0123456789"), "tag_prefix": ("",)},
    # ---- KotOR 2 (added 2026-10-23). Its journal tags share no prefixes, so each chapter
    # lists its own ("tags", exact; from a survey of every module: the chapter whose modules
    # set the tag most), and its story values are named by module number ("global_prefix").
    # module_prefix lists whole module names: 262tel belongs to Telos; the masters' meeting
    # and the return to Telos are "The Jedi Masters". Moved after the chapters were curated:
    # 950cor (left only from 262tel's first visit) to Telos; 004ebo and 007ebo (the ship landed
    # on Nar Shaddaa and the yacht's aftermath) with landingrights to Nar Shaddaa;
    # galactichistory to Peragus, traces to Korriban, altroute to Dxun (where they end), and
    # lightsaberquest, the party's quest across planets, to the Ebon Hawk.
    ("K2", "Peragus"): {"module_prefix": ("001ebo", "002ebo", "101per", "102per", "103per", "104per", "105per", "106per", "107per", "151har", "152har", "153har", "154har", "005ebo",),
                 "tags": ("galactichistory", "medbaymur", "orbitaldriftcharts", "pazaak_rules", "pazaak_rules2", "recenthistory", "recoverebonhawk", "rescuepc", "rescuet3", "turboliftlockdown", "tutorial_3cfd", "tutorial_fix_ebo", "tutorial_garage", "tutorial_heal_pc", "voiceprintprotocol",),
                 "global_prefix": ("001", "002", "005", "101", "102", "103", "104", "105", "106", "107", "151", "152", "153", "154",)},
    ("K2", "Telos"): {"module_prefix": ("201tel", "202tel", "203tel", "204tel", "205tel", "207tel", "208tel", "209tel", "211tel", "231tel", "232tel", "233tel", "261tel", "262tel", "950cor",),
                 "tags": ("arrested", "batono", "baturem", "blackmarket", "caller", "czerka_attack", "czerkacall", "czerkamain", "ehind", "ehstolen", "exch_meeting", "exchange", "falt", "high_stakes", "ithdip", "killers", "luxa", "merc_attack", "opo_chano", "restdroid", "smuggling", "smuggling_tsf", "yima",),
                 "global_prefix": ("201", "202", "203", "204", "205", "207", "208", "209", "211", "231", "232", "233", "261", "262", "950",)},
    ("K2", "Nar Shaddaa"): {"module_prefix": ("301nar", "302nar", "303nar", "304nar", "305nar", "306nar", "351nar", "352nar", "371nar", "004ebo", "007ebo",),
                 "tags": ("30001", "30002", "30003", "30004", "30005", "30006", "30007", "30008", "30010", "30011", "30012", "bithstd", "dancer", "droid_warehouse", "droidretrieval", "droidwarehousepuzzle", "ebonhawkidsignature", "fuel", "intergru", "landingrights", "lupoadv", "newtraderoutes", "papass", "pdchamp", "pddahn", "pds4c8", "pdsv", "tradewar", "voggahorde", "voggathehutt",),
                 "global_prefix": ("004", "007", "301", "302", "303", "304", "305", "306", "351", "352", "371",)},
    ("K2", "Dxun"): {"module_prefix": ("401dxn", "402dxn", "403dxn", "404dxn", "410dxn", "411dxn", "421dxn",),
                 "tags": ("altroute", "battle_circle", "explosivesit", "foutpost", "missingm", "pricepassage", "scouthunt", "tcannoks", "tsupport", "zchallenge",),
                 "global_prefix": ("401", "402", "403", "404", "410", "411", "421",)},
    ("K2", "Onderon"): {"module_prefix": ("501ond", "502ond", "503ond", "504ond", "505ond", "506ond", "510ond", "511ond", "512ond",),
                 "tags": ("cantinarats", "deadline", "docalibi", "escape_merchant", "master_palace", "matter_leader", "starportvisa",),
                 "global_prefix": ("501", "502", "503", "504", "505", "506", "510", "511", "512",)},
    ("K2", "Dantooine"): {"module_prefix": ("601dan", "602dan", "603dan", "604dan", "605dan", "610dan",),
                 "tags": ("akkere_hydro", "cavecrawl", "chguard", "danthief", "ghostrest", "khoonda_doors", "khoonda_droids", "khoonda_guns", "khoonda_medic", "khoonda_morale", "khoonda_traps", "khoondad", "lostshad", "redemption", "relicpast", "ssensor",),
                 "global_prefix": ("601", "602", "603", "604", "605", "610",)},
    ("K2", "Korriban"): {"module_prefix": ("701kor", "702kor", "710kor", "711kor",),
                 "tags": ("hidden_power", "jedi_tomb", "traces", "trapped",),
                 "global_prefix": ("701", "702", "710", "711",)},
    ("K2", "The Jedi Masters"): {"module_prefix": ("650dan", "006ebo", "220tel", "221tel", "222tel",),
                 "tags": ("fuel_sith", "lostjedi",),
                 "global_prefix": ("006", "220", "221", "222", "650",)},
    ("K2", "Ravager"): {"module_prefix": ("851nih", "852nih", "853nih",),
                 "tags": ("defeatdarthnihilus", "destroyravager",),
                 "global_prefix": ("851", "852", "853",)},
    ("K2", "Malachor V"): {"module_prefix": ("901mal", "902mal", "903mal", "904mal", "905mal", "906mal", "907mal",),
                 "tags": ("massshadowgenerator",),
                 "global_prefix": ("901", "902", "903", "904", "905", "906", "907",)},
    ("K2", "Ebon Hawk"): {"module_prefix": ("003ebo",),
                 "tags": ("lightsaberquest", "rebuildhk47",),
                 "global_prefix": ("003",),
                 # the companions' own conversations (chitin): most influence is won or lost there
                 "extra_dialogs": r"^(atton|attondem|baodur|disciple|g0t0|handmaiden|hanharr|hk47|kreia|mandalore|mira|t3m4|visasmarr)$"},
}


def planet_key(game, planet):
    """The PLANETS key for --game/--planet, ignoring case and spaces/underscores/hyphens."""
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    for k in PLANETS:
        if k[0].lower() == game.lower() and norm(k[1]) == norm(planet):
            return k
    return None
render = ncsvm.render

# More effect groups than this for one stage from one script are merged into one step
# (added 2026-10-23 for Manaan's man_questend; no Taris or Endar Spire script comes near it).
MAX_SCRIPT_GROUPS = 16

PC_SOURCES = {"GetFirstPC", "GetPCSpeaker", "GetPartyLeader", "GetEnteringObject", "GetLastUsedBy",
              "GetLastOpenedBy", "GetPartyMemberByIndex"}


def is_pc(v):
    if not (isinstance(v, tuple) and v[0] == "call" and v[1] in PC_SOURCES):
        return False
    if v[1] == "GetPartyMemberByIndex":
        return v[2] == (0,)
    return True


def tag_of(v):
    """Object tag for GetObjectByTag("x") / GetNearestObjectByTag("x"), else None."""
    if isinstance(v, tuple) and v[0] == "call" and v[1] in ("GetObjectByTag", "GetNearestObjectByTag") \
            and v[2] and isinstance(v[2][0], str):
        return v[2][0]
    return None


def item_of(v):
    """(holder, item tag) for GetItemPossessedBy(holder, "tag"), else None."""
    if isinstance(v, tuple) and v[0] == "call" and v[1] == "GetItemPossessedBy" and len(v[2]) == 2 \
            and isinstance(v[2][1], str):
        return v[2][0], v[2][1]
    return None


def created_item(v):
    """(template, target, count) for CreateItemOnObject(...), else None."""
    if isinstance(v, tuple) and v[0] == "call" and v[1] == "CreateItemOnObject" and v[2] \
            and isinstance(v[2][0], str):
        a = v[2]
        return a[0], (a[1] if len(a) > 1 else ("obj", "OBJECT_SELF")), (a[2] if len(a) > 2 else 1)
    return None


class Builder:
    def __init__(self, root, game, planet):
        self.g = gamefiles.Game(root)
        game, planet = planet_key(game, planet) or (game, planet)
        cfg = PLANETS[(game, planet)]
        self.game, self.planet = game, planet
        self.mprefix, self.tprefix = cfg["module_prefix"], cfg.get("tag_prefix", ())
        self.tags = set(cfg.get("tags", ()))
        # the story values of the planet (milestone.py's "never set" list): by name prefix
        self.gprefix = tuple(p.upper() for p in cfg.get("global_prefix", self.tprefix))
        self.extra_dialogs = cfg.get("extra_dialogs")
        self.extra_scripts = cfg.get("extra_scripts")
        nss, _ = self.g.get("nwscript", kfmt.T_NSS)
        text = nss.decode("latin-1")
        self.R = nwsig.parse(text)
        self.K = nwsig.constants(text)
        self.modules = [m for m in self.g.module_names() if m.startswith(self.mprefix)]
        self.paths_cache = {}
        self.script_cache = {}
        self.cond_cache = {}
        self.notes = collections.defaultdict(list)
        self.uncertain = collections.defaultdict(list)
        self.names = {"creature": {}, "item_tag": {}, "item_res": {}}
        self._plot = None
        self._globals = None

    def owns_tag(self, tag):
        """Whether the journal quest is one of the planet's own (KotOR 2: the exact list)."""
        return tag in self.tags or bool(self.tprefix) and tag.startswith(self.tprefix)

    # ------------------------------------------------------------ tables
    def plot_rows(self):
        if self._plot is None:
            d, _ = self.g.get("plot", kfmt.T_2DA)
            _c, rows = kfmt.twoda(d)
            self._plot = rows
        return self._plot

    def plot_xp_index(self, idx, pct):
        rows = self.plot_rows()
        if idx is None or idx < 0 or idx >= len(rows) or not (pct and pct > 0):
            return None
        base = int(rows[idx][1].get("xp") or 0)
        p = int(math.ceil(float(pct) * 100.0))
        xp = int(math.ceil(base * p * 0.01))
        return xp if xp > 0 else None

    def plot_xp_name(self, name, pct):
        for label, cells in self.plot_rows():
            if label.lower() == name.lower() or (cells.get("label") or "").lower() == name.lower():
                xp = int(math.ceil(int(cells.get("xp") or 0) * pct * 0.01))
                return xp if xp > 0 else None
        return None

    def globals_known(self):
        if self._globals is None:
            d, _ = self.g.get("globalcat", kfmt.T_2DA)
            _c, rows = kfmt.twoda(d)
            self._globals = {c["name"].lower(): (c["name"], c["type"]) for _l, c in rows}
        return self._globals

    # ------------------------------------------------------------ scripts
    def script(self, name, module):
        """(paths, truncated, source) for a script as the game resolves it in module. name may be
        a nodescript key: a KotOR 2 script with its conversation parameters."""
        name, params, _neg = nodescript.split(name)
        data, src = self.g.get(name, kfmt.T_NCS, module)
        if data is None:
            return None, False, None
        key = (hash(data), params)
        if key not in self.paths_cache:
            self.paths_cache[key] = ncsvm.run_script(data, self.R, params)
        paths, tr = self.paths_cache[key]
        return paths, tr, src

    # ------------------------------------------------------------ effects
    def effects(self, calls, owner, module, depth=0):
        """Turn a path's engine calls into the schema's "does" list."""
        does = []
        given = set()
        for name, args, _deferred in calls:
            if name == "ActionGiveItem" or name == "GiveItem":
                ci = created_item(args[0]) if args else None
                if ci and len(args) > 1 and is_pc(args[1]):
                    given.add(render(args[0]))
        for name, args, _deferred in calls:
            a = args
            if name == "AddJournalQuestEntry" and len(a) >= 2 and isinstance(a[0], str) and isinstance(a[1], int):
                does.append({"journal": [a[0], a[1]]})
                if len(a) > 2 and a[2] != 0:
                    does.append({"other": "that journal call may also lower the stage (bAllowOverrideHigher = %s)" % render(a[2])})
            elif name == "RemoveJournalQuestEntry":
                does.append({"other": "removes the journal quest %s" % render(a[0])})
            elif name == "SetGlobalBoolean" and len(a) == 2 and isinstance(a[0], str):
                if isinstance(a[1], int):
                    does.append({"set_global_bool": [a[0], bool(a[1])]})
                else:
                    does.append({"other": "sets global boolean %s to a value that is not constant: %s" % (a[0], render(a[1]))})
            elif name == "SetGlobalNumber" and len(a) == 2 and isinstance(a[0], str):
                if isinstance(a[1], int):
                    does.append({"set_global_number": [a[0], a[1]]})
                else:
                    does.append({"other": "sets global number %s to a value that is not constant: %s" % (a[0], render(a[1]))})
            elif name == "GiveXPToCreature" and len(a) == 2:
                if isinstance(a[1], int) and is_pc(a[0]):
                    does.append({"xp": a[1]})
                else:
                    does.append({"other": "gives XP to %s: %s" % (render(a[0]), render(a[1]))})
            elif name == "GivePlotXP" and len(a) == 2:
                if isinstance(a[0], str) and isinstance(a[1], int):
                    xp = self.plot_xp_name(a[0], a[1])
                    if xp:
                        does.append({"xp": xp})
                    else:
                        does.append({"other": "GivePlotXP(%s, %s): no XP found in plot.2da" % (a[0], a[1])})
                else:
                    does.append({"other": "gives plot XP: GivePlotXP(%s)" % ", ".join(render(x) for x in a)})
            elif name == "CreateItemOnObject" and a and isinstance(a[0], str):
                res, tgt, cnt = created_item(("call", name, a))
                if is_pc(tgt) and isinstance(cnt, int):
                    does.append({"give_item": [res, cnt]})
                elif render(("call", name, a)) in given:
                    does.append({"give_item": [res, cnt if isinstance(cnt, int) else 1]})
                else:
                    does.append({"other": "creates item %s on %s" % (res, self.who(tgt, owner))})
            elif name in ("ActionGiveItem", "GiveItem") and len(a) == 2:
                ci = created_item(a[0])
                it = item_of(a[0])
                if ci and is_pc(a[1]):
                    continue  # counted at CreateItemOnObject
                if it and is_pc(it[0]):
                    does.append({"take_item": [it[1], 1]})
                elif it:
                    does.append({"other": "%s gives item %s to %s" % (self.who(it[0], owner), it[1], self.who(a[1], owner))})
            elif name == "ActionTakeItem" and len(a) == 2:
                it = item_of(a[0])
                if it and is_pc(it[0]):
                    does.append({"take_item": [it[1], 1]})
                elif tag_of(a[0]) and is_pc(a[1]):
                    # ActionTakeItem(GetObjectByTag("x"), player): the item is found by tag
                    does.append({"take_item": [tag_of(a[0]), 1]})
                else:
                    does.append({"other": "takes an item: %s" % render(a[0])})
            elif name == "DestroyObject" and a:
                it = item_of(a[0])
                t = tag_of(a[0])
                if it and is_pc(it[0]):
                    does.append({"take_item": [it[1], 1]})
                elif it:
                    does.append({"other": "destroys item %s held by %s" % (it[1], self.who(it[0], owner))})
                elif t:
                    does.append({"destroy": t})
                elif a[0] == ("obj", "OBJECT_SELF"):
                    if owner:
                        does.append({"destroy": owner})
                    else:
                        does.append({"other": "removes the object running the script (owner unknown)"})
                else:
                    does.append({"other": "destroys %s" % render(a[0])})
            elif name == "SetLocked" and len(a) == 2:
                t = tag_of(a[0])
                if t and a[1] == 0:
                    does.append({"door_unlock": t})
                elif t and a[1] == 1:
                    does.append({"other": "locks %s" % t})
                else:
                    does.append({"other": "SetLocked(%s, %s)" % (render(a[0]), render(a[1]))})
            elif name in ("ActionOpenDoor",) and a:
                t = tag_of(a[0])
                does.append({"door_open": t} if t else {"other": "opens a door: %s" % self.who(a[0], owner)})
            elif name == "AdjustAlignment" and len(a) >= 3:  # KotOR 2 adds a fourth (bDontModifyNPCs)
                side = {self.K.get("ALIGNMENT_LIGHT_SIDE", 2): "light_side",
                        self.K.get("ALIGNMENT_DARK_SIDE", 3): "dark_side"}.get(a[1])
                if side and isinstance(a[2], int) and is_pc(a[0]):
                    does.append({side: a[2]})
                else:
                    does.append({"other": "AdjustAlignment(%s)" % ", ".join(render(x) for x in a)})
            elif name == "GiveGoldToCreature" and len(a) == 2:
                if is_pc(a[0]) and isinstance(a[1], int):
                    does.append({"credits": a[1]})
                else:
                    does.append({"other": "gives credits to %s: %s" % (self.who(a[0], owner), render(a[1]))})
            elif name == "TakeGoldFromCreature" and len(a) >= 2:
                if is_pc(a[1]) and isinstance(a[0], int):
                    does.append({"credits": -a[0]})
                else:
                    does.append({"other": "takes credits from %s: %s" % (self.who(a[1], owner), render(a[0]))})
            elif name == "ExecuteScript" and a and isinstance(a[0], str):
                sub = self.inline_script(a[0], module, owner, depth)
                if sub is None:
                    does.append({"other": "runs script %s (its effects branch or could not be read)" % a[0]})
                else:
                    does.extend(sub)
            elif name == "StartNewModule" and a:
                does.append({"other": "moves the party to module %s" % render(a[0])})
            elif name == "ActionStartConversation" and len(a) > 1:
                does.append({"other": "starts conversation %s" % render(a[1])})
            elif name in ("AddPartyMember", "AddAvailableNPCByTemplate", "AddAvailableNPCByObject"):
                does.append({"other": "%s(%s)" % (name, ", ".join(render(x) for x in a))})
            elif name in ("RemoveAvailableNPC", "RemovePartyMember", "SetPartyLeader", "ShowPartySelectionGUI",
                          "PlayMovie", "QueueMovie", "OpenStore", "StartPazaakGame", "SetPlanetAvailable",
                          "SetPlanetSelectable", "SetNPCSelectability", "EndGame", "AwardStealthXP"):
                does.append({"other": "%s(%s)" % (name, ", ".join(render(x) for x in a))})
            elif name == "ChangeToStandardFaction" and len(a) == 2:
                who = self.who(a[0], owner)
                fac = {v: k for k, v in self.K.items() if k.startswith("STANDARD_FACTION_")}.get(a[1], render(a[1]))
                does.append({"other": "changes the faction of %s to %s" % (who, fac)})
            elif name == "CreateObject" and len(a) >= 2 and isinstance(a[1], str):
                does.append({"other": "spawns %s" % a[1]})
            elif name in ("SetLocalBoolean", "SetLocalNumber") and len(a) == 3:
                # A local flag the game keeps on an object, its area or the module; the quest's
                # own NPCs read theirs to know a talk is done. Structured when the target and the
                # values are known (added 2026-10-23), so Skip Ahead can write it.
                r0 = render(a[0])
                target = ("area" if r0.startswith("GetArea(") else "module" if r0.startswith("GetModule(")
                          else (owner if a[0] == ("obj", "OBJECT_SELF") else tag_of(a[0])))
                if target and isinstance(a[1], int) and isinstance(a[2], int):
                    does.append({"local": [target, "number" if name == "SetLocalNumber" else "bool", a[1], a[2]]})
                else:
                    does.append({"other": "%s on %s: index %s = %s" % (name, self.who(a[0], owner), render(a[1]),
                                                                       render(a[2]))})
            elif name == "SetGlobalString" and len(a) == 2:
                does.append({"other": "sets global string %s to %s" % (render(a[0]), render(a[1]))})
        for x in does:
            if "other" in x:
                x["other"] = plain_other(x["other"])
        return does

    def who(self, v, owner):
        if v == ("obj", "OBJECT_SELF"):
            return owner or "the object running the script"
        if is_pc(v):
            return "the player"
        t = tag_of(v)
        if t:
            return t
        return render(v)

    def inline_script(self, name, module, owner, depth):
        if depth > 2:
            return None
        paths, _tr, _src = self.script(name, module)
        if not paths:
            return None
        groups = {}
        for p in paths:
            d = self.effects(p.calls, owner, module, depth + 1)
            groups[json.dumps(d)] = d
        if len(groups) != 1:
            return None
        return list(groups.values())[0]

    # ------------------------------------------------------------ conditions
    def atoms(self, v, b, out, other):
        """Split a condition known to be b into needs (out) and plain-text leftovers (other)."""
        if isinstance(v, (int, float)):
            return
        if isinstance(v, tuple) and v[0] == "not":
            return self.atoms(v[1], not b, out, other)
        if isinstance(v, tuple) and v[0] == "op":
            sym, x, y = v[1], v[2], v[3]
            if sym in ("&&", "&") and b:
                self.atoms(x, True, out, other)
                self.atoms(y, True, out, other)
                return
            if sym in ("||", "|") and not b:
                self.atoms(x, False, out, other)
                self.atoms(y, False, out, other)
                return
            if sym in ("==", "!=", ">=", ">", "<", "<="):
                if isinstance(x, int) and not isinstance(y, int):
                    x, y = y, x
                    sym = {">=": "<=", "<=": ">=", ">": "<", "<": ">"}.get(sym, sym)
                if not b:
                    sym = {"==": "!=", "!=": "==", ">=": "<", "<": ">=", ">": "<=", "<=": ">"}[sym]
                if isinstance(x, tuple) and x[0] == "call" and isinstance(y, int):
                    fn, fa = x[1], x[2]
                    if fn == "GetGlobalBoolean" and fa and isinstance(fa[0], str):
                        ok = [val for val in (0, 1) if _cmp(val, sym, y)]
                        if len(ok) == 1:
                            out.append({"global_bool": fa[0], "is": bool(ok[0])})
                        elif not ok:
                            other.append("impossible test on %s" % fa[0])
                        return
                    if fn == "GetGlobalNumber" and fa and isinstance(fa[0], str):
                        out.append({"global_number": fa[0], "op": sym, "value": y})
                        return
                    if fn == "GetJournalEntry" and fa and isinstance(fa[0], str):
                        out.append({"stage": [fa[0], y], "op": sym})
                        return
                if sym in ("==", "!=") and (y == ncsvm.INVALID or x == ncsvm.INVALID):
                    obj = x if y == ncsvm.INVALID else y
                    return self.atoms(("call", "GetIsObjectValid", (obj,)), sym == "!=", out, other)
            other.append(("" if b else "not ") + render(v))
            return
        if isinstance(v, tuple) and v[0] == "call":
            fn, fa = v[1], v[2]
            if fn == "GetGlobalBoolean" and fa and isinstance(fa[0], str):
                out.append({"global_bool": fa[0], "is": b})
                return
            if fn == "GetGlobalNumber" and fa and isinstance(fa[0], str):
                out.append({"global_number": fa[0], "op": "!=" if b else "==", "value": 0})
                return
            if fn == "GetJournalEntry" and fa and isinstance(fa[0], str):
                out.append({"stage": [fa[0], 1], "op": ">="} if b else {"stage": [fa[0], 0], "op": "=="})
                return
            if fn == "GetIsObjectValid" and fa:
                it = item_of(fa[0])
                if it and is_pc(it[0]):
                    out.append({"item": it[1]} if b else {"item": it[1], "is": False})
                    return
        other.append(("" if b else "not ") + render(v))

    def path_needs(self, conds):
        out, other = [], []
        for v, b in simplify(conds):
            self.atoms(v, b, out, other)
        return dedupe(out), dedupe(other)

    def conditional(self, name, module):
        """Needs for a StartingConditional script to return TRUE: (needs, leftovers, note).
        name may be a nodescript key: "!" asks for FALSE (KotOR 2's Not), "a;b" for both."""
        key = (name, module)
        if key in self.cond_cache:
            return self.cond_cache[key]
        if ";" in name:
            parts = [self.conditional(n, module) for n in name.split(";") if n]
            res = (dedupe([x for p in parts for x in p[0]]), dedupe([x for p in parts for x in p[1]]),
                   "; ".join(p[2] for p in parts if p[2]) or None)
            self.cond_cache[key] = res
            return res
        want = not nodescript.split(name)[2]
        paths, tr, src = self.script(name, module)
        if paths is None:
            res = ([], ["conditional script %s not found" % name], "conditional %s not found" % name)
            self.cond_cache[key] = res
            return res
        sets = []
        for p in paths:
            if p.ret is None:
                continue
            t = ncsvm.truth(p.ret, p.assume)
            if t is (not want):
                continue
            alts = [[]] if t is want else ncsvm.dnf(p.ret, want)
            for alt in alts:
                conds = list(p.conds) + alt
                if not ncsvm.consistent(conds):
                    continue
                n, left = self.path_needs(conds)
                sets.append((n, left))
        uniq = []
        for s in sets:
            if s not in uniq:
                uniq.append(s)
        sets = uniq
        note = None
        if not sets:
            res = ([], ["conditional %s never returns TRUE in the analysis" % name],
                   "conditional %s never returns TRUE in the analysis" % name)
        elif len(sets) == 1:
            res = (sets[0][0], sets[0][1], None)
        else:
            common = [n for n in sets[0][0] if all(n in s[0] for s in sets[1:])]
            commonleft = [n for n in sets[0][1] if all(n in s[1] for s in sets[1:])]
            alts = []
            for s in sets:
                rest = [plain_need(n) for n in s[0] if n not in common]
                rest += [x for x in s[1] if x not in commonleft]
                txt = ", ".join(rest) or "nothing more"
                alts.append(txt if len(txt) <= 90 else txt[:87] + "...")
            alts = dedupe(alts)
            note = ("conditional %s passes in %d different cases; only the tests shared by all are listed "
                    "as needs. Cases: %s%s" % (name, len(alts), " | ".join(alts[:3]),
                                               " | ..." if len(alts) > 3 else ""))
            res = (common, commonleft, note)
        if tr:
            note = (note + "; " if note else "") + "analysis of %s was cut short" % name
            res = (res[0], res[1], note)
        self.cond_cache[key] = res
        return res

    # ------------------------------------------------------------ script steps
    def script_variants(self, name, module, owner, want=None):
        """Distinct effect groups of a script: [(branch label or None, needs, does, leftovers)].

        want = (tag, stage): keep only paths that set that journal stage.
        """
        paths, tr, src = self.script(name, module)
        if paths is None:
            return None, False
        sel = []
        for p in paths:
            if want:
                hit = any(c[0] == "AddJournalQuestEntry" and len(c[1]) >= 2 and isinstance(c[1][0], str)
                          and c[1][0].lower() == want[0] and c[1][1] == want[1] for c in p.calls)
                if not hit:
                    continue
            sel.append(p)
        # Group paths by their game-state effects; "other" effects (plain-text notes) do not
        # split a group, they are collected from all of its paths.
        groups = collections.OrderedDict()
        for p in sel:
            d = self.effects(p.calls, owner, module)
            k = json.dumps([x for x in d if "other" not in x])
            gr = groups.setdefault(k, {"does": list(d), "paths": []})
            gr["paths"].append(p)
            for x in d:
                if "other" in x and x not in gr["does"]:
                    gr["does"].append(x)
        glist = list(groups.values())
        if want and len(glist) > MAX_SCRIPT_GROUPS:
            # A script made of many independent tests (Manaan's man_questend closes nine quests,
            # each behind its own journal test: 512 paths) would give one step per combination.
            # Keep what every path that sets the stage does, and name the rest in one line.
            return [self.collapse_groups(sel, module, owner)], tr
        return self.group_steps(glist), tr

    def collapse_groups(self, sel, module, owner):
        """One (label, needs, does, leftovers) for paths that differ only in side effects."""
        per = [self.effects(p.calls, owner, module) for p in sel]
        keys = [set(json.dumps(x, sort_keys=True) for x in d) for d in per]
        common = set.intersection(*keys) if keys else set()
        does = [x for x in per[0] if json.dumps(x, sort_keys=True) in common]
        rest = []
        for d in per:
            for x in d:
                if json.dumps(x, sort_keys=True) not in common and x not in rest:
                    rest.append(x)
        sets = [set((render(v), b) for v, b in p.conds) for p in sel]
        cshared = set.intersection(*sets) if sets else set()
        conds = [(v, b) for v, b in sel[0].conds if (render(v), b) in cshared]
        needs, left = self.path_needs(conds)
        if rest:
            from assemble import plain_does
            txt = "; ".join(plain_does(self, x, module) for x in rest[:8])
            does = does + [{"other": "depending on other tests in the script (%d combinations), it may also: %s%s"
                                     % (len(sel), txt, "; ..." if len(rest) > 8 else "")}]
        return (None, needs, does, left)

    def group_steps(self, glist):
        out = []
        # conditions shared by all paths of a group, in path order
        gconds = []
        for gr in glist:
            sets = [set((render(v), b) for v, b in p.conds) for p in gr["paths"]]
            common = set.intersection(*sets) if sets else set()
            gconds.append([(v, b) for v, b in gr["paths"][0].conds if (render(v), b) in common])
        allc = set.intersection(*[set((render(v), b) for v, b in c) for c in gconds]) if gconds else set()
        for i, gr in enumerate(glist):
            needs, left = self.path_needs(gconds[i])
            label = None
            if len(glist) > 1:
                dist = [(v, b) for v, b in gconds[i] if (render(v), b) not in allc]
                label = branch_label(dist, self) or ("otherwise" if sum(1 for j in range(len(glist)) if j != i) else "always")
            out.append((label, needs, gr["does"], left))
        return out

    # ------------------------------------------------------------ dialogs
    def dialog_owner(self, dlg, module):
        """Tags of the creatures/placeables/doors whose Conversation is this dialog in module."""
        res = []
        m = self.g.module(module)
        for (n, t), _d in m.items():
            if t in (kfmt.T_UTC, kfmt.T_UTP, kfmt.T_UTD):
                r = self.g.gff(n, t, module)
                if r is not None and (r.get("Conversation") or "").lower() == dlg:
                    res.append((r.get("Tag") or n, n, t))
        return res

    def creature_name(self, tag, module=None):
        if not tag:
            return ""
        key = tag.lower()
        if key in self.names["creature"]:
            return self.names["creature"][key]
        found = ""
        mods = [module] if module else []
        mods += [m for m in self.modules if m != module]
        for mod in mods:
            for (n, t), _d in self.g.module(mod).items():
                if t in (kfmt.T_UTC, kfmt.T_UTP, kfmt.T_UTD):
                    r = self.g.gff(n, t, mod)
                    if r is None:
                        continue
                    rt = (r.get("Tag") or "").lower()
                    nm = self.names["creature"]
                    if rt and rt not in nm:
                        if t == kfmt.T_UTC:
                            nm[rt] = (self.g.text(r.get("FirstName")) + " " + self.g.text(r.get("LastName"))).strip()
                        else:
                            nm[rt] = self.g.text(r.get("LocName") or r.get("LocalizedName"))
            if key in self.names["creature"]:
                found = self.names["creature"][key]
                break
        if not found and not self.names.get("chitin_done"):
            self.names["chitin_done"] = True
            nm = self.names["creature"]
            for n in self.g.chitin_names(kfmt.T_UTC):
                r = self.g.gff(n, kfmt.T_UTC)
                rt = (r.get("Tag") or "").lower() if r is not None else ""
                if rt and rt not in nm:
                    nm[rt] = (self.g.text(r.get("FirstName")) + " " + self.g.text(r.get("LastName"))).strip()
            found = nm.get(key, "")
        self.names["creature"][key] = found
        return found

    def item_name(self, ref):
        """Name of an item by template resref or by tag (both are tried)."""
        key = ref.lower()
        if key in self.names["item_res"]:
            return self.names["item_res"][key]
        r = self.g.gff(key, kfmt.T_UTI)
        if r is None:
            for m in self.modules:
                r = self.g.gff(key, kfmt.T_UTI, m)
                if r is not None:
                    break
        if r is not None:
            nm = self.g.text(r.get("LocalizedName"))
            self.names["item_res"][key] = nm
            return nm
        if not self.names["item_tag"]:
            for n in self.g.chitin_names(kfmt.T_UTI):
                rr = self.g.gff(n, kfmt.T_UTI)
                if rr is not None:
                    self.names["item_tag"].setdefault((rr.get("Tag") or "").lower(), self.g.text(rr.get("LocalizedName")))
            for m in self.modules:
                for (n, t), _d in self.g.module(m).items():
                    if t == kfmt.T_UTI:
                        rr = self.g.gff(n, t, m)
                        if rr is not None:
                            self.names["item_tag"].setdefault((rr.get("Tag") or "").lower(), self.g.text(rr.get("LocalizedName")))
        nm = self.names["item_tag"].get(key, "")
        self.names["item_res"][key] = nm
        return nm


def _cmp(a, sym, b):
    return {"==": a == b, "!=": a != b, ">=": a >= b, ">": a > b, "<": a < b, "<=": a <= b}[sym]


def dedupe(xs):
    out, seen = [], set()
    for x in xs:
        k = json.dumps(x, sort_keys=True)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def plain_need(n):
    if "global_bool" in n:
        return "%s is %s" % (n["global_bool"], "TRUE" if n["is"] else "FALSE")
    if "global_number" in n:
        return "%s %s %d" % (n["global_number"], n["op"], n["value"])
    if "item" in n:
        return ("has item %s" if n.get("is", True) else "does not have item %s") % n["item"]
    if "stage" in n:
        return "journal %s %s %d" % (n["stage"][0], n.get("op", ">="), n["stage"][1])
    return json.dumps(n)


def plain_other(o):
    for a, b in (("GetUserDefinedEventNumber()", "user-defined event"),
                 ("sub-result", "a helper function's result"),
                 ("GetGoodEvilValue(GetPCSpeaker())", "player alignment"),
                 ("GetGoodEvilValue(GetFirstPC())", "player alignment"),
                 ("GetPCSpeaker()", "player"), ("GetFirstPC()", "player")):
        o = o.replace(a, b)
    return o


def simplify(conds):
    """Drop "x == k is false" when the same list says "x == j is true"; it adds nothing."""
    eq_true = {render(ncsvm.eqinfo(v)[0]) for v, b in conds
               if b and ncsvm.eqinfo(v) and ncsvm.eqinfo(v)[1] == "=="}
    eq_false = {render(ncsvm.eqinfo(v)[0]) for v, b in conds
                if not b and ncsvm.eqinfo(v) and ncsvm.eqinfo(v)[1] == "!="}
    eq_true |= eq_false
    out = []
    for v, b in conds:
        ei = ncsvm.eqinfo(v)
        if ei and render(ei[0]) in eq_true and ((ei[1] == "==" and not b) or (ei[1] == "!=" and b)):
            continue
        out.append((v, b))
    return out


def branch_label(conds, builder):
    """Plain words for the conditions that pick this branch; game-state tests are preferred."""
    out, other = [], []
    for v, b in simplify(conds):
        builder.atoms(v, b, out, other)
    # numeric tests on one value (such as the player's alignment) read better as a range
    assume = {}
    for v, b in conds:
        ncsvm.assume_set(assume, v, b)
    ranges = []
    for key in sorted(k for k in assume if k.startswith(("lo:", "hi:"))):
        rx = key[3:]
        if rx.startswith(("GetGlobal", "GetJournalEntry")) or any(r[0] == rx for r in ranges):
            continue
        lo, hi = assume.get("lo:" + rx), assume.get("hi:" + rx)
        if lo is not None and hi is not None:
            txt = "%s from %d to %d" % (rx, lo, hi) if lo != hi else "%s is %d" % (rx, lo)
        elif lo is not None:
            txt = "%s at least %d" % (rx, lo)
        else:
            txt = "%s at most %d" % (rx, hi)
        ranges.append((rx, txt))
    if ranges:
        other = [o for o in other if not any(rx in o for rx, _t in ranges)] + [t for _rx, t in ranges]
    if out:
        s = "; ".join(plain_need(n) for n in dedupe(out))
    else:
        s = "; ".join(plain_other(o) for o in dedupe(other))
    if not s:
        return None
    s = "if " + s
    return s if len(s) <= 110 else s[:107] + "..."


def main():
    ap = argparse.ArgumentParser(description="Build the Save Editor quest database for one planet.")
    ap.add_argument("--game", default="K1")
    ap.add_argument("--planet", default="Taris")
    ap.add_argument("--out", required=True)
    ap.add_argument("--game-dir", default=None, help="default: the Steam folder of --game")
    ap.add_argument("--review", default=None, help="review page path (default: <out stem>-review.md)")
    ap.add_argument("--review-text", action="store_true",
                    help="also write the review page with the game's own names and journal text to "
                         "data/quests/local/ (kept out of the repository)")
    ap.add_argument("--milestone", default=None,
                    help="also write the end-of-planet milestone file (chapters set up in chapters.py)")
    a = ap.parse_args()
    key = planet_key(a.game, a.planet)
    if key is None:
        ap.error("only these are set up: %s" % ", ".join("%s %s" % k for k in PLANETS))
    a.game, a.planet = key
    a.game_dir = a.game_dir or STEAM[a.game]
    sys.setrecursionlimit(20000)
    import assemble
    b = Builder(a.game_dir, a.game, a.planet)
    assemble.write(b, a)
    if a.milestone:
        import milestone
        milestone.write(b, a.milestone)


if __name__ == "__main__":
    main()
