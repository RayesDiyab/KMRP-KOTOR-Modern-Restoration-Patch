# KMRP Controller: the standalone controller patch

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Every claim says how
> it was established; anything not run is listed under "Tested and not tested".

**Kind: reference.** What `KMRP Controller.kpatch` is, what it carries, what it
writes into a running game, and how it differs from the controller support inside
KMRP's own patch. Written 2026-10-05, the day it was built. The controller itself
(the joystick device, the mapping, the prompts, rumble) is described in
[`controller-support.md`](controller-support.md) and
[`controller-native-path.md`](controller-native-path.md), and is the same code.

## What it is

One file for KOTOR Patch Manager, id `kmrp-controller`: KMRP's native controller
support for a game that has **no KMRP**. It needs no other patch, no installer and
no Override file. It carries none of KMRP's other work: no interface scaling, no
engine recipe, no memory, movie or map fixes. It runs on the interface the game
ships.

KMRP's own patch (`kmrp`) already contains controller support as an option, and
both hold the same hook sites, so the two conflict. Every `kmrp` patch since
2026-10-04 already lists `kmrp-controller` as a conflict, because the id was the
controller add-on of the four-patch edition (2026-09-28 to 2026-10-04), which
needed KMRP's core. This patch replaces that add-on and needs nothing.

## The build this describes

| | |
| --- | --- |
| Package | `dist\controller\KMRP Controller.kpatch`, 9,882,946 bytes, SHA-256 `F18F31220D64E5A3C7805D978DE420FE277591E19028F6B7B912E34BE5CADC47`, version 1.0.0 |
| Module inside it | `binaries/windows_x86.dll`, 9,855,488 bytes, SHA-256 `49701CB213D39581EBA375EE990FCC7863189A8BF1DC334D4D0C4858157D737B` |
| File bank inside the module | 9,633,675 bytes, SHA-256 `5A3110FC6A6DF116796FA7C43DFA4D3115234EC5D65C13E7F6E9452D65F3DE09`, 948 entries |
| Executables it declares | CD 1.03 `761F9466...C49E9886`, GOG `9C10E045...DEA91435`, Steam `34E6D971...A439F34C88` |
| Address convention | `VA`, image base `0x00400000`; `FILE = VA - 0x400000`. Every site is in the original image. |

The build is reproducible: two builds from the same sources on 2026-10-05 gave the
same package hash (an earlier state of the sources that day, `CE677F4C...`, twice).

## 1. What is in the package

| Entry | What |
| --- | --- |
| `manifest.toml` | id, name, description, conflicts, the three executables, one option (`debug-logs`, off by default) |
| `kotor1.hooks.toml` | the 31 hooks below |
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

Checked against every patch in KOTOR Patch Manager 0.7.1 for an overlapping site:
four overlaps, all with `expanded-keyboard-control` (`0x0040C1F6`, `0x005E271E`,
`0x00686BA0`, `0x0068B170`), which the manifest therefore lists as a conflict
beside `xbox-controls-k1` and KMRP's patches.

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
`kmf` texture on the focused border when they differ. The same code runs in
KMRP's own module, whose sets carry the `kmf` art since 2026-10-05.

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
| `kmrp-controller.ini` beside the game | the module, once, if it is not there | the rumble settings, with the installer's defaults; a file already there is never touched |
| `configs\kmrp-controller.ini` | a KOTOR Patch Manager with patch options | `[Patch Options]`, `debug-logs`; a missing file means off |
| `kmrp-controller.log` beside the game | the module, only on failure | written if the file bank cannot be unpacked; the pad still works without its prompts |

### The Xbox-style HUD

Since later on 2026-10-05 the patch has one more option, `xbox-hud`, and one more
setting, `Style` under `[Hud]` in `kmrp-controller.ini`, both off by default. They
add two hooks (33 in all), four layout files and a button glyph per controller
family to the bank; the counts elsewhere in this document are the build before it.
[`controller-xbox-hud.md`](controller-xbox-hud.md) describes it.

## 6. Limits

- **The game's original interface only.** The badges and cues are made for the
  layouts the game ships. With another interface mod's layouts in Override the 16
  changed layout files replace that mod's, and the badges are the wrong shape for
  its buttons. A player who wants a scaled interface and a controller uses KMRP.
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
  KMRP's installer re-centres badges against the player's `dialog.tlk`; nothing does
  here, so in another language a badge sits a little further from, or closer to,
  its words.
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
screens; Pazaak and the other minigames; level-up; another language's game; AMD or
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
