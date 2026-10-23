"""Curated story state for every chapter of KotOR 1, read by milestone.py.

New file (2026-10-23). Everything here was worked out by reading the game's scripts
(tools/questdb/ncsvm.py, the NSS sources in scripts.bif) and checked, where a save exists,
against the maintainer's own saves: "GalaxyMap" (ebo_m12aa after Dantooine, before take-off,
55480 XP), "Game224" (tat_m17ae after the Tatooine star map), "Game22" (manm26ac after the
Manaan star map) and "Game133" (tar_m08aa, late Taris). A value seen in one of those saves
says so in its note; a value marked certain = True is the only one the game's scripts can
leave at that point of the story.

IDs only: no names or text taken from the game (KMRP rule, 2026-10-23).

Per chapter:
  order, chapter_title, returnable   order in the story, plain title, and whether the
                                     player can come back to the chapter's modules
  return_modules                     per-module exceptions to returnable
  critical                           [(module, script or "dialog <dlg> <node>", what)] in
                                     story order; writers in these scripts count as certain
  journal                            [(tag, stage, set by)] the stages the chapter ends with
  journal_remove                     quest tags the chapter's end removes from the journal
  finals                             {global: (value, certain, note)}; None = leave unchanged
  party_recruit                      [(slot, template, script, module, certain, note)] as the
                                     game's own AddAvailableNPCByTemplate call; an optional
                                     seventh element "male" / "female" limits the recruit to
                                     that player (KotOR 2, added 2026-10-23)
  party_remove                       [(slot, script, module, certain, note)]
  items                              [(resref, count, script, module, note)] held at the end
  star_map                           the star map rule (see STAR_MAP_RULE) for this planet
  jedi_class                         Dantooine only: the class choice the trials end with
  next                               {"from": (module, script)} to follow the game's own
                                     StartNewModule, or {"fixed": {...}} for a door
  increments                         [(global, amount, note)] a number several chapters share,
                                     raised by this one (KotOR 2's 000_Jedi_Found; added
                                     2026-10-23); the editor adds it once per skipped chapter
  teach_form                         True: a Jedi master teaches a form here (KotOR 2's
                                     a_give_form; the editor applies the game's rule)
  grants                             [{"spell" or "feat": row, "side": optional, "note"}]
                                     powers and feats the story grants (KotOR 2)
  credits_side_only                  {dialog: "light" / "dark"} conversations only a run of
                                     that side has, for credits.py (added 2026-10-23)
  credits_fixed                      [(credits, note, slot)] payments the main path cannot avoid;
                                     slot (optional): the companion the purchase brings, so a
                                     save that has them already is not charged again
                                     (added 2026-10-23), added to credits.py's totals
  dark                               what a dark-side run ends with instead (added
                                     2026-10-23): journal, finals, party_recruit,
                                     party_not_recruited (slots of the light run that never
                                     join), party_remove, next; the editor applies it when the
                                     player picks the dark side. Chapters without it end the
                                     same on both sides (alignment and credits aside, which
                                     credits.py works out)
"""

# The four star maps after Dantooine all run UT_StarMap1VariableSet (k_inc_utility, chitin
# scripts.bif) or a module copy of it. K_STAR_MAP is a counter, so a milestone cannot hold
# its value without knowing which other planets were done; the rule says how to work it out.
STAR_MAP_RULE = {
    "counter": "K_STAR_MAP",
    "base": 10,
    "base_note": "Dantooine's map sets K_STAR_MAP to 10 (k_pdan_starmap02, danm15)",
    "per_planet": 10,
    "planet_flags": ["K_STAR_MAP_TATOOINE", "K_STAR_MAP_KASHYYYK", "K_STAR_MAP_MANAAN", "K_STAR_MAP_KORRIBAN"],
    "rule": "K_STAR_MAP = 10 + 10 for each planet flag that is TRUE after this milestone's own flag is set",
    "on_count": [
        {"count": 30, "set": [{"name": "K_SWG_BASTILA", "value": 99, "only_if_below": 3}]},
        {"count": 40, "set": [{"name": "K_CAPTURED_LEV", "value": 5},
                              {"name": "K_SWG_BASTILA", "value": 99, "only_if_below": 5}],
         "note": "K_CAPTURED_LEV 5 makes the next take-off from the galaxy map (k_sup_galaxymap: K_STAR_MAP "
                 "== 40 and K_CAPTURED_LEV == 5) play the Leviathan capture"},
        {"count": 50, "set": [{"name": "K_KOTOR_MASTER", "value": 30}],
         "journal": ["k_starforge", 50],
         "note": "K_KOTOR_MASTER 30 opens the Unknown World on the galaxy map"},
    ],
    "journal_note": "each map also sets k_starforge to its own stage with bAllowOverrideHigher = TRUE "
                    "(10 Korriban, 20 Tatooine, 30 Kashyyyk, 40 Manaan), so the game's stage is the last map "
                    "found; the editor only raises a stage, which differs only in the journal text shown",
    "source": "UT_StarMap1VariableSet and UT_SetStarmapJournal in k_inc_utility",
}

CHAPTERS = {
    ("K1", "Endar Spire"): {
        "order": 1,
        "chapter_title": "The Endar Spire: escaping the ship in an escape pod",
        "returnable": False,
    },

    # ------------------------------------------------------------------ Taris
    ("K1", "Taris"): {
        "order": 2,
        "chapter_title": "The end of Taris: escaping on the Ebon Hawk",
        "credits_fixed": [(-2000, "the droid purchase in tar_m02ab (k_act_cred2000 in tar02_janice021; slot 7 "
                                  "joins after it), which credits.py, avoiding payments, leaves out", 7)],
        "returnable": False,
        "returnable_note": "the planet is destroyed when the chapter ends (Tar_Destroyed); its modules are never "
                           "loaded again",
        "critical": [
            ("tar_m02af", "k_ptar_addcarth", "slot 2 joins (template p_carth) in the hideout"),
            ("tar_m02ab", "k_ptar_addt3m4", "slot 7 joins (template p_t3m4) after the droid purchase"),
            ("tar_m04aa", "k_ptar_addmissio", "slot 6 joins (template p_mission) in the lower city"),
            ("tar_m05aa", "k_ptar_addzaal", "slot 8 joins (template p_zaalbar) in the sewers"),
            ("tar_m03af", "k_ptar_bastpart", "slot 0 joins (template p_bastilla) after the swoop race"),
            ("tar_m02ae", "k_ptar_davikest", "slot 1 joins (template p_cand), party selection, on to stunt_03a"),
            ("tar_m08aa", "k_ptar_davatk_en", "the estate: K_KOTOR_MASTER = 10"),
            ("tar_m08aa", "k_ptar_tarisover", "after the hangar fight: Tar_Destroyed, journal, plot XP, StartNewModule "
                                              "STUNT_06 with movie 05"),
        ],
        "journal": [
            ("tar_escape", 99, "k_ptar_tarisover (tar_m08aa)"),
            ("tar_planetinfo", 99, "k_ptar_tarisover (tar_m08aa)"),
        ],
        "journal_remove": ["tar_party", "k_rapidtransit", "tar_rancor", "end_attack", "tar_bendakbounty",
                           "tar_diabounty", "tar_infectedoutcasts", "tar_vulkarbase", "tar_largobounty", "tar_matrik",
                           "tar_rakghoulserum", "tar_rukilapprentice", "tar_selvenbounty", "tar_duelring",
                           "tar_promisedland", "tar_bastsearch", "tar_buydroid"],
        "journal_remove_note": "k_ptar_tarisover removes these when Taris ends (RemoveJournalQuestEntry); it is the "
                               "game's own clean-up, so the journal after Taris holds only tar_escape and "
                               "tar_planetinfo of the Taris quests",
        "finals": {
            "Tar_Destroyed": (True, True, "set by k_ptar_tarisover at the end of Taris; party banter reads it "
                                          "(k_hmis_tardest, k_swg_bastila01/02)"),
            "K_CURRENT_PLANET": (15, True, "k_ptar_tarisover sets 15 (Dantooine) before the escape; the galaxy map "
                                           "and the Dantooine landing read it"),
            "K_KOTOR_MASTER": (10, True, "k_ptar_davatk_en sets 10 on entering the estate; the galaxy map "
                                         "(k_pebn_galaxy) then offers Dantooine only"),
            "TAR_MILBASE": (1, False, "k_ptar_ssmilbase, the Sith base on the main path; read later by a random "
                                      "line in unk_m44aa"),
            "TAR_SWOOPRACE": (1, False, "the swoop race on the main path (k_ptar_postrace, k_ptar_winrace); read "
                                        "later by a random line in unk_m44aa"),
            "K_TAR_SWOOP_POINT_01": (True, False, "area-visited flags the ship's swoop/transit list reads "
                                                  "(k_pebn_ctaris*); set on first entry of upper city areas"),
            "K_TAR_SWOOP_POINT_02": (True, False, "as K_TAR_SWOOP_POINT_01"),
            "K_TAR_SWOOP_POINT_05": (True, False, "as K_TAR_SWOOP_POINT_01 (lower city)"),
            "K_TAR_SWOOP_POINT_06": (True, False, "as K_TAR_SWOOP_POINT_01 (lower city)"),
        },
        "party_recruit": [
            (2, "p_carth", "k_ptar_addcarth", "tar_m02af", True, "joins in the hideout at the start of Taris"),
            (7, "p_t3m4", "k_ptar_addt3m4", "tar_m02ab", True, "joins after the droid purchase (main path: needed "
                                                                   "for the Sith base)"),
            (6, "p_mission", "k_ptar_addmissio", "tar_m04aa", True, "joins in the lower city"),
            (8, "p_zaalbar", "k_ptar_addzaal", "tar_m05aa", True, "joins in the sewers"),
            (0, "p_bastilla", "k_ptar_bastpart", "tar_m03af", True, "joins after the swoop race"),
            (1, "p_cand", "k_ptar_davikest", "tar_m02ae", True, "joins before the estate (the tar_m02aa copy of "
                                                                   "k_ptar_davikest names p_canderous, which does "
                                                                   "not exist; that copy is never used)"),
        ],
        "next": {"from": ("tar_m08aa", "k_ptar_tarisover")},
    },

    # ------------------------------------------------------------------ Dantooine
    ("K1", "Dantooine"): {
        "order": 3,
        "chapter_title": "Dantooine: becoming a Jedi and finding the first star map",
        "returnable": True,
        "returnable_note": "the player can fly back to Dantooine until the Leviathan (K_KOTOR_MASTER 20 makes it "
                           "unselectable on the galaxy map)",
        "critical": [
            ("danm13", "k_pdan_13_area", "the enclave OnEnter on arrival"),
            ("danm13", "k_pdan_zhar03", "the trials begin: Jedi robe g_a_jedirobe01 to the player"),
            ("danm13", "k_pdan_saber08", "the trials pick DAN_PATH_STATE 1, 2 or 3 from the answers"),
            ("danm13", "k_pdan_makejedi", "AddMultiClass by DAN_PATH_STATE (1 = 3, 2 = 5, 3 = 4), XP to the next "
                                          "level"),
            ("danm13", "k_pdan_saber16", "the lightsaber by DAN_PATH_STATE (g_w_lghtsbr01, 04, 03)"),
            ("danm14ac", "k_pdan_14juh_d", "the grove: DAN_JEDI_PLOT 4, DAN_JUHANI_PLOT 2"),
            ("danm13", "k_pdan_zhar_d", "DAN_JEDI_PLOT 7"),
            ("danm13", "k_pdan_vandar02", "slot 5 joins (template p_juhani), DAN_JUHANI_JOINED"),
            ("danm15", "k_pdan_starmap02", "the star map: K_STAR_MAP = 10, DAN_STARMAP_DONE, journal dan_ruins 20"),
            ("danm13", "k_pdan_vandar03", "K_KOTOR_MASTER = 15: the galaxy map opens the four planets"),
            ("danm13", "k_pdan_vandar04", "DAN_RUINS_GONE"),
            ("danm13", "k_pdan_trig1301", "leaving the council: messenger flags, party zones"),
        ],
        "journal": [
            ("dan_trials", 50, "dialog dan13_zhar E20 (danm13)"),
            ("dan_ruins", 20, "k_pdan_starmap02 (danm15)"),
            ("k_starforge", 1, "dialog dan13_vandar R5 (danm13)"),
        ],
        "journal_remove": ["dan_council"],
        "journal_remove_note": "k_pdan_trig1303 removes dan_council once the council has sent the player out; the "
                               "GalaxyMap save has no dan_council entry",
        "finals": {
            "K_KOTOR_MASTER": (15, True, "k_pdan_vandar03; the galaxy map (k_pebn_galaxy) opens Kashyyyk, Manaan, "
                                         "Korriban and Tatooine at 15; seen in the GalaxyMap save"),
            "K_STAR_MAP": (10, True, "k_pdan_starmap02 sets 10 (Dantooine's map is always the first); seen in the "
                                     "GalaxyMap save"),
            "K_CURRENT_PLANET": (15, True, "set on the way from Taris; seen in the GalaxyMap save"),
            "DAN_STARMAP_DONE": (True, True, "k_pdan_starmap02 / k_pdan_15_strmp; seen in the GalaxyMap save"),
            "DAN_RUINS_GONE": (True, True, "k_pdan_vandar04 after the council; seen in the GalaxyMap save"),
            "DAN_JEDI_PLOT": (7, False, "k_pdan_zhar_d sets 7 at the end of the trials; seen in the GalaxyMap save"),
            "DAN_JUHANI_PLOT": (3, False, "3 is set by slot 5's own conversation scripts in scripts.bif; seen in "
                                          "the GalaxyMap save (light side: slot 5 spared)"),
            "DAN_JUHANI_STATE": (2, False, "k_pdan_juhani24; seen in the GalaxyMap save"),
            "DAN_JUHANI_JOINED": (True, False, "k_pdan_vandar02 when slot 5 is spared in the grove and joins (light side)"),
            "DAN_JUHANIQ_DONE": (True, False, "seen in the GalaxyMap save"),
            "DAN_PLANET_PLOT": (2, False, "set by the council's conversation scripts in scripts.bif; seen in the "
                                          "GalaxyMap save"),
            "DAN_JEDI_CODE": (True, False, "k_pdan_jedi44; seen in the GalaxyMap save"),
            "DAN_CORT_START": (True, False, "k_pdan_cut04; seen in the GalaxyMap save"),
            "DAN_ZHARL_DONE": (True, False, "k_pdan_jedi42; seen in the GalaxyMap save"),
            "DAN_CARTH_ZONE": (4, False, "k_pdan_trig1301; seen in the GalaxyMap save"),
            "DAN_CARTH_BACKUP": (True, False, "k_pdan_addcarth; seen in the GalaxyMap save"),
            "DAN_BASTILA_AT_JEDI": (False, False, "k_pdan_addbast sets FALSE when slot 0 rejoins; seen in the "
                                                  "GalaxyMap save"),
            "DAN_CARTH_AT_JEDI": (False, False, "k_pdan_addcarth sets FALSE when slot 2 rejoins; seen in the "
                                                "GalaxyMap save"),
            "DAN_BLACK_DONE": (True, False, "ruins computer (k_pdan_comp10), danm15 main path; seen in the "
                                            "GalaxyMap save"),
            "DAN_WHITE_DONE": (True, False, "ruins computer (k_pdan_comp11); seen in the GalaxyMap save"),
            "DAN_LIFE_DONE": (True, False, "ruins computer (k_pdan_comp12); seen in the GalaxyMap save"),
            "DAN_DEATH_DONE": (True, False, "ruins computer (k_pdan_comp13); seen in the GalaxyMap save"),
            "Dan_RakDroid_Build": (True, False, "ruins droid (k_pdan_drdbuildx); seen in the GalaxyMap save"),
            "Dan_RakDroid_Forge": (True, False, "ruins droid (k_pdan_drdforgex); seen in the GalaxyMap save"),
            "Dan_RakDroid_Time": (True, False, "ruins droid (k_pdan_drdtimex); seen in the GalaxyMap save"),
            "DAN_PATH_STATE": (None, False, "the trials' class choice: set by jedi_class below, not here"),
        },
        "party_recruit": [
            (5, "p_juhani", "k_pdan_vandar02", "danm13", False,
             "light side only: joins when spared in the grove; a player who kills her has no slot 5"),
        ],
        "items": [
            ("g_a_jedirobe01", 1, "k_pdan_zhar03", "danm13", "given when the trials begin"),
        ],
        "jedi_class": {
            "variable": "DAN_PATH_STATE",
            "set_by": "k_pdan_saber08 (from the trial answers), k_pdan_saber12 / 13 / 14 (the crystal choice)",
            "class_by": "k_pdan_makejedi: AddMultiClass(class, player), then XP up to the next level "
                        "(AddMultiClass at 0x0052DDC0 gives the next exptable threshold minus the current XP)",
            "lightsaber_by": "k_pdan_saber16: CreateItemOnObject on the player",
            "choices": [
                {"path_state": 1, "class": 3, "class_constant": "CLASS_TYPE_JEDIGUARDIAN",
                 "lightsaber": "g_w_lghtsbr01", "crystal_given": "dan13_bluecryst"},
                {"path_state": 2, "class": 5, "class_constant": "CLASS_TYPE_JEDISENTINEL",
                 "lightsaber": "g_w_lghtsbr04", "crystal_given": "dan13_goldcryst"},
                {"path_state": 3, "class": 4, "class_constant": "CLASS_TYPE_JEDICONSULAR",
                 "lightsaber": "g_w_lghtsbr03", "crystal_given": "dan13_grncryst"},
            ],
            "note": "the editor must let the player pick one choice: set DAN_PATH_STATE, add one level of the class "
                    "(the class's level-up is taken in game), give the lightsaber. The crystal and the plot crystal "
                    "dan13_plotcrys are used up when the lightsaber is built, so the player holds neither",
        },
        "dark": {
            "note": "the dark-side run kills slot 5 in the grove instead of sparing her: she never joins",
            "party_not_recruited": [5],
            "finals": {
                "DAN_JUHANI_PLOT": (2, False, "k_pdan_14juh_d sets 2 when the grove fight ends; 3 comes only from "
                                              "sparing her (k_pdan_juhani12)"),
                "DAN_JUHANI_JOINED": (False, False, "never set when she is killed"),
                "DAN_JUHANI_STATE": (None, False, "set by her conversation before the choice; left unchanged"),
            },
        },
        "next": {"fixed": {"module": "ebo_m12aa", "waypoint": "K_EBN_RAMP_ENTRANCE", "movies": [],
                           "by": "transition trigger dan13_tom12aa", "in": "danm13",
                           "note": "boarding the ship in the enclave's hangar; the next galaxy-map take-off "
                                   "plays the Dantooine take-off scene by itself (k_sup_galaxymap: K_KOTOR_MASTER "
                                   "15 and K_KALO_BANDON 0)"}},
    },
    # ------------------------------------------------------------------ the four free planets
    # Each can be the first, second, third or fourth after Dantooine, so their milestones set
    # only their own flags and leave the star map counter to STAR_MAP_RULE.
    ("K1", "Tatooine"): {
        "order": 4,
        "chapter_title": "Tatooine: the desert hunt and the star map",
        "credits_fixed": [(-2500, "slot 3's purchase in tat_m17ac (tat17ad_buyinghk47 stage 30, dialog "
                                  "tat17_08yuka_01), since the milestone recruits slot 3", 3)],
        "returnable": True,
        "returnable_note": "the four free planets stay on the galaxy map until the Unknown World is chosen "
                           "(k_sup_galaxymap CUSTOM_TurnOffPlanets)",
        "critical": [
            ("tat_m17ac", "cp_tat17ac_hkutl", "slot 3 can be bought (template p_hk47): optional"),
            ("tat_m18ac", "k_ptat_kraytcut9", "the dragon dies: tat_KraytDead, journal tat18ac_dragonhunt 70 and "
                                              "tat17_starmap 80"),
            ("tat_m18ac", "k_ptat_starcut", "the star map: K_STAR_MAP + 10, tat_StarmapFound, K_STAR_MAP_TATOOINE"),
        ],
        "journal": [
            ("tat17_starmap", 90, "dialog tat18_starspeak E0 (tat_m18ac)"),
            ("tat18ac_dragonhunt", 70, "k_ptat_kraytuser / k_ptat_kraytcut9 (tat_m18ac)"),
            ("tat17ag_sandbounty", 150, "dialog tat17_10czerk_01 E59 (tat_m17ag)"),
            ("k_starforge", 20, "the star map (UT_SetStarmapJournal)"),
        ],
        "finals": {
            "K_STAR_MAP_TATOOINE": (True, True, "k_ptat_starcut; seen in the Game224 save"),
            "tat_StarmapFound": (True, True, "k_ptat_starcut; seen in the Game224 save"),
            "tat_KraytDead": (True, False, "k_ptat_kraytuser / k_ptat_kraytcut9 (the dragon must die for the map); "
                                           "seen in the Game224 save"),
            "tat_KraytMap": (True, False, "k_ptat20aa_acqui / k_ptat_jawamap_g; seen in the Game224 save"),
            "tat_DuneSea": (True, False, "k_ptat18aa_enter; seen in the Game224 save"),
            "K_STAR_MAP": (None, False, "a counter: see star_map (STAR_MAP_RULE)"),
        },
        "star_map": dict(STAR_MAP_RULE, planet_flag="K_STAR_MAP_TATOOINE", script="k_ptat_starcut",
                         module="tat_m18ac", journal=["k_starforge", 20]),
        "party_recruit": [
            (3, "p_hk47", "cp_tat17ac_hkutl", "tat_m17ac", False,
             "optional: slot 3 joins only when bought in tat_m17ac. With K1 Community Patch the call is in "
             "cp_tat17ac_hkutl (placeable OnUserDefined); the unpatched game makes the same call in k_ptat_hk47add "
             "and k_ptat_hk47ship. The Game224 save has no slot 3"),
        ],
        "next": {"fixed": {"module": "ebo_m12aa", "waypoint": "K_EBN_RAMP_ENTRANCE", "movies": [],
                           "by": "cp_go_hawk2", "in": "tat_m17ab",
                           "note": "boarding the ship in the docking bay; the next galaxy-map take-off plays any "
                                   "story scene the star map count calls for (k_sup_galaxymap)"}},
    },
    ("K1", "Kashyyyk"): {
        "order": 5,
        "chapter_title": "Kashyyyk: the forest floor and the star map",
        "returnable": True,
        "returnable_note": "as Tatooine",
        "critical": [
            ("kas_m24aa", "k_pkas_joleejoin", "slot 4 joins (template p_jolee) on the forest floor (kas_m24aa)"),
            ("kas_m25aa", "k_pkas_openmap", "the star map computer: kas_ComputerDown, K_STAR_MAP + 10"),
            ("kas_m25aa", "k_pkas_starmap", "the star map: K_STAR_MAP_KASHYYYK, item kas_starpad"),
        ],
        "journal": [
            ("kas22_starmap", 70, "k_pkas_starcut (kas_m25aa)"),
            ("kas23_mainwookplot", 150, "dialog kas23_freyyr_01 E41 (kas_m23ad): the light-side ending"),
            ("k_starforge", 30, "the star map (UT_SetStarmapJournal)"),
        ],
        "finals": {
            "K_STAR_MAP_KASHYYYK": (True, True, "k_pkas_openmap / k_pkas_starmap"),
            "kas_ComputerDown": (True, True, "k_pkas_openmap: the star map's guard computer"),
            "G_JoleeJoined": (True, True, "k_pkas_joleejoin"),
            "kas_HelpedFreyyr": (True, False, "k_pkas_freyyrgo: the light-side ending of kas23_mainwookplot"),
            "K_STAR_MAP": (None, False, "a counter: see star_map (STAR_MAP_RULE)"),
        },
        "star_map": dict(STAR_MAP_RULE, planet_flag="K_STAR_MAP_KASHYYYK", script="k_pkas_starmap",
                         module="kas_m25aa", journal=["k_starforge", 30]),
        "party_recruit": [
            (4, "p_jolee", "k_pkas_joleejoin", "kas_m24aa", True, "joins on the forest floor (kas_m24aa)"),
        ],
        "items": [
            ("kas_starpad", 1, "k_pkas_starmap", "kas_m25aa", "given at the star map"),
        ],
        "next": {"fixed": {"module": "ebo_m12aa", "waypoint": "K_EBN_RAMP_ENTRANCE", "movies": [],
                           "by": "k_pkas_leave", "in": "kas_m22aa",
                           "note": "boarding the ship at the landing pad (dialog kas22_janos_01)"}},
    },
    ("K1", "Manaan"): {
        "order": 6,
        "chapter_title": "Manaan: the undersea station and the star map",
        "returnable": True,
        "returnable_note": "as Tatooine; man_questend closes Manaan's side quests when the player is banned",
        "critical": [
            ("manm28ad", "k_pman_starmap02", "the star map: K_STAR_MAP + 10, K_STAR_MAP_MANAAN"),
            ("manm28ad", "demo_trig03", "the star map is found: MAN_STARMAP_FOUND, journal man26_starmap 40"),
            ("manm27aa", "k_pman_27_init01", "the Sith base is sealed: MAN_SITHBASE_SEALED"),
        ],
        "journal": [
            ("man26_starmap", 40, "demo_trig03 (manm28ad)"),
            ("man_planet", 70, "dialog man26_repdip E94 (manm26ae): the ending that keeps the kolto machinery"),
            ("man_emb", 2, "dialog man26_repdip E0 (manm26ae)"),
            ("k_starforge", 40, "the star map (UT_SetStarmapJournal)"),
        ],
        "finals": {
            "K_STAR_MAP_MANAAN": (True, True, "k_pman_starmap02 / 06; seen in the Game22 save"),
            "MAN_STARMAP_FOUND": (True, True, "demo_trig03; seen in the Game22 save"),
            "MAN_HRAKERT_START": (True, False, "k_pman_merc01; seen in the Game22 save"),
            "MAN_SITHBASE_SEALED": (True, False, "k_pman_27_init01; seen in the Game22 save"),
            "MAN_PLANET_PLOT": (3, False, "seen in the Game22 save after the star map"),
            "MAN_LIVEB_STATE": (4, False, "k_pman_planet10; seen in the Game22 save"),
            "K_STAR_MAP": (None, False, "a counter: see star_map (STAR_MAP_RULE)"),
        },
        "star_map": dict(STAR_MAP_RULE, planet_flag="K_STAR_MAP_MANAAN", script="k_pman_starmap02",
                         module="manm28ad", journal=["k_starforge", 40]),
        "next": {"fixed": {"module": "ebo_m12aa", "waypoint": "K_EBN_RAMP_ENTRANCE", "movies": [],
                           "by": "cp_go_hawk2", "in": "manm26ad",
                           "note": "boarding the ship in the docking bay"}},
    },
    ("K1", "Korriban"): {
        "order": 7,
        "chapter_title": "Korriban: the academy and the star map",
        "returnable": True,
        "returnable_note": "as Tatooine",
        "critical": [
            ("korr_m39aa", "k_pkor_star_map", "the star map in the tomb: K_STAR_MAP + 10, K_STAR_MAP_KORRIBAN"),
        ],
        "journal": [
            ("kor33_findstarmap", 40, "k_pla_actmap2 / K1CP cp_k39_strmap_ps (korr_m39aa)"),
            ("kor33_enteracademy", 50, "dialog kor33_yuthura E16 (korr_m33aa)"),
            ("kor35_waysith", 60, "dialog kor39_yuthura R66 (korr_m39aa): the light-side ending"),
            ("k_starforge", 10, "the star map (UT_SetStarmapJournal)"),
        ],
        "finals": {
            "K_STAR_MAP_KORRIBAN": (True, True, "k_pkor_star_map / k_pla_actmap2 / cp_k39_strmap_ps"),
            "K_STAR_MAP": (None, False, "a counter: see star_map (STAR_MAP_RULE)"),
        },
        "star_map": dict(STAR_MAP_RULE, planet_flag="K_STAR_MAP_KORRIBAN", script="k_pkor_star_map",
                         module="korr_m39aa", journal=["k_starforge", 10]),
        "next": {"fixed": {"module": "ebo_m12aa", "waypoint": "K_EBN_RAMP_ENTRANCE", "movies": [],
                           "by": "cp_go_hawk2", "in": "korr_m33aa",
                           "note": "boarding the ship at the landing pad; slot 0 cannot leave the ship on this "
                                   "planet (k_sup_galaxymap SetNPCSelectability)"}},
    },

    # ------------------------------------------------------------------ Leviathan
    ("K1", "Leviathan"): {
        "order": 8,
        "chapter_title": "The Leviathan: captured, and the escape",
        "returnable": False,
        "returnable_note": "the Leviathan is never boarded again. In the game it comes after the third of the four "
                           "free planets (K_STAR_MAP 40 and K_CAPTURED_LEV 5 at the next take-off), not after the "
                           "fourth: order 8 is the chapter list's order, not a fixed place in the story",
        "critical": [
            ("lev_m40ac", "k_plev_finale5", "after the bridge (dialog lev40_carth R13): K_KOTOR_MASTER 20, "
                                            "K_CAPTURED_LEV 10, slot 0 leaves, the hangar door lev40_hangar unlocks"),
        ],
        "journal": [
            ("lev_captured", 99, "dialog lev40_carth R13 (lev_m40ac)"),
        ],
        "finals": {
            "K_KOTOR_MASTER": (20, True, "k_plev_finale5 / k_plev_goebon; the galaxy map makes Dantooine unselectable "
                                         "at 20"),
            "K_CAPTURED_LEV": (10, True, "k_plev_finale5 / k_plev_goebon"),
        },
        "party_remove": [
            (0, "k_plev_finale5", "lev_m40ac", True, "slot 0 is taken by the enemy (RemoveAvailableNPC 0)"),
        ],
        "next": {"fixed": {"module": "ebo_m40ad", "waypoint": "", "movies": [],
                           "by": "transition door lev40_hangar", "in": "lev_m40ac",
                           "note": "the hangar door k_plev_finale5 unlocks leads to the ship (ebo_m40ad), which "
                                   "flies out by its own scripts; k_plev_goebon and k_plev_hackebon make the same "
                                   "move but nothing in lev_m40ac runs them"}},
    },

    # ------------------------------------------------------------------ Unknown World
    ("K1", "Unknown World"): {
        "order": 9,
        "chapter_title": "The Unknown World: the temple and the last star map",
        "returnable": False,
        "returnable_note": "after the temple the galaxy map offers only the Star Forge",
        "critical": [
            ("unk_m44ac", "k_punk_disfldoff", "the temple summit: UNK_DISRUPT_OFF, journal unk_trapped"),
            ("unk_m44ac", "k_punk_bastesc", "light side: G_FinalChoice 2"),
            ("unk_m41aa", "k_punk_fincs_en", "back at the ship: K_KOTOR_MASTER 50"),
            ("unk_m41aa", "k_punk_finale04", "StartNewModule ebo_m41aa"),
        ],
        "journal": [
            ("unk_trapped", 99, "dialog unk44_evilbast R149 / R60 (unk_m44ac): the light-side ending"),
            ("k_starforge", 75, "dialog unk41_carth (ebo_m41aa): the light-side stage"),
        ],
        "finals": {
            "K_KOTOR_MASTER": (50, True, "k_punk_fincs_en / k_pebn_starf; the galaxy map then plays the take-off to "
                                         "the Star Forge"),
            "G_FinalChoice": (2, False, "light side (k_punk_bastesc); the dark side sets 1 and changes the party "
                                        "(k_punk_bastjoin)"),
            "UNK_DISRUPT_OFF": (True, True, "k_punk_disfldoff: the ship can leave"),
            "UNK_SHIELD_OFF": (True, False, "k_punk_shieldoff"),
            "K_CURRENT_PLANET": (45, True, "k_ren_unkcrash on arrival"),
        },
        "dark": {
            "note": "the dark-side run joins slot 0 at the temple summit (k_punk_bastjoin): slots 4 and 5 are lost "
                    "there, and back at the ship slot 2 leaves (k_punk_carthrem) and slot 6 is lost "
                    "(k_punk_misrem, the usual dark choice)",
            "journal": [
                ("unk_trapped", 98, "dialog unk44_evilbast R74 / R163 (unk_m44ac): the dark-side ending"),
                ("k_starforge", 70, "k_punk_disfldoff (unk_m44ac): the dark-side stage"),
                ("k_swg_bastilatalk", 4, "dialog unk44_evilbast R74 / R163 (unk_m44ac)"),
            ],
            "finals": {
                "G_FinalChoice": (1, True, "k_punk_bastjoin; the Star Forge plays the dark-side ending"),
            },
            "party_recruit": [
                (0, "p_bastilla004", "k_punk_bastjoin", "unk_m44ac", True,
                 "the template by the temple slot 0's level sum (unk44_evilbast: level 18 gives p_bastilla004)"),
            ],
            "party_remove": [
                (4, "k_punk_bastjoin", "unk_m44ac", True, "RemoveAvailableNPC(4) at the summit"),
                (5, "k_punk_bastjoin", "unk_m44ac", True, "RemoveAvailableNPC(5) at the summit"),
                (2, "k_punk_carthrem", "unk_m41aa", True, "dialog unk41_carth E23: slot 2 leaves"),
                (6, "k_punk_misrem", "unk_m41aa", False, "dialog unk41_mission E6: slot 6 is lost; "
                                                          "k_punk_zaalrem (E2) would lose slot 8 as well"),
            ],
        },
        "next": {"from": ("unk_m41aa", "k_punk_finale04")},
    },

    # ------------------------------------------------------------------ Star Forge
    ("K1", "Star Forge"): {
        "order": 10,
        "chapter_title": "The Star Forge: the end of the game",
        "returnable": False,
        "returnable_note": "the game ends",
        "critical": [
            ("sta_m45ad", "k_psta_ud_malak", "the last fight: STA_MALAK_DEAD"),
            ("sta_m45aa", "k_psta_bastleav2", "light side (G_FinalChoice 2): StartNewModule STUNT_56a with movie 56"),
        ],
        "journal": [
            ("sta_confront", 99, "the light-side ending (no setter found in the files; the ending cutscenes)"),
        ],
        "finals": {
            "G_FinalChoice": (2, False, "light side; 1 plays the dark-side ending (STUNT_54a)"),
            "STA_MALAK_DEAD": (True, True, "k_psta_ud_malak / k_psta_mlkend"),
        },
        "dark": {
            "note": "the dark-side ending: after the last fight k_psta_mlkend (sta_m45ad, G_FinalChoice 1) moves "
                    "on to STUNT_54a with movie 51",
            "journal": [],
            "finals": {
                "G_FinalChoice": (1, True, "set at the Unknown World's summit by the dark-side choice"),
            },
            "next": {"from": ("sta_m45ad", "k_psta_mlkend"), "target": "stunt_54a"},
        },
        "next": {"from": ("sta_m45aa", "k_psta_bastleav2"), "target": "stunt_56a", "last": "stunt_57",
                 "note": "the light-side ending: STUNT_56a with movie 56, then the ceremony (stunt_57); the "
                         "game ends there"},
    },

    # ------------------------------------------------------------------ side chapters
    ("K1", "Ebon Hawk"): {
        "order": 11,
        "side_chapter": True,
        "story_position": "the ship's own quests between planets; its XP is counted after Korriban",
        "chapter_title": "The Ebon Hawk: the ship's own quests",
        "returnable": True,
        "return_modules": {"m12ab": False, "ebo_m40aa": False, "ebo_m40ad": False, "ebo_m41aa": False,
                           "ebo_m46ab": False},
        "returnable_note": "ebo_m12aa is the ship between planets; the other modules are one-time scenes",
        "critical": [
            ("ebo_m12aa", "dialog ebo46_gizka E9", "journal k_pebo_gizkatrouble 30"),
            ("ebo_m12aa", "dialog ebo46_lurarka R9", "journal k_pebo_stowaway 40"),
            ("ebo_m12aa", "dialog ebo46_sasha E1", "journal ebo_supplies 99"),
        ],
        "journal": [
            ("k_pebo_gizkatrouble", 30, "dialog ebo46_gizka E9 (ebo_m12aa)"),
            ("k_pebo_stowaway", 40, "dialog ebo46_lurarka R9 (ebo_m12aa)"),
            ("ebo_supplies", 99, "dialog ebo46_sasha E1 (ebo_m12aa)"),
        ],
        "finals": {},
        "next": {"fixed": {"module": "ebo_m12aa", "waypoint": "", "movies": [],
                           "by": None, "in": "ebo_m12aa",
                           "note": "the chapter happens on the ship; the party stays on board"}},
    },
    ("K1", "Yavin Station"): {
        "order": 12,
        "side_chapter": True,
        "story_position": "an optional stop between the free planets; its XP is counted after Korriban",
        "chapter_title": "Yavin Station: the trader's station",
        "returnable": True,
        "critical": [],
        "journal": [],
        "finals": {},
        "next": {"fixed": {"module": "ebo_m12aa", "waypoint": "K_EBN_RAMP_ENTRANCE", "movies": [],
                           "by": "transition door yavinarea", "in": "liv_m99aa",
                           "note": "back to the ship through the station's door"}},
    },
}


# ------------------------------------------------------------------ KotOR 2
# Added 2026-10-23: one file per KotOR 2 chapter in chapters_k2/, each defining PLANET (the
# build.py PLANETS name) and CHAPTER (the same fields as above).
def _load_k2():
    import glob
    import importlib.util
    import os
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chapters_k2")
    for path in sorted(glob.glob(os.path.join(here, "*.py"))):
        spec = importlib.util.spec_from_file_location("chapters_k2_" + os.path.basename(path)[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if getattr(mod, "PLANET", None) and getattr(mod, "CHAPTER", None) is not None:
            CHAPTERS[("K2", mod.PLANET)] = mod.CHAPTER


_load_k2()
