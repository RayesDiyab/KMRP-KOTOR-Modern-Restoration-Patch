# Controller Live Adaptive Layout: how the controller patch draws every picture at the size it is shown

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it: measured claims only, every site
> tabulated, rejected alternatives and corrections kept visible, and anything untested
> labelled as untested.

**Reference.** This is the mechanism as it is in the source on 2026-10-29. The order in
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
and 28). The shared layout rules now cover 45 screens; see the
[layout reference](live-adaptive-layout.md).

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
| Source | `master` at `33a3b4d` plus the class-selection migration and controller preload of 2026-10-29 (uncommitted when written) |
| Controller module built for priority model preload and buffered diagnostics | `build\controller-standalone\kmrp-controller.dll`, 2,691,072 bytes, SHA-256 `8C18C537AE47E1B02BDB1016A5B8CDB4885B6BDAF414DB94488230C650E8BEF0`; verified by the maintainer in Steam at 3440x1440 on 2026-10-29 |
| Executable the addresses were checked in | `build-inputs\swkotornopatch.exe`, the 1.03 executable, 4,042,752 bytes, SHA-256 `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886` |
| Executable played | Steam's `swkotor.exe` (`build-inputs\swkotor-steam.exe`, 4,395,008 bytes, SHA-256 `34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88`). Its code is wrapped on disk, so it was not disassembled; KPM runs the module against it at the same addresses |
| Glyph bank | `build\controller-standalone\files\kmrp-glyphs.bin`, 1,712,499 bytes: 136 outlines and 172 scenes |
| What the patch carries | 2 files since 2026-10-30: `kmrplayout.gui` and `kmrp-glyphs.bin` (and SDL, packed beside them); the other 16 layout files are cued at run time (section 4, "The screens' cues"). 18 files before. No texture |

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

### Movie-triggered controller GUI preload (2026-10-29)

The controller owns the additional preload queue in `K1ControllerPreload.cpp`.
`NativeMovieFrameK1` submits it when movie frames begin. The callback snapshots paths,
viewport dimensions and controller family; it does not decode or draw the art. The
existing `K1BackgroundWorker` runs the file work and drawing, alongside the Controller
Layout and HUD picture jobs. No second worker is introduced. Repeated movie frames
are deduplicated by viewport size and the optional KMRP class-layout path. The GUI
frame submits the same work after a resize or when movies were skipped.

| Source | Work prepared on the controller worker |
| --- | --- |
| `classsel.gui` | panel and Cancel geometry, source texture decode, split Select/Cancel footer written to the private picture folder |
| `kmrplayout.gui`, `pazaaksetup.gui`, `pazaakgame.gui`, `savename.gui`, `galaxymap.gui` | scene dependencies named by border/highlight fills, at the file's dimensions; current controller family before the other families |
| `lbl_pazaak` | source texture read/decode before Pazaak opens |
| KMRP HUD preview texture requests | optional `KmrpQueueTexturePreloadK1` export, using the same worker |

Sources come from the optional KMRP live-layout path, otherwise the player's Override,
otherwise the controller's own GUI or the game's keyed resource. Textures come from
Override, optional KMRP common art, then the game's GUI texture pack. Unsupported mod
textures retain the live fallback. The pure class-footer algorithm is shared with that
fallback. It handles both KMRP's brighter art and the original dark-blue footer; the
earlier brightness-threshold detector reached the image edges on the original art
because its middle and gaps both measured 21/255. The added detector finds the brighter
rounded ends first. On the native 512x512 source they span columns 188 through 323,
with arrows at 186 and 325.

KMRP is optional. Its `KmrpPreloadGuiPathK1` export only copies a source path; no engine
object crosses the module boundary. Its HUD movie callback submits texture names when
the controller export is present, retaining its original path when it is absent.
HUD and text sizing remain KMRP features. The controller's `Sizes()` ignores the KMRP
INI section unless `kmrp.dll` is loaded, even if saved values remain from an older
installation; standalone uses the standard 50% policy value, whose factor is 1.0.

Worker decoding warms source files and supplies class pixels; normal source textures
still enter the engine through the GUI thread. With a current OpenGL context,
`KmrpControllerGuiPreloadFrameK1` retains/binds at most two queued textures per frame.
Completed drawings are registered through the existing GUI-thread collection path.
The worker calls neither engine resource functions nor OpenGL. Panel-dependent
Pazaak composition and exact live probe dimensions retain their existing fallbacks;
scanning a GUI's static dependencies does not construct a hidden engine panel.

| Existing engine use | VA | Thread |
| --- | --- | --- |
| `AurTextureGetReference` | `0x00423A60` | GUI collection only |
| texture bind | `0x004214B0` | GUI collection only |
| viewport width/height reads | `0x0078D1D4`, `0x0078D1D8` | submission callback |

These are existing 1.03 VAs, not new hook sites or executable-file writes.
`Test-ControllerPreload.py` compiles the production callback, worker loop and HUD size
reader against local game files, replacing hardware addresses and module lookup.
It passes with no KMRP and with a KMRP source snapshot: native 512x512 and KMRP
2868x1436 class textures; worker identity differs from the caller; repeated movie
events deduplicate; stale geometry is refused; GUI-only resize submits work; and
unsupported source textures retain their engine preload request. It also checks
standalone ignores nondefault KMRP sizes while the combined mode reads them.
Actual GPU upload, startup timing and this preload's appearance in game are
**not play-tested**.

### First-opening class model diagnostic (2026-10-29)

The maintainer reports black character models for the first visible frame of
New Game after launch, with later openings correct. The existing level 2 log
records all six `CSWGui3DSceneView` controls visible, but not their materials or
texture upload state. The new preload is file/GUI artwork preparation and does
not establish that model materials are uploaded. No cause or fix is claimed yet.

`K1ClassModelTrace.h` is enabled only at debug level 2. On class-panel binding,
it compares the native class Draw vtable entry with the expected handler before
atomically replacing that one pointer. A different patch's handler is left alone.
The wrapper snapshots the texture table before and after calling native Draw
exactly once. It records the first four draws of each bound class panel, then
only delegates. It performs no texture build, upload or model update of its own.
After the first diagnostic test, these snapshots are buffered in memory and
written only after draw four; there is no trace-file write during the first
three draws. Each of the six native model-view draws is also wrapped, retaining
its original call once and capturing its scene state before and after it.

| Read or temporary in-memory replacement | VA / object offset | Meaning |
| --- | --- | --- |
| class-selection Draw | `0x006DC030` | original function always called |
| class-selection Draw vtable entry | `0x00758054` | native pointer checked before level 2 trace installation |
| model-view Draw / vtable entry | `0x0067ACB0` / `0x00752E68` | native pointer checked before scene tracing; unrelated views only delegate |
| texture build queue count | `0x007A4774` | pending work before and after the draw |
| hashed texture array / count | `0x007A4798` / `0x007A479C` | texture table snapshot, limited to 16,384 entries |
| textures locked | `0x007A4714` | global engine lock state |
| texture GL name | basic texture `+0x58` | zero before upload |
| texture dimensions | `+0x68`, `+0x6C` | width and height |
| texture name | `+0x78`, 32 bytes | material resource name |
| texture built flag | `+0xE0` | engine's image-construction flag |
| model view within the class panel | `+0x230 + index * 0x25C` | six views, index 0 through 5 |
| scene pointer within model view | `+0x70` | `CSWGuiScene` at +0x5C, scene pointer at +0x14 |
| scene render count | scene `+0x50` | native scene render counter |
| scene children / animated counts | scene `+0x58` / `+0xF0` | before/after native view draw |
| scene light manager / ambient | scene `+0x80` / `+0x88` | light list and ambient RGB |
| light list / count | manager `+0x08` / `+0x0C` | first light's RGB read at light +0x4C, if present |

Addresses are 1.03 VAs. The matching reconstruction's `sw_gui_class_selection.cpp`,
`gui_scene.cpp` and `aur_texture.cpp` establish constructor/draw/queue ordering;
the native class Draw entry and table bytes were checked in the GOG executable
SHA-256 `9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435`.
REA/Ghidra evidence `ev_613fc64937c74a5fefe08d90f136ec5f06fa43d2297c754a6366c611bb30c0cf`
also confirms `OnPanelAdded` calls `HideLoadScreen(1,1)` at VA `0x006DB977`.
This is static evidence, not a capture of the failing frame.

A debugger attachment to the Steam session exited at its frame swap with Windows
exception `0x4000001F`, reported at `swkotor.exe+0x48C1`. The next measurement uses
this in-process log instead. `Test-ClassModelTrace.py` verifies native delegation,
bounded logging, unchanged texture data, level-0 delegation and refusal to replace
another patch's handler. The diagnostic was installed as a single controller-module
test on 2026-10-29, after the maintainer approved it. The previous Steam controller
hash was `985656DD1B8B108D2EB9CCA98142F4924980811FF7E6F0F033D49F7C985EA8F3`;
the first diagnostic hash was `096DE669A0D44B12B5FFF7586E7DE8BF56546D682B66F89092B8E4ED9C4B5CC2`.
Its owned manifest row was updated and both old files backed up. The buffered
scene/light diagnostic subsequently replaced that module within the same test;
its hash was `840CD5CE60EB504D6CE0BD2042D30BF3962DB8090A36BF27D0B966B9BFED7B2C`.
Both installs were verified by re-reading the module and manifest. The buffered
capture found the preexisting scene state reported below; the subsequent priority
preload build is the current build-table module.
Launch fresh, open New Game once, return and reopen, then compare
the `class-model` lines in `KMRP/logs/kmrp-controller-events.log`.

First diagnostic result (2026-10-29): the maintainer saw the black frame on
both openings. Both panels' first four native Draw calls recorded
`pending=0->0` and `locked=0->0`, with texture counts unchanged at 82 for panel
`1CE7A348` and 80 for panel `1CDE00E8`. Only `kmrpcnfa` and `NULL` retained GL
name zero; both were unchanged on every recorded frame. These are observed
texture-table values, not pixel captures. The pending-texture-upload hypothesis
is not supported by this trace. The maintainer suggested logging may expose a
race; the current evidence does not establish that. The next measurement adds
scene/light state and defers file output until after the first three frames.
The black-frame cause and fix remain unverified.

### Priority 3D preview initialization (2026-10-29)

The buffered follow-up found all six previews already had three lights, one
animated object and five children before their first render. Their first light's
RGB was `(0.867,0.867,0.867)` and unchanged afterward; scene ambient remained zero.
Texture queues remained empty. Those measurements do not support delayed CPU
light creation or pending texture uploads as the explanation. The native scene
render count alone changed from 0 to 1 on the first draw. The maintainer then
requested the models take first preload priority, including the main menu.
The maintainer confirmed the black frame remained on both openings with buffered
logging and reported it may also occur on the main menu. A logging-related race
has not been established.

`K1GuiModelPreload.h` queues the six class views or the main-menu view as their
panel binds, removes jobs on panel destruction, and primes each actual scene
immediately before its first visible model-view draw. This is the first graphics
preload work; the optional GUI texture upload loop returns while models are
pending. CPU file preparation remains on the existing controller worker.

The initial native model-view draw uses `GL_NONE` color output and zero delta.
Its scene's framebuffer-effects flag is temporarily zero, so postprocessing
cannot redirect the hidden pass to a visible buffer. Native render-side animation
also uses a global delta; that is saved, zeroed and restored too. The original
draw buffer and effect flag are restored before the normal draw. The native view
clears depth/stencil again for that visible draw. No loading delay, resource-name
guess or change to the player's sizing settings is involved. Scenes already
rendered are left alone, disabled 3D does not block uploads, and missing graphics
context defers initialization. A different patch's model-view Draw is preserved.

| Additional state | VA / offset | Operation |
| --- | --- | --- |
| main-menu class / view offset | `0x00752F70` / panel `+0x360` | queue its bound preview |
| 3D GUI flag | `0x0078D1E4` | do not wait on disabled previews |
| framebuffer effects | scene `+0xD4`, DWORD | zero only during the hidden render, then restore |
| engine animation delta | `0x0078E574`, float | zero only during the hidden render, then restore |
| `GL_DRAW_BUFFER` / `GL_NONE` | `0x0C01` / `0` | read, disable color output, restore |

Native DWORD reads of scene +0xD4 were verified at VAs `0x00451746`,
`0x00451946` and `0x0045197A` in the identified GOG 1.03 executable.
The matching GUI scene/viewport source establishes the depth/stencil clear and
model-view draw calls. These are in-memory renderer operations; no game executable
file or resource is changed. The black-frame root cause remains unconfirmed;
this implements preview initialization before presentation. Its successful
fresh-launch result is recorded below; the underlying cold-render subcomponent
is not identified.

`Test-GuiModelPreload.py` exercises six class views and one main-menu view,
hidden/visible call ordering, restored graphics state, zero animation delta,
single initialization, panel cleanup and missing-context deferral. The buffered
scene trace remains available at level 2; `model-preload priority=1` records its
hidden render count and output check after four visible draws.

The helper, trace and worker tests pass, including restoration of global render
time, hidden-view/disabled-3D handling and optional-upload deferral. The controller
module builds and its package checks pass. On 2026-10-29 the current module was
swapped directly into the ongoing Steam single-file test, with its prior module
`840CD5CE...` backed up and the owned manifest row updated. The native first-frame
visual result was subsequently confirmed by the maintainer, below.

Final play-test (2026-10-29): the maintainer fresh-launched, checked the main menu,
opened New Game, returned and reopened it, then reported "done it looks correct
now". The log records `model-preload priority=1` with `renders=0->1 hidden=1`
for the main-menu views and all six views on each class opening. Each first
visible class view records `renders=1->2`, with no pending texture uploads.
The logged viewport is 3440x1440. This confirms the preload occurred before
presentation and the reported black frame was resolved in that Steam test.
Other resolutions, controller-only vanilla and debug level 0 are covered by
source/mock checks, not by this native visual test.
After acceptance, the three temporary diagnostic/test backups were verified
against their ownership records and removed as required by the live-test policy.
Their installation metadata was retained in the ignored build records. The
accepted controller module and its manifest row remain installed.

### The screens' cues (2026-10-30)

The pictures were drawn at run time from 2026-10-28; the layouts that show them were not.
Until 2026-10-30 the patch carried 16 of the game's layout files with its cues added at
build time, and its folder is searched before `Override`, so a mod's file for one of those
screens was replaced by the game's own with cues. Now the patch carries only
`kmrplayout.gui`, and the module adds the cues to whichever file the game would load:

| Step | What |
| --- | --- |
| When | once a session, in `KmrpPrepareResourcesK1`, after the bank is unpacked and before the folder is registered (`CueScreens`, `K1ControllerStandalone.cpp`) |
| Which screens | `KmrpControllerCueScreen`: `abilities`, `character`, `equip`, `inventory`, `top`, `optgameplay`, `confirm`, `dialog` and the eight `mipc*` |
| From | the player's file in `Override` when there is one, else the game's own through `chitin.key` |
| What is added | `KmrpControllerCues` (`macos/tools/kmrp-guiadapt.c`): the party cue, the swap-tabs cue, the LT and RT cues, the Controller Layout entry, the travelling A (its label cloned from the patch's `kmrplayout.gui` `LBL_TITLE`), the combat cues. The same C steps Live Adaptive Layout runs for KMRP, without laying anything out: the file keeps its own size |
| Not written | a file that already has its cues, or lacks the controls they sit by (result 3): the game loads the player's file as it is. A failure is written to `kmrp-controller.log` |
| Beside KMRP | nothing: KMRP's screens carry the cues already (`LeaveLayoutsToKmrp`) |

Measured on 2026-10-30. `Test-ControllerKpatch.py` runs `KmrpControllerCues` on the game's
16 files and compares each with what the build's Python steps make, field for field. All
16 are identical but for the travelling A's `TEXT.COLOR` in `confirm.gui` and `dialog.gui`,
0.98 against 250/255, on a label with no text (`Test-LiveLayout.py` allows the same). A
file run through it a second time is not written. The scratch game
(`build\controller-standalone\game`, the CD executable, this patch alone, its data linked to
the Steam game's) was started without input. The patch's folder held the 16 screens and
`kmrplayout.gui`. An `equip.gui` placed in its `Override` with Back moved 7 px kept the
move and gained the party cue. The screens were not looked at in the game.

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
| The screens' cues made at run time (2026-10-30) | `Test-ControllerKpatch.py`; the scratch game started, its folder read | the 16 screens written, a mod's `equip.gui` cued and kept; **not seen in the game** |
| Other pads (Xbox, Switch, Deck), other aspect ratios than 21:9 and 4:3 | | **not seen in the game**; drawn by the same code and covered by the tests above |
| The background thread under a slow disk or processor | | **not measured**; its trigger is by events, not time, so that the order holds anywhere |

## 9. Rejected alternatives and corrections

| What | Why it was rejected or corrected |
| --- | --- |
| Shipping the pictures prebuilt (the state until 2026-10-27) | One size stretched over every screen: soft at most sizes (issue 68) |
| Drawing at install time, for every resolution | About 3 s and 8 to 10 MB per resolution for the Layout alone, 66 resolutions; and the controller patch works without KMRP's installer, whose code may not write controller art (the maintainer's rule). The maintainer chose the background thread |
| **Correction, 2026-10-29:** assuming KMRP's HUD-size INI section is absent without KMRP | Saved settings can remain after removing KMRP. The controller now requires `kmrp.dll` before reading those sizes; its standalone standard sizes are verified even with nondefault saved values |
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

### Pazaak gameplay action strip (2026-10-29)

`K1NativeJoystick.cpp` `UpdatePazaakActionStripK1` uses the live panel and the
`BTN_XTEXT` and `BTN_YTEXT` extents. Two `CSWGuiActivatedButton` instances cloned from
`BTN_XTEXT` carry strings 32330 (Play Hand Card) and 32331 (Flip Hand Card), with
X and LB badges. Existing controller handlers perform the actions; the added
buttons are excluded from controller focus. The row is Play, Flip, End Turn, Stand.

For End Turn left `E`, its gap `G` to Stand, and source button left `L`,
width `B`, the mirrored left is `2*E - G - L - B`. This continues the
existing pitch to the left, avoiding overlap at the panel midpoint. Read from the gold 3440x1440 layout with
`tools/dump_gui_extents.py`: End Turn is `(1704,1233,645,84)`, Stand is
`(2354,1233,645,84)`; the new Play and Flip boxes are `(404,1233,645,84)` and
`(1054,1233,645,84)`.

The loaded panel texture is read back through `K1CaptionInk`. In rows from the
player hand's bottom (or End Turn's top, whichever is earlier) through End Turn's
bottom, with a one-layout-pixel rim, each left-half texel copies the right-half
texel reflected across that same gap midpoint. Other texels are copied unchanged. The result is written to
the controller module's private texture folder. Switching to mouse input restores
the original fill and the PC flip legends. The game's source texture and GUI file
are not overwritten. No executable bytes or hooks change.

Correction to the previous Pazaak presentation: Play was placed below the flip
legend, which provided no matching left button strip. Both actions now occupy
mirrored button boxes on the same row as End Turn and Stand. At the first build,
in-game appearance, mouse switching and play were **untested**; final verification
is recorded below. To verify: open a table with the
controller, check all four captions and badges, play and flip a hand card, end the
turn and stand, then move the mouse and check the PC layout returns.

Follow-up correction (2026-10-29): the maintainer's first play-test showed the
four-part row, but Flip did not work, its caption stayed enabled, the small flip
control remained visible, and the new pair did not flash. The new pair had been
made as ordinary `CSWGuiButton` objects. They now use `CSWGuiActivatedButton`, as
End Turn and Stand do: 0x1D4 bytes, vtable VA 0x00753120, timer +0x1C4 initially
-1, flash colour +0x1C8. The matching source is
`matching/src/m/sw_gui_pazaak_card.cpp` in `swkotor1-reconstruction`.

Addresses below are VA in the unencrypted GOG executable
`build/controller-standalone/game-gog/swkotor.exe`, SHA-256
`9C10E0450A6EECA417E036E3CDE7474FED1F0A92AAB018446D156944DEA91435`.
The calling conventions and timer offsets were checked by disassembling its bytes
with Capstone; REA did not recognize these function entries in its analysis.

| Native routine/data | VA | Use |
| --- | --- | --- |
| Hand card right-click | 0x0067DD80 | `thiscall(panel, card)`, `ret 4`; saves active control, sets it to the card, calls 0x0067DCF0 and restores it |
| Activated button SetColor | 0x0067CA50 | `thiscall(button, colour)`, `ret 4`; stores 0.8 in timer +0x1C4 and copies 12 colour bytes to +0x1C8 |
| Activated button Draw | 0x0067CB70 | advances the timer and pulses the caption, then calls the ordinary button Draw |
| Activated button SetEnabled | 0x0067CC90 | native enabled/disabled caption colour, preserving an active flash |
| Pazaak flash colour | 0x007A23CC | same colour used by End Turn and Stand |

From `matching/src/m/sw_gui_pazaak_game.cpp`, the focused hand card is flippable
when its value (+0x304) is 12 through 17. The new Flip caption follows this
condition and the existing focused-card/mode guards. Its action calls the native
right-click routine directly, independently of the small flip button's visibility,
and flashes only if the card's flag at +0x308 changes. Play requires state 3, mode
0 and a nonempty focused hand card, then calls the existing click handler and flashes.
These are static source findings; the cause of the first build's failed flip was
not observed in a debugger.

Each of the four mouse flip controls keeps its native state and gets a private
40-slot copy of the ordinary button vtable, changing only Draw (slot +0x38).
Controller input skips that draw; mouse input calls its original Draw. This also
covers `RefreshDisplay` making a flip control visible inside the panel's Draw,
after the module's frame update. Original vtables are restored at teardown if the
private table is still installed. No global hook or executable byte changes.

`python testing/regression/Test-PazaakActions.py` compiles the production handlers
against native-layout mocks: 4,092 combinations of four hand positions, card values,
hand modes and game states; invisible/blocked cards and missing focus; flipping
while all small flip controls are hidden; accepted-action flashes; controller draw
suppression and mouse draw delegation. It substitutes only engine entry points.
The mock alone does not prove the live game invokes LB or that the animation looks
correct. This follow-up was awaiting play-test; the later results are recorded below.

Second play-test correction (2026-10-29): the maintainer confirmed the button
effect works, but Flip never appeared gray and playing a flipped card overwrote
the Play area. Level 2 log snapshots record the added Flip (control 75 at
1054,1233,645,84) changing between low flags `0x0E` and `0x06`, so selectable bit
`0x08` does clear. For example, ticks 88815406 and 88822390 show enabled then
disabled. The logs contain no caption RGB or screenshot, so they do not establish
the rendered color. The GOG bytes above give both native disabled color constants
(VA 0x0078D3B4 and 0x007A2408) as `(0,0.33,0.49)`, still cyan, while enabled
Pazaak text is `(0,0.66,0.98)` at VA 0x007A23B4.

`SetPazaakActionEnabledK1` now sets disabled captions explicitly to `(0.5,0.5,0.5)`
through `CSWGuiTextParams::SetColor` (VA 0x00414E10), and `KmrpPromptDimK1` sets
the separate badge label's border COLOR to `(0.4,0.4,0.4)` (white when enabled).
An invalid Flip cancels a previous card's flash timer. Play keeps the accepted
press flash even though consuming the card immediately disables it.

The native `RefreshDisplay` sets both PC legend draw flags from `bAnyFlip`. It
can run after the module's frame update, including while playing/flipping cards.
The four small flip buttons and **both** PC legends now share the mouse-only draw
policy (six controls; separate 40-slot button and label vtable copies). Their
native visibility flags are left intact, so mouse input draws exactly the state
the engine keeps. This removes the code path that could redraw the old Flip
legend over the new Play box; the reported overwrite was not captured in a
debugger. The regression additionally checks gray captions, badge dim/restore,
flash cancellation/preservation and refresh-visible legends. This intermediate build
was awaiting live recheck; the later results are recorded below.

Hand-slot focus correction (2026-10-29): the next play-test showed no highlighted
card at entry, followed by correct enabled actions after moving to the first card.
Level 2 logs show panel 0x07FEFC38 opening at tick 91776421 with active control
0x07FF6884, its End Turn at panel +0x6C4C; tick 91781750 records the first right
move to 0x07FF2A18, its first hand slot at +0x2DE0. These are heap addresses from
that run, not fixed game addresses.

`EnsurePazaakHandFocusK1` now restores a controller cursor to a hand slot whenever
the native active control is outside the four slots. Its initial index is zero;
an already selected slot, even empty, is preserved. `NavigatePazaakHandK1` handles
left/right as `(index + step + 4) % 4`, including empty slots, and consumes vertical
movement. It runs before the generic spatial navigator. An accepted Play remembers
and restores its slot after the native handler. Mouse input, another panel on top
(including tutorial/quit dialogs), and nonzero native hand mode prevent the focus
repair. Returning to controller input or from a modal restores the remembered slot.

The matching `sw_gui_pazaak_game.cpp` shows why slot navigation is separate:
`ReconnectSidedeckButtons` (VA 0x0067DA30) links occupied cards, and
`SetHandEnabled` (VA 0x0067DBB0) selects End Turn on leaving native hand mode.
Focus uses `CSWGuiPanel::SetActiveControl` (VA 0x0040A630), which sends the old
and new controls their native focus events without a selectability test. Empty
slot focus does not authorize playing it: `PazaakHandActionEnabledK1` and the
action guards still require a nonempty card for Play, value 12 through 17 for
Flip, mode zero, and the native player-turn state for Play. An accepted Play
finishes its short press flash before its disabled gray caption settles.

The production mock regression now also covers initial End Turn focus, first-slot
selection, a nonflippable card enabling Play alone, consumption clearing native
focus and restoring that empty slot, both actions disabled on empty, navigation
back onto empty slots, vertical movement, modal return and mouse isolation. These
tests verify controller logic without a game.

Final verification (2026-10-29): after testing the hand-slot build in the Steam
game at 3440x1440, the maintainer reported "works flawlessly" and authorized its
commit and push. Module `build/controller-standalone/kmrp-controller.dll` is
2,586,112 bytes, SHA-256
`985656DD1B8B108D2EB9CCA98142F4924980811FF7E6F0F033D49F7C985EA8F3`.
The installed module was re-read and its manifest row updated to that hash.
`Test-PazaakActions.py`, `Test-ControllerKpatch.py` and the documentation link
check pass. Other resolutions and controller families remain **not play-tested**.

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
6. **Preload ownership and standalone sizes.** Build the controller files first with
   `src\controller-native\build_controller_standalone.cmd`, then run
   `python testing/regression/Test-ControllerPreload.py --game "C:\path\to\game"`.
   It needs the game's `chitin.key`, data and GUI texture pack, the generated controller
   files, and `build/kmrp/resources/gui-3440x1440.zip` plus `override-common.zip` for the
   optional-core fixture (`--controller-files` and `--resources` override these paths).
   The local production-worker, HUD policy and Pazaak regressions pass, as do both
   module builds, both package checks and documentation links. This is automated
   verification; native renderer collection and preload timing still need a play-test.
