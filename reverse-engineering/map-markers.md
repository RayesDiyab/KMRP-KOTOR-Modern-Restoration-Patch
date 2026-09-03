# Area map markers: what KMRP writes, byte for byte

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


The icons drawn *on* the area map — map notes, party members and the player
arrow. `map-scaling.md` covers the map surface itself and the coordinate chain
that decides *where* a marker goes; this covers *what is drawn there* and how big
it is.

Everything below was disassembled from the clean executable or read out of gold
and a patcher-produced executable. Where something is untested it says so.

## The build this describes

Clean `swkotor.exe`, 4,042,752 bytes, SHA-256 `761F9466…C49E9886`. Gold v20
(`ACD521B8…`), 4,079,616 bytes, length unchanged by every edit in this document.

Sections 1-4 are in-place immediate rewrites and use `FILE = VA − 0x400000`.
Sections 5 and 6 involve the injected `.kui` section, where the convention is
**`FILE = VA − 0x492000`** — mixing the two produces offsets that land nowhere.

Scope note: this is the whole marker subsystem — how big a marker is drawn
(§1-4), where it is drawn (§5), and where it can be clicked (§6). The map
*surface* those three sit on is
[`area-map-surface.md`](area-map-surface.md); the per-resolution domain
derivation is [`map-scaling.md`](map-scaling.md).

## 1. Three markers, four draw paths

| marker | texture | verified from |
| --- | --- | --- |
| player arrow | `mm_barrow` | `push 0x0075472C` at `0x0069404C` |
| party member, and unselected notes | `lbl_mapcircle` | `push 0x0075471C` at `0x006940CD` |
| selected map note | `whitetarget` | `push 0x00754710` at `0x006947CD`, `0x006947DE` |

The texture names were read out of the image, not taken from another project's
notes.

**A map note has two draw paths, not one.** This is the thing that makes the
subsystem easy to half-fix:

```asm
006946F4  call 0x00578E00        ; world -> map pixel (KMRP redirects this)
006946F9  test eax, eax
006946FB  je   0x006949C2        ; off the map: draw nothing
00694701  mov  edx, [esp+0x48]   ; this note's index
00694705  cmp  edx, [ebx+0x23C]  ; the selected note's index
0069470B  jne  0x0069475A        ; ---> UNSELECTED path, its own rectangle
0069470D  ...                    ;      SELECTED path, its own rectangle
```

Each side has its own size immediate and its own pair of centring offsets. Scale
only the selected side and every other note on the map stays vanilla-sized —
which is exactly what KMRP shipped in gold v16 and v17 before this was found.

## 2. How a marker rectangle is built

Identical in shape on all four paths. The converted pixel is the marker's
*centre*, so the rectangle's origin is the centre minus half the size:

```asm
; selected note, 0x0069470D onward
0069470D  mov  eax, [esp+0x20]   ; X from the conversion
00694711  mov  ecx, [esp+0x10]   ; Y
00694718  add  eax, -0x0A        ; X - size/2
00694724  add  ecx, -0x0A        ; Y - size/2
0069471F  mov  eax, 0x14         ; size 20
00694727  mov  [esp+0x2C], eax   ; width
0069472B  mov  [esp+0x30], eax   ; height
0069471B  mov  [esp+0x24], eax   ; left
00694736  mov  [esp+0x28], ecx   ; top
```

**The invariant is `offset = −size / 2` on every path.** A size changed without
its offsets moves the icon off the point it marks by half the difference.

## 3. Every byte KMRP writes

Fourteen sites. All are per-resolution (`ResolutionPatch`); gold holds the
3440×1440 values.

**Sizes** — `mov r32, imm32`, so any value fits:

| VA | FILE | vanilla | gold | what |
| --- | --- | --- | --- | --- |
| `0x0069471F` | `0x294720` | 20 | 40 | map note, **selected** |
| `0x00694762` | `0x294763` | 14 | 28 | map note, **unselected** |
| `0x00694A12` | `0x294A13` | 16 | 32 | party marker |
| `0x00694AC3` | `0x294AC4` | 32 | 64 | player arrow |
| `0x0069405A` | `0x29405B` | 32 | 64 | `mm_barrow` control extent |
| `0x006940DB` | `0x2940DC` | 16 | 32 | `lbl_mapcircle` control extent |

**Centring offsets** — `add r32, imm8`, three bytes, range −128..127:

| VA | FILE | vanilla | gold | what |
| --- | --- | --- | --- | --- |
| `0x00694718` | `0x29471A` | −10 | −20 | note X, selected |
| `0x00694724` | `0x294726` | −10 | −20 | note Y, selected |
| `0x00694775` | `0x294777` | −7 | −14 | note X, **unselected** |
| `0x00694778` | `0x29477A` | −7 | −14 | note Y, **unselected** |
| `0x00694A51` | `0x294A53` | −8 | −16 | party X |
| `0x00694A54` | `0x294A56` | −8 | −16 | party Y |
| `0x00694ACE` | `0x294AD0` | −16 | −32 | arrow Y |
| `0x00694AD2` | `0x294AD4` | −16 | −32 | arrow X |

The last two sizes are **control extents**, set once when the marker control is
constructed rather than per frame, and they have no paired offset. The two of
them sit in parallel constructions a few instructions apart — finding one and not
the other is the second way this subsystem gets half-fixed.

## 4. The scale rule

`max(1, height / 720)` — the same `ScaleForHeight` the fonts, list rows and
message popup use. 1.00× at 720p, 1.50× at 1080p, **2.00× at 1440p**, 3.00× at
2160p.

| resolution | note sel | note unsel | party | arrow | offsets |
| --- | --- | --- | --- | --- | --- |
| *vanilla* | 20 | 14 | 16 | 32 | −10 / −7 / −8 / −16 |
| 800×600 | 20 | 14 | 16 | 32 | unchanged (factor 1.0) |
| 1920×1080 | 30 | 21 | 24 | 48 | −15 / −10 / −12 / −24 |
| 3440×1440 | 40 | 28 | 32 | 64 | −20 / −14 / −16 / −32 |
| 3840×2160 | 60 | 42 | 48 | 96 | −30 / −21 / −24 / −48 |
| 7680×4320 | 120 | 84 | 96 | 192 | −60 / −42 / −48 / −96 |
| 15360×8640 | 159 | 111 | 127 | 254 | clamped, see below |

**A rejected alternative, recorded so it is not retried.** The first attempt
scaled by the marker overlay's own factor, `overlayWidth / 440` = `screenWidth /
1024`, on the reasoning that it preserves vanilla's *fraction of the map* — 4.5%
of map width at every resolution, measured 4.53–4.65% across the range. It is
defensible arithmetic and it **play-tested too large**: 3.36× at 3440×1440 gives
67 px notes and a 107 px arrow. The map is read at a glance, not studied, so the
font rule wins. The proportional rule is not wrong, it is answering a question
nobody asked.

## 5. Where a marker goes: the coordinate chain

Size and position are separate problems with separate fixes. The engine converts
a world position into a marker position in three steps:

```asm
006946F4  call 0x00578E00        ; world -> map pixel, map notes      (redirected)
00694A39  call 0x005791B0        ; world -> map pixel, party members  (redirected)
00694AAC  call 0x005791B0        ; world -> map pixel, player arrow   (redirected)
```

All three return an **integer in vanilla's 440x256 space**, because the area's
`MapPt1/2` calibration is baked into that space by the `.are` loader. On an
enlarged map that answer is 3.9x too small.

KMRP redirects those three call sites into two wrappers in `.kui`. Each calls the
untouched vanilla routine and rescales only a successful result:

```asm
call 0x578E00 / 0x5791B0   ; the vanilla routine, unmodified
test eax, eax
je   skip                  ; off the map: leave the values alone
imul eax, [ebx+0x0C]       ; x live overlay width
add  eax, 0xDC             ; +220, half of 440, so it rounds
idiv 0x1B8                 ; / 440
imul eax, [ebx+0x10]       ; x live overlay height
add  eax, 0x80             ; +128, half of 256
idiv 0x100                 ; / 256
```

| VA | FILE | original target | redirected to | purpose |
| --- | --- | --- | --- | --- |
| `0x006946F4` | `0x2946F4` | `0x00578E00` | `0x0086D000` | world objects and map notes |
| `0x00694A39` | `0x294A39` | `0x005791B0` | `0x0086D080` | party markers |
| `0x00694AAC` | `0x294AAC` | `0x005791B0` | `0x0086D080` | player arrow |

**The scale factors are read from the object at run time**, not written per
resolution, which is why one gold binary serves all 48. `[ebx+0x0C]` is the
marker overlay width — **measured live with x64dbg at 1478 under gold v19 and
1720 under gold v20**, not 1720-at-v19 as `map.md`'s field table used to claim.

This costs precision, because the vanilla routine rounds to an integer in 440x256
space *before* the wrapper runs. The resulting lattice is
`overlayWidth / 440` by `overlayHeight / 256`, i.e. 3.9 x 2.8 px at 3440x1440
under gold v20 — constant in proportion at 1/440 of the map's width, so the
worst-case error is 0.11% either way. `map-scaling.md` §6 records why that trade
was taken and what removing it would cost.

## 6. Clicking a marker: the hit test

A marker you can see but cannot click is only half-fixed, and this half broke
twice.

The area map has a custom hit test at `0x00693300`, reached through vtable slot
`0x0075477C`. The engine hands it **window** mouse coordinates while drawing the
map into a canvas that is inset within that window, so the two disagree. KMRP
redirects the slot to a wrapper at `0x0086D100` (FILE `0x3DB100`) that subtracts
the inset and tail-jumps into the original.

| VA | FILE | original | redirected to |
| --- | --- | --- | --- |
| `0x0075477C` | `0x35477C` | `0x00693300` | `0x0086D100` |

Gold v20:

```asm
0086D100  mov  eax, [ecx+0x34]     ; the owning CUIMap
0086D103  test eax, eax
0086D105  je   0x0086D128          ; no map: pass the coordinates through
0086D107  mov  edx, [eax+0x0C]     ; window width, 3440
0086D10A  sar  edx, 1              ; 1720
0086D10C  sar  edx, 1              ; 860   = LBL_Map.left
0086D112  sub  [esp+4], edx        ; mouse x
0086D116  mov  edx, [eax+0x10]     ; window height, 1440
0086D119  sub  edx, [eax+0x1090]   ; - canvas height, 720
0086D11F  sar  edx, 1              ; 360
0086D121  add  edx, 0x0E           ; +14, the renderer's top inset
0086D124  sub  [esp+8], edx        ; mouse y  = 374 = LBL_Map.top
0086D128  jmp  0x00693300
```

**Why X and Y are computed differently.** The inset is `LBL_Map.left` and
`LBL_Map.top`, and those are placed by the **overlay**, not the canvas. Vertically
the overlay and canvas heights are equal (`screenHeight // 2`), so centring on
either gives the same number and the original `(window − canvas) / 2` form is
still correct. Horizontally they differ — the canvas is wider and `LBL_Map` crops
the overhang — so that form is wrong. Since
[`area-map-surface.md`](area-map-surface.md) fixes `overlay = screenWidth // 2`,
the X inset collapses to `(W − W/2) / 2 = W / 4`, two shifts and no field lookup.
It is exact at odd widths too: 1366 -> 683 -> 341, and
`(1366 − 683) / 2 = 341`.

**Correction, gold v20.** Through gold v19 the X half read

```asm
0086D107  mov edx, [eax+0x0C]      ; 3440
0086D10A  sub edx, [eax+0x108C]    ; - CANVAS width 2001
0086D110  sar edx, 1               ; = 719, but LBL_Map.left is 860
```

which assumed the canvas is centred in the window. That held until
`area-map-surface.md`'s Option D set `centringX = screenWidth`, putting the canvas
origin at `LBL_Map.left` instead. **Measured live:** a click at screen
(1445, 913) reached the wrapper as (1651, 766) and left as (932, 392) — an inset
of 719, against the 860 required. Clicks landed **141 px** to the right of the
pointer, exactly `(canvas − overlay) / 2 = (2001 − 1720) / 2`. Eleven bytes were
replaced by eleven (`tools/build_hit_test_center_fix.py`), so the wrapper did not
move and the vtable slot was not touched. **Re-measured after the fix: `edx` =
860.**

Note that `[eax+0x0C]` on *this* object is the **window** width, not the overlay —
a different field from the `[ebx+0x0C]` of §5, which is the overlay on the icon
container. An earlier version of this document's sibling described `+0x0C` as one
thing in both places; they are different objects.

## 7. Two limits, both measured

**The imm8 ceiling.** Sizes are `imm32` and unbounded, but every centring offset
is `add r32, imm8`. The largest is the arrow's `size/2`, so the factor is clamped
at `127 / 16 = 7.9375`, i.e. heights above ~5715 px. Of the 48 shipped
resolutions that is **15360×8640 alone**, which gets markers about two thirds of
the ideal size, still correctly centred. Lifting it means widening those three
`add`s into `imm32` in a stub — the same shape as the stack-count label fix in
gold v10 — which is not worth a section for one resolution nobody has.

**Half-pixel asymmetry.** When a scaled size is odd, `−size/2` is not an integer,
so the rectangle sits half a pixel off centre. Unavoidable with integer
rectangles, and it disappears again at even sizes.

## 8. What is deliberately not changed

* **The textures themselves.** `mm_barrow`, `lbl_mapcircle` and `whitetarget` are
  drawn stretched into the scaled rectangle. The engine draws GUI textures one
  texel per pixel *for GUI controls*, but these go through the map's own draw and
  scale cleanly, so no texture regeneration is needed. Confirmed in play at
  3440×1440.
* **`0x00694A39` / `0x00694AAC`** — the party and arrow coordinate calls. Those
  are redirected to KMRP's `.kui` wrapper for *position*; this document is only
  about size.
* **The note icon's 20×20 aspect.** All four rectangles are square in vanilla and
  stay square.

## 9. Verifying by hand

```powershell
& '.\dist\KMRP - KOTOR Modern Restoration Patch.exe' --apply `
    .\build-inputs\swkotornopatch.exe .\out.exe 1920x1080
```

Then read the fourteen FILE offsets above. The check that catches the mistakes
this subsystem invites is not "did the size change" but:

1. every size equals `round(vanilla × max(1, height/720))`, clamped at 7.9375;
2. **every offset equals `−size/2`** for its own marker;
3. both note paths moved, not just the selected one;
4. both control extents moved, not just `mm_barrow`'s.

Measured in play at 3440×1440: the unselected note marker went from **17×15 px**
on screen to **24×24**, and the selected from 34×34 in a 40 px rect — the ring
art does not reach its rectangle's edges, so on-screen is always smaller than the
rect.

**Untested:** every resolution other than 3440×1440 has been verified by reading
the bytes back, not by looking at the game.

Check the hit-test inset, which is the one number that silently breaks when the
map surface moves:

```
x64dbg: bp 0x0086D112, open the area map, click anywhere on it, read edx
```

At 3440x1440 under gold v20 it must be **860** (`= LBL_Map.left = screenWidth/4`).
719 means the wrapper is still centring on the canvas and clicks are 141 px right
of the pointer. Attaching steals focus, so click once to give it back to the game
before the click you want to measure.
