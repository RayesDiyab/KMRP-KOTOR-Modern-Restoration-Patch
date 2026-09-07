# The native controller path

KOTOR's PC build kept the console input system almost intact. What it lacks is a
joystick *device*: the count is a hardcoded zero and nothing produces records.
Supply those two things and the engine drives itself — analog movement, buttons,
screen cycling and camera all run through its own handlers, with no synthetic
keystrokes anywhere.

The reverse engineering behind every address here is in
`reverse-engineering/retained-xbox-gui-events.md`.

## What the module does

Four hooks, in `build/research/KPM-Xbox-Controls-K1/K1NativeJoystick.cpp`:

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

All bindings are registered in both input class 0 (gameplay) and class 2 (GUI).

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

**Nothing currently ships as B.** It was the fallback planned for Start and
turned out to be unnecessary. The one place it may still be warranted is
main-menu navigation (below).

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

**Screens that navigate themselves.** Six panels implement the direction events
in their own dispatcher — `ABILITIES`, `ABILITIES_CHARGEN`, `FEATS`, `MAP`,
`POWERS`, `SKILLS` — and a focused list box, editbox or slider consumes them
itself. In both cases the layer declines and the retained events do the work.

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
**radial 8%** applied in the module, with the remaining travel rescaled to the
full range. 8% clears the test controller's measured 4.8% resting drift and sits
inside the 5–8% modern practice band.

`K1_STICK_DEADZONE` and `K1_CAMERA_DEADZONE` are named constants, tunable
without touching logic.

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
| 0 ICPC | gameplay | both sticks, all face buttons, bumpers, triggers, D-pad, Start; A also bridges to the world action `0xEF` |
| 1 ICMiniGame | Pazaak, swoop, turret | both sticks, plus B / Y / LT / RT -- the four events the minigame dispatchers implement |
| 2 ICPCGUI | menus | both sticks, all face buttons, bumpers, triggers, D-pad, Start |
| 3 ICDialog | conversation | A, D-pad up/down, LB, RB -- the five events the dialogue dispatchers implement |
| 4 ICFreeLook | free look | the right stick, and R3 to leave |
| 5 ICMovie | pre-rendered movies | **nothing, and nothing can be** -- see below |

The axes are registered in all six classes; only the buttons are selective.

**ICMiniGame is registration on evidence, not on a pressed button.** From the
retained inventory, `PAZAAK_SETUP` (`0x006816F0`) implements `0x28`/`0x2E`,
`0x2A`, `0x35` and `0x36`, and `PAZAAK_GAME` (`0x0067E8F0`) implements
`0x28`/`0x2E`. Neither implements `0x27`, so A is deliberately left out rather
than sent into a default case. Pazaak, swoop and the turret cannot be reached
from the save the harness loads, so no minigame button has been observed
working; the suite checks that the four registrations took and marks the
behaviour itself as human-QA.

**Deliberately unbound.** X (`0x29`) and Black (`0x2B`) in gameplay: the
`AddEvent` survey found X registered exactly once in the whole executable and
Black not at all, so there is nothing for them to do that is not invented. The
mouse-look camera in class 2 has no meaning. Nothing at all is registered in
class 5.

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

## Testing

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
