# Live Adaptive Layout: screens laid out at run time from the file the game would load

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it: measured claims only, every site
> tabulated, rejected alternatives and corrections kept visible, and anything untested
> labelled as untested.

**Kind: reference.** What the code does now. The controller patch's part of the same
plan, every picture drawn at the size it is shown, is
[controller-live-adaptive-layout.md](controller-live-adaptive-layout.md).

KMRP ships each screen's layout made at build time for each of 66 sizes. A GUI mod's
`.gui` in `Override` took the place of KMRP's whole file, laid out for 640x480, so the
screen was drawn small in a corner of a large display, or not at all where KMRP's art
expects its own extents. Live Adaptive Layout (the maintainer's name, 2026-10-27) lays out
whichever file the game would load, the game's own or a mod's, for the size in use, when
the size's set is made ready. Since 2026-10-28 it does that for 14 screens: the 11 options
screens (`e237578`), then Inventory, Equipment and Character the same day; the rest still
come from the sets.

Provenance: every number below was computed from files in this repository and the
game's own layout files (`build-inputs/vanilla-gui`, extracted from the Steam game's
`chitin.key`), and is re-measured by `testing/regression/Test-LiveLayout.py`, except where
a figure is marked as measured once with scripts that are not in the repository. Seen in
the game at 3440x1440 only, and the last three screens not yet (section 6).

## The build this describes

| | |
| --- | --- |
| Source | master `80607b2` and the changes of 2026-10-28 after it (uncommitted when written) |
| Module | `build\native-runtime\kmrp-native.dll`, 759,296 bytes, SHA-256 `ACA3146F97263EEDAE09BF84C0CDDF0EE75446BBD762D7BA376176A6CDC07132`; the options screens alone were `BD9742A55E7788CD82E8D7E964EC5DBE692D5C96AAD5B5DEDE293DC2BAB12DB4`, 744,448 bytes |
| Table | `macos/tools/kmrp-livelayout-table.h`, made by `python tools/build_live_layout.py` |
| Executable | not changed: this writes layout files, no byte of `swkotor.exe` |

## 1. What the engine does with a layout

A `.gui` is a GFF file. Every control has an `EXTENT` (`LEFT`, `TOP`, `WIDTH`, `HEIGHT`),
and a list box also has a `PROTOITEM` (its row template) and a `SCROLLBAR`, each with an
`EXTENT` of its own. A control's extent is relative to its panel: in `confirm.gui` the root
is at 174,210 and its message at 6,10 inside it. A full-screen panel starts at 0,0, so there
the two are the same.

**A list's scroll bar takes only its width from the file.** Read from
`swkotor1-reconstruction` (`matching/src/d/gui_listbox.cpp` and
`src/units/0494/1c5c7c2cc3-listbox_listbox.cpp`), VA addresses in the Steam/GOG
`swkotor.exe`:

| VA | Function | What it does |
| --- | --- | --- |
| 0x0041BF07 | `CSWGuiListBox` constructor | flags `\|= 0x183A` (stored at this address): bit 0x10, the scroll bar on the left, is set on every new list |
| 0x0041D5B0 | `CSWGuiListBox::Load` | loads `BORDER`, then `SCROLLBAR` (its file extent), then `LEFTSCROLLBAR`, `PADDING`, `COLOR`, `LOOPING`, and last `CSWGuiNavigable::Load` |
| 0x0041C890 | `CSWGuiNavigable::Load` | `MOVETO`, then `CSWGuiControl::Load` (0x0041B8E0): the list's own `EXTENT` and its `SetExtent` |
| 0x0041BF80 | `CSWGuiListBox::SetExtent` | the list's extent, then `SetScrollBarExtent` (0x004181F0) with the bar's width |
| 0x004181F0 | `SetScrollBarExtent` | the bar's top and height are the list's; its left is the list's left (bit 0x10) or its right edge less the width; the width is capped to the list's |

So whatever a file gives as the scroll bar's left, top and height is replaced as the list
loads. High Resolution Menus gives about 12 lists another list's scroll-bar extent
(`abilities.gui`'s description list has the ability list's, on the other side of the
screen); that never shows, and nothing here depends on it.

## 2. The model: rules on the game's own value

High Resolution Menus lays each size out by hand (its `README.pdf`: "Find the
gui.WIDTHxHEIGHT folder ... matching the WIDTH and HEIGHT"; its `hires_patcher.pl` only
patches the executable). Across its 49 sets it changes nothing but extents, apart from a
few edits the same in every set (border art in `classsel.gui` and `mainmenu.gui`,
alignments in `character.gui` and `map.gui`, fill styles in `pazaakgame.gui` and
`scriptselect.gui`). Every structure follows one of a few rules applied to its value `v`
in the game's file, with `s = H / BH`:

| Rule | Value | Used for |
| --- | --- | --- |
| scale | `v * s` | tops and heights; a square's width |
| stretch | `v * W / BW` | lefts and widths of most controls, root panels, scroll bars |
| aspect | `(v + w/2) * W / BW - w * s / 2` | a square's left: it keeps its shape, centred where the stretched one would be (`w` its width) |
| fixed | `v` | list row templates (`PROTOITEM`) |
| centre | `W/2 + (v - BW/2) * s` | 4 fields in all of upstream |
| right | `W - (BW - v) * s` | 2 fields |

`BW x BH` is the file's own size: its root panel's when that fills the screen from 0,0,
else 640x480. The game's file names do not say it: `mainmenu10x7.gui`'s root is 800x600.

Measured once on 2026-10-28 with scripts not in the repository (they read every `EXTENT` of
the game's 81 files and of upstream's 48 sets of a family, leaving out the 21-by-9 folder's
1280x1080): one rule per field reproduces **92.1% of the 9,276 fields exactly in every set,
and 99.0% of the 445,248 values**; 98.7% to 99.4% per family. The misses are rounding within
3 px (672 fields, nearly all in the HUD files and Pazaak), the scroll bars of section 1
(33), `debug.gui` (8), and upstream's own hand layout (character select's model and first
portrait button, Character's `LBL_LEVEL`, the main menu's logo).

**KMRP's changes are gold's, carried as a ratio.** The build gives every size the
3440x1440 gold file's corrections by multiplying each changed field by gold / upstream
(`tools/transfer_gold_gui_geometry.py`). This takes the ratio against the rule instead:

```
r        = the field's rule at W x H, unrounded
r_gold   = the same rule at 3440 x 1440
placed   = round(r)                 where gold equals round(r_gold), or the table has no gold
         = round(gold * (r / r_gold))   otherwise (round(r + gold) when r_gold is 0)
round    = half away from zero
```

At 3440x1440 `r / r_gold` is 1 exactly, so gold comes out as it is. Measured once the same
day: over the 67 screens that are not the HUD, the debug panel or made by a step of their
own, this reproduces **95.1% of the values of KMRP's 66 sets exactly, 99.1% within a
pixel, 0.7% more than 3 px off**. The maintainer accepted the rounding pixel for every size
but gold on 2026-10-28.

What it produces, two controls of the options screens (`python` the example in section 8):

| `optionsmain.gui LB_DESC`, game `[330, 90, 256, 290]`, gold `[1780, 280, 1386, 850]` | rule alone | live | KMRP's set |
| --- | --- | --- | --- |
| 1024x768 | 528, 144, 410, 464 | 530, 149, 413, 453 | 530, 149, 413, 453 |
| 1920x1080 | 990, 203, 768, 653 | 993, 210, 774, 638 | 993, **211**, 774, 638 |
| 2560x1080 | 1320, 203, 1024, 653 | 1325, 210, 1031, 638 | **1324, 211**, 1031, 638 |
| 3440x1440 | 1774, 270, 1376, 870 | 1780, 280, 1386, 850 | 1780, 280, 1386, 850 |
| 5120x1440 | 2640, 270, 2048, 870 | 2649, 280, 2063, 850 | 2649, 280, 2063, 850 |

| `optkeymapping.gui LST_EventList`, game `[61, 97, 521, 306]`, gold `[632, 291, 2177, 918]` | rule alone | live | KMRP's set |
| --- | --- | --- | --- |
| 1920x1080 | 183, 218, 1563, 689 | 353, 218, 1215, 689 | 353, 218, 1215, 689 |
| 2240x1260 | 214, 255, 1824, 803 | 412, 255, 1418, 803 | **410**, 255, **1417**, 803 |
| 3440x1440 | 328, 291, 2800, 918 | 632, 291, 2177, 918 | 632, 291, 2177, 918 |
| 4096x3072 | 390, 621, 3334, 1958 | 753, 621, 2592, 1958 | **751**, 621, 2592, 1958 |

The second is one of the nine fields 2 or 3 px off (section 6): upstream's own value at
4096x3072 sits off the rule, and gold's ratio carries that.

**A field's rule is chosen up to a factor** (since 2026-10-28, with Character). The table
picks, per field, the rule that reproduces most of upstream's sets once scaled by
upstream's 3440x1440 value over the rule's there, the factor gold's ratio supplies at run
time; ties go to the unscaled fit, then the default. Character's `LBL_LEVEL` is half as wide
as stretching makes it at every size (0.0859 W against 0.1719 W); no rule fitted it
unscaled, "fixed" was picked, and the label stayed 296 px wide everywhere (1320 in the
15360x8640 set). Scaled, stretch fits, and the field is within 2 px at every size. The
options screens' table came out byte for byte as before.

**A mod's own control has no upstream data**, so its rule must follow from the control.
Measured over upstream's sets the same day: tops and heights scale (94% of fields; the rest
are row templates), wide and tall controls stretch, row templates stay fixed, and squares
are split: about 350 keep their shape (portraits, icons, item slots) and about 140 stretch
(value labels, the +/- buttons in character generation, square lists). Of the square
controls no rule pair seemed to fit, all 222 were "aspect" missed by at most 1.4 px in a few
sets, upstream's rounding. So the default is:

| Structure | LEFT | TOP | WIDTH | HEIGHT |
| --- | --- | --- | --- | --- |
| `PROTOITEM` | fixed | fixed | fixed | fixed |
| square control (width / height 0.8 to 1.25), not a list box (CONTROLTYPE 11) | aspect | scale | scale | scale |
| everything else (root, scroll bar, other controls) | stretch | scale | stretch | scale |

## 3. What KMRP writes

**Files.** For each size, into the folder the game searches before the size's set and
before `Override` (the roster folder, or this run's folder of links when the player's
`Override` has some of the set's files), `K1RuntimeAssets.cpp` `AdaptLiveLayoutK1`:

| File | Source when `Override` has none | Source when it has one |
| --- | --- | --- |
| `optionsmain.gui`, `optionsingame.gui`, `optautopause.gui`, `optgraphics.gui`, `optgraphicsadv.gui`, `optmouse.gui`, `optsound.gui`, `optsoundadv.gui`, `optkeymapping.gui`, `optkeyentry.gui`, `optresolution.gui` | the game's own, from `chitin.key` | the player's, if it is laid out for the game's size; else nothing is written and the player's file is left to the game, as before |
| `inventory.gui`, `equip.gui`, `character.gui` | the same, and the R3 cue added | the same, and the R3 cue added where the player's portraits leave room for it |

"Laid out for the game's size": its base (section 2) is the game's file's and its root lies
inside it. A mod's file laid out for 1920x1080 is refused (`Test-LiveLayout.py` part 4).

**Fields.** Only these change, in place; every other byte of the source is kept:

| Field | Value |
| --- | --- |
| every `EXTENT` (root, controls, `PROTOITEM`, `SCROLLBAR`) | section 2: the table's rule and gold for a structure the game's file has with the same TAG and the same extent; the table's rule without gold where the source moved it; the default rule for a TAG the table does not have (an untagged control is keyed by its place, `#index`) |
| `PADDING` of a list box (CONTROLTYPE 11) | the build's gutters, at `max(1, H / 720)`: 36 per unit for `LB_DESC`, `LB_DESCRIPTION`, `LBL_ITEM_DESCRIPTION`, `LB_ITEM_DESCRIPTION`, `LB_DESC_LS`; 12.5 for `LB_ITEMS`, `LB_ABILITY`, `LB_FEATS`, `LB_POWERS`, `LB_SHOPITEMS`, `LB_INVITEMS`; never reduced; then the per-file hand-set ones, which may reduce; rounded half to even (`prepare_universal_resources.py` `DESCRIPTION_LISTBOXES`, `LIST_LISTBOXES`, `HAND_TUNED_GUTTERS`, copied into the table by the script) |
| `PADDING` the gold file sets by hand | at 3440x1440 only, before the gutters: `optresolution.gui`'s resolution list, 20, and `optionsmain.gui LB_DESC`, 40, which the gutter then raises to 72 as in the set |
| `TEXT.ALIGNMENT` the gold file changes | at every size, where the file has the game's own alignment there, as `transfer_gold_gui_geometry.py` carries it: Character's `LBL_LEVEL`, 12 to 10 |
| a list made as tall as whole rows | after the gutters, `scale_listbox_padding.py` `fit_list_to_rows` for the lists of `ROW_LISTS` on these screens: Equipment's `LB_ITEMS`, rows of 56 at `max(1, H / 720)` in single precision, rounded half to even, each an eleventh of a row apart; a screen's list only shrinks, when a kind of row sits looser than an eighth of a row (at 1024x576, 336 to 313 px) |
| the R3 cue, `LBL_KMRPR3` | added last on Inventory, Equipment and Character, as `prepare_universal_resources.py` `add_party_switch_cue` adds it: a clone of the file's first label with the tag, the next free ID, the picture `kmrprb_party` and no frame or text, its side 90% of the portraits' height, centred in their gap when the gap holds it with a tenth of it free each side, else a third of it right of the second portrait. Left out, as the build would stop, where it would leave the panel or cover a button, check box, slider, scroll bar, progress bar or list, where `BTN_CHANGE1` or `BTN_CHANGE2` is missing or they overlap, or where the label it is cloned from lacks a field it sets |

**Why the cue.** With KMRP installed the controller patch takes its own copies of the
game's layouts out of its folder (`LeaveLayoutsToKmrp`, `K1ControllerStandalone.cpp`), and
KMRP's layouts must carry the controls it adds: on these three screens, the cue its R3
prompt is drawn on. A screen laid out at run time without it would lose that prompt.

**Adding a control** is the one change not made in place. The C copies the file's six GFF
sections as they are and appends: the clone's structures and fields (inline values copied,
strings and resrefs shared where unchanged and written anew where the cue sets them, nested
structures cloned), and a new copy of the `CONTROLS` list with the cue last, at the end of
the list indices, the root's `CONTROLS` field pointed at it. Every offset already in the
file stays right, because only the sections' ends grow; the old list is left unused. The
cue's fields keep the types pykotor gives them (`TAG` and `TEXT` strings, `FILL`, `CORNER`
and `EDGE` resrefs, `ID`, the extent and `DIMENSION` INTs, `STRREF` a DWORD), so the test
compares every field of the C's file with the Python's.

**The table** (`kmrp-livelayout-table.h`): per file, per structure of the game's file, its
four rule numbers, gold's four values, a hand-set `PADDING` and a changed alignment; the
build's gutter tiers, row-fitted lists and the cue's constants, copied from the build's own
definitions by the script. It holds no value of the game's: the game's files are read on
the player's machine. `Test-LiveLayout.py` fails when it is not what the script makes.

**Three implementations of one layout**, held to each other:

| Where | What |
| --- | --- |
| `tools/build_live_layout.py` `layout` | Python, the reference; makes the table |
| `macos/tools/kmrp-guiadapt.c` `KmrpLiveLayout` | C, in the Windows module (`build_native_runtime.cmd` compiles it with `KMRP_EMBEDDED`) and for the Mac; its own `main` takes `live KEY|GAME_GUI NAME W H OUT [SOURCE]` |
| `src/controller-native/K1RuntimeAssets.cpp` `AdaptLiveLayoutK1` | calls it per screen, moves the result over the target, and logs a mod's file it laid out or left |

## 4. How this stays isolated

It runs where the galaxy map's and the main menu's adapters run
(`KmrpRuntimeAssetsDimensions`), into the same folders, and writes a file beside its target
and moves it over, because those folders can hold hard links into the cache's sets. The
sets themselves are not changed; their copies of these 14 files are still made and simply
no longer what the game reads. `KmrpRuntimeLayoutFile` returns the roster folder's file
first, so the module's own readers of these layouts see the laid-out one. Of the 14 the
controller patch changes only the three with the R3 cue, the same cue under the same tag
(`tools/build_controller_assets.py`), and leaves its copies to KMRP beside it (section 3).

## 5. Rejected alternatives

| Alternative | Why not |
| --- | --- |
| A table of each field's value at each family and height (a per-field fit `a + b*W + c*H`) | Fits 97.4% of upstream's values but only 66.9% of fields exactly; and it is data per control of the game's files, useless for a mod's own controls |
| A rounding mode per field, to match the sets to the pixel | The maintainer accepted the pixel (2026-10-28); it would double the table for no visible change |
| The base size from the file name (`mipc10x7` = 1024x768) | `mainmenu10x7.gui` is 800x600 and `tooltip10x8.gui` 1024x768; the root says it |
| Scaling the nearest family's set | Measured 2026-09-29 for the blend (`tools/derive_resolution_gui_set.py`): 70.2% exact, 5.9% more than 10 px off |
| Gold's ratio against upstream's 3440x1440 value, as the build does | Upstream is not on the player's machine; against the rule it is 73.2% exact over all files against 73.7%, and gold comes out exact |
| Laying out the panels in memory after the game built them | The engine keeps panels across a change of size and other code reads the files; writing the file the game loads is what the galaxy map, main menu and party roster already do |

## 6. Limits

- **Seen in the game at 3440x1440 only.** The maintainer opened the options screens from
  the main menu and the pause menu in their Steam game with the module above on 2026-10-28:
  "works perfectly". Every other size, and a mod's file in `Override`, is verified by
  `Test-LiveLayout.py` (against the build's sets and between Python and C), not by looking
  at the game. (When first written that day this said nothing had been seen yet.)
  **Inventory, Equipment and Character are not yet seen in the game**, nor is the R3 cue as
  they place it.
- Against KMRP's 66 sets, the 14 screens: 71,544 `EXTENT` fields, **94.47% exact, 5.35% one
  pixel off, 123 further**; gold identical in every extent and `PADDING`, and every other
  field the set's at every size but colours, whose last decimals differ by less than 1e-5
  (the gold files were written back with single precision). The 123:

  | Fields | Where | Why |
  | --- | --- | --- |
  | 49 | Equipment's and Inventory's `LB_ITEMS` and Options' `LB_DESC` scroll bars, left or height, up to 10 px | the engine replaces them as the list loads (section 1); the test holds the width only |
  | 57 | `BTN_CHANGE2`'s left, 2 to 5 px, and the R3 cue beside it, on the three screens, at the 10 sizes from 3008 px wide | upstream's rounding carried by gold's ratio; at most 5 px of a 504 px button at 15360x8640 |
  | 8 | Key Mapping, below | the same |
  | 9 | single fields at 15360x8640 (`BTN_CHANGE1` on the three screens, four of Inventory's buttons, Equipment's title and list, `LBL_LEVEL`), 2 or 3 px | the same |

  The test allows `max(3, width / 3072)` px, 5 at 15360x8640. The options screens' nine,
  the scroll bar among them:

  | File | Size | Field | Live | Set |
  | --- | --- | --- | --- | --- |
  | `optionsmain.gui` | 15360x8640 | `LB_DESC` scroll bar LEFT (replaced by the engine, section 1) | 13753 | 13751 |
  | `optkeymapping.gui` | 15360x8640 | `BTN_Default` LEFT | 4010 | 4007 |
  | | 15360x8640 | `BTN_Accept` LEFT | 8961 | 8963 |
  | | 15360x8640 | `BTN_Filter_Move` LEFT | 4010 | 4012 |
  | | 2240x1260 | `LST_EventList` LEFT | 412 | 410 |
  | | 3360x2100 | `LST_EventList` LEFT | 617 | 619 |
  | | 3360x2100 | `BTN_Filter_Move` LEFT | 877 | 879 |
  | | 4096x2304 | `LST_EventList` LEFT | 753 | 751 |
  | | 4096x3072 | `LST_EventList` LEFT | 753 | 751 |

  2240x1260 and 3360x2100 are KMRP's own blends; the others are upstream's sets, whose value
  sits a pixel or two off the rule and is carried by gold's ratio.
- The gold-only `PADDING` repeats an inconsistency of the build: the resolution list has
  20 at 3440x1440 and the game's 0 elsewhere, because the build's gold transfer carries
  extents only. Kept so gold is identical; scaling it for every size would be a change of
  its own.
- A mod's file with two controls of one TAG lays each out on its own; the gold correction
  goes to each that has the game's extent.

## 7. What is deliberately not changed

- Every other screen still comes from the size's set. Next: the screens with build steps
  the run time does not repeat yet: `abilities.gui` (the R3 cue and the sub-tab swap cue,
  and its list fitted to rows), `top.gui` (LT and RT by the tab strip), `optgameplay.gui`
  (the Controller Layout entry), `optfeedback.gui` (its row template), `confirm.gui`
  (KMRP's own popup), `map.gui`, the container, the other row-fitted lists, and the HUD
  (`apply_proportions`).
- The sets keep their copies of the 14 files; removing them from the bank is a size change
  for later.
- The Mac does not call `KmrpLiveLayout` yet ([handoff item 102](macos-handoff-1.5-to-1.6.md)).
- No byte of the executable.

## 8. Verifying by hand

```
python tools\build_live_layout.py --check
python testing\regression\Test-LiveLayout.py
```

The test needs `build\kmrp\resources` (a build's 66 sets), `build-inputs\vanilla-gui` and
clang (LLVM) on the `PATH`. To lay one screen out by hand with the C:

```
clang -O2 -o kmrp-guiadapt.exe macos\tools\kmrp-guiadapt.c
kmrp-guiadapt.exe live build-inputs/vanilla-gui/optionsmain.gui optionsmain.gui 1920 1080 out.gui
python tools\dump_gui_extents.py out.gui
```

Checks that catch this subsystem's mistakes:

- pykotor's `get_struct` and `get_list` return copies: an edit made through them is lost
  silently (found writing the reference, 2026-10-28). The script takes nested structures
  with `acquire`.
- Compare `LB_DESC`'s `EXTENT` at 3440x1440 with the gold file's
  (`assets/override-3440x1440/optionsmain.gui`): 1780, 280, 1386, 850. Any difference
  there means the ratio or the table is wrong.
- In the game's log (`kmrp-kpm.log`, debug logs on): "live layout: 11 screens laid out for
  WxH". With a mod's options file in `Override`, the same line counts it, or "is not laid
  out for the game's size" names it.
