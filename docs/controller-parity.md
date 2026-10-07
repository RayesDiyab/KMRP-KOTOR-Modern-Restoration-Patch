# Controller parity: the native path against Saul0097's module

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before
> editing this file.

**Kind: reference.** It describes what each of the two controller paths does
today. The narrative of how the native path was built is in
[`controller-native-path.md`](controller-native-path.md); what may be removed
once QA passes is in [`controller-handover-plan.md`](history/controller-handover-plan.md).

**What ships, checked on 2026-10-08:** only the native path. It is the controller
patch, `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch` (id `kmrp-controller`;
[`controller-standalone.md`](controller-standalone.md)), which KMRP installs as
its controller support since 2026-10-05. The legacy sources are compiled into its
module, and no patch installs `DispatchMenuInputK1`, so the legacy transport never
runs in a shipped game. The comparison below is kept as the evidence the native
path was built from; "legacy" is what Saul0097's module does when installed by
itself.

## What this compares, and where the claims come from

Two implementations are compiled into the same module binary:

| path | source | how input reaches the game |
| --- | --- | --- |
| **legacy** | `src/controller-native/vendor/K1XboxControls.cpp`, `vendor/K1XboxControlsXInput.cpp` (Saul0097's KPM Xbox Controls K1 1.2, as modified by KMRP) | reads XInput, **synthesises keystrokes** into the game's keyboard path |
| **native** | `src/controller-native/K1NativeJoystick.cpp` | feeds XInput into KOTOR's **own retained joystick pipeline**, as DirectInput records |

Every claim below is read out of those tracked sources, by the symbol named, or
out of `src/controller-native/kotor1.hooks.toml`. (Until 2026-09-24 this document
pointed at line numbers; all five had drifted, so it names symbols instead.) Nothing here is measured from the
executable; the byte-level evidence for the native events lives in
[`../reverse-engineering/retained-xbox-gui-events.md`](../reverse-engineering/retained-xbox-gui-events.md).
Only one path's input transport is active at a time: `PollXInputK1()` has exactly
one call site, in `DispatchMenuInputK1` (`vendor/K1XboxControls.cpp`), and that
hook is installed by neither shipped patch.
(`testing/controller/select_controller_path.py`, which dropped or kept it for
comparison, writes the install layout of before 2026-09-29 and has not been
brought up to the two patches.)

## Button parity

Legacy from `BUTTON_BINDINGS` in `vendor/K1XboxControlsXInput.cpp`. Native from
`K1_BUTTONS`, `K1_TRIGGERS`, `K1_DPAD`, `K1_STICK_CLICKS` and
`K1_GAMEPLAY_ACTIONS` in `K1NativeJoystick.cpp`.

The `Parity` column is judged **in gameplay**, because that is where the two
paths diverge: the legacy keys reach keymap actions, the native events reach
GUI panels, and the gameplay HUD implements only five of them.

| Input | Legacy sends | Native: menus / gameplay | Parity in gameplay |
| --- | --- | --- | --- |
| A | `Return` + `R` = ActionMenuQueue + DefaultAction | event `0x27` / the interaction bridge | equivalent |
| B | `Delete` = ActionMenuRemoveQ | event `0x28` / `0x28` | equivalent |
| X | `G` + `End` = STEALTH | event `0x29` / in combat, presses the HUD's Disengage button (since 2026-09-25); otherwise nothing | differs: no stealth on the pad |
| Y | `F` + `Home` = CancleCombat | event `0x2A` / in combat, removes the last queued action (since 2026-09-25); otherwise nothing | differs: cancelling combat is X's on the native path |
| LB | `Space` + `Insert` = Pause | nothing / `0x06` SelectPrev, and leaves free look | differs |
| RB | `Tab` = ChangeChar | nothing / `0x05` SelectNext | differs |
| LT | `Q` = SelectPrev | `0x35` previous screen / `0x09` ChangeChar | differs |
| RT | `E` = SelectNext | `0x36` next screen / `0x02` Pause | differs |
| Back | `V` = PartyActive | `0x2B` Black / `0x0A` PartyActive | equivalent |
| Start | `Escape` = GUI | in the in-game menu acts as B, closing it; elsewhere `0x0B` / the Map hotkey `0xD7` | **differs by design** (issue #18) |
| L3 | `X` = Flourish | nothing / flourish weapons (engine bridge) | equivalent |
| R3 | `CapsLock` = Freelook | on the four party screens, the next party member / free look, entered with `0x01`; a press in free look leaves it | equivalent |

*Corrected 2026-09-24:* this table showed LB, RB, LT, RT and Back as sending
only their GUI events, with nothing in gameplay, and Start as `0x0B` in both.
The gameplay verbs below have been bound since, Start became the Map key for
issue #18, and R3 gained the party switch and a second press to leave free
look. *Corrected 2026-10-08:* X and Y read "native does nothing in gameplay";
since 2026-09-25 they press the HUD's own Disengage and clear-one buttons while
those are drawn (`NativeActionBarK1`, `PressHudButtonK1`). The right stick's row
named `CSWCModule::AcclTurnCamera`; the module calls `CSWCModule::RotateCamera`
(`K1_ROTATE_CAMERA`, `0x00640090`).
| D-pad | arrow keys, as repeating taps | codes `0x384`/`0x388`/`0x38C`/`0x390` | see below |
| Left stick | `W`/`S`/`Z`/`C`, plus a walk modifier on `B` | the movement fields directly, proportional | native is strictly better |
| Right stick | `A`/`D` taps | `CSWCModule::RotateCamera` | native is strictly better |

**Four legacy buttons send two scancodes at once** — the `secondary` column,
applied in `vendor/K1XboxControlsXInput.cpp` where `binding.secondary` is added
to the wanted keys (this pointed at line 605 until 2026-09-25; the code has moved
to 614). A is `Return`+`R`, X is
`G`+`End`, Y is `F`+`Home`, LB is `Space`+`Insert`. Of the four second keys,
only `R` is a keymap action (`action239 DefaultAction`); `End`, `Home` and
`Insert` appear in no row of `keymap.2da`, so they are GUI list-scrolling keys
rather than actions. The action names in the table above come from that file:
79 rows, extracted from `chitin.key`, columns `name`, `character` and the six
input-class columns.

## What the legacy path has and the native path does not

This is the gap list, and it is larger than it looks. Everything below is read
out of the game's own `keymap.2da` (79 rows, extracted from `chitin.key`) and
`../reverse-engineering/retained-gui-event-inventory.txt`.

**The structural reason there was a gap at all.** The legacy path synthesises
keystrokes, so its buttons land on KOTOR's **keymap actions** in input class
`icpc` — real gameplay verbs. The native path sends **retained GUI panel
events**, which are dispatched per screen. The gameplay HUD's dispatcher,
`INGAME_GAMEPLAY` at `0x006E6180`, implements only `0x28`, `0x2D`, `0x2E`,
`0x39` and `0x3A`. So `0x29`, `0x2A`, `0x2B`, `0x35` and `0x36` — X, Y, Back, LT
and RT — did nothing in gameplay, while the same buttons on the legacy path
performed actions.

> **Correction.** An earlier revision of this file said the same of LB and RB.
> That was wrong: `0x39` and `0x3A` **are** implemented by that dispatcher, at
> `0x006E622E` and `0x006E6250`. Four buttons were inert in gameplay, not six.

**Most of this is now closed** — see *Gameplay verbs, and how they are bound*
below. What follows is the gap as it stood, kept because it is the evidence
the fix was built from.

| Input | Legacy key | The action that key is bound to | Native in gameplay |
| --- | --- | --- | --- |
| LT | `Q` | `action204 SelectPrev` — cycle target backwards | **nothing.** `0x35` is not implemented by the gameplay dispatcher |
| RT | `E` | `action205 SelectNext` — cycle target forwards | **nothing.** `0x36`, likewise |
| RB | `Tab` | `action206 ChangeChar` — switch party member | **nothing in gameplay.** `0x3A` is description scroll on menu panels |
| X | `G` | `action264 STEALTH` | **nothing.** `0x29` is a menu-panel event |
| Y | `F` | `action240 CancleCombat` | **nothing.** `0x2A`, likewise |
| Back | `V` | `action207 PartyActive` | **nothing.** `0x2B` is implemented by JOURNAL, not the HUD |
| A | `Return` + `R` | `action250 ActionMenuQueue` + `action239 DefaultAction` | **covered** — the world-interaction bridge performs the default action |

`SelectPrev`, `SelectNext` and `ChangeChar` are the "focus on a person" verbs:
two of them cycle the current target and the third changes which party member
you control. All three are active in `icpc` and `icfreelook`, and none of them
has a native binding.

### Corrections to an earlier reading of this file

Two rows were wrong before `keymap.2da` was read, and are recorded because the
error was the same each time — treating a scancode as unknown rather than
looking it up:

| Claim | Correction |
| --- | --- |
| "L3 = `X`, R3 = `CapsLock`, deliberately not reproduced" | `X` **is** `action242 Flourish` and `CapsLock` **is** `action208 Freelook`. Both paths do the same two things. There is no divergence here at all |
| "Four buttons send a second scancode whose action is unidentified" | `R` is `DefaultAction`, covered by the interaction bridge. `End`, `Home` and `Insert` appear in no keymap row, so they are list-scrolling keys handled by the GUI, not actions |

### The shape of a fix

Free look shows the route. `R3` works natively because the action router at
`0x00621238` pairs a low console id with the high PC id for the same handler —
`0x01`/`0xD0` to enter free look, `0x06`/`0xCC` to leave — and the low ids were
unbound, so KMRP could register descriptions on them. Closing this list means
finding the equivalent low ids for `SelectPrev`, `SelectNext`, `ChangeChar`,
`STEALTH`, `CancleCombat` and `PartyActive` in that same switch, and binding
them the way `R3` is bound. **Not yet attempted.**

Until then the honest summary is: **the native path is better at movement,
camera, menus and focus, and worse at gameplay verbs.**

## Gameplay verbs, and how they are bound

Reading the action router closed most of the list. `CClientExoAppInternal::
HandleInputEvent` routes two switches — a low console-id switch at `0x00621238`
and a high PC-id switch at `0x00621254` — and eight handlers are reached from
both. **The high id is the `keymap.2da` action number**, which identifies every
one of them: `0xD0` is 208 is `action208 Freelook`, the pair R3 already used.

| low | high | action | the handler calls |
| --- | --- | --- | --- |
| `0x01` | `0xD0` (208) | Freelook | `CSWCModule::SetFreeLookCamera` |
| `0x02` | `0xE0` (224) | Pause | `RestoreCamera`, `SetInputClass` |
| `0x05` | `0xCD` (205) | SelectNext | `CClientExoAppInternal::SelectNearestObject` |
| `0x06` | `0xCC` (204) | SelectPrev | — and leaves free look when in it |
| `0x09` | `0xCE` (206) | ChangeChar | `ChangeCharacterToNextLivingPartyMember`, `CGuiInGame::ChangeCharacter` |
| `0x0A` | `0xCF` (207) | PartyActive | `CGuiInGame::ShowSoloModeQuery` |
| `0x0B` | `0xDF` (223) | GUI | opens the in-game menu |

### What is bound now

No new control slot was needed and the buffer emits exactly what it did before.
A slot resolves to whichever event is registered for it **in the current input
class**, so one button carries a GUI event in ICPCGUI and a gameplay verb in
ICPC — the mechanism free look already used on slot `0x7E`.

| Button | slot | ICPC (gameplay) | ICPCGUI (menus) |
| --- | --- | --- | --- |
| LB | `0x78` | `0x06` SelectPrev | — (see below) |
| RB | `0x79` | `0x05` SelectNext | — (see below) |
| Back | `0x7A` | `0x0A` PartyActive | `0x2B` Black |
| LT | `0x7B` | `0x09` ChangeChar | `0x35` previous screen |
| RT | `0x7D` | `0x02` Pause | `0x36` next screen |

Menus are unchanged. **`0x06` is registered on LB, not R3**, because it is one
event serving both SelectPrev and free-look exit and can sit on only one
button. The alternative — a second slot on that description, keeping the exit
on R3 — was rejected because it would make R3 in the world fire `0x01` and
`0x06` together, entering free look and cycling the target in one press.

**R3 still leaves free look.** `0x01` is polled only in ICPC, so a press while
in free look (ICFreeLook) is bridged instead: `PerformPendingFreeLookExitK1`
calls `HandleInputEvent` with `0x06` on the gameplay frame, and the press is
suppressed so it means one thing. So R3 toggles, and LB also leaves. (This
paragraph said "entered with R3 and left with LB" until 2026-09-24.)

**LB and RB carry no GUI event at all now.** The right stick already scrolls
descriptions in menus: `UpdateDescriptionScrollK1` dispatches `0x39`/`0x3A`
straight to the screen's own panel, gated to `K1_CLASS_PCGUI`, with its own
hold-and-repeat. Registering the same two events on these slots was a second
route to one behaviour, so it was removed. Their *descriptions* remain,
because ICDialog uses the same events for computer-terminal scrolling and
that does arrive through these slots.

**The cost, stated plainly.** LB and RB no longer carry `0x39`/`0x3A` in ICPC
either, and those *are* implemented by the gameplay HUD dispatcher. Target
cycling was judged worth more than HUD feedback scrolling. Back, LT and RT
lose nothing — their GUI events were never implemented there.

### Still not bound

`STEALTH` (`action264`) and `CancleCombat` (`action240`) have **high PC ids
only**. No low console id reaches their handlers, so there is no description to
register and they cannot be bound this way. They would need an engine bridge,
the pattern L3's flourish uses.

Since 2026-09-25 the combat half of `CancleCombat` has such a bridge of another
kind: X presses the HUD's own Disengage button while it is drawn
(`controller-native-path.md`, "The gameplay HUD action bar"). Stealth has no pad
button.

**Untested when written:** every binding in this section was measured from the
router and compiled, and none of it had been played. Recorded since: the Solo
Mode query that Back opens was play-tested on 2026-09-24 and 2026-09-25
([`controller-playtest-checklist.md`](controller-playtest-checklist.md)), and RB's
targeting was driven with the virtual pad on 2026-10-05
([`controller-standalone.md`](controller-standalone.md), section 8). No record
names LB, LT's party switch or RT's pause as tested one by one.

## What the native path has and the legacy path does not

| Capability | Where |
| --- | --- |
| Proportional analog movement, and diagonals that are not rescaled to full speed | `NativeJoystickMovementK1`, `NativeJoystickSkipNormalizeK1` |
| Right-stick camera through the engine's own turn, not synthesised key taps | `NativeCameraFrameK1` |
| Spatial focus navigation on screens the engine cannot navigate, with hold-repeat | `NativeGuiFrameK1` in `K1NativeJoystick.cpp` |
| A focusable in-game tab bar, and native list control inside tab content | `NativeGuiFrameK1` |
| D-pad control of the gameplay HUD action bar | `NativeActionBarK1` |
| World interaction on A in gameplay, where nothing has focus | interaction bridge |
| Free look on R3, including the pad state block the engine needs for it | `K1_STICK_CLICKS`, `EnsurePadStateK1` |
| Flourish weapons on L3, gated to input class 0 so it cannot fire in menus | `PerformPendingStickActionsK1` |
| Movie margins painted black | `NativeMovieWindowOpenK1`, `NativeMovieWindowCloseK1`. Not controller code, and since 2026-10-05 part of KMRP's patch only: the controller patch leaves the movie window alone |
| Controller prompt badges in four controller families, built per layout (`kmrp` Xbox, `kmrs` PlayStation, `kmrn` Switch, `kmrd` Steam Deck) | `tools/build_controller_prompt_textures.py` |
| Rumble: BioWare's table and KMRP's haptics | `K1Rumble.cpp`, [`controller-rumble.md`](controller-rumble.md) |
| PlayStation, Switch and Steam Deck pads read directly, through SDL | `K1ControllerBackend.cpp`, [`controller-sdl-backend.md`](controller-sdl-backend.md) |
| An optional HUD laid out like the Xbox version's | `K1XboxHud.cpp`, [`controller-xbox-hud.md`](controller-xbox-hud.md) |
| R3 switches party member on Abilities, Character, Equipment and Inventory, with an on-screen cue | `PerformPendingPartySwitchK1`, `K1_PARTY_SWITCH_PANELS` |
| Start opens and closes the Map | the `0xD7` bridge, `K1_START_OPENS_MAP` |
| Cues for LT/RT on the menu tab strip and X on the Abilities sub-tabs; an A beside a confirmation box's focused button | `reverse-engineering/custom-gui-controls.md` |
| The Controller Layout screen, under Options → Gameplay | `K1ControllerLayout.cpp`, [`controller-layout.md`](controller-layout.md) |

## Coverage of the retained Xbox layout

The retained events *are* the Xbox build's own controller handling, left in the
PC executable. Counting distinct event ids across every dispatcher in
`../reverse-engineering/retained-gui-event-inventory.txt`: **the engine
implements 25, and KMRP binds 19** -- 18 when this was first counted, plus `0xCE`
since R3 took it.

The ones that were unbound at that count, with how many panels implement each:

| id | panels | status |
| --- | --- | --- |
| `0x2E` | 32 | **meaning not established.** Shares handlers with `0x28` on most panels |
| `0x2D` | 26 | **meaning not established.** 58 occurrences overall, "list entries and options rows, always alongside `0x27`" |
| `0xDF` | 8 | the PC-side id paired with `0x0B` in the action router at `0x006213BC`; Start already drives that pair |
| `0x3F`, `0x40` | 5 each | **meaning not established** |
| `0x3D`, `0x3E` | 4 each | `CSWGuiListBox` treats them as aliases of `0x31`/`0x32`, scroll selection up and down — functionally covered by the D-pad |
| `0xCE` | 4 | change the party member the screen shows. **Bound since 2026-09-15:** R3 sends it to ABILITIES, CHARACTER, EQUIP and INVENTORY, the four panels that implement it (`K1_PARTY_SWITCH_PANELS`). This row said "INVENTORY only; unexamined" |
| `0x3B`, `0x3C`, `0x00` | 1 each | **meaning not established** |

So of the seven, one is already covered by Start, two are D-pad aliases, and the
rest are genuinely unknown rather than known-and-missing.
`retained-xbox-gui-events.md` says so directly: `0x2D`, `0x2E` and `0x3B`-`0x3F`
"share handlers with the above on several panels; individual meanings **not
established**". Binding a code whose meaning is unknown is not a feature.

**The original Xbox pad's White button has no implementation to bind.** The
dispatch table's column order runs `... Y, Black, 2c, 2d, 2e ...`, so `0x2C` is
the slot where White sits next to Black at `0x2B`. No panel in the inventory
implements `0x2C` at all, so there is nothing behind it.

**The gameplay verbs are the real gap, and they are not retained events.** They
are keymap actions, reached through the action router rather than the panel
dispatchers, which is why the table above does not show them missing. See the
gap list above.

## Legacy components still installed, and why

The native path replaces input *transport*. It does not replace the legacy
module's UI integration, which is why eight legacy hooks remain in
`kotor1.hooks.toml`. **Only one of the eight is installed**,
`ClearActionBarControlsK1` (`tools/build_controller_kpatch.py`, `hooks()`, read on
2026-10-08); the other seven are legacy exports outside `REQUIRED_LEGACY` in
`tools/kmrp_controller.py`, which no build selects, and are in the table as a
record. The table below says what each did; the native hooks that hold their
sites now are listed in [`controller-handover-plan.md`](history/controller-handover-plan.md).

| Hook | Keeps doing |
| --- | --- |
| `OnSetActiveControlK1` | a `SetActiveControl` focus bug, unrelated to input |
| `CaptureActionBarInputK1` | action-bar UI integration |
| `UpdateActionBarControlsK1`, `ClearActionBarControlsK1` | the same |
| `CancelActionBarKeyboardFocusOnMouseMoveK1` | focus behaviour on real mouse movement |
| `CancelMovieOnSpaceK1`, `PollMovieControllerK1` | legacy movie skip; the native path hooks the same loop with `NativeMovieFrameK1` |
| `DispatchMenuInputK1` | **dropped** on the native path — this is the single call site of `PollXInputK1()` |

Cursor parking and the device-active test (`IsControllerInputActiveK1`,
`KmrpMarkControllerActiveK1`, `KmrpMarkKeyboardMouseK1`) are legacy code the
native path *calls into* rather than replaces: the prompt layer and the cursor
policy both depend on them.

## Untested

- Gap 2, D-pad auto-repeat on the retained codes, is reasoned from the two
  sources and **has not been driven in game**.
- Gaps 1 and 3 depended on identifying what `R`, `End`, `Home`, `Insert`, `X`
  and `CapsLock` are bound to in KOTOR's own keymap. That has since been read
  out of `keymap.2da` -- see *Corrections to an earlier reading of this file*
  above -- so this item is closed.
- Everything in the native column has been played except where
  [`controller-playtest-checklist.md`](controller-playtest-checklist.md) says
  otherwise.
