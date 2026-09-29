# Project orientation

## Purpose

KMRP is a resolution-aware interface and engine restoration patch for the 2003 PC
release of *Star Wars: Knights of the Old Republic*. It generates resources for 49
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

override-common.zip + gui-<resolution>.zip (the 49 embedded as one pool of
    distinct files since 2026-09-25; tools/pack_resolution_layouts.py)
    -> game Override directory with a hash-backed restore manifest
```

Two editions from one build since 2026-09-28. The standalone above; and KMRP for
KPM, the same installer compiled with KPM_EDITION, which leaves swkotor.exe
unmodified and writes kmrp-kpm.dat (the same final bytes, as a diff from the
clean executable) for KMRP's module to apply in memory under KOTOR Patch
Manager, relocating gold's eleven sections. In KPM it is four patches, one per
fix: KMRP (required, self-contained: it carries the memory fixes and, on the
editable 1.03 executable, the 4 GB flag), KMRP Controller, KMRP Movies, KMRP Map
Notes; each hook's patch is `kpm_patch` in kotor1.hooks.toml. It supports the
editable 1.03 executable (761F9466…, which KPM keys `kotor1_cdcrack_103`) and
Steam's swkotor.exe (34E6D971…, decrypted identical to it); the standalone
supports the editable executable only. GOG's own v1.03 (9C10E045…) is a different
file -- see reverse-engineering/map-scaling.md.
See docs/kpm-edition.md.

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

