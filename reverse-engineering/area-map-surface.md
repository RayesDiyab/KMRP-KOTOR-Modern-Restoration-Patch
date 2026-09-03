# Area map surface: the canvas, the overlay, and the right-hand strip

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: reference**, with a lab record beside it in
[`experiments/area-map-surface/observations.json`](experiments/area-map-surface/observations.json).

The full-screen area map draws its picture onto one rectangle (the **canvas**)
and its fog grid and markers onto a second, narrower one (the **marker
overlay**). This document is about the relationship between those two and the
`LBL_Map` control that shows them, because getting it wrong is what produces the
**unfogged strip down the right-hand side of the map**.

[`map-scaling.md`](map-scaling.md) covers the coordinate chain and every
per-resolution byte; [`map-markers.md`](map-markers.md) covers marker sizes.
This covers the surface itself.

## The build this describes

| | |
| --- | --- |
| clean | `swkotornopatch.exe`, 4,042,752 bytes, `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886` |
| gold | `swkotor_gold_v19_areafog.exe`, `D4D4B793F333732D31FBD6D1C66778D527CD15D0DE20894DAC25E88132943A1E` |
| measured at | 3440x1440, Manaan West Central (module `m26`, texture `lbl_mapm26ab`) |

Addresses are `VA` unless labelled `FILE`. `FILE = VA − 0x400000` for the
original sections; appended sections use `FILE = VA − 0x492000`.

## 1. What the engine actually does

Two rectangles are created when the map screen is constructed, by two adjacent
blocks that differ only in which object they size:

```asm
0069504D  lea   ecx, [esi+0x1080]           ; the CANVAS object
00695058  mov   dword ptr [esp+0x1C], 0x6B8 ; 1720   canvas width   (vanilla 512)
00695060  mov   dword ptr [esp+0x20], 0x2D0 ; 720    canvas height  (vanilla 256)
00695068  call  dword ptr [edx+4]

0069507C  mov   ecx, edi                    ; the ICON CONTAINER object
0069507E  mov   dword ptr [esp+0x1C], 0x5C6 ; 1478   overlay width  (vanilla 440)
00695086  mov   dword ptr [esp+0x20], 0x2D0 ; 720    overlay height (vanilla 256)
0069508E  call  dword ptr [edx+4]
```

The fog grid is drawn by the icon container's own method at `0x006943D0`, whose
`this` is that second object. Read live with x64dbg, breakpoint at `0x006944A8`:

```
ebx = 0x15B37740
[ebx+0x04] = 0        left
[ebx+0x08] = 0        top
[ebx+0x0C] = 1478     width    <- the OVERLAY, not the canvas
[ebx+0x10] = 720      height
[esp+0x44] = 20       grid columns
[esp+0x50] = 11       grid rows
```

So the grid is built and normalised inside a 1478-wide rectangle while the map
picture is drawn inside a 1720-wide one. The 242 columns of canvas that the
overlay does not reach are drawn with picture and never covered by a fog tile.
That is the strip:

```
strip = canvas_width − overlay_width = 1720 − 1478 = 242 px
```

**Measured 242 px in four independent captures** (§6), including two where the
grid's tile size was deliberately changed. The strip never moved.

### It is not the map textures

The obvious suspect — the installed *Vanilla Maps HD* pack painting content into
a region vanilla left blank — is wrong. Read with pykotor:

| source | size | mean of columns past 440/512 | max |
| --- | --- | --- | --- |
| `swpc_tex_gui.erf`, `lbl_mapm26ab` | 512x256 | 33.6 | 115 |
| installed HD override, same name | 2048x1024 | 33.9 | 151 |

Vanilla's own atlas carries the same picture there. Nothing about the HD pack
causes this.

## 2. The three schemes, and where KMRP differs

| | canvas | overlay | `LBL_Map` in `map.gui` |
| --- | --- | --- | --- |
| **vanilla** (640x480) | 512 x 256 | 440 x 256 | **440 x 256** |
| **k1hrm + hires_patcher / K1AMF** | `w·512/640`, `h·256/480` | `w·440/640`, `h·256/480` | equals the overlay |
| **KMRP** | `w//2`, `h//2` | `canvasW·440/512`, `canvasH` | inherited from k1hrm, unchanged |

In vanilla and in the k1hrm scheme, **`LBL_Map` is exactly the overlay**. The
canvas is wider than `LBL_Map`, so the surplus is never shown. KMRP keeps
k1hrm's `LBL_Map` but makes the canvas *smaller* than it, so nothing is cropped
and the surplus becomes visible.

The `LBL_Map` claim is not an assumption. Reading `LBL_Map` out of every shipped
`map.gui` and comparing against `w·440/640` x `h·256/480`:

```
resolution     GUI LBL_Map    hires_patcher overlay
1024x576        704x307         704x307     MATCH
1280x720        880x384         880x384     MATCH
2560x1600      1760x853        1760x853     MATCH
3440x1440      2365x768        2365x768     MATCH
15360x8640    10560x4608      10560x4608    MATCH
```

**49 of 49 exact**, plus vanilla (640x480 -> 440x256, and vanilla's `LBL_Map`
read from `data\gui.bif` is 440x256). Reproduce with the snippet in §8.

At 3440x1440 KMRP is uniformly **62.5%** of that scheme horizontally
(`0.5 / 0.8`) and **93.75%** vertically (`0.5 / 0.5333`):

| | KMRP | k1hrm scheme |
| --- | --- | --- |
| canvas | 1720 x 720 | 2752 x 768 |
| overlay | 1478 x 720 | 2365 x 768 |

## 3. Where the canvas lands on screen

Derived from two captures that differ only in the centring immediate:

```
canvas_left = LBL_Map.left + (screenWidth − centringX) / 2
```

| centringX | predicted | measured (`grid.first`) | delta |
| --- | --- | --- | --- |
| 2750 (KMRP) | 856.0 | 851 | +5.0 |
| 3440 (k1hrm scheme) | 511.0 | 511 | 0.0 |

The +5 is one grid-line width: `grid.first` is the centre of the first line, not
the surface edge. KMRP's own formula for the immediate,
`centringX = (LBL_Map.left + 4)·2 + canvasWidth`, evaluates to 2750 and places
the canvas centre at 1716 against a screen centre of 1720 — that is, KMRP's
centring exists to **centre the canvas on the screen**, ignoring `LBL_Map`.

**Consequence.** For `LBL_Map` to crop the canvas the way vanilla does, the
canvas must start at `LBL_Map.left`, which requires

```
centringX == screenWidth
```

which is exactly the value the k1hrm scheme writes. The vertical is the same
shape with the renderer's 14 px top inset:
`centringY = (LBL_Map.top − 14)·2 + canvasHeight`. **The vertical rule is
derived by analogy and checked to about ±8 px on one capture — treat it as
less firmly established than the horizontal.**

## 4. What this means for the fix

Two candidates. Neither is implemented yet; this section is a plan, not a record
of shipped behaviour.

**Option A — adopt the k1hrm/hires_patcher geometry.** Set canvas and overlay to
`w·512/640` / `w·440/640`, and both centring immediates to the screen size.
`LBL_Map` then already matches the overlay at all 49 resolutions and no GUI file
changes at all. The visible map grows by 1/0.625 = 60% horizontally.
**Open risk:** the frame art around the map measures roughly 1782 px of interior
at 3440x1440, narrower than the 2365 the map would become. Whether the map is
drawn behind that art (and so visually cropped by it) or over it is
**not established** and must be tested before this option is chosen.

**Option B — keep KMRP's canvas, make `LBL_Map` crop it.** Keep
`canvas = screen//2`, set `centringX/Y = screenWidth/Height`, and set `LBL_Map`
to the overlay size positioned where the map should sit:
`LBL_Map = ((screenW − overlayW)/2, (screenH − canvasH)/2 + 14, overlayW, canvasH)`
= `(981, 374, 1478, 720)` at 3440x1440. The map keeps its current size and stays
centred; the strip is cropped away exactly as vanilla crops it. Costs a GUI
transform across 48 resolutions plus the two centring immediates.

Option B is the smaller, better-understood change. Option A is the more faithful
one and needs the frame-art question answered first.

## 5. What is deliberately not changed

* `0x00747748` (440.0f) and `0x007455D4` (256.0f). Shared with the HUD minimap
  walker at `0x00688153` / `0x00688161`. Gold v19 changes the *instructions* at
  `0x006944A8` / `0x006944C4` to stop reading them, but never writes the floats.
  See [`map-scaling.md`](map-scaling.md) §7.
* `0x00692959` / `0x0069296B`, the second centring pair, left at vanilla 640/480
  for the reason recorded in `map-scaling.md` §7. **Note:** K1AMF's
  `TECHNICAL.txt` writes all four and states that leaving them vanilla draws the
  map `((W−640)/2, (H−480)/2)` off its box. KMRP does not observe that offset,
  which is consistent with `map-scaling.md`'s finding that this pair is reached
  from a different vtable slot — but the two accounts have not been reconciled
  against each other and that is **untested**.

## 6. Corrections

Three claims made during this investigation were wrong and are recorded because
each one cost a rebuild or a play-test.

| claimed | actually |
| --- | --- |
| "The 1720 private-float build never took effect." | It did. `map-fog-v19b.png` measures a grid pitch of exactly 86.0 = 1720/20. It took effect and did not move the strip. |
| "The strip is caused by the HD map textures." | The vanilla atlas has the same content past column 440 (mean 33.6 vs 33.9). |
| "The grid divisor controls where the grid ends." | Divisors of 1478 and 1720 both yield a grid clipped at ~1478 and a strip of exactly 242 px. The grid is bounded by the overlay, not by the divisor. |

A fourth, in [`map.md`](map.md): its field table gives `+0x0C` as
"Icon normalization width — **1720** for full-map instance". Read live it is
**1478**. The field holds the overlay width, which is what the immediate at
`0x00695082` writes. Corrected here rather than silently in `map.md`.

## 7. Limits

* Every screen measurement here is at **3440x1440 only**, on one area. The
  formulas in §2 are read from the shipped GUI files at all 49 resolutions, but
  nothing has been looked at in game at any other resolution.
* The vertical placement rule in §3 is checked on one capture to ±8 px.
* The frame-art question in §4 is open.
* A practical trap found while testing: the canvas and overlay immediates at
  `0x0069505C`/`0x00695082` run **once, when the map screen is constructed**.
  Patching them in a running process and reopening the map does *not* re-read
  them — the object persists. Only the centring immediates at `0x006928B3` /
  `0x006928C3` are read per draw. An in-memory A/B of the size constants
  therefore needs a game restart, not a screen reopen.

## 8. Verifying by hand

Read the six per-resolution constants out of a patched executable:

```bash
python -c "import struct; d=open('swkotor.exe','rb').read(); print([struct.unpack_from('<i',d,o)[0] for o in (0x2928B3,0x2928C3,0x29505C,0x295064,0x295082,0x29508A)])"
```

At 3440x1440 gold v19 this prints `[2750, 1400, 1720, 720, 1478, 720]`.

Confirm `LBL_Map` equals the hires_patcher overlay at every shipped resolution:

```bash
python tools/dump_gui_extents.py third_party/kotor-high-resolution-menus-1.5/16-by-9/gui.1280x720/map.gui
# LBL_Map extent=(190, 177, 880, 384);  1280*440/640 = 880,  720*256/480 = 384
```

Measure a screenshot, reproducibly:

```bash
python tools/measure_map_screen.py shot.png
```

It reports the grid's first and last column, its **pitch**, and the strip. The
pitch is the falsifiable check: it must equal `divisor / grid_columns`, where the
divisor is whatever `0x006944A8` reads and the column count comes from the area.
At 3440x1440 on Manaan West Central that is `1478 / 20 = 73.9`, and the tool
measures 74.0.

Read the live rectangle rather than trusting any of this:

```
x64dbg: bp 0x006944A8, then evaluate [ebx+0C], [ebx+10], [esp+44], [esp+50]
```
