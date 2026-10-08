# Testing support

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


Material for checking KMRP at resolutions the build machine's monitor cannot
display, plus the installer cases that can be checked without a display at all.
Layout verification combines the static GUI audit below with play-tests: patch
at a resolution and compare the rendered result against the computed layout.
Installer behaviour is scripted.

## Exhaustive static GUI traversal

Reference. [Test-GuiAudit.py](regression/Test-GuiAudit.py) reads every `.gui` in
the 66 `gui-<W>x<H>.zip` archives, including recursive `CONTROLS`, `PROTOITEM`
and `SCROLLBAR`. The [2026-10-02 lab record](GuiAudit-2026-10-02.md) contains
the current measurements, input hashes, findings and explicit assumptions;
its [console output](GuiAudit-2026-10-02.console.txt) is retained verbatim.
No game execution is implied by these numeric checks.

```sh
# Use the project Python environment containing pykotor, as for the other GUI tests.
python testing/regression/Test-GuiAudit.py build/kmrp/resources \
  --game "/path/to/game/data" --report testing/GuiAudit-2026-10-02.md
```

`--game` is optional and names the directory containing `chitin.key` and
`dialog.tlk` (on macOS, the app's `Contents/Assets`). It reads core KEY/BIF
resources and Patch.erf for stock GUIs, and core/module item/creature templates, baseitems,
spells and feats, and resolves GUI STRREFs through TLK. It does not write to
the game or use installed Override files as stock references. Without game
files it reports that coverage as **untested** and uses the documented long
name corpus in the test. Save/placed-object overrides, installed Override
modifications and player-created names are outside that corpus. Real item names
are applied to item/inventory/shop row prototypes and action names to
ability/power/feat row prototypes. Description, dialogue, option and module rows
stay explicitly untested because this static audit cannot establish their runtime
contents. Applying single-line item/action names to SELF description slots is an
explicit upper-bound assumption; review the actual slot assignment before changing
a layout. Multiline template labels are excluded from the two-line name/SELF probe.

The default sweep calls the compiled native `kmrp-guiblend` helper with a
freshly built `gui-blend.bin`: heights 560 through 4400 in steps of 23,
at 4:3, 3:2, 16:10, 16:9, 21:9 and 32:9, plus 1036×583 and 1077×606.
Listed duplicates are omitted and helper rejections are counted. Each accepted
blend uses the nearest listed set's fonts, chosen by height then aspect ratio.
Temporary outputs are removed after inspection. This is an extended regression
run; `--listed-only --skip-build` is a quicker diagnostic and labels skipped
coverage **untested**. On Windows, compiled C# parity is a separate run of
[Test-GuiBlendHelper.py](regression/Test-GuiBlendHelper.py); it is untested
on a Mac.

Checks cover panel containment, font/known/runtime text capacity, intersections
between sibling buttons, text labels and list boxes, identified fixed-aspect art
and controller badges, list row pitch
and scrollbar placement, screen edges, the target name's clipping edge,
scaling classifications, and blended extents against all contributing anchors.
The active HUD is distinguished from unused shipped HUD variants. Python
reimplementations additionally exercise status-summary rows, popup fitting and
granted-popup rows. Mac runs rebuild patches with and without the controller,
inspect the hook metadata at VA `0x10049f636`, and check the modules' exported
`KmrpCoreGuiFrame` symbol. Controller selectability and the Windows core-frame
call are source-level checks, explicitly untested in game.

The [data allowlist](regression/GuiAudit-allowlist.json) gives each intentional
exception a reason and establishment source. Every finding stays in the report:
**KMRP** fails the run; **inherited** and **by design** are listed without failing.
Classifications use same-size upstream layouts (derived upstream layouts where
needed), stock aspect evidence, and explicit exceptions. Gold extents are
shown as additional evidence. Upstream text is evaluated with stock embedded
font metrics when game files are available; without them text inheritance is
untested and remains conservatively classified KMRP. New geometry/visibility assumptions require review,
not blanket exemptions. Findings are grouped by GUI, recursive control path,
check and class, with affected-size count, worst size and measured excess.

This audit is deliberately static. It cannot establish simultaneous visibility,
engine-created control membership, actual list-client dimensions, runtime font
assignment, TPC-only art shape, readable contrast, focus behavior or rendered
wrapping without game measurements. Runtime formulas use the explicit models
recorded in the lab report. It does not alter layouts or resource generators.
It is a regression screen for those measured/modelled invariants, not a claim
that every possible in-game visual defect is excluded.

To verify a finding by hand, open the named archive at its worst size, read the
control EXTENT and matching font TXI, and recompute the report's formula. For a
blend, follow the helper build and nearest-font-set steps in
`Test-GuiBlendHelper.py`, then read the helper's output. Compare the named
upstream/gold fields before deciding whether a finding needs a layout change.

| | |
| --- | --- |
| [`virtual-display/`](virtual-display/) | A virtual-monitor profile exposing 49 of the 66 listed resolutions (all there were until 2026-09-29) on one Windows machine, so a layout can be seen at 7680×2160 without owning such a display. |
| [`regression/`](regression/) | Scripted checks: installer behaviour against throwaway copies of the game files, read back as SHA-256, and the packaged resources read out of the build. |
| `controller/` | Controller harnesses: a virtual pad, probes and end-to-end tests that drive the running game, and `select_controller_path.py`, which installs the native or legacy controller path into a test game. They read `kmrp-native-joystick.log`, which the module writes only with the patch's `debug-logs` option on since 2026-10-04: the test game needs `debug-logs=1` under `[Patch Options]` in `configs/kmrp.ini`, and since 2026-10-05, when the controller became a patch of its own, in `configs/kmrp-controller.ini` for that patch's module (`KmrpOptions.h`; Debug Logs in Advanced Settings before installing sets both). `select_controller_path.py` still installs the four-patch edition's module, which is no longer built. |
| `gold-geometry-diffs.txt` | A recorded field-by-field diff of GUI geometry between two builds — the format these comparisons are read in. Committed with the first commit (2026-08-29); its values come from builds of that time, not the current one. |

## Running the installer checks

```powershell
.\build_kmrp.ps1                                        # the checks run the built patcher
.\testing\regression\Test-ReinstallOverOlderBuild.ps1
```

Each script exits non-zero if any check fails and prints one PASS or FAIL line
per assertion.

**Tests of the four-patch edition, removed 2026-10-04.** `Test-KpmEdition.ps1`,
`Test-ControllerSupport.ps1` and `Test-InstalledOverride.ps1` asserted the layout the
installer wrote until that day: four patches, `kmrp-kpm.dat` and the Override files.
The installer writes none of that now (one patch from
[2026-10-04](../docs/kpm-edition.md#one-patch-since-2026-10-04), two independent
ones since 2026-10-05), and the install code they covered is gone, so they were
deleted with it. `Test-InstallerPatch.ps1`, `Test-KpatchSource.py` and
`Test-ControllerKpatch.py` cover the current layout. The runs
recorded below and in the reference documents name them as they were.

**Do not interrupt `Test-InstallerPatch.ps1`.** It rewrites the real installer
settings, `%LOCALAPPDATA%\KMRP\settings.json`, case by case and puts them back
only in its `finally` block, and each fixture's DPI and NVIDIA state is undone
only by that fixture's own restore step. Stopped mid-run on 2026-09-25, it left
`controllerSupport` off -- the next real install would have skipped the
controller -- and one fixture unrestored. The fix was `--restore` on that
fixture's executable, then the settings file rewritten by hand. Since 2026-09-29
it copies the player's `settings.json` into its work folder first, so a stopped
run leaves that copy there to put back. They need `build-inputs\swkotornopatch.exe`, and they patch only
throwaway copies under the system temp folder — no installed game is touched.

The full set, as of 2026-09-24. Against that day's build, the four Python
checks and `Test-ControllerSupport.ps1` were run and pass; the other PowerShell
scripts were not re-run that day. Against the 1.5.0 installer of 2026-09-25
(`B599303A…`, 49 resolutions), the four Python checks,
`Test-ControllerSupport.ps1` and `Test-ReinstallOverOlderBuild.ps1` were run and
pass; `Test-ControllerSupport.ps1` again against `873A01E2…`, which changes only
the module (BioWare's rumble table). Against the haptics hardware-test
installers `74011765…`, `6BEE57FF…` (adds `SaberHum`), `F4B4CE4F…` (pulses
the hum), `BA103494…` (a random gap between pulses), `8C0A6D94…` (its
minimum and maximum as separate settings), `1815ED7A…` (the combat fixes
and the melee hit hook) `4C02A277…` (the action bar keeps focus) and `C796489A…` (`Debug=0` by default),
`Test-ControllerSupport.ps1`, including its new Case 7 for an edited
`kmrp-controller.ini`, and `Test-ReinstallOverOlderBuild.ps1` were run and pass.
Against `7C2FFF8B…` (X and Y in combat, the dialogue A moved, the combat
message, the update check), the four Python checks on its reused archives,
both of those scripts and `Test-UpdateCheck.ps1` were run and pass, and the
three scripts again against `AD3DC07D…`, which changes only the update dialog.
Against `E5AFC981…` (the dialogue A from the drawn layout, the combat message on
one line; a full build), the four Python checks and both of those scripts were
run and pass; against `EC98B10F…` (the character-creation A guard, reusing those
archives), both scripts again. Against `EE262D77…` (the character-creation
badges; a full build) the four Python checks and both scripts, and
`Test-LargeAddressAware.ps1` and `Test-DpiCompatibility.ps1` against
`189DF101…`; against `1720E0C1…` (Attributes and Skills navigation, reusing those
archives) both scripts again; against `DB9D7A08…` (Feats' A and X swapped,
the name-entry guard) both scripts, `Test-ControllerSupport.ps1` with its new
exports check; against `4EF3C181…` (the resolution layouts pooled, reusing
those archives and that module) both scripts and `Test-InstalledOverride.ps1`
at all 49 resolutions; against `6A822AAC…` (the settings screens' badges and
arrow glyphs, a full build) the four Python checks and all three scripts;
against `D407BF3A…` (the status summary's layout added to the module)
`Test-ControllerSupport.ps1` and `Test-ReinstallOverOlderBuild.ps1`; against
`63E7AAB9…` and `B5D3CBB7…` (the status summary's A, then the D-pad kept off
its OK) both scripts; against `49671B67…` (the swap-tabs cue beside Close, a
full build) the four Python checks and all three scripts; against
`80616FE6…` (the line spacing, reusing those archives) all three scripts;
against `128CDC79…` (Level Up, Auto Level Up and the skill-info notice, a
full build) the four Python checks and all three scripts; against
`9736B41F…` (the echo guard on every panel, the D-pad arrow glyphs taken
out, a full build) the four Python checks and all three scripts. All pass. Both use their own fixture executable names, so an NVIDIA
profile made for them cannot match a real `swkotor.exe`. `Test-DpiCompatibility.ps1` and
`Test-NvidiaPresentMethod.ps1` write per-user compatibility and NVIDIA profile
state for their throwaway executables and remove it again, so run them
knowingly:

| Script | What it pins |
| --- | --- |
| `Test-InstallerPatch.ps1` | *Since 2026-10-09 also:* the frame-rate lines of `swkotor.ini` in each case, and Case 6, High FPS Fix on (D3M0's patch third in the config with its 36 hooks, its module and `.kpatch` the bundled file's, restore). Every case writes `highFpsFix` into the settings, since left out it follows the test machine's display. What the installer puts in a game folder: KOTOR Patch Manager's runtime with KMRP's patch, `kmrp`, and, while Controller Support is on, the controller patch, `kmrp-controller`. With it on: both patches in `patch_config.toml` in that order with every hook of both `.kpatch` files and no options table, `patches\kmrp.dll` and `patches\kmrp-controller.dll` equal to the modules inside the two `.kpatch` files, both files delivered to KOTOR Patch Manager's patch folder and each accepted by its builder's `--check`. With it and map notes off: `kmrp` alone with the same hooks, one module, no `configs\kmrp-controller.ini`, no controller `.kpatch`. Both ways the `[Patch Options]` section of `configs\kmrp.ini` (`map-notes`, `debug-logs` off, no `controller` key, a section of the fixture's own kept), nothing in Override, no data file, the size asked for in `swkotor.ini`, and Restore Original leaving the folder file for file. Case 3: a resolution choice left in the settings by a build before 2026-10-07 writes no `kmrp-resolutions.txt`. It replaces the player's KMRP and KPM settings files for the run and puts them back. Does not start the game. (Until 2026-10-05 it pinned one patch with `controller` as an option; from 2026-10-04 to 2026-10-07 it required `kmrp-resolutions.txt` for a resolution choice.) |
| `Test-KpatchSource.py` | KMRP's patch as packaged: the `.kpatch` against the tracked hook table and the source engine guards, and `K1ListRows.inc` against the Mac's file when both are in the tree ([source reference](../docs/windows-engine-source.md)). |
| `Test-ControllerKpatch.py` | The controller patch as packaged (`dist\controller`): its hooks, its module's exports and what it carries ([`docs/controller-standalone.md`](../docs/controller-standalone.md)). |
| `Test-DpiCompatibility.ps1` | The per-executable Windows DPI setting, and restoring exactly what was there |
| `Restore-TestNvidiaProfiles.ps1` | Dot-sourced cleanup for the six scripts that install into fixtures. `Hide-KpmLauncherSettings` and `Restore-KpmLauncherSettings`, added 2026-09-29, move KOTOR Patch Manager's own settings aside for the run, since an install puts KMRP's `.kpatch` files into the patch folder they name. `Restore-TestNvidiaProfiles` undoes their NVIDIA profile records. `Remove-TestDpiValues`, added 2026-09-25, removes their Windows high-DPI values when the work folder is deleted, so a run stopped between install and restore no longer orphans one (see `docs/windows-dpi-scaling.md`) |
| `Test-LargeAddressAware.ps1` | Both accepted inputs, one with the LAA bit already set, give the same `--apply` output and restore byte for byte; since 2026-09-29, an install sets that bit and changes nothing else in `swkotor.exe`, and another header change is refused in place. Since 2026-09-30 (Case 6), GOG's executable, made from the editable one by zeroing its 16-byte header watermark and required to hash as GOG's: the same `--apply` output, the flag, KPM's backup, state file and config naming GOG's file, an exact restore, and another byte in that padding refused |
| `Test-MovieResolution.ps1` | The four movie-mode operands and the render-resolution operands, read back at four resolutions |
| `Test-NvidiaPresentMethod.ps1` | The NVIDIA present-method step: when it writes, when it leaves the player's choice alone, and restore (dot-sources `Restore-TestNvidiaProfiles.ps1`; `NvidiaPresentSelfTest.cs` is its compiled self-test) |
| `Test-ControllerPromptAssets.py` | Every prompt texture and control mapping in all 66 archives (49 until 2026-09-29), four controller families, and the Controller Layout screen; since 2026-09-28 that no archive carries a D-pad glyph for the −/+ arrows (`kmr?dl_*`, `kmr?dr_*`), which the build shipped from 2026-09-25 until the maintainer asked for the arrows' own art back; since 2026-09-26 the badges that stand on their button's own box (`backing`): the box on both borders, the texture exactly that colour away from the glyph, and the glyph clear of the edges |
| `Test-GeneratedGuiGeometry.py` | The reported GUI repairs and the active HUD in all 66 archives (49 until 2026-09-29), the R3 cue included, and since 2026-09-25 the swap-tabs cue's place left of Close on Abilities; since 2026-09-30 the journal's six rows, every list made as tall as whole rows, and the Feedback list's check box rows at `round(43s)` |
| `Test-FontAtlasScale.py` | Every packaged font atlas draws one texel per pixel |
| `Test-ProtonResourceCompatibility.py` | Case-exact, collision-free resource names for Linux / Proton |
| `Test-ReinstallOverOlderBuild.ps1` | Installing over an earlier KMRP, which wrote `swkotor.exe` (`-OlderPatcher`, default `build\legacy\KMRP-standalone.exe`: any installer from before 2026-09-29, such as KMRP 1.0 or the last standalone build `061AD6A2…`), restores it with its own backups first and leaves the original executable plus the 4 GB flag; one with a damaged backup is refused untouched; reinstalling the same build changes nothing; an unsupported executable is refused; a stray backup beside a clean executable no longer blocks. The two cases that need the earlier installer are skipped, and say so, without it. (Until 2026-09-29 it tested the standalone reinstalling over its own older output.) |
| `Test-UpdateCheck.ps1` | The installer's update check: release-tag parsing, the version comparison (a 2.x tag would be "newer" than 1.5.0), and "Don't remind me again for <version>" through the real `settings.json`, put back byte for byte. `-Live` asks GitHub once (informational); `-RenderTo` draws the dialog to a PNG. `UpdateCheckSelfTest.cs` is its compiled self-test |
| `Test-ResolutionDerivation.py` | Deriving a `.gui` set by blending the upstream sets around a resolution (`derive_resolution`): each upstream 16:10 set predicted from 4:3 and 16:9, each 16:9 set from 16:10 and 21:9, and 2880x1620 against its older two-set derivation. Added 2026-09-29 with the 17 macOS resolutions |
| `Test-AbilityIcons.py` | `macos/tools/kmrp-abilityicons.c` writes the same feat, power and skill icons as `AbilityIconGenerator.cs`, byte for byte at ten heights -- on macOS both slices, on Windows one x64 build (`native_helpers.py`, since 2026-09-29) -- and the skill icons on a canvas of `round(32s x 50 / 42)` capped at 64, their picture `round(0.62 × 50s)` at its place and nothing drawn outside it (a canvas of `round(32s)` and a picture of `round(0.62 × 42s)` until 2026-09-30, when the skill rows moved to `50s`). Needs clang and the .NET 8 SDK, on macOS or Windows. Added 2026-09-29 |
| `Test-GuiBlendHelper.py` | macOS: `macos/tools/kmrp-guiblend.c` matches an independent Python blend over the table `tools/build_gui_blend_table.py` packs, byte for byte, and derives each of the 17 Mac sets, held out, with 99.9% of fields within 1 px. Added 2026-09-29. Since 2026-09-30: runs on Windows too (the helper built with LLVM clang, `native_helpers.py`), where it also requires the Windows installer's own blend (`src/patcher/GuiBlend.cs`, through `--derive-gui`) to equal the helper's at every size above, every anchor and 300 random sizes, and to refuse the same sizes; and with table version 4, the lists made as tall as whole rows fitted by the build's own `fit_list_to_rows`, and every badge and the HUD's boxes drawn for the blended buttons, equal to the build's own `build_prompt_tga` and `build_menubg_texture`, every anchor rebuilt with its badges byte for byte, and every badge round on its blended button |
| `Test-KmrpLayoutPatch.py` | macOS: every site of `macos/patches/kmrp-layout` against the clean `KOTOR_Exe` (expected bytes, lengths, overlaps), its values at 76 resolutions against the Windows rule, the stubs' disassembly and the single load-time initialiser. Added 2026-09-29 |
| `Test-MacInstaller.py` | macOS: `kmrp-mac.sh` install, status and uninstall into a stand-in game for a listed size and a blended one; what `kmrp-gameart` makes is installed at its sizes and not in the package; the executable, bundle and `swkotor.ini` byte-identical afterwards. Added 2026-09-29 |
| `Test-GameArt.py` | What both installers make from the player's game (the hex row frames, the tutorial popup's icons, `tutorial.2da`): `GameArtGenerator.cs` and `macos/tools/kmrp-gameart.c` byte for byte at every set height and more, both against an independent Python reference, the sizes every older set shipped, and the table changed in its `icon` column only. Needs clang and the .NET 8 SDK, on macOS or Windows. Added 2026-09-29 |

## What is deliberately not committed

Two kinds of file under `virtual-display/` are ignored rather than stored:

- **`verify-*/` run artifacts** — the ~80 `.gui` files a patcher run emits at one
  resolution, in a timestamped folder. They are build output: regenerate them by
  running the patcher at that resolution rather than keeping a copy.
- **The virtual display driver package** — a signed third-party download. The
  upstream project and the expected SHA-256 are recorded in
  [`virtual-display/README.md`](virtual-display/README.md), which is what makes
  storing 200 MB of it unnecessary.

## Checking a resolution

```powershell
# Patch a throwaway copy at the resolution under test, then read the values back.
& '.\dist\KMRP - KOTOR Modern Restoration Patch.exe' --apply .\clean\swkotor.exe .\out\swkotor-7680.exe 7680x2160
```

Then compare the generated `gui-<resolution>.zip` and the patched executable's
constants against what the scaling rule predicts — see
[CONTRIBUTING.md](../CONTRIBUTING.md#resolution-scaling). Read the numbers back;
do not judge a layout by eye.

### Mac memory-safety hooks

`python testing/regression/Test-MacMemorySafety.py --exe <clean KOTOR_Exe>`
executes the four core x86_64 payloads (Rosetta supported), checks texture boundary
IDs, flags, shadow continuation and both grass cleanup ownership cases. Supply
`--kpatch <package>` repeatedly to verify all optional package variants. Requires
Capstone and clang++; touches only temporary test files. See the
[ownership and hook reference](../reverse-engineering/macos-memory-safety-audit.md).

### Mac popup and action-description fitting

`Test-MacStatusSummary.cpp` includes the production shared layout and executes it
with synthetic native text/font/control objects. It covers native width482,
fractional two-line height55, screen-capped and mandatory multiline text,
unchanged-frame caching, and cached unchanged frames. The removed action-specific resizing pass is no
longer exercised. Run on macOS with the x86_64 runtime:

```sh
clang++ -arch x86_64 -std=c++17 testing/regression/Test-MacStatusSummary.cpp -o /tmp/kmrp-status-summary-test
/tmp/kmrp-status-summary-test
```

The real XP popup was confirmed fixed at 1920×1200 on 2026-10-02. The action
description has measured failing geometry and automated coverage; its runtime
repair still needs play-testing. `Test-GeneratedGuiGeometry.py` reads the
action label's assigned font from the packaged GUI and checks its three-line
minimum with native float32 height arithmetic.

`python testing/regression/Test-MacTextHeight.py --exe CLEAN_KOTOR_EXE` verifies
the five native ideal-height hook guards and executes their SSE2 ceiling payloads
under Rosetta. Exact integer heights, fractional boundaries, flags and XMM2 are
checked. Live menu behavior still requires play-testing.

Mac KPM uninstall ownership decision (isolated fixtures; no game inputs):

```sh
python3 testing/regression/Test-MacKpmOwnership.py
```

Exercises the production shell function with state-only foreign patches,
invalid/missing state lists, legacy absent state, and foreign config/modules.
