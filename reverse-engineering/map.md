# Map Reverse-Engineering Notes

## Baseline executables

| Role | File | SHA-256 | Version |
| --- | --- | --- | --- |
| Current live executable | `../swkotor.exe` | `E3228D43C9DAB66FE349BD2E777EAC6F764CBE2475E8DB23288DEF94B10CF885` | 1.0.3.0 |
| Pre-global-split live backup | `../swkotor.exe.backup-before-global-split-20260827-183906.bak` | `3C73627AEEE967BD780AFEA108A6AB2EC4EA6EAF345E15727E081F945506DBD2` | 1.0.3.0 |
| Pre-marker-patch backup | `../swkotor.exe.backup-before-map-icons-20260827-125908.bak` | `D7DD19449F1BA2DE1D91D19E1BAA4BE15A7480AE4C9ED7F986DE5E2424E97909` | 1.0.3.0 |
| Selected clean source | `../swkotor.exe.bak` | `52AD3AE43E6D5B7ADFCE3AA240E7B26214CFE61BA9C3D9AF121DA065643E3B53` | 1.0.3.0 |
| Duplicate clean candidate | `../swkotor_UNPATCHED.exe_OLD` | `52AD3AE43E6D5B7ADFCE3AA240E7B26214CFE61BA9C3D9AF121DA065643E3B53` | 1.0.3.0 |
| Alternate original candidate | `../swkotororiginl.exe` | `2E86F7FB730092487A1E3F1BDE2140210908656F0BD3A7C83C5BE8C8F0587059` | 1.0.3.0 |

The duplicate clean candidates are byte-identical. Their store/build provenance
still needs to be established before any release patch signature is defined.

## Isolated analysis copies

| Role | File | SHA-256 |
| --- | --- | --- |
| Clean code reference | `../swkotor_phase0_clean.exe` | `52AD3AE43E6D5B7ADFCE3AA240E7B26214CFE61BA9C3D9AF121DA065643E3B53` |
| Current 3440x1440 behavior | `../swkotor_phase0_ultrawide.exe` | `D7DD19449F1BA2DE1D91D19E1BAA4BE15A7480AE4C9ED7F986DE5E2424E97909` |
| Global-dimension split candidate | `../swkotor_phase0_map_final.exe` | `E3228D43C9DAB66FE349BD2E777EAC6F764CBE2475E8DB23288DEF94B10CF885` |

Debugger experiments use isolated executable copies. Candidate 009 was copied
to live `swkotor.exe` only after isolated placement, click validation, and the
HUD-duplication regression check. The game configuration currently requests
3440x1440 fullscreen at 60 Hz.

## Verified working map patch

| Purpose | VA | Original | Patched | Value |
| --- | --- | --- | --- | --- |
| Map render width | `0x0069505C` | `00 02 00 00` | `B8 06 00 00` | 512 -> 1720 |
| Map render height | `0x00695064` | `00 01 00 00` | `D0 02 00 00` | 256 -> 720 |
| Horizontal centering input | `0x006928B3` | `80 02 00 00` | `BE 0A 00 00` | 640 -> 2750 |
| Vertical centering input | `0x006928C3` | `E0 01 00 00` | `78 05 00 00` | 480 -> 1400 |

The size patch is considered prior verified work. Phase 0 no longer starts by
rediscovering it; it verifies the bytes and uses the patched map as the baseline
for icon and button investigation.

The release candidate restores the four shared constructor immediates to their
retail values (512x256 render and 440x256 marker domains). Only the full-map
constructor call at `0x00633102` is redirected to a wrapper that assigns the
1720x720 domains and child rectangles to that instance. This prevents the
enlarged full-map dimensions from leaking into the gameplay minimap.

## Key functions

- `0x00694D50`: map initialization.
- `0x00692810`: per-frame map rendering and centering.
- `0x00693F60`: icon-container and GUI-object initialization.
- `0x006943D0`: icon positioning/drawing loop.
- `0x00578E00`: world-to-map pixel conversion.
- `0x00578F10`: coordinate bounds checking.
- `0x00579090`: original area-map dimension getter.
- `0x004592F0`: map render-context setup.

## Map object fields

| Offset | Meaning | Current issue |
| --- | --- | --- |
| `+0x0C` | Icon normalization width | 1720 for full-map instance; retail 512 for HUD instance |
| `+0x10` | Icon normalization height | 720 for full-map instance; retail 256 for HUD instance |
| `+0x70` | Render width | 1720 for full-map instance; retail 512 for HUD instance |
| `+0x74` | Render height | 720 for full-map instance; retail 256 for HUD instance |
| `+0xE38` | Marker overlay | 1478x720 for full map; retail 440x256 for HUD |
| `+0x1080` | Map canvas | 1720x720 for full map; retail 512x256 for HUD |

The normalization-domain mismatch is confirmed. World conversion returns
coordinates in the original 440x256 area-map space, but the resized full-map
control is 1720x720. A center point of `(220, 128)` must therefore become
`(860, 360)`, not remain `(220, 128)`.

## Confirmed isolated icon and hitbox fix

Candidate 006 redirects only the three coordinate calls made by the full-screen
map draw function. Two position-independent wrappers call the original
conversion routines and rescale their successful integer outputs using the
1478x720 marker overlay:

```text
overlay_width = round(map_canvas_width * 440 / 512)
scaled_x = round(original_x * overlay_width  / 440)
scaled_y = round(original_y * overlay_height / 256)
```

| Call site | Original target | Wrapper purpose |
| --- | --- | --- |
| `0x006946F4` | `0x00578E00` | World objects and map notes |
| `0x00694A39` | `0x005791B0` | Party-member markers |
| `0x00694AAC` | `0x005791B0` | Player arrow |

The icon-container immediates at `0x00695082` and `0x0069508A` are changed from
440x256 to 1478x720. The original conversion functions, area-map bounds,
minimap paths, and fog/grid constants remain untouched.

For the current executable, the new `.kui` section begins at `0x0086D000`.
Its coordinate-wrapper entry points are `0x0086D000` and `0x0086D080`. A third
wrapper at `0x0086D100` translates centered full-window mouse coordinates into
overlay-local space before tail-jumping to the original custom hit test at
`0x00693300`. Vtable slot `0x0075477C` is redirected to this wrapper.

The marker controls store their rectangles in overlay-local coordinates. Their
rendering is centered with the 1720x720 map canvas, while the original overlay
hit test receives full-window mouse coordinates. Candidate 006 derives the
centering inset from the live 3440x1440 owner and 1720x720 canvas rectangles,
yielding `(860,360)` for this test resolution, then adds the measured 14-pixel
render-viewport top inset to the Y coordinate before invoking the original hit
test. This aligns the clickable rectangles with the rendered marker centers.

## Visual validation at 3440x1440

- The gameplay minimap retained its explored walkways and player arrow.
- The full-map fog/grid retained its original cell scale.
- Yellow map-note, blue object, party, and player markers occupied the full
  1720x720 map area instead of the upper-left 440x256 corner.
- Cycling the note selector changed the text from `To the Czerka Dock` to
  `Basket to the Shadowlands` and moved the selected marker to its correctly
  scaled lower-right location.
- Clicking two different rendered points selected them directly, moved the
  yellow marker, and changed the note text to `To Rwookrrorro Village` and
  `Supply Station`.
- Candidate 006 was verified by clicking the visible centers of two markers;
  the lower marker selected `Basket to the Shadowlands` and the upper marker
  selected `To Rwookrrorro Village` without an upward click offset.
- Candidate 009 / `swkotor_phase0_map_final.exe` retained the same enlarged
  full-map rendering and click behavior while restoring a single, normal-sized
  gameplay HUD minimap. The earlier candidate-006 HUD duplication regression
  was not present.
- The executable reached the main menu, loaded the Kashyyyk autosave, opened
  the map repeatedly, and did not raise a game exception.

## Stock Ebon Hawk note positions

A clean-code run on `ebo_m12aa` was inspected with the stock 440x256 marker
overlay. The seven note centers were observed at:

| Note | Stock marker center |
| --- | --- |
| Port crew quarters | `(131,98)` |
| Cargo hold | `(144,172)` |
| Cockpit | `(228,17)` |
| Swoop hangar | `(284,182)` |
| Starboard crew quarters | `(319,92)` |
| Engine room | `(217,244)` |
| Exit ramp | `(274,110)` |

The clean executable visibly places the Engine Room note below the white room
shape and the Swoop Hangar note on the outer hull. Candidate 005 scales those
same module-authored positions correctly. The annotated reference image instead
uses hand-positioned room centers, so matching it requires a separate
Ebon-Hawk-specific waypoint/content patch. It is not evidence of a remaining
full-map scaling or hit-test error.

## Verified behavioral probes

- Increasing the immediate at `0x0069405A` from `0x20` to `0x28` enlarged the
  player arrow; a much larger value caused clipping/disappearance.
- Changing the signed adjustments at `0x00694719` and `0x00694725` moved only
  the selected yellow icon.
- Changing the dimension-looking values near `0x0069507E` and `0x00695086`
  alone produced no visible icon-position effect because coordinates were still
  emitted in 440x256 space.
- Broadly changing the shared area-map transforms proves the scale formula but
  enlarges the fog grid and breaks the gameplay minimap; those changes are not
  part of the confirmed patch.

## Known unknowns

- Exact distribution provenance of each executable build.
- Existing changes in the current live executable.
- Release signatures for additional retail/store executable builds.
- Whether any map-screen controls outside the programmatic marker containers
  need separate `.gui` edits at unusual aspect ratios.
- Cross-resolution visual validation beyond the current 3440x1440 test. The
  hit-test centering math reads runtime rectangles; the current build's canvas
  and overlay sizes are generated for 3440x1440.
- Whether an optional, compatibility-safe Ebon Hawk waypoint correction should
  be shipped separately from the universal EXE patch.
