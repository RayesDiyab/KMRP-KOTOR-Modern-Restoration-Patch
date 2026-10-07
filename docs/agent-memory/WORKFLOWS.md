# Workflows and verification

Run commands from the repository root in PowerShell unless a document says
otherwise. Generated files belong under ignored `build/`, `dist/`, or the system
temporary directory—not beside tracked sources.

## Before changing anything

1. Inspect status and the relevant diff; preserve unrelated changes.
2. Identify the authoritative source and generated consumers.
3. Record hashes before binary work.
4. Define a reproduction and a falsifiable acceptance check.
5. For time-sensitive state, query the current GitHub issue/release rather than
   relying on a memory snapshot.

## Build ladder

```powershell
# Optional module-only iteration. Both installer builds below compile it too
# since 2026-10-01; before that a stale module could be embedded unchanged.
& .\src\controller-native\build_native_runtime.cmd   # KMRP's module since 2026-10-04 (build.cmd, the old 245 KB one's, is removed)

# Fast patcher compilation using already-generated resources
.\build_kmrp.ps1 -ReuseResources

# Full resource regeneration (66 resolutions since 2026-09-29) and patcher build
.\build_kmrp.ps1
```

Both write `dist\KMRP - KOTOR Modern Restoration Patch.exe`, the one installer
(since 2026-09-29 it also installs for KOTOR Patch Manager; until then a second
installer, `dist\KMRP for KPM\KMRP for KPM.exe`, compiled with `KPM_EDITION`,
did); the two `.kpatch` files, `KMRP.kpatch` and `KOTOR 1 Native Controller Mod +
Xbox HUD.kpatch`, are built into `build\kmrp\kpm-patches\` and embedded in it
(`--export-kpm-patches <folder>` writes them out). The build compiles KOTOR Patch
Manager's runtime from the submodule (`src\kpm-runtime\build.cmd`, MSVC; `git
submodule update --init` in a fresh clone), assembles `windows-engine.bin` through
`tools/build_windows_engine.py`, and then:

- runs `src\controller-native\build_native_runtime.cmd` (KMRP's module, with the
  engine recipe and the resource bank; the bank is rebuilt unless
  `-ReuseResources` finds one) and `tools/build_native_kpatch.py`, which writes
  `KMRP.kpatch` and the installer's hook files in `build\kmrp\kpm-config\`;
- runs `src\controller-native\build_controller_standalone.cmd` (the controller
  patch's assets, then its module; needs `build-inputs\vanilla-gui`) and
  `tools/build_controller_kpatch.py --out ... --config-dir ...`, which writes the
  controller patch and its hooks beside KMRP's.

After a build run `.\testing\regression\Test-InstallerPatch.ps1`,
`python testing/regression/Test-KpatchSource.py` and
`python testing/regression/Test-ControllerKpatch.py` (the last reads
`dist\controller`, which `build_kmrp.ps1` does not write: see below).
A scratch install delivers the `.kpatch` files to the folder KOTOR Patch Manager's
settings name, which on the maintainer's PC is the play-test game's `patches` folder:
redirect `%APPDATA%\KPatchLauncher\settings.json` first, as `Test-InstallerPatch.ps1`
does. Steam-only facts: KPM needs its proxy deployment there, and SteamStub refuses
any changed executable (docs/kpm-edition.md).

**History of this ladder.** Until 2026-10-04 the build made four `.kpatch` files
with `tools/build_kpatch.py` (removed that day; its helpers are
`tools/kpatch_common.py`) and `Test-KpmEdition.ps1` (also removed) proved the
editions agreed; from 2026-10-04 to 2026-10-05 it made one patch; since 2026-10-05
two. The former `kmrp-sites.exe`, `--kpm-sites`, extracted-originals and gold-delta
steps were retired on 2026-10-01.

**The bank since 2026-10-05.** `tools/build_native_assets.py`
stores only what the module's blend helper does not write exactly, so it needs the x86
compiler: it runs inside `build_native_runtime.cmd`, or with `--helper` naming a helper
already built (`build\native-runtime\bank-helper\kmrp-guiblend.exe` after one build).
`--every-object` writes the old full bank, `--lzms` an LZMS one (smaller, slower at
every start; off). After a build also run
`python testing/regression/Test-NativeAssetsBank.py` (`--all` for every set, about ten
minutes). To time or compare a module without a whole build: replace
`patches\kmrp.dll` in a scratch install, set `debug-logs=1` in `configs\kmrp.ini`,
start the game and read the "interface files" line in `kmrp-kpm.log`; the files are in
the newest `%TEMP%\KMR*.tmp`. Only one copy of the game runs at a time: a second one
exits at once with code -1.

**The controller patch on its own (since 2026-10-05).** `build_kmrp.ps1` builds it
into the installer (above). To build and check the released package without the
installer:

```powershell
python tools\build_controller_assets.py --extract "C:\path\to\clean game"   # once: build-inputs\vanilla-gui
& .\src\controller-native\build_controller_standalone.cmd                   # assets, then the module
python tools\build_controller_kpatch.py --verify-clean build-inputs\swkotornopatch.exe
python testing\regression\Test-ControllerKpatch.py
```

It writes `dist\controller\KOTOR 1 Native Controller Mod + Xbox HUD.kpatch`. Install it in a scratch copy with
KOTOR Patch Manager's own launcher (`KPatchLauncher.exe <exe> --patches dist\controller
kmrp-controller --deployment proxy`, which also starts the game and did not touch
KPM's settings file). See `docs/controller-standalone.md`.

The required game-derived build inputs are ignored
`build-inputs/swpc_tex_gui.erf` and, for the controller patch,
`build-inputs/vanilla-gui` (the `--extract` line above). The Windows engine recipe builds from source;
no game executable or gold snapshot is required. Machine overrides belong in ignored
`build.local.ps1`; copy `build.local.example.ps1` as the template.

## Baseline checks

```powershell
.\testing\regression\Test-ReinstallOverOlderBuild.ps1
.\testing\regression\Test-InstallerPatch.ps1
python .github/scripts/check_links.py
```

The regression test uses throwaway copies under the system temp directory. It must
never target the live installation.

## Executable-change ladder

1. Read `reverse-engineering/exe-patching.md` and the relevant subsystem record.
2. Patch a named copy, or the live executable after copying it aside and recording
   its length and SHA-256 (AGENTS.md); verify every expected original byte before
   writing.
3. Assert output length and section layout.
4. Disassemble injected code from the bytes actually written.
5. Re-read every KMRP PE section, including sections the change did not target.
6. Generate representative outputs at low, common, ultrawide, and high-DPI
   resolutions and read back the patched constants.
7. Run:

```powershell
python tools/build_binary_inventory.py build-inputs/swkotornopatch.exe build/kmrp/<final-gold>.exe
```

   Then again with `--installed` and the installer's `--apply` output at every
   resolution, which also inventories the bytes the patcher writes where gold
   keeps vanilla (`reverse-engineering/binary-inventory.md` §2).

8. Run the full build and installer regression.
9. Update the subsystem reference, binary inventory, patch record where applicable,
   and `CHANGELOG.md`.

## GUI/resource-change ladder

1. Determine whether geometry comes from the upstream resolution layout, gold
   geometry transfer, or a dedicated generator.
2. Change the owning source or generator, not one generated archive.
3. Regenerate resources.
4. Inspect the actual archive contents and numeric extents.
5. Check at least one low resolution, 1920×1080, 3440×1440, 3840×2160, and a
   representative ultrawide when the affected subsystem is aspect-sensitive.
6. Separate numeric/archive verification from play-testing; report both explicitly.

## Release readiness

- `CHANGELOG.md` contains an accurate Unreleased section.
- Version strings, embedded resource metadata, file properties, and release notes
  agree.
- Full build and regression checks pass.
- Documentation link check passes.
- Output hashes are recorded where the project standard requires them.
- The clean repository contains no proprietary inputs or generated binaries.
- Installation, reinstall, rollback, and restore have been exercised on throwaway
  copies.
- Public issue and compatibility claims match what was actually verified.
