"""KotOR 2, Nar Shaddaa (301nar-306nar, the yacht 351nar, 352nar, the swoop track 371nar).

Curated 2026-10-23 from the game's scripts and conversations (scanmod.py, showscript.py,
dlgnode.py over the German Steam release); no save of this chapter was available, so every
value comes from reading the files, not from play.

The story, by module: the party lands on the refugee landing pad (301nar) and must win the
landing pad back from the crew in the ship (004ebo, LandingRights) and change the ship's ID
signature (EbonHawkIDSignature: tag gotoyach E3 refuses to leave Nar Shaddaa before stage
40). Once the Exchange has noticed the player (300NAR_Exchange_Gap >= 8) k_301_heartbeat
starts the call (300NAR_Visquis_Call). The bounty hunters' attack (a_azantiattk) wakes the
player at slot 7's flat (light) or slot 10's place (303NAR_Hanharr_Side 1, dark); slot 7 joins
there (miraapt R82) and the meeting in 304nar ends in the hideout of the master of this planet
(tag zezkaiel, template npc_vrook002; first talk zezkaiel E128-E129, lostjedi 40). The rescue
in 305nar ends with slot 7 or slot 10 winning (305han2 R25 / R28). On the landing pad the
yacht takes the ship (gotoyach R23, two companions picked in 351NAR_Party1/2); the yacht
(351nar) ends at trigger 351_MiraEnd_Dlg (k_351_miraend: movie NarMov07, StartNewModule 007EBO).
On the ship (007ebo, the Ebon Hawk chapter's module) slot 7 or slot 10 talks (miraend2 /
hanend), slot 3 joins (dialog g0t0 E234, a_select_goto) and a_load303 sends the party back to
the docks (303nar FROM_305NAR), where the master's second talk (zezkaiel E2 ... E145) counts
him found (000_Jedi_Found + 1) and sets lostjedi 45. The chapter ends when the party boards
the ship on the landing pad (tr_ehawk_custom, 301nar).

352nar is an older copy of the yacht that only test conversations (attontmp) load; a run
never enters it. IDs only: no names or text taken from the game (KMRP rule, 2026-10-23).
"""

# The masters' count several planets share. Recorded here for the editor; milestone.py does not
# copy this key and the editor does not read it (see the report of 2026-10-23): the editor's
# star_map rule counts BOOLEAN planet flags, and no planet sets a boolean when its master is
# found, so the counter cannot be worked out by that rule as it stands.
JEDI_FOUND_RULE = {
    "counter": "000_Jedi_Found",
    "base": 0,
    "per_planet": 1,
    "rule": "000_Jedi_Found = number of the four masters found (Nar Shaddaa, Onderon, Dantooine, Korriban)",
    "writers": [
        "303nar zezkaiel.dlg E2 and E113 (a_global_inc|1,0,0,0,0,000_Jedi_Found): this chapter",
        "506ond kavar.dlg, 602dan vrook.dlg, 702kor tr_vash: the other three planets",
        "301nar a_setup_cs (parameters 12 and 17) sets 3: a debug script, no run reaches it",
    ],
    "readers": [
        "k_sup_galaxymap (chitin): at the next take-off, >= 1 (and < 4) plays a 262TEL scene "
        "(000_Atriscs1 = 2), >= 2 plays another (000_Siscut1 = 2)",
        "kreia.dlg starts E603 / E605: == 4 (E605 also needs 000_Last_Jedi_Kill > 0), journal lostjedi 80 / 85, "
        "the call to Dantooine (650dan)",
        "003ebo k_003ebo_enter, a_next_scene, c_kelborn_mes; 262tel k_262_enter, a_atrend3, tr_atrend3, "
        "a_setup_ebo; 403dxn a_set_return; 605dan k_enter_605; 650dan 650jedi.dlg; disciple.dlg; "
        "a_item_gen / c_item_gen; k_align_movie",
    ],
    "planet_found_by": {
        "Nar Shaddaa": "journal lostjedi 45 (or 43 when killed); no global of its own except 000_ZezKaiEll_Dead "
                       "(killed only)",
    },
}

PLANET = "Nar Shaddaa"
CHAPTER = {
    "order": 3,
    "chapter_title": "Nar Shaddaa: the Exchange, the yacht and the hidden master",
    "returnable": True,
    "return_modules": {"351nar": False, "352nar": False, "004ebo": False, "007ebo": False},
    "returnable_note": "the planet stays on the galaxy map; the yacht (351nar) is destroyed when the chapter ends "
                       "(movie NarMov07), and 352nar is a test copy of the yacht no run enters",
    "credits_fixed": [],
    "credits_note": "no payment is unavoidable: the landing fee (a_quello_payment, dialog quello E10) can be talked "
                    "away (quello E16 / E23 set LandingRights 10 without paying), and the other payments belong to "
                    "side quests",
    "critical": [
        ("004ebo", "dialog cahhmakt R14", "the crew in the ship is talked off the ship: LandingRights 91 (light; the "
                                          "fight ends in k_releader_death, 301NAR_Red_Eclipse_At 2, stage 90)"),
        ("301nar", "dialog tienn R21", "the ship's ID signature: EbonHawkIDSignature 42 (gotoyach E3 needs > 39)"),
        ("301nar", "k_301_heartbeat", "the Exchange calls: 300NAR_Visquis_Call (needs LandingRights >= 90 and "
                                      "300NAR_Exchange_Gap >= 8), dialog visquis"),
        ("303nar", "dialog miraapt R82", "slot 7 joins (a_fadeto_304: template p_mira), on to 304nar"),
        ("304nar", "dialog visquis R73", "a_load303vis: 304NAR_Visquis_Meet 1, to 303nar FROM_VISQUIS_304NAR"),
        ("303nar", "dialog zezkaiel E129", "the master's first talk: lostjedi 40, 304NAR_Visquis_Meet 2 (R134)"),
        ("305nar", "dialog 305han2 R25", "light: slot 7 wins (a_305switch 0)"),
        ("305nar", "dialog 305kreia R37", "a_load303mira: back to 303nar FROM_305NAR"),
        ("301nar", "dialog gotoyach R23", "a_load351real: the yacht (351nar From_301NAR), movies NarMov05 / 06"),
        ("351nar", "k_351_enter", "the yacht's OnEnter: conversation gotocut1"),
        ("351nar", "k_351_miraend", "trigger 351_MiraEnd_Dlg (needs 351NAR_Ebon_Released): 351NAR_G0T0_Ship 1, "
                                    "movie NarMov07, StartNewModule 007EBO FROM_351NAR"),
        ("007ebo", "dialog miraend2 E0", "light: slot 7 on the ship, 351NAR_G0T0_Ship 1"),
        ("007ebo", "dialog g0t0 E234", "slot 3 joins (a_select_goto: AddAvailableNPCByObject on the placed p_g0t0)"),
        ("007ebo", "dialog g0t0 R208", "a_load303: StartNewModule 303NAR FROM_305NAR"),
        ("303nar", "dialog zezkaiel E2", "the master's second talk: 000_Jedi_Found + 1"),
        ("303nar", "dialog zezkaiel E145", "the master leaves for Dantooine: lostjedi 45"),
    ],
    "journal": [
        ("LandingRights", 90, "k_releader_death (004ebo) or dialog cahhmakt R14 (004ebo, stage 91): the lowest "
                              "stage every run reaches, 91 >= 90"),
        ("EbonHawkIDSignature", 40, "dialog tienn R21 / R22 / R23 / R52 (301nar, stages 40-43) or the TT-32 route "
                                    "(99): gotoyach E3 needs > 39, so 40 is the lowest stage every run reaches"),
        ("LostJedi", 45, "dialog zezkaiel E145 (303nar). A shared tag: Onderon, Dantooine and Korriban set their own "
                         "stages (50-77), so this stage alone does not mark Nar Shaddaa as played"),
        ("LightsaberQuest", 10, "dialog baosaber E11 (003ebo, a_quest_set|10): the Ebon Hawk's first scene after "
                                "Telos (see CUT_BAODUR_LIGHTSABER), on the ship before any of the four planets, so "
                                "every run that has played this chapter holds it"),
    ],
    "finals": {
        "300NAR_Visquis_Call": (True, True, "k_301_heartbeat; tr_ehawk_custom reads it on boarding"),
        "351NAR_Ebon_Released": (1, True, "the yacht's console (a_logout_power / 2 / 3): needed by k_351_miraend"),
        "351NAR_G0T0_Ship": (1, True, "k_351_miraend, gotocut1 E10, 007ebo miraend2 / hanend E0; 303nar's "
                                      "k_303nar_enter and tr_ehawk_custom read it"),
        "303NAR_Hanharr_Side": (0, True, "light side: slot 7's route (305han2 R25); 007ebo k_enter007 reads it to pick "
                                         "miraend2 over hanend. Its writers of 1 are the dark route's replies "
                                         "hanhboun R19 (303nar) and 305han R17 (305nar) and a test node (genodisc R6, "
                                         "the cheat node E4); 305han R16 sets 0"),
        "304NAR_Visquis_Meet": (3, True, "visquis R73 sets 1, zezkaiel R134 sets 2, and dialog visenter, which "
                                         "a_visquisconv starts only at 2, opens with E6 (its first start, c_global_eq "
                                         "2): 3, the way into 305nar. No later writer; a_visleaveconv reads 3"),
        "301NAR_Red_Eclipse_At": (3, False, "dialog cahhmakt E9 (004ebo) sets 3 when the crew is talked off the ship; "
                                            "the fight sets 2 (k_releader_death): the player's choice, either ending "
                                            "LandingRights. The game tests only 1 (tr_ehawk_custom: the crew aboard "
                                            "sends every boarding to 004EBO; k_recspawn) and 0 (k_recspawn1), so 2 and "
                                            "3 behave alike; a value is still needed because a save from before the "
                                            "chapter may hold 1"),
        "003EBO_RETURN_DEST": (3, True, "tr_ehawk_custom sets 3 on every path when the party boards at 301nar"),
        "003EBO_BACKGROUND": (3, True, "tr_ehawk_custom sets 3 on every path when the party boards at 301nar"),
        "301_FIRST_ENTER": (True, True, "k_301_enter (trigger 301Arrival) on landing"),
        "000_Jedi_Found": (None, False, "the masters' count: zezkaiel E2 / E113 add 1. A counter several planets share; "
                                        "see JEDI_FOUND_RULE in this file. Left unchanged here"),
        "000_ZezKaiEll_Dead": (None, False, "set to 1 only when the master is killed (k_zez_death, lostjedi 43); a full "
                                            "run talks to him. Left unchanged"),
        # The Ebon Hawk's cutscene table (k_003ebo_enter / a_next_scene, 003ebo; see peragus.py). Telos ends
        # with the move to 003ebo, whose arrival plays the scenes due after Telos; a skip that ends with Telos
        # lands there and plays them itself, so they belong to the first chapter after Telos. Any skip past
        # Telos either applies this chapter or comes from a save that really played a planet after Telos
        "CUT_BAODUR_LIGHTSABER": (True, True, "the table's third test: slot 1 available and 262TEL_Escape_Telos 1, "
                                              "nothing before it holds on the first entry after Telos (the attack "
                                              "on board needs two planets entered), so it plays on that arrival in "
                                              "every run; its dialog baosaber gives LightsaberQuest 10 (in this "
                                              "chapter's journal)"),
        # not set: CUT_BAO_T3 (slots 1 and 8, 262TEL_Escape_Telos 1), which the same arrival plays after baosaber;
        # its dialog bao_t3 runs a_adj_con|2 on slot 8 (constitution), which the editor cannot apply, so the scene
        # is left to play at the next entry of the ship
    },
    "party_recruit": [
        (7, "p_mira", "a_fadeto_304|0,0,0,0,0,", "303nar", False,
         "light side: joins in her flat (dialog miraapt R82); the dark-side run never recruits her (see dark)"),
        (3, "p_g0t0", "a_select_goto|0,0,0,0,0,", "007ebo", True,
         "joins on the ship after the yacht (dialog g0t0 E234 in 007ebo, the Ebon Hawk chapter's module). The game "
         "calls AddAvailableNPCByObject(3) on the creature placed from template p_g0t0, not "
         "AddAvailableNPCByTemplate, so the generator does not find this call"),
    ],
    "dark": {
        "note": "the dark-side run sides with slot 10's hunters (hanhboun R19: 303NAR_Hanharr_Side 1): the bounty "
                "hunters' attack wakes the player at slot 10's place (a_azantiattk, WP_PC_HAN_JEKK_0), slot 7 never "
                "joins, and in 305nar slot 10 wins (305han2 R28, a_305switch 1): slot 10 joins and slot 7 is removed. "
                "On the ship hanend plays instead of miraend2. The master is still talked to (killing him, R5 / R7 of "
                "zezkaiel, is a separate choice this milestone does not take)",
        "finals": {
            "303NAR_Hanharr_Side": (1, True, "hanhboun R19 (303nar) / 305han R17 (305nar), the replies that take "
                                             "this route; no later writer"),
        },
        "party_recruit": [
            (10, "p_hanharr", "a_305switch|1,0,0,0,0,", "305nar", True, "dialog 305han2 R28: slot 10 joins"),
        ],
        "party_not_recruited": [7],
        "party_remove": [
            (7, "a_305switch|1,0,0,0,0,", "305nar", True, "dialog 305han2 R28: RemoveAvailableNPC(7)"),
        ],
    },
    "next": {"fixed": {"module": "003ebo", "waypoint": "WP_from_outside", "movies": [],
                       "by": "tr_ehawk_custom", "in": "301nar",
                       "note": "the party walks back from the docks (303nar) to the landing pad and boards the ship "
                               "through trigger to_ebonhawk_custom (tr_ehawk_custom: 003EBO while "
                               "301NAR_Red_Eclipse_At is not 1); the galaxy map is on the ship. That arrival plays "
                               "the Ebon Hawk's scenes due once slot 3 has joined (g0t0rem1, bao_g0_1); the chapters "
                               "after this one set them"}},
    "jedi_masters": JEDI_FOUND_RULE,
    "master_met": [{"module": "303nar", "dialog": "zezkaiel", "local": 61}],  # the flag his own conversation sets once he has taught
    "teach_form": True,  # zezkaiel R92 > lrn_form (a_fire_learn|3): one a_give_form; the dark fight gives one too
    "increments": [("000_Jedi_Found", 1, "zezkaiel E2 / E113 (303nar): this planet's master found")],
    "xp": {
        "modules": ["301nar", "004ebo", "302nar", "303nar", "306nar", "371nar", "304nar", "305nar", "351nar", "007ebo"],
        "maybe": False,
        "extra": [],
        "endings": {
            "ebonhawkidsignature": 42,
            "30001": 30,
            "30002": 20,
            "30003": 12,
            "30004": 40,
            "30005": 33,
            "30006": 20,
            "30008": 21,
            "30010": 20,
            "30011": 21,
            "30012": 20,
            "droidwarehousepuzzle": 20,
            "intergru": 50,
            "tradewar": 91,
        },
    },
}
