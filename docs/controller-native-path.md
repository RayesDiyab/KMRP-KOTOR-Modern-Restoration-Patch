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
| Right stick X | — | — | — | camera, via the mouse-delta field | registered, feel untested |
| Start, L3, R3 | — | — | — | **unbound** — see below | n/a |

All bindings are registered in both input class 0 (gameplay) and class 2 (GUI).

### Why Start, L3 and R3 are unbound

The slot budget is fixed. Joystick button slots run `0x74`..`0x7E`, which is
eleven, and `0x7C` belongs to the game's own event `0x0B`. Ten remain, and twelve
pad controls do not fit. No retained console event was found for Start, L3 or
R3, so spending a slot on a guess would cost one that has a real action. They
stay on the legacy path.

### Why `0x2D` and `0x2E` are not used

They look attractive — implemented by 20 and 30 panels — but they resolve to the
same handlers as A and B wherever they appear. On `CSWGuiInGameCharacter` all of
`0x28`, `0x2D` and `0x2E` reach `0x006B2459`. They are confirm/cancel aliases,
not distinct actions.

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
