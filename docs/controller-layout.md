# Controller Layout screen

This document follows the [documentation standard](documentation-standard.md).
It describes the implementation prepared on 2026-09-19 and keeps runtime claims
separate from the manual acceptance test that still has to be performed.

## What ships

**Which patch, since 2026-10-05:** the screen belongs to the controller patch,
`KOTOR 1 Native Controller Mod + Xbox HUD.kpatch` (id `kmrp-controller`), which
KMRP's installer installs while Controller Support is on and which also runs
without KMRP. Beside KMRP it uses KMRP's `kmrplayout.gui` for the resolution in
use, the one this document describes; on the game's own interface it carries one
of its own, laid out for 800x600
([controller-standalone.md](controller-standalone.md), section 4). The archive
counts below (49) are those of 2026-09-24; KMRP has 66 menu sets since.

**Options → Gameplay** gains a `Controller Layout` button directly under
Keymapping, a copy of that button in the same column. It opens the dedicated
`kmrplayout.gui` panel, built from KOTOR's own controls, so it scales, takes
focus and closes like any other panel. Until 2026-09-21 the entry sat on the
Mouse screen instead, which Options does not list, so it was two screens deep
where nobody found it.

**Since 2026-10-18 the screen is also where the pad's buttons are remapped**
(uncommitted when written). It opens as a view of the layout, and a Remap button
makes it editable. Everything about that is in [Button remapping](#button-remapping)
at the end of this document, including what has and has not been run.

### The screen

A controller diagram fills the middle of a 760x380 design-unit board, with
leader lines from every button to its row:

| Part | How it is drawn |
| --- | --- |
| Diagram | one texture per family, `kmr?lytdiag.tga`: Xelu's unlabelled Xbox Series X or PS5 silhouette, tinted to KOTOR's palette, with the family's own A/B/X/Y glyphs composited onto the face buttons |
| Leader lines | baked into the same texture, antialiased by drawing at 4x and downsampling |
| Rows | an engine glyph control and an engine caption per button, so the text is in-game type and the glyph follows the pad at run time |
| View and Menu | a centre pair above the controller, captions stacked over their glyphs |

Switch and Steam Deck have no diagram in the pack, so they are drawn on the
Xbox silhouette with their own glyphs. A Deck is physically a handheld with
trackpads; that drawing is the nearest honest one, not a picture of a Deck.
Nintendo labels are positional, as on the HUD: the bottom button reads B.

**One layout for every family.** There is one `kmrplayout.gui`, so the rows
cannot move per family — only the texture behind them can. `rows()` in
`tools/build_controller_layout.py` therefore solves one row order for all of
them and is used by both the texture and the GUI, which is the whole alignment
contract. The order is searched exhaustively for the fewest lines passing
through a button that is not theirs, then the fewest crossings, weighted by how
many families each silhouette serves (three share Xbox's). Measured:

| Silhouette | Families | Lines through a foreign button | Crossings |
| --- | --- | --- | --- |
| Xbox | Xbox, Switch, Steam Deck | 0 | 0 |
| PS5 | PlayStation | 0 | 1 |

Two layout decisions came from measurement, not taste. Sorting rows by button
height alone crossed three pairs. And no row order kept the left column clear
while View and Menu were in it — they sit between the sticks, so any line to
them crosses one — which is why they became a centre pair. The left stick also
carries one row, "Move / Click: flourish", matching the right stick's "Camera /
Click: free look": two rows on one stick beside the inboard Xbox D-pad could
not be kept from crossing.

### Caption font and width

**Measured in game, 2026-09-24, 3440x1440.** The captions were authored in
`dialogfont10x10`, yet came out exactly the size of `dialogfont16x16` text:
the title, the pad heading and the captions all rendered alike. Every caption
measured 1.38-1.41x the width `dialogfont10x10`'s metrics predict, and 0.88x
what `dialogfont16x16`'s predict -- the same 0.88 that vanilla 16x16 text on the
Gameplay screen measured. So the game draws this panel's labels in 16x16. Boxes
sized for 10x10 made the long captions wrap, and a one-line box shows only the
last line of a wrapped label: "Camera / Click: free look" read "Free look",
"Switch ally / Prev tab" read "Tab", "Move / Click: flourish" read "Flourish".

The labels now ask for `dialogfont16x16`, and `build_gui` sizes each column's
box from that resolution's own TXI (`RENDER_FACTOR` 0.92, the measured 0.88 plus
margin), growing outward from the diagram; the side art shrinks or hides to
make room. On the two narrowest screens, 1280x1080 and 800x600, a column would
run off the edge, so it stops 14 units short and the boxes that cannot fit are
made two lines tall, where a wrapped caption shows both lines.
`Test-ControllerPromptAssets.py` checks the font and the fit in all 49
archives. Why the engine substitutes the font is not established.

### Spacing

The layout has a compact form, 540 design units tall, which short displays
such as 1024x576 get. Where the screen has room it opens out by up to 78 more:
the title and pad heading rise 18 and the help line and Back sink to the
bottom, so the board is framed by a hairline under the heading and another
above the help line. There is no active-device line any more; the heading
already names the pad. `LBL_KBM` and `LBL_PAD` remain in the file, empty and
sizeless, because the runtime binds them by tag and renumbering every later
control for them is not worth the risk.

### Full screen, not a box

The panel covers the screen. Its root fill is `kmrlytbg`, a deep-navy gradient
with a soft centre glow and a vignette: the only texture stretched to the
screen, so it carries no pattern that would stretch with it. Everything else is
a label of its own, `DECO_00`..`DECO_09`, placed against the screen's real edges
rather than the design space, so it reaches the corners at every aspect:

| Piece | Where | Texture |
| --- | --- | --- |
| Corner brackets | all four corners | `kmrlytcn0..3` |
| Hairlines, fading at both ends | under the device heading, under Back | `kmrlythair` |
| Status readouts | inside the top-left and bottom-right brackets | `kmrlytrd0/1` |
| Turret gunnery station: scope, target data, twin-grip yoke, power cells | left margin | `kmrlytgun` |
| Light freighter deck plan, top view and elevation, dorsal turret ringed | right margin | `kmrlytship` |

The two illustrations keep a 1:2 aspect and are centred in the margin beside
the 760-unit board. Where that margin is under 110 design units wide -- 4:3,
5:4 and 16:10 at some sizes -- they get a zero extent and are not drawn; the
brackets, hairlines and readouts are drawn everywhere. All of it is original
and dim, so the controller stays the subject.

**The lettering is real Aurebesh**, set in SilvinoR's OFL-1.1 font (see
`THIRD_PARTY_NOTICES.md`), whose letters were checked against the canonical
chart. Aurebesh is a cipher of English, so each label is an English phrase
that means what it says:

| Piece | Reads |
| --- | --- |
| Top-left readout | INPUT LINK · GAMEPAD SYNC · STATUS READY |
| Bottom-right readout | NAV COMPUTER · COURSE PLOTTED · SYSTEMS NOMINAL |
| Gunnery station | TURRET CONTROL · GUNNER · TARGET LOCK · HOSTILE · DISTANCE 2400 · SPEED 410 · FIRE · POWER CELLS · ARMED |
| Freighter | LIGHT FREIGHTER · DECK PLAN · COCKPIT · DORSAL TURRET · SUBLIGHT DRIVE · HULL 26M · BEAM 19M · REPUBLIC REGISTRY · CLASS · CREW 2 · ARMAMENT · PLATE 2 OF 4 |

Canon writes CH, AE, EO, KH, NG, OO, SH and TH with letters of their own, which
the no-ligature font lacks; `aurebesh()` in `tools/controller_layout_backdrop.py`
rejects any label containing one, so the wording avoids them rather than
misspelling them (DISTANCE, not RANGE; SUBLIGHT DRIVE, not ENGINES).

### Captions

Taken from what the **native** path does, read from `K1_GAMEPLAY_ACTIONS`,
`K1_BUTTONS` and `K1_STICK_CLICKS` in `K1NativeJoystick.cpp`. The previous
captions were written against the legacy key table in `controller-support.md`
and were wrong for the shipping path — View read "Menu-specific action" and LB
"Scroll description up".

| Button | Caption |
| --- | --- |
| LT / RT | Previous target / Prev tab · Next target / Next tab |
| LB / RB | Pause · Switch ally / Menu action |
| View / Menu | Solo mode · Last menu / Close menu |
| Left stick | Move / Click: flourish |
| Right stick | Camera / Click: free look |
| D-pad | Action bar / Navigate |
| A / B | Interact / Select · Disengage / Back |
| X / Y | Add to queue / Menu action · Undo or flourish / Menu action |

*Changed 2026-10-19 (issue 49):* the controller now uses the original Xbox game's
layout, with the Xbox's White and Black buttons on LB and RB, and the captions
follow it (`LAYOUT` in `tools/build_controller_layout.py`; `kActionNames` and
`kFixedAfter` in `K1ControllerLayout.cpp` for the remappable rows). Until then they
described KMRP's own layout: LT / RT "Switch ally / Prev tab" and "Pause / Next
tab", LB / RB "Previous target" and "Next target", Menu "Map / Close menu", B "Back
/ Release bar", X "Disengage / Menu action" and Y "Undo action / Menu action"
("Screen action" until 2026-09-25, before X and Y did anything in combat). Whether
the longer captions, such as "Undo or flourish / Menu action", fit their boxes at
every size has not been seen on screen, and `Test-ControllerPromptAssets.py`, which
checks the fit after a resource build, was not run for this note.

Plain ASCII, because the menu face has 95 printable-ASCII glyphs and nothing
else.

**Since 2026-10-18** the ten remappable rows do not show these captions while the
screen is open: each row's text is set at run time to the action now on that
button, with what stays with the button beside it in grey (B's row reads
"Disengage / Back" on the default layout; "Release bar / Back" until 2026-10-19).
The file's captions are what the screen starts from. See
[Button remapping](#button-remapping).

**Correction, 2026-09-20.** The first build of this screen shipped nothing a
player could read. PyKotor's `get_struct()` returns a *copy* holding its own
field dictionary, so the authoring tool's extents, captions, fonts and fills
were written to throwaway objects and discarded; every one of the controls
reached the archives with the same extent, no text and no fill. The tool now
stores each nested struct back, and `Test-ControllerPromptAssets.py` checks the
captions, the fills and the per-control placement instead of only tags and IDs.

## Runtime construction

KOTOR does not instantiate an unfamiliar control merely because it appears in a
`.gui`. The existing `CSWGuiPanel::ReleaseGff` hook runs at the last safe point,
while the parsed layout still exists (since 2026-10-05 the controller patch
reaches that moment from a site of its own, `NativePanelLoadedK1` at `0x00409B80`,
and calls the same handler). On `CSWGuiOptionsGameplay` it allocates one
engine `CSWGuiButton`, binds `BTN_KMRPLAY`, and registers its A/click callback.

**The opening press does not close it.** A on the entry opens the screen with
Back focused, and before 2026-09-24 that same A -- its release, or the press
still held -- then activated Back: the screen showed for a frame and shut, and
stayed only while A was held. Back now does nothing until confirm (A, Enter or
Space) has been seen released on two frames running; one frame was not enough,
because the engine may deliver the release before or after the frame hook in
that same frame.

**Nor does the closing press reopen it.** A on Back closes the screen and
returns focus to the entry, and that same A then activated the entry: the
screen shut and came straight back. After a close the entry is ignored until
confirm has been released on two frames running, the same rule. Back carries
the pad's B glyph (`GLYPH_BACK`, `kmr?lytbk`) at its left end, shown only while
a pad is in use.

Opening is queued until `CSWGuiManager::Update`; the callback itself never
changes or destroys the panel stack. The update creates a base `CSWGuiPanel`,
loads `kmrplayout.gui`, binds 47 controls, makes Back active, and adds the panel
as a modal. B and Back mark it for normal manager removal on the next update.
The parent Gameplay panel and its focused control are remembered and restored.

*Changed 2026-10-18:* the update now also makes the remap screen's 55 controls
from the file's own, before the file is let go, and does not open the screen if
any of them cannot be made. It no longer makes Back active: the screen opens with
no control focused (`SetActiveControl(panel, null)`), because it opens as a view
in which nothing is a place for the pad's focus, and Back is kept off the pad's
focus altogether (B presses it). The arm rule above still guards Back and every
button the remap screen adds. See [Button remapping](#button-remapping).

The custom scalar deleting destructor performs explicit ownership cleanup:

1. Clear the active control.
2. Null the custom controls in the panel's pointer array.
3. Invoke every control's engine deleting destructor.
4. Run the base panel destructor, which frees the pointer array.
5. Free the panel when the engine supplied the deleting flag.

This is necessary because the base panel owns its array storage but does not own
the objects referenced by it. That behavior was established directly from the
1.03 destructor; see
[custom GUI controls](../reverse-engineering/custom-gui-controls.md).

The panel checks the active input device and glyph family each GUI frame, but it
only changes visibility and fill resrefs when either value changes. Switching
from mouse to controller changes the device heading; switching between supported
controller families replaces the thirteen row glyphs and the diagram board
without rebuilding the panel.

## Lifecycle trace

The validation build writes transition records to
`kmrp-layout-lifecycle.log` in `KMRP\logs` in the game directory (the game directory
itself until 2026-10-20). It does not log per frame.
Each line contains the live panel and parent addresses plus cumulative counts for
panels, controls and callbacks. Useful events are:

| Event | Meaning |
| --- | --- |
| `entry-create` / `entry-destroy` | Gameplay-screen entry acquired and released |
| `open-callback` | A keyboard, mouse or controller activation reached the entry |
| `opened` | The modal panel and all 47 controls were added successfully |
| `refresh` | Input-device or controller-family presentation changed |
| `close-request` | Back or B requested normal manager removal |
| `back-ignored-unarmed` | Back was activated by the press that opened the screen, and ignored |
| `open-ignored-after-close` | The entry was activated by the press that closed the screen, and ignored |
| `destroy-begin` / `destroy-end` | Explicit control and panel cleanup completed |
| `bind-failed` | A required resource tag was absent or collided; the screen did not open |
| `remap-enter` | Remap pressed: the rows became editable (since 2026-10-18, as are the rows below) |
| `remap-listen` | A row asked for its new button: the prompt opened |
| `remap-assigned` | A button was chosen for the row |
| `remap-saved` | Save wrote the layout to `KMRP\controller.ini` (`kmrp-controller.ini` until 2026-10-20) |
| `remap-unsaved` | Close was pressed with changes not saved: the Unsaved Changes box opened |
| `remap-exit` | Back to the view, by Close with nothing unsaved or by Discard |

The `opened` line counts the file's 47 controls and, since 2026-10-18, the 55 the
remap screen makes; all of them are freed by the same destructor.

`controls` and `freed` also count the A label bound into each confirmation box
(see `updateConfirmBadges`), which lives as long as that box does -- usually
the whole session -- so compare the counts across a layout open/close cycle,
not in absolute terms.

After every completed cycle, `created == destroyed`. While the parent Gameplay
screen remains open, `controls - freed == 1` because its entry button is still
live; after leaving Gameplay the difference must return to zero. (This paragraph
and the table above called the parent "Controls" until 2026-09-24; the entry has
been on Options → Gameplay since 2026-09-21.) There must be
no second `opened` without a matching `destroy-end`, and no `bind-failed`
record.

## Manual acceptance test

**Used in play at 3440x1440, by 2026-09-24**: opened from Options →
Gameplay and closed with A on Back and with B, with a controller -- which is how
the open/close defects and the wrapped captions above were found, and after
their fixes it opens with one press and closes without reopening. The captions
were measured on screen. **Not run as a whole**: the matrix below -- repeated
cycles, keyboard-only activation, family switching, the lifecycle log. Use the
installed candidate and keep the lifecycle log after the run.

1. Open Options, then Gameplay, and activate Controller Layout under
   Keymapping with the mouse. Confirm Back returns to the same Gameplay screen.
2. Repeat open and close ten times, alternating the on-screen Back button and
   Escape/B. Confirm there is one panel, focus remains usable, and the parent
   screen is never skipped.
3. Navigate to the entry and activate it with keyboard only. On the panel,
   activate Back with Enter/Space and repeat with Escape.
4. Navigate and activate the entry with a controller. Close it with both A on
   Back and B. Repeat with the D-pad and left stick.
5. While the panel is open, move the mouse, then use the controller. Confirm the
   active-input heading follows the last device and focus does not stick.
6. If two supported controller families are available, make each one active
   while the panel remains open. Confirm all glyphs change together and the
   panel is not duplicated or rebuilt.
7. Return to gameplay and re-open Options → Gameplay → Controller Layout. Confirm no crash, stale
   focus, duplicate entry or lost input.
8. Exit normally and inspect `KMRP\logs\kmrp-layout-lifecycle.log` (in the game
   folder itself until 2026-10-20) for balanced panel and control counts and the
   absence of `bind-failed`.

Physical-family switching is conditional on having two independently visible
devices. A single controller cannot validate that row of the matrix.

*Since 2026-10-18* step 4 cannot be done as written: Back is no longer a place for
the pad's focus, so the pad closes the screen with B only (and the mouse still
clicks Back). The remapping checks are in
[`controller-playtest-checklist.md`](controller-playtest-checklist.md), section 9.

## Button remapping

**Kind: reference.** Written on 2026-10-18 from that day's source, which was not
yet committed: `src/controller-native/K1ButtonRemapPolicy.h` (the rules),
`K1ButtonRemap.h` and `K1ButtonRemap.cpp` (the settings and the translation),
`K1ControllerLayout.cpp` (the screen), `K1NativeJoystick.cpp` (the pad, the focus
and the HUD cues), `K1XboxHud.cpp` (the pause notice) and
`tools/build_controller_layout.py` (the textures). The rules are the maintainer's,
decided on 2026-10-18 from mockups they approved. **Nothing has been run with a pad**:
what was seen, and how, is under [Tested and not tested](#tested-and-not-tested)
below.

**Brought up to issue 49 on 2026-10-19**, from that day's source, also uncommitted
when written (the same files and `K1XboxHud.cpp`). The maintainer decided that day
that the controller uses the original Xbox game's layout everywhere ("It should be
classic everywhere"), with no second layout to choose; the Xbox's White and Black
are LB and RB, as Xbox 360 and One backward compatibility placed them. That moved
Disengage, Pause, Switch ally and both target actions to other default buttons;
replaced Release bar with Add to queue (B's action is Disengage now, which lets go
of the bar first) and renamed Undo action to Undo or flourish; changed the saved
keys to match (`AddToQueue` new, `ReleaseBar` gone); and added a `Layout` line to
the settings file. Interact, Undo, Flourish and Free look kept their buttons. The
rules, the screen and the translation are unchanged. The sections below say what
each part was until then. None of it has been run in the game;
`Test-ButtonRemap.py` was reported passing on that source (CHANGELOG,
`[Unreleased]`).

### The build and the address convention

Engine addresses are preferred-image **VA** in the clean editable CD 1.03
executable, 4,042,752 bytes, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`
(`build-inputs\swkotornopatch.exe`, hashed on 2026-10-18). Every address is in the
original image, so **FILE = VA - 0x400000**; the appended-section rule
(FILE = VA - 0x492000) does not apply.

Remapping writes no executable byte and adds no hook. The controller patch still has
38 (neither `src/controller-native/kotor1.hooks.toml` nor
`tools/build_controller_kpatch.py` is changed by it). It runs from hooks the patch
already had:

| Part | Runs from |
| --- | --- |
| The screen | `ControllerLayoutFrameK1`, called from `NativeGuiFrameK1` at `0x0040CE70` |
| The translation of the pad's buttons | `FillNativeJoystickBufferK1`, called from `NativeJoystickBufferK1` at `0x005E30F6` |
| The HUD's Y and B cues (Y and X until 2026-10-19) | `UpdateGuiCuesK1`, called from `NativeGuiFrameK1` |
| The pause notice's button | `PlacePause`, from `KmrpXboxHudK1` at `0x0068AB10` and `KmrpXboxHudPauseReasonDoneK1` at `0x006C02A4` |

### What can be remapped

Ten actions on ten buttons. An action is named by its default button, which is also
the name the rest of the controller code knows it by, so a remap is a translation of
the pad's buttons into the default ones and nothing downstream changes
(`K1ButtonRemapPolicy.h`). Read from `kActionNames`, `kFixedAfter` and
`kFixedBefore` in `K1ControllerLayout.cpp`, `ActionKeys` and `LayoutRow` in
`K1ButtonRemapPolicy.h`, and `LAYOUT` in `tools/build_controller_layout.py`:

| Action, as the row shows it | Key in `[Controller Remap]` | Default button | Its row (`GLYPH_nn`, `TEXT_nn`) | What stays with the button, in grey |
| --- | --- | --- | --- | --- |
| Interact | `Interact` | A | 11 | "/ Select" after it |
| Disengage | `Disengage` | B | 10 | "/ Back" after it |
| Add to queue | `AddToQueue` | X | 09 | "/ Menu action" after it |
| Undo or flourish | `UndoAction` | Y | 08 | "/ Menu action" after it |
| Pause | `Pause` | LB | 01 | nothing |
| Switch ally | `SwitchAlly` | RB | 06 | "/ Menu action" after it |
| Previous target | `PreviousTarget` | LT | 00 | "/ Prev tab" after it |
| Next target | `NextTarget` | RT | 05 | "/ Next tab" after it |
| Flourish | `Flourish` | L3, the left stick's click | 03, the left stick's row | "Move / Click:" before it |
| Free look | `FreeLook` | R3, the right stick's click | 12, the right stick's row | "Camera / Click:" before it |

The grey part is what the button keeps whatever action it carries: its meaning in
menus, which keep every button where it is, or its stick's movement. RB's "/ Menu
action" is the Xbox's Black there: the next party member on the four screens about
one, and the Journal's sort.

What the defaults do in the world, from `K1NativeJoystick.cpp`: Add to queue asks for
exactly what A does (on the Xbox X added an action to the queue and A acted at once;
on the PC every action is queued, so the two are one action here); Undo or flourish
presses the HUD's `BTN_CLEARONE` while it is on screen and otherwise flourishes the
weapons, as L3 does; Disengage lets go of the action bar when a slot has focus and
otherwise presses the HUD's Disengage button (`BTN_CLEARALL`) while it is on screen,
with either HUD; Pause, Switch ally, Previous target and Next target are the game's
events `0x02`, `0x09`, `0x06` and `0x05` on their default button's slot
(`K1_GAMEPLAY_ACTIONS`).

*Changed 2026-10-19 (issue 49).* Until then the defaults were KMRP's own, and the
table read: Interact on A; Release bar (`ReleaseBar`) on B, letting go of the action
bar only; Disengage on X; Undo action on Y; Previous target on LB; Next target on RB;
Switch ally on LT; Pause on RT. RB's row then had nothing grey after it. The rows did
not move: a row is a button, so only the action each button starts with changed.

**Fixed**, shown grey with a padlock and never a place for the focus: moving (the
left stick), the camera (the right stick), the D-pad (the action bar and
navigation; row 04), Start (row 07) and Back, the View button (row 02). The two
sticks' rows are remappable for the click only, so their padlock stands at the row's
outer end for the movement.

`Test-ButtonRemap.py` checks that each `LayoutRow` entry names the row `LAYOUT`
gives that button (a stick click is its stick's row).

### The rules

**No swapping.** Giving a button to an action takes it from the action that had it,
and that action is left without a button until it is given one. **Rows are
buttons:** each row's line on the drawing points at one button, so a row always shows
the action on its button, and an action given another button moves to that button's
row. The action left without a button waits, in orange with an orange "?" where its
glyph was, in the row the moving action left. There are as many actions as buttons,
so every free button always has exactly one action waiting in its row. **Save** works
only when no action waits; until then it is grey and the help line, in orange, names
the action with no button.

A worked example, the harness's first (`button_remap_harness.cpp`). On the default
layout, A on Undo or flourish's row (Y) and then RB:

| Row (button) | Shows | State |
| --- | --- | --- |
| RB | Undo or flourish | moved here, with a dot (the button carries an action not its own) |
| Y | Switch ally | waiting: orange, `kmrrmask` in place of the Y glyph |
| help line | `Switch ally has no button.   Every action needs one before you can save.` | orange; Save grey |

Then A on Y's row and Y: Switch ally is on Y, nothing waits, Save works. The two
actions have traded buttons, in two steps. (Until 2026-10-19 RB's default action was
Next target, and the example named it where it now names Switch ally.) The harness also runs every sequence of
three assignments over the ten rows and ten buttons (1,000 sequences) and checks
that the waiting rows always equal the free buttons, and that the layout is complete
exactly when none waits.

Why rows are buttons rather than actions: so the drawing, whose lines are fixed in
its texture, never contradicts itself (the reason given in `K1ButtonRemapPolicy.h`).
No swapping is the maintainer's decision; the source records the decision, not a
reason for it.

### The screen, state by state

The screen's own buttons are pressed with pad buttons, by position, as every menu
has them; they are never a place for the pad's focus (`KmrpPadFocusExcludeK1`,
below). A pad glyph beside a button shows only while a pad is the device in use.

| State | Footer | The pad | Mouse and keyboard |
| --- | --- | --- | --- |
| **View**, as the screen opens | (X) Remap, (B) Back; the help line | X: Remap. B leaves the screen. A and Y do nothing. Nothing can be focused | Remap and Back can be clicked; a row ignores a click; Escape leaves the screen |
| **Remapping** | (Y) Default, (X) Save, (B) Close; "(A) Change button" between the hairline and the buttons, pad only | the D-pad moves between the ten rows; A asks for the focused row's button; Y puts the default layout back (not saved); X saves when every action has a button; B is Close | click a row to ask for its button; Default, Save and Close can be clicked; Escape is Close |
| **Waiting for a button** | hidden; the prompt in its place | the first remappable button pressed after the prompt opened is the row's new button; Back cancels; every menu event is swallowed | the prompt's Cancel button or Escape cancels; the keyboard cannot choose a button |
| **Unsaved Changes** | hidden under a dimmed screen | A: Discard. B: Cancel | Discard and Cancel can be clicked; Escape is Cancel |

Remap focuses the row the focus was last on, LT's row the first time after the
screen opens. Close with
nothing unsaved, and Discard, put the saved layout back in the editor, return to the
view and clear the focus. Cancel in the Unsaved Changes box returns to remapping with
the changes kept.

**The help line.** With every action on a button: `A dot marks a changed button.   A
lock stays as it is: moving, the camera, the D-pad, Start and Back.`, in the
captions' colour; with one waiting: the orange line of the example above.

**Colours.** An action's caption is the file's caption colour, yellow
(236, 226, 38) on the focused row, orange (245, 140, 30) while it waits; the grey
parts and the fixed rows are (150, 150, 155). The dot is drawn outside the row's
frame at its outer end, beside a row whose button carries an action other than its
own; a saved remap therefore shows its dots in the view as well.

**The prompt while a button is awaited** stands in the help line's and the footer's
place, as wide as the three footer buttons: the title `Press the new button for
<action>`, the line `If another action has that button, it is left without one`, and
a Cancel button carrying the View button's glyph (`kmr?lyt02`). Its box is made from
the screen's Back button, filled black and never selectable, so it keeps that
button's blue border; yellow is kept for the focused row. While it is up, every other
row is faded: captions at 40% of their colour, grey parts at 50%, glyphs at 35%
opacity.

How the button is read: the screen reads the pad itself, every GUI frame, from the
word `K1NativeJoystick.cpp` keeps before translation (`g_padPhysicalButtons`, read
through `KmrpPadButtonsK1`), because menus send no event for LB or a stick's click,
RB's menu event (`0x2B`, the Xbox's Black, since 2026-10-19; none before) means
nothing on this screen, and every one of them may be chosen. Buttons already held as the prompt opens
do not count. Back cancels there because it can never be chosen. The pad's B arrives
as the menu's B event (`0x28`) as well as in that word; the screen tells it from the
keyboard's Escape, which is the same event, by whether the pad's B is down. **Read
from the code, not run:** Start sends B's event over a menu (the comment on
`handleBack`), so Start would cancel the wait too.

**The Unsaved Changes box:** the screen dimmed (a copy of `LBL_DIAGRAM` filled black
at 0.7), a box in the middle with the title `Unsaved Changes`, the lines `You have not
saved your new controller layout.` and `Discard your changes?`, and (A) Discard and
(B) Cancel.

**One press, one effect.** After Remap, after Close or Discard, and after a button is
chosen or the wait cancelled, the screen ignores every event until every pad button,
Start and Back included, is up and confirm is released (`settle`). B is acted on once
per frame, because the panel's own B handler and its input routine can both be told
of one press (`handleBack`).

### What the screen adds at run time

Nothing is added to `kmrplayout.gui`. Every control is made as the screen opens, from
one of the file's own controls by its tag, and placed from the file's rectangles read
at that moment, so it follows the file at every resolution and the file stays as
KMRP's sets have it (`buildRemap`, `layoutRemap`):

| Controls | Count | Made from | What |
| --- | ---: | --- | --- |
| Row frames | 10 | `BTN_BACK` | a button with its border images cleared and no text, round the glyph and the caption, a sixth of the glyph's height clear; the focus draws the game's highlight on it; its A runs `rowPressed` |
| Grey captions | 10 | `TEXT_05` | what stays with the button |
| Dots | 10 | `GLYPH_BACK` | `kmrrmdot`, 3/10 of the glyph's height |
| Padlocks | 5 | `GLYPH_BACK` | `kmrrmlock`: moving, the camera, the D-pad, Back, Start |
| Footer | 6 | `GLYPH_BACK`, `TEXT_05`, `BTN_BACK` | the "(A) Change button" hint's glyph and text; Default and its glyph; Save (Remap in the view) and its glyph |
| The prompt | 5 | `BTN_BACK`, `LBL_TITLE`, `LBL_HELP`, `GLYPH_BACK`, `BTN_BACK` | box, title, line, Cancel's glyph, Cancel |
| Unsaved Changes | 9 | `LBL_DIAGRAM`, `BTN_BACK`, `LBL_TITLE`, `LBL_HELP` twice, `BTN_BACK` and `GLYPH_BACK` twice | dim, box, title, two lines, Discard and Cancel with their glyphs |
| **Total** | **55** | | with the file's 47, 102 controls; `owned[]` holds 192 (`kOwnedSlots`, checked by a `static_assert`) |

The file's own Back button is relabelled Back in the view and Close while remapping,
and placed in the footer row with the others (Back and Remap as a centred pair in the
view; Default, Save and Close three across while remapping; centres 1.4 times
Back's width apart).

**How a control is added** (`bindAppend`). The file's control array has no free slot,
so a control is constructed, loaded from the tag's struct with the bind's store
switched off, given the next ID and appended:

1. `operator new` (`0x006FA7E6`), 0x1C4 bytes for a button or 0x140 for a label; the
   button or label constructor; the ID at `+0x50` set to -1.
2. `CSWGuiPanel::InitControl` (`0x0040B930`) with its last argument 0: the control is
   loaded and stored in no array (the store rule is in
   [custom-gui-controls.md](../reverse-engineering/custom-gui-controls.md)).
3. The ID set to the panel's count (`+0x24`), then `CSWGuiPanel::AddControl`
   (`0x0040B9A0`) appends it.
4. Read back: the count must have grown by one and the array (`+0x20`) must hold the
   control at that ID. Otherwise the control is destroyed, `bind-failed` is logged,
   and the screen does not open.

### Textures

Made by `build_art` in `tools/build_controller_layout.py`, which KMRP's resource
build and the controller patch's both run:

| Resref | Count | Drawn by | Used for |
| --- | ---: | --- | --- |
| `kmr?rm<code>`, `?` the family (`p` Xbox, `s` PlayStation, `n` Switch, `d` Steam Deck), `<code>` one of `a b x y lb rb lt rt l3 r3` | 40, ten per family | `REMAP_GLYPHS` through `build_square_glyph_tga`, the function that draws every other cue; a stick's click is the pack's click drawing | the footer's and the boxes' pad glyphs; the HUD's Y and B cues (Y and X until 2026-10-19); the pause notice's button, always since 2026-10-19 (`kmr?rmlb` on the default layout), and until then only while Pause was not on RT; on Pazaak's table, the flip legend's LB and the made "Play Hand Card" line's X (since 2026-10-19, `UpdatePazaakTableK1`) |
| `kmrrmask` | 1 | `_remap_marks`: an orange ring on the screen's navy with an orange "?" in `KOTOR_UI_Open.ttf` | a waiting row's glyph |
| `kmrrmlock` | 1 | `_remap_marks`: a grey (150, 156, 168) padlock | the fixed controls |
| `kmrrmdot` | 1 | `_remap_marks`: a yellow (236, 226, 38) disc | a changed button |

The three marks are one picture for every family. **Counted and compared on
2026-10-18** in `build\controller-standalone\files` as built at 19:10 that day: all
43 present, each 65,580 bytes (a 128x128 32-bit TGA). With `cmp`:

| Compared | Equal |
| --- | --- |
| `kmr?rmy`, `kmr?rmx`, `kmr?rmb` with the combat cues' own `kmr?y_cmbt`, `kmr?x_cmbt`, `kmr?b_cmbt`, four families | 12 of 12, so on the default layout the HUD's cues are the same pictures as before |
| `kmr?rm<code>` with the screen's row glyph `kmr?lyt<row>` for the same button, four families | 32 of 40; the 8 that differ are L3 and R3 in every family, where the row shows the bare stick and the remap glyph the stick's click |

*Since 2026-10-19* no `kmr?x_cmbt` is built: the Disengage cue's file fill is the B
picture, `kmr?b_cmbt` (`COMBAT_CUES` in `tools/prepare_universal_resources.py`; the
controller patch makes it once for that cue and the Xbox-style HUD's combat-mode
message, `tools/build_controller_assets.py`). So the X comparison in the first row
cannot be repeated on a newer build; the Y and B ones can. Not counted again for
this note.

### Engine functions it calls

Entry bytes read from the executable above and the first `ret` found disassembling
from the entry with Capstone, on 2026-10-18. Names are from the code's comments and
the documents that already list these routines. **Corroboration:**
[ingame-text-options.md](ingame-text-options.md) gives the same entry bytes for
`0x0040B9A0`, `0x0041AB20` and `0x0040A630`.

| VA | FILE | Entry bytes | Ends | Routine | Use here | New to this file |
| --- | --- | --- | --- | --- | --- | --- |
| `0x006FA7E6` | `0x2FA7E6` | `6A 01 FF 74 24 08` | `ret` | `operator new` | every added control | no |
| `0x0041C0F0` | `0x01C0F0` | `6A FF 68 31 53 71 00` | `ret` | `CSWGuiButton` constructor | frames, boxes, footer buttons | no |
| `0x0041ACD0` | `0x01ACD0` | `6A FF 68 63 51 71 00` | `ret` | `CSWGuiLabel` constructor | captions, glyphs, marks | no |
| `0x005E5A90` | `0x1E5A90` | `56 57 8B 7C 24 0C` | `ret 4` | `CExoString` from text | tags and texts | no |
| `0x005E5C20` | `0x1E5C20` | `56 8B F1 8B 06` | `ret` | `CExoString` destructor | the same | no |
| `0x0040B930` | `0x00B930` | `8B 44 24 08 55` | `ret 0xC` | `CSWGuiPanel::InitControl` | load by tag, last argument 0 | no (called with 1 before) |
| `0x0040B9A0` | `0x00B9A0` | `53 8B 5C 24 08 56` | `ret 4` | `CSWGuiPanel::AddControl` | append to the panel | **yes** |
| `0x00415E00` | `0x015E00` | `8B 44 24 04 56 50` | `ret 4` | the GUI text setter | text params at `+0xE8` (label) or `+0x16C` (button) | **yes** |
| `0x00414E10` | `0x014E10` | `8B 54 24 04 56 57` | `ret 4` | `CSWGuiTextParams::SetColor` | caption colours, Save's text | **yes** |
| `0x00414AE0` | `0x014AE0` | `83 EC 14 53 8B 5C 24 1C` | `ret 8` | `CSWGuiBorderParams::SetCornerImage` | cleared on the row frames | **yes** |
| `0x00414B70` | `0x014B70` | `83 EC 14 53 8B 5C 24 1C` | `ret 8` | `CSWGuiBorderParams::SetEdgeImage` | the same | **yes** |
| `0x00414C00` | `0x014C00` | `83 EC 14 53 8B 5C 24 1C` | `ret 8` | `CSWGuiBorderParams::SetFillImage` | every glyph, mark and box fill | no |
| `0x0041AB20` | `0x01AB20` | `53 56 8B 71 3C` | `ret 0xC` | add an event callback | A (`0x27`) on each row frame and button | no |
| `0x0040A630` | `0x00A630` | `56 8B 74 24 08` | `ret 8` | `CSWGuiPanel::SetActiveControl` | focus a row; null on opening and on Close | no |

Each `ret N` agrees with the arguments the code passes: the methods are
`__thiscall`, so N is four bytes per stack argument, and `operator new` is
`__cdecl`, so its caller removes the argument. Fields the code reads and writes, from the code; the last
three meanings are taken from what the code does with them and, for the opacity, from
the faded rows seen on screen:

| Where | What |
| --- | --- |
| control `+0x44`, bit 8 | selectable: set on the row frames only while remapping; never on the two boxes |
| control `+0x50` | the control's ID |
| panel `+0x1C` | the focused control, read every frame |
| panel `+0x20`, `+0x24` | the control array and its count |
| label `+0x70` | its border params: fill resref at `+0x40`; the float at `+0x0C` written 1.0, 0.7 or 0.35 as opacity |
| label `+0xE8` | its text params: colour, three floats, at `+0x1C` |
| button `+0x80` | its normal border params: colour, three floats, at `+0x10`, set grey on Save while it cannot save |

### Keeping the screen's buttons off the pad's focus

`KmrpPadFocusExcludeK1(control, excluded)` in `K1NativeJoystick.cpp` keeps a list of
up to 16 controls that `ControlIsNavigableK1` refuses, so the D-pad never lands on
them while the mouse still clicks them. The screen registers six as it opens (Back,
Default, Save, Discard, Cancel and the prompt's Cancel) and takes them back as it
closes (`forgetRemap`), so no address outlives its control. The selectable bit was
not used for this because a control that cannot be selected cannot be clicked either
(the comment on `g_padFocusExcluded`).

### In play: the translation

In `FillNativeJoystickBufferK1`, right after the pad is read and before any event is
made from it, the pad's button word goes through `KmrpRemapButtonsK1`. Everything
after it (the engine's slots, the HUD's activate and release, the combat buttons,
the stick clicks) sees each button as the default button of the action it carries.

| | |
| --- | --- |
| The word | XInput's button bits; LT and RT folded into the two bits XInput leaves unused, `0x0400` and `0x0800`, while pulled past 60 of 255 (`K1_TRIGGER_THRESHOLD`) |
| Remappable bits | A `0x1000`, B `0x2000`, X `0x4000`, Y `0x8000`, LB `0x0100`, RB `0x0200`, LT `0x0400`, RT `0x0800`, L3 `0x0040`, R3 `0x0080` |
| Passed through untouched | the D-pad (`0x0001` to `0x0008`), Start `0x0010`, Back `0x0020` |
| In the world | the input class at `CClientExoAppInternal + 0x9C` is 0 (`ICPC`) or 4 (`ICFreeLook`): each pressed button becomes the default button of its action |
| Everywhere else | menus (class 2), conversations (3), minigames (1) and movies (5): every button is itself |
| One press, one meaning | decided when the button goes down and kept until it is released, so a press that opens or closes a menu releases the button it pressed |
| Triggers after | only when the word changed: given back as 255 if their bit is set, else 0, which is all the function reads of them |
| An incomplete layout | never used: every button stays itself (the saved layout is always complete anyway) |

Example, checked by the harness: with Undo or flourish on RB and Switch ally on Y, RB
in the world is Y's (Undo or flourish), Y in the world is RB's (Switch ally), RB in a
menu is RB; RB pressed in the world and still held as a menu opens stays Y until it
is released, and the next RB in the menu is RB. (Until 2026-10-19 the example's
second action was Next target, RB's default then.)

### The HUD's cues follow the remap

`ShowActionCueK1` fills a cue with `kmr?rm<code>` for the button its action is on,
read from the saved layout (`KmrpRemapGlyphK1`), so a cue changes after Save, not
while the layout is being edited:

| Cue | Names the button of | Before 2026-10-18 |
| --- | --- | --- |
| `LBL_KMRPY`, beside `BTN_CLEARONE` | Undo or flourish (named Undo action until 2026-10-19); Y by default | the family's `kmr?y_cmbt` |
| `LBL_KMRPX`, beside `BTN_CLEARALL` | Disengage; B by default since 2026-10-19, so the cue shows B. Until then Disengage was X's by default and the cue showed X. The tag keeps the old name: it names the control in the layout files, not the button it shows | the family's `kmr?x_cmbt` |
| `LBL_KMRPX` with the Xbox-style HUD (controller patch only), in the combat-mode message | Disengage too, the Xbox game's "[B] to disengage" (`K1_GUI_CUES` gives both one action since 2026-10-19). From 2026-10-18 to 2026-10-19 it named Release bar, the action then on B, because Disengage was X's | `kmrpb_cmbt` (`kDisengageFill` in `K1XboxHudLayout.inc`), set by `K1XboxHud.cpp` and given the family's letter by `MatchCueFamilyK1`; `K1XboxHud.cpp` no longer sets it |
| the pause notice's button (Xbox-style HUD) | Pause; LB by default since 2026-10-19, so always `kmr?rm<code>`, `kmr?rmlb` on the default layout. From 2026-10-18 to 2026-10-19 Pause was RT's by default, and while it stayed on RT the notice kept `kmr?rt_pause`, the lighter trigger drawn for that line (`K1XboxHud.cpp`, `PauseNotice`) | `kmr?rt_pause` |

`kmr?rt_pause` is still built (`tools/build_controller_assets.py`): the Mac's patch
shows it until it moves to LB too. Windows no longer shows it.

The other cues (the tab strip's LT and RT, the party cue, the swap-tabs cue) are in
menus, where buttons do not move, and keep their own art (`MatchCueFamilyK1`).

### The settings file

`KMRP\controller.ini` in the game folder since 2026-10-20 (`KmrpControllerSettingsPath`
in `KmrpOptions.h`, read and written with the wide-character profile calls), section
`[Controller Remap]`, one key per action, the value its button, and since 2026-10-19 a
`Layout` line naming the defaults the keys were saved against. Until 2026-10-20 it was
`kmrp-controller.ini` in the game executable's folder (from
`GetModuleFileNameA(NULL)`, with the ANSI calls); the module moves that file into
`KMRP` the first time it looks for the settings and finds no `KMRP\controller.ini`, so
a saved layout is kept. Not run in a game. The default layout, as Save writes it (`LayoutKey`,
`LayoutName` and `ActionKeys` in `K1ButtonRemapPolicy.h`, written in that order by
`KmrpRemapSaveK1` in `K1ButtonRemap.cpp`):

```ini
[Controller Remap]
Layout=Xbox
Interact=A
Disengage=B
AddToQueue=X
UndoAction=Y
Pause=LB
SwitchAlly=RB
PreviousTarget=LT
NextTarget=RT
Flourish=L3
FreeLook=R3
```

Until 2026-10-19 there was no `Layout` line and the default read `Interact=A`,
`ReleaseBar=B`, `Disengage=X`, `UndoAction=Y`, `PreviousTarget=LB`, `NextTarget=RB`,
`SwitchAlly=LT`, `Pause=RT`, `Flourish=L3`, `FreeLook=R3`. Nine of those keys are
still keys, five of them (`Disengage`, `PreviousTarget`, `NextTarget`, `SwitchAlly`,
`Pause`) with other defaults now, so a layout saved then was chosen against defaults
that no longer exist. That is why a layout without the `Layout` line is not read
(the comment on `LayoutKey`).

It lives there and not in `configs\` because the controller patch works without KMRP,
as `Style` under `[Hud]` does (the comment at the top of `K1ButtonRemap.cpp`).

- **Read** once, the first time anything asks for the layout, and only when the
  section has `Layout=Xbox` (compared without case). Without that line, as in every
  layout saved from 2026-10-18 to 2026-10-19, nothing is read: the default is used
  and the screen opens on it. A missing key is its action's default button. Names
  are compared without case. A value that names no button, or two actions on one
  button, makes the layout incomplete, and an incomplete layout is not used at all:
  the default is, and the screen opens on it.
- **Written** by Save only, with `WritePrivateProfileStringA`, which also makes the
  file if it is missing. Since 2026-10-19 Save first deletes the whole section, so no
  key of the old layout is left behind, then writes the `Layout` line and the ten
  keys (until then it wrote the ten keys over whatever was there). The module takes
  the new layout only when the `Layout` line and all ten keys are written.
- KMRP's installer writes this file only when it is absent and never overwrites it.
  By the rule that Restore Original leaves alone a file changed since it was
  installed ([features-technical.md](features-technical.md), "Restore Original"), a
  saved layout should survive a restore. **Not tried.**

### Limits

Read from the code on 2026-10-18; none of these has been run.

- **The pause notice with Pause moved off RT: found and fixed the same day.**
  `PauseCarriesOurs` in `K1XboxHud.cpp` recognised this file's pause box only by the
  button's fill being `kmr?rt_pause`. With Pause on another button the fill is
  `kmr?rm<code>`, so the box would not have been recognised as this file's:
  `PauseNotice` would have taken the box's own, already moved, rectangles as the
  layout's each frame; `RestorePauseNotice` would have left the Xbox layout and the
  picture in the PC's box when the mouse or keyboard is used while paused; and
  `KmrpXboxHudPauseReasonK1` would not have taken the picture off before the game lays
  the box out again. Found while writing this section, from the code. It now
  recognises `kmr?rt_pause` and `kmr?rm<code>` for every remappable button, not only
  the one Pause is on now, since a layout saved while the box is up leaves the old
  picture in it until `PauseNotice` sets the new one. Built; **not run** (it needs a
  pad and a remapped Pause). *Since 2026-10-19* the notice always shows
  `kmr?rm<code>` (Pause is LB's by default), and `PauseCarriesOurs` recognises that
  alone; `kmr?rt_pause` is no longer one of its pictures on Windows.
- **A hand edit is seen at the next start**, unlike `[Rumble]`, which is read again
  while playing: the layout is read once.
- **A Save that fails part way** leaves the keys before the failure written. The file
  may then read as incomplete at the next start and give the default layout. Since
  2026-10-19 the section is deleted first, so a Save whose `Layout` line fails leaves
  no layout at all, which also reads as the default.
- **The keyboard and mouse cannot choose a button**: the prompt waits for the pad.
  They can open it, cancel it and use every other part of the screen.
- **The view with a pad** offers nothing to focus, so the D-pad there does nothing.
  That is the design (only X and B act), not seen.

### What is deliberately not changed

- Menus, conversations, minigames and movies: every button stays where it is, since
  only the world is translated.
- The sticks' movement, the D-pad, Start and Back: not remappable.
- `kmrplayout.gui`: no control added; its captions are what the screen starts from.
- `keymap.2da`, the keyboard's bindings and the executable: the remap is a
  translation inside the module, after the pad is read.
- The hook list: 38 hooks, as before.
- Issue 49 (2026-10-19) moved no row and added no control or texture to this screen:
  rows are buttons, so only the action each button starts with, two action names
  and the file's captions changed.

### Tested and not tested

**Seen on 2026-10-18**, in the test game at 3440x1440 and 1920x1080, driven with
mouse and keyboard by scripted input and checked in ddagrab screenshots:

| What | Result |
| --- | --- |
| The screen opens | as the view, with Remap and Back; a click on a row does nothing |
| Remap | the footer becomes Default, Save and Close |
| A click on a row | the prompt opens, the other rows faded |
| Escape | cancels the prompt, then closes remapping, then leaves the screen |
| The prompt's Cancel button | cancels |
| Close with nothing changed | back to the view |
| Close with a change | the Unsaved Changes box |
| Discard | back to the view, showing the saved layout with its dots |
| Save | writes `KMRP\controller.ini` (`kmrp-controller.ini` until 2026-10-20) |

`python testing\regression\Test-ButtonRemap.py` passes: it compiles and runs
`button_remap_harness.cpp` (assignment, completeness, the editor's rows, the
translation in and out of the world and per press, the settings names) and checks
the header's row and glyph tables against `tools/build_controller_layout.py`. Run
again on 2026-10-18 while this section was written: it printed its PASS line and both
table checks.

**Not tested: anything with a pad.** The machine has no virtual pad (ViGEmBus is not
installed), so none of these has run: the D-pad on the rows; A on a row and then a
new button, including LB, RB, the triggers and the stick clicks; X, Y and B on the
screen; Back cancelling the prompt; A and B in the Unsaved Changes box; the pad's
glyphs on the screen; the translation in play; the HUD's Y and B cues (Y and X until
2026-10-19) and the pause notice following a saved remap; the other families' art;
and a saved layout surviving Restore Original. They are rows of
[`controller-playtest-checklist.md`](controller-playtest-checklist.md), section 9.

**Not seen at all, 2026-10-19:** the screen with issue 49's defaults, captions and
action names; a save writing `Layout=Xbox`; a layout saved before that day opening
as the Xbox defaults; and any of the new defaults in play.

### Verifying by hand

```powershell
# the rules, and the tables the header shares with the tools
python testing\regression\Test-ButtonRemap.py
```

Then, after building the controller patch
(`src\controller-native\build_controller_standalone.cmd`):

1. Count the textures: `build\controller-standalone\files` must hold the 40
   `kmr?rm*.tga` and the three `kmrrm*.tga`, and `cmp` must find each `kmr?rm{y,b}`
   equal to `kmr?{y,b}_cmbt` (until 2026-10-19 this step also compared `kmr?rmx` with
   `kmr?x_cmbt`, which is no longer built). A count of zero means the build did not
   run `build_art`, not that the names are wrong: check one name by hand first.
2. Read the entry bytes and `ret` of the routines above from the clean executable
   at FILE = VA - 0x400000.
3. In a scratch game with `debug-logs` on and a pad, open the screen, Remap, change
   a button, Save, and leave. `KMRP\logs\kmrp-layout-lifecycle.log` should show `remap-enter`,
   `remap-listen`, `remap-assigned`, `remap-saved` and `remap-exit` in that order, no
   `bind-failed`, and `created == destroyed`; `KMRP\controller.ini` should have
   `[Controller Remap]` with `Layout=Xbox` and ten keys, no two with the same value.
4. Put a duplicate value into `[Controller Remap]` by hand and start the game: the
   screen must open on the default layout.
5. Delete the `Layout=Xbox` line by hand, leaving the ten keys on a layout that is not
   the default, and start the game: the screen must open on the default layout.
