# Phase 0: Map Fix Proof Plan

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


*Historical plan, labelled 2026-09-24.* This is the first-week plan for the 3440×1440
map fix, committed on 2026-08-29 and kept as written below. The coordinates it
names were true of that build. The current map model sizes the map from each
resolution (overlay W/2, canvas height H/2; at 3440×1440 those are still
1720×720). It is described in
[map-scaling.md](../reverse-engineering/map-scaling.md).

The last box below is half done. The map geometry is now generated for all 49
resolutions and read back from the installer's own `--apply` output. The
record does not say whether the map has been seen in play at any resolution
other than 3440×1440 since the model changed.

## Goal

Preserve and verify the known executable patch that enlarges and centers the map,
then solve the remaining icon/button positioning and clickable-hitbox problem at
3440x1440. Generalize the coordinate logic only after the known case is correct.

## Completed sequence

1. Verify the four known map-size/centering byte changes against clean and
   patched executable hashes.
2. Confirm the source coordinate domain is 440x256 while the resized map-control
   domain is 1720x720.
3. Separate the selected note, object-marker, party-marker, and player-arrow
   full-map call sites from the shared gameplay minimap conversion code.
4. Confirm the marker coordinates also build the marker GUI rectangle.
5. Reject the broad shared-transform candidate because it breaks the minimap
   and fog grid.
6. Validate the isolated call-wrapper candidate and record exact source bytes,
   payload hash, output hash, and visual behavior.

## Go/no-go proof

- [x] The known 1720x720 map renders centered at 3440x1440.
- [x] Player, party, waypoint, and map-circle visuals align with the map.
- [x] Marker GUI rectangles share the corrected coordinates.
- [x] Gameplay minimap and full-map fog/grid behavior remain intact.
- [x] The relevant code path and original bytes are documented.
- [x] The patch builder recognizes all source bytes and writes to a new file.
- [ ] Validate additional resolutions and executable builds before release.
