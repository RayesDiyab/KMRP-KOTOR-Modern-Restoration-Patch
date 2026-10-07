# KMRP for macOS: parity with Windows

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: tracker.** The goal, set by the maintainer on 2026-09-29, is a Mac build that
cannot be told apart from Windows at the same resolution. This lists every change KMRP
for Windows makes, from [`reverse-engineering/binary-inventory.md`](../reverse-engineering/binary-inventory.md)
(68 code and data runs, 11 added sections, 12 runs written at install), with its state
on the Mac. A row is **done** only when the Mac behaves the same in play, and says how
that was checked. The other direction -- what the Mac did first and Windows still needs --
is [`docs/windows-changes-from-macos.md`](../docs/windows-changes-from-macos.md).

## How the Mac build gets there

**Who does what changed after this section was written** (state on 2026-10-08;
[`README.md`](README.md), section 1, has the present arrangement). The rows of the table
further down name the code that first ported each Windows site, and what was seen with it.
Since 2026-10-04:

- the menu set, fonts and artwork are inside KMRP's module, which registers them with the
  game when it starts and blends a set for a size without one; the installer writes nothing
  into the game's override folder, and "the installer" and "at install" below describe the
  builds before that day;
- the resolution is chosen in the game, and the sites that depend on it are written again
  when it changes;
- the sites listed as `kmrp-layout`'s (`resolution_sizes.cpp`, `listbox_padding.cpp`,
  `area_map.cpp`, `popup_fit.cpp`, `granted_popup.cpp`, `dialogue_replies.cpp`) are written
  by FTD's Widescreen Patch in its `.gui` mode, which took them over; `kmrp-layout` keeps
  the code and `Test-KmrpLayoutPatch.py` checks it, but it does not write them while that
  patch is installed (measured that day: 41 of 53 sites byte for byte the same, 11 through
  that patch's own stub, 1 by another route). What was seen in play with `kmrp-layout`'s
  own writes has not all been seen again since: `README.md`, section 10, says what has;
- `UseGuiFileLayouts` is not written to `swkotor.ini`: KMRP's module asks the Widescreen
  Patch for that mode through an entry point.

And since 2026-10-07 the controller is a patch of its own (`README.md`, section 7a).
FTD's two patches are built unchanged from the KotOR Patch Manager tree given to `build.sh`;
the entry points KMRP uses are upstream since 2026-10-05 (LaneDibello/Kotor-Patch-Manager#319,
merge commit `7546ae5`). The submodule named below is the pin of 2026-09-30 and is no longer
what the build takes them from (`README.md`, section 9).

The first Mac build laid menus out with FTD's widescreen patch, which scales the
vanilla `.gui` files at runtime to a centred 4:3 canvas and sizes lists, fonts and
the HUD with its own calibrations. That works, but it is not what Windows does, and
the differences are visible: side bars, KMRP's 2:1 menu art squeezed to 4:3, five
large inventory rows where Windows shows eight, no feats-and-powers row fix.

Windows gets its look from three things, and the Mac build is moving to the same three:

| | Windows | Mac, target |
| --- | --- | --- |
| Layout | KMRP's per-resolution `.gui` set in Override (High Resolution Menus plus KMRP's edits) | the same archive, for the Mac's resolution; the 17 Mac resolutions are derived by `tools/derive_resolution_gui_set.py` (see `docs/universal-resolution-math.md`) |
| Text | a font atlas set baked at `max(1, H / 720)`, metrics at that scale | the same atlases from the same archive, with runtime font scaling off |
| Engine | the gold delta plus per-resolution fields written by the installer | the widescreen patch (resolution, K1–K9) with `UseGuiFileLayouts=1`, plus KMRP's `kmrp-layout` patch for the rest of the table below |

**KMRP builds on the widescreen patch** (decided 2026-09-29, replacing an earlier decision
the same day that KMRP should ship a Mac patch of its own). The widescreen patch, with the
engine fixes KMRP contributed to it (the submodule `third_party/Kotor-Patch-Manager`, FTD's branch `widescreen-patch`, merged there as
[FTD516/Kotor-Patch-Manager#1](https://github.com/FTD516/Kotor-Patch-Manager/pull/1) on 2026-09-29), is
the base: KMRP ships that version, and installs it when the player does not have it. What
goes where:

- **The widescreen patch** carries what does not depend on KMRP's layouts: the resolution
  (including Retina modes, K9) and the engine fixes K1–K8. One setting,
  `UseGuiFileLayouts=1`, which KMRP's installer turns on, stops its own menu layout: it then
  recentres at the full screen, loads the HUD file KMRP's Windows executable loads
  (`mipc28x6`, or `mipc210x7` at 3440x1440), and scales no menu, row or font itself.
  Checked in game at 1512x982 (windowed) and 3024x1964 (fullscreen) with KMRP's sets.
- **`macos/patches/kmrp-layout`** carries what KMRP's layouts need from the engine, as KMRP's
  Windows executable does: the sizes its installer writes per resolution (rows, stack
  label, chain rows, and still to come: popups, the area map) and the list-box `PADDING`
  fix of gold v11. Its module writes the resolution-dependent sites at start-up after
  checking their bytes; shared navigation handlers use KPM hooks (`testing/regression/Test-KmrpLayoutPatch.py`).
- **The installer** writes what Windows' installer writes as files: the `.gui` set for the
  resolution (derived when unlisted), and the enlarged feat, power and skill icons
  (`macos/tools/kmrp-abilityicons.c`, byte-identical to `AbilityIconGenerator.cs`,
  `testing/regression/Test-AbilityIcons.py`).

### Resolutions the build has no set for

The installer reads the display's size (pixels for native, points for half). A listed
size gets the built archive, the same files Windows installs. An unlisted size is derived
at install: a helper blends the **finished** KMRP sets around it, the same weighted blend
the build uses on upstream, so KMRP's layout logic still has one implementation (the
build). The finished `.gui` files have identical byte layouts at every resolution (all 83,
checked at seven resolutions from 800x600 to 3440x1440), so the helper writes numbers into
a template. Fonts and per-resolution art come from the nearest listed size.

Measured 2026-09-29 by hiding each finished set that has neighbours (45) and predicting it
from the others: 2,037,074 numeric fields, 97.27% exact, 99.89% within 1 px. In the files
the Mac loads, 78 fields were further off across 19 targets, all list scrollbars (up to
6 px) and one padding: those positions come from the 3440x1440 geometry the build carries
over, which is not linear. Blending them relative to the list's right edge did not help
(73.2% exact against 78.2%).

**Two files are made, not blended** (2026-09-30). *Corrected:* the paragraph above said
KMRP's layout logic has one implementation, the build. Two files are laid out by rules no
blend reproduces, and the helper now applies those rules itself, with the fonts of the
set it installs (`macos/tools/kmrp-guiblend.c`, table version 2):

| File | Rule | Blended, held out | Made at install, held out |
| --- | --- | --- | --- |
| `container.gui` | widened, in some sets, until "Switch To Give Item" and its badge fit (`fit_container_to_caption`) | 74 fields off by more than 1 px, up to 21 | 491 of 493 within 1 px |
| `kmrplayout.gui` | generated from its panel's size and the caption font (`build_gui`) | 241 fields off, up to 32 px | 3,162 of 3,162 within 1 px |
| the lists made as tall as whole rows (`container.gui`, `skillinfo.gui`, `ftchrgen.gui` and five more; table version 3 on this branch, 4 since the merge into `master`, 2026-09-30) | fitted to whole rows at the size's own row heights (`fit_list_to_rows`, `docs/windows-changes-from-macos.md`, item 14) | the 17 Mac sets 99.80% within 1 px, worst 41 px (the Feats list); the Container 417 of 493 | 99.90%, worst 12 px; the Container 491 of 493 |

The table carries the Container unwidened, with each set's widening from its prompt
manifest, each fitted list as it was before its fit (the manifest's `fitted` lines), and the generator's 53 constants by name with its 13 rows, so the helper keeps no
numbers of its own. Its arithmetic is a second copy of `build_gui`'s, kept honest by
`Test-GuiBlendHelper.py`: at 24 derived sizes the helper's file equals what `build_gui`
itself makes from the same blended Gameplay panel and font, byte for byte, and every one of
the 45 anchors the blend resolves to itself comes out as the build's set, byte for byte. The
Intel and Apple Silicon slices write identical files. The 17 Mac sets, each held out and
made from the others with its own fonts: 151,946 fields, every file counted, 99.90% within
1 px, worst 12 px, in a HUD variant the Mac does not load.

**And the badges and the HUD's boxes are drawn for the size** (2026-09-30, table version 3 on
`master`, 4 since the merge,
[`docs/macos-changes-from-windows.md`](../docs/macos-changes-from-windows.md), items 1 to 3).
The paragraphs above left the "art" of the nearest set in place, and two kinds of it depend
on the buttons: each controller badge is a texture stretched over its whole button, drawn to
be round on the button it was made for, and `lbl_mileftbot.tga` draws a box under each of the
HUD's eight top-right buttons. From the nearest set a badge came out up to 1.86 times as wide
as tall (3440x1400, whose nearest set by height is 1856x1392). The helper now draws both from
the blended files, with the build's arithmetic (Pillow's Lanczos for the badges), and the
Windows installer does the same byte for byte. Only the fonts still come from the nearest set.

## The table

States: **done** (behaves as on Windows, checked as stated), **to port**, **n/a**
(with the reason), **check** (may not apply; not yet established).

### Resolution and recentring

| Windows | What | Mac |
| --- | --- | --- |
| `0x0040AA65`, `0x0040AA85` | render width and height | K4 (video mode follows the target), K9 (Retina modes); separate from the menu whitelist below |
| `0x005F0C65`, `0x005F0C6F` | resolution menu acceptance | **done another way since 2026-10-04**: `KmrpResolutionKnown`, a detour at the head of the Mac's `IsKnownResolution` (`0x10026f1ee`), accepts a size when KMRP has menus for it and, since 2026-10-08, the display reports a mode of it, as Windows' `DisplayReports` does (`README.md`, "The resolution chosen in the game"). From 2026-10-02 to 2026-10-04 `kmrp_layout.cpp` wrote the one configured W/H into the first pair of comparisons at `0x10026f1f2` / `0x10026f1ff` (user-tested at 1920x1200; guarded at 76 resolutions; [audit](../reverse-engineering/macos-resolution-port-audit.md)); those bytes are inside the detour now and are not written |
| `0x00403D6C`, `0x00403D78`, `0x005F5B3B` | movie display mode | **n/a**: Aspyr's Bink player switches no display mode (checked in play, 2026-09-28) |
| `0x0040B6C7`, `0x0040B6DA`, `0x0040BA6C`, `0x0040BA83` | recentring references `-W`, `-H` | **done**: the widescreen patch with `UseGuiFileLayouts=1` writes `-W`, `-H` at its 20 sites. Clicks land on KMRP's menus at 1512x982 and 3024x1964 (2026-09-29) |
| `0x0068C4E3`, `0x0068C4F4` | HUD resource selector (which `mipc*.gui` loads) | **done**: the same switch points all five `lea` sites of the `CSWGuiMainInterface` constructor (`0x100233429` … `0x1002334d8`, the only references to the names) at `mipc28x6`, or `mipc210x7` at 3440x1440. The HUD and minimap drew KMRP's layout in both runs |

### Text

| Windows | What | Mac |
| --- | --- | --- |
| `.kfs` font floats, `0x0045A850`, `0x004A1770` | runtime font scaling (inert since the atlases carry the size) | **done** as "off": with `UseGuiFileLayouts=1` the widescreen patch scales no font; KMRP's atlases carry the size |
| `0x006A74D4` … `0x006A8E1D` (8 runs, `font.md`) | dialogue letterbox bars `H/6` and the reply box (`.klb` trampolines) | **done**: K7, the same `H/6` bar through the `2H/3` aspect float in the widescreen patch, and `LB_REPLIES` stretched to the reply panel (by KMRP's layout patch since 2026-09-30, `dialogue_replies.cpp`, when the widescreen patch dropped its hook). *Corrected 2026-09-29:* listed here as "text placement inside controls" and marked **check**; `font.md` places these runs under the letterbox, not text placement |
| `0x00415E0D`, `.ktn` | leading newline | **done**: K3 |
| `0x0045A5E0`, `.kwl`, `0x0045A3B7`, `0x0045A3DC` | word-wrap progress, short-string guards | **done**: K1 |
| `0x006B5336`, `.ksc`, install `0x006B5332` | stack-count label, 19s / 21s / 37s | **done in code, not yet seen in play** (no stack in the test save's first rows): `kmrp-layout` rewrites the label block `0x1002be4a0` (50 bytes) with 32-bit operands, as `.ksc` does. The store row's label follows its icon (`0x1002bfbc0`); Windows leaves the store's label at vanilla size |

### Lists and rows

| Windows | What | Mac |
| --- | --- | --- |
| `0x00417992`, `.kfs` row float | text-list row height `s` (save/load, journal, resolution popup) | **done** (`kmrp-layout`, `resolution_sizes.cpp`): `CSWGuiButton::Initialize` (`0x1004a59e6`), the template-row setup 12 row classes share, copies the rect at `0x1004a5a05`; a stub scales the height by `s` there, rounded as the x87 code rounds. The save list's and the journal's rows grew in play at 3024x1964 (2026-09-29). Also reached from the area map's overlay constructor, which overwrites the rect afterwards |
| install `0x006B4FA9`, `0x006B527F`, `0x006B55E3` | inventory icon and row height `56s` | **done** (`kmrp-layout`): icon `0x1002be441`, height `0x1002be870` (the Mac's only source of the row height), text offsets pointed at the icon register. 153 px rows at 3024x1964, seen in play |
| install `0x006C265F`, `0x006C2A23` | store icon and row height `56s` | **done in code, not yet seen in play**: height `0x1002bff6d`; the icon follows it through the widescreen patch's hook at `0x1002bfb49` |
| install `0x006AB8EF`, `0x006ACB20` | skills icon and row height `50s` (vanilla 42; `42s` until 2026-09-30, `docs/windows-changes-from-macos.md`, item 15) | **done** (`kmrp-layout`): icon `0x10022f256`, height `0x10022f60b`, text offsets pointed at the icon register. Seen in play at `42s`; `50s` not yet |
| install `0x006CD8D9`, `0x006CDB79` | feats and powers chain rows `50s` (vanilla 40) | **done** (`kmrp-layout`): both chain-row creators (`0x10028d7bc`, `0x10028dc90`) load one rect, `{0, 0, 242, 40}` at `0x100570ef0`, read by those two only; its height `0x100570efc` is written. Seen in play |
| `AbilityIconGenerator.cs` (install) | feat and power icons enlarged to the chain row's icon box; skill icons to a canvas of `round(32s x 50 / 42)` (new on both platforms 2026-09-29 as `round(32s)`; from 50 since 2026-09-30, with the skill rows at `50s`), with the picture `round(0.62 × 50s)` inside it, moved to the frame opening's centre, so it fits the frame (both platforms, 2026-09-29) | **done**: `macos/tools/kmrp-abilityicons.c`, byte-identical to the C# at 10 heights, run by the installer. With it the icons fill their frames at 3024x1964, as on Windows; without it they stayed 32 px in 136 px frames (seen 2026-09-29) |
| `GameArtGenerator.cs` (install, 2026-09-29) | the hex row frames (`56s`), the tutorial popup's `tut_*` icons (`64s`) and `tutorial.2da`, made from the player's game; the build shipped them until then | **done**: `macos/tools/kmrp-gameart.c`, byte-identical to the C# at 48 heights (`Test-GameArt.py`), run by the installer |
| `0x0041A2F2`, `0x0041B1C4` … `0x0041B553`, `.klb` | list-box geometry (horizontal-only padding) | **done** (`kmrp-layout`, `listbox_padding.cpp`): the six `PADDING` reads in `OrganizeControls` (`0x1004a82b4`). The inventory went from 6 rows with gaps to 7 without at 3024x1964 |
| `.kgs` | the gutter follows the scrollbar, in both row builders | **done** (`listbox_padding.cpp`): both builders (`OrganizeControls`' block `0x1004a8838`, and `0x1004a936e` for content taller than the box) jump to stubs that put the left edge at `PADDING` only with `LEFTSCROLLBAR` (bit `0x10` of `[listbox+0x370]`). The skills and journal description panes lost their left gutter in play (2026-09-29) |
| `0x0041B507`, `0x0041B52E` | list rows stop growing | **done**: K2 |

### Popups

| Windows | What | Mac |
| --- | --- | --- |
| `0x0062540D`, `0x006256DC`, `0x006256F6`, `0x00625759`, `0x00626F95`, install `0x0062540E`, `0x00626F96` | message popup auto-fit caps `450s` / `800s`, icon rect and inset `64s` | **done in code** (`resolution_sizes.cpp`): the four cap tests in `FixMessageLabel` (`0x100306877`, `0x10030687f`, `0x10030688b`, `0x1003068fd`; two compiled as `>=`), the icon offset `0x1003065a1` and the icon's rect `{0, 10, 32, 32}` at `0x100571bb0`. The quit confirmation drew in play with narrow OK and Cancel buttons: the popup auto-sizes buttons from 100 px to fit their label, as Windows' code does at `0x006254AC`, so Windows should look the same; **not yet compared with Windows**. Tutorial popups not yet seen. **Corrected 2026-10-02:** `kmrp-gameart.c` already generates the `tut_*` icons and `tutorial.2da`; the earlier exclusion warning was stale |
| `FitMessageBoxK1` at `0x006258E2` (`src/controller-native/K1PopupFit.cpp`, since the same evening) | the message popup fitted to its contents | **done on both** (2026-09-30, `popup_fit.cpp`; Windows' seen at 3440x1440, `docs/windows-changes-from-macos.md`, item 1): the message narrows to the least width that keeps its line count and shrinks to its text, the buttons follow it, the panel fits around it with the message's margins, and it keeps its centre. The Exit Game box went from 1,224x711 px to about 880x365 at 3024x1964; the Attributes, Skills and Feats tutorials and the unspent-points box seen fitted in play the same day. Windows the same since the same evening |
| `0x006DE012`, `0x006DE031`, and `0x006DE08E` with the function's padding at `0x006DE0D1` (Windows since the same evening; `docs/windows-changes-from-macos.md`, item 13) | the Options check boxes: circle, label offset and drop scaled | **done** (2026-09-30, `resolution_sizes.cpp`; the Feedback list's rows grow with them since the same evening, shared build code, `docs/macos-changes-from-windows.md`, item 11): `CSWGuiOptionsCheckbox::SetExtent` (`0x1002cecee`) replaced by the same layout at `25s`, `30s` and `2s`, a 68-px circle at 3024x1964; checked against the binary, not yet seen in play (`docs/windows-changes-from-macos.md`, item 13) |
| `GrantedPopupFilledK1` at `0x006CE0B0` and `GrantedRowTextK1` at `0x006AB9D5` (`src/controller-native/K1GrantedPopup.cpp`, since the same evening) | the granted popup's rows (`skillinfo.gui`: "You have been granted the following feat(s) this level.") | **done on both** (2026-09-30, `granted_popup.cpp`; Windows' seen at 3440x1440 with one row, item 10): the text inset by an eighth of the row, the hex, highlight and icon grown by a seventh so the hex spans the text frame, and the list cut to its rows at a pitch of the row plus an eleventh (the inventory's list spreads 8 to 10%), with OK and the panel following and the popup centred. At 3024x1964: rows 141 to 125 px apart, hex 97 to 111 px beside a 111-px frame, text 2 to 14 px inside the frame. Windows the same since the same evening |

### Area map and minimap

| Windows | What | Mac |
| --- | --- | --- |
| `.kui`, `0x0068ACA1`, `0x006928B3`, `0x006928C3`, `0x006944A8`, `0x006944C4`, `0x0069505C`, `0x00695082`, `0x0075477D` | area-map canvas, marker overlay, centring, fog grid, hit test | **done** (`kmrp-layout`, `area_map.cpp`): canvas `round(W/2 · 512/440)` x `H/2` and overlay `W/2` x `H/2` in the map screen's two rect constants (`0x100571390`, `0x1005713a0`); centring at the screen by the widescreen patch's switch; the fog grid by its hooks at `0x1002b4ce9`/`cfc`. The three position conversions in `CSWGuiMapHider::Draw` go through stubs that rescale to the overlay as Windows' wrappers do. The map filled KMRP's frame with the markers on the corridors at 3024x1964 (2026-09-29). The hit-test wrapper (`0x0075477D`) has no Mac counterpart, since the widescreen patch's `-W`/`-H` in `HandleMouseInput` already match `Draw`: clicking two notes at 3024x1964 selected each (2026-09-29) |
| `0x0069405B`, `0x006940DC`, `0x006946F6`, `0x0069471A`, `0x00694763`, `0x00694777`, `0x00694A13`, `0x00694A3A`, `0x00694A53`, `0x00694AAD`, `0x00694AC4`, `0x00694AD0` | map note, party marker and arrow sizes and centring | **done** (`area_map.cpp`): every size and centring offset by `min(s, 127/16)`; the arrow's 32 has three Mac copies (rect and draw viewport), written together; `mm_barrow`'s rect (`0x1005713c0`) directly; `lbl_mapcircle`'s rect is shared with the HUD, so the map's read is pointed at a private copy. Seen in play |
| `.kmz` (`0x0045992A`), `.kfg` | HUD minimap zoom and fog grid | **done**: K8 |
| `0x0062B39B` | minimap constructor wrap | **n/a**: on Windows the minimap shares the map's constructor and would inherit its new sizes. On the Mac the rect constants are read by the map screen's constructor (`0x1002b3930`) only, which the HUD does not build; the minimap drew right with the map enlarged (2026-09-29) |
| `.kmn` | map-note corrections | **done**: the `kmrp-map-notes` patch |

### Dialogue and movies

| Windows | What | Mac |
| --- | --- | --- |
| `0x00755788` | dialogue letterbox (`.klb` sites) | **done**: K7, the same `2H/3` rule. Seen with KMRP's layout at 3024x1964: bars a sixth of the screen each, three replies in the bottom bar (2026-09-29) |
| `.kmv`, `0x004057AC` | movie aspect fit | **n/a**: Aspyr's Bink player pillarboxes (checked in play) |

### Controller

The Windows controller module (`src/controller-native/`) is a module with hooks, not part of
the gold delta; its Mac port is `macos/patches/kmrp-controller` (`README.md`, section 7),
a KotOR Patch Manager patch of its own since 2026-10-07, with Windows' Xbox-style HUD and
badge overlays ported the same day (`README.md`, section 7a, which says what was seen).
*Corrected 2026-09-29:* this was one row under *Windows only*, first saying the Aspyr port has
its own controller support, then **not ported**. KOTOR I on the Mac has none that works: a pad
did nothing in play, and Aspyr lists controllers for KOTOR II on the Mac only.

| Windows | What | Mac |
| --- | --- | --- |
| `K1NativeJoystick.cpp` | the pad into the engine's joystick chain; walking, the camera, L3, Start, R3, A on the target; the menus' focus, remaps, echo and confirm guards; movies; the action bar | **done**, with SDL 3.4.16 as on Windows. Played with a scripted pad and with the maintainer's pad (2026-09-29). The confirm guards in character generation, Solo Mode and resolution: **not yet played** |
| the same, prompts and GUI cues | button prompts in the pad's family, hidden on mouse and keyboard use; the parked cursor; the cues | **done**: PlayStation art in play; the other three families not yet seen. The cursor is not confined to the window (macOS has no equivalent of `ClipCursor`) |
| `K1Rumble.cpp` | one mixer for BioWare's patterns, the cut ones and KMRP's | **done** for the saber (read in `rumble.log`); combat events and a real pad's motors **not yet tested** |
| `K1ControllerLayout.cpp` | the Controller Layout screen and its Gameplay entry; the confirm and dialogue A; the status summary's layout and A (the layout without the controller too: `kmrp-layout/status_summary.cpp`, `StatusSummaryFrameK1`'s counterpart, 2026-10-02) | the screen and the confirm A **done** (played 2026-09-29); the status summary's layout seen in play with the controller (2026-10-01); the dialogue A, its A and the layout without the controller **not yet seen in play** |

### Windows only

| Windows | Why not on the Mac |
| --- | --- |
| PE header, Large Address Aware | the Mac build is 64-bit |
| DPI, NVIDIA and driver settings | Windows code (see `README.md`, section 8; whether the Mac needs a lighting fix like K1DC's is not yet checked) |

*Corrected 2026-09-29:* this table listed `0x0045992A` as a texture-residency measure. It is the
HUD minimap's content zoom (`.kmz`, `reverse-engineering/map-scaling.md` §3), done by K8 and now
listed under *Area map and minimap*.

## Done so far

- **2026-09-29.** `macos/patches/kmrp-controller`: the Windows controller module ported, 21
  hooks and ten sites written at load (`README.md`, section 7), with SDL 3.4.16 shipped as
  `kmrp-sdl3.dylib` and KMRP's controller art installed. Committed as `0d147a1`.

- **2026-09-29.** The package and installer carry it all: `build.sh` stages the widescreen
  patch, `kmrp-map-notes` and `kmrp-layout` through KPM's KPatchCore (no overlapping hooks),
  pools every resolution's set (`layouts.zip`, 86.7 MB, the Windows installer's pool
  format), and adds `gui-blend.bin`, `kmrp-guiblend` and `kmrp-abilityicons`; 160 MB zipped.
  `kmrp-mac.sh` writes `UseGuiFileLayouts`, `ForceWidth`, `ForceHeight`, installs the
  size's set or a blended one, and the enlarged icons. Installed on the live game and
  played at 3024x1964 (see the rows above), then uninstalled to the previous state;
  `testing/regression/Test-MacInstaller.py` installs and uninstalls a listed and a blended
  size into a stand-in game.

- **2026-09-29.** `macos/patches/kmrp-layout`: every per-resolution size and gold change in
  the table that the widescreen patch's switch leaves undone. 48 sites, checked at 76
  resolutions by `testing/regression/Test-KmrpLayoutPatch.py`.

- **2026-09-29.** Deriving an unlisted display's set at install:
  `tools/build_gui_blend_table.py` packs the finished sets (83 files, 46 anchor sets in 5
  families, 8,938 varying fields, all 32-bit integers; 3.2 MB, 0.8 MB compressed), and
  `macos/tools/kmrp-guiblend.c` blends any resolution from it in about 20 ms.
  `testing/regression/Test-GuiBlendHelper.py`: the helper matches an independent Python
  blend byte for byte at 24 resolutions (after forbidding fused multiply-add, which rounded
  exact .5 ties differently on arm64), and the arm64 and x86_64 slices agree. Held out, the
  17 macOS sets come out 99.90% within 1 px (148,784 fields); worst 12 px, in a HUD variant
  the Mac does not load. Wired into the package and installer the same day (above).

- **2026-09-29.** The 17 Mac resolutions are in KMRP's build (`GROUPS["macOS"]`), derived
  from High Resolution Menus by a blend measured to reproduce upstream's own sets within
  1 px (`testing/regression/Test-ResolutionDerivation.py`), with a font set per new scale.
  The Windows launcher lists them under **macOS**. Not yet run on Windows.


## Port audit correction, 2026-10-02

The earlier resolution row combined rendering and menu acceptance and incorrectly
marked both complete. K4/K9 did not change the separate menu whitelist. The
[source comparison and live measurement](../reverse-engineering/macos-resolution-port-audit.md)
record the correction and remaining gaps. In particular, the Windows texture-bucket,
grass-buffer and save-buffer safety hooks were absent from this tracker. The
[memory-safety audit](../reverse-engineering/macos-memory-safety-audit.md) now identifies
implemented texture bounds/maximum protection and defensive grass alias checks.
Controlled machine-code tests pass; gameplay failure reproduction remains pending. Mac already frees the save-resource
buffer; adding that Windows free would duplicate cleanup.
The missing XP text at 1920x1200 also remained unresolved that day despite the earlier layout
attempt; neither a structural GUI audit nor a passing hook validator proved it fixed.
**Status, 2026-10-03:** the native-wrap and height repair that followed was confirmed in the
game at 1920x1200 (the audit's own status correction); other resolutions and popup wordings
were not looked at.
