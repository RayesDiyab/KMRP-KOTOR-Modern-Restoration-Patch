# F1: `kmrp.dll` built without the controller code

> **Documentation standard.** This document follows
> [`../documentation-standard.md`](../documentation-standard.md).

**Kind: fix report** (issue 82, finding F1 of
[`../cleanup-audit-1.6-findings.md`](../cleanup-audit-1.6-findings.md)). Done
2026-10-31 to 2026-11-01, uncommitted. Every finding below was measured as described;
anything not measured says so.

## In short

`kmrp.dll` no longer compiles any controller source. The few functions of KMRP's that lived in
the controller's files are in a core file of its own and six files both modules share. Both
modules export exactly what they did; 118 of the 124 functions `kmrp.dll` links from the
changed files compile to the same instructions as before, and every one of the other six,
and of the controller module's 15, differs for a reason listed below, none of them a change
of behaviour. `kmrp.dll` is 19,968 bytes smaller: it did carry controller data after all.
Dead code went with it: two frames no patch hooks, their hook table entries, an always-false
option, and two counters nothing could raise.

## The problem

`build_native_runtime.cmd`, which builds `kmrp.dll`, compiled the whole controller code
base: `K1NativeJoystick.cpp` (9,067 lines), `K1ControllerBackend.cpp`,
`K1ControllerLayout.cpp`, `K1Rumble.cpp`, `K1ButtonRemap.cpp`, `vendor/K1XboxControls.cpp`
(7,471 lines) and `vendor/K1XboxControlsXInput.cpp`. KMRP's patch has carried no controller
hook since the two patches were split on 2026-10-05: its 36 hooks name 33 functions, all
exported, none a controller's. `K1NativeJoystick.cpp` told the two modules apart with 35
`KMRP_NATIVE_RUNTIME` / `KMRP_CONTROLLER_STANDALONE` blocks.

**Correction (2026-11-01).** This said first that the linker already left the unreachable
controller code out of the file, from four strings the reference `kmrp-native.dll` (915,968
bytes, SHA-256 `3FFADEE1CBB9BD06...`) does not hold (`cursor: visible while parked`,
`rumble`, `SDL_`, `Remap`). It left out most of it, not all: that build's linker map lists
symbols of all seven controller objects (`K1Rumble.obj` 275, `K1NativeJoystick.obj` 131,
`K1ControllerLayout.obj` 103, `K1XboxControls.obj` 98, `K1ControllerBackend.obj` 39,
`K1ButtonRemap.obj` 22, `K1XboxControlsXInput.obj` 22), most of them data and strings, and
the new file is 19,968 bytes smaller. So the shipped file carried dead controller material
too, not only the sources and the build.

## What `kmrp.dll` really needs from the controller files

Measured by linking `kmrp.dll` from the build's own object files with the controller files
left out (a probe in the session's scratch folder; with every object it reproduces the
reference file, 915,968 bytes). The linker's unresolved symbols are the exact list:

| Needed | Lives in | Needed by |
| --- | --- | --- |
| `NativeMovieWindowOpenK1`, `NativeMovieWindowCloseK1` (exports) | `K1NativeJoystick.cpp:2587`, `:2596` | hooks `0x0040554B`, `0x00404BB0` |
| `KmrpCoreMovieWorkK1` (export) | `K1NativeJoystick.cpp:7874` | hook `0x00404D06` |
| `KmrpCoreGuiWorkK1` (export) | `K1NativeJoystick.cpp:7862` | hook `0x0040CE76` |
| `NativeFreeSaveBufferK1` (export) | `K1NativeJoystick.cpp:2826` | hook `0x005DDE32` |
| `CorrectHardwareMipmapsK1` | `K1NativeJoystick.cpp:7780` | `KmrpTextureUploadedK1` (`K1TextLayout.cpp`) |
| `KmrpPartyPortraitsK1` | `K1NativeJoystick.cpp:4752` | `PlaceLists` (`K1RuntimeLayout.cpp`) |
| `StatusSummaryFrameK1` | `K1ControllerLayout.cpp:2000` | `KmrpCoreGuiWorkK1` |

and what those reach in turn: the movie window's state and painting (`MovieStateK1`,
`BlackenMovieWindowK1`, `PaintMovieWindowK1`, `TrackMovieFrameK1`), cursor confinement
(`UpdateCursorConfinementK1`, issue 20), the status summary's layout, and the helpers
`FieldAt`, `EngineFn`, `LooksLikePointerK1`, `IsReadableK1`. Nothing else in KMRP's core
files calls into the controller files.

## Found on the way

### Dead code, in both modules

| What | Why it is dead |
| --- | --- |
| `CoreGuiFrameK1`, `CoreMovieFrameK1` (`K1NativeJoystick.cpp:7825`, `:2712`) | hooked by neither patch: `build_native_kpatch.py` leaves them out (`CORE_FRAMES`) since KMRP's own frame sites (`KmrpCoreGuiWorkK1`, `KmrpCoreMovieWorkK1`) came on 2026-10-05 |
| `ControllerFrameK1` | called only by the two above: it looked for a `kmrp-controller.dll` copy loaded beside KMRP, the four-patch edition's arrangement (until 2026-10-04) |
| `KmrpControllerOptionK1`, `g_controllerOption` (`K1RuntimeEngine.cpp:96`, `:160`) | always false since 2026-10-05 (`OptionalFeatures` sets it so); read only by the two dead frames |

### Behaviour gaps, recorded and left as they are

- **The party portrait repair needs the controller patch.** `KmrpPartyPortraitsK1` repairs
  the empty portraits of the Party Roster Limit 32 mod's roster. It acts only on pages whose
  bindings `CapturePartyRosterBindingsK1` recorded, and that runs only from
  `NativePanelReleaseGffK1`, a hook of the controller patch (`0x00409B80`). In `kmrp.dll` the
  bindings are always empty, so the call in `PlaceLists` returns at once. With the controller
  patch, its own copy does the repair. F1 kept both modules doing exactly what they did. This
  was recorded first as a gap to leave; on 2026-11-01 the maintainer asked for it to work with
  KMRP alone, and it does since: [`F5-party-portraits-with-kmrp-alone.md`](F5-party-portraits-with-kmrp-alone.md).
- **The status summary is laid out twice per frame with both patches.** `KmrpCoreGuiWorkK1`
  calls `StatusSummaryFrameK1` and the controller's `ControllerLayoutFrameK1` calls the same
  `updateStatusSummary`. It only sets extents when they differ, so the second pass changes
  nothing; it is wasted work, not a fault. Left as it is.
- **`kmrp.dll`'s copy of the status summary's A badge never shows**: the badge list is filled
  only by the controller's ReleaseGff hook. That is as intended (the badge is the pad's).

### A correction

On 2026-10-31 issue 85's fix was installed in the maintainer's game as both `kmrp.dll` and
`kmrp-controller.dll`, on the belief that both modules carried it. Only the controller
module does.

## The change

Every block was cut from its file by exact text (a script that refused any anchor that was not
unique), so the code moved is the code that was there, unchanged except where the table says.

| New file | In | What, from where |
| --- | --- | --- |
| `K1CoreFrames.cpp` | `kmrp.dll` only | `KmrpCoreGuiWorkK1`, `KmrpCoreMovieWorkK1`, `NativeFreeSaveBufferK1` (its `K1_FREE` and `FreeFn` with it), `CorrectHardwareMipmapsK1`; `StatusSummaryBadgeK1`, answering false. From `K1NativeJoystick.cpp` |
| `K1EngineMemory.h` | both | `FieldAt`, `EngineFn`, `LooksLikePointerK1`, `IsReadableK1`, inline. From `K1NativeJoystick.cpp` |
| `K1GuiControls.h` | both | `at`, `fn`, `readable`, `setExtent`, `setExtentIfChanged`, the text widths, `openLog`, inline, in `namespace KmrpGui`; `K1_PANEL_CONTROL_ARRAY` and `_COUNT`. From `K1ControllerLayout.cpp` (the constants from `K1NativeJoystick.cpp`) |
| `K1MovieWindow.cpp` / `.h` | both | `MovieStateK1` and `g_movie`, `BlackenMovieWindowK1`, `PaintMovieWindowK1`, `TrackMovieFrameK1`, the window's open and close exports, the four geometry offsets. From `K1NativeJoystick.cpp` |
| `K1CursorConfinement.cpp` / `.h` | both | `UpdateCursorConfinementK1` (issue 20), its three counters now `g_cursorConfinement`'s, not the pad state's. From `K1NativeJoystick.cpp` |
| `K1StatusSummary.cpp` / `.h` | both | the status summary's layout and `StatusSummaryFrameK1`; the A badge is asked of the module (`StatusSummaryBadgeK1`). From `K1ControllerLayout.cpp` |
| `K1PartyPortraits.cpp` | both | `KmrpPartyPortraitsK1`. From `K1NativeJoystick.cpp` |

`K1NativeJoystick.cpp` (9,067 to 8,453 lines) and `K1ControllerLayout.cpp` (2,002 to 1,780)
are now the controller module's alone, so their 65 module guards were resolved by a script
that evaluated only `KMRP_CONTROLLER_STANDALONE` (defined) and `KMRP_NATIVE_RUNTIME` (not):
the runtime's branches went (its includes, two forward declarations, the `kmrp` name in the
frame timing log, and in `NativeGuiFrameK1` the runtime's resolution and cursor calls), every
other directive stayed. `K1Rumble.cpp` includes `K1EngineMemory.h` instead of declaring the two
helpers itself.

Removed as dead:

| What | Where | Why |
| --- | --- | --- |
| `CoreGuiFrameK1`, `CoreMovieFrameK1`, `ControllerFrameK1`, `FrameFnK1` | `K1NativeJoystick.cpp` | no patch hooked them (above) |
| their two `install = "no-controller"` entries | `kotor1.hooks.toml` (0x0040CE70, 0x00404D96) | named the frames above; `build_native_kpatch.py` filtered them out (`CORE_FRAMES`, removed too) |
| `KmrpControllerOptionK1`, `g_controllerOption` | `K1RuntimeEngine.cpp`, `.h` | always false since 2026-10-05 |
| `g_stick.saveBuffersFreed` and the dump's `sbf=` column | `K1NativeJoystick.cpp` | the module that writes the dump never runs the save hook, so it was always 0. Token and argument removed together, as the format is positional |

Build scripts: `build_native_runtime.cmd` compiles `K1CoreFrames.cpp` and the four shared `.cpp`
files instead of the seven controller sources; `build_controller_standalone.cmd` adds the four.

## Why two shared helpers became inline

The first build put `LooksLikePointerK1`, `IsReadableK1` and `K1GuiControls`' functions in
`.cpp` files of their own. Comparing the code showed what that did: inside
`K1NativeJoystick.cpp` and `K1ControllerLayout.cpp` they had been inlined, and in another file
every check became a call (`ClientInternalK1`, three range checks, went from 16 instructions to
26). The logic was the same, but slower in loops that run every frame, so they are defined
`inline` in their headers, as they compiled before. That is also why the controller module is
2,560 bytes larger (2,514,944 to 2,517,504): `K1Rumble.cpp`, which used to call them, now has
them inline too.

## How it was checked

**Exports.** `dumpbin /exports` of both modules before and after: `kmrp.dll` 33 and 33,
`kmrp-controller.dll` 49 and 49, the same names.

**The code, function by function.** The last commit's sources (`git archive HEAD`) and the
working tree's were compiled with the build scripts' own flags, for both modules, and every
function of the changed files compared instruction by instruction from the objects'
disassembly (each function its own section under `/O2`, so exact boundaries), names and
relocation targets matched with the anonymous namespace's hash made neutral, only functions the
new module links. A first pass that cut functions out of the linked DLLs by map address gave
false differences wherever neighbouring symbols had come or gone, and was dropped.

| Module | Compared | Identical | Differ |
| --- | --- | --- | --- |
| `kmrp.dll` | 124 | 118 | 6 |
| `kmrp-controller.dll` | 397 | 382 | 15 |

With `g_stick`'s field offsets (four fields left it) and jump offsets made neutral, every
remaining difference was read:

| Function | Why it differs |
| --- | --- |
| `InitializeEngineAt` | the `g_controllerOption` store removed; jumps after it shift |
| `NativeFreeSaveBufferK1` | the counter removed, so the free became a tail jump |
| `UpdateCursorConfinementK1` | its counters are `g_cursorConfinement`'s |
| `StatusSummaryFrameK1` | `updateStatusSummary` inlined into it, in its own file now |
| `layoutStatusSummary` | the badge is a call to `StatusSummaryBadgeK1` (it was inlined); `KmrpDebugLogs` and `openLog` are inlined (they were calls) |
| `KmrpPartyControlK1`, `std::map::find` | inline header code, inlined differently in a different file |
| `ControllerLayoutFrameK1` | calls `StatusSummaryFrameK1` where it inlined `updateStatusSummary` |
| `updateConfirmBadges`, `updateDialogBadges`, `updateEntryBadges` | `readable` and the `SetExtent` call inlined |
| `BaseItemOf`, `PlayerCreature`, `KmrpRumbleTickK1`, `NativeMuzzleFlashK1`, `NativeRumbleCutoffK1` (`K1Rumble.cpp`) | `LooksLikePointerK1` and `IsReadableK1` inlined, where they were calls |
| `NativeJoystickDumpK1` | the `sbf=` column removed |

**The build.** `build_kmrp.ps1`, complete, after the last change: KMRP.kpatch 465,999 bytes,
the controller patch 2,547,691 bytes; `kmrp.hooks.toml` 36 hooks and `kmrp-controller.hooks.toml`
38, as before.

**Tests.** Passed: `Test-MiniGameFire`, `Test-PazaakActions`, `Test-ControllerKpatch`,
`Test-RuntimeKpatch`, `Test-KpatchSource`, `Test-DriverCompatImports`,
`Test-ProtonResourceCompatibility`, `Test-ButtonRemap`, `Test-HudOptions`, `Test-TextOptions`,
`Test-PartyRosterGui`, `Test-LiveLayout`, `Test-ModCompatibility` (630 checks),
`Test-NativeTextLayout`, `Test-TextRows`, `Test-ControllerGlyphs`; `tools/check_controller_drift.py`
with the two warnings it gave before (below). Failing, and not because of F1:

| Test | Failure | Before F1 |
| --- | --- | --- |
| `Test-SwoopPrompt` | its harness compiles a slice of `K1NativeJoystick.cpp` that calls `KmrpDrawnPictureK1` without a declaration | the same error on the last commit's sources |
| `Test-GuiAudit` | `kmrpb_charexit.tga` not in a built archive | reads built art, which F1 does not touch; not re-run on the old build |
| `Test-ControllerPromptAssets` | no prompt entry for `galaxymap.gui` `BTN_ACCEPT` | the same |

`Test-GuiAudit`'s source gate "Windows core frame calls `StatusSummaryFrameK1`" read
`CoreGuiFrameK1`, the dead frame, so it guarded nothing; it reads `KmrpCoreGuiWorkK1` in
`K1CoreFrames.cpp` now, and run on its own it passes (the test stops at the archive error
before reaching it). Not run: `Test-WindowsEngineSource` (needs `--csc`), `Test-AbilityIcons`
(needs clang), `Test-InstallerPatch.ps1` (it borrows the maintainer's settings files), the
controller tests that drive a running game. **Not seen in a game.**

## Left for later

- `kmrp_controller.py` still knows an `install = "no-controller"` hook kind, for the developer
  installs of before 2026-09-29 (`installed_set(False)`, `core_hooks()`, the drift check's
  stand-ins); with the two entries gone nothing has that kind.
- The other controller-only files (`vendor/K1XboxControls.cpp`, `K1ControllerBackend.cpp` and
  the rest) keep their `KMRP_CONTROLLER_STANDALONE` guards, now always true there.
- `readable` (`K1GuiControls.h`) and `IsReadableK1` (`K1EngineMemory.h`) are the same check
  written twice, and `at`, `Field`, `At` and `FieldAt` are one helper under four names across
  the files: a finding of their own. (Done 2026-11-01: F4.)
- `Test-SwoopPrompt` is broken on the last commit already.
- The status summary laid out twice per frame with both patches, as described above. (The
  party portraits needing the controller patch: fixed since, F5.)
- `check_controller_drift.py`'s two older warnings: three badges built and never referenced
  (`kmrpa_clssel`, `kmrpl_pzkflip`, `kmrpx_pzkplay`), and the state dump's line able to reach
  1,484 bytes in a 1,200-byte buffer (1,499 before F1 removed `sbf=`). (Corrected 2026-11-01,
  F6: the buffer is 2,048 bytes; the check had read another function's.)
