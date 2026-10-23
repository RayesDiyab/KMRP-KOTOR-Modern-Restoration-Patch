"""KotOR 2, Korriban: the valley, the academy, the cave and the hidden tomb.

Curated 2026-10-23 from the game's scripts and conversations (scanmod.py, showscript.py and
dlgnode.py of the research kit; tools/questdb/milestone.py builds the milestone). IDs only:
module names, dialog nodes, script keys, global names, tags and templates.

The chapter: the ship lands in the valley (701kor). In the academy (702kor) the entry door
shuts behind the player (journal trapped 10, dialog sion E32); the master searched for is
found dead (trigger tr_vash: 000_Jedi_Found + 1, 702KOR_Vash 1; dialog vash E0: journal
lostjedi 60). The player flees the enemy of the academy (dialog sion E0: trapped 99; R0:
702KOR_Sion 3; R8: a_to_701kor back to the valley). The cave (710kor) leads into the hidden
tomb (711kor, dialog sec_tomb E22, a_tomb 3), whose visions end with dialog kreia_tm E0
(hidden_power 99). The player walks back to the ship in the valley.

The master is dead, but the visit still counts as a master found: tr_vash raises
000_Jedi_Found, the masters' count four planets share (MASTERS_RULE in chapters_k2/dantooine.py);
the chapter carries it in "increments" (the editor adds 1 for each chapter skipped).
"""
PLANET = "Korriban"

CHAPTER = {
    "order": 7,
    "chapter_title": "Korriban: the abandoned academy and the hidden tomb",
    "returnable": True,
    "returnable_note": "the ship can fly back to Korriban while the four free planets are open; the valley, the "
                       "academy and the cave stay reachable",
    "critical": [
        ("701kor", "dialog kreia_cv E2", "on landing: journal hidden_power 10"),
        ("702kor", "dialog sion E32", "the academy's door shuts: journal trapped 10"),
        ("702kor", "tr_vash", "the dead master: 000_Jedi_Found + 1, 702KOR_Vash 1"),
        ("702kor", "dialog vash E0", "journal lostjedi 60"),
        ("702kor", "dialog sion E0", "the flight from the academy: journal trapped 99, a_sion_end"),
        ("702kor", "dialog sion R0", "702KOR_Sion 3"),
        ("702kor", "dialog sion R8", "a_to_701kor: StartNewModule 701kor (From_702Kor)"),
        ("710kor", "dialog sec_tomb E22", "a_tomb 3: StartNewModule 711KOR (From_710KOR)"),
        ("711kor", "tr_last_vision", "the last vision: 711KOR_Vision_Track 9"),
        ("711kor", "dialog kreia_tm E0", "the tomb's trials passed: journal hidden_power 99"),
    ],
    "journal": [
        ("trapped", 99, "dialog sion E0 (702kor): escaped from the academy"),
        ("hidden_power", 99, "dialog kreia_tm E0 (711kor): the tomb's trials passed"),
        ("jedi_tomb", 90, "a_jedi_jrnl_fin (711kor, container jedi_cont closed): the bonus quest in the tomb"),
    ],
    "finals": {
        "702KOR_Vash": (1, True, "tr_vash (702kor) when the dead master is found"),
        "702KOR_Sion": (3, True, "dialog sion R0 (702kor), the flight from the academy; 1 and 2 are earlier "
                                 "meetings (sion R35, kreia_si E0)"),
        "711KOR_Vision_Track": (9, True, "tr_last_vision (711kor): the last of the tomb's visions"),
        "701_FIRST_ENTER": (True, True, "tr_intro (701kor) on the first landing"),
        "003EBO_RETURN_DEST": (6, True, "tr_ehawk_custom (701kor) when boarding the ship"),
        "003EBO_BACKGROUND": (6, True, "tr_ehawk_custom (701kor) when boarding the ship"),
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
    },
    "master_met": [{"global": "702KOR_Vash"}],  # tr_vash sets it when the master is found
    "increments": [
        ("000_Jedi_Found", 1, "the masters' count four planets share: tr_vash (702kor) raises it when the dead "
                              "master is found; see MASTERS_RULE in chapters_k2/dantooine.py"),
    ],
    "next": {"from": ("701kor", "tr_ehawk_custom"),
             "note": "boarding the ship in the valley (trigger to_ebonhawk_custom); the ship (003ebo) is the Ebon "
                     "Hawk chapter's between-planets module. Slot 6 cannot be picked for the party on Korriban "
                     "(k_701area_enter: SetNPCSelectability 6 FALSE)"},
    "credits_fixed": [],
    "xp": {"modules": ["701kor", "702kor", "710kor", "711kor"], "maybe": False, "extra": [],
           "endings": {"trapped": 99, "hidden_power": 99, "jedi_tomb": 90}},
}
