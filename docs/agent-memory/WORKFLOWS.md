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
& .\src\controller-native\build.cmd

# Fast patcher compilation using already-generated resources
.\build_kmrp.ps1 -ReuseResources

# Full resource regeneration (66 resolutions since 2026-09-29) and patcher build
.\build_kmrp.ps1
```

Both write `dist\KMRP - KOTOR Modern Restoration Patch.exe`, the one installer
(since 2026-09-29 it also installs for KOTOR Patch Manager; until then a second
installer, `dist\KMRP for KPM\KMRP for KPM.exe`, compiled with `KPM_EDITION`,
did); the four `.kpatch` files are built into `build\kmrp\kpm-patches\` and
embedded in it (until later on 2026-09-29 they shipped in `dist\KPM patches\`;
`--export-kpm-patches <folder>` writes them out). The relocation step
needs Capstone (`requirements.txt`) and stops the build if its two methods
disagree. Since 2026-09-29 the build also compiles KOTOR Patch Manager's runtime
from the submodule (`src\kpm-runtime\build.cmd`, MSVC; `git submodule update
--init` in a fresh clone). Since 2026-10-01 it assembles
`windows-engine.bin` through `tools/build_windows_engine.py`, compiles the
controller module, then runs `tools/build_kpatch.py`, which writes the `.kpatch`
files and config sections and verifies their hooks against the tracked table
and source engine guards. **Correction:** the former `kmrp-sites.exe`,
`--kpm-sites`, extracted-originals and gold-delta steps are retired. After a build,
`.\testing\regression\Test-KpmEdition.ps1` proves the editions agree; put Steam's
unmodified `swkotor.exe` at `build-inputs\swkotor-steam.exe` to include its Steam
case. Steam-only facts: KPM needs its proxy deployment there, and SteamStub refuses
any changed executable (docs/kpm-edition.md).

The only required game-derived build input defaults to ignored
`build-inputs/swpc_tex_gui.erf`. The Windows engine recipe builds from source;
no game executable or gold snapshot is required. Machine overrides belong in ignored
`build.local.ps1`; copy `build.local.example.ps1` as the template.

## Baseline checks

```powershell
.\testing\regression\Test-ReinstallOverOlderBuild.ps1
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
