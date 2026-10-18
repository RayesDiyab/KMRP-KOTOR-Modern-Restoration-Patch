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

Build under test: the controller patch, `KOTOR 1 Native Controller Mod + Xbox
HUD.kpatch`, alone or installed by KMRP's installer with Controller Support on.

## 0. Known-broken before you start

Do not spend time diagnosing these; they are measured and understood.

| | Context | Input | Expected |
| --- | --- | --- | --- |
| [ ] | Dialogue | B, X, Y, Back, LT, RT, Start | **nothing** — no handler in the dialogue dispatcher |
| [ ] | Dialogue | right stick | camera still moves |
| [ ] | Free look | A, B, D-pad | nothing; only Start works (the game's own event), R3 or LB exits |
| [ ] | Pazaak | buttons | only B, Y, LT and RT are registered in class 1, the four events its GUI dispatchers implement; A is not. **Never observed**, please note what responds |
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
| [ ] | Computer terminal | LB / RB | scrolls the terminal text | | FUNC |
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
| [ ] | Gameplay | Start | the Map opens (since issue #18; the in-game menu's Options until then) | | FUNC, played 2026-09-25 |
| [ ] | In-game menu | Start again | closes the menu, from the Map or any tab | | FUNC, played 2026-09-25 from the Map |
| [ ] | In-game menu | B | back to the world | | FUNC [auto] |
| [ ] | Gameplay | LB / RB | previous / next target | | FUNC |
| [ ] | Gameplay | LT | the next living party member | | FUNC |
| [ ] | Gameplay | RT | pause, and again to continue | | FUNC |
| [ ] | Gameplay | Back | the Solo Mode question; A on OK turns it on, A on Cancel or B does not | | FUNC, played 2026-09-24 |
| [ ] | Gameplay | D-pad Left / Right, then Up / Down, then A | walks the action bar's slots, cycles a slot's actions, uses the slot and keeps it; B lets go | | FUNC, A played 2026-09-25 |
| [ ] | Combat | X, Y | X disengages, Y takes the last action off the queue, each only while its button is drawn | | FUNC |
| [ ] | Gameplay | L3 | weapons flourish | | FUNC [auto] |
| [ ] | Gameplay | R3 | free look on; R3 again, off | | FUNC [auto] |
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
| [ ] | Inventory, Equipment | LB / RB | **nothing**: they carry no menu event since 2026-09-14 | | FUNC |
| [ ] | Inventory, Equipment | right stick up / down | scrolls the item's description | | FUNC |
| [ ] | Equipment | D-pad between slots and list | transitions make sense | | **FEEL** |
| [ ] | Abilities, Character, Equipment, Inventory | R3 | the next party member, with the cue between the portraits | | FUNC, cue played 2026-09-24 |
| [ ] | Character | X | Scripts | | FUNC |
| [ ] | Character, a level to take | A, Y | Level Up, Auto Level Up; the D-pad moves no focus on this screen | | FUNC, seen 2026-09-26 and 2026-09-28 |
| [ ] | Abilities | X | the next of Skills / Powers / Feats | | FUNC |
| [ ] | Abilities | D-pad | engine's own navigation, not KMRP's | | FUNC |
| [ ] | Journal | X | sorts | | FUNC |
| [ ] | Journal | Y | quest selection | | FUNC |
| [ ] | Journal | Back | the only screen where Back does anything | | FUNC |
| [ ] | Map | X | transit | | FUNC |
| [ ] | Map | D-pad | engine's own map navigation | | FUNC |
| [ ] | Messages | X | clears | | FUNC |
| [ ] | Options | D-pad + A | can you reach and change a setting | | FUNC |

## 5. Save / Load

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Save/Load | D-pad | moves through the save list | | FUNC |
| [ ] | Save/Load | LB / RB | **nothing** (this row said "list scrolls"; they carry no menu event since 2026-09-14) | | FUNC |
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
| [ ] | Pazaak game | B, Y, LT, RT are registered (class 1); A is not. On the wager, the D-pad lowers and raises it and A wagers | |
| [ ] | Solo mode query | B should dismiss it | |
| [ ] | Any cutscene | A or Start skips it when the game allows; nothing else | |

In this table "LB/RB" was listed for the screens with a list. They carry no menu
event since 2026-09-14; try the right stick for a description instead. On the
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
`debug-logs` on and keep `kmrp-layout-lifecycle.log`.

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
| [ ] | Undo action (Y's row) given RB | look at the rows | Undo action in RB's row with a yellow dot; Next target waits in Y's row, orange, with an orange "?"; the help line names Next target in orange; Save grey | | FUNC |
| [ ] | The same | X | nothing is saved while an action waits | | FUNC |
| [ ] | The same, Y's row | A, then Y | Next target on Y; nothing waits; Save works | | FUNC |
| [ ] | Remapping | Y | Default: the default layout back on screen, not yet saved | | FUNC |
| [ ] | Remapping, a complete change | X | saved: `kmrp-controller.ini` has `[Controller Remap]` with ten keys | | FUNC |
| [ ] | Remapping, nothing unsaved | B | back to the view | | FUNC |
| [ ] | Remapping, a change not saved | B | the "Unsaved Changes" box, (A) Discard and (B) Cancel | | FUNC |
| [ ] | Unsaved Changes | B | back to remapping, the changes kept | | FUNC |
| [ ] | Unsaved Changes | A | back to the view, showing the saved layout | | FUNC |
| [ ] | The view after a saved remap | look | the moved rows carry dots; the padlocks on the sticks, the D-pad, Start and Back | | FUNC |
| [ ] | Any state | switch between the pad and the mouse | the pad glyphs appear and disappear; nothing else moves | | FUNC |
| [ ] | PlayStation, Switch or Steam Deck pad | the whole of 9a | that family's glyphs in the footer, the prompt and the box | | FUNC |
| [ ] | Leaving the screen | `kmrp-layout-lifecycle.log` | no `bind-failed`; `created == destroyed` | | FUNC |

### 9b. In play, with a saved remap

Save a layout with Undo action on RB and Next target on Y, and one with Pause on LB
and Previous target on RT, then play.

| | Context | Input | Expected | P/F | Kind |
| --- | --- | --- | --- | --- | --- |
| [ ] | Combat, an action queued | RB | the last queued action comes off the queue (Undo action) | | FUNC |
| [ ] | Gameplay | Y | the next target (Next target) | | FUNC |
| [ ] | Gameplay | LB | pauses, and again to continue | | FUNC |
| [ ] | Gameplay | RT | the previous target | | FUNC |
| [ ] | In-game menu | LT, RT | still the previous and next tab: menus keep every button | | FUNC |
| [ ] | In-game menu | Y, X, A, B | each does what it does on that screen without a remap | | FUNC |
| [ ] | Dialogue, Pazaak, swoop, turret | the remapped buttons | as without a remap | | FUNC |
| [ ] | Gameplay | hold RB (Undo action), open a menu with Start, release RB | nothing sticks; the next RB in the menu is RB | | FUNC |
| [ ] | Combat | look at the HUD | the cue beside the combat buttons shows RB for Undo action, X still for Disengage | | FUNC |
| [ ] | Combat, Xbox-style HUD | look at the combat-mode message | the button of Release bar (B unless moved) | | FUNC |
| [ ] | Paused, Xbox-style HUD, Pause on LB | look at the pause notice | "PAUSED. PRESS [LB] TO CONTINUE" | | FUNC |
| [ ] | Paused, Pause on LB | move the mouse, then back to the pad | the PC's pause box is the game's own, and the Xbox one comes back (a fault found from the code and fixed before it was run: [`controller-layout.md`](controller-layout.md), "Limits") | | FUNC |
| [ ] | Restart the game | play | the saved layout is still in force | | FUNC |
| [ ] | A duplicate value written into `[Controller Remap]` by hand | start the game | the default layout, in play and on the screen | | FUNC |
| [ ] | KMRP's installer | Restore Original, then look at `kmrp-controller.ini` | the file and its `[Controller Remap]` are still there | | FUNC |
