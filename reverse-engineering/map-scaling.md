# The area map: what KMRP writes, byte for byte

Published so that a collision with another executable patcher is diagnosable by
someone who is not us, and so that a determined person can reproduce or undo the
work by hand. Everything here was read out of the binaries with a disassembler,
or computed from values read out of them. Where something is untested it says so.

`map.md` is the lab record — what was tried, what failed, what was disproved.
This is the reference for the map surface and the coordinate chain.
**[map-markers.md](map-markers.md)** is the reference for the icons drawn on it.

## The build this describes

The clean **4,042,752-byte** `swkotor.exe`, SHA-256
`761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886` — the
Editable Executable after UniWS and KotOR High Resolution Menus 1.5, which is
also GOG's retail v1.03. KMRP refuses anything else.

Gold v18 (`0AA1A76D…`) is 4,079,616 bytes: the clean image plus nine appended
sections. `ResolutionPatch` then rewrites a small set of constants in place for
the selected resolution, changing no lengths.

## Two address conventions

`VA` is the virtual address a disassembler shows; `FILE` is the byte offset a
hex editor shows. For everything in the original sections **`FILE = VA −
0x400000`**. The nine appended sections start at `FILE 0x3DB000` / `VA
0x0086D000` and are contiguous 4 KB blocks in the order `.kui .klb .kfs .kwl
.ksc .kgs .ktn .kmz .kfg`, so for `.kui` **`FILE = VA − 0x492000`**.

## 1. What the engine actually does

A map note is a waypoint in a module's `.git` carrying a map-note flag; its
position is in world units. Turning that into a pixel is one function:

```asm
00578E00  ; world -> map pixel. ecx = map object, args = (x, y, z), &outX, &outY
00578E10  mov   eax, [esi+0x10]      ; NorthAxis
00578E17  ...   three branches, each fmul [0x740CBC]   ; cases 1, 2, 3
00578E61  fsub  dword ptr [esi+0x20] ; x: world - origin      (y uses +0x24)
00578E64  fdiv  dword ptr [esi+0x18] ; x: / world-units-per-pixel (y: +0x1C)
00578E67  fadd  dword ptr [0x73E9AC] ; + 0.5, so it rounds rather than truncates
00578E6D  call  0x006FAE8C           ; float -> int
00578E99  cmp   ecx, 0x1B8           ; bounds check, 440
00578EA5  cmp   eax, 0x100           ; bounds check, 256
00578EAD  mov   eax, 1               ; 1 = on the map; 0 makes the caller skip it
```

Three things follow, and all three matter:

* the scale and origin are **per-object fields**, not globals;
* the `440` / `256` in this function are **range tests**, not scale factors;
* the result is an **integer in a 440x256 space**, and that rounding is the only
  place precision is lost.

**Corroboration.** reone (`src/libs/game/gui/map.cpp`, clean-room, no
decompilation) computes the same transform from the `.are` `Map` struct:
`scaleX = (mapPt1.x − mapPt2.x) / (worldPt1.x − worldPt2.x)`, then
`(world.x − worldPt1.x) · scaleX + mapPt1.x`. It also confirms the `NorthAxis`
branches: cases 0 and 1 pass through, **cases 2 and 3 swap the axes**.

**Verification.** Applying that transform to all 33 map notes in `ebo_m12aa`,
using its own `.are` calibration, and multiplying by 440x256 reproduces all seven
stock marker centres recorded in `map.md` to sub-pixel accuracy (130.8 vs 131,
144.4 vs 144, 227.7 vs 228, 284.0 vs 284, 319.3 vs 319, 216.8 vs 217, 274.0 vs
274). Those centres were originally read off a screenshot; they now fall out of
module data plus this function.

## 2. The four domains, and how they are derived

| name | meaning | rule |
| --- | --- | --- |
| canvas | the surface the map renders onto | `screenWidth // 2` x `screenHeight // 2` |
| marker overlay | the space marker rectangles live in | `round(canvasWidth · 440 / 512)` x `canvasHeight` |
| centring X | design width the draw path centres against | `(LBL_Map.left + 4) · 2 + canvasWidth` |
| centring Y | design height, ditto | `(LBL_Map.top − 14) · 2 + canvasHeight` |

The canvas is exactly half the screen. The marker overlay is the canvas scaled
by the vanilla 440:512 ratio between the marker domain and the map texture. The
two centring domains are **not** pure formulas — they depend on where `LBL_Map`
sits in that resolution's own `map.gui`, plus two renderer insets (4 px
horizontally, 14 px vertically). They are computed by
`tools/analyze_resolution_guis.py` into `assets/resolution-geometry.json`, and
carried to the patcher through `resolutions.tsv`.

| resolution | centring X | centring Y | canvas | marker overlay |
| --- | --- | --- | --- | --- |
| *clean* | 640 | 480 | 512 x 256 | 440 x 256 |
| 800x600 | 646 | 568 | 400 x 300 | 344 x 300 |
| 1920x1080 | 1538 | 1044 | 960 x 540 | 825 x 540 |
| 3440x1440 | 2750 | 1400 | 1720 x 720 | 1478 x 720 |
| 15360x8640 | 12248 | 8540 | 7680 x 4320 | 6600 x 4320 |

## 3. Every byte KMRP writes for the map

**In place, per resolution** (`ResolutionPatch`, gold holds the 3440x1440 values):

| VA | FILE | size | clean | purpose |
| --- | --- | --- | --- | --- |
| `0x006928B3` | `0x2928B3` | 4 | 640 | horizontal centring domain |
| `0x006928C3` | `0x2928C3` | 4 | 480 | vertical centring domain |
| `0x0069505C` | `0x29505C` | 4 | 512 | canvas width |
| `0x00695064` | `0x295064` | 4 | 256 | canvas height |
| `0x00695082` | `0x295082` | 4 | 440 | marker overlay width |
| `0x0069508A` | `0x29508A` | 4 | 256 | marker overlay height |
| `0x0069471F` | `0x294720` | 4 | 20 | map note size |
| `0x00694718` | `0x29471A` | 1 | -10 | map note centring X |
| `0x00694724` | `0x294726` | 1 | -10 | map note centring Y |
| `0x00694A12` | `0x294A13` | 4 | 16 | party marker size |
| `0x00694A51` | `0x294A53` | 1 | -8 | party centring X |
| `0x00694A54` | `0x294A56` | 1 | -8 | party centring Y |
| `0x00694AC3` | `0x294AC4` | 4 | 32 | player arrow size |
| `0x00694ACE` | `0x294AD0` | 1 | -16 | player arrow centring Y |
| `0x00694AD2` | `0x294AD4` | 1 | -16 | player arrow centring X |
| `0x0069405A` | `0x29405B` | 4 | 32 | player arrow control extent |

**In place, fixed in gold:**

| VA | FILE | size | change | purpose |
| --- | --- | --- | --- | --- |
| `0x0068C4E3` | `0x28C4E3` | 4 | `0x400` -> `0xD70` | `mipc*.gui` variant selector: compare against 3440, not 1024 |

**Call sites redirected into appended sections:**

| VA | FILE | original target | now | purpose |
| --- | --- | --- | --- | --- |
| `0x006946F4` | `0x2946F4` | `0x00578E00` | `0x0086D000` | world objects and map notes |
| `0x00694A39` | `0x294A39` | `0x005791B0` | `0x0086D080` | party markers |
| `0x00694AAC` | `0x294AAC` | `0x005791B0` | `0x0086D080` | player arrow |
| `0x0068ACA1` | `0x28ACA1` | `0x00688100` | `0x00875000` | HUD fog grid (`.kfg`) |
| `0x0075477C` | `0x35477C` | `0x00693300` | `0x0086D100` | area map hit test (vtable slot) |

## 4. The injected code

**Coordinate wrappers** (`0x0086D000` map notes, `0x0086D080` party and arrow).
Both call the original conversion, and rescale only if it succeeded:

```asm
call 0x578E00 / 0x5791B0   ; the vanilla routine, unmodified
test eax, eax
je   skip                  ; off the map: leave the values untouched
imul eax, [ebx+0x0C]       ; x overlay width
add  eax, 0xDC             ; +220 = half of 440, so it rounds
idiv 0x1B8                 ; / 440
imul eax, [ebx+0x10]       ; x overlay height
add  eax, 0x80             ; +128 = half of 256
idiv 0x100                 ; / 256
```

The target size is read **from the object at run time**, which is why one gold
binary serves every resolution.

**Hit-test wrapper** (`0x0086D100`). Derives the centring offset from live
fields, never from a design-size constant, then tail-jumps into the original:

```asm
edx = [eax+0x0C] - [eax+0x108C]   ; canvasW - viewportW
edx >>= 1 ;  [esp+4] -= edx        ; mouse X
edx = [eax+0x10] - [eax+0x1090]   ; canvasH - viewportH
edx >>= 1 ;  edx += 0x0E           ; the +14 Y inset
[esp+8] -= edx                     ; mouse Y
jmp 0x693300
```

**`.kmz`** zooms the HUD minimap's content to its enlarged viewport, scaling the
destination rect by `viewportWidth / 120` about the viewport centre. At a vanilla
120 viewport it is the identity. It is gated on a square viewport of 121..2048
*and* a source rect of exactly 512x(256 or 512); any other caller of
`0x00459920` falls through untouched, because that function is not
minimap-specific and an earlier unconditional version broke unrelated screens.

**`.kfg`** matches the fog grid to the same basis.

## 5. How the map and the minimap stay separate

Three independent mechanisms, none of which duplicates a shared constant:

1. **Only the full map's call sites are redirected.** The three wrappers are
   hooked at calls made by the full-screen map draw function. The minimap reaches
   its coordinates through other call sites and never enters our code.
2. **The minimap's geometry comes from the GUI**, not the executable. Per
   resolution, `mipc*.gui` sets `LBL_MAPVIEW` (120x120 -> 270x270 at 3440x1440),
   `LBL_MAPBORDER` and `LBL_ARROW`. `LBL_MAP` goes from vanilla's 512x512 to
   **512x256**, which is also what removes vanilla's duplicated second draw: a
   512x512 extent over a 512x256 texture makes the engine emit a copy one texture
   height down.
3. **The content zoom is gated**, as above, so it cannot leak into other screens.

Consequently the two shared float constants at `0x00747748` (440.0) and
`0x007455D4` (256.0) are **left exactly as BioWare shipped them**. Both maps
still read the originals. Other patchers that rewrite the map's scale constants
in place must give the map private copies of those floats to stop the minimap
turning black; KMRP has nothing to privatise because it modifies nothing shared.

## 5a. Marker sizes

Moved to **[map-markers.md](map-markers.md)**, which documents all fourteen
sites, the two draw paths a map note has, and the scale rule.

## 6. Precision: the lattice this design costs

The conversion rounds to an integer in 440x256 space *before* the wrapper runs,
so a marker can only land on a lattice:

```
lattice_x = overlayWidth  / 440 = screenWidth  / 1024
lattice_y = overlayHeight / 256 = screenHeight / 512
```

| resolution | lattice |
| --- | --- |
| 800x600 | 0.78 x 1.17 px — finer than a pixel, no loss at all |
| 1920x1080 | 1.88 x 2.11 px |
| 3440x1440 | 3.36 x 2.81 px |
| 15360x8640 | 15.0 x 16.9 px |

In absolute pixels this grows with resolution; **in proportion it is constant**,
always 1/440 of the map's width, so the worst-case error is 0.11% of the map
either way. The `+0xDC` / `+0x80` rounding removes the systematic bias but cannot
restore discarded resolution.

**This is a deliberate trade.** Removing it means rounding in the enlarged domain,
which requires either widening the bounds checks at `0x00578E99` / `0x00578EA5`
in a routine the HUD minimap also calls — the shared-state risk this design
exists to avoid — or giving the map a private copy of the conversion and
following the chain further. A patcher that already rewrites those routines gets
the extra precision for free; KMRP would be paying for it.

**Untested:** whether the lattice is perceptible. Map notes are static, so it
cannot show on them; for the player arrow it is a step of one lattice unit as the
player moves. If anyone reports markers looking slightly off, or the arrow
stepping rather than sliding at very high resolution, this is the first thing to
check.

## 7. What is deliberately not changed

* `0x00747748` (440.0f) and `0x007455D4` (256.0f) — shared with the HUD path
  (`0x00688153` / `0x00688161`) as well as the map's icon loop
  (`0x006944A8` / `0x006944C4`). Never written.
* `0x00578E00`, `0x005791B0`, `0x00579090` — the conversion routines themselves.
  Called, never modified.
* `0x00633102` — the map screen's constructor call. Left as `call 0x694D50`.
* `0x00692959` / `0x0069296B` — a second pair of centring immediates with the
  same instruction shape as the draw pair, left at the vanilla 640/480. This is
  **not** a missed second copy: `0x00692930` is referenced once in the image, at
  `0x00754870`, which is not the area map's hit-test slot, and our hit-test
  wrapper derives its centring from live fields rather than a constant.

## 8. Verifying this by hand

```powershell
# produce a patched copy at any supported resolution, leaving the original alone
& '.\dist\KMRP - KOTOR Modern Restoration Patch.exe' --apply `
    .\build-inputs\swkotornopatch.exe .\out.exe 1920x1080
```

Then read the six per-resolution constants at the FILE offsets in section 3 and
check them against the table in section 2. `tools/verify_map_patch.py` carries the
`PEImage` helper used throughout this repository for exactly that.

Every claim in this document can be re-derived from the clean executable, gold,
and a patcher-produced executable — no state on the build machine is required.
