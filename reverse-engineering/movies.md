# Full-screen movie resolution and mode transitions

> **Documentation standard.** This document follows
> [`../docs/documentation-standard.md`](../docs/documentation-standard.md).

**Kind: confirmed static reconstruction; runtime movie playback remains untested.**

## Result

KOTOR does not draw Bink movies at one hardcoded output size, but neither does it
scale them proportionally. **The retail playback path derives its scale from the
client WIDTH alone.** Two separate things are wrong, and they were conflated in
the first version of this document:

1. a hardcoded `640x480` display mode the engine selects around full-screen movie
   playback, which can make Windows minimize the game or fail the transition; and
2. width-only scaling, which crops every movie whose aspect is narrower than the
   screen's.

KMRP fixes both: gold v23 writes the selected resolution into the mode pair, and
gold v24 replaces the scaling with a true aspect fit (§ Aspect fit).

### Correction, 2026-09-06

An earlier revision of this section claimed the path "computes an aspect-preserving
scale and centred offset", and concluded that "a resolution-matched upscaled BIK
can already be scaled and centred correctly". **Both statements were wrong**, and
the error mattered: it is why the aspect fix sat unwired in `tools/` while players
saw cropped intros. The disassembly settles it -- height is never read:

```asm
004057AC  mov  ecx, [esi+0x48]      ; BINK*
004057AF  mov  eax, [ecx]           ; movie width
004057B1  cmp  ebx, eax             ; client width vs movie width
004057BB  fild dword ptr [esp+0x14] ; (float) movie width
004057C7  fild dword ptr [esp+0x10] ; (float) client width
004057CB  fdiv st(1)                ; scale = client_width / movie_width
```

At 3440x1440 a 640x480 logo therefore scales by 5.375 to **3440x2580**, and 1140
rows fall off the screen. That is the reported "zoomed in" intro, measured rather
than inferred.

## Verified build

| Item | Value |
| --- | --- |
| clean executable | 4,042,752 bytes, SHA-256 `761F9466F456A83909036BAEBB5C43167D722387BE66E54617BA20A8C49E9886` |
| reference before this change | `swkotor_gold_v22_laa.exe`, SHA-256 `7863BCE3BDDAC279B6A14FEB2412D38572CF94D22D6E0D8EC869D491B7EFCDE8` |
| reference after this change | `swkotor_gold_v23_movies.exe`, SHA-256 `29BE3C23F53D53F521D98329F996248864834FB3873819DF63CCF1803C65A7E8` |
| aspect fit | `swkotor_gold_v24_movieaspect.exe`, 4,087,808 bytes, SHA-256 `9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A` -- the current gold |
| shipped | the installer of 2026-09-24 (`ECA3DE4B…`), `--apply` at all 48 resolutions: the four operands below carry each resolution, and the `.kmv` stub is byte-identical to gold's in every output |
| address convention | image base `0x00400000`; `VA = FILE + 0x00400000` for these original-image sites |
| method | aligned `llvm-objdump` disassembly, raw-byte search, import inspection, builder read-back, four-resolution output regression |

## The four operands

All four fields are little-endian `imm32` operands. Gold v23 carries KMRP's
3440x1440 reference; `ResolutionPatch` verifies those exact values and replaces
them with the selected width and height.

| Purpose | VA | FILE | clean | gold v23 |
| --- | ---: | ---: | ---: | ---: |
| entry comparison width | `0x00403D6C` | `0x003D6C` | 640 | 3440 |
| entry comparison height | `0x00403D78` | `0x003D78` | 480 | 1440 |
| temporary-mode width | `0x005F5B3B` | `0x1F5B3B` | 640 | 3440 |
| temporary-mode height | `0x005F5B43` | `0x1F5B43` | 480 | 1440 |

The first branch compares the active display globals at `0x0078D1D4` and
`0x0078D1D8`, plus 32-bit colour at `0x0078D1E0`. If they already equal the
movie mode, it skips the call that requests another mode. In clean form:

```asm
00403D66  cmp dword ptr [0078D1D4], 640
00403D70  jne 00403D87
00403D72  cmp dword ptr [0078D1D8], 480
00403D7C  jne 00403D87
00403D7E  cmp byte ptr  [0078D1E0], 32
00403D85  je  00403DA6
...
00403D94  push 480
00403D99  push 640
00403D9E  call 00403800
```

The second pair initializes a width/height structure used by the other movie
mode path:

```asm
005F5B37  mov dword ptr [esp+14], 640
005F5B3F  mov dword ptr [esp+10], 480
005F5B47  mov byte ptr  [esp+18], 32
...
005F5B6A  call 0070D220
```

Changing only the comparison pair leaves the second path requesting 640x480.
Changing only the initialization pair leaves the entry branch comparing against
640x480. Both copies are therefore one atomic resolution policy.

## Rendering reads the live window

The full-screen playback routine at `0x004053E0` obtains the live client bounds
before opening the Bink buffer. It opens the movie at `0x00405671`, opens the
buffer at `0x0040573B`, then computes a scale, calls `BinkBufferSetScale` through
IAT VA `0x0073D484` at `0x00405802`, and centres the result with
`BinkBufferSetOffset` at `0x00405867`.

**In retail the scale comes from the width alone** -- the disassembly under
*Correction, 2026-09-06* above. KMRP does not rewrite a BIK's dimensions; it
changes the display mode around playback (the four operands) and, since gold
v24, the scale itself (*Aspect fit*, below). A 3440x1440 game still needs a
matching movie set if the user expects native 3440x1440 frames.

*Corrected 2026-09-24:* this section still said the routine "derives an
aspect-fit scale from the Bink handle's width and height" and concluded that KMRP
"changes only the display mode" -- the very claims the 2026-09-06 correction
retracted, left behind when the rest of the document was fixed.

## Aspect fit (gold v24)

`tools/build_movie_aspect_fit.py` replaces the seven bytes at `0x004057AC`, where
the width-only computation starts, with a jump into `.kmv`, the eleventh appended
section (`VA 0x00877000`, `FILE 0x3E5000`, `FILE = VA − 0x492000`, 81 bytes used).
Disassembled from the installer's 1920x1080 output; the bytes are identical in
gold and every other output:

```asm
004057AC  e9 4f 18 47 00        jmp  0x00877000       ; was: mov ecx,[esi+48] / mov eax,[ecx] / cmp ebx,eax
004057B1  90 90                 nop ; nop

; entry: ESI = CExoMoviePlayerInternal*, EBX = client width,
;        EBP = client bottom, [esp+24] = client top
00877000  57                    push edi
00877001  8b 46 48              mov  eax, [esi+48]     ; BINK*
00877004  8b 08                 mov  ecx, [eax]        ; movie width  mw
00877006  8b 50 04              mov  edx, [eax+4]      ; movie height mh
00877009  8b fb                 mov  edi, ebx
0087700B  0f af fa              imul edi, edx          ; cw * mh
0087700E  8b c5                 mov  eax, ebp
00877010  2b 44 24 28           sub  eax, [esp+28]     ; ch = bottom - top
00877014  0f af c1              imul eax, ecx          ; ch * mw
00877017  3b f8                 cmp  edi, eax
00877019  7e 16                 jle  0x00877031        ; screen no wider than the movie: fit the width
0087701B  8b c5                 mov  eax, ebp          ; else fit the height:
0087701D  2b 44 24 28           sub  eax, [esp+28]
00877021  8b f8                 mov  edi, eax          ;   height = ch
00877023  0f af c1              imul eax, ecx
00877026  99                    cdq
00877027  8b 4e 48              mov  ecx, [esi+48]
0087702A  f7 79 04              idiv dword [ecx+4]
0087702D  8b d8                 mov  ebx, eax          ;   width = ch * mw / mh
0087702F  eb 0a                 jmp  0x0087703B
00877031  8b c2                 mov  eax, edx          ; fit the width: width = cw (EBX)
00877033  0f af c3              imul eax, ebx
00877036  99                    cdq
00877037  f7 f9                 idiv ecx
00877039  8b f8                 mov  edi, eax          ;   height = mh * cw / mw
0087703B  89 7c 24 14           mov  [esp+14], edi     ; the height the caller centres with
0087703F  8b 46 4c              mov  eax, [esi+4c]     ; the Bink buffer
00877042  57 53 50              push edi / push ebx / push eax
00877045  ff 15 84 d4 73 00     call [0x0073D484]      ; BinkBufferSetScale(buffer, width, height)
0087704B  5f                    pop  edi
0087704C  e9 b7 e7 b8 ff        jmp  0x00405808        ; resume after retail's own SetScale call
```

So `scale = min(cw / mw, ch / mh)`, in integers, and the retail code from
`0x00405808` centres the result as before. What it produces for a 640x480 logo and
a 1280x720 movie, from the formula:

| screen | 640x480 logo | 1280x720 movie |
| --- | --- | --- |
| 800x600 | 800x600 (width and height fit together) | 800x450 |
| 1920x1080 | 1440x1080 | 1920x1080 |
| 3440x1440 | 1920x1440 | 2560x1440 |

Retail drew the same logo at 3440x2580 on a 3440x1440 screen. Fitting leaves
bars beside a movie narrower than the screen, and those bars were never painted
-- the grey flash below, which is why that fix followed this one.

## Rejected community-patcher signature

The open-source helper in
[`nacefguessaymi/kotor_1_cutscene_resolution_fix`](https://github.com/nacefguessaymi/kotor_1_cutscene_resolution_fix)
correctly identifies the first pair, but searches for only
`00 00 C7 44 24 10` for the second. That short sequence occurs 250 times in the
verified executable. Its first match is at FILE `0xBF6E`; extending the helper's
two-byte-before/two-byte-after replacement would modify the high half of
`mov eax,[esi+0x80]` and the high half of the float `-1.0`, not a width and
height. That candidate was rejected.

The intended full sequence from the 2016 guide is
`80 02 00 00 C7 44 24 10 E0 01`; it occurs at FILE `0x1F5B3B`, aligned exactly
with the two `mov imm32` instructions above. KMRP uses fixed, verified addresses
and checks the full 32-bit values instead of accepting a short pattern.

## The grey flash is the window class

**Kind: confirmed static reconstruction, from the Ghidra archive; playtest pending.**

Players see a grey flash immediately before a movie starts and again immediately
after it ends, and grey bars beside a movie narrower than the screen. All three
are the same defect, and none of them is a Bink problem.

`CExoMoviePlayerInternal::InitializeMovie` at `0x004053E0` registers its own
window class and fills in the `WNDCLASSA` by hand:

```asm
00405429  mov dword ptr [esp+38], 00405190   ; lpfnWndProc
00405439  mov dword ptr [esp+44], eax        ; hInstance
0040545C  mov dword ptr [esp+4c], ebx        ; hbrBackground -- EBX is 0 here
00405464  mov dword ptr [esp+54], 0073d7fc   ; "SWMovieWindow"
0040546C  call dword ptr [0073d41c]          ; RegisterClassA
```

`hbrBackground` is **NULL**. The window procedure at `0x00405190` dispatches
`WM_ACTIVATEAPP`, `WM_KEYDOWN`, `WM_SYSKEYDOWN` and the mouse messages and hands
everything else to `DefWindowProc`, so `WM_ERASEBKGND` is never handled there
either -- and `DefWindowProc` with a NULL class brush erases nothing at all.

The window is then created full-screen and already visible:

```asm
00405521  push 90000000                      ; WS_POPUP | WS_VISIBLE
00405526  push 0073d7e4                      ; "SW Movie Player Window"
0040552B  push 0073d7fc                      ; "SWMovieWindow"
00405536  call dword ptr [0073d410]          ; CreateWindowExA
0040553C  mov dword ptr [esi+50], eax
```

So from the moment that window appears until Bink's first blit, and again from
the last blit until the `DestroyWindow` in `CExoMoviePlayerInternal::ShutDown`
at `0x00404C01`, the screen shows whatever was already in that memory. Nothing
ever paints it. The bars beside a narrow movie are the same uncovered window,
just for the whole length of playback.

The main game window does not have the problem. `InitOpenGLWindow` asks for
`GetStockObject(4)` -- `BLACK_BRUSH` -- at `0x00403779` and stores it in its own
class. `SWMovieWindow` is the one class that was left without one.

### What KMRP does

Two detours, both in `src/controller-native/kotor1.hooks.toml`, so they ship
with the controller component (on by default since 2026-09-24). With that
component turned off, the bars and the flash are back:

| address | function | when |
| --- | --- | --- |
| `0x0040554B` | `NativeMovieWindowOpenK1` | just after `CreateWindowExA` returns, ESI = the player |
| `0x00404BB0` | `NativeMovieWindowCloseK1` | `ShutDown`'s entry, ECX = the player |

Both call `BlackenMovieWindowK1`, which sets the class brush to `BLACK_BRUSH`
with `SetClassLongPtr` and fills the current window black. Setting the class is
the actual fix -- the class is registered once, on the first movie of the
session, and every movie window afterwards inherits the brush -- and the
`FillRect` covers the window that already exists at the moment the class is
changed, since a class brush only affects the next erase.

### Two earlier attempts, and why they were wrong

Both are recorded because both looked reasonable and neither was.

1. **Clearing the Bink buffer.** A no-op. `BinkBufferOpen` is given the *movie's*
   size, so the buffer holds only pixels `BinkCopyToBuffer` rewrites every frame.
   The bars are screen outside the blit, which the buffer cannot address.
2. **Padding the buffer to the window's aspect and centring the picture in it**
   (gold v25). This broke playback: the engine blits dirty rectangles from
   `BinkGetRects`, and those rectangles are in the movie's own coordinate space.
   Offsetting the picture inside the buffer desynced the blit from them, and the
   startup logos rendered with only their left portion on screen. Reverted to
   gold v24; `tools/build_movie_letterbox.py` is retained, marked abandoned, with
   the reasoning in its header.

The lesson worth keeping is that the measurement said "unpainted window" from the
first probe, and two attempts were spent looking for it inside Bink anyway.

## Compatibility and limits

The *K1 Cutscenes Rescaled* changelog says version 1.5.1 corrected a 60-fps
3440x1440 encoding that could crash. Users of that resolution should use 1.5.1
or later and install the movie files for the same resolution selected in KMRP.
KMRP neither distributes nor modifies those BIK files.

Automated coverage in `testing/regression/Test-MovieResolution.ps1` generates
800x600, 1920x1080, 3440x1440, and 3840x2160 executables, then reads all four
movie operands and the four ordinary render-resolution operands back from each.
The gold builder independently verifies every original value, output length,
final SHA-256, and written-file SHA-256.

**Untested:** actual vanilla and rescaled BIK playback; 16:9, 21:9, and 4K
transitions; Alt-Tab/minimize behavior; the first title crawl; 30-fps versus
60-fps movie sets; and Windows 10. No native game or x32dbg surface was exposed
to this Codex session, so static verification is not presented as a play-test.
