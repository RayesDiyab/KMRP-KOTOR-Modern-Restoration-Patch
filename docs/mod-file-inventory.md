# Vanilla file inventory: every game file KMRP edits or replaces

**Reference** (the [documentation standard](documentation-standard.md)). One row for each
of the game's own files that KMRP edits or replaces, what KMRP changes, and what happens
when a mod's copy of the same file is in `Override`. Files KMRP adds under names of its
own (its modules, `kmrplayout.gui`, the tutorial popup's `tut_*` icons, the
`kmrx_*` and `kmr*` drawn textures, `kmrp_prompts.txt`) replace nothing and are not
listed. Issue 79's work; built 2026-10-31. Live Adaptive Layout's own table is in
[`live-adaptive-layout.md`](live-adaptive-layout.md#coverage-inventory).

## The rule

The maintainer's rules (2026-10-31):

1. Whenever a game file KMRP edits or replaces is also in the player's `Override`, KMRP
   starts from the mod's copy and changes only what it needs.
2. **Structured resources get a true three-way merge, with vanilla as the common base.**
3. **Textures and models get a strategy of their own per format**, with a safe fallback,
   because a field-by-field merge of a picture or a mesh often means nothing.
4. Where the mod and KMRP changed the same thing, **the mod wins**.
5. Where the mod's win switches off a KMRP feature, the log names the file and the feature
   that is off. KMRP never reports a file as fully compatible when part of its feature is
   lost.
6. Nothing is decided by a file's name: the format decides the strategy. A new resource
   KMRP starts to change uses the same strategies without new merge code.

Two mods that put a file of the same name in `Override` overwrite each other when they
are installed; that is the player's to sort out, not KMRP's.

## How it works (built 2026-10-31)

Three copies of every resource:

| Copy | Where it comes from |
| --- | --- |
| **Vanilla** (the base) | the game's own file, through `chitin.key` (`KmrpReadKeyedResource`, `kmrp-guiadapt.c`) or the texture pack |
| **KMRP** | vanilla with KMRP's change made, exactly as KMRP makes it without the mod (the set's file) |
| **Mod** | the player's file in `Override`, only ever read |

KMRP's own output is never used as vanilla or as the mod's copy.

### Which strategy, by format

| Format | Strategy | Code | When it cannot run |
| --- | --- | --- | --- |
| `.2da` (binary `V2.b` and text `V2.0`) | three-way merge of cells | `macos/tools/kmrp-2da.h`, `kmrp-merge.c` (`KmrpMerge2da`) | the mod's file is not a table, its key column is gone, or the merge would move a row: the mod's table as it is, and the lost changes named |
| `.gui` | Live Adaptive Layout on the mod's file: geometry carried through KMRP's transformation, the other fields three ways | `kmrp-guiadapt.c` (`ll_layout`, `ll_canvas`); [`live-adaptive-layout.md`](live-adaptive-layout.md) | its canvas cannot be identified: the mod's file as it is, and the screen not laid out |
| `.tga`, `.tpc` made from a game picture | KMRP's transform run on the mod's picture | `kmrp-gameart.c` (`KmrpDeriveImage`) | the picture cannot be decoded: the mod's as it is, and KMRP's copy named as off |
| `.tga`, `.tpc`, `.txi` KMRP replaces with its own art, and its fonts | the mod's picture wins whole | `K1RuntimeAssets.cpp` (`LinkSet`, `LinkArtwork`) | always; a count line, as the picture is the mod's choice |
| `.mdl` (with its `.mdx`) | KMRP's change made where the part it changes is still the game's | `kmrp-swoophud.c` (`KmrpSwoopHudModel`) | the part differs: the mod's model as it is, and the fix named as off |
| a font a mod supplies | the mod's font, read with its own metrics; KMRP's layout is measured with it | `K1RuntimeAssets.cpp` (`OverrideFont`, `overrideFontHeights`) | none |
| `swkotor.exe` code | no merge, ever. KPM checks the original bytes of every hook site before it writes (`Trampoline::VerifyBytes`, KPM 0.7.1 `patcher.cpp`), so another patcher's change on a KMRP site stops that hook with "Original bytes mismatch at hookAddress" in KPM's log | KPM | always reported, never merged |
| any other format | the mod's file as it is | `DeriveFromOverrideK1` | logged where a KMRP record names one |

### The run time (`DeriveFromOverrideK1`, `K1RuntimeAssets.cpp`)

Each size's set holds `kmrp_derive.txt`, written by the tools as they make the set
(`kmrp-gameart.c`, `kmrp-abilityicons.c`, `kmrp-swoophud.c`), one line for each file KMRP
generates from a game resource:

```
OUTPUT \t SOURCE                                              a table or a model
OUTPUT \t SOURCE \t CANVAS \t PICTURE \t LEFT \t BOTTOM \t FILTER   a picture
```

`SOURCE` is the game resource `OUTPUT` is made from. A picture is `SOURCE` drawn
`PICTURE` x `PICTURE` at `LEFT`, `BOTTOM` on a transparent `CANVAS` x `CANVAS`, `nearest`
where `PICTURE` is a whole multiple of a square source, else `linear`. Each time a size's
folders are made (every start, every change of size), every line whose `SOURCE` the
player's `Override` has is made again from the mod's copy, by `OUTPUT`'s format, into the
run's folder that the game searches before `Override` and the set. Every file is written
under a temporary name and moved into place, never written through a name already there,
as the run's folders hold hard links into the cache.

**Never stale.** Nothing derived from a mod's file is kept between runs: it is made from
`Override` as it is at that start, at that size, by this build. What the set itself holds
(KMRP's side) is stamped with the build, the texture pack and `chitin.key`, as before, and
`art 3` since 2026-10-31, so sets made before the record existed are made again. The game
lists `Override` once a run, and so does KMRP: a file changed while the game runs is seen
at the next start. Not measured: the time this takes at a start with many mod files.

**Safe.** `Override` is only read; every output goes into KMRP's runtime folders
(`%LOCALAPPDATA%\KMRP\cache\<build>\`), which restore removes (`RemoveArtCache`, as
before). Every mod file a test gives is checked byte for byte before and after.

### The 2DA merge (`kmrp-2da.h`)

| Vanilla vs KMRP | Vanilla vs mod | Result | Logged |
| --- | --- | --- | --- |
| same | any | the mod's | no |
| changed | same | KMRP's | no |
| changed | changed to KMRP's value | that value | no |
| changed | changed differently | **the mod's** | yes: the row, the column and all three values |
| changed | the mod has no such row or column | the mod's table without it | yes: KMRP's change lost |

**Rows are found by identity, chosen from vanilla's table alone**, never from its name:

1. a column called `label` whose every row has a value and none repeats;
2. else the first column like that;
3. else the row labels, when they are names (not 0, 1, 2 ...) and none repeats;
4. else the row number. A row matched by number is taken for vanilla's only where at
   least half of its shared cells are still vanilla's, so a row the mod put in between is
   never taken for the one it pushed down.

A key the mod's table repeats or leaves empty is ambiguous: those rows are left as the
mod has them, and named. Columns are found by name, without regard to case, wherever they
stand; one the mod's table has twice is left alone.

**A row's name and its number do two different jobs.**

| | Its job | Who decides it |
| --- | --- | --- |
| the name (`label`) | tells KMRP which vanilla row a row of the mod's is, so KMRP's change goes to the right one | used only while merging |
| the number (its place) | how the game and every script find the row while playing: `ShowTutorialWindow(nWindow)` takes the row's number (`ExecuteCommandShowTutorialWindow`, `vm_commands_late.cpp` in `swkotor1-reconstruction`), and the game keeps its tutorial flags by number (`CClientExoApp`, `client_exo_app_r5.cpp`) | the mod's file, always |

So the merged table is the mod's table: its rows in its order at its numbers, its row
labels, its columns in its order, its format (a text table stays text, its `DEFAULT:` line
kept) and every cell KMRP does not change. KMRP only changes cells inside rows, and the
merge refuses itself if a row label would end up at another number. A vanilla row the mod
moved to another number is noted ("vanilla's row Enter_Map_Screen (row 13) is row 14 in
the mod's table; scripts asking for row 13 get the mod's row there"), never renumbered. A
row or column KMRP adds (none does today) would go after the mod's last.

Measured on 2026-10-31 with the game's `tutorial.2da`, KMRP's copy and a mod copy with a
row put in at row 5 and one icon of its own: KMRP's sharp icon went into the 19 rows the
mod left as vanilla's, the mod's icon was kept and noted as a conflict, the mod's row kept
its place, 44 rows as the mod has. The table KMRP writes through `kmrp-2da.h` is
byte-identical to the one it wrote before (the 3440x1440 set's).

### Layouts

Set out in [`live-adaptive-layout.md`](live-adaptive-layout.md), section 3: a moved
control keeps the mod's move on KMRP's place (`K(vanilla) + round(R(mod) - R(vanilla))`),
a line-up the mod made stays one, and a file already scaled follows the maintainer's three
rules: exactly as made at its own size; at another size KMRP's calibration once for a
control only scaled from the game's, the file's own placing converted for any other; and
where that is ambiguous the mod's placing wins and the skipped calibration is reported.
The other fields of a control (alignment, fill, border art and thickness, padding) take
gold's value only where the mod's file still has the game's.

### Stable identities

**Found by name, never by position** (the maintainer, 2026-10-31). A mod's file can be any
size, can have rows, columns, fields, controls or nodes put in between the game's, and
can hold them in another order.

| Never assumed | Instead |
| --- | --- |
| a byte offset or the file's length | the file read through its own format's headers and offsets (GFF, 2DA, MDL) |
| a row's number, a column's place, a field's place in its struct | the row's identity (above), the column's name, the field's label |
| a list element's index (a control, a row template, a model node) | its key: `TAG`, its parent's `TAG`, its node name |
| vanilla's counts | as many as the mod's file has; what has no vanilla match is the mod's own and is kept |
| vanilla's order | the mod's order, kept in the output |

| Resource | Identity | Checked |
| --- | --- | --- |
| `.gui` control | its `TAG`, within its file | the 84 vanilla `.gui` files: 2,099 controls, every one with a `TAG`, none repeated within its file (2026-10-31, read with PyKotor) |
| `.gui` row template, scroll bar | the `TAG` of the control that holds it | the same |
| 2DA row | as above | `tutorial.2da` (2026-10-31): 43 rows, `label` set in each and never repeated; its row labels only the numbers 0 to 42 |
| model node | its name, through the model's own name table | `kmrp-swoophud.c` finds `Plane09` this way |

### What is reported as a lost feature

Logged as `[KMRP] compatibility:` lines in `KMRP\logs\kmrp-kpm.log`, beside the file:

| Feature | Lost when |
| --- | --- |
| A screen laid out for the display | its canvas cannot be identified (the root's size is named) |
| KMRP's calibration of a control | an already-scaled file's control is not only scaled from the game's (counted), or the adjustment would break a line-up the mod made (the control named) |
| A controller cue or the travelling A | the control it sits beside is missing from the mod's file |
| The 32-slot party roster | `partyselection.gui` cannot be built from the mod's file |
| The galaxy map's planets on KMRP's map | `galaxymap.gui` is not the game's 640x480 layout |
| The main menu buttons on their art's bars | the mod has its own `mainmenu*.gui` |
| A KMRP change in a table | the cell was the mod's (a conflict), the row or column is gone or ambiguous, or the table could not be merged |
| KMRP's copy of a picture | the mod's picture cannot be decoded |
| The swoop race's speed bar fix (issue 47) | the mod's model's chevron is not the game's |

### Adding a resource KMRP changes

1. Make KMRP's file from vanilla in the tool that makes the set, as today.
2. Add its line to `kmrp_derive.txt` in that tool (`OUTPUT`, `SOURCE`, and for a picture
   how it is drawn).
3. That is all for a `.2da`, `.tga`, `.tpc` or a `.gui` Live Adaptive Layout lays out: the
   run time finds the line and the format's strategy does the rest. Only a format no
   strategy handles yet needs a branch in `DeriveFromOverrideK1`, keyed by the format, and
   a part in `Test-ModCompatibility.py`.

### Limits

* A text 2DA is written back tab-separated: its content and `DEFAULT:` line are the mod's,
  its spacing is not.
* A mod's `.txi` for a picture KMRP copies under another name (the tutorial popup's
  `tut_*` from `lbl_icn_*`) is not copied with it.
* Pictures the game's preload cannot decode (a greyscale or DXT3 TPC) are left as the mod
  has them, and named.
* A mod that renames a row's key (its `label`) has, for KMRP, a new row: KMRP's change of
  the old one is reported as lost.
* The Mac: the C is shared, but the Mac's module does not run `DeriveFromOverrideK1` and
  its build does not compile `kmrp-merge.c`. Not done, not tested.
* **Not tested in the game** (2026-10-31): every test runs the tools on files; no
  community mod combination has been played with this build.

### Tests

`testing/regression/Test-ModCompatibility.py` makes its files under names no KMRP code
knows and checks, against several 2DA schemas, every picture format the game reads, the
swoop model and the layouts, that each strategy does what this section says, that C and
Python agree, and that every input file is unchanged. It also checks the merge code names
no table at all. `Test-LiveLayout.py` keeps every vanilla screen at every size as before.

Run on 2026-10-31 on the maintainer's PC, the Steam game as the source of vanilla's files:

| Test | Result |
| --- | --- |
| `Test-ModCompatibility.py` | 627 checks passed: 2DA (ten cases, among them 40 random schemas with rows put in between), six picture formats, the record (312 icons and 18 game art files, every line naming a file written), the model, and the layouts (the moved list at 740, every already-scaled full-screen screen at both sizes, the plain-scaled list at KMRP's 632, a root resized alone refused, a line-up kept) |
| `Test-LiveLayout.py` | passed: 73 screens against the 66 sets as before (3440x1440 identical), 19,706 C/Python layouts, 73 root-only files refused, the cue, options and HUD cue mod suites |
| `Test-GameArt.py`, `Test-AbilityIcons.py` | passed: byte for byte the Windows installer's C# at every height (the new record left out of the comparison, as the C# has none) |
| `Test-ControllerKpatch.py`, `Test-PartyRosterGui.py`, `Test-OverrideFontMetrics.py` | passed |
| the module (`build_native_runtime.cmd`) | built and linked, the five new functions in its map |

Results for each file are in the [state table](#state-for-each-file) below.

### State for each file

Built 2026-10-31, source after `6dc8c25`; checked by the tools' tests, **not in the game**.

| Files | Strategy | Before 2026-10-31 | Now |
| --- | --- | --- | --- |
| `tutorial.2da` | three-way merge (any 2DA) | the mod's whole, KMRP's `icon` cells lost | merged: KMRP's sharp icons in every row the mod left vanilla's, the mod's rows, numbers and own icons kept |
| 82 layout files (`.gui`) | Live Adaptive Layout on the mod's file | a moved control lost gold's correction; an already-scaled file refused | a moved control keeps its move on KMRP's place; a mod's line-up kept; an already-scaled file laid out from its own canvas (the three rules); every skipped KMRP feature logged |
| Feat, power and skill icons (`i_*`, `ip_*`, `isk_*`) | KMRP's transform on the mod's picture | the mod's whole, at its small size | the mod's icon enlarged as the game's is |
| Row frames (`lbl_hex`, `_3`, `_6`, `_7`) | KMRP's transform on the mod's picture | the mod's whole, at its own size | the mod's frame sized as the game's is |
| Tutorial popup icons (from `lbl_icn_*`) | KMRP's transform on the mod's picture | copies of the game's | copies of the mod's where `Override` has one |
| Swoop HUD model (`m17mg_camera.mdl`, `.mdx`) | KMRP's change where the part is still the game's | the mod's whole, the fix off silently | the chevron moved where it is still the game's; else the fix named as off |
| KMRP's pictures and fonts in place of the game's (756 and 17) | the mod's wins whole | the mod's whole | the same, one count line |
| `swkotor.exe`, `binkw32.dll`, `swkotor.ini` | not merged | KPM refuses a hook whose bytes another patch changed | the same |

**Beside `Override`, for everything not made from the mod's copy** (`K1RuntimeAssets.cpp`, the comment above
`overrideFontHeights`; the maintainer's decision of 2026-10-11). The game searches the
folder registered last first, and KMRP's folders are registered after `Override`, so KMRP
leaves out of its folders every file whose name `Override` also has (`OverrideHas`,
`LinkSet`, `LinkArtwork`). A texture counts as one thing with its `.txi`: a `.tga` or
`.tpc` in `Override` leaves out KMRP's `.tga`, `.tpc` and `.txi` of that name. The
layout files KMRP makes from a mod's copy are the exception: they go into a folder
searched before `Override`, because they already hold the mod's work.

So a mod's file is never hidden. Until 2026-10-31, where KMRP's file was not made from the
mod's copy, the mod's file won whole and **KMRP's change was lost**; the files above are now
made from the mod's copy instead.

## How this was measured

On 2026-10-31, source `6dc8c25`. The file list is the runtime cache
`%LOCALAPPDATA%\KMRP\cache\5543d4158ebca85c`: its `store\` (the files every size
shares), `sets\3440x1440\` and this run's set folder (`set-16868-1\`, 83 `.gui`, one
`.2da`, the `.mdl` and `.mdx`, one `.txt` and its pictures), and `fonts-16868\` (the
game font names in use). Another size's set holds the same names; only the number of
enlarged icons can differ (`kmrp-abilityicons.c` skips icons already right for the
height). Where each file comes from and what happens beside `Override` is read from
`src/controller-native/K1RuntimeAssets.cpp` and the C it calls
(`macos/tools/kmrp-guiadapt.c`, `kmrp-gameart.c`, `kmrp-abilityicons.c`,
`kmrp-swoophud.c`). No mod was installed for it.

**Status** (since 2026-10-31): *Merged*: made from the mod's copy, so the rule is kept.
*Derived*: KMRP's transform run on the mod's picture or model. *Picture*: a picture or font with no
separate fields to merge, so the mod's is the right one to show. *Not a resource*: a file
in the game folder itself, which mods do not ship in `Override`.

## Files in the game folder

| File | What KMRP does to it | When a mod has its own | Status |
| --- | --- | --- | --- |
| `swkotor.exe` | not rewritten on disk since 2026-09-29, but for the 4 GB flag (`IMAGE_FILE_LARGE_ADDRESS_AWARE`, `PeCompatibility`) on the CD and GOG builds; Steam's is left whole, as SteamStub refuses a changed file. Every code change is made in memory by KPM at start, byte for byte in [`binary-inventory.md`](../reverse-engineering/binary-inventory.md) | another exe patch on the same sites is issue 79's part 3 | not a resource |
| `binkw32.dll` | moved to `binkw32Hooked.dll` and replaced by KPM's loader, which loads the game's own (`KpmEdition.cs`); put back by restore | a mod that replaces it again unloads KPM; the installer says so | not a resource |
| `swkotor.ini` | the start size (`[Graphics Options]`) at install; KMRP's own sections (`[KMRP Text]` and others) from the game; backed up in `KMRP\backups` | a settings file, not a mod resource | not a resource |

## Game data files

| File | What KMRP does to it | When a mod has its own | Status |
| --- | --- | --- | --- |
| `tutorial.2da` | the game's table (through `chitin.key`), its `icon` column pointed at KMRP's sharp `tut_*` copies (`kmrp-gameart.c`) | merged three ways (`kmrp-2da.h`, any 2DA): KMRP's `icon` cells only where the mod left the game's; the mod's rows, numbers and own values kept | Merged |
| `m17mg_camera.mdl`, `m17mg_camera.mdx` | the swoop race's HUD model from the game, its parked speed segment moved out of a wide screen's view (`kmrp-swoophud.c`, issue 47) | the chevron moved on the mod's model where it is still the game's (`KmrpSwoopHudModel`); else the mod's as it is, the fix named as off | Derived |

## Layout files (`.gui`): 82

| File | What KMRP does to it | When a mod has its own | Status |
| --- | --- | --- | --- |
| `abchrgen.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `abilities.gui` | laid out for the screen; controller cues added | laid out from the mod's file, the cues added to it | Merged |
| `areatransition.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `barkbubble.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `character.gui` | laid out for the screen; controller cues added | laid out from the mod's file, the cues added to it | Merged |
| `classsel.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `computer.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `computercamera.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `confirm.gui` | laid out for the screen; controller cues added | laid out from the mod's file, the cues added to it | Merged |
| `container.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `credits.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `custpnl.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `debug.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `dialog.gui` | laid out for the screen; controller cues added | laid out from the mod's file, the cues added to it | Merged |
| `equip.gui` | laid out for the screen; controller cues added | laid out from the mod's file, the cues added to it | Merged |
| `fade.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `ftchrgen.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `galaxymap.gui` | laid out for the screen; the planets put on KMRP's map | the mod's planets placed on KMRP's map; a mod file not 640x480 is left as it is | Merged |
| `inventory.gui` | laid out for the screen; controller cues added | laid out from the mod's file, the cues added to it | Merged |
| `journal.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `leveluppnl.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `loadscreen.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `maincg.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `maininterface.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `mainmenu.gui` | laid out for the screen; the buttons put on the art's bars | laid out from the mod's file; the bar step is skipped | Merged, bar step skipped |
| `mainmenu10x7.gui` | laid out for the screen; the buttons put on the art's bars | laid out from the mod's file; the bar step is skipped | Merged, bar step skipped |
| `mainmenu12x9.gui` | laid out for the screen; the buttons put on the art's bars | laid out from the mod's file; the bar step is skipped | Merged, bar step skipped |
| `mainmenu16x12.gui` | laid out for the screen; the buttons put on the art's bars | laid out from the mod's file; the bar step is skipped | Merged, bar step skipped |
| `mainmenu8x6.gui` | laid out for the screen; the buttons put on the art's bars | laid out from the mod's file; the bar step is skipped | Merged, bar step skipped |
| `map.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `messages.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `mi8x6.gui` | KMRP's HUD file; the module places it at run time, with the combat cues; never loaded with KMRP | the mod's file is used; the combat cues are added to it | Merged |
| `mipc10x7.gui` | KMRP's HUD file; the module places it at run time, with the combat cues; never loaded with KMRP | the mod's file is used; the combat cues are added to it | Merged |
| `mipc12x9.gui` | KMRP's HUD file; the module places it at run time, with the combat cues; never loaded with KMRP | the mod's file is used; the combat cues are added to it | Merged |
| `mipc16x12.gui` | KMRP's HUD file; the module places it at run time, with the combat cues; never loaded with KMRP | the mod's file is used; the combat cues are added to it | Merged |
| `mipc210x7.gui` | KMRP's HUD file; the module places it at run time, with the combat cues | the mod's file is used; the combat cues are added to it | Merged |
| `mipc212x9.gui` | KMRP's HUD file; the module places it at run time, with the combat cues; never loaded with KMRP | the mod's file is used; the combat cues are added to it | Merged |
| `mipc216x12.gui` | KMRP's HUD file; the module places it at run time, with the combat cues; never loaded with KMRP | the mod's file is used; the combat cues are added to it | Merged |
| `mipc28x6.gui` | KMRP's HUD file; the module places it at run time, with the combat cues | the mod's file is used; the combat cues are added to it | Merged |
| `mipc8x6.gui` | KMRP's HUD file; the module places it at run time, with the combat cues; never loaded with KMRP | the mod's file is used; the combat cues are added to it | Merged |
| `name.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `ntscpat.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optautopause.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optfeedback.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optgameplay.gui` | laid out for the screen; controller cues added | laid out from the mod's file, the cues added to it | Merged |
| `optgraphics.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optgraphicsadv.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optionsingame.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optionsmain.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optkeyentry.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optkeymapping.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optmouse.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optresolution.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optsound.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `optsoundadv.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `partyselection.gui` | laid out for the screen; rebuilt as the 32-slot roster | the roster built from the mod's file, its captions, IDs and navigation kept | Merged |
| `pause.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `pazaakgame.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `pazaaksetup.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `pazaakwager.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `portcust.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `pwrlvlup.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `qorcpnl.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `questitem.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `quickpnl.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `saveload.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `savename.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `scriptselect.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `skchrgen.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `skillinfo.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `splashscreen.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `store.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `titlemovie.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `tooltip10x8.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `tooltip12x9.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `tooltip16x12.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `tooltip6x4.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `tooltip8x6.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `top.gui` | laid out for the screen; controller cues added | laid out from the mod's file, the cues added to it | Merged |
| `upgrade.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `upgradeitems.gui` | laid out for the screen | laid out from the mod's file | Merged |
| `upgradesel.gui` | laid out for the screen | laid out from the mod's file | Merged |

"Laid out for the screen" is Live Adaptive Layout (`KmrpLiveLayoutSet`). "Controller cues
added" is the controller patch (`KmrpControllerCues`), on the mod's file as on the game's.
For every layout row: a moved control keeps the mod's move on KMRP's place, and a file
already scaled is laid out from its own canvas by the three rules
([`live-adaptive-layout.md`](live-adaptive-layout.md)); one whose canvas cannot be
identified is left as it is, with the screen named in the log.

## Pictures made from the game's files, per size

| Files | Count at 3440x1440 | What KMRP does to them | When a mod has its own | Status |
| --- | --- | --- | --- | --- |
| Feat and power icons `i_*`, `ip_*` | 179, 123 | the game's icons (`swpc_tex_gui.erf`) enlarged to KMRP's row size (`kmrp-abilityicons.c`) | the mod's icon enlarged as the game's is (`KmrpDeriveImage`) | Derived |
| Skill icons `isk_*` | 8 | the same, grown with the Skills tab's row | as above | Derived |
| The game's tutorial icons `lbl_icn_*`, as the popup shows them | 13 | not replaced: the popup is pointed at KMRP's copies (`tut_*`, through `tutorial.2da`), made from the game's `lbl_icn_*` at the popup's size (`kmrp-gameart.c`) | the copies made from the mod's `lbl_icn_*` | Derived |
| Row frames `lbl_hex`, `lbl_hex_3`, `lbl_hex_6`, `lbl_hex_7` | 4 | the game's frames sized to KMRP's rows | the mod's frame sized as the game's is | Derived |
| HUD button-row art `lbl_mileftbot` | 1 | KMRP's own drawing (`tools/build_menubg_texture.py`) | KMRP's copy left out | Picture |

## Game pictures and fonts KMRP replaces with its own, the same for every size

| Files | Count | KMRP's replacement | When a mod has its own | Status |
| --- | --- | --- | --- | --- |
| Portraits `po_*` | 178 | KMRP's art pack | the mod's picture | Picture |
| Item icons `ii_*`, `iw_*`, `ia_*`, `i_*` | 162, 125, 64, 2 | KMRP's art pack | the mod's picture | Picture |
| Interface art `lbl_*` | 148 | KMRP's art pack | the mod's picture | Picture |
| Loading screens `load_*` | 23 | KMRP's art pack | the mod's picture | Picture |
| Equipment slots (`iarmor`, `ibelt`, `ihands`, `ihead`, `iimplant`, `iforearm_*`, `iweap_*`, their `id*` versions, `inone`) | 18 | KMRP's art pack | the mod's picture | Picture |
| Frames and the rest (`border*` 8, `boxline*` 9, `confirm*` 4, `invent*` 4, `scr_*` 4, `panel*` 2, `blank`, `dp_*`, `logo_*`, `uparrow`) | 36 | KMRP's art pack | the mod's picture | Picture |
| Fonts: `dialogfont10x10`, `10x10a`, `10x10b`, `12x16`, `16x16`, `16x16a`, `16x16b`, `32x32`, `fnt_console`, `fnt_credits`, `fnt_creditsa`, `fnt_d10x10b`, `fnt_d16x16`, `fnt_d16x16a`, `fnt_d16x16b`, `fnt_dialog16x16`, `fnt_galahad14` (`.tga` with `.txi`) | 17 | KMRP's fonts at the size in use | KMRP's left out; the mod's read with its own metrics, and KMRP notes the size its own would have had (`overrideFontHeights`) | Picture |

756 pictures in all in `store\`, counted by name.

## Game tables KMRP reads but does not ship

| File | How KMRP uses it | When a mod has its own |
| --- | --- | --- |
| `footstepsounds.2da`, `visualeffects.2da`, `keymap.2da`, `planets.2da` | read through the game's own tables (`C2DA::GetINTEntry` 0x00413660 and the others in `K1Rumble.cpp`) | the mod's table is what KMRP reads |
| `rumble.2da` | KMRP carries the Xbox table built in: the PC game ships neither the file nor its loader | a mod's would be ignored; none is known |
| `skills.2da`, row 2 (Stealth) | the name (dialog.tlk 325) and icon (`isk_stealth`) are written into `K1XboxHud.cpp` for the Xbox HUD's Stealth button | a mod's change to Stealth's name or icon is not shown on that button |

## What the inventory shows

* **All 82 layout files** are made from the mod's copy.
* **Five things lost KMRP's change** when a mod had the same file, until 2026-10-31:
  `tutorial.2da`, the swoop HUD model, the feat, power and skill icons, the row frames,
  and (from the mod's `lbl_icn_*`) the tutorial icons. Each is now made from the mod's
  copy by its format's strategy (the state table above).
* **KMRP's own pictures and fonts** are left to the mod, which is right: a picture has no
  separate fields to merge.
* **The Stealth button** takes its name and icon from KMRP's code, not from `skills.2da`.
* Not covered: the Mac, whose files come from the same C code but are installed
  differently ([`macos-handoff-1.5-to-1.6.md`](macos-handoff-1.5-to-1.6.md)).
