# The KMRP 1.6 engineering audit: report

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md).

**Kind: working record, the one authoritative result of issue 82's audit.** Read at master
`2194acf`, 2026-11-01. It replaces no earlier file:
[`cleanup-audit-1.6.md`](cleanup-audit-1.6.md) is the entry list and
[`cleanup-audit-1.6-findings.md`](cleanup-audit-1.6-findings.md) the first findings, F1 to F13.
The fourteen reviews behind it, with line maps and evidence, are in `cleanup-1.6/reviews/`.

**State of this audit.** Fourteen read-only reviews by subsystem, then checks by the lead
reviewer. **Nothing in sections 1 to 8 has been run in a game.** No fix from this report has
been made. "Confirmed" means a path traced to its end in source and executable; it does not mean
reproduced. Audited code is never proof of behaviour on AMD, Intel, Proton or the Mac.

## 1. Result in brief

| | |
| --- | --- |
| Critical findings (memory corruption, data loss) | **none** |
| High | 13 (14 counting the conditional GFX-04) |
| Medium | 30, and 10 structural items |
| Low | 28 |
| Dead code proven | about 2,440 native lines, about 3,100 installer lines (reference code no install runs) |
| Native lines run by no test | about 11,800 in 20 files, and the two largest files only through slices |

**What held up, and should stay.** The KPM hook contract, all 74 hook sites and their stolen
bytes, the 87 recipe guards, 123 engine call signatures, the object lifetime logic, the applier's
thread pause and roll-back, the art pack and asset cache writes, ownership checks in the
installers, and the hook layout across all five patches (no overlaps). See section 5.

**What matters most, in order.**

1. Every upgrade resets a player's settings (INS-01).
2. Y, B and action cycling can silently do nothing (PAD-1, PAD-2), the traceable cause of
   issues 88 and 90. Issue 87 traces to the bark bubble (PAD-4).
3. Nothing runs the tests, and the code that runs in games has no test where it most needs one
   (TST-01, TST-02, TST-06).
4. A failed preparation repeats forever, a hang at start for some players (THR-2).
5. A 1600x1200 black rectangle painted by the game's own code is the leading explanation of
   issues 91 and 39 (GFX-01).

## 2. Coverage matrix

"Analysed" means read and judged, with the evidence named in the review. It does not mean run.

| Area | Items | Docs read | Checked against reality | Depth | Open |
| --- | --- | --- | --- | --- | --- |
| KMRP's hooks | 36 | yes | handlers, callers, exe | full | keyboard on real hardware (F13) |
| Controller hooks | 38 | yes | handlers, exe, stolen bytes | full | none in code |
| Bundled patches | 65 | yes | site overlap; High FPS dt handling by disassembly | overlap only, not their logic | K1DC source absent |
| Engine recipe | 87 runs, 59 operands | yes | every guard against the clean exe, every stub disassembled | full | `0x0045A3B7`, `0x0045A3DC` firing today |
| Run-time writes | 10 listed, 2 found missing | yes | import slots, hot patches, vtables | full | Proton's opengl32 form |
| kmrp.dll sources | 68 entries, helpers included | yes | link map, name search | full | |
| kmrp-controller.dll sources | 43 files | yes | link map, reachability walk | structure of the two largest files; about a third read line by line in pass 1, input and HUD paths in pass 2 | Pazaak, class selection, galaxy map logic sampled |
| C helpers shared with the Mac | 12 | yes | read whole except `kmrp-guiblend.c` past line 560 | high | |
| Installers | 24 + 14 files | yes | failure paths traced | high | nothing reproduced |
| Tools and build | all of `tools/`, root scripts | yes | traced from the build | medium | `logs/` writer |
| Tests | 58 + `testing/controller` | yes | reach mapped, not run | high | Mac tests not run |
| Documents | `docs/`, `reverse-engineering/` | set-level | names and paths checked, a sample read | medium | line by line not done |
| macOS | `macos/`, handoffs | yes | measured duplication | medium | nothing run on a Mac |

**Gaps in the inventory itself** (found by checking it against the builds; `tools/list_kmrp_changes.py`
should cover them):

| Missing from `cleanup-audit-1.6.md` | Why it matters |
| --- | --- |
| 11 files of `macos/tools` compiled into the modules, and `vendor/K1XboxControlsXInput.h` | shipped code outside the list |
| `build/native-runtime/NativeEngine.generated.h` (247 KB) and the two assets headers | generated, compiled in |
| 15 exports that are not hooks; 14 names cross modules through `GetProcAddress` | a run-time interface nothing documents |
| Vtable slots `0x00752E68` (normal play) and `0x00758054` (debug level 2), `K1ClassModelTrace.h` | run-time writes section 3 misses |
| `K1KpmApplier.cpp` shown in neither module | it is in kmrp.dll by `#include` |
| Installers, tools, tests | the list covers none of them |

Three errors in the generated list: rows 1, 5, 10 and 25 of section 1.2 carry a legacy hook's
comment; `K1RuntimeLayout.cpp:266-267` should be `:620-621`; the audit's own count "89 and 57" is
87 and 59, of which 85 runs are applied (79 with `original-movie-mode`).

## 3. Findings register

IDs: **MEM** memory and hooks, **THR** threads and cost, **GFX** rendering and third parties,
**GUI** layout, text, mod files, **PAD** controller, **INS** installers, **TST** tests, **MAC**
portability. State for all: **open** unless stated. Each entry gives where, what happens, trigger,
severity with likelihood, status, fix, and verification. "Mac" says whether the Mac is affected.

### 3.1 High

**INS-01 Every upgrade replaces swkotor.ini with the copy from the first install.**
`KpmEdition.cs:463,644`, `InstallCore.cs:1111-1133,1141-1149`. An install over KMRP runs `Restore`,
which writes the whole backup back; `Configure` then changes only size and rate keys. Sound, game
and graphics options are lost, and so are KMRP's own Text, Icon and HUD settings, which live in
that file. A chosen resolution returns to the display's. Likelihood certain on any upgrade.
Confirmed (lead reviewer read both). Fix: record the keys written and their old values, restore only
those still holding KMRP's value, skip the INI on an upgrade, delete the backup after a restore.
Verify: a changed INI through upgrade and restore, key by key. Linux same; Mac already correct.

**INS-02 Reinstall after KPM's Apply is refused by KMRP's own art pack.** `KpmEdition.cs:463,625-627,870,520,1463-1466`.
`IsRuntimeRecord` filters every `patches\` row, including the pack, so the manifest is gone and the
pack is then refused as foreign. The state left is the worst one, and it repeats. Medium, KPM users.
Confirmed by reading. Fix: never filter the pack row. Verify: takeover fixture (no present test has one).
Linux same.

**INS-03 No record exists while an install runs.** `KpmEdition.cs:521,1156-1158,423-428,883-901`.
The manifest is written last. A kill leaves an unrecorded runtime and perhaps a renamed
`binkw32.dll`; the next run takes it for KPM's. Low. Confirmed. Fix: write the manifest first with an
`incomplete` row, by temp file and rename. Verify: stop a test build at each step. Linux same; Mac writes first.

**INS-04 Rollback is not real for a partial write.** `KpmEdition.cs:523-538,1454-1455,1471-1474`,
`KmrpPatcher.cs:4854`, `MainWindow.cs:949`. A failed write stays; rollback steps have no try, so one
failure skips the rest; the window still says nothing was left. Disk full leaves a partial pack that
every later install refuses. Low to medium. Confirmed for the pack path. Fix: temp, verify, rename,
record; each rollback step in its own try; report what was left. Verify: small volume. Linux same.

**PAD-1 Y and B press handlers that refuse the press (issues 88, 90).** `K1NativeJoystick.cpp:3077-3089`,
called at `:2905,:2909`. `PressHudButtonK1` calls `0x0068B050` and `0x0068B0A0` directly. Both begin by
testing `[button+0x4C]` and exit if it is 0 (read by the lead reviewer). Only
`CSWGuiControl::HandleInputEvent` sets it (`0x004187AE`), and the constructor does not (reconstruction,
`gui_control.cpp:421`). The HUD comes from a plain `operator new`, so the result is whatever the heap
held, for that HUD's life. A mouse click sets it, and the Xbox HUD parks Clear All off screen. The function
returns true even when declined. Likelihood high. Code path confirmed; that it explains the reports
is strongly suspected, as the live value is unmeasured. Fix: press through vtable `+0x3C` with
`(0x27, 1)`, as the Mac does (`hud.cpp:175-180`). Verify: a debug line printing the field; pad only after
a fresh launch; one mouse click on Clear should cure it. Windows only.

**PAD-2 D-pad Up, Down and X on a slot are dead after A.** `vendor/K1XboxControls.cpp:5698-5700,5784-5788`.
Five handlers test `[slot+0x4C]` (read by the lead reviewer); A's release sets it to 0, so cycling
declines until focus leaves and returns. Likelihood high. Confirmed by reading. Fix: one press helper,
as PAD-1; check the wheel events' direction. Verify: A, release, Up, in combat. Windows only.

**PAD-4 A bark bubble takes the action bar away (issue 87).** `vendor/K1XboxControls.cpp:1383-1416,615-621`.
Any panel above the HUD but one vtable means "HUD not active". `CSWGuiBarkBubble` (`0x00755C60`) is
such a panel, not modal. While it shows, the D-pad is dropped, A attacks and B disengages. `a7f4224`
fixed the drawing only. Likelihood high in mods that bark in combat. Confirmed by reading; that BOS:SR's box is
this one is strongly suspected. Fix: treat the vtable as passive. Verify: a script barking in a fight.
Mac unchecked.

**GUI-1 A cyclic .gui crashes the game at start.** `kmrp-guiadapt.c:1138,1145,1163`. `ll_clone_field` and
`ll_clone_struct` recurse with no depth limit (read by the lead reviewer). Reached from Override's
screens through the cue templates, by both modules. Low: malformed or hostile files. Confirmed. Fix: depth 12
and a structure cap, as `K1PartyRosterGui.cpp:141`. Verify: self-referencing fixture in
`Test-ModCompatibility`. Mac and Linux same.

**GUI-2 K1TextRows cancels the Icon Size slider on skill rows.** `K1TextRows.cpp:180-188`,
`K1RuntimeLayout.cpp:582-595`. Two owners of the third icon part (`+0x29C`). With the slider moved in session,
or Text Size above 50%, skill icons follow the wrong rule until restart. Medium. Confirmed by reading; not run.
The slider was seen working in the maintainer's game, at settings not recorded. Fix: one owner, and a decision
on how Text and Icon sizes combine. Verify: Abilities at Text 50 and 100, slider 25, 50, 75.

**THR-2 A failed preparation repeats all its work, on every lookup or frame.** `K1RuntimeAssets.cpp:1724-1738`,
`K1ControllerStandalone.cpp:372-394,244-248,175-196`, `vendor/K1XboxControls.cpp:2288-2308,2676-2686`. No failure latch.
A full disk, or a user name outside the code page with no short names, repeats fonts, 73 layouts and the
adapters per `GetKeyEntry`, leaving a new folder each try. The controller's copy of folder registration
lacks KMRP's 2026-10-30 fix (`K1ControllerStandalone.cpp:201,209,231`), so such a user hits this
whenever the controller patch runs alone. Low, but the game is unusable at start for those affected.
Confirmed by reading. Fix: one latch per module, retry on a new size, one shared `K1ResourceFolder.h`.
Verify: read-only cache, non-code-page path, missing pack; count hook work.

**GFX-01 The game paints a fixed 1600x1200 black rectangle on the screen.** Game `0x00401A30`. The thread registers
class `KotorCin` (`0x0073D634`) and creates "Knights Cinematic Backdrop" (`0x0073D610`); the window
procedure `0x00401590` returns 0 for everything, so creation fails either way. `GetDC(NULL)` then gives
the screen, and `PatBlt(0,0,1600,1200,BLACKNESS)` runs (all read by the lead reviewer). Vanilla then changed mode;
KMRP rebuilds at the same mode, so nothing repaints. The block is 83% of a 1080p screen, 46% of 3440x1440.
Strongly suspected as the cause of issues 91 and 39; the maintainer's RTX 3080 does not show it, and what decides
visibility is not established. Fix: measure the block in issue 39's screenshot first, then a recipe run making
`je 0x00401B09` a `jmp`, after checking nothing relies on the curtain. Windows, perhaps Proton.

**TST-01 No test is run by anything.** CI byte-compiles `tools/` and checks links; `build_kmrp.ps1` runs no test;
`testing/README.md` lists 26 of 58. Breakage stood for days seven times. Confirmed. Fix: a tracked list and a
runner, fast group at the end of the build. Verify: break a harness on purpose.

**TST-02 Test-GuiAudit cannot fail, and measures files Windows no longer loads.** `Test-GuiAudit.py:829-833,759`.
Exit 1 on every run since 2026-10-02. The sets now hold 10 `.gui` files per size; 73 screens are made at run
time and the HUD by `K1PcHud.cpp`. Fix: run `measurements()` on Live Layout's output with a reviewed baseline.
It stays valid for the Mac until handoff item 102.

**GFX-04 No check that the copy to the window worked, and no off switch (conditional High).**
`K1OffscreenFrame.cpp:336-345`. `Show` never tests the blit; a multisampled blit into the default framebuffer has
run only on NVIDIA, and the option was removed. If a driver refuses it the screen stays black, with no way
out for the player. Failure theoretical; missing check confirmed. Fix: `glGetError` after the first `Show`, then
`Refuse`, plus a hand-set ini key. Verify: AMD and Intel, AA 0, 4, 8.

### 3.2 Medium

| ID | Where | What | Status | Fix | Mac |
| --- | --- | --- | --- | --- | --- |
| INS-05 | `KpmEdition.cs:1781-1804,605,653-656` | A damaged record gives false success or blocks forever | confirmed | require header and version row; keep manifest until done | no |
| INS-06 | no process check; `KpmEdition.cs:1507,823` | No running-game, second-installer or rights check; raw "Access denied" | confirmed | one preflight, per-folder lock, `FileGuard.Delete` | has it |
| INS-07 | `KpmEdition.cs:238-242,309-315` | After Steam Verify the window says patched; no repair | confirmed | compare rows to disk, offer Repair | n/a |
| INS-08 | `KpmEdition.cs:638-640,1339-1340` | Restore can report success with `binkw32.dll` missing | confirmed | check before removing the proxy, warn | no |
| PAD-3 | `K1NativeJoystick.cpp:1509,1777-1783,2868` | A on a focused slot may activate twice | strongly suspected | measure queue length, then one path | unchecked |
| PAD-5 | `K1NativeJoystick.cpp:7200-7213,2856-2859` | D-pad in menus moves the action bar later | confirmed by reading | test class PC when raising | unchecked |
| PAD-6 | `K1NativeJoystick.cpp:1013-1021` | Input rebuild replays held buttons, can swallow a release | strongly suspected | seed `lastButtons`, clear `remapSuppressed` | unchecked |
| GUI-3 | `K1RuntimeLayout.cpp:823-882`, `K1RuntimeResolution.cpp:329` | One odd layout aborts a mode change half done, then retries each frame | confirmed by reading | skip the bad control, compute before mutating | port |
| GUI-4 | `K1TextLayout.cpp:432-465`, `K1RuntimeLayout.cpp:859-871` | Container's widening read as the engine's at a size change | strongly suspected | expose the grow | port |
| GUI-5 | `K1RuntimeAssets.cpp:1624-1654` | A failed art helper is sealed into a complete set | strongly suspected | fill returns false except "absent" | if copied |
| GUI-8 | `kmrp-guiadapt.c:785-855` | "Exactly as its author left it" is false for third-party scaled files | confirmed by reading | decide rule; guard steps or correct the document | yes |
| THR-1 | `K1HudOptions.cpp:874,880-906`, `K1NativeJoystick.cpp:2472-2481` | KMRP alone never preloads HUD textures. **Not at a movie hook**: no GL context there | confirmed | call from `KmrpCoreGuiWorkK1`, drop the export | own path |
| THR-3 | `vendor/K1XboxControls.cpp:2204-2207`, `K1RuntimeAssets.cpp:1790-1812` | `bad_alloc` on background threads ends the game | path confirmed | try/catch per job | shared idea |
| THR-4 | `K1RuntimeAssets.cpp:1743-1751,1790-1800` | Game thread blocks on the build lock for a known size | confirmed by reading | small lock for `known` | no |
| THR-5 | `vendor/K1XboxControls.cpp:2744-2784,2314` | Picture sweep linear per border per frame, lists only grow; estimate 0.4 to 2 ms. Includes GFX-07 | confirmed, cost estimated | hash maps, skip unchanged | if ported |
| THR-6 | `K1TextLayout.cpp:936-973,714-769,615`, `K1TextRows.cpp:201-324` | Text work on every panel each frame; `artPlaces` never shrinks; estimate 0.2 to 1 ms | leak confirmed | visible filter, erase | if ported |
| THR-8 | `K1RuntimeAssets.cpp:387-388,1544-1547,536-550` | One cache for all game folders: rebuilds, and a live set can be deleted | confirmed by reading | key sets by stamp hash | check |
| GFX-02 | `K1OffscreenFrame.cpp:371-377` | Hot patch live before `real` is set | confirmed path, very low | set `real` first | no |
| GFX-03 | `K1OffscreenFrame.cpp:21-24,117,317` | K1DC wraps KMRP at SwapBuffers, the reverse of the docs | strongly suspected | correct docs; test brightness with AA 8 | no |
| MEM-01 | `K1EngineMemory.h:37-41`, `K1NativeJoystick.cpp:969` | Pointer ceiling below what a large-address game can hand out | strongly suspected | ceiling `0xFFFF0000` in one helper | no |
| TST-03 | `Test-GuiAudit.py:257-259` | Badge skip lost coverage; run-time rule untested | confirmed | `Test-BadgeShape` over 144 rows | yes |
| TST-05 | `Test-RuntimeResolution.cpp`, `K1RuntimeResolution.cpp:305-310` | Tests nothing shipped; a rebuild would not help | confirmed | new harness on today's source, then remove the preview | unknown |
| TST-06 | `K1RuntimeEngine.cpp:42-73`, `build_native_engine.py:33-65` | `FieldValue` has no test; the checked one is the C# twin | confirmed gap, no wrong value shown | `Test-EngineFields` | reference |
| TST-07 | `e2e_native_controller.py:45-47` and 10 more | The live controller suite cannot run | confirmed | one shared config | no |
| MAC-2 to MAC-6, MAC-8 | section 7 | Portability blockers | confirmed, MAC-4 suspected | section 7 | yes |

**Structure, Medium** (first pass; none changes behaviour):

| ID | What | Evidence | Fix |
| --- | --- | --- | --- |
| S-1 | `K1NativeJoystick.cpp`, 8,455 lines, over 20 jobs; `g_stick` 112 fields | map in the controller review | split in nine ordered steps, steps 1 to 7 moving code only |
| S-2 | `vendor/K1XboxControls.cpp`: 2,030 dead lines; six live jobs; `vendor/K1XboxControlsXInput.cpp`: 411 dead; 86% of live lines are KMRP's | map, link map, reachability walk | remove the keystroke path, split, retire the name `vendor/`, keep the credit |
| S-3 | `K1XboxHud.cpp`: `KmrpXboxHudK1` 482 lines, 7 jobs; `KmrpXboxHudBarsK1` 160 | 23 steps listed | name the steps, same order |
| S-4 | `K1RuntimeAssets.cpp` 8 jobs; `K1TextLayout.cpp`; `K1RuntimeLayout.cpp`; `K1ControllerLayout.cpp`; `K1KpmApplier.cpp` | maps | split along MAC-6 for assets |
| S-5 | Installer: `KmrpPatcher.cs`, `InstallCore.cs`, `KpmEdition.cs`; about 3,100 reference lines; source list written six times | maps | `core/` and `windows/`; reference code to tests |
| S-6 | Options page toolkit twice (`K1HudOptions.cpp`, `K1TextOptions.cpp`, 150 lines each) | line table | `K1OptionsPage.h`, keeping the harness's `Fn` seam |
| S-7 | Xbox `Piece` and `Placed` three times (Windows twice, Mac once); no test compares them. **Not documented as deliberate** | `K1HudOptions.cpp:83-84` | types header, the caller's table, shared arithmetic |
| S-8 | `keyed_resource` three copies; `resize` two; `Utf8Path` three; temp cleanup two; half-even rounding three; one Rect six times; SetExtent by hand eight times; five font readers; 21 addresses named more than once; 117 hand-written prototypes | reviews | one small shared header each, in the order of section 6 |
| S-9 | Hook tables in three places; 7 legacy rows; `exports.def`, `select_controller_path.py`, the `no-controller` kind | controller and input reviews | one table per patch |
| S-10 | Build cache hashes all of `tools/`: 80 of 136 files outside the build can trigger the slow steps | build review | fingerprint what the build reaches |

### 3.3 Low

| ID | Where | What | Status |
| --- | --- | --- | --- |
| PAD-7 | `K1NativeJoystick.cpp:2469` | Motors may hold through a movie | suspected |
| PAD-8 | `K1Rumble.cpp:872,949-952` | Stale saber hum after a load | suspected |
| GUI-6 | `K1TextLayout.cpp:646-648,796` | Picture references never released | confirmed |
| GUI-7 | `kmrp-gameart.c:462-467` | Weakest key reader; at set build, not every start | confirmed |
| GUI-9 | `vendor/K1XboxControls.cpp:3221-3248` | Badge signature ignores scale | suspected |
| GUI-10 | `K1RuntimeAssets.cpp:995,1719-1721` | "Override's font" logged for KMRP's own fonts | confirmed |
| GUI-11 | `kmrp-gameart.c:290-342` | Unchecked allocation on a large image | confirmed |
| GUI-12 | `kmrp-swoophud.c:161-208` | `size_t` wrap on 32-bit | theoretical |
| INS-09 | `InstallCore.cs:1597,1617` | v1.0.0 Override restore cannot resume | confirmed |
| INS-10 | `InstallPlatform.Linux.cs` | Linux restore does less | confirmed |
| THR-7 | `K1ControllerPreload.cpp:77-92,153-159` | 64 KB cleared and a file query per frame | confirmed, cost estimated |
| THR-9 | `kmrp-swoophud.c:80,232` | `SHIFT` outside the build lock | theoretical |
| THR-10 | `K1NativeJoystick.cpp:2638` | Sampler and applier can suspend each other, debug only | theoretical |
| GFX-05 | `K1OffscreenFrame.cpp:350-360` | `drawnOffscreen` ignores the binding | confirmed by reading |
| GFX-06 | `K1OffscreenFrame.cpp:199` | Every read resolves the whole frame | cost unmeasured |
| MEM-02 | `K1NativeJoystick.cpp:2901,7728` | `hudInterface` can outlive the HUD, one frame | confirmed stale read |
| MEM-03 | `KmrpOptions.h:32-87`, others | `_s` failure branches cannot run; game folder over about 220 characters ends the process | confirmed from code |
| MEM-04 | KPM `patcher.cpp:66-79` | 74 detours written with the game running on Steam | theoretical, upstream |
| MEM-05 | `K1KpmApplier.cpp:590-598` | Rollback omits the run that failed read-back | theoretical |
| TST-04 | `Test-ControllerPromptAssets.py:163-174` | Six hints bake width 0; badge up to 28 px from its caption with the controller patch alone | confirmed, cosmetic |
| TST-08 | several | Frozen `.diff`, harness compiling a shipped-nowhere configuration, stale comments, cache key | confirmed |
| MAC-1, MAC-7 | section 7 | Submodule pin, 32-bit address in a parameter | confirmed |
| E-1 | runs `0x0045A850`, `0x004A1770` | Multiply font metrics by 1.0 each text draw; removal also removes the one RWX page | proven |
| E-2 | run `0x00755788` | Float nobody reads (five readers all overwritten; lead reviewer checked each) | proven |
| E-3 | `K1KpmApplier.cpp` | Installers' file format still parsed; about 250 lines dead | proven for what is dead |
| R-1 | `K1NativeJoystick.cpp:2014-2153` | Rumble table never read: the play hook always takes its exit | proven by the review, to confirm by build |
| DOC | the reviews | Stale or wrong statements in documents and comments, listed by file and line in each review | confirmed |

## 4. Interactions across modules

| Interaction | State |
| --- | --- |
| kmrp.dll and kmrp-controller.dll | 14 names by `GetProcAddress`; all 13 pairs read match; every user tests for null. **No version handshake:** a changed meaning under one name would pass. Add one with `KmrpPeer.h` |
| Hooks of both patches at shared functions | Touching sites `0x00407230/35`, `0x0040CE70/76` are safe by KPM's one-patch-per-address rule. Duplicate work: status summary laid out twice a frame, documented |
| Text scale and badges | KMRP's fit changes `+0x40`; the controller measures from it (GUI-9). With KMRP absent, badges read the string's own fields: safe |
| Icon Size, Text Size, row hooks | Two owners (GUI-2) |
| Live Layout, re-layout, Container | GUI-3, GUI-4 |
| Recipe and hooks | No run duplicates a hook; `0x005F0C64` is left out of the applied runs |
| Movie thread and game thread | No engine or GL call on the movie thread today. Any new call there must not reach `Bind` (THR-1) |
| KMRP and K1DC | K1DC wraps KMRP at SwapBuffers (GFX-03); the mipmap fix depends on K1DC's ATI answer; `wglMakeCurrent` patch may exist only for K1DC. The bundled route has not been seen with the offscreen frame: the Steam test folder runs the standalone route |
| High FPS Fixes | `frameTime 0` guarded; rumble on engine dt; frame-counted logic harmless. Issue 78 had it on by the old automatic rule, so test with it off |
| Art pack and installers | INS-02 |
| Two game folders | THR-8 |
| Shared C with the Mac | Generated files must stay in step (section 7) |

## 5. Verified safe: keep unchanged

These looked suspicious and were checked. **Do not change them for style.**

- **KPM contract:** registers, flags and FPU saved before anything writes flags. Lead `0x0040C1F6` closed.
- **74 sites:** stolen bytes equal the executable, 7 apparent jumps into them are not real, consumed exits balanced.
- **ABI:** 123 engine calls checked, 0 real mismatches.
- **Lifetimes:** `g_popup` is a global panel, not a use after free; cue tables, panels, strings and controls are cleared by base destructors; `keyboardPanel` found in the list before use.
- **The strings map:** one constructor, one destructor, one vtable; every object seen.
- **Buffers:** all 23 unbounded string calls are safe by length. Xpress, asset pack and GFF readers check every offset.
- **Applier:** guards before any write; no heap while threads are stopped; `CommitEngineAt` rolls back.
- **Locks:** consistent order, none held across an engine call.
- **Parsers:** every GFF reader in the start path is bounded except the clone recursion (GUI-1); TGA, TPC and 2DA hold.
- **Merge:** never writes Override, a row never moves, unsafe merges fall back to the mod's file.
- **Cache writes:** temp names, atomic rename, `.complete`, SHA-256 on decode. Crash and full disk are safe there.
- **Installers:** every delete checks ownership; saves untouched; Override touched only by the 1.0 path; unknown hashes refused first; no zip slip; the update check downloads and runs nothing.
- **Things that look like duplicates and are not:** `FitMessageBoxK1` against the popup operands, `KmrpListRowK1` against the gutter runs, `KmrpTextStringWrapK1` against the wrap runs, `K1PcHud` against the minimap runs, `0x0040BE70` against `0x005F18F6` (F10), every pair of rumble hooks, `0x0040CFAB` against `0x0040CF70`, `FindK1MenuPanel` against `FindK1TitleMenuPanel`, `K1PartyRosterGui`'s GFF against the small readers.
- **Keep for the Mac though unused on Windows:** `CARRY_DRAWN`, `CARRY_CUED`, `--controller-art`, `--mac`, `pack_resolution_layouts.py`, `kmr?rt_pause`, `K1OptionsPad.h`, `src/patcher/brand.png`, `icons/`.

## 6. Remediation plan

Small steps, each with a baseline, a focused check, and a separate commit. Function comparison as in F4
where code only moves. **Risk** is regression risk. Decisions needed from the maintainer are in section 9.

| Batch | Contents | Risk | Proof |
| --- | --- | --- | --- |
| **0 Safety net** | Test runner (TST-01); `Test-EngineFields`; `Test-ResolutionGate`; correct the inventory tool | none to the game | a deliberately broken harness fails |
| **1 Corrections with no behaviour change** | Comments and documents; dead code with proven reach (kmrp P2, P3 dead parts; S-2's keystroke path; R-1; E-1, E-2); always-true guards | low | function compare, both test sets, one game start |
| **2 Player-facing fixes** | INS-01 to INS-04, INS-08; PAD-1, PAD-2, PAD-4, PAD-5; GUI-1; THR-1, THR-2 with `K1ResourceFolder.h`; MEM-01, MEM-02, MEM-03 | medium, each in its own commit | pad play by the maintainer; install tests (warn first); fixtures |
| **3 Investigations that need a run** | PAD-1's field value; PAD-3 queue count; GFX-01 screenshot; GFX-03 brightness; engine P8 and P9; pause hook P5 | none | measurements decide the fix |
| **4 Medium fixes** | GUI-2 to GUI-5, GUI-8; THR-3 to THR-8; GFX-02, GFX-04, GFX-05; INS-05 to INS-07 | medium | focused tests, AMD and Intel for GFX-04 |
| **5 Shared code before the port** | `kmrp-keyed.h`, `kmrp-image.h`, `K1EngineScale.h`, HUD table, Rect, address names, MAC-2, MAC-3, MAC-4, MAC-5, MAC-7 | low to medium | byte output held by the existing tests |
| **6 Splits** | S-1, S-2, S-3, S-4, S-5, S-6, S-9, S-10 | medium: text-reading tools must move with them | compare; tests; play for steps that change shapes |
| **7 Validation** | The checks of section 8 on Windows, then the Mac port | n/a | issue 83 |

Fixes before splits, because a split moves the text a fix changes. Name split files after the Mac's where
possible (`native`, `gameplay`, `gui`, `cues`, `prompts`, `overlays`, `hud`, `layout`). Do not split
`kmrp-guiadapt.c` into new `.c` files before the Mac calls live layout: that breaks `macos/build.sh:112-113`.

## 7. macOS portability

The Mac game is x86_64 Mach-O, SysV ABI, under Rosetta on Apple Silicon. Offsets do not scale, `ret N` does not
exist there, and files are little-endian on both. The "pending Mac PR" is gone: no PR, no branch.

| ID | Sev | Blocker | Fix |
| --- | --- | --- | --- |
| MAC-1 | Low | Submodule pin `2a784bf` cannot build the package; `build.sh` header says otherwise | move the pin past `7546ae5` |
| MAC-2 | Medium | `_stricmp` in `K1ButtonRemapPolicy.h:56` | local ASCII compare |
| MAC-3 | Medium | `K1HudOptionsPolicy.h:72-82` keys on Windows offsets: sliders silently ignored | `element` column generated into both tables |
| MAC-4 | Medium | `kmrp-guiadapt.c:450-466,478` lacks `FP_CONTRACT OFF`; arm64 tests are not the shipped arithmetic | add the pragma, test both slices |
| MAC-5 | Medium | `make_controller_assets.py:84,87` assigns module globals: a rename empties the Mac bank silently. 14 cross-module names; `dlsym(RTLD_DEFAULT)` finds nothing on the Mac | arguments; one `KmrpPeer.h` |
| MAC-6 | Medium | `K1RuntimeAssets.cpp:1148-1440` binds format logic to wide paths; issue 81 asks for one rule set | UTF-8 pipeline over a 6-function file layer |
| MAC-7 | Low | `K1TextOptions.cpp:31,62` truncates addresses | `uintptr_t` |
| MAC-8 | Medium | Mac prompt tables have no generator; 42 tables against 47 | one table generating both |

**Sharing measured:** 7,610 Mac code lines against Windows, 2,340 the same (31%). About 1,230 lift by matching runs
(16%), at most about 1,580. First lift: `K1Rumble.cpp:49-321,812-862`, 253 lines identical. Portable headers add
about 1,590 lines the Mac would otherwise re-port; `K1RuntimeAssets` about 400 after MAC-6.

**Findings that help the port most:** S-8's names and Rect, S-7, `kmrp-keyed.h`, `K1EngineScale.h`, and INS-01 to INS-08
as rules, since `kmrp-mac.sh` is a separate copy that already has what Windows lacks. Handoff items 56, 59, 60, 64,
67, 76, 87, 99, 102, 112, 126 and 130 are stale or wrong; each needs its correction in
`docs/macos-handoff-1.5-to-1.6.md`. Generated files that must stay in step: `xbox_hud_layout.inc`,
`K1ControllerBadgeShapes.inc`, `gui-blend.bin`, `K1ListRows.inc` and `list_rows.inc`.

## 8. Verification report

**Run in this audit:** none of the 58 tests after `2194acf`. Before that, on 2026-11-01: 22 regression tests against
`908a4fa`'s tree, 19 passing with the three now repaired (`6741836`), and the full build. The reviews ran read-only
scans of source, the clean executable and logs.

**Requires gameplay or hardware, not done:**

| Check | Needs |
| --- | --- |
| PAD-1, PAD-2, PAD-3, PAD-4 | pad in combat |
| GUI-2, GUI-4 | Abilities and containers at several settings |
| GFX-01 | issue 39's screenshot; an affected player |
| GFX-03, GFX-04, GFX-05 | K1DC with AA 8; AMD, Intel |
| Bundled K1DC route with the offscreen frame | a Windows install from a 1.6 installer |
| F5 | Party Roster Limit 32 |
| Windows keyboard repair (F13) | physical keyboard |
| Engine P8, P9 | Steam, debug counters, an ini with an absent size |
| Everything on Proton, Windows 7 and 8 | those systems |
| Mac | a Mac |

**Assessment of remaining technical debt.** The engine layer is in good shape: hooks are few for what they do,
and precise. The debt is in the layers above. Two large controller files, one of them a third dead; helpers written
several times; installer failure handling that assumes success; a test suite with real strength in places, no
runner and no reach into the code that runs most. The documents are a strength in depth but lag the code in many
places, mostly from the two-patch split, F1 and the removal of the four-patch edition.

## 9. Decisions for the maintainer

| # | Question | Default if not told otherwise |
| --- | --- | --- |
| 1 | Remove the keystroke path? A 2026-09-06 comment asks to keep its design; git keeps it | remove |
| 2 | F9: correct the documents, or restore the toggle? | correct the documents |
| 3 | `--apply` and `ResolutionPatch`: remove after `Test-EngineFields` (2,030 lines), or keep? It costs two tests and one `AGENTS.md` line | remove |
| 4 | Text and Icon sizes on skill rows: how should they combine (GUI-2)? | Icon Size owns the icon |
| 5 | "Exactly as its author left it" (GUI-8): guard the steps, or change the rule? | guard the steps |
| 6 | Add the six hints' wording (TST-04)? Moves badges only with the controller patch alone | yes |
| 7 | Retire the name `vendor/`, and how the credit reads | retire, credit kept |
| 8 | The 3440 compare at `0x0068C4E3` | leave until the two files are compared |
