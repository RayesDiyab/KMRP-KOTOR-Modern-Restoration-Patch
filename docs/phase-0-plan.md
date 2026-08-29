# Phase 0: Map Fix Proof Plan

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
