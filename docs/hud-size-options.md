# HUD Size: the page, and the HUD placed at run time

Reference, 2026-10-18. Follows the [documentation standard](documentation-standard.md).
This describes the current source and the checks below. It does not describe a
released installer.

**Evidence boundary:** the source, mock tests (`testing/regression/Test-HudOptions.py`),
the package tests, and one session in the separate test game at 3440x1440 (CD 1.03 with
KOTOR Patch Manager 0.7.3). That session was driven by scripted mouse input while the
maintainer was away; they reviewed its screenshots ("This looks so good", "Looks great").
The live Xbox-style HUD at other sizes has **not** been seen: it needs a pad, and the
virtual pad driver is no longer installed on the test PC. Other screen sizes, the party
leader swap animation with resized portraits, and another mod's HUD layout were not
tried in the game. Two later changes the same day were checked in the test game at
1920x1080: the slider drag ([below](#dragging-a-slider-with-the-mouse), by reading the
slider's value from memory during scripted drags) and the preview's Disengage
([below](#the-previews-disengage), by looking at the page).

## What the player gets

Graphics Options has a **HUD Size** button above Text Size and Font. Its page:

- **Two HUDs, kept apart.** "Mouse & Keyboard HUD" or "Controller HUD" at the top right
  chooses which HUD's sliders show (the maintainer, 2026-10-18: "have a clear
  separation of controller ui and mouse and keyboard UI").
- **A slider for each part**, 25% to 100%, 1% steps. 50% is the HUD as it was; 25% is
  half of it; 100% is two and a half times it (the scale is a straight line on each side
  of 50%). The mouse and keyboard HUD's parts: menu buttons, minimap, action bar,
  portraits, attack buttons (the target's action buttons, shown in combat), Disengage
  button (the combat queue with the button in it). The controller HUD's: action menu,
  party switch, minimap, top left bar (the target's name and health), Disengage (its
  bottom centre cluster; the combat strip across the top keeps its size). Dragged with
  the mouse, the thumb stays under the pointer where it was taken and the end of the
  track is 100% ([Dragging a slider](#dragging-a-slider-with-the-mouse)).
- **Each part grows about its corner of the screen**, or the middle of the bottom edge
  for the Disengage parts and the middle of the top edge for the attack buttons, so it
  never slides off. A part that would not fit stops growing at the screen's edge
  (`FittingSize`); at 50% or below nothing changes on any screen.
- **Link HUD Sizes**, on by default, moves one HUD's sliders together.
- **A preview** on the right: the chosen HUD in miniature, the part whose slider has the
  focus at full strength and the others at half, on a slate backdrop (`#3A424E`, a grey
  with a little of the GUI's blue), centred in the box's frame. The mouse and keyboard
  HUD's Disengage is drawn as the game draws it in combat
  ([The preview's Disengage](#the-previews-disengage)).

Saved in `swkotor.ini`, `[KMRP HUD Size]` (`PcMenu`, `PcMinimap`, `PcActionBar`,
`PcPortraits`, `PcAttackButtons`, `PcDisengage`, `XboxActionMenu`, `XboxPartySwitch`,
`XboxMinimap`, `XboxTopLeftBar`, `XboxDisengage`, `LinkSizes`). Applied as soon as the
game is back.

## The mouse and keyboard HUD is placed by KMRP

Until 2026-10-18 the PC HUD stood where the layout file the game loaded put it:
KMRP's `mipc*.gui` for each screen size, or another widescreen mod's. Now KMRP's module
places it the way the Xbox-style HUD has been placed since 2026-10-05: from a table, for
the screen the game is drawing, whichever file was loaded (the maintainer's direction:
"draw it like the current controller GUI ... so it's compatible with any other
widescreen mods"). The file still gives the controls their art and fonts.

- **The table**, `src/controller-native/K1PcHudLayout.inc`, is written by
  `tools/build_pc_hud.py` from KMRP's 3440x1440 HUD as it ships: the hand-corrected
  `assets/override-3440x1440/mipc210x7.gui` with the packager's three changes, made by
  the packager's own functions (the target menu, the action description, the combat
  message's width). Compared with the file in the running game's cache: all 108
  rectangles the same. `Test-HudOptions.py` checks the table against the tool.
- **Placing** (`K1PcHudLayout.h`, shared with the preview): each piece keeps its distance
  from its part's corner at the screen's height over 1440; the target menu's pieces
  scale as the packager scaled them (half of the height over 720, never below a half);
  then each part is sized about its corner. At 3440x1440 and 50% every rectangle is the
  table's (tested).
- **Applying** (`K1PcHud.cpp`, from KMRP's GUI frame): only when the HUD object, the
  screen's size or a size changes. Each control is found by its tag in the panel, so
  nothing depends on where the executable keeps it. With the controls, the numbers the
  HUD worked out from its layout and goes on using are set too: the map's window
  (`+0x6080`), the description's bottom edge (`+0xA454`), the target menu's width, the
  gaps under its name and the rectangle it is kept inside, each portrait's home
  (`+0xE98` in its `CSWGuiMainInterfaceChar`), and the rectangle a target's circle may
  stand in (`LBL_ARROW_MARGIN`): the screen less the thinner of the HUD's top bands
  and the thinner of its bottom ones. (A rectangle below the deepest top part hid the
  circle across the whole upper half once the minimap was large: seen at 2.5 times.)
- **The target menu**: its buttons grow about their top centre and the name strip widens
  to their span when they are wider, so the name stays centred over the target's circle
  and the buttons under the name (seen at 2.5 times, a door and a Sith soldier).
- **Beside the Xbox-style HUD**: while that HUD has the screen (the pad in use), KMRP's
  module leaves the HUD alone (`KmrpXboxHudOwnsK1`, exported by the controller patch's
  module) and places it again once it is given back. The Xbox-style HUD now keeps the
  PC HUD anew each time it takes it, so it gives back the HUD as KMRP last placed it.

## The Xbox-style HUD's sizes

The controller patch works without KMRP, so its module reads `[KMRP HUD Size]` itself:
once, then again whenever `swkotor.ini` has been written (looked at twice a second at
most). In `ApplyXbox` each table piece is placed as before and then sized about its
part's corner; the minimap (the game's own HUD's map size, taken at 50% of KMRP's
minimap slider through `KmrpHudAppliedSizeK1`, exported by KMRP's module, then at this
HUD's), the Y cue, the speech box, the description's bottom edge and the lengths drawn
each frame (the selected slot, the action box, the name bar) follow their part.

## Minimap

The minimap's picture zooms with its window through KMRP's executable change
(`tools/build_minimap_zoom_fix.py`) only for a window of 121 pixels or more. Below that it
shows a smaller piece of the area at the game's own zoom. At 3440x1440 the smallest
window, at 25%, is 135 pixels; on smaller screens a small minimap crosses that line.
Widening the change to any size is not done.

## Dragging a slider with the mouse

Correction, 2026-10-18: until this change the HUD Size sliders, and the Text Size sliders
([in-game text options](ingame-text-options.md)), used the game's own drag. Dragged with
the mouse to the end of the track they stopped at 99%, one step short of 100%. The
maintainer found it while testing at 1920x1080 and 3440x1440. Keys and the pad were never
affected. The fix is in `src/controller-native/K1SliderGrip.h`, called from `MakeScreen`
in `K1HudOptions.cpp` and `K1TextOptions.cpp` (`KmrpSliderTakeMouseK1`).

**The build.** Measured on 2026-10-18 in the separate test game, whose `swkotor.exe` is
a copy with KOTOR Patch Manager installed, SHA-256
`01b808251b3ee85f86f4c893fd4ee1a0448f94d9316fe9b09bd8b222c2b4132f`. KPM does not patch
these routines; that is a caveat, because the measured copy is not a clean executable.
For this document the routines were read again from the clean CD 1.03 executable,
4,042,752 bytes, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886`, and disassembled with
Capstone; the instructions quoted below are from it. The clean GOG executable (SHA-256
`9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435`) has the same bytes at
every site in the table. Addresses are **VA**; for these clean inputs
**FILE = VA - 0x400000**. No appended section is involved, and nothing here writes to
the executable.

| Engine site | VA | FILE | Stack arguments | What it does |
| --- | --- | --- | --- | --- |
| CSWGuiSlider's table | 0x0073E9D0 | 0x0033E9D0 | | 40 entries (the 41st word is text, not code); entry 4 is 0x00419250, entry 6 is 0x004191D0 |
| Mouse move (entry 4) | 0x00419250 | 0x00019250 | two (`ret 8`), returns 1 | the drag, quoted below |
| Left button down (entry 6) | 0x004191D0 | 0x000191D0 | none (plain `ret`) | reads the pointer, stores the hit test's answer at slider +0x6C |
| Hit test | 0x00419060 | 0x00019060 | two (`ret 8`) | 1 on the thumb, 2 left of it (two return sites), 3 right of it |
| Layout (entry 1) | 0x00418F20 | 0x00018F20 | one (`ret 4`) | places the thumb, quoted below |
| SetValue | 0x00417EE0 | 0x00017EE0 | one; ends by jumping to the layout, whose `ret 4` returns | clamps to 0..maximum, stores +0x74 |
| Thumb border's rect | 0x00415B30 | 0x00015B30 | one (`ret 4`) | writes left, top, width, height |
| Pointer in a panel's coordinates | 0x0040BA20 | 0x0000BA20 | two (`ret 8`) | x and y through two pointers |
| Key and pad step | 0x0041ADF0 | 0x0001ADF0 | | value minus or plus one, then SetValue |
| GUI manager | [0x007A39F4] | | | +0x0C bit 0 set while the left button is down |

Slider fields used: +0x04 left, +0x08 top, +0x0C width, +0x10 height (a slider taller
than wide is vertical), +0x34 its panel, +0x6C the part pressed, +0x70 maximum, +0x74
value, +0x164 the thumb's border. The HUD Size and Text Size sliders have maximum 75
(25% to 100%).

The engine's drag, horizontal branch:

```text
00419250 mov eax,[0x7A39F4]       ; the GUI manager
0041925B test byte [eax+0x0C],1   ; left button not down: no change
00419261 cmp dword [esi+0x6C],1   ; the press was not on the thumb: no change
00419276 call 0x0040BA20          ; the pointer, in the panel's coordinates
00419281 cmp edi,ebp              ; height > width: the vertical branch
004192A1 mov ecx,[esp+0x10]       ; x
004192A5 sub ecx,[esi+0x04]       ; dx = x - left; below 0 gives 0
004192AA cmp ecx,ebp              ; dx > width gives the maximum
004192B1 imul eax,ecx             ; maximum * dx
004192B5 idiv ebp                 ; / width, rounded down (dx is not negative)
004192BA call 0x00417EE0          ; SetValue
004192CA ret 8
```

The layout, horizontal branch (ebx is the thumb's width from 0x00415B30, ecx the
maximum):

```text
00418FE4 cmp eax,ebx              ; eax = width
00418FF3 sub eax,ebx              ; width - thumb width
00418FF5 imul eax,[esi+0x74]      ; * value
00418FFA idiv ecx                 ; / maximum, rounded down
00418FFC add eax,[edi]            ; + left: the thumb's left edge
```

So the value is read from the pointer across the whole width, while the thumb travels
only the width less its own. The maximum needs dx at least the width: the pointer at or
past the track's right edge. Anywhere inside the track the value is at most
floor(75 x (width - 1) / width) = 74. With the thumb drawn at the end of the track, the
pointer on it gives one step short at any resolution, and only a drag carried past the
track reached 100%. Measured with memory reads during scripted drags at 1920x1080: value
74 of 75 after releasing on the track's end; 75 only when released past it.

**KMRP's sliders.** Each slider the two pages make (`Bind`, the engine's constructor
0x0041BAA0) gets a copy of the table made once by KMRP's module, with two entries
replaced. Only a slider whose table is the engine's 0x0073E9D0 is changed; anything else
is left alone. This is a pointer in the slider object, in memory: no hook site and no
byte of the executable.

| Entry | Engine | KMRP |
| --- | --- | --- |
| 4, mouse move | 0x00419250 | `MouseMove`: the engine's own for a vertical slider; for a horizontal one, the same conditions as the engine's (left button down, press on the thumb), then the value below; SetValue only when it changes; returns 1 |
| 6, left button down | 0x004191D0 | `MouseDown`: the engine's, then, if the press was on the thumb (+0x6C is 1), how far right of the thumb's left edge it landed |

The value, `DragValue`:

```text
travel = width - thumb width
at     = pointer x - grab offset - left       grab offset: from the press; half the
                                              thumb's width if the last recorded press
                                              was on another slider
value  = 0                                    at <= 0
       = maximum                              at >= travel
       = floor((2 x at x maximum + travel) / (2 x travel))   otherwise: the nearest step
```

The thumb's left edge is then where the engine's layout draws it for that value, and it
stays under the pointer where it was taken. When the thumb is drawn for a value v (left
edge at floor(travel x v / maximum)), `DragValue` of that edge gives v back whenever the
travel is at least twice the maximum.

**Checked.**

| Check | Result | Not established |
| --- | --- | --- |
| `Test-HudOptions.py`, run 2026-10-18 | for maxima 75, 100 and 10 and every travel from twice the maximum to 3000 px in steps of 7: 0 at the start and below it, the maximum at the end and past it, every step reached one at a time, and the value of every drawn thumb position given back. Passed | the engine calls; travels below twice the maximum |
| Memory reads in the test game at 1920x1080, after the fix | dragged to the end: 75, kept after release; dragged to the start: 0; the thumb stopped 6 px short of the end reads 99%, matching where it is drawn | other screen sizes after the fix; a vertical slider (none on these pages) |

`Test-TextOptions.py` cannot cover the swap: its harness has no engine table to copy, so
the call is compiled out under `KMRP_TEXT_OPTIONS_TEST`. The Text Size page shares the
header, so `DragValue` is covered by `Test-HudOptions.py` for both pages.

**Not changed.** The engine's routines, its table and every other slider in the game
(brightness, mouse sensitivity, the volumes) keep the engine's drag. Keys and the pad
still step by one through 0x0041ADF0, up to the maximum.

## The preview's Disengage

Correction, 2026-10-18: the preview drew the mouse and keyboard HUD's Disengage as a dark
panel (`dialog2`) with the word Disengage at its left, over the red ring. That is not
what the game shows.

**What the game shows.** Read from the clean CD 1.03 executable above (VA,
FILE = VA - 0x400000): ShowActionQueue, 0x006874C0 (FILE 0x002874C0), shows or hides
a list of HUD controls together, writing the same bit (value 2 at each control's +0x44)
from its argument. Among them are the three
combat backgrounds: `LBL_COMBATBG1` at HUD +0x675C (the bit at +0x67A0), `LBL_COMBATBG2`
at +0x689C (+0x68E0) and `LBL_COMBATBG3` at +0x69DC (+0x6A20), with the queue's
controls and `BTN_CLEARALL` in the same list. Their art, read with pykotor from the
vanilla `mipc210x7.gui` (`build-inputs/vanilla-gui`, extracted from a clean game by
`tools/build_controller_assets.py --extract`; 76,322 bytes, SHA-256
`80810b26e572823637fbefb70049df4408320955be8db7cfe282eb724052928b`):

| Control | Art | What it is | Index in `CONTROLS` |
| --- | --- | --- | --- |
| `LBL_COMBATBG2` | `lbl_mirightbotb` | the black backing | 1 |
| `LBL_COMBATBG3` | `lbl_mirightbot` | the frame round the queue and the Disengage box (blue in the PC game) | 2 |
| `LBL_COMBATBG1` | `lbl_micomb` | the red ring round the action under way | 3 |
| `BTN_CLEARALL` | none (`BORDER` and `HILIGHT` have no `FILL`) | the word Disengage (`TEXT`, `ALIGNMENT` 18, `dialogfont10x10`) | 85 |

The game draws them in that order, so the ring is over the frame and the frame over
the backing.

**What the preview draws now.** `tools/build_pc_hud.py` puts all three backgrounds in
the Disengage part's preview group (`PARTS`), so in `K1PcHudLayout.inc`
`LBL_COMBATBG2` and `LBL_COMBATBG3` carry the preview flag (8) as `LBL_COMBATBG1`
already did. `MakePreview` draws them in the table's order, which is the file's (black
backing, frame, ring), and `BTN_CLEARALL` as its word alone, no art, centred with
CSWGuiTextParams::SetAlignment, 0x00415F20 (FILE 0x00015F20, one stack argument,
`ret 4`), called with 18 on the label's text parameters (+0xE8). The label the preview
is made from (`LBL_GAMMA`) reads from the left otherwise. The queue slots and the two
clear buttons have no art and are not drawn. Seen in the HUD Size page at 1920x1080, at
63% and 100%.

**Proportions, checked on the maintainer's request (read only, nothing changed).** The
table against vanilla `mipc210x7.gui`, both read with pykotor:

| Control | Vanilla | Twice vanilla | KMRP's table | Width:height, vanilla / table |
| --- | --- | --- | --- | --- |
| `LBL_COMBATBG2`, `LBL_COMBATBG3` (the group) | 131x90 | 262x180 | 262x180 | 1.456 / 1.456 |
| `BTN_CLEARALL` | 125x35 | 250x70 | 250x70 | 3.571 / 3.571 |
| `LBL_COMBATBG1` (the red ring) | 131x77 | 262x154 | 262x144 | 1.701 / 1.819 |
| `BTN_CLEARONE` | 74x30 | 148x60 | 148x60 | 2.467 / 2.467 |
| `BTN_CLEARONE2` (no art) | 51x53 | 102x106 | 102x102 | 0.962 / 1.000 |

The group and the Disengage word keep vanilla's shape exactly. The red ring's art is 10
px shorter than twice vanilla, about 6.5%; `BTN_CLEARONE2` is square where vanilla is
4 px taller, but it is not drawn. The table's rows equal KMRP's
`assets/override-3440x1440/mipc210x7.gui` (SHA-256
`8c9ca408013ae66ce2e56e67078f26b1fa8a69e571cff4e25384205c58352147`), which it is built
from. The older static `assets/override-3440x1440/mipc28x6.gui` has a wider group,
563x216, but it does not place the HUD: the run-time table from `mipc210x7` does.

## Seen in the game, 2026-10-18

The test game at 3440x1440, scripted mouse input, screenshots reviewed by the
maintainer:

| | |
| --- | --- |
| Every part at 2 and at 2.5 times, and at half | placed about its corner; the minimap shows the same piece of the area |
| Minimap click at twice the size | opens the map (clicked where only the larger minimap reaches) |
| Combat at twice the size | the Disengage cluster, the attack buttons on an enemy, the combat message moved right of the minimap, the pause notice under the menu buttons |
| Target at 2.5 times | the circle with the name centred above it; the buttons centred under the name |
| Options button at half the size | opens Options |
| Default | every part back at 50%, the HUD as before |
| The page | both HUDs' previews at 50% and 100%, the slate backdrop, centred in its frame (77 and 78 pixels either side) |

Not seen: clicking the Disengage button at a new size (the fight ended before the click),
the live Xbox-style HUD at any size, other screen sizes, the leader swap animation.

Later the same day, at 1920x1080: the slider drag after its fix (memory reads, in
[Dragging a slider](#dragging-a-slider-with-the-mouse)) and the preview's new Disengage
at 63% and 100% ([The preview's Disengage](#the-previews-disengage)). The 3440x1440
previews in the table above show the earlier Disengage panel; the new one has not been
looked at on that screen.

## Verifying by hand

```powershell
python testing/regression/Test-HudOptions.py     # the table is current; sizes, placing, DragValue
python tools/build_pc_hud.py --check              # the table against the tool alone
python .github/scripts/check_links.py
```

- **The drag.** In the clean executable above, read the table at FILE `0x0033E9D0`
  (entry 4 is `0x00419250`, entry 6 is `0x004191D0`, the word after entry 39 is not an
  address), disassemble FILE `0x00019250..0x000192CD` and the layout's horizontal
  branch at FILE `0x00018FE4..0x00018FFE`, and check the arithmetic quoted above. In the
  game, drag a HUD Size slider's thumb to the end of its track without passing it and
  release: the caption reads 100%, and the slider's +0x74 reads 75.
- **The preview.** Read `mipc210x7.gui` with pykotor: `LBL_COMBATBG2`,
  `LBL_COMBATBG3`, `LBL_COMBATBG1` are controls 1 to 3 and `BTN_CLEARALL` has no `FILL`
  and `ALIGNMENT` 18. In `K1PcHudLayout.inc` all three backgrounds carry flag 8. Disassemble
  FILE `0x002874C0` onwards: the writes to `+0x67A0`, `+0x68E0` and `+0x6A20` sit in one
  run with the other controls'. On the page, choose the mouse and keyboard HUD and focus
  the Disengage slider: the black backing, the blue frame, the red ring and the word
  centred in its box.
