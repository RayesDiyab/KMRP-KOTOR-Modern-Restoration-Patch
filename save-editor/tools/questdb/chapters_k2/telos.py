"""KotOR 2, Telos: the first visit, from the arrest at Citadel Station to the escape on the
Ebon Hawk (curated 2026-10-23).

Worked out from the game's scripts and conversations (scanmod.py, showscript.py, dlgnode.py of
the k2kit) and checked against the maintainer's save "Game3" (203tel, mid-Telos). IDs only: no
names or text from the game (KMRP rule, 2026-10-23); people are named by slot or tag.

The route: arrest in 201tel; the ship is reported stolen in 202tel (dialog 202drdt); the
station's side quests in 202-209tel; the Ithorian leader (tag 204_habat ... dialog 204habat) or
the Czerka director (dialog 203lorso) arranges the shuttle (201tel_shuttle_ready); the shuttle
(dialog 201shu) to the restoration zone 231tel, where slot 1 joins (a_baodur_join); the shield
network in 233tel; the military base 232tel and its shuttle (k_ptel_shuttle) to the polar plateau
261tel; the hidden academy 262tel, where the ship is found (ehstolen 99) and the companions are
freed (262TEL_CNPC_Freed); boarding the ship (dialog ebonhawk R1, a_setup_ebo2) plays the escape
in 950cor (dialog holorec: journal LostJedi 30, 262TEL_Escape_Telos = 1, the Handmaiden joins a
male player), and holorec's last line (a_load003) moves the party to the ship, 003ebo, where the
galaxy map opens the four planets.

950cor (the escape scene) is visited only from 262tel's first visit (a_setup_ebo2, a_atrissis),
so it belongs to this chapter, not to "The Jedi Masters" (build.py lists it there). Its
conversation lines are named below as dialog lines; its scripts are outside the chapter's
modules, so the milestone generator cannot check them.
"""
PLANET = "Telos"

CHAPTER = {
    "order": 2,
    "chapter_title": "Telos: Citadel Station, the stolen ship and the polar academy",
    "returnable": True,
    "return_modules": {
        "205tel": False, "211tel": False,
        "231tel": False, "232tel": False, "233tel": False, "261tel": False, "262tel": False,
    },
    "returnable_note": "after Telos the galaxy map (a_galaxymap, 003ebo) offers Citadel Station (planetary.2da row "
                       "10) but never Telos itself (row 9), so only the station modules 201-209tel can be visited "
                       "again, until 221tel (The Jedi Masters) deletes their save group 6 (modulesave.2da). The "
                       "shuttle to the restoration zone runs once (dialog 201shu E3 sets 201TEL_Shuttle_Ready 0), "
                       "so 231-233tel are never entered again; 261tel and 262tel are reached again only late, by "
                       "006ebo (The Jedi Masters), and are not stored as played. 205tel and 211tel are not kept "
                       "in a save (modulesave.2da includeinsave 0)",
    "critical": [
        ("201tel", "dialog 201bay E26", "the arrest: journal arrested 10"),
        ("202tel", "dialog 202drdt E12", "the ship is gone: journal ehstolen 10"),
        ("202tel", "dialog 202drdt E26", "the equipment comes back: journal ehind 30"),
        ("202tel", "a_grenn_cut|5,0,0,0,0,", "the quarantine ends: the force cages are taken down"),
        ("202tel", "a_grenn_cut|7,0,0,0,0,", "dialog 202grenn E118: on to 203TEL (From_202TEL_intro)"),
        ("203tel", "a_grenn_intro|4,0,0,0,0,", "the arrival at the apartment"),
        ("203tel", "a_grenn_intro|6,0,0,0,0,", "the officers leave the apartment"),
        ("203tel", "dialog 203atton E26", "house arrest lifted: journal arrested 20"),
        ("204tel", "dialog 204habat E25", "the Ithorian route: journal ehstolen 30"),
        ("204tel", "dialog 204habat E28", "the shuttle is arranged: 201tel_shuttle_ready = 1"),
        ("204tel", "a_czerkapad|2,0,0,0,0,", "dialog 204habat R239: the temporary slot 1 (tag 204_b4d4, added by "
                                             "a_b4d4control) leaves (RemoveAvailableNPC 1)"),
        ("201tel", "dialog 201shu R3", "the shuttle to the restoration zone: journal arrested 50"),
        ("201tel", "a_201shuttle|1,0,0,0,0,", "StartNewModule 231TEL"),
        ("231tel", "dialog 231sntry R50", "journal ehstolen 40"),
        ("231tel", "a_baodur_join|0,0,0,0,0,", "dialog 231sntry R54: slot 1 joins (AddAvailableNPCByObject, tag "
                                               "baodur)"),
        ("233tel", "dialog 233bdur E9", "the shield network: journal ehstolen 50"),
        ("232tel", "k_ptel_shuttle|0,0,0,0,0,", "dialog hk50_cut E5: the shuttle to 261TEL"),
        ("261tel", "a_load262|0,0,0,0,0,", "dialog 261exit R2: on to 262TEL"),
        ("262tel", "dialog atris E6", "the ship is found: journal ehstolen 99"),
        ("262tel", "a_set262freecnpc|1,0,0,0,0,", "dialog 262kreia E0: 262TEL_CNPC_Freed = 1"),
        ("262tel", "a_setup_ebo2|0,0,0,0,0,", "dialog ebonhawk R1: 003EBO_BACKGROUND and 003EBO_RETURN_DEST = 8, "
                                              "StartNewModule 950COR (a female player directly with movie "
                                              "TelMov14; a male one first through dialog atrissis, whose "
                                              "a_atrissis|5 moves to 950COR)"),
        ("950cor", "dialog holorec E0", "journal LostJedi 30, 262TEL_Escape_Telos = 1"),
        ("950cor", "dialog holorec E103", "male player: slot 4 joins (a_addhandmaid, AddAvailableNPCByObject)"),
        ("950cor", "dialog holorec R100", "female player: a_load003, StartNewModule 003EBO"),
        ("950cor", "dialog holorec R135", "male player: a_load003, StartNewModule 003EBO"),
    ],
    "journal": [
        ("ehstolen", 99, "dialog atris E6 (262tel)"),
        ("lostjedi", 30, "dialog holorec E0 (950cor); LostJedi is The Jedi Masters' quest, its stage 30 is set here"),
        ("arrested", 50, "dialog 201shu R3 (201tel)"),
        ("ehind", 30, "dialog 202drdt E26 (202tel)"),
        # Citadel Station side quests, the Ithorian (light) route
        ("caller", 40, "dialog 204habat E141 (204tel)"),
        ("czerkacall", 40, "dialog 203lorso E48 (209tel); seen at 40 in the Game3 save"),
        ("restdroid", 30, "dialog 204habat E185 (204tel): the droid brain to the Ithorians"),
        ("czerkamain", 50, "dialog 204habat E18 (204tel)"),
        ("czerka_attack", 30, "dialog 204habat E223 (204tel): the Ithorians saved"),
        ("merc_attack", 20, "dialog 203lorso E145 (209tel)"),
        ("opo_chano", 30, "dialog 207luxa E84 (207tel)"),
        ("exch_meeting", 40, "dialog 207luxa R125 (207tel): the money handed over"),
        ("luxa", 60, "dialog 203slusk E26 (208tel): the Exchange leader leaves the Ithorians alone"),
        ("ithdip", 40, "dialog 204habat E76 (204tel)"),
        ("batono", 70, "dialog 202grenn E168 (202tel): escorted to the TSF"),
        ("baturem", 40, "dialog 202grenn R23 (202tel)"),
        ("blackmarket", 30, "dialog 202grenn R110 / R125 (202tel)"),
        ("smuggling_tsf", 60, "dialog samhan E78 (202tel): the smuggler arrested"),
        ("killers", 40, "dialog 202grenn E17 (202tel)"),
        ("high_stakes", 50, "dialog dotonhet E32 (207tel): won at pazaak"),
        ("yima", 20, "Yima's quest, the first ending (no setter found in the files; a conversation in scripts.bif "
                     "or 201tel's own dialogs)"),
    ],
    "finals": {
        "262TEL_Escape_Telos": (1, True, "dialog holorec E0 (950cor, a_global_set). The galaxy map (a_galaxymap, "
                                         "003ebo) opens Dantooine, Korriban, Nar Shaddaa and Onderon (Dxun instead "
                                         "once 401DXN_Visited is set) only when it is 1 and 003EBO_Atton_Talk is "
                                         "above 4 (set to 5 and more in 003ebo before Telos; 7 in the Game3 save)"),
        "262TEL_CNPC_Freed": (1, True, "a_set262freecnpc (dialog 262kreia E0, 262tel): the companions freed; "
                                       "a_setup_ebo2 needs it"),
        "003EBO_BACKGROUND": (8, True, "a_setup_ebo2 (262tel) on boarding the ship; the galaxy map draws the ship "
                                       "in deep space and takes off from there"),
        "003EBO_RETURN_DEST": (8, True, "a_setup_ebo2 (262tel); the ship's exit (tr_leave_ehawk, 004ebo) has no "
                                        "planet for 8 until the next landing sets it"),
        "201TEL_Shuttle_Ready": (0, True, "dialog 201shu E3 sets 0 when the shuttle leaves (204habat E28 set 1 "
                                          "before); a_201shuttle, run after it, sets 2 only from 1"),
        "200TEL_Control": (1, True, "a_201shuttle (201tel), its only writer, on taking the shuttle: 1 on every path "
                                    "unless 203TEL_Czerka_Attack is 1 (the compound left under attack), then 2. The "
                                    "light run beats the attack (a_set204czerka: 0) or never starts it, so it ends "
                                    "at 1. Read by k_221tel_enter (221tel, The Jedi Masters): 1 places the Ithorian "
                                    "leaders (221_chodo, 221_moza) and militia, otherwise mercenaries"),
        "203TEL_Czerka_Call": (4, True, "the Czerka call: a_setczerkacall|4 on dialog 203lorso E0; the other writers "
                                        "(dialog 203b4d4 E1: 3, E3: 0, 203tel) come before it. Seen at 4 in both runs' "
                                        "saves (Game2, a light run, and AUTOSAVE / Game3). Read by c_chkczerkacall "
                                        "(209tel, 221tel)"),
        "201TEL_Chano_Spawn": (None, False, "the droid technician's fate: 4 only when he fled on the shuttle "
                                            "(a_201shuttle, journal opo_chano 24), which k_303nar_enter (303nar) "
                                            "reads to place him on Nar Shaddaa; the light run settles his debt "
                                            "(opo_chano 30), so it stays below 4. Left unchanged"),
        "200TEL_B4D4_T1N1": (None, False, "1 from dialog 204habat E211 (a_set200b4d4t1n1), 2 from k_ptel201_enter; "
                                          "read by a_t3m4intro (303nar) for a line of slot 8. Left unchanged"),
        "203TEL_Czerka_Attack": (0, True, "the attack on the Ithorian compound: 1 while it runs (tr_moza_help, "
                                          "a_moza_czerka), 0 once it is beaten (a_set204czerka, 204tel), 2 when the "
                                          "player leaves on the shuttle during it (a_201shuttle). The light run "
                                          "beats it or never starts it: 0 either way"),
        # first entries: each module's OnEnter plays its arrival scene while its flag is FALSE and sets it; all
        # five modules are on the main path. 201 also counts for the Ebon Hawk's cutscene table: its "planets
        # entered" count (a_next_scene / k_003ebo_enter) adds up 201, 301, 401, 501, 601 and 701_FIRST_ENTER
        "201_FIRST_ENTER": (True, True, "k_201tel_enter on the first entry; seen in all three saves past Peragus"),
        "202_FIRST_ENTER": (True, True, "k_202tel_enter on the first entry; seen in all three saves past Peragus"),
        "203_FIRST_ENTER": (True, True, "k_203tel_area (203tel, 208tel) on the first entry; seen in all three saves "
                                        "past Peragus"),
        "231_FIRST_ENTER": (True, True, "k_231area_enter on the first entry of the restoration zone (main path)"),
        "232_FIRST_ENTER": (True, True, "k_232_enter on the first entry of the military base (main path)"),
    },
    "dark": {
        "note": "the Czerka route and the station's dark choices: the player leaves the Ithorian compound under "
                "attack (journal czerka_attack 35 by a_201shuttle), so the station ends under Czerka control "
                "(200TEL_Control 2), which 221tel reads in The Jedi Masters. The shuttle is still arranged in dialog "
                "204habat E28 (the only setter of 201tel_shuttle_ready), so the route on is the same",
        "journal": [
            ("ehstolen", 99, "dialog atris E6 (262tel)"),
            ("lostjedi", 30, "dialog holorec E0 (950cor)"),
            ("arrested", 50, "dialog 201shu R3 (201tel)"),
            ("ehind", 30, "dialog 202drdt E26 (202tel)"),
            ("caller", 40, "dialog 204habat E141 (204tel): needed for the shuttle"),
            ("czerkacall", 40, "dialog 203lorso E48 (209tel)"),
            ("restdroid", 35, "dialog 203lorso E111 (209tel): the droid brain to Czerka"),
            ("czerka_attack", 35, "a_201shuttle (201tel): the Ithorians left under attack"),
            ("merc_attack", 20, "dialog 203lorso E145 (209tel)"),
            ("falt", 40, "dialog 203lorso E14 (209tel)"),
            ("exchange", 60, "dialog 203lorso R31 (209tel)"),
            ("luxa", 40, "k_luxa_death / k_slusk_death (208tel): both Exchange leaders killed"),
            ("opo_chano", 30, "dialog 207luxa E84 (207tel)"),
            ("exch_meeting", 45, "dialog 207luxa E99 / R123 (207tel): the money kept"),
            ("batono", 80, "dialog 203lorso E53 (209tel): rewarded by Czerka"),
            ("baturem", 40, "dialog 202grenn R23 (202tel)"),
            ("blackmarket", 40, "a_goodsjrl (202tel)"),
            ("smuggling", 80, "dialog samhan E85 (202tel)"),
            ("smuggling_tsf", 70, "a_tsfsmugclose (202tel): sided with the smuggler"),
            ("killers", 40, "dialog 202grenn E17 (202tel)"),
            ("high_stakes", 54, "dialog dotonhet E1 (203tel): by the Exchange's enforcers"),
            ("yima", 30, "Yima's quest, the second ending (a_setqyima, 201tel)"),
        ],
        "finals": {
            "200TEL_Control": (2, False, "a_201shuttle with 203TEL_Czerka_Attack 1: Czerka holds the station. "
                                         "Leaving during the attack is when the player boards, not a side's "
                                         "choice; this block's journal (czerka_attack 35) takes that route"),
            "203TEL_Czerka_Attack": (2, False, "a_201shuttle when the player leaves during the attack (see "
                                               "200TEL_Control)"),
        },
    },
    "party_recruit": [
        (1, "p_baodur", "a_baodur_join|0,0,0,0,0,", "231tel", True,
         "joins in the restoration zone (dialog 231sntry R54). The game adds him with AddAvailableNPCByObject from "
         "the placed tag baodur; p_baodur is the template the game's own debug script (a_debugparty) uses for "
         "slot 1. Slot 1 held a droid (tag 203_b4d4 / 204_b4d4) for a while on the station; a_czerkapad|2 removed "
         "it before"),
        (4, "p_handmaiden", "a_addhandmaid|0,0,0,0,0,", "950cor", True,
         "male player only: joins on the ship after the escape (dialog holorec E103 / E106, AddAvailableNPCByObject "
         "on tag handmaiden; p_handmaiden as a_debugparty uses). A female player gets slot 11 on Dantooine "
         "instead", "male"),
    ],
    "items": [],
    "credits_fixed": [],
    "next": {"fixed": {"module": "003ebo", "waypoint": "", "movies": [],
                       "by": "a_load003|0,0,0,0,0,", "in": "950cor",
                       "note": "the last line of dialog holorec (R100 female, R135 male) runs a_load003: "
                               "StartNewModule 003EBO with no waypoint, so the party stands at the module's entry "
                               "point. 950cor itself is the escape scene (includeinsave 0), entered from 262tel by "
                               "a_setup_ebo2; the milestone applies its effects (journal LostJedi 30, "
                               "262TEL_Escape_Telos, the male player's slot 4) and goes straight to the ship. That "
                               "arrival is a real module start, so the Ebon Hawk's cutscene table plays the scenes "
                               "due after Telos there (dialog baosaber: CUT_BAODUR_LIGHTSABER and LightsaberQuest "
                               "10; dialog bao_t3: CUT_BAO_T3, which raises slot 8's constitution); they are set "
                               "only by the chapters after this one (Nar Shaddaa)"}},
    "xp": {
        "modules": ["201tel", "202tel", "203tel", "204tel", "205tel", "207tel", "211tel", "208tel", "209tel",
                    "231tel", "233tel", "232tel", "261tel", "262tel"],
        "maybe": False,
        "extra": [],
        "endings": {"ehstolen": 99, "arrested": 50, "ehind": 30, "caller": 40, "czerkacall": 40, "restdroid": 30,
                    "czerkamain": 50, "czerka_attack": 30, "merc_attack": 20, "opo_chano": 30, "exch_meeting": 40,
                    "luxa": 60, "ithdip": 40, "batono": 70, "baturem": 40, "blackmarket": 30, "smuggling_tsf": 60,
                    "killers": 40, "high_stakes": 50, "yima": 20},
    },
}
