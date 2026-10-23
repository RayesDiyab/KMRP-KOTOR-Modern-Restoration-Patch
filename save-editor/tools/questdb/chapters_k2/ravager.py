"""KotOR 2, Ravager: the flagship over Telos, its destruction and the Sith lord on its bridge
(curated 2026-10-23).

Worked out from the game's scripts and conversations (scanmod.py, showscript.py, dlgnode.py of
the k2kit). IDs only: no names or text from the game (KMRP rule, 2026-10-23); people are named by
slot or tag.

The route: 222tel's dialog carth R10 (The Jedi Masters) moves the party to 851NIH FROM_222TEL.
  851nih  the boarding scene (dialog 851mand: E0 journal destroyravager 10, R0 defeatdarthnihilus
          10; EndConversation a_end_openingcs). The charges: the trigger at each bomb site sets
          851NIH_BOMBSITE 1..4; the dialogs 851dem (R10 a_fire851expdlg: 851NIH_Bomb_Ravager 1,
          E8: 3) and 851mis (R3: 851NIH_Bomb_Ravager 2, 851NIH_Missile_Bay 2), 851com (E2:
          851NIH_Missile_Bay 1). The trigger TO_852NIH leads to the bridge.
  852nih  the Sith lord (dialog 852nih; EndConversation a_atkonend). E25 a_nihilus|14 takes slot 9
          out of the party and makes her unselectable for the fight. Slot 9 can offer her life
          (E20: 852NIH_VisasSacrifice 1, an optional choice this milestone does not take). The lord's
          defeat (k_nihilus_ud, user event 1006): journal defeatdarthnihilus 99 (and destroyravager
          70 on one branch), a_start_ending: 852NIH_Nihilus_Dead 1 and dialog 852end (or 852sacri
          with 000_Visas_Dead 1 after the sacrifice, whose R14 a_sacrifice|3 removes slot 9 for good).
          852end R8 (take the mask: a_give_item nihilusmask, a_addforcepoints 20) is an optional reply;
          R9 and the others leave it.
  851nih  back through TO_852NIH; dialog 222tel (the way to the shuttle) E3 (start: 852NIH_Nihilus_Dead
          1 and 851NIH_Bomb_Ravager > 2): journal destroyravager 99; R5 a_escape_851: movie MalMov05,
          then by 101PER_Revan_End (Peragus's answer about the previous game's hero): not 1 ->
          StartNewModule 205TEL (the admiral's farewell, dialog carthend, whose EndConversation
          a_901jump plays TelMov02, HypMov01, MalMov07, MalMov08 and moves on to 907MAL with
          907MAL_CUTSCENE 2); 1 -> the same movies and 907MAL directly.

853nih is never loaded: no script, door or trigger in the game names it (its three cutscenes
nihilus, nihtobin and sioncut end in StartNewModule 000TEST, a module that does not exist), so
it is leftover content; nothing in it is curated.
"""
PLANET = "Ravager"

CHAPTER = {
    "order": 9,
    "chapter_title": "The Ravager: destroying the flagship and its master",
    "returnable": False,
    "return_modules": {"851nih": False, "852nih": False, "853nih": False},
    "returnable_note": "the ship is destroyed when the chapter ends; 853nih is never loaded",
    "critical": [
        ("851nih", "dialog 851mand E0", "the boarding: journal destroyravager 10"),
        ("851nih", "dialog 851mand R0", "journal defeatdarthnihilus 10"),
        ("851nih", "a_fire851expdlg|0,0,0,0,0,", "dialog 851dem R10: 851NIH_Bomb_Ravager 1"),
        ("851nih", "dialog 851mis R3", "851NIH_Bomb_Ravager 2, 851NIH_Missile_Bay 2"),
        ("851nih", "dialog 851dem E8", "851NIH_Bomb_Ravager 3"),
        ("852nih", "a_nihilus|14,0,0,0,0,", "dialog 852nih E25: slot 9 out of the party and unselectable"),
        ("852nih", "k_nihilus_ud", "the lord beaten: journal defeatdarthnihilus 99, a_start_ending"),
        ("852nih", "a_start_ending", "852NIH_Nihilus_Dead 1, dialog 852end"),
        ("851nih", "dialog 222tel E3", "the way out: journal destroyravager 99"),
        ("851nih", "a_escape_851|0,0,0,0,0,", "dialog 222tel R5: movie MalMov05, StartNewModule 205TEL (or 907MAL "
                                              "when 101PER_Revan_End is 1)"),
    ],
    "journal": [
        ("destroyravager", 99, "dialog 222tel E3 (851nih): the ship blown up"),
        ("defeatdarthnihilus", 99, "k_nihilus_ud (852nih): the lord defeated"),
    ],
    "finals": {
        "852NIH_Nihilus_Dead": (1, True, "a_start_ending (852nih); dialog 222tel's start E3 in 851nih and the trigger "
                                         "tr_852mand read it"),
        "851NIH_Bomb_Ravager": (3, True, "the order is fixed by dialog 851dem: the third charge (E7, then R10 / R11 / "
                                         "R12 a_fire851expdlg) sets 1, the core from the missile bay (851mis R3) sets "
                                         "2, and the fourth charge (E8, reached from R2 only once local 32 is set) "
                                         "sets 3, its last writer; 222tel's start E3 and 852nih R72 need more than 2"),
        "851NIH_Missile_Bay": (2, True, "dialog 851mis R3, its last writer (851com E2 sets 1 before); the core it "
                                        "frees is the fourth charge, so every run passes it"),
        "851NIH_BOMBSITE": (4, False, "the bomb-site triggers tr_851demone..four set 1..4 on entering each site, so "
                                      "the value is the site entered last; whether the sites can only be reached in "
                                      "that order was not worked out"),
        "852NIH_VisasSacrifice": (None, False, "1 only when slot 9 offers her life (dialog 852nih E20), a choice the "
                                               "full run does not take"),
        "000_Visas_Dead": (None, False, "1 only after the sacrifice (a_start_ending); read by the last chapter's "
                                        "dialog 904kreia (R159 / R160 / R161)"),
        "907MAL_CUTSCENE": (2, True, "a_escape_851 (101PER_Revan_End 1) or 205tel's a_901jump: 907mal's entry "
                                     "script k_907_enter plays the scene of cutscene 2 (dialog krecut1)"),
    },
    "party_note": "slot 9 is forced into the party in 222tel and taken out for the fight on the bridge (a_nihilus|14: "
                  "RemovePartyMember 9, SetNPCSelectability 9 FALSE). She is lost for good only if she sacrifices "
                  "herself (dialog 852nih E20, then 852sacri R14 a_sacrifice|3: RemoveAvailableNPC 9, "
                  "000_Visas_Dead 1), which this milestone does not take",
    "next": {"from": ("851nih", "a_escape_851|0,0,0,0,0,"), "target": "205tel",
             "note": "a_escape_851 (dialog 222tel R5): movie MalMov05, then StartNewModule 205TEL when 101PER_Revan_End "
                     "is not 1 (Peragus's answer); 205tel's dialog carthend ends with a_901jump (movies TelMov02, "
                     "HypMov01, MalMov07, MalMov08; 907MAL_CUTSCENE 2; StartNewModule 907MAL). When 101PER_Revan_End "
                     "is 1 the same script plays those movies itself and moves straight to 907MAL"},
    "credits_fixed": [],
    "xp": {"modules": ["851nih", "852nih"], "maybe": False, "extra": [],
           "endings": {"destroyravager": 99, "defeatdarthnihilus": 99}},
}
