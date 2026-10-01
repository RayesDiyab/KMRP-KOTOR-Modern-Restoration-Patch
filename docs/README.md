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
| [agent-memory/](agent-memory/) | Repository-local guidance for coding agents: project orientation, task routing, build and verification workflows, durable cross-cutting discoveries, and the boundary between shared knowledge and ignored workstation state. |
| [universal-resolution-math.md](universal-resolution-math.md) | How one patcher covers 66 resolutions: the executable fields that hold screen geometry, the coordinate math, how the per-resolution GUI archives are packaged, reproduction steps, and **which resolutions have actually been play-tested** as opposed to generated. |
| [font-scaling.md](font-scaling.md) | The font, dialogue-letterbox and list-row scaling work, and the **gold snapshot chain** — every reference executable with its SHA-256 and what it added. Start here to rebuild or verify a gold snapshot. |
| [patcher-ui-build.md](patcher-ui-build.md) | The Windows patcher itself: UI state machine, proportional resize, icon pipeline, embedded resources, build process, transaction safety, and the release checklist. |
| [windows-engine-source.md](windows-engine-source.md) | Current source-built Windows engine recipe: no clean EXE or gold input, all 81 byte-guard runs, eleven relocatable pages, package checks, and the measured Ubuntu cross-build. |
| [windows-dpi-scaling.md](windows-dpi-scaling.md) | Why Windows display scaling can zoom KOTOR a second time, the per-executable compatibility value KMRP manages, exact restore ownership rules, and the tested/untested matrix. |
| [nvidia-present-method.md](nvidia-present-method.md) | The NVIDIA "Vulkan/OpenGL present method" the patcher sets for `swkotor.exe` when the driver would otherwise show it half-drawn frames: the setting and value, when it writes and when it leaves the player's choice alone, restore ownership, and the tested/untested matrix. |
| [third-party-driver-compat.md](third-party-driver-compat.md) | **K1 Modern Driver Compatibility**, bundled with Synchro's permission and installed unless turned off: what it fixes on each vendor, every byte it writes, and the reproducible check that none of its eight sites collides with anything KMRP writes — 0 of 8 collide, and 8 of 8 still hold the bytes it expects. |
| [controller-support.md](controller-support.md) | The controller component -- on by default since 2026-09-24 -- its provenance and build, installed files, hook sites, prompt families and validation. |
| [controller-native-path.md](controller-native-path.md) | How the native path works: the joystick device KOTOR's console input expects, the mapping, focus navigation, the camera, the tab bar, input classes, movies and the action bar. |
| [controller-behaviour-matrix.md](controller-behaviour-matrix.md) | What every input does on every screen, as measured, with what has changed since the measurement. |
| [controller-parity.md](controller-parity.md) | The native path against the legacy keyboard path, button by button, and the gameplay verbs. |
| [controller-prompt-specification.md](controller-prompt-specification.md) | Which button prompt appears where, and the rules for placing it. |
| [controller-playtest-checklist.md](controller-playtest-checklist.md) | The physical-pad checklist, with each dated pass on a real controller. |
| [controller-handover-plan.md](controller-handover-plan.md) | Which parts of the legacy path the native one has replaced, as the basis for removing them. |
| [controller-sdl-backend.md](controller-sdl-backend.md) | Current hybrid XInput/SDL backend, x86 dependency, normalization, rumble, ownership and outstanding runtime/hardware validation. |
| [controller-layout.md](controller-layout.md) | Controller Layout resource generation, custom panel callbacks and ownership, lifecycle trace, and manual acceptance test. |
| [v1.5-development-validation.md](v1.5-development-validation.md) | Dated development checks and issue disposition, including the 2026-10-01 Ubuntu/Proton evidence and driver-component clarification for issue 15. |
| [controller-planned-work.md](controller-planned-work.md) | Controller work agreed but not yet written: the Guide button (blocked by an XInput bit collision), virtual-pad slot safety, and bumper tab cycling. Its hint-icon section shipped as the R3 cue. |
| [windows-changes-from-macos.md](windows-changes-from-macos.md) | Changes the macOS build made first and Windows still needs: popups fitted to their contents, any resolution, and the shared build fixes to check on Windows. |
| [macos-changes-from-windows.md](macos-changes-from-windows.md) | The other direction: changes made on Windows first that the macOS build still needs or has to build and check -- badges and HUD boxes drawn for a blended size, the installer's second step, and KOTOR Patch Manager recognising the install as it does on Windows. |
| [linux-proton-steam-deck.md](linux-proton-steam-deck.md) | Linux/Proton procedure, measured Ubuntu install/restore and limited gameplay, package audit and report collector, with stable Proton, Steam Deck and remaining hardware tests explicitly unverified. |
| [large-address-aware.md](../reverse-engineering/large-address-aware.md) | The exact one-bit PE-header change that enables a 4 GB virtual address space on 64-bit Windows, strict recognition of an already-LAA clean executable, and byte-for-byte restore behavior. |
| [kpm-edition.md](kpm-edition.md) | **KMRP on KOTOR Patch Manager's runtime**: since 2026-09-29 KMRP's one installer, which installs KPM's runtime and proxy itself and never rewrites swkotor.exe, or installs for KOTOR Patch Manager when KPM manages the game (section 1a; until then the separate KMRP for KPM did that); both ways as four patches, one per fix (KMRP, Controller, Movies, Map Notes), for the editable 1.03 executable and **Steam's own**. The runtime's build is in [src/kpm-runtime/README.md](../src/kpm-runtime/README.md). The relocation table that moves KMRP's code (46 fields, each with its instruction), the data file and the unmodified bytes it is built from, the applier, the `.kpatch` files and their measured conflicts, Steam's DRM and timing, and the proof that it makes the same game as the standalone. |
| [mod-build-compatibility.md](mod-build-compatibility.md) | Supported executable variants, K1CP/K1R and KOTORganizer install order, KotOR Patch Manager's hash boundary, and measured limits for other executable patchers. |
| [phase-0-plan.md](phase-0-plan.md) | The original proof plan for the map fix — the project's first milestone. Kept as a record of how the work was scoped. |
| [technical-reconstruction/](technical-reconstruction/) | A long-form technical reconstruction of the gold build: the Word document, a PDF render, and page images used to proof it. |

## Where to start

- **Playing, not building?** The [main README](../README.md) is all you need.
- **Starting an agent task?** Read the root [`AGENTS.md`](../AGENTS.md), then use
  the routing table in [`agent-memory/README.md`](agent-memory/README.md).
- **Adding a resolution?** `universal-resolution-math.md`, then
  `GROUPS` in `tools/prepare_universal_resources.py`.
- **Changing an engine constant?** Read
  [exe-patching.md](../reverse-engineering/exe-patching.md) first, then the
  document for that subsystem.
- **Rebuilding a gold snapshot?** The chain table in `font-scaling.md`.
