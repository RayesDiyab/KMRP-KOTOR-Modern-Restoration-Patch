# The native controller path

KOTOR's PC build kept the console input system almost intact. What it lacks is a
joystick *device*: the count is a hardcoded zero and nothing produces records.
Supply those two things and the engine drives itself — analog movement, buttons,
screen cycling and camera all run through its own handlers, with no synthetic
keystrokes anywhere.

The reverse engineering behind every address here is in
`reverse-engineering/retained-xbox-gui-events.md`.

## What the module does

The native path began as four hooks, in what was then
`build/research/KPM-Xbox-Controls-K1/K1NativeJoystick.cpp` -- now
`src/controller-native/K1NativeJoystick.cpp`, the tracked source. It has grown:
the set the installer writes with controller support on is 18 detours and 4 byte
patches on 2026-09-24, 26 detours and 4 byte patches after the rumble mixer of
2026-09-25 (`docs/controller-rumble.md`), and 33 detours and 4 byte patches since
the echo guard of 2026-09-28 (`native_hooks()` in `tools/kmrp_controller.py`,
checked against the patcher's table by `tools/check_patcher_hook_table.py` until that tool was removed on 2026-10-04),
covering focus, the camera, the tab bar, movies, the action bar, the prompts and
cues, and three memory fixes. Three of those detours and the 4 byte patches are
the core set, installed with the option off as well, beside two stand-ins: 9
entries ([`controller-support.md`](controller-support.md), *Installed files and
ownership*). *Corrected 2026-09-28:* this stopped at "26 detours since the rumble
mixer", seven detours short.

**Since 2026-10-05 the native path ships as a patch of its own**, `KOTOR 1 Native
Controller Mod + Xbox HUD.kpatch` (id `kmrp-controller`), run by KOTOR Patch
Manager's runtime with or without KMRP: 36 detours and no byte patch
(`hooks()` in `tools/build_controller_kpatch.py`, counted on 2026-10-09; the list
is in [`controller-standalone.md`](controller-standalone.md), section 2). The
memory fixes, the movie bars and the keyboard hooks counted above are KMRP's
patch's, `KMRP.kpatch`, which installs no controller hook. The counts above are
those of the installers of their dates.
The first four:

| Hook | Address | Purpose |
| --- | --- | --- |
| `NativeJoystickInitK1` | `0x005E24E0` | registers descriptions, raises the device count, feeds the camera |
| `NativeJoystickBufferK1` | `0x005E30F6` | replaces `GetJoystickBuffer`, emits records from XInput |
| `NativeJoystickMovementK1` | `0x00679940` | gameplay heartbeat only; writes nothing |
| `NativeJoystickSkipNormalizeK1` | `0x00679B71` | always reproduces vanilla; exists because the stolen bytes are a relative call |

## The mapping

Every row was verified by driving a virtual pad and reading the description's
value out of the running process.

| XInput | Control slot | Control code | Event | Native action | Verified |
| --- | --- | --- | --- | --- | --- |
| Left stick | `0x6E` / `0x6F` | `DIJOFS_X` / `Y` | `0x08` / `0x07` | analog movement (the game's own axes) | yes |
| A | `0x74` | `BUTTON(0)` | `0x27` | confirm | yes |
| B | `0x75` | `BUTTON(1)` | `0x28` | cancel — 35 panels | yes |
| X | `0x76` | `BUTTON(2)` | `0x29` | per-panel — 10 panels | yes |
| Y | `0x77` | `BUTTON(3)` | `0x2A` | per-panel — 8 panels | yes |
| LB | `0x78` | `BUTTON(4)` | `0x39` | description scroll up — 17 panels | yes |
| RB | `0x79` | `BUTTON(5)` | `0x3A` | description scroll down — 19 panels | yes |
| Back | `0x7A` | `BUTTON(6)` | `0x2B` | Black | yes |
| LT | `0x7B` | `BUTTON(7)` | `0x35` | `CGuiInGame::PrevSWInGameGui` | yes |
| RT | `0x7D` | `BUTTON(9)` | `0x36` | `CGuiInGame::NextSWInGameGui` | yes |
| D-pad up | `0x7F` | `0x384` | `0x31` | scroll up | yes |
| D-pad down | `0x81` | `0x388` | `0x32` | scroll down | yes |
| D-pad left | `0x80` | `0x38C` | `0x2F` | D-pad left | yes |
| D-pad right | `0x82` | `0x390` | `0x30` | D-pad right | yes |
| Start | `0x7C` | `BUTTON(8)` | `0x0B` | opens the in-game menu — **the game's own description** | yes |
| R3 | `0x7E` | `BUTTON(10)` | `0x01` / `0x06` | free look, enter and leave | yes |
| L3 | — | — | — | flourish weapons, **engine bridge** | yes |
| Right stick X | — | — | — | camera, via the mouse-delta field | registered, feel untested |

The table is the first mapping, as it was verified. **Since changed**, read from
the code on 2026-09-24: in gameplay LB, RB, Back, LT and RT carry gameplay verbs
instead of these events, and LB and RB carry no menu event at all (2026-09-14,
*Gameplay verbs* in [`controller-parity.md`](controller-parity.md)); the
free-look exit `0x06` moved to LB's slot, with R3's second press bridged; R3
switches party member on the four party screens (2026-09-15); and Start opens
the Map (issue #18, below). [`controller-behaviour-matrix.md`](controller-behaviour-matrix.md)
lists these under *Changed since this measurement*.

**Changed again on 2026-10-19 (issue 49), read from the code, not played:** the
controller uses the original Xbox game's layout, White and Black on LB and RB. In
menus RB's slot carries `0x2B` (Black) instead of `0x3A`, Back's carries nothing,
and LB's `0x39` is registered for conversations only, with RB's `0x3A` given a
description of its own there; the free-look exit `0x06` is on LT's slot, where
target cycling backwards now is; R3 does nothing in menus and RB switches party
member on the four party screens; and Start reopens the screen the menu last showed
(below). The gameplay verbs are in [`controller-parity.md`](controller-parity.md),
*What is bound now*.

When first written, all bindings were registered in both input class 0
(gameplay) and class 2 (GUI); the classes each binding is registered in now are
under *Input classes, and what is bound in each*.

### Start costs no slot at all

Slot `0x7C` was written off as unusable because it "belongs to the game's own
event `0x0B`". That was the wrong conclusion drawn from a correct observation.
`0x0B` **is** the menu-open action, and the game already registers a complete
device-2 description for it — type 1, device 2, slot `0x7C`, control code `0x38`
= `DIJOFS_BUTTON(8)`. Nothing had to be created. Emitting that control code on
the XInput Start mask reaches the engine's own handler directly, so Start is
category A, not a bridge, and consumes no slot from the budget.

Confirmed live: the description at index `0x0B` is structurally identical to
A's, and in gameplay its `+0x04` peaks at `1` while Start is held, exactly as A's
does.

Handler `0x006213BC` serves events `0x0B` and `0xDF`:

```asm
00621446  mov ecx, [esi+0x40]
00621449  cmp dword ptr [ecx+0x34], 3    ; is the module in the plain-gameplay state?
0062144D  jne 0x621472                   ; no  -> ShowSWInGameGui(7)
0062144F  push ebp
00621450  call 0x62cba0                  ; yes -> HideSWInGameGui(0)
```

**Start opens the menu but does not close it.** Measured repeatedly: from
gameplay Start produces an 81.3% screen change; with the menu already open it
produces 0.0%, at the menu root and on a sub-screen alike. The hide branch needs
`[module+0x40]+0x34 == 3`, which no longer holds once the GUI is up, so the
handler re-takes the show branch and re-shows what is already shown.

**B is the close**, from the menu root and from sub-screens both — 81.3% back to
gameplay in either case. That is also the Xbox idiom, so the result is the
console behaviour rather than a compromise. `0x28` is implemented by 35 panels,
`MAIN_MENU` among them, which is why it backs out from everywhere.

### Start is now a Map toggle (issue #18)

`0x0B` pushes **7** to `ShowSWInGameGui`, and the index is the tab's control ID in
`top.gui` -- `LBLH_EQU` 0 through `LBLH_OPT` 7, the order `CGuiInGame` keeps its
screens in (Lane's `swkotor.exe.h`: `in_game_equip` ... `in_game_map`,
`in_game_options`). So Start opened **Options**, the Escape-style menu.

The keyboard's menu hotkeys are events `0xD1`–`0xD8`. The router's jump table
(`0x00622154`, indexed through the byte table at `0x006221FC` with `event - 0x19`)
sends all eight to one handler, `0x006218D5`, which computes the screen as
`event - 0xD1` and shows it -- or hides the menu when `CGuiInGame+0x34` is `3` and
`+0x2C` already holds that screen. So **`0xD7` is the Map**.

`0xD7` has no joystick description and every free slot is spent, so Start is
routed on the press, and the release follows the press:

| where | what Start does |
| --- | --- |
| input class 0, the world | `CClientExoAppInternal::HandleInputEvent(0xD7, 1)` on the next frame, the same bridge the free-look exit uses -- the Map opens with every guard the handler applies |
| class 2 with the tab strip in front | B's control code, `DIJOFS_BUTTON(1)` -- the close measured above, from the Map or any tab LT/RT moved to |
| anywhere else | the game's own `0x0B`, as before |

The in-game menu's own dispatcher, `CSWGuiInGameMenu::HandleInputEvent`
(`0x00624970`), handles only `0xF3`/`0xF4` and passes everything else to the base
panel, so the hotkey handler's own toggle is not reachable with a menu up; that is
why the close is B's rather than `0xD7`'s. **Play-tested on 2026-09-25 at
3440x1440: Start opens the Map and closes it again.**

**Since 2026-10-19 (issue 49) Start reopens the last screen, not the Map.** The
original Xbox game's Start opened "the menu screens you used before" (dialog.tlk
10283), and the PC executable keeps that screen: `CGuiInGame+0x2C`
(`K1_IN_GAME_SCREEN_INDEX`), which `ShowSWInGameGui` (`0x0062C9B0`) writes at
`0x0062CA57` with the screen it opens, which `HideSWInGameGui` (`0x0062CBA0`)
leaves alone, and which the hotkey handler compares with its own screen
(`0x00621946`) to close the menu when that screen is showing. So in the world
`PerformPendingMenuOpenK1` reads it through `CClientExoAppInternal+0x40` and calls
`HandleInputEvent(0xD1 + index, 1)`, the hotkey of that screen, with every guard the
handler applies; when the index is not 0 to 7 it sends `0xD7`, the Map, as before.
The first row of the table above is therefore `0xD1` plus that index since then.
The route constant is `K1_START_OPENS_MENU` (it was `K1_START_OPENS_MAP`), and the
diagnostic line's `map=` counter is `mnu=`. The addresses are as the comment on
`PerformPendingMenuOpenK1` records them, and were not disassembled again for this
note; **not played**, and `test_hud_release_and_start_map.py`, which now checks it,
has not been run.

### R3 is free look, and it is a restoration

The action router pairs a low console id with a high PC id on the same handler.
Start was `0x0B`/`0xDF`. Free look is the same shape:

| Ids | Handler | What it does |
| --- | --- | --- |
| `0x01` / `0xD0` | `0x006216C7` | `GetPlayerCreature`, `CSWParty::GetPlayerCharacter`, `CSWCModule::SetFreeLookCamera`, then writes input class `4` to `[internal+0x9c]` and calls `CExoInput::ClearEvents` |
| `0x06` / `0xCC` | `0x0062184C` | if the camera mode at `ClientOptions+0x6D` reads `5`, `CSWCModule::RestoreCamera` and `SetInputClass(0, 1)` |

The high ids carry the game's own keyboard descriptions — `0xD0` and `0xCC` are
on keyboard slots `0x59` and `0x43` — and **both low ids were unbound**, exactly
as `0x0B` was. So R3 is category A: no bridge, no synthesised key.

Both events sit on the one free slot, `0x7E` → `DIJOFS_BUTTON(10)`. Sharing is
safe because they are registered in **different input classes** and only the
current class is polled: entering switches the class to `ICFreeLook`, so the
enter event stops being visible at the instant the exit event starts being. The
toggle is therefore deterministic rather than dependent on dispatch order inside
a frame — which matters, because entering also calls `ClearEvents`.

`ICFreeLook` is class **4**. The six `keymap.2da` columns load in a fixed order —
`ICPC`, `ICMiniGame`, `ICPCGUI`, `ICDialog`, `ICFreeLook`, `ICMovie` — which puts
`ICPC` at 0 and `ICPCGUI` at 2, the two indices already known from the working
bindings. The enter handler agrees independently: it writes literal `4`.

Measured: six presses, `cameraMode` alternating `5,3,5,3,5,3` and `inputClass`
alternating `4,0,4,0,4,0`.

### L3 is flourish weapons, and it is a bridge

`CClientExoApp::PlayerFlourishWeapons` (`0x005EDE90`) is reached from handler
`0x00621C21`, which serves **only** the PC id `0xF2`. There is no console
partner, and `0xF2`'s keyboard description already owns that event id.
Descriptions are one per event id, so no joystick description can be added.
L3 is therefore the project's **first category B binding**.

The call itself is small — `[[0x007A39FC]+4]` is `CClientExoApp`, and the method
takes no arguments — but it resolves the player by game-object id and calls
`CSWCCreature::ComputeWeaponOverlays(0, 1)` on the result **with no null check**.
The router gets away with that because it only runs in a live module. A bridge
has no such guarantee, so it is guarded and, importantly, is performed from the
gameplay heartbeat rather than from inside the input hook: that keeps it out of
`CExoInput`'s own polling and means a click in a menu or a cutscene cannot reach
the action at all. A request nothing consumes within 250 ms is dropped, so a
click pressed elsewhere does not fire on return to the world.

Measured with the module's own counters: four presses in gameplay gave
`performed +4, declined +0`; three presses in free look gave `performed +0,
declined +3`.

**L3 is a KMRP default, not a settled design decision.** It is isolated in one
table so it can be changed without touching anything else:

```cpp
constexpr StickClickBinding K1_STICK_CLICKS[] = {
    { XINPUT_LEFT_THUMB_MASK,  StickAction::FlourishWeapons, "L3" },
    { XINPUT_RIGHT_THUMB_MASK, StickAction::FreeLook,        "R3" },
};
```

Changing L3 means editing that one row. `StickAction` already distinguishes a
native event from an engine bridge from deliberately unbound, so a replacement
action of either kind needs no architectural change. R3 restores original
behaviour and should not move.

### Why screen diffing could not measure the flourish

Worth recording, because it nearly produced a wrong answer. Idle windows
measured 0.5–1.3% of the screen changing and flourish windows 2.3–3.6% — the
character's own idle animation overlaps the effect. The module's counters were
added for this reason, and they are what the suite asserts on.

### Why `0x2D` and `0x2E` are not used

They look attractive — implemented by 20 and 30 panels — but they resolve to the
same handlers as A and B wherever they appear. On `CSWGuiInGameCharacter` all of
`0x28`, `0x2D` and `0x2E` reach `0x006B2459`. They are confirm/cancel aliases,
not distinct actions.

## Three ways an input can reach the engine

Every binding in this project is one of three kinds. Keeping them distinct
matters because they have different costs, different failure modes and different
claims to being a *restoration*.

### A — the restored native path

An XInput control is emitted as a DirectInput record on a control slot that an
input-event description maps to a retained console event. The engine's own
handler then runs, unmodified. Nothing is synthesised and nothing is called from
outside.

This is the whole button map, both sticks' movement axes, the D-pad, the
triggers, and Start. It is the default and everything else should be justified
against it.

Two sub-kinds are worth separating, because one of them was nearly missed:

* **descriptions we register** — the slot was unused, so the module calls
  `CreateNewEvent` / `AddEvent` to bind it to a retained event. A, X, Y, LB, RB,
  Back, LT, RT and the D-pad.
* **descriptions the game already has** — the engine registers it itself and the
  module only has to emit the control code. Start (`0x0B`), and the movement
  axes' own `0x03`/`0x04`/`0x3B`/`0x3C` siblings. These cost no slot and need no
  registration, so they are strictly better when they exist. **Look for one of
  these before spending a slot** — Start was written off as impossible for
  exactly the want of that check.

### B — a direct engine bridge

No retained event exists, so the module calls an engine function itself. This
buys behaviour the event system cannot express, at the cost of being a genuine
modification: the call site is ours, the arguments are ours, and a wrong guess
about a calling convention is a crash rather than a dead button.

When this section was written nothing shipped as B: it was the fallback planned
for Start and turned out to be unnecessary there. **Several bindings are bridges
now**, each described in its own section of this file: L3's flourish, A's world
action (`0xEF`), the right stick's `RotateCamera`, Start's menu hotkey (`0xD1` plus
the last screen's index since 2026-10-19; the Map's `0xD7` until then), R3's exit
from free look, Y and B pressing the HUD's combat buttons (X and Y until
2026-10-19), Y's flourish when nothing is queued, RB's party switch in menus, the
buttons of Pazaak's table (since 2026-10-19), the movie skip, and focus navigation
itself (`SetActiveControl`).

### C — legacy synthetic input

XInput is read and keystrokes are synthesised, which the engine cannot tell from
a keyboard. This is Saul's original approach and it works, but it is invisible to
the input-description layer, fights the native path when both are live, and
cannot express an analog value.

Everything in C that has an A equivalent is listed in
`controller-handover-plan.md`. What remains in C is there because it is not input
transport at all — movie skipping, focus fixes, cursor policy and device
switching.

### Where the main menu sits

**Superseded.** The section below described the state before the focus-navigation
layer existed; the layer now drives this screen and the others like it. What is
still true is the diagnosis: the retained path really is absent here.

See "Focus navigation" below.

### The original finding, kept because the diagnosis stands

`MAIN_MENU`'s dispatcher (`0x0067B380`) implements exactly **one** event, `0x28`.
There are no scroll events to receive, so the D-pad has nothing to reach there
and A is not available — this is the one place the retained path is genuinely
absent rather than merely unbound.

Its dispatcher was for a while reported as implementing only `0x28`. It is
`0x28`, `0x2D` and `0x2E` — the decimal-immediate bug above — but all three are
confirm/cancel aliases, so the conclusion survives the correction: **there is no
scroll event to receive.**

Focus does not rescue it either. The base panel handler forwards to the focused
control, and the main menu's controls are buttons: `CSWGuiButton`'s dispatcher
(`0x0041AD40`) implements **exactly one event, `0x27`**. A D-pad event delivered
to a focused main-menu button reaches a control that implements nothing for it.
`CSWGuiNavigable`, `CSWGuiListBox` and `CSWGuiSlider` do implement the scroll
codes, which is why the in-game screens navigate and this one does not.

**So a bridge here is not a missing call to wire up — it is menu navigation to
write.** It would have to enumerate the panel's buttons, impose an order on them,
hold an index across events, call `CSWGuiPanel::SetActiveControl`
(`0x0040A630`, `__thiscall(panel, control)`, focus stored at `panel+0x1C`, reached
only through the vtable so a bridge would call it absolutely), and leave the
highlight looking right. The order and the feel are judgement calls, not
measurements, which puts the design decision with a person rather than with this
pass.

That is the recommendation: **do not build it blind.** The main menu is fully
usable with the mouse, B already backs out of it, and A activates a focused
button if one is focused.

None of this affects the in-game menus. Those are reached with Start and their
D-pad, trigger and face-button navigation is verified working end to end.

## Focus navigation

Most screens have no retained way to move focus, so a D-pad press had nowhere to
go. This layer supplies one. It is geometric and applies to any panel; the only
per-screen knowledge is the measured question "does this screen navigate itself
already?", and where the answer is yes the layer stands down.

### What it reads

All confirmed live against the running game.

| Structure | Field | Meaning |
| --- | --- | --- |
| `CSWGuiManager` | `+0x88`, `+0x8C` | panel array and count |
| `CSWGuiPanel` | `+0x1C`, `+0x20`, `+0x24`, `+0x44` | active control, control array, count, flags |
| `CSWGuiControl` | `+0x04`…`+0x10` | x, y, width, height |
| `CSWGuiControl` | `+0x38`, `+0x3C` | the `AddEvent` table and its count |
| `CSWGuiControl` | `+0x44` | flags: `0x02` visible, `0x08` selectable, `0x20` disabled |

Flags are read as a **byte**. `CSWGuiControl::HitCheckMouse` tests `cl`, not
`ecx`, and the upper three bytes carry unrelated data — read as a dword they
poison the test.

The topmost panel is found the way `CSWGuiManager::IsOnTop` finds it: the last
entry whose flags do not carry `0x600`.

### What counts as an entry

Visible, not disabled, selectable, non-zero area — **and carrying at least one
registered event**. That last test is the one that matters. Without it the Main
Menu is unusable: its background is a control the full size of the screen,
3440×1440, carrying the visible and selectable bits, whose centre sits closer to
the menu column than the next real entry does. Every downward press would have
focused the wallpaper. The five real entries register four events each; the
background, the logo and the side art register none.

### How a direction is chosen

Score every candidate that lies in the requested direction and take the lowest:

```
score = distance along the axis
      + (overlaps the current control on the cross axis ? 0
                                                        : cross offset * 6)
```

Overlapping rows and columns therefore cost nothing and everything else is
penalised six-fold, because a menu is a column and drifting out of it reads as a
bug even when the diagonal distance is genuinely shorter. With nothing in the
direction, focus wraps to the farthest control the other way, which is what a
console menu does. With nothing focused at all, the topmost-then-leftmost entry
is taken.

Focus is moved with `CSWGuiPanel::SetActiveControl` (`0x0040A630`), the engine's
own mechanism: it clears the previous control, sets the new one, plays the GUI
sound and lets each control draw its own highlight. **Nothing here draws
anything.**

### Where it does not run

Two gates, both measured rather than assumed.

**Input class.** `CClientExoAppInternal+0x9c` reads 0 in the world, 2 once a GUI
screen has the input and 4 in free look. The layer runs only at 2. In gameplay
the panel in front is the HUD, and taking the direction presses there would both
hijack the D-pad's own gameplay bindings and let focus wander around the
heads-up display.

**Screens that navigate themselves.** Four panels implement the direction events
in their own dispatcher — `ABILITIES`, `FEATS`, `MAP`, `POWERS` — and a focused
list box, editbox or slider consumes them itself. In both cases the layer
declines and the retained events do the work. Character creation's Attributes
and Skills (`ABILITIES_CHARGEN`, `SKILLS`) were on this list until 2026-09-25. KMRP
now navigates them itself, rows and a strip, because their Xbox dispatchers
changed a value on every Left/Right even with focus on the buttons below; see
`K1_POINTS_SCREENS` and `docs/controller-behaviour-matrix.md`.

### The native codes are suppressed where the layer acts

This was not the original design and the change is worth recording.

The engine is **not** inert on direction events: `CSWGuiManager::HandleInputEvent`
moves focus on `0x2F`…`0x32`, and throttles repeats to 150 ms. But it does not
move it the way the screen reads. Measured on the Main Menu, its own sequence
from the top entry runs 666 → 810 → 954 → 738 → 882, skipping an entry each time
and wrapping oddly.

Emitting the native codes alongside this layer therefore moved focus **twice per
press** — once sensibly and once not — which is exactly the symptom that looked
like a scoring bug and was not. So on a screen this layer owns, the codes are not
emitted at all. The decision is latched at the press: deciding it again at the
release could emit a press with no matching release, and a digital description
that never sees its zero stays stuck on.

### Held directions, and the left stick

A held direction moves once immediately, waits `K1_NAV_HOLD_DELAY_MS` (400 ms),
then repeats every `K1_NAV_REPEAT_MS` (120 ms).

The left stick drives the same operation, with two thresholds rather than one: it
must pass `K1_NAV_STICK_ENGAGE` (0.55) to register and must fall back below
`K1_NAV_STICK_RELEASE` (0.35) before another direction can register. Without that
gap a stick resting near the threshold chatters, and a worn stick with resting
drift would walk through a menu on its own. Whichever axis is pushed further
wins, so a diagonal push does not fire both. Verified: a 12% deflection held
repeatedly does not move focus.

Gameplay analog movement is untouched — the stick's navigation path is gated on
input class 2 like everything else here.

## Screen classification

`tools/classify_controller_screens.py` reports it, reading the NATIVE set out of
the retained-event inventory so it cannot drift from what the binary implements.

| Screen | Class | Why |
| --- | --- | --- |
| Skills, Feats, Powers, Map | NATIVE | the panel implements the direction events itself |
| Dialogue | NATIVE | runs on the in-game GUI; entries are a list box the retained events reach |
| Inventory, Equipment, Journal, Save, Load, Merchant, Containers | HYBRID | built around a list box that scrolls itself; the layer moves focus on and off it |
| Main Menu, Character, Options, Level-up, Party select | KMRP | buttons only; the layer drives them |

## Analog behaviour

`PollInput`'s type 3 path returns `[desc+0x24] - [desc+0x04]` and then sets the
baseline to the accumulator, consuming what it read. So **axes emit one record
per frame carrying the absolute position**, and each poll returns exactly that
position. Buttons are the opposite: edge-triggered, because their store writes
rather than accumulates.

Measured earlier against the movement integrator: velocity is `input * 8.1`,
exactly, at every deflection. KOTOR retained true proportional movement.

### Deadzone

The engine's own joystick deadzone is `8191.75 / 32767` — exactly 25%, matching
Microsoft's `XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE` of 7849 and the era's advice for
a square per-axis deadzone. It is neutralised at startup and replaced with a
**radial 15%** applied in the module (`K1_STICK_DEADZONE = 0.15f`), with the
remaining travel rescaled to the full range. *Corrected 2026-10-08, from the
constant and its comment in `K1NativeJoystick.cpp`:* this said a radial 8%, which
cleared the 4.8% resting drift first measured. A pad's left stick was then
measured resting at 9.6%; past an 8% deadzone it moved the character,
overrode keyboard movement and kept the pad counted as the device in use, so the
value went to 15%, still under the engine's 25%. The camera's deadzone stayed at
12% (the same pad's right stick rests at 4.8%), and whether the pad counts as in
use is a third threshold, `K1_ACTIVITY_STICK`, 0.35.

`K1_STICK_DEADZONE` and `K1_CAMERA_DEADZONE` are named constants, tunable
without touching logic.

The rescaled vector is the stick's **unit vector times the rescaled
deflection**, so it never exceeds the unit circle. *Corrected 2026-10-15:* until
then the deflection was clamped to 1 but the direction kept the raw vector's
length, and a thumbstick reports its corners at up to sqrt(2); with the engine's
`Vector::Normalize` skipped for the analog path (below), that length reached the
character as speed. Measured from the engine's own movement fields with
`debug-logs=2` on a ROG Ally X under Proton: `move ud=-999 lr=999`, a vector of
1.41, whenever a flick landed in a corner, against 1.00 for a straight push; a
gradual tilt rarely reaches a corner, which is why the extra speed showed as a
"quick tilt" fault. Reported together with the character heading the wrong way
on such a flick; with the vector bounded the speed is constant and the
reversal has not been seen again, though its mechanism was not read out of the
engine.

**Why a length over 1 turns the character the wrong way** (read 2026-10-21, checked
against the maintainer's own reverse engineering of KOTOR). `Control` turns the
character's facing toward the stick's direction at a rate it takes from the speed,
at `0x00679D54`..`0x00679D80`:

    r    = |velocity (+0x5C)| / maximum speed (0x00679510)
    rate = turnMin (+0x38) + (turnMax (+0x3C) - turnMin) * (1 - r)

The player's control has `turnMin` 150 and `turnMax` 1500, so the rate falls to
zero at r = 1.11 and is negative past it: the step is taken away from the stick,
the gap grows, and the character keeps turning. A keyboard is normalised to r = 1
and never gets there. Reproduced in the test game with a diagonal of length 1.19
(the engine's own dead zone at `0x0074D708` set negative, in memory only): running
on one diagonal and switching to the other without letting go swung the facing
97, 147, 110, 55, 7 degrees, away from the -172 asked for, and the character ran
off that way; with a length of 1 the same switch turned straight to -172. Issue
46's two logs (KMRP 1.5.1, before the buffer fix) show diagonals of 1.13 to 1.24,
which is the circling and the drift reported there.

So `NativeJoystickSkipNormalizeK1`, which skips `Vector::Normalize` for the
stick, now scales a vector longer than 1 back to 1 instead. The buffer already
bounds the stick; this bounds anything else that can add to it, such as the
accumulator's sum over a frame the engine did not poll. The call is reached only
when both parts are non-zero (`0x00679B4F`..`0x00679B6B`), which is every
diagonal; a single axis is clamped to 1 by `ScaledValue`. With that guard and the
same overlong input, the speed stayed at 5.40, the run maximum, and the switch
from one diagonal to the other turned straight across, both ways.

Ruled out on the way, measured the same day in the test game:

* **The chase camera does not follow the character.** Strafing with the keyboard
  for six seconds kept one heading; mode 3's camera holds its yaw unless input or
  a script turns it. A sideways stick therefore runs straight, not in a circle.
* **The cursor at a screen edge turns the camera nonstop** (`UpdateCamera`,
  `0x005F5F7A`..`0x005F607E`), and since the heading is taken from the camera every
  frame, a run would bend. In pad mode the parked cursor prevents it: with the
  mouse left at the left edge, the first stick movement moved the cursor to the
  top centre (1720, 16 at 3440x1440) and the camera stopped.
* **Turning the camera while moving (issue 46's third report)** kept up with the
  stick: switching from forward to right while the right stick turned changed the
  heading in the next sample. Not reproduced with an Xbox pad; the report used a
  DualSense presented as an Xbox 360 pad.

## The camera

**Working, playtest-confirmed.** The right stick turns the camera through the
engine's own `CSWCModule::RotateCamera`. Getting there took two wrong answers,
both recorded below, because both are easy to arrive at again from the listing.

### What actually drives the turn

`UpdateCamera` @ `0x005F5E10` has two inputs, and **neither is the mouse X
delta**.

* **Horizontal rotation is event `0x11C`**, polled at `0x005F5EE6`,
  `0x005F5F05` and `0x005F5F32`. The result is +1.0, -1.0, or -- and this
  matters -- the **raw analog value** when it is neither, so the turn is
  analog-capable. It reaches `CSWCModule::RotateCamera` @ `0x00640090`.
* **The mouse contributes only `+0x3A4`.** `GetMouseDelta` @ `0x005DF610`
  (single caller, `0x005F5EB2`) writes `+0x3A0` to its first argument and
  `+0x3A4` to its second; `UpdateCamera` reloads only the second (`fld
  [esp+0x1c]` at `0x005F5ED4`, esp having moved by 4 for the pushed argument)
  and passes it to the mode-gated tilt at `0x0063FCC0`.
* **`CExoInputInternal+0x3A0` is fetched and discarded** -- its stack slot is
  never read again in the function.

`UpdateMouseDelta` @ `0x005E0110` confirms the field roles: X to `+0x3A0`, Y to
`+0x3A4`, both zeroed when the mouse is not captured.

### First wrong answer: writing +0x3A0

The module used to add the stick to `+0x3A0`. That could never rotate anything.
A virtual-pad run showing +-14.0 there was the module reading back its own
write, and it was taken as evidence of a working camera for weeks; a pixel
comparison that reported "nothing" over the same run was correct and was
disbelieved. An earlier reading of `UpdateCamera` had the consumed stack slot
wrong by four bytes and concluded the opposite.

### Second wrong answer: calling at the wrong time

Calling `RotateCamera` from the `GetEvents` hook ran 1400 times in 30 seconds
with a live receiver and still produced no motion. `RotateCamera` stores the
turn in `camera+0x10C` (mode 3, at `0x006400FF`), but `UpdateCamera`'s **idle**
path -- the one taken whenever the `0x11C` axis is zero, which for a controller
is every frame -- calls `CSWCModule::ScrollCamera` at `0x005F60D5`, and that
zeroes `camera+0x10C` outright at `0x0063FE87`. Anything written earlier in the
frame is erased before the camera update at `0x006391A0` can read it. The
keyboard escapes this because a non-zero turn makes `UpdateCamera` jump past the
`ScrollCamera` call at `0x005F6024`.

Counters alone could not distinguish this from success: the bridge ran, the
receiver was live, the argument was correct, and the camera did not move.

### The implementation

`NativeCameraFrameK1`, hooked at **`0x006039CF`** -- where both of
`UpdateCamera`'s paths converge, still inside the same function, with `ESI`
holding `CClientExoAppInternal`. Stolen bytes `A1 E0 39 7A 00 / 8B 48 04`,
absolute addressing only.

* Receiver `[CClientExoAppInternal+0x18]`, which `0x006039CA` corroborates by
  calling `RotateCamera(0, 0)` through the same field when input is suppressed.
* Second argument is the frame delta from `0x0078E574`, as `UpdateCamera` is
  handed at `0x006039A7`.
* **Not negated.** `UpdateCamera` negates its axis at `0x005F6018`, but that
  axis is `0x11C`, whose two-button description already runs opposite to the
  stick. Mirroring the `fchs` flipped left and right, which a playtest caught.
* Gated on input class 0 or 4 (`UpdateCamera` is skipped in the minigames --
  `0x0060399A` tests the class against 1) and on a live module.
* Event `0x11C` cannot carry the stick instead: it is a live type-4 two-button
  axis on the keyboard device (slots `0x36`/`0x33`), and PollInput's type-4 path
  at `0x005E242F` recomputes it from those two control states on every poll.
  Repointing its slots would take the keyboard's own turn away.

`K1_CAMERA_SPEED` is **1.0**, the value at which full deflection equals a full
keyboard turn. That is the neutral choice, not a tuned one. `K1_CAMERA_DEADZONE`
is 0.12.

**There is no vertical camera axis to drive.** `ScrollCamera` and `ZoomCamera`
take computed values, not input, and the tilt path is mode-gated.

**Not yet honoured:** the engine's camera-invert option at `0x00832920`, which
`UpdateCamera` folds in and the bridge does not. Untested against the stick.

## The in-game tab bar

The in-game menu is two panels. `CSWGuiInGameMenu` (dispatcher `0x00624970`) is
the strip of eight tab icons and stays in front the whole time the menu is open;
the screen's content is a separate panel below it in the manager's list. The
navigation layer used to see only the panel in front, so the content was
unreachable and the strip itself read wrongly.

### Sixteen controls, eight tabs

| indices | size / y | registers | what it is |
| --- | --- | --- | --- |
| 0-7 | 192x192 at y=96 | `0x35`, `0x36` only | the tab stops, and the engine's own focus targets |
| 8-15 | 156x120 at y=129 | `0x27`, one handler each | the mouse hotspots, sitting inside the frames |

`CSWGuiInGameMenu::SetActiveControlID` @ `0x00624BD0` indexes the panel's control
array directly, so **tab k is control k**, and the array is in visual
left-to-right order. Both sets pass the navigable test, so left/right used to
walk sixteen stops through an eight-tab strip, landing half the time on a frame
that A cannot activate. Only the frames are focus stops now.

The eight `0x27` handlers all call `CGuiInGame::SetScreen` @ `0x0062CF10` with a
different constant (`0x00624CF0`=0 … `0x00624DD0`=4 … `0x00624DB0`=7), and the
current tab is `CGuiInGame+0x2C`, with `CGuiInGame` at
`CClientExoAppInternal+0x40`. Nothing per-tab is encoded anywhere in KMRP:
activating a tab hands its own overlay its own registered `0x27` through its own
`HandleInputEvent`, which is exactly what a mouse click does.

### Behaviour

* left/right walk the eight frames in visual order, wrapping, **without**
  switching tabs
* A opens the focused tab
* down enters that tab's content, on the panel below
* up from the content's top boundary returns to the frame of the tab being shown
* up from the strip does nothing
* LT/RT still switch immediately, unchanged -- they are events `0x35`/`0x36` on
  the frames, which the panel's own dispatcher turns into `0xF3`/`0xF4`

Focus lives on two panels at once, which is what the engine already does: each
panel keeps its own active control, so the active tab stays lit while focus is
down in the content. Which panel a press acts on cannot be derived from that --
both are non-null always -- so it is remembered in one flag, cleared when the
strip stops being in front and when the tab changes under it.

### A panel-level exemption only counts for the panel in front

`PanelNavigatesItselfK1` used to stand down for the six screens that navigate
themselves, wherever they were. On the Abilities tab that content panel is one of
them **and sits behind the strip**, and `CSWGuiInGameMenu` handles `0xF3`/`0xF4`
and then routes to its own focused control -- so the retained press reached the
strip and died there. Focus entered the tab and could never leave. Standing down
in favour of navigation that cannot be delivered is not standing down.

Entry also refuses to land on a control that owns the direction keys: the
Abilities screen remembers its ability list as its focused control, and resuming
straight onto it handed every later up press to the list.

### Lists, and why standing down was standing down into nothing

A retained direction event cannot reach a panel behind the strip. The strip is in
front, `CSWGuiInGameMenu::HandleInputEvent` answers only `0xF3`/`0xF4`, and the
base class then routes to the strip's **own** focused control. So deferring to a
content list's "native navigation" deferred to nothing at all: the press reached
the strip and died there.

Behind the strip, a focused control that owns the direction keys is therefore
handed its own retained event directly, through its own `HandleInputEvent` --
the same call the engine makes. The navigation stays the engine's; only the
delivery changes.

The escape from a list comes from the engine as well.
`CSWGuiListBox::HandleInputEvent`'s `0x31` case at `0x0041CF3E` computes its own
"did anything happen":

    mov   ax, [esi+0x2C8]     ; the selected row
    test  ax, ax
    setne cl                  ; moved = (row != 0)

so a list on row 0 cannot scroll up, and that is exactly when up leaves it for
the tab strip. `+0x2C6` selects a different branch when it is not `-1`, so the
escape is taken only on the plain-row path. All eight tabs, Abilities and Map
included, enter their content and come back out.

### A panel can open IN FRONT of the strip, and that is not the menu closing

Walking every tab was reported here as "closes the in-game menu", confirmed
against the pre-tab-work module, and called pre-existing. **That was wrong**, and
the way it was wrong is worth keeping:

* The menu never closed. `[CGuiInGame+0xA0]` -- vtable `0x00755CD0`, dispatcher
  `0x006AA8A0`, one of the screens the in-game allocator at `0x00632xxx` builds
  on demand -- opens **in front of** the strip. The input class stays 2 and the
  strip is still in the stack, merely covered.
* The harness asked "is the front panel the strip?", got no, and called the
  strip gone.
* A later check then pressed B, which backed out of the covering panel *and*
  the menu. The snapshot taken afterwards showed gameplay, which is what made
  the diagnosis look confirmed.

Confirming the symptom on the baseline confirmed the symptom, not the cause.
The suite now separates the two -- covered means class 2 with the strip still
present, and is recovered from with B; closed means class 0 and no strip.

**Still unknown:** what makes that panel open. It does not reproduce from the tab
walk alone (nine full cycles), from bumping tabs with focus left in content, or
from driving the Abilities list. It needs state from earlier in the suite that
has not been isolated.

## Input classes, and what is bound in each

A description is polled only in the classes it was added to, which is why the pad
was completely inert in dialogue until ICDialog was registered. The rule
everywhere since: register an event in a class only when a dispatcher in that
class was measured to implement it.

| class | what it is | bound |
| --- | --- | --- |
| 0 ICPC | gameplay | both sticks, all face buttons, D-pad, Start; the bumpers, Back and the triggers carry the gameplay verbs (`K1_GAMEPLAY_ACTIONS`) rather than their GUI events; A also bridges to the world action `0xEF` |
| 1 ICMiniGame | Pazaak, swoop, turret | both sticks, plus B / Y / LT / RT -- the four events the minigame dispatchers implement |
| 2 ICPCGUI | menus | both sticks, all face buttons, RB (Black, `0x2B`, since 2026-10-19), triggers, D-pad, Start; LB carries no menu event (since 2026-09-14), nor does Back (since 2026-10-19, when its `0x2B` moved to RB) |
| 3 ICDialog | conversation | A, D-pad up/down, LB, RB: the five events the dialogue dispatchers implement (RB's `0x3A` through a description of its own on RB's slot since 2026-10-19) |
| 4 ICFreeLook | free look | the right stick, and LT to leave (`0x06` on its slot; LB's until 2026-10-19); R3's press here is bridged to the same exit |
| 5 ICMovie | pre-rendered movies | **nothing, and nothing can be** -- see below |

The axes are registered in all six classes; only the buttons are selective.

### Swoop racing and the turret

Since 2026-10-13 (issue #47). Read from the executable; a first build was played once in a
race by the maintainer and corrected from it (CHANGELOG, [Unreleased]). On
2026-10-16 the maintainer confirmed the final swoop prompt works and A, LT and RT
each fire in Steam's turret. They also confirmed A fires in the original Xbox
game, beyond the manual's documented triggers. Start and overlapping holds were
not individually reported as tested.

Class 1 is three different things. Pazaak is two GUI panels, and the row above is
theirs. A swoop race and the gun turret are `CSWMiniGame` (the area's, at
`CSWCArea+0x264`; type 1 and type 2 at `[game+0x80]`), with no panel at all, and
the registrations above gave the pad nothing there:

| What | How the game takes it | Where |
| --- | --- | --- |
| steering, aiming | `CClientExoAppInternal::ProcessInput` polls actions `0x11B` and `0x11E` (and the vertical pair for the turret), holds the sum to -1..1 and calls `CSWMiniGame::UpdateAxis(vector, seconds)`, once a frame | `0x006241DD` (swoop), `0x00624404` (turret); `UpdateAxis` is `0x00670FB0`, `ret 8` |
| the actions | `keymap.2da`: `action283` is the two-button axis `MGActionLeft` (A) and `MGActionRight` (D), `action282` `MGActionUp` (W) and `MGActionDown` (S); the first key of a pair is the positive one | the game's `2da.bif` |
| fire | `MGshoot`, `action217`, Space: its handler calls `CSWMiniPlayer::Fire` on `[game+0x24]` | handler `0x00621CAC`; `Fire` is `0x0066DC50`, no arguments, a plain `ret` |

The stick's own events (`0x3B`, `0x3C`) are polled by nothing on that path, and A's
`0x27` is not registered in class 1 (Pazaak's panels do not implement it).

`NativeMiniGameAxisK1`, hooked at `UpdateAxis`'s entry (`8B 81 80 00 00 00`, `mov
eax, [ecx+0x80]`, one instruction with nothing to relocate; `ecx` the game,
`[esp+4]` the vector):

- adds the left stick to the vector the keys gave, with the gameplay path's radial
  deadzone, and holds the sum to -1..1: `x` plus the stick's right (played: with it
  subtracted the bike went the wrong way), and for the turret `z` plus the stick's
  down (not measured);
- asks the router for `PauseMinigame` (`0xFD`, `HandleInputEvent`, `0x00621210`)
  when Start goes down;
- calls `Fire` once when A goes down, or in the turret either trigger, with
  independent held bits for A, LT and RT. Holding one does not suppress another's
  new press; simultaneous presses request one fire for that frame. Held inputs
  do not repeat. The pause guard (`GetPausedByCombat`, `0x005F2DF0`, as the game's
  handler asks) blocks firing while paused and consumes those presses. In a race `Fire` runs the
  track's `OnFire` script, which starts the bike and changes gear and punishes a
  gear change that comes too early, so a held button must not repeat.

**Correction, 2026-10-16:** the original bridge combined A and the triggers into
one held flag, so holding LT swallowed subsequent RT pulls (and holding A
swallowed both). The bridge now detects rising edges per input. The steering,
Start route, pause guard and hook site are unchanged. To verify in play, hold LT
and repeatedly pull RT, then swap them; repeat with A held, and confirm that a
held input alone does not repeat. An MSVC x86 harness compiled the production
fire block and passed all 512 transitions across previous/current A/LT/RT states,
swoop/turret, paused/running and present/missing client (2026-10-16). The overlap
sequence has not been reported from play; the individual A/LT/RT fire inputs
were confirmed by the maintainer on 2026-10-16. The reproducible source-based
harness is `python testing/regression/Test-MiniGameFire.py` (MSVC x86, no game files).

Not measured: the direction of the turret's vertical axis with the stick, and the
game's "Reverse Minigame YAxis" option, which the game applies to the keys' value
before the hook and which the stick does not get.

#### Swoop shift prompt

Since 2026-10-16, `UpdateSwoopPromptK1` runs from the existing GUI frame
(the controller package still has 38 hooks). The model's `Plane14` uses `abutton`,
which the PC GUI texture pack supplies as a 32x32 Space-key image. Its UV window
is u=0.185497..0.842288, v=0.134816..0.867799. Read with PyKotor from the Steam
game's `chitin.key` model `m17mg_camera` and `swpc_tex_gui.erf`, 2026-10-16.
Four private 128x128 TGA textures (`kmrpp_swoop`, `kmrsp_swoop`, `kmrnp_swoop`,
`kmrdp_swoop`) put the existing family's confirm glyph inside that window; Xbox
and Steam Deck show A, PlayStation Cross, Switch B by physical position.

The GUI frame follows the live area to its type-1 race, then the player's
attached `m17mg_camera` instance and its named `Plane14` part. While class 1 is
active and a connected pad is the active device, that part's material receives
the glyph reference. Keyboard/mouse, disconnect or leaving class 1 restores the
retained original while the race still exists. A turret is never targeted, and
an unloaded race leaves no cached Part or Material pointer to dereference.
The model, animations, shift timing, control mappings and unrelated materials
are unchanged. Missing glyph data keeps the original Space reference.

Read from the local disassembly exports and the clean CD 1.03 executable:
4,042,752 bytes, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`.
Addresses below are Windows virtual addresses; FILE = VA - 0x400000 for this
clean file's original sections. These are reads/calls, with no added hook.

| Address / layout | Purpose | Evidence |
| --- | --- | --- |
| internal `+0x18` -> module `+0x48` -> area `+0x264` | current live mini-game | `ProcessInput`, `0x006227E0` |
| mini-game `+0x80`, `+0x24` | type (1 = swoop), player | `ProcessInput`; camera setup `0x00671670` |
| player `+0x68`, count `+0x6C`; stride 8 | race-owned attached Gob instances | getter `0x0066D260` |
| Gob `+0x58`; model `+0x08` | model resource name (`m17mg_camera`) | Gob constructor/model layout in local disassembly and Lane reference |
| Gob vtable `+0x10C` (`0x004402F0`) | named-part accessor, called with `Plane14` | camera setup `0x00671670`; accessor calls `FindPart`, `0x0043FE00` |
| Part `+0x40`, `+0x44` | owner Gob and material | instance creation `0x004492B0`; material access `0x004434A0` |
| material `+0x00` | first texture reference | `Material::GetTextureTID`, `0x0047AF00` |
| vtable `0x0073F0A8`; reference `+0x10` | CTextureRef and its texture object | constructor `0x00422E30`, getter `0x004205C0` |
| texture `+0x98`, 16 bytes read | resource name | texture lookup `0x00420AC0` |
| `0x00423A60` | create a named texture reference | cdecl, `(name, optionalAlternateName)` |
| `0x00447FA0` | retain/replace a tracked reference | thiscall, `(destinationSlot, newReference)` |
| `0x00420BF0` | ensure glyph loads and obtain its texture id | cdecl, `(textureReference)` |

The retained texture references use the game's ownership list instead of changing
shared art or editing a model. Each GUI update resolves the live target afresh:
no global material registry, discovery cursor or weak target cache remains.
The vanilla ARE player-model lists read from Steam's `tar_m03mg.rim`,
`tat_m17mg.rim` and `manm26mg.rim` contain four, four and five attachments;
`m17mg_camera` is at zero-based index 1, 0 and 1 respectively. Consequently the
code matches the resource name rather than hardcoding one track's array index.
It accepts at most 64 attachments as a corrupt-count guard, then calls the
engine's named-part accessor only on the selected camera model. This accessor
walks that model's part tree: it is a local named lookup, not a global search.

An unchanged cue performs no texture demands, loads, allocations or reference
assignments. Pointer readability checks and the one model-local part lookup still
run each callback; this deliberately trades the previous weak cache for safe
resolution through current ownership, including a rebuilt Part on the same Gob.
A missing glyph keeps Space and retries after 500 ms. No new hook or race-input
state flag is needed; the GUI frame also handles paused activity/family changes.

**Direct-target correction, 2026-10-16:** the intermediate cached-registry DLL
`0FCAAEFD02898E3D6A44F0647B2F479F880916197F2BFF3FDCA8BD2BC1F346ED`
stopped rescanning once it found the material, but still used global discovery
and searched for moved registry entries. The maintainer requested the direct
race/model route instead. The current implementation removes that registry use.

**Performance correction, 2026-10-16:** the first prompt build, controller DLL
SHA-256 `C4B1804C9535895D0EDC37030195403F959F4C40EF594B872FE3539B40F3A03F`,
walked every live material and demanded the glyph from both hooks every frame.
The maintainer reported low FPS in a swoop race. The initial 27 functional checks
did not test this CPU cost. The intermediate cache and bounded discovery replaced that loop; the direct
race/model implementation above supersedes the intermediate cache.

Measured with MSVC x86 `/O2` on this Windows host using the production update
code and real `VirtualQuery`, with synthetic material registries; engine texture
calls were stubbed. The steady-state comparison calls each updater twice per
simulated frame, and the cached code used one GUI callback. These are historical measurements
of the intermediate cache, not timings for the current direct implementation
and not in-game FPS.

| Materials | Old steady ms/frame | Cached steady ms/frame | Largest new discovery update, ms |
| --- | --- | --- | --- |
| 500 | 1.483876 | 0.000024 | 0.101700 |
| 2,000 | 5.852572 | 0.000022 | 0.092800 |
| 5,000 | 15.095986 | 0.000022 | 0.150200 |

`python testing/regression/Test-SwoopPrompt.py` compiles the current production
updater with fake race/model objects and passes 47 checks: every attachment
position in four/five-model lists, all glyph families, activity/disconnect/class
changes, missing glyph load/demand with retry throttling, invalid/no race, turret
exclusion, foreign art, ownership mismatch, and a new Part/material on the same
Gob. Across 100 unchanged updates per family, it verifies one targeted part lookup
and at most 22 pointer checks per callback, with zero texture loads/demands or
assignments. Unrelated material count does not affect those bounds. The previous
114 registry-cache checks are superseded. It needs MSVC x86, without game files.
The controller package regression and its 38 guarded hook sites also pass.
On 2026-10-16 the maintainer reported "perfect it works" after testing the direct
implementation in Steam (the installed controller DLL was SHA-256
`6637A3D78A3C78EC2FC61E71D8DCF9D64981854C02058FAC8D00AC10B5EBAC4E`).
No numerical in-game FPS measurement was taken. The
other glyph families, device changes while paused and unplug/reconnect were not
individually reported as tested. To check them: reach the shift point with the
pad, then use the keyboard or mouse: the cue should switch A/Space in the same
place; repeat while paused, unplug/reconnect the pad, and return to menus. The
light's appearance, flashing and disappearance must remain the game's own.

**ICMiniGame is registration on evidence, not on a pressed button.** From the
retained inventory, `PAZAAK_SETUP` (`0x006816F0`) implements `0x28`/`0x2E`,
`0x2A`, `0x35` and `0x36`, and `PAZAAK_GAME` (`0x0067E8F0`) implements
`0x28`/`0x2E`. Neither implements `0x27`, so A is deliberately left out rather
than sent into a default case. Pazaak, swoop and the turret cannot be reached
from the save the harness loads, so no minigame button has been observed
working; the suite checks that the four registrations took and marks the
behaviour itself as human-QA.

**Pazaak's table answers the pad through the module, not through class 1.** Since
2026-10-11 (issue 42) A played the focused hand card, and since 2026-10-19 (issue
49) the table takes the Xbox game's buttons, "(X) Play Hand Card, (White) Flip Hand
Card, (A) End Turn, (Y) Stand": rows of `K1_BUTTON_REMAPS`, asked about in class 2
and class 1 alike because which of the two the table runs in has not been measured
(`RemappedButtonEventK1`). The press is suppressed and performed on the GUI frame,
through the table's own handlers:

| Button | Does | Through |
| --- | --- | --- |
| X | plays the focused hand card | the mouse's click on it, `0x0067EF80` (A's from 2026-10-11 to 2026-10-19) |
| A | End Turn, `BTN_XTEXT` at `+0x6C4C` | `HandleContinue`, `0x0067EC20`, with the button |
| Y | Stand, `BTN_YTEXT` at `+0x6E20` | `HandleStand`, `0x0067ED00`, with the button |
| LB | flips the focused hand card | its flip button's click, `0x0067DDA0` (`BTN_FLIP0..3` at `+0x62BC`, `0x1C4` apart) |

Each acts only while its button is on screen and enabled, and all four are taken
whenever the table is the front panel, so the engine's own A never reaches a hand
card. `InstallPazaakTableK1` keeps the D-pad off End Turn, Stand and the four flip
buttons (`KmrpPadFocusExcludeK1`) and makes two labels from the table's own
`LBL_FLIPICON` and `LBL_FLIPLEGEND` for an "X Play Hand Card" line (dialog.tlk
32330); `UpdatePazaakTableK1` shows them, and LB on the flip legend's icon, only while
the pad is in use; `ForgetPazaakTableK1` frees them at the table's end. Offsets and
handlers are as the code's notes record them from `CSWGuiPazaakGame`'s constructor
(`0x00680FBC` on), not disassembled again for this note. **Not played**: no save the
harness loads reaches a table.

**Deliberately unbound.** X (`0x29`) and Black (`0x2B`) in gameplay: the
`AddEvent` survey found X registered exactly once in the whole executable and
Black not at all, so there is nothing for them to do that is not invented. The
mouse-look camera in class 2 has no meaning. Nothing at all is registered in
class 5. (Since 2026-09-14 Back's slot carries the Solo Mode query in gameplay,
and from 2026-09-25 X pressed the HUD's Disengage button in combat, neither
through these two events: "The gameplay HUD action bar", below, and *Gameplay
verbs* in [`controller-parity.md`](controller-parity.md). Since 2026-10-19 X in the
world asks for the world action, as A does, and B disengages; Black is RB's menu
event, while RB's slot carries `0x09` ChangeChar in gameplay. Neither event has a
meaning in gameplay still.)

## Movies

`ICMovie` has no reachable retained consumer, and this is structural rather than
an omission: a pre-rendered movie owns the game loop inside
`CExoMoviePlayerInternal::PlayMovieLoop`, so `CExoInput` is never polled while
one plays. A description added to class 5 could never receive a value. The only
way in is a bridge from inside that loop, which is what `NativeMovieFrameK1` at
`0x00404D96` is.

It calls the engine's own `CExoMoviePlayerInternal::CancelMovie` @ `0x00404C40`
as `CancelMovie(player, 0, 0)`. The second argument is a force flag: non-zero
takes the branch at `0x00404C5C` and raises the cancel flag unconditionally,
while zero goes through the engine's own guard --

    cmp dword ptr [ecx+0x30], 1     ; is this movie cancellable at all
    jne 0x00404C69                  ; if not, only record the result field

-- so passing zero honours the game's rule about which movies may be skipped
instead of overriding it. The keyboard's Space path does the same.

**A and Start** skip. Both are conventional and neither means anything else
while a movie is on screen. B and LB are equally safe -- nothing consumes them
here -- and are left out only because four buttons on one action makes an
accidental skip likelier; `K1_MOVIE_SKIP_MASK` is one constant if that changes.

**One press, one skip.** The state arms on a *release*, not on entry: a button
already down when the movie starts -- the A that dismissed a menu, the Start
that began a new game -- must not count as a press against the movie that
follows, or the startup logos skip themselves. A new player pointer disarms
again, so nothing is left pending when a movie ends.

Verified from a cold launch by `testing/controller/test_movie_skip.py`: 122 loop
iterations observed, 3 cancels from 4 presses.

**This hook shares an address with Saul0097's `PollMovieControllerK1`.** Two
hooks cannot occupy one instruction, so `select_controller_path.py` drops the
legacy entry in "both" mode; the native one supersedes it.

## The gameplay HUD action bar

The bottom-right action bar is driven with the D-pad, through **Saul0097's
existing implementation**, unchanged. `MoveFocus`, `CycleAction` and the activate
callback in `vendor/K1XboxControls.cpp` already call `CSWGuiMainInterface`'s own
functions; none of that was rewritten.

| what | address | role |
| --- | --- | --- |
| `getIsSelectable` | `0x004189D0` | can this slot take focus |
| `setActiveControl` | `0x0040A630` | move the highlight |
| `targetPrevious` / `targetNext` | `0x006884B0` / `0x00688520` | cycle a target-action slot |
| `personalPrevious` / `personalNext` | `0x0068AF70` / `0x0068AFE0` | cycle a personal slot |
| `activate` | `0x0068B970` | use the selected action |

**What KMRP replaces is only how the intent arrives.** His
`CaptureActionBarInput` reads buffered **keyboard** records -- `DIK_LEFT`,
`DIK_RIGHT`, `DIK_UP`, `DIK_DOWN`, `DIK_RETURN` -- which is why his path needs
the XInput layer to synthesise arrow keys first. KMRP's D-pad already exists as
controller state, so `NativeActionBarK1` (hooked at `0x00686BA0`, the same site
his `UpdateActionBarControlsK1` uses) raises the same pending bits directly and
**no key is ever synthesised**.

* **Left / right** move one slot, wrapping across the seven.
* **Up / down** cycle the action within the focused slot.
* **A** uses the focused slot.

`FindSelectableButton` skips the three target-action slots while nothing is
targeted, which is the engine's own rule, so on a normal save the walk covers the
four personal slots.

**Cycling is a no-op on a slot with one action, by the engine's design.**
`0x00688820` reads the count at `mainInterface + 0x78 + slot*0x0C` and returns
early at `0x006888B1` (`cmp [count], 1` / `jle`). The current action is at
`mainInterface + 0x1BAC + slot*4`, which is the field to watch -- the focused
*control* does not change when the action does, and watching it instead makes a
working cycle look dead.

**A has exactly one destination.** It uses the slot while a slot has focus, and
performs the world action otherwise. Both consumers ask
`KmrpActionBarFocusedK1`, so precisely one acts however the two per-frame hooks
happen to be ordered within a frame. Since 2026-10-01 "has focus" means a slot
that can still act (`IsActionButtonSelectable`, the D-pad's own test): a target
slot keeps the focus after the target changes to a door, which has no actions
there, and A went to the empty slot instead of opening the door (seen on the Mac).
B asks `KmrpActionBarHeldK1`, any focused slot, so it still lets go of one.

**Using a slot keeps the bar; B lets go of it (issue #17).** After the
activate callback -- `CSWGuiMainInterface::OnDefaultActionLeft`, `0x0068B970`,
which performs the action and does not touch focus -- the slot stays focused, so
A can be pressed again at once. **B** lets go of the bar:
`KmrpActionBarReleaseK1` clears the focus the way the vendor's Delete path does,
`setActiveControl(mainInterface, nullptr, 1)` when an action slot holds it. Until
2026-10-19 B had no other effect in the world (behaviour matrix, gameplay); since
then B with no slot to let go of disengages (below). Left/Right
re-enter through `MoveFocus`'s `activeIndex < 0` seed. `hrel=` in the
diagnostic line counts the releases. When the HUD takes an A it still clears the
world consumer's pending request, so one press does exactly one thing.

*Changed 2026-09-25:* until then a used slot let go of the bar as well, so the
next A acted on the world. In combat that meant D-pad Right before every
action, and the user asked for the bar to stay focused. **Neither version has
been verified by `test_hud_release_and_start_map.py` on a loaded save.**

**X disengages and Y removes the last queued action, in combat (2026-09-25).**
The input hook only records the press, in gameplay (class 0).
`NativeActionBarK1` then presses the HUD's own button on the next HUD frame:
- Y presses `BTN_CLEARONE` through `OnClearOneButtonPressed` (`0x0068B050`),
  which calls `OnCombatYButton`, the Xbox build's Y in combat;
- X presses `BTN_CLEARALL`, the Disengage button, through
  `OnClearAllButtonPressed` (`0x0068B0A0`).

The button itself is passed as the argument, so a press is exactly a mouse
click, tutorial included. A press only acts while its button is drawn,
`CSWGuiControl` flags bit 2, the test `OnClearOneButtonPressed` makes itself.
The request is taken whatever happens on that frame, so a press can never act
later on another screen. X's and Y's GUI events `0x29`/`0x2A` still go out, and
gameplay still ignores them. A badge beside each button, `LBL_KMRPX` and
`LBL_KMRPY`, shows while that button does (see
[`reverse-engineering/custom-gui-controls.md`](../reverse-engineering/custom-gui-controls.md)).
**Untested in game.**

**Changed 2026-10-19 (issue 49): B disengages, X adds to the queue, Y flourishes
when nothing is queued.** As on the Xbox ("COMBAT MODE engaged. (B) to disengage."):
- B with no slot to let go of presses `BTN_CLEARALL` (`KmrpActionBarHeldK1` found
  none), with either HUD; until then only the Xbox-style HUD did this, and X did it
  with both.
- X asks for what A asks for, the world action or the focused slot, because on the
  Xbox X added an action to the queue and on the PC every action is queued.
- Y presses `BTN_CLEARONE` as before, and when that button is not drawn
  (`PressHudButtonK1` returns false: not in combat, or nothing to clear) it asks for
  a flourish instead, the request L3 makes (`PerformPendingStickActionsK1`).

The Disengage badge, `LBL_KMRPX`, shows B (its file fill `kmrpb_cmbt`; the tag is
kept). **Not played.**

**The D-pad's retained codes are suppressed in gameplay**, for the same reason
they are in menus: one press, one mechanism. Nothing else in gameplay consumes
`0x2F`..`0x32`.

This hook shares an address with Saul's `UpdateActionBarControlsK1`, so
`select_controller_path.py` drops the legacy entry in "both" mode.

## The engine rebuilds the input object, and the module has to notice

Playing a movie destroys `CExoInputInternal` and constructs a new one. Every
event this module registers lives on the old object, and the old object is
freed.

This was found from a crash reported in play: a Bastila vision that ended on a
black screen with only the HUD, then `0xc0000005` at `0x005E0DFB`. Four things
were measured on the way, and three earlier explanations were wrong and are
recorded in the commit history rather than here.

**What the crash is.** `0x005E0DFB` is inside
`CExoInputInternal::IsEventInClass`, which indexes a per-class record at
`this + class * 0x30` and reads a bitmap pointer at `+0x2C` guarded by a length
at `+0x30`:

```
005E0DB3  cmp ebx, edi        ; edi = the length
005E0DB5  jl  skip-grow       ; "big enough" -> do not reallocate
005E0DEA  mov eax,[esi+0x2c]  ; the bitmap
005E0DFB  mov ecx,[eax+ebx*4] ; <- the fault
```

**What the state is.** Logging every class record each frame showed all six
going null after playback with their lengths untouched:

```
mve=58    ptr=03EBBA88 size=13     ... six records, all valid
mve=204   ptr=00000000 size=13     ... six records, all null
```

A length left behind by a freed pointer is what makes this fatal: the engine
believes the array is long enough, skips its own reallocation, and dereferences
null. Note that this is *not* what `CExoArrayList<unsigned long>::SetSize(0)` at
`0x00405150` does -- that zeroes the counts as well -- so the buffers were freed
by a destructor, not resized.

**Why it reached that state.** The hook at `0x005E24E0` fires with the input
object; it is named `NativeJoystickInitK1` here but the Ghidra reference names
it `CExoInputInternal::GetEvents`, and it runs every frame, not once. Logging
the pointer it carries:

```
JOYINIT call=1    input=03F03E60  cached=00000000  registered=0
JOYINIT call=508  input=18F5D008  cached=03F03E60  registered=1
```

The module latched on a `registered` flag alone, so it returned early on the new
object and went on using the freed one -- writing the device count into freed
memory once a frame, and leaving every registration stranded where nothing would
read it.

**The fix, and why it is not a pointer comparison.** Comparing object pointers
was tried first and was not enough: the allocator may hand back the same address
for the new object, in which case a pointer test reports "already registered",
registration is skipped, and the pad half-dies instead of crashing. That is
exactly how it presented -- the crash stopped and LT/RT stopped with it.

So the object is asked instead. `DescriptionPresentK1` reads the description
table at `[input+0x128]`, indexed by event id and bounded by `[input+0x12C]` --
the same table `AddEvent` reads at `0x005E0FB3` -- and a null slot for an event
this module registered means the registration is gone, whatever the address
says. Registration is idempotent to match: `CreateNewEvent` returning 0 is only
a failure when the description is genuinely absent, because it also returns 0
for one that already exists.

**The same crash from a change of resolution (2026-10-11).** That fix made the
`GetEvents` hook notice a new object, and left the pointer cached between two runs of
the hook. A change of resolution in the game destroys the object too (`0x00604344`
deletes the `CExoInput` at `0x007A39E4` and zeroes the global), from the Options
screen's OK, which the frame reaches after `GetEvents`. With a save loaded the
movement hook then ran later in the same frame with the old pointer. Measured on
SteamOS 3.8 under Proton 11.0-100, Steam executable, the controller module's build
`8659381A`, four sessions, each dying on the second or third switch between 1280x800
and 3440x1440:

| Fault | Where in the module | What it was doing |
| --- | --- | --- |
| null read at `0x005E0DFB`, three times | called from module `+0x9968`, in `NativeJoystickDumpK1` | polling events 7 and 8 on the destroyed object |
| read of `0x00200753` at module `+0x5556`, once | `EnsureDeviceCountK1` (`EnsurePadStateK1` inlined) | `[input+0x140]` of the freed object held `0x00200723`, taken for the raw-input pointer |

The offsets were resolved with that build's `.map`. `LiveStickInputK1` now gives the
cached pointer only while `[[0x007A39E4]+4]` is still it and the module's description
is on it, and the device count, the pad's state block, the stick read and the dump
all go through it. **Not verified where it failed:** the fixed module was built and
passed `Test-ControllerKpatch.py`, which starts no game; the crash was not reproduced
on Windows, where the same use of freed memory is present and has not been seen to
fault. The handoff also tied the crash to launches whose log says "after its window; 3
other thread(s)"; that link is not explained by this and was not investigated.

### `add=[0 3 3 3 0 3]` is correct, and always was

Classes 0 (ICPC) and 4 (ICFreeLook) return 0 from `AddEvent` for the two analog
axis events. That is not a failure. `AddEvent` returns 0 when the event is
**already in that class**, and those are the two classes where vanilla KOTOR
already registers an analog stick.

Forcing them was tried, on the theory that the structures did not exist yet at
init. A retry every frame for a whole session won none of them back
(`cls=0/1024`), and the crash happened anyway with the device count never
raised. Registering them would create duplicates, not fix anything.

### The pad slot needs a state block, not just a count

Raising the device count is only half of claiming a pad exists. The other half is
the raw state block, and leaving it out crashed free look.

`CExoRawInputInternal::GetLastState` indexes a per-pad array:

```asm
005E397F  add  eax, -2            ; joystick ordinal = device index - 2
005E3982  imul eax, eax, 0x74     ; 0x74 bytes per pad
005E3985  add  eax, [ecx+0x30]    ; + the array base
005E399B  mov  eax, [eax]
```

`CExoRawInputInternal+0x30` is null on a machine with no DirectInput joystick,
which is every machine KMRP targets — the pad arrives through XInput, not
DirectInput. Measured live under x32dbg: base 0, fault at `0x005E399B` with
`eax = 0`, called from `CExoInputInternal::GetEvents` at `0x005E2968` with
`(2, 0)`.

**Why free look and not gameplay.** Vanilla registers its analog stick events in
`ICPC` and `ICFreeLook` only — the same fact recorded above under
`add=[0 3 3 3 0 3]`. The free-look enter handler at `0x006216C7` calls
`CExoInput::ClearEvents`, which empties the buffered records the pad's input
normally arrives through, so the next `GetEvents` asks for **raw** state instead
and reaches the null base. Offset `0` in that call is `DIJOFS_X`.

**Why allocate rather than detour.** Only two functions in the image index the
array:

| site | function | status |
| --- | --- | --- |
| `0x005E31D4` | `CExoRawInputInternal::GetJoystickBuffer` | already declined by the module's hook at `0x005E30F6` |
| `0x005E3982` | `CExoRawInputInternal::GetLastState` | unguarded — this was the crash |

A capstone sweep of `0x005E2E00`-`0x005E3A00` finds three reads of `[reg+0x30]`,
no store, and no null test, so nothing gates behaviour on the pointer and nothing
frees it. `EnsurePadStateK1` allocates four slots with the engine's own
`operator new` and only when the slot is null, leaving a real joystick's own
block alone.

**Rejected: detouring `GetLastState`.** The first attempt hooked `0x005E3951`
with its parameter sourced from `EAX` and `exclude_from_restore = ["eax"]`. KPM
leaves the handler's return value in `EAX`, so the re-executed
`cmp eax,[0074D3D0]` compared that return value against the joystick index, not
the device index; both possible returns are below 2 so the following `jl` always
jumped. It did not fix the crash and it broke device-activity detection, making
the prompts flicker between keyboard and pad. **A parameter sourced from a
register cannot be combined with excluding that register from restore when the
stolen bytes read it.**

**The wrapper's order, which both lessons follow from.** KPM's detour wrapper
(Kotor-Patch-Manager, `wrapper_x86.cpp`) calls the handler, restores every
register except those in `exclude_from_restore`, runs the **stolen bytes**, and
only then, for a hook with `consumed_exit_address`, tests EAX to choose the
consumed exit. So a consumed-exit hook's stolen bytes must neither touch EAX nor
move ESP. The Solo Mode confirm hook broke the first rule: it stole
`mov eax,[0x7A39FC]`, the test read the app pointer, and every A on that dialog
took the close path, OK included. The resolution hook broke the second with a
stolen `push 0`. Both were moved to their handler's entry, where they rewrite
the event argument (a stack source such as `esp+4` is passed as a pointer)
instead of using a consumed exit. `tools/check_hook_stolen_bytes.py` enforces
both rules and the excluded-register one above.

## Why movies had grey margins

The aspect-fit patch lives in `CExoMoviePlayerInternal::InitializeMovie+0x3CC`
and is correct: a 640x272 movie on 3440x1440 was measured at 3388x1440 with
`bink_buffer_offset_x/y` of 26,0, which is exactly centred. (*Since 2026-10-20* the
fit is to a 16:9 area, so the same movie is 2560x1088 at 440,176, computed from the
source and not measured: [movies](../reverse-engineering/movies.md), *The 16:9 area*.)

But vanilla scaled to the window's full *width* and let the picture overflow
vertically, so it always overfilled the surface and no part of it was ever left
unwritten. Fitting properly leaves 26px columns that `BinkCopyToBuffer` never
touches, and they showed whatever the surface already held -- grey down both
sides, and a grey frame before playback began.

`ClearMovieSurfaceK1` black-fills the surface once per playlist entry through
`BinkBufferLock`/`BinkBufferUnlock`, bounds-checked before the write. Once is
enough, because the copy only ever writes the picture rect.

This is not controller code, and since 2026-10-05 it belongs to KMRP's patch
alone (`KmrpCoreMovieWorkK1` at `0x00404D06`, with `NativeMovieWindowOpenK1` and
`NativeMovieWindowCloseK1`). The controller patch's movie frame only reads the
pad for the skip (`KpmMoviesOffK1` returns true in its module), and without KMRP
the aspect fit that leaves those margins is not applied either.

## Testing

Read on 2026-10-08: the package is checked without a game by
`testing/regression/Test-ControllerKpatch.py`, and the runs in a game since
2026-10-05 were made in scratch copies with KOTOR Patch Manager 0.7.1's launcher
and `testing/controller/virtual_pad_server.py`
([`controller-standalone.md`](controller-standalone.md), section 8). The two
tools below date from the installer that put `kmrp-controller.module` beside the
game (until 2026-09-29); neither has been brought up to the two patches, and
whether `test_native_input.py` still runs against a current install was not
tried.

* `testing/controller/select_controller_path.py [saul|native|both]` switches the
  install. All of the legacy path's controller input is driven from
  `DispatchMenuInputK1`, so dropping that one hook silences it.
* `testing/controller/test_native_input.py` is the regression suite. It proves
  every binding from memory rather than by eye, and skips the analog tests when
  not in gameplay rather than reporting a meaningless failure.

**Run the suite in gameplay, not at the main menu.** It presses A and B, which at
the menu will start a new game.

### The pad server's vocabulary is not the button names

Three separate "failures" in this work were the test harness, not the game:

* `press RT` / `press LT` are **not valid**. The triggers are analog and are
  driven with `triggers <l> <r>`. Sending `press RT` returns
  `err unknown button` and the ad-hoc script that ignored the reply recorded a
  0.0% screen change, which read as "screen cycling is broken". It is not:
  driven properly, LT and RT cycle screens by 14–27% per press.
* The D-pad is `UP` / `DOWN` / `LEFT` / `RIGHT`, not `DPAD_UP` and friends. The
  same silent-error path produced "the D-pad does not move menu selections".
  Driven properly, all four events are delivered and the screen responds.
* The `dpad` and `tap` verbs press **and release** before replying, so a sampler
  that reads after the reply always reads the released state. Use
  `press` / `release`.

**Check the reply.** Every one of these returned `err` and every one was
discarded. Any harness added here should assert on it.

## Hybrid physical input (2026-09-19)

`ReadPadAxes` now consumes `ReadControllerK1`, preserving its XInput-shaped state
and the existing engine event mapping. SDL/HIDAPI supplies non-Xbox physical
pads; XInput remains the Xbox path. Rumble and glyph identity follow the selected
backend. See [controller-sdl-backend.md](controller-sdl-backend.md) for the pinned
32-bit dependency, normalization, ownership, and untested hardware/runtime cases.
The earlier source path under `build/research` above is historical; tracked native
code lives in `src/controller-native`.
