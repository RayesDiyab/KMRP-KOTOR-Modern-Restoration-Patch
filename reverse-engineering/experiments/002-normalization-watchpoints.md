# Experiment 002: Normalization Fields and Blue-Icon Path

> **Documentation standard.** This document follows
> [`docs/documentation-standard.md`](../../docs/documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.


## Goal

Find the instructions that write and read the map object's `+0x0C` and `+0x10`
fields, then determine which read path controls the unresolved blue icons and
whether the same path supplies clickable hitboxes.

## Preconditions

- Use only `swkotor_phase0_ultrawide.exe`.
- Confirm SHA-256
  `D7DD19449F1BA2DE1D91D19E1BAA4BE15A7480AE4C9ED7F986DE5E2424E97909`.
- Disable automatic TLS-callback breaks in x32dbg.
- Reach a saved game at 3440x1440 with the known 1720x720 map patch active.
- Do not apply any disk patch.

## Procedure

1. Break at map initialization `0x00694D50` and capture the map-object pointer.
2. Set hardware write breakpoints on `[map_object+0x0C]` and
   `[map_object+0x10]` before initialization completes.
3. Record every writer, written value, call stack, and timing.
4. Replace the write breakpoints with read breakpoints immediately before the
   map is opened.
5. Classify each reader as map rendering, yellow selected icon, blue icon,
   waypoint/party icon, or input/hit testing.
6. At the division in `0x006943D0`, test 440 and 256 as temporary in-memory
   divisors without changing the 1720x720 render dimensions.
7. Compare visual positions and click response before and after the temporary
   change, then restore original memory.

## Evidence required

- Exact instruction addresses and original bytes for every relevant writer/read.
- Map-object pointer and field values at map open.
- Call stacks for yellow and blue icon paths.
- Screenshots showing icon position before/after.
- Separate hitbox results for every visible map button/control tested.

## Stop conditions

- Stop on any unexpected exception or if the live `swkotor.exe` is loaded.
- Do not save a patched executable during this experiment.
