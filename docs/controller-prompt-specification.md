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

*Checked 2026-09-25 against `K1_GAMEPLAY_ACTIONS` in
`src/controller-native/K1NativeJoystick.cpp`:* LB and RB no longer carry any GUI
event in menus. The right stick scrolls descriptions instead, and only ICDialog's
computer-terminal scrolling still arrives through those two buttons. A "Scroll"
prompt on LB / RB would therefore be false; that row describes the earlier
binding, and none was shipped.

## Per-screen

### Gameplay (class 0)

| Glyph | Label | Location | Show when | Hide / dim when |
| --- | --- | --- | --- | --- |
| A | Talk / Use / Open — context | near the target reticle | a target is selected | `[internal+0x2b4]` is `0x7F000000` |
| Start | Map | bottom-right cluster | always in gameplay | any GUI screen is up |
| L3 | Flourish | bottom-right cluster | always in gameplay | in a menu, dialogue or free look |
| R3 | Free Look | bottom-right cluster | always in gameplay | in a menu or dialogue; **see below** |

Nothing else earns a prompt here: B, X, Y, LB, RB, Back, LT, RT and the D-pad
all deliver their events and the world ignores every one of them.

*No longer true for five of them (checked 2026-09-25 against
`K1_GAMEPLAY_ACTIONS`):* the build now gives them gameplay verbs:

| Button | Verb |
| --- | --- |
| LB | cycle the target backwards |
| RB | cycle the target forwards |
| Back | open the Solo Mode query |
| LT | switch to the next living party member |
| RT | pause |

The D-pad drives the action bar (see above). Whether any of these should earn a
gameplay prompt is not decided here, and none is shipped.

*Shipped 2026-09-25: X and Y in combat, with prompts.* X presses the HUD's
Disengage button and Y its "clear one" button, which removes the last queued
action. Each has a badge, placed at build time from the button itself, that
shows exactly while the button is drawn and the pad is in use:

| Glyph | Label | Location | Show when | Hide when |
| --- | --- | --- | --- | --- |
| X | (the Disengage button beside it) | `LBL_KMRPX`, left of `BTN_CLEARALL` | Disengage is drawn -- in combat | Disengage is hidden, or the mouse or keyboard is the active device |
| Y | (the action queue beside it) | `LBL_KMRPY`, left of `BTN_CLEARONE` | the clear-one button is drawn | it is hidden, or the mouse or keyboard is the active device |

Both are glyph-only: the buttons beside them say what they do. See
[`../reverse-engineering/custom-gui-controls.md`](../reverse-engineering/custom-gui-controls.md).

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
| Store | X | the button's own caption, Show Sell List or Show Buy List | **ships** since 2026-10-06; read from the dispatcher, not yet seen in play |
| Container | X | Take All | S |

Every row marked S needs live confirmation before shipping its prompt. Inventory
is the only one confirmed.

*Corrected 2026-09-26:* the Character rows were wrong. Its X is Scripts, which
ships, and its Y is Auto Level Up (`0x006B233C`), not Equip; A is Level Up
(`0x006B2295`). Decoded from the dispatcher, `0x006B2250`; see *Character
screen* above.

*Added 2026-10-06:* the store. Its dispatcher (`CSWGuiStore::HandleInputEvent`,
`0x006C2190`) answers event `0x29`, X, by swapping the buy and the sell list
whatever holds focus, and `0x28` or `0x2E`, B, by closing the screen. A buys or
sells the row in focus. So the screen's three buttons carry A (Buy or Sell), X
(Show Sell List or Show Buy List) and B (Close). At a shop that only buys or only
sells the game does not draw the X button (`0x006C1B50`), and no badge is drawn
for it.

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

**Not shipped, and now known to be undrawable this way (2026-09-20).** The
table above says A/Confirm and B/Cancel, and a Cancel badge did ship. A
photograph of the Solo Mode prompt showed it as a thin red vertical smear across
the caption rather than a disc beside it.

`CSWGuiMessageBox::FixMessageLabel` (`0x006253A0`) rebuilds both button extents
before calling their virtual `SetExtent`: it copies the four fields out of the
control, overwrites the third with the constant `0x64`, and passes that back —
`BTN_OK` at `0x006254AC`, `BTN_CANCEL` at `0x00625574`. So the button is about
an eighth of the 780 its `.gui` gives at 3440x1440, and a badge shaped from the
file is pre-compensated for a stretch it never gets.

Shaping it for the real width does not rescue it. Only the control's aspect
matters to the pre-compensation, so 100 against the file's height is the right
shape — and at that shape a disc sized to the control's height reaches the
middle of the button, where the caption is. `Test-ControllerPromptAssets.py`
rejects it on exactly that ground. Both attempts were reverted, and the
message box now carries no badge at all rather than a wrong one.

What these buttons need is a prompt drawn **beside the box** rather than inside
a control, which is the same thing dialogue needs below and which neither has
yet. The panel remains registered in `IsK1MenuPanel` regardless, because an
unrecognised top modal blanks the badges of the screen underneath it.

*Since 2026-09-24 they have one:* `LBL_KMRPA`, an A drawn beside the focused
button; see [custom-gui-controls.md](../reverse-engineering/custom-gui-controls.md).

Both controls belong to `CSWGuiMessageBox`, from its constructor at
`0x00626DF0`: `BTN_OK` at `+0x2F4`, `BTN_CANCEL` at `+0x4B8`, over the GUI named
`confirm`. The resolution screen, whose badges DID ship, gets its own pair from
`0x006E0710` at `+0x484` and `+0x648` — it is an ordinary panel and does not
resize them.

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

*Built differently, 2026-09-25:* the maintainer chose an A glyph that follows
the highlighted reply, instead of a captioned prompt beneath the list. It was
first left of the reply's number, like the main menu's A, where the engine's
panel clipping hid it. After the second play-test that day it moved to the end
of the reply's text, where the engine's measure put it mid-sentence; since the
third it sits at the end of the reply's last line, measured from the drawn
layout. Since the fifth it is centred on that line's letters, 5/8 of the
line height below the line's top. The reply list fills the whole
bottom bar, so nothing fits beneath it. The A shows only while replies can be
picked, so it never has to say "Skip". See `LBL_KMRPDLG` in
[custom-gui-controls.md](../reverse-engineering/custom-gui-controls.md).
**Measured in game on 2026-09-25**, in a scratch copy at 3440x1440 driven by
the virtual pad: the A's centre and the centre of the reply's
capital-to-baseline band are on the same pixel row. Not yet played by hand.

### Status summary — built 2026-09-25

| Glyph | Label | Location | Show when |
| --- | --- | --- | --- |
| A | OK | left of OK, as on the confirmation boxes | a controller is in use |

The box that says "Journal Entry Added", "Item(s) Received" and the like.
Its only button is OK, and A presses it: the panel registers OK's handler for
`0x27`. The game's `statussummary.gui` has no control for the glyph, so the
module adds a label when the panel is built; see
[custom-gui-controls.md](../reverse-engineering/custom-gui-controls.md).
**Seen in game on 2026-09-25** at 3440x1440 and 1920x1080 in a scratch copy.
The D-pad does nothing on this box: focusing its OK makes A recurse until
the game crashes, so the module never moves focus there.

### Character screen — Level Up and Auto Level Up, built 2026-09-26

| Glyph | Button | Handler, with nothing focused |
| --- | --- | --- |
| A | Level Up | `0x006B2295` |
| Y | Auto Level Up | `0x006B233C` |

Both buttons are drawn only while the member on screen can level up, and so
are their badges. They are the first badges on filled buttons: the box is
`dialog2`, which the badge carries under its glyph and the module puts back
when the badge is not shown. They are sized like the screen's Close and
Scripts badges. The pad moves no focus on this screen
([`controller-behaviour-matrix.md`](controller-behaviour-matrix.md)).
**Seen in game** 2026-09-26 and 2026-09-28, at 3440x1440 in a scratch copy.

### Granted-feats notice — built 2026-09-26

| Glyph | Button | Why |
| --- | --- | --- |
| A | OK | the dispatcher, `0x006CD3C0`, closes the box on A whatever holds focus |

"You have been granted the following feat(s) this level", `skillinfo.gui`,
which Feats opens with in character creation and level-up. The same panel
says "The following power(s) have been recommended" when Powers' Y is
pressed, and carries the same A. **Seen in game** 2026-09-28, both texts, at
3440x1440 in a scratch copy.

## Character creation and level-up — built 2026-09-25

Every screen of both flows carries badges, 42 in all. The class portraits
carry art and take none. The +/− arrows carry art too and keep it (*Settings
screens*, below). Each glyph is a button the screen's own
dispatcher answers; the handler addresses are in the module's tables
(`src/controller-native/vendor/K1XboxControls.cpp`, beside
`K1_CLASS_SELECT_PROMPTS`). Tags, indices, empty fills and widths were checked
in all 49 archives before the targets went in.

| Screen | .gui | A | B | X | Y |
| --- | --- | --- | --- | --- | --- |
| Class selection | `classsel.gui` | the focused class (no badge: each portrait is a 400x870 frame over the model) | Cancel | — | — |
| Quick or Custom | `qorcpnl.gui` | the focused choice, FocusOnly | Cancel | — | — |
| Custom character | `custpnl.gui` | the focused step (only the current one is enabled), FocusOnly; Cancel when focused | Back (one step) | — | — |
| Quick character | `quickpnl.gui` | the focused step, FocusOnly; Cancel when focused | Back (one step) | — | — |
| Portrait | `portcust.gui` | OK, FocusFallback | Cancel | — | — |
| Attributes | `abchrgen.gui` | OK, FocusFallback | Cancel | — | Recommended |
| Skills | `skchrgen.gui` | OK, FocusFallback | Cancel | — | Recommended |
| Feats | `ftchrgen.gui` | OK, FocusFallback | Cancel | Add (the highlighted feat) | Recommended |
| Name | `name.gui` | OK, FocusFallback | Cancel | — | Random Name |
| Level up | `leveluppnl.gui` | the focused step, FocusOnly | Back | — | — |
| Powers | `pwrlvlup.gui` | OK, FocusFallback | Cancel | Select (the highlighted power) | Recommended |

**FocusFallback** is right for the five screens that answer A themselves,
because since `GuardChargenConfirmK1` A presses whichever button is focused
there: the A on OK steps aside while focus sits on another badged button.
**Feats' A and X are swapped by the module** so every screen has A on OK. The
panel's own dispatcher has them the other way round: A adds the feat
(`0x006F46EF`) and X is OK (`0x006F46CF`), the mirror of Powers. On Feats the pad's
A now presses a focused button, and otherwise runs the panel's `OnAccept`
(`0x006F44C0`). X runs its add, the highlighted feat through `OnFeatPicked`
(`0x006F3C20`). Both call the routines directly, not the dispatcher, whose pass-on
to the focused control would click a focused OK. The swap applies only while
Feats is the screen in front, so a message box over it keeps its own A. The
maintainer asked for it on 2026-09-25, from a play-test screenshot of the first
layout.

**Portrait's D-pad now picks portraits.** Left and Right are sent to the screen
as LT/RT's `0x35`/`0x36`, which its dispatcher treats like `0x2F`/`0x30`
(`0x006F905F`, `0x006F9094`) but which no control there answers, so focus stays
put. Until then only LT and RT cycled portraits.

Known limits, not changed:
- a pad cannot type a name; Random Name (Y) works;
- level-up's `BTN_CANCEL` is bound at `+0x1B08` but no shipped `leveluppnl.gui`
  has one;
- `CSWGuiMainCharGen` and `CSWGuiLevelUpCharGen`, the backdrops, are not
  recognised as menu panels. They have no buttons, and recognising one that sat
  above its screen would hide that screen's badges.

**Untested in game**, level-up included.

## Settings screens — built 2026-09-25

Every settings screen carries its buttons' glyphs since the maintainer asked
for them from a screenshot of Advanced Graphics. Tags, indices, empty fills and
STRREFs are checked in all 49 archives by the build and by
`Test-ControllerPromptAssets.py`.

| Screen | .gui | A | B | Y | D-pad left and right |
| --- | --- | --- | --- | --- | --- |
| Options, main menu | `optionsmain.gui` | the focused entry, FocusOnly, one column | Close | — | — |
| Options, in game | `optionsingame.gui` | the focused entry, FocusOnly, one column | Close | — | — |
| Gameplay | `optgameplay.gui` | Mouse Settings, Key Mapping and Controller Layout when focused | Close | Default | Difficulty's − and +, focused row |
| Mouse | `optmouse.gui` | — | Close | Default | the slider's own |
| Feedback | `optfeedback.gui` | — | Close | Default | — |
| Auto-Pause | `optautopause.gui` | — | Close | Default | — |
| Graphics | `optgraphics.gui` | Screen Resolution and Advanced Options when focused | Close | Default | Gamma's own |
| Advanced Graphics | `optgraphicsadv.gui` | OK | Cancel | Default | Texture Quality, Anti-aliasing, Anisotropy |
| Sound | `optsound.gui` | Advanced Options when focused | Close | Default | the sliders' own |
| Advanced Sound | `optsoundadv.gui` | OK | Cancel | Default | EAX |
| Key Mapping | `optkeymapping.gui` | OK | Cancel | Default | — |
| Pazaak's wager | `pazaakwager.gui` | Wager | Quit | — | Less and More |

**Y presses Default**, which no settings panel does itself. The module presses
the button as a click does (`PressDefaultK1`, `K1NativeJoystick.cpp`). The five Y
registrations the engine has on these screens are the gamma and volume sliders'
change callbacks (`0x006E0190`, `0x006E0F50`); each tests its control's
`+0x4C` and re-applies the current value, so nothing a player could want is
lost.

**The −/+ arrows keep the game's art** and take no glyph. From 2026-09-25 to
2026-09-28 they showed the D-pad's left and right in its place on the focused
row, and always on Portrait and Pazaak's wager; the maintainer asked for the
arrows back ("I dont want the dpad leave the + and -"), and
`Test-ControllerPromptAssets.py` now fails if an archive carries one of those
glyphs (`kmr?dl_*`, `kmr?dr_*`). The D-pad still changes the value: Left and
Right press the row's arrows (`K1_CYCLE_ROWS`); on Attributes and Skills they
call the panel's own lower and raise (`K1_POINTS_SCREENS`); on Portrait and the
wager the screen's dispatcher answers them.

The Controller Layout entry is KMRP's own button, bound at run time, so its A
is painted from `K1ControllerLayout.cpp` through `KmrpPaintLayoutEntryPromptK1`;
its caption is inline text, so its badge is placed against "Controller Layout"
and never re-measured by the installer (`PROMPT_INLINE_LABELS`).

**Untested in game.**

## Screens needing no prompts

(Until 2026-09-25; since then four: Attributes and Skills in character creation are
navigated by KMRP -- see `docs/controller-behaviour-matrix.md`.) The six
native-direction screens (Abilities, Feats, Powers, Skills, Map, chargen
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

*Superseded 2026-09-25:* the maintainer asked for glyphs on every settings
screen, and Y now presses Default on all nine (*Settings screens*, above). The
`[Y] Default` badge is therefore not invented: it depicts what the button does.
The rule held while no controller button did it.

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

*Since then:* the Solo Mode query was play-tested by hand on 2026-09-24 at
3440x1440. A on OK turns Solo Mode on, and A on Cancel leaves it off; see
*Cancel now cancels on the Solo Mode prompt* in `CHANGELOG.md`. Nothing recorded
confirms the A badge beside the focused button on that box. The delete-save and
overwrite-save confirmations, the tutorial popup and the warning boxes are still
not driven live.


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


## Tab-screen badges — measured button by button, 2026-09-08

An earlier pass concluded every button on these screens was focus + A, because
the panels sit behind the tab strip and the retained `0x28`/`0x29` "cannot reach
them". **That was wrong**, and it was wrong because it was reasoned instead of
pressed. Physical QA said so directly: X does something on every screen, Y on
some, and Close is always B.

`testing/controller/probe_button_effects.py` now presses A, B, X and Y on each
tab and records what changed:

| screen | A | B | X | Y |
| --- | --- | --- | --- | --- |
| Inventory | opens a message box | closes the menu (95%, class 2 -> 0) | 3.2%, stays | 17.3%, stays |
| Messages | nothing | closes | 91.9%, stays | nothing |
| Journal | nothing | closes | 65%, opens the quest-items list | 39%, re-sorts |
| Map | opens `CSWGuiPartySelect` | closes | opens a message box | nothing |

The two ambiguous ones were settled by looking: Journal's X showed datapads and
star maps -- the Quest Items list -- and its Y changed the header to
"Quests - By Order Received", which is the Sort button. Map's X opening a
message box is the Return To Ebon Hawk confirmation, exactly as described.

**Shipped badges**

| screen | badge |
| --- | --- |
| Inventory | `[X] Show New Items`, `[A] Use Item`, `[B] Close` |
| Messages | `[X] Show Feedback`, `[B] Close` |
| Journal | `[X] Quest Items`, `[A] Completed Quests`, `[Y] Sort by Name`, `[B] Close` |
| Map | `[A] Party Selection`, `[X] Return To Ebon Hawk`, `[B] Close` |

The offsets, pixel extents and labels were all read from the running game, and
`tools/build_tab_screen_prompts.py` regenerates the textures from that table.

**Known cosmetic limit.** Map's Party Selection and Return To Ebon Hawk rows are
39px tall against an 84px Close, so their glyphs are correspondingly smaller.
Short controls already take a larger share of their height (0.40 rather than
0.29); beyond that the glyph would not fit inside the button.


## The prompt vocabulary is family-independent — 2026-09-08

`build_controller_prompt_textures.py` now names **actions**, not Xbox pictures:

    A  B  X  Y  LB  RB  LT  RT  START  BACK
    DPAD_UP  DPAD_DOWN  DPAD_LEFT  DPAD_RIGHT  L3  R3

`GLYPH_FAMILIES` maps each action to a file per family -- Xbox, PlayStation,
Switch and Steam Deck -- and all four are complete at 16/16, checked by
`check_controller_drift.py`. `GLYPH_FAMILY` selects the one the shipped textures
are built from, and it is `xbox`.

**Controller-family detection is deliberately not implemented.** Nothing asks the
running game which pad is attached. The point of this change is that adding that
later touches one constant rather than every caller.

*Superseded 2026-09-19 (issue #19):* detection is implemented. All four families
are built and shipped, named by the resref's fourth letter (`kmrp` Xbox, `kmrs`
PlayStation, `kmrn` Switch, `kmrd` Steam Deck), and the module picks one from the
pad it reads -- its vendor id, or through Steam Input the controller Steam says is
behind it. The Switch set now maps by button position rather than by
letter. See *Controller families* in [`controller-support.md`](controller-support.md).

## L3 / R3 badges in gameplay — specified, not shipped

`[L3] Flourish` and `[R3] Free Look` are the right prompts, and the glyph art for
both now exists. **They cannot be placed with the mechanism this layer uses.**

A badge is a texture swap on an existing control's `BORDER.FILL`. The gameplay
HUD's only wide, short controls are `13EADE68` (356x114, the action-bar backdrop)
and `13EB7E4C` (597x64, the status strip), and both register **zero events** --
they are decorative frames. Swapping either one's fill would delete that frame's
own artwork and leave a lone glyph floating on the HUD, which fails "no overlap
with HUD elements, no clutter" rather than satisfying it.

This is the same structural blocker as LT/RT on the tab strip, and it has the
same three options; adding two controls to the relevant GUI asset is the clean
one. Nothing was shipped rather than shipping something that damages the HUD.
