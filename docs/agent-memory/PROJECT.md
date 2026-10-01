# Project orientation

## Purpose

KMRP is a resolution-aware interface and engine restoration patch for the 2003 PC
release of *Star Wars: Knights of the Old Republic*. It generates resources for 66
resolutions from 800×600 through 15360×8640, blends other supported sizes at install,
and applies source-built engine fixes in memory plus Override resources.

The first public release is KMRP 1.0, tagged `v2.10.0` (its internal number;
its Properties → Details say 2.7.0.0). The build in progress is KMRP 1.5, installer
version 1.5.0. Do not assume that remains the latest release; verify tags, releases,
`CHANGELOG.md`, and `GoldPatch.PatchVersion` for release work. `build_kmrp.ps1`
refuses to compile unless `AssemblyInfo.cs` carries the same version.

## Architecture

Since 2026-10-01 the normal Windows build uses tracked source sites and assembly
emitters (`tools/build_windows_engine.py`, `src/patcher/WindowsEnginePatch.cs`)
without a clean EXE or gold snapshot. See [the current source build](../windows-engine-source.md).

```text
tracked source sites + x86 emitters
    -> windows-engine.bin
    -> ResolutionPatch constants for the selected resolution
    -> kmrp-kpm.dat
    -> guarded, relocated memory writes when KPM loads patches/kmrp.dll

override-common.zip + gui-<resolution>.zip (the 66 embedded as one pool of
    distinct files since 2026-09-25; tools/pack_resolution_layouts.py)
    -> game Override directory with a hash-backed restore manifest
```

*Correction, 2026-10-01:* this overview previously described the retired standalone
gold-delta build and 49 resolutions. The source recipe is now the normal build;
historical snapshots and the optional `--apply` reference command remain separate.

**Since 2026-09-29 KMRP's installer does not write gold into swkotor.exe.** It is
the KPM edition's install plus KOTOR Patch Manager's runtime (KPM's binkw32.dll
proxy and KotorPatcher.dll, built from the submodule by src/kpm-runtime/build.cmd)
with KMRP's four patches, so one installer serves the editable 1.03 executable and
Steam's; on the editable one it sets only the 4 GB bit, leaving KPM a KPM-format
backup of the unmodified file and kpm_install_state.json first -- KPM knows a game
only by its exe hash, and refused the flagged one without them (measured with
KPM 0.7.1's launcher, 2026-09-29). It upgrades a standalone
install through the standalone's own restore. For a folder holding KPM's own
runtime it installs for KPM instead (an Advanced Settings option that also chose
this was removed on 2026-09-30) (no runtime; the player ticks the .kpatch files, which the installer
carries and puts in KPM's patch folder -- from KPM's settings -- or a "KPM patches"
folder in the game folder) -- what the separate KMRP for KPM installer did until
the same day. `--apply` now builds an offline reference from the source recipe. The
current diagram above describes the runtime path. See docs/kpm-edition.md 1a.

Historically two editions were built from one source since 2026-09-28: standalone
and KMRP for KPM, compiled with KPM_EDITION. They became one installer on
2026-09-29. The KPM route leaves swkotor.exe
unmodified on Steam and writes kmrp-kpm.dat from the source recipe for KMRP's
module to apply in memory under KOTOR Patch Manager, relocating eleven pages.
In KPM it is four patches, one per
fix: KMRP (required, self-contained: it carries the memory fixes and, on the
editable 1.03 executable, the 4 GB flag), KMRP Controller, KMRP Movies, KMRP Map
Notes; each hook's patch is `kpm_patch` in kotor1.hooks.toml. It supports the
editable 1.03 executable (761F9466…, which KPM keys `kotor1_cdcrack_103`) and
Steam's swkotor.exe (34E6D971…, decrypted identical to it), and since 2026-09-30
GOG's own v1.03 (9C10E045…): the editable file with its 16-byte "Hellspawn Reborn"
header watermark zeroed, measured by hash (GameExecutable in KmrpPatcher.cs; see
reverse-engineering/map-scaling.md). The patcher's step 2 names which of the three it
found.
See docs/kpm-edition.md.

- `src/patcher/KmrpPatcher.cs` contains the Windows patcher, executable validation,
  resolution constants, INI/Override installation, backup/restore logic, settings,
  and UI.
- `src/controller-native/` is the controller module -- KMRP's native path plus
  Saul0097's files as modified by KMRP, built by `build.cmd` into
  `kmrp-controller.module`, which the installer embeds with SDL 3 and, since
  2026-09-29, the KPM runtime `src/kpm-runtime/build.cmd` builds from the
  submodule (until then a prebuilt one from `third_party/`).
- `tools/` contains binary builders, resource generators, inspection utilities,
  and verification scripts.
- `assets/override-3440x1440/` is the hand-tuned gold GUI/art source.
- `third_party/Included/kotor-high-resolution-menus-1.5/` supplies upstream
  per-resolution GUI layouts.
- `build-inputs/` holds ignored, user-supplied game inputs.
- `build/` and `dist/` are ignored generated outputs.
- `docs/` holds design/build references; `reverse-engineering/` holds engine lab
  records, subsystem references, and machine-readable patch records.
- `testing/` holds installer regression and virtual-display support.

## Authority order

When sources disagree, use this order and document the discrepancy:

1. bytes measured from the identified clean, gold, or generated artifact;
2. current implementation and generated output;
3. subsystem reference document;
4. experiment/lab record;
5. agent memory, issue prose, comments, or recollection.

`README.md` describes the player-facing product. `CONTRIBUTING.md` defines the
engineering contract. `docs/documentation-standard.md` defines evidence quality.

## Product invariants

- The supported clean executable is identified by both length and SHA-256.
- Apply, rollback, reinstall, and restore must remain fail-closed and predictable.
- KMRP must not silently destroy or claim ownership of files it did not install.
- Optional third-party components retain their licences, attribution, permissions,
  version identity, and independent restore behavior.
- Generated GUI resources and executable constants must agree at every supported
  resolution, not only at 3440×1440.
- Player-facing compatibility guidance must distinguish measured support, expected
  compatibility, known limitations, and untested configurations.
