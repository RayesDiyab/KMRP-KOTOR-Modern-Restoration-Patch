# Input lost after a movie list: the movie thread's posted deactivation

> **Documentation standard.** This document follows
> [`documentation-standard.md`](../docs/documentation-standard.md). Read it before
> editing this file, and check the result still meets it: measured claims only,
> every site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

**Kind: reference.** Why keyboard and mouse sometimes stop working after the startup movies,
until the game is minimised and restored, and the filter KMRP adds against it (2026-11-11).
Related: [movies.md](movies.md), *Alt-Tab and focus during a movie*, which read the same
worker path on 2026-10-19 for the full-screen case, and
[alt-tab-fullscreen.md](alt-tab-fullscreen.md) for the main window procedure's
`WM_ACTIVATEAPP`.

**How this was read.** Disassembled with Capstone from `build-inputs/swkotornopatch.exe` (CD 1.03,
SHA-256 `761F9466…C49E9886`, 4,042,752 bytes) and from GOG's v1.03 (`9C10E045…4DEA91435`) on
2026-11-11; every site below has the same bytes in both. The function names are those of the
public reconstruction TeamGizka/Odyssey (`dev/libsource/exomovieplayer/exomovieplayerinternal.cpp`,
`dev/game/swmain/main.cpp`), used as corroboration: every address and instruction quoted here was
read from the executable. Addresses are VAs; `FILE = VA − 0x400000` for every site here.

**How the race was measured.** Not in KMRP. It was measured on 2026-11-11 in KCRP, the
maintainer's other project, on GOG 1.03 with KCRP's OpenGL bridge loaded, which logged every call
to `CExoRawInputInternal::SetActive` (`0x005E3C20`) and every activation message the game's thread
handled. The maintainer has seen the same loss in vanilla and in KMRP. **KMRP's filter has been
built, not run in the game** (section 8).

## 1. What the engine does

Each movie plays in a window of the movie thread (`SWMovieWindow`, made by `InitializeMovie` for
every entry of a list, [movies.md](movies.md), *How the window is made*). To Windows, activation
moving between that window and the render window (`[0x007A39D8]`) is activation moving between
two threads, and each window is sent `WM_ACTIVATEAPP` for it: `wParam` 0 to the one losing
activation, with the other thread's id in `lParam` (Windows' documentation of the message).

**The movie window takes any deactivation as the game losing the player.** Its procedure,
`MovieMessageHandler` (`0x00405190`), `WM_ACTIVATEAPP` case:

```
00405255  test edi, edi                ; wParam: only a deactivation goes on
00405257  jne  0x00405387
0040525D  mov  ecx, [0x007A3CF4]        ; the movie player
00405265  je   0x00405387
0040526B  mov  eax, [ecx+0x24]          ; shutting down: ignored
00405270  jne  0x00405387
00405276  push edi                      ; 0
00405277  call 0x00404C20               ; OnDeactivation(0): [player+0x1C] = 1
0040527C  push 1
0040527E  push 1
00405280  call 0x00404C40               ; CancelMovie(1, 1): stopped, kept to play again
```

`lParam` is never read, so the game's own render window taking activation counts the same as
another program taking it. `OnDeactivation` has two direct callers in `.text`, this one and Alt+Enter's
(`0x004052BE`, which passes 1); counted with a scan for every `E8`/`E9` whose target is `0x00404C20`.

**At the end of the list, the worker forwards the deactivation to the render window.**
`MoviePlaybackWorker` (`0x00405B30`), with `[player+0x1C]` at 1 and `[player+0x20]` at 0:

```
00405C62  cmp  [esi+0x1C], edi          ; edi = 1: a deactivation was recorded
00405C6E  jne  0x00405CD9               ; no: post 0x40A, RestoreResolutionFromMovie
00405C76  cmp  [esi+0x20], edi          ; Alt+Enter recorded?
00405C79  jne  0x00405CC0               ; no:
00405CC0  mov  edx, [0x007A39D8]        ;   the render window
00405CC6  push ebp                      ;   lParam 0
00405CC7  push ebp                      ;   wParam 0
00405CC8  push 0x1C                     ;   WM_ACTIVATEAPP
00405CCA  push edx
00405CCB  call [0x0073D434]             ;   PostMessageA
00405CD1  mov  [esi+0x20], ebp
00405CD4  mov  [esi+0x1C], ebp          ; the record is cleared; the kept movies are not
```

`[esi+0x30]`, the "a movie is playing" flag, was cleared at `0x00405C6B`, before the post.

**The main window procedure handles it as a real loss of the foreground.** Its `WM_ACTIVATEAPP`
handler (`0x00402951`, [alt-tab-fullscreen.md](alt-tab-fullscreen.md)), `wParam` 0:

```
004029C8  call [eax+4]                  ; the renderer: full screen?
004029D0  jne  0x004029EC
004029DB  call [ShowWindow]             ; (render window, SW_MINIMIZE): full screen only
004029E9  call [edx+0x18]               ; the desktop's gamma and display mode
004029EC  mov  eax, [esp+0x34]          ; hwnd
004029F0  cmp  eax, [0x007A39D8]        ; the render window?
004029F8  call 0x00401D90               ; DeactivateRenderWindow
004029FD  call [GetTickCount]
00402A03  mov  [0x007A3C4C], eax        ; when the window was deactivated
```

`DeactivateRenderWindow` (`0x00401D90`), while `[0x007A3A38]` (the render window's "active" flag)
is set: pauses the game with pause type 2, switches input off through
`CClientExoApp::SetInputActive(0, 0)`, puts sound in its lost-focus mode, and clears
`[0x007A3A38]`. The pause and the sound are read from the reconstruction and the first
instructions of `0x00401D90`; only the input switch was measured (section 4).

## 2. The race

The post is not wrong by itself: when the player really leaves during a movie, the render window
has not been told, and the post tells it. It goes wrong when the deactivation the movie window
recorded was activation passing to the render window, or when Windows hands activation back to the
render window before the posted message is taken from the queue:

1. the movie window records a deactivation and the movie is cancelled;
2. the render window becomes the foreground window, and is sent `WM_ACTIVATEAPP(1)`:
   `ActivateRenderWindow` (`0x00401E00`), input on;
3. the worker's posted `WM_ACTIVATEAPP(0, 0)` is then taken from the queue: input off, with the
   render window still the foreground window.

Nothing activates the render window again until the foreground changes: minimising and restoring
it is what does that. It is a race between two threads, so it happens on some starts only.

**In full screen** (read from the code, not measured) the same message also minimises the game
and puts the desktop's display mode back, because the "a movie is playing" flag is already clear.
That would be seen as the game dropping to the desktop after the startup movies.
[movies.md](movies.md) reads this path for a real Alt-Tab and names "back to the desktop between
two movies" in issue 48; whether this race is a cause of that report is not established.

## 3. What KMRP changes

**No byte of the executable and no hook table entry.** One function of KMRP's module, called from
an existing hook:

| what | where | when |
| --- | --- | --- |
| `KmrpInstallMovieActivationFilterK1` | `src/controller-native/K1MovieActivation.cpp` | from `NativeMovieWindowOpenK1` (`0x0040554B`, a "kmrp-movies" hook, always installed), at every movie window; it installs once, as soon as `[0x007A39D8]` is set |
| `FilterPostedActivation` | the same file | a `WH_GETMESSAGE` hook on the thread that owns the render window |

The filter turns a message into `WM_NULL` when all of these hold:

| condition | why |
| --- | --- |
| `message == WM_ACTIVATEAPP`, `wParam == 0`, `lParam == 0` | the worker's post; Windows' own names the other thread in `lParam` |
| the target is `[0x007A39D8]`, read for each message | the render window, also after a rebuild makes a new one |
| `GetForegroundWindow()` is that window, and it is not iconic | the player really is in the game |
| `PM_REMOVE` | the message is being taken from the queue, not peeked |

A `WH_GETMESSAGE` hook sees posted messages only, so Windows' own `WM_ACTIVATEAPP`, which is sent,
cannot reach it, nor can the one `NotifyModeChangeActivate` (`0x00401E90`) sends with
`SendMessageA`. When the player has left during a movie, the render window is not the foreground
window, the message goes through, and the game deactivates as it always did. With debug logs on, each drop writes
`[KMRP] dropped the movie thread's WM_ACTIVATEAPP(0, 0): the game window is in front` to
`KMRP\logs\kmrp-kpm.log`; a filter that could not be installed is written there always.

The filter is built into `kmrp.dll` only (`#ifdef KMRP_NATIVE_RUNTIME` in `K1MovieWindow.cpp`); the
controller patch's module compiles `K1MovieWindow.cpp` too and gets none of it.

## 4. Measured

In KCRP (see *How the race was measured* above), on starts where the input was lost:

- `SetActive(0)` was called from `DeactivateRenderWindow`, with `GetFocus()` and
  `GetForegroundWindow()` both the render window;
- the message before it was a posted `WM_ACTIVATEAPP` to the render window, `wParam` 0, `lParam` 0;
- no `WM_ACTIVATEAPP` followed until the window was minimised and restored.

With the same filter in KCRP's bridge, on fresh starts it dropped that message about 15 s after
start, and a script then loaded a save and paused the game with keyboard and mouse, without a
minimise and restore. KCRP's record: its `docs/m2-play-endar-spire.md`, run 25.

## 5. How this stays isolated

- **KMRP's Alt-Tab return** (`KmrpFullscreenReturnK1`, `0x00402A66`) handles `WM_ACTIVATEAPP` with
  `wParam` 1. A dropped message never reaches the window procedure, so it never runs that
  handler; a message that is not dropped reaches it unchanged.
- **The movie window's procedure** is not touched: a movie is still cancelled and kept as before.
- **The hook's owner.** Windows removes a hook when the thread that set it ends. It is set from the
  movie thread, whose worker loops until the game asks it to stop (`0x00405CFE`-`0x00405D00`),
  then calls `ExitThread` (`0x00405D09`, through the import at `0x0073D1E0`). That Windows removes
  the hook then, and only then, is from its documentation, not tested.

## 6. Limits

- The filter decides when the message is taken from the queue. If the render window is not yet
  the foreground window at that moment, the message goes through and input is lost as before.
- In full screen, the minimise is dropped together with the deactivation when the window is in
  front, and kept when it is not. Neither case has been run.

## 7. What is deliberately not changed

- **The cancelled movie.** The deactivation the movie window records still cancels the movie that
  was playing and keeps it and the rest of its list (`0x00405280`; [movies.md](movies.md)). The
  game plays a kept list again from `RestartMoviesIfNecessary`, on a later return in a window
  (`0x00402AA2`, more than 100 ms after the last deactivation) or after `ReInitAurora`. In the race
  vanilla never gets that return either until the player minimises and restores, so the kept list
  is the same with or without the filter. Whether a later Alt-Tab return then replays a cut
  startup movie, in vanilla and with the filter alike, was read from the code and not seen.
- **The post itself** at `0x00405CCB`, which is right when the player has left.
- **Alt+Enter's posts** (0x409, `0x00405C97`, `0x00405CB2`) and the end-of-list post (0x40A,
  `0x00405CEC`).

## 8. Rejected and not tried

- **Removing the post** (`0x00405CC0`-`0x00405CD0`). Appealing because it is six bytes; rejected
  because a player who really leaves during a movie would then leave a game that still thinks it
  has the foreground, with input and sound on.
- **Deciding on the movie thread, at the post.** The foreground can still change between the post
  and the main thread taking the message, which is the race itself.
- **Not tried: the root.** Ignoring, in `MovieMessageHandler`, a deactivation whose `lParam` is
  the game's main thread would stop the cancel, the record and the post together, and would keep
  the startup movies from being cut. It needs a hook inside `0x00405190`, and first a measurement
  of the `lParam` the movie window actually gets on such a start: it is not known that activation
  passing to the render window is what records the deactivation.
- **Installing from KMRP's `wglMakeCurrent` swap** (`MakeCurrentForGame`, `K1OffscreenFrame.cpp`),
  as KCRP installs from its `ChoosePixelFormat` swap. Rejected: that swap is left out with
  `window-drawn=1` and in other cases, so the fix would depend on the offscreen frame.

**Untested:** whether the filter installs and drops the message in KMRP's build; in a window, in
full screen, under Wine or Proton; with KMRP's Alt-Tab return; Steam's build (decrypts to the same
bytes in memory, [alt-tab-fullscreen.md](alt-tab-fullscreen.md)).

## 9. Verifying by hand

1. Disassemble `0x00405255`-`0x00405285`, `0x00405C62`-`0x00405CD7` and `0x004029C8`-`0x00402A03`
   from `build-inputs/swkotornopatch.exe` and compare with the listings above. With Python and
   Capstone: map the VA to the file (`FILE = VA − 0x400000`) and disassemble 32-bit.
2. Count `OnDeactivation`'s callers: every `E8` or `E9` in `.text` whose `rel32` lands on
   `0x00404C20`. Two, at `0x00405277` and `0x004052BE`.
3. In a built module, the map (`build/native-runtime/kmrp-native.map`) lists
   `KmrpInstallMovieActivationFilterK1` and `FilterPostedActivation` from `K1MovieActivation.obj`,
   and `NativeMovieWindowOpenK1` ends in a jump to the first.
4. In the game, with debug logs on: start it several times. On a start where the race happens,
   `KMRP\logs\kmrp-kpm.log` has the "dropped" line and keyboard and mouse work at the main menu
   without a minimise. Then Alt-Tab away during an intro movie and come back: the game deactivates
   and returns as before, with no "dropped" line.
