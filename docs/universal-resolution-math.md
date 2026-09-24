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
contains the full cumulative gold chain through map-note corrections and Large
Address Aware support. The
resolution math below is unchanged by that; only the baseline executable
differs. See `docs/font-scaling.md` and
`reverse-engineering/listbox-geometry.md` for the gold lineage.

## Resolution inputs

For a selected screen width `W` and height `H`:

```text
map_canvas_width  = floor(W / 2)
map_canvas_height = floor(H / 2)

marker_overlay_width  = round_half_up(map_canvas_width × 440 / 512)
marker_overlay_height = map_canvas_height
```

The `440×256` values are KOTOR's original marker-coordinate domain. The executable wrappers scale map notes, the selected marker, the party marker, and the player arrow from that original domain into the new overlay:

```text
screen_marker_x = round_half_up(original_x × marker_overlay_width / 440)
screen_marker_y = round_half_up(original_y × marker_overlay_height / 256)
```

## Centering from `map.gui`

Every resolution uses its matching `map.gui`. The generator reads the `LBL_Map` control instead of guessing screen offsets.

```text
render_left = LBL_Map.LEFT + 4
render_top  = LBL_Map.TOP

centering_width  = 2 × render_left + map_canvas_width
centering_height = 2 × (render_top - 14) + map_canvas_height
```

KOTOR's renderer adds a 14-pixel vertical inset. The hit-test wrapper derives the inverse translation from the live window and canvas rectangles:

```text
local_mouse_x = mouse_x - (window_width  - map_canvas_width)  / 2
local_mouse_y = mouse_y - (window_height - map_canvas_height) / 2 + 14
```

This is why markers remain clickable at the position where they are drawn.

For the confirmed gold resolution, the generated values are:

```text
W × H                   = 3440 × 1440
map canvas              = 1720 × 720
marker overlay          = 1478 × 720
LBL_Map origin          = 511, 354
render origin           = 515, 354
centering domain        = 2750 × 1400
```

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

### Feedback list prototypes

KOTOR positions and wraps each list row from the listbox's embedded
`PROTOITEM.EXTENT`. High Resolution Menus had scaled the two parent panes and
their scrollbars, but left both prototypes at vanilla coordinates with a
240-pixel width. At 3840×2160 the generated file therefore contained:

| Control | Parent `(L,T,W,H)` | Old prototype `(L,T,W,H)` | Final prototype `(L,T,W,H)` |
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

| Control | Parent `(L,T,W,H)` | Old prototype `(L,T,W,H)` | Final prototype `(L,T,W,H)` |
| --- | --- | --- | --- |
| `LST_AIState` | `(291,384,1574,1409)` | `(71,84,241,50)` | `(387,384,1478,50)` |
| `LB_DESC` | `(1931,384,1605,1409)` | `(324,86,242,50)` | `(1931,384,1509,50)` |

The same geometry helper now repairs those prototypes after gold-layout
transfer. This is why the fix applies to all 48 packages rather than containing
a 4K-only coordinate table.

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
Scripts prototypes fill the exact non-scrollbar portion of their parent, every
direct confirmation child stays inside its panel, and the HUD file KOTOR
actually selects contains the exact height-scaled gold extents for all twelve
transient controls. The 3840×2160 package was installed through `--in-place`;
the installed `optfeedback.gui` and `mipc28x6.gui` matched their archive members
byte-for-byte, and the already-patched executable remained 4,083,712 bytes with
SHA-256
`6D4DEB0F778DAF08CC8385E4A59C05D2344E8F605EF702501BB92559B657A99F`.

This is structural verification, not a visual play-test. Opening Feedback,
Character Scripts, and a confirmation dialog; receiving XP and an item; and
targeting a character or container at 3840×2160 remain explicitly untested in
game.

## Executable fields

The universal build replaces these verified 32-bit values after applying the gold delta:

| Purpose | Gold value | File offsets |
|---|---:|---|
| Screen width | 3440 | `0xAA65`, `0x1F0C65`, `0x28C4E3` |
| Screen height | 1440 | `0xAA85`, `0x1F0C6F` |
| Movie-mode width | 3440 | `0x3D6C`, `0x1F5B3B` |
| Movie-mode height | 1440 | `0x3D78`, `0x1F5B43` |
| Map centering width | 2750 | `0x2928B3` |
| Map centering height | 1400 | `0x2928C3` |
| Map canvas width | 1720 | `0x29505C` |
| Map canvas height | 720 | `0x295064` |
| Marker overlay width | 1478 | `0x295082` |
| Marker overlay height | 720 | `0x29508A` |

All replacements verify the expected gold value first. A mismatch blocks patching rather than writing to an unknown executable. The movie fields are a separate display-mode policy, not Bink render dimensions; see [`../reverse-engineering/movies.md`](../reverse-engineering/movies.md).

## Interface packaging

- The 240 shared TGA assets are stored once in the standalone patcher.
- Each supported resolution has a small independent GUI archive.
- 3440×1440 uses the exact final, play-tested GUI collection.
- The other resolutions use the corresponding KOTOR High Resolution Menus layout.
- `[Graphics Options]` in `swkotor.ini` is rewritten with the selected `Width` and `Height` while preserving unrelated settings and comments.
- Existing executable, INI, and conflicting Override files are backed up and verified before replacement.

## Adding another resolution

**Step 1 is the hard one, and it blocked 2880x1620 (issue #16).** That preset is
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

1. Add a matching `gui.WIDTHxHEIGHT` directory containing the full GUI set.
2. Add the resolution to `GROUPS` in `tools/prepare_universal_resources.py`.
3. Run `tools/analyze_resolution_guis.py` to regenerate `assets/resolution-geometry.json`.
4. Run `build_kmrp.ps1` without `-ReuseResources`.
5. Generate the executable through `--apply CLEAN_EXE OUTPUT_EXE WIDTHxHEIGHT` and verify all eight dynamic fields.
6. Test in game: menus, HUD, minimap at multiple player positions, full map, marker clicks, marker cycling, and repeated `M` open/close.

## Validation status

- All 48 requested executable variants were generated and structurally verified.
- 3440×1440 matches the play-tested gold executable byte-for-byte.
- A complete 1920×1080 install verified the EXE, INI, selected GUI files, shared artwork, backup records, resolution-switch protection, and full restore.
- The remaining resolutions still require representative in-game play testing because structural verification cannot prove how every module and GPU driver renders them.
- The Feedback prototype and active transient-HUD geometry are checked directly
  in all 48 packaged archives by
  `testing/regression/Test-GeneratedGuiGeometry.py`; the installed 3840×2160
  files were hash-verified, but their reported scenarios still need visual
  in-game confirmation.
