# Project orientation

## Purpose

KMRP is a resolution-aware interface and engine restoration patch for the 2003 PC
release of *Star Wars: Knights of the Old Republic*. It generates resources for 48
resolutions from 800×600 through 15360×8640 and applies a verified executable delta
plus resolution-specific constants and Override resources.

The first public release is KMRP 1.0, tagged `v2.10.0` (its internal number;
its Properties → Details say 2.7.0.0). The build in progress is KMRP 1.5, installer
version 1.5.0. Do not assume that remains the latest release; verify tags, releases,
`CHANGELOG.md`, and `GoldPatch.PatchVersion` for release work. `build_kmrp.ps1`
refuses to compile unless `AssemblyInfo.cs` carries the same version.

## Architecture

```text
verified clean swkotor.exe + embedded gold delta
    -> gold engine-fix image
    -> ResolutionPatch constants for the selected resolution
    -> patched swkotor.exe

override-common.zip + gui-<resolution>.zip
    -> game Override directory with a hash-backed restore manifest
```

- `src/patcher/KmrpPatcher.cs` contains the Windows patcher, executable validation,
  resolution constants, INI/Override installation, backup/restore logic, settings,
  and UI.
- `src/controller-native/` is the controller module -- KMRP's native path plus
  Saul0097's files as modified by KMRP, built by `build.cmd` into
  `kmrp-controller.module`, which the installer embeds with the prebuilt KPM
  runtime and SDL 3 from `third_party/`.
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

