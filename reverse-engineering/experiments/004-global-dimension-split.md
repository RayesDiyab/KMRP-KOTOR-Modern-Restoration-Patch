# Experiment 004: Split Full-Map and HUD Map Dimensions

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


> **Superseded.** This records what was tried, not what ships. Gold v15 sets the
> four constructor immediates globally and leaves `0x00633102` unredirected; the
> gameplay minimap is kept correct by the later `.kmz` / `.kfg` work instead.
> Verified against the shipped binary on 2026-09-03 -- see `../map.md`.

## Goal

Keep the universal marker-coordinate and hit-test fix while preventing the
enlarged full-map dimensions from changing the gameplay HUD minimap.

## Inputs and output

- Source: `swkotor_phase0_icon_candidate_006.exe`
- Source SHA-256: `3C73627AEEE967BD780AFEA108A6AB2EC4EA6EAF345E15727E081F945506DBD2`
- Output: `swkotor_phase0_map_final.exe`
- Output SHA-256: `E3228D43C9DAB66FE349BD2E777EAC6F764CBE2475E8DB23288DEF94B10CF885`
- Test resolution: 3440x1440 fullscreen

## Change

The four shared constructor immediates at `0x0069505C`, `0x00695064`,
`0x00695082`, and `0x0069508A` are restored to their retail values
(512x256 render and 440x256 marker domains). The full-map constructor caller
at `0x00633102` is redirected to a `.kui` wrapper. The wrapper calls
`0x00694D50`, then assigns 1720x720 to the full-map object's normalization and
render fields and to its map-canvas/marker-overlay child rectangles.

Candidate 007 and 008 tried the other constructor call site and/or reset child
fields there; both left the HUD duplication in place. The `0x00633102` split is
the first version that isolates the enlarged dimensions to the full-map path.

## Results

1. Full-map Ebon Hawk rendering remained enlarged and centered.
2. Markers and the player arrow retained candidate-006 placement and click
   behavior.
3. The gameplay HUD showed one normal-sized minimap instead of the duplicated
   enlarged map seen in candidate 006.
4. No source module waypoint data was changed; Ebon Hawk's stock Engine Room
   and Swoop Hangar note positions therefore remain content-data positions.

## Conclusion

The global-dimension split is the release candidate for the universal EXE
patch. It separates the shared HUD constructor defaults from the full-map
instance while preserving the resolution-neutral coordinate and hit-test
wrappers.
