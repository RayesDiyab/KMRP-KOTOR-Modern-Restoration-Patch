# Universal resolution patching

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


## What this build does

KMRP starts from the supported editable `swkotor.exe`, applies the already play-tested 3440×1440 gold transformation, and then replaces only the verified resolution-dependent values. It also updates `swkotor.ini` and installs the matching high-resolution GUI set plus the shared HD artwork.

The original 3440×1440 patcher is frozen separately as
`D8F0EEBF470660FFBB0DBE9D6953774B937F73F92260FA2D3427189D8B7F6ADE`.

**Selecting 3440×1440 in KMRP no longer reproduces that
historical hash.** The current baseline is `swkotor_gold_v24_movieaspect.exe`
(`9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A`). It
contains the full cumulative gold chain through map-note corrections, Large
Address Aware support and the Bink aspect fit. See `docs/font-scaling.md` and
`reverse-engineering/listbox-geometry.md` for the gold lineage.

**Gold is not what 3440×1440 ships either.** Gold is a fixed snapshot, and some
of its values predate the rules below: its area-map fields are an earlier
model's, and it leaves the list-row sizes at vanilla for the patcher to fill in.
Measured on 2026-09-24 by running the installer (`ECA3DE4B…`) with `--apply` at
all 48 resolutions: the 3440×1440 output differs from gold in 22 bytes across
17 runs, all of them fields in *Executable fields* below.

## Resolution inputs

For a selected screen width `W` and height `H`, the area-map geometry is
(`tools/analyze_resolution_guis.py`, written into `resolutions.tsv`, which the
patcher embeds and reads):

```text
marker_overlay_width  = W // 2
map_canvas_height     = H // 2
marker_overlay_height = map_canvas_height
map_canvas_width      = round(marker_overlay_width × 512 / 440)
centering_domain      = W × H
```

The map picture is drawn on the canvas; the fog grid and the markers live in the
overlay. Only 440 of the map atlas's 512 columns carry picture, so the canvas is
the overlay plus that surplus, and `LBL_Map` is set to exactly the overlay so the
control crops it. The frame art's interior measures `W // 2`, which is why the
overlay does. For `LBL_Map` to crop from the canvas's own left edge the centring
domain must equal the screen: `canvas_left = LBL_Map.left + (W − centering_x) / 2`.
KOTOR's renderer adds a 14-pixel top inset, which `LBL_Map.top` absorbs:

```text
LBL_Map = ((W − overlay_width) // 2, (H − canvas_height) // 2 + 14, overlay_width, canvas_height)
```

The `440×256` values are KOTOR's original marker-coordinate domain. The executable
wrappers scale map notes, the selected marker, the party marker and the player
arrow from that domain into the overlay:

```text
screen_marker_x = round_half_up(original_x × marker_overlay_width / 440)
screen_marker_y = round_half_up(original_y × marker_overlay_height / 256)
```

The hit test inverts the same placement; the version that centred the canvas in
the window instead was 141 px out, see
[`../reverse-engineering/map-markers.md`](../reverse-engineering/map-markers.md).

What ships, read back from the installer's outputs (FILE `0x295082`/`0x29508A`,
`0x29505C`/`0x295064`, `0x2928B3`/`0x2928C3`):

| W×H | overlay | canvas | centring |
| --- | --- | --- | --- |
| 800×600 | 400×300 | 465×300 | 800×600 |
| 1920×1080 | 960×540 | 1117×540 | 1920×1080 |
| 2560×1440 | 1280×720 | 1489×720 | 2560×1440 |
| 3440×1440 | 1720×720 | 2001×720 | 3440×1440 |
| 2880×1620 | 1440×810 | 1676×810 | 2880×1620 |
| 3840×2160 | 1920×1080 | 2234×1080 | 3840×2160 |
| 15360×8640 | 7680×4320 | 8937×4320 | 15360×8640 |

Gold still holds the earlier model's 3440×1440 values -- canvas 1720×720,
overlay 1478×720, centring 2750×1400 -- which the patcher checks and replaces at
every resolution, 3440×1440 included.

### Correction, 2026-09-24

Until this date this section gave that earlier model as the current one:
`canvas = W / 2`, `overlay = canvas × 440 / 512`, a centring domain derived from
`LBL_Map`, and gold's values as what 3440×1440 produces. It changed with the
fix for the unfogged strip down the right of the map
([`../reverse-engineering/area-map-surface.md`](../reverse-engineering/area-map-surface.md)).
Gold kept the old values, which is how the old formulas survived here: they
describe gold, not what the installer writes.

## Gameplay minimap isolation

The full map and gameplay minimap share the same KOTOR class. Enlarging the shared constructor surface caused the gameplay minimap to wrap and show a second copy of the map. The final wrapper restores the gameplay minimap instance to its retail values:

```text
minimap canvas          = 512 × 256
minimap marker overlay  = 440 × 256
```

Only the full-screen map uses the selected large-map dimensions. This avoids the duplication glitch without activation/deactivation hooks, which previously caused a crash when closing the map with `M`.

The upstream HUD layouts keep the visible minimap viewport at `120×120` and
its frame at `136×137` at every resolution. The final gold HUD enlarged these
to `270×270` and `276×276`. The universal resource builder preserves that
play-tested size and scales it with vertical resolution:

```text
minimap_scale = max(1, screen_height / 1440)
viewport_size = round_half_up(270 × minimap_scale)
```

`LBL_MAP` and the executable's `512×256` minimap surface remain unchanged;
that render-domain isolation is what prevents a vertically wrapped second
copy. At `7680×2160`, the GUI uses a `405×405` viewport, a `414×414`
frame, and a matching `408×405` minimap button/hit area.

## Transferring the gold GUI corrections

The upstream resolution folders contain the correct root canvases, but they
do not include the manual control-proportion fixes made in the final
3440×1440 build. During packaging, the generator compares the original
3440×1440 GUI with the gold version and transfers only changed `EXTENT`
fields to each target GUI as ratios. This retains every target resolution's
textures, IDs, strings, and event wiring while carrying forward the corrected
button, panel, list, scrollbar, HUD, and text-box proportions. The active gold
HUD template is applied to every `mipc*.gui` variant because KOTOR can select
different variants at runtime.

## Reported 4K layout repairs

This section records the two resource defects reported in
[GitHub issue #4](https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/issues/4).
The source observations are the reporter's 3840×2160 captures of the
[Feedback screen](https://imgur.com/a/jkhrqBG),
[XP notification and target nameplate](https://imgur.com/a/tRdk44w), and
[item notification](https://imgur.com/a/c4uEndx). The output measured below is
from `build/kmrp/resources/gui-3840x2160.zip`, produced on 2026-09-05; that
archive was embedded in the 228,886,528-byte standalone package with SHA-256
`642CB53A239307E8389E4D07DBC3FF85929721D35EBCE81BFAB40AA72708CE29`.

### Feedback list prototypes -- rewritten, then reverted

> **Reverted on 2026-09-06; nothing below in this subsection or the next one's
> prototype table ships.** The prototype rewrite shipped, and the Character
> Scripts screen came back broken from play-testing. The play-tested 3440×1440
> gold files leave these prototypes at their vanilla values, identical to
> upstream, while the parent list around them is fully scaled, so the rewrite is
> disabled in `tools/prepare_universal_resources.py` and
> `Test-GeneratedGuiGeometry.py` now asserts the opposite: every prototype is left
> exactly as upstream ships it. The installer's 3840×2160 archive holds
> `(76,90,240,43)` and `(330,90,240,25)` for the two Feedback prototypes and
> `(71,84,241,50)` and `(324,86,242,50)` for Character Scripts -- the "Old
> prototype" values. What those screens get instead, since 2026-09-24: a gutter
> between the Feedback list's left scrollbar and its option circles
> (`HAND_TUNED_GUTTERS`), and Character Scripts rows centred in the box its
> background art draws (`centre_rows_in_frame`). Issue #12's 3840×2160 report
> therefore still needs a different diagnosis.
>
> *Checked 2026-09-25:* the installer's 3840×2160 archive was compared with its
> 1920×1080 archive, control by control, in fractions of the screen. Both are
> 16:9, and 1080p is reported to work. No control on any screen moves or resizes
> by 5% of the screen or more, apart from controls that have the same pixel
> size at both resolutions: the minimap's 512-pixel `LBL_MAP` and the main menu's
> hidden debug `LB_MODULES` / `BTN_WARP`. The children that leave their panels
> at 4K are the same ones that leave them at 1080p: the party's hidden fourth
> slot, background art and tab hover highlights. So the report is **not** a
> layout-geometry fault in the shipped `.gui` files.
>
> *Named 2026-09-25, from the Reddit thread the maintainer forwarded:* the empty
> screen is **Character Scripts** (`scriptselect.gui`) at 3840×2160. Its frame
> draws, but the title, both lists and both buttons are missing. A second reader
> reports the same at 1080p. Both reports predate 1.5, so 1.0 was the only public
> build. The files, compared field by field:
>
> | Comparison (`scriptselect.gui`) | Differences other than extents |
> | --- | --- |
> | 1.0 release (`0d0eace7…`) vs the 1.5 installer, at 3840×2160 | `LST_AIState.PADDING` 2 → 40; ROOT left −15 → 0 |
> | 1.5 at 3440×1440 (the hand-tuned file, seen working in play) vs 1.5 at 3840×2160 | padding only (35 → 40, 72 → 108) |
> | vanilla vs 1.5 at 3840×2160 | ROOT `BORDER.FILLSTYLE` 0 → 2 (upstream's), padding |
>
> So the 4K and 1080p files are structurally the file that works at 3440×1440, in
> 1.0 as in 1.5, and nothing in them hides children. Whether the screen still
> comes up empty at 1080p or 4K in 1.5 was untested when this was written.
>
> *Checked in play, 2026-09-25:* the maintainer opened Character Scripts in 1.5
> and it works. The resolution of that check was not recorded, so it covers
> the 1.5 build but not specifically 1080p or 4K.

KOTOR positions and wraps each list row from the listbox's embedded
`PROTOITEM.EXTENT`. High Resolution Menus had scaled the two parent panes and
their scrollbars, but left both prototypes at vanilla coordinates with a
240-pixel width. At 3840×2160 the generated file therefore contained:

| Control | Parent `(L,T,W,H)` | Old prototype `(L,T,W,H)` | Rewritten to, reverted `(L,T,W,H)` |
| --- | --- | --- | --- |
| `LB_OPTIONS` | `(360,405,1536,1305)` | `(76,90,240,43)` | `(456,405,1440,43)` |
| `LB_DESC` | `(1987,420,1544,1275)` | `(330,90,240,25)` | `(1987,420,1442,25)` |

`tools/fix_feedback_list_prototypes.py` anchors the prototype to the parent's
top edge, starts it after a left-hand scrollbar or ends it before a right-hand
scrollbar, and spans the remaining content width. It deliberately leaves row
height untouched because the runtime list-row hook owns that dimension.

### Full-screen Character Scripts and confirmation dialog

A later 3840×2160 report identified the same stale-prototype defect in
`scriptselect.gui`. Its frame and two parent listboxes filled the screen, but
the embedded rows still used 640×480-era positions and widths. Measured from the
final 4K archive:

| Control | Parent `(L,T,W,H)` | Old prototype `(L,T,W,H)` | Rewritten to, reverted `(L,T,W,H)` |
| --- | --- | --- | --- |
| `LST_AIState` | `(291,384,1574,1409)` | `(71,84,241,50)` | `(387,384,1478,50)` |
| `LB_DESC` | `(1931,384,1605,1409)` | `(324,86,242,50)` | `(1931,384,1509,50)` |

The same geometry helper repaired those prototypes after gold-layout transfer,
until the 2026-09-06 revert above.

The confirmation report exposed an independent containment error. At the
3440×1440 tuning scale, `TGuiPanel` ended at child y=375 while `BTN_CANCEL`
ended at y=490. At 3840×2160 that became a 172-pixel overrun. The authored panel
height is now 525 at scale 2, leaving a measured 35-pixel bottom margin; the
shared height rule produces this final 4K layout:

| Control | Final 3840×2160 extent `(L,T,W,H)` |
| --- | --- |
| `TGuiPanel` | `(1239,747,1350,788)` |
| `LB_MESSAGE` | `(90,36,1170,225)` |
| `BTN_OK` | `(90,480,1170,120)` |
| `BTN_CANCEL` | `(90,615,1170,120)` |

Both buttons now end inside the panel, with 53 pixels below Cancel at this
resolution. The popup's engine-created tutorial icon can add height at runtime;
the no-icon confirmation path was the one the old table failed to contain.

### Target strip and transient notifications

The upstream active HUD (`mipc28x6.gui` at every generated resolution except
3440×1440) derived these short-lived controls from screen width. At 3840×2160
that produced a 960×94 target-name background and 115-pixel notification icons,
which matches the oversized elements in the reports. The final generator reads
the play-tested 3440×1440 gold extents and applies:

```text
transient_scale = max(1, screen_height / 720) / 2
target_extent   = round_half_up(gold_extent × transient_scale)
```

All four extent fields are top-left anchored. Representative packaged values
are:

| Resolution | Name background | Name text | Notification icons |
| --- | --- | --- | --- |
| 800×600 | `(0,0,200,26)` | `(0,0,150,26)` | `32×32` |
| 1920×1080 | `(0,0,300,39)` | `(0,0,225,39)` | `48×48` |
| 3440×1440 | `(0,0,400,52)` | `(0,0,300,52)` | `64×64` |
| 3840×2160 | `(0,0,600,78)` | `(0,0,450,78)` | `96×96` |

The affected notification tags are `LBL_JOURNAL`, `LBL_CASH`, `LBL_PLOTXP`,
`LBL_ITEMRCVD`, `LBL_ITEMLOST`, `LBL_STEALTHXP`, `LBL_DARKSHIFT`, and
`LBL_LIGHTSHIFT`. The target strip uses `LBL_NAMEBG`, `LBL_NAME`,
`LBL_HEALTHBG`, and `PB_HEALTH`.

The bottom HUD clusters retain their existing gold-proportion rule, and the
centre combat queue remains untouched.

### Verification and limits

After a full resource build,
`python testing/regression/Test-GeneratedGuiGeometry.py` opens all 48 packaged
GUI archives. For each resolution it proves that the Feedback and Character
Scripts prototypes are exactly upstream's, the Feedback list keeps its scrollbar
gutter, the Character Scripts rows are centred in their frame, every direct
confirmation child stays inside its panel, the HUD file KOTOR actually selects
contains the exact height-scaled gold extents for all twelve transient
controls, and the R3 party-switch cue is sized and placed by its rule. On
2026-09-05 the 3840×2160 package was installed through `--in-place`; the
installed `optfeedback.gui` and `mipc28x6.gui` matched their archive members
byte-for-byte, and the patched executable was then 4,083,712 bytes with SHA-256
`6D4DEB0F778DAF08CC8385E4A59C05D2344E8F605EF702501BB92559B657A99F`. The
2026-09-24 installer's 3840×2160 executable is 4,087,808 bytes, SHA-256
`59A62449F5C1579B12251610EE5AB6079C7B5FA894244A6CECDDBFC5156B713B`.

This is structural verification, not a visual play-test. Opening Feedback,
Character Scripts, and a confirmation dialog; receiving XP and an item; and
targeting a character or container at 3840×2160 remain explicitly untested in
game.

## Executable fields

`ResolutionPatch.Apply` in `src/patcher/KmrpPatcher.cs` replaces these fields
after applying the gold delta. Every replacement first checks that the field
holds gold's value, and a mismatch blocks patching rather than writing to an
unknown executable. `s = max(1, H / 720)`, the shared scale; `m = min(s, 127/16)`,
because the marker centring offsets are signed bytes. C#'s `Math.Round` rounds
halves to even, so `19 × 1.5 = 28.5` ships as 28. Every value below was **read
back from the installer's own output** (`--apply`, installer `ECA3DE4B…`,
2026-09-24), not computed:

| Field | FILE offsets | Gold | Rule | 800×600 | 1920×1080 | 3440×1440 | 3840×2160 | 15360×8640 |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Screen width | `0xAA65`, `0x1F0C65` | 3440 | `W` | 800 | 1920 | 3440 | 3840 | 15360 |
| Screen height | `0xAA85`, `0x1F0C6F` | 1440 | `H` | 600 | 1080 | 1440 | 2160 | 8640 |
| Movie-mode width | `0x3D6C`, `0x1F5B3B` | 3440 | `W` | 800 | 1920 | 3440 | 3840 | 15360 |
| Movie-mode height | `0x3D78`, `0x1F5B43` | 1440 | `H` | 600 | 1080 | 1440 | 2160 | 8640 |
| Recentring width reference | `0xB6C7`, `0xBA6C` | -3440 | `-W` | -800 | -1920 | -3440 | -3840 | -15360 |
| Recentring height reference | `0xB6DA`, `0xBA83` | -1440 | `-H` | -600 | -1080 | -1440 | -2160 | -8640 |
| List-row scale (`.kfs` float) | `0x3DD004` | 1.75 | `s` | 1.0 | 1.5 | 2.0 | 3.0 | 12.0 |
| Stack label height | `0x2B5332` | 19 | `19s` | 19 | 28 | 38 | 57 | 228 |
| Stack label width, 1-2 and 3+ digits (`.ksc`) | `0x3DF003`, `0x3DF009` | 21 | `21s` | 21 | 32 | 42 | 63 | 252 |
| Stack label top offset (`.ksc`) | `0x3DF020` | 37 | `37s` | 37 | 56 | 74 | 111 | 444 |
| Inventory icon and row height | `0x2B527F`, `0x2B4FA9`, `0x2B55E3` | 56 | `56s` | 56 | 84 | 112 | 168 | 672 |
| Abilities (skills) icon and row height | `0x2AB8EF`, `0x2ACB20` | 42 | `42s` | 42 | 63 | 84 | 126 | 504 |
| Store icon and row height | `0x2C265F`, `0x2C2A23` | 56 | `56s` | 56 | 84 | 112 | 168 | 672 |
| Powers/feats chain row height | `0x2CD8D9`, `0x2CDB79` | 40 | `50s` (vanilla 40) | 50 | 75 | 100 | 150 | 600 |
| Popup auto-fit height stop | `0x2256E3`, `0x225759` | 900 | `450s` | 450 | 675 | 900 | 1350 | 5400 |
| Popup auto-fit width cap | `0x2256DC`, `0x2256F6` | 1600 | `800s` | 800 | 1200 | 1600 | 2400 | 9600 |
| Popup icon rect, message inset | `0x226F95`, `0x22540D` | 128 | `64s` | 64 | 96 | 128 | 192 | 768 |
| Map note size, selected | `0x294720` | 40 | `20m` | 20 | 30 | 40 | 60 | 159 |
| Map note size, unselected | `0x294763` | 28 | `14m` | 14 | 21 | 28 | 42 | 111 |
| Party marker size | `0x294A13` | 32 | `16m` | 16 | 24 | 32 | 48 | 127 |
| Player arrow size | `0x294AC4` | 64 | `32m` | 32 | 48 | 64 | 96 | 254 |
| `mm_barrow` control extent | `0x29405B` | 64 | `32m` | 32 | 48 | 64 | 96 | 254 |
| `lbl_mapcircle` control extent | `0x2940DC` | 32 | `16m` | 16 | 24 | 32 | 48 | 127 |
| Note centring, selected (imm8) | `0x29471A`, `0x294726` | -20 | `-10m` | -10 | -15 | -20 | -30 | -79 |
| Note centring, unselected (imm8) | `0x294777`, `0x29477A` | -14 | `-7m` | -7 | -10 | -14 | -21 | -56 |
| Party centring (imm8) | `0x294A53`, `0x294A56` | -16 | `-8m` | -8 | -12 | -16 | -24 | -64 |
| Arrow centring (imm8) | `0x294AD0`, `0x294AD4` | -32 | `-16m` | -16 | -24 | -32 | -48 | -127 |
| Map centring width | `0x2928B3` | 2750 | `W` | 800 | 1920 | 3440 | 3840 | 15360 |
| Map centring height | `0x2928C3` | 1400 | `H` | 600 | 1080 | 1440 | 2160 | 8640 |
| Map canvas width | `0x29505C` | 1720 | `round(W//2 × 512/440)` | 465 | 1117 | 2001 | 2234 | 8937 |
| Map canvas height | `0x295064` | 720 | `H//2` | 300 | 540 | 720 | 1080 | 4320 |
| Marker overlay width | `0x295082` | 1478 | `W//2` | 400 | 960 | 1720 | 1920 | 7680 |
| Marker overlay height | `0x29508A` | 720 | `H//2` | 300 | 540 | 720 | 1080 | 4320 |

The 33 rows are all 89 bytes that differ between the 48 outputs; none falls
outside them. The movie fields are a separate display-mode policy, not Bink
render dimensions; see
[`../reverse-engineering/movies.md`](../reverse-engineering/movies.md).

**`0x28C4E3` is deliberately not replaced.** It is the last live comparison in
the HUD minimap selector: gold sets it to 3440, so `mipc210x7.gui` -- the HUD
hand-corrected for 3440×1440 -- loads there and every other resolution falls
through to `mipc28x6.gui`. Every output keeps 3440. Writing the live width into
it made the comparison always true, and every resolution loaded the ultrawide
HUD. *Corrected 2026-09-24:* this table listed it as a replaced screen-width
field, and listed only ten fields.

## Interface packaging

- The 236 shared TGA assets are stored once in the standalone patcher; three
  more, `lbl_mileftbot`, `lbl_hex_3` and `lbl_hex_6`, are built per resolution
  (build of 2026-09-24).
- Each supported resolution has its own GUI archive in the build,
  `gui-<W>x<H>.zip`, which the regression checks read. Since 2026-09-25 the
  installer embeds them as one pool that stores each distinct file once, and
  rebuilds the chosen resolution's files from it
  (`tools/pack_resolution_layouts.py`). The 49 archives were 118.2 MB and the
  pool is 57.7 MB.
- 3440×1440 starts from the final, play-tested GUI collection; the controller
  cues, confirm badges and list gutters are added at every resolution, 3440×1440
  included.
- The other resolutions use the corresponding KOTOR High Resolution Menus layout.
- `[Graphics Options]` in `swkotor.ini` is rewritten with the selected `Width` and `Height` while preserving unrelated settings and comments.
- Existing executable, INI, and conflicting Override files are backed up and verified before replacement.

## Adding another resolution

**Step 1 is the hard one, and it blocked 2880x1620 (issue #16) until 2026-09-25.**
The resolution now ships; how it was derived follows the original text below.
That preset is
16:9 and exactly 1.5x 1920x1080, but the upstream mod ships no `gui.2880x1620`,
and the sets it does ship **cannot be scaled into one another**. Measured across
all 81 shared files:

| From | To | Scale | Extent fields reproduced |
| --- | --- | --- | --- |
| 1920x1080 | 2560x1440 | 1.3333 | 73.9% (best of round/floor/ceil/trunc) |
| 1024x576 | 1920x1080 | 1.875 | 57.2% |
| 1920x1080 | 3840x2160 | **2.0 exactly** | 64.1%, and all four rounding modes agree |

At an exact doubling, where rounding cannot be the explanation, only **4 of 81
files** scale cleanly; `partyselection.gui`, `mainmenu.gui` and the whole
`mipc*` minimap family differ in 40–60% of their fields. The upstream sets are
laid out per resolution, not derived from one another, so producing a new one
means reimplementing that layout — or asking ndix UR, whose work KMRP already
bundles with permission, for the missing set. Neither is a small change, and
neither has been done.

**How 2880x1620 was added (2026-09-25).** Neither scaling nor a new layout was
needed, because 2880x1620 is exactly halfway between two sets upstream does ship,
1920x1080 and 3840x2160, in width and in height. `tools/derive_resolution_gui_set.py`
interpolates every field halfway between those two sets:
- a field upstream doubles from one to the other comes out 1.5×;
- a field it holds fixed, such as the list prototypes, stays fixed;
- a hand adjustment lands between its two values.

Only `EXTENT` fields differ between upstream sets (measured across the 1080p →
4K pair: every other field is identical). The tool stops if anything else
differs.

Checked against a set upstream does ship. 2560x1440 is a third of the way from
1920x1080 to 3840x2160, and interpolating at 1/3 reproduces its 9,276 extent
fields as follows:

| Derivation of 2560x1440 | Exact | Within 1 px | Further |
| --- | --- | --- | --- |
| scale 1920x1080 by 4/3 (the table above) | 73.9% | -- | -- |
| interpolate 1920x1080 → 3840x2160 at t = 1/3 | 87.6% | 12.4% | **0** |

`prepare_universal_resources.py` derives the set at build time into a temporary
folder (`DERIVED_GUI_SETS`) and computes its map geometry from the derived
`map.gui` with the same rule as every other resolution. The font set is the
2.25× bake from `tools/build_font_scale_sets.py`. **Not seen in play:** the
maintainer's monitor is 3440x1440, and the preset exists for DSR on 1080p
screens.

1. Add a matching `gui.WIDTHxHEIGHT` directory containing the full GUI set.
2. Add the resolution to `GROUPS` in `tools/prepare_universal_resources.py`.
3. Run `tools/analyze_resolution_guis.py` to regenerate `assets/resolution-geometry.json`.
4. Run `build_kmrp.ps1` without `-ReuseResources`.
5. Generate the executable through `--apply CLEAN_EXE OUTPUT_EXE WIDTHxHEIGHT` and verify every field in *Executable fields*.
6. Test in game: menus, HUD, minimap at multiple player positions, full map, marker clicks, marker cycling, and repeated `M` open/close.

## Validation status

- All 48 requested executable variants were generated and structurally verified,
  and since 2026-09-25 all 49: the 2880x1620 output reads back the rule's
  values (overlay 1440x810, canvas 1676x810, centring 2880x1620, row scale 2.25)
  and differs from the 1920x1080 output in 75 bytes.
- 3440×1440 differs from the gold snapshot in 22 bytes across 17 runs, all
  fields in *Executable fields* that gold holds at an earlier or vanilla value.
  *Corrected 2026-09-24:* this line said it matched gold byte-for-byte.
- A complete 1920×1080 install verified the EXE, INI, selected GUI files, shared artwork, backup records, resolution-switch protection, and full restore.
- `Test-InstalledOverride.ps1` installs through the real installer and requires
  Override to hold exactly `override-common.zip` and the resolution's archive,
  byte for byte, and nothing after restore. It passed at all 49 resolutions on
  the installer of 2026-09-25, `4EF3C181…`.
- The remaining resolutions still require representative in-game play testing because structural verification cannot prove how every module and GPU driver renders them.
- The Feedback prototype and active transient-HUD geometry are checked directly
  in all 48 packaged archives by
  `testing/regression/Test-GeneratedGuiGeometry.py`; the installed 3840×2160
  files were hash-verified, but their reported scenarios still need visual
  in-game confirmation.
