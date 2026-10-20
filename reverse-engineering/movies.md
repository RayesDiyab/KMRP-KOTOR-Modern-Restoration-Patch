# Full-screen movie resolution and mode transitions

> **Documentation standard.** This document follows
> [`../docs/documentation-standard.md`](../docs/documentation-standard.md).

**Kind: confirmed static reconstruction.** Runtime playback was untested
until 2026-09-25, when the maintainer reported that with K1 Cutscenes Rescaled
at 3440x1440 what used to render wrongly now renders correctly, and that
skipping a movie never minimised the game (issue #6). The rest of the untested
list at the end still stands.

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

*Since 2026-10-20, read from the source and not yet seen in the game:* the fit is
to a 16:9 area in the middle of the screen, not the whole screen (*The 16:9 area*),
and Bink is asked to draw with GDI instead of DirectDraw (*KMRP asks for the DIB
section*), KMRP's answer to issue 48. Later the same day (after commit `4a1cd73`) the
third 640x480, the check after a playlist, gets the game's size too, so a full-screen
movie no longer ends in a rebuild of the renderer and a second display-mode change
(*The third pair*), and the anti-aliasing rebuild the game held back at start-up in
full screen until after the start-up movies is made before them (*The anti-aliasing
rebuild at start-up*).

> **Where these bytes are written (note of 2026-10-08, read from the source).**
> Until 2026-09-29 KMRP's installer wrote the four operands and the `.kmv`
> routine into `swkotor.exe`. It no longer does: the module of `KMRP.kpatch`
> applies the same bytes in memory each time the game starts, under KOTOR Patch
> Manager's runtime (`src/controller-native/K1KpmApplier.cpp`,
> `K1RuntimeEngine.cpp`), from a recipe built from source
> (`src/engine/windows-sites.json`, `tools/build_windows_engine.py`,
> `tools/build_native_engine.py`). The four operands are not the resolution
> "selected in KMRP" any more: no resolution is chosen in the installer since
> 2026-10-04, and the module writes them for the size the game runs at, again
> when the size is changed in the game (`FieldValue`, kinds 1 and 2). `.kmv` is
> in the block of memory the module allocates, not at its gold address.
> "Shipped", `ResolutionPatch` and `Test-MovieResolution.ps1` below describe the
> installer's `--apply` output, a patched executable written to a new file,
> which is still the reference ([`docs/kpm-edition.md`](../docs/kpm-edition.md)).
> The movie fixes are part of KMRP's patch and not an option. *Since 2026-10-20*
> one key that no installer writes, `original-movie-mode=1` under `[Movies]`
> in `configs\kmrp.ini`, leaves the four operands out and keeps the rest
> (*The fallback: `original-movie-mode`*, below). *Later on 2026-10-20* the operands
> are six, the third pair having joined them, and the key leaves out all six and the
> branch at `0x005F92A8` with them (*The third pair*).

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
| since 2026-10-20 | the source-built recipe (`tools/build_windows_engine.py`), not gold: `.kmv` 116 bytes (*The 16:9 area*; 104 in `4a1cd73`), one more site at `0x00405734` (*KMRP asks for the DIB section*), the four operands as feature 8; 84 guarded runs, template 48,202 bytes, SHA-256 `B37B1910076438026944FA1968C4701381B8B6264C31A6EE539AADED96EDB102`, computed in memory from the working tree that day. That was `4a1cd73`'s recipe. Later the same day, with the third pair and the branch at `0x005F92A8` in feature 8 (*The third pair*): 87 guarded runs, 855 bytes, template 48,258 bytes, SHA-256 `CAE9C59577FF5B7ED2FA7D3D7BC5CD6B3D4E4017C8C6E59F0BC5BD6FC63BA336`, read from `build()` in memory |
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

**A feature of their own since 2026-10-20.** In the source-built recipe the four
operands are feature bit 8, the movie display mode (`MOVIE_MODE` in
`tools/build_windows_engine.py`, `kMovieMode` in `src/controller-native/K1KpmApplier.cpp`);
until then they were bit 2 with the rest of the movie changes, which keeps the fit's
jump and, since the same day, Bink's buffer type. They are three guarded runs:
`0x00403D6C` (4 bytes), `0x00403D78` (4) and `0x005F5B3B` (12: both `mov` operands and
the four instruction bytes between them). KMRP's module applies bit 8 unless
`original-movie-mode=1` (*The fallback*, below), so both pairs still change together
or not at all. `WindowsEnginePatch.cs` accepts bit 8 in the template since the same
day, and `--apply` writes every feature. (*Later on 2026-10-20* bit 8 is six runs: these
three, the third pair's two operands and the branch at `0x005F92A8`, *The third pair*
and *The anti-aliasing rebuild at start-up*, below.)

### What each pair guards, and a third copy (2026-10-19)

*Correction and extension, read from the clean executable on 2026-10-19 while looking
into issue 48. The paragraph above is right that the two pairs belong together and wrong
to treat them as the whole policy: there is a third 640x480, which KMRP does not change.*
(Since 2026-10-20, after `4a1cd73`, it does: *The third pair*, below. This subsection
and its table are kept as they were written on 2026-10-19, with the changes marked.)

| sites | function | what 640x480 decides there | with KMRP |
| --- | --- | --- | --- |
| `0x00403D66`-`0x00403D85` (operands `0x00403D6C`, `0x00403D78`) | `ChangeResolutionForMovie`, `0x00403CF0` | before a playlist in full screen: if the mode is not 640x480x32, `ReInitAurora(640, 480, 32, 1, 0, 0)` at `0x00403D9E` | the game's size, so never called |
| `0x005F5B37`-`0x005F5B4C` (operands `0x005F5B3B`, `0x005F5B43`) | `CClientExoAppInternal::ReadAndSetVideoMode`, `0x005F5AB0`, called for the startup movies | the mode the first window is made in. It also sets `[0x007A3C54] = 1`, which makes the first `ChangeResolutionForMovie` skip its check (`0x00403D45`-`0x00403D64`), and stores the size `swkotor.ini` gives in `0x0078D1D4`/`0x0078D1D8` (`0x005F5C18`) | the game's size |
| `0x00403EA7`, `0x00403EB3`, `0x00403EBF` (640, 480, 32) | `RestoreResolutionFromMovie`, `0x00403DE0` | after the playlist in full screen: the mode saved at its start is compared with 640x480. Equal calls only `ActivateRenderWindow` (`0x00401E00`); anything else calls `ReInitAurora(saved mode)` at `0x00403F07` | **unchanged** until 2026-10-20; the game's size since (operands `0x00403EAD`, `0x00403EB9`), so only `ActivateRenderWindow` is called |

So the startup logos depend on the second pair alone, and story movies on the first
alone.

**`ReInitAurora` (`0x00403800`) is a rebuild of the renderer, not a mode request.** It:
- hides and disables the taskbar (`FindWindowA("Shell_TrayWnd")`, `EnableWindow`,
  `ShowWindow(SW_HIDE)`, `0x004038A4`-`0x004038BA`);
- starts a backdrop thread at time-critical priority (`initCinematicBackdrop`,
  `0x00401A30`);
- makes a new OpenGL window (`InitOpenGLWindow`, `0x00403A23`) and destroys the old one
  (`0x00403B3D`), reloading every texture;
- calls `ActivateRenderWindow` and `RestartMoviesIfNecessary` (`0x00403C21`);
- on one path, shows the taskbar again (`0x00403C4D`-`0x00403C59`).

What follows from the table:
- **With KMRP, no rebuild happens before a story movie.** The movie window opens over
  the live OpenGL window. Vanilla rebuilt the renderer at 640x480 first.
- **Every full-screen playlist still ends in a rebuild,** at the size the game is
  already at, because the third copy still says 640x480. Vanilla at any other size
  rebuilt at both ends; at 640x480, at neither. *Changed 2026-10-20, after `4a1cd73`:*
  that was true of KMRP until then, the start-up movies and every story cutscene
  included. Since then, with KMRP's display mode on (feature 8), a playlist ends in
  `ActivateRenderWindow` alone, as vanilla's did at 640x480: no rebuild at either end
  (*The third pair*).
- **In windowed mode none of the three copies matters.** `ChangeResolutionForMovie`
  returns before its check when the renderer is not full screen (`0x00403D2C` →
  `0x00403DC0`, clearing `[0x007A3CBC]`), and `RestoreResolutionFromMovie` tests
  `[0x007A3CBC]` first. The full-screen query is the virtual at `+4` of the object at
  `0x007A39F8`, read from its uses in the main window's `WM_ACTIVATEAPP` and in
  `toggleFullScreen`.

### The third pair: the game's size since 2026-10-20

**Kind: read from the source and disassembled from the clean executable with Capstone;
not seen in the game.** Since 2026-10-20, after commit `4a1cd73`, KMRP writes the size
the game runs at into the third copy too, per resolution, like the other four operands
(`FILE = VA − 0x400000`):

| VA | FILE | size | clean | recipe (3440x1440) | written | feature | purpose |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `0x00403EAD` | `0x003EAD` | 4 | 640, `80020000` | 3440, `700d0000` | `W` | 8 | imm32 of `cmp dword ptr [0x0078D1F0], 640` at `0x00403EA7`: the saved width |
| `0x00403EB9` | `0x003EB9` | 4 | 480, `e0010000` | 1440, `a0050000` | `H` | 8 | imm32 of `cmp dword ptr [0x0078D1F4], 480` at `0x00403EB3`: the saved height |

Not changed: the colour depth, imm8 `0x20` at `0x00403EC5` in the `cmp byte ptr
[0x0078D1F8], 32` at `0x00403EBF`. The values are written where the other movie
operands are: `tools/build_windows_engine.py` (the integer fields, `MOVIE_MODE`),
`resolution_fields` in `tools/build_native_engine.py` (kinds 1 and 2, so a change of
resolution in the game writes them again), `MovieWidthOffsets` and
`MovieHeightOffsets` in `src/patcher/KmrpPatcher.cs` (FILE `0x00003EAD`, `0x00003EB9`,
for `--apply`), and `kMovieModeFields` in `src/controller-native/K1RuntimeEngine.cpp`
(`FieldInForce`, six fields now), which leaves them alone while
`original-movie-mode=1` is set.

From `build-inputs/swkotornopatch.exe` (SHA-256 `761F9466…C49E9886`), trimmed:

```asm
; ChangeResolutionForMovie, 0x00403CF0: the mode is saved before every playlist
00403CF6  mov  ecx, [0x0078D1D8]              ; the game's height
00403CFC  mov  eax, [0x0078D1D4]              ; the game's width
00403D08  mov  dl,  [0x0078D1E0]              ; its colour depth
00403D0E  mov  [0x0078D1F4], ecx              ; saved height
00403D1A  mov  [0x0078D1F0], eax              ; saved width
00403D1F  mov  [0x0078D1F8], dl               ; saved depth
; RestoreResolutionFromMovie, 0x00403DE0: after the playlist
00403E95  cmp  dword ptr [0x007A3CBC], 1      ; did the playlist start in full screen?
00403E9C  jne  0x00403F0F                     ; no: return
00403E9E  ...                                 ; and returns unless [0x007A3CC0] is 0 (not decoded)
00403EA7  cmp  dword ptr [0x0078D1F0], 0x280  ; saved width : 640 (KMRP: W)
00403EB1  jne  0x00403ED1
00403EB3  cmp  dword ptr [0x0078D1F4], 0x1E0  ; saved height : 480 (KMRP: H)
00403EBD  jne  0x00403ED1
00403EBF  cmp  byte ptr  [0x0078D1F8], 0x20   ; saved depth : 32 (unchanged)
00403EC6  jne  0x00403ED1
00403ECC  jmp  0x00401E00                     ; all equal: ActivateRenderWindow, and nothing else
00403ED1  ...                                 ; otherwise:
00403EDE  movzx ecx, byte ptr [eax+0x44]      ;   the anti-aliasing setting
00403EE3  call 0x0044F2F0                     ;   applied again
00403F07  call 0x00403800                     ;   ReInitAurora(saved width, height, depth, [0x007A3CBC], 0)
```

With the game at its own size and 32-bit colour, the mode saved before the playlist
is the mode the game is in, and KMRP never changes it for a movie, so all three
compare equal: the game calls `ActivateRenderWindow` and makes no rebuild. That removes
these, after every full-screen playlist (the start-up movies and every story cutscene):
- a new OpenGL window and the old one destroyed, with every texture reloaded;
- the taskbar hidden, and on one path shown again (*What each pair guards*, above);
- the calls to `ChangeDisplaySettingsA` that `ReInitAurora` makes through the
  renderer object at `[0x007A39F8]` (vtable `0x00741518`): its virtuals at `+0x0C`
  (`CAurInternal::GetValidMode`, `0x0044D6E0`, in
  [`resolution-switch.md`](resolution-switch.md); called at `0x00403A57`), `+0x08`
  (`0x00403A86`) and `+0x20` (`0x00403923`) call it,
  at `0x0044D81C`, `0x0044DBA0`/`0x0044DBCD` and `0x0044EC18`. Which mode each call sets
  was not decoded;
- the anti-aliasing setting applied again at `0x00403EE3`. Without that rebuild the
  game's start-up rebuild has to apply it (next subsection).

Limits of the reading:
- **Another colour depth still rebuilds.** A saved depth other than 32 fails the third
  test. Whether the game can be set to one was not checked.
- **One path replaces the saved mode.** At `0x00403E63`, while `[0x0078D1FC]` is set,
  `0x005F0CE0`, which reads `Width` under `[Graphics Options]` of `swkotor.ini`, writes
  the saved mode again. No instruction in the image names `0x0078D1FC` but that read
  and its clear at `0x00403E6E`, so the path was not followed.
- **Windowed play is unchanged:** the return at `0x00403E9C`.

**Why, and what is not known.** Two reports on 2026-10-20:
- a player (StellarExile, a 240 Hz monitor) saw the monitor's signal break up for
  about half a second on quitting the game with KMRP. They did not see it with Scaled
  Kotor, and stopped seeing it once they had added KOTOR Patch Manager's own Movie Patch;
- the maintainer has seen the screen go black for a moment while playing.

Both fit the extra display-mode change after every playlist. Neither is confirmed in
play, and the change has not been run on either PC. KMRP's own patch lists the Movie
Patch among its conflicts (`OTHERS` in `tools/build_native_kpatch.py`; both hook
`0x00404D06`), so which patches were installed together on that PC was not established.

**Corroboration, not evidence: KOTOR Patch Manager's Movie Patch**
(`better-movie-playback-v1` 1.5.3 by J; its `hooks.toml` is read from
`build/research/kpm-0.7.1/src/Kotor-Patch-Manager-0.7.1/Patches/Movie Patch/`, and the
copy under `third_party/Kotor-Patch-Manager/Patches/Movie Patch/` differs only in line
endings) avoids the same rebuild another way. Its first hook, at
`0x00403D2C`, turns `je 0x00403DC0` (`0F 84 8E 00 00 00`) into `jmp 0x00403DC0`
(`E9 8F 00 00 00 90`), so `ChangeResolutionForMovie` always takes its windowed path,
which clears `[0x007A3CBC]`. `RestoreResolutionFromMovie` then returns at `0x00403E9C`,
with no rebuild and no `ActivateRenderWindow` either; that patch carries a detour of
its own at `0x00404C10` (`postMovieCleanup`), which by its comment gives the game window
its input back. KMRP's change keeps the game's own `ActivateRenderWindow`, the path
vanilla took after a playlist at 640x480.

### The anti-aliasing rebuild at start-up (2026-10-20)

**Kind: one branch, read from the source and disassembled from the clean executable;
not seen in the game.** The start-up routine that reads `swkotor.ini` (it calls
`ReadAndSetVideoMode` at `0x005F905F`) ends its graphics settings with a rebuild that
applies the anti-aliasing setting. The unpatched game skips it in full screen when
start-up movies are to play:

```asm
005F9032  mov  [esp+18], edi        ; 1 when "Disable Movies" ([Game Options]) is 0
005F9253  test edi, edi             ; "Anti Aliasing" found under [Graphics Options]?
005F9255  je   0x005F92E1           ; no: no rebuild
005F9288  call 0x0061D710           ; store the setting at [options+0x44], apply it (0x0044F2F0)
005F9291  call 0x005E5630           ; the setting as a number
005F9298  jle  0x005F92E1           ; 0 or less: no rebuild
005F929A  mov  eax, [esp+18]
005F929E  test eax, eax
005F92A0  je   0x005F92AA           ; no start-up movies: rebuild now
005F92A2  mov  eax, [esp+10]        ; FullScreen ([Graphics Options])
005F92A6  test eax, eax
005F92A8  jne  0x005F92E1           ; full screen: no rebuild here (KMRP: 90 90)
005F92AA  ...
005F92D9  call 0x00403800           ; ReInitAurora(width, height, depth, bit 3 of [options], 1)
```

So the unpatched game left the rebuild with the setting to the one after the start-up
movies, `RestoreResolutionFromMovie`'s, which applies it at `0x00403EE3` (previous
subsection). With the third pair at the game's size that rebuild is gone, and KMRP NOPs
the branch instead, so the setting is applied at start-up, as it already was in
windowed mode or with `Disable Movies` set:

| VA | FILE | size | clean | KMRP | feature | purpose |
| --- | --- | --- | --- | --- | --- | --- |
| `0x005F92A8` | `0x1F92A8` | 2 | `75 37`, `jne 0x005F92E1` | `90 90` | 8 | the anti-aliasing rebuild at start-up in full screen with start-up movies |

- **Only with anti-aliasing on.** With `Anti Aliasing` missing, or at 0 or less, there
  is no rebuild here, patched or not (`0x005F9255`, `0x005F9298`).
- **Before the start-up movies.** That this code runs before them is read from the skip
  itself, which exists only when start-up movies are to play, and from the Movie Patch's
  comment on its own copy of the change; the call chain from here to the start-up movies
  was not traced.
- **Corroboration:** the Movie Patch makes the same change with a 16-byte hook at
  `0x005F929A`, `E9 0B 00 00 00` (a jump to `0x005F92AA` over both tests) and eleven
  `nop`s. KMRP NOPs only the last branch; the two loads it leaves only read the stack.
- **Bit 3 of `[options]`,** the fourth argument, was not decoded; the Movie Patch's
  comment calls the step full-screen anti-aliasing.

Both this branch and the third pair are feature 8, so `original-movie-mode=1` leaves
them out with the other four operands, and the game rebuilds after every full-screen
playlist and applies anti-aliasing there, as unpatched (*The fallback*, below). With
them the recipe has 87 guarded runs, 855 bytes (84 and 845 in `4a1cd73`); feature 8 is
six runs, 30 bytes; the 46 relocation fields and 457 proved instructions are unchanged.

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

*Since 2026-10-20 the stub is 116 bytes and fits a movie smaller than the screen inside
a 16:9 area (*The 16:9 area*, below). The listing and the table in this section are gold v24's
81-byte stub as it shipped until then, kept as the record; the jump into it and the
retail code it returns to are unchanged.*

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

| screen | 640x480 logo | 640x272 movie | 640x360 movie | 1280x720 movie |
| --- | --- | --- | --- | --- |
| 800x600 | 800x600 (width and height fit together) | 800x340 | 800x450 | 800x450 |
| 1920x1080 | 1440x1080 | 1920x816 | 1920x1080 | 1920x1080 |
| 3440x1440 | 1920x1440 | 3388x1440 | 2560x1440 | 2560x1440 |

*The two middle columns were added on 2026-10-19.* Steam's movies, read from their Bink
headers that day:
- `legal`, `biologo` and `leclogo` are 640x480;
- `02`, `09`, `31a`, `50` and `56b` are 640x360;
- every other story movie is 640x272 (2.35:1).

On a 3440x1440 screen (2.39:1) a 640x272 movie fills the height with 26-pixel bars at
the sides, so it looks full screen without being cropped. Retail drew it 3440x1462 and
lost 11 rows top and bottom.

Retail drew the same logo at 3440x2580 on a 3440x1440 screen. Fitting leaves
bars beside a movie narrower than the screen, and those bars were never painted
-- the grey flash below, which is why that fix followed this one.

### The 16:9 area (2026-10-20)

**Kind: read from the source and disassembled from `build_stub`; not seen in the
game.** On 2026-10-20 the maintainer chose to fit every movie inside a 16:9 area in
the middle of the screen. With the fit above, a 2.35:1 story movie filled a 3440x1440
screen (3388x1440) and looked zoomed in. It is now 2560x1088, the size it has on a
16:9 screen of the same height.

The rule, in integers (`idiv` truncates; the sizes are positive):

```
w16    = cw                    if mw >= cw or mh >= ch   (a movie as large as the screen)
       = min(cw, ch * 16 / 9)  otherwise                 cw, ch: the client's width and height
if w16 * mh <= ch * mw:  width = w16,            height = mh * w16 / mw
else:                    width = mw * ch / mh,   height = ch
x = (cw - width) / 2,  y = (ch - height) / 2   (retail's centring, unchanged)
```

On a screen 16:9 or narrower `w16` is the client width and nothing changes. A movie at
least as wide or as tall as the client is fitted to the whole client, as before: the
maintainer's choice the same evening, so that a replacement made for the screen fills
it (a 3440x1440 movie on a 3440x1440 screen). In `4a1cd73` it did not, and was drawn
2560x1071 inside the area; the stub was 104 bytes then. The game's own movies are 640
wide and always get the area. `build_stub` puts the exception and the cap in front of
gold v24's code; disassembled with Capstone from
`build_movie_aspect_fit.build_stub(0x877000)`, the address `tools/build_windows_engine.py`
gives the page (logical VA; the module moves the block, section 2 of
[`docs/kpm-edition.md`](../docs/kpm-edition.md)):

```asm
; entry as before: ESI = CExoMoviePlayerInternal*, EBX = client width,
;                  EBP = client bottom, [esp+24] = client top
00877000  57                    push edi
00877001  8b 4e 48              mov  ecx, [esi+48]     ; BINK*
00877004  39 19                 cmp  [ecx], ebx        ; movie width : cw
00877006  7d 1c                 jge  0x00877024        ; at least as wide: keep cw
00877008  8b c5                 mov  eax, ebp
0087700A  2b 44 24 28           sub  eax, [esp+28]     ; ch = bottom - top
0087700E  39 41 04              cmp  [ecx+4], eax      ; movie height : ch
00877011  7d 11                 jge  0x00877024        ; at least as tall: keep cw
00877013  c1 e0 04              shl  eax, 4            ; ch * 16
00877016  99                    cdq
00877017  b9 09 00 00 00        mov  ecx, 9
0087701C  f7 f9                 idiv ecx               ; w16 = ch * 16 / 9
0087701E  3b d8                 cmp  ebx, eax
00877020  7e 02                 jle  0x00877024        ; the client is no wider than 16:9: keep cw
00877022  8b d8                 mov  ebx, eax          ; else fit to w16 from here on
00877024  8b 46 48              mov  eax, [esi+48]     ; BINK*: gold v24's code from here
...                                                    ; each address 0x23 higher than above
0087705E  89 7c 24 14           mov  [esp+14], edi     ; the height the caller centres with
00877062  8b 46 4c              mov  eax, [esi+4c]
00877065  57 53 50              push edi / push ebx / push eax
00877068  ff 15 84 d4 73 00     call [0x0073D484]      ; BinkBufferSetScale(buffer, width, height)
0087706E  5f                    pop  edi
0087706F  e9 94 e7 b8 ff        jmp  0x00405808
```

116 bytes, 35 more than gold v24's. The one relocated field in it is the last jump's
displacement, now at `0x00877070` (`0x0087704D` in gold v24, `0x00877064` in
`4a1cd73`). **Why the picture stays
in the middle:** what the stub hands back is the drawn width in EBX and the drawn
height at `[esp+10]` (written as `[esp+14]` while EDI is pushed), as gold v24's did.
Retail's centring at `0x00405808`, read from the clean executable, measures from the
client's own edges, not from `w16`:

```asm
00405808  8b c7                 mov  eax, edi          ; client right (EDI, restored by the stub's pop)
0040580A  2b c3                 sub  eax, ebx          ; - drawn width
0040580C  2b 44 24 20           sub  eax, [esp+20]     ; - client left
00405810  8b 5c 24 24           mov  ebx, [esp+24]     ; client top
00405817  d1 f8                 sar  eax, 1            ; x = (cw - width) / 2  (after cdq / sub eax,edx)
0040581F  8b c5                 mov  eax, ebp          ; client bottom
00405821  2b 44 24 10           sub  eax, [esp+10]     ; - drawn height
00405825  2b c3                 sub  eax, ebx          ; - client top
0040582A  d1 f8                 sar  eax, 1            ; y = (ch - height) / 2
00405867  ff 15 80 d4 73 00     call [0x0073D480]      ; BinkBufferSetOffset(buffer, x, y)
```

What it gives, from the rule (offsets in brackets; "was" is gold v24's stub, where it
differs):

| screen | 640x480 logo | 640x272 movie | 640x360 movie | 1280x720 movie |
| --- | --- | --- | --- | --- |
| 800x600 | 800x600 (0,0) | 800x340 (0,130) | 800x450 (0,75) | 800x450 (0,75) |
| 1920x1080 | 1440x1080 (240,0) | 1920x816 (0,132) | 1920x1080 (0,0) | 1920x1080 (0,0) |
| 2560x1080 | 1440x1080 (560,0) | 1920x816 (320,132); was 2541x1080 | 1920x1080 (320,0) | 1920x1080 (320,0) |
| 3440x1440 | 1920x1440 (760,0) | **2560x1088 (440,176); was 3388x1440** | 2560x1440 (440,0) | 2560x1440 (440,0) |
| 3840x2160 | 2880x2160 (480,0) | 3840x1632 (0,264) | 3840x2160 (0,0) | 3840x2160 (0,0) |
| 5120x1440 | 1920x1440 (1600,0) | 2560x1088 (1280,176); was 3388x1440 | 2560x1440 (1280,0) | 2560x1440 (1280,0) |

The 640x480 logos and the 640x360 and 1280x720 movies were already narrower than
16:9 on these screens, so only the 2.35:1 story movies change, and only on screens
wider than 16:9. Consequences of the rule, computed and not seen:
- **A movie made for the screen still fills it.** A movie whose Bink header says
  3440x1440 is drawn 3440x1440 on a 3440x1440 screen, as before. *Correction,
  2026-10-20:* in `4a1cd73` it was drawn 2560x1071 inside the area; the doc review of
  that commit found it, and the maintainer chose the exception the same evening. A
  movie smaller than the screen both ways still gets the area, a 1920x816 upscale
  included (2560x1088 on 3440x1440), and a 2560x1080 movie on a 3440x1440 screen is
  drawn 2560x1080. Whether the K1 Cutscenes Rescaled set this document mentions under
  *Compatibility and limits* is encoded at a screen's size was not read.
- **Truncation can cost a row.** At 3840x1600, `w16` is 2844 (2844.4 truncated) and
  a 640x360 movie is drawn 2844x1599, not 2844x1600.

Not changed: the jump at `0x004057AC`, retail's centring and `BinkBufferSetOffset`,
the call to `BinkBufferSetScale` on every movie, the black bars (now on all four sides
of a 2.35:1 movie on a screen wider than 16:9: they are the movie window's black
brush, *The grey flash*, below), and everything at 16:9 or narrower. Checked by
`testing/regression/Test-WindowsEngineSource.py`, which expects `.kmv` at 116 bytes
and 457 instructions proved after a move (443 until then; 104 and 452 in `4a1cd73`); it checks bytes, not a
movie on screen. To read the stub again:

```powershell
cd tools
python -B -c "import build_movie_aspect_fit as m; from capstone import *; c=m.build_stub(0x877000); print(len(c)); [print(hex(i.address), i.mnemonic, i.op_str) for i in Cs(CS_ARCH_X86, CS_MODE_32).disasm(c, 0x877000)]"
```

## Bink's buffer: DirectDraw or GDI (2026-10-19)

**Kind: static, from the Steam copy's `binkw32Hooked.dll`** (the game's own Bink, which
KPM's `binkw32.dll` proxy forwards to): version 1.5v, 2003.

`InitializeMovie` opens the buffer with
`BinkBufferOpen(movie window, movie width, movie height, 0x5D000000)`
(`0x00405733`-`0x0040573B`). That is buffer type 0, Bink's own choice, with stretch and
shrink flags in the high byte. Bink reads the type from the low five bits
(`and esi, 0x1F` at `0x300104DC` in that DLL) and keeps the one it chose at `+0x80` of
the buffer, which `BinkBufferGetDescription` names:

| `[buffer+0x80]` | type |
| --- | --- |
| 1 | DirectDraw primary surface |
| 2 | DIB Section |
| 3, 4, 5 | DirectDraw YV12, YUY2, UYVY overlay |
| 6, 7, 8 | DirectDraw YV12, YUY2, UYVY off-screen surface |
| 9, 10 | DirectDraw RGB off-screen surface, video and system memory |

- **Every type but 2 draws through DirectDraw;** the DLL loads `DDRAW.DLL` itself.
- **Type 2 draws with GDI** (`CreateDIBSection`, `StretchBlt`).
- **Which type a PC gets has not been measured on any PC.** (Since 2026-10-20 KMRP
  asks for type 2, next subsection; that Bink then opens a DIB section on every PC
  has not been measured either.)
- **Retail skips `BinkBufferSetScale` when the window is exactly as wide as the movie**
  (`je 0x00405834`), which at 640x480 is every 640-wide movie. The `.kmv` stub always
  calls it.

### KMRP asks for the DIB section (2026-10-20)

**Kind: one byte, read from the source and checked against the clean executable; not
seen on any PC.** Since 2026-10-20 KMRP passes type 2 instead of 0, for every player,
with no option to turn it off. It is aimed at the first hypothesis for issue 48 (last
section): DirectDraw output that is not shown over the full-screen OpenGL window. A
DIB section is drawn with GDI into the movie window.

| VA | FILE | size | clean | KMRP | feature | purpose |
| --- | --- | --- | --- | --- | --- | --- |
| `0x00405734` | `0x005734` | 1 | `00` | `02` | 2 (movies) | the low byte of `BinkBufferOpen`'s flags: buffer type 2 |

Clean, and with KMRP (`FILE = VA − 0x400000`; disassembled from
`build-inputs/swkotornopatch.exe`, SHA-256 `761F9466…C49E9886`):

```asm
00405733  68 00 00 00 5d        push 0x5D000000        ; flags: type 0, Bink's own choice
00405738  52                    push edx               ; movie height
00405739  50                    push eax               ; movie width
0040573A  51                    push ecx               ; the movie window
0040573B  ff 15 8c d4 73 00     call [0x0073D48C]      ; BinkBufferOpen
; with KMRP:
00405733  68 02 00 00 5d        push 0x5D000002        ; flags: type 2, DIB section
```

The high byte, `0x5D`, is unchanged. Bink's SDK names type 2 `BINKBUFFERDIBSECTION`;
that header is not in this repository, and the type's meaning here is the table above,
read from `BinkBufferGetDescription`. The site is in `src/engine/windows-sites.json`,
and `tools/build_windows_engine.py` makes it feature 2, with the fit's jump: it stays
in when `original-movie-mode=1` leaves the display mode out. The recipe has 84 guarded
runs since (83 until then). No hook of KMRP's two patches and none of K1 Modern Driver
Compatibility 2.0.0's 28 sites lies on it
([`../docs/third-party-driver-compat.md`](../docs/third-party-driver-compat.md),
section 4, rerun on 2026-10-20).

**Untested:** Windows 7, AMD cards, and so whether it ends issue 48; how fast GDI
stretches a frame to 2560x1440 or 3840x2160 compared with DirectDraw, on any PC;
K1 Modern Driver Compatibility's `BinkCopyToBuffer` hook writing into a DIB section.

The section *The grey flash* below ("none of them is a Bink problem") holds for the
flash and the bars. Whether the black picture of issue 48 is a Bink problem is open: see
the last section.

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

### How the window is made, shown and handled (2026-10-19)

*Extension, read from the clean executable on 2026-10-19.* Movies play on a thread of
their own. `CExoMoviePlayerInternal::PlayMoviesAsync` wakes `MoviePlaybackWorker`
(`0x00405B30`), which for each entry of the list calls `InitializeMovie`, then
`PlayMovieLoop`, then `StopMovie` (and so `ShutDown`). **Every entry gets its own window
and Bink buffer.**

`InitializeMovie`, in order:
1. creates the window as above, owned by the main window (`hWndParent` is
   `[0x007A39D8]`), over the main window's client area (`GetWindowInfo`, `0x004054D8`);
2. `SetCapture` (`0x00405545`). KMRP's open hook follows here;
3. `SetWindowLongA(GWL_STYLE, 0x82000000)`, `WS_POPUP | WS_CLIPCHILDREN`, which drops
   `WS_VISIBLE` from the style (`0x00405561`);
4. `SetWindowPos(HWND_TOPMOST, ..., SWP_NOSIZE | SWP_FRAMECHANGED | SWP_NOCOPYBITS)`
   (`0x0040558A`);
5. `BinkOpen`, `BinkBufferOpen`, the scale and the offset (the sections above);
6. waits while `[0x007A3C9C]` is 1;
7. paints the *main* window black with `PatBlt(BLACKNESS)` over the size at
   `0x0078D1D4`/`0x0078D1D8` (`0x004058B1`);
8. `ShowWindow(SW_SHOWNA)` (`0x004058CB`).

The window procedure handles more than the paragraph above lists:

| message | what it does | where |
| --- | --- | --- |
| `WM_ACTIVATEAPP` (0x1C), deactivated, the movie not shutting down | `PrepareMovieForCancellation(0)`, then `CancelMovie(1, 1)`: the movie stops at once and is kept to be played again | `0x00405255` |
| `WM_KEYDOWN` (0x100), Escape | `CancelMovie(0, 0)`, which honours whether the movie may be skipped | `0x00405221` |
| `WM_SYSKEYDOWN` (0x104), Alt+F4 | posts `WM_CLOSE` to `[0x007A39D4]` | `0x004051DE` |
| `WM_SYSKEYUP` (0x105), Alt+Enter | `PrepareMovieForCancellation(1)`, then `CancelMovie(1, 1)` | `0x00405299` |
| `WM_LBUTTONUP` (0x202), `WM_RBUTTONUP` (0x205) | `CancelMovie(0, 0)`, one or the other by the client option at `+0x54` | `0x004052E8`, `0x00405342` |
| the other button messages, 0x201 to 0x206 | swallowed | |
| 0x407 | `UpdateWindowPosition` (`0x00404F40`): `BinkBufferCheckWinPos` | `0x004053BC` |
| 0x408 | `RefreshWindowLayout` (`0x00404F80`): `BinkBufferSetOffset`, `MoveWindow` over the main window's client area, `PatBlt` black on the main window, `ShowWindow(SW_SHOWNA)` | `0x0040539B` |
| anything else | `DefWindowProcA` | |

While a movie plays, the main window posts 0x408 on `WM_WINDOWPOSCHANGED`
(`0x00402B61`-`0x00402BB7`) and 0x407 from `0x004028F8`. Which message leads to the
second was not decoded.

### Alt-Tab and focus during a movie (static, 2026-10-19)

**Kind: confirmed static reconstruction; not watched in play.** In full screen:

1. **Leaving the game cancels the movie and keeps it.** The movie window's
   `WM_ACTIVATEAPP` cancels it with the "play again" flag at `[player+0x1C]`.
   `MoviePlaybackWorker` keeps that entry and the rest of the list (it clears an entry
   only when the flag is down, `0x00405C06`) and ends the loop.
2. **The worker posts `WM_ACTIVATEAPP(0, 0)` to the main window** (`0x00405CCB`). Alt+Enter
   posts 0x409 instead (`0x00405C97`, `0x00405CB2`). A list that simply ends posts 0x40A
   (`0x00405CEC`), and the main window then calls `RestoreResolutionFromMovie`
   (`0x00403316`).
3. **The main window minimises the game.** Its `WM_ACTIVATEAPP` (`0x00402951`), with no
   movie playing any more, calls `ShowWindow(main, SW_MINIMIZE)` (`0x004029DB`) and the
   renderer's virtual at `+0x18` (not decoded; read as leaving full screen).
4. **On return the interrupted movie plays again from its first frame,** with a new
   window and a new Bink buffer. Its activation calls the renderer's virtual at `+0x1C`
   (not decoded; read as entering full screen again). The replay is started by
   `RestartMoviesIfNecessary`, which the activation handler calls in windowed mode
   (`0x00402AA2`), and which `ReInitAurora` (`0x00403C21`) and
   `CClientExoAppInternal::RestartMoviesIfNecessary` (`0x005F9780`, through
   `ChangeResolutionForMovie`) call too. Which of them runs in full screen was not traced.

So anything that deactivates the movie window, a real Alt-Tab or anything else, stops
the movie and drops the game to the desktop until the player comes back. That is the
"back to the desktop between two movies" of issue 48.

### What KMRP does

Two detours, both in `src/controller-native/kotor1.hooks.toml`. Until
2026-09-28 they shipped only with the controller component, and with it turned
off the bars and the flash were back. Since then they install on every patch:
the window hooks as core hooks, and the per-frame one as `NativeMovieFrameK1`
with controller support or `CoreMovieFrameK1` (bars only) without.

*Since 2026-10-05 (note of 2026-10-08, read from `tools/build_native_kpatch.py`
and `K1NativeJoystick.cpp`):* KMRP is two patches, and the two window hooks
below are in KMRP's own, `KMRP.kpatch`, always installed. Its per-frame hook is
no longer either of the two named above: it is `KmrpCoreMovieWorkK1` at
`0x00404D06` (`8B 56 48 50 8B 46 4C`, ESI the movie player), earlier in the
same loop, which centres and tracks the movie window and gives it its bars
(`TrackMovieFrameK1`). The site `0x00404D96` belongs to the controller patch
(`kmrp-controller`), which works with or without KMRP. **No movie has been
watched with the hook at its new place** (CHANGELOG, `[1.5.0]`, "KMRP and
the controller patch are two patches"): that a movie is centred, has its bars
and can be skipped is unverified there.

| address | function | when |
| --- | --- | --- |
| `0x0040554B` | `NativeMovieWindowOpenK1` | just after `CreateWindowExA` returns and the `SetCapture` that follows it (`0x00405545`), ESI = the player |
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

## Black picture with sound on Windows 7 and AMD (issue 48, open)

**Kind: what is established comes from others' reports and the code; the mechanism is a
hypothesis.** Reported on 2026-10-13 with KMRP 1.5.1 on Windows 7 and a Radeon
6000-series card:
- the startup movies (the logos, and promotional films Steam's copy lacks) are black
  while their sound plays;
- story movies play;
- Alt-Tab brings the picture back;
- between two movies the game sometimes drops to the desktop.

Vanilla plays them all, and so does the game with Flawless Widescreen.

**Established:**
- **The trigger is the removed 640x480 switch.** The same black movies came with the
  Universal Widescreen Patcher, whose "movies edit 1" and "movies edit 2" are the first
  two pairs of the table above: signatures `800200007515813DD8D17800E001`, the check at
  `0x00403D66`, and `80020000C7442410E001`, at `0x005F5B3B`. The fix posted for it is to
  leave both edits out, after which the movies play small. That patcher has no fit, no
  black window and no K1DC, so none of those is the cause.
- **Alt-Tab brings the picture back by replaying the movie** after a minimise and a
  return to full screen (*Alt-Tab and focus*, above). The drop to the desktop is the
  same path, started by something that deactivates the movie window.
- **K1DC cannot take part on Windows 7:** it does not load there
  ([`../docs/third-party-driver-compat.md`](../docs/third-party-driver-compat.md),
  section 3). Elsewhere, its one movie hook, the `BinkCopyToBuffer` import, corrects
  RGB frames only and touches no window. (On 2026-10-20 Synchro told the maintainer
  they will publish K1DC with Windows 7 support themselves; until then KMRP's
  installer leaves it out there, as before.)

**Hypotheses, most likely first:**
1. **Bink chose a DirectDraw type, and its output is not shown** while the driver
   presents the full-screen OpenGL window directly. The screen keeps the OpenGL window's
   last frame, which `InitializeMovie` has just painted black. A real mode change, the
   vanilla rebuild at 640x480 or the minimise of Alt-Tab, resets that state.
2. **Bink's hardware stretch fails on that driver.** Vanilla never calls
   `BinkBufferSetScale` at 640x480. Against: story movies are stretched too and play,
   and the replay after Alt-Tab uses the same scale.
3. **KMRP's black fill covers a DirectDraw overlay's colour key.** At most a second
   cause, since the Universal Widescreen Patcher has no fill.

**Unexplained:** why only the startup movies. The path for every story movie is the
same, and players of the Universal Widescreen Patcher had black story movies instead,
so the difference is more likely the driver's state than another branch of the game.

*Added 2026-10-20, after `4a1cd73`; reasoning from the code, not tested.* One difference
between the two kinds of movie with KMRP as the reporter had it (1.5.1, the same in
`4a1cd73`): in full screen the startup movies were the only ones before any rebuild of
the renderer. The game skipped its anti-aliasing rebuild at start-up (*The
anti-aliasing rebuild at start-up*), and the first rebuild came at the end of the
startup playlist (*The third pair*); every story movie came after it. That fits the
first hypothesis, in which a real mode change resets the state. With the changes of
that evening:
- **with `Anti Aliasing` above 0 in `swkotor.ini`,** the rebuild is made at start-up,
  so the startup movies, too, come after one;
- **with it at 0 or missing,** a full-screen session now has no rebuild at all, so the
  story movies, which came after one until then, do not either. If the first
  hypothesis holds, they could be black as well on such a PC; the DIB section
  (*KMRP asks for the DIB section*) is meant to make that state not matter.

Which `Anti Aliasing` value the reporter's `swkotor.ini` has is not known, and neither
case has been run there.

**To tell them apart:**
- **windowed mode** (`FullScreen=0`), which switched no mode even in vanilla;
- **does a movie replay from its start after Alt-Tab?**
- **the Bink type,** logged from `[buffer+0x80]` on a movie's first frame;
- **test builds with one change each:** the first or the second pair back at 640x480,
  or Bink's DIB section forced, the byte at `0x00405734` from `00` to `02` (flags
  `0x5D000002`).

**Built on 2026-10-20, not run on Windows 7 or with an AMD card.** Both changes are in
KMRP's patch from that day; neither has been run on the reporter's kind of PC, and
issue 48 stays open until one has.
- **The DIB section, for everyone, by default** (*KMRP asks for the DIB section*,
  above): aimed at the first hypothesis. Not a test build with one change: it ships
  to every player, with the four operands and the 16:9 area as before.
- **The fallback, `original-movie-mode`**, next subsection: the switch to 640x480
  back, for a PC where the movies are still black.
- *Later the same day,* **no rebuild after a playlist, and the anti-aliasing rebuild at
  start-up** (*The third pair*, *The anti-aliasing rebuild at start-up*): made for the
  reports of a blank screen, not for issue 48, but they change which movies follow a
  rebuild (the note above).

### The fallback: `original-movie-mode`

**Kind: read from the source; not run.** A player who still sees black movies can add
two lines to `configs\kmrp.ini` in the game folder, a section of their own:

```ini
[Movies]
original-movie-mode=1
```

`OptionalFeatures` in `src/controller-native/K1RuntimeEngine.cpp` reads it once, when
the game starts (`OriginalMovieMode`); a missing key, or 0, is off. (For an hour on
2026-10-20 it was a key under `[Patch Options]`, which every install rewrites; see
below.)
With it on, the module leaves out feature 8, the four operands (*The four operands*,
above), and they keep the clean executable's 640 and 480. The game then switches the
screen as it did unpatched:
- the first window is made at 640x480, the mode the startup movies play in (the
  second pair, `ReadAndSetVideoMode`); those are the movies that were black on the
  reporter's PC;
- before a story movie in full screen the screen goes to 640x480 (the first pair,
  `ChangeResolutionForMovie`).
- *Since later on 2026-10-20,* when feature 8 is six operands and the branch at
  `0x005F92A8`: after every full-screen playlist the renderer is rebuilt at the
  game's size (the third pair), and the anti-aliasing rebuild at start-up is left to
  that rebuild, both as unpatched.

What stays KMRP's: the fit and its 16:9 area (which changes nothing at 640x480, where
`w16` is 853), the movie window's black brush and bars, and the DIB section. With
`debug-logs=1` the `applied:` line of `KMRP\logs\kmrp-kpm.log` names
"KMRP + Movies at 640x480" where it otherwise says "KMRP + Movies".

It is not an option of the patch: neither the installer's Advanced Settings nor a
KOTOR Patch Manager option list offers it, and nothing writes it but the player. It is
in a section of its own because the installer rewrites `[Patch Options]` with its own
keys on every install (`WritePatchOptions`, `src/patcher/KpmEdition.cs`) and Restore
Original takes that section out (`RemovePatchOptions`); both leave every other section
of the file as it is. *Correction, 2026-10-20:* the first version of that day read the
key from `[Patch Options]`, where any install removed it; found by reading the
installer's code, before any build left the machine. Whether a KOTOR Patch Manager with
patch options keeps another section was not checked.

**A change of resolution in the game.** `KmrpRuntimeEngineDimensions`
(`K1RuntimeEngine.cpp`) writes a new size only after checking that every size field
still holds the value it computed at start. The four operands are size fields
(`resolution_fields` in `tools/build_native_engine.py`), and with the key on they are
never written. *Correction, 2026-10-20:* the first version checked them anyway, so at
any start size but 640x480 every change of resolution in the game would have been
refused ("native size transaction refused: field 00403D6C changed"), found by reading
the source. Since then the check and the write leave those four out while feature 8
is (`FieldInForce`), and `Test-WindowsEngineSource.py` holds its list of four against
the recipe's feature-8 bytes. Not run. (*Later on 2026-10-20* the list is six, with
the third pair, `0x00403EAD` and `0x00403EB9`; the test allows the branch at
`0x005F92A8` as the one feature-8 change outside it.)

## Compatibility and limits

The *K1 Cutscenes Rescaled* changelog says version 1.5.1 corrected a 60-fps
3440x1440 encoding that could crash. Users of that resolution should use 1.5.1
or later and install the movie files for the same resolution selected in KMRP.
KMRP neither distributes nor modifies those BIK files.

Automated coverage in `testing/regression/Test-MovieResolution.ps1` generates
800x600, 1920x1080, 3440x1440, and 3840x2160 executables, then reads all four
movie operands and the four ordinary render-resolution operands back from each.
(*Since 2026-10-20* it still reads only those four, not the third pair; the third
pair's values are checked by `Test-WindowsEngineSource.py` at its 69 resolutions.)
The gold builder independently verifies every original value, output length,
final SHA-256, and written-file SHA-256. (*Since 2026-10-20*
`tools/build_movie_aspect_fit.py` no longer compares its output with gold v24's
SHA-256: its stub is the 104-byte one, so its output is not gold v24 any more. The
build takes only `build_stub` from it; its header says so. *Corrected later the same
day:* the stub is 116 bytes since the exception for a movie as large as the screen,
*The 16:9 area*; this sentence still said 104.)

**Untested:** actual vanilla BIK playback, and rescaled playback other than
the 3440x1440 report above; 16:9 and 4K transitions; Alt-Tab (a skip never minimised the game, 2026-09-25); the first title crawl; 30-fps versus
60-fps movie sets; and Windows 10. No native game or x32dbg surface was exposed
to this Codex session, so static verification is not presented as a play-test.

*Since 2026-10-19:*
- **What Alt-Tab does during a movie** is read from the code (*Alt-Tab and focus*),
  still not watched.
- **Untested as well:**
  - which Bink buffer type any PC gets;
  - windowed play;
  - several playlists one after another;
  - Windows 7 and AMD cards (issue 48);
  - K1DC 2.0 beside a movie.
- **The regression tests check bytes only.** `Test-MovieResolution.ps1` checks the
  installer's `--apply` output and `Test-WindowsEngineSource.py` the recipe; neither
  plays a movie.

*Since 2026-10-20*, none of the three changes of that day has been seen in the game
or run on Windows 7:
- the 16:9 area, on any screen (*The 16:9 area*);
- the DIB section, on any PC, its speed included (*KMRP asks for the DIB section*);
- `original-movie-mode=1` (*The fallback*), and a change of resolution in the game
  with it on.

*Since later on 2026-10-20*, the third pair and the start-up anti-aliasing rebuild have
not been seen in the game or run on any PC either:
- whether the half-second loss of signal on quitting and the black moments go
  (*The third pair*);
- whether anti-aliasing is in effect after the startup movies, and a session with
  `Anti Aliasing` at 0 (*The anti-aliasing rebuild at start-up*);
- Alt-Tab during a movie, and a playlist interrupted by it, with no rebuild after it;
- a change of resolution in the game since the third pair is a size field.

`Test-WindowsEngineSource.py` covers the bytes: `.kmv` at 116 bytes, 457 instructions
proved after a move (443 until then), the new site under feature 2 and the four
operands under feature 8. Since later that day it also checks the third pair's two
values at each of its 69 resolutions and allows the branch at `0x005F92A8` under
feature 8. The K1 Modern Driver Compatibility 2.0.0 check
([`../docs/third-party-driver-compat.md`](../docs/third-party-driver-compat.md),
section 8), run again on the working tree that evening, finds none of its 28 sites on
the three new runs. To read the three sites in the clean executable again:

```powershell
python -B -c "from capstone import *; d=open('build-inputs/swkotornopatch.exe','rb').read(); md=Cs(CS_ARCH_X86, CS_MODE_32); [print(hex(i.address), i.bytes.hex(), i.mnemonic, i.op_str) for a,b in ((0x403EA7,0x403ED1),(0x5F929A,0x5F92AA)) for i in md.disasm(d[a-0x400000:b-0x400000], a)]"
```
