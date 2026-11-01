# The KMRP 1.6 audit: where every finding stands

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md).

**Kind: working record, reconciled against the code, 2026-11-01.** It gives each finding of the
[audit report](cleanup-audit-1.6-report.md) one status. A status was given by reading the code as it
stands and the test named, not from a commit's message. The report keeps the findings' detail;
this says what became of them. What only a game can check is in the
[gameplay checklist](gameplay-checklist-1.6.md).

| Status | Means |
| --- | --- |
| **Tested** | fixed, and an automated test that fails without the fix passes |
| **In-game** | fixed, passes whatever can be checked here, and needs the game to confirm it |
| **Open** | confirmed and not fixed |
| **Disproven** | the finding was wrong |
| **Kept** | intentional: left as it is, on evidence |
| **Deferred** | not done now, with the reason |

"Commit" names the fix. A test named under **Tested** was proved able to fail where the row says so;
tests from before this cycle were not all re-proved.

## High

| ID | What | Status | Commit | Evidence, and what remains |
| --- | --- | --- | --- | --- |
| INS-01 | An upgrade reset `swkotor.ini` | Tested | `96bf347`, `b0feedc` | Test-InstallerPatch cases 4, 12, 14. Real folder on the checklist |
| INS-02 | KPM takeover refused by the art pack | Tested | `b0feedc` | Case 13, fails on the old installer |
| INS-03 | No record during an install | Tested | `b0feedc`, `df3360e` | Case 17, kills at fifteen moments. The first fix had a gap the test then found: File.Replace |
| INS-04 | Rollback not real | Tested | `b0feedc` | Cases 15, 16. Not tried on a really full disk |
| PAD-1 | Y and B refused the press | In-game | `2a83b64` | Test-HudPress holds the source and the handlers' test of `+0x4C`. The live value was never measured |
| PAD-2 | D-pad and X dead after A | In-game | `2a83b64` | Test-HudPress. Needs a pad in combat |
| PAD-4 | A bark bubble takes the bar (issue 87) | In-game | `2a83b64` | Test-HudPress. That BOS:SR's box is this one is still only suspected |
| GUI-1 | Cyclic `.gui` crashes at start | Tested | `75c1ed6` | Test-ModCompatibility harness: old code ends in a stack overflow |
| GUI-2 | Two owners of the skill icon (decision 4) | In-game | `8061ac1` | Test-TextRows skill row, fails without the fix. Abilities at several settings on the checklist |
| THR-2 | A failed preparation repeats forever | In-game | `4ef6081` | Test-ResourceFolder. Read-only cache and a non-code-page path not run in a game |
| GFX-01 | The game's 1600x1200 black fill | Open | | Code path confirmed, link to issues 39 and 91 not. Needs issue 39's screenshot or an affected player. No change made without that |
| TST-01 | Nothing runs the tests | Tested | `5007618`, this cycle | `run_regression.py`, every test listed; `build_kmrp.ps1 -Test`. CI still runs links and byte-compile only: it has no game files |
| TST-02 | GUI audit cannot fail, measures unused files | Tested | `a88ab3a` | Measures Live Layout output; baseline of 1,317 groups; a faked new or worse group fails it. 243 groups still unreviewed |
| GFX-04 | No check of the copy, no off switch | In-game | `397129c` | Test-OffscreenFrame against a stand-in driver. AMD, Intel and Proton unknown |

## Medium

| ID | What | Status | Commit | Evidence, and what remains |
| --- | --- | --- | --- | --- |
| INS-05 | Damaged record | Tested | `cf60ec7` | Case 18. No automatic way back: the message says what to do |
| INS-06 | No running-game, second-installer or rights check | Tested | `cf60ec7`, `df3360e` | Case 21 on Windows. Linux's check not run on Linux |
| INS-07 | Status after Steam's Verify | Tested | `cf60ec7` | Case 20. The window's Repair on the checklist |
| INS-08 | Restore reports success with files missing | Tested | `cf60ec7` | Case 19. Departs from the audit's "check before removing the proxy": left, the next install would move it aside as the game's |
| PAD-3 | A on a slot may activate twice | Open | | Needs measuring in a game. No change without it |
| PAD-5 | D-pad in menus moves the bar later | In-game | `2a83b64` | Test-HudPress |
| PAD-6 | Input rebuild replays held buttons | In-game | `53ce379` | No test: needs the game's input object |
| GUI-3 | One odd layout stops a size change | Tested | `8061ac1` | Test-RuntimeRelayout, on the shipped file, fails with the old `return false` |
| GUI-4 | Container's widening read as the engine's | In-game | this cycle | Reproduced on the shipped file, not only by reading: Test-RuntimeRelayout and Test-NativeTextLayout's Container case, each fails with its half taken out. The real Container across a size change on the checklist |
| GUI-5 | Failed art helper sealed in | Tested | `f29e522` | Test-AssetPrepare case 10 |
| GUI-8 | "Exactly as its author left it" (decision 5) | Tested | `e8ea7b4` | Test-ModCompatibility, fails without the fix. A real mod's screen on the checklist |
| THR-1 | KMRP alone never preloads the HUD page | In-game | `53ce379` | No test: needs a GL context |
| THR-3 | Exceptions on background threads | In-game | `75c1ed6` | By reading; `bad_alloc` not provoked |
| THR-4 | Game thread waits on the build lock | In-game | `5576e8b` | By reading; no test of the timing |
| THR-5 | Picture sweep per border per frame (GFX-07 with it) | In-game | this cycle | Measured with the built file's 136 glyphs and 172 pictures: one border's lookups 4.6 to 14.9 us walked, 0.26 us hashed, whatever the session's length. Test-PictureKey holds the new key to the old comparison on 400,005 pairs and fails when broken. The audit's "skip unchanged" is not needed after this. The module grew 8 KB. Pictures in a game on the checklist |
| THR-6 | Text work on every panel each frame | Kept | this cycle | The leak is fixed: `artPlaces` rows now go with their control, by reading, as no harness reaches them. The visible filter is not done, on evidence: an unchanged list costs 0.2 us a row (60 us for 300 rows, timed on the shipped code), far under the 0.2 to 1 ms estimated, while a filter by the manager's lists could stop preparing a panel drawn inside another, with no way to see that here |
| THR-8 | One cache for all game folders | Tested | `5576e8b` | Test-AssetPrepare case 11 |
| GFX-02 | Hot patch live before `real` | In-game | `75c1ed6` | By reading; the race is too narrow to provoke |
| GFX-03 | K1DC wraps KMRP at SwapBuffers | In-game | this cycle | Confirmed from K1DC's source: KMRP takes the slot in `DllMain`, K1DC at the end of `InitExtensions`, so K1DC is outermost. Documents and two comments corrected. By reading the code is right in both orders. Brightness with AA 8 on the checklist |
| MEM-01 | Pointer ceiling below 4 GB | In-game | `75c1ed6` | By reading; needs a large-address game past 2 GB |
| TST-03 | Badge skip lost coverage | Tested | `0f4eb22` | Test-BadgeShape, fails with the old 2% rule |
| TST-05 | Resolution test read a stale DLL | Tested | `cac345e` | Test-ResolutionGate. Reported size without a layout checked in source only |
| TST-06 | `FieldValue` had no test | Tested | `6c33f55` | Test-EngineFields, 4,071 values. Ten exact ties differ from the C# twin, by arithmetic |
| TST-07 | Live controller suite cannot run | In-game | `553fc67` | Paths fixed, Test-LiveSuitePaths. The scripts have not been run |
| MAC-2 to 6, 8 | Portability blockers | Deferred | | The port comes after Windows validation, as asked. Each stays in the report's section 7 |

## Structure

| ID | What | Status | Evidence, and what remains |
| --- | --- | --- | --- |
| S-1 | `K1NativeJoystick.cpp` split | Deferred | No bug hangs on it, and a split moves the text every open fix touches. Do after the Mac handoff's items are settled |
| S-2 | Keystroke path | Tested | 2,811 lines gone, `kmrp-controller.dll` byte-identical; see decision 1 |
| S-3 | `KmrpXboxHudK1` steps | Deferred | As S-1 |
| S-4 | Other large files | Deferred | MAC-6 decides `K1RuntimeAssets.cpp`'s shape |
| S-5 | Installer split | Deferred | `--apply`'s removal comes first (decision 3) |
| S-6 | Options page toolkit twice | Open | |
| S-7 | Xbox `Piece` and `Placed` three times | Deferred | The third copy is the Mac's |
| S-8 | Small helpers written several times | Open | |
| S-9 | Hook tables | Tested | Seven legacy rows gone, all 43 others proved unchanged, drift check passes |
| S-10 | Build cache hashes all of `tools/` | Tested | `a88ab3a`. 63 or 64 of 128 tools count per step; a name in a comment still counts |

## Low

| ID | What | Status | Commit | Evidence, and what remains |
| --- | --- | --- | --- | --- |
| PAD-7 | Motors may hold through a movie | Open | | Suspected; on the checklist to measure |
| PAD-8 | Stale saber hum after a load | Tested | `5576e8b` | Test-RumbleMixer |
| GUI-6 | Picture references never released | Open | | |
| GUI-7 | Weakest key reader | Tested | this cycle | Test-GameArtFailure: bad keys refused, a good one read; the old file ends in an access violation |
| GUI-9 | Badge signature ignores scale | Open | | |
| GUI-10 | "Override's font" for KMRP's own | Tested | `5576e8b` | One log line, read |
| GUI-11 | Unchecked allocation | Tested | this cycle | Test-GameArtFailure fails each of a picture's 7 allocations in turn. `add_texture`'s path has the same checks but is not run: it needs a texture pack |
| GUI-12 | `size_t` wrap on 32-bit | In-game | this cycle | Every sum of file values in `kmrp-swoophud.c` is 64-bit. By reading: the wrapped read lands in harmless memory, so no test can tell |
| INS-09 | Override restore cannot resume | Tested | `cf60ec7` | Case 19 |
| INS-10 | Linux restore does less | In-game | `cf60ec7` | Art cache removal compiled, not run on Linux. Kept: Linux sets no DPI value, and a `C:\` row is skipped on purpose |
| THR-7 | 64 KB cleared per frame | Open | | |
| THR-9 | `SHIFT` outside the lock | In-game | this cycle | The file-wide value is gone: each run's shift is in its own `Model`. By reading; Test-LiveLayout's and the build's swoop checks pass |
| THR-10 | Sampler and applier suspend each other | Open | | Debug only |
| GFX-05 | `drawnOffscreen` ignored the binding | Tested | `397129c` | Test-OffscreenFrame, fails without it |
| GFX-06 | Each read resolves the whole frame | Open | | Cost unmeasured |
| GFX-07 | Scene fills never pruned | In-game | this cycle | The list by border is gone: only its picture-to-scene answer was ever read, so one row per picture drawn. With THR-5 |
| MEM-02 | `hudInterface` outlives the HUD | In-game | `75c1ed6` | By reading |
| MEM-03 | `_s` failure branches cannot run | In-game | `75c1ed6` | By reading; a 220-character path not run |
| MEM-04 | Detours written with the game running | Kept | | KPM's, upstream. Theoretical |
| MEM-05 | Rollback omits the failed run | In-game | `75c1ed6` | By reading |
| TST-04 | Six hints bake width 0 (decision 6) | In-game | `d04ca91` | Test-ControllerPromptAssets without its exception list. Controller alone moves three badges: checklist 3b |
| TST-08 | Frozen diff, stale harness | Open | | |
| MAC-1, MAC-7 | Submodule pin, truncated address | Deferred | | With the port |
| E-1 | Font metrics multiplied by 1.0 | Open | | |
| E-2 | A float nobody reads | Open | | |
| E-3 | Dead installer format in the applier | Open | | |
| R-1 | Rumble table never read | In-game | this cycle | Scan of the game: the fields' only readers are the hooked gate, the code behind it, `UpdateRumble` for each queued instance, and the destructor, and the hook is unconditional and always declines. Test-RumbleMixer passes. One rumble in a game on the checklist |
| DOC | Stale statements | Open | | |

## The eight approved decisions

| # | Decision | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Remove the keystroke path | Tested | 72 functions and 167 names. `kmrp-controller.dll` unchanged by the second step and differing from the first only by inlining: the four functions that left the map still exist, with one caller each. Nothing else depended on it: drift check, quick group |
| 2 | Correct F9's documents | Tested | `dd1a626`. `controller-support.md` no longer offers it; check_links passes. No toggle, no new hook |
| 3 | Remove `--apply` | Tested | `dd1a626`. From the installer, not from the project: deleting the code would have lost what checks the size values, the 4 GB flag's inputs and the inventory, so it is `build/kmrp/kmrp-reference.exe`, which ships nowhere. Four tests pass against it; Test-EngineFields' baseline unchanged; 778 lines and 53 KB left the installer |
| 4 | Icon Size owns the skill icon | In-game | GUI-2 |
| 5 | Preserve mod-authored layouts | Tested | GUI-8, `e8ea7b4` |
| 6 | Add the six captions | In-game | TST-04, `d04ca91` |
| 7 | Retire `vendor/` | Tested | `4db596f`. Credit in both files' first lines and `THIRD_PARTY_NOTICES.md`, with licence, permissions and table. The move changed 174 bytes of the module: its build hash and a 12 byte shift of globals |
| 8 | Keep the 3440 compare | Kept | Compared at 3440x1440: `mipc210x7.gui` and `mipc28x6.gui` hold the same 111 controls, of which 110 differ. They are two layouts, the first hand-made for this size (a 400 wide name bar against 860, a 270 map against 120), so the compare at `0x0068C4E3` chooses a real thing. Removing it would change every 3440-wide HUD for no gain |

## F1 to F13

| ID | Status | Evidence |
| --- | --- | --- |
| F1, F5 | Tested | `80f9277`, seen working in your game |
| F2, F4, F6, F7, F8, F9 | Tested | Commits in the findings document |
| F3 | Kept | Confirm guards stay |
| F10 | Kept | Four callers found; the hook stays |
| F11 | Tested | The preview is gone (`cac345e`) |
| F12 | Deferred | S-1 to S-8 |
| F13 | Open | Keyboard on real hardware: gameplay checklist |
