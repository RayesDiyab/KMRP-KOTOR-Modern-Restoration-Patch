"""KotOR 2, Dantooine: Khoonda, the master in the kinrath cave and the mercenaries' attack.

Curated 2026-10-23 from the game's scripts and conversations (scanmod.py, showscript.py and
dlgnode.py of the research kit; tools/questdb/milestone.py builds the milestone). IDs only:
module names, dialog nodes, script keys, global names, tags and templates.

The chapter: the ship lands on the Khoonda plains (601dan); the administrator in Khoonda
(602dan) sends the player to the ruined enclave (605dan, 610dan) and the master (tag
npc_vrook) is found held by mercenaries in the kinrath cave (604dan). He warns of the
attack on Khoonda (journal khoondad 10, dialog vrook E21 in 604dan). The player then picks a
side: the militia (601DAN_Side 1, light) or the mercenaries (601DAN_Side 2, dark). The
battle is fought on the plains (601dan, a_begin_battle) and ends in Khoonda (602dan); after
it the master talks to the player and counts as found (000_Jedi_Found + 1).

000_Jedi_Found is the masters' count four chapters share (see MASTERS_RULE below). The star-map
rule cannot hold it (it counts only boolean planet flags), so the chapter carries it in
"increments": the editor adds 1 for each chapter skipped.
"""
PLANET = "Dantooine"

# The masters' count. Each of the four free planets after Telos raises 000_Jedi_Found by one
# with a_global_inc (param 1, string 000_Jedi_Found) in the master's conversation:
#   Nar Shaddaa  303nar dialog zezkaiel E2 / E113
#   Onderon      506ond dialog kavar E7 / E88
#   Dantooine    602dan dialog vrook E11 / E13 (light) and R0 (the mercenary side)
#   Korriban     702kor (the dead master: see chapters_k2/korriban.py)
# At 4 the ship's conversation of slot 6 (003ebo/005ebo dialog kreia, start entries 603 and 605:
# c_global_eq 4 000_Jedi_Found) sends the player to the enclave (journal lostjedi 80/85); the
# masters' meeting in 650dan then sets the count to 4 again (dialog 650jedi R0, a_global_set).
# No boolean per-planet flag exists in globalcat.2da for a STAR_MAP_RULE; the markers below are
# numbers (an editor rule would need "number flag > 0").
MASTERS_RULE = {
    "counter": "000_Jedi_Found",
    "base": 0,
    "per_planet": 1,
    "planet_markers": {
        "Nar Shaddaa": "300NAR_ZezKaiEll (number; the master's state, 303nar)",
        "Onderon": "the kavar conversation in 506ond (no global of its own found; 000_Kavar_Dead is the dark one)",
        "Dantooine": "602DAN_End > 0 (the battle is over; the master's talk follows at once)",
        "Korriban": "702KOR_Vash (number, 702kor)",
    },
    "on_count": [
        {"count": 4, "note": "slot 6's conversation on the ship (dialog kreia E604, journal lostjedi 80) sends "
                             "the player to the enclave: The Jedi Masters chapter (650dan)"},
    ],
    "source": "a_global_inc in each master's conversation; c_global_eq 4 000_Jedi_Found in dialog kreia",
}

CHAPTER = {
    "order": 6,
    "chapter_title": "Dantooine: the ruined enclave, the master and the battle for Khoonda",
    "returnable": True,
    "returnable_note": "the ship can fly back to Dantooine while the four free planets are open; the masters' "
                       "meeting later takes place in 650dan (The Jedi Masters), not in these modules",
    "critical": [
        ("602dan", "dialog terena E66", "the administrator opens the enclave: journal relicpast 20, "
                                        "605DAN_Enclave_Open 1"),
        ("604dan", "dialog vrook E0", "the master is freed in the kinrath cave: journal lostshad 90"),
        ("604dan", "dialog vrook E21", "the master warns of the attack: journal khoondad 10, 604DAN_Vrook_Status 3"),
        ("601dan", "dialog zherron E48", "the militia's side: 601DAN_Side 1"),
        ("602dan", "dialog zherron R102", "a_begin_battle: StartNewModule 601DAN (the battle on the plains)"),
        ("602dan", "dialog terena E99", "after the battle: journal khoondad 90"),
        ("602dan", "dialog terena E100", "a_redemption: journal redemption 90"),
        ("602dan", "dialog vrook E13", "the master is found: 000_Jedi_Found + 1, journal lostjedi 77"),
        ("610dan", "dialog disc_enc R3", "a_disc_join: slot 11 joins a female player (AddAvailableNPCByObject)"),
    ],
    "journal": [
        ("khoondad", 90, "dialog terena E99 (602dan): Khoonda held, the administrator alive"),
        ("lostshad", 90, "dialog vrook E0 (604dan): the master freed in the kinrath cave"),
        ("redemption", 90, "a_redemption from dialog terena E100 (602dan)"),
        ("relicpast", 90, "tr_enter_610 (610dan): entering the enclave's lower level"),
        # the battle's preparations: a_khoondad (param 19) closes each one when the battle starts,
        # so every run ends them at 90 or higher; these are the full run's light outcomes
        ("khoonda_doors", 90, "dialog sec_door R2 (601dan): the side door sealed"),
        ("khoonda_droids", 90, "the three droids repaired (a_khoondad 19 at the battle's start)"),
        ("khoonda_guns", 90, "the turrets repaired (a_khoondad 19 at the battle's start)"),
        ("khoonda_medic", 90, "the medical droid repaired (a_khoondad 19 at the battle's start)"),
        ("khoonda_morale", 90, "recruits for the militia (a_khoondad 19 at the battle's start)"),
        ("khoonda_traps", 91, "the minefields strengthened (a_khoondad 19 at the battle's start)"),
        # side quests of a full run (light choices)
        ("akkere_hydro", 91, "dialog akkere R38 (601dan): the mechanic joins the militia"),
        ("cavecrawl", 90, "dialog zherron R54 (602dan): the kinrath matriarch reward"),
        ("chguard", 91, "dialog terena R33 (602dan): the sensors given to the administrator"),
        ("danthief", 91, "dialog suulru E6 (602dan): the modulator and the credits returned"),
        ("ghostrest", 90, "dialog daraala R18 (605dan): both bodies brought back"),
        ("ssensor", 90, "dialog saedhe R25 (602dan) / R7 (601dan): the three sensors handed in"),
    ],
    "finals": {
        "601DAN_Side": (1, True, "the militia's side (dialog zherron E48 / R79 in 601dan, a_begin_battle, its only "
                                 "writer of 1); the "
                                  "mercenaries' side is 2 (dialog azkul E22): see dark"),
        "602DAN_End": (1, True, "k_battle_death when the attackers are beaten (the militia's side); 2 on the "
                                "mercenaries' side (dialog azkul E20)"),
        "601DAN_Battle_Mili": (4, True, "k_battle_death at the battle's end, on the branch that also sets 602DAN_End "
                                        "1; the other writers (a_begin_battle 1, a_khoondad|19 and the death "
                                        "counters 2) come before it"),
        "601DAN_Winners": (True, True, "a_clean_up (ExecuteScript from k_enter_dan, 601dan's OnEnter) once "
                                       "601DAN_Battle_Mili is 4; the party re-enters 601dan after the battle to board "
                                       "the ship there (this chapter's route on)"),
        "602DAN_Winners": (True, True, "a_clean_up once 601DAN_Battle_Mili is 4, as 601DAN_Winners"),
        "605DAN_Enclave_Open": (1, True, "dialog terena E66 (602dan): the administrator's permission"),
        "604DAN_Vrook_Status": (4, False, "dialog vrook E32 / R41 / R48 / R92 (604dan): the master walks out of "
                                          "the cave; 3 is set at E21 just before. dialog merc_cpt (604dan: E5, E15, "
                                          "R4, R19) sets 6, which vrook R2 (602dan) reads; whether a light run can "
                                          "still pass through those lines after 4 was not worked out"),
        "602DAN_Changing_Guard": (2, False, "dialog terena R33 (602dan): the light end of chguard (the sensors handed "
                                            "in). Order-dependent: when that happens before the master is back, "
                                            "terena's later start E84 runs R101 > E85 > R102 > E98, which sets 3 "
                                            "(the militia leader reinstated); after it, 2 stays. Read by zherron E43 / "
                                            "R44 (== 2) and terena E98"),
        "003EBO_RETURN_DEST": (5, True, "tr_ehawk_custom (601dan) when boarding the ship"),
        "003EBO_BACKGROUND": (5, True, "tr_ehawk_custom (601dan) when boarding the ship"),
        "000_Disciple_Joined": (None, False, "a_disc_join sets 1 when slot 11 joins, which happens only for a "
                                             "female player; the party entry carries it"),
        "601_FIRST_ENTER": (True, True, "k_enter_dan (601dan OnEnter) on the first entry; also one of the six planet "
                                        "flags the Ebon Hawk's cutscene table counts"),
        # The Ebon Hawk's cutscene table (peragus.py; scenes due once slot 3 has joined in Nar Shaddaa, which
        # comes before this chapter in skip order: see dxun.py and onderon.py)
        "CUT_G0T0_REMOTE_1": (True, True, "slots 3 and 1 available and 003EBO_G0t0_Remote 0: the first entry after "
                                          "slot 3 joins; dialog g0t0rem1 E3 sets 003EBO_G0t0_Remote 1"),
        "003EBO_G0t0_Remote": (1, True, "dialog g0t0rem1 E3 (003ebo); CUT_G0T0_REMOTE_2 (000_Jedi_Found above 2) is "
                                        "left to the game"),
        "CUT_BAO_G0T0_1": (True, True, "slots 1 and 3 available: on the same entry as g0t0rem1 or the next"),
        "003EBO_G0T0_BAO_2": (1, False, "the table sets 1 with CUT_BAO_G0T0_1; the next entry raises it to 2 and plays "
                                        "CUT_BAO_G0T0_2 (dialog bao_g0_2: a_adj_dex|1 on slot 3), left to the game "
                                        "because the editor cannot raise slot 3's dexterity"),
        # not set: slot 11's scenes on the ship (CUT_DISC_WORLD_1, CUT_KREIA_DISC_1 to 3, CUT_DISC_FORCE...).
        # A female player only, and each of them ends the run of scenes (a_next_scene|1), so they come one per
        # entry after the slot joins; the editor has no per-gender value, and they are left to the game
    },
    "master_met": [{"module": "602dan", "dialog": "vrook", "local": 60}],  # the flag his own conversation sets once he has taught
    "teach_form": True,  # vrook R16 > lrn_form (a_fire_learn|2): one a_give_form; the dark fight gives one too
    "increments": [
        ("000_Jedi_Found", 1, "the masters' count four planets share: a_global_inc in dialog vrook E13 (602dan, "
                              "light) or E11 / R0 (the mercenaries' side); see MASTERS_RULE in this file"),
    ],
    "party_recruit": [
        (11, "p_disciple", "a_disc_join|0,0,0,0,0,", "610dan", True,
         "a female player only: slot 11 joins in the enclave's lower level (dialog disc_enc R3 / R37 / R38 / R43) "
         "or in Khoonda (602dan dialog disc_enc R74); the game adds the placed creature (template p_disciple in "
         "610dan's area file) with AddAvailableNPCByObject", "female"),
    ],
    "dark": {
        "note": "the mercenaries' side: the player helps the attackers take Khoonda (601DAN_Side 2, dialog azkul "
                "E22 in 601dan); Khoonda falls, the administrator dies (azkul E19 / E20 in 602dan: 602DAN_End 2), "
                "the mercenaries' leader pays the player (azkul E6 onward, credits.py's business) and the master "
                "fights the player in 602dan (dialog vrook E1, R0 still raises 000_Jedi_Found) and flees",
        # the editor puts this list in place of the light one, so it holds the whole journal
        "journal": [
            ("khoondad", 92, "dialog azkul E4 (602dan): Khoonda taken with the mercenaries"),
            ("lostshad", 90, "dialog vrook E0 (604dan): the master freed in the kinrath cave, as on the light side"),
            ("relicpast", 90, "tr_enter_610 (610dan), as on the light side"),
            ("khoonda_doors", 91, "dialog sec_door R4 (601dan): the side door left open"),
            ("khoonda_droids", 91, "the droids turned on the militia (a_khoondad 19)"),
            ("khoonda_guns", 91, "the turrets turned on the militia (a_khoondad 19)"),
            ("khoonda_medic", 92, "dialog med_drd E4 (602dan): the wounded sedated"),
            ("khoonda_morale", 91, "the mercenaries' battle plan (a_khoondad 19)"),
            ("khoonda_traps", 96, "every mine disarmed (a_khoondad 19)"),
            ("akkere_hydro", 90, "dialog akkere E24 / R33 (601dan)"),
            ("cavecrawl", 90, "dialog zherron R54 (602dan)"),
            ("chguard", 92, "a_quest_cleanup from dialog azkul R16 (602dan)"),
            ("danthief", 90, "dialog suulru E7 (602dan)"),
            ("ghostrest", 90, "dialog daraala R18 (605dan)"),
            ("ssensor", 90, "dialog saedhe R25 (602dan) / R7 (601dan), as on the light side"),
        ],
        "journal_note": "redemption is left as it was: a_redemption raises it only on the light ending (terena "
                        "E100), and no setter of its stage 91 was found",
        "finals": {
            "601DAN_Side": (2, True, "dialog azkul E22 (601dan)"),
            "602DAN_End": (2, True, "dialog azkul E20 (602dan)"),
            "601DAN_Battle_Mili": (4, False, "dialog azkul E20 (602dan)"),
            "602DAN_Changing_Guard": (None, False, "left unchanged on the mercenaries' side"),
        },
    },
    "next": {"from": ("601dan", "tr_ehawk_custom"),
             "note": "boarding the ship on the Khoonda plains (trigger to_ebonhawk_custom); the ship (003ebo) is "
                     "the Ebon Hawk chapter's between-planets module"},
    "credits_fixed": [],
    "xp": {"modules": ["601dan", "602dan", "605dan", "610dan", "604dan", "603dan"], "maybe": False, "extra": [],
           "endings": {"khoondad": 90, "lostshad": 90, "redemption": 90, "akkere_hydro": 91, "chguard": 91,
                       "danthief": 91, "khoonda_traps": 91, "ssensor": 90}},
}
