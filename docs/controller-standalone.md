# KOTOR 1 Native Controller Mod + Xbox HUD: the standalone controller patch

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Every claim says how
> it was established; anything not run is listed under "Tested and not tested".

**Kind: reference.** What `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch` is (it was `KMRP Controller.kpatch` until the evening of 2026-10-05, and the build this document measures still had that name), what it carries, what it
writes into a running game, and how it stands beside KMRP's own patch. Written
2026-10-05, the day it was built, when KMRP's patch still had controller support
of its own; since that evening this patch is KMRP's controller support, and
"What it is" below says how the two relate now. The controller itself
(the joystick device, the mapping, the prompts, rumble) is described in
[`controller-support.md`](controller-support.md) and
[`controller-native-path.md`](controller-native-path.md), and is the same code.

## What it is

One file for KOTOR Patch Manager, id `kmrp-controller`: KMRP's native controller
support, **with or without KMRP**. It needs no other patch, no installer and no
Override file. It carries none of KMRP's other work: no interface scaling, no
engine recipe, no memory, movie or map fixes. It runs on whatever interface is
loaded: the game's own, a widescreen patch's or KMRP's (section 5, "Beside a patch
that rescales the interface").

**Since the evening of 2026-10-05 it is one of the two patches KMRP ships**, by the
maintainer's decision that day (`CHANGELOG.md`, "KMRP and the controller patch are
two patches"). `KMRP.kpatch` (id `kmrp`) has no controller hook and no controller
option; KMRP's installer installs this patch beside it while Controller Support is
on in Advanced Settings, the default, and leaves it out otherwise
(`src/patcher/KpmEdition.cs`). Neither patch requires the other or lists the other
as a conflict (read from both manifests on 2026-10-08). Where both would want one
address each has a site of its own, because KOTOR Patch Manager allows one patch
per address:

| | This patch | KMRP |
| --- | --- | --- |
| GUI frame | `0x0040CE70` | `0x0040CE76` |
| Movie frame | `0x00404D96` | `0x00404D06` |
| Resource lookup | `0x00407235` | `0x00407230` |

Beside KMRP (it looks for `patches\kmrp.dll`) this patch leaves the cursor
confinement to KMRP and deletes its own copies of the game's layouts from its
temporary folder, so KMRP's scaled ones are used (`KmrpIsBesideK1` in
`K1NativeJoystick.cpp`, `LeaveLayoutsToKmrp` in `K1ControllerStandalone.cpp`).

*Until that evening* this section said KMRP's own patch contained controller
support as an option, that both held the same hook sites and so conflicted, and
that every `kmrp` patch since 2026-10-04 listed `kmrp-controller` as a conflict.
That was the state of the build measured below. The id had been the controller
add-on of the four-patch edition (2026-09-28 to 2026-10-04), which needed KMRP's
core; the retired ids of that edition are still this patch's conflicts.

## The build this describes

| | |
| --- | --- |
| Package | `dist\controller\KMRP Controller.kpatch`, 9,882,946 bytes, SHA-256 `F18F31220D64E5A3C7805D978DE420FE277591E19028F6B7B912E34BE5CADC47`, version 1.0.0 |
| Module inside it | `binaries/windows_x86.dll`, 9,855,488 bytes, SHA-256 `49701CB213D39581EBA375EE990FCC7863189A8BF1DC334D4D0C4858157D737B` |
| File bank inside the module | 9,633,675 bytes, SHA-256 `5A3110FC6A6DF116796FA7C43DFA4D3115234EC5D65C13E7F6E9452D65F3DE09`, 948 entries |
| Executables it declares | CD 1.03 `761F9466...C49E9886`, GOG `9C10E045...DEA91435`, Steam `34E6D971...A439F34C88` |
| Address convention | `VA`, image base `0x00400000`; `FILE = VA - 0x400000`. Every site is in the original image. |

**Later builds of the same day** are not measured in this document section by
section. The one committed last on 2026-10-05 is
`dist\controller\KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`, 10,027,574 bytes,
SHA-256 `A1D5A6D21B3B43FE16CFCF476C3A3BAD5F9D9F53C0F01E2A934CEE4959786F8F`, module
9,999,872 bytes, SHA-256 `B995A05FE1400431C0D580C9E05E4A2914EF832522B5FE595A06BE894D0B6452`,
34 hooks. What it adds to the build above (the Xbox-style HUD and its two hooks, the
panel hooks that let it run beside Scaled Kotor, prompts placed from the running
game, the tab strip's arrows, the HUD's drawn frames) is in
[`controller-xbox-hud.md`](controller-xbox-hud.md) and the changelog's entries of
that day.

The build is reproducible: two builds from the same sources on 2026-10-05 gave the
same package hash (an earlier state of the sources that day, `CE677F4C...`, twice).

## 1. What is in the package

| Entry | What |
| --- | --- |
| `manifest.toml` | id, name, description, conflicts, the three executables, one option (`debug-logs`, off by default); two since later that day, with `xbox-hud`, off by default until 2026-10-08 and on since |
| `kotor1.hooks.toml` | the 31 hooks below; 34 since later that day (section 2) |
| `binaries/windows_x86.dll` | the module, with the file bank as resource 101 |
| `licenses/` | KMRP's licence, `THIRD_PARTY_NOTICES.md`, SDL's licence |

The module is built by `src\controller-native\build_controller_standalone.cmd` with
`KMRP_CONTROLLER_STANDALONE`, from the controller's own sources
(`K1NativeJoystick.cpp`, `K1ControllerBackend.cpp`, `K1ControllerLayout.cpp`,
`K1Rumble.cpp`, `vendor\`) and `K1ControllerStandalone.cpp`, which supplies the
file bank, the module entry point and nothing else. `K1KpmApplier.cpp` and the
`K1Runtime*.cpp` files are not compiled in, so no engine change can be applied.

### The file bank

Made by `tools\build_controller_assets.py` from the game's own layout files
(`build-inputs\vanilla-gui`, written by its `--extract`) and the game's own font
metrics (`build-inputs\swpc_tex_gui.erf`).

| Count | What |
| ---: | --- |
| 17 | layout files: 16 of the game's, each changed by one of the steps below, and `kmrplayout.gui` |
| 640 | badge, cue and layout-glyph textures, `kmr?...`: one per controller family (Xbox `p`, PlayStation `s`, Switch `n`, Steam Deck `d`) |
| 280 | focused-state badge textures, `kmf?...` (section 3) |
| 10 | Controller Layout backdrop and edge art |
| 1 | `kmrp-sdl3.dll`, SDL 3.4.16, for non-Xbox pads |

The layout steps are the ones KMRP's resource build runs on its own sets
(`tools\prepare_universal_resources.py`), called here on the game's files:

| Step | Files |
| --- | --- |
| R3 party cue | `abilities`, `character`, `equip`, `inventory` |
| Swap-tabs cue | `abilities` |
| LT and RT cues | `top` |
| Controller Layout entry | `optgameplay` |
| Travelling A | `confirm`, `dialog` |
| X and Y beside the combat buttons | the eight `mipc*.gui` |
| Container column fit | `container`: ran, and changed nothing, so the file is not carried |

At run time the bank is unpacked to a `KMC*.tmp` folder in `%TEMP%` (about 166 MB) and
registered with the game's resource manager through a private alias, as
`K1RuntimeAssets.cpp` does for KMRP. A folder left by a game that is no longer
running is removed at the next start. Seen after a dozen starts of the scratch game:
one folder, the running game's.

## 2. Every site it hooks

All are KPM detours. 30 are the hooks marked `install = "controller"` in
`src\controller-native\kotor1.hooks.toml`; `KmrpPrepareResourcesK1` is the one site
taken from `kotor1-native-runtime.hooks.toml`. `tools\build_controller_kpatch.py
--verify-clean` compared all 31 `original_bytes` with the unmodified CD 1.03 and GOG
executables: equal at every site.

| VA | Original bytes | Function |
| --- | --- | --- |
| `0x00404D96` | `8B 46 48 8B 48 08` | `NativeMovieFrameK1` |
| `0x00407230` | `8B 44 24 04 53` | `KmrpPrepareResourcesK1` |
| `0x00409E60` | `8B 49 1C 85 C9` | `GuardPanelEchoK1` |
| `0x0040B8F0` | `56 8B F1 F6 46 44 02` | `NativePanelReleaseGffK1` |
| `0x0040C1F6` | `89 1E 89 7E 04` | `NativeNoteMouseK1` |
| `0x0040CE70` | `51 53 55 56 8B E9` | `NativeGuiFrameK1` |
| `0x005E24E0` | `6A FF 68 FD 48 72 00` | `NativeJoystickInitK1` |
| `0x005E271E` | `8B 84 24 E4 00 00 00` | `NativeNoteKeyboardK1` |
| `0x005E30F6` | `89 5C 24 2C 74 0F` | `NativeJoystickBufferK1` |
| `0x005F74B0` | `56 8B B1 50 03 00 00` | `NativeRumbleStopK1` |
| `0x005F7617` | `68 C0 27 09 00` | `NativeRumbleK1` |
| `0x005FB49F` | `3B A9 44 03 00 00` | `NativeRumblePlayK1` |
| `0x005FB98E` | `0F B6 45 0C 83 E8 00` | `NativeRumbleCutoffK1` |
| `0x006039CF` | `A1 E0 39 7A 00 8B 48 04` | `NativeCameraFrameK1` |
| `0x0060DE20` | `83 EC 1C 56 8B F1` | `NativeSaberContactK1` |
| `0x00617EB0` | `64 A1 00 00 00 00` | `NativeMeleeHitK1` |
| `0x0063C4F0` | `51 8B 49 68 85 C9` | `NativeParryK1` |
| `0x00646BA0` | `A1 FC 39 7A 00 56` | `NativeSaberPowerK1` |
| `0x00679940` | `D9 05 64 D7 73 00` | `NativeJoystickMovementK1` |
| `0x00679B71` | `E8 BA 15 E3 FF` | `NativeJoystickSkipNormalizeK1` |
| `0x00686BA0` | `53 56 57 8B F1` | `NativeActionBarK1` |
| `0x0068B170` | `6A FF 68 B0 F7 72 00` | `ClearActionBarControlsK1` |
| `0x006C2400` | `8B 54 24 08 85 D2` | `ResolveSoloModeConfirmK1` |
| `0x006D4440` | `53 8B 5C 24 08 56` | `NativeMuzzleFlashK1` |
| `0x006E0CF0` | `55 8B EC 83 E4 F8` | `ResolveResolutionConfirmK1` |
| `0x006F28C0` | `53 8B 5C 24 0C` | `GuardPowersConfirmK1` |
| `0x006F4680` | `53 8B 5C 24 0C` | `GuardFeatsConfirmK1` |
| `0x006F6A10` | `53 8B 5C 24 08` | `GuardSkillsConfirmK1` |
| `0x006F8880` | `53 8B 5C 24 08` | `GuardAbilitiesConfirmK1` |
| `0x006F8FF0` | `53 8B 5C 24 08` | `GuardPortraitConfirmK1` |
| `0x006FA220` | `53 8B 5C 24 08` | `GuardNameConfirmK1` |

**The table since later on 2026-10-05: 34 hooks** (`hooks()` in
`tools\build_controller_kpatch.py`, counted on 2026-10-08; the package in
`dist\controller` holds the same 34). Two rows above changed and four were added:

| VA | Original bytes | Function | Change |
| --- | --- | --- | --- |
| `0x00407235` | `8B 5C 24 10 55` | `KmrpPrepareResourcesK1` | in place of `0x00407230`, which is KMRP's |
| `0x00409B80` | `51 8B 0D E8 39 7A 00` | `NativePanelLoadedK1` | with the next row, in place of `NativePanelReleaseGffK1` at `0x0040B8F0`, which Scaled Kotor hooks |
| `0x0040CFAB` | `C7 46 5C 00 00 00 00` | `NativePanelDestroyedK1` | |
| `0x0068AB10` | `A1 FC 39 7A 00` | `KmrpXboxHudK1` | new: the Xbox-style HUD |
| `0x00685ED0` | `56 8B F1 F6 86 EC 1A 00 00 01` | `KmrpXboxHudBarsK1` | new: the Xbox-style HUD |

**Since 2026-10-09: 36 hooks.** Two more for the Xbox-style HUD's pause notice, on the
game's own layout of the pause box (`CSWGuiInGamePause::SetPauseReason`;
[`controller-xbox-hud.md`](controller-xbox-hud.md), "The pause notice"):

| VA | Original bytes | Function | Change |
| --- | --- | --- | --- |
| `0x006C00C0` | `6A FF 64 A1 00 00 00 00` | `KmrpXboxHudPauseReasonK1` | new: the routine's entry, `ecx` the pause panel |
| `0x006C02A4` | `8B 4C 24 48 5F` | `KmrpXboxHudPauseReasonDoneK1` | new: after the routine's last call, `esi` the pause panel |

Neither site is in KMRP's table or in High FPS Fixes' (`Test-InstallerPatch.ps1`
installs the three together). Not compared again with the other patches of KOTOR
Patch Manager 0.7.1.

Checked against every patch in KOTOR Patch Manager 0.7.1 for an overlapping site:
four overlaps, all with `expanded-keyboard-control` (`0x0040C1F6`, `0x005E271E`,
`0x00686BA0`, `0x0068B170`), which the manifest therefore lists as a conflict
beside `xbox-controls-k1` and KMRP's retired patches (not `kmrp`). Run again on
2026-10-06 with both of KMRP's patches (`tools\check_kpm_overlaps.py`): this patch
only neighbours KMRP, at two pairs of adjacent sites (the GUI frame's and the
resource lookup's, above), and overlaps it nowhere.

## 3. Badges on the game's small buttons

The rule, from the maintainer on 2026-10-05: a badge's width-to-height ratio is
never changed. A badge that draws as an oval or with an edge cut off is a defect.

### What the engine does

A badge is a texture on the button's fill, and the engine stretches the fill over
the area the border leaves. Read from the decompiled `CSWGuiBorder::Draw`
(`0x004168C0`) and `CSWGuiBorderParams::GetBorderDim` (`0x00414CD0`) in the
Ghidra archive, not from raw disassembly of this image:

- a border that holds a corner image starts its fill the corner's size in from the
  left and top, and shortens it by twice that; the corner's size is the border's
  `DIMENSION` when that is not zero;
- a border with no corner image fills the whole extent.

A button has two borders, `BORDER` and `HILIGHT`, and draws `HILIGHT` instead of
`BORDER` while it has focus.

### Measured in the scratch game, 1024x768

| Button | Border | Badge made for | Drew as |
| --- | --- | --- | --- |
| Options, `BTN_GAMEPLAY`, 240x40, focused | `HILIGHT`, corner art, `DIMENSION` 6 | the whole 240x40 | 28x20: an oval |
| the same | the same | 228x28, the inset area | 24x24 |
| Options, `BTN_BACK`, 142x28, focused | `HILIGHT`, corner art, `DIMENSION` 6 | 130x16, at the unfocused size | 20x16: top and bottom cut |
| the same | the same | 130x16, fitted to it | 14x14 (before the half-pixel margin; the final build was not re-measured focused) |
| the same, not focused | `BORDER`, no corner art, `DIMENSION` 0 | the whole 142x28 | 20x20 |
| Main menu, `BTN_NEWGAME`, 235x24, focused | `HILIGHT`, no corner art, `DIMENSION` 4 | the whole 235x24 | 17x16 |
| the same | the same | 227x16 | 14x20: stretched tall |

The last two rows are the test of the rule: the main menu's buttons have a
`DIMENSION` and no corner art, and their fill covers the whole button. Sizes are
bounding boxes of the badge's colour in a screenshot, so each is one or two pixels
under the drawn disc.

### What the generator and the module do

`tools\build_controller_prompt_textures.py`, with `fill_insets=True` (this patch
and, since later the same day, KMRP's own sets):

1. `fill_inset(border)` is the `DIMENSION` when the border names corner art, else 0.
2. The badge is designed on the whole control, then mapped onto the inset area, so
   it keeps its shape and its place.
3. It is kept whole inside that area, smaller if it must be, half a pixel short of
   the area's height and no nearer its left edge than a badge is to a button's
   (`BADGE_EDGE`). An area under 8 px tall gets an empty texture.
4. Where the two borders inset differently, the focused state gets its own
   texture, named `kmf...` beside `kmr...`.

`SetK1ControllerPromptFill` (`vendor\K1XboxControls.cpp`) makes the same comparison
on the live button, reading each border's `DIMENSION` (the first field of its
params) and its corner image pointer (the field after the params), and asks for the
`kmf` texture on the focused border when they differ. KMRP's sets carry the `kmf`
art since 2026-10-05 too; KMRP's patch installs no controller hook since that
evening, so the code runs only from this patch's module.

**Rejected the same day.** Fitting both states to the smaller of the two areas, so
a button's badge never changed size: the Map screen's two 13 px rows, whose focused
border leaves 1 px, lost their badges altogether. And taking the `DIMENSION` as the
inset whatever the corner art: the main menu row above.

**KMRP's own badges had the same stretch, smaller, and were fixed the same day.** A
720x90 button with a 6 px border fills 708x78, so a badge made for 720x90 was drawn
about 13% wider than tall. KMRP's resource build now passes `fill_insets` too, and
the blend table (version 5), `kmrp-guiblend.c` and `GuiBlend.cs` draw the same for a
size with no set: see `CHANGELOG.md`, 2026-10-05, and
[`macos-changes-from-windows.md`](macos-changes-from-windows.md), item 18.

## 4. The Controller Layout screen

The screen's design is 760 units wide. Built on the Gameplay screen's own 640x480
panel its captions were cut short (seen: "ally / Prev tab" for "Switch ally / Prev
tab"). It is laid out for 800x600 instead and its panel given that size: the size
of the game's own main-menu panel above 640x480. The game centres it on a larger
screen (seen at 1024x768).

In the game's font, which is wider than KMRP's, the two captions above the diagram
met ("Solo modeMap / Close menu"). `build_gui`'s `separate_top` moves them apart to
leave 12 design units between their words. Off for KMRP's sets, whose
`kmrplayout.gui` the Mac helper reproduces byte for byte.

## 5. Settings and options

| File | Who writes it | What |
| --- | --- | --- |
| `kmrp-controller.ini` beside the game | KMRP's installer, or else the module, once, if it is not there | the rumble settings, with the installer's defaults; both with `[Hud]` and `Style=Xbox` since 2026-10-08 (until then the module's copy had `Style=PC` and the installer's no `[Hud]`). A file already there is never touched |
| `configs\kmrp-controller.ini` | a KOTOR Patch Manager with patch options, or KMRP's installer | `[Patch Options]`: `debug-logs`, and from a manager `xbox-hud`; a missing `debug-logs` means off, a missing `xbox-hud` means the settings file decides. KMRP's installer writes `debug-logs` only, so that `Style` under `[Hud]` still decides the HUD (`ControllerPatchOptions`, `KpmEdition.cs`) |
| `kmrp-controller.log` beside the game | the module, only on failure | written if the file bank cannot be unpacked; the pad still works without its prompts |

### The Xbox-style HUD

Since later on 2026-10-05 the patch has one more option, `xbox-hud`, and one more
setting, `Style` under `[Hud]` in `kmrp-controller.ini`, both on by default since
2026-10-08 (off until then). They
add two hooks and a button glyph per controller family to the bank (and the patch
has 34 hooks since it left `StopLoadFromLayout`'s entry to other patches and took two
sites of its own for it; [`controller-xbox-hud.md`](controller-xbox-hud.md), "Beside a
widescreen patch");
the counts elsewhere in this document are the build before it. The HUD is the Xbox
one while the pad is in use and the game's own with the mouse and keyboard.
[`controller-xbox-hud.md`](controller-xbox-hud.md) describes it.

### Beside a patch that rescales the interface

Worked out on 2026-10-05 beside Scaled Kotor 1.3.1 at 3440x1440, the maintainer
looking at each build. Scaled Kotor rescales a screen's controls as its layout
finishes loading, which is before this patch adds anything to the screen, and gives
buttons shapes the game's layouts do not have. Three things follow it now.

**The added cues** (LT and RT on the tab strip, the sub-tab cue, the party cue).
Each is a label the patch's layout file adds, with the file's rectangle. As it is
bound, the control the build placed it beside (`BTN_EQU`, `BTN_OPT`, `BTN_EXIT`,
`BTN_CHANGE1`) is loaded once more into a label the panel never holds, which gives
that control's rectangle in the file; its ID says which live control it is. The cue
is then put where the file has it relative to that control, as the control is now,
and scaled by the smaller of the two factors, so its shape is kept
(`K1NativeJoystick.cpp`, `PlaceCueByReferenceK1`). Two cues are then adjusted as the
maintainer asked: the sub-tab cue 1.2 times its size about the middle of its right
edge, the party cue an eighth of its size from the portrait and on the live
portraits' middle line.

**LT and RT are arrows** (`tools/build_tab_arrows.py`, later the same day): a
triangle with rounded corners pointing along the strip, the trigger's name in its
wide end, in the strip's own colours: the dark fill of a tab's box, with the frame
and the glow in the blue of the tabs' icons (sampled from a screenshot of the
strip; the letters are lighter, to be read). The picture is drawn, letters
included (strokes with round ends; LT and RT, L2 and R2, ZL and ZR by family), so
it carries no one's art and no font. The maintainer chose it from four prototypes
and set its size and place in the running game; `BindOneCueK1` computes them from
the live tab beside each cue:

| | Rule | From |
| --- | --- | --- |
| Size | the arrow's flat side as tall as a tab's box, without the lip on top | the box is 35 of the tab's 40 units (measured on screen: the lip's three rows, then 35), the flat side 76% of the cue's square (`FLAT`), so the square is 1.15 times the tab's height |
| Height on screen | level with the box | the box's middle is 21.5 units down the tab |
| Distance | as far from the strip as two tabs are from each other | a tab is 52 wide and the next begins 62 on, each frame one unit inside its rectangle; the arrow's flat side is 3% inside its square (`EDGE`) |

Measured in the unchanged game at 1280x960: 12 px between two tabs' frames and
12 px from each arrow to its tab; the flat side on rows 287 to 322, the box on 287
to 321. Seen the same in proportion with Scaled Kotor at 3440x1440. Tried and set
aside by the maintainer: a lighter body in a brighter frame (committed for one
commit), the body in the icons' blue, the lip counted in the height, and the arrow
centred on the whole tab. Also run with Scaled Kotor at 3440x1440 on that day's
last build: the eight tabs of the in-game menu, the HUD, and the swap to the mouse
and back to the pad (the module's target menu fields read after each: the Xbox
layout, the game's own, the Xbox layout).

**A badge never changes shape.** A badge is a texture stretched over the area its
button's border fills, so it is round only on a button of the shape it was made for.
`K1ControllerBadgeShapes.inc` (written by `tools/build_controller_assets.py
--badge-shapes` from the layouts and textures the badges were built on) gives that
area for 133 of the 135 badges, with where the glyph stands across it and how wide
it is. When the live button's fill area differs from it by more than a fiftieth,
in the normal state or the focused one (a border's inset is a number of pixels a
rescaled button keeps, so Options' Close was right until focused), the button
carries no badge and the texture is drawn on a label of the patch's own: as tall as
the button's fill area and as wide as the made-for shape makes it at that height
(`vendor/K1XboxControls.cpp`, `ShowK1BadgeOverlay`). The label is constructed, given
the panel as parent and the next free ID, and added to the panel's control array
with the engine's `CExoArrayList::Add` (`0x00671C00`), as
`CSWGuiPanel::InitControl` (`0x0040B930`) files a loaded control; its fill is set to
stretch (the low two bits of the flags at `+0x1C` of `CSWGuiBorderParams`: 0 tiles,
which drew the badge twice on Graphics Options' wide buttons, 1 centres, 2
stretches); and it is freed when the panel is destroyed. In the unchanged game the
shapes agree and the badge is on its button, as before.

**The badge stands beside the caption as it is on screen.** Its texture has the
glyph where the caption was when it was made, in the game's font at the layout's
size; on a button three times as large with a caption hardly larger the glyph was
far out from the text. The engine has no "width of this string", only the height a
string takes when wrapped to a width (`CAurGUIStringInternal::GetIdealPixelHeight`,
the virtual at `+0x50`; a button's `CSWGuiText` is at `+0x154`), so the caption's
width is found as the narrowest width at which it is still one line high
(`MeasureK1Caption`). The glyph is put a quarter of the button's height from the
text, on the side it stands on in its texture, and kept inside the button. Where a
caption cannot be measured, the glyph keeps its distance from the button's middle
if that fits and from the button's end if not.

**And on the caption's line.** A layout's `ALIGNMENT` is in the text's flags (`+0x38`
of its `CSWGuiTextParams`): 8 is the top of the text's rectangle, 32 its bottom, 16
its middle (the game's buttons have 9, 10, 18 and 34). The Map screen's two rows are
13 units tall with their text at the top; beside Scaled Kotor at 3440x1440 they were
39 px tall with a 16 px line still at the top, and their glyphs stood in the rows'
middles, below the captions (the maintainer saw it; the numbers are a diagnostic
log's). So the label is centred on the caption's line, and a resized button whose
caption is more than a sixth of its height off its middle line has its badge moved
to a label even when its shape is the one the badge was made for. A button that is
the size its badge was made for is left alone, whatever its alignment.

With the badge alone moved up to the caption, the two stood above the row and the
maintainer found the whole line too high. So such a caption is brought to the
button's middle line as well: it is given a rectangle one line tall there
(`CSWGuiText::SetExtent`, `0x00416280`) for as long as the badge is shown, and its
own rectangle back when the badge goes (the mouse or keyboard in use, or the panel
closed). Seen after that at 3440x1440: both rows' captions and glyphs in the
middle of their rows, and the other seven tabs as before. Not looked at: the
caption going back when the mouse is used on that screen.

**Beside KMRP, 2026-10-06.** KMRP's layouts are a third case: neither the game's
nor a rescaling of them. Four defects the maintainer saw there at 3440x1440 were
this patch's, and the rule he set is that it scales itself to any interface and
takes nothing from another patch (KMRP's set has badges of the same names made for
its own buttons; this patch does not use them).

- *The X of Inventory's "Show ..." button was an oval.* That badge has six textures,
  one per caption, `kmrpx_invnew0` to `5`; the shape table has one row,
  `kmrpx_invnew`, and the lookup compared whole names. No row, no guard. The lookup
  now also takes a name less its last digit.
- *The A of an Options row stood about 90 px from "Load Game".* `MeasureK1Caption`
  found a caption's width by asking the line breaker for heights, and KMRP's patch
  changes the line breaker (a word that fits no line stays on it). The width is now
  the sum `Draw` makes: for each character (lower-right u - upper-left u) x
  `texturewidth` + `spacingR`, times the text's scale and 100, from the font
  information of the caption's own string (`MeasureK1CaptionByFont`). The old search
  remains for a font that cannot be read.
- *An A stood beside Equip's empty button.* The game hides that button while a slot
  has the focus; a badge on the button's fill went with it, a badge on a label of
  its own did not. `SyncK1BadgeOverlays` runs every frame for the panel in front:
  a label is drawn only while its button is, and is placed again when the caption
  or the button's rectangle changes (Equip's button then reads "OK", and the A
  stands beside it).
- *The party cue stood against the left portrait.* It was moved by a fixed share of
  its size from where the layout file has it, which is right in the game's layout
  (the cue follows the last portrait) and wrong in KMRP's (the cue is between two).
  `BindOneCueK1` now finds the portraits among the live controls, by the size of
  the one the cue was built beside, and puts the cue an eighth of its size from
  the one on its left, or in the middle of the gap where the next portrait leaves
  less room.

Seen in the scratch copies that night, pad driven: beside KMRP at 3440x1440, alone
on the unchanged game, and beside Scaled Kotor 1.3.1 at 3440x1440.

**Level Up and Auto Level Up, the same night.** These two badges stand on their
buttons' own box (`dialog2`), which their texture carried under the glyph, and both
buttons have a 16-unit border with corner art (`character.gui`: `BTN_LEVELUP`
127x40, `BTN_AUTO` 127x52). So the fill, and the texture with it, is a strip 8 and
20 units tall: in the unchanged game at 1280x960 the A was a dot and the Y a smear
over "Auto", the first time this build's Character screen was seen with a level to
take (a scratch save with the class levels lowered). They were also the two badges
the shape guard left on their buttons whatever the shape.

`ShowK1BackedBadge` now leaves the box on the button and draws the glyph from a
plain badge of the same letter (`kmrpa_abcgok`, `kmrpy_abcgrec`) on a label, as
tall as the Close button's 28 units are of the button's own height in the game's
layout. Where it stands is the maintainer's, set over four builds he looked at:

| | Rule |
| --- | --- |
| The buttons | made wide enough for badge and caption; both get the wider of the two needs and grow about their own middles; a layout whose buttons are wide enough is left alone |
| The caption | keeps the number of lines its layout gives it ("Auto / Level Up" stays two), centred in the button right of the badge |
| The badge | at the button's left end, so the two stand under each other |
| The room | three quarters of the badge's height at each end, a third of it between badge and caption |

Nothing is a fixed place or size: the badge's height is a share of the button's,
the caption's width is the narrowest that holds it in its lines, summed from its
own font (`MeasureK1CaptionByFont`, `wrapLines`), and the rest are shares of the
badge's height. The buttons get their own rectangles back when the badge goes
(`HideK1BadgeOverlay`). Where a button would need more than twice its width, which
no layout seen does, the buttons are left and the badges stand outside them on the
left. Tried and set aside by the maintainer that night: the badge shrunk to the
room beside the caption (10 px, then 16 and 11 px), the badge inside with only the
caption moved, the caption on one line, and half and a quarter of the badge's
height for the room.

Seen by the maintainer at 3440x1440 with Scaled Kotor: the tab strip's LT and RT,
Abilities' two cues, Options, Gameplay Options (the Controller Layout entry, placed
from the live Mouse Settings and Key Mapping buttons), Graphics Options and its
resolution pop-up, character generation. Not run since: the unchanged game (the
regression test passes; the code paths for it are the old ones), the remaining
screens, other sizes and other families' art. The two badges left out are made for
another control's size (`size_like`) and stay on their buttons.

## 6. Limits

- **Another mod's layout files in Override.** The badges and cues are made for the
  layouts the game ships, and the patch serves its 16 changed layout files in
  their place. Beside KMRP it serves none of them, and beside a patch that rescales
  the game's own layouts at run time (Scaled Kotor) the badges and cues follow the
  live controls (section 5). With another interface mod's layout files in Override
  the 16 replace that mod's: not tried. (Until 2026-10-06 this limit read "the
  game's original interface only", with KMRP as the answer for a scaled interface;
  the patch now runs beside KMRP.)
- **An executable changed on disk is refused by KOTOR Patch Manager**, which
  accepts the three declared executables by hash. UniWS changes the executable.
- **640x480** loads `mainmenu.gui`, whose buttons are 210x22; the main-menu badges
  are made for the 235x24 buttons of the four files the game loads above it. The
  Controller Layout screen is an 800x600 panel and does not fit a 640x480 screen.
- **The Map screen's two rows are 13 px tall**, so their badges are 9 px and the
  letter cannot be read; the colour is the cue. Focused, a row's fill area is 1 px,
  so its focused texture is empty by rule 3 of section 3 (not seen: focus was not
  moved onto a row).
- **English badge placement.** Each badge sits beside its button's English caption.
  KMRP's installer re-centred badges against the player's `dialog.tlk` while it
  wrote the interface files itself (until 2026-10-04; no call of that step is left
  in `src/patcher`, read on 2026-10-08); nothing does here, so in another language
  a badge on a button of the game's own size sits a little further from, or closer
  to, its words. A badge moved to a label of its own (section 5) is placed from
  the caption as measured in the running game, whatever the language. No game in
  another language has been looked at.
- **Windows only.** A macOS module does not exist; see
  [`macos-changes-from-windows.md`](macos-changes-from-windows.md), item 17.

## 7. What is deliberately not changed

- The executable on disk, apart from what KOTOR Patch Manager's own deployment
  does. Every hook is applied in memory.
- Override, and every file in the game folder except `kmrp-controller.ini` when it
  is missing.
- The movie window: `KpmMoviesOffK1` returns true, so the movie frame only reads
  the pad and KMRP's black bars are not drawn.
- Keyboard and mouse behaviour. KMRP's keyboard navigation hooks
  (`KeyboardNavigateK1` and its two companions) are not in this patch: the pad's
  navigation is separate (`K1KeyboardNavigation.cpp`, "the controller's 0x2F..0x32
  path remains independent").
- KMRP's Controller Layout screen. `build_controller_layout.py`'s `separate_top`
  defaults to off: run on KMRP's 800x600, 1920x1080 and 3440x1440 sets, it
  produces `kmrplayout.gui` byte for byte as the committed generator does.
  (KMRP's badges did change that day, on purpose: section 3.)

## 8. Tested and not tested

All on one PC (NVIDIA RTX 3080), in scratch copies of the game with no Override,
installed with KOTOR Patch Manager 0.7.1's own launcher
(`KPatchLauncher.exe <exe> --patches dist\controller kmrp-controller --deployment
proxy`), driven by a virtual pad (`testing\controller\virtual_pad_server.py`), in a
window. Badge sizes were measured from screenshots.

| What | Result |
| --- | --- |
| CD 1.03 executable, 800x600, 1024x768, 1280x960, 1600x1200 | main menu, Options, Load Game, loading a save, the HUD, the Start menu and two of its tabs: badges present and round at every stop (an earlier build of the day at the three other sizes; this build at 1024x768) |
| GOG executable, 1024x768 | the same tour: the same |
| Main menu, Options, its Gameplay and Sound screens with Default and Close, the Controller Layout entry and screen | seen |
| The seven in-game menu tabs reached with RT (Options, Equip, Inventory, Character, Abilities, Messages, Journal) and the Map | seen, with the LT and RT cues, the R3 cue and the swap-tabs cue |
| Exit Game's confirmation box | the A travels between OK and Cancel |
| Walking with the left stick, turning with the right, RB to target, A to talk, B to release the action bar | worked |
| New Game: class selection, Quick or Custom, the Portrait, Name, Play list | seen, with badges |
| PlayStation glyphs | a virtual DualShock 4, read through the embedded SDL: Cross and Circle badges and the PlayStation layout screen |
| Switch and Steam Deck glyphs | the art and both layout screens seen, **with the family written into the running game's memory**: no virtual pad of either kind exists, so their detection was not exercised |
| Debug logs off | no log file beside the game |

**Not tested:** Steam's executable (the hooks are KMRP's, which the maintainer ran
on Steam on 2026-10-04, but this package was not run there); fullscreen; a real
controller of any kind, and so rumble; combat, and so the X and Y combat cues on
screen; a dialogue with replies, and so the dialogue's A; the Container and store
screens (the store had no badges until 2026-10-06, when the maintainer saw it bare
beside KMRP; A, X and B were added that day, see the changelog); Pazaak and the other minigames; level-up; another language's game; AMD or
Intel graphics; Proton.

## 9. Verifying by hand

```powershell
# the game's own layouts, once, from an unmodified copy of the game
python tools\build_controller_assets.py --extract "C:\path\to\clean game"

# module and package
src\controller-native\build_controller_standalone.cmd
python tools\build_controller_kpatch.py --verify-clean build-inputs\swkotornopatch.exe

# the package against its sources, and the file bank's rules
python testing\regression\Test-ControllerKpatch.py
```

Then install it in a scratch copy with KOTOR Patch Manager, connect a pad, and
measure the badges in a screenshot of the main menu and of Options with Close
focused: each should be as wide as it is tall, to a pixel.
