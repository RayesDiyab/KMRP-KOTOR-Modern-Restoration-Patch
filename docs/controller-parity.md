# Controller parity: the native path against Saul0097's module

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before
> editing this file.

**Kind: reference.** It describes what each of the two controller paths does
today. The narrative of how the native path was built is in
[`controller-native-path.md`](controller-native-path.md); what may be removed
once QA passes is in [`controller-handover-plan.md`](controller-handover-plan.md).

## What this compares, and where the claims come from

Two implementations ship in the same module binary:

| path | source | how input reaches the game |
| --- | --- | --- |
| **legacy** | `src/controller-native/vendor/K1XboxControls.cpp`, `vendor/K1XboxControlsXInput.cpp` (Saul0097's KPM Xbox Controls K1 1.2, as modified by KMRP) | reads XInput, **synthesises keystrokes** into the game's keyboard path |
| **native** | `src/controller-native/K1NativeJoystick.cpp` | feeds XInput into KOTOR's **own retained joystick pipeline**, as DirectInput records |

Every claim below is read out of those tracked sources at the line given, or out
of `src/controller-native/kotor1.hooks.toml`. Nothing here is measured from the
executable; the byte-level evidence for the native events lives in
[`../reverse-engineering/retained-xbox-gui-events.md`](../reverse-engineering/retained-xbox-gui-events.md).
Only one path's input transport is active at a time —
`tools/select_controller_path.py` drops the legacy `DispatchMenuInputK1` hook,
and `PollXInputK1()` is called from nowhere else
(`vendor/K1XboxControls.cpp:3228`).

## Button parity

Legacy from `BUTTON_BINDINGS`, `vendor/K1XboxControlsXInput.cpp:137-151`. Native
from `K1_BUTTONS`, `K1_TRIGGERS`, `K1_DPAD` and `K1_STICK_CLICKS`,
`K1NativeJoystick.cpp:187-312`.

The `Parity` column is judged **in gameplay**, because that is where the two
paths diverge: the legacy keys reach keymap actions, the native events reach
GUI panels, and the gameplay HUD implements only five of them.

| Input | Legacy sends | Native sends | Parity in gameplay |
| --- | --- | --- | --- |
| A | `Return` + `R` = ActionMenuQueue + DefaultAction | event `0x27`, plus the interaction bridge | equivalent |
| B | `Delete` = ActionMenuRemoveQ | event `0x28` | equivalent |
| X | `G` + `End` = STEALTH | event `0x29` | **native does nothing** |
| Y | `F` + `Home` = CancleCombat | event `0x2A` | **native does nothing** |
| LB | `Space` + `Insert` = Pause | event `0x39`, description scroll up | differs; both useful |
| RB | `Tab` = ChangeChar | event `0x3A`, description scroll down | **native does nothing** |
| LT | `Q` = SelectPrev | event `0x35`, screen cycling | **native does nothing** |
| RT | `E` = SelectNext | event `0x36`, screen cycling | **native does nothing** |
| Back | `V` = PartyActive | event `0x2B`, Black | **native does nothing** |
| Start | `Escape` = GUI | event `0x0B` | equivalent |
| L3 | `X` = Flourish | flourish weapons (engine bridge) | equivalent |
| R3 | `CapsLock` = Freelook | free look, events `0x01` / `0x06` | equivalent |
| D-pad | arrow keys, as repeating taps | codes `0x384`/`0x388`/`0x38C`/`0x390` | see below |
| Left stick | `W`/`S`/`Z`/`C`, plus a walk modifier on `B` | the movement fields directly, proportional | native is strictly better |
| Right stick | `A`/`D` taps | `CSWCModule::AcclTurnCamera` | native is strictly better |

**Four legacy buttons send two scancodes at once** — the `secondary` column,
applied at `vendor/K1XboxControlsXInput.cpp:605`. A is `Return`+`R`, X is
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

**The structural reason there is a gap at all.** The legacy path synthesises
keystrokes, so its buttons land on KOTOR's **keymap actions** in input class
`icpc` — real gameplay verbs. The native path sends **retained GUI panel
events**, which are dispatched per screen. The gameplay HUD's dispatcher,
`INGAME_GAMEPLAY` at `0x006E6180`, implements only `0x28`, `0x2D`, `0x2E`,
`0x39` and `0x3A`. So `0x29`, `0x2A`, `0x2B`, `0x35` and `0x36` — X, Y, Back, LT
and RT — **do nothing in gameplay on the native path**, while the same buttons
on the legacy path perform actions.

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

## What the native path has and the legacy path does not

| Capability | Where |
| --- | --- |
| Proportional analog movement, and diagonals that are not rescaled to full speed | `NativeJoystickMovementK1`, `NativeJoystickSkipNormalizeK1` |
| Right-stick camera through the engine's own turn, not synthesised key taps | `NativeCameraFrameK1` |
| Spatial focus navigation on screens the engine cannot navigate, with hold-repeat | `NativeGuiFrameK1`, `K1NativeJoystick.cpp:2651-2740` |
| A focusable in-game tab bar, and native list control inside tab content | `NativeGuiFrameK1` |
| D-pad control of the gameplay HUD action bar | `NativeActionBarK1` |
| World interaction on A in gameplay, where nothing has focus | interaction bridge |
| Free look on R3, including the pad state block the engine needs for it | `K1_STICK_CLICKS`, `EnsurePadStateK1` |
| Flourish weapons on L3, gated to input class 0 so it cannot fire in menus | `PerformPendingStickActionsK1` |
| Movie margins painted black | `NativeMovieWindowOpenK1`, `NativeMovieWindowCloseK1` |
| Controller prompt badges, generated per resolution at install time | `tools/build_controller_prompt_textures.py` |

## Coverage of the retained Xbox layout

The retained events *are* the Xbox build's own controller handling, left in the
PC executable. Counting distinct event ids across every dispatcher in
`../reverse-engineering/retained-gui-event-inventory.txt`: **the engine
implements 25, and KMRP binds 18.**

The seven unbound ones, with how many panels implement each:

| id | panels | status |
| --- | --- | --- |
| `0x2E` | 32 | **meaning not established.** Shares handlers with `0x28` on most panels |
| `0x2D` | 26 | **meaning not established.** 58 occurrences overall, "list entries and options rows, always alongside `0x27`" |
| `0xDF` | 8 | the PC-side id paired with `0x0B` in the action router at `0x006213BC`; Start already drives that pair |
| `0x3F`, `0x40` | 5 each | **meaning not established** |
| `0x3D`, `0x3E` | 4 each | `CSWGuiListBox` treats them as aliases of `0x31`/`0x32`, scroll selection up and down — functionally covered by the D-pad |
| `0xCE` | 4 | INVENTORY only; unexamined |
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
`kotor1.hooks.toml`.

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
- Gaps 1 and 3 depend on identifying what `R`, `End`, `Home`, `Insert`, `X` and
  `CapsLock` are bound to in KOTOR's own keymap. That has not been read out of
  `keymap.2da`, and until it is, "absent" is a statement about the code, not
  about whether anything is missing in play.
- Everything in the native column has been played except where
  [`controller-playtest-checklist.md`](controller-playtest-checklist.md) says
  otherwise.
