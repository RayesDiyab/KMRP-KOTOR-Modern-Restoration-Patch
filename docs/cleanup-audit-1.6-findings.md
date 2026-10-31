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
| 1.1 KMRP's hooks | 36 | 15 |
| 1.2 the controller patch's hooks | 38 | 8 |
| 1.3 to 1.5 bundled patches | 65 | not KMRP's code: checked for overlap and timing only |
| 2 engine recipe | 89 runs, 57 operands | 0 |
| 3 run-time writes | 10 | 0 |
| 4 source files | 80 | 0 |

## F1. `kmrp.dll` compiles the whole controller code base (fixed, uncommitted)

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

## F2. Two resource-preparation hooks five bytes apart (keep)

`0x00407230` (KMRP, `KmrpPrepareResourcesK1` in `K1RuntimeAssets.cpp:1724`) and
`0x00407235` (the controller patch, its own `KmrpPrepareResourcesK1` in
`K1ControllerStandalone.cpp:372`): one name, two different functions, one per module. Each
patch must work without the other, and KOTOR Patch Manager allows one patch per address, so
they cannot share one entry. Kept. The shared name is confusing; renaming the controller's
(`ControllerPrepareResourcesK1`) would change its hook table and the module's exports, so it
is only worth it together with F1.

## F3. Confirm guards (keep)

The controller patch's five character-creation guards (`0x006F28C0` to `0x006F8FF0`) are
one-line exports over one shared `GuardChargenConfirmK1`, as the hook table's check
(`check_patcher_hook_table.py`) needs one export per hooked dispatcher. Already the shape
issue 82 asks for.

## F4. One memory check and one field helper, written several times (open)

Found while fixing F1. `readable` (`K1GuiControls.h`) and `IsReadableK1`
(`K1EngineMemory.h`) are the same `VirtualQuery` check, written twice (the first also
accepts a size of 0). The helper that reads a field at an offset has four names across the
files: `at` (`K1GuiControls.h`), `FieldAt` (`K1EngineMemory.h`), `Field`
(`K1RuntimeLayout.cpp`) and `At` (`K1TextLayout.cpp`), and `fn` / `EngineFn` for an engine
routine. To be counted file by file before anything changes.

## F5. The party portrait repair needs the controller patch (fixed, uncommitted)

`KmrpPartyPortraitsK1` repaired the Party Roster Limit 32 mod's empty portraits only on pages
whose buttons the controller patch's ReleaseGff hook had found, so KMRP alone never repaired
them. Recorded first as a gap to leave (2026-10-31); the maintainer then asked for it to work
with KMRP alone (2026-11-01). Fixed the same day without a new hook: KMRP takes the five
buttons' IDs from its own records of the panel's controls. Report:
[`cleanup-1.6/F5-party-portraits-with-kmrp-alone.md`](cleanup-1.6/F5-party-portraits-with-kmrp-alone.md).
Not seen in a game.

## F6. The controller's state dump can outgrow its buffer (open)

`tools/check_controller_drift.py`: the line `NativeJoystickDumpK1` writes can reach 1,484
bytes in a 1,200-byte buffer (1,499 before F1). Already reported before F1; whether the write
is bounded is to be read.

## F7. `Test-SwoopPrompt` fails on the last commit already (open)

Its harness compiles a slice of `K1NativeJoystick.cpp` that calls `KmrpDrawnPictureK1`
without a declaration in the slice: the same error with the last commit's sources as after
F1.

