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

## HUD minimap content zoom — `0x00459920`

The gameplay minimap's frame scales with the GUI (`tools/scale_hud_minimap.py`
grows `LBL_MAPVIEW` to 270x270 in `mipc210x7.gui` at 3440x1440) but the map drawn
inside it does not zoom to the player: you see the whole area with a tiny marker.

`0x00459920` normalises a pixel rect into 0..1 UV and hands it to a virtual draw.
Disassembled from the editable exe (`761F9466...`, file offset `0x00059920`):

```
00459920  push  ecx
00459921  mov   eax, [0x7BB4D0]            ; early bypass flag
00459926  test  eax, eax
00459928  jne   0x004599A5                 ; -> pop ecx / ret 0x20
0045992A  movsx eax, word [0x7B9460]       ; active render viewport index
00459931  lea   eax, [eax+eax*4]           ; * 5
00459934  shl   eax, 1                     ; * 10 = entry stride
00459936  movsx edx, word [eax+0x7B946E]   ; viewport height
0045993D  movsx eax, word [eax+0x7B946C]   ; viewport width
...                                        ; fild / fdiv per argument
004599A2  call  [edx+0x14]                 ; 4 floats + 4 raw args
004599A6  ret   0x20                       ; thiscall, ecx = this, 8 stack dwords
```

The four stack arguments normalise as `arg1/W`, `arg2/H`, `arg3/W`, `arg4/H` —
that is `(x, y, width, height)` over the **active render viewport**, not over the
screen. So the zoom is decided by the destination rect's size *relative to the
viewport*. Vanilla sizes that rect on a 120px basis; enlarging the viewport to
270 without enlarging the rect is precisely "zoomed out".

`0x007B946C` / `0x007B946E` are the width/height of a viewport table entry,
10-byte stride, indexed by the word at `0x007B9460` — the same table the font
metrics work touched.

**This function is not minimap-specific.** Candidate 004 (2026-08-29) replaced
the viewport lookup with the live screen resolution unconditionally and broke
unrelated screens; it was reverted. Any fix here has to prove it is looking at
the minimap before changing anything.

`tools/build_minimap_zoom_fix.py` (section `.kmz`) scales the destination rect by
`viewportWidth / 120` about the viewport centre, behind two gates: the active
viewport must be square and 121..2048, and the source rect must be exactly the
map atlas (width 512, height 256 or 512, which is what `LBL_MAP` is in every
shipped GUI variant). Failing either gate it restores `eax`/`edx` and falls
through to untouched vanilla code, so the worst case is that it does nothing.

At a 120px viewport the arithmetic is the identity, so it cannot alter anything
vanilla already draws correctly. Reproducing the vanilla ratio of 512/120 =
4.2667:

| viewport | unpatched ratio | patched `arg3` | patched ratio | error |
| --- | --- | --- | --- | --- |
| 120 | 4.2667 | — (gate rejects) | 4.2667 | 0% |
| 140 | 3.6571 | 597 | 4.2643 | -0.056% |
| 188 | 2.7234 | 802 | 4.2660 | -0.017% |
| 270 | 1.8963 | 1152 | 4.2667 | 0% |
| 405 | 1.2642 | 1728 | 4.2667 | 0% |

Residual error is integer truncation in `idiv`.

### Confirmed under x64dbg, 3440x1440, player near an area's south edge

Everything above was inferred statically and is now measured. Attached to the
running patched exe (base `0x00400000`, no relocation):

| read | where | value |
| --- | --- | --- |
| HUD minimap rect | `[esi+0x6080..0x608C]` at `0x0068ABB0` | left 2, top 2, **270 x 270** |
| viewport index | `[0x007B9460]` | 1 |
| viewport entry 0 | `0x007B946C` | 3440 x 1440 (the full screen) |
| viewport entry 1 | `0x007B9476` | **270 x 270** (the minimap) |
| args in | `[esp+8..0x14]` at `0x0045992A` | x -70, y -72, w 512, h 256 |
| args out | same, after the stub | x -326, y -306, w 1152, h 576 |

Three things follow.

**The engine already knows the viewport is 270.** The HUD rect carries the GUI's
`LBL_MAPVIEW` value, and the pan at `0x0068ABB0` centres on `[esi+0x6088]/2` =
135. There is no "120px basis" anywhere in this path and nothing needs telling
the real size. An earlier theory to the contrary was wrong.

**The gate design is validated.** Viewport entry 0 is the full screen at
3440x1440, not square, so the square test rejects it; entry 1 is the minimap at
270x270. The two are genuinely distinguishable at the call.

**Black at an area's edge is vanilla behaviour, not a regression.** From the
measured args the player is 207px down a 256px map, 49px above its bottom edge.
At that spot the black band is:

| | black |
| --- | --- |
| true vanilla, 800x600, 120px view | 11px = **9.2%** |
| unpatched at 3440x1440 | 86px = 31.9% |
| the `.kmz` patch | 24.8px = **9.2%** |

The patch reproduces vanilla's proportion exactly. It reads as worse only because
the minimap is 2.25x larger on screen. A map surface 256px tall cannot fill a
270px viewport when the player stands near its edge, in any version.

**Do not "fix" it by clamping the pan.** That was tried as candidate 006 and
reverted. Clamping the scaled position to `[viewport - scaledSize, 0]` does remove
the band -- measured, it moved y from -330 to -306 -- but the engine keeps the
player arrow pinned at the viewport centre, so the map slides 24px out from under
the marker. Vanilla does not clamp, and the arrow is only correct while it does
not.

### The residual black band, and why it stays

Corrected: the earlier claim that the band matches vanilla was wrong. It compared
against a 256-tall map surface, but vanilla's is 512. Measured at the same spot
(player 80.9% down the surface):

| | surface | black |
| --- | --- | --- |
| true vanilla 800x600 (`mipc8x6`, 512x512) | 512 | **0%** |
| ours unpatched at 3440x1440 (`mipc210x7`, 512x256) | 256 | 31.9% |
| ours with the `.kmz` zoom | 256 | 9.2% |
| `mipc210x7` raised to 512x512 | 512 | **0%** |

The cause is that `mipc210x7.gui` alone ships `LBL_MAP` at 512x**256** where all
nine other variants use 512x512. Magnified to match the viewport, a 256-tall
surface is only 2.13x it, against vanilla's 4.27x, so the player cannot stay
centred near an area's vertical extreme.

**Raising it to 512 was tested in game on 2026-09-02.** It removes the band and
keeps the marker correct -- and reintroduces the vertical texture-wrap
duplication bug that the 512x256 value exists to avoid. Reverted. The constraint
is real and now confirmed twice.

So the band is the price of the wrap workaround, not a fault in the zoom patch,
which improves it from 31.9% to 9.2%. Removing it properly needs one of:

* ~~fixing the wrap itself~~ -- **investigated 2026-09-02 and ruled out.** The
  area map textures are natively 512x**256**: of the 97 `lbl_map*` entries in
  `swpc_tex_gui.erf`, 90 are 512x256, and the only 512x512 ones are the generic
  `lbl_map` fallback and a single outlier. There is no map below row 256 to
  reveal, so no sampler state can produce it. Clamping instead of repeating would
  replace the duplicated strip with a smear of the bottom row -- different
  garbage, not more map;
* clamping the pan **and** moving the player arrow by the same delta, so the map
  covers the viewport without the marker drifting. That needs a second hook on
  the arrow control (`hud+0x5F40` / `hud+0x6098`) and writable state shared with
  the `.kmz` stub, and it deviates from vanilla framing by design.

### What the band actually is

The missing rows are identical in vanilla and here -- at the measured position,
11 rows of map that do not exist, because the player stands closer to the map's
edge than half the viewport. Only the filler differs:

| `LBL_MAP` extent | texture | missing rows show as |
| --- | --- | --- |
| 512x512 (vanilla, and 9 of 10 variants) | 512x256 | the texture repeating -- duplicated map |
| 512x256 (`mipc210x7`) | 512x256 | nothing -- black |

So "vanilla is not black" is true but misleading: vanilla fills that space with
wrong data. `mipc210x7`'s 512x256 is the more honest of the two, and is why the
duplication bug was closed that way. Ours is more visible only because the
minimap is 2.25x larger, not because more map is missing.

The band is therefore not fixable by any render-state change. The only remaining
option that removes it is clamping the pan **and** moving the player arrow by the
same delta, which shows slightly less map than vanilla in exchange for never
showing a gap.

### A backdrop behind the minimap: mechanism proven, parked

Researched and tested 2026-09-02. xoreos, a clean-room reimplementation of the
same engine, builds the minimap as
`_mapQuad("lbl_map" + map, 0, 0, 512, 256)` under `glm::ortho(0, 120, 0, 120, ...)`
and positions it with a plain `translate(-(relX * 435) + 60, -(256 - relY*256) + 60, 0)`.
Three things follow: the map quad really is 512x256, the `+ 60` is the 120px
viewport's centre -- the same `centre - player*factor` pan seen in the
disassembly -- and there is **no clamping anywhere**. Letting the map run past the
viewport is authentic; vanilla's 512x512 control, which repeats the texture into
that space, is the anomaly. `relX * 435` also shows the map content is ~435-440px
wide inside the 512px texture, matching KPM's `AreaMapViewportWidth = 440`.

That reframes the black as something to *fill* rather than geometry to fight.
Two candidates were tested in game:

* **`LBL_MAPVIEW` fill** -- setting its `BORDER.FILL` ResRef does nothing. The
  engine treats that control purely as a viewport and never paints its fill.
  Every shipped variant leaves the ResRef empty, vanilla included.
* **`LBL_MAPBORDER` fill** -- **works.** It is drawn *behind* the map, so painting
  its transparent interior puts that artwork where the black was. `lbl_minimap.tga`
  is 184x184 and 95.7% transparent, a thin ring of rgb(80,117,248); filling the
  interior via a flood fill from the centre is enough.

The catch, and why it is parked rather than shipped: the area map textures are
themselves mostly transparent -- only the walkable geometry is painted -- so the
backdrop shows through across the **whole** minimap, not only past the map's edge.
It is therefore a decision about what the minimap's empty space looks like, not a
localised edge fix. A first attempt at rgb(12,24,52) with rgb(46,88,165) lines
every 12px read as a grid laid over the map. Subtler variants (near-black navy
with and without lines) were built but not adopted; the black was kept.

If this is revisited, the mechanism is settled and only the artwork is open. Fill
`lbl_minimap.tga`'s interior and ship it through `override-common.zip` so every
resolution picks it up -- no exe patch, no clamping, no arrow desync, and vanilla
framing is preserved.
