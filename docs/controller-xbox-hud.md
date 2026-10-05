# The Xbox-style HUD

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Every claim says how
> it was established; anything not run is listed under "Tested and not tested".

**Kind: reference.** An option of the standalone controller patch
([`controller-standalone.md`](controller-standalone.md)): the in-game HUD laid out
and behaving as the original Xbox version's. Built on 2026-10-05 with the maintainer
comparing each build against frames of the Xbox game; this is the layout he
approved that day. Later the same day it stopped being a set of replaced layout
files: the module lays the live HUD out itself, for any screen size, and gives the
game's own HUD back while the mouse or keyboard is in use. KMRP's own patch does
not have it.

## What the player sees

| Piece | Where | How it behaves |
| --- | --- | --- |
| Action menu | bottom left | a box with the selected action's name and a row of six slots; the selected slot is large with a yellow frame and yellow arrows |
| Target bar | top left, fixed | the target's name over its health bar, in a blue frame, red for a hostile target |
| Party | bottom right | the leader large, the others small above, each with a curved vitality bar on the left and Force bar on the right that empty from the top; the group is 85% of the Xbox layout's size (the maintainer found it too big) |
| Minimap | top right | the size the game's own HUD has it (the maintainer's direction; the Xbox layout's is a little smaller) |
| Speech box | under the target bar | a line of speech or a notice: it starts a little left of the target bar's frame, right under it, and is one and a half times as wide as the bar's frame |
| Action queue | bottom, right of the action menu | with the pad's Y (take the last action off) beside it |
| Combat mode | a strip across the top | "COMBAT MODE engaged. (B) to disengage." in red, the pad's B drawn in the line, a thin blue line under the strip; the target bar and minimap stand lower while it is there |

The PC HUD's row of eight menu buttons and its pause, solo and stealth toggles are
not shown. A pad does without most of them: Start opens the menus, RT pauses, Back
toggles solo mode (`tools/build_controller_layout.py`, `LAYOUT`). Stealth has no
pad button; the keyboard's key still works.

### The six slots

| Place | Without a target | With a target |
| --- | --- | --- |
| 1 | "No Action" | the target's default action: "Attack", "Open", "Dialog" |
| 2 | the character's skills and friendly powers | the target's other actions of that kind (feats, a door's lock); the skills when it has none |
| 3 | a dim frame | the target's Force powers |
| 4 | mines | grenades while the target offers any, mines otherwise |
| 5 | medical items | the same |
| 6 | other items | the same |

Place 1 is selected whenever no other slot is. A there does the default action. The
D-pad moves along the row as it is on screen; left from place 2, or B, returns to
place 1. Up and down walk a slot's actions. B with place 1 selected disengages from
combat; X does too.

**It follows the device.** While the pad is what the player is using, the HUD is
the Xbox one. The moment the mouse or keyboard is used it is the game's own HUD
again, exactly as it was, and the pad brings the Xbox one back. Nothing is
remembered between the two: before every frame the HUD is drawn the module asks
which device was used last, so after a conversation, a movie or a loaded save the
HUD is the one for the device in the player's hands.

Every texture is the game's own, already in `swpc_tex_gui.erf` of the PC release.
The patch carries no Xbox art, no font and no layout file for this: only one small
button glyph per controller family for the combat line.

## How it is switched on

| Manager | How |
| --- | --- |
| A KOTOR Patch Manager with patch options | the patch's **Xbox-style HUD** option (`xbox-hud`, off by default) |
| KOTOR Patch Manager 0.7.1, which has no options | `kmrp-controller.ini` beside the game: `Style=Xbox` under `[Hud]` |

The module reads the manager's recorded option first (`configs\kmrp-controller.ini`,
`[Patch Options]`, `xbox-hud`) and the settings file only when there is none, once,
when the game starts. With the option off both hooks return at once.

## Why it is built this way

### Laid out at run time

Until the evening of 2026-10-05 `tools/build_xbox_hud.py` rewrote a copy of each PC
HUD layout file and the patch loaded the copy in the original's place. That tied the
HUD to the four screen sizes those files exist for, replaced whatever HUD layout
another mod had installed, and could not be undone while the game ran. Now the tool
writes a table, `src/controller-native/K1XboxHudLayout.inc` (101 controls: where
each goes, how it is anchored, what art it wears), and `K1XboxHud.cpp` applies it to
the live controls:

- **A control is found by its place in the HUD object, not by the layout file.**
  The executable builds every HUD control as a member of `CSWGuiMainInterface` at a
  fixed offset. A control's ID, its index in the panel's array, comes from the file,
  and differs between the game's own four files (compared: `mipc28x6`, `mipc210x7`,
  `mipc212x9`, `mipc216x12`). The offsets were read from the running CD 1.03 game:
  each tag's ID in `mipc210x7.gui` looked up in the panel's array (80 controls),
  and the 22 the panel does not list (the target's menu, the combat-effect arrows)
  found in the object's memory by class and ID.
- **Kept, applied, put back.** At the first sight of a HUD object the module keeps
  each control's rectangle, art and font as the layout file and the engine made
  them (`Keep`). `ApplyXbox` moves and dresses them for the screen the game is
  drawing (the GUI manager's viewport), with the engine's own setters:
  `SetExtent`, `CSWGuiBorderParams::SetFillImage`, and
  `CSWGuiTextParams::SetBaseFont` (`0x00415DD0`), which the layout loader uses.
  `RestorePc` puts everything back, and with it what the hook changes each frame
  that the engine does not set again by itself: the frames the engine last gave the
  target's slots, the visibility of parked slots and hidden arrows, the action
  description, and (through `UpdateNameLabel`) the stack under the target's name.
- **Three things the HUD worked out from its layout when it was built** are set and
  put back with the controls: the bottom edge the action description grows up from
  (`+0xA454`, read by `SetActionDescription`), the rectangle the map is drawn in
  (`+0x6080`, `LBL_MAPVIEW`'s in the file), and the target menu's origin, size and
  clamp. The combat-effect arrows on a portrait are kept by the engine relative to
  the portrait's corner (in the running game `LBL_CMBTEFCTINC1` was at (2, 23)
  where the file has (8, 727) and `LBL_CHAR1` (6, 704)), so the table gives them so.
- **The speech box is a panel of its own**, `CSWGuiBarkBubble`, held by
  `CGuiInGame` at `+0x4C`. Its `Draw` (`0x006A9CE0`, decompiled) puts it back,
  before every draw, on the rectangle its constructor copied from its layout file to
  `+0x1A4`, so that rectangle is what `ApplyXbox` sets and `RestorePc` puts back.
  The numbers are from a frame of the Xbox game the maintainer sent: the box from
  49 to 509 across with its top at 82, the target bar from 53 to 307 and down to 73
  (640x480 units). The Xbox width, 460, was tried and the maintainer asked for one
  and a half times the bar's frame instead, 381. Seen at 1024x768: the box from 20
  to 627 px, under a bar whose frame is 27 to 432; with the mouse, the game's own place again.
- **A new HUD object is told to the module** from `CSWGuiPanel::ReleaseGff`, which
  every panel calls as it is built and as it is destroyed
  (`NativePanelReleaseGffK1`): a HUD at an address seen before is still a new HUD.

### The layout

**The PC data holds the Xbox HUD's layout files, and the PC game cannot load them.**
`maininterface.gui` (640x480) and `mi8x6.gui` (800x600) are in the PC data with 102
controls each. The PC executable's HUD class, `CSWGuiMainInterface`, binds none of
their tags (`LBL_ICON1`, `LBH_ARROW1`, `LBH_BORDER1B`...): its constructor
(`0x0068C100`, decompiled) asks for `BTN_ACTION%d`, `BTN_TARGET%d`, `LBL_CHAR%d` and
so on, from `mipc28x6`, `mipc210x7`, `mipc212x9`, `mipc212x10` or `mipc216x12` (the
data has no `mipc212x10`). So the Xbox look is made from the PC HUD's own controls,
each placed and dressed as the Xbox file places and dresses its counterpart.
`tools/build_xbox_hud.py` does that to a PC layout.

**Scaled by height / 480.** The console drew `maininterface.gui`, the 640x480 file,
stretched over the whole picture. `mi8x6.gui` holds the same rectangles at the same
pixel sizes, only moved out to an 800x600 screen's edges, so its numbers are used with
lengths scaled by `height / 480`: left and top pieces from the top left, right-hand
pieces from the right edge, bottom pieces from the bottom edge. (The first build
scaled by `height / 600` and came out a fifth too small: the action box 28% of the
screen's width where the Xbox has 35%.) The game's fonts are not scaled; see Limits.

**Nearer the corners than the Xbox.** The Xbox layout keeps 45 units clear at every
edge, a television's margin. At the maintainer's direction each group is moved out
towards its own corner: 38 units sideways, and the bottom pieces 30 down
(`OUT_X`, `OUT_Y`). The queue's Y button sits two units off the queue's art, on its
middle line (measured on screen at 1024x768: both centres at row 710).

**Draw order decides which control carries the box.** The panel draws its controls
in the layout file's order. The description label comes after `LBL_MOULDING1` and
before `LBL_MOULDING3`, so the box is on `LBL_MOULDING1` (on `LBL_MOULDING3` it was
drawn over the text). The box's upper half reaches one screen pixel into its lower
half: laid edge to edge, as the file has them, the pair showed a light line across
the slots that the Xbox does not show.

### What needs code

`src/controller-native/K1XboxHud.cpp`, from two hooks.

**`KmrpXboxHudK1`, at the entry of `CSWGuiMainInterface::DrawMap` (`0x0068AB10`,
`ecx` = the HUD).** The HUD's `Draw` (`0x0068B4A0`) does its own updating and then
calls `DrawMap`, the panel's draw and the target menu's draw, so that entry is after
everything that moves or re-dresses a control and before anything is drawn. (The
target menu's `Draw` is after the panel is drawn, and the entry of `Draw` is before
the engine re-stacks the target's controls: both were tried.) It does this, every
frame:

- **Pins the target's menu.** The target's name, health bar and three slots are one
  object, `CSWGuiTargetActionMenu`, that the engine draws in its own viewport and
  moves to where the target is on screen (`PositionMenu`, `0x00686090`). The hook
  pins the viewport to the whole screen and sets the rectangle the engine clamps it
  into so that it cannot move; the menu's controls are laid out in screen
  coordinates. `SetNameLabel` (`0x00685AF0`) re-stacks the health bar and slots
  under the name from offsets `Initialize` (`0x0068BF50`) stored **as single
  bytes**; top left to bottom left is more than 255 pixels, so the stored offset has
  wrapped (measured: the layout's slot top 659, the live control's 130), and the
  hook places the target's slots from a personal slot, which nothing moves.
- **Places the seven PC slots in six places** and makes the selected one large
  (64 against 41, the arrow strip 14x56 so that the arrowheads touch the bracket).
  Two pairs share a place, feats with skills and grenades with mines; the one not
  shown is parked off the screen with its button invisible, so the focus cannot
  land on it. The target's slots get the Xbox frame (`lbl_mibox01`, `lbl_mibox02`)
  in place of the engine's `lbl_miscroll_h` and `lbl_miscroll_f`.
- **Makes the first place.** It is not an engine slot. On the PC the default action
  is what A does while no slot has the focus, so the first place stands for exactly
  that. Its name and icon come from a routine the PC executable still has and never
  calls, `CClientExoAppInternal::GetDefaultActions` (`0x00620620`): for the HUD's
  target it makes a one-entry list, "Dialog" with `i_dialog`, "Open", "Attack"; with
  no target it is "No Action" with `i_noaction` (dialog.tlk 32236). Where that
  action is also in the target's first list ("Attack" was the last of its list
  after two feats), the target's first slot is kept off it: the engine's up and
  down walk the whole list, and when they reach the default action the hook sends
  the choice on to the next entry in the same direction.
- **Puts the action's name in the box and the target's in the name bar.** The PC
  puts a target slot's action in the name bar (`UpdateNameLabel`, `0x00685CB0`);
  the hook calls it again with no slot named and gives the action's name to
  `SetActionDescription` (`0x00685560`).
- **Sizes the box to its text.** The Xbox file's 90 units are the box for three
  lines; with one line its top edge is at 364.6, not 326 (measured in the reference
  video). The engine keeps the description's bottom fixed and grows it upward, so
  the box's top is put 6 units above the description's.
- **Dresses the name bar and the party's bars.** The name's frame is
  `lbl_miindic01f`, or `lbl_miindic01e` for a hostile target (the engine's sign is
  the frame it gives the target's slots). The engine fills the vitality bars with a
  flat `redfill` (`greenfill` when poisoned) at every update; the hook puts
  `lbl_health` (`lbl_healthp`) back.
- **Draws the combat strip** before the panel while the engine shows the
  combat-mode message's label, and moves the name bar and the minimap (its border,
  its button, and the rectangle at `+0x6080` the map is drawn in) 14 units down.
  The Xbox strip is 57 units tall with those 26 lower; the maintainer asked for a
  shorter one, 44.
- **Keeps the minimap at the game's own size**: its frame takes the Xbox frame's top
  right corner and the size the PC layout gives it, and the button and the map's
  rectangle keep their places inside the frame.
- **Writes the combat line.** In place of the PC's "COMBAT MODE engaged. Press the
  Disengage button to cancel." (dialog.tlk 48208), the Xbox game's own line, which
  is still in dialog.tlk (42475, "COMBAT MODE engaged. <bbutton> to disengage."):
  the engine turns the token into the character `0x11`, which the PC fonts leave
  blank, so the hook splits the line there, puts the first half in the message
  label, the second in the message's background label, and the pad's B between
  them (the X cue's label with a B glyph, `kmrpb_cmbt`, made per controller
  family). Only while the pad is the device in use; with the mouse it is the game's
  line.

**`KmrpXboxHudBarsK1`, at the entry of `CSWGuiTargetActionMenu::Draw`
(`0x00685ED0`), right after the panel is drawn.** It draws the first place (with
two controls the Xbox layout has no use for, `LBL_MENUBG` and `BTN_MSG`), the dim
frame of the Force place when there is no target, and the party's bars. A bar on
the Xbox empties from the top and keeps its curve; the PC's progress bar gives its
fill the rectangle of the filled part and stretches the texture into it
(`CSWGuiProgressBar::SetExtent`, `0x00419300`), which squeezed the whole arc into
the lower part. So a bar that is neither full nor empty is emptied for the panel's
draw and its fill is drawn here whole, through a viewport that is the filled
part's rectangle (`AurGUISetupViewport`, as the engine clips the target menu).

With the mouse or keyboard in use the first hook puts the game's HUD back and
returns, and the second has nothing to draw.

Elsewhere: `MoveFocus` in `vendor/K1XboxControls.cpp` walks the row in its on-screen
order with the first place as "no slot"; `NativeActionBarK1` in
`K1NativeJoystick.cpp` makes B disengage when there is no slot to let go of; the X
cue label follows the combat message instead of the hidden Disengage button.
`RestorePc` puts back every fill of every control in the table, not only the ones
the table changes: the hooks draw with two parked controls, and one of them,
`LBL_MENUBG`, is the dark backing of the PC HUD's menu buttons (left in the last
art drawn with it, the buttons had no backing after a swap; the maintainer saw it).

**The party's bars are drawn by the module, whole.** Their art runs to the side
edge of its texture (`lbl_health2`, 16x64: the arc's outline is the first column),
and the engine samples a GUI texture with wrap, so the outer edge was mixed with
the texture's far side: the arc's outer outline came out half as thick and a faint
dark tick stood at the top and bottom of that edge. The first hook hides each bar
from the panel's draw; the second draws the empty bar, then its filling through
the clipping viewport, and right after each, while that texture is still the one
bound, tells OpenGL to clamp it at its edges (`ClampBoundTexture`:
`glTexParameteri`, `GL_CLAMP_TO_EDGE`). The setting belongs to the texture, so it
holds from the second frame on. Those four textures are used by nothing else.
Each piece's outer edge column is then drawn once more, one pixel further out (two
on a bar 30 px wide or more): at the arc's widest its outline is the texture's first
column alone, one texel where it is two elsewhere, which still read as the arc cut
off at the side. Only the middle of that column is repeated (rows 25 to 38 of the
64; the art has it from 20 to 43): over its whole length the added line stood out
at its ends. Measured on the leader's vitality bar at 1024x768: 20 px, where the
whole column was 35.

Five of the parked menu buttons hold the textures the hooks swap in and out before
every draw, so that changing a fill twice a frame never loads or frees one.

## Beside a widescreen patch: Scaled Kotor

Tried on 2026-10-05 with Scaled Kotor 1.3.1 (J and Vriff, a KOTOR Patch Manager
patch that unlocks resolutions and scales menus and HUD at run time; release
`ScaledKotor_1.3.1.zip` from the author's GitHub, SHA-256 `108D9C3E...`), its
textures in the scratch game's Override, both patches applied by KOTOR Patch
Manager 0.7.1's launcher to the CD 1.03 executable.

- **They could not be installed together**: "Hook conflicts detected: Address
  0x0040B8F0 used by multiple patches". Both hooked the entry of
  `CSWGuiPanel::StopLoadFromLayout`. The standalone patch now leaves that entry
  alone and reaches the same two moments from sites of its own
  (`tools/build_controller_kpatch.py`, `PANEL_LOADED_HOOK` and
  `PANEL_DESTROYED_HOOK`): the entry of `CRes::Release` (`0x00409B80`), acting only
  on the call `StopLoadFromLayout` makes on the panel's layout (return address
  `0x0040B901`, the panel in `esi`), and `0x0040CFAB` in the panel's destructor, the
  instruction before its own call of `StopLoadFromLayout`. 34 hooks in all. KMRP's
  own patch keeps the old site. Scaled Kotor's other 111 sites do not overlap this
  patch's (compared from both hook tables).
- **1920x1080 with both**: the Xbox HUD laid out as at the game's own sizes (action
  menu, target bar, party, speech box), the first real run at a size and shape the
  game does not have. With the mouse, Scaled Kotor's own scaled PC HUD.
- **The minimap needed one change.** Scaled Kotor puts `LBL_MAPBORDER` back on its
  PC place inside `DrawMap` (its hook at `0x0068ABB0`, after this patch's at the
  entry) and sets the map's size, but not where the map is drawn: the map was at
  the Xbox place and its frame in the opposite corner. So after the panel is drawn
  the frame is compared with where this patch put it; if something moved it, the
  engine's frame is not shown while the Xbox layout is up and the module draws one
  around the map as it is (`g_mapBorderForeign`). Seen at 1920x1080: the frame
  around the map, top right.

Not run with both: a fight, the combat strip, the swap back to the pad (the real
mouse was in use on the test PC), other sizes, Scaled Kotor's own options screen,
the menus' controller badges (the main menu showed none), a conversation.

## Measured against the Xbox game

One frame of the reference video (https://www.youtube.com/watch?v=b0X_7pRUkgo at
10:11), enlarged in the browser to 2.81 screenshot pixels per layout unit and
measured by colour, against our screenshot at 1024x768 (1.6 pixels per unit), in
units of the 640x480 layout. The video is compressed, so an edge is good to about
one unit. Measured on the build before the groups were moved towards the corners;
sizes and ratios are unchanged by that.

| Part | Xbox, width x height | Ours | Ratio w/h, Xbox | Ours |
| --- | --- | --- | ---: | ---: |
| Name bar, red frame | 258.1 x 37.0 | 253.8 x 36.2 | 6.98 | 7.00 |
| Action box, one line of text | 222.6 x 67.9 | 223.1 x 66.2 | 3.28 | 3.37 |
| Slot frame, not selected | 27.0 x 21.7 | 26.9 x 21.9 | 1.24 | 1.23 |
| Slot frame, selected | 42.6 x 35.5 | 64 in the layout, as the Xbox file | 1.20 | 1.20 |
| Slot pitch | 36.1 | 36 in the layout | | |
| Curve beside the portraits | 18.5 x 60.8 | 18.8 x 61.9 | 0.30 | 0.30 |
| Minimap, blue line | 72.9 x 72.6 | 73.1 x 72.5 | 1.00 | 1.01 |
| Capital letter height | 9.2 | 5.6 | | |

The selected slot and the pitch were measured at 58 and 31 on an earlier build that
had seven slots in the row; they are the Xbox file's numbers since, and were not
measured again.

## Limits

- **Text is 0.61 of the Xbox's size.** The Xbox drew `dialogfont16x16` on 480
  lines; the PC draws it at the same pixel size at every resolution. The standalone
  patch carries no font, by the maintainer's decision (KMRP's HD font belongs to
  KMRP, and this patch is for the game as it is). Enlarging the game's own font is
  blocked by something not understood: with any font on `LBL_NAME` or
  `LBL_ACTIONDESC` other than the two the HUD's layout already uses
  (`dialogfont10x10`, `dialogfont16x16`), the game crashes while loading a save
  (access violation at `0x61666564`, CD 1.03). Tried: the game's `dialogfont32x32`,
  `dialogfont12x16`, `fnt_d16x16b` and `fnt_galahad14`, and a copy of KMRP's HD
  atlas under a new name; on either label alone; and on the plain PC HUD with this
  option off, which crashes the same way.
- **Other screen sizes are not run.** The layout is computed from the screen the
  game is drawing and nothing in it depends on the shape; the regression test lays
  it out for ten screens from 800x600 to 3840x2160 and 5:4 to 21:9 (one row, nothing
  overlapping, all on screen). In the running game only the game's own four sizes
  were seen: the unchanged executable falls back to 800x600 for any other size
  (tried: 1280x720 in `swkotor.ini`), and KOTOR Patch Manager refuses an executable
  a widescreen patcher has changed on disk, so the first real test is beside a
  widescreen patch that is itself a KOTOR Patch Manager patch.
- **The patch's other screens are still the game's four sizes.** The standalone
  patch replaces 16 layout files (menus with badges, and the four HUD layouts with
  the two queue cues added); beside an interface mod those replace the mod's. The
  Xbox HUD itself no longer needs any of them: with another HUD layout loaded it
  lays out the same, without the Y and B cues.
- **Friendly Force powers and skills are not in the row during a fight** with a
  target that has feats: the second place holds the feats then, as on the Xbox.
- **The mouse on the slots** was not tried. The up arrow's button covers the middle
  of an icon, as the Xbox arrow strip does.
- **KMRP's own patch does not have it.** KMRP scales the whole interface and makes
  its HUD layouts per resolution.
- macOS: not built. The Mac has no standalone controller patch.

## Tested and not tested

Run in a scratch copy of the CD 1.03 game, the patch installed by KOTOR Patch
Manager 0.7.1's own launcher with `Style=Xbox`, driven by a virtual Xbox pad and a
synthetic mouse, judged from screenshots.

On the last build that replaced layout files (package SHA-256 `F4DB0879...`):

- **1024x768, a friendly creature targeted:** "Dialog" selected in the first place,
  skills in the second, a dim frame in the third, a mine, medical and items; the
  D-pad through every place and back to the first; the action's name in the box.
- **1024x768, a fight in the Sith base, paused and not:** "Attack" in the first
  place; the second walked between Critical Strike and Master Power Attack with up
  and down; Stasis and Frag Grenade selected, with the target's name staying in the
  name bar; A on Master Power Attack put it in the queue; the strip with the red
  line and the B in it; B with a slot selected returned to the first place, and B
  again, unpaused, emptied the queue; a wounded companion's bar as the lower part
  of the arc.
- **800x600, 1280x960, 1600x1200:** the friendly-creature save with a slot selected.

On the build that lays the HUD out at run time (package SHA-256 `DD9C8C9A...`,
the minimap change included; the swaps were seen on the build before it,
`AB92BDC8...`):

- **1024x768 and 800x600, the friendly-creature save loaded with the pad:** the
  Xbox HUD from the first frame, the same picture as the replaced-file build's.
- **The swap, 1024x768:** the mouse moved, and the HUD was the game's own, the same
  picture as with the option off (minimap top left, menu buttons, the target's name
  beside the target); a D-pad press, and the Xbox HUD was back with that slot
  selected.
- **The swap in the fight:** the same, both ways; the game's HUD showed the target's
  three slots in the engine's red frames under the name and the personal row as
  the option-off game shows them in that fight (compared with a run with the
  option off).
- **After a conversation** started and ended with the pad: the Xbox HUD.
- **`testing/regression/Test-ControllerKpatch.py`:** the table is what the tool
  writes; its 101 pieces are controls of the game's four HUD layouts, of the class
  the table says; the layout for ten screens (above); no HUD twin and no font in
  the bank; 33 hooks.

Not run: the GOG and Steam executables, fullscreen, a real controller and a real
mouse, any screen size but the game's four, the run-time build at 1280x960 and
1600x1200, another mod's HUD layout, the swap while the combat line is up, a movie,
an area change, a door, a container or a droid as the target (the maintainer's frames of
the Xbox game show "Open" with the lock in the second place, and "Dialog" with a
second action; the same code decides them), using a grenade or an item from the
row, a level-up, stealth and solo mode, the PlayStation, Switch and Steam Deck B
glyph in the combat line, any language but English, and a clean end of combat mode
after B (enemies were still attacking).
