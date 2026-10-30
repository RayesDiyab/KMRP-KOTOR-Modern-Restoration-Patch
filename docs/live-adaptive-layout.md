# Live Adaptive Layout: screens laid out at run time from the file the game would load

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it: measured claims only, every site
> tabulated, rejected alternatives and corrections kept visible, and anything untested
> labelled as untested.

**Kind: reference.** What the code does now. The controller patch's part of the same
plan, every picture drawn at the size it is shown, is
[controller-live-adaptive-layout.md](controller-live-adaptive-layout.md).

**Status: complete on Windows (2026-10-30, the maintainer: "mark it complete").** Every one
of the 85 layout files has its status and none is pending: 73 laid out here, 3 placed at
run time by other code (the HUD's table, the status summary's), 8 never loaded, 1 KMRP's
own. Seen in the Steam game at 3440x1440 batch by batch. Still open: the Mac does not call
it yet ([handoff item 102](macos-handoff-1.5-to-1.6.md)), and the 66 sets still carry their
copies of these files (section 7).

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
Options (`optgameplay.gui`, `optfeedback.gui`), making 49 screens. On 2026-10-30 the
nine screens whose lists the build fits to their rows join them (Terminal, Container,
Feats, Journal, Powers, Script Selection, the granted skill popup, Store and the
workbench's item list), making 58 screens; the same day the pause notice (`pause.gui`)
and party selection (`partyselection.gui`) follow, making 60, and then the five
tooltip files, making 65, the main menu's five files, making 70, and then the message
popup, the area map and the conversation box, making **73 screens**. The HUD's two loaded
files are placed at run time by the HUD's own table instead (`K1PcHud.cpp`), the status
summary is laid out in code each time it opens, seven HUD files and `startscreen.gui` are
never loaded with KMRP installed, and `kmrplayout.gui` is KMRP's own screen (2026-10-30,
coverage inventory).
**Coverage: 73 / 85 layout files in the shared path (85.88%); 76 / 85 laid out at run
time (89.41%); 8 never loaded; 1 KMRP's own; none remain.** The
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
| Source | master `86ee647` with the path handling of 2026-10-30 (uncommitted when written) |
| Module (73 screens, any path) | `build\native-runtime\kmrp-native.dll`, 884,224 bytes, SHA-256 `97E5DE246601EB368D2427C6B8C51226A4F0469D9AFA166223F2E899A8801EA5`, with the controller module from the same source (2,721,792 bytes, `2A04EF18F24AB2FFAA613F0427EB942A0AAE4244083AC4495D111F868B767570`); section 6, "Paths" |
| Previous module (73 screens) | 881,664 bytes, SHA-256 `5E61BDE801B6331967BDFFE39551F2BC98A6FFED94F5FD348ECB3DE65CD087CA`; installed in the Steam game 2026-10-30 for the maintainer's test, with the controller module from the same source (2,722,816 bytes, `FC057B85D2E53E08CFD3B7F27E4A57FD2ED825978FBE8B068CAB7FCCADCC6F08`) |
| Previous module (70 screens) | 870,912 bytes, SHA-256 `659BF0E9A1F9267E70740CB4D90216F70451998008965210575BF0E14A6E4331`, with the controller module `C57CDEC3CB93EC8333989D844036A9B232F52594123385329669082398431B8D`; seen in the game 2026-10-30 ("Both look right"), committed as `a314a6d` |
| Withdrawn module (70 screens, first centre rule) | `BF8BB39C445D5E650F847B47C9A4473B8AB224C1627F0CEAEC0CD69B0AE5CBFB`: carried the centre for every kept-shape control, which failed 295 fields; installed for a short while the same day, replaced by the one above |
| Previous module (65 screens, HUD cues) | 865,280 bytes, SHA-256 `506B380E4AAA95ACD35A9BC06E49C2D95B38799045563E017FEA329D9D0BEAC0`, with the controller module `28F2046EFC28B190B0D50037B685B53357F489A7067BABAB79EF54382E4D2D02`; committed as `94259de` |
| Previous module (65 screens) | 860,672 bytes, SHA-256 `B2C2C639C7A40B3AF85CD45544926873B60BD8AFFE3CB6A3DC86A465F5FC566D`, with the controller module `4B1A279104DA41814AF3C438A04594DCDE048D2B2288C79C1C6C1D589039F922`; installed and seen in the game 2026-10-30 ("it works", the HUD's tooltips) |
| Previous module (60 screens) | 860,160 bytes, SHA-256 `D074F8E673736A2D6C5885F83E3CCF54648E2D10614F0CFCA1DF36068BEEEA00`, with the controller module `D1DDDB2DFECC6C403B6362A1C8EBA72A79EA3245475911E8873DD6D20CC1E8BF`; installed and seen in the game 2026-10-30 ("looks good") |
| Previous module (58 screens) | 856,064 bytes, SHA-256 `47FEE683DE0BC7304078D62EFFA0ECE7AC3061471D506A87BA84DF7668725910`, with the controller module `795C4355FCC5B5B78C7CE6D24C01C52AEF41A7BAC4993A445FFCC100255FAC51`; installed and play-tested 2026-10-30 ("all works perfectly") |
| Previous module (49 screens) | 846,336 bytes, SHA-256 `F842D1C5F1A3DC943CB7514D7C38710BADEA5E139FDB9FE2090063E03E08939D`; installed in the Steam game 2026-10-30 |
| Previous module (47 screens) | 842,240 bytes, SHA-256 `C388D0DA3ED09D656EAA70996BB6AD51312CA968980A78E834D301A834380793` |
| Previous module (45 screens) | `build\native-runtime\kmrp-native.dll`, 837,632 bytes, SHA-256 `DE6FD58D9F8C9C3B5AA6F56C03EC4EE5BCFD52CE7C5840F4066D5300DDEA7541` |
| Previous module | the 14-screen build was 759,296 bytes, SHA-256 `ACA3146F97263EEDAE09BF84C0CDDF0EE75446BBD762D7BA376176A6CDC07132`; the options-only build was 744,448 bytes, `BD9742A55E7788CD82E8D7E964EC5DBE692D5C96AAD5B5DEDE293DC2BAB12DB4` |
| Table | `macos/tools/kmrp-livelayout-table.h`, made by `python tools/build_live_layout.py` |
| Executable | not changed: this writes layout files, no byte of `swkotor.exe` |

## Coverage inventory

**73 / 85 GUI layout files implemented in the shared path: 85.88%.**
**2 / 85 placed at run time by the HUD's own table (HUD table) and 1 / 85 laid out in code
each time it opens (Run-time code): 76 / 85 laid out at run time, 89.41%.**
**8 / 85 never loaded with KMRP installed (Not loaded); 1 / 85 KMRP's own screen (KMRP's own).**
**0 / 85 remain** (2026-10-30).

Measured on 2026-10-29 against source `a9419f6`, and the numerator again on 2026-10-30
after the row-fitted lists (the denominator unchanged): the denominator is the union of
84 original files in `build-inputs/vanilla-gui` and 83 distinct `.gui` names across
all 66 `build/kmrp/resources/gui-*.zip` archives. Their union contains 85 names:
the archives add `kmrplayout.gui`, while `startscreen.gui` and `statussummary.gui`
occur only in the original-file inventory. The numerator is membership in
`tools/build_live_layout.py` `FILES`. Percentage is `100 * 73 / 85`, rounded to
two decimal places. Every name is listed once below.

**Status definition:** Yes means the file is implemented in the shared
`KmrpLiveLayout` path. HUD table (since 2026-10-30) means the file the game loads is
used as it is, a mod's included, and every control is placed for the screen and HUD
Size by the module's own table (`K1PcHud.cpp`, `docs/hud-size-options.md`): the same
outcome by another route. Not loaded means the game never loads the file with KMRP
installed, so there is nothing to lay out (for `startscreen.gui`: its name is not in the
executable). Run-time code (since 2026-10-30) means the game and KMRP's module lay the
screen out in code each time, whatever the file says. KMRP's own means KMRP's own screen,
made for every size by its build, which no game or mod file replaces. No means migration,
integration or an explicit audit is still pending; since 2026-10-30 no file is No. A No does not mean the screen is broken or has no runtime sizing:
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
| `computer.gui` | Yes | Shared rules and its hand-set list gutters. |
| `computercamera.gui` | Yes | Shared runtime layout rules. |
| `confirm.gui` | Yes | Gold at 3440x1440 only (`GOLD_GEOMETRY_EXCLUDED`); the measured popup table by the font scale (`apply_tuned`); `LBL_KMRPA` cloned from the size's `kmrplayout.gui`. |
| `container.gui` | Yes | Popup list fitted to rows; column widened for the Give Items caption the size's prompt manifest gives. |
| `credits.gui` | Yes | Shared runtime layout rules. |
| `custpnl.gui` | Yes | Shared runtime layout rules. |
| `debug.gui` | Yes | Shared runtime layout rules. |
| `dialog.gui` | Yes | Upstream ships none: every field the game's own (fixed), gold's at 3440x1440 only, as the build has it (`vanilla_dialog_gui`); `LBL_KMRPDLG` cloned from the size's `kmrplayout.gui`. The module places the box at run time. |
| `equip.gui` | Yes | Shared runtime layout rules. |
| `fade.gui` | Yes | Shared runtime layout rules. |
| `ftchrgen.gui` | Yes | Feat list fitted to rows. |
| `galaxymap.gui` | Yes | Shared runtime layout rules. |
| `inventory.gui` | Yes | Shared runtime layout rules. |
| `journal.gui` | Yes | Quest row template sized for six rows. |
| `kmrplayout.gui` | KMRP's own | KMRP's Controller Layout screen, made for every size by its build (`build_controller_layout.py`) and loaded by KMRP's module; no game or mod file of it exists to adapt. |
| `leveluppnl.gui` | Yes | Shared runtime layout rules. |
| `loadscreen.gui` | Yes | Shared runtime layout rules. |
| `maincg.gui` | Yes | Shared runtime layout rules. |
| `maininterface.gui` | Yes | Shared runtime layout rules. |
| `mainmenu.gui` | Yes | Shared rules (a kept-shape control's centre carried by gold); then `AdaptMainMenuK1` puts the buttons on the bars of their art, from this result. |
| `mainmenu10x7.gui` | Yes | Shared rules (a kept-shape control's centre carried by gold); then `AdaptMainMenuK1` puts the buttons on the bars of their art, from this result. |
| `mainmenu12x9.gui` | Yes | Shared rules (a kept-shape control's centre carried by gold); then `AdaptMainMenuK1` puts the buttons on the bars of their art, from this result. |
| `mainmenu16x12.gui` | Yes | Shared rules (a kept-shape control's centre carried by gold); then `AdaptMainMenuK1` puts the buttons on the bars of their art, from this result. |
| `mainmenu8x6.gui` | Yes | Shared rules (a kept-shape control's centre carried by gold); then `AdaptMainMenuK1` puts the buttons on the bars of their art, from this result. |
| `map.gui` | Yes | Gold at 3440x1440 only (`GOLD_GEOMETRY_EXCLUDED`); `LBL_Map` from the screen's size (`map_control_box`). |
| `messages.gui` | Yes | Shared runtime layout rules. |
| `mi8x6.gui` | Not loaded | The Xbox game's HUD; the PC game never loads it (the HUD's constructor, 0x0068C4D5, picks only `mipc*`). The Xbox-style HUD's table is built from it (`tools/build_xbox_hud.py`). |
| `mipc10x7.gui` | Not loaded | Never loaded with KMRP: its HUD selector loads only `mipc210x7` and `mipc28x6` (binary inventory 5.4). A mod's copy is still given the combat cues. |
| `mipc12x9.gui` | Not loaded | Never loaded with KMRP: its HUD selector loads only `mipc210x7` and `mipc28x6` (binary inventory 5.4). A mod's copy is still given the combat cues. |
| `mipc16x12.gui` | Not loaded | Never loaded with KMRP: its HUD selector loads only `mipc210x7` and `mipc28x6` (binary inventory 5.4). A mod's copy is still given the combat cues. |
| `mipc210x7.gui` | HUD table | Loaded (`mipc210x7` at 3440 wide, `mipc28x6` elsewhere: KMRP's selector, binary inventory 5.4) and placed at run time by the HUD's own table (`K1PcHud.cpp`, since 2026-10-18), the combat cues included since 2026-10-30; a mod's copy is given the cues (`KmrpHudCues`). |
| `mipc212x9.gui` | Not loaded | Never loaded with KMRP: its HUD selector loads only `mipc210x7` and `mipc28x6` (binary inventory 5.4). A mod's copy is still given the combat cues. |
| `mipc216x12.gui` | Not loaded | Never loaded with KMRP: its HUD selector loads only `mipc210x7` and `mipc28x6` (binary inventory 5.4). A mod's copy is still given the combat cues. |
| `mipc28x6.gui` | HUD table | Loaded (`mipc210x7` at 3440 wide, `mipc28x6` elsewhere: KMRP's selector, binary inventory 5.4) and placed at run time by the HUD's own table (`K1PcHud.cpp`, since 2026-10-18), the combat cues included since 2026-10-30; a mod's copy is given the cues (`KmrpHudCues`). |
| `mipc8x6.gui` | Not loaded | Never loaded with KMRP: its HUD selector loads only `mipc210x7` and `mipc28x6` (binary inventory 5.4). A mod's copy is still given the combat cues. |
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
| `partyselection.gui` | Yes | Shared rules; left to `AdaptPartyRosterK1` while the 32-slot roster is active. |
| `pause.gui` | Yes | Shared rules; the module's `Pause` then places it under the live menu row. |
| `pazaakgame.gui` | Yes | Shared runtime layout rules. |
| `pazaaksetup.gui` | Yes | Shared runtime layout rules. |
| `pazaakwager.gui` | Yes | Shared runtime layout rules. |
| `portcust.gui` | Yes | Shared runtime layout rules. |
| `pwrlvlup.gui` | Yes | Power list fitted to rows. |
| `qorcpnl.gui` | Yes | Shared runtime layout rules. |
| `questitem.gui` | Yes | Shared runtime layout rules. |
| `quickpnl.gui` | Yes | Shared runtime layout rules. |
| `saveload.gui` | Yes | Shared runtime layout rules. |
| `savename.gui` | Yes | Shared runtime layout rules. |
| `scriptselect.gui` | Yes | Script rows centred in the art's frame (list PADDING). |
| `skchrgen.gui` | Yes | Shared runtime layout rules. |
| `skillinfo.gui` | Yes | Popup skill list fitted to rows. |
| `splashscreen.gui` | Yes | Shared runtime layout rules. |
| `startscreen.gui` | Not loaded | Its name is in neither the executable (0 matches, 2026-10-30) nor the decompilation: the game never loads it. |
| `statussummary.gui` | Run-time code | The game lays the box out in code each time it opens (0x00625C60) and KMRP's module again each frame, scaled to the font (`layoutStatusSummary`, `K1ControllerLayout.cpp`); the file's numbers never reach the screen. |
| `store.gui` | Yes | Both item lists fitted to rows. |
| `titlemovie.gui` | Yes | Shared runtime layout rules. |
| `tooltip10x8.gui` | Yes | Shared runtime layout rules. |
| `tooltip12x9.gui` | Yes | Shared runtime layout rules. |
| `tooltip16x12.gui` | Yes | Shared runtime layout rules. |
| `tooltip6x4.gui` | Yes | Shared runtime layout rules. |
| `tooltip8x6.gui` | Yes | Shared runtime layout rules. |
| `top.gui` | Yes | Menu tab strip and LT/RT cues. |
| `upgrade.gui` | Yes | Shared runtime layout rules. |
| `upgradeitems.gui` | Yes | Item list fitted to rows. |
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
| `computer.gui`, `container.gui`, `ftchrgen.gui`, `journal.gui`, `pwrlvlup.gui`, `scriptselect.gui`, `skillinfo.gui`, `store.gui`, `upgradeitems.gui` | the game's own, with the build's row steps below | the player's file, the same steps where its controls have what they need; a step it cannot take is left out |
| `pause.gui` | the game's own, by the rules and gold alone; the module's `Pause` (`K1TextLayout.cpp`) then places the notice under the live menu row, its margins read from this file | the player's file, the same |
| `partyselection.gui` | the game's own, by the rules and gold alone; **not written while the 32-slot roster is active**, whose file `AdaptPartyRosterK1` builds from the set's layout just before and keeps (`managedPartyRoster`) | the same, or the roster's file |
| `mainmenu.gui`, `mainmenu8x6.gui`, `mainmenu10x7.gui`, `mainmenu12x9.gui`, `mainmenu16x12.gui` | the game's own, by the rules and gold; then `AdaptMainMenuK1` puts the five buttons on the bars of their art (`KmrpMainMenuBars`) from this file | the player's file, laid out the same; the bars are KMRP's art's, so a mod's file keeps its own button places, as before |
| `galaxymap.gui` (since 2026-10-28) | the game's own, by the rules and gold; then `AdaptGalaxyMapK1` puts the planets and Live slots where the game's own 640x480 layout has them (issue 67), from this file | the same, the mod's destinations placed |
| `mipc*.gui` (the HUD) | nothing: the set's file is used, and the module's table places the HUD (`K1PcHud.cpp`) | the player's file **as it is**, with KMRP's two combat cues added when it lacks them (`KmrpHudCues`: `add_combat_cues`'s rule, clones of `LBL_QUEUE1`); not laid out, because the table places every control, the cues included |

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
| Script Selection's `LST_AIState` `PADDING` | after the gutters, `scale_listbox_padding.py` `centre_rows_in_frame`: the rows centred in the box `lbl_char_scr.tpc` draws at 302.5/2868 and 1409/2868 of the screen width, from the list's own left, width and scroll bar width, rounded half to even, kept within 0 to 255 and half the content width. A list with no `PADDING` field keeps none (the C adds no fields) |
| the Journal's `LB_ITEMS` `PROTOITEM` HEIGHT | then `fit_rows_to_list`: the largest row template whose six rows fill the list, each an eleventh of a row apart, at `max(1, H / 720)` in single precision; left alone where six rows would not fit |
| a list made as tall as whole rows | after the gutters, `scale_listbox_padding.py` `fit_list_to_rows` for the lists of `ROW_LISTS`: Equipment's, the Container's, the workbench's and the Store's two lists (rows of 56), the Feats, Powers, Abilities and granted skill lists (rows of 50), at `max(1, H / 720)` in single precision, rounded half to even, each an eleventh of a row apart; a screen's list only shrinks, when a kind of row sits looser than an eighth of a row (at 1024x576, Equipment's 336 to 313 px); a popup's (the Container, the granted skill popup) grows or shrinks and moves what is below it, its panel kept centred |
| the Container's panel and column widths | last, `prepare_universal_resources.py` `widen_container`: widened by an even number of pixels about its centre until `BTN_GIVEITEMS` holds its caption and badge (`badge_fit_width`); `LBL_MESSAGE`, `LB_ITEMS`, `BTN_OK`, `BTN_GIVEITEMS` and `BTN_CANCEL` widen with it. The caption's width is the `kmrpx_contgive` row of the size's `kmrp_prompts.txt`, the same number the build measured in the size's font; with no manifest the Container is not widened. 43 of the 66 sets are widened, by 6 to 186 px (their manifests' `widened` lines, 2026-10-30) |
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
  Its `LBL_CLASS` alignment is carried from 10 to 18. When written this said its layout
  migration had not been play-tested. **Correction, 2026-10-30:** the maintainer reports
  every one of the 49 screens implemented by then tested in their game ("all implemented
  ones are already tested"); which sizes was not stated.

- The row-fitted lists (added 2026-10-30, uncommitted): the nine screens against the 66
  sets, 32,736 extent fields, 91.36% exact, 8.31% one pixel off, 110 further within the
  allowances; 3440x1440 identical in every extent and `PADDING`. C and Python agree on
  2,430 layouts (each set's own manifest at a set's size, a made-up caption from 100 to
  900 px at the 200 random sizes) and refuse nine files laid out for 1920x1080. Two
  allowances are new, each printed as a note and checked, not assumed:

  | Allowance | Where | Why it is right |
  | --- | --- | --- |
  | Script Selection's `PADDING` 1 to 3 px from the set's, at 33 sizes | `LST_AIState` | each value is `centre_rows_in_frame` of its own list, and the two differ by no more than that list's rounding (its left twice, its width, its scroll bar's width, one for the result). The run time centres the rows for the list as it lays it out |
  | a list's height a whole row from the set's | `ftchrgen.gui` `LB_FEATS` and its scroll bar at 2880x1864 | the rounding pixel before fitting: the set's 1035 px holds 7 rows of 129 with 18 px left, looser than an eighth, and shrinks to 984; the run time's 1036 holds 8 exactly and stays. The test runs the build's own `fit_list_to_rows` on both and requires each result |

  The full 58-screen run the same day passes: 291,984 extent fields against the 66 sets,
  94.09% exact, 5.66% one pixel off, 718 further within the allowances; 3440x1440
  identical; 15,656 C/Python layouts, 58 refused files laid out for 1920x1080, and both
  36-layout mod suites. Both Windows module builds and `Test-OverrideFontMetrics.py`,
  `Test-PartyRosterGui.py`, `Test-KpatchSource.py`, `Test-ControllerKpatch.py`,
  `Test-RuntimeKpatch.py` and `Test-ControllerPreload.py` pass.

  **Not seen in the game.** Built for the user's test; a mod's version of these screens has
  only the automated mod cases (one control moved, one added). **Correction, 2026-10-30:**
  the maintainer play-tested the 58-screen build the same day: "all works perfectly".

- The pause notice and party selection (added 2026-10-30, uncommitted): `pause.gui` 1,056
  extent fields, 91.10% exact, the rest one pixel off; `partyselection.gui` 10,560,
  92.25% exact, 7.65% one pixel off, 10 further within the allowance; 3440x1440 identical
  for both. The full 60-screen run passes: 303,600 extent fields against the 66 sets,
  94.02% exact, 5.74% one pixel off, 728 further within the allowances; 16,196 C/Python
  layouts, 60 refused files laid out for 1920x1080, both 36-layout mod suites. Both
  module builds and seven module/package regressions pass. Seen in the game the same day
  at 3440x1440: the maintainer, "looks good". Not tested: the 32-slot roster's skip
  (`managedPartyRoster`) is by code reading only.

- **Correction, 2026-10-30: live layout undid the galaxy map's planet placement.** From
  `32b426e` (2026-10-28) `AdaptLiveLayoutK1` ran after `AdaptGalaxyMapK1` and wrote
  `galaxymap.gui` over it, so the planets stood where High Resolution Menus put them, not
  where the game's own layout does (issue 67). Measured with the C at 3440x1440: Korriban
  2237, 351 from live layout against 1805, 646 from the galaxy adapter; Tatooine 1760, 677
  against 2161, 406. Since then the module runs the party roster, then live layout, then
  the galaxy map and the main menu on what live layout wrote (`LayoutBase`,
  `K1RuntimeAssets.cpp`). That order, run with the C, gives the galaxy adapter's planets
  and the main menu's barred buttons exactly as from the set at 3440x1440 and 1920x1080,
  and within a pixel at 2560x1440.

- The message popup, the area map and the conversation box (added 2026-10-30, uncommitted).
  `confirm.gui` and `map.gui` are in `GOLD_GEOMETRY_EXCLUDED`: the build gives them gold's
  geometry at 3440x1440 only, and so does live layout now (`gold_size_only`; text alignment
  and the rest stay gold's, which upstream's own files have too). Without that the popup,
  which gold sets left of the middle at 3440x1440 on purpose, was 2,373 px from the set at
  15360x8640. `dialog.gui` has no upstream file: every field is the game's own (fixed)
  but at 3440x1440, as the build has it. Two build steps repeat at run time: the popup's
  measured table by the font scale (`apply_tuned`) and `LBL_Map` from the screen's size; and
  two controller badge labels, `LBL_KMRPA` and `LBL_KMRPDLG`, are cloned from the size's
  `kmrplayout.gui` as the build clones them (the C copies a control **from another file**
  since then: labels found or added, field data copied). Gold's border thickness at
  3440x1440 is carried too (the reply list's, 4 to 8 and 0 to 4). Allowed: the badge label's
  text colour, 0.98 against the set's 250/255, a tenth of a step on a label with no text.
  Focused runs: `confirm.gui` 1,848 extent fields, 99.73% exact; `map.gui` and `confirm.gui`
  together 4,488, 97.68%; `dialog.gui` 1,584, 100%; 3440x1440 identical, C equal to the
  Python at every case. The full run passes: 73 screens, 333,432 extent fields, 94.13%
  exact, 5.64% one pixel off, 755 further within the allowances; 19,706 C/Python layouts
  and the three mod suites, in 4.1 minutes on 16 cores. Both module builds and eight
  module/package regressions pass. Seen in the Steam game at 3440x1440 the same day with the
  module above: the confirmation popups, the area map and a conversation ("All look
  right"). The last three files are done by finding:
  `statussummary.gui` is laid out in code (Run-time code), `startscreen.gui` is never loaded,
  `kmrplayout.gui` is KMRP's own. A side finding, not acted on: the four sized main menu
  files' names are not in the executable either, only `mainmenu` is (0 and 3 matches), so
  the game appears to load `mainmenu.gui` itself, against `build_controller_assets.py`'s
  note; all five are laid out, so nothing depends on it.

- The main menu (added 2026-10-30, uncommitted): the five files. One rule came with it,
  `aspect_centre` (rule 8): a kept-shape control's LEFT carries gold by its **centre**, by
  the width (`aspect_left`), instead of by the left edge, which moved the centre with the
  height too. The logo (`LBL_GAMELOGO`, 870 px square at 3440x1440) was 4 to 9 px from the
  sets at 7680x4320, 8192x4608 and 15360x8640; the sets keep its centre a fixed share of the
  width from the middle at every height (+414.5 px at every 3840-wide size). **Correction,
  the same day:** done first for every kept-shape control gold differs from the rule by, it
  failed 295 fields, the galaxy map's planets and Terminal's icons up to 23 px from the
  sets. The build carries gold to other sizes on each field itself, and only where gold
  differs from upstream's own 3440x1440 value (`transfer_gold_gui_geometry.py`); where it
  does not, the sets keep upstream's places, whose square controls are centred by the
  width. So the rule chooser now gives `aspect_centre` only where gold equals upstream's
  value and carrying the centre reproduces upstream's 48 sets at strictly more sizes than
  the left edge (`aspect_centre_fits`): 18 fields, among them the logo, the main menu's
  `LBL_NEWCONTENT` and `LBL_BW`, Pazaak's card labels and `top.gui`'s `BTN_OPT`. The full
  run then passes: 70 screens, 327,360 extent fields against the 66 sets, 94.05% exact,
  5.72% one pixel off, 755 further within the allowances, 3440x1440 identical; 18,896
  C/Python layouts and the three mod suites. Seen in the Steam game at 3440x1440 with the
  module above, the same day: the main menu and the galaxy map, the planets where the
  game's own layout has them ("Both look right").

- The tooltips (added 2026-10-30, uncommitted): the five files, 2,640 extent fields,
  97.35% exact, the rest one pixel off, 3440x1440 identical. The full 65-screen run
  passes: 306,240 extent fields against the 66 sets, 94.05% exact, 5.72% one pixel off,
  728 further within the allowances; 17,546 C/Python layouts, 65 refused files laid out
  for 1920x1080, both 36-layout mod suites. Both module builds and seven module/package
  regressions pass. Seen in the game the same day at 3440x1440, on the HUD's hover
  tooltips (the medpac slot): the maintainer, "it works". Every control with tooltip
  text shows it through this one panel (`CSWGuiControl::DisplayToolTip`, then the GUI
  manager's tooltip panel, swkotor1-reconstruction `gui_control.cpp`); tooltips over
  objects in the 3D world were not looked at. Measured the same day and left on the sets,
  each needing a step of its own (coverage inventory): the five main menu files, the
  HUD files (`mi8x6`, `mipc*`), `confirm.gui`.
  Audited the same day and left on the sets: `dialog.gui` (upstream ships it in none of
  its 48 sets, so there are no upstream values to choose rules from; every KMRP set adds
  `LBL_KMRPDLG`), `map.gui` (rules alone leave 395 of 2,640 fields far off, up to 2,880 px
  on `LBL_Map`: the build computes the map rectangle per size) and `statussummary.gui` (in
  no set and not in gold).

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

- **Paths (2026-10-30).** Until this date the module gave every path to the C helpers
  (`kmrp-guiadapt`, `kmrp-guiblend`, `kmrp-gameart`, `kmrp-abilityicons`,
  `kmrp-swoophud`) in the system's ANSI code page, and gave up on a path with a character
  that page lacks. KMRP's cache is under `%LOCALAPPDATA%`, so its path holds the Windows
  user name: a player with, say, a Cyrillic or Chinese user name on a Windows set to a
  Western language got no live layout, no per-size set and no KMRP folder given to the
  game, with nothing said. The set copies were no fallback for them: the game itself
  could not be given the folder that holds them.

  Now the helpers take UTF-8 and open every file through `macos/tools/kmrp-path.h`
  (`_wfopen` and `_wmkdir` on Windows, the plain calls on the Mac). The one path that
  must still be in the code page is the folder given to the game's resource manager
  (`RegisterFolder`); for it `Narrow` falls back to the 8.3 short name Windows keeps on
  the system drive, where `%LOCALAPPDATA%` is. A drive without short names (on the test PC
  E: has none, C: has them) still cannot be given to the game under such a name, and the
  module logs that once.

  Checked on the test PC, whose code page is 1256: `KmrpLiveLayoutSet` with UTF-8 paths
  through a folder named `Тест_用户`, the game reached by a junction inside it and the
  1920x1080 set copied into it, wrote `confirm.gui` byte for byte as the plain path does;
  `KmrpGameArt` and `KmrpSwoopHud` made a new folder there and wrote the same 20 files.
  Not tried: a real Windows profile with such a name, in the game.

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
- **Correction, 2026-10-30:** the container and the row-fitted lists no longer wait: the
  nine screens are laid out at run time (section 3). Still from the sets: `confirm.gui`,
  `kmrplayout.gui`, `dialog.gui`, `pause.gui`, `partyselection.gui`, `statussummary.gui`,
  `map.gui`, the HUD files (`mi8x6`, `mipc*`), the main menu files, the tooltips and
  `startscreen.gui`. The Journal's and Script Selection's Close and neighbour buttons
  (`tools/menu_bottom_row.py`) need no step of their own: gold's ratio places them where
  the set has them.
- The sets keep their copies of the 58 files; removing them from the bank is a size change
  for later.
- The Mac does not call `KmrpLiveLayout` yet ([handoff item 102](macos-handoff-1.5-to-1.6.md)).
- No byte of the executable.

## 8. Verifying by hand

```
python tools\build_live_layout.py --check
python testing\regression\Test-LiveLayout.py
# Focus one migration; the table and both cue/options mod suites still run:
python testing\regression\Test-LiveLayout.py --screens optgameplay.gui optfeedback.gui
# Everything again, the cache aside:
python testing\regression\Test-LiveLayout.py --no-cache
```

The test needs `build\kmrp\resources` (a build's 66 sets), `build-inputs\vanilla-gui` and
clang (LLVM) on the `PATH`.

**The test's cache** (since 2026-10-30). A screen that passed is kept in
`build\test-cache\live-layout\screens\NAME.json` with a fingerprint of everything its
checks read: the code (Python by its parsed code, as `tools/source_fingerprint.py` counts
it for `build_kmrp.ps1`; `build_live_layout.py` without its `FILES` list), the C, the
table's shared part and the screen's own rows, its files (the game's, gold's, upstream's 48,
each set's copy and prompt manifest by CRC) and the Python and pykotor versions. While it
still matches, the screen's counts and notes are replayed and its checks skipped; the rules
upstream's sets give each screen (`rules\`) and the three mod suites (`suites\`) are kept
the same way. So adding a screen checks that screen, and a change to shared code or a new
build checks everything. Nothing that failed is kept. Each screen's random Container
captions come from its own seeded stream, so its cases do not depend on which screens ran
before it. The screens left to check run in worker processes, one a core (`--jobs N`, 1
for none): every screen of 70, on 16 cores, in 3.4 minutes against about 18 on one
(2026-10-30, same result).

To lay one screen out by hand with the C:

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
