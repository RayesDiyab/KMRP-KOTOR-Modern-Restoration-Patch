"""KotOR 2, Onderon: Iziz, the return to Dxun and its tomb, and the battle for the palace
(2026-10-23).

The chapter starts where Dxun ends (chapters_k2/dxun.py): the camp's shuttle lands in 501ond.
Its story, in order:

  1. Iziz, first visit (501ond, 502ond, 512ond, 503ond): the spaceport, the alibi for the
     contact (docalibi), the holodisks (cantinarats), the meeting in the cantina
     (master_palace 50), the escape (escape_merchant), the shuttle back to the camp
     (a_to_dxun, 501ond). 502OND_End_First is 2 from the cantina on (a_endgame|4).
  2. Back at the camp, 403dxn: dialog mand_cs2 E0 runs a_set_return, which stores the masters'
     count 000_Jedi_Found in 403DXN_Return_Trigger; the party leaves the moon on the Ebon Hawk.
  3. Another planet. The Ebon Hawk's cutscene table (k_003ebo_enter / a_next_scene, 003ebo)
     plays the message dialog t3kelbrn once 000_Jedi_Found is above 403DXN_Return_Trigger (or
     the trigger is 3), sets CUT_MSG_FROM_KELBORN so it plays once, and the dialog sets
     403DXN_Second_Visit 1 and master_palace 60 (light) or 65 (dark).
  4. Back at the camp: dialog kelborn E15 (master_palace 70, 500OND_Civil_War 1; E69 and
     master_palace 75 on the dark side), the second team's leader picked (403DXN_PARTY2_*),
     a_to_tomb to 410dxn, the tomb 411dxn (411DXN_Tempt by the leader's choice, a_leave_411:
     411DXN_Complete 1, back to 403dxn).
  5. The shuttle again (a_to_iziz2 with 411DXN_Complete set: OndMov07, 511ond), the square,
     the sky ramp (504ond, the turret 505ond), the palace (506ond): deadline, the end with the
     queen (light) or the general (dark), and a_end_game, which flies the party to 401dxn.

Steps 2 to 4 run in 003ebo, 403dxn, 410dxn and 411dxn, which build.py gives to other
chapters: they are listed in "critical" by their own modules (milestone.py checks them there
since 2026-10-23), and the values they leave are curated as finals without a writer in this
chapter's modules.

The civil war's sides: the light side stays with the queen (500OND_Civil_War 2, 506OND_End 1);
the dark side takes the general's offer in the cantina (dialog tobin R38, a_endgame|8:
500OND_DarkSide_Iziz 1), kills the master in the palace (000_Kavar_Dead 1) and ends with
500OND_Civil_War 3 and 506OND_End 2. Later chapters read all four (see the dark block).

The masters' count 000_Jedi_Found is shared by the four planets; this chapter raises it by 1
("increments"), never sets it. IDs only.
"""
PLANET = "Onderon"

_JOURNAL_BOTH = [
    ("escape_merchant", 90, "k_501_enter (501ond) on the return to the spaceport (502OND_End_First 2)"),
    ("docalibi", 99, "dialog dhagon E20 (512ond)"),
    ("cantinarats", 99, "dialog dhagon R16 (512ond)"),
    ("starportvisa", 91, "dialog cp_terly R2 (a_visa_quest|1, 502ond): the lowest of the second-visa endings "
                         "91 to 95, any of which is at or above it"),
]

CHAPTER = {
    "order": 5,
    "chapter_title": "Onderon: Iziz, the tomb on Dxun and the battle for the palace",
    "returnable": False,
    "returnable_note": "after the cantina 502OND_End_First is 2 and the camp's shuttle no longer flies (dialog "
                       "shuttle, 403dxn: start E1 needs it at 0); after the palace the party is flown to 401dxn "
                       "and the galaxy map lands every later visit there. Iziz is never entered again",
    "credits_side_only": {"talia": "light", "vaklu": "dark"},  # each side's ruler pays the war's reward
    "credits_fixed": [(-25, "the part bought from the vendor droid in 512ond (dialog mp_128 E23, a_alibi_s0d3: "
                             "TakeGoldFromCreature 25 on every path); docalibi 70 and 80 need it")],
    "critical": [
        ("501ond", "k_501_enter", "501ond OnEnter: 501_FIRST_ENTER; slot 2 joins here if the camp did not add him "
                                  "(501OND_Mand_Join 0); on the return from the cantina (502OND_End_First 2) "
                                  "journal escape_merchant 90"),
        ("501ond", "dialog 501_mand E1", "journal master_palace 20"),
        ("502ond", "dialog mp_riike E92", "journal master_palace 30, the alibi starts (docalibi 10 and 20)"),
        ("502ond", "dialog mp_riike E38", "journal master_palace 40: the contact is freed (502OND_Dhagon_Free, "
                                          "a_alibi_end2 on E44)"),
        ("512ond", "dialog dhagon E20", "journal docalibi 99"),
        ("512ond", "dialog dhagon R16", "journal cantinarats 99 (the holodisks handed over)"),
        ("512ond", "a_dhagon|0,0,0,0,0,", "dialog dhagon R13: 502OND_End_First 1, StartNewModule 503OND "
                                          "From_502OND_Dhagon (the meeting in the cantina)"),
        ("503ond", "dialog kavar E0", "journal master_palace 50 (a_endgame|1)"),
        ("503ond", "dialog kavar E20", "journal escape_merchant 10, lostjedi 50"),
        ("502ond", "dialog cp_replac E9", "journal escape_merchant 20 on the way back to the spaceport"),
        ("501ond", "a_to_dxun|0,0,0,0,0,", "dialog shuttle R2: OndMov06, StartNewModule 403DXN From_501OND"),
        ("403dxn", "a_set_return|0,0,0,0,0,", "dialog mand_cs2 E0 back at the camp: 403DXN_Return_Trigger = "
                                              "000_Jedi_Found; the party then leaves on the Ebon Hawk"),
        ("003ebo", "dialog t3kelbrn E0", "after another master is found: 403DXN_Second_Visit 1, master_palace 60 "
                                         "(E3, light) or 65 (E2, dark); CUT_MSG_FROM_KELBORN keeps it from replaying"),
        ("403dxn", "dialog kelborn E15", "master_palace 70, 500OND_Civil_War 1 (E69 and 75 on the dark side)"),
        ("403dxn", "a_to_tomb|2,0,0,0,0,", "dialog kelborn R56: StartNewModule 410DXN From_403DXN, the tomb"),
        ("411dxn", "a_leave_411|0,0,0,0,0,", "dialog xarga R5: 411DXN_Complete 1, StartNewModule 403DXN "
                                             "From_411DXN2"),
        ("403dxn", "a_to_iziz2|0,0,0,0,0,", "with 411DXN_Complete set: OndMov07, StartNewModule 511OND From_403DXN"),
        ("506ond", "dialog tobin E32", "journal deadline 10 in the palace"),
        ("506ond", "dialog ro_weed E7", "journal deadline 20"),
        ("506ond", "dialog termeast E3", "journal deadline 30"),
        ("506ond", "dialog ro_weed R17", "journal deadline 40 (or termeast R17 / E2)"),
        ("506ond", "dialog vaklu E40", "journal deadline 90, 500OND_Civil_War 2 (the light-side end of the war)"),
        ("506ond", "dialog vaklu E49", "journal deadline 90"),
        ("506ond", "dialog kavar E4", "journal master_palace 90"),
        ("506ond", "a_global_inc|1,0,0,0,0,000_jedi_found", "dialog kavar E7: the masters' count + 1"),
        ("506ond", "a_quest_set|57,0,0,0,0,lostjedi", "dialog kavar E8: lostjedi 57"),
        ("506ond", "dialog talia E0", "506OND_End 1"),
        ("506ond", "a_end_game|2,0,0,0,0,", "dialog talia E3: 10000 credits and the museum relics still in place"),
        ("506ond", "a_end_game|4,0,0,0,0,", "dialog talia R10: 506OND_End 1, PlayMovie OndMov06, StartNewModule "
                                            "401DXN From_506OND"),
    ],
    "journal": [
        ("master_palace", 90, "dialog kavar E4 (506ond); 95 is the dark-side end"),
        ("deadline", 90, "dialog vaklu E40 / E49 (506ond); 91 is the dark-side end"),
    ] + _JOURNAL_BOTH,
    "finals": {
        "501_FIRST_ENTER": (True, True, "k_501_enter on the first entry of 501ond"),
        "501OND_Mand_Join": (1, True, "k_501_enter sets 1 on the first entry of 501ond whenever it is still 0 (its "
                                      "only test; it adds slot 2 by template on the same branch), and nothing else "
                                      "writes it, so every run leaves 1. Only k_501_enter reads it"),
        "502OND_Dhagon_Free": (1, True, "a_alibi_end2 (dialog mp_riike E44): the alibi proven"),
        "502OND_End_First": (2, True, "a_dhagon sets 1 before the cantina, a_endgame case 4 (503ond) sets 2 when "
                                      "the meeting is broken up (read from a_endgame's own code; the call with "
                                      "parameter 4 is not in a conversation the tools list). Every run reaches 2: "
                                      "k_501_enter gives escape_merchant 90, which this chapter's journal holds, only "
                                      "at 2, and the shuttle back to the camp needs it. Read by k_501_enter, the "
                                      "shuttle dialogs (403dxn, 501ond), c_kelborn_mes and a_galaxymap (003ebo)"),
        "503OND_Cap_Murder": (8, False, "the alibi's state machine (a_alibi_start 1, a_alibi_set 2 to 7 in the "
                                        "dialogs bahima, al_droid, mp_128, kiph, nikko); trigger tr_alibi_end2 sets 8 "
                                        "when it is 7. Whether every docalibi ending crosses that trigger was not "
                                        "worked out"),
        "512OND_Visited": (1, True, "k_512_enter"),
        "500OND_Turret": (None, False, "a player's choice: the turret terminal in 505ond (dialog term_acc R8, "
                                       "a_505turret) sets 1, and a_check_turret on the transition To_506 (504ond) "
                                       "sets 2 only when it is still 0. Left unchanged"),
        "500OND_DarkSide_Iziz": (0, True, "light side: never set (its only writer is a_endgame case 8 / 10). The dark side sets 1 in the cantina (dialog tobin "
                                           "R38, a_endgame|8); read later by 221tel and 222tel (c_500darkside, "
                                           "k_221tel_enter, k_222tel_enter, dialog grenn)"),
        "500OND_Civil_War": (2, True, "dialog vaklu E40 (506ond), the light-side end of the war; 1 is set on the "
                                       "return to the camp (dialog kelborn E15 / E63, 403dxn); 3 is the dark side's. "
                                       "Read by dialog geeda (301nar) and 904kreia (904mal, == 3)"),
        "506OND_End": (1, True, "dialog talia E0 and a_end_game|4 (506ond); read by dialog ond_dip (204tel), "
                                "vrook (604dan) and 851tobin (851nih)"),
        "000_Kavar_Dead": (None, False, "light side: the master lives; the dark side sets 1 (dialog vaklu E4) and "
                                        "650dan reads it"),
        "403DXN_Return_Trigger": (None, False, "a_set_return (dialog mand_cs2 E0, 403dxn) copies 000_Jedi_Found when "
                                               "the party comes back from Iziz; only c_kelborn_mes reads it, and "
                                               "CUT_MSG_FROM_KELBORN keeps the message from playing again"),
        "CUT_MSG_FROM_KELBORN": (True, True, "the Ebon Hawk's cutscene table (k_003ebo_enter / a_next_scene, 003ebo, "
                                             "read from their disassembly) plays dialog t3kelbrn when the flag is "
                                             "FALSE, slot 8 is available, 502OND_End_First is set and "
                                             "403DXN_Return_Trigger is 3 or below 000_Jedi_Found, and sets the flag "
                                             "as it does. t3kelbrn is the only writer of 403DXN_Second_Visit, which "
                                             "403dxn's scripts need for the second visit, so every run that finishes "
                                             "this chapter has played it"),
        "403DXN_Second_Visit": (1, True, "dialog t3kelbrn E0 (003ebo), the message that calls the party back"),
        "411DXN_Complete": (1, True, "a_leave_411 (dialog xarga R5, 411dxn) after the tomb; a_to_iziz2 then flies to "
                                     "511ond and the camp's scripts treat the tomb as done"),
        "411DXN_Tempt": (1, True, "a_temptation|0 (dialog ritlead R25, 411dxn, the light reply: a_lighthigh): the "
                                  "tomb team's leader refuses; "
                                   "2 is a_temptation|1 (R20). The party's own dialogs (chitin) and c_baodur_tempt "
                                   "read it"),
        "411DXN_Tempt_NPC": (None, False, "the slot of the companion who led the tomb team (a_temptation: 0, 4, 7, 9 "
                                          "or 11); depends on the party, left unchanged"),
        # The Ebon Hawk's cutscene table (peragus.py). This chapter has entries of the ship that run it: leaving
        # the moon after the first visit to Iziz, and the entry where t3kelbrn plays (both before the tomb)
        "CUT_BAO_VS_MAND_1": (True, False, "slots 1 and 2 available, no other test: the table's last scene, so it "
                                           "plays on the first of those entries unless a scene earlier in the table "
                                           "ends the run with a_next_scene|1 on both (the attack on board, g0t0rem1 "
                                           "R2, attkreia, the second companion's scenes). Dialog mand1 changes nothing"),
        # the scenes due once slot 3 has joined (Nar Shaddaa, before this chapter in skip order): by now at
        # least those two entries came after it (see dxun.py)
        "CUT_G0T0_REMOTE_1": (True, True, "slots 3 and 1 available and 003EBO_G0t0_Remote 0: the first entry after "
                                          "slot 3 joins; dialog g0t0rem1 E3 sets 003EBO_G0t0_Remote 1"),
        "003EBO_G0t0_Remote": (1, True, "dialog g0t0rem1 E3 (003ebo); CUT_G0T0_REMOTE_2 (000_Jedi_Found above 2) is "
                                        "left to the game"),
        "CUT_BAO_G0T0_1": (True, True, "slots 1 and 3 available: on the same entry as g0t0rem1 or the next"),
        "003EBO_G0T0_BAO_2": (1, False, "the table sets 1 with CUT_BAO_G0T0_1 and k_003ebo_enter raises it to 2 on "
                                        "the next entry, which plays CUT_BAO_G0T0_2 (dialog bao_g0_2: a_adj_dex|1 on "
                                        "slot 3); a run has usually seen it by now, but the editor cannot raise slot "
                                        "3's dexterity, so 1 leaves that scene to the next entry"),
    },
    "master_met": [{"module": "506ond", "dialog": "kavar", "local": 60}],  # the flag his own conversation sets once he has taught
    "teach_form": True,  # kavar R13 > lrn_form (a_fire_learn|1): one a_give_form; the dark fight gives one too
    "increments": [
        ("000_Jedi_Found", 1, "dialog kavar (506ond): a_global_inc|1,0,0,0,0,000_Jedi_Found on E7 (light) or E88 "
                              "(dark), once per run. The masters' count shared by Nar Shaddaa, Onderon, Dantooine and "
                              "Korriban (dialog 650jedi in 650dan sets 4); read by k_sup_galaxymap, c_kelborn_mes "
                              "(003ebo), k_enter_605 (605dan), 262tel's scripts and the party's dialogs"),
    ],
    "items": [
        ("a_robe_21", 1, "a_end_game|2,0,0,0,0,", "506ond", "dialog talia E3: a museum relic, given unless the "
                                                           "player took it from its case (k_mus_treasure gives the "
                                                           "same item), so a full run holds it either way"),
        ("a_gloves_12", 1, "a_end_game|2,0,0,0,0,", "506ond", "as a_robe_21"),
        ("u_l_crys_18", 1, "a_end_game|2,0,0,0,0,", "506ond", "as a_robe_21"),
        ("u_l_colo_09", 1, "a_end_game|2,0,0,0,0,", "506ond", "as a_robe_21"),
    ],
    "dark": {
        "note": "the dark side sides with the general in the cantina (dialog tobin R35 escape_merchant 15, R38 "
                "master_palace 55 and a_endgame|8: 500OND_DarkSide_Iziz 1), works for him on the return to the camp "
                "(master_palace 65 and 75), kills the master in the palace (dialog kavar E87 to R112..R114, "
                "a_atkonend; dialog vaklu E4 sets 000_Kavar_Dead) and ends with the queen dead (dialog vaklu E29 "
                "master_palace 95 and 500OND_Civil_War 3, E30 deadline 91, R34 a_end_game|6: 506OND_End 2, 10000 "
                "credits, 401DXN From_506OND). The party does not change",
        "journal": [
            ("master_palace", 95, "dialog vaklu E29 (506ond)"),
            ("deadline", 91, "dialog vaklu E30 (506ond)"),
        ] + _JOURNAL_BOTH,
        "finals": {
            "500OND_DarkSide_Iziz": (1, True, "dialog tobin R38, a_endgame|8 (503ond)"),
            "500OND_Civil_War": (3, True, "dialog vaklu E29 (506ond); 904kreia (904mal) tests == 3"),
            "506OND_End": (2, True, "a_end_game|6 (dialog vaklu R34, 506ond)"),
            "000_Kavar_Dead": (1, True, "dialog vaklu E4 (506ond); 650dan's dialog 650jedi and its death scripts "
                                        "read it"),
            "411DXN_Tempt": (2, True, "a_temptation|1 (dialog ritlead R20, 411dxn, the dark reply: a_darkhigh): "
                                      "the tomb team's leader gives in"),
        },
        "party_recruit": [],
        "party_not_recruited": [],
        "party_remove": [],
        "next": {"from": ("506ond", "a_end_game|6,0,0,0,0,"), "target": "401dxn",
                 "note": "dialog vaklu R34: PlayMovie OndMov06, StartNewModule 401DXN From_506OND"},
    },
    "next": {"from": ("506ond", "a_end_game|4,0,0,0,0,"), "target": "401dxn",
             "note": "dialog talia R10: PlayMovie OndMov06, StartNewModule 401DXN From_506OND; the party walks to "
                     "the Ebon Hawk from there (trigger to_ebonhawk_custom, tr_ehawk_custom: 003EBO "
                     "WP_from_outside)"},
    "xp": {
        "modules": ["501ond", "502ond", "512ond", "503ond", "510ond", "410dxn", "411dxn", "511ond", "504ond",
                    "505ond", "506ond"],
        "maybe": False,
        "extra": [],
        "endings": {"master_palace": 90, "deadline": 90, "starportvisa": 91, "escape_merchant": 90},
    },
}
