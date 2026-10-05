# Changelog

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


All notable changes to KMRP are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

> **On the entries below.** This project was not git-tagged during its first
> week, so the versions here are reconstructed from the `PatchVersion` constant
> in `src/patcher/KmrpPatcher.cs` and the commit that introduced each
> one. **Dates are the date that constant changed, not a release date.** Where a
> version's gold snapshot is recorded in the build script it is named; for
> 2.0.0–2.5.0 the build script's default still pointed at an older snapshot than
> the documentation describes, so no gold snapshot is claimed for those. Going
> forward, tag releases so this stops being reconstruction. **2.10.0 is where
> that starts:** it is the first tagged version. The entries below it, 2.7.0 back
> to 2.0.0, are reconstructed; it and everything above it are not. (Until
> 2026-09-24 this said "every entry above it is reconstructed". Newest entries
> are at the top, so that had the direction backwards.)
>
> **Public names.** 2.10.0 is **KMRP 1.0**, and [Unreleased] is **KMRP 1.5**.
> The headings keep the internal `PatchVersion` numbers, because the 2.0.0
> hash record uses them. The 1.0 release is tagged `v1.0.0` since 2026-09-25,
> on the same commit. Until then its tag was `v2.10.0`, which remains as a
> plain tag; it moved because the installer's update check reads release tags
> as versions (see [Unreleased]). (Until that day this note also gave the tag
> as a reason to keep the internal numbers.)

## Everything the patch changes in the executable

The version entries below are a running record of *changes*, so they describe
each fix at the moment it landed and never in one place. This section is the
other view: **the complete set of differences between an unmodified
`swkotor.exe` and a patched one, in plain language**, so it can be read without
knowing the project's history.

It is kept honest by
[`reverse-engineering/binary-inventory.md`](reverse-engineering/binary-inventory.md),
which lists every byte position the installer changes -- the 721 where gold
differs from the clean executable and the 21 more it writes over values gold
leaves vanilla -- and refuses to pass if any run of them has no technical
write-up. If something appears there and not here, this section is out of date.

**The size of it.** KMRP's installer changes 742 byte positions inside the
original 4,042,752-byte executable, at one resolution or another — 0.018% — and
appends eleven new 4KB sections holding the code and data the original has no
room for, so every patched executable is 4,087,808 bytes. Nothing else in the
file moves. Measured on 2026-09-24 by running the installer (`ECA3DE4B…`) at all
48 resolutions.

**Where they are made.** Until 2026-09-29 the installer wrote them into
`swkotor.exe`. Since then it writes none of them to the file: the same bytes are
applied in memory each time the game starts, by KMRP's module under KOTOR Patch
Manager's runtime, from `kmrp-kpm.dat`, with the eleven sections at an address
of the module's choosing and every reference to them moved to match
([docs/kpm-edition.md](docs/kpm-edition.md)). On the editable build the file
gets only the large-address flag; Steam's is not changed at all. The table
below is unchanged: it describes the game that runs. `--apply` still writes the
whole patched image to a new file, and it is what the in-memory result is proved
against.

*Corrected 2026-09-24:* this section said 702 positions and ten sections, the
count before gold v24 added the movie aspect fit, and before the installer's
own output rather than gold was counted. It also lacked five of the rows below:
the movie aspect fit, the list gutter, the blank first line, the HUD minimap's
zoom and fog, and two of the resolution fields.

| What you see in game | What changes in the executable |
| --- | --- |
| **Text is legible at modern resolutions** instead of tiny. | Text size is carried on the font atlases' own metrics rather than scaled at runtime, because scaling it at runtime changed the size one frame *after* the engine had already measured and centred the text, which visibly shifted the first screen of each session. The executable keeps a scale constant for list rows, which are built after nothing has measured them and so have no such ordering problem. |
| **List rows grow with the text**, so save/load and dialogue entries stop overlapping. | A hook rewrites each row's height as the row is constructed. Rows never shrink below vanilla, so short screens are untouched. |
| **Inventory, Abilities and Store rows and icons are sized to match.** | Three separate hardcoded 56s decide the icon box, the text offset and the row height, none of them reachable from any `.gui` file. That is why editing the interface files alone never moved them. |
| **Item stack counts are visible again.** | Two guards blanked any string of one or two characters that did not fit its box, and the enlarged font made the fixed 21px stack label too narrow to pass them, so two-digit counts silently vanished. Both guards are removed, together with a fix to the line-breaking loop that they were the only thing protecting against. |
| **The game no longer crashes** on items with long descriptions. | The line-breaker's only guard compared against the start of the whole string rather than the start of the current line, so a line that could not break looped until memory ran out. |
| **Lists keep their gaps where they belong.** | Each list's `PADDING` byte did six jobs at once -- left and right inset, the first row's top, the row pitch and two fit tests -- so a gutter beside the text also spread the rows apart and pushed the list down. It is now a horizontal gutter only, on the scrollbar's side, in both of the engine's list-rect builders. |
| **Descriptions no longer open with a blank line.** | The game builds a description by prefixing a newline to each property line, so an item whose description starts with properties began with an empty line. Leading newlines are stripped as the text is set. |
| **Dialogue gets proper letterboxing** at any aspect ratio. | The bars are derived from screen height rather than assumed. |
| **The area map fills its frame**, at every resolution. | The map picture is drawn on its own canvas, separate from both the window and the marker overlay, and sized so its content fits the frame; the `LBL_Map` control crops whatever overhangs, as it always did. |
| **Fog of war covers the whole map** instead of stopping 242px short on the right. | The fog grid was stepped by a fixed constant while the map was drawn at a different width, so the last strip was never covered by any tile. Two instructions now read the live rectangle instead of that constant. |
| **Clicking a map marker hits the marker.** | The hit test recentred the map's canvas inside the window, but the control that positions it is placed by the overlay, and the canvas overhangs it. Clicks landed 141px to the right; eleven bytes were replaced with eleven, and it was measured live before and after. |
| **Map markers keep their size as the map grows**, and stay on their subject. | Note, party and player-arrow rectangles were built from the original hardcoded sizes while everything around them scaled. |
| **250 map notes point at the right place.** | Optional. A table keyed on each note's shipped world position substitutes a corrected one. It needs no hook of its own, because the code KMRP already redirects receives that position as its own argument. The corrections are Derslok's measurements, used with permission. |
| **The HUD minimap stays zoomed in on you**, however large it is drawn. | Vanilla sizes the minimap's map picture for a 120-pixel viewport, so an enlarged viewport showed a zoomed-out map. The picture is scaled by `viewport / 120` about the centre -- only when the viewport is square and the source is the map atlas, so nothing else that shares the draw is touched -- and the fog grid is scaled to match, or explored ground re-fogged as it left the middle. |
| **The HUD minimap is unaffected by the map work.** | The full map and the HUD minimap share one constructor. The minimap's call to it is wrapped, and the wrapper puts that one instance back to retail values — so the map screen can be resized without dragging the minimap with it. |
| **The process can use more than 2 GB of virtual address space on 64-bit Windows.** | The PE header's standard `IMAGE_FILE_LARGE_ADDRESS_AWARE` bit is enabled. No allocator or code path is changed. |
| **Full-screen movies stay in the selected display mode.** | KOTOR has two independent 640x480 mode pairs around Bink playback even though the renderer itself scales from the live client rectangle. Both pairs are rewritten per resolution, avoiding the forced legacy-mode transition. |
| **Movies keep their shape** instead of being cropped. | Retail scaled every movie by the screen width alone, so a 640x480 logo became 3440x2580 on a 3440x1440 screen and lost 1140 rows. The scale is now the smaller of the width and height ratios, in a small appended routine. The bars this leaves beside a narrow movie are painted black by KMRP's runtime, which installs on every patch since 2026-09-28; until then it came only with the optional controller component, and without it they showed whatever was on screen. |
| **Tutorial and confirmation popups fit their text** instead of clipping it. | The shared popup sizes itself from constants that never accounted for larger text. |
| **Interface elements sit where they should** at your resolution, not at 640x480. | Two shared helpers recentre almost every non-HUD screen using the resolution the interface was designed for. The patcher writes your actual resolution into them at install time, which is also why the reference build in this repository has one author's monitor baked in and the shipped executable never does. Two more width and height pairs get the same treatment: a centring subtraction that assumed 640 pixels, and a mode comparison against 800x600. |
| **The correct interface artwork is chosen for your screen.** | A chain of width comparisons picks a resource set; the first is redirected to your width and the later ones are disabled so they cannot win instead. |
| **Nothing else.** | The remaining changes are the PE header's own bookkeeping — the section count, the code and image sizes, a zeroed checksum, and the eleven new section headers. One casualty is worth naming: a leftover `Hellspawn Reborn` signature string sitting in the header's unused padding is overwritten by the fifth section header. Nothing reads it. |

**What is *not* changed in the executable**, though the patch installs it:
interface layout files, font atlases and icon artwork all ship as ordinary
`Override` files, and the bundled *K1 Modern Driver Compatibility* patches its
own process in memory at startup without writing to `swkotor.exe` at all.
KMRP's runtime is the same: its hooks are applied in memory from
`patch_config.toml`. It installs on every patch and always carries three memory
fixes from the KOTOR Patch Manager project, the movie bars, mouse confinement
and the status summary's layout; the controller's own hooks join them when
controller support is on. Since 2026-09-29 that runtime is KOTOR Patch
Manager's own, built from the submodule and loaded through KPM's `binkw32.dll`
proxy, and it applies the executable changes above as well.

## [Unreleased]

- **KMRP as two patches, its own and the controller patch it requires: first stage,
  on the branch `kmrp-two-patches` only** (2026-10-05). The maintainer decided that
  day that KMRP ships `KMRP.kpatch` plus the standalone controller patch ("KOTOR 1
  Native Controller Mod + Xbox HUD", id `kmrp-controller`) and no controller of its
  own, with the controller always installed. **This branch does not build a working
  installer and must not be released**: see "Not done" below.
  - *Done.* `KMRP.kpatch` has 22 hooks, no controller group and no `controller`
    option, and `requires = ["kmrp-controller"]`; its module's `g_controllerOption`
    is always off (`tools/build_native_kpatch.py`, `K1RuntimeEngine.cpp`). KOTOR
    Patch Manager allows one patch per address, so the GUI frame (`0x0040CE70`) and
    the movie frame (`0x00404D96`) are the controller patch's, and its module calls
    KMRP's share of each, `KmrpCoreGuiWorkK1` and `KmrpCoreMovieWorkK1`, which
    KMRP's module exports (`K1NativeJoystick.cpp`). The controller patch has its
    resource hook at `0x00407235`, two instructions into the function KMRP hooks at
    `0x00407230`; it no longer lists `kmrp` as a conflict; and beside KMRP it
    deletes its own copies of the game's layouts from its temporary folder, so that
    KMRP's scaled ones are used (`tools/build_controller_kpatch.py`,
    `K1ControllerStandalone.cpp`).
  - *Seen.* The two installed together by KOTOR Patch Manager 0.7.1's launcher in a
    scratch copy at 1920x1080: the main menu, all eight in-game tabs, the HUD, the
    pad, and the Xbox-style HUD's swap to KMRP's HUD with the mouse and back.
    `Test-ControllerKpatch.py` passes in the form it has on this branch.
  - *Not done.* The installer (`src/patcher/KpmEdition.cs`) still installs only
    `KMRP.kpatch`, still removes `kmrp-controller` as a retired patch and still has
    a Controller Support setting, so an install made from this branch has a patch
    whose requirement is missing (not run). KMRP's bank still carries its
    per-resolution badge textures under the controller patch's names.
    `Test-KpatchSource.py` fails on this branch (it validates the build's older
    patch), and `Test-InstallerPatch.ps1`, `tools/check_kpm_overlaps.py`,
    `docs/kpm-edition.md`, `docs/controller-standalone.md` and the README are not
    updated. Not run in the pair: a fight, a movie, any other resolution.
- **The Xbox-style HUD's frames are drawn, and its portraits are framed alike**
  (2026-10-05, the standalone controller patch). The HUD was dressed in the game's
  own HUD textures, 16 to 256 pixels across and stretched over a modern screen:
  soft lines, stair-stepped curves. The maintainer asked for a crisp HUD, looked at
  upscaled versions (bilinear, Lanczos, a pixel-art scaler, Real-ESRGAN and six
  community models) and at a hand-modelled speech icon, and chose: every icon stays
  the game's own, and the frames are redrawn.
  - *Seventeen frames, as geometry.* The slot box in blue and yellow, the slot
    arrows in both, the minimap's frame, the portrait's frame, the vitality, poison
    and Force bars with their two empty forms, the description box's two ends, the
    target's name bar for a friend and for an enemy, the combat queue's frame and
    the curve beside the portraits. Each of the game's textures was measured row by
    row and is described as lines, arcs and polygons in its own pixel units and
    colours, then rendered at four times its size
    (`tools/build_xbox_hud_art.py`, new). Nothing is read from the game at build
    time and no game art is in the patch. They have names of their own, `kmrx_*`,
    so the game's textures are untouched for the PC HUD and for other mods; the
    table and the module ask for the new names (`tools/build_xbox_hud.py`,
    `K1XboxHud.cpp`). The package grew by 46 KB.
  - *Each texture carries `clamp 3`* (a `.txi` beside it). The engine repeats a
    texture past its edge and makes smaller copies of a TGA; in those a frame's
    last row was mixed with its first, and the description box showed a dark seam
    where its two ends meet. With the edge rows whole, the one-pixel overlap of the
    box's two halves (`SEAM_OVERLAP`) showed as a dark line instead, so it is 0 now.
  - *The bars keep their outline.* The empty bar was a bare half-opaque shape and
    the filling carried the black outline, so a wounded character's bar lost its
    outline from the top down. The empty bar has the outline now. The second
    drawing of a bar's outer edge beside itself, added earlier that day because the
    game's art has that edge cut by its texture's side, is removed at the
    maintainer's request: the drawn arc is half a pixel further in and its outline
    is whole.
  - *The three portraits are framed alike.* The Xbox layout puts each portrait a
    fraction of a unit off its frame's panel, differently for each: one showed a
    black strip under it, one beside it, the leader's none. The module now puts
    each frame around its portrait in screen pixels (`FramePortraits`): the
    portrait's top and bottom edges fall in the middle of the frame's blue lines,
    which are three pixels thick in the drawing for that; at each side a black
    hairline stands between the picture and the lens, drawn from the frame's
    outline at the top to its outline at the bottom, and the picture is kept one
    whole pixel clear of each lens, giving up a pixel or two in width and height.
    The bars are placed the leader's way on all three; the layout has the
    companions' wider for their height and further in, and their ends lay on the
    picture's corners.
  - Seen in a scratch copy of the CD 1.03 game at 1280x960 in a window, the patch
    alone, a save with a friendly creature targeted and two companions, one of
    them and the leader wounded (package SHA-256 `A1D5A6D2...59786F8F`,
    10,027,574 bytes, 34 hooks). `testing/regression/Test-ControllerKpatch.py`
    passes and now checks that the bank holds exactly the seventeen drawings, each
    with its `.txi`. **Not run:** a hostile target (the red name bar), a fight (the
    queue's frame, the combat strip), a poisoned character, an empty Force bar, any
    other screen size, fullscreen, beside Scaled Kotor or another patch, the swap to
    the game's own HUD and back, and the GOG and Steam executables.
    [`docs/controller-xbox-hud.md`](docs/controller-xbox-hud.md), "Drawn frames".
- **KMRP's patch is half the size: 129 MB instead of 249 MB** (2026-10-05). The
  patch's module carried every file of every
  resolution's set, 62,898 files for 66 sizes. It also carries the blend helper
  (`KmrpGuiBlend`, `macos/tools/kmrp-guiblend.c`), which writes a size's layouts,
  badges, prompt manifest and HUD box from the blend table, and for most listed
  sizes what the helper writes is the build's own set, byte for byte. So the build
  now runs that helper for every set, compiled with the module's own flags, and
  stores a file only if the helper does not write it exactly: the fonts, 1280x1080
  (outside the blend), and the 32 to 329 files per set that the blend makes
  differently at 20 sizes. 56,349 files are left to the module; the bank is
  128,804,860 bytes instead of 248,545,368 (`tools/build_native_assets.py`, format
  `KNAST002`), `KMRP.kpatch` 129,287,315 bytes instead of 249,026,195, and the
  installer 136,111,616 bytes instead of 255,850,496 (130 MB for 244 MB; it was
  196 MB before the focused badge textures).
  - *The result is unchanged.* A set's index still names every file with its
    SHA-256. The module writes the files it has, runs the helper, puts stored files
    back over the helper's, and holds every file against the index; a difference is
    reported in `kmrp-kpm.log` and the blend's file is used
    (`K1RuntimeAssets.cpp`, `KmrpRuntimeAssetsDimensions`). Compared in a scratch
    install against the module of the build pushed the same day, every file of the
    module's folder hashed: identical at 1920x1080 (rebuilt whole), 1360x768 and
    1344x840 (rebuilt in part), 1280x1080 (stored whole) and the unlisted 1700x1000.
    Installed by the rebuilt installer and looked at: 1360x768 in a window and
    3440x1440 fullscreen, where the 953 files of the set also hash to the build's
    archive.
  - *Starting the game takes as long as before.* Measured on this PC, 1920x1080:
    6.5 s to produce the interface files, of which the helper 1.3 s; a size with
    every file stored took 5.9 s. Two savings in the same change pay for the
    helper: a decoded object is no longer hashed a second time before it is
    written, and after the helper only the set's files are read back, not the
    300 MB of common files. Most of the time is the creation of about 2,100 files,
    which this change does not touch.
  - `testing/regression/Test-NativeAssetsBank.py` (new) checks the index against
    the archives, that nothing the module cannot make is missing, and that an
    independently built helper makes every left-out file exactly (all 56,349, with
    `--all`). It, `Test-KpatchSource.py` and `Test-InstallerPatch.ps1` pass on the
    rebuilt installer (SHA-256 `928A35A8...0CE3E8`). `Test-GuiBlendHelper.py` and
    `Test-ControllerPromptAssets.py` were not run again: the resources and the
    helper are the pushed build's, unchanged.
  - **Stronger compression is a build switch, and off.** With
    `tools\build_native_assets.py --lzms` the bank is LZMS instead of
    XPRESS-Huffman: 94,534,820 bytes instead of 128,804,860, the same files in the
    scratch install at 1920x1080, and 9.0 s instead of 6.5 s to produce them at
    every start of the game on this PC (two runs each). 34 MB of download against
    2.5 s per start is the maintainer's trade to make; the module reads either
    bank.
- **LT and RT beside the menu's tab strip are arrows in the game's style** (2026-10-05,
  the standalone controller patch). In place of the controller family's trigger
  pictures: a triangle with rounded corners pointing along the strip, the trigger's
  name in its wide end (LT and RT, L2 and R2, ZL and ZR by family), in the strip's own
  colours (the dark fill of a tab's box, the frame and glow in the blue of the tabs'
  icons, sampled from a screenshot; it was a lighter body in a brighter frame for one
  commit), drawn by `tools/build_tab_arrows.py` with no one's art and no font (the
  letters are strokes). The maintainer chose the look from four prototypes
  and set the rest in the running game: the arrow's flat side is as tall as a tab's
  box without its lip and level with it, and the arrow is as far from the strip as
  the tabs are from each other. The module computes all three from the live tab
  beside each cue, so they hold at any size. Measured in the unchanged game at
  1280x960: 12 px between two tabs and 12 px from each arrow to its tab, the flat
  side on the box's rows; seen the same with Scaled Kotor at 3440x1440, where the
  eight tabs, the HUD, and the swap to the mouse and back to the pad were also run.
  [docs/controller-standalone.md](docs/controller-standalone.md), "Beside a patch
  that rescales the interface".
- **The standalone controller patch's prompts follow another patch's scaling, and a
  glyph never changes shape** (2026-10-05). Beside Scaled Kotor at 3440x1440 the
  maintainer found the LT, RT, sub-tab and party cues small in a corner, the badges on
  reshaped buttons oval, and badges far from their captions. Now, in this patch only:
  - a cue (LT, RT, the sub-tab cue, the party cue) is put where its layout file puts
    it relative to the control it was placed beside, as that control is now, and
    scaled by one factor;
  - a badge on a button whose shape is no longer the one the badge was made for, in
    either its normal or its focused state, is drawn on a label of the made-for shape
    instead of stretched over the button
    (`K1ControllerBadgeShapes.inc`, 130 badges, written by
    `tools/build_controller_assets.py --badge-shapes`);
  - that label stands beside the caption as it is on screen, a quarter of the
    button's height from the text, inside the button, and on the caption's line: a
    resized button whose caption is no longer on its middle line (the Map screen's
    two rows, three times as tall with their text still at the top) has its badge
    moved to a label for that reason alone, and its caption brought to the button's
    middle line with the badge while the badge is shown;
  - the sub-tab cue is 1.2 times its size and the party cue sits nearer the portrait,
    on the portraits' middle line.
  In the unchanged game a badge is on its button as before. Seen by the maintainer on
  the CD 1.03 executable with Scaled Kotor 1.3.1 at 3440x1440: the in-game menu's
  tab strip, Abilities, Options, Gameplay and Graphics Options, the resolution
  pop-up, character generation. Not run: the unchanged game since these changes
  (the regression test passes), the other screens, other sizes.
  [docs/controller-standalone.md](docs/controller-standalone.md), "Beside a patch
  that rescales the interface".
- **The standalone controller patch is now "KOTOR 1 Native Controller Mod + Xbox HUD"** (2026-10-05).
  The file is `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch` and KOTOR Patch Manager
  lists it under that name; it was "KMRP Controller". Its id (`kmrp-controller`), its
  settings file and its log keep their names.
- **The standalone controller patch installs beside Scaled Kotor, and the Xbox-style
  HUD works with it at 1920x1080 and 3440x1440** (2026-10-05).
  KOTOR Patch Manager refused the pair: both hooked the entry of
  `CSWGuiPanel::StopLoadFromLayout` (`0x0040B8F0`). The standalone patch now reaches
  the same two moments from sites of its own, the entry of `CRes::Release`
  (`0x00409B80`, acting on one caller only) and `0x0040CFAB` in the panel's
  destructor; 34 hooks. KMRP's own patch is unchanged. With Scaled Kotor 1.3.1 at
  1920x1080 the Xbox HUD lays out as at the game's own sizes; the minimap's frame,
  which Scaled Kotor moves back every frame, is drawn by the module around the map
  when that happens. Also in the Xbox-style HUD:
  - the PC HUD's menu buttons keep their dark backing after a swap (the module
    draws with that label and had not put its art back);
  - the party's bars have their whole outer outline and no faint ticks at their
    ends: the module draws them and sets their textures to clamp at the edge;
  - the party's group is 85% of the Xbox layout's size.
  - the party's group is drawn with each bar's outer outline completed (the art's
    edge column repeated once, in its middle rows);
  - beside a patch that takes the minimap's frame, the frame is left without art
    rather than made invisible: invisible, the engine drew the speech box across the
    whole screen (seen at 3440x1440);
  - the Controller Layout entry in Options, Gameplay is placed from the live Mouse
    Settings and Key Mapping buttons, so it follows another patch's scaling (at
    3440x1440 with Scaled Kotor it stood over the first rows). Not looked at since.
  Seen: both patches at 1024x768, 1920x1080 and 3440x1440 with a loaded save and a
  line of speech; the rest on the controller patch alone at 1024x768. Not run with
  both: a fight, the swap back to the pad, the menus' badges. Text beside Scaled
  Kotor is small at 3440x1440, as it is with Scaled Kotor alone (measured: the main
  menu's capitals 9 px with and without this patch). [docs/controller-xbox-hud.md](docs/controller-xbox-hud.md),
  "Beside a widescreen patch: Scaled Kotor".
- **The Xbox-style HUD follows the device and fits any screen** (2026-10-05). It no longer replaces the game's HUD layout files.
  The module finds each of the HUD's controls at its fixed place in the game's HUD
  object and moves and dresses it itself, from a table `tools/build_xbox_hud.py`
  writes (`K1XboxHudLayout.inc`, 101 controls), for the screen the game is drawing:
  - while the pad is in use the HUD is the Xbox one; the moment the mouse or
    keyboard is used it is the game's own again, exactly as it was, and back with
    the pad. Seen both ways at 1024x768, peaceful and in a fight, and after a
    conversation;
  - the layout is computed from the real screen size and does not depend on its
    shape, and it no longer matters which HUD layout file is loaded, so another
    mod's layout is left alone. Only the game's own sizes were run (the unchanged
    executable refuses others); the regression test lays it out for ten screens
    from 800x600 to 3840x2160;
  - the minimap is the size the game's own HUD has it, in both;
  - the box a line of speech appears in starts by the target bar's left edge, right
    under the bar, as in the Xbox game, and is one and a half times the bar's width.
  The four `kmxh*.gui` files are gone from the bank. No new hook: a call from the
  existing panel hook tells the module of a new HUD object.
  [docs/controller-xbox-hud.md](docs/controller-xbox-hud.md), "Laid out at run time".
- **An Xbox-style HUD for the standalone controller patch** (2026-10-05). An
  option of `KMRP Controller.kpatch`, off by default (`Style=Xbox` under `[Hud]` in
  `kmrp-controller.ini`, or the patch's "Xbox-style HUD" option where the manager
  offers options). The HUD is laid out and behaves as the original Xbox version's,
  at its proportions:
  - the action menu at the bottom left, a box with the selected action's name over
    a row of six slots, the selected one large and yellow; the first place is the
    default action ("Attack", "Open", "Dialog", or "No Action" without a target),
    the target's feats and powers take the next two while there is a target, and
    grenades take the mines' place while the target offers any;
  - the target's name and health fixed at the top left, in a red frame for a
    hostile target; the party at the bottom right with curved bars that empty from
    the top; the minimap at the top right;
  - in combat mode a strip across the top with the Xbox game's own line, "COMBAT
    MODE engaged. (B) to disengage.", the pad's B drawn in it. B disengages when no
    slot is selected; beside the queue only Y is left.
  The layout is the Xbox HUD's own (`mi8x6.gui`, still in the PC data) applied to
  the PC HUD's controls by `tools/build_xbox_hud.py`, each group moved a little
  nearer its corner at the maintainer's direction; the art and the combat line are
  the game's own, and the patch carries no font. Two new hooks, 33 in all
  (`K1XboxHud.cpp`): one at `CSWGuiMainInterface::DrawMap` (`0x0068AB10`) places and
  dresses the controls before each draw, one at `CSWGuiTargetActionMenu::Draw`
  (`0x00685ED0`) draws the first place and the party's bars. Seen with a virtual
  pad on the CD 1.03 executable: a friendly target and a fight at 1024x768, and the
  layout at 800x600, 1280x960 and 1600x1200; `Test-ControllerKpatch.py` passes.
  Not built: the PC HUD coming back when the mouse is used, and any screen size but
  the game's four. Text is the PC's size, 0.61 of the Xbox's.
  [docs/controller-xbox-hud.md](docs/controller-xbox-hud.md) has the design, the
  limits and what was not run. KMRP's own patch does not have it.
- **Controller badges are made for the area a button's border really fills**
  (2026-10-05). A badge is a texture on its button's fill, and a border that names
  corner art draws that fill inside itself, by its `DIMENSION` on every side
  (`CSWGuiBorder::Draw`, `0x004168C0`, read from the decompiled function). KMRP made
  every badge for the whole button, so on a bordered button it was drawn squeezed:
  about 13% wider than tall on a 720x90 one, and 28x20 on the game's original 240x40
  Options buttons, where the standalone controller patch showed it. Now:
  - each badge is drawn for its border's area and kept whole inside it;
  - where a button's focused border fills a different area than its normal one (a
    Close button has no normal border and a 6 px focused one), there is a second
    texture for the focused state, `kmf...` beside `kmr...`, and the module asks for
    it (`SetK1ControllerPromptFill`);
  - the blend table is version 5 and carries each badge's two insets;
    `macos/tools/kmrp-guiblend.c` and `src/patcher/GuiBlend.cs` draw the same for a
    size with no set. A version 4 table is refused;
  - the Container screen's Give Items button, which is widened until its badge sits
    at the designed gap from the caption, is widened for the smaller area too
    (`badge_fit_width` takes the border's inset). Without that the badge sat up to
    3 px nearer the caption than designed at 24 blended sizes, which
    `Test-GuiBlendHelper.py` reported.
  Per set, 196 of the 552 badge textures change and 280 are new. **The installer
  grows from 196 MB to 244 MB**, because every set carries the focused textures (the
  entry above takes that back, and more, by making them on the player's PC). Measured in a scratch install on the CD 1.03 executable: Options at
  1920x1080 in a window, the focused Gameplay A 47x46 px, Close's B 32x32 and
  focused 31x31; at 3440x1440 fullscreen 61x61, 43x43 and 42x41. Other screens at
  those sizes were not measured, and the measurements are from the build before the
  Give Items change, which touches no other screen. `Test-ControllerPromptAssets.py`
  (66 archives, 34,848 textures), `Test-GuiBlendHelper.py`, `Test-InstallerPatch.ps1`
  and `Test-KpatchSource.py` pass on the final build.
  The Mac's controller code does not ask for the focused texture yet
  ([docs/macos-changes-from-windows.md](docs/macos-changes-from-windows.md), item 18).
- **The installer's Controller Support row names KMRP as its author** (2026-10-05).
  It read "KMRP, based on Saul0097" (Windows) and "RaymanGT, based on Saul0097"
  (macOS). The maintainer asked for the public-facing credit to be KMRP's alone; the
  licence notices, `THIRD_PARTY_NOTICES.md` and the documentation still credit
  Saul0097's KPM Xbox Controls, whose code is in the module. The macOS line was
  changed in source and not built.

- **KMRP Controller: controller support as a patch of its own** (2026-10-05).
  `KMRP Controller.kpatch` (id `kmrp-controller`) is KMRP's native controller
  support for a game without KMRP: the pad in the game and in every menu, the
  button prompts of four controller families, rumble and the Controller Layout
  screen, on the game's original interface. It needs no other patch and no
  installer, writes nothing to Override, and carries none of KMRP's other work.
  KMRP's own patch already contains it, so KOTOR Patch Manager refuses the two
  together. Built by `src\controller-native\build_controller_standalone.cmd` and
  `tools\build_controller_kpatch.py` into `dist\controller\`; its files are made
  for the game's own layouts by `tools\build_controller_assets.py`.
  - *Badges keep their shape on the game's small buttons.* A button's border
    draws its fill inside the border when it has corner art, so a badge made for
    the whole button came out oval (28x20 on the original Options screen) or cut
    off (the focused Close). Badges in this patch are made for the area each
    border fills, with a second texture for the focused border where the two
    differ.
  - Seen in scratch copies with the CD 1.03 and GOG executables, installed by KOTOR
    Patch Manager 0.7.1, at 800x600, 1024x768, 1280x960 and 1600x1200, with a
    virtual Xbox pad and a virtual DualShock 4. Not run: Steam's executable,
    fullscreen, a real controller (so rumble), combat, another language.
    [docs/controller-standalone.md](docs/controller-standalone.md) has the full
    list. `testing\regression\Test-ControllerKpatch.py` passes.

- **The resolution checklist shows every size KMRP has, in sections** (2026-10-04).
  Step 3's **Choose** listed the display's sizes and, of KMRP's other sizes, only
  those no larger than the desktop, so 3840x2160 was missing on a 3440x1440
  display. It now lists all of them under three headings: *This display*
  (fullscreen, ticked), *Fits this display* (runs in a window) and *Larger than
  this display* (cut off at the right and bottom). Each row shows the size, its
  shape (16:9, 21:9, or a number such as 1.55:1 for a shape without a common name)
  and its common name where it has one (4K UHD, Ultrawide QHD, Steam Deck handheld);
  the display's current size is marked *current* and a size the player typed
  *custom*. The list draws its own rows and has the shell's dark scrollbar.
  Measured: 3840x2160 on that display ran as a 3840x2160 window at the top left
  corner with the main menu's lower buttons off the screen, which is what the third
  heading says. The dialog was looked at through a harness that opens it alone, not
  from the installer's own window.

- **Options in `configs`, and debug logs off by default** (2026-10-04, after the
  entry below).
  - **Where the options are recorded.** `configs\kmrp.ini` in the game folder,
    section `[Patch Options]`, a key per option, `1` or `0`: the layout KOTOR Patch
    Manager's patch-options pull request settled on that day (not merged yet). The
    installer writes that section, leaves anything else in the file alone, and
    Restore Original takes it out again. `patch_config.toml` no longer has a
    `[patches.options]` table, and KMRP's module reads the file instead
    (`KmrpOptions.h`); a missing file, section or key is the default, so KPM 0.7.1
    still runs controller support and map notes on.
  - **Debug logs.** A third option, `debug-logs`, off by default, with a fourth row
    in Advanced Settings. Without it the module writes none of its diagnostic logs
    (`kmrp-native-preview.log`, `kmrp-layout-lifecycle.log`, `kmrp-confirm-focus.log`,
    `kmrp-native-joystick.log`) and only errors and warnings to `kmrp-kpm.log`; until
    now all of them were written on every run. A run to the main menu wrote no
    `kmrp-*.log` with it off and three with it on. The controller tests read
    `kmrp-native-joystick.log`, so their game folder needs `debug-logs=1`.
  - **Removed:** `tools/build_kpatch.py`, `src/controller-native/build.cmd` and
    `tools/check_patcher_hook_table.py`, the last files of the four-patch edition.
    What the other builders used of the first is now `tools/kpatch_common.py`.
    `tools/check_controller_drift.py`, `tools/check_module_exports.py` and
    `testing/controller/select_controller_path.py` still describe the four-patch
    layout and were not run or changed.

- **KMRP is one patch.** The installer installs KOTOR Patch Manager's runtime with a
  single patch, `kmrp`, in place of four (KMRP, KMRP Controller, KMRP Movies, KMRP
  Map Notes), a per-resolution data file and about 1,850 files in `Override`. The
  patch's module carries the engine changes, every resolution's files, the controller
  and SDL, so nothing is written to `Override` and nothing is built for one
  resolution. Decided by the maintainer on 2026-10-04; measured the same day on
  scratch copies of the editable 1.03 game and installed on the play-test game.
  - **Options.** Controller support and map notes are options of the patch, chosen
    in Advanced Settings as before; the installer writes the hooks of the options
    left on into `patch_config.toml` itself and the chosen values into
    `configs\kmrp.ini` (first a `[patches.options]` table in `patch_config.toml`; see
    "Options in `configs`" below). With
    both off it wrote 24 of the 52 hooks and the game logged "KMRP + Movies". The
    movie fixes are always installed: they were a third option for a few hours and
    the maintainer made them part of KMRP ("standard baked into KMRP, non-negotiable").
  - **Resolutions.** The pick-one-resolution step is gone. The game starts at the
    display's current size, written to `swkotor.ini`, and offers every size the
    display supports under Options, Graphics. Step 3's **Choose** opens a checklist
    with those sizes ticked: unticking one hides it in the game, and ticking a size
    the display does not support (a listed one or a custom one) adds it. The choice
    is written beside the game as `kmrp-resolutions.txt` only when it differs from
    the default. The game takes its modes from Windows and fell back to 800x600 for
    a size Windows does not report, so the module adds such a size to the modes it
    sees; it runs in a window, and with fullscreen on as a borderless window on the
    desktop's own mode, since asking Windows for the mode made the game exit
    (3000x1300 on a 3440x1440 display). That window is kept in the middle of the
    display and the mouse is confined to it, as in fullscreen: it sat at the top
    left corner at first, and a click outside it minimised the game (2000x1200 on
    the same display: at 720,120 through the intro movies, the main menu and a
    minimise and restore; a click on Options opened it).
  - **One `.kpatch`.** `KMRP.kpatch` is delivered to KOTOR Patch Manager's patch
    folder in place of four files, and `--export-kpm-patches` writes the one. KPM
    0.7.1 installs it with every option on. The installer carries the 189 MB module
    once, inside the `.kpatch`, and is 195.8 MB (164.8 MB before).
  - **Upgrading.** An install of the four-patch edition is restored first, by the new
    installer's own restore: on a scratch game its 1,854 `Override` files, data file,
    modules and SDL were removed, the new patch installed, and Restore Original then
    left the original files.
  - **Patch ids.** `kmrp-controller`, `kmrp-movies`, `kmrp-map-notes` and the
    experimental `kmrp-native`, `kmrp-native-options` and `kmrp-native-map-notes`
    are retired; `kmrp` lists them as conflicts.
  **Removed with the old layout:** the installer's Override install code and the
  three regressions that asserted four patches (`Test-KpmEdition.ps1`,
  `Test-ControllerSupport.ps1`, `Test-InstalledOverride.ps1`);
  `Test-InstallerPatch.ps1` and a rewritten `Test-KpatchSource.py` cover the one
  patch. The restore of older installs is unchanged. The sections of
  [KPM edition](docs/kpm-edition.md) below its first describe the old layout. Steam's executable was run by the maintainer (a resolution
  change in the game included) and GOG's to the main menu on a scratch game, both
  on 2026-10-04.

- Mouse confinement now applies in fullscreen only. A windowed game no longer
  traps the cursor inside its window: confinement is skipped, and released if
  held, whenever the client area does not cover its whole monitor. Both copies
  changed (the installer edition's module and the standalone module). See
  [Mouse confinement](docs/controller-support.md#mouse-confinement-on-multi-monitor-setups).

- Experimental standalone package: one `KMRP Standalone.kpatch` built by
  `tools/build_native_kpatch.py` carries the core, movie and memory hooks with
  the engine recipe and resource bank embedded in its module, and the licence
  texts of the bundled work. It installs through KOTOR Patch Manager 0.7.1's own
  installer on a clean CD 1.03 fixture and needs no KMRP installer. Changes made
  while play-testing it on 2026-10-04:
  - Stack arguments use KPM's `esp+N` slot-address form. The released runtime
    drops a bracketed `[esp+N]` source, which crashed the first build at startup.
  - A resolution change in Options keeps its text: a hook at `0x005F18F6` puts
    the new size's files in place before the window is re-created, and every
    font's TXI metrics are re-read. Play-tested by the maintainer across several
    switches.
  - The module makes the files the installer makes from the player's own game
    (tutorial popup icons, `tutorial.2da`, hex row frames, feat, power and skill
    icons), at startup and on every size change. Without them the tutorial
    popup's icon tiled.
  - The message popup's icon square follows the resolution in force
    (`K1PopupFit.cpp`), where it kept the size the box was constructed with.
  - The private resource cache of a game that has exited is removed at the next
    launch; none was ever removed before.
  - The module opts the process out of DPI virtualization, as the installer's
    AppCompat value does.
  - Map notes left the main patch: Derslok's corrections are the add-on
    `KMRP Standalone Map Notes.kpatch`, which the module detects in
    `patch_config.toml`.
  - A size the layouts cannot reach is refused, as the installer refuses it: the
    Screen Resolution list offers only sizes KMRP has a layout for.
  - Screen Resolution lists each size and refresh rate once. Windows reports one
    mode per scaling variant, and the game listed them all.
  - After a switch, a control keeps what the engine's own code added to its
    layout file. The Options screen's five buttons sat 20 px high at 1080 lines
    after a round trip; they now return to the fresh-load position.
  - A second package, `dist/native-options/KMRP.kpatch`, makes controller
    support, map notes and the movie fixes options of the one patch, all on by
    default. A KOTOR Patch Manager with patch options (upstream issue 13;
    prototyped locally) lets the player turn each off. KPM 0.7.1, which has no
    options, installs it with every option at its default: on. The first
    package is unchanged in what it installs. Both carry the same module, which
    now contains the controller code, its prompt art and SDL.
  - The module makes the installer's NVIDIA check itself, at the first frame of
    each run. If the game would inherit "Prefer layered on DXGI Swapchain" from
    NVIDIA's global setting (the white flashes of issue #14), it writes a
    warning to `kmrp-kpm.log` that says so and that KMRP is setting "Prefer
    native" for `swkotor.exe`, then sets it in the game's own NVIDIA profile.
    The global setting is never written, a value set for the game is left as it
    is, and the change applies from the next start. `KMRP_NVIDIA.manifest`
    beside the game records it in the installer's format. See
    [NVIDIA present method](docs/nvidia-present-method.md#the-standalone-module).
  **Still experimental.** Known gaps are listed in the
  [runtime experiment](reverse-engineering/runtime-resolution-preview.md#standalone-package-2026-10-04).

- Added an experimental embedded engine/resource bank and existing-panel geometry
  migration for the standalone core. Removed the terminating zero from native
  control tag keys. This is unfinished runtime
  work, not a complete KMRP package; font cache migration and full mode-switch
  coverage remain pending. See the [runtime experiment](reverse-engineering/runtime-resolution-preview.md).

- Added an experimental, independent Windows native-resolution `.kpatch` build
  without controller or installer-resource dependencies. It exposes native
  driver modes through Graphics → Screen Resolution and includes existing
  keyboard/memory repairs. Live testing found and corrected the native tooltip
  layout-load hole for width 1280 with non-vanilla heights. This is a first slice,
  **not complete standalone KMRP**: layout/font/map/movie migration and broader
  input/mode-switch coverage remain unfinished. See the
  [runtime resolution experiment](reverse-engineering/runtime-resolution-preview.md).

- Ported the Mac row traversal, list-boundary handoff, and stationary-mouse
  focus mechanism to Windows core hooks, independently of the controller option.
  Keyboard aliases alone enter the repair; controller traversal and shared MOVETO
  links remain unchanged. Synthetic Windows-layout tests pass at five heights.
  Physical-keyboard and live controller/mouse verification remain pending; this
  is not yet a verified fix for the reported Windows keyboard failure. See the
  [Windows navigation reference](reverse-engineering/windows-keyboard-navigation.md).

- Mac uninstall now checks KPM’s `InstalledPatches` state before removing a runtime taken over by KPM. Byte-only foreign patches retain their runtime; invalid state also prevents removal.

- Integrated FTD's Mac Scripts-menu Enter callback fix: dismissing the Combat Scripts tutorial leaves Scripts open. Clean executable bytes and hook compatibility are verified. **Status correction, 2026-10-03:** the maintainer confirmed Scripts-menu Enter in game on 2026-10-02; broader mouse/controller selection remains unverified. His new GUI-layout writers overlap KMRP's existing guarded layout patches and are not enabled alongside them.

- macOS native ideal-text-height calculations now round upward at their existing quantization stages. The previous action-label frame adjustment was removed after a play-test showed native layout overwrote it before rendering. The correction uses the resolution-scaled font, object scale and wrapped line count. The font-height getter uses the same upward rounding so confirmation-button sizing can terminate. **Status correction, 2026-10-03:** the maintainer confirmed the final two-line action name and Exit Game in game on 2026-10-02; broader resolution/controller gameplay remains unverified. These native hooks are Mac-only; the Windows port is unfinished.

- macOS status-summary popups now choose text widths using native wrapping and round the rendered height upward. XP text at 1920×1200 no longer depends on an underestimated glyph-width calculation; rows that must wrap expand vertically, with OK below them. Automated coverage passes; the maintainer confirmed the XP popup in game at 1920×1200.

- macOS: installation enables Aspyr fullscreen by default; uninstall restores the previous setting if the player has not changed it.

- macOS: guard texture-bucket insertion and cap its clearing maximum at 4999; guard both grass cleanup paths against deleting an aliased buffer twice. These core protections also apply with controller support disabled.

- Ported the Windows resolution-menu acceptance patch to macOS. The configured
  size now replaces the vanilla 800x600 whitelist entry; display enumeration and
  the other native accepted sizes remain unchanged. The user confirmed
  1920x1200 at 120 Hz appears. Guards and output values pass at 76 resolutions.
  See the [port audit](reverse-engineering/macos-resolution-port-audit.md).

- Restored loading of macOS menu direction targets from GUI resources. The Mac
  engine left those slots at zero, sending arrow-key focus to control 0. Main-menu
  Up/Down and wraparound, Options Close navigation, and stationary-pointer
  keyboard navigation are user-tested at 1920x1200. The default mouse clamp now
  follows the active game viewport instead of the Mac desktop point size; the
  user confirmed mouse clicks on Close and the corrected single highlight.
  Follow-up submenu failures revealed incomplete resource navigation cycles; the
  shared handler now repairs reachability from live actionable controls, including
  late-bound buttons. The user confirmed submenu reachability. A further refinement
  makes Up/Down move between rows and Left/Right move within a button row;
  the user confirmed the row behavior and Feedback list boundary handoff. A structural audit of 87 effective GUI resources (67 menu layouts) passes; other runtime paths remain untested. See [runtime evidence](reverse-engineering/macos-keyboard-navigation.md).

- The macOS status-summary layout attempts a text reflow when a row remains
  wrapped despite an unchanged extent. **Correction, 2026-10-02:** the earlier
  entry presented a stale-layout explanation as established fact. It was not
  measured in-game, and the user's subsequent 1920x1200 play-test still shows
  missing XP text. This unsuccessful retry has now been replaced by the native-wrap
  and upward-rounded-height repair described above. Menu navigation was repaired
  separately; see the runtime evidence linked above.

- The macOS package-art builder now writes `Icon.icns` with Pillow instead of
  `iconutil`. On macOS 26.0.1, `iconutil` rejected both KMRP's complete iconset
  and an iconset it had extracted from Apple's QuickTime icon, stopping the app,
  ZIP and disk-image build before signing.

- The generated HUD action description reserves three lines using the shared
  `max(1, height / 720)` scale, a 16-pixel baseline and upward-rounded float32
  height arithmetic. It remains bottom-anchored and expands its background with
  the same scaled margins. **Correction, 2026-10-03:** the earlier entry assumed
  10-pixel font lines and a 51-pixel requirement at 1920×1200. Live Mac measurement
  instead found 27.0000019-pixel lines: two require 55px and three require 82px.
  The rebuilt Windows archives reserve 48px at 800×600/1280×720, 82px at
  1920×1200, 96px at 3440×1440 and 144px at 3840×2160. All 66 archives pass
  geometry checks; these resource measurements do not establish Windows' live
  font metrics or fix native height rounding. See the
  [Windows verification record](docs/handoffs/windows-text-clipping-2026-10-02.md).

- The generated-GUI regression now checks keyboard/controller Up and Down
  navigation through all five main-menu layouts in every resolution archive.
  The files use two different ID assignments for Exit and the hidden Warp
  control, so the check resolves targets by tag; all existing navigation maps
  already form the correct five-button cycle and leave Warp disconnected.

- The font cache builder now reports the documented scale-12 shared-atlas
  fallback instead of failing after baking every other scale. Ubuntu regeneration
  completed with 40 cached scale sets. The Proton archive audit checks the current
  resolution catalog rather than a stale fixed count of 49. A missing or unexpected
  resolution remains a failure. A whitespace fix in the native controller module
  also permits its existing arithmetic expression to compile with MinGW.

- Windows now assembles engine fixes from tracked patch sites and x86 source
  builders. Building the installer needs no clean 1.03 executable, gold snapshot,
  gold delta or extracted-originals resource. The build also compiles its native
  module. Runtime byte guards, relocation, optional feature flags and restore
  ownership remain in place. The source regression compiles the C# installer
  code and checks all 66 shipped resolutions plus three edge cases on Ubuntu;
  the native Windows/MSVC build remains untested. See
  [the source build reference](docs/windows-engine-source.md).

  The complete Ubuntu build exposed additional clean/gold file reads in the
  `.kpatch` packager. It now takes the documented CD/GOG header edit from source,
  checks packaged runtime hooks against the tracked measured table, and rejects
  any source engine write over their stolen bytes. Corrupted original bytes,
  static replacement bytes, missing hooks and missing target builds are rejected.

  The complete installer was cross-built on Ubuntu on 2026-10-01 and passed
  actual install/restore tests through Proton Experimental at 3440×1440 and
  1920×1080. The live Steam game was then installed at 3440×1440, preserving its
  executable hash. A subsequent Steam launch applied all 81 engine guard runs
  and 46 relocations. Menus, dialogue, save/load, an NPC label, and virtual Xbox
  movement/camera were exercised at 3440×1440; the gameplay follow-up also
  loaded High FPS Fixes 1.0.0 separately and showed about 120 FPS. That extra
  patch is not bundled in this installer. Stable Proton, Steam Deck and the
  remaining hardware/gameplay matrix are untested. See
  [the Ubuntu record](docs/linux-proton-steam-deck.md#ubuntu-installer-test-2026-10-01).

  *Correction, 2026-10-01:* the initial entry described installer-only coverage
  and said Proton gameplay was untested; the later checks supersede that limit.

**This is KMRP 1.5**, the build in progress. Its installer reports 1.5.0 in
Properties → Details and in the install record
(`swkotor.exe.kotor-ui-patch.json`).

Until 2026-09-24 it carried internal numbers, and they disagreed.
`PatchVersion` read `2.11.0-movieaspect`, but Properties → Details still
reported `2.10.0-mapnotes`. It was the second time these two drifted apart;
1.0 itself reports 2.7.0.0 there. `build_kmrp.ps1` now refuses to compile
while they disagree. Before the versions were corrected, it was run against
the real mismatch and refused it.

The 1.5.0 installer of 2026-09-25 (`873A01E2…36870`, 179,625,984 bytes) was
compared with the play-tested one of 2026-09-24 (`ECA3DE4B…`):
- its `--apply` output at the 48 resolutions both builds share is
  byte-identical, so every executable measurement below that cites `ECA3DE4B…`
  also holds for it;
- the 49th resolution, 2880x1620, is new (below);
- its GUI archives differ, because every resolution now ships `dialog.gui` for
  the dialogue A. It has 70 resources: the 49 archives, the MIT licence and the
  controller module with the fixes below.

Intermediate builds of the same days, never installed as releases:
- `D81E640C…`, the relabel without the licence;
- `7933…`, with the licence;
- `78A5CC43…`, the first build with 49 resolutions;
- `B599303A…`, committed as `1cca3fe`, before BioWare's rumble table.

The **haptics installer** of the same day (`C796489A…FDFC`, 179,650,560 bytes)
changes only the controller component: the module
(`E52826A2…`), eight new hooks in `patch_config.toml`, and a settings file. Its
executable patching code is unchanged in source, but its `--apply` output was
not re-compared. It still carries 70 resources. The builds before it, in order:
- `13ADCC63…`, `F328A18A…` and `C00B66AF…`, superseded before any test. The
  first predates the fade radius's 2 m floor. The second predates the pause
  and menus no longer freezing the clock (see
  [controller-rumble.md](docs/controller-rumble.md)). The third predates two
  fixes: damage no longer registers on a corpse, and a looping BioWare row no
  longer restarts while it is already playing, which the engine's own
  `PlayRumblePattern` also refuses (`0x005FB4BB`–`0x005FB4D2`).
- `74011765…` (179,645,440 bytes), the first pad test: the hum at BioWare's full
  level, far too strong.
- `6BEE57FF…` (179,645,952 bytes), a steady `SaberHum`. The second pad test found
  it too strong even at the pad's lowest step.
- `F4B4CE4F…` (179,646,464 bytes), the hum pulsed at a fixed 50 ms every 500 ms.
  The third pad test settled the defaults this build ships, with a random gap
  between pulses.
- `BA103494…` (179,648,512 bytes), that random gap set as one range key,
  `SaberHumPeriodMs=1000-2000`, superseded before any pad test by separate
  `SaberHumPeriodMinMs` and `SaberHumPeriodMaxMs`.
- `8C0A6D94…` (179,648,512 bytes), with those two keys, the build of the first
  combat test. Every combat pattern reached the pad at its intended strength
  but lasted 0.1–0.2 s, too briefly to feel. No saber hit could fire, because
  the hook sat on blade-on-blade contact rather than a blow landing. And no
  positional rumble was logged at all, grenades included.
- `1815ED7A…` (179,650,560 bytes), which fixed those three (see
  [controller-rumble.md](docs/controller-rumble.md)), superseded before any pad
  test.
- `4C02A277…` (179,650,560 bytes), adding the action bar keeping focus after a
  slot is used (issue #17, below) and the 500 ms shortest gap between hum
  pulses. The fourth pad test ran on it and found it right. This build differs
  only in writing `Debug=0` into a new `kmrp-controller.ini`; the module is the
  same, `E52826A2…`.

*Corrected before any commit:* this paragraph once named `F328A18A…` as
`F4B4CE4F…`. Each build's hash update was applied to the whole file, and it
rewrote the names of earlier builds along with the current one.

Builds after the haptics installer, the same day, each adding to the one
before:
- `99A9ECC6…` (179,832,832 bytes), X and Y in combat with their HUD badges, and
  the window's v1.5.0 label. Its four Python checks were run and pass.
- `D58A2E33…` (179,832,320 bytes), the dialogue A moved to the end of the reply,
  and the combat message widened at 3440x1440. Its four Python checks were run
  and pass. Its module is 204,800 bytes, `577AAE92…`.
- `7C2FFF8B…` (179,837,952 bytes), the update check. It was built with
  `-ReuseResources`, so its archives and module are `D58A2E33…`'s, and those
  checks hold for it; `Test-UpdateCheck.ps1` was run against its source and
  passes. `Test-ControllerSupport.ps1` and `Test-ReinstallOverOlderBuild.ps1`
  were run against it and pass; neither was run on the two builds before it.
  Superseded before any test by the dialog's second layout.
- `AD3DC07D…` (179,837,440 bytes), that second layout (Download and Skip
  version, the switch naming the version); nothing else changed. Its archives
  and module are still `D58A2E33…`'s. `Test-UpdateCheck.ps1`,
  `Test-ControllerSupport.ps1` and `Test-ReinstallOverOlderBuild.ps1` were run
  against it and pass. **Installed and play-tested that day:** the dialogue A
  sat mid-sentence and the combat message showed one of its two lines (both
  entries above). X and Y in combat were not reported on.
- `E5AFC981…` (179,838,464 bytes): the A from the drawn layout, and the combat
  message on one line at 1120 px. A full build: every archive regenerated, and
  the module rebuilt, 205,824 bytes, `32F018CF…`. The four Python checks,
  `Test-ControllerSupport.ps1` and `Test-ReinstallOverOlderBuild.ps1` were run
  against it and pass. Installed and play-tested that day: character creation
  crashed (the first entry under Fixed).
- `EC98B10F…` (179,840,000 bytes): the character-creation A
  guard, five more hooks (31 native). Built with `-ReuseResources`, so its
  archives are `E5AFC981…`'s. The module is 206,336 bytes, `628D4DC2…`; a
  rebuild after a comment-only edit gave the same hash.
  `Test-ControllerSupport.ps1`, which byte-checks the five new sites, and
  `Test-ReinstallOverOlderBuild.ps1` were run against it and pass. Installed
  and play-tested that day: no crash was reported, and the Attributes screen's
  D-pad was (next entries).
- `189DF101…` (208,659,456 bytes), the character-creation badges, a full build,
  29 MB larger for their 8,232 textures. Its module is 208,384 bytes,
  `5F7FB20A…`. `Test-ControllerPromptAssets.py` failed on it: the 42 new
  targets had no caption STRREFs, so their badges were placed at a fixed inset.
  Superseded.
- `EE262D77…` (208,663,552 bytes), with those STRREFs, including Feats' and
  Powers' runtime Add/Remove captions. A full build: the four Python checks
  (99 mappings, 19,404 textures), `Test-ControllerSupport.ps1` and
  `Test-ReinstallOverOlderBuild.ps1` pass, as do `Test-LargeAddressAware.ps1` and
  `Test-DpiCompatibility.ps1` with the new DPI cleanup (on `189DF101…`).
- `1720E0C1…` (208,664,576 bytes): Attributes and Skills
  navigated by KMRP. It reuses `EE262D77…`'s archives, and its module is
  209,408 bytes, `B7307208…`. `Test-ControllerSupport.ps1` and
  `Test-ReinstallOverOlderBuild.ps1` pass, and the runs left no test DPI value
  in the registry.
- `BCA35F28…` (208,672,256 bytes), Feats' A and X swapped; a full build. **Broken,
  and installed.** The name-entry guard was added to the source while it built.
  The installer compiles its hook table at the end, so the table named
  `GuardNameConfirmK1`, but the module it embedded (`609368A7…`) was built
  before the edit. The runtime stopped at that entry, the 13th of 36. The 23
  hooks after it never applied: movies (no skip), rumble, the camera, the
  action bar, and the keyboard and mouse detection. The maintainer reported it
  that day: "something is wrong with the mouse and keyboard and controller
  switching, and I can't skip movies". The pad log agreed, with no movie frame
  and no keyboard-or-mouse switch in either session. Every regression check
  passed it: they compared the hook table with the source, not with the
  module. `tools/check_module_exports.py` now does that, and
  `Test-ControllerSupport.ps1` runs it; it fails on that install and passes on
  the next.
- `DB9D7A08…` (208,672,256 bytes): `BCA35F28…`'s archives
  with a module built after the last edit, 209,920 bytes, `B28A80F7…`. It
  includes the name-entry guard and the dialogue A's larger gap, lower seat and
  bigger badge. `Test-ControllerSupport.ps1`, with the new exports check, and
  `Test-ReinstallOverOlderBuild.ps1` pass. Not yet play-tested.
- `4EF3C181…` (145,208,320 bytes): `DB9D7A08…` with the
  resolution layouts pooled, 63,463,936 bytes smaller (under Changed). Built
  with `-ReuseResources`, so its archives and module are `DB9D7A08…`'s. It
  embeds 22 resources instead of 70. `Test-ControllerSupport.ps1`,
  `Test-ReinstallOverOlderBuild.ps1` and the new `Test-InstalledOverride.ps1`
  at all 49 resolutions pass, as does a direct comparison with `DB9D7A08…`'s
  install. Not yet play-tested.
- `6A822AAC…` (155,054,592 bytes): the settings screens' badges and the D-pad
  glyphs on the -/+ arrows, Y on Default, Left and Right on -/+ rows, Pazaak's
  wager and the dialogue A on its line (all below). A full build, 9.8 MB larger
  than `4EF3C181…` for 30 badges and 42 arrow glyphs a resolution; its pool is
  67.1 MB. The four Python checks, `Test-ControllerSupport.ps1`,
  `Test-ReinstallOverOlderBuild.ps1` and `Test-InstalledOverride.ps1` pass. Its
  module is 214,528 bytes, `968A1C0D…`.
- `D407BF3A…` (155,056,640 bytes): `6A822AAC…`'s archives with the status
  summary's layout added to the module, 216,576 bytes, `36D23D9B…`.
  `Test-ControllerSupport.ps1` and `Test-ReinstallOverOlderBuild.ps1` pass.
  Previewed in a scratch copy of the game on 2026-09-25 (below); not
  play-tested by hand.
- `13A6270E…` (155,056,640 bytes): built with `-ReuseResources` before
  `src/controller-native/build.cmd` had compiled the module, so it embeds
  `D407BF3A…`'s module unchanged. Superseded and not tested; the build ladder
  in `docs/agent-memory/WORKFLOWS.md` now starts with the module.
- `63E7AAB9…` (155,057,664 bytes): the status summary's A, module 217,600
  bytes, `D13FF3CB…`. `Test-ControllerSupport.ps1` and
  `Test-ReinstallOverOlderBuild.ps1` pass. Previewing it found the D-pad
  crash on the status summary (under Fixed), which the builds before it share.
- `B5D3CBB7…` (155,057,664 bytes): the D-pad kept off the status summary's
  OK, module 217,600 bytes, `1419AD04…`. Both scripts pass, and the crash
  sequence runs clean in the scratch copy.
- `49671B67…` (155,057,664 bytes): the swap-tabs cue beside Close and a first
  try at the status summary's line spacing, a full build; module 217,600
  bytes, `42426D92…`. The four Python checks, both scripts and
  `Test-InstalledOverride.ps1` pass. The spacing read the wrong field and
  changed nothing (under Fixed).
- `80616FE6…` (155,057,664 bytes): `49671B67…`'s archives
  with the spacing read from the right field; module 217,600 bytes,
  `CB61BF17…`. `Test-ControllerSupport.ps1`,
  `Test-ReinstallOverOlderBuild.ps1` and `Test-InstalledOverride.ps1` pass.
  Seen in the scratch copy at 1920x1080 and 3440x1440: the status summary
  and its A, and the swap-tabs cue with X cycling the sub-tab, at both; the
  crash sequence at 3440x1440. Not played by hand.
- `128CDC79…` (156,569,600 bytes), 2026-09-26: A on Level
  Up, Y on Auto Level Up and A on the skill-info notice's OK; the D-pad kept
  off the Character screen and the notice; a full build. Module 218,112 bytes,
  `C19CC772…`; pool 68.5 MB. The four Python checks,
  `Test-ControllerSupport.ps1`, `Test-ReinstallOverOlderBuild.ps1` and
  `Test-InstalledOverride.ps1` pass. Seen in the scratch copy at 3440x1440
  through four level-ups (above). Not played by hand.
- `9736B41F…` (152,089,600 bytes), 2026-09-28: the echo
  guard on every panel (under Fixed) and the - and + arrows back to the game's
  own art (under Changed); a full build, 4.3 MB smaller than `128CDC79…`, pool
  64.3 MB. Module 217,600 bytes, `69E1811B…`; 33 native hooks. The four Python
  checks, `Test-ControllerSupport.ps1`, `Test-ReinstallOverOlderBuild.ps1` and
  `Test-InstalledOverride.ps1` pass, and so does
  `tools/check_controller_drift.py` against the scratch copy. Seen in the
  scratch copy at 3440x1440 and 1920x1080 on the virtual pad (under Fixed).
  Not played by hand.
- `C77F7640…` (152,090,112 bytes), 2026-09-28: KMRP's
  runtime on every patch, the controller option switching only its own hooks
  (under Changed). Built with `-ReuseResources`, so its archives and pool are
  `9736B41F…`'s; module 217,600 bytes, `AF223C4D…`, rebuilt first and
  confirmed installed. `Test-ControllerSupport.ps1` (143 checks, three new
  cases), `Test-ReinstallOverOlderBuild.ps1` and `Test-InstalledOverride.ps1`
  pass, as do the hook-table, stolen-byte, export and drift checks for both
  sets. Seen in the scratch copy at 1920x1080, both ways (under Changed). Not
  played by hand.
- `D6E40FAF…` (152,119,808 bytes), 2026-09-28, with the
  first KPM edition beside it in `dist\KMRP for KPM\`: `KMRP for KPM.exe`
  (147,598,848 bytes, `9ED1C740…`), `KMRP.kpatch` (133,757 bytes, `E3429B2B…`)
  and `KMRP (no controller).kpatch` (132,914 bytes, `0EEBEBA1…`); module
  236,544 bytes, `57E68A91…`, now with the applier (under Added). Built with
  `-ReuseResources`. `Test-ControllerSupport.ps1` (143),
  `Test-ReinstallOverOlderBuild.ps1` (12), `Test-InstalledOverride.ps1` (28) and
  the new `Test-KpmEdition.ps1` (77) pass. (These counts, and the 143 above, were
  first recorded one higher: a case-insensitive count of "PASS" also matched each
  suite's closing "All checks passed." Corrected the same day.) The standalone was seen in the scratch
  copy with the new module: 37 hooks, the applier idle. Not played by hand.
- `125DEA64…` (152,127,488 bytes), 2026-09-28, with the KPM
  edition as four patches (under Added): `KMRP for KPM.exe` (147,601,920 bytes,
  `2C715CA5…`), `KMRP.kpatch` (136,021 bytes, `0E454D87…`), `KMRP
  Controller.kpatch` (136,714 bytes, `5A29F9CD…`), `KMRP Movies.kpatch` (135,933
  bytes, `77CC3D71…`) and `KMRP Map Notes.kpatch` (391 bytes, `1D365F9F…`); module
  241,664 bytes, `0C89C330…`. Built with `-ReuseResources`.
  `Test-ControllerSupport.ps1` (143), `Test-ReinstallOverOlderBuild.ps1` (12),
  `Test-MovieResolution.ps1` (36) and `Test-KpmEdition.ps1` (98) pass. The KPM
  edition was seen in the scratch copy three ways (under Added). Not played by
  hand.
- `603DC45D…` (152,135,168 bytes), the current build, 2026-09-28, with the KPM
  edition self-contained and supporting Steam's executable (under Added):
  `KMRP for KPM.exe` (147,611,648 bytes, `1533474E…`), `KMRP.kpatch` (138,747
  bytes, `C27E108A…`), `KMRP Controller.kpatch` (138,764 bytes, `56C45ED3…`),
  `KMRP Movies.kpatch` (137,986 bytes, `014743BB…`) and `KMRP Map Notes.kpatch`
  (446 bytes, `D7977A3A…`); module 245,248 bytes, `4B1131DA…`. Built with
  `-ReuseResources`. `Test-ControllerSupport.ps1` (143),
  `Test-ReinstallOverOlderBuild.ps1` (12), `Test-MovieResolution.ps1` (36),
  `Test-LargeAddressAware.ps1` (15), `Test-InstalledOverride.ps1` (28) and
  `Test-KpmEdition.ps1` (107, its Steam case included) pass. Seen in game on the
  editable 1.03 executable and on Steam's (under Added). Not played by hand.

- **The KOTOR Patch Manager MIT licence is installed with the controller.** The
  runtime, the controller module and the memory-safety patches all come from
  KPM, which is MIT-licensed, and MIT asks for the notice to travel with every
  copy. The installer shipped all three without it. It now embeds
  `LICENSE-KOTOR-PATCH-MANAGER.txt` and installs it as
  `kmrp-kotor-patch-manager-LICENSE.txt`; the controller manifest owns it, and
  Restore removes it. `Test-ControllerSupport.ps1` checks the installed copy
  byte for byte, and `Test-ReinstallOverOlderBuild.ps1` also passes.

### Added

- **Windows: any resolution, not only the listed ones** (2026-09-30, at the maintainer's
  request: "make the choose resolution arbitrary ... macOS already achieved arbitrary
  resolution ... look at the pull request and how it did it"). The patcher's third step lists
  this display's size first, then the 66 listed sizes, and ends with **Custom size…**, which
  takes any size from 640x480 up that the finished sets reach -- shapes from 4:3 to 32:9 --
  and otherwise says which heights they reach at that shape. A listed size installs as
  before. Any other size installs the nearest listed set (the nearest height, then the
  nearest shape, the Mac installer's rule) with its `.gui` files blended from the finished
  sets around it, the Container widened and the Controller Layout screen laid out for the
  size: `src/patcher/GuiBlend.cs`, the C# of the Mac's `macos/tools/kmrp-guiblend.c`, over
  the same table (`tools/build_gui_blend_table.py`, embedded gzipped as `Kmrp.guiblend`,
  `build_kmrp.ps1` step 4a). The engine needs nothing new: every value `ResolutionPatch`
  writes follows the height, and the five map fields the catalogue carried are computed
  with the catalogue's own formula (`ResolutionChoice.ForSize`, from
  `tools/analyze_resolution_guis.py`), which every one of the 66 listed rows equals. The
  command line (`--apply`, `--in-place`) takes any such size too. `Test-GuiBlendHelper.py`
  runs on Windows (the helper built with LLVM clang) and requires the installer's blend,
  through its new `--derive-gui`, to equal the helper's byte for byte: it did at 369 sizes,
  300 of them random, and both refused the same 7. `Test-InstalledOverride.ps1` installs
  three sizes with no set. **Played** at 1600x1024, a mode the test monitor offers and no set
  has (between the 4:3 and 16:10 families), fullscreen, on GOG's executable in a scratch copy
  of a GOG install: KMRP applied in memory (91 of 91 runs), and the main menu, character
  generation (class, the hub, portrait), Load Game and the game itself on Manaan laid out
  with the blended menus. Windowed at 2560x1200 the engine's render window stayed 800x600 at
  the intro in that copy, which was not pursued; fullscreen at such a size needs a mode the
  display offers. The installer of these changes, `EE0CF629…` (159,756,800 bytes, with the game found in
  step 1 and the KPM option removed, below), passes all nine Windows suites:
  `Test-LargeAddressAware.ps1` (38), `Test-InstalledOverride.ps1` (1,963, with the three
  sizes without a set), `Test-KpmEdition.ps1` (165), `Test-ControllerSupport.ps1`
  (173), `Test-ReinstallOverOlderBuild.ps1` (38), `Test-MovieResolution.ps1` (36),
  `Test-DpiCompatibility.ps1` (16), `Test-NvidiaPresentMethod.ps1` and `Test-UpdateCheck.ps1`.
- **GOG's own `swkotor.exe`** (2026-09-30, at the maintainer's request: "the only two that
  exist is GOG and Steam"). GOG's v1.03 (`9C10E045…`) is the editable 1.03 build with the 16
  bytes of `Hellspawn Reborn` at FILE `0x000AC0`, header padding nothing reads, zeroed:
  zeroing them in the editable build gives GOG's SHA-256 exactly (measured 2026-09-30; until
  then KMRP had no copy and refused it by hash). The installer knows the three builds by hash
  (`GameExecutable`), GOG's also with the 4 GB flag set (`01B80825…`, computed by setting the
  flag), and on GOG's sets the flag as on the editable build and names GOG's file in
  `patch_config.toml`, `kpm_install_state.json` and KPM's backup record. `--apply` normalises
  GOG's file to the editable build by putting the watermark back; gold's fifth section header
  lands on those bytes anyway, so both give the same output. KMRP's four `.kpatch` files list
  it as `kotor1_gog_103`, the static 4 GB hook included. `Test-LargeAddressAware.ps1` Case 6
  makes GOG's file from the editable build, requires GOG's hash, the same `--apply` output,
  the flag, KPM's records naming GOG's file and an exact restore, and refuses another byte in
  that padding (38 checks pass). In game: that file, in a scratch copy of a GOG install folder,
  installed at 1600x1024 (the executable became `01B80825…`), started with KMRP applied (91
  of 91 runs), was played to the Manaan save, and restored to `9C10E045…` byte for byte.

- **One installer for the editable and Steam executables, on KOTOR Patch
  Manager's runtime** (2026-09-29, at the maintainer's request: "build its own
  KPM launcher that accepts the editable version and the Steam version ... just
  do patch and then I can start the game normally"). KMRP's installer no longer
  writes KMRP into `swkotor.exe`. It installs the KPM edition's files -- the data
  file, SDL, Override, the INI -- plus KOTOR Patch Manager's runtime, laid out as
  KPM's own proxy deployment lays out a game folder: KPM's `binkw32.dll` proxy in
  place of the game's (renamed `binkw32Hooked.dll`), `KotorPatcher.dll`,
  `patch_config.toml`, and KMRP's four patches' modules in `patches\`. The
  player starts the game as always, from Steam or `swkotor.exe`; the runtime
  loads KMRP's module, which applies the executable changes in memory, and the
  hooks. So both executables run the same bytes, and Steam's, whose DRM refuses
  a changed file, is supported without KOTOR Patch Manager. The details, the
  measurements and what was rejected are in
  [docs/kpm-edition.md](docs/kpm-edition.md), section 1a:
  - **The runtime is built from the submodule**, `third_party/Kotor-Patch-Manager`
    at `17fd051` -- since that evening FTD's `widescreen-patch`, first
    `9884466` (the same tree), then `71ac5fa` (new patches, the runtime's
    sources unchanged), both of which build the same bytes -- by the new
    `src/kpm-runtime/build.cmd`, which
    `build_kmrp.ps1` runs: `KotorPatcher.dll` and KProxy's `binkw32.dll`,
    statically linked, since KPM's own build needs the Visual C++
    redistributable. It waits for SteamStub to decrypt before patching.
  - **Each patch's config section is generated** by `tools/build_kpatch.py
    --config-dir` from the same hook table as its `.kpatch`, and checked against
    it; the installer joins the chosen ones under the executable's hash. The
    options choose the patches: controller support adds `kmrp-controller`, the
    marker fixes `kmrp-map-notes`; `kmrp` and `kmrp-movies` always go in.
  - **On the editable build the one change to `swkotor.exe` is the 4 GB flag**,
    set and cleared by the installer and checked by hash; Steam's is never
    changed.
  - **It replaces an earlier KMRP install**, which wrote `swkotor.exe`, with that
    install's own restore and backups first; with a damaged backup it refuses
    and changes nothing.
  - **KMRP for KPM is part of it** (later the same day, at the maintainer's
    request: "we should remove the for kpm version because this is already the
    standard version"). The installer installs for KOTOR Patch Manager -- the
    KPM edition's install, no runtime, `swkotor.exe` untouched, and the player
    ticks KMRP's patches in KPM -- when the new *KOTOR Patch Manager* option in
    Advanced Settings is on, or by itself when KPM's runtime is already in the
    game folder (`binkw32Hooked.dll`, `KotorPatcher.dll`, `patch_config.toml` or
    `kpm_install_state.json` this install did not write, or that has changed
    since). The first build of
    the day refused such a folder instead. The separate `KMRP for KPM.exe`, the
    `KPM_EDITION` compile and `dist\KMRP for KPM\` are gone; the four `.kpatch`
    files shipped in `dist\KPM patches\` with their README
    (`src/patcher/KPM-PATCHES-README.txt`, until then
    `KMRP-for-KPM-README.txt`). Advanced Settings has four rows now, 78 px each
    where three were 86, so all fit above the buttons.
  - **The installer is the one file** (that evening, at the maintainer's request:
    "cant we bundle it into the exe?"). It carries the four `.kpatch` files, their
    README and KPM's licence, and `dist\KPM patches\` is gone. For KPM's app to
    list KMRP's patches, the installer puts them in KPM's own patch folder, which
    it reads from KPM's settings (`%APPDATA%\KPatchLauncher\settings.json`), on
    either kind of install; when KPM has none, an install for KPM puts them in a
    `KPM patches` folder in the game folder and says so. Restore removes the ones
    it added while they are unchanged. A KMRP patch already in KPM's folder is
    brought up to this version and left on restore; a file of the same name that
    is not KMRP's is left alone. `--export-kpm-patches <folder>` writes the set
    out for sharing. `Test-KpmEdition.ps1` Cases 11 and 12 cover KPM's folder and
    the export, with a settings file whose path is escaped as KPM writes it; the
    six suites that install move KPM's own settings aside for their run, so a
    test never writes into a player's KPM folder. The installer that does this,
    `C4E01BB6…`, is 161,857,024 bytes, 425 KB more; all nine Windows suites
    passed on it, `Test-KpmEdition.ps1` with 171 checks. **Seen with KPM's own
    window the same evening**, on the maintainer's game: with KPM 0.7.1's
    settings naming the game's `patches` folder, a normal install put the four
    there (the manifest's `kpatch` rows, `created`), and KPM listed KMRP,
    Controller, Movies and Map Notes at 1.5.0 beside its own patches, with the
    game identified as "KOTOR 1.0.3". KPM's Apply was not part of that check.
  - **KPM's Apply keeps KMRP's proxy, fixed in KPM itself** (that night). KPM
    0.7.1 picks the deployment from its global *Use library proxy* setting alone,
    so with it off an Apply in KPM moved this install to injection, and the game
    started directly ran unpatched (0 of 37 hook sites, measured). The fix went
    upstream as
    [LaneDibello/Kotor-Patch-Manager#283](https://github.com/LaneDibello/Kotor-Patch-Manager/pull/283),
    merged the same night: KPM keeps the method a game's `kpm_install_state.json`
    records, both ways, on Apply and Launch. The installer records the proxy
    there, and now on Steam's executable too, where it wrote no such file before:
    KPM knows Steam's unchanged file by its hash, but on Steam only the proxy works.
    KPM's merged code read the file the installer writes over Steam's executable
    and kept the proxy with the setting off. So from KPM's first release after
    0.7.1 nothing has to be set; with 0.7.1 the player ticks *Use library proxy*
    first (README). Rejected the same night: having the installer turn that
    global setting on in KPM's own settings file. It would be obsolete with KPM's
    next release, and on 0.7.1 it would change the method for every other game
    KPM manages. The installer with the Steam state file is `8AB56A02…`
    (161,857,024 bytes); all nine Windows suites passed on it,
    `Test-ControllerSupport.ps1` now checking the Steam state file (173 checks).
  - **It hands its runtime to KOTOR Patch Manager** when KPM takes it over. KPM
    0.7.1 reads a game's installed patches from `patch_config.toml`, and this
    config is KPM's format, so KPM lists KMRP's patches as installed and lets
    the player add others. KPM knows a game only by its executable's hash, and
    CD 1.03 with the 4 GB flag is not one it knows, so on CD 1.03 the installer
    also leaves KPM two files: `kpm_install_state.json`, KPM's record that the
    executable was CD 1.03, and, just before it sets the flag, a backup of the
    unmodified `swkotor.exe` as KPM makes one (`swkotor.exe.backup.<time>` and
    its `.json`). KPM's Apply starts by restoring the newest backup, so it
    starts from the unmodified file and sets the flag itself, and its own
    backup, which its "uninstall all" restores, is the unmodified file.
    Measured with KPM 0.7.1's launcher, KMRP's four patches and KPM's Fair
    Pazaak Turn Order: with neither file (`5CCC1961…`) KPM refused every patch,
    "Game version: KOTOR Unknown", having already removed KMRP's runtime; with
    the state file alone, written by hand as `702034D8…` then wrote it, it
    applied them but backed up the flagged file; with both (`D25212D7…`) it
    applied them from the unmodified file. The game then ran from KPM's launcher
    and from `swkotor.exe` directly with all 91 runs, the 37 KMRP sites and Fair
    Pazaak's hook. KPM's "uninstall all" was read in its source and replayed by
    hand, not run in its window (the table is in
    [kpm-edition.md](docs/kpm-edition.md), section 1a). Once KPM's Apply has
    rewritten `patch_config.toml`, the installer treats the runtime as KPM's: a
    reinstall is one for KPM, and restore leaves the runtime, the modules, the proxy, the state file, the
    backup and the 4 GB flag in place. Found tracing that case through: a reinstall would otherwise have
    deleted the modules KPM had re-extracted byte for byte. `Test-KpmEdition.ps1`
    Case 10 covers it, and was run against the build before the fix
    (`D12C44F5…`), where it failed on exactly that: the modules deleted, the
    proxy undone, the 4 GB flag cleared. A `patch_config.toml` that is gone
    rather than changed is not a takeover -- KPM's "remove all patches" deletes
    it with the rest -- and gets the usual restore.
  - **Two ordering faults fixed before release:** a refusal could come after the
    previous install was already removed -- every check that can refuse now
    runs first -- and restore skipped K1DC in the KPM edition's build, so
    switching to it left K1DC behind. Both were found reading the code, not by a
    test; `Test-KpmEdition.ps1` Cases 8 and 9 were added for them and passed on
    the first build with the fix (`208C7344…`). They were not run against the
    build before, so they are not shown to catch the faults.
  - **Retired:** installing the gold image into `swkotor.exe`
    (`ApplyStandalone`), the standalone's runtime -- Saul0097's statically linked
    KPM runtime as an `.asi`, loaded by K1DC's `dinput8.dll` -- and its
    hand-written hook table (`ControllerOperations.BuildConfig`, a second copy
    of `kotor1.hooks.toml`). K1DC's loader now installs only with K1DC. The
    standalone's restore stays, for the upgrade. `--apply` still writes the
    gold image to a new file, as the reference the in-memory result is proved
    against.

  Seen in game on 2026-09-29 at 3440x1440, started as a player starts it: on the
  editable build, upgraded over the last standalone build (`061AD6A2…`), and on
  the maintainer's Steam test install through Steam. Both applied all 91 runs
  and hooked all 37 sites, and the memory matched the data file exactly (the
  table is in section 1a); the Steam folder was restored and checked against its
  backups afterwards. Not played beyond the menus on Steam.

  The builds of that day named here and in section 1a: `061AD6A2…`, the last
  standalone, which the upgrade was measured over; `D12C44F5…`, before the
  takeover fix; `208C7344…`, the first with the ordering fixes; `112CA755…`,
  while KMRP for KPM was still a separate installer; `5CCC1961…`, one installer,
  before the two files for KPM; `702034D8…`, with `kpm_install_state.json`; and
  `D25212D7…` (168,930,816 bytes), with the backup as well, the final one. On
  `702034D8…` and on `D25212D7…` all nine Windows suites passed; on the final
  one `Test-ControllerSupport.ps1` with 171 checks, `Test-KpmEdition.ps1` 148,
  `Test-InstalledOverride.ps1` 462 at all 66 resolutions,
  `Test-ReinstallOverOlderBuild.ps1` 38, `Test-MovieResolution.ps1` 36,
  `Test-LargeAddressAware.ps1` 23, `Test-DpiCompatibility.ps1` 16, the NVIDIA
  self-test 34 and the update-check self-test. The checks added for the backup
  were not run against a build without it, so they are not shown to catch its
  absence.

- **KMRP for KOTOR Patch Manager: a second edition, built from the same
  source** (2026-09-28, at the maintainer's request: "one source, two ways to
  build it"). The standalone installer writes KMRP's changes into swkotor.exe,
  which KOTOR Patch Manager (KPM) then no longer recognises, so KMRP could not be
  combined with KPM patches such as High FPS Fixes (issue #22). The KPM edition
  never modifies swkotor.exe:
  - **Four patches, one per fix** (split the same day at the maintainer's
    request: "Each fix is a different patch ... Not a bundle"):
    **`KMRP`**, required -- the widescreen interface and everything KMRP always
    does; **`KMRP Controller`**; **`KMRP Movies`** -- the movie display-mode
    operands, the aspect fit and the black movie window; and **`KMRP Map
    Notes`** -- Derslok's marker corrections, a manifest-only patch that KPM
    records and loads nothing for. KMRP requires nothing: it carries the
    texture, grass and save-game memory fixes itself, as the standalone does,
    and on the editable 1.03 executable sets the 4 GB flag with a static hook,
    so it conflicts with
    KPM's four patches that make the same fixes (no KPM patch requires them).
    The three add-ons require KMRP. The other conflicts are per patch: Map
    Texture Patch and Scaled Kotor with KMRP, Movie Patch with KMRP Movies only,
    Expanded Keyboard Control and Xbox Controls K1 with KMRP Controller --
    measured, not guessed: no other byte of any K1 patch KPM 0.7.1 ships
    overlaps KMRP's (`tools/check_kpm_overlaps.py`). Earlier that day it was two
    files, KMRP with and without its controller, and then four with KMRP
    requiring KPM's patches -- which Steam's executable could not satisfy.
  - **Steam's own `swkotor.exe` is supported** (at the maintainer's request,
    with a clean Steam install lent for testing). It is the editable 1.03
    executable's program behind SteamStub DRM: decrypted in memory, its code is
    the editable executable's byte for byte,
    measured at every byte KMRP changes. Its file is encrypted, so the installer
    carries the unmodified bytes it builds the data file from (91 ranges,
    `tools/kpm_originals.py`, proved against the gold delta and every resolution
    field) and writes the same data file for both executables. Steam refuses to
    start a changed executable, so there KPM must use its `binkw32.dll` proxy,
    KMRP applies after the game has started (about 460 ms in, pausing the game's
    threads while it writes), and the game runs without the 4 GB flag. The
    standalone now refuses Steam's executable with that explanation.
  - **The module applies the executable changes in memory** when KPM loads it
    (`K1KpmApplier.cpp`): gold's runs, and its eleven appended sections copied
    to memory it allocates -- their own addresses are taken by Windows in an
    unmodified process, measured -- with the 46 addresses that name them moved.
    Only KMRP's own copy applies, and it leaves out the Movies and Map Notes
    parts unless `patch_config.toml` shows those patches installed. All or
    nothing: every original byte is checked before any is written, and
    `kmrp-kpm.log` says why when nothing is applied. In the standalone edition
    it does nothing.
  - **`KMRP for KPM.exe`**, the same installer compiled with `KPM_EDITION`:
    Override, the resolution, DPI and NVIDIA settings, plus `kmrp-kpm.dat` --
    the final bytes, built as the standalone builds its executable, so no
    resolution rule exists twice -- and SDL beside the game. For the editable
    1.03 executable or Steam's.

  The relocation table is found twice by independent methods that must agree
  and proved by moving the code (`tools/kpm_relocations.py`); the `.kpatch`
  files are checked against KPM 0.7.1's install rules (`tools/build_kpatch.py`);
  and `Test-KpmEdition.ps1` proves, at 1920x1080, 3440x1440 and 1024x768, that
  the data file makes byte for byte the standalone's executable with all four
  patches, and the standalone's with its marker fixes off without Map Notes.
  **Seen in game on 2026-09-28** through KPM 0.7.1's own launcher in a scratch
  copy at 1920x1080, three ways -- all four patches; KMRP and KMRP Controller;
  KMRP, Movies and Map Notes -- each time with the running game's memory exactly
  the data file's for the patches ticked, at three different load addresses,
  and exactly the expected sites hooked (37, 35, 9). With KMRP Controller the
  pad drives the menus and skips movies; without KMRP Movies a movie switches
  the display to 640x480 as the unmodified game does, and with it plays at
  1920x1080, fitted. The first two-variant version was also seen in game: its
  main menu, HUD, Map and Inventory matched the standalone's captures. The
  final, self-contained build (`603DC45D…`) with only the four KMRP patches
  ticked: memory exact, the 37 sites hooked, and the 4 GB flag set by KMRP's own
  static hook, on disk and in the running game. **On Steam's executable**, in a
  clean Steam install the maintainer lent, a trial build of the same design
  applied 457 ms after the game started through KPM's proxy deployment, with
  memory exact and the 37 sites hooked; the main menu, character creation,
  Options and a movie matched the editable executable's captures. On
  2026-09-29 the final build did the same on that install: its installer left
  Steam's executable untouched and wrote the data file byte-identical to the
  editable executable's, and in game every change applied with memory exact
  (KMRP's code placed below the image this time), the 37 sites hooked, the pad
  driving the menus, and the screens matching again. Steam gameplay was not
  played, to keep the install's cloud save untouched. Not GOG yet, not KPM's graphical
  launcher, not played by hand. See [kpm-edition.md](docs/kpm-edition.md).
- **macOS: KMRP Installer, a window like the Windows patcher's** (2026-09-30). The Mac
  package is now `KMRP Installer.app` with the installer and everything it installs inside
  it, in place of `Install KMRP.command` and `Uninstall KMRP.command`, which ran the same
  script in Terminal. It is the Windows patcher's window, ported: the same colours, brand
  lockup and animated smoke header, the four-step card with its icons, the progress fill
  on the action button, Advanced Settings and the footer. Advanced Settings has Windows'
  two Mac-relevant options, the area map's marker fixes and controller support
  (`kmrp-mac.sh --no-controller` is new: no module, SDL or settings file), both on by
  default. Its icon, and the disk image's, is
  the Jedi crest from the lockup over "KMRP". The Mac download is a disk image,
  `KMRP-macOS-<version>.dmg`, whose window shows KMRP Installer, an arrow and Applications,
  in the installer's art direction; the build also makes a zip for sites that take only
  archives.
  Step 3 lists this display first (native, and half on a Retina display), then 34 Mac and
  external display sizes grouped by shape, and takes a custom size, which it checks the
  menu sets can reach. It runs `kmrp-mac.sh` and shows what it refuses. For macOS 10.13 and
  later, Intel and Apple Silicon. Restore Original and Start Patching were run through it on
  the live game at 3024x1964, and `Test-MacInstaller.py` passes on its payload. Not yet
  tried: a downloaded copy's first run through Gatekeeper (it is signed ad hoc, not by a
  Developer ID, so macOS asks the player to allow it) (`macos/README.md`, *The installer
  app*).
- **macOS: the installer runs its helpers from a copy without the quarantine flag**
  (2026-09-30). Gatekeeper kills a downloaded, flagged helper as it starts (exit 137,
  tested), and the app's own copy is read-only, so `kmrp-mac.sh` copies `bin/` to its work
  folder and clears the flag there. `status --brief` reports without hashing every
  installed file, for the app.

- **17 more resolutions, the sizes of current Mac displays** (2026-09-29): each display's
  default size and the pixel size it renders at on a Retina panel, from 1344x840 to
  4480x2520, listed under **macOS** in the launcher, 66 in all. Upstream ships no set for
  any of them, so each is derived: `derive_resolution` (`tools/derive_resolution_gui_set.py`)
  blends the upstream sets around it in aspect ratio and in height. Predicting each upstream
  16:10 set from the 4:3 and 16:9 ones this way puts every field within 1 px of the real
  one (`Test-ResolutionDerivation.py`; `docs/universal-resolution-math.md`). The Windows
  installer offers them because it embeds the same pool as the Mac port. Seen in play only
  on the Mac, at 3024x1964 and 1512x982; not yet built or run on Windows.

- **KMRP for macOS** (2026-09-29), for the Steam Aspyr build (`KOTOR_Exe` 1.4.0,
  `C1FCB8D3…6D71`), in [`macos/`](macos/README.md). The goal is a Mac build that cannot be
  told apart from Windows at the same resolution; `macos/WINDOWS-PARITY.md` tracks it
  Windows site by Windows site.
  - The same files as Windows: every resolution's menu set (the 49 Windows sizes and 17
    new Mac ones, `GROUPS["macOS"]`), pooled as the Windows installer pools them, with its
    fonts baked at `max(1, H / 720)`; for any other size the installer blends the `.gui`
    files from the finished sets around it (`tools/build_gui_blend_table.py`,
    `macos/tools/kmrp-guiblend.c`: 99.9% of fields within 1 px when a known set is predicted
    from the others) and takes the nearest set's fonts and art. The feat, power and skill
    icons are enlarged at install by a byte-identical port of `AbilityIconGenerator.cs`.
  - The engine: FTD's widescreen patch (a KotOR Patch Manager patch) is the base, with
    KMRP's engine fixes ported to it as K1–K8, plus K9, which makes a Retina display's pixel
    resolution a valid mode, and one setting, `UseGuiFileLayouts`, which turns its own
    layout off for pre-laid-out `.gui` sets. What the gold delta and the installer's
    per-resolution writes do beyond that is `macos/patches/kmrp-layout`: list-row, stack
    label, chain-row and popup sizes, list-box `PADDING` as a gutter (gold v11, v12),
    text-list rows, and the area map's canvas, overlay, marker positions and sizes.
  - On a Retina display the installer offers native resolution (3024x1964 on a 14" MacBook
    Pro) or half (1512x982, scaled up by macOS), or `--size` for any other. The mouse needs
    no fix at native: Aspyr's own conversion scales it once the mode exists.
  - Derslok's map-note corrections are a separate KPM patch.
  - `macos/kmrp-mac.sh` installs, uninstalls and reports, from a hashed manifest that also
    covers the three `swkotor.ini` keys it writes.

  Play-tested on a 14" MacBook Pro through Aspyr's launcher, fullscreen, at native
  3024x1964, installed by the installer: main menu, Load Game, HUD, inventory, abilities
  (skills, powers), journal, area map, options, the quit confirmation and a conversation;
  the same screens at half, 1512x982; and a blended size, 1352x878, windowed. Install and
  uninstall were tested against the live game and against a stand-in game for a listed and
  a blended size (`Test-MacInstaller.py`); the game and `swkotor.ini` came back identical.
  Store rows, the stack-count label, tutorial popups, pressing Play
  in the Steam client itself and any other display were not tested. See `macos/README.md`, *Coverage*.

  *Corrected 2026-09-29:* the first Mac build, the same day, laid out the vanilla menus with
  the widescreen patch's own runtime layout, wrote `NativeResolution`, `FontScale` and
  `FullWidthMenus`, and installed per-scale fonts and none of KMRP's `.gui` sets. It looked
  visibly different from Windows (4:3 menus, larger inventory rows, no feat and power row
  fix) and was replaced before release.

- **The skill icons grow with the Skills rows** (2026-09-29, Windows and macOS, at the
  maintainer's request: "the skills have small icons still"). The Skills tab's rows grow to
  42s, but the eight `isk_*` icons are 32x32 textures the engine draws one texel per pixel,
  so at 3024x1964 a 32 px icon sat in a 115 px row. `AbilityIconGenerator.cs` now also
  writes them, at `round(32s)` capped at 64: none at 720 and below, 44 px at 982, 48 at 1080,
  64 from 1440 up. They keep their vanilla proportion to the row until the cap. The Mac
  helper does the same; `Test-AbilityIcons.py` compares both byte for byte at ten heights
  and checks the sizes against the rule itself. Seen in game on the Mac at 1512x982 the
  same day: 44 px icons filling their frames. Not yet seen on Windows.

- **The Character screen shows A on Level Up and Y on Auto Level Up, and the
  granted-feats notice shows A on its OK** (2026-09-26, at the maintainer's
  request after a preview found neither had a glyph). The Character screen
  levels up on A and auto-levels on Y itself, with nothing focused
  (`0x006B2295`, `0x006B233C`), so both badges are unconditional; the buttons
  are drawn only while the member on screen can level up. Unlike every badge
  before them, these two stand on a filled button: their box is `dialog2`,
  uniform black at half alpha (read from `swpc_tex_gui.erf`). The build now
  composites a badge over such a fill (`backing` in
  `tools/build_controller_prompt_textures.py`), the module puts `dialog2` back
  whenever the badge is not shown, and the badges are sized like the screen's
  Close and Scripts badges rather than from their own 120 and 156 px buttons.
  The installer's re-placement for other languages slides a badge sideways;
  the columns it vacates now repeat the edge column, so a backed badge keeps an
  unbroken box. Every one of the 26,460 ordinary badges in the build has a
  transparent edge column, and a harness around the real `ShiftColumns` found
  40 of them byte-identical to the old shift at six distances. The notice is
  `skillinfo.gui`, "You have been granted the following feat(s) this level"
  (`CSWGuiSkillInfoBox`, vtable `0x00757940`); its dispatcher closes it on A
  whatever holds focus, so its OK carries a plain A. `Test-ControllerPromptAssets.py`
  checks the backed badges' fills, that everything but the glyph is exactly
  the backing, and that the glyph stays clear of the texture's edges.
  **Seen in game** in a scratch copy of the game at 3440x1440 with `128CDC79…`
  installed, on a copy of the maintainer's save levelled from 12 to 16 on the
  virtual pad alone (2026-09-26 and 2026-09-28): the badges on the Character
  screen, gone once no level is left; the level-up list, Attributes, Skills,
  Feats and Powers with their badges; the granted-feats notice with its A; and
  the "following power(s) have been recommended" notice, which Powers' Y opens,
  with the same A, since it is the same `skillinfo.gui` panel. Not played by
  hand.

- **The status summary shows the pad's A beside OK** (2026-09-25, at the
  maintainer's request: "just add the glyph to the journal entry popup"). The
  box that says "Journal Entry Added", "Item(s) Received" and the like has the
  A left of its OK while a controller is in use, placed as on the confirmation
  boxes: a disc the height of OK, a quarter of its size clear of OK's edge. A
  already pressed OK there; the panel registers OK's handler (`0x00624BA0`)
  for `0x27`. The box widens when one short line would leave no room for the
  A. The game's own `statussummary.gui` has no control for a badge, and KMRP
  does not ship that file, so the module adds one as the panel is built: a
  label loaded from `LBL_JOURNAL`'s definition without taking its place, put
  in the empty slot the file's missing ID 16 leaves in the panel's control
  array, and freed with the panel. The mechanism is in
  [custom-gui-controls.md](reverse-engineering/custom-gui-controls.md).
  **Seen in game on 2026-09-25** in the scratch copy, at 3440x1440 and
  1920x1080: the A left of OK while the pad is in use, gone while the mouse
  is, and A closing the box.

- **Every settings screen shows its controller buttons** (2026-09-25, from a
  play-test screenshot of Advanced Graphics: "add glyphs to all settings
  screens"). Y now presses Default on the nine screens that have one --
  Graphics, Advanced Graphics, Sound, Advanced Sound, Gameplay, Mouse, Feedback,
  Auto-Pause and Key Mapping -- and each Default carries a Y. No settings panel
  answers Y itself, so the module presses the button as a click does
  (`PressDefaultK1`). The five Y registrations the engine has on these screens
  are the gamma and volume sliders' change callbacks (`0x006E0190`,
  `0x006E0F50`), which only re-apply the current value. A follows the focus down
  both Options lists and onto the buttons that open another screen: Screen
  Resolution, Advanced Options, Mouse Settings, Key Mapping and Controller
  Layout. With a pad in use, the - and + of the focused row show the D-pad's
  left and right in their place: Difficulty, Texture Quality, Anti-aliasing,
  Anisotropy, EAX, and every row of Attributes and Skills. Their own art comes
  back when the row loses focus or the mouse is used. Portrait's arrows and
  Pazaak's wager show them all the time, since they act whatever holds focus,
  and the wager also gets A on Wager and B on Quit. That is 30 badges and 42
  arrow glyphs a resolution, for each controller family.
  `Test-ControllerPromptAssets.py` checks every arrow's art, size and centring,
  and which side each glyph lights. This reverses the 2026-09-08 rule that
  Default takes no badge, which held while no controller button pressed it.
  **Seen in game on 2026-09-25**, from screenshots of a scratch copy of the
  game at 3440x1440 with `D407BF3A…` installed, driven by the virtual pad
  (`testing/controller/virtual_pad_server.py`): every Default's Y, the A on
  the focused Options entry, Screen Resolution and Mouse Settings, the D-pad
  glyphs on Difficulty, Texture Quality, Anti-aliasing, Anisotropy, EAX,
  Attributes, Skills and Portrait, the arrows' own art back on rows without
  focus, and Y resetting Advanced Graphics to the engine's defaults. The
  wager and the other controller families were not seen, and nobody has
  played it by hand yet. **Correction, 2026-09-28:** the D-pad glyphs on the
  - and + are gone again at the maintainer's request, and the arrows keep the
  game's art (under Changed). The badges, and Left and Right changing the
  value, stay.

- **X disengages and Y cancels the last queued action, in combat**, each with
  its badge on the HUD. The engine has both buttons: Disengage (`BTN_CLEARALL`)
  and a "clear one" button over the action queue (`BTN_CLEARONE`). The second
  calls `OnCombatYButton`, which removes the last queued action and, once none
  is left, clears everything -- the Xbox build's Y in combat, by its name. On
  PC they took a mouse click; nothing routed a button to them. Now the pad
  presses them through the engine's own click handlers, so a press is exactly a
  click, first-time tutorial included, and only while the button is on screen.
  - **X** disengages: combat mode off and the whole queue cleared, as the
    on-screen button does.
  - **Y** removes the last queued action; pressed again with the queue empty,
    it clears everything too.

  An X badge beside Disengage and a Y beside the queue show only while those
  buttons do, and only with a pad in use, in all four controller families. At
  every resolution they are placed from the buttons themselves, and
  `Test-GeneratedGuiGeometry.py` checks their size, placement, and that they
  cover no button or queue icon at all 49. The Controller Layout screen now
  reads "Disengage / Menu action" for X and "Undo action / Menu action" for Y,
  where both said "Screen action". **Untested in game.**
- **Controller glyphs on every character-creation and level-up screen**
  (issue #21). There are 42 badges in all four controller families, on class
  selection, Quick or Custom, both step lists, Portrait, Attributes, Skills,
  Feats, Name, the level-up list and Powers:
  - **B** is Cancel or Back;
  - **Y** is Recommended, or Random Name on Name;
  - **X** is Feats' Add Feat and Powers' Select. Feats' own A and X are the
    other way round, and the module swaps them there, at the maintainer's
    request after a play-test screenshot, so every screen has A on OK;
  - **A** follows the focused step on the step lists, and sits on each other
    screen's own A button.

  Every glyph is a button the screen's own dispatcher answers; the handler
  addresses are in the module's tables. Tags, indices, empty fills and widths
  were checked in all 49 archives before the targets went in. The Quick or
  Custom, step-list and Portrait screens were also missing from the module's
  menu-panel list, so no badge could have shown there. **The D-pad now picks
  portraits** on the Portrait screen, as LT and RT already did. The class
  portraits and the +/− arrows carry art and take no badge. A pad still cannot
  type a name; Random Name works. The full table is in
  [controller-prompt-specification.md](docs/controller-prompt-specification.md).
  **Seen in game on 2026-09-25**, in the same scratch copy, on every
  character-creation screen; level-up and Powers were not reached. The notice
  Feats opens with, "You have been granted the following feat(s) this
  level", has no badge on its OK.

- **The installer's window says v1.5.0.** Its label was a hardcoded `"v1.0.0"`,
  a second copy of the version that did not follow `PatchVersion` to 1.5.0. It
  is derived from `PatchVersion` now.
- **The installer says when a newer KMRP is out.** When its window opens, it
  asks GitHub once, in the background, for the repository's latest release. If
  that release is newer than the installer, a dialog offers **Download**, which
  opens the [Deadly Stream page](https://deadlystream.com/files/file/3096-kmrp-kotor-modern-restoration-patch/), and **Skip version**.
  A switch names the version on offer, *Don't remind me again for 1.6.0*. It
  stops that one version from being offered again, whichever button closes the
  dialog; a later one still is, and nothing turns reminders off for good. The
  first layout was replaced the same day as unintuitive: a plain **Skip**, and
  a switch titled only *Don't remind me again*. The version turned off is
  remembered as `skippedUpdate` in
  `%LOCALAPPDATA%\KMRP\settings.json`.
  - **What it sends:** one HTTPS request carrying only the User-Agent GitHub
    requires, `KMRP/1.5.0`. The command-line modes never make it.
  - **What it reads:** only the tag name, digits and dots. The Download link is
    fixed in the installer, never taken from the answer.
  - **Failures:** it gives up after five seconds. Any failure is silent:
    offline, rate limited, or a tag that is not a version.
  - It never appears while a patch or restore is running.

  Releases must now be tagged with the public version. On 2026-09-25 the 1.0
  release moved from tag `v2.10.0`, its internal number, to `v1.0.0` on the
  same commit, because 2.10.0, read as a version, is later than 1.5.0, and every
  1.5 player would have been offered 1.0. `Test-UpdateCheck.ps1` checks the tag
  parsing, the comparison, the remembered version, and that case. Asked live,
  GitHub answered 1.0.0, and the check stayed quiet. **The dialog has been drawn
  to an image, not seen over the real window, and its Download has not been
  clicked.**

- **Rumble modes, Off, Original and Enhanced, with haptics beyond what
  shipped.** **Felt on an Xbox pad on 2026-09-25 and judged right**, after four
  pad tests that tuned it; what was and was not covered is listed in
  [controller-rumble.md](docs/controller-rumble.md). A single
  mixer in the controller module (`K1Rumble.cpp`) now plays every rumble,
  BioWare's included. It takes each motor's maximum across everything playing,
  and it records what kind each rumble is:
  - **Original BioWare rumble.** The shipped mappings, unchanged: the grenades,
    the Stomp footsteps, Force Choke, Push and Wave, the terentatek, the
    Korriban ceiling and obelisk, and the Endar Spire.
  - **Restored cut BioWare rumble.** Rows 0 `LightSaberOn` and 21 `Whirlwind`,
    which nothing shipped fires. They now play while the controlled character
    holds a lit saber, and while it is caught in Force Whirlwind. These
    attachments are KMRP's; what fired the rows on Xbox is not known.
  - **KMRP Enhanced haptics.** 25 patterns of KMRP's own, named `KMRP_…` and
    numbered from 100:
    - melee hits, a saber's or any other weapon's, felt as the blow lands;
    - saber ignition and retraction, hits (a swing that meets nothing is
      silent), parries, deflections and the saber feats;
    - blaster recoil by weapon class, for the controlled character only;
    - damage received, scaled by the share of health it took and merged within
      50 ms, and death;
    - lightning, drain, Force buffs and stun;
    - droid explosions, the poison and adhesive grenades, rockfalls, and the
      space-laser strike;
    - the Rancor's death, on BioWare's Rancor row.

    None of it existed on Xbox.

  Every one-shot pattern holds its peak for 100–180 ms and runs 0.3 s or more,
  because the first combat test showed shorter ones reach the pad but are not
  felt. Enhanced plays BioWare's positional rumble -- grenades, Force Push, the
  Stomp footsteps -- measured from the controlled character rather than the
  engine's sound listener, reaching three times BioWare's cutoffs under 10 m
  (grenades 15 m instead of 5 m), and fading with distance to nothing there.
  Original leaves it to the engine, full strength inside the 2DA's cutoff, as
  vanilla does. Rumble is silent in menus, pause, fades and load screens, and
  stops on death.

  `kmrp-controller.ini`, beside the game, sets Mode, Strength (0–100%),
  SaberHum (0–100% of BioWare's hum level, default 6), SaberHumPulseMs
  (default 100), SaberHumPeriodMinMs and SaberHumPeriodMaxMs (default 500 and
  2000; the gap before each pulse is drawn at random between them, as settled
  in the third pad test), and Debug. The first pad test
  (2026-09-25) found BioWare's hum at its full 0.20 far too strong. The second
  found even an Xbox pad's weakest steady vibration, 1% of full power, too
  strong, so the hum now pulses that level by default. The installer writes it once and never overwrites an edited copy.
  `Debug=1` logs every rumble event to `kmrp-rumble.log`. It defaulted to 1 in
  the hardware-test builds and is 0 since they passed.

  There are eight new hooks. One of them declines `PlayRumblePattern`'s own
  queue, so the mixer alone drives the motors. All eight pass
  `check_hook_stolen_bytes.py` and `check_patcher_hook_table.py`. All 170
  pattern arrays are in the compiled module byte for byte.
  `Test-ControllerSupport.ps1` passes, with a new case for edited settings, and
  so does `Test-ReinstallOverOlderBuild.ps1`.

  Deferred, with the reasons in
  [controller-rumble.md](docs/controller-rumble.md): critical hits, the Krayt
  dragon, doors, the swoop and turret minigames, damage types, and an installer
  or in-game control for the settings.

- **Rumble uses BioWare's own patterns, all 22 of them.** The rumble KMRP
  restored earlier ran on nine envelopes KMRP had authored, one for each index
  the shipped content fires, with every other index silent. BioWare's data was
  thought lost with the Xbox build. It is K1's `rumble.2da`, published by the
  OpenKotOR wiki ([rumble-k1.md](https://github.com/OpenKotOR/wiki/blob/main/wiki/odyssey-engine/2da/rumble-k1.md)), and the module now installs it
  verbatim:
  - 22 rows, 0 to 21, with their keyframes, sample counts and looping flags;
  - generated from that page by script, and validated row by row (counts match
    the filled cells, times ascend, magnitudes stay within 0 to 1);
  - checked in the compiled module, where all 78 arrays appear byte for byte.

  Every rumble the game fires now feels as it did on Xbox: the grenades
  (FragGenade), the Stomp footsteps (Heavy_step), Force Choke, Push and Wave
  (Critical_hit), the terentatek (Rancor), the falling ceiling on Korriban, and
  the Endar Spire's tremors (Endar_01, Endar_02). The row names match those
  indices, which identifies the table. The engine's three rumble entry points
  pass the index as data, so nothing is fired that content does not ask for;
  the two looping rows, LightSaberOn and Whirlwind, are fired by nothing
  shipped. How the envelope evaluator treats rows with an empty motor or a late
  first keyframe was read from its code before relying on it. **Not yet felt on
  a pad.**

- **2880x1620, the 49th resolution** (issue #16), for DSR at 2.25x on 1080p
  screens. High Resolution Menus has no layout for it, and its layouts are made
  by hand per resolution, so scaling one does not reproduce another. But
  2880x1620 is exactly halfway between two it does ship, 1920x1080 and 3840x2160,
  so `tools/derive_resolution_gui_set.py` interpolates every field halfway:
  - an extent upstream doubles comes out 1.5x;
  - one it holds fixed, such as the list prototypes, stays fixed;
  - a hand adjustment lands between its two values.

  The same method, run at a third of the way, reproduces upstream's real
  2560x1440 set: 87.6% of its 9,276 extent fields exactly and the rest within
  1 px, against 73.9% for plain scaling. It gets its own 2.25x font set. The
  installer's catalog check, the build's resolution count and the
  virtual-display profile now expect 49. **Not seen in play**, since no
  maintainer screen runs 2880x1620.

- **An A beside the highlighted dialogue reply** (issue #21), at the end of the
  reply's last line since the third play-test (below); it was first placed left of
  the reply's number, following the highlight like the main menu's A. It shows only
  while a controller is in use and replies can be picked, and it hides while a
  line plays, when A would skip it instead. Every resolution now ships
  `dialog.gui` to carry the label. Below 3440x1440 that is a vanilla-equivalent
  file rebuilt from the tuned 3440x1440 asset, differing from the game's own
  only in four colour floats in the seventh decimal. The art is the confirm
  boxes' A, in all four families. **Untested in game.** Two of its inputs --
  which field holds the highlighted row, and which space the row rects are in --
  are read from the disassembly, not measured. It writes a `dialog-geometry`
  line to `kmrp-layout-lifecycle.log` the first time each conversation shows
  replies, so one play-test confirms the placement or shows how to fix it.

  **That play-test (2026-09-25, 3440x1440) found it off screen.** The log
  confirmed both inputs: the rows are relative to the list, and `[panel+0x68]`
  and the list's own index agreed. But it read `placed=(-77,0,32,32)` for a panel
  at x 48, which is screen x −29. The rows are 3312 px wide in a 3344 px list,
  because the list's 32 px scrollbar sits on their left, and the A had been
  placed from the row's edge rather than from where the text starts. It is now
  placed just left of the text (list left + scrollbar width), clamped to the
  screen. At 1920x1080 the same rule gives the text start seen in a screenshot,
  48 + 16 = 64 px. **The corrected placement is untested in game.**

  **The second play-test (same day) still showed no A.** The log read
  `placed=(-41,0,32,32)`: correctly just left of the text, but at a negative x
  inside the dialogue panel, and the engine does not draw a panel's children
  outside the panel. Nothing left of the reply text can be seen, because at
  3440x1440 the text begins at the panel's own left edge; the screenshot shows
  the "1." starting at exactly that edge. **So the A now sits at the end of the
  highlighted reply's text**, which is where the maintainer asked for it. The
  engine measures the text itself (`CSWGuiText::GetIdealWidthAndHeight`, the
  function its tooltips use), once whenever the highlight or the replies
  change. The A goes a quarter of a glyph past the text, and a reply that wraps
  gets it on its last line. The log line now carries `textWidth=`. **Untested
  in game.**

  **The third play-test (same day, `AD3DC07D…`) showed the A mid-sentence**,
  over "of" in "Can you show me one of the visions again?". The log read
  `textWidth=320`, but the screen showed that line at about 600 px: the
  engine's measure read about 1.875 times short. **The A now sits at the end of the
  highlighted reply's last line.** That line's width is read from the layout
  being drawn: the text object's line lengths and the font's own glyph
  rectangles, at one atlas texel per pixel. The A is centred on that line,
  keeps the height of a one-line row, and sits an eighth of its size past the
  text. The log line now carries `lineWidth=`, `lines=`, `textScale=` and the
  render viewport. **Untested in game.**

  **The fourth play-test (same day) placed it at the end of the line**, and
  the maintainer asked for three changes. The gap is now half the badge; an
  eighth, with the art's rim, still touched the last letter. The badge sits
  half a text line lower, using the reply font's own `fontheight`. It is a
  quarter larger than a one-line row: 40 px at 3440x1440, against 32. The log
  line adds `lineHeight=`. **Untested in game.**

  **The fifth play-test (same day) found it low**, and the maintainer asked for
  "vertical lineheight based centering". Measured on that screenshot, the
  reply's capital tops and baseline sit 11 and 28 px into its 32 px line at
  3440x1440. So the letters' middle is 19.5 px down, and the A's middle was at
  32. The A is now centred on its line's letters: 5/8 of the line height below
  the top of the reply's last line, 20 px at 3440x1440. A reply's lines are
  centred in its row. The two builds before put the A's middle at half a line
  (seen as sitting high) and at a whole line (seen as low). **Measured in
  game on 2026-09-25** in the scratch copy, on Trask's first reply at
  3440x1440: the A covers rows 1206 to 1233, centre 1219.5, and the reply's
  capitals and baseline rows 1210 to 1229, centre 1219.5. Not yet played by
  hand.

  *Corrected 2026-09-25:* this entry, the code and commit `f423d03` blamed the
  text object's scale (`+0x40`), put at about 0.53. The next play-test's own log
  line read `textScale=1.0000`, so that is not the cause, and why the engine's
  measure read short is not established. The new placement does not depend on
  it. It reads the drawn layout, and the same log gave `lineWidth=435` and
  `470` for two replies. Whether the A then sat at their ends was not reported.

- **Menu and dialogue text is drawn at the size it was rendered at** (issue
  #16). Two players reported pixelated, aliased text, one at 1920x1080 and one
  at 3440x1440, which ruled out any single resolution being at fault. The font
  atlases were baked once at scale 3.0 and reused everywhere, with the
  per-resolution TXI rescaling `texturewidth` — and `texturewidth * 100` is what
  turns glyph coordinates into texels, so it matched the atlas's real width at
  3840x2160 and nowhere else. 1080p declared 512 px of a 1024 px atlas, 1440p
  declared 683. Every font TXI also carries `mipmap 0` and `filter 0`, so that
  resampling was point sampled: texels dropped rather than blended, which threw
  away the antialiasing the atlas had, and 1440p's uneven 1.5:1 ratio is what
  made strokes look ragged. Each resolution now ships atlases baked at its own
  scale, so one texel lands on one pixel and nothing is resampled. **The
  typeface is unchanged** — the same Old Republic and Arimo Medium as before,
  baked more than once. Adds about 15 MB to the installer;
  `Test-FontAtlasScale.py` asserts the one-texel-per-pixel invariant for every
  font at every resolution. 15360x8640 is the one exception and still resamples,
  because its scale-12.0 atlas is larger than the baker can produce.
  **Play-tested on 2026-09-25 at 3440x1440**, the second reporter's
  resolution: the text reads right. 1080p, the first reporter's, has not been
  checked in play.

- **The mouse stays inside the game window** on multi-monitor setups (issue
  #20). KOTOR steers the camera with mouse movement but never clips the cursor,
  so a wide enough sweep put the pointer on the next display and the camera
  stopped following. The cursor is now clipped to the game window's client area
  whenever KOTOR is the foreground window, and released on Alt-Tab, on losing
  focus, on minimise and on exit — a crash cannot leave it trapped, because the
  clip does not outlive the process. The game imports no `ClipCursor` of its
  own, so nothing in the engine is being overridden. It first shipped inside
  the optional controller component, so a player who declined that component
  did not get it; since 2026-09-28 it installs either way (under Changed). See
  [controller-support.md](docs/controller-support.md). Untested on real
  multi-monitor hardware: the maintainer has none to test on. Issue #20 was
  closed on 2026-09-28 on that basis, with a note asking anyone whose cursor
  still escapes to reopen it.

### Changed

- **The patcher's second step names the game version** (2026-09-30, at the maintainer's
  request: "drop the verify editable exe ... It should automatically say which one is it
  Steam or GOG ... or the editable one"). "2. Verify Editable EXE" is now "2. Detect Game
  Version": beside its badge it names what it found -- Steam, GOG or Editable -- and its
  subtitle says so ("The Steam version of KOTOR detected.") or which file it could not use.
  The recovery it grew into when the file was not the editable build, "Get Editable EXE" (a
  link to the Deadly Stream page) and "Check Again", is gone: every version KMRP knows is
  installed as it is, and the window checks again whenever it is activated. The room the
  card kept for it stays, so the window keeps its proportions (the Mac's copies them). The
  resolution list now starts at this display's size (`EnumDisplaySettings`, in pixels, since
  the patcher is not DPI-aware), where it started at 3440x1440.
- **Advanced Settings has no *KOTOR Patch Manager* option any more** (2026-09-30, the
  maintainer: "I feel like the kpm option in advanced settings is redundant now right?").
  It chose an install for KPM -- KMRP's files and data, no runtime, KMRP's patches ticked in
  KPM -- where KPM did not manage the game yet. The installer still chooses that install by
  itself where KPM's runtime is in the game folder, and anywhere else KMRP's own install is
  one KPM recognises and takes over when its Apply is pressed (`kpm_install_state.json`,
  the KPM-format backup, the `.kpatch` files in KPM's folder), so the option decided only
  who installed the runtime first. On Steam with KPM 0.7.1 it also left the runtime to KPM,
  which injects unless "Use library proxy" is ticked, and a game Steam starts then ran
  without KMRP. The saved `kotorPatchManager` key is no longer read or written.
  `Test-KpmEdition.ps1` now gives its for-KPM fixtures stand-ins for KPM's runtime, and its
  Case 9 checks that a settings file with the old key on changes nothing. Advanced Settings
  is back to three rows.
- **The patcher finds Steam's and GOG's KOTOR by itself** (2026-09-30, at the maintainer's
  request: "can we auto detect steam version if its there? cus macos can do that"). Step 1
  started at `swkotor.exe` beside the patcher or in the current folder, and otherwise asked
  for Browse. It now also looks where Steam installed app 32370 -- Steam's uninstall record,
  then every library `steamapps\libraryfolders.vdf` lists, at the folder its appmanifest
  names (`steamapps\common\swkotor`), as `kmrp-mac.sh`'s `find_game` looks on the Mac -- and
  then at GOG's registry entry for the game (`GameFolders`). The registry and Steam's own files
  are read; no drive is searched. On the test PC it found Steam's install in the first of
  three libraries (identified as Steam) and GOG's entry for the main game folder (the editable
  build); a harness listing `GameFolders.Installed()` was the check. **Browse** is unchanged.
- **The patcher header's smoke fades out before the header's bottom edge** (2026-09-30,
  `docs/windows-changes-from-macos.md` item 11, found on the Mac's port of the same code). The
  smoke and the motes are drawn only inside the header, and where the plume reached furthest
  they stopped on a straight line beside the card. Both are now multiplied by the Mac's
  `BottomFade`, a smoothstep from 1 at 70% of the header's height to 0 at its bottom. **Not
  yet watched on Windows.**

- **No release carries anything taken from the game any more** (2026-09-29, Windows and
  macOS, after an audit the maintainer asked for). Three things did:
  - the four hex frames list rows tile behind item icons (`lbl_hex`, `lbl_hex_3`,
    `lbl_hex_6`, `lbl_hex_7`, at `56s`), exported from the build machine's texture pack into
    every resolution's archive;
  - the tutorial popup's thirteen `tut_*` icons (`64s`), exported the same way;
  - `tutorial.2da`, the game's table with its `icon` column pointed at those copies, committed
    to the repository and shipped in `override-common.zip`.

  Both installers now make all eighteen at install from the player's own game:
  `src/patcher/GameArtGenerator.cs` on Windows and `macos/tools/kmrp-gameart.c` on the Mac.
  They read `TexturePacks/swpc_tex_gui.erf`, and `tutorial.2da` through `chitin.key` from
  `data/2da.bif`. `Test-GameArt.py` checks them:
  - the two are byte-identical at 48 heights, on both Mac slices;
  - an independent Python reference agrees;
  - every texture has the size the sets shipped (1,122 compared);
  - `tutorial.2da` is byte-identical to the file that was committed.

  One difference is deliberate. The build decoded the DXT5 sources with pykotor, which weights
  the eight-level alpha codes by i/7 instead of (i − 1)/7. The installers use the standard
  formulas, so at 1964 the colour is identical to what shipped and the alpha differs by up to
  36 on soft edges.

  If the texture pack or `chitin.key` cannot be read, none of the eighteen is installed and the
  game keeps its own: its small icons then tile in the enlarged popup, and its frames tile in
  the enlarged rows. On the Mac, a blended size now gets its icons at exactly its own `64s`
  instead of the nearest set's. The build also now refuses to ship the game's own font art.
  It never did, since all 18 fonts have KMRP atlases, but nothing enforced it.

  The same audit compared every image in both installers with the game's texture pack; nothing
  else is the game's art (THIRD_PARTY_NOTICES.md, *The game's own files*). The Windows side
  compiles as C# 5 against .NET Framework 4.8, checked on the Mac, but has not been built or
  run on Windows.

  *Updated the same evening, merging it into the Windows work:* built and run on Windows.
  The installer `4EEA6F04…` (161,432,064 bytes) carries none of the eighteen, checked in all
  66 archives, `override-common.zip` and the layout pool. `Test-GameArt.py`'s checks, run
  through a harness because the machine then had neither clang nor the .NET 8 SDK:
  `GameArtGenerator.cs` compiled with .NET Framework's `csc`, as the installer is, and
  `kmrp-gameart.c` built with MSVC for x64 (`/fp:strict`) made the same bytes at all 48 set
  heights, matched the Python reference at five, and `tutorial.2da` passed against pykotor.
  The x86 build of the helper was not compared: Bitdefender quarantined it each time it was
  linked, a false positive on a test build that ships in nothing. Installed in a scratch copy
  at 3440x1440, the eighteen files were byte-identical to that output, and in game the
  inventory drew each hex frame whole around its item. The tutorial popup's icons were not
  seen: no tutorial comes up in the save used. All nine Windows suites passed on
  `4EEA6F04…` with the same counts as on `D25212D7…`. The merge needed `GameArtGenerator.cs`
  in four more compile lists -- the resolution-site lister in `build_kmrp.ps1`, where the
  first full build stopped, the NVIDIA and update-check self-tests, and
  `Restore-TestNvidiaProfiles.ps1`, which every suite runs.

  Later that evening, with LLVM's clang and the .NET 8 SDK installed, `Test-GameArt.py`
  itself passed on Windows, the helper built as one x64 program
  (`testing/regression/native_helpers.py`): byte-identical to the C# at the same 48 heights,
  the Python reference and `tutorial.2da` as before. Its two comparisons with what the build
  shipped had nothing to compare, since the new archives no longer carry those textures; the
  Mac run against the older archives stands for them. Two things in the test had assumed
  macOS and were changed: the Python reference's temporary files, which Windows will not let
  a second writer open, and the helper's paths, now given with forward slashes, the only
  separator the helpers split on.

- **Turning controller support off no longer removes fixes that have nothing to
  do with controllers** (2026-09-28, at the maintainer's request). KMRP's
  runtime -- the KOTOR Patch Manager hook engine and KMRP's module -- installed
  only with the optional controller component, and so did every run-time fix
  it carries. A player who unticked Controller Support also lost the three
  memory-safety fixes (the texture-bucket overrun, the grass double free, the
  save-buffer leak), mouse confinement (issue #20), the black bars beside a
  narrow movie, and the status summary fitting KMRP's larger text. The runtime
  now installs on every patch, with its ASI loader:
  - **always:** the seven core hooks -- the movie window's two, the four
    memory-safety byte patches and the save-buffer hook;
  - **with controller support** (the default, unchanged): the controller's 30
    other hooks, 37 in all, the same table as before;
  - **without it:** two core stand-ins at controller sites instead,
    `CoreGuiFrameK1` (mouse confinement and the status summary's layout) and
    `CoreMovieFrameK1` (the movie bars), 9 hooks in all. Nothing that reads the
    pad, draws a prompt or rumbles is installed.

  The core hooks come first in `patch_config.toml`: KPM's runtime stops at the
  first hook that fails, so no controller hook can keep them from applying.
  Which hook belongs to which install is one new key, `install`, in
  `src/controller-native/kotor1.hooks.toml`; `tools/kmrp_controller.py` derives
  both sets from it, and `Test-ControllerSupport.ps1` checks both installs
  against it, and switching the option on an installed game both ways. The
  option's name and default are unchanged; the file names still say
  "controller", since renaming them would orphan older installs' manifests. A
  foreign `patch_config.toml` still skips the whole runtime, as it skipped the
  controller component before. **Seen in game on 2026-09-28** in the scratch
  copy at 1920x1080 with `C77F7640…`, read from the running game's memory:
  - **controller off:** of the 37 distinct hook sites, exactly the 9 core
    ones held a jump and the other 28 their original bytes. The bars beside
    the 4:3 LucasArts logo measured pure black (0) against the movie's own
    dark edge (about 12). The D-pad moved nothing on the main menu, and no
    badge showed. A 100x100 cursor clip set from outside was replaced by the
    game's own within half a second, which only the per-frame confinement
    does; with no game running the same clip stayed;
  - **controller on,** reinstalled over it: all 37 sites hooked, the D-pad
    moved the main menu's focus, and the cursor was confined as before.

  The status summary's layout without the controller was not seen: no box
  came up in that session. It is the same function the controller path runs.

- **Item icons sit in their slots at the game's own size** (2026-09-29, Windows and
  macOS, at the maintainer's request: "can we keep the same ratio for inventory items
  within their frame? I think they are too big now", then "normalize all of the HD pack
  icons to make them have the same size"). The game draws an item icon scaled to its slot,
  so what sets its size in the frame is how much of the canvas the picture fills.
  Measured at the half-opaque edge, the game's own 64x64 icons are all drawn to one size:
  a median of 39 px of 64, half of them within 37-41, and the same for armour, weapons and
  items. The HD Icon Pack's pictures span 0.56 to 0.95 of theirs, and the weapons' median
  is 0.82. The HD items therefore sat larger in their frames than vanilla's, and a robe's
  sleeves reached past the inventory's hex frame at 1512x982. The build's existing resample
  of the pack (192 to 160 px) now also sizes each picture to 39/64 of the canvas, centred
  (`ICON_PICTURE_SPAN`, `frame_icon` in `tools/prepare_universal_resources.py`). Measured
  in the shipped DXT5 files, all 351 are 96-100 px of 160, 232 of them exactly 98, and
  centred within half a pixel. Before, they ranged from 89 to 155 px. No picture loses a
  pixel: the build refuses one that would. The size of the files is unchanged, 8.6 MB.
  A rebuild of every resource with the change matched the previous one in every file but
  `override-common.zip`, and there in every entry but these 351. Seen in game on the Mac at
  1512x982 the same day: the robe inside its frame, and the arm band and shield clear of
  the frame's edge. Windows gets it from the next build that does not reuse resources;
  not yet seen there.

- **The - and + arrows keep the game's own art** (2026-09-28, at the
  maintainer's request: "I dont want the dpad leave the + and -"). Since
  2026-09-25 the focused row's arrows on the settings screens, every row of
  Attributes and Skills, Portrait's arrows and Pazaak's wager showed the
  D-pad's left and right in their place. The 42 glyphs a resolution are no
  longer built or installed, and the module no longer swaps them in; the
  installer is 4.3 MB smaller (`9736B41F…`). The D-pad still changes the
  value: Left and Right press the row's arrows as before.
  `Test-ControllerPromptAssets.py` now fails if any archive carries a D-pad
  arrow glyph (`kmr?dl_*`, `kmr?dr_*`). **Seen in game** in the scratch copy
  at 3440x1440: Gameplay's Difficulty shows the game's - and + with the pad
  in use, and D-pad right still took it from Normal to Difficult; at
  1920x1080 the same, and Skills' + keeps its art on level-up.

- **The Abilities screen's swap-tabs cue sits beside Close** (2026-09-25, at
  the maintainer's request). The X-and-arrows cue that says X cycles Skills,
  Powers and Feats sat past the last sub-tab, at the top. It is now in the
  bottom bar with the screen's other button prompts: a third of its height
  left of Close, centred on it, and the size it was. `add_subtab_swap_cue`
  places it from each resolution's own Close and refuses a spot over a
  button or another cue; all 49 resolutions place it, 6 to 108 px clear of
  Close.

- **The installer is 60.5 MB smaller**: 145,208,320 bytes, down from
  208,672,256. Explorer lists it as 141,805 KB instead of 203,782 KB; the
  maintainer asked why it had grown to "203 MB". It embedded all 49
  per-resolution archives, 118.2 MB, to install one. Most of their files are
  the same bytes at several resolutions: a prompt badge is drawn for its
  button's size, and many buttons are the same size at many resolutions. The
  archives held 27,342 files, and 11,930 of them were distinct. (MB here as the
  build prints it, 1,048,576 bytes. 29 MB of the growth came with the
  character-creation badges, `189DF101…` above.)

  The installer now embeds one pool, 57.7 MB, holding each distinct file once
  and an index per resolution. A new build step makes it
  (`tools/pack_resolution_layouts.py`), and the installer rebuilds the chosen
  resolution's files from it (`GuiPool` in `src/patcher/KmrpPatcher.cs`). What
  reaches Override does not change. Three checks hold it there:
  - **At build time**, the packer rebuilds all 49 resolutions from the pool. It
    stops the build unless each has its archive's names, in its archive's
    order, with the same SHA-256s. It was proved on five kinds of damage planted
    in a pool, and stopped on each: a changed object, a missing object, an index
    line pointing at another object, an index missing its last file, and two
    names swapped. Two runs over the same archives give the same bytes.
  - **At install time**, each file written from the pool must match its
    object's name, the first 16 hex digits of its SHA-256. Otherwise the install
    stops before replacing anything. A prompt badge moved for the player's own
    `dialog.tlk` is exempt, since it is meant to differ.
  - **Through the real installer**, the new `Test-InstalledOverride.ps1`
    requires a fixture's Override to hold exactly the files of
    `override-common.zip` and the resolution's archive, byte for byte. It also
    requires Override to be empty after restore. It passed at all 49
    resolutions on `4EF3C181…`, and at 3440x1440 on `DB9D7A08…`, which still
    embedded the archives. With one byte of `abchrgen.gui` changed in a copy of
    the archives, it failed and named that file.

  The old and new installers were also compared directly, once, at 3440x1440.
  That fixture had the texture pack, and a copy of `dialog.tlk` with its 55
  prompt labels lengthened. So 420 badges were moved and 302 ability icons
  were generated, the two paths a plain fixture never reaches. Both installers
  wrote the same 1,714 files, the same patched executable and the same
  Override manifest. The new installer then upgraded the old one's install to
  those same files. It restored both fixtures to the clean
  executable and an empty Override.

  The archives stay in `build\kmrp\resources`, where the Python checks read
  them. The pool is written one folder up, as
  `build\kmrp\resolution-layouts.zip`, so no check that globs the resources
  folder picks it up. One side effect: an installer missing its interface files
  now also removes the backup folder it has just made, rather than leaving it
  to block the next attempt. The files are now opened inside the install
  transaction rather than before it.

  Not done: a solid archive. It would also shrink files that are close but not
  identical, such as one badge a pixel wider. But the installer is .NET
  Framework, which reads Deflate and nothing stronger, so it would need a
  decoder shipped inside it. Its saving was not measured.

### Fixed

- **The target's action buttons cut off, at every size but 3440x1440** (2026-10-01; a
  tester's screenshots at 1920x1200, Windows and the Mac alike). The engine clips the target
  menu at the name box's right edge (`LBL_NAME`). Since 2026-09-05 the name strip has been
  scaled by height while the buttons kept High Resolution Menus' width-scaled places, so the
  second and third button reached past it (250 px against 377 at 1920x1200). The whole target
  menu now follows one rule, `target_menu_extents` in `tools/apply_gold_hud_proportions.py`,
  from the play-tested 3440x1440 HUD: the strip at `max(1, H/720) / 2`, the buttons and their
  icons 1.5 times that (the maintainer, in play at 1512x982), centred under the bar and 8
  gold pixels below the health line, the bar widened only where the buttons need it. 3440x1440
  itself, whose HUD is gold's own file, gets the same. Gold's first slot had its up and down
  arrows swapped, a slip of its hand editing; read the right way up. `Test-GeneratedGuiGeometry.py`
  checks every target control at all 66 sizes and that no button ends past the name box.
  Seen in play at 1512x982 on the Mac (an enemy, a door); not yet on Windows.
- **macOS: A on a door did nothing after an action slot had the focus** (2026-10-01, in play).
  The action bar's focus outlives the target: a slot focused on an enemy stayed focused on a
  door, which has no actions there, and A pressed the empty slot while the world's default
  action was declined (76 such presses in one session's log). A focused slot now holds A
  only while it can act (`hud.cpp`, `ActionBarFocused`). Windows' `IsActionBarFocused` makes
  the same test (`docs/windows-changes-from-macos.md`, item 18).
- **Windows: the same for A after a stale action-slot focus** (2026-10-01, from the Mac). A
  uses a focused action slot, and the world action is declined, only while that slot can act
  (`IsActionBarFocused`, with `IsActionButtonSelectable`, the D-pad's own test); B still lets
  go of any focused slot (`KmrpActionBarHeldK1`). Not seen in play on Windows.
- **macOS: the installer patches to the resolution macOS is set to** (2026-10-01; the
  maintainer: "I want it to patch to the currently running resolution"). On a Retina display
  it chose the pixel size (3024x1964 on a 14" MacBook Pro), which a tester reading 1512x982 in
  System Settings took for a wrong guess. The current resolution is now first and chosen; full
  Retina sharpness is the second choice (`--resolution current|native`; `half` still works).
- **Credits** (2026-10-01, the maintainer): KMRP's Windows patches are RaymanGT's; the Mac
  patch, `kmrp`, is RaymanGT's and FTD's, who laid its foundation. FTD's own widescreen patch
  manifest also names J and Vriff.

- **macOS: KotOR Patch Manager's own window over KMRP** (2026-10-01; built and run on a Mac
  with KPM 0.7.1, the current release, `KotorPatchManager-macos-arm64-v0.7.1`). Four fixes
  found by doing it:
  - KPM 0.7.1 refused `kmrp.kpatch` outright: the controller's movie hook took its argument
    from `rbp-0x4b0`, a parameter source added to KPM after 0.7.1. It now takes `rbp` and the
    handler subtracts `0x4b0`; all four builds pass 0.7.1's own KPatchCore (`LoadPatch`,
    `ValidateHooks`, no overlaps). A and Start still skip movies (the maintainer, in play).
  - KPM's Apply empties `patches/` and puts back only each patch's module, so the controller's
    `kmrp-sdl3.dylib` there was deleted and the pad fell back to Apple's GameController. SDL
    now goes beside `KOTOR_Exe` and the module looks there after its own folder, as Windows
    does (`K1ControllerBackend.cpp`).
  - Uninstall after that Apply took KPM's runtime half out: it found a takeover only from
    `patch_config.toml` changing, and KPM writes it byte for byte as KMRP does (as it does
    `kmrp.dylib`), while `KOTOR_Exe`, `KotorPatcher.dylib` and `kpm_install_state.json`
    change. A takeover is now any recorded runtime file changed, except a `KOTOR_Exe` back to
    the untouched game. The maintainer's install was put back by hand, the leftovers kept in
    `~/KMRP-mac-backup/2026-10-01-kpm-takeover`.
  - With KMRP KPM's only patch, uninstall now also removes KPM's runtime as KPM's own Remove
    would (`addresses.db` included), leaving the untouched game and nothing to untick in KPM;
    beside another KPM patch it is as before. Windows does neither yet
    (`docs/windows-changes-from-macos.md`, item 16). (*It does both since the same day:
    below.*)

  KPM's settings are in `~/Library/Application Support/KPatchLauncher/settings.json` on the
  Mac (KPM 0.7.1 is .NET 8; seen 2026-10-01), one of the two places the script reads.
  `Test-MacInstaller.py`'s round 6 now does both takeovers as KPM 0.7.1 was seen to: 0
  problems. In play: KPM's Apply and launch, then Steam's launch, both ran the game.

- **Windows: uninstall after KotOR Patch Manager's takeover, as on the Mac** (2026-10-01,
  `docs/windows-changes-from-macos.md`, item 16). A takeover is found from any runtime file
  the install recorded having changed, not `patch_config.toml` alone; the game's own
  `binkw32.dll` back over the proxy is not one. With KMRP's patches all KPM has (its config,
  its state file's patch list and `patches\`), Restore removes KPM's runtime too, as KPM's own
  removal would (`addresses.db` and `sqlite3.dll` included), and puts back the untouched
  `swkotor.exe` from KPM's newest backup or by clearing the 4 GB flag, so nothing is left to
  untick in KPM; with another patch in KPM's list the runtime is left to KPM, as before. A
  reinstall over a takeover still installs for KPM and keeps its runtime.
  `Test-KpmEdition.ps1` Cases 10b and 10c; then KPM 0.7.1's own Apply (its command line, not
  its window) on a copy of the game: KMRP alone with injection and with the proxy, and beside
  Fair Pazaak Turn Order, each followed by KMRP's restore, all as above; the game ran with
  KMRP's 95 of 95 runs each time. Fair Pazaak has no module, so only KPM's state file showed
  it was there.

- **macOS: KotOR Patch Manager handled as on Windows** (2026-10-01, the maintainer: "It should
  do the same with kpm as windows"). KMRP's own install now leaves KPM's records as the
  Windows installer does: `kpm_install_state.json` with KPM's identity for the Aspyr build, a
  copy of the untouched `KOTOR_Exe` in KPM's backup format, and `kmrp.kpatch` (now in the
  package, declaring a conflict with FTD's two patches, which it carries) in the patch folder
  KPM's settings name, so KPM recognises the install and can take it over; uninstall then
  leaves KPM's runtime to it. With KPM patches installed that are not FTD's, KMRP installs for
  KPM instead of refusing: the menus and settings, `KOTOR_Exe` and KPM's files untouched,
  `kmrp.kpatch` for the player to tick. An install of FTD's patches alone is still replaced.
  Written on Windows: the script's syntax and its KPM functions checked under WSL's zsh (18
  checks); `Test-MacInstaller.py` extended for it. Built and run on a Mac the same night (the
  entry above).

- **Windows: message popups fit their contents, and the granted popup's rows look like the
  inventory's** (2026-09-30; the Mac did both first, `docs/windows-changes-from-macos.md`,
  items 1 and 10; the maintainer: "you didnt apply the quit game fixes we did on macos").
  Both are the Mac's layout-patch code ported to KMRP's module, which every KMRP patch
  loads, as three detours installed with or without the controller option: the popup fit
  (`K1PopupFit.cpp`, at `FixMessageLabel`'s end, `0x006258E2`) and the granted popup's
  rows (`K1GrantedPopup.cpp`, after its fill hands the rows to the list, `0x006CE0B0`, and
  before each row gives its text its rect, `0x006AB9D5`), with every offset read from the
  Windows executable. Seen in play at 3440x1440: the Exit Game box ("Do you really want to
  quit?") 657x272 px and centred, the Attributes and Skills tutorials and the Solo Mode
  prompt fitted and centred, and the recommended-feat popup cut to its one row with the hex
  as tall as the text frame and the text inside it. `KMRP.kpatch` carries 10 hooks, 40 in
  all four. Installer `17EE496D…`. All nine Windows suites pass on it, `Test-ControllerSupport.ps1` checking the new hooks against the module's exports and KMRP's patch configurations.

- **Windows: the Options check boxes scale with the resolution, and the Feedback list's rows
  with them, on both platforms** (2026-09-30; the Mac scaled the check boxes first the same
  day, `docs/windows-changes-from-macos.md`, item 13). The Options toggles (Gameplay,
  Feedback, Auto-pause, Graphics, Advanced Graphics, Mouse, Advanced Sound) drew their
  circle in a fixed 25x25 square, 2 px below the middle, with the label 30 px in, at every
  resolution (`CSWGuiOptionsCheckbox::SetExtent`, `0x006DE000`). The installer now writes
  `25s`, `2s` and `30s` there: the square's operand in place, the drop's signed byte in
  place, and the label's two signed-byte operands, which `30s` outgrows above 3048 px tall,
  replaced by a jump into the 15 bytes of padding after the function, where they take 32-bit
  operands. Read back from the installer's `--apply`: a 50-px circle, 4 below the middle,
  the label 60 px in at 3440x1440; 38, 3 and 45 at 1920x1080; vanilla's at 720 and below.
  Seen in play at 3440x1440: in Gameplay, Auto-pause and Graphics each circle is 50 px in its
  120-px toggle. In the Feedback list they overlapped, 50-px circles 44 px apart: its rows
  are check boxes too, built at the height of `LB_OPTIONS`'s row template, 43 in every set,
  which the runtime row scale does not reach, so they had stayed 43 px at every resolution.
  The Mac's patch does the same there (68-px circles in 43-px rows at 3024x1964). The
  resource build now scales that template, `round(43s)` (`scale_listbox_padding.py`,
  `FEEDBACK_LIST`): 86-px rows at 3440x1440, nine circles 87 px apart, all nine options on
  screen, measured in play. And at the maintainer's request ("move the points more to the
  right", the scrollbar left where it is) the list's gutter beside its scrollbar is 16 x
  font scale, where it was 6: the circles 36 px from the scrollbar at 3440x1440, where they
  were 16, the scrollbar unmoved (measured in play). `Test-GeneratedGuiGeometry.py` checks the
  rows in the 66 sets; `Test-KpmEdition.ps1` shows KOTOR Patch Manager installs carry the new
  sites; `build_binary_inventory.py` finds every byte documented. Installer `97BEA480…`. The Mac
  gets the rows and the gutter with its next build (`docs/macos-changes-from-windows.md`,
  item 11); not played on the Mac.

- **Windows builds: the Mac sizes' fonts drawn one texel per pixel** (2026-09-30, found by
  `Test-FontAtlasScale.py` while testing the merge). The build takes each resolution's font
  atlases from a cache baked per scale (`build/fonts`, git-ignored, made by
  `tools/build_font_scale_sets.py`). This machine's cache had no set for 16 of the 17 Mac
  sizes' scales, so the Windows builds from 2026-09-29 gave those sizes the shared 3.0 bake,
  resampled -- the ragged text of issue #16 -- and a custom size took them from its nearest
  set. The 49 Windows sizes had their own. The baker filled the 16 scales in (15360x8640's
  12.0 is still too large to bake, as before), and `Test-FontAtlasScale.py` passes on the 66
  sets of `97BEA480…`. The Mac's own cache is unseen from here
  (`docs/macos-changes-from-windows.md`, item 12).

- **Controller badges and the HUD's button-row boxes at sizes with no set, on both
  platforms** (2026-09-30, found while bringing the Mac's blend to Windows; the maintainer:
  "the issue is significant this needs a fix on both mac and windows"). A badge is a 512x64
  texture the engine stretches over its whole button, drawn to come out round on that
  button. At a size with no set both installers took the nearest set's, drawn for that set's
  buttons, and the blended buttons have other shapes: measured on the blended files, the
  worst badge came out 1.857 times as wide as tall at 3440x1400 (nearest set 1856x1392, the
  resolution screen's OK drawn for 336x64 and shown on 624x64), 1.835 at 3200x1350 and 1.375
  at 2560x1200. `lbl_mileftbot.tga`, the boxes under the HUD's eight top-right buttons, is
  drawn per set from that set's `mipc28x6.gui` and so followed the nearest set's buttons too.
  `gui-blend.bin` is version 3: it carries `build_prompt_tga`'s constants, the 16 glyph
  artworks the badges use, and for each of the manifest's 552 badges where its button sits,
  its glyph, its backing and the controls that size it, and where LBL_MENUBG and the HUD
  buttons sit. The Mac helper and the Windows installer draw every badge again for its
  blended button, with Pillow 12's arithmetic (the Lanczos resample on premultiplied alpha
  in 22-bit fixed point, the masked paste, `alpha_composite`), write the prompt manifest with
  the blended sizes, and draw the HUD boxes from the blended HUD. A plain-Python model of that
  arithmetic reproduced Pillow's `resize` in 60 of 60 random cases and `build_prompt_tga` in
  40 of 40. `Test-GuiBlendHelper.py`: the helper equals the build's own `build_prompt_tga` and
  `build_menubg_texture` at 24 sizes; every one of the 45 anchors rebuilt from the table is
  the build's set byte for byte, badges, manifest and HUD boxes included; every badge at the
  24 sizes is round on its blended button within 5% (worst 1.049, texel rounding); the
  Windows installer equals the helper. The table grew from 3.2 to 3.7 MB (0.8 MB gzipped).
  `kmrp-mac.sh` installs every file the helper writes. **Built and tested on Windows only**;
  what the Mac still has to build and check is `docs/macos-changes-from-windows.md`, a new
  tracker of changes made on Windows first. Seen in play on Windows at 1600x1024: every badge
  on the main menu, character generation and Load Game round and beside its words, and the
  HUD's eight boxes under its eight buttons. Not played on the Mac.

- **The skill icons sit inside their frames** (2026-09-29, Windows and macOS, at
  the maintainer's request: "The skills are a bit too big make it fit in the
  frame correctly"). The enlargement below kept stock's proportion, and stock's
  eight `isk_*` pictures fill their whole 32x32 canvas, so each sat on the
  border of its frame -- `lbl_hex_3`, fitted to the Skills row's icon box
  (`42s`) -- rather than inside it; stock does the same. Measured in game at
  3440x1440 (box 84): the frame's outline spans x 8..70 and y 11..80 of the
  box, its opening about 57x65, and the 64 px canvas, centred in the box, lay
  over the border on the right and at the bottom. The canvas keeps its size and
  place; the picture inside it is now `round(0.62 × 42s)`, on transparent
  pixels, centred and then moved `(round(−0.5s), round(−2s))` px, since the
  canvas sits about 1.5 px right of and 2 px below the frame's opening at 1440p
  (`SkillPictureOfBox`, `SkillShiftX`, `SkillShiftY` in
  `AbilityIconGenerator.cs`, the same in `macos/tools/kmrp-abilityicons.c`). The
  icons are written at every height, 720 and below too:

  | height | canvas | picture | at (left, top) |
  | --- | --- | --- | --- |
  | 720 and below | 32 | 26 | 3, 1 |
  | 982 | 44 | 36 | 3, 1 |
  | 1080 | 48 | 39 | 3, 1 |
  | 1440 | 64 | 52 | 5, 2 |
  | 1964 and up | 64 | 64 | 0, 0 |

  How large: the frame's border pixels were read from an in-game shot at
  3440x1440 (those border-coloured in at least four of five rows), and all eight
  pictures resampled at each size and placed as above. 52 px is the largest that
  keeps every opaque pixel of every picture 2 px clear of the border; centred
  without the move, 46 px was, and at 55 px Awareness touches it. A first pass
  the same day shipped 46 px centred; the maintainer asked for them larger
  ("Increase them a bit but dont let them touch the frame").

  Checked in game at 3440x1440 through the new installer: every picture inside
  its frame's opening, clear of the border on each side. The Windows generator
  and a Windows build of the Mac helper (MSVC, `/fp:strict`) wrote
  byte-identical files at the ten heights `Test-AbilityIcons.py` uses, which now
  checks the picture's size and place and that nothing is drawn outside it;
  `Test-AbilityIcons.py` itself, which needs clang and the .NET 8 SDK, was not
  run. Only 1440p was seen in game.

  *Updated the same evening:* `Test-AbilityIcons.py` passed on Windows, with LLVM's
  clang 18.1.8 and the .NET 8 SDK, once the tests build the Mac helper there as one
  x64 program (`testing/regression/native_helpers.py`, shared with
  `Test-GameArt.py`; on macOS both slices, as before). The helper and the C# were
  byte-identical at the ten heights, 2,704 icons, and every skill icon had the size
  and place the rule gives, with nothing drawn outside its picture.

  *Changed the same day, in the merge of the macos branch:* the skill rows are `50s` now
  (below, *Skill rows are as tall as the Feats and Powers rows*), and the frame is stretched
  over the row's icon box (`lbl_hex_3` is 64x64 with its outline at x 7..55, y 6..59, which
  stretched to 84 gives the outline measured above). So the canvas is `round(32s x 50 / 42)`,
  the picture `round(0.62 × 50s)`, and its move `(round(−0.5s × 50 / 42), round(−2s × 50 /
  42))`, both growing with the box:

  | height | canvas | picture | at (left, top) |
  | --- | --- | --- | --- |
  | 720 and below | 38 | 31 | 2, 1 |
  | 982 | 52 | 42 | 4, 2 |
  | 1080 | 57 | 46 | 4, 1 |
  | 1440 | 64 | 62 | 0, 0 |
  | 1964 and up | 64 | 64 | 0, 0 |

  At 1440p the 64 px cap leaves the picture one pixel to move, where the rule asks five up
  and one left: it sits about 4 px lower in its frame than the measurement above centred
  it. Not yet seen in play at the new sizes.

- **macOS: the left stick steers where it points** (2026-10-01, reported from play: diagonals
  went the wrong way; Windows was right). The Mac engine does not pass the analog axes through:
  each comes back as sign(v) x (0.5 + 0.5 |v|), measured at Control's Normalize call (a stick
  1,668/32,767 right of centre gave -0.525, 386 left gave +0.506), so any drift from straight up
  steered half sideways and diagonals bent by up to 27 degrees. While the stick drives, KMRP's
  hook there now writes the stick's own direction and deflection into the movement vector
  (`gameplay.cpp`, `KmrpSkipNormalize`); the keyboard path is unchanged. Seen in play at
  3024x1964 with a DualSense.
- **macOS: one patch, built on FTD's current patches, replacing an install of his** (2026-09-30).
  FTD's `widescreen-patch` moved on after the version KMRP shipped (`71ac5fa`, 27 commits to
  `074972b`): he applied the chargen fix (bit `0x08` kept), split the fixes that hold at any
  resolution (K1, K2, K3, K5, K6) into a separate *Stray Bug Fixes* patch that the widescreen
  patch now requires, and dropped the K7 hook that stretches the dialogue reply list. As pushed,
  the two did not install together: the widescreen patch still declared the 11 moved hooks, and
  KPM's own check reported "Multiple hooks at address" for all of them. Now:
  - the submodule is `RayesDiyab/Kotor-Patch-Manager`, branch `kmrp`: FTD's `074972b` with those
    hooks declared once (it followed FTD's branch directly until now), so KMRP takes his changes
    when they are merged there;
  - KMRP is one KPM patch, `kmrp` (`patches/kmrp.dylib`), where it was five: FTD's two patches
    compiled from their source with KMRP's layout, map-note and controller code linked in
    (`macos/tools/make_kmrp_patch.py`), in four builds for the two options. Every byte hook comes
    before every detour, as FTD's hook file requires; FTD's constructor runs before KMRP's layout
    code (checked in the built module); a hook two parts declare identically is kept once. KPM
    validates and stages each build with no overlapping hooks (78 hooks with both options);
  - K7's reply-list stretch is KMRP's layout code (`dialogue_replies.cpp`), so KMRP no longer
    depends on the base patch keeping it;
  - an install of FTD's patches through KotOR Patch Manager is replaced, with FTD's agreement:
    the installer puts back the untouched game from KPM's copy, deletes his patch files and KPM's
    leftovers, and installs KMRP; Restore Original then leaves the untouched game. Any other KPM
    patch stops the install, by name, and changes nothing (*since 2026-10-01 it installs for
    KPM instead, as Windows does: above*).
  `Test-KmrpLayoutPatch.py` (53 sites; it fails against the old base, whose K7 hook overlaps the
  new site) and `Test-MacInstaller.py` (a fifth round: a stand-in KPM install replaced, and one
  with another patch refused) pass. Installed at 3024x1964; **not yet played**.
- **Lists are as tall as whole rows, spaced as the inventory's** (2026-09-30, found by an
  audit of every list at every resolution after the journal's report). A list box shares the
  height left under its last whole row between its rows, and rows sized in code (items 56s,
  skills and feats 50s) sit in lists the upstream layouts scale with the screen, so the gaps
  depended on what was left over. Measured over the 66 sets, where the inventory keeps 8 to
  12.5% of a row:
  - the Container (footlockers, bodies): 4 rows of 153 px, 34 px apart at 3024x1964 (22%), and
    over 13% in 64 sets;
  - the granted popup ("You have been granted the following feat(s) this level."): 22% in 64
    sets, which only the Mac's layout patch corrected, at run time;
  - character creation's Feats: 7 rows of 136 px, 19 px apart at 3024x1964, up to 18% in 46
    sets;
  - below 1024x768 and at 1920x540: the store, level-up powers, equipment, upgrade items and
    the Abilities screen, up to 32%.
  The resource build now makes each of these lists as tall as whole rows, each `row // 11`
  from the next (`tools/scale_listbox_padding.py`, `ROW_LISTS` and `fit_list_to_rows`). In the
  two popups the buttons below the list move with it and the panel keeps its centre: at
  3024x1964 the Container is 4 rows 13 px apart and 85 px shorter (1,253 px), the granted
  popup 4 rows 12 px apart. A full-screen list is only shortened, and only where its gaps
  pass an eighth of a row: the Feats list by 51 px there, 12 px apart. All 66 sets now keep
  7.5 to 12.5%. The Container with one row more (5 at 3024x1964, 166 px taller) was tried in
  play against the 4 that fit and declined. The Mac's installer redoes the fit for a size with
  no set: the blend table (version 3 on the macos branch, 4 since the merge with master's
  badges the same day) holds each list as it was before and each set's
  manifest says by how much it changed; blended as fitted, the 17 Mac sets missed by up to
  41 px, fitted at install they are back to 99.90% of fields within 1 px, worst 12 px
  (`Test-GuiBlendHelper.py`). Shared build code: Windows gets it with its next build
  (`docs/windows-changes-from-macos.md`, item 14). *Built for Windows the same evening*
  (`97BEA480…`), whose installer fits the lists for a size with no set as the Mac's helper does
  (`GuiBlend.cs`, equal to the helper at 369 sizes). The Container seen in play on the Mac at
  3024x1964; the others checked by `Test-GeneratedGuiGeometry.py`, not yet seen.
- **Skill rows are as tall as the Feats and Powers rows** (2026-09-30). The Abilities
  screen shows its three tabs in one list, with skill rows at `42s` and the Feats and Powers
  tabs' chain rows at `50s`, so one tab's gaps stayed loose in 11 of the 66 sets: the Skills
  tab 8 to 11 px (18 to 21% of a row) from 800x600 to 1470x956, the Feats and Powers tabs
  10 px at 1920x540 and 1024x576, and fitting either would have taken a row off the other.
  Skill rows are now scaled from 50 on both platforms (`RowSizeGroups` in
  `src/patcher/KmrpPatcher.cs`, `resolution_sizes.cpp` on the Mac): 136 px at 3024x1964, where
  they were 115, so the Skills tab shows five of the eight skills at a time there rather than
  six; the granted popup's rows grow with them. The skill icons keep their proportion to the
  row, `round(32s x 50 / 42)` capped at 64, in `AbilityIconGenerator.cs` and the Mac's helper
  alike: 38 px from 720 down, 52 at 982, 57 at 1080, 64 from about 1210 up (the picture
  inside them grows with the row too: above, *The skill icons sit inside their frames*). Checked by
  `Test-KmrpLayoutPatch.py`, `Test-AbilityIcons.py` (the two generators byte for byte) and
  `Test-MacInstaller.py`; **not yet seen in play**. Windows: `docs/windows-changes-from-macos.md`,
  item 15; *built for Windows the same evening* (`97BEA480…`), `Test-AbilityIcons.py` passing there.
- **macOS: the Options check boxes scale with the resolution** (2026-09-30, found by
  reading the code while auditing what does not scale). The Options screens' toggles
  (Feedback's list, Auto-pause, Gameplay, Graphics, Advanced Graphics, Mouse, Advanced
  Sound) draw their circle in a fixed 25x25 square and start the label 30 px in, at every
  resolution (`CSWGuiOptionsCheckbox::SetExtent`, Mac `0x1002CECEE`, Windows `0x006DE000`),
  so at 3024x1964 the circle was 25 px in toggles 117 to 164 px tall, where vanilla drew
  it in 43- and 60-px ones. The Mac's layout patch replaces the function with the same
  layout at 25s, 30s and 2s (`resolution_sizes.cpp`): a 68-px circle and the label 82 px
  in at 3024x1964, 38 and 45 at 1920x1080, vanilla's at 720 and below. Checked against
  the game binary by `Test-KmrpLayoutPatch.py` (52 sites); **not yet seen in play**.
  **Windows does not have this yet** (`docs/windows-changes-from-macos.md`, item 13).
  *Windows since the same evening, and the Feedback list's rows fixed for both: above.*
- **The journal shows six quest rows, spaced as the inventory's** (2026-09-30, reported
  from play at 3024x1964: the rows sat far apart). A list box shares the height its rows
  leave over between them, and every set's `journal.gui` kept upstream's 78-unit row
  template, twice vanilla's 39, so four rows fit and each gap was 22% of a row: 47 px under
  213-px rows at 3024x1964, 25 under 117 at 1920x1080, where the inventory's are 8 to 10%
  and vanilla's journal showed six rows. The resource build now sizes the template per
  resolution from its own list (`tools/scale_listbox_padding.py`, `fit_rows_to_list`) so
  six rows fill it, each an eleventh of a row from the next: at 3024x1964, 158-px rows
  15 px apart (the inventory's: 153 and 15); across the 66 sets, gaps of 8 to 11% of a
  row. Only the template's height changes. Shared build code: Windows gets it with its
  next build (`docs/windows-changes-from-macos.md`, item 12); seen in play on the Mac at
  3024x1964 only. `Test-GeneratedGuiGeometry.py` checks every set. *Built for Windows the
  same evening* (`97BEA480…`).
- **macOS: the granted popup's rows look like the inventory's** (2026-09-30, reported
  from play: "You have been granted the following feat(s) this level."). The text touched
  its frame's left line, the hex beside it was shorter than the text frame, and the rows
  sat far apart. For this popup's rows only, the Mac's layout patch
  (`granted_popup.cpp`) now insets the text by an eighth of the row, grows the hex, its
  highlight and the icon by a seventh so the hex spans the text frame, and cuts the list
  to the rows it shows at a pitch of the row plus an eleventh, about the share the
  inventory's list spreads between its rows (8 to 10%); OK and the panel move up with it,
  and the popup stays centred. At 3024x1964, with four feats: rows 141 px apart became
  125 (14 px between frames), the hex went from 97 to 111 px beside a 111-px frame, the
  first letter from 2 to 14 px inside the frame, and the popup from 941 to 876 px tall
  (screenshots). Every size follows the row's height, so it holds at any resolution;
  seen at 3024x1964 only, and a list long enough to scroll has not been seen. **Windows
  does not have this yet** (`docs/windows-changes-from-macos.md`, item 10). *Windows since the
  same evening: above.*
- **macOS: message popups fit their contents** (2026-09-30, reported from play:
  the tutorial boxes and the Exit Game box were far taller than their text).
  The shared popup keeps the height `confirm.gui` gives it, sized for the
  tallest case, and its message area keeps a height sized for a four-line
  tutorial, with OK hung under it. At the end of the popup's own layout
  (`FixMessageLabel`, `0x100306552`) the Mac's layout patch now narrows the
  message to the least width at which its text keeps its line count (never
  narrower than the buttons), shrinks it to its text, moves OK and Cancel up
  under it with the engine's own spacing, fits the panel around it with the
  message's own margins, and keeps the popup centred. At 3024x1964 the Exit
  Game box went from 1,224x711 px to about 880x365, and the Attributes, Skills
  and Feats tutorials were seen fitted and centred in play the same day, with
  their line counts unchanged (screenshots). Only while the text fits without a scrollbar; otherwise the
  popup is left as the engine made it. **Windows does not have this yet**: its
  popups keep the file's height until the same step is added after
  `0x006253A0` (`reverse-engineering/message-popup.md`). *Windows since the same
  evening: above.*
- **Controller badges sit at their designed distance from the words, and no
  longer on them** (2026-09-30, reported from play on the Mac: the Square of
  the Container's "Switch To Give Item" sat on the "S" at 3024x1964). The
  prompt generator measured each caption with the font's `spacingR` scaled by
  `texturewidth` -- 2.56 px a letter at `texturewidth` 5.12, 5.12 px at 10.24 --
  where the engine adds `spacingR * 100`, half a pixel. Every caption measured
  long, more so at higher resolutions, and every badge sat about twice its
  designed gap from its text: the A of Gameplay's Controller Layout entry 50 px
  away at 3024x1964, 13 px now (screenshots before and after). Seven Options
  captions read off a 3024x1964 screenshot inked 0.825 to 0.843 of the old
  measure and 0.96 to 0.97 of the corrected one, the rest being side bearings.
  Where a long caption nearly filled its button, the generator's rule that a
  badge never leaves its button put it on the text. Windows places badges from
  the same textures and the same manifest, so this applies to both platforms.
  The Controller Layout screen had absorbed the error as a 0.88 draw ratio
  (`RENDER_FACTOR` 0.92); it is now a 4% margin over the corrected measure
  (1.04): the caption boxes played at 3440x1440 grow by 7 to 9 px, and those at
  3024x1964, which the error made wider, lose 18 to 32. Every caption still fits
  its box (`Test-ControllerPromptAssets.py`).
- **The Container's buttons are wide enough for "Switch To Give Item" and its
  badge** (2026-09-30, the same report). With the measure corrected, the
  caption is 425 px of text on a 528 px button at 3024x1964, where the badge
  needs 70 px beside it on either side; 45 of the 66 sets were short, by 2 to
  182 px. The build now widens `container.gui` -- the panel about its centre,
  its title, item list and all three buttons -- by exactly what that button
  needs, in each set that needs it (`fit_container_to_caption` in
  `tools/prepare_universal_resources.py`): 38 px at 3024x1964, 44 at 1512x982,
  none at 3440x1440. `Test-ControllerPromptAssets.py` checks every set.
  Measured with the English wording, like the badge; a longer localised one is
  re-placed at install as before and still meets the button's edge. **Not yet
  seen in play**; the rest of the screen is unchanged.
- **A with a button focused presses that button once, on every screen**
  (2026-09-28, at the maintainer's request after the Level Up freeze below:
  "create this for all screens"). Many buttons do nothing of their own: their
  click presses A, B, X or Y on their own panel, through four two-instruction
  thunks (`0x00624BA0`, `0x00624BB0`, `0x00624BC0`, `0x00644720`). A panel acts
  on a button press and then hands it to the focused control (`0x00409E60`).
  A click never sets the focus, so it never mattered; the D-pad does. With
  such a button focused, one A either echoed -- the button pressed A back on
  the panel, without end: the status summary's stack overflow and the
  double level-up -- or ran a second action, A accepting and the focused
  Cancel's B cancelling too. A scan of all 515 `AddEvent` calls in the
  executable found 62 such registrations on 39 panels (the table is in
  [retained-xbox-gui-events.md](reverse-engineering/retained-xbox-gui-events.md)).
  Two halves now cover all of them:
  - A with such a button focused presses that button and nothing else,
    exactly as a click does (`PressFocusedRaiseButtonK1`). Character
    creation, Feats and the resolution box keep their own tested A paths.
  - A panel never hands an event to a focused control whose own handler would
    press that same event back: the hand-off becomes the inert `0x41`
    (`GuardPanelEchoK1`, a new hook at `0x00409E60`, the 33rd native hook).
    It catches what the first half does not, such as a focused OK on a screen
    that answers A itself.

  `K1_NO_PAD_FOCUS_PANELS` stays, since those screens need no focus.
  **Seen in game on 2026-09-28** in the scratch copy at 3440x1440 with
  `9736B41F…`, on the virtual pad: A on a focused Close on Gameplay and on
  the in-game Options each pressed it once. With OK focused on level-up
  Skills and points unspent, A showed one "unspent skill points" box, the
  guard made the echo inert, and the level was then accepted. The Load Game
  list loaded the save. Inventory used a focused shield once, 3/5 charges to 2/5;
  Messages' X, the Journal's A and Y, the Map's A and B, Party Selection's B,
  Abilities' X, Start, R3, and a conversation (A to talk, A to skip a line,
  the D-pad down the replies, A to pick one) each did one thing. The guard
  log shows the two presses and the one inert hand-off, nothing else.
  **The same walk at 1920x1080**, the same day and build: the same three
  log lines and no other; Gameplay's Close and the in-game Options' Close
  each pressed once; A on the Character screen opened one level-up, whose
  Skills OK showed one box, and Powers' notice closed on A; the level was
  accepted (Jedi Guardian 10 to 11). Inventory used the shield once (4/5 to
  3/5), and R3, Abilities' X, Messages' X, the Journal's A and Y (Order
  Received to By Name), the Map's A and Party Selection's B, Equipment's A
  and B, and a conversation (one A per line or reply) each did one thing.
  Not played by hand.

- **Level Up no longer opens twice and freezes the game** (found 2026-09-26
  in a preview, with a copy of the maintainer's save). With the D-pad focus on
  the Character screen's Level Up, one A opened two level-up screens, stacked,
  and the game froze; the maintainer closed it. The screen levels up on A
  itself (`0x006B2295`) and then passes A to the focused control
  (`0x00409E60`), and Level Up's click raises A on the screen again
  (`0x00624BA0` through the vtable's `+0x50`, `0x0040B640`). Auto Level Up's
  click raises Y the same way (`0x00644720`, `+0x5C`), so a focused Auto Level
  Up would have run both actions. The pad no longer moves the focus on the
  Character screen: every action there has a button of its own -- A Level Up,
  Y Auto Level Up, X Scripts, B Close, R3 the next party member. The status
  summary's rule from yesterday and the granted-feats notice are in the same
  list now, `K1_NO_PAD_FOCUS_PANELS`. The other panels with such buttons are
  covered by the echo guard since 2026-09-28 (the entry above).
  **Seen in game on 2026-09-26** in the scratch copy with `128CDC79…`: after
  two D-pad presses on the Character screen, A opened exactly one level-up
  screen, and four level-ups then ran on the pad without a freeze (2026-09-28).

- **The status summary no longer crashes the game after a D-pad press**
  (found 2026-09-25 while previewing its A). With the box up, a D-pad press
  moved the pad's focus onto its OK, and the next A closed the game with a
  stack overflow, exit code `0xC00000FD`, with or without the new A. The
  box's handler (`0x00625AC0`) closes it on A and then passes every event to
  the focused control (`0x00409E60`), and OK's A handler (`0x00624BA0`) is
  the box's own "press A" (`0x0040B640`). So with OK focused the two call
  each other until the stack runs out. A stack capture of the crash shows
  that cycle 116 times in the 12 KB read, with the box's click sound at the
  top, where the stack ran out. The game never focuses OK, and A closes the
  box without it, so the D-pad now does nothing there. In the scratch copy
  the same sequence -- the mouse moved, D-pad presses, A -- closes the box
  and the game runs on (`B5D3CBB7…` and `80616FE6…`, 3440x1440).

- **The status summary's text no longer crowds its right edge** (1920x1080,
  2026-09-25). The module measured each line from its glyphs alone, but the
  engine also adds the font's `spacingR` to every glyph's width
  (`0x0045ABDF`), half a pixel in KMRP's `dialogfont16x16`. "Journal Entry
  Added" measured 262 px at 1920x1080 and drew 273, 6 px from the border; at
  3440x1440, 357 and 364, 17 px from it. The measure now includes the
  spacing: 271 px and 15 px clear at 1920x1080, 366 px and 26 px clear at
  3440x1440, seen in the scratch copy. The first build of it, `49671B67…`,
  read the neighbouring field, spacingB, which is 0, and changed nothing.
  The dialogue A's measure keeps the short width, because its gap was tuned
  by eye on top of it.

- **D-pad left and right change a setting** (play-test, 2026-09-25: "pressing
  D-pad right doesn't change the settings"). On Advanced Graphics the pad moved
  the focus from a value onto its + and stopped there, because the native path
  only moved focus spatially and nothing lies right of the +. Left and Right on a
  row with a - and a + now press them the way a click does (the arrow's own
  registered `0x27`), and the focus stays on the value. An arrow hidden at the
  end of its range does nothing. Up and Down leave from the row, never onto an
  arrow. The rows are Difficulty on Gameplay; Texture Quality, Anti-aliasing and
  Anisotropy on Advanced Graphics; and EAX on Advanced Sound (`K1_CYCLE_ROWS`).
  The keyboard's arrow keys already did this. Sliders were not affected: the
  engine's slider takes Left and Right itself. With Attributes, Skills and
  Portrait, every screen whose values move by - and + now moves them on Left and
  Right. **Seen in game on 2026-09-25** in the scratch copy: Right took
  Difficulty from Normal to Difficult, Left took Texture Quality from High to
  Medium and Anisotropy from 16x to 8x, Right changed the portrait and raised
  Strength, Dexterity and Computer Use, and the focus stayed on its row each
  time.

- **Pazaak's wager moves with the D-pad.** Its dispatcher (`0x0067E150`) lowers
  the wager on Left and Down and raises it on Right and Up whatever holds focus
  (`0x0067E221`, `0x0067E23D`), accepts on A and quits on B. The retained-event
  inventory never listed the panel, so KMRP owned its directions and moved the
  focus between its buttons instead. It is now one of the screens the engine
  navigates itself, and KMRP moves no focus there. **Untested in game.**

- **The status summary fits its text** (screenshots, 2026-09-25). This is the
  box that lists "Journal Entry Added", "Credits Lost: 100", "Experience Points
  (XP) Received: 50" and "Item(s) Received" beside their icons, with OK under
  them. At 3440x1440 its text ran past the right edge, OK was drawn over the
  last line as a bar, and the XP line showed only "Received: 50". The panel
  lays itself out in code (`0x00625C60`), in 640x480 pixels. It uses the game's
  own 640x480 `statussummary.gui`, which High Resolution Menus does not ship.
  Its rows are 37 px apart, and each line is widened 20 px at a time until the
  line breaker fits it on one line, never past 440. The box is that width plus
  62, with OK 7 px above the next row. KMRP draws its text at 32 px a line
  there, against the 16 it was laid out for. So the XP line hit the 440 cap and
  wrapped: the box measured 507 px on the screenshot, and the formula gives 502.
  The breaker's short measure let the other lines overflow, and the rows and OK
  collided. The controller module now lays the box out again after the engine,
  every frame: the same layout scaled by the lines' font height over 16, each
  line as wide as the glyphs the engine draws for it, capped only by the screen.
  It runs from KMRP's runtime, with or without controller support since
  2026-09-28; until then it came only with the controller component.
  **Seen in game on 2026-09-25** in the scratch copy, with one
  row, "Journal Entry Added", after Trask's first conversation. The log read
  `box=(1475,648,489,144) ok=(144,80,200,44)`, and the screenshot shows the
  line inside the box and OK centred under it. Two or more rows have not been
  seen.

- **Attributes and Skills are navigable with the D-pad** (play-test,
  2026-09-25). Left and Right always lowered or raised the selected attribute,
  even with focus on the bottom buttons, and moved along those buttons at the
  same time. So Left from OK lowered Charisma and showed "cannot be reduced
  below 8", and Right to Cancel raised it. Both screens are the Xbox design:
  Up/Down had no handler, Left/Right changed the value, and the focus was
  never meant to reach the buttons. KMRP now owns the D-pad there, in character
  creation and level-up:
  - **Up/Down** walks the rows, and Down from the last row reaches OK;
  - **Left/Right on a row** lowers or raises that row, through the panel's own
    routines and sound, and focus stays;
  - **on the bottom strip**, Left/Right moves between Recommended, OK and Cancel
    without touching a value, and Up returns to the row last in focus.

  A row is its value button. Focusing it runs the engine's own "enter" event,
  which is what selects the row, so the description follows too.
  **Seen in game on 2026-09-25** in the scratch copy: Down went from Strength
  to Dexterity and from Computer Use to Demolitions, and Right raised each
  with the focus kept on its row. The bottom strip was not tried.

- **Regression runs no longer leave Windows high-DPI values behind.** A fixture's
  `HIGHDPIAWARE` value was removed only by its own `--restore`, so a run that
  stopped part-way deleted the folder and kept the value. Twelve such values
  were found on the maintainer's machine and deleted at their instruction. The four in-place scripts now remove
  their own values in `finally`. It was a test fault, not an installer one: a
  foreign `patch_config.toml` only skips KMRP's runtime (then the controller
  component), and the
  completed install's value is removed by Restore Original. Details are in
  [windows-dpi-scaling.md](docs/windows-dpi-scaling.md).

- **The Name screen stays open after A** (play-test, 2026-09-25). A on the
  Name step opened it, and letting go of A closed it again with the name
  accepted: the screen stayed up only while A was held. The release reached the
  focused name box, whose A is wired to "done" (`HandleDoneButton`,
  `0x006F9CD0`). The engine's base control handler runs a wired event on a
  release as well as a press. The Name screen's dispatcher (`0x006FA220`) now
  has the same guard as the five in the entry below. A release there is inert,
  and a press reaches the focused control as before. **Untested in game.**

- **Character creation no longer crashes on A** (stack overflow). On the
  Attributes screen, D-pad Left on an attribute at 8 shows "Attribute scores
  cannot be reduced below 8.", and confirming it crashed the game: three times
  on 2026-09-25, each `0xC00000FD` at `swkotor.exe+0x3000BE`. The Attributes,
  Skills, Feats, Powers and Portrait screens are retained Xbox panels that answer
  A themselves *and* pass it on to the focused control
  (`CSWGuiPanel::HandleInputEvent`, `0x00409E60`, forwards to `[panel+0x1C]`).
  Their buttons are wired to raise the panel's events: the Attributes OK's click
  runs `AcceptButtonCallback` (`0x00624BA0`), which calls the panel's
  `HandleInputEvent(0x27, 1)` through vtable `+0x50` (`0x0040B640`). So with OK
  focused, one A was the panel's A, OK's click, the panel's A again, and so on
  until the stack ran out. Each pass re-showed the "spend your points" box. A
  mouse never loops, because clicking does not set the panel's focused control;
  the pad's D-pad focus does. A hook at each of the five dispatchers now does
  three things:
  - A presses the focused button once, as A does on every other KMRP screen;
  - the one re-entry that press raises is let through, and a deeper one becomes
    an inert event (`0x41`);
  - a release can no longer click anything.

  This also fixes A on a focused Cancel, which ran the screen's accept and then
  Cancel. With no button in focus, A is still the screen's own A. The D-pad
  Left that showed the box is the Xbox screen's decrease, working as designed.
  Diagnosed from the crash record and the bytes, not reproduced here.
  **Untested in game.**

- **The combat-mode message reads in full at 3440x1440.** "COMBAT MODE
  engaged. Press the Disengage button to cancel." showed only "the Disengage /
  button to" (play-test screenshot, 2026-09-25). KMRP's hand-tuned 3440x1440 HUD
  moved the message to the top-left corner, but left its text label 300 px
  wide. Its background twin kept 564 px, and upstream's box is 1895. At that
  resolution's font the sentence is about 1,049 px, so it wrapped to five lines
  and the 50 px box showed the middle two. The build now gives both labels
  **1120 px**, where both wordings -- mouse and keyboard -- read on one line,
  with about 30 px to spare either side of the longer. The label draws in
  32 px lines at 1440, `dialogfont16x16`'s, whatever its `.gui` says, so its
  50 px box holds one line. `Test-GeneratedGuiGeometry.py` now wraps both
  wordings against the box at all 49 resolutions, using a width factor
  calibrated on the first screenshot. Before the fix it failed at 3440x1440
  alone, with exactly the five lines seen. **Untested in game.**

  *Corrected 2026-09-25:* the first fix made the labels 660 px, to fit two
  lines, and a play-test screenshot showed only the second, "Disengage button
  to cancel.". Two 32 px lines do not fit a 50 px box, and the engine skips a
  line that starts above the box. The check had passed that build because it
  took a line to be 25 px. At 32 px it fails the 660 px build, at 3440x1440
  only, for both wordings. The width factor was confirmed on the same
  screenshot: it gives 480 px for the visible line, and the screen showed 478.

- **Down from Close no longer loses the focus on in-game Options.** Reported
  2026-09-25 with a screenshot: pressing Down at Close, the bottom entry, left
  nothing highlighted, and Up could not bring the focus back. With nothing
  below Close, the D-pad navigation wrapped to the farthest control above it in
  the same column, which was the description pane. That is a list box, which
  the navigation admits on tab screens so the Messages and Journal lists can be
  reached. The pane draws no focus highlight and keeps every D-pad press to
  scroll its text, so focus could not leave it. The navigation now never chooses
  a screen's description pane. The right stick scrolls it, and the vendor code's
  per-screen table (`FindK1DescriptionListbox`, now exported as
  `KmrpDescriptionPaneK1`) says which control it is. Down from Close wraps to a
  real button instead. Diagnosed from the code and the report, not
  reproduced; **play-tested on 2026-09-25 at 3440x1440: fixed.**

- **Controller buttons leave every screen when the mouse or keyboard takes
  over**, not only the screen in front. Reported 2026-09-25: switching to mouse
  and keyboard cleared the badges on the current screen, but the next screen
  opened with the mouse still showed them. Badges are texture swaps on a
  screen's own buttons, and the in-game menu builds its tab screens once and
  keeps them, so a tab painted while the pad was in use kept its art. The clear
  ran only on the panel in front when the device changed, assuming that any
  other panel reaching the front in keyboard/mouse mode was new and blank.
  `UpdateK1ControllerPrompts` now records every panel it paints (with its
  vtable, so a freed-and-reused address is not written to) and clears each one
  the first time it comes to the front in keyboard/mouse mode. The R3, LT/RT and
  swap-tab cues never had the problem: every live cue is shown or hidden each
  frame. **Play-tested on 2026-09-25 at 3440x1440: fixed.**

- **Cancel now cancels on the Solo Mode prompt** (issue #21). Pressing A with
  Cancel highlighted turned Solo Mode on anyway. The panel is a retained Xbox
  one: its handler at `0x006C244C` calls `CClientExoApp::TogglePartyFollow`
  before looking at anything, and never reads which button has focus — on the
  Xbox there was none, A meant yes and B meant no. KMRP now consumes A there
  when Cancel holds focus and exits into the panel's own close path, so A on
  Cancel does exactly what B does. That first fix left **both buttons
  refusing**: it was a KPM consumed-exit hook, and KPM runs a hook's stolen
  bytes before it tests the handler's answer. The stolen instruction loaded
  EAX, so the test never saw the answer and every A took the close path, OK
  included. Both hooks now sit at the panel's input-handler entry and, with
  Cancel focused, rewrite A into B on the stack, so the game's own dispatcher
  cancels; A on OK runs the vanilla confirm once. `check_hook_stolen_bytes.py`
  now refuses a consumed-exit hook whose stolen bytes touch EAX or the stack.
  **Play-tested on 2026-09-24:** A on OK turns Solo Mode on and A on Cancel
  leaves it off; `kmrp-confirm-focus.log` records each decision. Checked
  again on 2026-09-25.
  **The resolution screen had the identical
  defect** and was fixed with it: A applied the highlighted resolution from
  Cancel, through `CSWGuiOptionsResolution::OnResolutionChosen`. That half was
  play-tested on 2026-09-25 at 3440x1440 and works. Ordinary
  confirmation boxes were never affected — they implement no `0x27` at all, so
  A genuinely reaches the focused control.

- **Sound Options: Down from Movie Volume reaches Advanced Options.** It jumped
  to Default, while Up from Default reached Advanced correctly. A focused slider
  handled every direction itself, and for Up and Down it follows the game's own
  links, which skip Advanced. A horizontal slider now keeps only Left and Right;
  Up and Down go through the same navigation as every button, on every options
  screen with a slider. Play-tested on 2026-09-24.

- **The Movies screen shows B / Circle on Close.** The screen already closed on
  B; nothing said so. Play-tested on 2026-09-24.

- **Xbox LT and RT use the Xbox 360 trigger art**, like the rest of the Xbox
  set, on the menu tab strip and the Controller Layout screen. Play-tested on
  2026-09-24.

- **The R3 party-switch cue is 10% smaller, and sits beside the portraits
  where it did not fit between them.** On all four party screens. Its side
  was the whole space between the two portraits -- the gap or their height,
  whichever was smaller -- and is now 90% of the portrait height
  (`R3_CUE_SCALE`).

  It stays centred in the gap wherever the gap holds it with a tenth of it
  free either side: every 32:9 and 21:9 resolution but 1280x1080, 3440x1440
  included, where nothing moved. At 4:3, 16:10 and 16:9 the gap is narrower
  than a portrait, and a cue sized to fit it was a few pixels wide -- 6 px at
  800x600, and 5 px once made 10% smaller, which is what prompted the move.
  There it now sits right of the second portrait, a third of a cue away, like
  the tab-strip cues. Right rather than left: the portraits sit at the curved
  left end of a bar the background art draws, and on the left the cue was
  rendered crowding that curve on all four screens, while the bar runs on
  empty to the right. Measured in the built archives, identical on all four
  screens:

  | Resolution | Portrait | Gap | Before | Now | Where |
  | --- | ---: | ---: | ---: | ---: | --- |
  | 800x600 | 35 | 6 | 6 | 32 | right of the portraits |
  | 1920x1440 | 84 | 15 | 15 | 76 | right of the portraits |
  | 1920x1080 | 63 | 36 | 36 | 57 | right of the portraits |
  | 2560x1440 | 84 | 48 | 48 | 76 | right of the portraits |
  | 3840x2160 | 126 | 72 | 72 | 113 | right of the portraits |
  | 3440x1440 | 84 | 94 | 84 | 76 | between them |
  | 5120x2160 | 126 | 138 | 126 | 113 | between them |

  The build refuses a cue that would cover a button or a list, and
  `Test-GeneratedGuiGeometry.py` now checks the cue's size, placement, spacing
  and centring in all 48 archives; nothing checked its geometry before. The new
  check rejected the old placement on the 160 of 192 screens it changes.
  Rendered against the real background art at 800x600, 1920x1080 and
  3440x1440. **Play-tested on 2026-09-24 at 3440x1440**, where the cue stays
  between the portraits; the right-of-portraits placement is not yet seen in
  game.

- **Swap-tabs prompts for every controller.** The "swap tabs" art existed for
  Xbox only, and the other controllers showed a bare X-position button there.
  PlayStation, Switch and Steam Deck now have their own. Reported working in
  play on 2026-09-24; the families tried were not recorded.

- **Installer: the optional components are independent.** Controller support
  no longer forces Modern Driver Compatibility on. Both need the same ASI loader,
  so it is installed whenever either is chosen, and Synchro's patch itself only
  when driver compatibility is. The controller option is described as what it
  now is -- Xbox, PlayStation, Switch and Steam Deck, credited to KMRP and the
  Saul0097 module it grew from -- and each row's credit no longer overlaps its
  switch. Controller support is now on by default like the other two, and
  *Restore Defaults* turns all three on. The independent switches were
  play-tested on 2026-09-24.

- **Loading a save from in game no longer crashes.** With a save already loaded
  from the main menu, loading another from the in-game menu crashed mid loading
  screen, every time. KMRP's controller module kept a table of the controller
  cues it adds to in-game screens and checked each frame whether their screens
  still existed by reading them; loading a save destroys those screens, and once
  their memory was released the check itself crashed. Cues are now forgotten when
  their screen is destroyed, their labels are freed rather than leaked, and no
  remembered screen is read without first confirming its memory is still there.
  Present since the R3 cue was added on 2026-09-15. **Play-tested on
  2026-09-24:** the same sequence now loads.

- **Feedback Options: the circles no longer sit on the scrollbar.** The option
  list keeps its scrollbar on the left, the game starts each row exactly where
  the scrollbar ends, and draws each circle at the row's very edge. The list now
  has a small gutter on that side, 12 px at 3440x1440, scaled with the
  resolution. Awaiting an in-game check.

- **Script Selection: the option rows are centred in their box.** They started
  outside the box's left edge and stopped short of its right one. The box is
  drawn by the background art at a fixed share of the screen width, so the
  rows' left inset is now computed per resolution to leave the same margin on
  both sides. Awaiting an in-game check.

- **Answering a dialog no longer acts on the world behind it** (issue #21).
  Dismissing "do you wish to turn Solo Mode on?" with A went on to start a
  conversation with whoever was targeted. A asks for the world-interaction
  bridge on press, and that request was made whatever owned the input; the
  consumer checks that gameplay is active, but it checks when it runs, and
  closing the dialog handed the input back well inside the request's 250 ms
  window. The request is now gated on press, exactly as B's already was.

- **The resolution screen has controller glyphs**, the one Options screen that
  never did (issue #21). A on OK, B on Cancel, and the D-pad moves between them.

- **A confirmation box no longer blanks the badges of the screen behind it.**
  `CSWGuiMessageBox` was missing from the panel search, and the modal branch
  returns nothing for a top modal it does not recognise, so opening any Yes/No
  dialog cleared the prompts on the screen underneath.

- **Yes/No boxes show an A beside the focused button** (issue #21, Quit Game).
  Exit Game, Solo Mode, overwrite and delete save all use one confirmation
  box, whose buttons the engine shrinks to fit their captions, so no badge can
  be painted inside them. The A is now a control of its own that sits just
  left of whichever button has focus and moves with the D-pad, like the main
  menu's. Shown only while a controller is the active device. **Play-tested
  on 2026-09-25 at 3440x1440** on Quit Game.

- **Removed the Solo Mode prompt's Cancel badge**, which drew as a thin red
  smear across the caption rather than a glyph beside it. `FixMessageLabel`
  (`0x006253A0`) rewrites both message-box button extents before drawing,
  overwriting the third field with `0x64`, so the button is roughly an eighth of
  the width its `.gui` declares and the badge is stretched by the wrong factor.
  Rebuilding it for the real width does not help: a disc sized to the control's
  height covers the middle of a button only two and a half times as wide as it
  is tall. These buttons needed a prompt drawn beside them instead of inside,
  which is what the travelling A above now is.

### Added

- Added a **Controller Layout** screen, opened from **Options → Gameplay** by a
  button directly under Keymapping. A real controller diagram — Xelu's CC0
  Xbox Series X or PS5 silhouette, tinted to KOTOR's palette with the pad's own
  face-button glyphs on it — sits between two columns of callouts, each an
  engine-drawn glyph and caption joined to its button by a leader line. It
  follows the pad: Xbox, PlayStation, Switch and Steam Deck each get their own
  diagram and glyphs, swapped live without rebuilding the screen. Captions
  describe what the native controller path actually does (View is solo mode,
  LB/RB cycle targets, Start opens the Map), not the legacy key table the first
  draft used. Row order is searched so that no leader line passes through a
  button that is not its own; on the Xbox silhouette, which three families
  share, none cross either. The screen is full-screen rather than a box: a
  navy backdrop with dim, original edge art anchored to the real screen edges
  at every aspect — corner brackets, hairlines, two status readouts, and in the
  side margins a turret gunnery station and a light freighter's deck plan. Its
  lettering is real Aurebesh (SilvinoR's OFL font) spelling English that means
  what it says. The A that opens it no longer closes it again: the screen used
  to flash for a frame and shut unless A was held. Nor does the A that closes
  it through Back reopen it, and Back now shows the pad's B / Circle glyph.
  The long captions are whole again: the game draws the screen's labels in the
  larger menu font, so they wrapped and showed only their last line ("Free
  look", "Tab"). Their boxes are now sized from that font at every resolution.

- **Options → Gameplay: Mouse Settings, Keymapping and Controller Layout sit
  higher**, by half their own spacing, so the new button no longer touches the
  bottom bar. In-game manual acceptance
  remains outstanding.

- Added a hybrid XInput / SDL3 HIDAPI controller backend and pinned x86 SDL
  packaging. Xbox retains XInput; mapped non-Xbox devices feed the existing
  normalized controller state, physical-position Nintendo glyphs, and rumble.
  Device discovery is throttled and handoff releases old-device input. Runtime
  and physical-device validation remain outstanding; see
  [controller-sdl-backend.md](docs/controller-sdl-backend.md).
- Hardened NVIDIA profile ownership: a same-name foreign profile is not adopted,
  existing shared profiles are left alone, and unavailable-driver restore keeps
  its recovery record. Verified saves remain eligible for rollback even when
  their subsequent readback fails.

- **Controller glyphs follow the controller** (issue #19). The badges and cues
  show PlayStation, Switch or Steam Deck buttons when that is the pad being used,
  and Xbox otherwise. The module asks about the one pad it reads, the way SDL
  does: `XInputGetCapabilitiesEx` (`xinput1_4.dll` ordinal 108) gives the USB
  vendor and product id behind that XInput slot -- Sony `054C` is PlayStation,
  Nintendo `057E` Switch, Valve `28DE:1205` the Steam Deck, anything else Xbox.
  Through **Steam Input** the slot holds Steam's virtual pad (`28DE:11FF`), and
  Steam publishes the physical controller behind it in the file named by
  `SteamVirtualGamepadInfo`, which the module reads for that pad's `[slot N]`. A
  translator that presents an Xbox pad of its own, such as DS4Windows, gets Xbox
  buttons. It is asked only when that pad connects or changes slot, or when Steam
  rewrites its file: no timer, nothing to configure.

  All four families are built and shipped, named by the resref's fourth letter
  (`kmrpb_charexit` Xbox, `kmrsb_…` PlayStation, `kmrnb_…` Switch, `kmrdb_…` Steam
  Deck), so the Xbox names are unchanged and nothing grows past 16 characters;
  the installer grew 28.1 MB. The Switch set maps by button **position** -- the
  bottom button a Switch Pro labels B carries the A action -- which assumes a
  positional translator. `check_controller_drift.py` fails if the module's and the
  build's family letters disagree or any family's art is missing, and
  `Test-ControllerPromptAssets.py` checks every family's badges against that
  family's own art.

  **Verified:** the call on this machine (a virtual Xbox 360 pad reads
  `045E:028E`) and the parsing of Steam's file in SDL's documented format.
  **Untested:** a real Steam virtual pad, any physical PlayStation, Switch or Steam
  Deck controller, Proton, and the new families' art in game. See *Controller
  families* in [`docs/controller-support.md`](docs/controller-support.md).
  **Reported working by the maintainer on 2026-09-28**, and issue #19
  closed that day; which controllers were used was not recorded.
- **Start opens the Map, and closes the menu again** (issue #18). In the world
  it now sends the engine's own Map hotkey, event `0xD7`, instead of Start's
  `0x0B`, which opened Options; with the in-game menu in front it acts as B, so it
  closes the Map or whichever screen LT/RT moved to. The Map is `0xD7` because the
  router sends `0xD1`–`0xD8` to one handler (`0x006218D5`) that shows screen
  `event - 0xD1`, and the Map's tab ID in `top.gui` is 6. Options and every other
  screen stay one LT/RT away. **Play-tested on 2026-09-25 at 3440x1440: it
  works.** `testing/controller/test_hud_release_and_start_map.py` checks it
  against the engine's memory once a save is loaded.
- **X is shown beside the Skills / Powers / Feats tabs.** It has cycled them
  all along and nothing said so.

  That it really does was read from the handler rather than assumed: the
  ABILITIES panel registers `0x29` at `0x006AE714`, which reads a byte at
  `CGuiInGame+0xBC0`, switches on 0, 1 and 2, and writes 0 back on the third
  -- a three-state cycle that wraps, which is exactly three sub-tabs.

  One control rather than two: the bundled `Swap_tabs.png` is already the
  whole phrase, the X button and the arrows together. Its art is about two to
  one, so its control is given that shape and its texture the same, which
  keeps the engine's stretch equal on both axes -- the square cue builder now
  takes a height for exactly this.

  Placed from the sub-tab row: one third of a tab's height past the last tab,
  on the row's own line.
- **LT and RT are shown either side of the menu tab strip.** They have moved
  between the eight in-game screens since controller support landed, and
  nothing said so.

  The same mechanism as the R3 cue, on a panel that took no extra proving:
  the tabs are not in the screens that display them -- `inventory.gui` has no
  tab controls at all -- they belong to `top.gui`, whose panel draws with the
  base `CSWGuiPanel::Draw`, the same child-walk the cue mechanism relies on.

  Both cues are positioned from the strip itself: its pitch, its height and
  its vertical centre, each sitting one pitch beyond the outermost tab, where
  a ninth and a zeroth tab would be. So they follow the strip at every
  resolution with no coordinates to keep in step.

  The runtime table changed shape -- from a list of panels sharing one tag to
  a list of (panel, tag) pairs -- because this panel wants two cues rather
  than one. Nothing else about the binding changed.
- **R3 changes which party member a menu is showing.** Character, Equipment,
  Inventory and the Skills/Powers/Feats screen are each about one party
  member, and with a pad there was no way to switch between them: the two
  portrait buttons in the bottom bar could only be clicked.

  Nothing new had to be invented. `0xCE` is a retained GUI event the screens
  implement themselves, and the full event inventory says exactly four panels
  implement it -- ABILITIES, CHARACTER, EQUIP and INVENTORY, which are
  precisely the four screens that carry the portrait pair. That match is the
  evidence it is the party switch rather than something else sharing a code.

  Dispatched to the panel rather than to `CClientExoAppInternal`. The two are
  different actions with one name: `0x09` changes who the player controls in
  the world, `0xCE` changes who a screen is about. Only the second belongs in
  a menu. It is performed on the GUI frame rather than in the input hook,
  because the handlers rebuild the screen around the new character -- the same
  reason the Journal's remapped buttons are deferred. Counted as `psw`.

  R3's native code is suppressed while a menu is in front. It did nothing
  there already -- free-look enter is registered in `ICPC` only, so the slot
  is not polled in `ICPCGUI` -- but one press meaning one thing is the rule
  the rest of the input layer follows. Free look in gameplay is unchanged.

  **It is advertised by the two portraits, on a control the game does not
  have** -- between them, or right of them where the gap is too narrow (the
  entry above; it was always between them until 2026-09-24, 5 px wide at
  800x600). There was nowhere to put a badge: a badge replaces a control's
  `BORDER.FILL`, the portraits' fill *is* the portrait -- rewritten per
  character by the panel -- and the gap between them holds no control. No
  spare label exists to move there either; Inventory has fifteen controls and
  uses all fifteen.

  Adding one to the `.gui` does nothing on its own, which was measured rather
  than assumed: a control was added to a live `inventory.gui` and nothing
  drew. The reason is that a panel does not load the file's controls, it asks
  for the ones it knows by name -- `0x0040B930` resolves a tag by walking the
  GFF and comparing `TAG` -- so a control nobody asks for is never built.

  So the build adds `LBL_KMRPR3` to the four screens, placed from each
  resolution's own portrait extents, and the module binds it at runtime. That
  is possible in exactly one instant: every panel constructor ends by calling
  `CSWGuiPanel::ReleaseGff`, which deletes the parsed `.gui` and nulls the
  pointer the binder reads. Hooking that one function catches all 68
  constructors with the panel already in `ecx`, and its prologue has no
  relative operand for a trampoline to relocate. Panels that are not party
  screens are ignored.

  The control is then drawn because `CSWGuiPanel::Draw` walks the same array
  the binder files into, skipping null slots and gating each child on
  `bit_flags & 2`. That bit is the engine's own show/hide -- it sets it on a
  control that loaded and clears it to hide one, which is how CHARACTER hides
  its ten alignment-meter labels immediately after binding them -- so the cue
  follows the pad by flipping one bit rather than swapping any artwork.

  Sizes and addresses were read from the gold image and each confirmed more
  than once; `reverse-engineering/custom-gui-controls.md` records every one,
  including the ownership question -- the array's destructor frees the pointer
  block and never dereferences an element, so a control we allocate is never
  freed. That is a `0x140` byte leak per panel construction, against the
  `0x1DE8` the engine allocates for the panel itself.

  The glyph is `XboxSeriesX_Right_Stick_Click.png`, on its own square texture:
  the control is square at every resolution, so unlike the caption badges it
  needs no pre-compensation and one texture serves the whole game. `L3` is
  deliberately left on the 360 artwork -- nothing uses it, and restyling an
  unused glyph is a change nobody asked for.

### Fixed
- **B lets go of the bottom-right action bar** (issue #17), so the next A talks
  to the NPC or opens the door again. B uses nothing -- it had no other effect
  in the world. D-pad Left/Right re-enters the bar as before, and A on a slot
  uses it and **keeps the bar focused**, so an attack or a grenade can be used
  again at once. The press that uses a slot also clears the world interaction's
  pending request, so one press does exactly one thing. `hrel=` in the
  diagnostic line counts the releases. **Play-tested on 2026-09-25** on an Xbox
  pad at 3440x1440 ("works perfectly"): A keeps the bar focused. B's release
  was not separately reported. See
  `testing/controller/test_hud_release_and_start_map.py`.

  *Changed 2026-09-25, at the user's request:* this entry first had A let go of
  the bar too, after using a slot. In combat that meant D-pad Right before
  every action, where the user wanted to press attack repeatedly.
- **The one-frame white flash in the in-game menus is gone** (issue #14), along
  with two quieter relatives: the menu backdrop drawn alone for a frame when
  switching to the Utility or Equipable filter, and a half-drawn world, with
  characters missing, on the frame a menu closes.

  None of the three was the engine's doing. NVIDIA's **"Vulkan/OpenGL present
  method: Prefer layered on DXGI Swapchain"** puts frames on screen that the game
  has not finished drawing, and each symptom is a frame caught while it stalled:
  the flash is `WinMain`'s bare frame-start `glClear` (the area's `SunFogColor`,
  near-white on Manaan) during the 15–65 ms the inventory takes to rebuild.
  Measured on an RTX 3080, driver 32.0.16.1656, two-minute captures:

  | present method | menu fix | white flashes | other unfinished frames |
  | --- | --- | ---: | ---: |
  | Prefer layered (global) | off | 7 of 8 tab entries | — |
  | Prefer layered (global) | on | 0 | 2 and 6 in two runs |
  | Prefer native | on | 0 | 0 |
  | Prefer native | off (checked in the live process) | 0 | 0 |

  NVIDIA's default is Auto, and on Auto the driver presented both vanilla and
  KMRP natively in-game; this machine's *global* had been set to prefer layered.
  So the patcher now checks, through NvAPI, what the driver will do for the
  installed `swkotor.exe`, and **only if it would inherit Prefer layered** sets
  Prefer native (`OGL_CPL_PREFER_DXPRESENT`, `0x20D690F8` = `0`) in the game's
  own profile — normally NVIDIA's predefined KOTOR profile — recording it in
  `KMRP_NVIDIA.manifest`. A value set for the game on purpose is left alone,
  the global profile is never touched, restore removes only KMRP's value, and
  any error is logged with the manual steps rather than failing the install. No
  administrator rights needed. See
  [`docs/nvidia-present-method.md`](docs/nvidia-present-method.md) and
  `testing/regression/Test-NvidiaPresentMethod.ps1`.

  **Correction, 2026-09-19:** the development renderer-clear mitigation was
  removed from the module, exports, TOML, and installer. It had hooked VA
  `0x0040467C` (`NativeFrameClearK1`) and `0x004512D0`
  (`NativeSceneRenderK1`), with diagnostic `fcl=` counters. Native driver
  presentation is the production fix; no independent engine defect justified
  retaining clear suppression. Historical measurements remain in
  [the investigation](reverse-engineering/experiments/white-flash-video-capture.md).

  **Untested:** a full install writing a real KOTOR profile (this machine's
  already held a value, which the installer correctly kept), 32-bit Windows,
  older drivers, Optimus laptops, and AMD or Intel, where no such path was seen.

  **Play-tested on 2026-09-25 at 3440x1440: no white flash** when switching
  party members. On that PC the driver resolves Prefer native from the game's own NVIDIA profile, with the global still Prefer layered (read 2026-09-25 with `NvidiaPresentSelfTest describe`), so KMRP's step found a value set on purpose and left it alone; there is no `KMRP_NVIDIA.manifest`. That confirms the setting removes the flash, not KMRP writing it in a real install.
- **Three memory-safety patches from the Kotor Patch Manager project are now
  installed.** Two are VexFlint's and one is Lane Dibello's, each adopted
  rather than re-derived: the replacement bytes are copied verbatim, so the
  behaviour is the one reviewed there. KMRP
  had already folded in KPM's *rendering* fixes -- cube maps, grass tearing,
  soft shadows -- and none of its memory ones, and that split was not
  principled. Two of the three are bounds and lifetime bugs that get more
  likely the more textures and data a session loads, which is what KMRP does to
  this engine.

  They install as ordinary entries in KMRP's own hook table, so the executable
  on disk is not touched and the gold SHA-256 is unchanged at
  `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`. Each
  patch's `original_bytes` was checked to match **both** the clean source and
  the gold image -- KMRP's own delta touches none of those four addresses.

  | site | address | type | what it does |
  | --- | --- | --- | --- |
  | `AurTextureGetMaxTexID` | `0x0041FEB5` | `replace` | saturates the returned id at 4999 |
  | `AddPartToMeshBuckets` | `0x0046BE64` | `replace` | range-checks the id before the indexed write, rejoining at `0x0046BEB1` |
  | `DestroyGrassPolys` | `0x004A847C` | `replace` | zeroes the argument when `+0x3C` aliases `+0x38` |
  | `~CAurTriangleBin` | `0x004A8380` | `replace` | the same, with `eax` for `edx` |
  | `CERFFile::WriteResource+0x272` | `0x005DDE32` | `detour` | `NativeFreeSaveBufferK1` frees the buffer the writer abandons |

  The first two are the texture-bucket overrun: three 5000-entry arrays at
  `0x008194E0` are indexed by driver-assigned GL texture names with no range
  check, and `maxTexID` (`0x007A46BC`) only ever rises. Saturating rather than
  masking, because an `AND` would wrap a legitimate 4500 down to 404 and leave
  stale buckets uncleared. See
  [`reverse-engineering/experiments/texture-bucket-overrun.md`](reverse-engineering/experiments/texture-bucket-overrun.md).

  The grass pair is one allocation stored in two fields that two paths each
  free; `free` (`0x006FB7B2`) guards NULL explicitly, so zeroing the aliased
  argument is a safe no-op. The save detour reclaims one buffer per resource
  written, counted as `sbf` in the diagnostic line.

  The hook tooling had to learn that a hook need not name an exported function:
  `kmrp_controller.is_byte_patch` identifies one, ownership for those is KMRP
  directly, the renderer emits `replacement_bytes` instead of `function`, and
  the drift checker matches them by address. Without that, adding the first
  byte patch would have raised `KeyError` in every one of those checks.

  **Measured in play, not assumed:** across two sessions on this build
  `maxTexID` peaked at 471 and 296 against the 5000-entry array, so the
  overrun was not reached in either -- the patch is a guard, and nothing here
  claims it fixed a symptom that was observed. `sbf` stayed 0 because neither
  session saved.
- **Holding a D-pad direction now scrolls a list, on every screen.** Reported
  on Quest Items: a held Down moved one item and stopped.

  Two layers navigate menus, and only one of them repeated. Where KMRP moves
  the focus itself it has always held-and-repeated -- 400 ms, then every
  120 ms -- which is why the tabbed screens behaved. Where the ENGINE
  navigates, KMRP stands down and emits the retained direction code instead:
  `NavigateFocusK1` declines when a focused control navigates itself and the
  screen has no tab strip, and `KmrpOwnsDirectionsK1` agrees. That path sent
  one press and one release, and `CSWGuiListBox` acts on the press and
  nothing after it -- it has no auto-repeat of its own.

  The emitter now repeats the presses it sends, on the same two constants, so
  a held direction feels identical whichever layer is handling the screen. It
  repeats only what actually went out (`dpadEmitted`), so the screens KMRP
  navigates are untouched and the direction is never delivered twice -- the
  double-step `KmrpOwnsDirectionsK1` exists to prevent. Each repeat releases
  before pressing, because a second press with no release in between is not
  an edge and the engine would ignore it. Counted as `drp` in the diagnostic
  line.

- **A pad that is plugged in shows its badges from the first frame**, instead of
  waiting to be pressed. Reported from the launch sequence: skipping the intro
  movies with the pad and then arriving at a main menu with no badges on it.

  "Nobody has used anything yet" was the state that did not exist. The flag was a
  boolean over two meanings -- pad, or not-pad -- with not-pad as the opening
  value, so a menu reached before any press read as keyboard-and-mouse. It is now
  three: the pad is in use, the keyboard or mouse is in use, or the question is
  still open. While it is open a connected pad answers it, because a pad plugged
  in is a statement of intent where a keyboard sitting there is not. The instant
  either device is actually used the question closes for good, so nothing about
  how the two hand over has changed -- only where they start.

  The connected half had to be taught to the native path too.
  `g_controllerConnected` was maintained only by `ReadPad`, which runs from the
  legacy poll; the native module reads XInput itself, so it knew a pad was
  answering while that flag did not, and the opening state could never have
  fired. `ReadPadAxes` now reports presence either way.

  Worth noting for anyone chasing the same symptom: `ConsumeMovieSkipK1` was
  *not* the culprit. It already raises the active flag when a skip button is
  held, so skipping a movie with the pad did count as pad use. **Playtest
  pending.**

### Added
- **An A badge that follows the focus down the main menu**, and badge art for
  the equipment and quest items screens, which had none at all.

  The main menu's badge is a new kind of binding, `FocusOnly`: it is painted only
  while its control holds the panel's focus and cleared otherwise, so one A
  travels with the selection instead of five sitting there at once. Clearing is
  as much the point as painting -- without it the badge would be left behind on
  the entry the focus just left. The focused control is now part of the state the
  repaint compares against, or the early-out would hold the first frame's badge
  for as long as the screen stayed up, which is the trap the inventory filter's
  caption fell into.

  All five are placed as a **badge group**: sized from the shortest control in
  the group and placed against the widest label in it, so they stand in one
  column at one size. Placing each against its own button gave five glyphs that
  stepped sideways down the list, and made Quit's a fifth larger than the rest
  because it is 81 tall where the others are 66.

  | Button | Label | Was | Now |
  | --- | --- | --- | --- |
  | New Game | 181px | x 194.7, r 19.1 | **x 187.0, r 19.1** |
  | Load Game | 197px | x 187.0, r 19.1 | **x 187.0, r 19.1** |
  | Movies | 121px | x 224.8, r 19.1 | **x 187.0, r 19.1** |
  | Options | 142px | x 214.4, r 19.1 | **x 187.0, r 19.1** |
  | Quit | 74px | x 241.8, r **23.5** | **x 187.0, r 19.1** |

  The installer's re-centring survives grouping without any change to it, and
  the reason is worth recording: its shift is
  `CenterFor(measured) - CenterFor(baked)`, which reduces to
  `(baked - measured) / 2` -- the radius cancels. So giving every member of the
  group the same variants in the manifest makes them all resolve the same
  measured width and shift by the same amount, and the column survives a
  language whose wording is longer.

- **The control offsets came out of the engine rather than a symbol database.**
  A panel's controls are embedded objects and the bind call names each one:

  ```
  0067AE38  push 0x752F0C          "BTN_LOADGAME"
  0067AE4D  lea  eax, [esi+0x5B4]   the embedded control
  0067AE5E  call 0x0040B930         bind
  ```

  `tools/extract_control_offsets.py` reads all 771 of those call sites. Doing it
  mechanically mattered: the four upper main-menu buttons sit on a uniform
  `0x1C4` stride and `BTN_EXIT` does not -- it is bound earlier, at `0x1084` --
  so extrapolating the stride would have put that badge on nothing. The register
  holding the control also varies (`ecx`, `eax`, `edx`, and `ebx` loaded 240
  bytes earlier on the quest items screen), which mispaired two tags until the
  extractor matched `lea`/`push` pairs rather than a fixed register; every
  offset below was then checked against the disassembly.

  | Screen | Button | Offset | Badge |
  | --- | --- | --- | --- |
  | Main menu | NEWGAME / LOADGAME / MOVIES / OPTIONS / EXIT | `0x3F0` `0x5B4` `0x778` `0x93C` `0x1084` | A, follows focus |
  | Equip | BTN_EQUIP / BTN_BACK | `0x3698` / `0x385C` | A / B |
  | Quest items | BTN_BACK | `0x8A8` | B |

  **Playtest pending.**

### Fixed
- **The mouse no longer stops working at random, and the pointer hides and
  returns with the input device reliably.** Reported as two symptoms -- sometimes
  no menu item can be clicked, keyboard only; and the cursor not disappearing for
  the pad and reappearing for the mouse -- which turned out to be one mechanism,
  and two faults in it rather than anything to do with detecting input.

  KMRP parks the pointer near the top of the screen and hides it through the
  engine's own reason mask while the pad is the device in use.

  **A failed park or unpark was forgotten.** The pending flag was cleared
  unconditionally, before the move was attempted:

  ```
  g_pendingCursorToggle = false;         // cleared whatever happens
  if (MoveK1Cursor(!g_cursorParked)) {   // and this can fail
  ```

  `MoveK1Cursor` returns false whenever there is no active GUI manager or its
  viewport is not sized -- during a load, a movie, a scene transition. The
  request was dropped there, and since the edge that raised it had already
  recorded the new device, it could never be raised again until the device
  changed a second time. When the failure landed on the *unpark*, the cursor
  stayed parked and hidden while the player was on mouse, and the per-frame
  re-assert kept snapping it back to the top of the screen: invisible, immovable,
  hit-testing nothing. That is the "I can't press any menu items with the mouse"
  exactly, and as intermittent as whether a GUI manager happened to exist at that
  moment. The flag is now cleared only once the move has actually happened.

  **The module counted its own cursor moves as the player using the mouse.**
  `MoveK1Cursor` goes through the engine's `MoveMouseToPosition`, which forwards
  to `HandleMouseMove` -- the very function KMRP hooks to notice mouse activity.
  So every park, and every re-assert of the park spot, read as though a hand had
  moved the pointer. That broke the detector both ways: several panels place the
  cursor on a default control as they open, so the re-assert undoing it could
  accumulate the 24 pixels and 2 events that mean "the mouse is in use" and hand
  the pointer back mid-controller-session; and while parked, a real movement and
  the snap-back cancelling it both counted, so the distance measured bore little
  relation to how far the hand moved. A guard around the module's own moves now
  keeps them out of the detector.

  One consequence of retrying is that a flip can still be pending when the device
  changes again, which would apply it the wrong way round. The device-change edge
  now *assigns* the flag rather than only raising it, so a stale request is
  cancelled -- which also means a device change wins over a pending F9, the right
  precedence for an override that only applies within a mode. **Playtest
  pending.**

- **The Journal's A and Y buttons do what their badges say.** Reported from
  play: the button labelled A, "Active Quests", was pressed by Y, and the button
  labelled Y, "Sort by Priority", answered to nothing.

  Read out of `CSWGuiInGameJournal`'s dispatcher at `0x006456E0`:

  | Event | Handler | What it does | Pad sent it |
  | --- | --- | --- | --- |
  | `0x29` | `0x00645C8C` | opens Quest Items, via `0x0040BC70` on `[panel+0xFB4]` | X |
  | `0x2A` | `0x006459CE` | Active/Completed -- `0x00645610`, then a re-sort | **Y** |
  | `0x2B` | `0x0064573F` | the sort order -- `inc eax / cmp eax, 4` into `[0x00833A90]` | **Back** |
  | `0x28` | `0x00645CAB` | close | B |

  So the badges were right about the intended layout and wrong about the facts.
  The sort was not unreachable -- Back sends `0x2B` -- but no badge says so, so
  in practice it answered to nothing a player would try.

  A now sends `0x2A` and Y sends `0x2B`, on this screen only, through a small
  per-panel remap table. The native code is **suppressed** for a remapped
  button, which is what makes it a remap rather than an addition: without that,
  Y would sort *and* toggle in one press. The decision is taken at the press and
  remembered for the release, the same way the direction codes do it -- deciding
  again at the release would let a screen change mid-press leave a digital
  description holding a value nothing ever clears, and the button would stick on
  for the rest of the session.

  Back keeps `0x2B`. It is a second way to reach the sort, it collides with
  nothing, and removing it was not asked for. The comment on that binding said
  "Journal quest items", which was wrong -- quest items is `0x29`, on X -- and
  now says what `0x2B` actually is.

  `rmp=` in the diagnostic line counts remapped presses performed.
  **Playtest pending.**

### Changed
- **The item icons ship at 160x160 instead of 192x192**, taking the pack from
  12.4 MB to 8.5 MB: 25.0 KB an icon rather than 36.1 KB. This reverses an
  earlier decision to keep them at native size, so the reasoning for the
  reversal is recorded beside the reasoning it replaces.

  The cost is real and measured. `equip.gui` draws item icons through controls
  whose EXTENT is exactly 192x192 at the authored resolution, so 192 is native
  and 160 is upsampled 1.2x on the largest place icons are drawn -- 24.1 dB
  against 27.8 dB on colour weighted by visibility.

  | Size | Each | 351 total | Visible colour |
  | --- | --- | --- | --- |
  | 192 | 36.1 KB | 12.39 MB | 27.8 dB |
  | **160** | **25.0 KB** | **8.57 MB** | **24.1 dB** |
  | 144 | 20.2 KB | 6.94 MB | 23.5 dB |
  | 128 | 16.0 KB | 5.48 MB | 22.6 dB |

  **The free version of this saving does not exist**, which is why resolution
  was the only lever. DXT1 would have halved the size at 34 dB -- it carries no
  alpha, so it spends its whole budget on colour -- but it needs one bit of
  alpha and this executable cannot upload that at all. The format table at
  `0x0073F36C` holds the no-alpha `0x83F0` and DXT5's `0x83F3` and nothing else;
  `GL_COMPRESSED_RGBA_S3TC_DXT1` (`0x83F1`) appears nowhere in the image.
  Repointing `0x83F0` would hand the transparent three-colour mode to all 5,229
  shipped DXT1 textures, and **1,387 of them use it** -- holes through Jawa,
  Gammorean and Ithorian skins and the BioWare logo.

  **The resize is premultiplied**, and that is a correctness fix rather than a
  refinement: the RGB of a fully transparent pixel in these icons is arbitrary,
  and a straight Lanczos blends it into the visible edge as a fringe. Measured
  on twelve icons, the naive and premultiplied resizes differ by 30.5 dB -- the
  same order as the compression error itself, so doing it the easy way would
  have thrown away much of what the remaining pixels buy.

  `ICON_TEXTURE_SIZE` in `prepare_universal_resources.py` is the one place this
  lives; setting it back to `ICON_SOURCE_SIZE` restores native size and nothing
  else has to change. **Playtest pending.**

### Fixed
- **The full-screen menu backgrounds are compressed.** With the item icons
  converted, they were what was left: an installed Override measured 1008 MB, of
  which all 351 icons are 12.4 MB -- 1.2% -- and forty-nine full-screen
  backgrounds are 768 MB, at 15.68 MB apiece, uncompressed 32-bit. Two of them
  are `lbl_equip` and `lbl_invent`, read exactly when the Equipment and
  Inventory screens open, which is where a residual hitch was reported after the
  icons were fixed.

  Measured on the installed files at 2867x1434:

  | | Size | | Quality |
  | --- | --- | --- | --- |
  | uncompressed | 15.68 MB | | |
  | **DXT1** | **1.96 MB** | 8.0x | 37.7 dB |
  | DXT5 | 3.91 MB | 4.0x | same colour; the alpha is all 255 |

  27 of the 49 are fully opaque -- every `lbl_*` menu background, including both
  of the two that matter -- so they take DXT1, which with no alpha to carry
  spends its whole budget on colour. That is why it scores *better* here than
  DXT5 does on the item icons (36.9 dB), where half the bits go to an alpha
  channel. The engine already uploads 5,229 of its own textures this way. The
  other 22 are loading screens carrying alpha on 0.49% of their pixels, and take
  DXT5.

  Across all 49: **768 MB -> 139 MB**, and opening Equipment reads 1.96 MB where
  it read 15.68 MB.

  Two details worth keeping. DXT encodes 4x4 blocks and these are 2867x1434, so
  the image is padded up to the block grid by repeating its last row and column
  -- padded rather than cropped, because the added pixels duplicate the frame
  border where a crop would shave three columns off it. And the source TGAs
  carry descriptor `0x08`, bottom-left origin, matching TPC's own row order, so
  they are flipped before encoding exactly as the icons are; the icons once
  shipped upside down for want of that.

  **Font atlases are excluded and must stay excluded.** `dialogfont32x32` is
  2048x2048 -- *larger* in pixels than these backgrounds, so a size threshold
  alone would catch it -- and DXT on glyph edges would visibly damage every line
  of text in the game. The selection tests the name as well, and the build now
  fails if the number of backgrounds it compresses is not exactly 49, so a
  change to the shared assets cannot quietly pull a font in or drop a background
  out. **Playtest pending.**

- **The compressed item icons can actually reach an existing installation.**
  The HD icons ship as DXT5 `.tpc` rather than 192x192 uncompressed `.tga`,
  because Inventory and Equipment are the only two screens that stall and the
  only two that draw dozens of icons. On any machine that already had KMRP
  installed, that fix could never land, so the stall stayed.

  Bundled third-party art yields to whatever is already in `Override`, so KMRP
  never overwrites a mod the player installed on purpose -- and the test spans
  texture extensions, because the engine resolves a texture by resref and
  prefers `.tpc` over `.tga`, so a bundled `.tpc` would otherwise silently win
  over a player's `.tga`. But it only asked whether a sibling *existed*, never
  whose it was. Installing `i_x.tpc` looks up `i_x.tpc` in the manifest, does
  not find it -- the manifest holds `i_x.tga` from the build before -- and then
  yields to that `.tga`. **KMRP was deferring to itself.**

  Measured on a live installation patched before the change:

  | | |
  | --- | --- |
  | `.tga` in Override | 1095 |
  | `.tpc` in Override | **0** |
  | at 147,500 bytes (192x192, uncompressed) | 399 |
  | of those, bundled by the current build as `.tpc` | **351** |
  | files recorded in the manifest as KMRP's own | 1196 |

  Those 351 total 12.4 MB as `.tpc` against 51.8 MB as `.tga` -- 4.1x smaller,
  39.4 MB less to load on the two screens that stall.

  Two changes. The sibling test now ignores a sibling the manifest already
  records as ours, since a file KMRP installed is not the player's file whatever
  extension it carries. And installing a texture over our own superseded sibling
  deletes that sibling, so the uncompressed copies do not sit on disk forever
  and do not keep blocking every future install. The sibling's manifest record
  is deliberately left in place: restore skips its hash check when the file is
  gone, and still copies the player's original back if they had one.

  The installer now reports how many it replaced.

  **Not changed:** 48 icons still ship as 192x192 uncompressed, and they are
  KMRP's own art rather than the bundled pack -- 18 empty-equipment-slot
  placeholders and 30 `lbl_*` tab and HUD pieces. They are interface chrome with
  hard edges, where DXT artefacts show far more than they do on item art, and 18
  textures are not what makes a full inventory stutter. Left alone on purpose.
  **Playtest pending.**

- **The X badge sits beside the inventory filter button's caption, whichever
  caption it is showing.** It used to be drawn on top of the words. The badge is
  placed against the measured width of the label, and this button was declared
  as STRREF 32182 -- the bare words "Quest Items", which it never says.

  Its caption is built at runtime from an index:

  ```
  006B3A58  call 0x005ED690               CClientExoApp::GetGuiInGame
  006B3A5D  movzx eax, byte [eax+0xBC1]   the current filter
  006B3A64  inc eax                       the button offers the NEXT one
  006B3A65  cmp eax, 6 / mov 0            six wraps to zero
  006B3A88  mov edx, [ecx*4 + 0x756444]   that index into a STRREF table
  006B3AAC  push 0xA577                   42359, "Show"
  006B3ADD  call 0x005E5D10               append
  ```

  so it reads "Show " plus one of six filter names -- All Items, New Items,
  Quest Items, Equippable Items, Utility Items, Useable Items. Six, not the five
  consecutive strings `41818`-`41822`: "New Items" sits apart at `42165`, and is
  the one the `kmrpx_invnew` resref was named for.

  Measured on the 1166px-wide button with the metrics inside the built archive:
  "Quest Items" is 222px, and placing the badge for it put the glyph on top of
  **every one of the six captions** -- 19px into the shortest, 90px into the
  longest. The first pass at these figures used a font atlas found by globbing
  the repository rather than the one this resolution ships, and understated it.

  Rather than place it against the longest caption -- which never overlaps but
  leaves it floating up to 103px away from the shortest -- the build now bakes
  **one badge per caption**, `kmrpx_invnew0`-`5`, and the module picks the
  matching one from the engine's own filter index. Not by reading the label,
  which would depend on the player's language: `CGuiInGame+0xBC1` plus one,
  wrapping at six, is exactly the index the engine itself used to choose the
  words. Every caption now clears the text by the same 15px:

  Clearance is the gap between the badge's right edge and the first letter;
  negative means the glyph is drawn over the words.

  | Index | Caption | Label | Shipped | Widest-only | Per-caption |
  | --- | --- | --- | --- | --- | --- |
  | 0 | Show All Items | 289px | **-19px** | 86px | 15px |
  | 1 | Show New Items | 300px | **-24px** | 80px | 15px |
  | 2 | Show Quest Items | 337px | **-42px** | 62px | 15px |
  | 3 | Show Equippable Items | 431px | **-90px** | 15px | 15px |
  | 4 | Show Utility Items | 353px | **-50px** | 54px | 15px |
  | 5 | Show Useable Items | 379px | **-63px** | 41px | 15px |

  The middle column is what declaring the six captions but keeping one texture
  would have given: never overlapping, but drifting up to 86px from the words.
  The last is what shipped -- the same 15px on every caption, which is the
  generator's own gap constant, `radius * 0.55`.

  Each numbered texture carries only its own wording in the placement manifest,
  so the installer's existing per-row re-centring against the player's real
  `dialog.tlk` handles each one correctly with no change to it. The unnumbered
  `kmrpx_invnew` is still generated, placed against the widest, as the fallback
  for a module that cannot read the index.

  Three other toggling buttons were declaring only one of their wordings and had
  happened to pick the wider one: Messages' "Show Feedback" / "Show Dialog", the
  Journal's "Completed Quests" / "Active Quests", and its four sort orders. They
  now declare all of them. No English art changes, but the installer re-resolves
  these against the player's own `dialog.tlk`, so an undeclared variant is an
  overlapped badge in any localisation where the other wording is longer. These
  keep a single texture: their captions differ by far less, and each would need
  its own index read to do better. **Playtest pending.**

### Removed
- **The D-pad no longer moves focus onto the in-game menu's tab strip.** That
  layer was built before LT and RT changed screens; with those working it was a
  second, worse way to do the same thing, because focus could sit on a tab frame
  and a direction press then had two possible meanings depending on invisible
  state. The strip is no longer a focus target at all: every direction press
  acts on the content of the tab being shown. LT and RT change screen, X still
  cycles sub-tabs.

  Removed with it, each having existed only to serve focus sitting on a frame:
  the frames walk and the enter-content press, both routes back up to the strip
  (off the top of a list, and off a content panel's top boundary), the
  A-on-a-focused-frame bridge and the request the input hook raised for it, the
  tab-frames-only candidate filter, and five helpers left with no callers. The
  `entered`, `returned` and `activated` counters went too, since nothing could
  increment them any more. **Playtest pending.**

### Added
- **The diagnostic line's format and argument list are checked against each
  other.** `check_controller_drift.py` now parses the `wsprintfA` call, counts
  conversions against top-level arguments, and reports the worst-case width
  against the buffer. This is the bug it exists for: a conversion was once
  inserted mid-format with its argument appended at the end of the list, so
  every field after it printed the wrong variable, and the widened line overran
  a 512-byte stack buffer and tripped the `/GS` stack cookie -- the game froze
  on load and the cause looked nothing like a logging change. Verified to fail
  by introducing a mismatch deliberately.

### Fixed
- **Left and right on the equipment screen move sideways instead of jumping a
  row up.** The 3x3 slot grid is 192x192 cells on a row pitch of 150, so
  consecutive rows overlap by 42 pixels while the columns, on a pitch of 268, do
  not overlap at all. The focus layer waived its cross-axis penalty outright
  whenever two controls overlapped on that axis, so pressing right from Body
  scored the correct neighbour (Right Arm), the slot above it (Hands) and the
  slot below it (Right Weapon) at exactly 268 apiece -- same horizontal step, all
  three counted as "in the row". The tie-break is a strict less-than, so the
  first in the control array won, and the array runs top to bottom.

  The waiver is now a discount: a candidate that still touches the row pays a
  third of the rate one that misses it entirely pays, rather than nothing.
  Scored against the real geometry from the generated `equip.gui`, over all nine
  cells and all four directions, the old rule was wrong eight times -- every one
  of them a left or a right, with up and down always correct because the columns
  do not overlap -- and the new rule is wrong none. **Playtest pending.**

### Added
- **Rumble works.** The engine's rumble subsystem was never removed from the PC
  build -- `UpdateRumble` ticks every frame, the pattern evaluator and the mixer
  are both intact, and the module already forwarded the result to XInput. One
  field stopped all of it. `PlayRumblePattern` tests the caller's index against
  the pattern *count* before anything else:

  ```
  005FB49F  cmp ebp, dword ptr [ecx+0x344]
  005FB4A5  jge 0x5fb536                      -> return 0, nothing queued
  ```

  and that count is zero for the life of the process, so every rumble the game
  asked for was dropped at the door. Two instructions in the entire class write
  those fields -- the constructor zeroing them (`0x005FC15C`, `0x005FC168`) and
  the destructor freeing and re-zeroing (`0x005FC82A`, `0x005FC844`) -- found by
  sweeping every instruction in the class's address range, not by inference.
  The loader went with the Xbox build.

  KMRP now supplies the table, and nothing else changes: `PlayRumblePattern`
  appends an instance, `UpdateRumble` walks the list taking each motor's maximum
  through `CSWRumblePattern::GetMagnitudes`, and the detour already sitting on
  `0x005F7617` forwards the pair to XInput.

  **Which patterns exist is measured, not invented.** Two exhaustive sweeps of
  the shipped content:

  | Source | Swept | Patterns found |
  | --- | --- | --- |
  | 2DAs with a `rumblepattern` column | all 209 in `chitin.key` | `footstepsounds` → 17; `visualeffects` → 11, 14, 16, 20 |
  | NCS calls to routine 370, `PlayRumblePattern` | all 401 bifs, rims, erfs and mods | adds 5, 12, 13, 15 |

  The union is 5, 11, 12, 13, 14, 15, 16, 17, 20, so the count is 21 and every
  index nothing references is silent rather than guessed at. The same sweep
  found **no** call to `StopRumblePattern` anywhere in the shipped content, which
  settles the loop flag: a looping pattern would never be stopped and the motors
  would run until the area unloaded, so every entry is one-shot.

  | Pattern | What fires it | Shape |
  | --- | --- | --- |
  | 5 | `k_pend_1b_area2` | a swell, ~1.1s |
  | 11 | tarentatek/terentatek arrivals, `VFX_FNF_TERANTANAK_DEATH` | slow and heavy, ~0.9s |
  | 12 | `k_pkor_ceil_fall` | the hit, then debris, ~1.2s |
  | 13 | `k_pkor_ther_dest` | demolition: full scale, long tail |
  | 14 | all seven grenade VFX plus 18 script sites | a crack and a fast decay, ~0.45s |
  | 15 | `k_pend_rumble01` | a sustained tremor, ~2.2s |
  | 16 | `k_pend_area02`, `VFX_IMP_SCREEN_SHAKE` (cutoff 30) | strong and sustained, ~1.6s |
  | 17 | `footstepsounds` rows 5 and 10, both `Stomp` | one short heavy footfall |
  | 20 | Force Choke, Force Push, Force Wave | a shove, no crack |

  **What each one feels like is authored**, and that is the honest limit here:
  BioWare's envelope data went with the Xbox build and cannot be recovered from
  the PC files. The *mapping* is not authored -- each shape is cut to the events
  the sweeps name.

  The table is allocated with the engine's own `operator new` (`0x006FA7E6`),
  because the destructor frees it with the matching `0x006FA390`. The hook now
  also takes `UpdateRumble`'s own `this` from `EBP` and refuses to install
  unless it matches the module's pointer walk, since a table written to the
  wrong object would be handed to `free()` later. **Playtest-confirmed on a
  real pad**: a frag grenade, pattern 14, rumbles.

  *Superseded 2026-09-25:* the shapes above are no longer KMRP's own. BioWare's
  `rumble.2da` turned up, published by the OpenKotOR wiki, and the module now
  installs all 22 of its rows as authored; see *Rumble uses BioWare's own
  patterns* above.

  This also settles which magnitude drives which motor, previously left open:
  `0x005F760F` loads envelope B's maximum into `EAX` and `0x005F7613` loads
  envelope A's into `ECX`, so A is the heavy low-frequency motor and B the light
  high-frequency one -- which is the pairing the shapes were cut for.

### Fixed
- **The D-pad moves through the Powers, Feats and Skills lists.** It could not
  before: the press was swallowed and nothing on those screens moved. Their
  selection is not a focused control at all but a cursor owned by the screen, so
  neither a retained event delivered to a control nor the module's own spatial
  focus layer could reach it. Measured in the clean executable --
  `CSWGuiInGamePowers::HandleInputEvent` serves all eight direction events from
  one arm at `0x006F297B`, which walks a cursor object at `panel+0x19FC`
  (`+0x0C` column, `+0x0D` row, `+0x04` the count) through `0x006CDD80`, then
  stores the resulting selection at `panel+0x19C4` via `0x006F1460`.
  `CSWGuiInGameAbilities` does the same at `0x006AE818`/`0x006AE839`, and
  `SKILLS`, `FEATS` and `MAP` are built the same way.

  Behind the tab strip, `NavigateFocusK1` asked `PanelNavigatesItselfK1` with
  `reachable = false`, which by design drops the panel half of the test and
  leaves only the control half, so the panel was never dispatched to and the
  press fell through to the spatial layer, which sees nothing there because the
  grid is not made of controls. The screen is now handed its own direction event
  directly, and before the focused control rather than after: these screens own
  all four directions and forward to their own description box where that is
  what they mean (`0x006F299E` takes `0x3A` and sends `0x32` to the listbox at
  `+0xFCC`), so a description list holding focus would otherwise swallow up and
  down and leave the grid frozen.

  One deliberate consequence: up no longer climbs back to the tab strip on these
  screens. The grid wraps -- `0x006CDDB8` sets the row to 0 on passing the last
  -- so there is no top edge to detect. LT and RT still change screen, which is
  what the strip was being focused to do. **Playtest-confirmed**: the D-pad
  moves through the Powers, Feats and Skills lists.

### Fixed
- **R3 free look no longer crashes the game.** Raising the input device count so
  the engine polls a pad claimed a device that DirectInput never created, and
  nothing allocated its raw state block. `CExoRawInputInternal::GetLastState`
  indexes that block as `[rawInput+0x30] + (deviceIndex - 2) * 0x74`
  (`0x005E397F`-`0x005E3985`), so with the base null it read address 0. Measured
  under x32dbg on the live game: `0x005E399B`, `mov eax,[eax]` with `eax = 0`,
  called from `CExoInputInternal::GetEvents` at `0x005E2968` with `(2, 0)` — the
  pad's index and `DIJOFS_X`. Free look is what reaches it because vanilla
  registers the analog stick events in `ICPC` and `ICFreeLook` only, and the
  enter handler at `0x006216C7` calls `CExoInput::ClearEvents`, emptying the
  buffered records the pad normally speaks through. The module now allocates the
  block alongside the device count it raises, with the engine's own
  `operator new`, and only when the slot is null so a real DirectInput joystick
  keeps its own. Only two functions in the image index that array —
  `GetJoystickBuffer` at `0x005E31D4`, which the module already declines, and
  `GetLastState` — and a sweep of `0x005E2E00`-`0x005E3A00` finds no store to
  the pointer and no null test on it, so nothing gates on it or frees it.
  **Playtest-confirmed on a real pad**: R3 enters and leaves free look
  without crashing.

  A first attempt detoured `GetLastState` itself and was withdrawn: it sourced
  its parameter from `EAX` while also excluding `EAX` from restore, so the
  re-executed `cmp eax,[0074D3D0]` compared the handler's return value against
  the joystick index instead of the device index. It did not fix the crash and it
  broke controller/keyboard device-activity detection.

### Added
- **Linux/Proton diagnostics and a reproducible Steam Deck procedure.** A new
  case-sensitive package audit checks all 48 resolution archives, 3,889 GUI
  resources, referenced font pairs, archive collisions/paths, and the active
  target-name font chain. A read-only report collector records hashes, manifests,
  resolution, key HUD/font resources, and case collisions without copying game
  content. The Protontricks install/restore workflow and remaining stable,
  Experimental, controller, and hardware matrix are documented without claiming
  unperformed gameplay tests. See `docs/linux-proton-steam-deck.md`.
- **Optional Xbox controller support is now integrated under Advanced Settings.**
  KMRP embeds Saul0097's KPM Xbox Controls K1 1.2 module and a statically linked
  KOTOR Patch Manager runtime, generates a hash-bound seven-detour configuration,
  and uses ownership manifests for safe install and restore. The option is off by
  default and enables the bundled ASI loader when selected. Automated regression
  covers exact hook bytes, TOML structure, foreign-config refusal, rollback, and
  restore; a named-copy Windows launch loaded both modules and showed `E9`
  detours at the original six sites without changing the executable on disk. Physical
  XInput gameplay and Proton/Steam Deck remain untested. Dynamic, original KMRP
  A/B/X badges now appear on ten verified Character, Container, Save/Load, and
  Upgrade action buttons while XInput is connected, and clear on disconnect.
  Normal and highlighted button fills are both covered so focused controller
  navigation does not hide the badge. All 480 resolution-specific
  textures and control mappings are regression-checked. The PC data's retained
  Xbox strings and seven legacy textures remain unused because their console
  mapping conflicts with this module. See `docs/controller-support.md`.
  *Since superseded:* this is the first integration. The component is now KMRP's
  native path -- the pad driving the game's own input pipeline, 18 detours and 4
  byte patches, prompts in four controller families -- and it is on by default
  since 2026-09-24; see the controller entries above.

### Changed
- **Mod-build compatibility now has an explicit supported-input and install-order
  contract.** The exact LAA-only source variant is accepted, K1CP/K1R content
  installs before KMRP, separate UniWS/High Resolution Menus/4 GB steps are
  replaced by KMRP, and KOTORganizer's manual-patch workflow is documented.
  KotOR Patch Manager and another public executable-fix set were audited rather
  than treated as automatically compatible; their remaining hash/restore limits
  are stated in `docs/mod-build-compatibility.md`.

### Fixed
- **Controller button badges now sit next to the button's words, and use the
  words your game actually shows.** The A/B/X badge used to sit at a fixed
  distance from the button's left edge, while the game centres a button's label —
  so on a wide button such as the 978-pixel "Upgrade Items" the badge floated most
  of a screen away from the text it belonged to. It is now placed against the
  measured width of the label, about thirteen pixels to its left, the way the
  original Xbox release drew it.

  Which words those are is no longer guessed. All ten buttons store a `dialog.tlk`
  string reference rather than literal text, and the first version of this
  measured a hand-written list of English labels that was wrong for five of the
  ten: the Container "Cancel" button and both "Back" buttons actually read
  "Close", the save/load button reads "Save" or "Load" rather than always "Load",
  and "Switch To Give Items" is two shorter strings that add up to something
  else. The patcher now reads those references out of your own `dialog.tlk` at
  install time and re-places each badge against the real label, so localised
  installs are measured correctly too. Where a button's wording changes while the
  screen is open — save versus load — it is measured against the wider of the two
  so the text can never overlap the badge. If `dialog.tlk` cannot be read, the
  English placement is used and nothing fails.
- **A controller-support conflict no longer aborts the whole patch.** Every
  reason the optional component could not install -- a `patch_config.toml` owned
  by another KPM mod, a missing ASI loader, or a build without the controller
  resources -- threw `InvalidDataException` out of `ApplyInPlace`. A user who
  happened to have any other KPM mod installed therefore got no fonts, no GUI
  archives and no executable patch either, with a .NET stack trace as the only
  explanation; `dist/KMRP.startup-error.log` recorded exactly that. The ownership
  guard itself was right and is unchanged -- KMRP still never overwrites a file it
  does not own. It now reports and skips, which is how
  `DriverCompatOperations.Install` has always handled the identical case
  ("Left the existing dinput8.dll alone"). Optional components decline; they do
  not take the install down with them.
- **Full-screen movies are no longer cropped on a screen wider than the movie.**
  KOTOR derives its Bink scale from the client *width* alone -- `fdiv` of client
  width by movie width at `0x004057CB`, with height never read -- so at 3440x1440
  a 640x480 logo scaled by 5.375 to 3440x2580 and lost 1140 rows off the top and
  bottom. Gold v24 redirects `0x004057AC` into a `.kmv` stub that takes the
  smaller of the width and height ratios, so every movie is letterboxed or
  pillarboxed rather than cropped, and vanilla and upscaled replacements share
  one policy. Verified by simulation across five client/movie pairs and by
  patching a clean executable end to end; **not yet play-tested**.

  Two failures are recorded rather than quietly fixed. The tool that does this
  existed since 2026-09-05 but was wired into nothing and had an empty expected
  output hash, so it had never been run to completion. And its stub jumped to
  `0x0087703C`, one byte inside the shared `mov [esp+0x14], edi`, which would
  have resumed on `7C 24` -- a `jl` into nothing -- on every movie. The
  displacement is `0x0A`, not `0x0B`; it was caught by disassembling the built
  image rather than the intended assembly, and the builder now checks that every
  internal branch lands on an instruction boundary.
- **Holding a D-pad direction now repeats in menus instead of stepping once.**
  The four directions went through the module's held-key demand set, and that set
  produces exactly one edge per state change, so a held direction moved the
  selection a single row and then sat there. Only the right stick repeated, and
  the upstream source says why: DirectInput reports key transitions only. A
  keyboard does not behave that way -- holding an arrow makes the OS auto-repeat
  and the engine sees a stream of keydowns -- so holding a direction was strictly
  *less* faithful than the keyboard it emulates. The directions are now driven as
  repeating taps through `SendInput`, the same mechanism the right-stick scroll
  already used: the press acts immediately, the next waits 400 ms, and the rest
  follow every 120 ms. Pressing a second direction hands over and restarts the
  delay, and holding two at once does nothing rather than walking diagonally at
  double rate. Reported from play-testing; the repeat rate itself has not been
  play-tested yet.
- **The Character Scripts and Feedback screens are no longer rebuilt from stale
  prototype geometry.** `fix_feedback_list_prototypes.py` rewrote each listbox's
  `PROTOITEM` extent to its parent's content area, on the assumption that those
  coordinates share the parent's space. They do not: upstream ships prototypes
  sitting above and to the left of their own parent (`scriptselect`
  `LST_AIState` parent `TOP=103`, prototype `TOP=84`), which no absolute reading
  explains, and the play-tested 3440x1440 gold files leave every one of them at
  its vanilla value while scaling the parent listbox fully. The rewrite shipped
  and the Character Scripts screen came back broken from play-testing. The pass
  is disabled, both screens now match gold field for field, and
  `Test-GeneratedGuiGeometry.py` asserts these extents equal what upstream ships
  -- the inverse of what it asserted before. The 3840x2160 report that prompted
  the change is unexplained again and needs a different diagnosis.
- **Controller buttons can now skip Bink movies.** KOTOR suspends its ordinary
  input loop during playback, so controller-generated keyboard events were
  never produced. A verified seventh runtime detour polls XInput once per movie
  frame and edge-triggers cancel for A, B, LB, or Start.
- **Controller prompt badges remain visible on focused buttons.** The earlier
  implementation changed only the normal button border, but controller
  navigation selects the separate highlight border immediately. Both empty
  fills now receive the badge while an XInput pad is connected.
- **Controller support no longer hides and parks the Windows mouse cursor on
  startup.** Keyboard/mouse remains immediately available; F9 still toggles the
  optional parked controller-only cursor state.
- **Opening Save/Load with controller prompts active no longer dereferences the
  wrong GUI object.** An unreleased prompt build treated packaged GUI list order
  as the live panel control-array order and crashed in `SetFillImage` at
  `swkotor.exe+0x14C3E`. Runtime prompt assignment now uses the ten verified
  embedded button offsets from the K1 1.0.3 class-layout database. The report,
  matching Windows crash dump, and rejected lookup are recorded in
  `docs/controller-support.md`.
- **Full-screen movies no longer request a separate 640×480 display mode.** Gold
  v23 changes the comparison operands at FILE `0x3D6C` / `0x3D78` and the
  temporary-mode operands at `0x1F5B3B` / `0x1F5B43` to 3440×1440;
  `ResolutionPatch` strictly replaces all four with the selected resolution.
  The Bink renderer itself was confirmed to derive scale and centring from the
  live client rectangle and BIK dimensions, so movie files are not stretched or
  rewritten. A published helper's ambiguous second signature was rejected after
  it matched unrelated instructions. Four output resolutions pass structural
  regression; actual movie playback and minimize/focus transitions remain
  untested. See `reverse-engineering/movies.md`.
- **KMRP now enables Large Address Aware / 4 GB virtual-address support on
  64-bit Windows.** Gold v22 changes only
  `IMAGE_FILE_HEADER.Characteristics` at file `0x926`, from `0x010F` to
  `0x012F`. The exact clean executable with that one bit already set is accepted,
  normalized for deterministic patching, and backed up unchanged; restore
  returns either supported input byte-for-byte. Other executable changes remain
  rejected. `testing/regression/Test-LargeAddressAware.ps1` covers both inputs,
  identical output, an unrelated-header rejection, and both restore paths.
  Memory-heavy gameplay remains untested.
- **The remaining reported 3840×2160 HUD and full-screen layout defects are now
  generated from measured geometry instead of width-scaled upstream defaults.**
  `optfeedback.gui` aligns each embedded row prototype with its scaled parent
  list and scrollbar, restoring the full text pane. `scriptselect.gui` now does
  the same for the Character Scripts list and description pane, whose frame had
  scaled while its content rows remained at 640×480 coordinates. The shared
  `confirm.gui` panel now contains both action rows instead of ending 115 pixels
  before Cancel at the tuning scale. The target name/health strip
  and transient journal, credit, XP, item, stealth, and alignment notifications
  now use the shared height-based UI scale and the play-tested 3440×1440 gold
  proportions. `testing/regression/Test-GeneratedGuiGeometry.py` reads all 48
  packaged archives and verifies the active HUD, both affected prototype pairs,
  and confirmation-child containment.
  The packaged 3840×2160 files were installed and hash-verified. **Tested in
  game at 3840×2160 by the maintainer on 2026-09-28** and reported to look
  right; issue #4 closed that day.
  *Superseded in part:* the prototype rewrite for `optfeedback.gui` and
  `scriptselect.gui` was reverted on 2026-09-06 -- see *The Character Scripts and
  Feedback screens are no longer rebuilt from stale prototype geometry* above --
  and on 2026-09-24 those screens got a scrollbar gutter and centred rows
  instead. The HUD, notification and confirmation parts stand.
- **Windows display scaling no longer applies a second zoom layer to KMRP's
  resolution-aware interface.** In-place installs now add the per-user
  `HIGHDPIAWARE` compatibility flag for the selected `swkotor.exe`. KMRP records
  the exact prior compatibility string in `KMRP_DPI.manifest`; restore puts that
  string back only if the value still equals what KMRP installed, so a later user
  change is never overwritten. Permission failures leave the registry unchanged
  and report the manual Compatibility-tab fallback. The four ownership paths are
  covered by `testing/regression/Test-DpiCompatibility.ps1`. Automated on Windows
  11 build 26200; visual tests at 125%, 150%, 175%, and 200% and Windows 10 remain
  untested.

---

## [2.10.0] — 2026-09-04

First tagged release, and the first public one: **KMRP 1.0**. The tag and the
GitHub release keep the internal number, and its Properties → Details report
2.7.0.0 (see [Unreleased]). `PatchVersion` in
`src/patcher/KmrpPatcher.cs` reads `2.10.0-mapnotes`; gold snapshot
`swkotor_gold_v21_mapnotes.exe`, SHA-256
`9ACE45023EAB9063803136E6C312E5E87DD85E07E33CCB5525C04DCA38C478DC`.

### Added
- **Area map fog now covers the whole map.** The grid was built and normalised
  inside the 1478x720 marker overlay while the map picture was drawn on a
  1720x720 canvas, so 242px down the right showed picture no fog tile ever
  covered. Gold v19 rewrites `0x006944A8` / `0x006944C4` from
  `fdivr [shared constant]` to `fidivr [ebx+0x0C]` / `[ebx+0x10]`, stepping the
  grid by the live rectangle instead of a constant, and gold v21's Option D sizes
  the canvas so the map content fills its frame, `LBL_Map` cropping the surplus
  as vanilla does. See `reverse-engineering/area-map-surface.md`.
- **250 map-note position corrections** from *K1 Area Map Fixes* by Derslok,
  GPL-3.0, used with permission. Only the data is taken; the lookup is KMRP's and
  needs no hook of its own, because the wrapper KMRP already installs at
  `0x0086D000` receives the note's world position as its own first two arguments.
  Optional under Advanced Settings. See `reverse-engineering/map-markers.md` §7.
- **K1 Modern Driver Compatibility 1.2.0** by Synchro, MPL-2.0, bundled with
  permission and installed unless turned off. Two files beside `swkotor.exe`;
  the executable is never touched. Its eight patch sites were checked against
  every byte KMRP writes: 0 of 8 collide, and 8 of 8 still hold the bytes it
  expects. See `docs/third-party-driver-compat.md`.
- **Party Portraits** by MadDerp and the **KOTOR 1 HD Icon Pack 1.0** by
  JackInTheBox, both bundled with permission and not optional.
- **Advanced Settings** in the patcher — a settings view in the same card, with a
  cross-fade, for turning the two optional components off. The choice persists in
  `%LOCALAPPDATA%\KMRP\settings.json`.

### Fixed
- **Map clicks landed 141px right of the pointer** after the map surface moved.
  The hit-test wrapper centred the canvas in the window, but `LBL_Map` is placed
  by the overlay and the canvas overhangs it. Since the overlay is
  `screenWidth // 2`, the inset collapses to `window / 4`: eleven bytes replaced
  by eleven, no relocation. Measured live before and after -- 719, then 860.
- **Hand-tuned 3440x1440 layouts reached only 17 GUI files.** The transfer was an
  allow-list and had drifted, so 23 tuned files -- `abilities.gui`, `store.gui`,
  every options screen -- shipped upstream's extents at every other resolution and
  their text ran to the edge of the artwork. The set is now derived from which
  files actually differ, covering 39.
- **A gap between the map and its frame.** The frame's opening measured 726 rows
  against a 720-row map. `tools/fit_map_frame_art.py` moves the top edge down 5
  and the bottom up 1, touching only the frame's own columns.
- **Bundled artwork no longer overwrites another mod's files.** A bundled file
  already in `Override` that KMRP's manifest does not claim is skipped, so K1CP's
  `ia_class8_004.tga` and `ia_class9_003.tga` survive. Scoped to the bundled art;
  KMRP's own files install as always.

  executable in place.** `IsVerifiedPatchedInstall` called an install patched
  whenever the sidecar's `patchedSha256` matched the file on disk, which proves
  only that nothing edited the executable since — not that those bytes came from
  the current build. `--in-place` therefore exited 0, rewrote the sidecar, and
  skipped the executable: reinstalling over gold v19b left `0x006944A8` still
  reading `fdivr dword ptr [0x008750A0]` instead of the new
  `fidivr dword ptr [ebx+0x0C]`. The Gold branch of `ApplyInPlace` now rebuilds
  the expected bytes from the verified clean backup and compares; anything else
  is restored and re-applied. The sidecar also records `goldTargetSha256`, the
  gold hash of the build that patched the install, which is what the check falls
  back to when no backup is available. Reusing the same `PatchVersion` string
  made the old behaviour easier to hit but was never the cause. Covered by
  `testing/regression/Test-ReinstallOverOlderBuild.ps1`.
- **Area map markers no longer shrink as the map grows.** Map note, party and
  player-arrow rectangles were built from vanilla immediates while the marker
  overlay scaled with the screen, so at 3440x1440 they were 3.4x smaller
  relative to the map than in vanilla. **Fourteen** sites now scale by
  `max(1, height/720)`, giving 2x markers at 1440p: four sizes, eight centring
  offsets and two control extents. A map note has separate selected and
  unselected draw paths, and `mm_barrow` and `lbl_mapcircle` each carry their own
  control extent — the first two attempts scaled only some of them. Gold v18.
  See `reverse-engineering/map-markers.md`.

### Documentation
- Repository documentation set: `LICENSE` (GPL-3.0), `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, this changelog, issue and pull request
  templates, a continuous integration workflow, `.gitattributes`, and indexes
  for `docs/` and `reverse-engineering/`.
- **A byte-level audit of the patched executable.** At the time this entry was
  written, `reverse-engineering/binary-inventory.md` called a merged 893-byte
  presentation span “changed bytes.” That wording was corrected on 2026-09-05:
  the current inventory counts actual unequal byte positions separately from
  the readable merged spans and ties every run to the document explaining it;
  `tools/build_binary_inventory.py` regenerates it and exits non-zero if any run
  has no write-up. Its first run found six patch sites that were implemented and
  explained in build scripts but had never reached a document — including the
  reference build's baked-in 3440x1440 constants and the two guards that were
  blanking stack counts. Those six are now written up.
- A plain-language summary of every executable change, above, so the patch can be
  understood without reading the version history.

### Changed
- `README.md` rewritten for people who have not seen the project before:
  what it is, how to install and undo it, what it fixes, and how it works.

---

## [2.7.0] — 2026-09-02

Gold snapshot `swkotor_gold_v15_popup.exe`
(`79356D1A92637C1B5C619B530FDA742A622A330E19AD628DBA19464202425048`).

### Added
- Shared message popup (tutorial hints and confirmations) rebuilt: auto-fit
  height stop, width cap and icon rect raised in the executable, with the
  `confirm.gui` layout generated per resolution from a play-tested table.
- Thirteen tutorial icons shipped at the popup's icon size per resolution, with
  `tutorial.2da` repointed at private copies so the eight shared source
  textures keep their existing sizes everywhere else.

### Fixed
- **Message text clipped mid-word.** The auto-fit loop widens the popup only
  while it is narrower than a cap authored for 640×480, so at any HD size the
  loop never ran.
- **The patcher could not install over an existing installation.** Four places
  assumed every install was a first install, so no build could ship a changed or
  added Override file without a full restore first; three of them reported it as
  a resolution mismatch. An interrupted install could also leave a backup file
  that permanently blocked retries.
- Tutorial icons were written upside down, and were generated from KMRP's own
  scaled output rather than the stock texture pack.

### Changed
- Patcher executable now carries version information (product, description,
  version, copyright) instead of a blank description and `0.0.0.0`.

## [2.6.0] — 2026-09-02

Gold snapshot `swkotor_gold_v14_minimap.exe`
(`1F1684A5DC8BC440B2C8FF0194873315EDD39DE1C1039CB2E73861A4B3732504`).

### Fixed
- **HUD minimap content was not zoomed to the player** at resolutions the engine
  did not recognise, and the fog-of-war grid did not match the zoomed map.
  Added as the `.kmz` and `.kfg` sections.

## [2.5.0] — 2026-08-31

### Fixed
- **Item stack-count numbers disappeared** once the font was enlarged. The label
  is built in the inventory row's `SetRect` rather than any `.gui`, and is
  bottom-right-aligned inside the icon box, so scaling the icon left it behind.
  Three of its four constants were `imm8` operands capped at 127, so the
  arithmetic was relocated into a `.ksc` stub with `imm32` operands.

## [2.4.0] — 2026-08-31

### Fixed
- **List rows grew every time a list was repopulated** — a vanilla BioWare bug,
  reproduced with a `.gui` byte-identical to the original. Invisible at low
  resolution because growth is clamped by box height; measured ratcheting
  42 → 56 → 126 on the Powers tab with a larger box.

## [2.3.0] — 2026-08-31

### Fixed
- Inventory, Abilities and Store rows and icons stayed vanilla-sized, being
  driven by hardcoded constants no `.gui` edit can reach.

## [2.1.0] — 2026-08-30

### Fixed
- **Inventory crash** on items with long descriptions. The line-breaker's only
  guard compared against the start of the string rather than the current line,
  so an unbreakable line looped until the allocator failed.

## [2.0.0] — 2026-08-29

### Added
- First universal release: one patcher covering **48 resolutions** across 4:3,
  16:10, 16:9, 21:9 and 32:9, replacing the earlier 3440×1440-only gold patcher.
- Resolution-aware font scaling (`max(1.0, height / 720)`) carried on the font
  atlases' TXI metrics, list-row scaling, and a height-derived dialogue
  letterbox.
- Verified backup and restore for the executable, INI and Override folder.

[Unreleased]: https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/compare/v2.10.0...HEAD
[2.10.0]: https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/releases/tag/v2.10.0
