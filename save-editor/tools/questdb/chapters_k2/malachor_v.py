"""KotOR 2, Malachor V: the end of the game (curated 2026-10-23).

Worked out from the game's scripts and conversations (scanmod.py, showscript.py, dlgnode.py of
the k2kit, and the dialogs' EndConversation fields). IDs only: no names or text from the game
(KMRP rule, 2026-10-23); people are named by slot or tag.

The route: the Ravager chapter ends in 205tel (dialog carthend, EndConversation a_901jump) or, when
101PER_Revan_End is 1, in a_escape_851 itself; both set 907MAL_CUTSCENE 2 and move to 907MAL.
  907mal  a cutscene copy of the academy's core: k_907_enter with 907MAL_CUTSCENE 2 plays dialog
          krecut1, whose E13 a_kreiacut|7 moves on to 901MAL. (Cutscenes 0 and 1, dialogs kreiaend
          and sioncut1, end in StartNewModule 000test, a module that does not exist; nothing sets
          907MAL_CUTSCENE to 0 or 1 on the way here, so they are leftovers.)
  901mal  the crash site; slot 7 and slot 10's hunter meet (dialog 901mira, a_mira_cs|2 spawns the
          hunter as an enemy).
  902mal  slot 7 fights the hunter (dialog 902mira: E7 sets 101PER_Kreia_Res1 5, E6 a_mira|6 sets
          MAL_TURNINTO_REMOTE and moves to 901MAL wp_remote_start). If the hunter wins
          (k_hanharr_ud) slot 7 is lost (RemoveAvailableNPC 7, 000_Mira_Dead 1). A run without slot
          7 (the dark side, which has slot 10 instead) gets dialog flank, E5 a_flank_cs|5, with the
          same move.
  901mal  as the remote: k_901mal_enter (MAL_TURNINTO_REMOTE) removes slot 1 for good
          (RemoveAvailableNPC 1) and puts the remote object in slot 1 (AddAvailableNPCByObject);
          dialog 901bao E0 (a_sensor_cs|0: 901MAL_REMOTE 1, journal massshadowgenerator 10); the
          consoles (901MAL_Mass_Shadow); the trigger TO_902MAL.
  902mal  the last drive core: dialog sensorfi (R38 journal massshadowgenerator 85: slot 3 takes
          the remote), E40 a_sensor_end|0: movie MalMov09, StartNewModule 903MAL From_902MAL.
  903mal  the academy: tr_sionenter makes slot 1 unselectable and clears MAL_TURNINTO_REMOTE;
          the companions' scenes (903atton, 903hand, 903kreia); the side halls 905mal and 906mal
          (dialog 903sion); the trigger TO_904MAL.
  904mal  the core and the last fight (dialog 904kreia: 904MAL_Kreia_Battle 1, 2, 3); after it E108
          leads to E109 (a_playgoodmovie, the light ending) or, with c_dark, E110 (a_playdarkmovie,
          the dark ending); R112 a_end_game: GBL_GAME_COMPLETE (1 the first light ending, 2 the
          first dark one, 3 both, by G_PC_Align_Val > 49), UnlockAllSongs, EndGame(0). The game ends:
          there is no StartNewModule after it.

The milestone leaves the player at the core's door (904mal FROM_903MAL) with the last fight and the
ending still to play: no module follows EndGame, and setting the fight's values
(904MAL_Kreia_Battle, GBL_GAME_COMPLETE) would make a_end_game count a second completion.
"""
PLANET = "Malachor V"

CHAPTER = {
    "order": 10,
    "chapter_title": "Malachor V: the academy and the end of the game",
    "returnable": False,
    "returnable_note": "the game ends in 904mal; 907mal is a cutscene module and 901mal / 902mal are left for good "
                       "once the remote's sequence is done",
    "critical": [
        ("205tel", "dialog carthend E0", "the admiral's farewell (Telos's module); EndConversation a_901jump: "
                                         "907MAL_CUTSCENE 2, StartNewModule 907MAL"),
        ("907mal", "k_907_enter", "907MAL_CUTSCENE 2: dialog krecut1"),
        ("907mal", "a_kreiacut|7,0,0,0,0,", "dialog krecut1 E13: StartNewModule 901MAL"),
        ("901mal", "a_mira_cs|2,0,0,0,0,", "dialog 901mira: slot 10's hunter appears"),
        ("902mal", "dialog 902mira E7", "slot 7 beats the hunter: 101PER_Kreia_Res1 5"),
        ("902mal", "a_mira|6,0,0,0,0,", "dialog 902mira E6: MAL_TURNINTO_REMOTE, StartNewModule 901MAL "
                                        "wp_remote_start"),
        ("901mal", "k_901mal_enter", "as the remote: RemoveAvailableNPC 1, the remote object in slot 1"),
        ("901mal", "a_sensor_cs|0,0,0,0,0,", "dialog 901bao E0: 901MAL_REMOTE 1, journal massshadowgenerator 10"),
        ("902mal", "dialog sensorfi R38", "journal massshadowgenerator 85: slot 3 takes the remote"),
        ("902mal", "a_sensor_end|0,0,0,0,0,", "dialog sensorfi E40: movie MalMov09, StartNewModule 903MAL"),
        ("903mal", "tr_sionenter", "slot 1 unselectable, MAL_TURNINTO_REMOTE FALSE"),
        ("904mal", "dialog 904kreia E109", "after the last fight: the light ending's movie (a_playgoodmovie)"),
        ("904mal", "a_end_game|0,0,0,0,0,", "dialog 904kreia R112: GBL_GAME_COMPLETE, EndGame(0)"),
    ],
    "journal": [
        ("massshadowgenerator", 85, "dialog sensorfi R38 (902mal): the remote's task done and the remote taken"),
    ],
    "finals": {
        "907MAL_CUTSCENE": (2, True, "a_901jump (205tel) or a_escape_851 (851nih) before 907mal is entered"),
        "MAL_TURNINTO_REMOTE": (False, True, "a_mira|6 / a_flank_cs|5 set TRUE (902mal), tr_sionenter (903mal) sets "
                                             "FALSE again"),
        "901MAL_REMOTE": (1, True, "a_sensor_cs|0 (dialog 901bao E0, 901mal)"),
        "101PER_Kreia_Res1": (5, True, "dialog 902mira E7 (902mal), when slot 7 beats the hunter: E7 is the "
                                       "dialog's first start without a condition (E20 only once talked to), so the "
                                       "first talk always passes it; no other writer. Read by dialog 904kreia (R152 / "
                                       "R153)"),
        "904MAL_Kreia_Battle": (None, False, "set by the last fight (dialog 904kreia E40 / E97 / E105: 1, 2, 3); left "
                                             "unset so the fight plays when the player walks in"),
        "GBL_GAME_COMPLETE": (None, False, "a_end_game sets 1 (first light ending), 2 (first dark ending) or 3 (both); "
                                           "left unset: the player has not seen the ending yet"),
        "000_Mira_Dead": (None, False, "1 only when slot 10's hunter wins the fight in 902mal (k_hanharr_ud)"),
    },
    "party_remove": [
        (1, "k_901mal_enter", "901mal", True,
         "on entering 901mal as the remote (MAL_TURNINTO_REMOTE): RemoveAvailableNPC(1); the game then puts the "
         "remote object in slot 1 (AddAvailableNPCByObject), which 903mal's tr_sionenter makes unselectable"),
    ],
    "party_note": "slot 7 is lost (RemoveAvailableNPC 7, 000_Mira_Dead 1) only if slot 10's hunter wins in 902mal "
                  "(k_hanharr_ud), which a full run does not do. The companions' later scenes in 903mal and 904mal "
                  "call no party function",
    "dark": {
        "note": "the dark side: the run has slot 10 instead of slot 7 (Nar Shaddaa's dark block), so 902mal has no "
                "fight between them; dialog flank E5 (a_flank_cs|5, when slot 7 is not available) sets "
                "MAL_TURNINTO_REMOTE and moves to 901MAL as on the light side. After the last fight 904kreia E108 "
                "takes E110 (c_dark: a_playdarkmovie, the dark ending) and R112 a_end_game ends the game the same way "
                "(GBL_GAME_COMPLETE 2 the first time, by G_PC_Align_Val <= 49). The route and the journal are the "
                "same as on the light side",
        "journal": [
            ("massshadowgenerator", 85, "dialog sensorfi R38 (902mal)"),
        ],
        "finals": {
            "101PER_Kreia_Res1": (None, False, "set only by dialog 902mira E7, which a run without slot 7 never plays"),
        },
    },
    "next": {"fixed": {"module": "904mal", "waypoint": "FROM_903MAL", "movies": [],
                       "by": "transition trigger TO_904MAL", "in": "903mal",
                       "note": "the core's entrance: the last fight and the ending (dialog 904kreia, R112 a_end_game, "
                               "EndGame(0)) are left to play. The game has no module after its end"}},
    "credits_fixed": [],
    "xp": {"modules": ["901mal", "902mal", "903mal", "905mal", "906mal", "904mal"], "maybe": False, "extra": [],
           "endings": {"massshadowgenerator": 85}},
}
