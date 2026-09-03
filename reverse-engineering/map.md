# Map Reverse-Engineering Notes

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


> This file is the **lab record**: what was tried, what failed, and what was
> disproved, in the order it happened. For the finished mechanism -- every byte
> KMRP writes for the map, the per-resolution domain tables, and the precision
> analysis -- see **[map-scaling.md](map-scaling.md)**.

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

**Corrected 2026-09-03 against the shipped binary.** The paragraph that stood
here described experiment 004's split -- the four shared constructor immediates
restored to retail, with only the full-map constructor call at `0x00633102`
redirected to a wrapper. **Gold v15 does neither of those things.** Read out of
`swkotor_gold_v15_popup.exe`:

| VA | clean | gold v15 |
| --- | --- | --- |
| `0x0069505C` render width | 512 | **1720** |
| `0x00695064` render height | 256 | **720** |
| `0x00695082` marker domain width | 440 | **1478** |
| `0x0069508A` marker domain height | 256 | **720** |
| `0x00633102` constructor call | `e8 49 1c 06 00` | **byte-identical, not redirected** |

So the enlarged domains are set globally rather than per instance, and the 004
split was superseded -- the gameplay minimap is kept correct by the later HUD
minimap content zoom (`.kmz`) and fog grid (`.kfg`) work documented below, plus
the per-resolution `mipc*.gui` scaling, rather than by isolating the full-map
constructor. `experiments/004-global-dimension-split.md` remains accurate as a
record of what was tried at the time; it is not a description of what ships.

The lesson is the one this project keeps relearning: a document describing a
release candidate stops being true the moment the design moves on, and only a
diff against the shipped binary catches it.

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

### What the wrappers actually compute

Disassembled out of gold v15 rather than restated from the design note. Both
coordinate wrappers are the same shape:

```asm
call 0x578E00              ; the vanilla conversion, unchanged
imul eax, [ebx+0x0C]       ; x live canvas width   (1478)
add  eax, 0xDC             ; +220, half of 440, to round rather than truncate
idiv 0x1B8                 ; / 440   -- the vanilla domain
imul eax, [ebx+0x10]       ; x live canvas height  (720)
add  eax, 0x80             ; +128, half of 256
idiv 0x100                 ; / 256
```

**KMRP leaves the two shared float constants at `0x00747748` (440.0) and
`0x007455D4` (256.0) untouched** and rescales the *result* instead. Because the
target size is read from the object at run time (`[ebx+0x0C]`, `[ebx+0x10]`) and
not baked in as a constant, one gold binary serves every resolution.

*Corrected the same day this was written:* an earlier sentence here said the
vanilla routine "divides by" those two floats. It does not. `0x00578E00` divides
by a **per-object field**, and the 440/256 appearing in it are bounds checks --
see below. The floats are used elsewhere in the chain. The claim was written
from the design note rather than from the disassembly, which is the exact
mistake the correction above this section is about.

The hit-test wrapper derives its centring the same way:

```asm
edx = [eax+0x0C] - [eax+0x108C]   ; canvasW - viewportW
edx >>= 1
[esp+4] -= edx                     ; mouse X
edx = [eax+0x10] - [eax+0x1090]   ; canvasH - viewportH
edx >>= 1
edx += 0x0E                        ; the +14 Y correction
[esp+8] -= edx
jmp 0x693300                       ; the original custom hit test
```

That matters for one specific question. There is a **second** pair of centring
immediates at `0x00692959` / `0x0069296B`, in the function at `0x00692930`,
with instruction-for-instruction the same shape as the draw-path pair at
`0x006928B3` / `0x006928C3` -- and KMRP leaves it at the vanilla 640/480. It is
**not** a missed second copy: `0x00692930` is referenced exactly once in the
image, as a pointer at `0x00754870`, which is not the area map's hit-test slot.
The area map's slot is `0x0075477C`, and gold redirects it (`0x00693300` ->
`0x0086D100`). The inverse transform therefore never reads a design-size
constant at all, so the vanilla value in that path is inert.

### The map-note coordinate chain, end to end

Every step below was disassembled from the clean executable or from gold,
corroborated against an independent clean-room reimplementation, and then
checked numerically against positions this file had already recorded. Nothing
here is inferred.

**1. Input.** A map note is a waypoint in the module's `.git` with a map-note
flag; its `XPosition` / `YPosition` are world coordinates. `ebo_m12aa` has 63
waypoints, 33 of them map notes.

**2. World to map pixel — `0x00578E00`.** Reads everything it needs from the map
object, not from globals:

```asm
00578E10  mov   eax, [esi+0x10]      ; NorthAxis
00578E17  jne / 00578E30 / 00578E49  ; three branches, each fmul [0x740CBC]
                                     ; -- the axis swap / negate cases
00578E61  fsub  dword ptr [esi+0x20] ; world - origin        (X; Y uses +0x24)
00578E64  fdiv  dword ptr [esi+0x18] ; / world-units-per-pixel  (Y uses +0x1C)
00578E67  fadd  dword ptr [0x73E9AC] ; + 0.5  -> round, not truncate
00578E6D  call  0x006FAE8C           ; float -> int
00578E99  cmp   ecx, 0x1B8           ; bounds check, 440
00578EA5  cmp   eax, 0x100           ; bounds check, 256
00578EAD  mov   eax, 1               ; 1 = on the map, 0 = off it
```

The scale is a **per-object field**, and the 440/256 here are range tests. The
function returns a success flag; the caller skips the note entirely when it is 0.

**3. Corroboration.** reone (`src/libs/game/gui/map.cpp`, clean-room, no
decompilation) computes the same transform from the `.are` `Map` struct:

```cpp
scaleX = (_mapPoint1.x - _mapPoint2.x) / (_worldPoint1.x - _worldPoint2.x);
result.x = (world.x - _worldPoint1.x) * scaleX + _mapPoint1.x;
```

Algebraically identical to the engine's per-object form -- `[esi+0x18]` is that
scale reciprocal and `[esi+0x20]` that origin, both computed at map load from
`MapPt1/2` and `WorldPt1/2`. reone also confirms what the three `NorthAxis`
branches do: cases 0 and 1 pass through, cases 2 and 3 **swap the axes**.

**4. Numeric proof.** Taking `ebo_m12aa`'s `.are` calibration
(`MapPt1 = 0.2682, 0.3593`, `MapPt2 = 0.6114, 0.7222`,
`WorldPt1 = 19.3, 56.2`, `WorldPt2 = 65.4, 26.3`, `NorthAxis = 0`), applying the
transform to all 33 note positions and multiplying by 440 x 256 reproduces
**all seven** of the stock marker centres recorded earlier in this file, to
sub-pixel accuracy:

| note | computed | recorded |
| --- | --- | --- |
| Port crew quarters | (130.8, 98.1) | (131, 98) |
| Cargo hold | (144.4, 171.7) | (144, 172) |
| Cockpit | (227.7, 17.5) | (228, 17) |
| Swoop hangar | (284.0, 181.4) | (284, 182) |
| Starboard crew quarters | (319.3, 91.9) | (319, 92) |
| Engine room | (216.8, 244.0) | (217, 244) |
| Exit ramp | (274.0, 110.0) | (274, 110) |

That closes the loop: the recorded centres were read off the screen, and they
fall out of the module data plus the transform above.

**5. KMRP's wrapper.** Gold replaces the `call 0x00578E00` at `0x006946F4` with
`0x0086D000`, which calls the original and then, only on success, rescales:

```
x = (x * [ebx+0x0C] + 220) / 440      [ebx+0x0C] = 1478
y = (y * [ebx+0x10] + 128) / 256      [ebx+0x10] =  720
```

**6. What the caller does with it.** Vanilla, and unchanged by gold:

```asm
0069470D  mov  eax, [esp+0x20]   ; X
00694711  mov  ecx, [esp+0x10]   ; Y
00694718  add  eax, -0x0A        ; X - 10
00694724  add  ecx, -0x0A        ; Y - 10
0069471F  mov  eax, 0x14         ; 20
0069472B  [esp+0x30] = 20        ; a 20x20 icon centred on the point
```

So the wrapper's output **is** the final icon rectangle. Nothing else rescales
it afterwards. The note icon stays 20x20 in gold; the player arrow is the one
marker gold does resize, at `0x0069405B`, `0x20` -> `0x28`.

**7. Which makes the lattice unavoidable in this design.** Step 2 rounds to an
integer in 440x256 space and step 5 multiplies that integer up, so a note can
only land on multiples of 1478/440 = 3.36 px horizontally and 720/256 = 2.81 px
vertically. See the precision section above.

**Not part of this chain:** the `fdivr [0x747748]` / `fdivr [0x7455D4]` pair at
`0x006944A8` / `0x006944C4`. Those are `fild` of a stack counter followed by a
**reverse** divide -- they compute *440 / n* and *256 / n* as ratios during the
icon container's grid setup, not a coordinate normalisation. An earlier reading
of this file treated them as part of the marker path; they are not.

### Marker coordinate precision, and the lattice it costs

Every statement here was read out of the binaries; the arithmetic follows from
those values.

**The vanilla conversion is float maths that truncates once, at the end.**
`0x00578E00`, disassembled from the clean executable:

```asm
00578E61  fsub  dword ptr [esi+0x20]   ; world - origin
00578E64  fdiv  dword ptr [esi+0x18]   ; / world-units-per-pixel  <- PER-OBJECT field
00578E67  fadd  dword ptr [0x73E9AC]   ; + 0.5
00578E6D  call  0x006FAE8C             ; float -> int
...
00578E99  cmp   ecx, 0x1B8             ; 440  <- BOUNDS CHECK, not a scale
00578EA5  cmp   eax, 0x100             ; 256  <- BOUNDS CHECK, not a scale
```

So the scale divisor is `[esi+0x18]` / `[esi+0x1C]`, not a global constant, and
the `440` / `256` immediates inside this function are range tests (`cmp` + `jg`)
that decide whether the point is on the map at all.

**KMRP's wrappers receive an already-truncated integer.** Both read the result
with `mov eax, dword ptr [esi]` and rescale it with integer `imul` / `idiv`. The
rounding therefore happens in vanilla 440x256 space, before any KMRP code runs,
and no post-scaling can recover what it discarded.

**The resulting lattice**, on the 1478x720 marker overlay:

| axis | step |
| --- | --- |
| horizontal | 1478 / 440 = **3.36 px** |
| vertical | 720 / 256 = **2.81 px** |

That is 0.23% of the map's width. Map notes are static, so it is invisible for
them; for the player arrow it is a ~3 px step as the player moves. **Whether
that is perceptible has not been tested** -- if it ever looks like stepping
rather than sliding, this is the cause.

**It is a deliberate trade, not an oversight.** Removing it means the rounding
has to happen in 1478x720 space, which requires either widening the bounds
checks at `0x00578E99` / `0x00578EA5` -- in a routine the HUD minimap also calls,
which is the shared-state risk this design exists to avoid -- or giving the map a
private copy of the conversion and then following the normalisation chain
further. The `+0xDC` / `+0x80` rounding in the wrappers removes the systematic
bias but cannot restore the lost resolution.

**Where the two shared floats are actually used.** Found by scanning the clean
image for references to their addresses:

| | referenced from |
| --- | --- |
| `0x00747748` (440.0f) | `0x00509D1B`, `0x00578F3E`, `0x00688153`, `0x006944A8` |
| `0x007455D4` (256.0f) | `0x00509DD6`, `0x00688161`, `0x006944C4` |

`0x006944A8` / `0x006944C4` are in the full map's icon loop (`0x006943D0`);
`0x00688153` / `0x00688161` are in the HUD path. Both maps reach the same two
constants, which is exactly why they cannot be edited in place. KMRP writes
neither address -- verified against gold and against a patcher-produced
executable.

### Independent corroboration: K1 Area Map Fixes 1.0.0

*Derslok, GPL-3.0, downloaded for comparison only and not adopted. Kept out of
this repository; nothing from it is redistributed here.*

It patches the same executable for the same purpose and reached the same
diagnosis independently: the constants the area map divides by are shared with
the HUD minimap, and editing them in place "turns the minimap black". Its fix
writes scaled private copies at `0x0078CC00` and repoints only the map's own
operands -- a **pre**-scale where KMRP **post**-scales. Same destination,
opposite order, and its version does not pay the lattice above because it had to
touch those routines anyway.

Two findings from its published source are worth keeping.

**It independently disproved the theory that the four constructor immediates
belong to the minimap.** Its own comment:

> TRIED AND REVERTED 2026-08-23 (first minimap attempt): excluding
> map_projection_offsets_x (0x29505C) + one map_offsets_y entry (0x295064) from
> scaling. Theory was that this (512,256) pair belonged to the HUD minimap.
> WRONG - it didn't fix the minimap and it broke the big map's room geometry.

That is the same conclusion gold relies on when it enlarges those four globally.

**The two mods are mutually exclusive.** Measured by diffing clean -> gold ->
patcher output and intersecting with the offsets its source lists: **14 offsets
where both write the same bytes**, including `0x0040AA65` / `0x0040AA85`
(KMRP's resolution constants), both recentring helpers, the map centring pair,
and the four constructor immediates. Beyond that, both append their added data at
file offset `0x3DB000` -- the first byte past the end of the clean image -- and
its marker hooks land byte-adjacent to KMRP's in the same three functions.

It also expects `0x00755788` to hold `0.428571` (3/7); gold writes `0.285714`
(2/7) there for the dialogue letterbox, so its verification would reject a
KMRP-patched executable on that byte alone.

The one thing it has that KMRP does not is a **250-entry map-note correction
table**, keyed on world position rather than module or index. Of the Ebon Hawk's
33 map notes it corrects 7 -- the same seven whose placement is noted above --
and converted through that area's own map transform the corrections are between
14 and **90 px** on the 1478x720 overlay. KMRP scales the vanilla positions
faithfully, so those notes land wrong at every resolution; this repository has
always classified that as content data rather than a scaling fault, which is
correct, but it does mean the notes are still wrong on screen.

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
| 512x512 (vanilla, and 9 of 10 variants) | 512x256 | a second draw of the same map -- duplicated |
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

**Corrected 2026-09-02: the premise below was wrong.** The area atlases are not
transparent. Measured over `swpc_tex_gui.erf`, 91 of the 92 are alpha 255
everywhere; the 95.7%-transparent figure was `lbl_minimap.tga`, the border ring,
not the maps. What the border experiment actually showed, per the in-game report,
is grid **around** the view and black where the map ends -- i.e. the fill never
reaches inside `LBL_MAPVIEW`'s clip at all. Either way the route is dead, and for
a simpler reason than recorded: nothing drawn behind an opaque map can appear
past its edge.

The original, mistaken reasoning is kept below for the record: the area map
textures are themselves mostly transparent -- only the walkable geometry is
painted -- so the backdrop shows through across the **whole** minimap, not only
past the map's edge.
It is therefore a decision about what the minimap's empty space looks like, not a
localised edge fix. A first attempt at rgb(12,24,52) with rgb(46,88,165) lines
every 12px read as a grid laid over the map. Subtler variants (near-black navy
with and without lines) were built but not adopted; the black was kept.

If this is revisited, the mechanism is settled and only the artwork is open. Fill
`lbl_minimap.tga`'s interior and ship it through `override-common.zip` so every
resolution picks it up -- no exe patch, no clamping, no arrow desync, and vanilla
framing is preserved.

## The padded atlas -- the route that is actually shaped like the hole

Built 2026-09-02, awaiting playtest. Three coupled pieces:

* `tools/build_padded_minimap_atlases.py` paints a 632x632 canvas, drops the
  stock 512-wide content in at (60, 60) and fills the surround. 92 area atlases;
  the 5 `lbl_map*` HUD icons are excluded by name;
* `LBL_MAP`'s extent becomes 632x632 (`scale_hud_minimap.py --map-surface 632`),
  so the source rect equals the texture exactly. No overrun, so no wrap, so no
  duplication -- the constraint that forced 512x256 is gone rather than traded;
* the `.kmz` stub gains a second accepted geometry. For a 632x632 rect it adds
  back zero instead of the viewport centre, which subtracts exactly the 60-unit
  content offset: `60 * W / 120` is `W / 2`, the centre itself. So the map
  content lands on the identical screen pixels, and the player arrow -- which the
  engine pins to the viewport centre and never moves -- stays correct. That is
  the property candidate 006's pan clamp lacked.

60 map units is half the 120-unit window, the furthest the view can ever reach
past the content, so the margin covers every edge of every area. Verified
arithmetically against the x64dbg capture: at a 270 viewport with pan x = -70,
the stock path gives content at -326 and the padded path gives rect -461 with
content at -461 + 135 = -326. Identical, with no rounding drift, since the
`idiv` truncation happens before an integer offset in both.

The stub accepts both geometries, so one exe works with a padded or unpadded GUI.
At a 120 viewport it is still the identity.

## The fog grid -- `0x00688100`, a separate draw with its own basis

Found 2026-09-02 while investigating a report that explored ground re-fogs once
it leaves the centre of the view. `0x0068AC9F` calls `0x00688100`, which walks
the explored bitset (`sar eax, 5` then `test [edx+eax*4], ecx` with
`and ecx, 0x8000001F`) and emits one quad per unexplored 4-unit tile. Its
coordinates come from

    [0x00747748] = 440.0     the area map's viewport width
    [0x007455D4] = 256.0     ... and height

divided by `[edi+0x6088]` / `[edi+0x608C]`, the live minimap viewport. Both
constants are exactly KPM's `AreaMapViewportWidth` / `AreaMapViewportHeight`.

**The fog therefore has a scale basis entirely independent of the map's.** The
map is sized by `LBL_MAP`'s extent against the viewport at `0x00459920`; the fog
is sized by 440x256 against the same viewport here. In vanilla, at a 120
viewport, the two agree. Enlarging `LBL_MAPVIEW` to 270 shrinks both by 2.25, so
they still agree -- which is why an unpatched KMRP build looks consistent, merely
zoomed out. The `.kmz` patch then restores the *map* to vanilla's ratio and
leaves the fog at 1/2.25 of it, so the two desynchronise.

KPM handles precisely this in `beginHudMinimapGridZoom` / `endHudMinimapGridZoom`:
around the grid draw it pins the two constants to 440/256, writes 120 into
`hud+0x6088` and `hud+0x608C`, and shifts the rect by `(viewport - 120) / 2`,
restoring afterwards. A smaller divisor makes the normalised coordinates larger,
so the grid zooms by the same 2.25 the map does, and the shift recentres it.

For us that is one more wrapper around the call at `0x0068AC9F` -- not a change
to `0x00688100` itself, which is shared. Not yet built.

## Measured under x64dbg, 2026-09-02: the fog fix, and two corrections

Attached to the running `.kmz` + `.kfg` build at 3440x1440, viewport index 1 =
270x270 (the minimap).

**The duplication is two draw calls, not a sampler wrap.** Breaking at
`0x0045992A` with `[esp+0x10] == 512` caught two hits in one frame:

| hit | x | y | w | h |
| --- | --- | --- | --- | --- |
| 1 | -70 | -72 | 512 | 256 |
| 2 | -70 | **+184** | 512 | 256 |

`+184 = -72 + 256`, exactly one texture height down. The engine tiles the
512x256 atlas down the 512-tall control rather than letting a sampler repeat it.
Everything previously written here about UV overrun and address modes was wrong
about the mechanism, though right about the outcome.

**`LBL_MAP`'s height does not set that rect.** The GUI on disk was verified as
512x512 at the time of the capture and the rect still arrived as `h = 256`: the
height is the atlas's own. What the extent controls is how many tiles get
emitted. So `mipc210x7`'s 512x256 suppressed the second draw, which is why it
showed black where the others show a duplicate.

**The `.kfg` fog wrapper does what it was derived to do.** During the fog draw:

| read | value |
| --- | --- |
| `hud+0x6088` / `hud+0x608C` | **120**, 120 -- the basis, substituted |
| pan point behind the argument pointer | **(-145, -147)** = (-70, -72) - 75 |

and the fog's own numbers, from the stack inside `0x00688100`:

| | |
| --- | --- |
| grid | A = 20 cells across, B = 11 down |
| `440/A`, `256/B` | 22.0 and 23.2727 map units per cell |
| tile size | 88.0 x 93.0909 map units |

Screen pixels per unit, which is the only figure that decides whether the fog
matches the map:

| | |
| --- | --- |
| map | 512 texels -> 1152 px after the stub = **2.25 px/texel** |
| fog, horizontal | 88.0 / 120 * 270 = 198 px per tile / 88 = **2.25 px/unit** |
| fog, vertical | 93.0909 / 120 * 270 = 209.4 px per tile / 93.09 = **2.25 px/unit** |

Identical on both axes, so the fog occupies exactly the fraction of the minimap
it does in vanilla -- about 5.5 cells across the view either way. It reads as
coarser only because a cell is 49.5 x 52.4 screen pixels instead of 22 x 23.3.
The cells are also not square (22 wide by 23.27 tall here), which comes from the
per-area grid dimensions, not from any patch.

**Still open: the fog domain is 440 units wide, the atlas is 512.** If an area's
map content actually reaches texel 511 the fog under-covers the right ~14% --
too narrow, not too wide. Vanilla-inherited, unchanged by any of this work, and
untested. Symptom to watch for: fog that stops short of the map's right edge.

## Before editing this executable again

`.kmz` and `.kfg` are two of five cumulative sections, and a tool that edits one
is editing a file that already carries the others. The invariants -- above all
that an in-place edit must not change the file length, because section raw
offsets are absolute -- are in [exe-patching.md](exe-patching.md), along with the
failure signatures that identify a slide rather than a logic bug.
