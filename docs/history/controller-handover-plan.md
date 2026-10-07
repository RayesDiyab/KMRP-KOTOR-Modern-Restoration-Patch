# Handover: which parts of the legacy controller path the native one replaces

> **Parity and the remaining gaps** are in [`controller-parity.md`](../controller-parity.md). This file is about what may be *removed*; that one is about what is still *missing*.

**Status, checked against the code on 2026-10-08: the removal was never carried
out, and nothing below is installed any more.** The legacy sources are still
compiled into both modules (`BUTTON_BINDINGS`, `ApplyLeftStick` and
`ApplyRightStick` in `vendor/K1XboxControlsXInput.cpp`), but neither patch KMRP
ships installs `DispatchMenuInputK1`, the one caller of `PollXInputK1()`, so none
of it runs. What ships is the controller patch, `KOTOR 1 Native Controller Mod +
Xbox HUD.kpatch` (id `kmrp-controller`, 34 hooks from
`tools/build_controller_kpatch.py`; [`controller-standalone.md`](../controller-standalone.md)).
Read the tables below as the record of 2026-09-07, with these differences:

- *Not superseded -- still required*: of its hooks only `ClearActionBarControlsK1`
  is installed. `OnSetActiveControlK1`, `CancelMovieOnSpaceK1` and
  `PollMovieControllerK1` are in `kotor1.hooks.toml` and never installed, like
  the action-bar capture and update hooks and the mouse-move hook. Four native
  hooks hold four of those sites: `NativeMovieFrameK1` (`0x00404D96`),
  `NativeActionBarK1` (`0x00686BA0`), `NativeNoteKeyboardK1` (`0x005E271E`) and
  `NativeNoteMouseK1` (`0x0040C1F6`); nothing is hooked at `0x0040A638` or
  `0x004051C3`. The device-switching and cursor code is still called by the
  native path.
- *Awaiting human QA*: the camera, menu navigation and LT/RT were played on a
  real pad on 2026-09-08 ([`controller-playtest-checklist.md`](../controller-playtest-checklist.md));
  `K1_CAMERA_SPEED` is 1.0, a full keyboard turn, and the movement deadzone is
  15%, not 8% (`K1_STICK_DEADZONE`, `K1NativeJoystick.cpp`).
- *Controller prompts*: the badge counts are those of 2026-09-07. LB, RB, Back
  and Start changed meaning again afterwards, and the cues and badges added since
  are in [`controller-prompt-specification.md`](../controller-prompt-specification.md).
- `testing/controller/select_controller_path.py` writes the install layout of
  before 2026-09-29 (`kmrp-controller.module` beside the game), which nothing
  builds any more.

Nothing is deleted here. The point is to make a later removal mechanical, by
recording exactly what has a native equivalent and what does not, with the
evidence for each.

The legacy path is the KPM Xbox Controls module by Saul0097, which reads XInput
and synthesises keystrokes. Its entire controller input is driven from one place:
`PollXInputK1()` is called only from `DispatchMenuInputK1`. Dropping that hook
silences all of it, which is what `select_controller_path.py native` does.

## Superseded, and verified

| Legacy component | What it did | Native replacement | Safe to disable? |
| --- | --- | --- | --- |
| `ApplyLeftStick` W/S/Z/C synthesis | stick → movement keys | events `0x07` / `0x08`, the game's own analog axes | **yes** — and it must be, see below |
| `ApplyLeftStick` walk modifier (`SC_B`) | held below a run threshold | none needed; movement is proportional | **yes** |
| A → `SC_RETURN` | confirm | event `0x27` | yes |
| B → `SC_DELETE` | cancel | event `0x28` | yes |
| X → `SC_G` | per-panel | event `0x29` | yes |
| Y → `SC_F` | per-panel | event `0x2A` | yes |
| LB → `SC_SPACE` | — | event `0x39`, description scroll up | yes |
| RB → `SC_TAB` | — | event `0x3A`, description scroll down | yes |
| LT → `SC_Q` | screen cycling | event `0x35`, `PrevSWInGameGui` | yes |
| RT → `SC_E` | screen cycling | event `0x36`, `NextSWInGameGui` | yes |
| Back → `SC_V` | — | event `0x2B`, Black | yes |
| D-pad → arrow keys | menu navigation | events `0x31`/`0x32`/`0x2F`/`0x30` | yes, in the in-game menus; **not** on the main menu, which implements no scroll events |
| Start → `SC_ESCAPE` | open the menu | event `0x0B`, the game's own description | yes — opens; **B** is the close |
| `ApplyRightStick` → `SC_A`/`SC_D` | camera turn | `CSWCModule::RotateCamera` from `NativeCameraFrameK1` @ `0x006039CF` | yes — playtest-confirmed; `+0x3A0` was a dead field |

**Changed since this table was written**, read from the code on 2026-09-24: in
gameplay LB, RB, Back, LT and RT now carry gameplay verbs -- target cycling,
the Solo Mode query, the party member and pause -- and LB and RB carry no menu
event (the right stick scrolls descriptions); Start in the world opens the Map
rather than the menu; R3 switches party member on the four party screens. The
native column shows the first replacement, and the legacy keys it replaced are
still superseded. See [`controller-parity.md`](../controller-parity.md).

**The left-stick synthesis is actively harmful alongside the native path**, not
merely redundant. Running both drove the same movement fields from two sources
and the walk modifier halved whatever the native path had just written. That is
what produced movement in every direction at inconsistent speeds. The existing
`NativeMovementOwnsLeftStickK1` gate already stands it down during gameplay.

## Not superseded — still required

| Legacy component | Why it stays |
| --- | --- |
| `OnSetActiveControlK1` | fixes a `SetActiveControl` focus bug; unrelated to how input arrives |
| Movie skip (`CancelMovieOnSpaceK1`, `PollMovieControllerK1`, `ConsumeMovieSkipK1`) | the normal input loop is suspended during Bink playback, so no record ever reaches the engine |
| Action bar capture and update hooks | UI integration, not input transport |
| `CancelActionBarKeyboardFocusOnMouseMoveK1` | focus behaviour |
| `IsControllerInputActiveK1`, cursor hiding, device switching | the prompt system and cursor policy both depend on it |
| — | *(nothing; L3 and R3 now have native and bridged bindings respectively)* |

## Awaiting human QA before disabling anything

| Item | Why it needs a person |
| --- | --- |
| Camera speed | `K1_CAMERA_SPEED` is unmeasured against a real mouse |
| Deadzone size | 8% is defensible but a feel judgement |
| D-pad direction mapping | registration is proven; which POV code is which direction is inferred |
| Menu navigation end to end | the suite proves events arrive, not that every screen responds sensibly |
| Screen cycling on LT/RT | proven to reach `Prev/NextSWInGameGui`; not watched in play |

## Controller prompts

The prompt textures are generated at install time and are **not** affected by
this work — they are art plus STRREF-driven placement, not input.

What does need checking is whether the labels still describe what the buttons
do. Most survive because the native mapping is semantically identical: A still
confirms, B still cancels, X and Y remain per-panel. Three changed meaning:

| Button | Legacy | Native |
| --- | --- | --- |
| LB | Space | description scroll up |
| RB | Tab | description scroll down |
| Back | V | Black |

`tools/audit_controller_prompt_coverage.py` reports which screens have prompts.
Run 2026-09-07: **31 strip buttons, 22 carrying a badge (71%)**. All nine gaps
are the same control — the "Default" button on the options screens, plus Key
Mappings and the two in-game option panels. That gap predates this work and is
unrelated to the native path; closing it is texture and placement work, and it
needs somebody to decide which button "Default" should depict.

The audit now checks truthfulness as well as coverage, and the answer is a good
one: **all 30 badges depict A (8), B (19) or X (3)**, and those three are exactly
the buttons whose meaning did not change. A still confirms, B still cancels, X is
still the per-panel action. **No existing badge became misleading.**

Every binding whose meaning did change, or that is new, has no badge at all:

| Button | Legacy | Native | Badge still accurate? |
| --- | --- | --- | --- |
| LB | Space | description scroll up | needs checking |
| RB | Tab | description scroll down | needs checking |
| Back | V | Black | needs checking |
| R3 | — | free look | new; no badge exists |
| L3 | — | flourish weapons | new; no badge exists |
| Start | — | opens the in-game menu | new; no badge exists |

A and B are unchanged in meaning, so most badges survive untouched. Extending the
auditor needs a panel-and-control to native-action map, which the event inventory
now supplies; it is the next mechanical task here, but the *judgement* of what a
badge should say is a person's.

## Suggested removal order, once QA passes

1. `ApplyLeftStick` — already gated, highest confidence, biggest conflict risk.
2. The button rows of `BUTTON_BINDINGS` that have native equivalents.
3. D-pad synthesis.
4. `ApplyRightStick`, after the camera speed is settled.
5. Leave everything in the "not superseded" table alone.
