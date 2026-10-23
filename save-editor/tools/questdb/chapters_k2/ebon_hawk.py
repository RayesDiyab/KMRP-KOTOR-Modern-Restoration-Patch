"""KotOR 2, the Ebon Hawk between planets (003ebo, 004ebo, 007ebo): a side chapter.

Curated 2026-10-23 from the game's scripts and conversations (tools/questdb/ncsvm.py and the
research helpers in the session's k2kit). IDs only: no names or text from the game.

What happens on board, and where each part belongs:
  003ebo  the ship between planets. Its own quests: the droid in the cargo hold rebuilt from
          four parts (RebuildHK47, dialog drdparts), the attack that brings slot 9 on board (dialog visasmarr, started
          by the alignment movie k_align_movie), and the party's own scenes, scheduled one at
          a time by k_003ebo_enter / a_next_scene (CUT_* flags, 003EBO_* counters).
          It also holds other chapters' moments: the first visit after Peragus (003atton and
          003kreia up to the galaxy-map pick of Telos: RecoverEbonHawk 99, RecentHistory,
          GalacticHistory 10 and 90, 003EBO_Atton_Talk, 003EBO_BACKGROUND 1, 003EBO_RETURN_DEST 1,
          000_Astrogation, 106PER_Peragus_End), folded into the Peragus chapter; the Dxun approach
          (attond R12 a_to_421dxn), the Onderon message (ond_rece: foutpost, altroute 10),
          the message for Onderon's palace (t3kelbrn: master_palace), the Korriban approach
          (kor_int: traces 10) and the trip to the end of Nar Shaddaa (attontmp R6 a_load351).
  004ebo  the ship docked at Nar Shaddaa while a gang holds it (entered from 301nar by
          tr_ehawk_custom, left by k_004_heart back to 301nar); LandingRights ends here.
  007ebo  the ship at the end of Nar Shaddaa (entered from 351nar by k_351_miraend, left by
          a_load303 to 303nar): slot 3 joins here (a_select_goto, AddAvailableNPCByObject)
          and the slot 7 / slot 10 farewell dialogs (miraend, miraend2, hanend) play.
  004ebo and 007ebo belong to Nar Shaddaa's story; build.py lists them here.

Influence (a KotOR 2 party value, not yet applied by the editor): PARTYTABLE.res
PT_INFLUENCE, one PT_NPC_INFLUENCE per slot, 0 to 100 (src/save.rs). Conversations change it
through scripts.bif a_influence_inc / a_influence_dec (parameter 1 = slot; ModifyInfluence by
+8 / -8 whatever parameter 2 says: the three levels are all 8 in the shipped script) and
a_setinfluence (ModifyInfluence by parameter 2); c_influence_gt / lt / eq / bet test it.
"""
PLANET = "Ebon Hawk"
CHAPTER = {
    "order": 11,
    "side_chapter": True,
    "xp_after": "Korriban",
    "story_position": "the ship's own quests between planets; its XP is counted after Korriban, the last of the "
                      "four free planets in chapter order, by when the droid's four parts (sold or carried on "
                      "Telos, Nar Shaddaa, Onderon and Dantooine) can all be found, the alignment movie has "
                      "brought slot 9 on board and the Nar Shaddaa and Korriban visits on the ship are done",
    "chapter_title": "The Ebon Hawk: the ship's own quests",
    "returnable": True,
    "returnable_note": "003ebo is the ship between planets (004ebo and 007ebo, the Nar Shaddaa scenes on board, "
                       "moved to the Nar Shaddaa chapter in build.py after curation)",
    "credits_fixed": [(-1500, "the droid's chassis (hkpart02, item Cost 1500) has no source but a store: the "
                              "store scripts (a_stockstore in 208tel, a_stock_* on the other planets) stock the "
                              "next missing part while RebuildHK47 is open; at m_chano (208tel, MarkUp 100) it costs "
                              "1500. The other three parts can be found (hkpart04 on a 101per HK-50, hkpart03 on a "
                              "261tel HK-50, hkpart01 on npc_akkere in 601dan)", 5)],
    "critical": [
        ("003ebo", "dialog visasmarr E190", "the attack on board ends: a_visasarrives 9 recruits slot 9"),
        ("003ebo", "a_visasarrives|9,0,0,0,0,", "slot 9 joins (template p_visas)"),
        ("003ebo", "dialog drdparts E13", "the four parts installed: journal RebuildHK47 80"),
        ("003ebo", "a_createhk47|0,0,0,0,0,", "drdparts R10: 000_HK_Alive 1, the droid created from p_hk47"),
        ("003ebo", "dialog hk47 R448", "slot 5 joins: a_addhk47_2 (AddAvailableNPCByObject 5). Named by its line: "
                                       "hk47 is the conversation of the creature a_createhk47 spawns, which the "
                                       "generator's reachability does not follow"),
    ],
    "journal": [
        ("RebuildHK47", 80, "dialog drdparts E13 (003ebo)"),
    ],
    "finals": {
        # the droid in the cargo hold (dialog drdparts, a_hk47jrl, a_createhk47)
        "000_HK_Chassis": (1, True, "drdparts E9 (a_hk_chassis) / E10; only 1 is ever written"),
        "000_HK_Control_C": (1, True, "drdparts E5 / E6; only 1 is ever written"),
        "000_HK_Vocab": (1, True, "drdparts E7 / E8; only 1 is ever written"),
        "000_HK_Processor": (1, True, "drdparts E11 / E12; only 1 is ever written"),
        "000_HK_Total_Parts": (4, True, "a_global_inc on drdparts R5 to R8, once per part; E13 needs 4"),
        "000_HK_Alive": (1, True, "a_createhk47 (drdparts R10); hk47 starts at E384 while it is 1"),
        # slot 9's arrival
        "003EBO_VISAS_ARRIVES": (False, True, "set TRUE by the alignment movie (k_align_movie, scripts.bif); "
                                              "k_003ebo_enter sets it FALSE when the attack starts"),
        "000_Event_Movie": (1, True, "k_align_movie (scripts.bif, read from its disassembly), its only writer, sets 1 "
                                     "when it plays the movie that sends slot 9: while it is 0, at an alignment of "
                                     "75 and above or 25 and below, and in any case once 000_Jedi_Found reaches 3, "
                                     "so every run sees it; at 0 the movie (and the attack) would come again"),
        "GBL_MAIN_SITH_LORD": (2, True, "k_align_movie sets 2 with the movie (5 only when GBL_GAME_COMPLETE > 2, "
                                        "which a first run never has). Later writers: dialog atrend3 E0 / E1 (262tel, "
                                        "The Jedi Masters) set 3 or 4, so this side chapter must not be applied to a "
                                        "save past that point"),
        "003_IN_COMBAT": (0, True, "k_003ebo_enter sets 1 for the attack; k_visas_damage sets 0 when slot 9 "
                                   "is beaten; at 1 the exit (tr_leave_ehawk) skips party selection"),
        "003EBO_CLEANUP_VISAS": (False, True, "the cutscene table sets TRUE when the attack starts (scene VISAS "
                                              "ARRIVES); a_next_scene|1 (003atton R115, the aftermath scene) clears it, "
                                              "and the flag only steers that clean-up, so a finished arrival leaves "
                                              "FALSE"),
        "VISAS_ARRIVES_CONV": (False, False, "set TRUE by a_next_scene's party spawn after the attack and FALSE by "
                                             "visasmarr E171 (a_glob_bool_set 0); whether every run reaches E171 was "
                                             "not worked out"),
    },
    "party_recruit": [
        (9, "p_visas", "a_visasarrives|9,0,0,0,0,", "003ebo", True,
         "joins after the attack on board (dialog visasmarr E190); the attack comes after the alignment movie "
         "(k_align_movie), which every run sees once the alignment leaves the middle"),
        (5, "p_hk47", "a_addhk47_2|0,0,0,0,0,", "003ebo", False,
         "optional side quest: after the four parts (drdparts E13) a_createhk47 creates the droid from template "
         "p_hk47 and dialog hk47 R448 adds that object (AddAvailableNPCByObject 5, not ByTemplate)"),
    ],
    "next": {"fixed": {"module": "003ebo", "waypoint": "", "movies": [],
                       "by": None, "in": "003ebo",
                       "note": "the chapter happens on board; the party stays on the ship (module.ifo entry point)"}},
    "xp": {
        "modules": ["003ebo"],
        "maybe": False,
        "extra": [],
        "endings": {"rebuildhk47": 80},
    },
}
