"""KotOR 2, Dxun: the first stay on the jungle moon, up to the shuttle to Iziz (2026-10-23).

Where the chapter ends. The Dxun and Onderon modules interleave in the story: the crash on
Dxun (421dxn turret, 401dxn landing), the Mandalorian camp (402dxn, 403dxn, 404dxn), the
shuttle to Iziz (501ond ...), the escape back to the camp, the Ebon Hawk, a message that calls
the party back (after another master is found), the tomb (410dxn, 411dxn) and the battle for
Iziz (511ond, 504ond, 506ond). build.py gives each chapter only its own module numbers, and a
milestone can only name scripts in those modules, so this chapter ends at the one point where
the story first leaves the 4xx modules, in a single move: the camp's shuttle to Iziz
(a_to_iziz2 in 403dxn, light and dark alike). Everything after it, including the return to
the camp and the tomb, is the Onderon chapter (tools/questdb/chapters_k2/onderon.py), whose
values for 403dxn, 410dxn and 411dxn are curated there.

Worked out with the k2kit research tools (scanmod.py, showscript.py, dlgnode.py) over the
game's own scripts and dialogs; no save of this point exists. IDs only.
"""
PLANET = "Dxun"
CHAPTER = {
    "order": 4,
    "chapter_title": "Dxun: the Mandalorian camp and the shuttle to Iziz",
    "returnable": True,
    "return_modules": {"410dxn": False, "411dxn": False, "421dxn": False},
    "returnable_note": "after the first visit every later landing on the moon goes to 401dxn (k_sup_galaxymap: "
                       "401DXN_Visited set, 003EBO_RETURN_DEST 4) and the camp is reached on foot, so 401dxn to "
                       "404dxn come back. 421dxn is the one-time turret fight of the arrival; the tomb (410dxn, "
                       "411dxn) is played later, in the Onderon chapter, so it is not stored as played here",
    "critical": [
        ("401dxn", "k_401enter", "401dxn OnEnter on the crash landing: 401DXN_Visited 1, 401_FIRST_ENTER, the guide "
                                 "(401DXN_Man_Guide)"),
        ("402dxn", "a_to_mandalore|0,0,0,0,0,", "dialog sentry R28: the sentry takes the party to the camp "
                                                "(403dxn WP_MEETMANDALORE)"),
        ("403dxn", "dialog mandalor E40", "journal foutpost 90 (E70 on the route that fought the guards)"),
        ("403dxn", "dialog mandalor E41", "journal altroute 20"),
        ("403dxn", "a_pp_start|0,0,0,0,0,", "dialog mandalor E45: journal pricepassage 10, 403DXN_Price_Passage 1"),
        ("403dxn", "c_pp_done|0,0,0,0,0,", "the camp's tasks counted from their journal end stages; enough of them "
                                           "set 403DXN_Price_Passage 50 (link mandalor R38>E19)"),
        ("403dxn", "a_mand_cs1|10,0,0,0,0,", "dialog mandalor R25: missingm 50 if it was never finished, then the "
                                             "cutscene mand_cs1"),
        ("403dxn", "dialog mand_cs1 E19", "journal pricepassage 99"),
        ("403dxn", "k_403_hb", "module heartbeat: the attack on the camp ends, 403DXN_Sith_Attack 5, dialog "
                               "sith_att"),
        ("403dxn", "a_to_iziz|0,0,0,0,0,", "dialog sith_att R12 (411DXN_Complete 0): slot 2 joins (template "
                                           "p_mand), party selection with slot 2 forced, then a_to_iziz2"),
        ("403dxn", "a_to_iziz2|0,0,0,0,0,", "411DXN_Complete 0: PlayMovie OndMov05, StartNewModule 501OND "
                                            "From_403DXN"),
    ],
    "journal": [
        ("foutpost", 90, "dialog mandalor E40 / E70 (403dxn)"),
        ("altroute", 20, "dialog mandalor E41 (403dxn)"),
        ("pricepassage", 99, "dialog mand_cs1 E19 (403dxn)"),
        ("explosivesit", 99, "dialog mandalor R32 (403dxn)"),
        ("scouthunt", 99, "dialog kelborn R3 / R5 / R7 (402dxn)"),
        ("tcannoks", 99, "dialog zuka E6 / R5 (403dxn)"),
        ("tsupport", 99, "dialog zuka R26 (403dxn)"),
        ("zchallenge", 99, "dialog gategrd E1 / E27 (403dxn)"),
        ("battle_circle", 90, "k_fab_dueluser / tr_circle (403dxn): the last fight of the circle won; 91 is the "
                              "ban, which is above 90"),
        ("missingm", 70, "dialog xarga E6 (403dxn): the recruit brought back alive and the trainer's reward, the "
                         "light-side ending; 80 (blaming the recruit) is the other ending with XP"),
    ],
    "finals": {
        "401DXN_Visited": (1, True, "k_401enter on the first landing; k_sup_galaxymap reads it: with it set, choosing "
                                    "the moon lands at 401dxn instead of replaying the arrival attack"),
        "401_FIRST_ENTER": (True, True, "k_401enter"),
        "401DXN_Man_Guide": (None, False, "nothing reads it; k_401enter sets 1 only on an entry of 401dxn after the "
                                          "camp is visited (403DXN_Camp_Visited > 0), not on the crash landing, and "
                                          "this chapter goes on from the camp by shuttle: 0 or 1 by whether the "
                                          "player walks back to 401dxn. Left unchanged"),
        "401DXN_STARTED": (None, False, "the arrival sequence (k_sup_galaxymap 1 and 2, k_421_modheart 4, "
                                        "k_003ebo_enter 3 or 5, a_dxun_cs 3 in 003ebo) runs before the landing; "
                                        "the galaxy map only reads it while 401DXN_Visited is 0. Left unchanged"),
        "402DXN_SentryPost": (False, True, "a_walk_mandalore (dialog sentry E21, the only way to R28 a_to_mandalore) "
                                           "sets TRUE; k_402_enter sets it FALSE again on the next entry of 402dxn while "
                                           "the sentry is there, and the full run goes back to 402dxn for the camp's "
                                           "tasks (missingm: a_kumus_found in 402dxn)"),
        "402DXN_Sentry_Talk": (1, True, "trigger TR_MEETMANDALORE (tr_sentrytlk), its only writer, on the way to the "
                                        "sentry"),
        "402DXN_ScoutHunt": (4, True, "a_kel_wpend (dialog kelborn E10): the scouts reported, journal scouthunt 99 "
                                      "(in this chapter's journal); the triggers' + 1 come before it"),
        "403DXN_Camp_Visited": (1, True, "a_meetmand_cs / a_mand_cs1 / a_mandtalktrue when tag g_mandalore is met"),
        "403DXN_Kreia_Spawned": (None, False, "a_mand_cs1 (dialog mand_cs1 E19) sets it only when no object tagged "
                                              "kreia is in the camp, i.e. when slot 6 was not in the active party: the "
                                              "player's party choice. Left unchanged"),
        "403DXN_Price_Passage": (50, False, "c_pp_done sets 50 once enough of the camp's tasks are done; the tasks "
                                            "themselves add 1 each (a_es_reward, a_mm_set, a_zc_finish, scouts), "
                                            "so each task finished after the check adds 1 more: 50 to 54 by the "
                                            "order the player does them. Its readers (mandalor E11: above 1, "
                                            "c_pp_check, c_pp_done) treat any of them alike"),
        "403DXN_Sith_Attack": (5, True, "k_403_hb when the attack ends; dialog sith_att then sends the party to Iziz"),
        "403DXN_ES_Quest": (4, True, "a_es_reward / dialog mandalor R32: the explosives task rewarded (explosivesit "
                                     "99 in this chapter's journal); 1 to 3 come before it"),
        "403DXN_Missing_Mand": (4, True, "a_mm_set|4 (dialog xarga E6): the ending missingm 70 this chapter's journal "
                                         "holds; a_mm_set never lowers it"),
        "403DXN_TechSupport": (4, True, "a_techsupport|4 (dialog zuka R26) with journal tsupport 99; the repairs' + 1 "
                                        "come before it"),
        "403DXN_TS_Telecomp": (1, True, "a_ts_telecomp (dialog ts_comp E3), its only writer; tsupport 99 needs both "
                                        "repairs (c_ts_allfixed)"),
        "403DXN_TS_Wires": (1, True, "a_ts_repairwires (dialog ts_wire E3), its only writer; tsupport 99 needs both "
                                     "repairs (c_ts_allfixed)"),
        "403DXN_CannokTrouble": (5, True, "a_cannokt_reward / a_cannok_reward0 (dialog zuka E7 / E11): both rewards "
                                          "set 5 with tcannoks 99"),
        "403DXN_Zakkeg_Ch": (3, False, "a_zc_finish (dialog gategrd E27, zchallenge 99 with the reward). Killing the "
                                       "beast sets 2 (k_zak_death) and the guard's other ending E1 also gives "
                                       "zchallenge 99 without a_zc_finish, leaving 2. Only c_zc_done (== 2) reads it"),
        "403DXN_Battle_Circle": (5, False, "a win counter (k_fab_dueluser / tr_circle add 1); journal battle_circle "
                                           "90 comes with the fifth win; whether later bouts add more was not worked "
                                           "out (a_circle_fight is too large for the tools)"),
        # The Ebon Hawk's cutscene table (peragus.py): the scenes due once slot 3 has joined (Nar Shaddaa, the
        # chapter before this one in skip order) play on the first entries of the ship after it. This chapter
        # has no entry of its own that runs the table (k_003ebo_enter only starts dialog attond on the Dxun
        # approach, 401DXN_STARTED 2 or 4), so a real run has had one entry since slot 3 joined: likely, not
        # certain (the attack on board, which ends the run of scenes with a_next_scene|1, may take it)
        "CUT_G0T0_REMOTE_1": (True, False, "slots 3 and 1 available and 003EBO_G0t0_Remote 0: the first entry after "
                                           "slot 3 joins; its dialog g0t0rem1 opens with E3 (a_global_set 1)"),
        "003EBO_G0t0_Remote": (1, False, "dialog g0t0rem1 E3 (003ebo), the scene CUT_G0T0_REMOTE_1 plays. Its second "
                                         "scene (CUT_G0T0_REMOTE_2) waits for 000_Jedi_Found above 2 and is left to "
                                         "the game"),
        "CUT_BAO_G0T0_1": (True, False, "slots 1 and 3 available: plays after g0t0rem1 on the same entry when that "
                                        "dialog ends with a_next_scene|0 (R5), else on the next entry"),
        "003EBO_G0T0_BAO_2": (1, False, "the table sets 1 with CUT_BAO_G0T0_1; k_003ebo_enter raises it to 2 on the "
                                        "next entry, which plays CUT_BAO_G0T0_2 (dialog bao_g0_2: a_adj_dex|1 on slot "
                                        "3). That scene is left to the game, as the editor cannot raise slot 3's "
                                        "dexterity"),
        "411DXN_Complete": (None, False, "set in the tomb (a_leave_411), which is the Onderon chapter's; while it is "
                                         "0, a_to_iziz2 flies to 501ond and a_to_iziz recruits slot 2"),
        "500OND_Civil_War": (None, False, "set on the return to the camp (dialog kelborn E15), in the Onderon chapter"),
        "403DXN_Return_Trigger": (None, False, "set when the party comes back from Iziz (a_set_return, mand_cs2 E0), "
                                               "in the Onderon chapter"),
    },
    "party_recruit": [
        (2, "p_mand", "a_to_iziz|0,0,0,0,0,", "403dxn", True,
         "joins after the attack on the camp, right before the shuttle to Iziz (dialog sith_att R12). If he has "
         "not, k_501_enter adds the same template on the first entry of 501ond (501OND_Mand_Join 0)"),
    ],
    "next": {"from": ("403dxn", "a_to_iziz2|0,0,0,0,0,"), "target": "501ond",
             "note": "the camp's shuttle to Iziz: a_to_iziz2 plays OndMov05 (PlayMovie) and starts 501OND at "
                     "From_403DXN, where the Onderon chapter begins"},
    "xp": {
        "modules": ["421dxn", "401dxn", "402dxn", "403dxn", "404dxn"],
        "maybe": False,
        "extra": [],
        "endings": {"missingm": 70, "battle_circle": 90},
    },
}
