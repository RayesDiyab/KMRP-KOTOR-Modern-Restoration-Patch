# Experiment 003: Isolated Full-Map Coordinate and Hit-Test Wrappers

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


## Goal

Scale the resized full-map markers, player arrow, and marker hitboxes without
changing the shared conversion code used by the gameplay minimap and fog grid.

## Inputs

- Source: `swkotor.exe.backup-before-map-icons-20260827-125908.bak`
- Source SHA-256:
  `D7DD19449F1BA2DE1D91D19E1BAA4BE15A7480AE4C9ED7F986DE5E2424E97909`
- Confirmed output: `swkotor_phase0_icon_candidate_006.exe`
- Output SHA-256:
  `3C73627AEEE967BD780AFEA108A6AB2EC4EA6EAF345E15727E081F945506DBD2`
- Resolution: 3440x1440 fullscreen
- Map canvas: 1720x720
- Marker overlay: 1478x720
- Save: Kashyyyk, The Great Walkway
- Stock comparison save: Ebon Hawk (`ebo_m12aa`)

## Candidate progression

1. Candidate 002 made the marker overlay 1720 pixels wide and over-scaled X.
2. Candidate 003 used a 1478-pixel overlay but also changed the wrapper divisor
   to 512, applying the horizontal correction twice and under-scaling X.
3. Candidate 004 paired the 1478-pixel overlay with the original 440-unit
   marker domain. Marker and player placement became correct, but visible
   markers remained unclickable because the overlay hit test still received
   full-window mouse coordinates.
4. Candidate 005 keeps candidate 004's drawing math and redirects the map
   overlay's custom hit-test vfunc through a centered-coordinate wrapper.
5. Candidate 006 retains candidate 005's rendering and adds the measured
   14-pixel Y correction to the hit-test wrapper, aligning clickable rectangles
   with the rendered marker centers.

## Confirmed patch

The builder adds an executable/readable `.kui` section at `0x0086D000`:

- `+0x000`: world-to-map coordinate wrapper
- `+0x080`: cached party/player coordinate wrapper
- `+0x100`: map-overlay hit-test wrapper

The marker coordinate wrappers call the original conversion functions and
scale successful integer outputs through the 1478x720 marker overlay. The
overlay width is `round(1720 * 440 / 512)`, so its original 440-unit X domain
maps onto the complete 1720-pixel map canvas without modifying shared map or
minimap transforms.

The vtable entry at `0x0075477C` originally points to the overlay hit test at
`0x00693300`. Candidate 006 redirects it to `0x0086D100`. The wrapper reads the
owning `CUIMap` through overlay offset `+0x34`, reads the embedded map canvas at
owner offset `+0x1080`, and translates incoming mouse coordinates by:

```text
local_x = mouse_x - (window_width  - canvas_width)  / 2
local_y = mouse_y - (window_height - canvas_height) / 2 + 14
```

It then tail-jumps to the original hit test. At 3440x1440 with a 1720x720
canvas this derives `(860, 360)` at runtime, then applies the measured 14-pixel
render-viewport top inset to Y; the centering values are not hard-coded.

## Results

1. The executable reached the main menu and loaded the Kashyyyk autosave.
2. The gameplay minimap and full-map grid retained their prior behavior.
3. Map notes, blue points, and the player arrow aligned with map geometry.
4. Cycling notes with the left/right arrows continued to work.
5. Runtime inspection found note hitboxes at overlay-local coordinates such as
   `(772,97,14,14)` and `(635,196,14,14)`.
6. Before the hit-test wrapper, those stale local screen positions selected the
   notes while clicking their rendered positions did nothing.
7. With candidate 005, clicking the corresponding rendered points selected
   them directly. The yellow selection moved and the note text changed to
   `To Rwookrrorro Village`, then `Supply Station`.
8. Candidate 006's visible-center probes selected `Basket to the Shadowlands`
   and `To Rwookrrorro Village`, confirming the remaining upward hitbox offset
   was removed.
9. A clean-code Ebon Hawk run exposed the stock note-control rectangles before
   any coordinate scaling. Their centers are `(131,98)`, `(144,172)`,
   `(228,17)`, `(284,182)`, `(319,92)`, `(217,244)`, and `(274,110)` in the
   original 440x256 marker domain.
10. The stock Engine Room center is `(217,244)` and is visibly below the white
   engine-room shape even in the unpatched executable. The stock Swoop Hangar
   note likewise sits on the outer hull. Candidate 006 preserves and scales
   these source positions; it does not introduce either displacement.

## Ebon Hawk content-data caveat

The supplied annotated 512x256 reference image uses hand-positioned room
centers that differ from the game's module waypoint data. For example, its
Engine Room marker is approximately `(219,232)` in texture space, whereas the
game's Ebon Hawk waypoint converts to approximately `(252,244)` in texture
space and `(217,244)` in the 440x256 marker domain.

Changing the universal wrapper to force the annotated positions would distort
correct coordinates on every other module. If room-center markers are desired,
that must be implemented as a separate Ebon Hawk module-data correction, not as
part of the resolution-neutral EXE scaling patch.

## Conclusion

Candidate 006 is the confirmed 3440x1440 Phase 0 map-marker and hitbox scaling
patch. It faithfully preserves module-authored note positions, including stock
placement defects in the Ebon Hawk data.
Candidates 002 and 003 are rejected scaling experiments; candidate 004 proves
the final placement math but lacks the required input translation.
