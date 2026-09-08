# Controller prompt specification

What each screen should show, and when. Drawn from
`controller-behaviour-matrix.md`, with every rule tracing to a measurement in it.

**Status, 2026-09-08.** The badge layer is implemented and live. It was written
by Saul0097 -- per-panel tables swapping a button's `BORDER.FILL` to a
pre-baked glyph-plus-label texture -- and was **unreachable in native mode**
until `KmrpUpdatePromptsK1` was wired into `NativeGuiFrameK1`:
`UpdateK1ControllerPrompts` was called only from the legacy
`DispatchMenuInputK1`, and the device flag it consults was raised only from the
legacy `PollXInputK1`. Both are dropped in native mode, so no badge was drawn on
any screen, ever. Tables, textures and mode logic were all present and all
unused, and nothing noticed because nothing looked at pixels.

The glyphs are Xelu's CC0 Xbox 360 set, and each badge already sits
**immediately left of the button's label**, positioned from the measured label
width rather than a fixed inset.

Two classes have changed since this was first written and the rules below are
updated for them: **ICMiniGame is now bound** (B, Y, LT, RT), and movies have a
**bridge** rather than a binding (A or Start cancels, from inside the movie
loop). The HUD action bar is now driven by the D-pad.

One rule governs all of it: **a prompt must not appear for an input that cannot
act.** That is stricter than it sounds, because of the input-class finding.

## The blocker that outranks the design

A description is polled only in the classes it was registered for. Buttons live
in classes 0 and 2, plus five events in class 3 for dialogue. Class 4 carries
only free look's own exit event, and classes 1 and 5 carry nothing.

**Dialogue is now bound and verified**, so its prompts are live specifications.
Minigames (class 1) and movies (class 5) are still unbound, so **no prompt should
be specified for them**: a glyph there would advertise a button that provably
does nothing.

## Global glyph vocabulary

| Glyph | Label | Shown when |
| --- | --- | --- |
| A | context verb — "Select", "Activate", "Take", "Buy" | a focusable control has focus |
| B | "Back" at a sub-screen, "Close" at a tab root | the screen can be left with B |
| X | **screen-specific label, never generic** | only on the screens listed below |
| Y | **screen-specific label, never generic** | only on the screens listed below |
| LB / RB | "Scroll" | the focused control is a list box |
| LT / RT | tab names or arrows | the in-game 8-tab strip is active **and** no modal is up |
| Start | "Menu" | gameplay only |
| L3 | "Flourish" | gameplay only |
| R3 | "Free Look" | gameplay only |
| Back/View | — | **never**; it does nothing on 39 of 40 panels |
| D-pad | — | not prompted; navigation is self-evident |

## Per-screen

### Gameplay (class 0)

| Glyph | Label | Location | Show when | Hide / dim when |
| --- | --- | --- | --- | --- |
| A | Talk / Use / Open — context | near the target reticle | a target is selected | `[internal+0x2b4]` is `0x7F000000` |
| Start | Menu | bottom-right cluster | always in gameplay | any GUI screen is up |
| L3 | Flourish | bottom-right cluster | always in gameplay | in a menu, dialogue or free look |
| R3 | Free Look | bottom-right cluster | always in gameplay | in a menu or dialogue; **see below** |

Nothing else earns a prompt here: B, X, Y, LB, RB, Back, LT, RT and the D-pad
all deliver their events and the world ignores every one of them.

**R3 dimming is specified but not yet implementable.** After a flourish, free
look declines for 4–7 seconds and the exact predicate was not identified. Either
find it first, or do not dim at all — a prompt that dims on a four-second timer
would be wrong for the seven-second case.

**A is now the interact button**, bridged to the engine's own router for event
`0xEF` — talk, open, use, on whatever is targeted. It should carry a
context-sensitive label where the game knows one, and be **hidden when nothing
is targeted** (`[CClientExoAppInternal+0x2b4]` reads `0x7F000000`), which is the
one cheap predicate this area does have.

### Main menu

| Glyph | Label | Location | Show when |
| --- | --- | --- | --- |
| A | Select | bottom strip | always |

B, X, Y, LB, RB, LT, RT, Start, L3 and R3 all do nothing here — no prompts.

### In-game menu — the 8-tab strip

The cycle is Equipment → Inventory → Character → Abilities → Messages → Journal
→ Map → Options, both directions.

| Glyph | Label | Location | Show when | Hide when |
| --- | --- | --- | --- | --- |
| **LT** | previous tab | **far left edge of the tab strip** | the strip is active | a modal owns input |
| **RT** | next tab | **far right edge of the tab strip** | the strip is active | a modal owns input |
| A | Select | bottom strip | a control has focus | — |
| B | Close | bottom strip | always | — |

**Hide LT/RT while `CSWGuiTutorialBox` is on the panel stack.** Tab cycling
demonstrably stops working while it is up. This is a recommendation from
observed behaviour; the box has not been proven to be a formal modal.

### Per-tab X and Y

Only these, and only with these labels:

| Tab | Glyph | Label | Evidence |
| --- | --- | --- | --- |
| Inventory | X | **Filter** | `SetNextFilter`, **verified live** |
| Journal | X | Sort | S |
| Journal | Y | Quest Select | S |
| Journal | Back | (the only screen implementing it) | S — prompt only if it proves useful |
| Map | X | Transit | S |
| Character | X | Character Sheet | S |
| Character | Y | Equip | S |
| Messages | X | Clear | S |
| Save / Load | X | **Delete** | S — destructive, so the label must be exact |
| Store | X | Buy / Sell | S |
| Container | X | Take All | S |

Every row marked S needs live confirmation before shipping its prompt. Inventory
is the only one confirmed.

### LB / RB

Show "Scroll" only on: Equipment, Inventory, Abilities, Journal, Store, Upgrade,
Upgrade Item Select, and the options sub-screens. Silent everywhere else, so a
prompt would be a lie.

### Confirmation boxes

| Glyph | Label |
| --- | --- |
| A | Confirm |
| B | Cancel |

`CSWGuiSoloModeQuery` is included: it implements both `0x27` (Toggle Party
Follow) and `0x28` (`HideSoloMode`), contrary to the first pass's claim.

### Dialogue — live and verified

| Glyph | Label | Location | Show when |
| --- | --- | --- | --- |
| A | **Select** while replies show, **Skip** while a line plays | beneath the reply list | always in dialogue |
| D-pad up/down | — | not prompted; the yellow highlight already shows it | — |
| LB / RB | Scroll | computer terminals only | the panel is `CSWGuiDialogComputer` |

B, X, Y, Back, LT, RT, Start, L3 and R3 reach the dialogue dispatcher's default
case and do nothing, so they must not be prompted.

A's label is genuinely two things: its handler skips the current line while one
is playing and chooses the highlighted reply otherwise. A single "Select" is a
half-truth, and the state is readable, so the label can follow it.

## Screens needing no prompts

The six native-direction screens (Abilities, Feats, Powers, Skills, Map, chargen
Abilities) beyond their A/B/X/Y rows; free look, where only Start works and
leaving is R3; and gameplay beyond the three listed.


## LT / RT on the in-game tab strip — specified, not implemented

The strip should show LT at its far left and RT at its far right. **It cannot be
done with the mechanism this layer uses**, and the reason is a measurement:
`CSWGuiInGameMenu` has exactly **16 controls** -- eight 192x192 tab frames at
y=96 and eight 156x120 icon overlays inside them -- and `dump_panel_stack.py
--all` shows nothing else. A badge is a texture swap on an existing control, so
with no control at either edge there is nothing to swap.

Three options, none of them free:

1. **Add two controls to the in-game menu's `.gui`.** The clean answer, and the
   repository already patches GUI assets. The runtime would toggle their
   visibility with the rest of the prompt state. Cost: a new asset patch, and
   the new controls have no fixed member offset in the panel class, so the
   runtime must find them by array index rather than by the byte offsets every
   other binding uses.
2. **Badge the outermost tab frames.** Free, and semantically exact -- those two
   controls are the ones carrying `0x35`/`0x36`. But the frame is 192px wide
   with a 156px icon inside it, leaving an 18px margin, which is too narrow for
   a legible glyph without drawing over the tab art.
3. **Leave the bumpers to speak for themselves.** LT/RT tab switching is
   discoverable and already works.

Nothing was shipped for this rather than shipping option 2 and calling the
result clean when it would not be.

**The art side is no longer a blocker.** The full pack now lives at
`third_party/Included/Xelu_Free_Controller&Key_Prompts/`, and its `Xbox/` folder
carries the whole 360 set including `360_LT.png` and `360_RT.png`. All 16 glyphs
the builder names resolve; `check_controller_drift.py` asserts it.


## Verified live, 2026-09-08

### The Options "Default" buttons are NOT a coverage gap

They were listed as one here because no panel implements an X or Y shortcut for
them. Wrong question. Measured on the Gameplay options screen:

| check | result |
| --- | --- |
| control is visible and selectable | yes, flags `0x0A` |
| registers `0x27` | yes -- one entry, handler `0x006E68B0` |
| D-pad navigation lands on it | yes |
| A executes it | yes -- the handler calls `GetClientOptions`, the reset routine at `0x0061D4E0`, then the panel's own refresh at `0x006E6770` |
| B still backs out afterwards | yes, `0x00758E00` -> `0x00750148` |

So A reaches them through `CSWGuiPanel`'s ordinary focused-control path, exactly
like every other button. **They must not get an invented `[X] Default` or
`[Y] Default` badge.** They are `[A] Select` buttons and need nothing.

More generally: the static survey resolves **288 controls registering `0x27`**
across the executable. A button without a badge is the normal case, not a defect.
`tools/audit_controller_prompt_coverage.py` now says "no dedicated badge --
reachable by focus + A" instead of "gap".

### Confirmation modals

Measured on the quit confirmation (`MESSAGE_BOX`, dispatcher `0x006250F0`,
reached from the last row of the Options tab):

* it carries two choices, both registering `0x27`, plus a text control that is
  visible and selectable but registers **no events**
* up and down move between exactly the two choices; the text control never takes
  focus, because the navigation layer rejects any control with an empty event
  table -- the rule that was put there for the Main Menu wallpaper
* B closes it
* every panel underneath kept its active control, before and after -- the screen
  behind does not move, and focus is restored

**A was deliberately not pressed.** One of the two choices ends the process, so
"A activates the focused choice" is recorded as human-QA rather than asserted by
a suite that would then have nothing left to run.

### Not yet reached

Solo-mode query, delete-save and overwrite-save confirmations, the tutorial
popup, and warning boxes were not driven live. They share the `MESSAGE_BOX` and
`SOLO_MODE_QUERY` dispatchers whose retained events are already in the
inventory, but sharing a dispatcher is an argument, not a measurement, and this
document has been wrong before by reasoning from one to the other.


## Prompt-art audit, Inventory / Equipment / Messages — 2026-09-08

Physical QA reported working buttons with no controller art: **Close**, **Show
New Items**, **Use Item**. Measured on the live Inventory screen, the buttons map
to `CSWGuiInventory` members like this:

| button | offset | rect |
| --- | --- | --- |
| Show New Items | `panel+0x14EC` | (1821, 1122) 1166x93 |
| Use Item | `panel+0x1328` | (1333, 1230) 770x84 |
| Close | `panel+0x1164` | (2122, 1230) 774x84 |

The obvious badges would be `[B] Close` and `[X] Show New Items`, because
INVENTORY implements `0x28` and `0x29` (its `0x29` handler is `0x006B3FC3`, the
one X binding in the whole executable). **Both would be lies.**

The Inventory panel sits **behind the in-game tab strip**. A retained event goes
to the panel in front, `CSWGuiInGameMenu` answers only `0xF3`/`0xF4`, and its
base class then routes to its own focused control -- a tab frame. So `0x28` and
`0x29` never arrive. Proven rather than argued: pressing X on the live Inventory
screen leaves `panel+0x1DE4`, the flag its `0x29` handler sets, at zero across
repeated presses. B does close the screen, but by closing the whole menu from the
strip, not by running Inventory's own handler.

So every one of those three buttons is **focus + A**, and the same holds for
Messages (`Show Feedback`, `Close`) and Equipment. The truthful badge is `[A]`
on each, which is consistent with the existing convention -- eight `A` badges
already sit on focus-plus-A buttons elsewhere.

**Not implemented.** Each badge needs four coordinated pieces: a `PromptTarget`
entry, a label StrRef for the width measurement that positions the glyph, a
runtime binding in the vendor prompt table, and a regeneration of the textures
through the resolution-patcher pipeline that feeds `build_prompt_textures`.
That was not attempted rather than attempted in a rush; a badge whose resref has
no texture behind it renders as nothing at all, silently, which is this area's
standing failure mode.
