# Handover: which parts of the legacy controller path the native one replaces

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
| D-pad → arrow keys | menu navigation | events `0x31`/`0x32`/`0x2F`/`0x30` | yes |
| `ApplyRightStick` → `SC_A`/`SC_D` | camera turn | mouse-delta injection at `+0x3A0` | yes, once the camera speed is tuned |

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
| Start, L3, R3 bindings | no native event exists and no control slot is free |

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

`tools/audit_controller_prompt_coverage.py` reports which screens have prompts;
it has not yet been extended to check that a prompt's *label* matches the native
action. That is the next mechanical task in this area.

## Suggested removal order, once QA passes

1. `ApplyLeftStick` — already gated, highest confidence, biggest conflict risk.
2. The button rows of `BUTTON_BINDINGS` that have native equivalents.
3. D-pad synthesis.
4. `ApplyRightStick`, after the camera speed is settled.
5. Leave everything in the "not superseded" table alone.
