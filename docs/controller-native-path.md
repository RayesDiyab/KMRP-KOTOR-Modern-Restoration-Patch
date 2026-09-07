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

`UpdateCamera` has exactly two inputs and only one is analog.

* Event `0x11C` is a **two-button axis on the keyboard device**, `DIK_A` and
  `DIK_D`. Descriptions are one per event id, so no joystick description can be
  added for it.
* The accumulated mouse delta **is** analog. `GetMouseDelta` is a plain read of
  `CExoInputInternal+0x3A0` and `+0x3A4`, and `UpdateCamera` scales the X
  component by the mouse sensitivity setting before `CSWCModule::TiltCamera`.

The right stick is added to `+0x3A0` from the `GetEvents` hook, which
`ProcessInput` calls after `UpdateMouseDelta` computes the delta and before
`UpdateCamera` consumes it. No new hook, no cursor movement, and a real mouse
keeps working in the same frame.

**There is no vertical camera axis.** The Y delta slot is overwritten with the
invert sign before use (`mov [esp+0x18], eax` at `0x005F5ECC`) and never read.
`ScrollCamera` and `ZoomCamera` take computed values, not input. This was traced
rather than assumed, and nothing should be invented for it.

`K1_CAMERA_SPEED` is a named constant in mouse-pixels-per-frame, before the
game's own sensitivity multiplier. It has **not** been tuned against a real
mouse.

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
