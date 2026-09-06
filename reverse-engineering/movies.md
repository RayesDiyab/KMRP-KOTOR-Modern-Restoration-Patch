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

## Rendering is dynamic

The full-screen playback routine at `0x004053E0` obtains the live client bounds
before opening the Bink buffer. It opens the movie at `0x00405671`, opens the
buffer at `0x0040573B`, then derives an aspect-fit scale from the Bink handle's
width and height and the client rectangle. It calls `BinkBufferSetScale` through
IAT VA `0x0073D484` at `0x00405802`, then centres the result with
`BinkBufferSetOffset` at `0x00405867`.

Consequently KMRP does not rewrite a BIK's dimensions and does not stretch a
movie to an arbitrary aspect ratio. A 3440x1440 game still needs a compatible
movie set if the user expects native 3440x1440 frames. KMRP changes only the
display mode surrounding playback.

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
