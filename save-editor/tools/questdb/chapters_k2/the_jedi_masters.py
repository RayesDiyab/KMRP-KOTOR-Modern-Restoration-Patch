"""KotOR 2, The Jedi Masters: the masters' meeting at the enclave, the return to the polar
academy and the move to the Ravager (curated 2026-10-23).

Worked out from the game's scripts and conversations (scanmod.py, showscript.py, dlgnode.py of
the k2kit, and the dialogs' EndConversation fields). IDs only: no names or text from the game
(KMRP rule, 2026-10-23); people are named by slot or tag.

How the act begins. The four free planets (Nar Shaddaa, Onderon, Dantooine, Korriban) each raise
the masters' count 000_Jedi_Found by one when their master is found (STAR_MAP_RULE below). At 4,
slot 6's conversation on the ship (dialog kreia, start entries E603, or E605 when
000_Last_Jedi_Kill > 0) sends the player to the enclave (journal lostjedi 80, or 85). Entering the
ruined enclave 605dan with the count at 4 sets 650DAN_Rebuilt 1 (k_enter_605) and the trigger
To_650 leads into 650dan.

The route:
  650dan  on arrival slot 6 leaves the party for good (dialog 650kreia E2 / E3 / E7:
          a_removekreia, RemoveAvailableNPC 6). The masters' meeting (dialog 650jedi: R0 sets the
          count to 4 again, E1 journal lostjedi 99); slot 6 returns as the enemy and the masters
          die. If a master was killed on his planet (000_Kavar_Dead, 000_Vrook_Dead or
          000_ZezKaiEll_Dead), the meeting is a fight instead (start entries E240 to E249,
          a_jediatk) and dialog krealone follows (E1 lostjedi 95). Dialog krehand1 E13
          (a_handspawn) sets 650DAN_006EBO_Trans 1 and, for a male player whose slot 4 has
          joined, makes slot 4 unselectable; the trigger Trans006EBO (k_006ebo) moves on to 006EBO.
  006ebo  the ship: k_attonend starts dialog AttonEnd, whose a_load006end plays discend (a
          female player, slot 11) or visasend (a male player, slot 9); both end in a_load262
          (movies DanMov02, TelMov15): StartNewModule 262TEL FROM_006EBO.
  262tel  (Telos's module; this is its second visit): k_262_enter with 000_Jedi_Found 4,
          trigger tr_atrend3 starts dialog atrend3. Sparing the academy's mistress ends with
          262TEL_Atris_End 2 (E91, light); leaving her to the holocrons with 1 (E86, dark, then
          dialog atrend4). Both reach a_hand_pc_end: a female player goes straight to 221TEL
          (movies MalMov02, MalMov01b); a male player first has dialog handend with slot 4, whose
          EndConversation script a_221load makes the same move.
  221tel  first entry (k_221_area_enter): slot 4 selectable again, slot 2 unselectable; the
          allies from the planets wait here (k_221tel_enter spawns them by 500OND_DarkSide_Iziz,
          200TEL_Control and 602DAN_End). The Onderon leader's line (dialog riiken E3, or ondlead
          E3 on the dark side) starts the bonus quest fuel_sith 10.
  220tel  the battle in the station (k_220area_hb: 220TEL_Battle_Over).
  222tel  the bonus target dies (k_fuelsith_death: fuel_sith 20); slot 2's scene (dialog
          222mand R3 a_mandalore|3 spawns the admiral by 101PER_Revan_End, R12 a_set_party forces
          slot 9 into the party), the admiral's conversation (dialog carth, R10 a_to851|2):
          StartNewModule 851NIH FROM_222TEL. That is the end of the chapter.

950cor is not part of this chapter: it is only reached from 262tel's first visit (a_setup_ebo2,
a_atrissis) and its dialog holorec sets lostjedi 30 and 262TEL_Escape_Telos, so it belongs to
Telos (chapters_k2/telos.py says the same).
"""
PLANET = "The Jedi Masters"

# ---------------------------------------------------------------------------- the masters' count
# Since 2026-10-23 (coordinator) the four free planets each carry "increments":
# [("000_Jedi_Found", 1, ...)], which the editor adds per skipped chapter, so this rule is kept
# only as the record of how the game counts. This chapter sets what the count's readers set on
# the way here (the take-off scenes at 1 and 2, the call at 4) as its own finals and journal.
# The rule, in the shape of chapters.py's STAR_MAP_RULE. It is NOT
# put into CHAPTER below: this chapter sets the count itself (650jedi R0: a_global_set 4), and
# the editor's star_map code (src/questdb.rs apply_chapter) counts only planet flags whose value
# is Boolean TRUE. KotOR 2 has no boolean per master; the markers are numbers, so the current
# editor would count 0 flags and write 000_Jedi_Found = base = 0. What the editor needs is in
# "editor_needs" below. Each free planet's chapter would carry
# dict(STAR_MAP_RULE, planet_flag=<its flag>, script=..., module=...) once the editor can test numbers.
STAR_MAP_RULE = {
    "counter": "000_Jedi_Found",
    "base": 0,
    "base_note": "000_Jedi_Found starts at 0; nothing before the four planets raises it (301nar a_setup_cs sets 3, "
                 "a debug script no run reaches)",
    "per_planet": 1,
    "planet_flags": ["351NAR_Ebon_Released", "506OND_End", "602DAN_End", "702KOR_Vash"],
    "planet_flags_note": "one Number per planet that every finished run of it leaves above 0 (light and dark): "
                         "Nar Shaddaa 351NAR_Ebon_Released 1 (the yacht's console, needed for the way back to the "
                         "docks where the master is found; the master's own talk, zezkaiel E2 / E113 in 303nar, "
                         "sets no global of its own), Onderon 506OND_End 1 / 2 (dialog talia E0 / a_end_game, "
                         "506ond; the master is found in the same module, dialog kavar E7 / E88), Dantooine "
                         "602DAN_End 1 / 2 (the battle's end; dialog vrook E11 / E13 / R0 follows at once), "
                         "Korriban 702KOR_Vash 1 (tr_vash, the same script that raises the count)",
    "flag_test": "number > 0",
    "rule": "000_Jedi_Found = 0 + 1 for each planet flag above 0 after this milestone's own values are set",
    "on_count": [
        {"count": 4, "set": [], "journal": ["lostjedi", 80],
         "note": "slot 6's conversation on the ship (dialog kreia, start E603: c_global_eq 4 000_Jedi_Found; E604 "
                 "journal lostjedi 80) sends the player to the enclave; a player with 000_Last_Jedi_Kill > 0 gets "
                 "E605 and lostjedi 85 instead. The conversation still starts by itself when the count is 4, so "
                 "setting the stage is cosmetic. k_enter_605 (605dan) sets 650DAN_Rebuilt 1 on entering the "
                 "enclave at 4 or more"},
    ],
    "readers": "k_sup_galaxymap (>= 1 and < 4: plays the academy scenes in 262tel at the next take-off, "
               "000_Atriscs1 2 at >= 1 and 000_Siscut1 2 at >= 2, which the game does by itself), dialog kreia "
               "(== 4), k_enter_605 (>= 4), k_262_enter / tr_atrend3 / a_setup_ebo (262tel, == 4 / < 4), 650jedi "
               "R0 (sets 4), k_align_movie (>= 3), a_set_return / c_kelborn_mes (Dxun's return message)",
    "source": "a_global_inc|1,0,0,0,0,000_Jedi_Found in dialogs zezkaiel (303nar E2 / E113), kavar (506ond E7 / "
              "E88), vrook (602dan E11 / E13 / R0); SetGlobalNumber in tr_vash (702kor)",
    "editor_needs": "src/questdb.rs apply_chapter counts a flag only when its value is "
                    "GlobalValue::Bool(true). For KotOR 2 it must also count GlobalValue::Number(n) with n > 0 "
                    "(for example: a flag counts when it is Bool(true) or Number(n > 0), or per flag "
                    "{\"name\": ..., \"min\": 1}); with that, base 0, per_planet 1 and these four flags give the "
                    "game's count. on_count works as it is (only numbers and one journal entry are set)",
}

CHAPTER = {
    "order": 8,
    "chapter_title": "The Jedi Masters: the enclave, the polar academy and the move to the Ravager",
    "returnable": False,
    "return_modules": {"650dan": False, "006ebo": False, "220tel": False, "221tel": False, "222tel": False,
                       "950cor": False},
    "returnable_note": "after 222tel the party is on the Ravager and then Malachor V; the ship never flies the "
                       "galaxy map again, so none of these modules is entered again. 950cor belongs to Telos's "
                       "first visit (see the docstring)",
    "critical": [
        ("262tel", "dialog atriscs1 E23", "the take-off scene at 000_Jedi_Found >= 1 (k_sup_galaxymap sets "
                                          "000_Atriscs1 2, k_262_enter sets 1): a_atriscs1|9 back to 003EBO"),
        ("262tel", "dialog siscut1 E2", "the take-off scene at 000_Jedi_Found >= 2: 000_Siscut1 1, then E11 "
                                        "a_siscut1|5 back to 003EBO"),
        ("003ebo", "dialog kreia E604", "000_Jedi_Found == 4 (start E603): journal lostjedi 80, the call to the "
                                        "enclave (E605, lostjedi 85, when 000_Last_Jedi_Kill > 0)"),
        ("605dan", "k_enter_605", "entering the ruined enclave at 000_Jedi_Found >= 4: 650DAN_Rebuilt 1; the "
                                  "trigger To_650 leads into 650dan FROM_605DAN"),
        ("650dan", "dialog 650kreia E2", "on arrival: a_removekreia, slot 6 leaves the party for good"),
        ("650dan", "dialog 650jedi R0", "the masters' meeting: 000_Jedi_Found = 4 (a_global_set)"),
        ("650dan", "dialog 650jedi E1", "journal lostjedi 99 (the masters met, slot 6 destroys them)"),
        ("650dan", "dialog 650jedi E2", "650DAN_Jedi_End 1"),
        ("650dan", "a_handspawn|0,0,0,0,0,", "dialog krehand1 E13: 650DAN_006EBO_Trans 1; slot 4 unselectable "
                                             "for a male player"),
        ("650dan", "k_006ebo", "trigger Trans006EBO: 003EBO_Background 5, StartNewModule 006EBO"),
        ("006ebo", "k_attonend", "on entering: dialog AttonEnd"),
        ("006ebo", "a_load006end|0,0,0,0,0,", "dialog attonend: discend (female player) or visasend (male)"),
        ("006ebo", "a_load262|0,0,0,0,0,", "discend R2 / visasend: movies DanMov02, TelMov15, StartNewModule "
                                           "262TEL FROM_006EBO"),
        ("262tel", "dialog atrend3 E91", "the academy's mistress spared: 262TEL_Atris_End 2 (light)"),
        ("262tel", "dialog atrend3 R103", "a_hand_pc_end: a female player moves to 221TEL; a male player gets "
                                          "dialog handend, whose EndConversation a_221load moves to 221TEL"),
        ("221tel", "k_221_area_enter", "first entry: slot 4 selectable again, slot 2 unselectable"),
        ("221tel", "dialog riiken E3", "journal fuel_sith 10 (the Onderon leader; ondlead E3 on the dark side)"),
        ("220tel", "k_220area_hb", "the station battle ends: 220TEL_Battle_Over"),
        ("222tel", "k_fuelsith_death", "the saboteur dies: journal fuel_sith 20"),
        ("222tel", "a_mandalore|3,0,0,0,0,", "dialog 222mand R3: the admiral appears (by 101PER_Revan_End), "
                                             "slot 9 selectable"),
        ("222tel", "a_set_party|0,0,0,0,0,", "dialog 222mand R12: party selection with slot 9 forced in"),
        ("222tel", "a_to851|2,0,0,0,0,", "dialog carth R10: StartNewModule 851NIH FROM_222TEL"),
    ],
    "journal": [
        ("lostjedi", 99, "dialog 650jedi E1 (650dan): the light-side end of the quest"),
        ("fuel_sith", 20, "k_fuelsith_death (222tel): the bonus quest's end"),
    ],
    "finals": {
        "000_Jedi_Found": (4, True, "dialog 650jedi R0 (and R237..R242 on the fighting route) sets 4; the four "
                                    "planets reached 4 before (STAR_MAP_RULE in this file)"),
        "000_Atriscs1": (1, False, "k_sup_galaxymap (read from its disassembly) sets 2 and moves to 262TEL at a "
                                   "take-off while 000_Jedi_Found is 1 to 3, the flag is 0 and the "
                                   "000_PLAYER_GENDER flag is TRUE; k_262_enter (262tel) sets 1 when the scene plays. "
                                   "Three take-offs come at those counts in every run, so a run of that gender has "
                                   "played it; with the flag FALSE the galaxy map never plays it and the value stays "
                                   "0 (the editor has no per-gender value; 1 there only blocks a scene that cannot "
                                   "play). Left at 2 or 0 it would not replay after the count is 4"),
        "000_Siscut1": (1, False, "k_sup_galaxymap sets 2 at a take-off with 000_Jedi_Found 2 or 3 under the same "
                                  "flag test as 000_Atriscs1; dialog siscut1 E2 / k_262_enter (262tel) set 1 when the "
                                  "scene plays. Same gender limit as 000_Atriscs1"),
        "650DAN_Jedi_End": (1, True, "dialog 650jedi E2; 650jedi's start E251 reads it"),
        "650DAN_Revelation": (1, True, "dialog 650kreia R14, its only writer: the scene's start E12 (local 12 == 1) "
                                       "runs R12 > E13 > R13 > E14 > R14 with no choice"),
        "650DAN_006EBO_Trans": (1, True, "a_handspawn (dialog krehand1 E13); k_006ebo reads it"),
        "650DAN_Rebuilt": (1, True, "k_enter_605 (605dan, Dantooine's module) sets 1 on every branch that runs with "
                                    "000_Jedi_Found >= 4, on the way into this chapter; its only writer"),
        "003EBO_Background": (5, True, "k_006ebo and krehand1 E13 (650dan) both set 5: the ship's backdrop in 006ebo; "
                                       "003ebo is not entered again after this chapter"),
        "262TEL_Atris_End": (2, True, "dialog atrend3 E91 (262tel, second visit): spared, the light reply; E86 sets 1 "
                                      "on the dark side. atrend4's start E5 reads 2"),
        "220TEL_Battle_Over": (True, False, "k_220area_hb (220tel), its only writer of TRUE, when the station battle "
                                            "is over"),
        "000_Kavar_Dead": (None, False, "light side: the masters die by slot 6's hand in the meeting; their death "
                                        "scripts are not run on that route. See dark"),
        "000_Vrook_Dead": (None, False, "as 000_Kavar_Dead"),
        "000_ZezKaiEll_Dead": (None, False, "as 000_Kavar_Dead"),
    },
    "party_remove": [
        (6, "a_removekreia|0,0,0,0,0,", "650dan", True,
         "dialog 650kreia E2 / E3 / E7: RemoveAvailableNPC(6) on arrival at the enclave, on every route; slot 6 "
         "is the enemy from here on"),
    ],
    "party_note": "slot 4 (a male player's companion) is made unselectable in 650dan (a_handspawn) and selectable "
                  "again on entering 221tel (k_221_area_enter); slot 2 is unselectable from 221tel on; 222tel "
                  "forces slot 9 into the party (a_set_party). No slot joins in this chapter",
    "dark": {
        "note": "the dark-side run has killed a master on his planet (Onderon's dark block sets 000_Kavar_Dead 1), "
                "so the meeting in 650dan is a fight (650jedi start E240..E249, a_jediatk): the player kills the "
                "masters, their death scripts set the *_Dead values and the last one starts dialog krealone (E1 "
                "lostjedi 95). In 262tel the academy's mistress is left to the holocrons (atrend3 E86: "
                "262TEL_Atris_End 1, then dialog atrend4). The route on is the same",
        "journal": [
            ("lostjedi", 95, "dialog krealone E1 (650dan), started by the last master's death script "
                             "(k_death_kavar / k_death_vrook / k_death_zez)"),
            ("fuel_sith", 20, "k_fuelsith_death (222tel); fuel_sith 10 comes from dialog ondlead E3 (221tel)"),
        ],
        "finals": {
            "000_Kavar_Dead": (1, True, "k_death_kavar (650dan) or dialog vaklu E4 (506ond, Onderon's dark side)"),
            "000_Vrook_Dead": (1, False, "k_death_vrook (650dan) in the fight"),
            "000_ZezKaiEll_Dead": (1, False, "k_death_zez (650dan) in the fight, or k_zez_death (303nar)"),
            "262TEL_Atris_End": (1, True, "dialog atrend3 E86 (262tel)"),
        },
    },
    "next": {"from": ("222tel", "a_to851|2,0,0,0,0,"),
             "note": "dialog carth R10 (222tel): StartNewModule 851NIH FROM_222TEL; R5 a_to851|1 has played movie "
                     "MalMov04 just before"},
    "credits_fixed": [],
    "grants": [
        {"spell": 180, "side": "light", "note": "a_grant_force (650jedi E137 / E138 / E188 / E189, krealone E161): "
                                                "Force Enlightenment when GoodEvil is 40 or more"},
        {"spell": 177, "side": "dark", "note": "a_grant_force: Force Crush when GoodEvil is 0 to 39"},
    ],
    "xp": {"modules": ["650dan", "006ebo", "221tel", "220tel", "222tel"], "maybe": False, "extra": [],
           "endings": {"lostjedi": 99, "fuel_sith": 20}},
}
