# Testing support

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


Material for checking KMRP at resolutions the build machine's monitor cannot
display, plus the installer cases that can be checked without a display at all.
Layout verification is still done by hand: patch at a resolution and compare the
result against what the tooling intended. Installer behaviour is scripted.

| | |
| --- | --- |
| [`virtual-display/`](virtual-display/) | A virtual-monitor profile exposing all 49 supported resolutions on one Windows machine, so a layout can be seen at 7680×2160 without owning such a display. |
| [`regression/`](regression/) | Scripted checks: installer behaviour against throwaway copies of the game files, read back as SHA-256, and the packaged resources read out of the build. |
| `controller/` | Controller harnesses: a virtual pad, probes and end-to-end tests that drive the running game, and `select_controller_path.py`, which installs the native or legacy controller path into a test game. |
| `gold-geometry-diffs.txt` | A recorded field-by-field diff of GUI geometry between two builds — the format these comparisons are read in. Committed with the first commit (2026-08-29); its values come from builds of that time, not the current one. |

## Running the installer checks

```powershell
.\build_kmrp.ps1                                        # the checks run the built patcher
.\testing\regression\Test-ReinstallOverOlderBuild.ps1
```

Each script exits non-zero if any check fails and prints one PASS or FAIL line
per assertion.

**Do not interrupt `Test-ControllerSupport.ps1`.** It rewrites the real installer
settings, `%LOCALAPPDATA%\KMRP\settings.json`, case by case and puts them back
only in its `finally` block, and each fixture's DPI and NVIDIA state is undone
only by that fixture's own restore step. Stopped mid-run on 2026-09-25, it left
`controllerSupport` off -- the next real install would have skipped the
controller -- and one fixture unrestored. The fix was `--restore` on that
fixture's executable, then the settings file rewritten by hand. They need `build-inputs\swkotornopatch.exe`, and they patch only
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
| `Test-ControllerSupport.ps1` | Controller install and restore ownership, the installed hook table against the source and against the installed module's exports (`tools/check_module_exports.py`, added 2026-09-25 after installer `BCA35F28` shipped a hook its module lacked), foreign-file refusal, controller-only, driver-only and default installs, and an edited `kmrp-controller.ini` surviving restore and reinstall |
| `Test-DpiCompatibility.ps1` | The per-executable Windows DPI setting, and restoring exactly what was there |
| `Restore-TestNvidiaProfiles.ps1` | Dot-sourced cleanup for the five scripts that patch fixtures in place. `Restore-TestNvidiaProfiles` undoes their NVIDIA profile records. `Remove-TestDpiValues`, added 2026-09-25, removes their Windows high-DPI values when the work folder is deleted, so a run stopped between install and restore no longer orphans one (see `docs/windows-dpi-scaling.md`) |
| `Test-LargeAddressAware.ps1` | Both accepted inputs, one with the LAA bit already set, give the same output and restore byte for byte |
| `Test-MovieResolution.ps1` | The four movie-mode operands and the render-resolution operands, read back at four resolutions |
| `Test-NvidiaPresentMethod.ps1` | The NVIDIA present-method step: when it writes, when it leaves the player's choice alone, and restore (dot-sources `Restore-TestNvidiaProfiles.ps1`; `NvidiaPresentSelfTest.cs` is its compiled self-test) |
| `Test-ControllerPromptAssets.py` | Every prompt texture and control mapping in all 66 archives (49 until 2026-09-29), four controller families, and the Controller Layout screen; since 2026-09-28 that no archive carries a D-pad glyph for the −/+ arrows (`kmr?dl_*`, `kmr?dr_*`), which the build shipped from 2026-09-25 until the maintainer asked for the arrows' own art back; since 2026-09-26 the badges that stand on their button's own box (`backing`): the box on both borders, the texture exactly that colour away from the glyph, and the glyph clear of the edges |
| `Test-GeneratedGuiGeometry.py` | The reported GUI repairs and the active HUD in all 66 archives (49 until 2026-09-29), the R3 cue included, and since 2026-09-25 the swap-tabs cue's place left of Close on Abilities |
| `Test-FontAtlasScale.py` | Every packaged font atlas draws one texel per pixel |
| `Test-ProtonResourceCompatibility.py` | Case-exact, collision-free resource names for Linux / Proton |
| `Test-ReinstallOverOlderBuild.ps1` | Reinstalling a newer build over an older one replaces the executable instead of skipping it; reinstalling the same build changes nothing; an unsupported executable is refused; a damaged backup blocks a patch. |
| `Test-InstalledOverride.ps1` | What an install writes to Override: exactly the files of `override-common.zip` and the resolution's archive, byte for byte, and nothing left after restore. Its fixture has no texture pack and no `chitin.key`, so nothing is generated (`Test-AbilityIcons.py` and `Test-GameArt.py` cover that). Added 2026-09-25, when the installer began rebuilding each resolution's files from a pool (`tools/pack_resolution_layouts.py`). Four resolutions by default; `-Resolutions all` installs all 49, 19 minutes on 2026-09-25 |
| `Test-UpdateCheck.ps1` | The installer's update check: release-tag parsing, the version comparison (a 2.x tag would be "newer" than 1.5.0), and "Don't remind me again for <version>" through the real `settings.json`, put back byte for byte. `-Live` asks GitHub once (informational); `-RenderTo` draws the dialog to a PNG. `UpdateCheckSelfTest.cs` is its compiled self-test |
| `Test-ResolutionDerivation.py` | Deriving a `.gui` set by blending the upstream sets around a resolution (`derive_resolution`): each upstream 16:10 set predicted from 4:3 and 16:9, each 16:9 set from 16:10 and 21:9, and 2880x1620 against its older two-set derivation. Added 2026-09-29 with the 17 macOS resolutions |
| `Test-AbilityIcons.py` | macOS: `macos/tools/kmrp-abilityicons.c` writes the same feat, power and skill icons as `AbilityIconGenerator.cs`, byte for byte at ten heights, on both slices, and the skill icons at `round(32s)` capped at 64. Needs the .NET 8 SDK. Added 2026-09-29 |
| `Test-GuiBlendHelper.py` | macOS: `macos/tools/kmrp-guiblend.c` matches an independent Python blend over the table `tools/build_gui_blend_table.py` packs, byte for byte, and derives each of the 17 Mac sets, held out, with 99.9% of fields within 1 px. Added 2026-09-29 |
| `Test-KmrpLayoutPatch.py` | macOS: every site of `macos/patches/kmrp-layout` against the clean `KOTOR_Exe` (expected bytes, lengths, overlaps), its values at 76 resolutions against the Windows rule, the stubs' disassembly and the single load-time initialiser. Added 2026-09-29 |
| `Test-MacInstaller.py` | macOS: `kmrp-mac.sh` install, status and uninstall into a stand-in game for a listed size and a blended one; what `kmrp-gameart` makes is installed at its sizes and not in the package; the executable, bundle and `swkotor.ini` byte-identical afterwards. Added 2026-09-29 |
| `Test-GameArt.py` | What both installers make from the player's game (the hex row frames, the tutorial popup's icons, `tutorial.2da`): `GameArtGenerator.cs` and `macos/tools/kmrp-gameart.c` byte for byte at every set height and more, both against an independent Python reference, the sizes every older set shipped, and the table changed in its `icon` column only. Needs the .NET 8 SDK. Added 2026-09-29 |

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
