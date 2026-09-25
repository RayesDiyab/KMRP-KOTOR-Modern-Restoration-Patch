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
run and pass. Both use their own fixture executable names, so an NVIDIA
profile made for them cannot match a real `swkotor.exe`. `Test-DpiCompatibility.ps1` and
`Test-NvidiaPresentMethod.ps1` write per-user compatibility and NVIDIA profile
state for their throwaway executables and remove it again, so run them
knowingly:

| Script | What it pins |
| --- | --- |
| `Test-ControllerSupport.ps1` | Controller install and restore ownership, the installed hook table against the source, foreign-file refusal, controller-only, driver-only and default installs, and an edited `kmrp-controller.ini` surviving restore and reinstall |
| `Test-DpiCompatibility.ps1` | The per-executable Windows DPI setting, and restoring exactly what was there |
| `Test-LargeAddressAware.ps1` | Both accepted inputs, one with the LAA bit already set, give the same output and restore byte for byte |
| `Test-MovieResolution.ps1` | The four movie-mode operands and the render-resolution operands, read back at four resolutions |
| `Test-NvidiaPresentMethod.ps1` | The NVIDIA present-method step: when it writes, when it leaves the player's choice alone, and restore (dot-sources `Restore-TestNvidiaProfiles.ps1`; `NvidiaPresentSelfTest.cs` is its compiled self-test) |
| `Test-ControllerPromptAssets.py` | Every prompt texture and control mapping in all 49 archives, four controller families, and the Controller Layout screen |
| `Test-GeneratedGuiGeometry.py` | The reported GUI repairs and the active HUD in all 49 archives, the R3 cue included |
| `Test-FontAtlasScale.py` | Every packaged font atlas draws one texel per pixel |
| `Test-ProtonResourceCompatibility.py` | Case-exact, collision-free resource names for Linux / Proton |
| `Test-ReinstallOverOlderBuild.ps1` | Reinstalling a newer build over an older one replaces the executable instead of skipping it; reinstalling the same build changes nothing; an unsupported executable is refused; a damaged backup blocks a patch. |
| `Test-UpdateCheck.ps1` | The installer's update check: release-tag parsing, the version comparison (a 2.x tag would be "newer" than 1.5.0), and "Don't remind me again for <version>" through the real `settings.json`, put back byte for byte. `-Live` asks GitHub once (informational); `-RenderTo` draws the dialog to a PNG. `UpdateCheckSelfTest.cs` is its compiled self-test |

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
