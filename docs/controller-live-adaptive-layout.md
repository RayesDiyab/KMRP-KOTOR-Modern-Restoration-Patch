# Controller Live Adaptive Layout: how the controller patch draws every picture at the size it is shown

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it: measured claims only, every site
> tabulated, rejected alternatives and corrections kept visible, and anything untested
> labelled as untested.

**Reference.** This is the mechanism as it is in the source on 2026-10-28. The order in
which it was built, and every fault found on the way, is in [`CHANGELOG.md`](../CHANGELOG.md)
(the entries for phases 1 to 5, 2026-10-27 and 28) and in section 9 here.

The controller patch ("KOTOR 1 Native Controller Mod + Xbox HUD",
[`docs/controller-standalone.md`](controller-standalone.md)) carries no texture. Every
picture it shows (the button badges, the cues, the Controller Layout screen, the
remapping screen's symbols, the swoop race's prompt and the Xbox-style HUD's frames) is
kept as outlines and drawn by its module while the game runs, at the size of the control
that shows it, and written into the module's folder as a texture the engine then loads.
"Controller Live Adaptive Layout" is the name for that whole: the outlines, the drawer, and
the module code that decides what to draw, at what size, and when. It is the first built
part of Live Adaptive Layout, the project to make KMRP's interface follow any screen and
any layout at run time instead of from prebuilt files (the maintainer's names, 2026-10-27
and 28). The rest of that project, laying out any `.gui`, the game's or a mod's, by rules
per aspect ratio, is not built.

Provenance. Engine structures and addresses are read from the swkotor1-reconstruction
project (a byte-matching decompilation, `matching/`), and the ones this module calls were
checked in the executable named below. Picture comparisons were run with
`tools/controller_glyphs.py` (the Python drawer) against the textures the build made
before; timings were read from the module's own log (`kmrp-controller-events.log`,
`debug-logs=1`) in the maintainer's game at 3440x1440 unless a row says otherwise. What
was seen in the game, and what was not, is in section 8.

## The build this describes

| | |
| --- | --- |
| Source | `master` at f688a48 plus the corrections of 2026-10-28 listed in the CHANGELOG (uncommitted when this was written) |
| Executable the addresses were checked in | `build-inputs\swkotornopatch.exe`, the 1.03 executable, 4,042,752 bytes, SHA-256 `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886` |
| Executable played | Steam's `swkotor.exe` (`build-inputs\swkotor-steam.exe`, 4,395,008 bytes, SHA-256 `34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88`). Its code is wrapped on disk, so it was not disassembled; KPM runs the module against it at the same addresses |
| Glyph bank | `build\controller-standalone\files\kmrp-glyphs.bin`, 1,712,499 bytes: 136 outlines and 172 scenes |
| What the patch carries | 18 files: 17 layout files and `kmrp-glyphs.bin` (and SDL, packed beside them). No texture |

Addresses are virtual addresses (VA) in the executable. This document changes no byte of
the executable; every address here is one the module reads, writes in memory, or calls.

## 1. What the engine does

### A border, its fill, and how a picture reaches the screen

Every label, button, toggle and progress bar draws pictures through `CSWGuiBorder`
objects. Each border has a `CSWGuiBorderParams` block whose fill texture name, 16
bytes, is at +0x40 of the block.

| Control | Vtable | Border parameters (block start) | Read from |
| --- | --- | --- | --- |
| `CSWGuiLabel` | 0x0073E5B8 | +0x70 | `K1XboxControls.cpp`, `K1_GUI_LABEL_VTABLE`; reconstruction `gui_control.h` |
| `CSWGuiButton` | 0x0073E658 | border +0x80, highlight +0xF4 | `K1_BUTTON_BORDER_PARAMS_OFFSET`, `K1_BUTTON_HILIGHT_PARAMS_OFFSET` |
| `CSWGuiButtonToggle` | 0x0073EB88 | as a button (it derives from it) | reconstruction `gui_control.h:452` |
| `CSWGuiProgressBar` | 0x0073E7A0 | border +0x7C, progress +0xF0 (the borders at +0x68 and +0xDC, parameters 0x14 in) | reconstruction `gui_control.h:508`; `K1XboxHud.cpp` `kBarBorderParams`, `kBarFillParams` |
| `CSWGuiPanel` (its own border) | per class | `m_pBorder` at +0x5C, a `CSWGuiBorder*`, its parameters at +0x14 of it; the panel's extent at +0x04 | `CSWGuiPanel::StartLoadFromLayout`, 0x0040A680 |

`CSWGuiBorderParams::SetFillImage` (0x00414C00, `__thiscall(params, CResRef*, int bForce)`)
stores the name and, when it differs or `bForce` is set, releases the old image and
creates a new one with `NewCAurGUIImage` (reconstruction `gui_parts.cpp:52`). The module
always passes `bForce` 1, as the code it replaced did.

A button draws one of its two borders (`CSWGuiButton::Draw`, reconstruction
`gui_control_draw.cpp:169`):

```cpp
if (m_bFlag0) m_cHilight.Draw(fDelta);      // focused: the highlight border
else          m_cBorder.Draw(fDelta);
```

`m_bFlag0` is bit 0 of the control's flags at +0x44; the level-2 snapshot (section 10)
logs it.

### Where controls are, and where some are not

The GUI manager (`*(void**)0x007A39F4`) keeps its panels at +0x88 (count +0x8C) and its
modal stack at +0x94 (count +0x98). A panel keeps its controls at +0x20 (count +0x24).
Not every control is in a panel's list:

* **A panel's own border** (the root `BORDER` of its layout file) is no control. The
  Controller Layout's backdrop, `kmrlytbg`, is one.
* **The in-game interface** (`CSWGuiMainInterface`, vtable 0x00753F50, 0xC8CC bytes,
  reconstruction `sw_gui_main_interface.h`) holds its target menu at +0xBC
  (`CSWGuiTargetActionMenu`: its name label +0x15CC, the name bar's background +0x170C,
  the health bar +0x198C, its three action slots from +0x54, each
  `CSWGuiMainInterfaceAction` 0x71C long (`K1XboxHud.cpp`, `kActionSize`): frame, icon, up
  and down buttons at +0, +0x1C4, +0x388, +0x54C) and its party
  members at +0x1F88 (`CSWGuiMainInterfaceChar[3]`, 0xEA8 each) *inside itself*. Their
  controls are drawn by their owners and are in no panel's list.
* **Stamps.** The Xbox-style HUD draws some frames by setting one spare label's picture
  and rectangle and drawing it, several times in one frame (`K1XboxHud.cpp`: the empty
  places of the action row, the first place's frame, the map's frame when another patch
  removed the game's, and a tall name's three bar slices).

### The resource folder

The module's files are unpacked into a folder of its own in `%TEMP%` (`KMC*.tmp`, made
and removed by `K1ControllerStandalone.cpp`) and registered with the game's resource
manager under an alias. A file written there later is found once the folder is listed
again: `0x004088E0`, called with the manager at `*(void**)0x007A39E8` and the alias as a
`CExoString` (built with 0x005E5A90, freed with 0x005E5C20), in
`KmrpControllerRelistK1`. The folder lives for one game session.

### The screen size

`0x0078D1D4` (width) and `0x0078D1D8` (height), written by the mode switch
(`SetVideoMode`). The engine keeps its panels across a change of resolution: choosing a
resolution (`CSWGuiOptionsResolution::OnResolutionChosen`, 0x006DF690) calls
`SetVideoMode`, writes `swkotor.ini`, pops the top modal panel and sets
`m_bReinitPending`; closing Graphics Options then calls `ReInitAurora`. No panel is made
again. KMRP's own module lays the open panels out again in place when it observes the new
size (`KmrpRuntimeLayoutDimensions`, `K1RuntimeLayout.cpp`).

## 2. The data: outlines and scenes

### The drawing rules

[`tools/controller_glyphs.py`](../tools/controller_glyphs.py) states them, and three copies
follow them byte for byte: `tools/controller_glyphs.py` (the build and the tests),
`macos/tools/kmrp-glyphs.c` (the module, and the Mac's helper) and `src/patcher/GuiBlend.cs`
(KMRP's installer). In short: a glyph is a box of W x H units, its larger side 65536, and
items painted in order, each a set of closed integer polygons, a fill rule and a paint
(solid RGBA, or a linear or radial gradient of 1 to 16 stops). Each pixel takes 8 x 8
samples; integer arithmetic only.

### `kmrp-glyphs.bin`

Written by `pack_glyphs` in [`tools/build_controller_assets.py`](../tools/build_controller_assets.py),
read by `FindK1Glyph` in `vendor/K1XboxControls.cpp`.

| Part | Layout |
| --- | --- |
| Header | `KGLY`, u32 glyph count |
| Per glyph | u16 name length, the name (`p/A`, `-/kmrlytbg`; the first letter the family, `-` for a picture the same for every family), then the glyph as `controller_glyphs.pack` writes it: u32 W, u32 H, u32 items; per item u8 rule, u8 paint, the paint (solid 4 bytes; linear 3 x i64; radial 6 x i64; then u32 stops and per stop u32 position and 4 bytes RGBA), u32 polygons, per polygon u32 n and n x (i32 x, i32 y) |
| Scenes | `SCEN`, u32 count; per scene u16 name length and the texture's name, u32 width, u32 height, u32 parts, u32 flags (bit 0: each glyph fills its box), u32 cap (the most pixels on its longer side, 0 for any); per part u16 name length, the glyph's name, 4 x i32 box (left, top, width, height in the texture's pixels) |

**The module stops at the first glyph it cannot read** and loses every glyph after it
and every scene. `kmrp_glyph_read` refuses a glyph wider or taller than 65536 units,
with more than 4,096 items, a gradient of 0 or more than 16 stops, or a polygon of more
than 1,000,000 points. `controller_glyphs.pack` refuses the same, so the build fails
instead of shipping such a bank.

### What is in it

| Glyphs (136) | From |
| --- | --- |
| The 21 pictures of each of four families (faces, shoulders, triggers, Start and Back, the D-pad and its four directions, the stick clicks, the sticks, the swap-tabs phrase), 84 | `assets/controller-glyphs/glyphs.json` (Xelu's vector source, [`tools/build_controller_glyph_vectors.py`](../tools/build_controller_glyph_vectors.py)) |
| `TAB_LEFT`, `TAB_RIGHT` per family, 8; `-/kmrrmask`, `-/kmrrmlock`, `-/kmrrmdot`, 3 | [`tools/controller_drawn_art.py`](../tools/controller_drawn_art.py) |
| `LAYOUT_BODY`, `LAYOUT_LINES` per family (the Controller Layout's board), 8 | `controller_drawn_art.layout_diagram`, the silhouette from `glyphs.json` (`DIAGRAM`) |
| `-/kmrlyt*`, the Controller Layout's backdrop, 10 | [`tools/controller_layout_backdrop.py`](../tools/controller_layout_backdrop.py), `outlines()` |
| `-/kmrx_*`, the Xbox-style HUD's 17 frames and 6 name-bar slices, 23 | [`tools/build_xbox_hud_art.py`](../tools/build_xbox_hud_art.py), `outlines()` |

84 + 8 + 3 + 8 + 10 + 23 = 136, the count the bank's header holds.

A scene names a texture the game asks for, the glyphs it shows and where. Every texture
the build makes is registered as one (`register_scene`, or `build_square_glyph_tga` for a
one-glyph picture), by the texture's SHA-256, and `scenes_for` writes those whose
texture is carried. The textures themselves are written to
`build\controller-standalone\made` (1,067 files) and not carried; `--carry-drawn` carries
them again as a fallback.

| Scene kind | Flags | Cap |
| --- | --- | --- |
| One-glyph pictures (cues, Layout row glyphs, remap pictures), the tab arrows, the swoop prompt | keep proportions | none |
| The Controller Layout's board (`kmr?lytdiag`: body, the four face buttons, lines) and backdrop pieces | keep proportions | none |
| `kmrlythair` (the hairline, stretched along the screen) | fill | none |
| `kmrlytbg` (the full-screen backdrop) | fill | 1024 |
| The 23 HUD frames | fill (the HUD stretches its frames over their controls) | none |

## 3. Every engine site the module uses

| VA | What | How the module uses it | Where |
| --- | --- | --- | --- |
| 0x00414C00 | `CSWGuiBorderParams::SetFillImage` | sets a fill to a drawn texture | `K1XboxControls.cpp`, `K1XboxHud.cpp`, `K1ControllerLayout.cpp`, `K1NativeJoystick.cpp` |
| 0x004088E0 | the resource folder listed again | after each texture written | `KmrpControllerRelistK1` |
| 0x007A39F4 | the GUI manager | panels +0x88/+0x8C, modal stack +0x94/+0x98 | the sweep, the probe |
| 0x0078D1D4, 0x0078D1D8 | screen width, height | the swoop prompt's size; the probe's trigger | `KmrpDrawnPictureK1`, `probeLayoutPictures` |
| 0x0040B570 | `CSWGuiPanel` constructor | the probe's copy of the Controller Layout | `probeLayoutPictures` |
| 0x0040A680 | `CSWGuiPanel::StartLoadFromLayout` | loads `kmrplayout` into the copy | the same |
| 0x0040B930 | `CSWGuiPanel::InitControl` | binds each control of the copy (`bind`) | the same |
| 0x0041ACD0, 0x0041C0F0 | label, button constructors | the copy's controls | the same |
| 0x0040CF70 | `CSWGuiPanel::~CSWGuiPanel` body | takes the copy apart (it removes a panel from the manager only if the panel is in it; the copy never is) | the same |
| 0x006FA7E6, 0x006FA390 | the game's allocator, free | the copy | the same |
| 0x00423A60 | load a texture reference | the swoop prompt's drawing | `UpdateSwoopPromptK1` |
| 0x006DF690 | `CSWGuiOptionsResolution::OnResolutionChosen` | called once on A (section 9) | `ResolveResolutionConfirmK1` |
| 0x0040A140 | `CSWGuiManager::PlayGuiSound` | the sound the screen's own confirm plays | the same |
| vtable slot 2 | a panel's `SetActiveControl` | the HUD lets go of a hidden slot's focus | `K1XboxHud.cpp` |

`OnResolutionChosen` was checked in the executable before it was called: the screen's own
call at 0x006E0F1E is `push 0; mov ecx, edi; call 0x006DF690` after
`call 0x0040A140` at 0x006E0F19, and the function returns with `ret 4` (one argument,
`__thiscall`). `PlayGuiSound` was already called the same way elsewhere in the module.

## 4. The module: what decides what to draw, at what size, and when

All in `src/controller-native/vendor/K1XboxControls.cpp` unless named; built only into
the controller patch (`KMRP_CONTROLLER_STANDALONE`). KMRP's own module has stubs that
draw nothing (`KmrpLogicalFillK1` returns its argument, and so on).

### The size of a picture

For a border at parameters offset `o` of control `c`: the control's extent (+0x04, left,
top, width, height) less `2 x inset` each way, where `inset` is the border's DIMENSION
(the first int of its parameters) when the border has a corner image
(`K1ButtonFillInset`), else 0. A scene's cap scales that down to the cap on its longer
side, keeping its shape. Pictures larger than 4095 on a side are not drawn.

### Drawing one (`K1SceneTexture`)

The texture's name is `K1DrawnName('s', scene, w, h)`: `kmzs`, the FNV-1a hash of the
scene's name (6 hex digits), w and h (3 hex digits each). "kmz", not "kmr": the module
gives a "kmr" name the pad family's letter at its fourth character, which would rename a
drawing. If the name was drawn this session it is used as it is. Otherwise each part's
glyph is fitted into its box (keeping proportions unless the scene fills), drawn with
`kmrp_glyph_draw`, laid over the sheet, and the sheet written as `<name>.tga` with a TXI
`mipmap 0` and `clamp 3`, and the folder listed again.

`kmrp_glyph_draw` (`macos/tools/kmrp-glyphs.c`) works four pixel rows at a time
(`glyph_rows`), so a drawing needs one band's memory. A drawing of 8 MB of sums or less
is kept (up to 256 drawings, 8 MB in all) for reuse within the session;
`kmrp_glyph_draw_alone` draws without that cache, for the background thread.

### The five ways a picture is asked for

| Path | When | Function |
| --- | --- | --- |
| **The sweep** | every frame, before anything else in `UpdateK1ControllerPrompts` | `K1SweepRuntimePictures` over the GUI manager and, if it is another, the in-game interface's manager: each panel's own border, each control of each panel, and, for the in-game interface, every label, button and progress bar inside it (found by their vtables, 0x0073E5B8, 0x0073E658, 0x0073E7A0) |
| **A picture set by name** | whenever code sets a fill to one of the patch's pictures | `KmrpDrawnFillK1(params, name)`: finds the control from the parameters' place (+0x70 a label, +0x80/+0xF4 a button or toggle, +0x7C/+0xF0 a progress bar, told by the vtable at the start; the read guarded), draws the picture at its size and returns the drawing's name. Used by the HUD (`SetFill`), the Controller Layout and remapping screens (`setFill`, `refresh`, the confirm badges), the badges' paint (`SetK1ControllerPromptFill`) and the cues (`MatchCueFamilyK1`, `ShowActionCueK1`) |
| **A stamp** | each draw of the HUD's spare label | `KmrpStampPictureK1(control, offset, name)`, after the stamp's rectangle is set |
| **The swoop prompt** | when the race HUD's prompt is first needed | `KmrpDrawnPictureK1`, 128 x screen height / 480 (128 to 1024) |
| **The background thread** | as the game starts and after a change of resolution | below |

`KmrpLogicalFillK1(fill)` answers the other way, the picture a drawing stands for, for
code that compares names (the cues, the HUD's `SetFill`, the remap screen's `setFill`,
the pause box's `PauseCarriesOurs`).

### The background thread (the Controller Layout's pictures)

The Controller Layout's pictures are the large ones (the board 1520x760 at 3440x1440).
They are drawn before the screen is opened:

1. **When** (`probeLayoutPictures`, `K1ControllerLayout.cpp`), by events, not time: the
   screen size changes; the screens up are noted; once they have been made again or laid
   out for the new size (the panels, or their sizes, differ) and have held for a frame,
   and a whole frame has gone by in which the game thread drew nothing
   (`KmrpPicturesSettledK1`), the probe runs. As the game starts, from the first such
   frame with a screen up. `layout-predraw=0` in `configs\kmrp-controller.ini` turns it
   off.
2. **The sizes**: a copy of the screen is made as the screen is opened (panel
   constructor, `kmrplayout` loaded, every control bound) but never added to the
   manager, each picture's size read as the sweep would, and the copy taken apart as the
   screen's own destructor does.
3. **The drawing**: one thread (`K1BackgroundWorker`) draws each queued picture with
   `kmrp_glyph_draw_alone` and writes its files. The current family's pictures first,
   the other three after. It calls nothing of the engine's.
4. **Collected** on the game thread each frame (`K1CollectBackgroundPictures`): the folder
   is listed again once for what is finished.
5. **A picture asked for before it is ready**: taken out of the queue and drawn at once if
   the thread has not reached it; waited for if the thread is drawing it.

## 5. How this stays isolated

* Only fills whose name begins `kmr` or `kmz` and names a scene are touched; every other
  fill (the game's, another mod's) is left as it is. A guessed control (the in-game
  interface's scan, `KmrpDrawnFillK1`) whose fill is none of these is not changed.
* The drawn textures are written only to the module's own `%TEMP%` folder, never to
  Override or the game folder.
* The background thread calls no engine function and shares no drawing state with the
  game thread (`kmrp_glyph_draw_alone`); the queue is under one mutex.
* KMRP's own module compiles the same sources without `KMRP_CONTROLLER_STANDALONE` and
  draws nothing; its sets carry no controller art (b1148c9).

## 6. Limits

| Limit | Value | Where it comes from |
| --- | --- | --- |
| Glyph items | 4,096 | `kmrp_glyph_read` (64 until 2026-10-27; the backdrop's illustrations have 61 after merging) |
| Gradient stops | 1 to 16 | `kmrp_glyph_read` |
| Drawn size | 4095 x 4095 | the sweep and `KmrpDrawnFillK1` |
| The backdrop | drawn at most 1024 wide, stretched | its scene's cap |
| Memory | about 20 bytes a sample, 64 samples a pixel, four rows at a time: 7.5 MiB for the board at 1520x760 | `glyph_rows` |
| A drawing's time | the board 1.4 to 1.5 s, the gunnery station 0.5 s, the freighter 0.3 s, the backdrop 1.4 to 1.8 s (at 3440x1440, on the background thread); a HUD frame or badge 0 to 16 ms | the log |
| Drawings per session | made again each game session: the folder is per session | `K1ControllerStandalone.cpp` |

## 7. What is deliberately not changed

* **No byte of the executable.** Everything is in the module's memory and its folder.
* **The game's own textures.** No game texture is replaced or written; the HUD's frames
  have names of their own (`kmrx_*`), so the PC HUD and other mods see the game's.
* **KMRP's sets.** They carry no controller art and are not drawn at run time on
  Windows; the Mac carries the drawn pictures as textures
  (`macos/tools/make_controller_assets.py` sets `CARRY_DRAWN`) because its module does
  not draw them ([`docs/macos-handoff-1.5-to-1.6.md`](macos-handoff-1.5-to-1.6.md), items 100 and 101).
* **Drawings across sessions.** Not kept; each session draws again (in the background for
  the Layout). Keeping them in a lasting folder was offered and not chosen
  (section 9).

## 8. Tested and not tested

| What | How | Result |
| --- | --- | --- |
| The C drawer equals the Python drawer | `Test-ControllerGlyphs.py`: 925 drawings, byte for byte, one of them 950x615 (the banded path) | passes |
| C, C# and Python drawers agree | `Test-GuiBlendHelper.py`, 369 sizes | passes (2026-10-28, before the corrections, which did not touch the drawer) |
| The bank holds every glyph and scene, reads to its end, carries no texture, the HUD frames made with their TXI | `Test-ControllerKpatch.py` | passes |
| Pictures match the textures they replace | mean difference per channel, drawn at the old texture's size: tab arrows and remap symbols 0.6 to 3.2 of 255; the board 0.38 (Xbox), 0.41 (PlayStation); the backdrop 0.02 to 1.06; the HUD frames 0.01 to 0.65 | measured |
| Badges, cues, the Controller Layout, the remapping screen, the HUD's frames | the maintainer, at 3440x1440 and after changes to 2560x1440 and 1920x1440, with a DualSense | seen working on 2026-10-28 |
| The swoop race's prompt | | **not seen in the game** |
| Other pads (Xbox, Switch, Deck), other aspect ratios than 21:9 and 4:3 | | **not seen in the game**; drawn by the same code and covered by the tests above |
| The background thread under a slow disk or processor | | **not measured**; its trigger is by events, not time, so that the order holds anywhere |

## 9. Rejected alternatives and corrections

| What | Why it was rejected or corrected |
| --- | --- |
| Shipping the pictures prebuilt (the state until 2026-10-27) | One size stretched over every screen: soft at most sizes (issue 68) |
| Drawing at install time, for every resolution | About 3 s and 8 to 10 MB per resolution for the Layout alone, 66 resolutions; and the controller patch works without KMRP's installer, whose code may not write controller art (the maintainer's rule). The maintainer chose the background thread |
| Keeping drawings in a lasting folder | Offered; the maintainer chose drawing in the background as the game starts and after a change of resolution |
| Filling each row only between its crossings (to draw faster) | Measured no faster: the board 1.15 s against 1.00 s, the backdrop slower (sorting). Not kept |
| A delay before the probe (15 frames, then 2.5 s) | Ran while the game made its screens again; and a delay depends on each machine (the maintainer). Replaced by events |
| **Correction**: a 17-stop gradient (the hairline) | The module stopped reading the bank at it: "104 glyph outlines and 0 pictures read", every drawn picture white. 13 stops now, and `pack` refuses what the module would |
| **Correction**: the whole sample grid at once | 1.38 GiB for the board at 1520x760, which the 32-bit game could not have: a crash. The CHANGELOG first said "about 2 GB at about 1800x900", an estimate before the board's size was read from the log; and "about 2 MB" for the banded drawing, which is 7.5 MiB for that board |
| **Correction**: the panel's own border not swept | The Layout's backdrop was white until the sweep read `m_pBorder` |
| **Correction**: controls inside the in-game interface, stamps, and pictures set by name | White frames, then a white flash on every change of focus; each found in the game by the maintainer and fixed as section 4 says |
| **Correction**: A on the Resolution screen | ran `OnResolutionChosen` twice (the screen's own 0x27 and its focused row's, whose 0x27 handler is the same function, `CSWGuiControl::HandleInputEvent` 0x00418750 setting `m_n4c` from the press), popping Graphics Options without the flags its Close sets; the pad then moved an unseen focus. Not caused by drawing; found with level 2. Confirmed once now |
| **Correction**: the focus left on a hidden slot | After a cutscene and as combat ended the game left its focus on an empty target slot, which the Xbox layout hides; the HUD lets go of it |

## 10. Verifying by hand

1. **The bank reads to its end.** `Test-ControllerKpatch.py` walks `kmrp-glyphs.bin` and
   fails unless it reads to its end with every glyph its scenes name. The limits the
   module's reader adds (section 2) are enforced where the bank is written:
   `controller_glyphs.pack` raises on a glyph `kmrp_glyph_read` would refuse, so a bank
   that builds is one the module reads whole.
2. **The module read it.** With `debug-logs=1`, `kmrp-controller-events.log` says
   `badges: 136 glyph outlines and 172 pictures read`. Fewer means it stopped early.
3. **A picture was drawn.** Each drawing logs `pictures: <scene> drawn at WxH as kmzs…`
   (or `in the background`). The files are in `%TEMP%\KMC*.tmp`; a frame's colour can be
   read from its TGA (the selected slot's frame is (255, 255, 0)).
4. **Level 2** (`debug-logs=2` in `configs\kmrp-controller.ini`, by hand) adds: the
   screens up whenever they change (each panel's type, extent, active control with its
   flags and both borders' pictures, and every control of the panel the pad navigates);
   each move the pad makes; each badge painted; each picture set by name (`fill by
   name:`); each fill the sweep replaces (`sweep:`). It writes every frame and slows the
   game: set it back to 1 or 0 after.
5. **The tests.** `python testing\regression\Test-ControllerKpatch.py`,
   `Test-ControllerGlyphs.py`, `Test-NativeAssetsBank.py` and `Test-GuiBlendHelper.py`.
