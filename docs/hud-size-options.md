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
tried in the game.

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
  bottom centre cluster; the combat strip across the top keeps its size).
- **Each part grows about its corner of the screen**, or the middle of the bottom edge
  for the Disengage parts and the middle of the top edge for the attack buttons, so it
  never slides off. A part that would not fit stops growing at the screen's edge
  (`FittingSize`); at 50% or below nothing changes on any screen.
- **Link HUD Sizes**, on by default, moves one HUD's sliders together.
- **A preview** on the right: the chosen HUD in miniature, the part whose slider has the
  focus at full strength and the others at half, on a slate backdrop (`#3A424E`, a grey
  with a little of the GUI's blue), centred in the box's frame.

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
