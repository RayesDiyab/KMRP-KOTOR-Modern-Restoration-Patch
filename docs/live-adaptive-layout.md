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
the size's set is made ready. Since 2026-10-28 it does that for 44 screens: the 11 options
screens (`e237578`), then Inventory, Equipment and Character (`8ddb433`), then the 30 that
KMRP's build gives no step of its own (character creation, saving and loading, Messages,
Quest Items, the Galaxy Map, Pazaak, the workbench, the HUD's base file `maininterface`, and
the screens with nothing to fit); the rest still come from the sets (section 7).
Class selection (`classsel.gui`) joins them on 2026-10-29, followed by Abilities
(`abilities.gui`) and the menu tab strip (`top.gui`), then Gameplay and Feedback
Options (`optgameplay.gui`, `optfeedback.gui`), making **49 screens**.
**Coverage: 49 / 85 layout files, 57.65% complete by file count.** The
[full inventory](#coverage-inventory) lists every file and its implementation status.

Both mouse/keyboard and controller modes use the same live geometry; the existing
controller Select/Cancel treatment reads the resulting rectangles.

Provenance: every number below was computed from files in this repository and the
game's own layout files (`build-inputs/vanilla-gui`, extracted from the Steam game's
`chitin.key`), and is re-measured by `testing/regression/Test-LiveLayout.py`, except where
a figure is marked as measured once with scripts that are not in the repository. Seen in
the game at 3440x1440 only (section 6).

## The build this describes

| | |
| --- | --- |
| Source | master `a9419f6`, including the Abilities/tab-strip and Gameplay/Feedback migrations of 2026-10-29 (uncommitted when first written) |
| Module (49 screens) | `build\native-runtime\kmrp-native.dll`, 846,336 bytes, SHA-256 `F842D1C5F1A3DC943CB7514D7C38710BADEA5E139FDB9FE2090063E03E08939D`; built and packaged, not installed |
| Previous module (47 screens) | 842,240 bytes, SHA-256 `C388D0DA3ED09D656EAA70996BB6AD51312CA968980A78E834D301A834380793` |
| Previous module (45 screens) | `build\native-runtime\kmrp-native.dll`, 837,632 bytes, SHA-256 `DE6FD58D9F8C9C3B5AA6F56C03EC4EE5BCFD52CE7C5840F4066D5300DDEA7541` |
| Previous module | the 14-screen build was 759,296 bytes, SHA-256 `ACA3146F97263EEDAE09BF84C0CDDF0EE75446BBD762D7BA376176A6CDC07132`; the options-only build was 744,448 bytes, `BD9742A55E7788CD82E8D7E964EC5DBE692D5C96AAD5B5DEDE293DC2BAB12DB4` |
| Table | `macos/tools/kmrp-livelayout-table.h`, made by `python tools/build_live_layout.py` |
| Executable | not changed: this writes layout files, no byte of `swkotor.exe` |

## Coverage inventory

**49 / 85 GUI layout files implemented: 57.65% (about 58%).**
**36 / 85 remain outside the shared path: 42.35%.**

Measured on 2026-10-29 against source `a9419f6`: the denominator is the union of
84 original files in `build-inputs/vanilla-gui` and 83 distinct `.gui` names across
all 66 `build/kmrp/resources/gui-*.zip` archives. Their union contains 85 names:
the archives add `kmrplayout.gui`, while `startscreen.gui` and `statussummary.gui`
occur only in the original-file inventory. The numerator is membership in
`tools/build_live_layout.py` `FILES`. Percentage is `100 * 49 / 85`, rounded to
two decimal places. Every name is listed once below.

**Status definition:** Yes means the file is implemented in the shared
`KmrpLiveLayout` path. No means migration, integration or an explicit audit is
still pending. A No does not mean the screen is broken or has no runtime sizing:
some have separate adapters already. The count includes resolution-specific
HUD, main-menu and tooltip variants, the custom controller screen, and static
or auxiliary game layouts. It is a file coverage measure, not a count of unique
player-facing screens or completed play-tests. Mac runtime integration remains
pending separately; section 6 records verification limits.

| Layout file | Implemented in shared path? | Remaining work / notes |
| --- | --- | --- |
| `abchrgen.gui` | Yes | Shared runtime layout rules. |
| `abilities.gui` | Yes | Row fitting, party-switch and sub-tab swap cues. |
| `areatransition.gui` | Yes | Shared runtime layout rules. |
| `barkbubble.gui` | Yes | Shared runtime layout rules. |
| `character.gui` | Yes | Shared runtime layout rules. |
| `classsel.gui` | Yes | Fixed frame margins and class-button art corrections. |
| `computer.gui` | No | Terminal layout migration pending. |
| `computercamera.gui` | Yes | Shared runtime layout rules. |
| `confirm.gui` | No | Custom confirmation popup migration pending. |
| `container.gui` | No | Container row fitting and caption layout pending. |
| `credits.gui` | Yes | Shared runtime layout rules. |
| `custpnl.gui` | Yes | Shared runtime layout rules. |
| `debug.gui` | Yes | Shared runtime layout rules. |
| `dialog.gui` | No | Existing runtime placement needs an integration audit. |
| `equip.gui` | Yes | Shared runtime layout rules. |
| `fade.gui` | Yes | Shared runtime layout rules. |
| `ftchrgen.gui` | No | Feat-selection row fitting pending. |
| `galaxymap.gui` | Yes | Shared runtime layout rules. |
| `inventory.gui` | Yes | Shared runtime layout rules. |
| `journal.gui` | No | Quest-list row layout migration pending. |
| `kmrplayout.gui` | No | Custom Controller Layout screen; existing separate runtime path needs integration/audit. |
| `leveluppnl.gui` | Yes | Shared runtime layout rules. |
| `loadscreen.gui` | Yes | Shared runtime layout rules. |
| `maincg.gui` | Yes | Shared runtime layout rules. |
| `maininterface.gui` | Yes | Shared runtime layout rules. |
| `mainmenu.gui` | No | Main-menu variant; existing runtime handling needs integration/audit. |
| `mainmenu10x7.gui` | No | Main-menu variant; existing runtime handling needs integration/audit. |
| `mainmenu12x9.gui` | No | Main-menu variant; existing runtime handling needs integration/audit. |
| `mainmenu16x12.gui` | No | Main-menu variant; existing runtime handling needs integration/audit. |
| `mainmenu8x6.gui` | No | Main-menu variant; existing runtime handling needs integration/audit. |
| `map.gui` | No | Area-map integration pending. |
| `messages.gui` | Yes | Shared runtime layout rules. |
| `mi8x6.gui` | No | HUD variant; proportion/layout integration pending. |
| `mipc10x7.gui` | No | HUD variant; proportion/layout integration pending. |
| `mipc12x9.gui` | No | HUD variant; proportion/layout integration pending. |
| `mipc16x12.gui` | No | HUD variant; proportion/layout integration pending. |
| `mipc210x7.gui` | No | HUD variant; proportion/layout integration pending. |
| `mipc212x9.gui` | No | HUD variant; proportion/layout integration pending. |
| `mipc216x12.gui` | No | HUD variant; proportion/layout integration pending. |
| `mipc28x6.gui` | No | HUD variant; proportion/layout integration pending. |
| `mipc8x6.gui` | No | HUD variant; proportion/layout integration pending. |
| `name.gui` | Yes | Shared runtime layout rules. |
| `ntscpat.gui` | Yes | Shared runtime layout rules. |
| `optautopause.gui` | Yes | Shared runtime layout rules. |
| `optfeedback.gui` | Yes | Checkbox row template height scaling. |
| `optgameplay.gui` | Yes | Controller Layout entry and column spacing. |
| `optgraphics.gui` | Yes | Shared runtime layout rules. |
| `optgraphicsadv.gui` | Yes | Shared runtime layout rules. |
| `optionsingame.gui` | Yes | Shared runtime layout rules. |
| `optionsmain.gui` | Yes | Shared runtime layout rules. |
| `optkeyentry.gui` | Yes | Shared runtime layout rules. |
| `optkeymapping.gui` | Yes | Shared runtime layout rules. |
| `optmouse.gui` | Yes | Shared runtime layout rules. |
| `optresolution.gui` | Yes | Shared runtime layout rules. |
| `optsound.gui` | Yes | Shared runtime layout rules. |
| `optsoundadv.gui` | Yes | Shared runtime layout rules. |
| `partyselection.gui` | No | Existing runtime placement needs an integration audit. |
| `pause.gui` | No | Existing runtime placement needs an integration audit. |
| `pazaakgame.gui` | Yes | Shared runtime layout rules. |
| `pazaaksetup.gui` | Yes | Shared runtime layout rules. |
| `pazaakwager.gui` | Yes | Shared runtime layout rules. |
| `portcust.gui` | Yes | Shared runtime layout rules. |
| `pwrlvlup.gui` | No | Power-selection row fitting pending. |
| `qorcpnl.gui` | Yes | Shared runtime layout rules. |
| `questitem.gui` | Yes | Shared runtime layout rules. |
| `quickpnl.gui` | Yes | Shared runtime layout rules. |
| `saveload.gui` | Yes | Shared runtime layout rules. |
| `savename.gui` | Yes | Shared runtime layout rules. |
| `scriptselect.gui` | No | Character-script row centering migration pending. |
| `skchrgen.gui` | Yes | Shared runtime layout rules. |
| `skillinfo.gui` | No | Skill-list row fitting pending. |
| `splashscreen.gui` | Yes | Shared runtime layout rules. |
| `startscreen.gui` | No | Original game file, absent from size archives; audit pending. |
| `statussummary.gui` | No | Absent from size archives; existing runtime placement needs an audit. |
| `store.gui` | No | Store-list row fitting pending. |
| `titlemovie.gui` | Yes | Shared runtime layout rules. |
| `tooltip10x8.gui` | No | Tooltip variant migration pending. |
| `tooltip12x9.gui` | No | Tooltip variant migration pending. |
| `tooltip16x12.gui` | No | Tooltip variant migration pending. |
| `tooltip6x4.gui` | No | Tooltip variant migration pending. |
| `tooltip8x6.gui` | No | Tooltip variant migration pending. |
| `top.gui` | Yes | Menu tab strip and LT/RT cues. |
| `upgrade.gui` | Yes | Shared runtime layout rules. |
| `upgradeitems.gui` | No | Upgrade-item row fitting pending. |
| `upgradesel.gui` | Yes | Shared runtime layout rules. |

Recount with the inventory command in section 8 after each migration; update
the table status, numerator and percentage together.

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
| frame | `(v - b) * a + b`, `a = W/BW` for LEFT/WIDTH, `H/BH` for TOP/HEIGHT | class selection's enlarged model and first class button |

For `frame`, `b` is -10 for a position and +20 for a dimension. Its
`frame_inclusive` variant uses +21 for HEIGHT: the first class button is exactly
21 px taller than the other class buttons in all 66 sets, measured by reading
their extents. Only class selection currently considers these rules when fitting
fields; the previously migrated 44 screens keep exactly their old rule tables.

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

For the frame rules the fixed margin is kept outside the gold ratio:
`placed = round((gold - b) * (r - b) / (r_gold - b) + b)`, except where gold
already equals the rounded rule. If `r_gold == b`, use `round(r + gold - r_gold)`.
All older rules have `b = 0`, so their calculation is unchanged. Multiplying the
margin itself by the gold ratio was rejected: at 15360x8640 the first class
button's height missed the existing set by 8 px. The 21 px inclusive height
margin reduces that difference to the accepted rounding allowance.

Class selection examples, read back from the Python live layout (LEFT, TOP, WIDTH,
HEIGHT). The 1920x1080 set has 672 rather than 673 for the first button's height;
the 15360x8640 set has 1480 and 5232 rather than 1482 and 5235 for its left and
height. The gold size is identical in every field.

| Size | First class button | First model | Cancel, also used by the controller split |
| --- | --- | --- | --- |
| 800x600 | 77,118,114,383 | 81,154,106,254 | 311,513,178,35 |
| 1280x720 | 124,118,170,456 | 129,187,158,301 | 498,615,284,42 |
| 1920x1080 | 185,118,245,673 | 194,285,227,441 | 747,923,426,63 |
| 3440x1440 | 332,118,423,890 | 348,383,391,581 | 1338,1230,763,84 |
| 15360x8640 | 1482,118,1820,5235 | 1554,2348,1676,3386 | 5976,7380,3408,504 |

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
| `classsel.gui` | the game's own, with the frame rules and gold's alignment/border corrections | the player's file at the game's base size; replacement border art is preserved |
| `abilities.gui`, `top.gui` | the game's own, with row fitting and the added cues below | the player's file, with cues added where their controls support them; existing cues preserved |
| `optgameplay.gui`, `optfeedback.gui` | the game's own, with the Controller Layout entry or scaled checkbox row template | the player's file, retaining button styling and custom row height; existing entry preserved |

"Laid out for the game's size": its base (section 2) is the game's file's and its root lies
inside it. A mod's file laid out for 1920x1080 is refused (`Test-LiveLayout.py` part 4).

**Fields.** Only these change, in place; every other byte of the source is kept:

| Field | Value |
| --- | --- |
| every `EXTENT` (root, controls, `PROTOITEM`, `SCROLLBAR`) | section 2: the table's rule and gold for a structure the game's file has with the same TAG and the same extent; the table's rule without gold where the source moved it; the default rule for a TAG the table does not have (an untagged control is keyed by its place, `#index`) |
| `PADDING` of a list box (CONTROLTYPE 11) | the build's gutters, at `max(1, H / 720)`: 36 per unit for `LB_DESC`, `LB_DESCRIPTION`, `LBL_ITEM_DESCRIPTION`, `LB_ITEM_DESCRIPTION`, `LB_DESC_LS`; 12.5 for `LB_ITEMS`, `LB_ABILITY`, `LB_FEATS`, `LB_POWERS`, `LB_SHOPITEMS`, `LB_INVITEMS`; never reduced; then the per-file hand-set ones, which may reduce; rounded half to even (`prepare_universal_resources.py` `DESCRIPTION_LISTBOXES`, `LIST_LISTBOXES`, `HAND_TUNED_GUTTERS`, copied into the table by the script) |
| `PADDING` the gold file sets by hand | at 3440x1440 only, before the gutters: `optresolution.gui`'s resolution list, 20, and `optionsmain.gui LB_DESC`, 40, which the gutter then raises to 72 as in the set |
| `TEXT.ALIGNMENT` the gold file changes | at every size, where the file has the game's own alignment there, as `transfer_gold_gui_geometry.py` carries it: Character's `LBL_LEVEL`, 12 to 10 |
| class selection's cleared `BORDER` and `HILIGHT` `CORNER`/`EDGE` resrefs | six class buttons, four fields each (24 fields); cleared only where the source still names the game's own art. A mod's different art is kept. The C redirects each field to an existing empty resref encoding, leaving shared value bytes intact |
| a list made as tall as whole rows | after the gutters, `scale_listbox_padding.py` `fit_list_to_rows` for the lists of `ROW_LISTS` on these screens: Equipment's `LB_ITEMS`, rows of 56 at `max(1, H / 720)` in single precision, rounded half to even, each an eleventh of a row apart; a screen's list only shrinks, when a kind of row sits looser than an eighth of a row (at 1024x576, 336 to 313 px) |
| the R3 cue, `LBL_KMRPR3` | added last on Inventory, Equipment and Character, as `prepare_universal_resources.py` `add_party_switch_cue` adds it: a clone of the file's first label with the tag, the next free ID, the picture `kmrprb_party` and no frame or text, its side 90% of the portraits' height, centred in their gap when the gap holds it with a tenth of it free each side, else a third of it right of the second portrait. Left out, as the build would stop, where it would leave the panel or cover a button, check box, slider, scroll bar, progress bar or list, where `BTN_CHANGE1` or `BTN_CHANGE2` is missing or they overlap, or where the label it is cloned from lacks a field it sets |

**Why the cue.** With KMRP installed the controller patch takes its own copies of the
game's layouts out of its folder (`LeaveLayoutsToKmrp`, `K1ControllerStandalone.cpp`), and
KMRP's layouts must carry the controls it adds: on these four party screens, the cue its R3
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

**Abilities and the menu strip (2026-10-29).** The same append writer now accepts
each cue's tag, fill and rectangle. Abilities fits `LB_ABILITY` to 50-unit rows
using the existing screen-list rule, adds the party cue, then adds `LBL_KMRPSWAP`.
The swap cue clones `BTN_SKILLS`; its height is the maximum of Skills/Powers/Feats,
its width twice that height, its left is `Close.left - height//3 - width`, and
its top is `Close.top + (Close.height-height)//2`. Missing controls, an unsuitable
template, no room left of Close or overlap with a clickable control/another cue
omit this added cue. Mod controls and existing cues remain in the layout.

`top.gui` adds `LBL_KMRPLT` and `LBL_KMRPRT`. Sort the eight tab rectangles by
`(left, top, width, height)`, take the first tab's height `s` and gap `s//3`.
The left cue's left is `first.left - gap - 2*(s//2)`; the right cue's left is
`last.left + last.width + gap`. Both have the first tab's top and size `s`.
This retains the build's odd-size rounding. Clone the first plain label, or
`BTN_EQU` when there is none; each new ID follows the highest existing ID.
If either cue already exists or any tab is absent, leave the pair as supplied.
The live source and Python reference use the build's same template requirements.

Read back from the C helper's output on 2026-10-29; coordinates are panel-relative
`left, top, width, height`. The regression compares all fields with the Python
build functions, including cloned text, border data and IDs.

| Size | `LB_ABILITY` | Swap cue | LT cue | RT cue |
| --- | --- | --- | --- | --- |
| 800x600 | 67,284,336,215 | 438,519,46,23 | 30,54,50,50 | 720,54,50,50 |
| 1920x1080 | 162,511,807,387 | 1084,934,82,41 | 131,97,90,90 | 1700,97,90,90 |
| 3440x1440 | 290,681,1445,516 | 1986,1245,108,54 | 316,129,120,120 | 3005,129,120,120 |
| 3840x2160 | 324,1022,1613,774 | 2169,1867,162,81 | 261,194,180,180 | 3400,194,180,180 |

Both mouse/keyboard and controller modes read this geometry. The controller's
existing bindings control cue visibility, family art and input; these additions
do not move input handling into KMRP. Standalone controller sizing is unchanged.
The two migrated screens have not yet been play-tested.

The 45 preceding screen-rule tables are byte-for-byte unchanged (compared with
`6b4b17f`); only the two tables, cue constants, row-list entry and Abilities'
party-screen entry are added. Both Windows module builds, core/controller
package regressions and the controller worker/preload check pass. No full
installer rebuild or live-game install was performed for this migration.

**Gameplay and Feedback Options (2026-10-29).** Gameplay repeats
`build_controller_layout.py` `add_entry`. Clone `BTN_KEYMAP` as `BTN_KMRPLAY`,
with the next ID and caption `Controller Layout`, retaining its border, hilight,
font and text alignment. Let `step = Keymapping.top - Mouse.top`, or
`round(Keymapping.height * 1.175)` if Mouse is absent; rounding is half to even.
Lift Mouse, Keymapping and the new entry by `step//2`; the entry's initial top is
`Keymapping.top + step`. Existing `BTN_KMRPLAY` skips both insertion and lifting.
If Keymapping or its required template fields are missing, omit the added entry.
The append writer publishes the changed buffer only after the clone and original
button extents are available, so failure cannot leave a partially lifted stack.
The native Keymapping button has `TEXT.STRREF=48142` without a `TEXT.TEXT`
string. The clone adds the missing string field (reusing the existing `TEXT`
label), sets STRREF to `0xFFFFFFFF`, and leaves the original localized caption
unchanged. An initial requirement for an existing string field omitted the entry
in all 66 sets; the structure comparison caught it before any installation.

Feedback repeats `scale_listbox_padding.py` `scale_row_template`: after the
ordinary live geometry/gutters, change only `LB_OPTIONS.PROTOITEM.EXTENT.HEIGHT`
to `round(float32(template * max(1, float32(H/720))))`. Keep the prototype's
left, top and width. A mod's different height is the input to this rule; it is
not replaced with vanilla's 43. Missing list/prototype geometry skips this step.
This preserves the correction of the older broken prototype-fitting approach
recorded in section 7 and the agent memory; it does not fit prototypes to their
parents or introduce double text scaling.

The `ENTRY_*` values now have named definitions in the existing Python build
function and are emitted into the C header, alongside the Feedback list name.
No input binding is added to KMRP: the controller's existing Gameplay handler
binds the new tag, corrects its live placement and opens its independent screen.
Both input modes use the same file geometry. Native visual verification of
these two migrations is pending.

Read back from compiled C output on 2026-10-29. Gameplay coordinates are the top
of Mouse, Keymapping and Controller Layout; the new entry keeps Keymapping's
left/width/height. Feedback's prototype left/top/width remain `76,90,240`.

| Size | Mouse TOP | Keymapping TOP | Controller Layout TOP | New entry LEFT,WIDTH,HEIGHT | Feedback prototype HEIGHT |
| --- | --- | --- | --- | --- | --- |
| 800x600 | 397 | 431 | 465 | 75,300,29 | 43 |
| 1920x1080 | 715 | 776 | 837 | 180,720,52 | 64 |
| 3440x1440 | 953 | 1034 | 1115 | 323,1290,69 | 86 |
| 3840x2160 | 1430 | 1551 | 1672 | 360,1440,104 | 129 |

The focused regression passes 7,392 extent fields against all 66 sets (95.22%
exact, 3.98% one pixel off, 59 further within the unchanged allowances), exact
at 3440x1440. C/Python agree on 540 layouts and refuse two hires files. Another
36 option-mod layouts cover custom borders/fonts/high IDs, missing Mouse,
reversed column pitch, existing entries, missing required fields and a custom
57-pixel Feedback row, which becomes 86 at 1080p without changing its width.

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
sets themselves are not changed; their copies of these 49 files are still made and simply
no longer what the game reads. `KmrpRuntimeLayoutFile` returns the roster folder's file
first, so the module's own readers of these layouts see the laid-out one. Among the first 44, the
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

- Current set comparison (2026-10-29): **49 screens, 259,248 extent fields**
  against all 66 sets, 94.44% exact, 5.33% one pixel off, 608 further within the
  existing allowances. At 3440x1440 every extent is identical. C and Python agree
  on **13,226 layouts** and refuse 49 files laid out for a different resolution.
  The cue-mod check passes another 36 layouts, including moved tabs, missing controls,
  blocked swap placement, retained mod cues, a template without an ID and a
  tab-strip file without any plain label. Another 36 option-mod layouts pass.
  The preceding 47-screen run covered 12,686 C/Python layouts and 47 refused hires
  files; Gameplay/Feedback's focused check covers 540 layouts and two refusals.
  Both Windows module builds, package regressions and the controller preload
  regression pass. No installer rebuild or live installation was performed.
  The maintainer accepted the batch on 2026-10-29: "works commit and push".
  The installed build and resolution for that report were not recorded.

- Class selection (added 2026-10-29): against the 66 sets, 4,752 extent fields,
  4,434 exact, 308 one pixel off, 10 two or three pixels off; 3440x1440 identical.
  Its `LBL_CLASS` alignment is carried from 10 to 18. Its layout migration has
  **not yet been play-tested**, including the existing controller split artwork.

- **Seen in the game at 3440x1440 only.** The maintainer opened the options screens from
  the main menu and the pause menu in their Steam game with the module above on 2026-10-28:
  "works perfectly". Every other size, and a mod's file in `Override`, is verified by
  `Test-LiveLayout.py` (against the build's sets and between Python and C), not by looking
  at the game. (When first written that day this said nothing had been seen yet.)
  Inventory, Equipment and Character, and the R3 cue as they place it, were seen in the
  maintainer's game at 3440x1440 the same day (8ddb433), through the day's play tests of
  those tabs.
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

- The 30 screens added after the first 14 also carry gold's border fill style where it
  changed one (Pazaak's `BTN_PLRSIDE1`, 1 to 2), as its alignment is carried. Before class selection was added,
  `Test-LiveLayout.py` covered 44 screens: 235,752 `EXTENT` fields, 94.58% exact, 5.23% a
  pixel off, 449 further, 3440x1440 identical; a value gold moved far may be off by the
  rounding allowance times gold's move (the Galaxy Map's `LBL_Live01`, 2.7 times, 6 px at
  15360x8640). Screens without controls are laid out and compared, with no mod's file.
  Seen in the game: not yet.
- **Correction, 2026-10-29:** class selection no longer waits for a rule. The earlier
  description of its buttons as about `0.117 W + 20` was incomplete: the first button
  keeps a 20 px width margin and a 21 px height margin; the first model also needs
  fixed position/dimension margins. Those fields now use the frame rules above.
  `startscreen.gui` is in no set; the build ships the game's own. `dialog.gui`,
  `pause.gui`, `partyselection.gui` and `statussummary.gui` wait for a check against the
  module's own code that places them at run time.
- **Correction, 2026-10-29:** Abilities and the menu strip no longer wait for their
  build steps. The live writer now repeats row fitting and all four added cues
  described in section 3. Every other screen still comes from the size's set.
  Gameplay and Feedback now repeat their build steps too, as recorded above.
  Next: `confirm.gui`
  (KMRP's own popup), `map.gui`, the container, the other row-fitted lists, and the HUD
  (`apply_proportions`).
- The sets keep their copies of the 49 files; removing them from the bank is a size change
  for later.
- The Mac does not call `KmrpLiveLayout` yet ([handoff item 102](macos-handoff-1.5-to-1.6.md)).
- No byte of the executable.

## 8. Verifying by hand

```
python tools\build_live_layout.py --check
python testing\regression\Test-LiveLayout.py
# Focus one migration; the table and both cue/options mod suites still run:
python testing\regression\Test-LiveLayout.py --screens optgameplay.gui optfeedback.gui
```

The test needs `build\kmrp\resources` (a build's 66 sets), `build-inputs\vanilla-gui` and
clang (LLVM) on the `PATH`. To lay one screen out by hand with the C:

```
clang -O2 -o kmrp-guiadapt.exe macos\tools\kmrp-guiadapt.c
kmrp-guiadapt.exe live build-inputs/vanilla-gui/optionsmain.gui optionsmain.gui 1920 1080 out.gui
python tools\dump_gui_extents.py out.gui
```

To recount the coverage inventory, run this Python from the repository root with
the original GUI inputs and generated resource archives available. It lists the
same union and checks implementation against `FILES`, without importing builders:

```python
import ast
from pathlib import Path
from zipfile import ZipFile

inventory = {p.name.lower() for p in Path("build-inputs/vanilla-gui").glob("*.gui")}
for archive in Path("build/kmrp/resources").glob("gui-*.zip"):
    with ZipFile(archive) as files:
        inventory.update(Path(n).name.lower() for n in files.namelist()
                         if n.lower().endswith(".gui"))
tree = ast.parse(Path("tools/build_live_layout.py").read_text())
definition = next(n for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "FILES" for t in n.targets))
implemented = set(ast.literal_eval(definition.value))
assert implemented <= inventory
for name in sorted(inventory):
    print(name, "Yes" if name in implemented else "No")
print(f"{len(implemented)}/{len(inventory)} = {100 * len(implemented) / len(inventory):.2f}%")
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
