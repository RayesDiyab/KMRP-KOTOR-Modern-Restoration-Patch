"""KotOR 1 XP calculator: kill XP along a story path, with the engine's exact arithmetic.

Usage:
    python -I calc.py <module> [<module> ...] [--xp N | --level N] [--maybe] [--order file|high|low]
                      [--encounters sim|rec|max|none] [--party N] [--runs N] [--data PATH] [--verbose]
    python -I calc.py --scenario PATH [--xp N] [--verbose]

The first form adds kill XP enemy by enemy, module by module, from data/xp/k1-enemies.json
(placed creatures, scripted spawns and encounters marked hostile), with the PC's level
re-read from its XP before every kill, and prints the XP at each module's end.

The second form plays an ordered scenario file (see data/xp/k1-endar-spire-path.json):
kills, plot XP, GiveXPToCreature amounts and SetXP floors in the order a player meets them.

Engine rules implemented (swkotor.exe 1.0.3; addresses are the original's):
  * Kill XP, CSWSCreature::ApplyDeathExperience 0x004FB1E0 and
    CalculateDeathExperience 0x004F19E0: the victim must not be the player-controlled
    creature or a party member, and repute.2da row Player must be <= 10 for its faction.
    level = 1 + the highest exptable.2da row whose XP the PC's XP reaches (not the PC's
    class level: unspent level-ups count). base = xptable.2da[level - 1][1 + trunc(CR)]
    (column 0 is the "level" column, so CR 0 reads c0); a column past c20 fails and gives 0.
    xp = base * npc.2da[GAME_XP_General].PercentXP * 0.01 (stored as a float); when
    npc.2da[PER_NPC_Bonus] > 0, xp *= PER_NPC_Bonus * 0.01 * party size + 1. award = ceil(xp).
  * CSWPartyTable::DistributeExperience 0x005653A0 gives the award to each active party
    member and to the PC; CSWSCreature::ReceiveExperience 0x004EF930 scales it by
    GAME_XP_General (and by the NPC's own PercentXP for party NPCs) and rounds up.
    Difficulty is not used anywhere in this chain.
  * SetXP (0x005437B0 -> CSWSCreatureStats::SetExperience 0x005AF480) never lowers XP.
  * Plot XP (GivePlotXP, dialog lines, journal entries) goes through the same
    DistributeExperience; scenario files carry the amount already computed (the quest
    database does that), and this tool only applies ReceiveExperience to it.

Encounters (CSWSEncounter 0x00590B10, 0x00590F80, 0x00592280, 0x005931D0, 0x005935D0) spawn
between RecCreatures and MaxCreatures creatures, chosen from party levels with random picks.
--encounters sim (the default) replays that spawn-list code for a party of --party members
(the PC at full level, the others counted at half level as TallyEnemyRadiusPoints does)
with the PC's current level, --runs times with a fixed seed, and adds the mean XP. The
original compares the budget against 16 heap bytes before the creature array when it
starts a same-CR group (0x00591186); that value is unknowable, and the comparison is
assumed to pass. rec / max count RecCreatures / MaxCreatures kills, split evenly over the
encounter's templates.

Origin: written 2026-10-23 for the Save Editor's "skip to a point in the story" XP research.
"""
import json
import math
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "data", "xp", "k1-enemies.json"))

# ---------------------------------------------------------------- 2DA values (KotOR 1 1.0.3, chitin 2da.bif)
EXPTABLE = [0, 1000, 3000, 6000, 10000, 15000, 21000, 28000, 36000, 45000, 55000, 66000, 78000, 91000,
            105000, 120000, 136000, 153000, 171000, 190000, 0xFFFFFFFF]
XPTABLE = [  # rows: PC level 1..20; columns c0..c20
    [50, 75, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000],
    [25, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250, 1350, 1450, 1550, 1650, 1750, 1850, 1950],
    [20, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
    [20, 25, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250, 1350, 1450, 1550, 1650, 1750, 1850],
    [20, 25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800],
    [20, 25, 30, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250, 1350, 1450, 1550, 1650, 1750],
    [20, 25, 30, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700],
    [20, 25, 30, 35, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250, 1350, 1450, 1550, 1650],
    [20, 25, 30, 35, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600],
    [20, 25, 30, 35, 40, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250, 1350, 1450, 1550],
    [20, 25, 30, 35, 40, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500],
    [20, 25, 30, 35, 40, 45, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250, 1350, 1450],
    [20, 25, 30, 35, 40, 45, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400],
    [20, 25, 30, 35, 40, 45, 50, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250, 1350],
    [20, 25, 30, 35, 40, 45, 50, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300],
    [20, 25, 30, 35, 40, 45, 50, 50, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250],
    [20, 25, 30, 35, 40, 45, 50, 50, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
    [20, 25, 30, 35, 40, 45, 50, 50, 50, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150],
    [20, 25, 30, 35, 40, 45, 50, 50, 50, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100],
    [20, 25, 30, 35, 40, 45, 50, 50, 50, 50, 75, 150, 250, 350, 450, 550, 650, 750, 850, 950, 1050],
]
GAME_XP_GENERAL = 100     # npc.2da row 9 PercentXP
PER_NPC_BONUS = 0         # npc.2da row 10 PercentXP
ENC_DIFFICULTY = [0, 1, 2, 5, 9]                    # encdifficulty.2da VALUE
FRACTIONAL_MIN = [0.40, 0.30, 0.20, 0.15, -99999.0]  # fractionalcr.2da MIN
F_TENTH = 0.10000000149011612                       # 0.1f at 0x0073E798
F_EPSILON = 0.0010000000474974513                   # 0.001f at 0x0073D708


def f32(v):
    """Round a double to IEEE single precision, as an fstp dword does."""
    return struct.unpack("<f", struct.pack("<f", v))[0]


F_PERCENT = f32(0.01)    # the float 0.01f at 0x0073DFEC


def ftol(v):
    """__ftol: truncation toward zero."""
    return int(v)


K1_TABLES = None


def use_game(game):
    """Switch the tables to KotOR 1 (the constants above) or KotOR 2 (read from its own 2da.bif:
    exptable for 50 levels, xptable with columns 0..50, npc.2da's GAME_XP_General and
    PER_NPC_Bonus). Added 2026-10-23. KotOR 2's kill XP is assumed to follow KotOR 1's
    arithmetic above; swkotor2.exe was not checked."""
    global EXPTABLE, XPTABLE, GAME_XP_GENERAL, PER_NPC_BONUS, K1_TABLES, GAME, CRMOD
    if K1_TABLES is None:
        K1_TABLES = (EXPTABLE, XPTABLE, GAME_XP_GENERAL, PER_NPC_BONUS)
    GAME = game
    if game != "K2":
        EXPTABLE, XPTABLE, GAME_XP_GENERAL, PER_NPC_BONUS = K1_TABLES
        return
    sys.path.insert(0, os.path.join(HERE, "..", "questdb"))
    import build
    import gamefiles
    import kfmt
    g = gamefiles.Game(build.STEAM_K2)
    _c, rows = kfmt.twoda(g.get("exptable", kfmt.T_2DA)[0])
    EXPTABLE = [int(c["xp"], 0) for _l, c in rows]  # its last row is the 0xFFFFFFFF cap, as in KotOR 1
    cols, rows = kfmt.twoda(g.get("xptable", kfmt.T_2DA)[0])
    XPTABLE = [[int(c[k] or 0) for k in cols[1:]] for _l, c in rows]
    _c, rows = kfmt.twoda(g.get("npc", kfmt.T_2DA)[0])
    pct = {c["tag"].lower(): int(c["percentxp"]) for _l, c in rows}
    GAME_XP_GENERAL = pct.get("game_xp_general", 100)
    PER_NPC_BONUS = pct.get("per_npc_bonus", 0)
    _c, rows = kfmt.twoda(g.get("autobalance", kfmt.T_2DA)[0])
    CRMOD = {int(label): int(c["crmod"] or 0) for label, c in rows}


GAME = "K1"
CRMOD = {}


def level_from_xp(xp):
    for i in range(len(EXPTABLE) - 2, -1, -1):
        if xp >= EXPTABLE[i]:
            return i + 1
    return 1


def kill_award(pc_xp, cr, party_size=1, multiplier_set=0, spawn_level=None):
    """XP the PC gains for one kill (the engine's float steps).

    KotOR 2 (swkotor2.exe 1.0.2, 0x00575B20, read 2026-10-23): the row is the level - 1 capped
    at 30 and the column CR + 1 capped at 31; a creature with an autobalance row
    (MultiplierSet, byte 0x250) uses PCLevelAtSpawn (byte 0x251, at least 1) plus the row's
    crmod, not less than 0, in place of its challenge rating. spawn_level is the player's level
    when the creature spawned (a placed one: on entering the module); else the level now."""
    level = level_from_xp(pc_xp)
    column = ftol(f32(cr)) + 1
    if GAME == "K2":
        if multiplier_set:
            at_spawn = spawn_level if spawn_level is not None else level
            column = max(0, max(1, at_spawn) + CRMOD.get(multiplier_set, 0)) + 1
        column = min(column, 31)
        level = min(level, 31)
    if 1 <= column <= len(XPTABLE[0]):
        table = float(XPTABLE[level - 1][column - 1])
    elif column == 0:
        table = float(level)          # column 0 is the 2DA's "level" column
    else:
        table = 0.0                   # GetFLOATEntry fails, the zeroed slot stays
    percent = f32(float(GAME_XP_GENERAL))
    xp = f32(float(percent) * F_PERCENT * table)
    if PER_NPC_BONUS > 0:
        xp = f32(xp * (PER_NPC_BONUS * F_PERCENT * party_size + 1.0))
    award = ftol(math.ceil(xp))
    return receive(award)


def receive(amount, npc_percent=None):
    """CSWSCreature::ReceiveExperience for the PC (npc_percent None) or a party NPC."""
    mult = 1.0
    if npc_percent is not None:
        mult = f32(npc_percent * F_PERCENT)
    mult = f32(GAME_XP_GENERAL * F_PERCENT * mult)
    return ftol(math.ceil(amount * mult))


# ---------------------------------------------------------------- encounters
POINTS = [f32(1.5 ** i) for i in range(51)]


def points_from_cr(cr):
    """CSWSEncounter::CalculatePointsFromCR 0x005919E0."""
    if 0.0 < cr < 1.0:
        for i, k in enumerate((0.0, -1.0, -2.0, -3.0)):
            if cr >= FRACTIONAL_MIN[i]:
                return 1.0 if i == 0 else 1.5 ** k
        return 1.5 ** -4.0
    if 0.0 <= cr <= 50.0:
        return POINTS[ftol(f32(cr))]
    return 1.5 ** cr


class Entry:
    __slots__ = ("resref", "cr", "points", "single", "used", "tried", "xp_cr")

    def __init__(self, resref, cr, single, xp_cr):
        self.resref, self.cr, self.single, self.xp_cr = resref, f32(cr), single, xp_cr
        self.points = f32(points_from_cr(self.cr))
        self.used = 0
        self.tried = 0


def spawn_list(templates, rec, mx, difficulty_index, party_levels, rng):
    """Replay BuildSpawnList for one trigger. templates: [(resref, encounter CR, single, kill CR)]."""
    ents = [Entry(*t) for t in templates]
    n = len(ents)
    for _i in range(n):                       # bubble sort, CR descending (swaps only when less)
        for k in range(n - 1):
            if ents[k].cr < ents[k + 1].cr:
                ents[k], ents[k + 1] = ents[k + 1], ents[k]
    min_points = ents[-1].points if ents else 0.0
    party = 0.0
    for i, lv in enumerate(party_levels):
        party = f32(party + points_from_cr(float(lv if i == 0 else lv // 2)))
    if party == 0.0:
        return []
    diff = ENC_DIFFICULTY[difficulty_index] if 0 <= difficulty_index < len(ENC_DIFFICULTY) else 0
    level = ftol(math.log(party * 0.25) / math.log(1.5) + 0.5) + diff
    budget = f32(points_from_cr(float(level - 1)))
    if not budget > 0.0:
        return []
    out = []

    # BuildInitialSpawnList 0x00590F80
    slack = f32(F_TENTH * budget)
    points = budget
    i = 0
    while i < n:
        if len(out) >= mx or not points > 0.0:
            break
        e = ents[i]
        if e.single == 1 and e.used == 0:
            out.append(e)
            e.used = 1
            i += 1
            continue
        if e.points == 0.0:
            i += 1
            continue
        allow = points + slack
        if e.points > allow:
            i += 1
            continue
        if i + 1 < n and ents[i + 1].cr == e.cr:
            end = i + 1
            group, singles, tried = 1, 1, 0
            while end < n and ents[end].cr == e.cr:
                ents[end].tried = 0
                if ents[end].single:
                    singles += 1
                group += 1
                end += 1
            end -= 1
            e.tried = 0
            while len(out) < mx:
                idx = i + rng.randrange(group)
                c = ents[idx]
                if c.single == 0 or c.used == 0:
                    out.append(c)
                    c.used = 1
                    points = f32(points - c.points)
                if c.tried == 0:
                    c.tried = 1
                    tried += 1
                if group == singles and tried == group:
                    break
                if points + slack < c.points:
                    break
            i = end + 1
            continue
        taken = e.used
        while len(out) < mx:
            if e.single and taken:
                break
            out.append(e)
            taken = e.used = 1
            points = f32(points - e.points)
            if points + slack < e.points:
                break
        i += 1

    # AddCreaturesToSpawnList 0x00592280, from the last entry back
    if len(out) < rec and budget > min_points:
        k = len(out) - 1
        while k >= 0 and len(out) < rec:
            value = f32(points_from_cr(out[k].cr))
            if value != min_points:
                del out[k]
                threshold = f32(value - F_EPSILON)
                for c in ents:
                    if len(out) > rec:
                        break
                    if not c.points <= value:
                        continue
                    while True:
                        if not c.points <= threshold or len(out) >= mx or (c.single and c.used):
                            break
                        out.append(c)
                        c.used = 1
                        value = f32(value - c.points)
                        if not c.points <= value:
                            break
            k -= 1

    # PadOutCreatureCount 0x00590B10
    remaining = rec - len(out)
    threshold = 0.0
    while remaining > 0:
        pick = None
        for k in range(n - 1, -1, -1):
            if ents[k].points > threshold and (ents[k].single == 0 or ents[k].used == 0):
                pick = k
                break
        if pick is None:
            break
        threshold = ents[pick].points
        same = [k for k in range(n) if ents[k].points == threshold]
        first, last = same[0], same[-1]
        singles = sum(1 for k in same if ents[k].single == 1)
        for k in same:
            ents[k].tried = 0
        rng_range = last - first + 1
        tried = 0
        while True:
            idx = first + rng.randrange(rng_range)
            c = ents[idx]
            if c.single == 0 or c.used == 0:
                out.append(c)
                c.used = 1
                remaining -= 1
            if c.tried == 0:
                c.tried = 1
                tried += 1
            if rng_range == singles and tried == singles:
                break
            if remaining <= 0:
                break
    return out


# ---------------------------------------------------------------- data
def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def module_kills(doc, module, include_maybe):
    """(plain kills [(resref, cr, note)], encounters [dict]) of one module."""
    m = doc["modules"].get(module)
    if m is None:
        raise SystemExit("module %s not in the data" % module)
    kills, encs = [], {}
    for c in m["creatures"]:
        ok = c["hostile"] is True or (include_maybe and c["hostile"] == "maybe")
        if not ok or c["challenge_rating"] is None:
            continue
        if c["source"] == "encounter":
            e = c["encounter"]
            if not e.get("active") and not include_maybe:
                continue
            key = (e.get("instance"), e["template"])
            d = encs.setdefault(key, {"template": e["template"], "rec": e["rec"], "max": e["max"],
                                      "difficulty_index": e["difficulty_index"], "templates": []})
            d["templates"].append((c["resref"], e["encounter_cr"] or 0.0, e["single_spawn"] or 0,
                                   c["challenge_rating"]))
        else:
            for _ in range(c["count"] or 0):
                kills.append((c["resref"], c["challenge_rating"], c["source"]))
    return kills, list(encs.values())


def run_path(doc, modules, xp, include_maybe=False, order="file", enc_mode="sim", party=3, runs=200,
             verbose=False):
    rng = random.Random(1)
    rows = []
    for mod in modules:
        kills, encs = module_kills(doc, mod, include_maybe)
        if order == "high":
            kills.sort(key=lambda k: -k[1])
        elif order == "low":
            kills.sort(key=lambda k: k[1])
        start = xp
        for rr, cr, src in kills:
            gain = kill_award(xp, cr)
            if verbose:
                print("  %-10s %-18s CR %-5g level %2d  +%d" % (mod, rr, cr, level_from_xp(xp), gain))
            xp += gain
        for e in encs:
            if enc_mode == "none":
                continue
            if enc_mode in ("rec", "max"):
                count = e["rec"] if enc_mode == "rec" else e["max"]
                for i in range(count):
                    t = e["templates"][i % len(e["templates"])]
                    xp += kill_award(xp, t[3])
                continue
            total = 0
            counts = []
            for _r in range(runs):
                lv = level_from_xp(xp)
                spawned = spawn_list(e["templates"], e["rec"], e["max"], e["difficulty_index"],
                                     [lv] * party, rng)
                x = xp
                for c in spawned:
                    x += kill_award(x, c.xp_cr)
                total += x - xp
                counts.append(len(spawned))
            gain = int(round(total / runs))
            if verbose:
                print("  %-10s encounter %-16s spawns %d..%d (mean %.2f)  +%d (mean)" % (
                    mod, e["template"], min(counts), max(counts), sum(counts) / runs, gain))
            xp += gain
        rows.append((mod, start, xp, level_from_xp(xp)))
    return rows


# ---------------------------------------------------------------- scenario
def run_scenario(path, xp, verbose=False):
    sc = load(path)
    use_game(sc.get("game", "K1"))
    rows = []
    hd = None
    for mod in sc["modules"]:
        start = xp
        entry_level = level_from_xp(xp)
        for step in mod["steps"]:
            kind = step["do"]
            before = xp
            if kind == "kill":
                for _ in range(step.get("count", 1)):
                    xp += kill_award(xp, step["cr"], 1, step.get("multiplier_set", 0),
                                     entry_level if step.get("spawned_on_entry") else None)
            elif kind == "plot_xp":
                xp += receive(step["xp"])
            elif kind == "give_xp_hd":
                # GiveXPToCreature(PC, GetHitDice(PC) * N): hit dice = class levels taken, which
                # follow the XP level when the player levels up as soon as the game allows.
                hd = level_from_xp(xp) if step.get("hit_dice") is None else step["hit_dice"]
                xp += receive(hd * step["per_hd"])
            elif kind == "encounter":
                # added 2026-10-23 (make_path.py): an active encounter, as run_path's "sim" mode does
                rng = rng if "rng" in dir() else random.Random(1)
                runs = step.get("runs", 200)
                party = step.get("party", 3)
                templates = [tuple(t) for t in step["templates"]]
                total = 0
                for _r in range(runs):
                    lv = level_from_xp(xp)
                    spawned = spawn_list(templates, step["rec"], step["max"], step["difficulty_index"],
                                         [lv] * party, rng)
                    x = xp
                    for c in spawned:
                        x += kill_award(x, c.xp_cr)
                    total += x - xp
                xp += int(round(total / runs))
            elif kind == "next_level":
                # added 2026-10-23: AddMultiClass (0x0052DDC0) gives the next exptable threshold minus
                # the current XP, through DistributeExperience
                lv = level_from_xp(xp)
                if lv < len(EXPTABLE) - 1:
                    xp += receive(EXPTABLE[lv] - xp)
            elif kind == "floor":
                # SetXP(PC, xp) behind the script's own test; SetExperience never lowers XP.
                test = step.get("when", "always")
                if test == "always" or (test == "below" and xp < step["xp"]) or \
                        (test == "at_most" and xp <= step["xp"]):
                    xp = max(xp, step["xp"])
            else:
                raise SystemExit("unknown step " + kind)
            if verbose:
                print("  %-10s %-60s %6d -> %6d (level %d)" % (mod["module"], step.get("what", kind)[:60],
                                                           before, xp, level_from_xp(xp)))
        rows.append((mod["module"], start, xp, level_from_xp(xp)))
    return rows


def main(argv):
    opts = {"--xp": None, "--level": None, "--order": "file", "--encounters": "sim", "--party": "3",
            "--runs": "200", "--data": DATA, "--scenario": None}
    flags = {"--maybe": False, "--verbose": False}
    mods = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in opts:
            opts[a] = argv[i + 1]
            i += 2
        elif a in flags:
            flags[a] = True
            i += 1
        else:
            mods.append(a.lower())
            i += 1
    xp = 0
    if opts["--level"] is not None:
        xp = EXPTABLE[int(opts["--level"]) - 1]
    if opts["--xp"] is not None:
        xp = int(opts["--xp"])
    if opts["--scenario"]:
        rows = run_scenario(opts["--scenario"], xp, flags["--verbose"])
    else:
        if not mods:
            print(__doc__)
            return 1
        doc = load(opts["--data"])
        rows = run_path(doc, mods, xp, flags["--maybe"], opts["--order"], opts["--encounters"],
                        int(opts["--party"]), int(opts["--runs"]), flags["--verbose"])
    print("%-12s %8s %8s %6s" % ("module", "start", "end", "level"))
    for mod, s, e, lv in rows:
        print("%-12s %8d %8d %6d" % (mod, s, e, lv))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
