# Controller Layout screen

This document follows the [documentation standard](documentation-standard.md).
It describes the implementation prepared on 2026-09-19 and keeps runtime claims
separate from the manual acceptance test that still has to be performed.

## What ships

**Options → Gameplay** gains a `Controller Layout` button directly under
Keymapping, a copy of that button in the same column. It opens the dedicated
`kmrplayout.gui` panel, built from KOTOR's own controls, so it scales, takes
focus and closes like any other panel. Until 2026-09-21 the entry sat on the
Mouse screen instead, which Options does not list, so it was two screens deep
where nobody found it.

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
| LT / RT | Switch ally / Prev tab · Pause / Next tab |
| LB / RB | Previous target · Next target |
| View / Menu | Solo mode · Map / Close menu |
| Left stick | Move / Click: flourish |
| Right stick | Camera / Click: free look |
| D-pad | Action bar / Navigate |
| A / B | Interact / Select · Back / Release bar |
| X / Y | Screen action |

Plain ASCII, because the menu face has 95 printable-ASCII glyphs and nothing
else.

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
while the parsed layout still exists. On `CSWGuiOptionsGameplay` it allocates one
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
`kmrp-layout-lifecycle.log` in the game directory. It does not log per frame.
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
8. Exit normally and inspect `kmrp-layout-lifecycle.log` for balanced panel and
   control counts and the absence of `bind-failed`.

Physical-family switching is conditional on having two independently visible
devices. A single controller cannot validate that row of the matrix.
