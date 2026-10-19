# Physical controller playtest checklist

For a real pad. Ordered so the things most likely to be broken come first, and
so you are not walking across the galaxy between tests.

Two kinds of row:

* **FUNC** — it either works or it does not. A failure is a bug.
* **FEEL** — it works; the question is whether it is pleasant. Your answer is
  the specification.

Automation has already verified everything marked **[auto]**; those rows are
there to catch a real pad behaving differently from a virtual one, so skim them
rather than dwell.

---

## Physical QA result — 2026-09-25

Reported working at 3440x1440 on the install made by the installer `4C02A277…`
(the game folder's `swkotor.exe.kotor-ui-patch.json` and `KMRP.log`). The
later builds of that day -- X and Y in combat, the dialogue A at the end of the
reply, the combat message, the update check -- were not installed and are not
covered.

| Verified working |
| --- |
| Rumble: four pad tests on an Xbox pad, judged right after the fourth; what they covered is in `docs/controller-rumble.md` |
| The action bar keeps focus after A, for repeated attacks (issue #17); B's release was not separately reported |
| Start opens the Map and closes it again (issue #18) |
| Text is sharp (issue #16, at the second reporter's resolution) |
| No white flash when switching party members (issue #14), with the driver resolving Prefer native from the game's own NVIDIA profile, not from a KMRP write |
| K1 Cutscenes Rescaled renders correctly, where it used to render wrongly, and skipping a movie never minimises the game (issue #6) |
| Solo Mode prompt: A on OK turns it on, A on Cancel does not (again; first 2026-09-24) |
| Sound Options navigation and B on the Movies screen (again; first 2026-09-24) |
| Quit Game's Yes/No box: the A beside the focused button |
| The resolution screen: A on Cancel cancels |
| In-game Options: Down from Close keeps a focus |
| Switching to mouse or keyboard clears the badges on every screen, not only the one in front |

**Superseded rows, 2026-10-19 (issue 49).** "Start opens the Map and closes it
again" above, and "The R3 party-switch cue" in the 2026-09-24 result below, were
true when they were played. Since 2026-10-19 the controller uses the original Xbox
game's layout: Start in the world reopens the in-game menu on the screen it last
showed (it still closes it), RB switches the party member on the four party screens
and the cue there shows RB. Neither has been played since; the rows that check them
are in sections 2 and 4.

## Physical QA result — 2026-09-24

Reported working on a real pad at 3440x1440, from the installer built that day
(`ECA3DE4B…`). Each is also marked play-tested in its `CHANGELOG.md` entry.

| Verified working on a real pad |
| --- |
| Loading a save from the in-game menu after one loaded from the main menu -- the crash is gone |
| Solo Mode prompt: A on OK turns it on, A on Cancel does not |
| The R3 party-switch cue, between the portraits (3440x1440 places it there; the right-of-portraits placement is used only at 4:3, 16:10 and 16:9) |
| Xbox LT and RT in the 360 art |
| B / Circle on the Movies screen's Close |
| Sound Options: Down from Movie Volume reaches Advanced Options |
| The installer's three independent switches |
| The swap-tabs icons |

**Superseded row below.** "Start opens the in-game menu" was true on 2026-09-08;
since issue #18 Start in the world opens the Map instead, which was
**verified in play on 2026-09-25**.

## Physical QA result — 2026-09-08

A full pass on a real pad. These are **human-verified PASS** and need no further
automation; the suite covers each of them, but a person has now confirmed the
real device behaves like the virtual one.

| Verified working on a real pad |
| --- |
| Intro / pre-rendered movie skipping |
| Menu navigation, general |
| Load Game |
| Controller button art appears dynamically |
| Left-stick movement feel |
| Walk / run proportional speed |
| Right-stick camera left and right, and its feel |
| Camera stops immediately on release |
| Mouse and controller usable together without fighting |
| L3 flourish (gameplay) |
| Start opens the in-game menu |
| LT / RT tab switching |
| Down from the tab strip enters content |
| A activates focused controls and items |

### Bugs the same pass found, and what happened to them

| Bug | Status |
| --- | --- |
| Left stick cycled the gameplay HUD action bar while walking | **FIXED** — only the D-pad reaches the HUD now |
| D-pad moved two list rows per tap in Equipment and Inventory | **FIXED** — the retained code and KMRP's own dispatch were both firing |
| Messages: could not move up into the message list | **FIXED** — zero-event list boxes are focusable in tab content |
| Journal / Active Quests: same | **FIXED** by the same change; not yet driven live |
| R3 free look crashed | **FIXED** — reproduced on a real pad, cause measured, fix played |
| Right stick does not scroll item descriptions | **FIXED** — dispatches the retained 0x39/0x3A pair to the screen's own panel |
| Missing art on Close / Show New Items / Use Item | **SHIPPED** later the same day as `[B] Close`, `[X] Show New Items`, `[A] Use Item`, after each button was pressed and measured; see "Tab-screen badges" in the prompt specification. (This row said "audited, not implemented -- all three are focus + A", the reasoning that measurement overturned.) |

### L3 — physically verified in gameplay, and now menu-safe

Physical QA passed L3 flourish. A later audit found it also fired in every menu
screen, which physical QA would not have noticed with the menu covering the
world. Fixed: the bridge now requires input class 0. L3 gameplay stays **PASS**;
"L3 does nothing in menus" is newly true and unverified by hand.

### R3 free look — reproduced on a real pad, and fixed

Six scenarios were driven with the virtual pad and none crashed: entering and
leaving while walking, with a HUD slot focused, twenty rapid presses, with the
camera held right, with the camera held **left** while R3 was down, and R3
interleaved with HUD D-pad presses.

Two stale-pointer paths introduced in the same session were removed anyway,
because both were real and either could plausibly fault during the class 0 -> 4
transition:

* `NativeActionBarK1` asked `KmrpActionBarStateK1` about the interface on every
  frame **before** checking the input class, so it walked the button array and
  the panel manager during transitions.
* the world-action guard called `KmrpActionBarFocusedK1(nullptr)`, whose null
  fallback used the vendor's cached `g_mainInterface` — a pointer that outlives
  the interface it names across a screen change.

Neither was the crash.

**The cause, measured under x32dbg attached to the running game.** A real pad
reproduced it on the first press where six virtual-pad scenarios never had.
`CExoRawInputInternal::GetLastState` faulted at `0x005E399B`,
`mov eax,[eax]` with `eax = 0`, called from `CExoInputInternal::GetEvents` at
`0x005E2968` with `(2, 0)` — the pad's device index and `DIJOFS_X`. It indexes
a per-pad state array as `[rawInput+0x30] + (deviceIndex - 2) * 0x74`
(`0x005E397F`-`0x005E3985`), and that base read 0: raising the device count
claimed a pad DirectInput never created, and nothing allocated its state
block. Free look is what reaches it because vanilla registers the analog stick
events in `ICPC` and `ICFreeLook` only, and the enter handler at `0x006216C7`
calls `CExoInput::ClearEvents`, emptying the buffered records the pad normally
speaks through.

`EnsurePadStateK1` now allocates that block beside the device count it raises.
**Played on a real pad: R3 enters free look, the right stick looks around, and
R3 leaves it, with no crash.**

The lesson worth keeping is that the virtual pad was not evidence of absence
here: it drove the buttons but never made the engine ask for raw device state.

---

## The checklist, as brought up to the code on 2026-10-08

Sections 0 to 8 were written on 2026-09-08. The rows whose expected result the
code has changed since were corrected on 2026-10-08, each from
`src/controller-native/K1NativeJoystick.cpp` and the documents named in the row;
none of the corrected rows was played again for it. Not in the checklist at all,
because they came later: rumble ([`controller-rumble.md`](controller-rumble.md)
has its own checklist), the Controller Layout screen
([`controller-layout.md`](controller-layout.md), "Manual acceptance test"), the
Xbox-style HUD ([`controller-xbox-hud.md`](controller-xbox-hud.md), "Tested and
not tested"), and PlayStation, Switch and Steam Deck pads. Button remapping, added
on 2026-10-18, has its pad checks in section 9.

**Brought up to issue 49 on 2026-10-19.** Since that day the controller uses the
original Xbox game's layout, with the Xbox's White and Black on LB and RB
(`K1_GAMEPLAY_ACTIONS`, `K1_BUTTONS` and `K1_BUTTON_REMAPS` in
`src/controller-native/K1NativeJoystick.cpp`; [`controller-layout.md`](controller-layout.md)
and `CHANGELOG.md`, `[Unreleased]`). The rows it changed are corrected in place, each
saying what it expected until then, and rows were added for what is new; section 10
holds Pazaak's table and the menu buttons that now do nothing. **None of these rows
has been played.**

Build under test: the controller patch, `KOTOR 1 Native Controller Mod + Xbox
HUD.kpatch`, alone or installed by KMRP's installer with Controller Support on.

## 0. Known-broken before you start

Do not spend time diagnosing these; they are measured and understood.

| | Context | Input | Expected |
| --- | --- | --- | --- |
| [ ] | Dialogue | B, X, Y, Back, LT, RT, Start | **nothing** — no handler in the dialogue dispatcher |
| [ ] | Dialogue | right stick | camera still moves |
| [ ] | Free look | A, B, D-pad | nothing; only Start works (the game's own event), R3 or LT exits (R3 or LB until 2026-10-19) |
| [ ] | Pazaak | buttons | only B, Y, LT and RT are registered in class 1, the four events its GUI dispatchers implement; A is not. **Never observed**, please note what responds. At the table itself the module answers X, A, Y and LB since 2026-10-19 (section 10) |
| [ ] | Cutscenes | buttons | A or Start skips a movie the game allows to be skipped; nothing else does anything (class 5 has no retained event) |

---

## 0b. The two things just fixed — please confirm on a real pad

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Gameplay, NPC targeted | A | starts the conversation | | FUNC |
| [ ] | Gameplay, container targeted | A | opens it | | FUNC |
| [ ] | Gameplay, door targeted | A | opens/uses it | | FUNC |
| [ ] | Gameplay, **nothing targeted** | A | **nothing happens** — could not be proven in automation | | FUNC |
| [ ] | Gameplay | A held down | one action, not a stream | | FUNC |
| [ ] | Gameplay | A, change target, A | acts on the new target, no stale action | | FUNC |
| [ ] | Dialogue | D-pad Up/Down | moves one reply per tap | | FUNC [auto] |
| [ ] | Dialogue | hold Up/Down | repeats, clamps at the ends | | **FEEL** — repeat timing |
| [ ] | Dialogue | A on a reply | chooses it | | FUNC [auto] |
| [ ] | Dialogue | A while a line is playing | skips the line | | FUNC |
| [ ] | Dialogue | left stick | does **not** navigate replies — should it? | | **FEEL** |
| [ ] | Computer terminal | LB / RB | scrolls the terminal text (since 2026-10-19 RB's scroll has a description of its own, because RB's menu event is Black) | | FUNC |
| [ ] | Dialogue | highlight visible from the sofa | | | **FEEL** |

## 0c. Swoop and turret controls

On 2026-10-16 the maintainer confirmed the swoop shift cue works and A, LT and RT
each fire in the turret in Steam's game. They also confirmed A fires in the
original Xbox game. The more specific scenarios below still need individual
confirmation; automated coverage is recorded in
[`controller-native-path.md`](controller-native-path.md), "Swoop racing and the turret".

| | Context | Input | Expected |
| --- | --- | --- | --- |
| [ ] | Swoop | left stick, A | steer proportionally; A starts thrusters and shifts; LT/RT do not shift |
| [ ] | Swoop shift cue | pad, then keyboard/mouse | confirm glyph at the shift point, Space when keyboard/mouse is active |
| [ ] | Swoop shift cue | controller family change, disconnect/reconnect | matching confirm glyph; Space while disconnected |
| [ ] | Turret | left stick | reticle moves in the pushed direction; check vertical aim and Reverse Minigame YAxis separately |
| [ ] | Turret | hold LT, pull RT; swap; repeat while holding A | each new press fires despite another held input |
| [ ] | Swoop/turret | Start, then Start | pause and resume; fire while paused does not carry into resume |

## 1. Gameplay — movement and camera

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Gameplay | left stick 25% | slow walk, proportional | | FUNC [auto] |
| [ ] | Gameplay | left stick 50% | faster, still not a run | | FUNC [auto] |
| [ ] | Gameplay | left stick 75% | faster again | | FUNC [auto] |
| [ ] | Gameplay | left stick 100% | full run | | FUNC [auto] |
| [ ] | Gameplay | partial diagonal | no faster than the same deflection straight | | FUNC [auto] |
| [ ] | Gameplay | full diagonal, all 4 quadrants | no speed boost; goes where you point | | FUNC [auto] |
| [ ] | Gameplay | stick released | stops immediately, no drift | | FUNC [auto] |
| [ ] | Gameplay | stick resting untouched 30s | character never moves | | **FEEL** — deadzone |
| [ ] | Gameplay | very small deflections | where movement starts feels right | | **FEEL** — deadzone |
| [ ] | Gameplay | right stick left/right | camera turns the way you push | | FUNC [auto] |
| [ ] | Gameplay | right stick speed | turn rate comfortable, not sickening | | **FEEL** — sensitivity |
| [ ] | Gameplay | right stick up/down | **nothing** — there is no vertical axis | | FUNC |

## 2. Gameplay — the bound buttons

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Gameplay | Start | the in-game menu opens on the screen it last showed, or the Map when that cannot be read; what it opens on before the menu has been shown once was not looked at (since 2026-10-19, the Xbox's Start; the Map from issue #18 until then, the in-game menu's Options before that) | | FUNC; the Map played 2026-09-25, the last screen not yet |
| [ ] | In-game menu, moved to another tab with RT | Start, then Start again | closes the menu, then reopens it on that tab | | FUNC |
| [ ] | In-game menu | Start again | closes the menu, from the Map or any tab | | FUNC, played 2026-09-25 from the Map |
| [ ] | In-game menu | B | back to the world | | FUNC [auto] |
| [ ] | Gameplay | LT / RT | previous / next target (LB / RB until 2026-10-19) | | FUNC |
| [ ] | Gameplay | RB | the next living party member (LT until 2026-10-19) | | FUNC |
| [ ] | Gameplay | LB | pause, and again to continue (RT until 2026-10-19) | | FUNC |
| [ ] | Paused, Xbox-style HUD | look at the pause notice | "PAUSED. PRESS [LB] TO CONTINUE", LB in the same drawing as the other cues (until 2026-10-19 RT, in a lighter drawing of the trigger) | | FUNC |
| [ ] | Gameplay | Back | the Solo Mode question; A on OK turns it on, A on Cancel or B does not | | FUNC, played 2026-09-24 |
| [ ] | Gameplay | D-pad Left / Right, then Up / Down, then A | walks the action bar's slots, cycles a slot's actions, uses the slot and keeps it; B lets go | | FUNC, A played 2026-09-25 |
| [ ] | Gameplay | X, on a target and then on a focused action-bar slot | the same as A each time: the target's action, then the slot's (since 2026-10-19; until then X disengaged in combat and did nothing else) | | FUNC |
| [ ] | Combat | B, Y | with no action-bar slot focused B disengages; Y takes the last action off the queue; each only while its button is drawn, with either HUD (until 2026-10-19 X disengaged, and B only with the Xbox-style HUD) | | FUNC |
| [ ] | Gameplay, not in combat | Y | weapons flourish, as L3 (since 2026-10-19) | | FUNC |
| [ ] | Gameplay | L3 | weapons flourish | | FUNC [auto] |
| [ ] | Gameplay | R3 | free look on; R3 again, off | | FUNC [auto] |
| [ ] | Free look | LT | leaves free look (LB until 2026-10-19) | | FUNC |
| [ ] | Gameplay | **L3 then R3 immediately** | free look refuses for 4–7s, then works | | FUNC — known |
| [ ] | Gameplay | L3 with no weapon drawn | nothing bad happens | | FUNC |
| [ ] | Free look | left stick | does the camera behave sensibly? | | **FEEL** |

## 3. Main menu

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Main menu | D-pad Down x5 | steps through all five entries in reading order | | FUNC [auto] |
| [ ] | Main menu | D-pad Down at the last | wraps to the first | | FUNC [auto] |
| [ ] | Main menu | D-pad Up at the first | wraps to the last | | FUNC [auto] |
| [ ] | Main menu | **D-pad Left / Right** | currently moves *vertically* | | **FEEL** — decide: move or stay |
| [ ] | Main menu | left stick | navigates like the D-pad | | FUNC [auto] |
| [ ] | Main menu | hold Down | first step immediate, pause, then repeats | | **FEEL** — repeat timing |
| [ ] | Main menu | A | activates the highlighted entry | | FUNC |
| [ ] | Main menu | highlight visibility | can you see what is selected, at a glance, from the sofa? | | **FEEL** |

## 4. The 8-tab strip

Cycle: Equipment → Inventory → Character → Abilities → Messages → Journal → Map
→ Options.

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Any tab | RT x8 | returns to where you started | | FUNC [auto] |
| [ ] | Any tab | LT | steps back one tab | | FUNC [auto] |
| [ ] | Messages tab | tutorial box appears | LT/RT stop working until it clears | | FUNC — known |
| [ ] | Messages tab | any button while the box is up | note anything that dismisses it | | FUNC — **unknown, please observe** |
| [ ] | Each tab | D-pad, all four | focus moves somewhere sensible | | **FEEL** — spatial transitions |
| [ ] | Each tab | A | activates the focused control | | FUNC |
| [ ] | Each tab | B | closes to the world | | FUNC [auto] |

### Per-tab specifics

| | Tab | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Inventory | X | item filter changes | | FUNC [auto] |
| [ ] | Inventory, Equipment | LB | **nothing**: it carries no menu event since 2026-09-14 (this row said LB / RB until 2026-10-19; RB is the party row below) | | FUNC |
| [ ] | Inventory, Equipment | right stick up / down | scrolls the item's description | | FUNC |
| [ ] | Equipment | D-pad between slots and list | transitions make sense | | **FEEL** |
| [ ] | Abilities, Character, Equipment, Inventory | RB | the next party member, with an RB cue between the portraits, the Xbox Character screen's "(Black) Change Character" (R3 and an R3 cue until 2026-10-19) | | FUNC; the R3 cue played 2026-09-24, RB not yet |
| [ ] | Abilities, Character, Equipment, Inventory | R3 | **nothing** since 2026-10-19 | | FUNC |
| [ ] | Character | X | Scripts | | FUNC |
| [ ] | Character, a level to take | A, Y | Level Up, Auto Level Up; the D-pad moves no focus on this screen | | FUNC, seen 2026-09-26 and 2026-09-28 |
| [ ] | Abilities | X | the next of Skills / Powers / Feats | | FUNC |
| [ ] | Abilities | D-pad | engine's own navigation, not KMRP's | | FUNC |
| [ ] | Journal | X | the Quest Items list, its badge X (this row said "sorts" until 2026-10-19; the Journal's `0x29` is Quest Items) | | FUNC |
| [ ] | Journal | Y | switches between active and completed quests, its badge Y (this row said "quest selection"; until 2026-10-19 KMRP moved this to A) | | FUNC |
| [ ] | Journal | RB | the sort order, its badge RB, the Xbox's Black (Y until 2026-10-19, which KMRP moved it to from Back) | | FUNC |
| [ ] | Journal | Back | **nothing** since 2026-10-19 (this row said "the only screen where Back does anything") | | FUNC |
| [ ] | Map | X | transit | | FUNC |
| [ ] | Map | D-pad | engine's own map navigation | | FUNC |
| [ ] | Messages | X | clears | | FUNC |
| [ ] | Options | D-pad + A | can you reach and change a setting | | FUNC |

## 5. Save / Load

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Save/Load | D-pad | moves through the save list | | FUNC |
| [ ] | Save/Load | LB / RB | **nothing** (this row said "list scrolls"; they carry no menu event since 2026-09-14, except RB's Black, `0x2B`, since 2026-10-19, which only the Journal implements) | | FUNC |
| [ ] | Save/Load | A | loads or saves the highlighted slot | | FUNC |
| [ ] | Save/Load | **X** | **Delete — confirm the prompt appears before anything is destroyed** | | FUNC |
| [ ] | Save/Load | B | back | | FUNC |

## 6. Screens automation never reached

Everything here is **static-only**. Please note anything that does not respond.

| | Screen | Inputs to try | P/F |
| --- | --- | --- | --- |
| [ ] | Merchant / store | D-pad, A, B, X (buy/sell), LB/RB | |
| [ ] | Container / loot | D-pad, A (take), X (take all), B | |
| [ ] | Party select | D-pad, A, B | |
| [ ] | Level up | D-pad, A, B | |
| [ ] | Character creation — class select | D-pad, A, B, **LT/RT** | |
| [ ] | Character creation — name entry | D-pad, A, Y, B | |
| [ ] | Character creation — abilities | D-pad, A, Y, LB/RB | |
| [ ] | Options → Gameplay | D-pad, A, B, LB/RB | |
| [ ] | Options → Graphics | D-pad, A, B | |
| [ ] | Options → Resolution | D-pad, A, B | |
| [ ] | Options → Sound | D-pad, A, B, LB/RB | |
| [ ] | Options → Auto-pause | D-pad, A, B | |
| [ ] | Options → Feedback | D-pad, A, B, LB/RB | |
| [ ] | Key mappings | D-pad, A, B | |
| [ ] | Upgrade / workbench | D-pad, A, B, LB/RB | |
| [ ] | Pazaak setup | D-pad, A, B, Y, LT/RT | |
| [ ] | Pazaak game | B, Y, LT, RT are registered (class 1); A is not. On the wager, the D-pad lowers and raises it and A wagers. The table's own buttons since 2026-10-19: section 10 | |
| [ ] | Solo mode query | B should dismiss it | |
| [ ] | Any cutscene | A or Start skips it when the game allows; nothing else | |

In this table "LB/RB" was listed for the screens with a list. They carry no menu
event since 2026-09-14; try the right stick for a description instead. (Since
2026-10-19 RB sends the Xbox's Black, `0x2B`, which none of these screens
implements.) On the
settings screens Y presses Default, and Left and Right step a row's - and +
(2026-09-25). The store shows A, X and B on its three buttons since 2026-10-06,
not yet seen in play.

## 7. Device handoff and robustness

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Gameplay | keyboard, then pad | both keep working; prompts switch | | FUNC |
| [ ] | Gameplay | mouse, then pad | cursor hides when the pad is used | | FUNC |
| [ ] | Menu | mouse click, then D-pad | focus does not fight the cursor | | **FEEL** |
| [ ] | Gameplay | unplug the pad mid-run | character stops, no drift | | FUNC [auto] |
| [ ] | Gameplay | plug it back in | control resumes | | FUNC [auto] |
| [ ] | Any menu | mash A and B rapidly | nothing double-fires or gets stuck | | FUNC |
| [ ] | Any menu | mash the D-pad rapidly | focus keeps up, no runaway | | FUNC |
| [ ] | Any menu | hold a direction 5s | repeat is steady and stoppable | | **FEEL** — repeat timing |
| [ ] | Any menu | hold a direction and release | stops immediately | | FUNC |

## 8. The feel questions, gathered

These are the decisions only you can make. Everything else above is pass/fail.

| | Question | Current value |
| --- | --- | --- |
| [ ] | Camera turn speed | `K1_CAMERA_SPEED = 1.0`, a full keyboard turn at full deflection (14.0 until the camera was moved to `RotateCamera`: mouse pixels, for a field the camera does not read) |
| [ ] | Movement deadzone | radial 15% (`K1_STICK_DEADZONE`; 8% until a pad's left stick was measured resting at 9.6%); the camera's is 12% |
| [ ] | Menu repeat: delay before repeating | 400 ms |
| [ ] | Menu repeat: rate once repeating | 120 ms |
| [ ] | Stick-to-navigate push distance | engage 0.55, release 0.35 |
| [ ] | Should menus wrap top-to-bottom? | they do |
| [ ] | Should Left/Right move on a single column? | they do — you lean toward "stay" |
| [ ] | How strongly should focus prefer its own row/column? | penalty 6 |
| [ ] | Is L3 = Flourish worth a stick click? | provisional |
| [ ] | Physical D-pad orientation | mapping is inferred, not confirmed |

## 9. Button remapping (added 2026-10-18)

The Controller Layout screen (Options, Gameplay, Controller Layout) remaps A, B, X,
Y, LB, RB, LT, RT and the two stick clicks; how it works is in
[`controller-layout.md`](controller-layout.md), "Button remapping". On 2026-10-18 it
was run with mouse and keyboard only (scripted input, at 3440x1440 and 1920x1080).
**Every row below is untested**: there was no virtual pad on the machine (ViGEmBus is
not installed). Start each run from the default layout: Remap, Default, Save. Have
`debug-logs` on and keep `kmrp-layout-lifecycle.log` (in `KMRP\logs` in the game
folder since 2026-10-20; the game folder itself until then). The layout is saved in
`KMRP\controller.ini` since the same day, `kmrp-controller.ini` beside the game until
then.

*Since 2026-10-19* the default layout is the original Xbox game's (issue 49): A
Interact, B Disengage, X Add to queue, Y Undo or flourish, LB Pause, RB Switch ally,
LT Previous target, RT Next target, L3 Flourish, R3 Free look. The rows below are
written against it; where a row named an action or a button of the earlier defaults
it says so.

### 9a. On the screen

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Screen just opened (the view) | D-pad, A, Y | nothing: no row takes the focus, A and Y do nothing | | FUNC |
| [ ] | The view | X | Remap: the footer becomes (Y) Default, (X) Save, (B) Close, and LT's row is focused | | FUNC |
| [ ] | The view | B | leaves the screen | | FUNC |
| [ ] | Remapping | D-pad, all four | moves between the ten remappable rows only; never onto Default, Save, Close or a padlocked row | | FUNC |
| [ ] | Remapping | D-pad | the focused row's action turns yellow and the game's highlight frames the row | | **FEEL** |
| [ ] | Remapping, pad in use | look at the footer | "(A) Change button" between the hairline and the buttons, and the Y, X and B glyphs of your pad | | FUNC |
| [ ] | Remapping, a row focused | A | the prompt "Press the new button for ..." opens, blue border, the other rows faded | | FUNC |
| [ ] | The prompt | the A still held from opening it | does not count; only a new press does | | FUNC |
| [ ] | The prompt | LB, RB, LT, RT, L3, R3 in turn (one per prompt) | each is accepted: the action moves to that button's row | | FUNC |
| [ ] | The prompt | B | B is chosen (not cancel) | | FUNC |
| [ ] | The prompt | Back (View) | cancels; nothing changes | | FUNC |
| [ ] | The prompt | Start | expected from the code to cancel, like Back: **please note what happens** | | FUNC, unknown |
| [ ] | The prompt | D-pad | nothing: the focus stays on the row | | FUNC |
| [ ] | After a choice | keep the chosen button held | nothing else happens until it is released | | FUNC |
| [ ] | Undo or flourish (Y's row) given RB | look at the rows | Undo or flourish in RB's row with a yellow dot; Switch ally waits in Y's row, orange, with an orange "?"; the help line names Switch ally in orange; Save grey (Next target in place of Switch ally until 2026-10-19) | | FUNC |
| [ ] | The same | X | nothing is saved while an action waits | | FUNC |
| [ ] | The same, Y's row | A, then Y | Switch ally on Y; nothing waits; Save works | | FUNC |
| [ ] | Remapping | Y | Default: the default layout back on screen, not yet saved | | FUNC |
| [ ] | Remapping, a complete change | X | saved: `KMRP\controller.ini` (`kmrp-controller.ini` until 2026-10-20) has `[Controller Remap]` with `Layout=Xbox` and ten keys (no `Layout` line until 2026-10-19) | | FUNC |
| [ ] | The screen opened | look at the rows | the captions of the Xbox layout (since 2026-10-19): "Previous target / Prev tab", "Pause", "Next target / Next tab", "Switch ally / Menu action", "Undo or flourish / Menu action", "Add to queue / Menu action", "Disengage / Back", "Last menu / Close menu", none cut short | | FUNC |
| [ ] | Remapping, nothing unsaved | B | back to the view | | FUNC |
| [ ] | Remapping, a change not saved | B | the "Unsaved Changes" box, (A) Discard and (B) Cancel | | FUNC |
| [ ] | Unsaved Changes | B | back to remapping, the changes kept | | FUNC |
| [ ] | Unsaved Changes | A | back to the view, showing the saved layout | | FUNC |
| [ ] | The view after a saved remap | look | the moved rows carry dots; the padlocks on the sticks, the D-pad, Start and Back | | FUNC |
| [ ] | Any state | switch between the pad and the mouse | the pad glyphs appear and disappear; nothing else moves | | FUNC |
| [ ] | PlayStation, Switch or Steam Deck pad | the whole of 9a | that family's glyphs in the footer, the prompt and the box | | FUNC |
| [ ] | Leaving the screen | `KMRP\logs\kmrp-layout-lifecycle.log` | no `bind-failed`; `created == destroyed` | | FUNC |

### 9b. In play, with a saved remap

Save a layout with Undo or flourish on RB and Switch ally on Y, and one with Pause on
RT and Next target on LB, then play. (Until 2026-10-19 this read "Undo action on RB
and Next target on Y, and one with Pause on LB and Previous target on RT": the same
two trades on that day's defaults.)

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Combat, an action queued | RB | the last queued action comes off the queue (Undo or flourish) | | FUNC |
| [ ] | Gameplay | Y | the next living party member (Switch ally) | | FUNC |
| [ ] | Gameplay | RT | pauses, and again to continue | | FUNC |
| [ ] | Gameplay | LB | the next target | | FUNC |
| [ ] | In-game menu | LT, RT | still the previous and next tab: menus keep every button | | FUNC |
| [ ] | In-game menu | Y, X, A, B | each does what it does on that screen without a remap | | FUNC |
| [ ] | Dialogue, Pazaak, swoop, turret | the remapped buttons | as without a remap | | FUNC |
| [ ] | Gameplay | hold RB (Undo or flourish), open a menu with Start, release RB | nothing sticks; the next RB in the menu is RB | | FUNC |
| [ ] | Combat | look at the HUD | the cue beside the combat buttons shows RB for Undo or flourish, B still for Disengage (X until 2026-10-19) | | FUNC |
| [ ] | Combat, Xbox-style HUD | look at the combat-mode message | the button of Disengage, B unless moved (Release bar's until 2026-10-19, also B unless moved) | | FUNC |
| [ ] | Paused, Xbox-style HUD, Pause on RT | look at the pause notice | "PAUSED. PRESS [RT] TO CONTINUE", RT in the same drawing as the other cues (this row tested Pause on LB until 2026-10-19, when RT was Pause's default) | | FUNC |
| [ ] | Paused, Pause on RT | move the mouse, then back to the pad | the PC's pause box is the game's own, and the Xbox one comes back (a fault found from the code and fixed before it was run: [`controller-layout.md`](controller-layout.md), "Limits") | | FUNC |
| [ ] | Restart the game | play | the saved layout is still in force | | FUNC |
| [ ] | A duplicate value written into `[Controller Remap]` by hand | start the game | the default layout, in play and on the screen | | FUNC |
| [ ] | A layout saved before 2026-10-19 (no `Layout` line), or the line deleted by hand | start the game | the Xbox defaults, in play and on the screen; a Save then rewrites the whole section | | FUNC |
| [ ] | KMRP's installer | Restore Original, then look at `KMRP\controller.ini` (`kmrp-controller.ini` until 2026-10-20) | the file and its `[Controller Remap]` are still there | | FUNC |
| [ ] | A `kmrp-controller.ini` with a saved layout beside the game, from a build before 2026-10-20, and no `KMRP\controller.ini` (added 2026-10-20) | start the game | the file is now `KMRP\controller.ini`, none is left beside the game, and the saved layout is in force | | FUNC |

## 10. Pazaak's table and the menu buttons (added 2026-10-19)

Issue 49. Pazaak's table follows the Xbox game's footer, "(X) Play Hand Card, (White)
Flip Hand Card, (A) End Turn, (Y) Stand", with White on LB (`K1_BUTTON_REMAPS`,
`InstallPazaakTableK1` and `UpdatePazaakTableK1` in
`src/controller-native/K1NativeJoystick.cpp`). Read from the executable; no save the
harness loads reaches a table, and **none of this has been played**. Until
2026-10-19 A played the focused hand card (since 2026-10-11, issue 42), and End
Turn, Stand and the four flip buttons were places for the D-pad, pressed with A.

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Pazaak table, your turn, a hand card focused | X | the card is played, as a click on it does | | FUNC |
| [ ] | The same | A | End Turn, whatever holds focus; A never plays a card | | FUNC |
| [ ] | The same | Y | Stand | | FUNC |
| [ ] | A +/- hand card focused | LB | the card's sign flips, as its own flip button does | | FUNC |
| [ ] | Not your turn, or End Turn or Stand not on screen or disabled | A, Y | nothing | | FUNC |
| [ ] | The table | D-pad, all four | moves between the hand cards only; never onto End Turn, Stand or the four flip buttons | | FUNC |
| [ ] | The table, pad in use | look | an A badge on End Turn and a Y badge on Stand; the flip legend's icon is LB; an X and "Play Hand Card" on the row under the flip legend | | FUNC |
| [ ] | The same | look at the "Play Hand Card" line | does it stand somewhere sensible? Its place is a first guess, the flip legend's own rectangle moved down by its height, and nothing has been seen | | **FEEL** |
| [ ] | The table | move the mouse | the flip legend's own picture is back, and the "Play Hand Card" line and the badges are gone | | FUNC |
| [ ] | A second game after leaving the table | the rows above | the same; nothing left over from the first table | | FUNC |
| [ ] | Pazaak side-deck screen | Y, LT, RT | unchanged: its own Y adds a card, LT and RT switch lists | | FUNC |
| [ ] | Any menu | R3 | **nothing** (until 2026-10-19 it switched the party member on four screens) | | FUNC |
| [ ] | Any menu | Back | **nothing** (until 2026-10-19 it sent `0x2B`, which sorted the Journal) | | FUNC |
