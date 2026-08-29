# Universal resolution patching

## What this build does

The universal patcher starts from the supported editable `swkotor.exe`, applies the already play-tested 3440×1440 gold transformation, and then replaces only the verified resolution-dependent values. It also updates `swkotor.ini` and installs the matching high-resolution GUI set plus the shared HD artwork.

The original 3440×1440 patcher is frozen separately. Selecting 3440×1440 in the universal patcher produces the same executable SHA-256 as that gold build:

`D8F0EEBF470660FFBB0DBE9D6953774B937F73F92260FA2D3427189D8B7F6ADE`

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

## Executable fields

The universal build replaces these verified 32-bit values after applying the gold delta:

| Purpose | Gold value | File offsets |
|---|---:|---|
| Screen width | 3440 | `0xAA65`, `0x1F0C65`, `0x28C4E3` |
| Screen height | 1440 | `0xAA85`, `0x1F0C6F` |
| Map centering width | 2750 | `0x2928B3` |
| Map centering height | 1400 | `0x2928C3` |
| Map canvas width | 1720 | `0x29505C` |
| Map canvas height | 720 | `0x295064` |
| Marker overlay width | 1478 | `0x295082` |
| Marker overlay height | 720 | `0x29508A` |

All replacements verify the expected gold value first. A mismatch blocks patching rather than writing to an unknown executable.

## Interface packaging

- The 240 shared TGA assets are stored once in the standalone patcher.
- Each supported resolution has a small independent GUI archive.
- 3440×1440 uses the exact final, play-tested GUI collection.
- The other resolutions use the corresponding KOTOR High Resolution Menus layout.
- `[Graphics Options]` in `swkotor.ini` is rewritten with the selected `Width` and `Height` while preserving unrelated settings and comments.
- Existing executable, INI, and conflicting Override files are backed up and verified before replacement.

## Adding another resolution

1. Add a matching `gui.WIDTHxHEIGHT` directory containing the full GUI set.
2. Add the resolution to `GROUPS` in `tools/prepare_universal_resources.py`.
3. Run `tools/analyze_resolution_guis.py` to regenerate `assets/resolution-geometry.json`.
4. Run `build_universal_patcher.ps1` without `-ReuseResources`.
5. Generate the executable through `--apply CLEAN_EXE OUTPUT_EXE WIDTHxHEIGHT` and verify all eight dynamic fields.
6. Test in game: menus, HUD, minimap at multiple player positions, full map, marker clicks, marker cycling, and repeated `M` open/close.

## Validation status

- All 48 requested executable variants were generated and structurally verified.
- 3440×1440 matches the play-tested gold executable byte-for-byte.
- A complete 1920×1080 install verified the EXE, INI, selected GUI files, shared artwork, backup records, resolution-switch protection, and full restore.
- The remaining resolutions still require representative in-game play testing because structural verification cannot prove how every module and GPU driver renders them.
