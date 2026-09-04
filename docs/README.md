# Documentation

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it — measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

Design and build documentation. Engine analysis lives one level over, in
[`reverse-engineering/`](../reverse-engineering/README.md).

| Document | What it covers |
| --- | --- |
| [documentation-standard.md](documentation-standard.md) | **The standard every document here is held to.** Read before writing or updating one: what counts as measured, how sites are tabulated, why rejected alternatives and corrections stay visible, and the checklist to run before committing. |
| [universal-resolution-math.md](universal-resolution-math.md) | How one patcher covers 48 resolutions: the executable fields that hold screen geometry, the coordinate math, how the per-resolution GUI archives are packaged, reproduction steps, and **which resolutions have actually been play-tested** as opposed to generated. |
| [font-scaling.md](font-scaling.md) | The font, dialogue-letterbox and list-row scaling work, and the **gold snapshot chain** — every reference executable with its SHA-256 and what it added. Start here to rebuild or verify a gold snapshot. |
| [patcher-ui-build.md](patcher-ui-build.md) | The Windows patcher itself: UI state machine, proportional resize, icon pipeline, embedded resources, build process, transaction safety, and the release checklist. |
| [third-party-driver-compat.md](third-party-driver-compat.md) | **K1 Modern Driver Compatibility**, bundled with Synchro's permission and installed unless turned off: what it fixes on each vendor, every byte it writes, and the reproducible check that none of its eight sites collides with anything KMRP writes — 0 of 8 collide, and 8 of 8 still hold the bytes it expects. |
| [phase-0-plan.md](phase-0-plan.md) | The original proof plan for the map fix — the project's first milestone. Kept as a record of how the work was scoped. |
| [technical-reconstruction/](technical-reconstruction/) | A long-form technical reconstruction of the gold build: the Word document, a PDF render, and page images used to proof it. |

## Where to start

- **Playing, not building?** The [main README](../README.md) is all you need.
- **Adding a resolution?** `universal-resolution-math.md`, then
  `GROUPS` in `tools/prepare_universal_resources.py`.
- **Changing an engine constant?** Read
  [exe-patching.md](../reverse-engineering/exe-patching.md) first, then the
  document for that subsystem.
- **Rebuilding a gold snapshot?** The chain table in `font-scaling.md`.
