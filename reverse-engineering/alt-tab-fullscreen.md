# Alt-Tab in full screen: the rebuild on return, and KMRP's light return

> **Documentation standard.** This document follows
> [`documentation-standard.md`](../docs/documentation-standard.md). Read it before
> editing this file, and check the result still meets it: measured claims only,
> every site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: reference.** What the game does when it loses and regains the foreground in
full screen, and what KMRP changes about the return (issue
[#96](https://github.com/RayesDiyab/KMRP-KOTOR-Modern-Restoration-Patch/issues/96),
2026-11-10). Related: [resolution-switch.md](resolution-switch.md) for `ReInitAurora`
on a change of resolution, and [movies.md](movies.md), *Alt-Tab and focus during a
movie*.

**How this was read.** Disassembled with Capstone from `build-inputs/swkotornopatch.exe`
(CD 1.03, SHA-256 `761F9466…C49E9886`, 4,042,752 bytes) on 2026-11-10. GOG's v1.03 has the
same code, and Steam's decrypts to the same bytes in memory (measured 2026-09-28,
`tools/kpm_originals.py`); Steam's file on disk is encrypted (`.bind` section) and was not
read. Addresses are VAs; `FILE = VA − 0x400000` for every site here. **Nothing in this
document was traced in a running game.** The freeze in issue 96 is a report from two
players of KMRP 1.5.1 under a YouTube video; it has not been reproduced, and it is not
established that the rebuild is where it happens.

## 1. What the engine does

The main window procedure is at `0x00402800`. Its `WM_ACTIVATEAPP` handler starts at
`0x00402951`; `[esp+0x34]` is the procedure's `hwnd` there (`[esp+0x38]` after the
`push edi` at `0x00402A2A`), `ebp` its `wParam`. `[0x007A39D8]` is the main window,
`[0x007A39F8]` the renderer object (vtable `0x00741518`), `[0x007A3C4C]` the tick count
when the game last left the foreground.

**Leaving** (`wParam == 0`), in full screen, no movie:

```asm
004029D2  mov  ecx, [0x7A39D8]
004029D8  push 6                       ; SW_MINIMIZE
004029DB  call [0x73D400]              ; ShowWindow(main, SW_MINIMIZE)
004029E9  call [edx+0x18]              ; renderer +0x18, 0x0044D8D0
004029F8  call 0x00401D90              ; the render loop stopped (main window only)
004029FD  call [0x73D0F8]              ; GetTickCount -> [0x7A3C4C]
```

**Coming back** (`wParam != 0`), in full screen (`renderer +4` true at `0x00402A3F`), no
rebuild already pending (`[0x7A3A2C] == 0` at `0x00402A46`):

```asm
00402A4F  mov  eax, [esp+0x38]         ; hwnd
00402A53  cmp  eax, [0x7A39D8]         ; the main window?
00402A59  jne  0x00402A66              ; no: only the flag below
00402A63  call [edx+0x1C]              ; renderer +0x1C, 0x0044D900
00402A66  mov  dword ptr [0x7A3A2C], 2 ; a full-screen rebuild for the main loop
00402A70  jmp  0x00402AA7
...
00402AB3  call edi                     ; GetTickCount
00402AB5  sub  eax, [0x7A3C4C]
00402ABB  cmp  eax, 0x3E8              ; away under a second?
00402AC0  jb   0x00402AD1              ;   yes: resume drawing
00402ACA  call [eax+4]                 ; renderer +4: full screen?
00402ACF  jne  0x00402AD6              ;   yes: leave it to the rebuild
00402AD1  call 0x00401E00              ; ActivateRenderWindow
```

In a window (`renderer +4` false) the handler takes `0x00402A72` instead: if
`[0x7A3A18]` is 0, no movie is playing (`0x005EDB40` returns 0) and more than 100 ms have
passed, it calls `RestartMoviesIfNecessary` (`0x005ED980`, `0x00402AA2`), then reaches the
same tick test, and `ActivateRenderWindow`. No rebuild.

**The two renderer virtuals** (`0x0044D8D0`, `0x0044D900`):

| virtual | what it does | evidence |
| --- | --- | --- |
| `+0x18` | `+0x24(1.0f, 1)`: a gamma ramp of 1.0; then, if `[this+0xA8]`, `ChangeDisplaySettingsA(NULL, 0)`: the desktop's mode | `0x0044D8D7` pushes `0x3F800000`; `0x0044D8EE` calls the import at `0x0073D3E8` |
| `+0x1C` | `+0x24([this+0xB0], 1)`: the game's own gamma; then, if `[this+0xA8]`, `ChangeDisplaySettingsA(this+4, CDS_TEST)` and on success `(this+4, CDS_FULLSCREEN)`: the mode the renderer was made in | `0x0044D903` reads `+0xB0`; `0x0044D924` pushes 2, `0x0044D930` pushes 4 |
| `+0x24` (`0x0044D990`) | builds a 256-step ramp from the value given (`cmp esi, 0x100` at `0x0044D9F1`), stores the value at `+0xB0` when its second argument is 0 | read; the call that sets the ramp not followed |

**The rebuild.** The main loop reads the flag at `0x0040460E` and, when it is not 0,
calls `ReInitAurora` (`0x00403800`, `0x00404663`) with the game's size
(`[0x0078D1D4]`, `[0x0078D1D8]`, depth `[0x0078D1E0]`) and full screen `= (flag == 2)`.
`ReInitAurora` destroys the window and makes a new one with a new OpenGL context and
input, and every texture is loaded again ([resolution-switch.md](resolution-switch.md),
step 5); it clears the flag (`0x00403B58`) and restarts interrupted movies
(`0x00403C21`, [movies.md](movies.md)). Where `[[[[0x007A39FC]+4]+4]+0x4BC]` is not 0
(`0x00404623`) it rebuilds at 640x480 instead (`0x00404638`); that field was not decoded.

So the return in full screen always rebuilds, however short the absence: under a second,
drawing resumes first and the rebuild follows; otherwise drawing waits for the rebuild.
`+0x1C` has already put back the gamma and the mode, so the rebuild is not what restores
them.

## 2. What KMRP changes

Two hooks in `src/controller-native/kotor1-native-runtime.hooks.toml`, in KMRP's patch
on all three builds, always installed:

| VA | FILE | size | vanilla | KMRP | purpose |
| --- | --- | --- | --- | --- | --- |
| `0x00402A66` | `0x002A66` | 10 | `C7 05 2C 3A 7A 00 02 00 00 00` (`mov [0x7A3A2C], 2`) | detour to `KmrpFullscreenReturnK1`, original bytes not replayed, `consumed_exit_address = 0x00402A72`, parameter `esp+56` (the `hwnd` slot) | decide whether the rebuild happens |
| `0x00402ACF` | `0x002ACF` | 2 | `75 05` (`jne 0x00402AD6`) | `90 90` | resume drawing in full screen too, as in a window |

`KmrpFullscreenReturnK1` (`src/controller-native/K1RuntimeResolution.cpp`):

1. For a window other than the main one, or with `rebuild=1` in `[Alt-Tab]` of
   `configs\kmrp.ini`, it stores the 2 itself and returns 0: the game goes on at
   `0x00402A70` exactly as before.
2. It reads the display's mode (`EnumDisplaySettingsA`, `ENUM_CURRENT_SETTINGS`). If it is
   not the game's size, `+0x1C`'s mode switch did not take: it stores the 2, writes
   `back from Alt-Tab: the display came back at WxH, not the game's WxH` to
   `KMRP\logs\kmrp-kpm.log`, and returns 0.
3. Otherwise it keeps the window: a window still minimised is restored with
   `ShowWindowAsync` (asynchronous, since this runs inside the window's own
   `WM_ACTIVATEAPP`); one not at the top left at the game's size is moved there with
   `SetWindowPos`. It returns 1, and the wrapper leaves through `0x00402A72`: the
   windowed path, which restarts interrupted movies and, with the second hook, calls
   `ActivateRenderWindow`. With debug logs on it writes `back from Alt-Tab at WxH: the same
   window and OpenGL context, no rebuild`.

The stack is the same at the hook and at `0x00402A72`: `edi` is pushed at `0x00402A2A` on
both paths, and the hook steals no instruction that moves `esp`. `0x00402A66` is a branch
target only at its first byte (`0x00402A59`); `0x00402ACF` is none (`0x00402AC0` jumps to
`0x00402AD1`). Both checked by scanning `0x00401000`-`0x006FF000` for branches into them.

**Count.** Eleven instructions reference `0x007A3A2C`, found by searching the code for
the address and decoding each hit from its instruction start. Five read it:
`0x00402A46` (this handler), `0x00403B50` (`ReInitAurora`), `0x0040460E` (the main loop),
`0x0040489F`, and `0x005F18F6` (the mode switch, where KMRP's `KmrpModeSwitchK1` hooks).
Six write it: `0x00402A66` (the one store in this handler, hooked), `0x00403B58`
(`ReInitAurora` clearing it), and `0x00401EC8`, `0x00401EDB`, `0x00402868` and
`0x0061B72B`, which set 1 or 2 elsewhere. Those four are not on the `WM_ACTIVATEAPP` path
and were not decoded further.

*Corrected later on 2026-11-10, twice.* The first two hooks did not stop the rebuild. The
maintainer's NVIDIA recording of a return at 3440x1440 showed the old frame for about 0.9 s,
about 0.9 s of black, then the game, and `KMRP\logs\kmrp-kpm.log` had `offscreen frame: on`
again at each return, which only a new window or context makes.

- **Rejected: the window's `WM_SIZE`.** `0x00402868` is the window procedure's `WM_SIZE`
  (message 5 goes to `0x0040284D` in its jump table at `0x00403368`/`0x0040338C`; `case 5`
  in the reconstruction's `message_00402800`): for the render window sized `SIZE_MAXIMIZED`
  (`wParam == 2` at `0x00402861`) it stores that 2. The guess was that Windows restores the
  window maximized, and a third hook made that store only outside full screen. It changed
  nothing, and the trace below shows that store never ran: no `WM_SIZE` hook call in five
  returns. The hook was taken out.
- **The cause, measured: the game's second window.** A trace written to the log on every
  return (each hook's decision, every `ReInitAurora` with its caller through a hook at
  `0x00403800`, why the offscreen buffer was made again, and every swap for five seconds)
  showed `WM_ACTIVATEAPP` arriving twice. The game has two windows sharing the procedure:
  the render window (`g_hRenderWindow`, `0x007A39D8`) and the outer window (`g_hWindow`,
  `0x007A39D4`, both named in swkotor1-reconstruction's `app_window.cpp`, read at
  `ac462c8`). The procedure asks for the rebuild for either (`0x00402A59` jumps past `+0x1C`
  to `0x00402A66` for any window but the render window). The hook kept the render window's
  return at tick 104526812 and, treating any other window as not its business, made the
  store for the outer window's 47 ms later; `ReInitAurora` followed from the main loop
  (`0x00404668`), with a new window (`00040E62` to `001D0AF6`) and a new context.
  `KmrpFullscreenReturnK1` now decides the same for both windows and restores only the
  render window. Next run: five returns, both windows kept each time, no `ReInitAurora`
  after start-up, the offscreen buffer made once, the first frame drawn 0.3 s after the
  return, no black (the maintainer). The trace was then taken out; the decision lines stay
  with debug logs on.

The other writers were decoded on the way: `0x00401EC8` and `0x00401EDB` are in
`0x00401E90`, called on Alt+Enter (`WM_SYSKEYUP` with `VK_RETURN` and Alt, `0x00402C9F`) and
for the movie window's Alt+Enter (`0x00403334`); `0x0061B72B` is an options setter that asks
for a rebuild only when the full-screen option itself changes (`0x0061B710`).

## 3. What is deliberately not changed

- **Leaving the game:** the minimise, `+0x18`'s desktop mode and gamma, and the stop of the
  render loop. A player switching away gets the desktop as before.
- **`+0x1C`:** the game's own gamma and mode switch, called by the game as before.
- **A rebuild already pending** (`[0x7A3A2C] != 0` at `0x00402A46`): goes ahead.
- **The game in a window:** never reaches either site's changed behaviour (`0x00402A44`
  takes `0x00402A72`; the `jne` at `0x00402ACF` is not taken when `+4` is false).
- **The other writers of the flag** (section 2, *Count*) and a change of resolution:
  their own rebuilds.
- **The 640x480 branch at `0x00404638`:** not reached on the light return, unchanged where
  the rebuild still happens.

## 4. Rejected

**KOTOR Patch Manager's Alt Tab Patch** (J, 1.8.1, MIT; `third_party/Kotor-Patch-Manager/
Patches/Alt Tab Patch`) removes the same rebuild, with three byte changes (`0x00402A5B`,
`0x00402A66`, `0x00402ACF`) and a window procedure of its own that switches the display
mode with `ChangeDisplaySettingsA`, restores and aligns the window, re-checks for three
seconds on a timer and shows the cursor again. It supports CD 1.03 and GOG, not Steam.
Appealing because it has been used; not adopted as it is, because it removes the `+0x1C`
call (`0x00402A5B`, eleven bytes of NOPs): `+0x18` set the gamma ramp to 1.0 on leaving,
so after a return the picture would stay at the desktop's brightness rather than the
game's (read from the code, not seen). KMRP keeps the game's call, and lists
`alt-tab-patch-v1` as a conflict in its patch (`OTHERS`, `tools/build_native_kpatch.py`),
since two patches cannot hook one address. Its timer and cursor handling are not copied:
whether a return needs them was not established, and the in-game test below is to show it.

**Borderless full screen** (the display mode never changes, so there is nothing to
restore): considered on 2026-11-10 and left for later by the maintainer, because it
changes full screen for every player and a size other than the desktop's would need
scaling.

## 5. Limits and untested

- **Not run in the game.** Whether the light return works on a real driver (picture,
  brightness, input, the cursor, a movie interrupted by Alt-Tab) is untested. So is
  whether the freeze of issue 96 is in the rebuild at all.
- A display whose mode comes back other than the game's size falls back to the rebuild,
  which is the old behaviour and the old risk.
- With `rebuild=1`, the second hook still makes drawing resume before the rebuild after an
  absence of a second or more, which vanilla did only under a second.
- On several monitors, `EnumDisplaySettingsA(NULL)` reads the primary display, which is
  the one the game's full screen changes (`ChangeDisplaySettingsA` with no device name).

## 6. Verifying by hand

1. `python tools/check_hook_stolen_bytes.py`: every hook steals position-independent bytes.
2. `python testing/regression/Test-KpatchSource.py`: the packaged hooks equal the source.
3. Disassemble the window procedure from the clean executable and confirm the bytes in the
   table: `0x00402A66` `C7052C3A7A0002000000`, `0x00402ACF` `7505`.
4. In the game, full screen, debug logs on: Alt-Tab away for more than a second and back.
   `KMRP\logs\kmrp-kpm.log` shows `back from Alt-Tab at WxH: the same window and OpenGL
   context, no rebuild`; the picture comes back at once, at the game's brightness, with the
   mouse working. Then the same during a movie: it starts again from its first frame.
