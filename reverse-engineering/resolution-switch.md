# Changing the resolution in the game

> **Documentation standard.** This document follows
> [`documentation-standard.md`](../docs/documentation-standard.md). Read it before
> editing this file, and check the result still meets it -- measured claims only,
> every site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: reference.** What the game does, from the click on a size in Options to the
first frame at the new size, what it rebuilds and what it keeps, and what KMRP adds
at each step. Written on 2026-10-09 with two faults found that day by the
maintainer: the area map kept the first size's surfaces, and two buttons of the
Character screen came back wider after a change there and back.

**How this was read.** The functions were decompiled from the Ghidra archive of the
GOG executable (`Lane-reference`, kept off the repository); the names are the
archive's. Addresses are the unmodified 1.03 executable's, which the GOG build
shares. Byte-level statements were read with a disassembler from
`build-inputs/swkotornopatch.exe`. **Nothing in sections 1 to 4 was traced in a
running game for this document**; where a statement was measured in the game, on
whatever day, it says so. What KMRP does is read from its source.

## 1. The path

```text
Options, Graphics, "Resolution"
  CSWGuiOptionsGraphics::OnResolution        0x006E1660   makes the dialog, centres it, adds it as a modal panel
    CSWGuiOptionsResolution (constructor)    0x006E0710   fills its list from EnumDisplaySettingsA
  a row is chosen
  CSWGuiOptionsResolution::OnResolutionChosen 0x006DF690
    EnumDisplaySettingsA(mode number)                     the refresh rate of that mode is kept
    CClientExoApp::SetVideoMode              0x005ED8D0
      CClientExoAppInternal::SetVideoMode    0x005F1830   section 2
    writes Width, Height, RefreshRate to .\swkotor.ini    only if SetVideoMode returned 1
    CSWGuiManager::PopModalPanel                          the dialog goes
    CSWGuiManager::ReloadToolTipPanel        0x0040A350
```

The list's rows carry the display's mode number (`custom_value`), not a size: the
chosen row is handed to `EnumDisplaySettingsA` again. That is why KMRP changes the
list by answering the game's `EnumDisplaySettingsA` (import slot `0x0073D3E4`,
`EnumModesOnce` in `K1RuntimeResolution.cpp`) and never by editing rows.

## 2. `CClientExoAppInternal::SetVideoMode` (`0x005F1830`)

In order:

| Step | What | Note |
| --- | --- | --- |
| 1 | Returns 1 at once if the mode number is the one in force (`this+0x1A0`) | choosing the current row does nothing |
| 2 | `EnumDisplaySettingsA(mode)`; returns 0 if it fails | |
| 3 | The mode's size and depth go to the globals `screenWidth` (`0x0078D1D4`), `screenHeight` (`0x0078D1D8`), `bitsPerPixel` | |
| 4 | Fullscreen or windowed: kept as it is, unless the caller forces one. Windowed is refused (made fullscreen) when the desktop is smaller than 640x480 or not larger than the new size | |
| 5 | `ReInitAurora(width, height, depth, fullscreen, 1)` (`0x00403800`) | the renderer is torn down and made again: window, OpenGL context, input. `CAurInternal::GetValidMode` (`0x0044D6E0`) picks the display mode: the largest one that fits inside the size asked for |
| 6 | `CSWGuiManager::SetSize(width, height)` (`0x0040BE70`) | section 3 |
| 7 | The main menu, if it is on screen: `CSWGuiMainMenu::LoadFromLayout` (`0x0067ACE0`) | its layout is loaded again |
| 8 | The loading screen, if there is one: destroyed and constructed again (`CSWGuiLoadScreen`, `0x0067A710`) | |
| 9 | In a game: `CGuiInGame::ResetInterfaceForSize` (`0x0062F5F0`) | section 4 |

KMRP's detour on this function is `KmrpModeSwitchK1`, and the size the game has
taken is noticed on the next GUI frame (`KmrpResolutionObservedK1`, from
`KmrpCoreGuiWorkK1` at `0x0040CE76`): section 5.

## 3. `CSWGuiManager::SetSize` (`0x0040BE70`)

Only if the size differs from the manager's (`viewport_width` at `+0x6C`,
`viewport_height` at `+0x6E`, both shorts):

1. stores the two;
2. `UpdateAllFonts` (`0x0040B420`): `ResetFont` on every panel in the manager's
   list that has one, on the tooltip, on the main interface, and on eight panels the
   in-game GUI holds from `in_game_equip` on (the tab screens);
3. destroys the object at `manager+0x7C` if there is one and calls
   `DetermineNeedToDraw`.

It lays nothing out. The game's own sizes all used one 640x480 layout, drawn in the
middle of the screen, so nothing needed to move.

## 4. `CGuiInGame::ResetInterfaceForSize` (`0x0062F5F0`)

This is everything the game itself does to the in-game interface:

| Object | What happens |
| --- | --- |
| `main_interface` (the HUD, `CSWGuiMainInterface`, 0xC8CC bytes) | destroyed and constructed again |
| `dialog_cinematic` (`CSWGuiDialogCinematic`) | destroyed and constructed again |
| `message_box` (`CSWGuiMessageBox`) | destroyed and constructed again |
| the four debug menus, `container`, `skill_info_box`, `tutorial_box` | `CSWGuiPanel::CenterPanel` |
| **every other panel**: inventory, equipment, character, abilities, journal, messages, map, options, the store, the workbench, party selection | **nothing** |

So the HUD is made again for the new size, its minimap with it, and the tab screens
live on as they were made when the game was loaded. On a game with one layout that
was enough. With a layout per size it is not, and that is the gap KMRP fills.

## 5. What KMRP does on a change

Read from `K1RuntimeResolution.cpp`, `K1RuntimeEngine.cpp`, `K1RuntimeAssets.cpp` and
`K1RuntimeLayout.cpp`.

| When | What | Where |
| --- | --- | --- |
| The dialog is filled | repeated rows of the display's modes are hidden | `EnumModesOnce` |
| The game asks whether a size is valid | yes if KMRP has a layout for it and the display reports a mode of it | `KmrpAllowRuntimeResolutionK1` |
| `SetVideoMode` runs | the recipe's per-size operands are written for the new size (section 6) and that size's interface files are unpacked to the cache, fonts included | `KmrpModeSwitchK1`; `FieldValue`; `K1RuntimeAssets.cpp` |
| The next GUI frame | every live panel is laid out for the new size: section 5a | `KmrpRuntimeLayoutDimensions` |

### 5a. Laying live panels out again

KMRP knows every panel that loaded a layout (`KmrpPanelLayoutStartK1`), and each of
its controls by tag (`KmrpPanelControlK1`), with the rectangle the layout file gave
it. On a change, for every panel of the manager:

1. the panel's own rectangle is the new file's, centred where the old one was
   centred;
2. each top-level control gets the new file's rectangle, plus what the control's
   rectangle differed from the old file by (`moved`), scaled by the height rule.
   That keeps what the game's own code adds after loading: the Options screen moves
   its five buttons down, and without this they stood 20 px high at 1080 lines
   (measured 2026-10-04);
3. a list's `PADDING` and scrollbar width are the new file's, and its rows are placed
   again ([listbox-geometry.md](listbox-geometry.md));
4. since 2026-10-09, the area map's surfaces: section 7.

Step 2 cannot tell the game's own additions from anyone else's. Section 8 is a case
of that.

Since 2026-10-09 a panel loaded at the size being laid out for is left alone. The
game makes the HUD, the dialogue and the message box again on a change (section 4),
from the new size's files and with its own additions already worked out for the new
size; laid out again here, those additions were scaled a second time. The Mac found
it on 2026-10-08 in the code ported from this file (the conversation's message
label 2108 wide where the game had made it 1824, and black over most of the
picture; `docs/windows-changes-from-macos.md`, item 22). A panel records the size
in force when its layout starts loading and the size it was last laid out for.
**Not seen on Windows, before or after.**

## 6. The per-size operands, and when each is read

KMRP's recipe writes these immediates again on every change
(`resolution_fields` in `tools/build_native_engine.py`). An operand read each time
something is drawn or measured takes effect at once. One read only when an object is
constructed leaves every object made before the change with the old size's value.
The function is the one holding the operand; the last column is read from that.

| Operand | Value | In | Read |
| --- | --- | --- | --- |
| `0x00403D6C`, `0x00403D78` | width, height | `ChangeResolutionForMovie` | each movie |
| `0x0040AA65`, `0x0040AA85` | width, height | `CSWGuiPanel::GetExtentAccountingForPanelOffset` | each call |
| `0x0040B6C7`, `0x0040B6DA` | -width, -height | `CSWGuiPanel::HitCheckMouse` | each call |
| `0x0040BA6C`, `0x0040BA83` | -width, -height | `CSWGuiPanel::GetLocalMouseCoords` | each call |
| `0x005F5B3B`, `0x005F5B43` | width, height | `ReadAndSetVideoMode` | at start |
| `0x0062540D`, `0x006256DC`, `0x006256E3`, `0x006256F6`, `0x00625759` | 64, 800, 450, 800, 450 scaled | `CSWGuiMessageBox::FixMessageLabel` | each message |
| `0x00626F95` | 64 scaled | `CSWGuiMessageBox` constructor | **construction.** The in-game box is constructed again by the game (section 4) |
| `0x006928B3`, `0x006928C3` | width, height | `CSWGuiInGameMap::Draw` | each frame |
| `0x0069405B`, `0x006940DC` | 32 and 16, marker rule | `CSWGuiMapHider` constructor | **construction.** Set again by KMRP since 2026-10-09 (section 7) |
| `0x0069471A` to `0x00694AD4`, twelve operands | marker sizes and their centring | `CSWGuiMapHider::Draw` | each frame |
| `0x0069505C`, `0x00695064`, `0x00695082`, `0x0069508A` | canvas width, half height, half width, half height | `CSWGuiInGameMap` constructor | **construction.** The fault of section 7 |
| `0x006AB8EF` | 50 scaled | `CSWGuiInGameSkillEntry::SetExtent` | each layout of a row |
| `0x006ACB20` | 50 scaled | `CSWGuiInGameSkillEntry::Initialize` | when a row is made |
| `0x006B4FA9` | 56 scaled | `CSWGuiInGameItemEntry::Initialize` | when a row is made |
| `0x006B527F`, `0x006B5332` | 56 and 19 scaled | `CSWGuiStoreItemEntry::SetExtent` | each layout of a row |
| `0x006B55E3` | 56 scaled | `CSWGuiStoreItemEntry::Initialize` | when a row is made |
| `0x006C265F` | 56 scaled | `CSWUpgradeItemEntry::SetExtent` | each layout of a row |
| `0x006C2A23` | 56 scaled | `CSWUpgradeItemEntry::Initialize` | when a row is made |
| `0x006CD8D9`, `0x006CDB79` | 50 scaled | `CSWGuiSkillFlowChart::AddPowerSet`, `AddFeatSet` | **when the chart is filled.** See below |
| `0x006DE012`, `0x006DE031`, `0x006DE0D3`, `0x006DE0D8` | 25, 2, 30, 30 scaled | `CSWGuiOptionsCheckbox::SetExtent` | each layout of a box |
| `0x0086F004`, `0x00871003`, `0x00871009`, `0x00871020` | the scale as a float; 21, 21, 37 scaled | KMRP's own appended code | each call |

Rows made by an `Initialize` are made when their list is filled, which the game does
each time the screen is opened, so they take the new size on the next opening. **Not
checked for each list.** The abilities' rows are the known exception: a skill's row
and a row of the powers' or the feats' chart are made once and kept, so they kept
the old size's height under the new size's icons. The Mac build found it and
repaired it on 2026-10-05; the repair is on Windows since 2026-10-09
(`KmrpListAddRowsK1`, a hook on `CSWGuiListBox::AddControls` at `0x0041C1D0`, which
gives each such row the height its constant has now: `0x006ACB20` for a skill,
`0x006CD8D9` for a chart's row). **Seen** on the skills' list after 3440x1440 to
1920x1080 and after 1920x1080 to 1680x1050; the two charts were not looked at.

## 7. The area map kept the first size's surfaces

**Seen** by the maintainer on 2026-10-09: started at 3440x1440, changed to
1920x1080, opened the map. The frame, the title and the buttons were 1920x1080's;
the map's picture and its grid were far larger and ran out of the frame to the right
and below.

**Cause**, read from `CSWGuiInGameMap`'s constructor (`0x00694D50`). After its layout
has loaded it sizes two things no layout file holds:

```asm
0069504D  lea  ecx, [esi+0x1080]            ; the picture's canvas, a CSWGuiImage
00695058  mov  dword ptr [esp+0x1C], 0x200  ; width 512   (operand 0x0069505C)
00695060  mov  dword ptr [esp+0x20], 0x100  ; height 256  (operand 0x00695064)
00695068  call dword ptr [edx+4]            ; SetExtent {0, 0, 512, 256}
...
0069507E  mov  dword ptr [esp+0x1C], 0x1B8  ; width 440   (operand 0x00695082)
00695086  mov  dword ptr [esp+0x20], 0x100  ; height 256  (operand 0x0069508A)
0069508E  call dword ptr [edx+4]            ; SetExtent on the CSWGuiMapHider, at this+0xE38
00695094  call 0x0040B9A0                   ; CSWGuiPanel::AddControl
```

The panel is constructed once, with the game, and is not among what
`ResetInterfaceForSize` makes again. KMRP wrote the four operands for the new size,
but nothing ran them: the canvas stayed 2001x720 and the overlay 1720x720, drawn
through a 960x540 `LBL_Map`.

**Repair** (`KmrpRuntimeLayoutDimensions`, `K1RuntimeLayout.cpp`): for a live panel
whose vtable is `CSWGuiInGameMap`'s (`0x00754830`), the canvas and the overlay get
the new size's rectangles by the recipe's own rules ([map-scaling.md](map-scaling.md),
section 2), and the overlay's two pictures (the player's arrow at `+0x60`, the
selection circle at `+0x64`, made by `CSWGuiMapHider`'s constructor at the marker
rule's 32 and 16) their sizes.

The HUD constructs a second `CSWGuiInGameMap` for its minimap, which the recipe's
wrapper puts back to the game's own 512x256 and 440x256
([map-scaling.md](map-scaling.md), section 5). It is recognised by exactly those
numbers and its two surfaces are left alone; the game makes the HUD again on a
change in any case.

**Not seen in the game with the repair.** Built on 2026-10-09; the maintainer's test
is outstanding. The two pictures' sizes were not seen wrong before it: they are set
because the constructor sets them.

## 8. Two buttons wider after a change there and back

**Seen** by the maintainer on 2026-10-09: after 3440x1440 to 1920x1080 and back,
"some buttons were slightly stretched horizontally".

**Cause, read from the source, not traced in the game.** The controller patch grows
the Character screen's Level Up and Auto Level Up buttons to hold their badges
(`ShowK1BackedBadge`, `vendor/K1XboxControls.cpp`) and remembers the rectangle the
screen gave them. It left them grown while another screen was in front. A change of
size happens with the Options screen in front, so step 2 of section 5a met the grown
rectangles, took the growth for something the game had added, and laid the buttons
out at the new size with the growth scaled. The controller patch then found a
rectangle that was not the one it had grown, took it for the screen's own, and grew
it again if the caption needed more. Back at the first size the growth, measured at
the other size and scaled up by the height rule, was more than the caption needs.

**Repair**, in the controller patch (`RestoreK1GrownButtons`): a grown button is its
screen's own size again whenever another screen is in front, each frame, so nothing
that lays the interface out meets a grown one. The two patches still know nothing of
each other. **Not seen in the game with the repair**, and the maintainer has not yet
said which buttons they were: if they were not these two, this section is wrong.

## 8a. Three more, found on 2026-10-09 with the controller patch

All three **seen** in a scratch copy of the game, 1920x1080 to 1680x1050 from the
in-game Graphics Options with the pad, before and after their repairs.

| Seen | Cause | Repair |
| --- | --- | --- |
| On Abilities (opened before the change) the first party portrait kept the old size's place and stood over the second | The controller patch reads where `BTN_CHANGE1` is in its layout file by loading that tag once more into a label of its own, not filed with the panel, and frees the label (`PlaceCueByReferenceK1`, `K1NativeJoystick.cpp`). KMRP's record of the tag (`KmrpPanelControlK1`, the hook on `CSWGuiPanel::InitControl`) became that label's and went with it when it was freed, so step 2 of section 5a had no control for the tag. The four party screens have this cue: Abilities, Character, Equip, Inventory | `KmrpPanelControlK1` now takes `InitControl`'s last argument (`esp+12`): a second control from a tag whose own control is still the panel's, loaded with that argument 0, leaves the record alone. The Mac found the same on 2026-10-07 in the code ported from this file |
| On the same screen Close's caption and its B stood below and right of the button (after 3440x1440 to 1920x1080: off the screen, an empty button) | The controller patch moves a caption to its button's middle line and remembers the rectangle it had (`textWas`, `vendor/K1XboxControls.cpp`), to give it back when the badge goes. It gave it back after the button had been laid out for the new size, which gives the caption its rectangle too | The saved rectangle is kept with the button's rectangle it was saved under (`textFor`) and dropped once the button's is another (`DropK1StaleCaptionRect`) |
| No badge on any screen after a change, until the pad's next press | The window is made again and the pointer put into it, at the same place counted in other pixels: steps shorter than the 300 px that tell a placed pointer from a hand (`MouseIsBeingUsedK1`), so the game was taken to be on the mouse | For a second and a half after the game's `screenWidth` or `screenHeight` (`0x0078D1D4`, `0x0078D1D8`) changes, no pointer movement counts as mouse use |

## 9. Start-up, for comparison

The same pieces at the game's start, where there is no change but a first size:

| Function | What |
| --- | --- |
| `CClientExoAppInternal::ReadVideoModeSettings` (`0x005F0CE0`) | reads `Width` and `Height` from `.\swkotor.ini`, asks `IsValidResolution` (`0x005F0C60`: the game's own list is 800x600, 1024x768, 1280x960, 1280x1024, 1600x1200), and takes 800x600 if the answer is no (`0x005F0FB2`) |
| `CClientExoAppInternal::ReadAndSetVideoMode` (`0x005F5AB0`) | looks the size up among the display's modes (`SetDisplayDevMode`, `0x0070D220`: same size and depth, and the refresh rate asked for or 0 or 1); if there is none, the mode nearest 800x600 (`0x005F5B84`, `GetNearestVideoMode`, `0x0070D0A0`) |

KMRP answers `IsValidResolution` itself and writes both 800x600s as the desktop's
size when its module loads (`KmrpStartAtDisplaySize`), so a display without the
file's size starts at its own (CHANGELOG, 2026-10-07; measured that day).

Movies have a pair of their own: `ChangeResolutionForMovie` (`0x00403CF0`) calls
`ReInitAurora(640, 480, 32, fullscreen, 0)` unless the game is at that size, and
`RestoreResolutionFromMovie` (`0x00403DE0`) calls it again with the size it saved.
KMRP writes the running size into the first, so nothing changes
([movies.md](movies.md)).

## 10. Open

| | |
| --- | --- |
| The map after a change, with the repair | not seen |
| The Character screen's buttons after a change and back, with the repair | not seen; which buttons were reported is not established |
| The powers' and the feats' charts after a change | the Mac's repair is on Windows since 2026-10-09 and seen on the skills' list; the two charts not looked at |
| Lists filled before a change and still open after it | not checked list by list |
| A change while a tab screen other than Options is in front | cannot be reached from the game's own menus; not tried |
