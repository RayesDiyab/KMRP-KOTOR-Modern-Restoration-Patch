"""KotOR 2, Peragus: the prologue on the ship, the mining facility, the Harbinger and the escape.

Curated 2026-10-23 from the game's scripts and dialogs (German Steam release, no mods), read with
the research helpers (scanmod, showscript, dlgnode), and checked against the maintainer's own
save "000001 - AUTOSAVE" (201TEL, early Telos; the prologue was skipped in that run, so its
tutorial quests are not in its journal). A value seen in that save says so in its note.

IDs only: no names or text taken from the game (KMRP rule, 2026-10-23).

The story order: 001ebo / 002ebo (the prologue, played as slot 8; the game offers to skip it),
101per, 102per, 103per, 104per (outside), 105per, 101per again, the Harbinger (151har, 152har,
153har; 154har is a copy of 151har that no door, trigger or script leads to), back through
103per to the hangar 106per, the ship in the hangar under attack (107per, with 005ebo when the
boarders get on board), then 003ebo: the escape scene on the ship (Peragus is destroyed), the
conversations that open the galaxy map, and the choice of Telos. The chapter ends there; the
ship's ramp then leads to 201tel.

Party: the companions join by object (AddAvailableNPCByObject on the placed creature), not by
template. The milestone names the game's own templates for the same slots (p_kreia, p_atton,
p_t3m4 in templates.bif), which Telos itself recruits by template (203tel, 208tel, 209tel).
"""
PLANET = "Peragus"
CHAPTER = {
    "order": 1,
    "chapter_title": "Peragus: the mining facility, the Harbinger and the escape",
    "returnable": False,
    "returnable_note": "Peragus is destroyed in the escape (003atton E14 sets 106PER_Peragus_End); the galaxy map "
                       "never offers it again (k_sup_galaxymap: planet 8 only posts an error). The prologue "
                       "modules (001ebo, 002ebo), the Harbinger and 005ebo are one-time scenes",
    "critical": [
        ("001ebo", "a_bet3m4", "prologue OnEnter: slot 8 by template p_t3m4 (played as slot 8), "
                               "000_PLAYER_GENDER from the player"),
        ("001ebo", "a_end_001|0,0,0,0,0,", "end of the prologue (dialog outro R5; intro R1 / R21 skip it with "
                                           "parameter 1): slots 7 and 8 removed, tutorial stages closed, "
                                           "StartNewModule 101PER"),
        ("101per", "a_addkreia|0,0,0,0,0,", "slot 6 joins by object (tag kreia), dialog 101kreia R108 / R111: "
                                            "101PER_Kreia_Joined"),
        ("101per", "a_addatton|0,0,0,0,0,", "slot 0 joins by object (tag atton), dialog hk50 R19: "
                                            "101PER_Atton_Joined"),
        ("101per", "a_106perjump|0,0,0,0,0,", "slot 8 joins by object (tag t3m4), dialog 101t3m4 R7: "
                                              "PER_TURNINTO_T3M4, the section played as slot 8 in 106per"),
        ("103per", "a_addt3m4sp|0,0,0,0,0,", "slot 8 into the active party, dialog 103atton R6"),
        ("103per", "dialog 103atton R6", "journal RescueT3 99"),
        ("103per", "dialog fuelcon E5", "journal RescuePC 99"),
        ("103per", "dialog voice R2", "journal VoiceprintProtocol 99 (the assembled voice print)"),
        ("104per", "a_setsion", "trigger SionArrives: 101PER_Sion_Arrives"),
        ("105per", "a_suitrestrict", "back inside: G_PER_IN_SPACE_SUIT FALSE"),
        ("105per", "dialog turbocon E11", "journal TurboliftLockdown 99 (the code accepted)"),
        ("151har", "dialog navcom E11", "journal OrbitalDriftCharts 99"),
        ("153har", "a_sion_cut|10,0,0,0,0,", "dialog 153sion E3: slot 6 leaves the active party "
                                             "(RemovePartyMember 6; she stays available)"),
        ("106per", "a_transformt3m4", "106per OnEnter: PER_TURNINTO_T3M4 FALSE"),
        ("106per", "dialog ebonhawk E2", "journal RecentHistory 99"),
        ("106per", "a_load003ebo|0,0,0,0,0,", "boarding the ship (dialog ebonhawk R1): 003EBO_BACKGROUND 0, "
                                              "StartNewModule 107PER"),
        ("107per", "a_hangar_timer", "the hangar defence ends: 107PER_MG_FINISHED, dialog turend"),
        ("107per", "a_leave_107per|0,0,0,0,0,", "dialog turend R4: 003EBO_BACKGROUND 8, movie permov05, "
                                                "StartNewModule 003EBO"),
        ("003ebo", "dialog 003atton R16", "the escape, light side: the player refuses to fire on the asteroids "
                                          "(a_givelight); E13 plays permov06. The dark choice R20 leads to E14 "
                                          "(a_setperend: 106PER_Peragus_End 1) and permov07"),
        ("003ebo", "dialog 003atton E39", "journal RecoverEbonHawk 99"),
        ("003ebo", "dialog 003kreia E53", "journal GalacticHistory 90"),
        ("003ebo", "dialog 003atton E79", "003EBO_Atton_Talk 5: the galaxy map opens (a_galaxymap needs more "
                                          "than 4)"),
    ],
    "grants": [
        {"feat": 205, "note": "a_addforcechain in dialog 101kreia E70 (101per): GrantFeat FORCE_CHAIN"},
    ],
    "journal": [
        ("RecoverEbonHawk", 99, "dialog 003atton E39 (003ebo, the first scene after the escape)"),
        ("GalacticHistory", 90, "dialog 003kreia E53 (003ebo); seen in the AUTOSAVE save"),
        ("RecentHistory", 99, "dialog ebonhawk E2 (106per), or a_recenthisquest in 003ebo when the stage is past "
                              "59 (152har droid2 E0 sets 60); E1 sets 90 instead, which the AUTOSAVE save holds"),
        ("RescuePC", 99, "dialog fuelcon E5 (103per); seen in the AUTOSAVE save"),
        ("RescueT3", 99, "dialog 103atton E0 / R6 (103per); seen in the AUTOSAVE save"),
        ("VoiceprintProtocol", 99, "dialog voice R2 (103per): the full run assembles the voice print; destroying "
                                   "the console (drocon R1) ends at 90, which the AUTOSAVE save holds"),
        ("TurboliftLockdown", 99, "dialog turbocon E11 / E15 (105per): the code accepted; destroying the "
                                  "turbolift (destroytu E0) ends at 98, which the AUTOSAVE save holds"),
        ("OrbitalDriftCharts", 99, "dialog navcom E11 (151har); seen in the AUTOSAVE save"),
        ("MedBayMur", 99, "dialog hk50 R56 (101per): the side quest's full ending (R42 gives 90, R55 95)"),
        ("pazaak_rules", 90, "dialog atton E276 (102per / 106per); seen in the AUTOSAVE save"),
        ("pazaak_rules2", 90, "dialog atton R305 (102per / 106per); seen in the AUTOSAVE save"),
    ],
    "finals": {
        # read after Peragus
        "106PER_Peragus_End": (0, True, "light side: only a_setperend in dialog 003atton E14 sets it (1), and E14 "
                                        "follows the dark choice R20; the light choice R16 leaves it 0. 201tel "
                                        "c_perend and 262tel c_chk106perend read it. The Game2 save (a light run) "
                                        "holds 0, the AUTOSAVE and Game3 saves (a dark-leaning run) hold 1"),
        "003EBO_BACKGROUND": (1, True, "k_sup_galaxymap sets 1 when Telos (planet 10) is picked on the galaxy map "
                                       "after the escape (it also queues movie TelMov01); a_galaxymap offers no other "
                                       "planet before 262TEL_Escape_Telos (Peragus, row 8, is shown but not "
                                       "selectable), so every run picks Telos. Seen in all three saves past Peragus"),
        "003EBO_RETURN_DEST": (1, True, "k_sup_galaxymap sets 1 with Telos; check_party_gui (the ship's exit) "
                                        "then sends the party to 201TEL WP_from_ebonhawk. Seen in all three saves "
                                        "past Peragus"),
        "003EBO_Atton_Talk": (5, False, "dialog 003atton E79 sets 5 after the conversation with slot 6 (003kreia "
                                        "E94 sets 4); a_galaxymap opens the map only above 4, so 5 is the lowest "
                                        "value that lets the story go on. A reply on the ship (003atton E92 > R144, "
                                        "offered while it is below 6) sets 6, and the saves hold 6 (Game2) or 7 "
                                        "(AUTOSAVE, Game3) on Telos. Only the cutscene table (0, 1, 2), a_galaxymap "
                                        "(above 4) and 003atton's own links (below 5, below 6) read it"),
        "000_Astrogation": (None, False, "a player's choice: a_setastrogation runs only on dialog 003atton E112, "
                                         "which two replies lead to; the Game2 run never set it (0 on Telos), the "
                                         "AUTOSAVE run did (1). Only chitin t3m4's links (c_chkastrogation) read it. "
                                         "Left unchanged"),
        "G_PER_In_Space_Suit": (False, True, "104per sets TRUE outside, 105per's a_suitrestrict sets FALSE back "
                                             "inside; 304nar a_gas_dmg and 305nar a_poison read it, so it must "
                                             "end FALSE"),
        "PER_TURNINTO_T3M4": (False, True, "TRUE only for the section played as slot 8; a_transformt3m4 (106per) "
                                           "and a_hatchopen (101per) set it back to FALSE"),
        "101PER_Open_Hatch": (1, True, "a_sethatch in dialog 101atton E42 (101per): the conversation after the "
                                       "section played as slot 8 (starts E37 / E53, c_chkt3end2*) runs through its "
                                       "empty replies R61 to R63 into E42 on every path; 101per's and 105per's "
                                       "c_chkhatch read it. Seen at 1 in both runs' saves"),
        "101PER_Revan_End": (None, False, "the player's answer to slot 0 in 101atton: R116 (a_setrevanevil) sets "
                                          "1, otherwise 0 stays (the light-side ending of the first game). Read by "
                                          "003ebo a_createk1cnpcs, 201tel a_spawn_admiral / a_del_admiral, 222tel "
                                          "a_mandalore and others. A choice, not a side: left unchanged"),
        "101PER_Revan_Sex": (None, False, "the player's answer in 101atton: R115 (a_setrevanfem) sets 1, R121 sets "
                                          "0; read by 003ebo a_createk1cnpcs. A choice: left unchanged"),
        "101PER_Republic_ID": (None, False, "a choice in dialog admoff (101per): R11 (a_settelmsg1) sets it, R0 sets "
                                            "101PER_Republic_Jedi instead; 201tel and 202tel c_chkshipid read it. "
                                            "Left unchanged (0 in the AUTOSAVE save)"),
        "101PER_Switch": (None, False, "a choice: secoff R1 sets 1, admlog R2 (a_neuter_droid 2) sets 2, 102per "
                                       "shfcon E30 sets 0; 201tel c_chkswitch reads it. Left unchanged (2 in the "
                                       "AUTOSAVE save)"),
        "000_PLAYER_GENDER": (None, False, "set from the player's own gender by a_bet3m4 (001ebo) and a_hatchopen "
                                           "(101per); any save past the first module already holds it"),
        # the chapter's own state
        "101PER_Kreia_Joined": (1, True, "a_addkreia (101kreia R108 / R111); seen in the AUTOSAVE save"),
        "101PER_Atton_Joined": (1, True, "a_addatton (hk50 R19); seen in the AUTOSAVE save"),
        "101PER_Sion_Arrives": (1, True, "a_setsion on the 104per trigger SionArrives (its only writer, on the way "
                                         "outside); seen at 1 in both runs' saves (Game2 and AUTOSAVE / Game3)"),
        "107PER_MG_FINISHED": (1, True, "a_hangar_timer when the hangar defence ends; seen in the AUTOSAVE save"),
        "001EBO_End": (1, True, "a_end_001 at the end of the prologue, also when the prologue is skipped (intro R1 / "
                                "R21 run it with parameter 1); seen at 1 in every save, the Game1 save in 101per "
                                "included"),
        "005_FIRST_ENTER": (None, False, "a player's choice: 005ebo is entered only through dialog turend R6 "
                                         "(a_load005ebo, 107per); R4 boards the ship directly. The Game2 run never "
                                         "entered it (0 on Telos), the AUTOSAVE run did. Only k_005_enter reads it. "
                                         "Left unchanged"),
        # the Ebon Hawk's cutscene table (k_003ebo_enter and a_next_scene, 003ebo; the same table in both).
        # Every entry of 003ebo that is not a load from a save (and not the Dxun approach, 401DXN_STARTED 2 or 4)
        # plays the first scene whose test holds and sets its CUT_ flag; each scene's conversation ends with
        # a_next_scene, parameter 0 picking the next scene at once and parameter 1 ending the run of scenes
        # until the next entry. The first two are the escape conversations of this chapter
        "CUT_FIRST_ATTON": (True, True, "the table's first scene: slots 8, 0 and 6 available and 003EBO_Atton_Talk 0, "
                                        "i.e. the first entry after the escape. Seen at 1 in all three saves past "
                                        "Peragus"),
        "CUT_SECOND_ATTON": (True, True, "CUT_FIRST_ATTON set, slots 8, 0, 6 available, 262TEL_CNPC_Freed 0 and "
                                         "003EBO_Atton_Talk 1 or 2, which only this chapter's conversations on the "
                                         "ship leave. Seen at 1 in all three saves past Peragus"),
    },
    "party_recruit": [
        (6, "p_kreia", "a_addkreia|0,0,0,0,0,", "101per", True,
         "joins in 101per by object (AddAvailableNPCByObject on tag kreia, placed template p_kreia001); leaves the "
         "active party on the Harbinger (153har a_sion_cut, RemovePartyMember) but stays available; 107per "
         "spawns her again (SpawnAvailableNPC 6). In the party at 201tel in the AUTOSAVE save"),
        (0, "p_atton", "a_addatton|0,0,0,0,0,", "101per", True,
         "joins in 101per by object (AddAvailableNPCByObject on tag atton). In the party at 201tel in the "
         "AUTOSAVE save"),
        (8, "p_t3m4", "a_106perjump|0,0,0,0,0,", "101per", True,
         "available from 101per by object (AddAvailableNPCByObject on tag t3m4, placed template p_t3m005), in "
         "the active party from 103per (a_addt3m4sp); the prologue's own slot 8 (p_t3m4 by template) is removed "
         "by a_end_001. Available at 201tel in the AUTOSAVE save"),
    ],
    "party_remove": [
        (7, "a_end_001|0,0,0,0,0,", "001ebo", True,
         "slot 7 holds the prologue's utility droid (a_3cfd_end, by object tag 3CFD); a_end_001 removes it "
         "(RemoveAvailableNPC 7) before Peragus"),
    ],
    "items": [
        ("comlink", 1, "a_give_item|0,0,0,0,0,comlink", "101per", "dialog 101atton R79"),
    ],
    "dark": {
        "note": "the dark-side run gives the order to fire in the escape scene (dialog 003atton R20, a_setrumble "
                "then E14 a_setperend): 106PER_Peragus_End 1, which Telos reads. Party, journal and route are the "
                "same on both sides",
        "finals": {
            "106PER_Peragus_End": (1, True, "a_setperend|1 in dialog 003atton E14 (003ebo), which follows only the "
                                            "dark choice R20; seen in the AUTOSAVE and Game3 saves"),
        },
    },
    "next": {"fixed": {"module": "201tel", "waypoint": "WP_from_ebonhawk", "movies": ["TelMov01"],
                       "by": None, "in": "003ebo",
                       "note": "after the escape the party is on the ship (107per a_leave_107per: movie permov05, "
                               "StartNewModule 003EBO). The conversations of 003atton and 003kreia open the galaxy "
                               "map (a_galaxymap); picking Telos runs k_sup_galaxymap (003EBO_RETURN_DEST 1, "
                               "003EBO_BACKGROUND 1, movie TelMov01), and the ship's exit, check_party_gui, then "
                               "calls StartNewModule(201TEL, WP_from_ebonhawk). 201tel's first entry "
                               "(k_201tel_enter, 201_FIRST_ENTER) starts the Telos chapter"}},
    "xp": {
        "modules": ["001ebo", "002ebo", "101per", "102per", "103per", "104per", "105per", "151har", "152har",
                    "153har", "106per", "107per", "005ebo"],
        "maybe": False,
        "extra": [
            # RecoverEbonHawk 99 is set in 003ebo (dialog 003atton E39), outside the chapter's modules, so the
            # quest database has no step for it; its journal XP (global.jrl) is counted here
            {"after": "005ebo", "position": "after_quests", "step": {
                "do": "plot_xp", "xp": 1000, "what": "RecoverEbonHawk stage 99: journal 1000 (003ebo, dialog "
                                                     "003atton E39)"}},
        ],
        "endings": {"tutorial_garage": 90, "tutorial_heal_pc": 90, "tutorial_3CFD": 90, "tutorial_fix_ebo": 90,
                    "RescueT3": 99, "RescuePC": 99, "RecentHistory": 99, "VoiceprintProtocol": 99,
                    "TurboliftLockdown": 99, "MedBayMur": 99, "OrbitalDriftCharts": 99},
    },
}
