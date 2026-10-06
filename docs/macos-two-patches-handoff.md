# macOS handoff: KMRP and the controller as two patches, and the Windows work of 2026-10-05 and 06

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it -- measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: handoff.** Written on Windows on 2026-10-06 for whoever does the Mac side
next. It says what changed in KMRP on Windows in the session of 2026-10-05 and 06,
why, and what the Mac build has to take over. Nothing in it was built or run on a
Mac: every statement about the Mac is read from this repository's Mac files that
day, and says so, or is work still to do.

The tracker, [`macos-changes-from-windows.md`](macos-changes-from-windows.md), keeps
the item-by-item record (items 20 to 29 are this session). This document is the one
to read first. The earlier handoff,
[`macos-standalone-kpatch-handoff.md`](macos-standalone-kpatch-handoff.md), still
holds for everything it says about one self-contained patch with options; section 2
here changes one thing in it, the controller.

## 1. What changed, and what each means for the Mac

| # | Change on Windows | Where | The Mac |
| --- | --- | --- | --- |
| 2 | KMRP and the controller are two patches, each working without the other | `tools/build_native_kpatch.py`, `tools/build_controller_kpatch.py`, `src/patcher/KpmEdition.cs`, `K1NativeJoystick.cpp`, `K1ControllerStandalone.cpp` | **to do**: the Mac's `kmrp` patch still contains the controller (section 2) |
| 3 | The font sets carry `spacingR 0`: text no longer runs over the right edge of its box | `tools/prepare_universal_resources.py` | **build and check**: shared resources (section 3) |
| 4 | The installer's wording for a game KOTOR Patch Manager manages | `src/patcher/KmrpPatcher.cs`, `KpmEdition.cs` | **to do**: one line in `macos/installer-app/main.m` (section 4) |
| 5 | The marker on a target is missing over half the screen at 3440x1440: found, **not fixed** | `assets/override-3440x1440/mipc210x7.gui` | **check** which HUD file the Mac loads; the fix is owed on both (section 5) |
| 6 | Four pictures added to the glyph pack, one new glyph name | `third_party/Included/Xelu_Free_Controller&Key_Prompts/`, `tools/build_controller_prompt_textures.py` | **build and check**: the build fails without the files (section 6) |
| 7 | The controller patch lays itself out on any interface; Level Up and Auto Level Up; the pause notice and the target's circle in the Xbox-style HUD | `vendor/K1XboxControls.cpp`, `K1XboxHud.cpp` | **nothing to do** while the Mac has no standalone controller patch; two things to look at in the Mac's own controller (section 7) |
| 8 | The Windows bank left out what the helper makes; the Xbox-style HUD's frames drawn | tracker items 20 and 21 | **nothing to do** (section 8) |
| 10 | The list rows' centring is on Windows too, with two differences from the Mac's: a chart row's inset is 0, and the store's and the workbench's rows are set in from both borders | `src/controller-native/K1RuntimeLayout.cpp`, `K1ListRows.inc`, `kotor1-native-runtime.hooks.toml` | **decide** whether the Mac takes the two differences (section 10) |
| 11 | The store has controller badges: A, X and B | `tools/build_controller_prompt_textures.py`, `vendor/K1XboxControls.cpp` | **to do** in the Mac's controller: the store's three buttons (section 11) |

## 2. KMRP and the controller are two patches

### What was decided

| When | The maintainer | Meaning |
| --- | --- | --- |
| 2026-10-05 | "we should have the K patch from KMRP, and the controller mod" | KMRP ships two `.kpatch` files; KMRP's own has no controller in it |
| 2026-10-05 | "put the controller support mod in the advanced settings, and when it's off, we just don't put the controller K patch in the game" | the installer's Controller Support switch decides whether the second patch is installed |
| 2026-10-05 | "in the two variant option after having only KMRP in the KPM app can we later just also install the controller mode separately and it would work"; "this makes both basically independent right?" | neither patch may need the other: the controller patch can be added to a game that has KMRP, or taken away, in the installer or in KOTOR Patch Manager |
| 2026-10-06 | "the controller mod should auto scale to any arbitrary GUI that is there. It shouldn't rely on any other resources"; "with Jay's mod for the widescreen with KMRP with vanilla with any GUI mod in the future" | beside KMRP the controller patch draws from its own files and fits them at run time; it takes nothing of KMRP's (section 7) |

### What Windows is now

| | `KMRP.kpatch`, id `kmrp` | `KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`, id `kmrp-controller` |
| --- | --- | --- |
| Hooks | 24 | 34 |
| Requires | nothing | nothing; does not list `kmrp` as a conflict |
| Options | `map-notes`, `debug-logs` | `xbox-hud` (off unless chosen), `debug-logs` |
| Options file | `configs\kmrp.ini` | `configs\kmrp-controller.ini` |
| Installed by the installer | always | while Controller Support is on in Advanced Settings |

KOTOR Patch Manager allows one patch per hook address, and on Windows both patches
work in the GUI frame, the movie frame and the first resource lookup. So each has a
site of its own in each of the three:

| | The controller patch | KMRP |
| --- | --- | --- |
| GUI frame | `0x0040CE70` | `0x0040CE76`, the next instruction: `KmrpCoreGuiWorkK1` |
| Movie frame | `0x00404D96` | `0x00404D06`, earlier in the same loop: `KmrpCoreMovieWorkK1` |
| Resource lookup | `0x00407235` | `0x00407230` |

These are addresses of the Windows executable. What carries over is the rule, not
the numbers.

Beside KMRP (its module is loaded: `KmrpIsBesideK1`), the controller patch:

- leaves the cursor's confinement to KMRP, which knows the sizes it adds;
- deletes its own copies of the game's layouts from its temporary folder before it
  registers the folder, so that KMRP's layouts load. KMRP's layouts already hold
  the controls the controller patch adds to the game's own (the same tags, from
  the same build step);
- keeps drawing its own badge art, which is made for the game's own layouts, and
  fits it to KMRP's buttons at run time (section 7).

KMRP's sets still carry badge textures of the same names, made for KMRP's buttons.
They are not used in the pair; taking them out of KMRP's bank is open work on
Windows.

### What the Mac is today

Read from `macos/build.sh`, `macos/README.md` and `macos/patches/` on 2026-10-06:

- One KOTOR Patch Manager patch, id `kmrp`, built by `tools/make_kmrp_patch.py`
  from FTD's two patches and KMRP's `patches/kmrp-layout`, `kmrp-map-notes` and
  `kmrp-controller`, in four variants (`kmrp`, `kmrp.no-map-notes`,
  `kmrp.no-controller`, `kmrp.no-map-notes.no-controller`).
- `patches/kmrp-controller/` is a port of the Windows controller with sources of
  its own (`cues.cpp`, `prompts.cpp`, `hud.cpp`, `pad.mm` and others); it does not
  compile `src/controller-native/`. It has a `manifest.toml` of its own, id
  `kmrp-controller`.
- The three folders' hook tables have no address in common (compared that day:
  26, 18 and 1 hooks). `patches/kmrp-layout/without-controller/` holds a second
  hooks file for the layout, so the layout's hooks depend on whether the
  controller is there.
- The controller's art goes into `Assets/override` at install.

### What the Mac needs

Not started. In the order it would be done:

1. **Decide the Mac's shape.** To match Windows, `kmrp` is built without the
   controller and `patches/kmrp-controller/` becomes a patch of its own that the
   installer adds when the controller is wanted. Tracker item 17 lists what a
   standalone Mac controller patch needs (a dylib of its own, its files unpacked by
   the dylib, the Mac hooks file in the package).
2. **One patch per address.** The hook tables share no address today, which is the
   condition. Check it again after the split, and check what
   `kmrp-layout/without-controller/` changes: on Windows the two patches turned out
   to share three places only once they were separate.
3. **Whatever KMRP did for the controller's frame stays KMRP's.** On Windows KMRP's
   frame work (the resolution sampled, the cursor kept to the picture, the status
   summary laid out, the movie window) had been called from the controller's hooks
   and needed sites of its own. Look for the same on the Mac: anything in
   `kmrp-layout` that runs only because the controller's hook calls it.
4. **Beside KMRP, the controller patch loads KMRP's layouts.** If the Mac's
   controller patch brings layouts of its own for a game without KMRP, it must
   step aside for KMRP's, as the Windows one does.
5. **The installer.** Controller Support decides whether the second patch is
   installed; each patch has its own options file.

### Tested on Windows

- Installed by the installer on the maintainer's Steam test copy at 3440x1440
  (2026-10-05 and 06) and played by him there and in scratch copies at 1920x1080
  and 3440x1440: menus, the HUD in both styles, movies, pausing.
- The controller patch alone on the unchanged game, and beside Scaled Kotor 1.3.1
  at 3440x1440, pad driven in scratch copies (2026-10-06).
- `Test-KpatchSource.py`, `Test-ControllerKpatch.py`,
  `Test-ControllerPromptAssets.py`, `Test-InstallerPatch.ps1` pass.
- Not run: KMRP alone beyond its menus and speech lines, a fight, sizes other than
  those three, `Test-ReinstallOverOlderBuild.ps1`, `tools/check_kpm_overlaps.py`.

## 3. The font sets carry `spacingR 0`

**What was wrong.** At 1920x1080 lines of speech ran over the right edge of the
speech box. The maintainer first took it for a fault of the split; three recordings
(the pair, KMRP alone, KMRP built before the split) showed it in all three.

**The cause.** KMRP gave every font `spacingR 0.005`, half a pixel, as a margin for
the engine's line breaker. On Windows the engine uses the value in both passes:

| Pass | What it does with `spacingR` |
| --- | --- |
| The line breaker (`0x0045A2F0`) | trunc((u width x `texturewidth` + `spacingR`) x scale x 100 + 0.25) a glyph |
| `Draw` (`0x0045A850`, the pen at `0x0045AF6F`) | the glyph's width plus `spacingR`, not truncated |

Every font set is baked at its own scale and its glyphs are whole pixels wide (all
720 atlases under `build/fonts`). With a width n and half a pixel the breaker
counts trunc(n + 0.75), which is n. So the margin widened every drawn line and no
measured one. In the scratch copy the same line, stored by the breaker as 763 px,
drew 786 px with the value and 762 px with it set to 0 in memory.

**Corrected in passing.** `reverse-engineering/font-atlases.md` said the renderer
did not read `spacingR`; the site it named, `0x0045A806`, is the breaker seeding a
new line. Its section is rewritten.

**The change.** `LETTER_SPACING_PX = 0.0` for a set baked at its own scale, which is
every set a release ships. `Test-ControllerPromptAssets.py` accepts a spacing of 0.
All text is drawn about 3% narrower than in 1.4.

**For the Mac** (tracker item 22):

1. The resources are shared: a Mac build from this code gets `spacingR 0`.
2. `macos/README.md` lists K6, "0.5 px wrap margin", as a TXI fix. It is no longer
   applied; correct the row.
3. The Mac's engine was not read for this. Check a long speech line and a long
   item description: if the Mac's line breaker and renderer agree without the
   margin, as Windows' do, nothing more is needed; if lines are cut, the Mac's
   breaker differs and the finding belongs in the tracker.
4. `kmrp-guiblend.c` and the status summary's measure read `spacingR` from the
   font and follow by themselves.

## 4. The installer's wording for a game KOTOR Patch Manager manages

The maintainer asked for the "install for KPM" type to go; there was no switch for
it left (removed 2026-09-30), only the automatic case, which he chose to keep with
wording that does not call it a type of install. Windows now says:

| Where | Text |
| --- | --- |
| The window's fourth row (`KmrpPatcher.cs`) | "Managed by KOTOR Patch Manager: tick KMRP there, then Apply and Launch." |
| The folder's description (`KpmEdition.cs`) | "KMRP is installed. KOTOR Patch Manager manages this game and loads KMRP's patch." |
| The install log | "... is in the game folder: KOTOR Patch Manager manages this game, so KMRP adds its patch there and leaves the game's files to it." |
| The install log's last line | "KMRP's patch is ready in KOTOR Patch Manager. swkotor.exe was not modified." |

The row's first wording that day was a sentence longer and was cut off in the
window (seen in a screenshot of the installer on a stand-in folder); a row holds
one line.

**For the Mac:** `macos/installer-app/main.m` has "KotOR Patch Manager manages this
game. KMRP is installed for it." (line 1594 that day). Bring it in line, and check
it fits its row.

## 5. Open: the marker on a target at 3440x1440

Found on 2026-10-06, not fixed. The engine draws the marker on a target as a
circle only while the target's point on screen is inside the rectangle of
`LBL_ARROW_MARGIN`, and as an arrow on that rectangle's edge otherwise
(`CSWGuiMainInterface::UpdateIndicator`, `0x0068A310`). The rectangle in KMRP's HUD
for 3440x1440 is not scaled:

| File | `LBL_ARROW_MARGIN` |
| --- | --- |
| the game's `mipc210x7.gui` (1024x768) | 3, 129, 1018, 501 |
| `assets/override-3440x1440/mipc210x7.gui`, which that size loads | 3, 129, 2554, 501 |
| KMRP's `mipc28x6.gui` in the same set, for comparison | 13, 310, 3414, 799 |

So at 3440x1440 a target below 630 or right of 2557 gets the arrow, standing on
its head, and no circle. The Xbox-style HUD of the controller patch sets the
rectangle itself while it is up (section 7); KMRP with the PC's HUD has the fault.

**For the Mac:** find which HUD file the Mac loads at its sizes and read its
`LBL_ARROW_MARGIN`. If it comes from the same gold file, it has the same fault.
The correction belongs in the gold file and needs a full resource build; it is the
maintainer's to schedule.

## 6. The glyph pack

The maintainer added four pictures of Xelu's to
`third_party/Included/Xelu_Free_Controller&Key_Prompts/` on 2026-10-06:
`Xbox/360_RT_ALT.png`, `Xbox/360_LT_ALT.png`, `PS5/PS5_R2_Light.png`,
`PS5/PS5_L2_Light.png`. `GLYPH_FAMILIES` in
`tools/build_controller_prompt_textures.py` has one new name, `RT_NOTICE`, in all
four families: `360_RT_ALT`, `PS5_R2_Light`, and the pack's `Switch_RT` and
`SteamDeck_R2`. Only the controller patch's assets use it
(`tools/build_controller_assets.py`, the texture `kmr?rt_pause`). The two LT
pictures are not used yet.

**For the Mac:** the table is shared with KMRP's resource build, and a glyph whose
file is missing stops it. The four files have to be in the checkout (they were
untracked when this was written). Nothing else changes for the Mac's art.

## 7. The controller patch on any interface

All of this is the Windows standalone controller patch
([`controller-standalone.md`](controller-standalone.md), "Beside a patch that
rescales the interface"; [`controller-xbox-hud.md`](controller-xbox-hud.md), "The
pause notice and the target's circle"). The Mac has no such patch (tracker item
17), and its controller is a port with its own sources, so none of it is code the
Mac compiles. It is here for two reasons: the rule, and two things worth looking at
in the Mac's own controller.

**The rule** (the maintainer, 2026-10-06): the controller patch fits itself to
whatever interface is loaded, the game's, a widescreen patch's, KMRP's or a later
one's, from what it measures in the running game, and takes nothing from another
patch; a badge's width and height never change apart. A first attempt that night
had the patch use KMRP's fitted badge textures when KMRP was loaded. It made the
screens right and he rejected it within minutes.

**What that took on Windows:**

| Seen beside KMRP at 3440x1440 | Cause | Now |
| --- | --- | --- |
| The X of Inventory's "Show ..." button an oval | a badge with one texture per caption found no row in the shape table, so the shape guard was skipped | the lookup takes a name less its last digit |
| The A of an Options row about 90 px from its caption | the caption was measured by asking the line breaker for heights, and KMRP changes the line breaker | the width is summed from the caption's own font, as `Draw` sums it |
| An A beside Equip's empty button | a badge on a label of its own did not follow its hidden button | checked every frame: drawn only while its button is, placed again when the caption changes |
| The party cue against the left portrait | moved by a fixed share of its size from where the layout file has it | placed from the live portraits |
| Level Up and Auto Level Up: a dot and a smear (in the unchanged game too) | the badge was the button's box with the glyph on it, stretched over the strip a 16-unit border leaves | the box stays on the button; a plain badge on a label; the buttons grow to hold badge and caption |
| A paused game said nothing (Xbox-style HUD) | the game places its pause notice under a button this HUD parks | left of the minimap, one line with the pad's right trigger in it; the game's own box again with the mouse |
| An arrow on the target's head, no circle (Xbox-style HUD) | section 5 | the rectangle set from this HUD's own parts while it is up |
| The circle a dot (Xbox-style HUD) | the engine sizes it 16 to 64 pixels whatever the screen | scaled by the screen's height over 480 |

**Two things to look at on the Mac**, in KMRP's own controller:

1. **Level Up and Auto Level Up.** On Windows the fault was in the unchanged game
   as well, and was seen only once a save had a level to take. Open the Character
   screen on the Mac with a level to take and look at the two badges. KMRP's sets
   make these badges for KMRP's own, larger buttons, so they may be right; they
   were not looked at in KMRP alone on Windows either.
2. **Captions measured through the line breaker.** If the Mac's controller measures
   a caption by wrapping it at trial widths, it has the weakness the Windows patch
   had beside KMRP.

## 8. Already in the tracker, nothing for the Mac

- **The Windows bank leaves out what the blend helper makes** (2026-10-05, tracker
  item 20): `KMRP.kpatch` 249 MB to 129 MB. The bank is the Windows module's alone.
- **The Xbox-style HUD's frames are drawings** and its portraits are framed by the
  module (tracker item 21); a slot's picture is centred on its box. Controller
  patch only.

## 9. The state of the repository when this was written

- Branch `kmrp-two-patches`, ahead of `master`. Its first two commits are `2b47b42`
  and `816ee48`; everything in sections 2 to 7, 10 and 11 was committed after them on
  2026-10-06 in one commit, with the four pictures of section 6, and the branch was
  pushed that night. It is not merged into `master`.
- `README.md` and `docs/kpm-edition.md` were brought up to the two patches on
  2026-10-06 (`kpm-edition.md` by a section at its head; its numbered sections still
  read as they did). `CHANGELOG.md`, `controller-standalone.md` and
  `controller-xbox-hud.md` are current.
- The installer built from that tree: `dist\KMRP - KOTOR Modern Restoration
  Patch.exe`, SHA-256 `C5BDE472...EBF05FFC`, holding `KMRP.kpatch` `4B0E818E...` and
  the controller patch `1EA6A0D0...`.

## 10. The list rows' centring, on Windows too

The Mac's item 19 of `windows-changes-from-macos.md` (its commits `40b96fa` and
`3e0cc2b`) was brought to Windows on 2026-10-06, at the maintainer's request after he
saw the Mac's rows: the same table, copied (`src/controller-native/K1ListRows.inc`,
which `Test-KpatchSource.py` compares with `macos/patches/kmrp-assets/list_rows.inc`
when both are in the tree), the same logic, and three detours in
`CSWGuiListBox::OrganizeControls`. The whole of it is in
[`reverse-engineering/listbox-geometry.md`](../reverse-engineering/listbox-geometry.md),
"Rows centred in their box", and in the tracker's section 28.

Counted at 3440x1440 on screenshots of the maintainer's run, dark columns left and
right of the rows: the inventory 7 and 7 (19 and 12 before), the journal 5 and 6, the
store 0 and 1, the powers' chart 11 and 7. Two things then differ from the Mac, and
both are for the Mac to look at:

1. **A chart row's inset is 0 on Windows**, not the Mac's `-1.47 * scale`: the game
   places the row's three pictures symmetrically in its rectangle
   (`CSWGuiSkillFlow::SetExtent`, `0x006CCE30`). If the Mac's routine is the same
   code, the Mac's chart stands that much right of centre; a count on a Mac
   screenshot at the pictures' dark edge would say.
2. **The store's and the workbench's rows are set in from both borders** by
   `round(3.5 * scale)` pixels (`kRowGap`), because centred they touched both borders
   of their box and the maintainer asked for a gap.

Neither had been seen in the game when this was written; the build holding them was
installed in the maintainer's Steam game that night. Not brought to Windows: the
abilities' row height after a resolution change (`3e0cc2b`).

## 11. The store's controller badges

The store screen had no badge on any platform's list. Windows' controller patch now
shows A on Buy or Sell, X on Show Sell List or Show Buy List and B on Close; the three
targets are in the shared `tools/build_controller_prompt_textures.py`
(`kmrpa_storebuy`, `kmrpx_storelist`, `kmrpb_storeback`), so the shared resource build
makes their textures for every menu set. For the Mac's own controller: a table for the
store panel with its three buttons' offsets in the Mac's build, as the tracker's
section 29 lays out. Not seen in the game when this was written.
