# GFX-01 audit: the 1600x1200 black fill (2026-11-02)

> **Documentation standard.** This document follows
> [`documentation-standard.md`](../../documentation-standard.md).

**Kind: audit record of 2026-11-02.** Static audit of the 1600x1200 fill; its T0, T1 and T2 have since run. Results since are in
[`windows-verification-1.6.md`](../../windows-verification-1.6.md).

Read-only. Nothing was built, run, started or edited. Evidence words: **read** (instructions or
source read), **measured** (a value taken from a file or log), **reported** (a player said it),
**suspected** (inference, not proven). "Documented API" means what Windows documents, not seen here.

**Image read:** GOG 1.03, `C:\KoTor RE\swkotor.exe`, disassembled with Capstone across all of
`.text`. `build/verify/steam/swkotor.exe` could not be used: its bytes at `0x00401A30` are
`6C 74 E8 30...` on disk, so `.text` is encrypted there and Ghidra sees no procedures (measured).
That the Steam image equals GOG here once decrypted is **suspected**: K1DC's table says one address
table covers all three, and KMRP's 82 guarded runs apply on Steam, but no guard covers this routine.
Other sources: the public decompilation, the maintainer's own private reverse engineering, `git`.

## Short answer

1. **The earlier "not reproduced" run did not test the reported sequence.** In 1.5.0 and 1.5.1 the
   fill runs at the **end of the start-up logos**, from `RestoreResolutionFromMovie`, right before
   the menu (read). That rebuild has not existed on master since `3ab7a87` (2026-10-20). On master
   with Anti Aliasing 8 and movies on, the fill runs **before** the logos, and a full-screen topmost
   movie window then opens over it. So the run on master says nothing about 1.5.1.
2. **Issue 39 already holds a cause report the audit documents did not use:** two players, one of
   them the reporter, said turning compatibility mode off removes the block, on 1.5.1 (reported,
   issue comments of 2026-10-15 and 2026-10-16). The block appeared after the logos, not on them
   ("opening lucas arts and bioware logos are unaffeced"). Both fit point 1.
3. **Why it stays is still not proven.** The game has no repaint call of any kind, so anything that
   clears the block comes from Windows or the driver. Compatibility mode decides it (reported); how
   is suspected only.
4. **Master can still run the fill**: start-up with AA above 0, returning from Alt+Tab in full
   screen, and the Options screens (read). None of them was tested. The installer's layer removal
   does not cover a mode set for all users, or one set after installing.
5. **A safe fix exists:** six bytes at `0x00401B09`. Nothing depends on the fill. See section 5.
6. **Issue 91 is unproven.** Its picture fits (primary monitor, about 83% of a 1080p screen, helped
   by moving to the other monitor) but nothing rules out another cause, and neither the KMRP
   version nor a compatibility setting is known.

## 1. The thread and the fill

### Callers of `ReInitAurora` (`0x00403800`, cdecl, 5 args: width, height, depth, fullScreen, reload)

Eight call sites in all of `.text` (read, a scan of every instruction). The thread starts only when
`CAurInternalGL::GetDisplayStyle` (vtable `+4`, `0x0044D6D0`, returns `[this+0xAC]`) is 1 **and**
arg 4 is 1 (`0x00403850`-`0x0040385F`), that is full screen to full screen.

| Call site | Routine | Arg 4 | When | 1.5.1 | master |
| --- | --- | --- | --- | --- | --- |
| `0x00403D9E` | `ChangeResolutionForMovie` | 1 | before a playlist, mode not 640x480x32 | never (operands patched) | never |
| `0x00403F07` | `RestoreResolutionFromMovie` | `[0x7A3CBC]` | after a full-screen playlist, saved mode not 640x480x32 | **every playlist** | never (`0x00403EAD`, `0x00403EB9` patched), unless `original-movie-mode=1` |
| `0x005F92D9` | start-up, reads `swkotor.ini` | `[options]` bit 3 | AA above 0 | only without movies or when windowed (`jne 0x005F92A8` kept) | **full screen too** (`jne` is NOPs) |
| `0x00404663` | `InitApplication` main loop | `[0x7A3A2C]==2` | flag `[0x7A3A2C]` set, see below | yes | yes |
| `0x005F19B2` | `SetVideoMode` (`0x005F1830`) | varies | video mode change | yes | yes |
| `0x006DEC31` | `CSWGuiOptionsGraphics::HandleInputEvent` | current | Options | yes | yes |
| `0x006E032D` | `CSWGuiOptionsGraphicsAdvanced::HandleInputEvent` | current | Options (AA and so on) | yes | yes |
| `0x006E0E41` | `CSWGuiOptionsResolution::HandleInputEvent` | current | resolution apply | yes | yes |

**`[0x7A3A2C]`** is set to 2 at `0x00402A66`, in the window procedure's activation handler, after
`RestoreAuroraDisplayMode` (vtable `+0x1C`), when the game is in full screen and `[0x7A3A10]` is 0.
`[0x7A3A10]` is set on leaving only if `IsMoviePlaying` (`0x005EDB40`) returned 1 (`0x00402988`-
`0x004029A1`). So **returning from Alt+Tab in full screen with no movie playing queues a full-screen
rebuild, and so the fill** (read; the handler's whole control flow was not traced, and the path was
not run). No earlier document lists this path. Also set by `HandleKeyDown` (`0x00402868`), `OnAppActivated` (`0x00401EC8`,
`0x00401EDB`) and `CClientOptions` (`0x0061B72B`). The value 2 gives arg 4 = 1.

**Side finding, a fourth 640x480:** at `0x00404638`/`0x0040463D`, when `[client+0x4BC]` is non-zero,
the same path calls `ReInitAurora(640, 480, 32, ...)`. Those operands are not in KMRP's recipe
(`grep` of `tools/build_windows_engine.py`, `build_native_engine.py`, `windows-sites.json`: no hit).
What `+0x4BC` means was not decoded, so whether this ever runs is unknown. CLAUDE.md rule 3 applies.

### The thread

Read at `0x00401A30`-`0x00401BAD`. The decompilation agrees.

| Step | Address | Detail |
| --- | --- | --- |
| Created | `0x00403869`-`0x00403892` | `CreateEventA` (manual-reset 0, unset), `CreateThread(0, 0x8000, 0x00401A30, event, 0)`, then `SetThreadPriority(15)`, time critical. The thread can run before that call lands |
| Register class | `0x00401A3D`-`0x00401AE3` | Once, flag `[0x7A3CEC]`. Class `KotorCin` (`0x0073D634`), procedure `0x00401590`. A failure shows a message box and returns |
| Window check | `0x00401B01`-`0x00401B09` | `GetWindowInfo([0x7A39D8])`. **Failure returns with no fill** |
| Create window | `0x00401B37` | `CreateWindowExA(WS_EX_TOPMOST, "Knights Cinematic Backdrop", same, WS_POPUP\|WS_VISIBLE, 0, 0, 0x640, 0x4B0, ...)` |
| Move | `0x00401B53` | `SetWindowPos(eax, TOPMOST, 0, 0, 0x640, 0x4B0, 0x121)` |
| DC | `0x00401B5A` | `GetDC(eax)` |
| **Fill** | `0x00401B71` | `PatBlt(dc, 0, 0, 0x640, 0x4B0, BLACKNESS)` |
| Tidy | `0x00401B79`, `0x00401B82` | `ReleaseDC`, `ShowWindow(eax, SW_MAXIMIZE)` |
| Wait | `0x00401B92`-`0x00401B9C` | `WaitForSingleObject(event, 1)` while it times out |
| End | `0x00401B9F` | `DestroyWindow(eax)`, return 0 |

**The window never exists (read).** `0x0073D610` is pushed only as those two names. None
of the five `RegisterClassA` sites (`0x00401A92`, `0x00403794`, `0x004040C8`, `0x0040546C`,
`0x0042E09A`) can register it, as nothing else names that string; the class registered here is `KotorCin`. Even with matching names, `0x00401590`
is `xor eax,eax; ret 0x10`, so `WM_NCCREATE` would return 0 and creation would fail anyway (documented
API). So `eax` is NULL, every window call fails, and `GetDC(NULL)` gives the **screen DC** (documented
API). No run has confirmed the NULL. It is the design failing: a black curtain window was meant to
cover the rebuild, and BioWare's bug turned it into one unclipped GDI write to the screen.

**Size:** hard-coded, three pairs of immediates (`0x00401B1A/1F`, `0x00401B42/47`, `0x00401B62/67`).
Not from the resolution. `GetWindowInfo`'s result is never read. The 60 bytes of `WINDOWINFO` go
unused, so the check only tests that a window handle is valid.

**Place:** (0,0) of the screen DC, the primary monitor's origin, whichever monitor the game is on
(documented API; suspected for an unusual monitor layout).

**A race (read):** the main thread clears `[0x7A39D8]` at `0x0040392A`, and the new handle lands at
`0x004037E3`. Thread start to `0x00401B01` is short and the main thread has a cross-process
`FindWindowA`, `EnableWindow`, `ShowWindow` and `Shutdown` to do first, so the thread usually wins
(suspected). A loss means no fill at all, so the fill is not guaranteed on every rebuild.

### What follows, in `ReInitAurora` (read)

1. Taskbar hidden and disabled (`0x004038B2`, `0x004038BA`).
2. `CAurInternalGL::Shutdown(0, 0)` through vtable `+0x20` at `0x00403923`. The second argument is
   0 on the full screen to full screen path, so `ChangeDisplaySettingsA(0,0)` at `0x0044EC18` and
   `DestroyWindow` at `0x0044EC4B` are **skipped**. The desktop mode is not restored.
3. New window, `InitRenderWindow` (`0x004036F0`): class brush `BLACK_BRUSH` (`0x00403779`), style
   `0x02CA0000`, `CW_USEDEFAULT` size.
4. Vtable `+0xC` `GetValidMode` at `0x00403A57`, then `+8` at `0x00403A86` (`0x0044DAB0`), which
   finds a display mode matching width, height, depth **and refresh** (`0x0044DB34`-`0x0044DB63`),
   `ChangeDisplaySettingsA(CDS_TEST)` at `0x0044DBA0`, `CDS_FULLSCREEN` at `0x0044DBCD`, style
   `0x82000000`, `SetWindowPos(HWND_TOPMOST, 0, 0, w, h, 0x120)` at `0x0044DC72`, `ShowWindow(1)`,
   new pixel format and context.
5. `DestroyWindow(old)` at `0x00403B3D`, `InitGLState`, `AppDeactivate`, `AppActivate` (`0x00403BFE`).
6. `RestartMoviesIfNecessary` (`0x00403C21`) when arg 5 is 1 and a flag allows.
7. Taskbar shown (`0x00403C59`), `SetEvent` (`0x00403C64`), spin on `GetExitCodeThread`
   (`0x00403C8A`), `CloseHandle` twice.

**So the rebuild's mode call is a no-op only if the mode already matches.** With the same size and
refresh, Windows has nothing to change (suspected, documented behaviour not checked). With another
refresh, the mode really changes. That matches the 240 Hz monitor's half-second signal loss recorded
on 2026-10-20 (`movies.md`, *The third pair*).

## 2. Every other black or fixed-size draw

**Every drawing call the game imports (read, import table):** gdi32 gives only `ChoosePixelFormat`,
`DescribePixelFormat`, `GetStockObject`, `PatBlt`, `SetDeviceGammaRamp`, `SetPixelFormat`,
`SwapBuffers`. user32 has **no** `InvalidateRect`, `RedrawWindow`, `UpdateWindow`, `BeginPaint`,
`EndPaint` or `FillRect`. There is no `BitBlt` or `StretchBlt`. **The game cannot ask for a repaint.**

| Site | What | Size | DC | Fixed? |
| --- | --- | --- | --- | --- |
| `0x00401B71` | fill above | 1600x1200 | screen | **yes, the only one** |
| `0x00405012` | `RefreshWindowLayout`, movie message 0x408 | `0x78D1D4/D8` | `GetDC(0x7A39D8)`, main window | no, game's size, clipped to the window |
| `0x004058B1` | `InitializeMovie` | same | same | no. Runs just before the movie is shown |
| `0x00403779`, `0x004040AD` | black class brush | client area | erase | no |
| `0x0042E07F` | `InitializeAntiAliasing` probe window | client | erase | no |
| 22 `glClear` sites | GL | current viewport | GL | no fixed viewport found: no `0x640`/`0x4B0` near them |
| `0x0044DA27` | `SetDeviceGammaRamp` on `GetDC(0x7A39D8)` | not a draw | | |

All other `0x640`/`0x4B0` immediates in `.text` were listed. Those in functions with known names are
resolution compares (`IsValidResolution` `0x005F0CB7`, `GetScreenResolutionString` `0x0040A457`,
tooltips `0x00627807`, target menu `0x0068C4F9`) or unrelated (`0x0044ADDC` a vertex pool in
`MdlNodeLightsaber`, `0x004B2599` a disk-space check). The rest, in `0x0063C000`-`0x006E5300`, are
compares and subtractions on 16-bit values, not read one by one. No float `1600.0` or `1200.0`
appears as an immediate. Constant-pool floats were not scanned.

The loading screen and every later frame are GL, in the window.

## 3. KMRP and K1DC sites

No hook or patch in KMRP's master `kotor1.hooks.toml`, `windows-sites.json`, High FPS Fixes 1.0.1 or
Marked Empty Containers falls in the thread, `ReInitAurora` or `RestoreResolutionFromMovie`
(measured, a script over their tables). K1DC 1.2.0 and 2.0.1 have one in the wider range, `0x0044DF8E`,
a context-creation call. So nothing touches the fill: KMRP changes **when it runs and what follows**.

| Item | 1.5.0, 1.5.1 | master | Effect on the fill |
| --- | --- | --- | --- |
| First two movie pairs | patched | patched | No 640x480 for a movie. No real mode change around a playlist. **This is what removed the repaint: vanilla's rebuild after the logos really changed the mode** |
| Third pair `0x00403EAD/B9` (`3ab7a87`, 2026-10-20) | absent (measured, `git grep v1.5.1`) | patched | 1.5.x: fill after every full-screen playlist, at the same mode. Master: no rebuild after a playlist |
| `0x005F92A8` NOP (same commit) | absent | patched | Master: with AA above 0 the fill moves to before the logos |
| `0x00405734`, Bink surface | DirectDraw (no site in 1.5.1) | DIB | Suspected relevant, H3 |
| Offscreen frame | absent | always on | Unrelated to issue 39, which predates it. `SwapBuffers` still writes the whole window. A refused blit (GFX-04) would be all black, not this block |
| `SwapBuffers` slot `0x0073D00C` | game's or K1DC's | KMRP and K1DC share it | Same |
| NVIDIA present | installer sets Prefer native if layered would be inherited (`K1RuntimeNvidia.cpp`) | removes old values only (`KpmEdition.cs:541`) | Present path differs between 1.5.1 and master, H4 |
| Movie window | black class brush | same | Master: a topmost movie window opens after the AA rebuild. Suspected to wipe a fill |
| DPI | `HIGHDPIAWARE` layer token, `SetProcessDPIAware` | same | Fill is in physical pixels. Issue 39's exact 1600x1200 at 3440x1440 agrees |
| Compatibility modes | left alone | installer removes them from HKCU, `dpi.manifest` keeps the old value; HKLM only reported | **Not seen in a game (CHANGELOG 2026-10-27).** A mode set later, or for all users, stays |
| K1DC | 1.2.0 | 2.0.1 | Reporter still had the block with it deselected on 1.5.0 (reported). Excluded for issue 39 |

Compatibility tokens removed: `WIN95` to `WIN81RTM`, `256COLOR`, `16BITCOLOR`, `640X480`
(`KmrpPatcher.cs:254`). `DISABLEDXMAXIMIZEDWINDOWEDMODE` is kept. So the earlier run's second layer
was never a mode the installer treats as the cause.

**The start-up sequences:**

| Build | Sequence with full screen, movies on |
| --- | --- |
| vanilla | window at 640x480, logos, rebuild to the ini size (**real mode change**, fill, covered), menu |
| 1.5.x | window at game size, logos, **rebuild at the same mode, fill**, menu. Reporter: logos fine, block on the menu |
| master, AA 0 | window, logos, `AppActivate` only, menu. **No fill at start-up** |
| master, AA above 0 | window, **rebuild, fill**, logos in a topmost window, `AppActivate`, menu |
| master or 1.5.x, AA above 0, `Disable Movies=1` | window, rebuild, fill, menu. **Closest thing on master to 1.5.x** |

**Can KMRP skip the repaint? Yes, in 1.5.x, and that is the one change that exposes the block (read
for the sequence, suspected for its visual effect).** On a rebuild at the same mode nothing tells
Windows the desktop changed. Other than the mode change, what could clear the block is the new window
appearing and its presents. Those are the only candidates:

- **`WM_PAINT` and erase:** the class brush erases the window, not the screen. Whether that overwrites
  a screen-DC write depends on how the composed desktop treats such a write. Not known here.
- **`SwapBuffers`:** the same. It writes to the window's surface, not to the screen DC.
- **Composition:** under a composed desktop, screen-DC writes appear above windows until the area is
  updated (suspected, general knowledge, not measured here). Whether a GL window in the flip path
  counts as an update, and what a compatibility mode does to that path, is the open question.
- **DPI virtualisation:** excluded for issue 39 by the exact size, unless that PC runs at 100%, where
  it has no effect anyway.

## 4. Hypotheses, ranked

| # | Hypothesis | For | Against, unknown |
| --- | --- | --- | --- |
| **H1** | The block is the fill at the same-mode rebuild, and a compatibility mode keeps later frames from replacing it | Exact rect, nothing inside it; timing after logos (read); compat off removes it (reported, 2 players); vanilla menu fine (reported, 800x600) | Mechanism unknown |
| **H2** | The mode really changes on most PCs, which clears it; only a rebuild at the matching refresh leaves it | Mode match includes refresh (read); 240 Hz report | Compat off fixed it, which H2 alone does not explain. Can only be a modifier of H1 |
| **H3** | Bink's DirectDraw surface in 1.5.x plus a compatibility mode changes the desktop's state | DirectDraw is the subsystem compat modes mostly target (suspected); gone on master | No evidence yet |
| **H4** | Present path decides it (native vs layered, by vendor) | 1.5.x forces native on NVIDIA; test PC's profile differs; issue 91 says AMD; reporter's GPU never stated | |
| **H5** | Not the fill: a GL or GUI element sized 1600x1200 | 1600x1200 is a GUI size KMRP 1.5 shipped | "Nothing inside" means it is above the menu; compat off would not explain it; no such draw found |
| **H6** | The window does exist under a compat layer | | Class mismatch and `WM_NCCREATE` are independent of layers. Near dead |

### Tests here, on `build/verify/steam`

All by you, harness and ddagrab. Sample the box at 1 s and 10 s after the menu. Set and remove the
layer on the copy's path only.

**T0, prove each layer took effect (the gap in the earlier run).** After start, read the process PEB
with `ReadProcessMemory`: `OSMajorVersion`/`OSMinorVersion` (`+0xA4`, `+0xA8`) for a version layer,
and `pShimData` (`+0x1E8`; check the offset for a 32-bit PEB). A layer that changes nothing there has
not been applied. A version layer that shows Windows 10 means the run proves nothing.

| Test | Setup | Proves or kills |
| --- | --- | --- |
| **T1, first** | `Disable Movies=1` under `[Game Options]`, AA 8, each of `WIN7RTM`, `WIN8RTM`, `WIN81RTM`, `VISTASP2`, `WINXPSP3`, none | Block with a layer, none without: H1 confirmed on this PC. No block at all: go to T2 |
| **T2** | Movies on, a new script writes 640 and 480 back to `0x00403EAD`, `0x00403EB9` after KMRP applies (`live_harness.py` does not write memory, so a separate tool), same layers | Exact 1.5.x order on master. No block in T1 and T2 with T0 good: not reachable on this PC, H4 stands |
| **T3** | In a run that shows it, write `E9 99 00 00 00 90` at `0x00401B09` before the rebuild | **Decisive for H1 and H5.** Block gone: it was the fill. Still there: H5 |
| **T4** | Master with no layer, AA 8: leave and return with Alt+Tab; change AA in Options | Shows what master does for normal players. `bring_forward` works for the return. The Alt+Tab path needs a keyboard or the maintainer |
| **T5** | With T1's block, set `RefreshRate` in the ini to another mode of the display, then to the desktop's | H2 |
| **T6** | Write `00` back at `0x00405734` on the T1 or T2 setup | H3. Run with layers both on and off |
| **T7** | Run 1.5.1 itself on a separate copy (a release download, your decision), one layer | Ground truth for the reported build |

To confirm the fill runs at all, a log breakpoint on `0x00401B71` works on a GOG fixture such as
`build/controller-standalone/game-gog`, not on the Steam game. A second test counts the race.

### What needs an affected player

- **Issue 39's reporter, or anyone like them:** the value at `HKCU\...\AppCompatFlags\Layers` for
  `swkotor.exe`, which mode they had. GPU, which was asked and never answered. What took the
  screenshots: a Steam F12 or an in-game hook reads the GL buffer, so a block in that kind of shot
  kills H1. Windows capture does not.
- **Issue 91:** KMRP version, primary monitor size, whether the block's corner is at the primary's
  (0,0), compatibility tab, `swkotor.ini` `RefreshRate` and the desktop's, AMD model and driver, a
  photo. If 1.6, whether `Anti Aliasing` is above 0.
- **AMD and second-monitor runs:** this PC has neither. H4 cannot be settled here.

## 5. Is there a safe fix? Yes. Not made.

**Recommended: make the thread return at its existing exit.**

| VA | FILE (GOG) | Bytes | From | To |
| --- | --- | --- | --- | --- |
| `0x00401B09` | `0x001B09` | 6 | `0F 84 98 00 00 00`, `je 0x00401BA7` | `E9 99 00 00 00 90`, `jmp 0x00401BA7` |

Check: `0x00401B0E + 0x99 = 0x00401BA7`. The two pushes at `0x00401B14`/`15` come after the jump and
`0x00401BA7` is before their pops, so the stack matches; the game's own `je` takes the same path.

- **Nothing depends on it (read).** No caller reads the exit code but for "still active". `SetEvent`,
  the spin and both `CloseHandle` calls work on a thread that has ended. A failed `GetWindowInfo`
  already takes this path.
- **Visible change:** during a rebuild the player sees the last frame or the desktop in that corner,
  not black. Only the top-left 1600x1200 was ever black, so the curtain never hid the whole screen on
  a large display. A smaller display loses a brief black moment.
- **Alternative:** `00 00 00 00` for the width at `0x00401B68`. Four bytes, but it leaves the failing
  `CreateWindowExA` calls in. Not better.
- **Not recommended:** a real curtain, or sizing the fill to the screen. Both add work and the second
  makes a stuck block cover everything. A `RedrawWindow` after the rebuild treats the symptom and
  relies on the unknown mechanism.
- **Risk:** low. It may not cure the cause if T3 says the block is something else, and it can do no
  harm then. An unrelated flicker could become visible.

**What it would need:** a site in `src/engine/windows-sites.json` through `tools/build_windows_engine.py`;
guards pass on GOG, CD and Steam (the Steam file is encrypted here, so a run-time site, and the
`--apply` path needs a check); `binary-inventory.md`; CHANGELOG; `movies.md`; the Mac handoff doc
(the Aspyr build was not read). On Steam, KMRP's engine lands about 1.2 s after start (measured: 255
of 259 logged runs say "before its window", 4 say "after"), which is before every rebuild but
possibly the AA one in those 4.

**Docs to correct whichever way this goes:**

- `docs/windows-verification-1.6.md`, "GFX-01: running game": the run tested master's order only.
- `docs/windows-verification-1.6.md` line 54 and the audit report: `no GL state or KMRP site touches
  it` stays true, but KMRP moved **when** it runs, in both directions.
- `docs/cleanup-audit-1.6-report.md`, GFX-01: "KMRP rebuilds at the same mode" is 1.5.x's sequence;
  on master it is only the AA, Alt+Tab and Options paths. The 46% was already corrected.
- `movies.md` line 183 and the "Which of them runs in full screen was not traced" item: the Alt+Tab
  path above answers part of it.

## Not done

Issue 39's screenshots were not reopened (the documents' measurement was used). The window procedure
was read in part, around activation. The `glClear` sites' viewports were checked by constant only.
No Steam in-memory image was read. KMRP 1.5.1 was read in `git`, not run.
