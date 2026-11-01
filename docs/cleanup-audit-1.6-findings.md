# The 1.6 cleanup audit: findings

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md).

**Kind: working record** (issue 82). What the audit of
[`cleanup-audit-1.6.md`](cleanup-audit-1.6.md) found, item by item. That list is generated
from the build; the notes in its audit column refer here by number (F1, F2, ...). Each
finding says what was measured and how, and what is proposed. Nothing here is changed in
the code until it is agreed and done in its own small, tested step.

## Progress

| Section | Items | Audited |
| --- | --- | --- |
| 1.1 KMRP's hooks | 36 | 36 |
| 1.2 the controller patch's hooks | 38 | 8 |
| 1.3 to 1.5 bundled patches | 65 | not KMRP's code: no site overlaps another, measured 2026-11-01 |
| 2 engine recipe | 89 runs, 57 operands | 0 |
| 3 run-time writes | 10 | 0 |
| 4 source files | 80 | 0 |

## F1. `kmrp.dll` compiles the whole controller code base (fixed, `80f9277`)

**Measured 2026-10-31.** `build_native_runtime.cmd`, which builds `kmrp.dll`, compiled
`K1NativeJoystick.cpp` (9,067 lines), `K1ControllerBackend.cpp`, `K1ControllerLayout.cpp`,
`K1Rumble.cpp`, `K1ButtonRemap.cpp`, `vendor/K1XboxControls.cpp` (7,471 lines) and
`vendor/K1XboxControlsXInput.cpp`, though KMRP's patch has carried no controller hook since
the two patches were split on 2026-10-05.

**Fixed 2026-11-01**, in its own report:
[`cleanup-1.6/F1-kmrp-without-controller-code.md`](cleanup-1.6/F1-kmrp-without-controller-code.md).
`kmrp.dll` compiles no controller source; KMRP's few functions in those files are in
`K1CoreFrames.cpp` and six files both modules share; the exports are unchanged, and the code
was compared function by function. **Correction:** this finding first said the linker already
left the unreachable controller code out of the shipped file. It left out most of it: the old
`kmrp.dll` carried symbols of all seven controller objects, mostly data, and the new one is
19,968 bytes smaller.

**Correction it found.** On 2026-10-31 issue 85's fix was installed in the maintainer's
game as both `kmrp.dll` and `kmrp-controller.dll`, on the belief that both modules carried
it. Only the controller module does; `kmrp.dll` was rebuilt from the same sources and
swapped too, which did no harm.

**Seen in the maintainer's game on 2026-11-01** at 3440x1440: "it works" (`kmrp.dll`
`67B4E784...5D22`, `kmrp-controller.dll` `7815B513...9E08`).

## F2. Two resource-preparation hooks five bytes apart (kept; the name fixed)

`0x00407230` (KMRP, `KmrpPrepareResourcesK1` in `K1RuntimeAssets.cpp:1724`) and
`0x00407235` (the controller patch, its own `KmrpPrepareResourcesK1` in
`K1ControllerStandalone.cpp:372`): one name, two different functions, one per module. Each
patch must work without the other, and KOTOR Patch Manager allows one patch per address, so
they cannot share one entry. Kept.

**Renamed 2026-11-01:** the controller's is `ControllerPrepareResourcesK1`
(`RESOURCE_OWN_FUNCTION`, `tools/build_controller_kpatch.py`). The site, its bytes and the
function's instructions are unchanged. The export's name changed, so a `kmrp-controller.dll`
from now on needs a `patch_config.toml` that names it: a module swapped alone into a game
installed earlier leaves that hook without its function.

## F3. Confirm guards (keep)

The controller patch's five character-creation guards (`0x006F28C0` to `0x006F8FF0`) are
one-line exports over one shared `GuardChargenConfirmK1`, as the hook table's check
(`check_patcher_hook_table.py`) needs one export per hooked dispatcher. Already the shape
issue 82 asks for; nothing to change.

## F4. One memory check and one field helper, written several times (fixed)

Found while fixing F1. Counted on 2026-11-01; the first count had two copies of each.

| Helper | Copies before | Now |
| --- | --- | --- |
| The readable-memory check | `IsReadableK1`, `KmrpGui::readable`, `K1CaptionInk::Readable`, `K1BadgeReadable` (`vendor/K1XboxControls.cpp`) | `IsReadableK1` (`K1EngineMemory.h`) |
| A field at an offset, as a reference | 13: `at` (`K1GuiControls.h`), `Field` (`K1RuntimeLayout.cpp`, `K1KeyboardNavigation.cpp`), `F` (`K1TextRows.cpp`), `At` in eight files and `K1OptionsPad.h` | `At` (`K1EngineMemory.h`) |
| An engine routine at an address | `EngineFn`, `KmrpGui::fn`, `Fn` in `K1HudOptions.cpp` and `K1Rumble.cpp` | `EngineFn` |

`FieldAt`, which returns a pointer, stays, on `At`. `K1TextRows.cpp`'s own `At` gave a part's
address, so it is `Part` now. **Left as they are:** the `Fn` of `K1TextLayout.cpp`,
`K1TextOptions.cpp` and `K1TextRows.cpp`, where a test harness swaps the engine's routines;
`K1SliderGrip.h`'s `Field`, an `int` only; and the `VirtualQuery` calls of
`K1RuntimeResolution.cpp` and `K1OffscreenFrame.cpp`, which ask about a slot about to be
written, not whether a range can be read.

**One difference in behaviour.** `K1CaptionInk::Readable` and `K1BadgeReadable` looked at the
first memory region only, so they answered no for a range running into a second region even
when that was readable. `IsReadableK1` walks the regions. Windows joins neighbouring pages of
the same kind into a region, so this changes the answer only for a range that crosses a
change of page protection. `KmrpGui::readable` said yes to a size of 0 and `IsReadableK1`
says no: every caller was read, none can pass 0 and go on to read.

**Checked.** All sources of both modules compiled from `80f9277` and from the working tree
with the build's flags, and each function's instructions compared (jump targets, anonymous
namespace hashes and the helpers' names made neutral): `kmrp.dll` 9,369 identical and 13 not,
the controller 5,006 and 18. The differences were sorted by their listings, not read one
instruction at a time: some are lambdas that the neutral names made collide; the others have
the same operations with other registers or stack slots, or `IsReadableK1` inlined where a
smaller copy was a call (`K1GuiModelPreload`, `K1ClassModelTrace`,
`K1CaptionSignature`, `NativePanelReleaseGffK1`, `updateDialogBadges`), and
`NativeJoystickDumpK1` is F6. Both modules are 512 bytes smaller.

**Seen in the maintainer's game on 2026-11-01** with F2 and F6: "it works correctly" (what was
checked not stated; `kmrp.dll` `12DA0264...58AE`, `kmrp-controller.dll` `7D216F68...8892`).

## F5. The party portrait repair needs the controller patch (fixed, `80f9277`)

`KmrpPartyPortraitsK1` repaired the Party Roster Limit 32 mod's empty portraits only on pages
whose buttons the controller patch's ReleaseGff hook had found, so KMRP alone never repaired
them. Recorded first as a gap to leave (2026-10-31); the maintainer then asked for it to work
with KMRP alone (2026-11-01). Fixed the same day without a new hook: KMRP takes the five
buttons' IDs from its own records of the panel's controls. Report:
[`cleanup-1.6/F5-party-portraits-with-kmrp-alone.md`](cleanup-1.6/F5-party-portraits-with-kmrp-alone.md).
The build with it runs in the maintainer's game (F1), but without the roster mod, so the
repair itself is not seen in a game.

## F6. The controller's state dump can outgrow its buffer (fixed; no overrun)

`tools/check_controller_drift.py` said the line `NativeJoystickDumpK1` writes can reach 1,484
bytes in a 1,200-byte buffer (1,499 before F1). **Read on 2026-11-01: there was no overrun.**
The check took the file's first `char line[`, which is the frame timing log's; the dump's
own buffer is 2,048 bytes. The same check had once measured the wrong `wsprintfA`.

**What was wrong instead.** `wsprintfA` stops at 1,024 bytes, so with every field at its
widest the line would have lost its last columns and its line end. The longest line in the
maintainer's log of 2026-10-30 is 700 bytes (16,713 lines), so this had not happened.

**Fixed:** `std::snprintf` with the buffer's size, which prints the same conversions without
that ceiling, and the check reads the buffer inside the function. It reports 106 conversions,
106 arguments, worst case 1,484 of 2,048 bytes.

The check's other warning stands: three badges built and never referenced (`kmrpa_clssel`,
`kmrpl_pzkflip`, `kmrpx_pzkplay`). It is not this finding's.

## F7. `Test-SwoopPrompt` fails on the last commit already (fixed)

Its harness compiles a slice of `K1NativeJoystick.cpp` that calls `KmrpDrawnPictureK1`, and
the harness never got that function when the call came in `0ae9175` (2026-10-28), so the
test had not compiled since. The harness now has it, drawing families 1 and 3 and naming
none for 0 and 2, so both ways the prompt can load are checked. **Passes: 47 checks.**

## F8. `Test-GuiAudit` stopped at a badge KMRP's sets no longer carry (fixed; findings stand)

Since `b1148c9` (2026-10-27) KMRP's sets carry no controller art, and the audit's badge step
still read each listed badge from them, so it stopped at `kmrpb_charexit.tga`. It reads only
the badges a set draws now, and the report says the badge aspect check is untested when
there are none. The audit runs to its end again: 66 listed and 606 blended sizes, 394 helper
rejections, 1,611,456 control instances. Mac artifact builds were skipped (`--skip-build`).

**It still exits 1, and that is the audit's design:** "A nonzero exit with KMRP findings is
expected until the maintainer reviews them". Finding groups: KMRP 1,269, inherited 891, by
design 219. The last report's figures are 1,651, 889 and 219 (`GuiAudit-2026-10-11.md`). Nothing
was exempted, and none of the 1,269 was reviewed here. The test is run with `--report`
outside `testing/` while it is only being checked, so it leaves no dated report in the repository.

## F9. `Test-ControllerPromptAssets` stopped at the galaxy map (fixed)

Six hints added on 2026-10-28 have no entry in `PROMPT_STRREFS`: Travel and Cancel on the galaxy
map, OK and Cancel on the save name popup, and Pazaak setup's `BTN_YTEXT` and `BTN_ATEXT`. The
builder takes a missing entry as no wording (`.get`), the test demanded one, and it had not got
past the first. Their rows in `kmrp_prompts.txt` bake a width of 0 and no variants, and no
controller source reads that file, so a table entry would change nothing there on Windows.

The test names the six (`RUNTIME_CAPTIONED_TARGETS`), checks that they bake nothing, and fails
for a seventh button without an entry, or if one of the six gains one. **Passes: 38,544 badged
buttons in 66 sets.** What was not read: whether the Mac's own badges need a width for these
six, since its build keeps controller art in its sets.

## The standard for the rest of the audit

The maintainer, 2026-11-01: "The code just needs to be efficient without any convolutions, even
hooks. We shouldn't have like hooks that do the same. It should be a very clear architecture."
Every entry is read and asked four things: is it needed, does anything else do the same job,
is it simple, and is it in the right module. Issue 82's limit stands: hooks merge only where
timing, registers and behaviour really match, and the game's behaviour does not change.

## F10. `0x0040BE70` and `0x005F18F6`: not the same job (closed, keep)

**Corrected 2026-11-01.** This finding first said the two hooks have one job and proposed
removing `0x0040BE70`, from a log count and a text search of the private reconstruction. The
maintainer asked why, and the technical documents had not been read. Read now, with every
caller listed from `build-inputs/swkotornopatch.exe` (the Steam file's code is packed): direct
calls found by a scan of `.text`, and no pointer to the function anywhere in the file.

| Caller of `SetSize` | In | Size | `Prepare` already run? |
| --- | --- | --- | --- |
| `0x005F19DE` | `SetVideoMode` (`0x005F1830`) | the new mode | Yes, `0x005F18F6`, same size. Here the hook does nothing. |
| `0x005F93FA` | `0x005F8470`, just after the GUI manager is made | the screen size globals | Only if `SetVideoMode` got past its first steps. It returns early when the mode is the one in force or `EnumDisplaySettingsA` fails, and `0x005F18F6` never runs. |
| `0x0068FA08` | the evil ending's credits | 640x480 | No. The log shows that size refused on this PC, so nothing is done here. |
| `0x0068F1C5` | the same, on the way back | the saved size | No mode switch. The size should be the current one, so `Prepare` returns at once. |

So `0x0040BE70` is the one hook that sees every change of the GUI's size, and in the
`0x005F93FA` case it can be the only `Prepare` of a size that `KmrpPrepareResourcesK1`, which
reads `swkotor.ini`, did not already prepare. The 133 pairs in the maintainer's log show that
this did not happen on this PC, not that it cannot happen.

**Kept.** What can go: `g_requested`, written and never read (`K1RuntimeResolution.cpp`). Its
hook's row was also missing from the table of what KMRP does on a change, in
[`resolution-switch.md`](../reverse-engineering/resolution-switch.md) section 5; added.

## F11. The first preview module is still in the build's files (open, proposed removal)

`build_runtime_preview.cmd`, `tools/build_runtime_kpatch.py` and `Test-RuntimeKpatch.py` make
and check `kmrp-native-preview.dll`, the first standalone module (`8da2821`). Nothing ships
it. Its test passes against a module last built long ago in `build/native-preview`, so it
proves nothing about today's code. It keeps three things alive in the sources: the
`#ifndef KMRP_NATIVE_RUNTIME` branches of `K1RuntimeResolution.cpp`, a second
`NativeFreeSaveBufferK1` calling a different address (`0x006FA390`, not the module's
`0x006FB7B2`), and a comment naming `K1RuntimeCore.cpp`, which does not exist. The resolution
trace is still called `kmrp-native-preview.log`.

**Proposed:** remove the three files and the branches, and rename the log to
`kmrp-resolution.log`, with `InstallCore.cs`, `KmrpOptions.h` and `docs/kpm-edition.md`. The
patch IDs `kmrp-native-preview` in the kpatch tools' conflict lists stay, since an old install
may hold one. Also from this pass: `K1TextLayout.cpp` still says `CorrectHardwareMipmapsK1`
is in `K1NativeJoystick.cpp` (F1 moved it), and 11 `.obj`, `.exp` and `.lib` files of 2026-10-04
lie ignored in `src/controller-native`.

## F12. Where the sources are too big or say a thing twice (open, measured, section 4 decides)

`K1NativeJoystick.cpp` (8,455 lines) and `vendor/K1XboxControls.cpp` (7,455) are the two
monoliths, `K1XboxHud.cpp` (2,680) and `K1RuntimeAssets.cpp` (2,007) the next. `KmrpXboxHudK1`
is one function of 361 lines and `KmrpXboxHudBarsK1` one of 133.

A token scan of 69 native files and 18 installer files, comments ignored, found 129 exact
repeats of 50 tokens or more and 154 of the same shape at 90 or more in the native code, 16 and
17 in the installers. The ones that matter:

| Repeat | Where | Size |
| --- | --- | --- |
| The options page toolkit (`Extent`, `Text`, `AddControl`, `CloneButton`, `Bind`, `Navigation`) | `K1HudOptions.cpp:201-243`, `K1TextOptions.cpp:147-193` | 658 tokens, and 267 and 293 more |
| The Xbox HUD's `Placed` arithmetic and its `Piece` table | `K1HudOptions.cpp:84-118`, `K1XboxHud.cpp:620-905` | 262 tokens, across modules |
| Old temp folder cleanup, UTF-8 paths, SHA-256 | `K1ControllerStandalone.cpp`, `K1RuntimeAssets.cpp` | 433 tokens, across modules |
| Picture sizing, repeated in one file | `K1XboxControls.cpp:2385-2600` | 125 tokens, five times |
| Rounded rectangle loops | `K1NativeJoystick.cpp:5500-5519` | 153 tokens |
| `PressDefault` and `PressListedButton` bodies | `K1NativeJoystick.cpp:3490-3560` | 149 tokens |
| Installers | `KmrpPatcher.cs:1094` and `1282`; `KmrpPatcher.cs:2249` and `MainWindow.cs:726` | 168 and 96 tokens |

Each is read when section 4 reaches its file. The scan counts text, not meaning, so a repeat
is a place to look, not yet a finding.
